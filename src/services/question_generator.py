"""
Question generation service using Claude API.

Generates BCBA exam questions from pre-processed content.
"""

import json
import random
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

import anthropic
from anthropic import transform_schema
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
        description="Why the answer is correct and others wrong"
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

# System prompt for question generation
SYSTEM_PROMPT = """You are an expert BCBA (Board Certified Behavior Analyst) exam question writer. Your task is to create high-quality practice questions based on the BCBA 5th Edition Task List content provided.

Core Guidelines:
1. All options should be plausible to someone who hasn't mastered the content
2. Avoid "all of the above" or "none of the above" options
3. The explanation should teach the concept and explain why the correct answer is right AND why other options are wrong
4. Match the difficulty and style of actual BCBA certification exam questions
5. Reference specific ethics codes, task list items, or principles where relevant
6. Use diverse names, settings, and demographics in scenarios
7. Vary complexity - some questions should require multi-step reasoning

You MUST respond with valid JSON matching this exact schema:
{
  "question": "The question text here",
  "type": "multiple_choice",
  "options": {
    "A": "First option",
    "B": "Second option",
    "C": "Third option",
    "D": "Fourth option"
  },
  "correct_answer": "B",
  "explanation": "Detailed explanation of why B is correct and why other options are incorrect."
}

For true/false questions, use this schema:
{
  "question": "The statement to evaluate as true or false",
  "type": "true_false",
  "options": {
    "True": "True",
    "False": "False"
  },
  "correct_answer": "True",
  "explanation": "Explanation of why the statement is true/false."
}"""

# System prompt for batch question generation (no JSON formatting needed - schema handles it)
BATCH_SYSTEM_PROMPT = """You are an expert BCBA exam question writer creating practice questions based on the BCBA 5th Edition Task List.

Guidelines:
1. All options should be plausible to someone who hasn't mastered the content
2. Avoid "all of the above" or "none of the above" options
3. Explanations should teach the concept and explain why correct/incorrect
4. Match BCBA certification exam difficulty and style
5. Reference specific ethics codes, task list items where relevant
6. Use diverse names, settings, demographics in scenarios

Requirements for variety in each batch:
- Mix categories: ~40% scenario-based, ~30% definition, ~30% application
- Each question must test a DIFFERENT concept
- Vary difficulty levels"""

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
    ContentArea.ETHICS: """Ethics focus areas:
- BACB Ethics Code sections and applications
- Multiple relationships and conflicts of interest
- Informed consent and assent
- Confidentiality boundaries
- Supervisory responsibilities
- Professional conduct in various settings""",
    ContentArea.BEHAVIOR_ASSESSMENT: """Behavior Assessment focus areas:
- Functional behavior assessment (FBA) methods
- Indirect vs. direct assessment
- Identifying functions of behavior
- Baseline data collection
- Assessment tool selection
- Interpreting assessment results""",
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: """Behavior-Change Procedures focus areas:
- Reinforcement and punishment procedures
- Extinction and its effects
- Differential reinforcement (DRA, DRI, DRO, DRL)
- Shaping, chaining, prompting
- Token economies and group contingencies
- Generalization and maintenance""",
    ContentArea.CONCEPTS_AND_PRINCIPLES: """Concepts and Principles focus areas:
- Operant and respondent conditioning
- Stimulus control and discrimination
- Motivating operations (MOs)
- Verbal behavior (mand, tact, intraverbal, etc.)
- Rule-governed vs. contingency-shaped behavior
- Behavioral momentum and matching law""",
    ContentArea.MEASUREMENT: """Measurement focus areas:
- Data collection methods (frequency, duration, latency, IRT)
- IOA calculation methods
- Visual analysis of graphs
- Variability, trend, and level
- Continuous vs. discontinuous measurement
- Validity and reliability of measures""",
    ContentArea.EXPERIMENTAL_DESIGN: """Experimental Design focus areas:
- Single-subject designs (reversal, multiple baseline, alternating treatment)
- Internal and external validity threats
- Baseline logic and steady state
- Replication types
- When to use each design type
- Interpreting design results""",
    ContentArea.INTERVENTIONS: """Interventions focus areas:
- Evidence-based practice selection
- Intervention planning and goal setting
- Treatment integrity monitoring
- Social validity considerations
- Crisis/emergency protocols
- Transition and discharge planning""",
    ContentArea.SUPERVISION: """Supervision focus areas:
- RBT and trainee supervision requirements
- Feedback delivery methods
- Performance monitoring and evaluation
- Training and competency assessment
- Supervision documentation
- Ethical supervision practices""",
    ContentArea.PHILOSOPHICAL_UNDERPINNINGS: """Philosophical Underpinnings focus areas:
- Radical behaviorism principles
- Determinism and selectionism
- Parsimony in explanation
- Pragmatism and scientific attitudes
- Public vs. private events
- Mentalism vs. behaviorism""",
}


class QuestionGenerator:
    """Generates quiz questions using Claude API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        self.processed_content_dir = Path("data/processed")

    def _load_content_for_area(self, content_area: ContentArea) -> str:
        """Load pre-processed markdown content for a content area."""
        # Map content areas to file paths
        # Core materials (task_list, handbook, tco) contain content spanning multiple areas
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
        for file_path in area_files.get(content_area, []):
            full_path = self.processed_content_dir / file_path
            if full_path.exists():
                content_parts.append(full_path.read_text())

        if not content_parts:
            logger.warning(f"No content found for {content_area.value}")
            return ""

        return "\n\n---\n\n".join(content_parts)

    def _select_category(self) -> QuestionCategory:
        """Select a question category based on distribution weights."""
        r = random.random()
        cumulative = 0.0
        for category, weight in CATEGORY_WEIGHTS.items():
            cumulative += weight
            if r < cumulative:
                return category
        return QuestionCategory.SCENARIO  # Default fallback

    async def generate_question(
        self,
        content_area: ContentArea,
        question_type: Optional[QuestionType] = None,
        question_category: Optional[QuestionCategory] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Generate a single question for a content area.

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
        content = self._load_content_for_area(content_area)

        # Build user prompt with category and content-area specific guidance
        type_instruction = (
            "Create a multiple choice question with 4 options (A, B, C, D)."
            if question_type == QuestionType.MULTIPLE_CHOICE
            else "Create a true/false question."
        )

        category_instruction = CATEGORY_INSTRUCTIONS.get(
            question_category, CATEGORY_INSTRUCTIONS[QuestionCategory.SCENARIO]
        )

        area_guidance = CONTENT_AREA_GUIDANCE.get(content_area, "")

        user_prompt = f"""Based on the following BCBA study content about {content_area.value}, {type_instruction}

QUESTION STYLE:
{category_instruction}

{area_guidance}

CONTENT:
{content if content else f"[Content for {content_area.value} - use your knowledge of BCBA exam topics]"}

Generate a challenging but fair exam-style question that matches the requested style. Respond with JSON only."""

        try:
            response = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Parse response - handle different content block types
            content_block = response.content[0]
            if not hasattr(content_block, "text"):
                logger.error("Response has no text content")
                return None
            response_text = content_block.text

            # Try to extract JSON from response
            question_data = self._parse_question_json(response_text)

            if question_data:
                # Add content area and category
                question_data["content_area"] = content_area.value
                question_data["category"] = question_category.value

                # Log usage
                logger.info(
                    f"Generated {question_category.value} question for {content_area.value}: "
                    f"{response.usage.input_tokens} in, {response.usage.output_tokens} out"
                )

                return question_data

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
        except Exception as e:
            logger.error(f"Question generation error: {e}")

        return None

    def _parse_question_json(self, text: str) -> Optional[dict[str, Any]]:
        """Parse question JSON from response text."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in response
        import re

        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse question JSON: {text[:200]}...")
        return None

    async def generate_batch(
        self,
        content_area: ContentArea,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Generate a batch of questions for a content area (legacy - one at a time).

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
        content = self._load_content_for_area(content_area)
        area_guidance = CONTENT_AREA_GUIDANCE.get(content_area, "")

        user_prompt = f"""Generate exactly {count} BCBA exam questions about {content_area.value}.

CONTENT AREA GUIDANCE:
{area_guidance}

STUDY CONTENT:
{content if content else f"Use your knowledge of {content_area.value} from the BCBA Task List."}

Generate {count} diverse questions testing different concepts within this area.
Include a mix of multiple choice and true/false questions (approximately 80% MC, 20% TF)."""

        try:
            # Use structured outputs beta - guarantees valid JSON matching schema
            response = self.client.beta.messages.create(
                model=self.settings.claude_model,
                max_tokens=4096,
                betas=["structured-outputs-2025-11-13"],
                system=BATCH_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                output_format={
                    "type": "json_schema",
                    "schema": transform_schema(QuestionBatch),
                },
            )

            # Guaranteed valid JSON - just parse it
            content_block = response.content[0]
            if not hasattr(content_block, "text"):
                logger.error("Batch response has no text content")
                return []

            data = json.loads(content_block.text)
            questions = data["questions"]

            # Normalize each question
            for q in questions:
                # Convert options from structured format to simple dict
                # Filter out None values and use original key names
                raw_opts = q.get("options", {})
                normalized_opts = {}
                for key, val in raw_opts.items():
                    if val is not None:
                        normalized_opts[key] = val
                q["options"] = normalized_opts

                # Add content area
                q["content_area"] = content_area.value

            logger.info(
                f"Generated {len(questions)} questions for {content_area.value}: "
                f"{response.usage.input_tokens} in, {response.usage.output_tokens} out"
            )

            return questions

        except anthropic.APIError as e:
            logger.error(f"Claude API error in batch generation: {e}")
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
