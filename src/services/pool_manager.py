"""
Question pool management service for AbaQuiz.

Manages the question pool using active-user-based thresholds,
BCBA exam weight distribution, and Haiku-based deduplication.
Uses AsyncAnthropic for non-blocking API calls.
"""

import asyncio
import json
from typing import Any, Optional

import anthropic
from anthropic import AsyncAnthropic

from src.config.constants import ContentArea
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository
from src.services.question_generator import get_question_generator

logger = get_logger(__name__)

# BCBA 5th Edition exam content weights
BCBA_WEIGHTS: dict[ContentArea, float] = {
    ContentArea.ETHICS: 0.13,
    ContentArea.BEHAVIOR_CHANGE_PROCEDURES: 0.14,
    ContentArea.CONCEPTS_AND_PRINCIPLES: 0.14,
    ContentArea.BEHAVIOR_ASSESSMENT: 0.13,
    ContentArea.INTERVENTIONS: 0.11,
    ContentArea.SUPERVISION: 0.11,
    ContentArea.MEASUREMENT: 0.12,
    ContentArea.EXPERIMENTAL_DESIGN: 0.07,
    ContentArea.PHILOSOPHICAL_UNDERPINNINGS: 0.05,
}

# Enhanced deduplication prompt with examples and clear confidence criteria
DEDUP_PROMPT = """Determine if a new quiz question is too similar to existing questions in the pool.

<similarity_criteria>
TOO SIMILAR (reject as duplicate):
- Tests the exact same specific concept with only superficial wording changes
- Scenarios are nearly identical with minor detail swaps (names, numbers, settings)
- Core knowledge being tested is identical, just phrased differently
- Would feel repetitive to a student seeing both questions

NOT TOO SIMILAR (accept as unique):
- Tests different aspects or applications of the same broad topic
- Requires different reasoning paths or knowledge application
- Presents meaningfully different scenarios even if on the same topic
- Would provide additional learning value to a student
</similarity_criteria>

<examples>
SIMILAR - Should REJECT:
- "What is the primary purpose of an FBA?" vs "The main goal of a functional behavior assessment is to..."
- "John hits when denied iPad access. What is the likely function?" vs "Sarah hits when her tablet is taken away. What function is this?"
- "Which is an example of positive reinforcement?" vs "Positive reinforcement is demonstrated when..."

NOT SIMILAR - Should ACCEPT:
- "What is the primary purpose of an FBA?" vs "Which assessment method identifies if behavior is maintained by escape?"
- "John hits when denied iPad - what function?" vs "After FBA reveals attention function, which intervention is appropriate?"
- "Define positive reinforcement" vs "A child receives candy after cleaning. What happens to cleaning behavior?"
</examples>

<confidence_levels>
- high: Nearly identical questions testing the exact same specific concept - REJECT
- medium: Same general topic area but possibly testing different specific aspects - consider accepting
- low: Related topic but clearly different focus or application - ACCEPT
</confidence_levels>

<new_question>
{new_question}
</new_question>

<existing_questions>
{existing_questions}
</existing_questions>

<output_format>
Respond with valid JSON only:
{{"is_duplicate": true/false, "reason": "brief specific explanation", "confidence": "high/medium/low"}}
</output_format>"""


class PoolManager:
    """
    Manages the question pool with active-user-based threshold checking.

    Triggers generation when avg unseen questions per active user < threshold.
    Uses BCBA exam weights for content area distribution.
    Uses Claude Haiku for deduplication checking with rate limiting.
    """

    DEFAULT_THRESHOLD = 20
    DEFAULT_BATCH_SIZE = 50
    ACTIVE_DAYS = 7
    DEDUP_CHECK_LIMIT = 30  # Check against most recent N questions per area

    # Rate limiting for API calls
    MAX_CONCURRENT_DEDUP_CALLS = 5

    def __init__(self) -> None:
        self.settings = get_settings()
        # Use AsyncAnthropic for non-blocking API calls
        self.client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        # Semaphore for rate limiting dedup API calls
        self._dedup_semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_DEDUP_CALLS)

        # Load pool management settings from settings class
        self.threshold = self.settings.pool_threshold
        self.batch_size = self.settings.pool_batch_size
        self.dedup_model = self.settings.pool_dedup_model
        self.dedup_check_limit = self.settings.pool_dedup_check_limit
        self.dedup_confidence_threshold = self.settings.pool_dedup_confidence_threshold
        self.dedup_early_exit_batches = self.settings.pool_dedup_early_exit_batches
        self.generation_batch_size = self.settings.pool_generation_batch_size

        # Load BCBA weights from config or use defaults
        self.bcba_weights = self.settings.pool_bcba_weights
        if self.bcba_weights:
            # Convert string keys to ContentArea if weights from config
            self.bcba_weights = {
                ContentArea(k) if isinstance(k, str) else k: v
                for k, v in self.bcba_weights.items()
            }
        else:
            self.bcba_weights = BCBA_WEIGHTS

    async def check_and_replenish_pool(self) -> dict[str, Any]:
        """
        Check if pool needs replenishment and generate questions if needed.

        Returns:
            Dict with status info: {
                "needed": bool,
                "avg_unseen": float,
                "active_users": int,
                "generated": int,
                "by_area": dict[str, int]
            }
        """
        repo = await get_repository(self.settings.database_path)

        # Get current pool status
        active_users = await repo.get_active_user_count(days=self.ACTIVE_DAYS)
        avg_unseen = await repo.get_avg_unseen_questions_for_active_users(
            days=self.ACTIVE_DAYS
        )
        total_questions = await repo.get_total_question_count()

        logger.info(
            f"Pool status: {total_questions} total questions, "
            f"{active_users} active users, "
            f"{avg_unseen:.1f} avg unseen per active user"
        )

        result = {
            "needed": False,
            "avg_unseen": avg_unseen,
            "active_users": active_users,
            "total_questions": total_questions,
            "generated": 0,
            "by_area": {},
        }

        # Check if we need to generate (or if there are no questions yet)
        if avg_unseen >= self.threshold and total_questions > 0:
            logger.info(
                f"Pool sufficient: {avg_unseen:.1f} >= {self.threshold} threshold"
            )
            return result

        result["needed"] = True
        logger.info(
            f"Pool needs replenishment: {avg_unseen:.1f} < {self.threshold} threshold"
        )

        # Calculate distribution
        distribution = self.calculate_batch_distribution()
        logger.info(f"Batch distribution: {distribution}")

        # Generate questions
        generated_by_area: dict[str, int] = {}
        total_generated = 0

        for area, count in distribution.items():
            if count <= 0:
                continue

            try:
                questions = await self.generate_with_dedup(area, count)
                generated_by_area[area.value] = len(questions)
                total_generated += len(questions)

                # Store questions
                for q in questions:
                    await repo.create_question(
                        content=q["question"],
                        question_type=q.get("type", "multiple_choice"),
                        options=q["options"],
                        correct_answer=q["correct_answer"],
                        explanation=q["explanation"],
                        content_area=q["content_area"],
                        model=q.get("model"),
                    )

                logger.info(f"Generated {len(questions)} questions for {area.value}")

            except Exception as e:
                logger.error(f"Failed to generate questions for {area.value}: {e}")
                generated_by_area[area.value] = 0

        result["generated"] = total_generated
        result["by_area"] = generated_by_area

        logger.info(f"Pool replenishment complete: {total_generated} questions added")
        return result

    def calculate_batch_distribution(self) -> dict[ContentArea, int]:
        """
        Calculate how many questions to generate per content area.

        Based on BCBA exam weights and configured batch size.
        """
        distribution: dict[ContentArea, int] = {}
        remaining = self.batch_size

        # Sort by weight descending to handle rounding
        sorted_areas = sorted(
            self.bcba_weights.items(), key=lambda x: x[1], reverse=True
        )

        for i, (area, weight) in enumerate(sorted_areas):
            if i == len(sorted_areas) - 1:
                # Last area gets remaining to ensure we hit batch_size
                distribution[area] = remaining
            else:
                count = round(self.batch_size * weight)
                distribution[area] = count
                remaining -= count

        return distribution

    async def generate_with_dedup(
        self,
        content_area: ContentArea,
        count: int,
    ) -> list[dict[str, Any]]:
        """
        Generate questions with deduplication checking, using batch generation.

        Args:
            content_area: The content area to generate for
            count: Number of questions to generate

        Returns:
            List of unique question dicts
        """
        generator = get_question_generator()
        repo = await get_repository(self.settings.database_path)

        # Get existing questions for dedup checking
        existing_questions = await repo.get_questions_by_content_area(
            content_area.value, limit=self.dedup_check_limit
        )

        unique_questions: list[dict[str, Any]] = []
        batch_size = self.generation_batch_size
        max_batches = (count * 2) // batch_size + 1  # Allow for rejections
        rejected_count = 0
        total_generated = 0
        batches_run = 0

        for batch_num in range(max_batches):
            if len(unique_questions) >= count:
                break

            # Generate batch of questions
            batch = await generator.generate_question_batch(
                content_area=content_area,
                count=batch_size,
            )

            batches_run += 1

            if not batch:
                logger.warning(
                    f"Batch {batch_num + 1} returned empty for {content_area.value}"
                )
                continue

            total_generated += len(batch)

            # Check each question for duplicates
            for question in batch:
                if len(unique_questions) >= count:
                    break

                is_dup = await self.check_duplicate(
                    question, existing_questions + unique_questions
                )

                if not is_dup:
                    unique_questions.append(question)
                    logger.debug(
                        f"Added unique question {len(unique_questions)}/{count} "
                        f"for {content_area.value}"
                    )
                else:
                    rejected_count += 1
                    logger.debug(
                        f"Skipped duplicate question for {content_area.value}"
                    )

        # Log batch summary
        remaining = count - len(unique_questions)
        success_rate = (len(unique_questions) / total_generated * 100) if total_generated > 0 else 0

        if remaining > 0:
            logger.warning(
                f"[{content_area.value}] Batch incomplete: "
                f"{len(unique_questions)}/{count} accepted, "
                f"{rejected_count} rejected, "
                f"{remaining} remaining, "
                f"{success_rate:.0f}% success rate "
                f"({batches_run} API batches)"
            )
        else:
            logger.info(
                f"[{content_area.value}] Batch complete: "
                f"{len(unique_questions)}/{count} accepted, "
                f"{rejected_count} rejected, "
                f"{success_rate:.0f}% success rate "
                f"({batches_run} API batches)"
            )

        return unique_questions

    async def generate_without_dedup(
        self,
        content_area: ContentArea,
        count: int,
    ) -> list[dict[str, Any]]:
        """
        Generate questions without deduplication checks.

        Use this for initial seeding when the pool is empty.

        Args:
            content_area: The content area to generate for
            count: Number of questions to generate

        Returns:
            List of question dicts
        """
        generator = get_question_generator()
        questions: list[dict[str, Any]] = []
        batch_size = self.generation_batch_size

        batches_needed = (count + batch_size - 1) // batch_size

        for batch_num in range(batches_needed):
            needed = min(batch_size, count - len(questions))
            batch = await generator.generate_question_batch(content_area, needed)
            questions.extend(batch)

            logger.debug(
                f"Generated batch {batch_num + 1}/{batches_needed} for {content_area.value}"
            )

        result = questions[:count]

        # Log batch summary
        logger.info(
            f"[{content_area.value}] Batch complete: "
            f"{len(result)}/{count} generated "
            f"({batches_needed} API batches, no dedup)"
        )

        return result

    async def check_duplicate(
        self,
        new_question: dict[str, Any],
        existing_questions: list[dict[str, Any]],
    ) -> bool:
        """
        Check if a new question is too similar to existing questions.

        Uses Claude Haiku for semantic similarity checking with optimizations:
        - Rate limiting via semaphore
        - Confidence-based filtering: only reject high-confidence duplicates
        - Early exit: stop after N consecutive clean batches

        Returns False (not a duplicate) if the check fails to avoid blocking.
        """
        if not existing_questions:
            return False

        # Format new question
        new_q_text = (
            f"Question: {new_question['question']}\n"
            f"Options: {json.dumps(new_question['options'])}\n"
            f"Answer: {new_question['correct_answer']}"
        )

        # Batch existing questions (check against 5 at a time for efficiency)
        batch_size = 5
        consecutive_clean = 0

        for i in range(0, len(existing_questions), batch_size):
            batch = existing_questions[i : i + batch_size]

            existing_text = "\n\n".join(
                f"[{j + 1}] Question: {q.get('content', q.get('question', ''))}\n"
                f"Options: {json.dumps(q['options'])}\n"
                f"Answer: {q['correct_answer']}"
                for j, q in enumerate(batch)
            )

            prompt = DEDUP_PROMPT.format(
                new_question=new_q_text,
                existing_questions=existing_text,
            )

            try:
                # Use semaphore for rate limiting
                async with self._dedup_semaphore:
                    response = await self.client.messages.create(
                        model=self.dedup_model,
                        max_tokens=256,
                        messages=[{"role": "user", "content": prompt}],
                    )

                # Extract text from response
                content_block = response.content[0]
                if not hasattr(content_block, "text"):
                    logger.warning("Dedup response has no text content")
                    consecutive_clean += 1
                    continue

                result_text = content_block.text
                result = self._parse_dedup_result(result_text)

                if result and result.get("is_duplicate"):
                    confidence = result.get("confidence", "high")

                    # Confidence-based filtering: only reject high confidence
                    # (or medium if threshold is not set to "high")
                    should_reject = confidence == "high" or (
                        confidence == "medium"
                        and self.dedup_confidence_threshold != "high"
                    )

                    if should_reject:
                        logger.debug(
                            f"Duplicate rejected ({confidence}): "
                            f"{result.get('reason', 'unknown')}"
                        )
                        return True
                    else:
                        logger.debug(
                            f"Duplicate skipped ({confidence} < threshold): "
                            f"{result.get('reason', 'unknown')}"
                        )
                        consecutive_clean += 1
                else:
                    consecutive_clean += 1

                # Early exit: if we've seen N consecutive clean batches, assume no dup
                if consecutive_clean >= self.dedup_early_exit_batches:
                    logger.debug(
                        f"Early exit after {consecutive_clean} clean batches"
                    )
                    return False

            except anthropic.RateLimitError as e:
                # On rate limit, wait and retry once
                logger.warning(f"Dedup rate limited, waiting 5s: {e}")
                await asyncio.sleep(5)
                try:
                    async with self._dedup_semaphore:
                        response = await self.client.messages.create(
                            model=self.dedup_model,
                            max_tokens=256,
                            messages=[{"role": "user", "content": prompt}],
                        )
                    # Process response same as above
                    content_block = response.content[0]
                    if hasattr(content_block, "text"):
                        result = self._parse_dedup_result(content_block.text)
                        if result and result.get("is_duplicate"):
                            confidence = result.get("confidence", "high")
                            if confidence == "high" or (
                                confidence == "medium"
                                and self.dedup_confidence_threshold != "high"
                            ):
                                return True
                except Exception:
                    pass
                consecutive_clean += 1

            except Exception as e:
                # Log warning but don't block on dedup failure
                logger.warning(f"Dedup check failed, allowing question: {e}")
                return False

        return False

    def _parse_dedup_result(self, text: str) -> Optional[dict[str, Any]]:
        """Parse deduplication result JSON."""
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

        logger.warning(f"Failed to parse dedup result: {text[:100]}...")
        return None


# Singleton instance
_pool_manager: Optional[PoolManager] = None


def get_pool_manager() -> PoolManager:
    """Get or create the pool manager instance."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = PoolManager()
    return _pool_manager
