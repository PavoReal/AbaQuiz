"""
Question generation service using Claude API.

Generates BCBA exam questions from pre-processed content.
"""

import json
import random
from pathlib import Path
from typing import Any, Optional

import anthropic

from src.config.constants import ContentArea, QuestionType
from src.config.logging import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)

# System prompt for question generation
SYSTEM_PROMPT = """You are an expert BCBA (Board Certified Behavior Analyst) exam question writer. Your task is to create high-quality practice questions based on the BCBA 5th Edition Task List content provided.

Guidelines:
1. Questions should be scenario-based and test application of concepts, not just memorization
2. All options should be plausible to someone who hasn't mastered the content
3. Avoid "all of the above" or "none of the above" options
4. The explanation should teach the concept and explain why the correct answer is right AND why other options are wrong
5. Match the difficulty and style of actual BCBA certification exam questions
6. Reference specific ethics codes, task list items, or principles where relevant

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

    async def generate_question(
        self,
        content_area: ContentArea,
        question_type: Optional[QuestionType] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Generate a single question for a content area.

        Args:
            content_area: The BCBA content area
            question_type: Type of question (if None, follows distribution)

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

        # Load content
        content = self._load_content_for_area(content_area)

        # Build user prompt
        type_instruction = (
            "Create a multiple choice question with 4 options (A, B, C, D)."
            if question_type == QuestionType.MULTIPLE_CHOICE
            else "Create a true/false question."
        )

        user_prompt = f"""Based on the following BCBA study content about {content_area.value}, {type_instruction}

CONTENT:
{content if content else f"[Content for {content_area.value} - use your knowledge of BCBA exam topics]"}

Generate a challenging but fair exam-style question. Respond with JSON only."""

        try:
            response = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Parse response
            response_text = response.content[0].text

            # Try to extract JSON from response
            question_data = self._parse_question_json(response_text)

            if question_data:
                # Add content area
                question_data["content_area"] = content_area.value

                # Log usage
                logger.info(
                    f"Generated question for {content_area.value}: "
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
        Generate a batch of questions for a content area.

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


# Singleton instance
_generator: Optional[QuestionGenerator] = None


def get_question_generator() -> QuestionGenerator:
    """Get or create the question generator instance."""
    global _generator
    if _generator is None:
        _generator = QuestionGenerator()
    return _generator
