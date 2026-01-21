"""
Question generation service using OpenAI GPT 5.2 API.

Generates BCBA exam questions from pre-processed content.
Uses AsyncOpenAI client with structured outputs for reliable JSON responses.
"""

import json
import random
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config.constants import ContentArea, QuestionType
from src.config.logging import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


# Pydantic models for structured outputs
class QuestionOptions(BaseModel):
    """Answer options for quiz questions.

    For multiple choice: use A, B, C, D
    For true/false: use True_, False_ (which serialize as True/False)
    """

    # Multiple choice options
    A: Optional[str] = Field(None, description="Option A text for multiple choice questions")
    B: Optional[str] = Field(None, description="Option B text for multiple choice questions")
    C: Optional[str] = Field(None, description="Option C text for multiple choice questions")
    D: Optional[str] = Field(None, description="Option D text for multiple choice questions")
    # True/false options (use alias for JSON serialization)
    True_: Optional[str] = Field(None, alias="True", description="True option for true/false questions")
    False_: Optional[str] = Field(None, alias="False", description="False option for true/false questions")

    model_config = {"populate_by_name": True}


class SourceCitation(BaseModel):
    """Citation from source material for question verification."""

    section: Optional[str] = Field(
        None,
        description="Document section or task list item (e.g., 'Task List F-1', 'Ethics Code 2.09')"
    )
    heading: Optional[str] = Field(
        None,
        description="Section heading or topic name"
    )
    quote: Optional[str] = Field(
        None,
        description="Brief relevant quote from source (max 50 words)"
    )


class GeneratedQuestion(BaseModel):
    """A single generated quiz question."""

    question: str = Field(description="The question text")
    type: Literal["multiple_choice", "true_false"] = Field(description="Question type")
    options: QuestionOptions = Field(
        description="Answer options. For multiple_choice use A/B/C/D, for true_false use True/False"
    )
    correct_answer: str = Field(
        description="The correct answer key only (A, B, C, D for multiple choice, or True/False for true/false)"
    )
    explanation: str = Field(
        description="Why the answer is correct and why each incorrect option is wrong"
    )
    category: Optional[str] = Field(
        None,
        description="Question category: scenario, definition, or application"
    )
    source_citation: Optional[SourceCitation] = Field(
        None,
        description="Citation from the study content that supports this question"
    )


class QuestionBatch(BaseModel):
    """Batch of generated questions."""

    questions: list[GeneratedQuestion] = Field(
        description="List of generated questions"
    )


class QuestionCategory(str, Enum):
    """Categories of question styles for variety."""

    SCENARIO = "scenario"  # Clinical vignettes
    DEFINITION = "definition"  # Key terms and concepts
    APPLICATION = "application"  # Novel situation application


# Distribution: 40% scenario, 30% definition, 30% application
CATEGORY_WEIGHTS: dict[QuestionCategory, float] = {
    QuestionCategory.SCENARIO: 0.4,
    QuestionCategory.DEFINITION: 0.3,
    QuestionCategory.APPLICATION: 0.3,
}

# System prompt for question generation - Claude 4.x optimized
SYSTEM_PROMPT = """You are an expert BCBA exam question writer creating practice questions for the BCBA 5th Edition certification exam.

<guidelines>
- Create plausible distractors that would challenge someone who hasn't mastered the content
- Never use "all of the above" or "none of the above" options
- Reference specific ethics codes, task list items, or principles where relevant
- Use diverse names, settings, and demographics in scenarios
- Vary complexity - include questions requiring multi-step reasoning
- Match the difficulty and style of actual BCBA certification exam questions
</guidelines>

<explanation_format>
Each explanation should:
1. State why the correct answer is right with specific reasoning
2. Address each incorrect option individually, explaining the specific misconception it represents
3. Connect to relevant BCBA task list items or ethics codes when applicable
</explanation_format>

<citation_requirement>
For each question, provide a source_citation from the study content:
- section: The task list item or document section (e.g., "Task List F-1", "Ethics Code 2.09")
- heading: The topic or heading name
- quote: A brief relevant quote (max 50 words) that supports the question
</citation_requirement>

<example>
Question: A BCBA notices that a client's aggressive behavior increases immediately after demands are placed and results in the removal of task materials. Based on this pattern, the behavior analyst should FIRST:

Options:
A: Implement a DRA procedure targeting compliance
B: Conduct a functional behavior assessment
C: Apply an extinction procedure by not removing materials
D: Consult with the client's physician about medication

Correct Answer: B

Explanation: A functional behavior assessment (FBA) should be conducted first to systematically identify the function of the behavior before selecting an intervention (Task List item F-1). While the pattern suggests escape-maintained behavior, a proper FBA will confirm this hypothesis and rule out other maintaining variables. Option A (DRA) and Option C (extinction) are intervention procedures that should only be implemented after the function is confirmed through formal assessment. Option D (physician consultation) may be appropriate for ruling out medical causes but is not the first step when the behavior appears to have a clear environmental antecedent-behavior-consequence pattern.

Source Citation:
- section: Task List F-1
- heading: Review records and available data at the outset of the case
- quote: "Behavior analysts conduct assessments...before selecting and implementing interventions"
</example>"""

# System prompt for batch question generation
BATCH_SYSTEM_PROMPT = """You are an expert BCBA exam question writer creating practice questions for the BCBA 5th Edition certification exam.

<guidelines>
- Create plausible distractors that would challenge someone who hasn't mastered the content
- Never use "all of the above" or "none of the above" options
- Explanations should teach the concept: state why the correct answer is right AND address why each incorrect option is wrong
- Match BCBA certification exam difficulty and style
- Reference specific ethics codes and task list items where relevant
- Use diverse names, settings, and demographics in scenarios
</guidelines>

<variety_requirements>
For each batch, ensure:
- Approximately 40% scenario-based clinical vignettes
- Approximately 30% definition/concept questions
- Approximately 30% application questions
- Each question tests a DIFFERENT concept within the content area
- Mix of difficulty levels (some straightforward, some requiring multi-step reasoning)
- Include the category field for each question (scenario, definition, or application)
</variety_requirements>

<explanation_format>
Each explanation should:
1. State why the correct answer is right with specific reasoning
2. Address each incorrect option individually
3. Reference relevant BCBA task list items when applicable
</explanation_format>

<citation_requirement>
For each question, provide a source_citation from the study content:
- section: The task list item or document section (e.g., "Task List F-1", "Ethics Code 2.09")
- heading: The topic or heading name
- quote: A brief relevant quote (max 50 words) that supports the question
</citation_requirement>"""

# Category-specific instructions
CATEGORY_INSTRUCTIONS: dict[QuestionCategory, str] = {
    QuestionCategory.SCENARIO: """Create a SCENARIO-BASED question (clinical vignette):
- Present a realistic clinical situation with specific client details
- Include relevant background (age, diagnosis, setting, behavior description)
- Ask what the BCBA should do, what concept is being demonstrated, or what the likely outcome would be
- The scenario should require applying knowledge, not just recalling definitions
- Example contexts: home-based therapy, school setting, clinic, parent training, supervision""",
    QuestionCategory.DEFINITION: """Create a DEFINITION/CONCEPT question:
- Focus on testing understanding of a key term or principle
- Can ask for the best definition, what term describes something, or to identify examples
- Include subtle distinctions that require true understanding
- Good distractors should be related terms that are commonly confused
- Reference specific terminology from the BCBA Task List""",
    QuestionCategory.APPLICATION: """Create an APPLICATION question (novel situation):
- Present a situation the candidate likely hasn't seen before
- Require applying principles to determine the best course of action
- Test transfer of learning to new contexts
- Focus on "what should happen" or "what would result" type questions
- Can involve troubleshooting, predicting outcomes, or selecting interventions""",
}

# Content-area specific guidance
CONTENT_AREA_GUIDANCE: dict[ContentArea, str] = {
    ContentArea.ETHICS: """<content_area_focus>
Ethics - Key topics to assess:
- BACB Ethics Code sections and real-world applications
- Multiple relationships and conflicts of interest
- Informed consent and assent procedures
- Confidentiality boundaries and exceptions
- Supervisory responsibilities and requirements
- Professional conduct across various settings
- Reporting obligations and ethical decision-making
</content_area_focus>""",
    ContentArea.BEHAVIOR_ASSESSMENT: """<content_area_focus>
Behavior Assessment - Key topics to assess:
- Functional behavior assessment (FBA) methods and procedures
- Indirect vs. direct assessment comparison
- Identifying functions of behavior (attention, escape, tangible, automatic)
- Baseline data collection methods
- Assessment tool selection criteria
- Interpreting assessment results and forming hypotheses
- Preference assessments and stimulus preference hierarchies
</content_area_focus>""",
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: """<content_area_focus>
Behavior-Change Procedures - Key topics to assess:
- Reinforcement and punishment procedures (positive/negative)
- Extinction and its side effects
- Differential reinforcement (DRA, DRI, DRO, DRL, DRH)
- Shaping, chaining (forward/backward/total task), prompting
- Token economies and group contingencies
- Generalization and maintenance programming
- Stimulus control transfer procedures
</content_area_focus>""",
    ContentArea.CONCEPTS_AND_PRINCIPLES: """<content_area_focus>
Concepts and Principles - Key topics to assess:
- Operant and respondent conditioning
- Stimulus control, discrimination, and generalization
- Motivating operations (EOs and AOs)
- Verbal behavior (mand, tact, echoic, intraverbal, textual, transcription)
- Rule-governed vs. contingency-shaped behavior
- Behavioral momentum and matching law
- Schedules of reinforcement and their effects
</content_area_focus>""",
    ContentArea.MEASUREMENT: """<content_area_focus>
Measurement, Data Display, and Interpretation - Key topics to assess:
- Data collection methods (frequency, rate, duration, latency, IRT)
- IOA calculation methods (total, interval, exact agreement)
- Visual analysis of graphs (level, trend, variability)
- Continuous vs. discontinuous measurement
- Validity and reliability of behavioral measures
- Graphing conventions and data display
- Calculating and interpreting percentage and rate data
</content_area_focus>""",
    ContentArea.EXPERIMENTAL_DESIGN: """<content_area_focus>
Experimental Design - Key topics to assess:
- Single-subject designs (reversal/ABAB, multiple baseline, alternating treatment, changing criterion)
- Internal and external validity threats
- Baseline logic and steady state criteria
- Replication types (direct, systematic)
- When to use each design type
- Interpreting design results and drawing conclusions
- Component and parametric analyses
</content_area_focus>""",
    ContentArea.INTERVENTIONS: """<content_area_focus>
Selecting and Implementing Interventions - Key topics to assess:
- Evidence-based practice selection criteria
- Intervention planning and goal setting
- Treatment integrity/fidelity monitoring
- Social validity considerations
- Crisis and emergency protocols
- Transition and discharge planning
- Least restrictive intervention selection
</content_area_focus>""",
    ContentArea.SUPERVISION: """<content_area_focus>
Personnel Supervision and Management - Key topics to assess:
- RBT and trainee supervision requirements
- Feedback delivery methods (immediate, delayed, written, verbal)
- Performance monitoring and evaluation
- Training and competency assessment
- Supervision documentation requirements
- Ethical supervision practices
- Effective supervision structures and scheduling
</content_area_focus>""",
    ContentArea.PHILOSOPHICAL_UNDERPINNINGS: """<content_area_focus>
Philosophical Underpinnings - Key topics to assess:
- Radical behaviorism principles
- Determinism and selectionism
- Parsimony in explanation
- Pragmatism and scientific attitudes
- Public vs. private events
- Mentalism vs. behaviorism distinction
- Dimensions of applied behavior analysis
</content_area_focus>""",
}


class QuestionGenerator:
    """Generates quiz questions using OpenAI GPT 5.2 API with async support."""

    def __init__(self) -> None:
        self.settings = get_settings()
        # Use AsyncOpenAI with built-in retries (exponential backoff with jitter)
        # SDK handles 429/5xx errors automatically
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            max_retries=5,  # Increased from default 2
        )
        # Use absolute path from project root
        self.processed_content_dir = Path(__file__).parent.parent.parent / "data" / "processed"
        # Content cache to avoid repeated file reads
        self._content_cache: dict[ContentArea, str] = {}

    def _load_content_for_area(self, content_area: ContentArea) -> str:
        """Load pre-processed markdown content for a content area.

        Uses caching to avoid repeated file reads for batch operations.

        Raises:
            FileNotFoundError: If no content files exist for the area.
        """
        # Check cache first
        if content_area in self._content_cache:
            return self._content_cache[content_area]

        # Map content areas to file paths
        area_files = {
            ContentArea.PHILOSOPHICAL_UNDERPINNINGS: [
                "core/task_list.md",
                "core/handbook.md",
            ],
            ContentArea.CONCEPTS_AND_PRINCIPLES: [
                "core/task_list.md",
                "reference/glossary.md",
            ],
            ContentArea.MEASUREMENT: [
                "core/task_list.md",
                "core/tco.md",
            ],
            ContentArea.EXPERIMENTAL_DESIGN: [
                "core/task_list.md",
                "core/tco.md",
            ],
            ContentArea.ETHICS: [
                "ethics/ethics_code.md",
                "core/handbook.md",
            ],
            ContentArea.BEHAVIOR_ASSESSMENT: [
                "core/task_list.md",
                "core/tco.md",
            ],
            ContentArea.BEHAVIOR_CHANGE_PROCEDURES: [
                "core/task_list.md",
                "reference/glossary.md",
            ],
            ContentArea.INTERVENTIONS: [
                "core/task_list.md",
                "core/tco.md",
            ],
            ContentArea.SUPERVISION: [
                "supervision/curriculum.md",
                "core/handbook.md",
            ],
        }

        content_parts = []
        missing_files = []

        for file_path in area_files.get(content_area, []):
            full_path = self.processed_content_dir / file_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
                if content.strip():
                    content_parts.append(content)
                else:
                    logger.warning(f"Empty content file: {full_path}")
                    missing_files.append(file_path)
            else:
                missing_files.append(file_path)

        if missing_files:
            logger.warning(f"Missing files for {content_area.value}: {missing_files}")

        if not content_parts:
            raise FileNotFoundError(
                f"No content available for {content_area.value}. "
                f"Missing files: {missing_files}. "
                f"Content dir: {self.processed_content_dir}. "
                f"Run preprocessing first: python -m src.preprocessing.run_preprocessing"
            )

        content = "\n\n---\n\n".join(content_parts)
        # Cache the loaded content
        self._content_cache[content_area] = content
        return content

    def clear_content_cache(self) -> None:
        """Clear the content cache. Useful after content updates."""
        self._content_cache.clear()
        logger.debug("Content cache cleared")

    def _select_category(self) -> QuestionCategory:
        """Select a question category based on distribution weights."""
        r = random.random()
        cumulative = 0.0
        for category, weight in CATEGORY_WEIGHTS.items():
            cumulative += weight
            if r < cumulative:
                return category
        return QuestionCategory.SCENARIO  # Default fallback

    async def _call_api_with_retry(
        self,
        create_func,
        **kwargs,
    ) -> Any:
        """Call API - SDK handles retries automatically.

        The OpenAI SDK (max_retries=5) handles rate limits and transient errors
        with exponential backoff and jitter. We just need to catch and log final errors.

        Args:
            create_func: The async API function to call
            **kwargs: Arguments to pass to the API function

        Returns:
            API response

        Raises:
            openai.APIError: If SDK retries are exhausted
        """
        return await create_func(**kwargs)

    async def generate_question(
        self,
        content_area: ContentArea,
        question_type: Optional[QuestionType] = None,
        question_category: Optional[QuestionCategory] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Generate a single question for a content area using structured outputs.

        Args:
            content_area: The BCBA content area
            question_type: Type of question (if None, follows distribution)
            question_category: Style of question (if None, follows distribution)

        Returns:
            Question dict or None if generation fails
        """
        # Determine question type
        if question_type is None:
            mc_ratio = self.settings.type_distribution.get("multiple_choice", 0.8)
            question_type = (
                QuestionType.MULTIPLE_CHOICE
                if random.random() < mc_ratio
                else QuestionType.TRUE_FALSE
            )

        # Determine question category
        if question_category is None:
            question_category = self._select_category()

        # Load content
        try:
            content = self._load_content_for_area(content_area)
        except FileNotFoundError as e:
            logger.error(f"Cannot generate question: {e}")
            return None

        # Build user prompt with category and content-area specific guidance
        type_instruction = (
            "Create a multiple choice question with exactly 4 options (A, B, C, D)."
            if question_type == QuestionType.MULTIPLE_CHOICE
            else "Create a true/false question."
        )

        category_instruction = CATEGORY_INSTRUCTIONS.get(
            question_category, CATEGORY_INSTRUCTIONS[QuestionCategory.SCENARIO]
        )

        area_guidance = CONTENT_AREA_GUIDANCE.get(content_area, "")

        user_prompt = f"""Based on the following BCBA study content about {content_area.value}, {type_instruction}

<question_style>
{category_instruction}
</question_style>

{area_guidance}

<study_content>
{content}
</study_content>

Generate a challenging but fair exam-style question that matches the requested style. Set the category field to "{question_category.value}".

Include a source_citation with the specific section, heading, and a brief quote from the study content that this question is based on."""

        try:
            # Use structured outputs for guaranteed valid JSON (GPT 5.2)
            response = await self._call_api_with_retry(
                self.client.chat.completions.create,
                model=self.settings.openai_model,
                max_completion_tokens=self.settings.generation_max_tokens,
                messages=[
                    {"role": "developer", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "generated_question",
                        "strict": True,
                        "schema": GeneratedQuestion.model_json_schema(),
                    },
                },
            )

            # Parse guaranteed-valid JSON response
            response_content = response.choices[0].message.content
            if not response_content:
                logger.error("Response has no content")
                return None

            question_data = json.loads(response_content)

            # Normalize options - filter out None values
            raw_opts = question_data.get("options", {})
            normalized_opts = {k: v for k, v in raw_opts.items() if v is not None}
            question_data["options"] = normalized_opts

            # Add metadata
            question_data["content_area"] = content_area.value
            question_data["category"] = question_category.value
            question_data["model"] = self.settings.openai_model

            # Log usage
            logger.info(
                f"Generated {question_category.value} question for {content_area.value}: "
                f"{response.usage.prompt_tokens} in, {response.usage.completion_tokens} out"
            )

            return question_data

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error (unexpected with structured outputs): {e}")
        except Exception as e:
            logger.error(f"Question generation error: {e}")

        return None

    async def generate_batch(
        self,
        content_area: ContentArea,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Generate a batch of questions for a content area (legacy - one at a time).

        This method generates questions individually, which is less efficient
        than generate_question_batch() but provides more control over each question.

        Args:
            content_area: The BCBA content area
            count: Number of questions to generate

        Returns:
            List of question dicts
        """
        questions = []

        for i in range(count):
            question = await self.generate_question(content_area)
            if question:
                questions.append(question)
            else:
                logger.warning(
                    f"Failed to generate question {i + 1}/{count} for {content_area.value}"
                )

        logger.info(
            f"Generated {len(questions)}/{count} questions for {content_area.value}"
        )
        return questions

    async def generate_question_batch(
        self,
        content_area: ContentArea,
        count: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Generate multiple questions in a single API call using structured outputs.

        This is more efficient than generating one question at a time.

        Args:
            content_area: The BCBA content area
            count: Number of questions to generate (default 5)

        Returns:
            List of question dicts
        """
        try:
            content = self._load_content_for_area(content_area)
        except FileNotFoundError as e:
            logger.error(f"Cannot generate batch: {e}")
            return []

        area_guidance = CONTENT_AREA_GUIDANCE.get(content_area, "")

        # Calculate category distribution for this batch
        scenario_count = round(count * 0.4)
        definition_count = round(count * 0.3)
        application_count = count - scenario_count - definition_count

        user_prompt = f"""Generate exactly {count} BCBA exam questions about {content_area.value}.

{area_guidance}

<distribution_requirements>
Generate this specific mix of question types:
- {scenario_count} scenario-based questions (clinical vignettes) - set category to "scenario"
- {definition_count} definition/concept questions - set category to "definition"
- {application_count} application questions - set category to "application"

Approximately {round(count * 0.8)} should be multiple choice, {count - round(count * 0.8)} should be true/false.
</distribution_requirements>

<study_content>
{content}
</study_content>

Generate {count} diverse questions testing different concepts within this area.

For each question, include a source_citation with the specific section, heading, and a brief quote from the study content that the question is based on."""

        try:
            # Use structured outputs - guarantees valid JSON matching schema (GPT 5.2)
            response = await self._call_api_with_retry(
                self.client.chat.completions.create,
                model=self.settings.openai_model,
                max_completion_tokens=self.settings.generation_max_tokens,
                messages=[
                    {"role": "developer", "content": BATCH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "question_batch",
                        "strict": True,
                        "schema": QuestionBatch.model_json_schema(),
                    },
                },
            )

            # Guaranteed valid JSON - just parse it
            response_content = response.choices[0].message.content
            if not response_content:
                logger.error("Batch response has no content")
                return []

            data = json.loads(response_content)
            questions = data["questions"]

            # Normalize each question
            for q in questions:
                # Filter out None values in options
                raw_opts = q.get("options", {})
                normalized_opts = {k: v for k, v in raw_opts.items() if v is not None}
                q["options"] = normalized_opts

                # Add content area and model metadata
                q["content_area"] = content_area.value
                q["model"] = self.settings.openai_model

                # Ensure category is set (default to scenario if missing)
                if not q.get("category"):
                    q["category"] = "scenario"

            logger.info(
                f"Generated {len(questions)} questions for {content_area.value}: "
                f"{response.usage.prompt_tokens} in, {response.usage.completion_tokens} out"
            )

            return questions

        except openai.APIError as e:
            logger.error(f"OpenAI API error in batch generation: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in batch generation: {e}")
        except Exception as e:
            logger.error(f"Batch question generation error: {e}")

        return []


# Singleton instance
_generator: Optional[QuestionGenerator] = None


def get_question_generator() -> QuestionGenerator:
    """Get or create the question generator instance."""
    global _generator
    if _generator is None:
        _generator = QuestionGenerator()
    return _generator
