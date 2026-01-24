"""
Question generation service using OpenAI GPT 5.2 API with File Search.

Generates BCBA exam questions using OpenAI's file search tool to retrieve
relevant content from the vector store containing BCBA study materials.
Uses AsyncOpenAI client with structured outputs for reliable JSON responses.
"""

import json
import random
from enum import Enum
from typing import Any, Literal, Optional

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config.constants import ContentArea, QuestionType
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.services.usage_tracker import get_usage_tracker
from src.services.vector_store_manager import get_vector_store_manager

logger = get_logger(__name__)


# Semantic queries for content area retrieval via file_search
CONTENT_AREA_QUERIES: dict[ContentArea, str] = {
    ContentArea.ETHICS: "BACB ethics code professional conduct multiple relationships confidentiality informed consent supervisory responsibilities",
    ContentArea.BEHAVIOR_ASSESSMENT: "functional behavior assessment FBA indirect direct assessment preference assessment baseline data collection",
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: "reinforcement punishment extinction differential reinforcement DRA DRI DRO shaping chaining prompting",
    ContentArea.CONCEPTS_AND_PRINCIPLES: "operant respondent conditioning stimulus control verbal behavior mand tact echoic motivating operations",
    ContentArea.MEASUREMENT: "data collection frequency rate duration latency IOA interobserver agreement graphing visual analysis",
    ContentArea.EXPERIMENTAL_DESIGN: "single subject design reversal multiple baseline alternating treatment changing criterion replication",
    ContentArea.INTERVENTIONS: "evidence-based practice treatment integrity social validity intervention selection crisis protocols",
    ContentArea.SUPERVISION: "RBT supervision feedback performance monitoring training competency assessment documentation",
    ContentArea.PHILOSOPHICAL_UNDERPINNINGS: "radical behaviorism determinism selectionism parsimony pragmatism dimensions of ABA",
}


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
    type: Literal["multiple_choice"] = Field(description="Question type (always multiple_choice)")
    options: QuestionOptions = Field(
        description="Answer options using A/B/C/D keys"
    )
    correct_answer: str = Field(
        description="The correct answer key only (A, B, C, or D)"
    )
    explanation: str = Field(
        description="Why the answer is correct and why each incorrect option is wrong"
    )
    category: Optional[str] = Field(
        None,
        description="Question category: scenario, definition, or application"
    )
    difficulty: int = Field(
        description="Difficulty rating from 1 (basic recall) to 5 (complex multi-step reasoning)"
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

# System prompt for question generation - GPT 5.2 with reasoning
SYSTEM_PROMPT = """You are an expert BCBA exam question writer creating practice questions for the BCBA 5th Edition certification exam.

<guidelines>
- Generate ONLY multiple choice questions with 4 options (A, B, C, D)
- Do NOT generate true/false questions
- Create plausible distractors that would challenge someone who hasn't mastered the content
- Never use "all of the above" or "none of the above" options
- Reference specific ethics codes, task list items, or principles where relevant
- Use diverse names, settings, and demographics in scenarios
- Vary complexity - include questions requiring multi-step reasoning
- Match the difficulty and style of actual BCBA certification exam questions
</guidelines>

<difficulty_rating>
Rate each question's difficulty from 1-5:
- 1: Basic recall of a single concept
- 2: Understanding of a concept with straightforward application
- 3: Application requiring integration of 2+ concepts
- 4: Analysis of complex scenarios with multiple variables
- 5: Evaluation/synthesis requiring multi-step reasoning and nuanced judgment
</difficulty_rating>

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
- Generate ONLY multiple choice questions with 4 options (A, B, C, D)
- Do NOT generate true/false questions
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
- Approximately 30% contextualized definition/concept questions (see definition format below)
- Approximately 30% application questions
- Each question tests a DIFFERENT concept within the content area
- Mix of difficulty levels (some straightforward, some requiring multi-step reasoning)
- Include the category field for each question (scenario, definition, or application)
- Include the difficulty field (1-5) for each question
</variety_requirements>

<difficulty_rating>
Rate each question's difficulty from 1-5:
- 1: Basic recall of a single concept
- 2: Understanding of a concept with straightforward application
- 3: Application requiring integration of 2+ concepts
- 4: Analysis of complex scenarios with multiple variables
- 5: Evaluation/synthesis requiring multi-step reasoning and nuanced judgment
</difficulty_rating>

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

# Difficulty emphasis guidance for targeted generation
DIFFICULTY_EMPHASIS: dict[int, str] = {
    3: "Focus on questions requiring integration of multiple concepts.",
    4: "Focus on complex scenarios with multiple variables. Require analysis of nuanced situations where simple recall is insufficient.",
    5: "Focus on evaluation and synthesis questions requiring multi-step reasoning and nuanced professional judgment. These should challenge even experienced practitioners.",
}

# Category-specific instructions
CATEGORY_INSTRUCTIONS: dict[QuestionCategory, str] = {
    QuestionCategory.SCENARIO: """Create a SCENARIO-BASED question (clinical vignette):
- Present a realistic clinical situation with specific client details
- Include relevant background (age, diagnosis, setting, behavior description)
- Ask what the BCBA should do, what concept is being demonstrated, or what the likely outcome would be
- The scenario should require applying knowledge, not just recalling definitions
- Example contexts: home-based therapy, school setting, clinic, parent training, supervision""",
    QuestionCategory.DEFINITION: """Create a CONTEXTUALIZED DEFINITION question:
- Present a brief scenario or example that demonstrates the concept
- Ask what term/principle is being illustrated OR what best describes the situation
- The scenario should require understanding the concept, not just memorizing the definition
- Include subtle distinctions that require true understanding
- Good distractors should be related terms that are commonly confused
- Reference specific terminology from the BCBA Task List

Example format: "A behavior analyst observes that a client's responding increases when
the therapist provides verbal praise. Later, responding decreases when praise is withheld.
This pattern best illustrates which principle?" (Answer: Positive reinforcement / extinction)""",
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
    """Generates quiz questions using OpenAI GPT 5.2 API with file search."""

    def __init__(self) -> None:
        self.settings = get_settings()
        # Use AsyncOpenAI for non-blocking API calls
        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            max_retries=3,
        )
        self.vector_store_manager = get_vector_store_manager()
        # Cache for vector store ID
        self._vector_store_id: Optional[str] = None
        # Cache retention setting: "in_memory" (5-10 min) or "24h" (extended)
        self._cache_retention: str = "in_memory"

    async def _get_vector_store_id(self) -> str:
        """Get the vector store ID, caching the result.

        Raises:
            RuntimeError: If vector store is not configured.
        """
        if self._vector_store_id is None:
            self._vector_store_id = await self.vector_store_manager.get_store_id()

        if not self._vector_store_id:
            raise RuntimeError(
                "Vector store not configured. Run: python -m src.scripts.manage_vector_store create"
            )

        return self._vector_store_id

    def clear_vector_store_cache(self) -> None:
        """Clear the vector store ID cache. Useful after store recreation."""
        self._vector_store_id = None
        logger.debug("Vector store ID cache cleared")

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

    def set_cache_retention(self, retention: str) -> None:
        """Set cache retention mode for prompt caching.

        Args:
            retention: Either "in_memory" (5-10 min, default) or "24h" (extended)

        Raises:
            ValueError: If retention value is invalid
        """
        if retention not in ("in_memory", "24h"):
            raise ValueError("retention must be 'in_memory' or '24h'")
        self._cache_retention = retention
        logger.debug(f"Cache retention set to: {retention}")

    def _extract_response_usage(self, response) -> dict[str, int]:
        """Extract token usage including cache info from Responses API.

        Args:
            response: OpenAI Responses API response object

        Returns:
            Dict with input_tokens, output_tokens, and cached_tokens
        """
        usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
        if hasattr(response, 'usage') and response.usage:
            usage["input_tokens"] = getattr(response.usage, 'input_tokens', 0) or 0
            usage["output_tokens"] = getattr(response.usage, 'output_tokens', 0) or 0
            if hasattr(response.usage, 'input_tokens_details'):
                details = response.usage.input_tokens_details
                if details and hasattr(details, 'cached_tokens'):
                    usage["cached_tokens"] = details.cached_tokens or 0
        return usage

    async def _track_usage(
        self,
        response,
        content_area: ContentArea,
    ) -> None:
        """Track API usage from response including cache metrics.

        Args:
            response: OpenAI Responses API response object
            content_area: Content area for the question
        """
        usage = self._extract_response_usage(response)
        if usage["input_tokens"] > 0:
            tracker = get_usage_tracker()
            await tracker.track_usage(
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cache_read_tokens=usage["cached_tokens"],
                content_area=content_area.value,
                model=self.settings.openai_model,
            )
            if usage["cached_tokens"] > 0:
                cache_pct = (usage["cached_tokens"] / usage["input_tokens"]) * 100
                logger.info(
                    f"Cache hit: {usage['cached_tokens']}/{usage['input_tokens']} "
                    f"input tokens ({cache_pct:.1f}%)"
                )

    async def generate_question(
        self,
        content_area: ContentArea,
        question_type: Optional[QuestionType] = None,
        question_category: Optional[QuestionCategory] = None,
        difficulty_min: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Generate a single question for a content area using file search.

        Uses OpenAI's file_search tool to retrieve relevant content from the
        vector store before generating the question.

        Args:
            content_area: The BCBA content area
            question_type: Type of question (if None, follows distribution)
            question_category: Style of question (if None, follows distribution)
            difficulty_min: Minimum difficulty level 1-5 (None = any)

        Returns:
            Question dict or None if generation fails
        """
        # Get vector store ID
        try:
            store_id = await self._get_vector_store_id()
        except RuntimeError as e:
            logger.error(f"Cannot generate question: {e}")
            return None

        # Always use multiple choice (true/false eliminated for better discrimination)
        question_type = QuestionType.MULTIPLE_CHOICE

        # Determine question category
        if question_category is None:
            question_category = self._select_category()

        # Build user prompt with category and content-area specific guidance
        type_instruction = "Create a multiple choice question with exactly 4 options (A, B, C, D)."

        category_instruction = CATEGORY_INSTRUCTIONS.get(
            question_category, CATEGORY_INSTRUCTIONS[QuestionCategory.SCENARIO]
        )

        area_guidance = CONTENT_AREA_GUIDANCE.get(content_area, "")
        area_query = CONTENT_AREA_QUERIES.get(content_area, content_area.value)

        # Build difficulty requirement if specified
        difficulty_instruction = ""
        if difficulty_min and difficulty_min > 1:
            emphasis = DIFFICULTY_EMPHASIS.get(difficulty_min, "")
            difficulty_instruction = f"""
<difficulty_requirement>
Generate a question with difficulty level {difficulty_min} or higher only.
{emphasis}
Do NOT generate a question rated below {difficulty_min}.
</difficulty_requirement>
"""

        user_prompt = f"""Search the BCBA study materials for content about: {area_query}

Based on the retrieved content about {content_area.value}, {type_instruction}

<question_style>
{category_instruction}
</question_style>

{area_guidance}
{difficulty_instruction}
Generate a challenging but fair exam-style question that matches the requested style. Set the category field to "{question_category.value}".

Include a source_citation with the specific section, heading, and a brief quote from the retrieved content that this question is based on.

IMPORTANT: You MUST respond with ONLY valid JSON matching this exact structure:
{{
  "question": "...",
  "type": "multiple_choice",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "correct_answer": "A" or "B" or "C" or "D",
  "explanation": "...",
  "category": "{question_category.value}",
  "difficulty": 1-5,
  "source_citation": {{"section": "...", "heading": "...", "quote": "..."}}
}}"""

        try:
            # Use Responses API with file_search tool, reasoning, and prompt caching
            response = await self._call_api_with_retry(
                self.client.responses.create,
                model=self.settings.openai_model,
                input=[
                    {"role": "developer", "content": SYSTEM_PROMPT + "\n\nYou MUST respond with valid JSON only, no markdown formatting."},
                    {"role": "user", "content": user_prompt},
                ],
                reasoning={
                    "effort": self.settings.reasoning_effort,
                    "summary": self.settings.reasoning_summary,
                },
                tools=[{
                    "type": "file_search",
                    "vector_store_ids": [store_id],
                }],
                prompt_cache_key=f"bcba-question-{content_area.value}",
                prompt_cache_retention=self._cache_retention,
            )

            # Track API usage including cache metrics
            await self._track_usage(response, content_area)

            # Extract response text
            response_text = None
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            response_text = content.text
                            break

            if not response_text:
                logger.error("Response has no text content")
                return None

            # Clean up response - remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # Remove markdown code block wrapper
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            question_data = json.loads(response_text)

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
                f"Generated {question_category.value} question for {content_area.value} "
                f"using file_search"
            )

            return question_data

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
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
        difficulty_min: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Generate multiple questions in a single API call using file search.

        Uses OpenAI's file_search tool to retrieve relevant content from the
        vector store before generating the questions.

        Args:
            content_area: The BCBA content area
            count: Number of questions to generate (default 5)
            difficulty_min: Minimum difficulty level 1-5 (None = any)

        Returns:
            List of question dicts
        """
        # Get vector store ID
        try:
            store_id = await self._get_vector_store_id()
        except RuntimeError as e:
            logger.error(f"Cannot generate batch: {e}")
            return []

        area_guidance = CONTENT_AREA_GUIDANCE.get(content_area, "")
        area_query = CONTENT_AREA_QUERIES.get(content_area, content_area.value)

        # Calculate category distribution for this batch
        scenario_count = round(count * 0.4)
        definition_count = round(count * 0.3)
        application_count = count - scenario_count - definition_count

        # Build difficulty requirement if specified
        difficulty_instruction = ""
        if difficulty_min and difficulty_min > 1:
            emphasis = DIFFICULTY_EMPHASIS.get(difficulty_min, "")
            difficulty_instruction = f"""
<difficulty_requirement>
Generate questions with difficulty level {difficulty_min} or higher only.
{emphasis}
Do NOT generate questions rated below {difficulty_min}.
</difficulty_requirement>
"""

        user_prompt = f"""Search the BCBA study materials for content about: {area_query}

Generate exactly {count} BCBA exam questions about {content_area.value} based on the retrieved content.

{area_guidance}

<distribution_requirements>
Generate this specific mix of question categories:
- {scenario_count} scenario-based questions (clinical vignettes) - set category to "scenario"
- {definition_count} contextualized definition/concept questions - set category to "definition"
- {application_count} application questions - set category to "application"

ALL questions must be multiple choice with 4 options (A, B, C, D). Do NOT generate true/false questions.
</distribution_requirements>
{difficulty_instruction}
Generate {count} diverse questions testing different concepts within this area.

For each question, include a source_citation with the specific section, heading, and a brief quote from the retrieved content that the question is based on.

IMPORTANT: You MUST respond with ONLY valid JSON matching this exact structure:
{{
  "questions": [
    {{
      "question": "...",
      "type": "multiple_choice",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "A" or "B" or "C" or "D",
      "explanation": "...",
      "category": "scenario" or "definition" or "application",
      "difficulty": 1-5,
      "source_citation": {{"section": "...", "heading": "...", "quote": "..."}}
    }}
  ]
}}"""

        try:
            # Use Responses API with file_search tool, reasoning, and prompt caching
            response = await self._call_api_with_retry(
                self.client.responses.create,
                model=self.settings.openai_model,
                input=[
                    {"role": "developer", "content": BATCH_SYSTEM_PROMPT + "\n\nYou MUST respond with valid JSON only, no markdown formatting."},
                    {"role": "user", "content": user_prompt},
                ],
                reasoning={
                    "effort": self.settings.reasoning_effort,
                    "summary": self.settings.reasoning_summary,
                },
                tools=[{
                    "type": "file_search",
                    "vector_store_ids": [store_id],
                }],
                prompt_cache_key=f"bcba-batch-{content_area.value}",
                prompt_cache_retention=self._cache_retention,
            )

            # Track API usage including cache metrics
            await self._track_usage(response, content_area)

            # Extract response text
            response_text = None
            for item in response.output:
                if item.type == "message":
                    for content in item.content:
                        if content.type == "output_text":
                            response_text = content.text
                            break

            if not response_text:
                logger.error("Batch response has no text content")
                return []

            # Clean up response - remove markdown code blocks if present
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            data = json.loads(response_text)
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
                f"Generated {len(questions)} questions for {content_area.value} using file_search"
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
