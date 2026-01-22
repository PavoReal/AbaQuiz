"""
Question pool management service for AbaQuiz.

Manages the question pool using active-user-based thresholds,
BCBA exam weight distribution, and embedding-based deduplication.
"""

import asyncio
from typing import Any, Optional

from src.config.constants import ContentArea
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository
from src.services.dedup_service import get_dedup_service
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



class PoolManager:
    """
    Manages the question pool with active-user-based threshold checking.

    Triggers generation when avg unseen questions per active user < threshold.
    Uses BCBA exam weights for content area distribution.
    Uses embedding-based deduplication checking.
    """

    DEFAULT_THRESHOLD = 20
    DEFAULT_BATCH_SIZE = 50
    ACTIVE_DAYS = 7
    DEDUP_CHECK_LIMIT = 30  # Check against most recent N questions per area

    def __init__(self) -> None:
        self.settings = get_settings()

        # Use embedding-based deduplication service
        self.dedup_service = get_dedup_service()

        # Load concurrency settings from config
        self.max_concurrent_generation = self.settings.pool_max_concurrent_generation

        # Semaphore for rate limiting generation API calls
        self._generation_semaphore = asyncio.Semaphore(self.max_concurrent_generation)

        # Load pool management settings from settings class
        self.threshold = self.settings.pool_threshold
        self.batch_size = self.settings.pool_batch_size
        self.dedup_check_limit = self.settings.pool_dedup_check_limit
        self.dedup_threshold = getattr(self.settings, 'pool_dedup_threshold', 0.85)
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

        # Generate questions for all content areas in parallel
        async def generate_for_area(
            area: ContentArea, count: int
        ) -> tuple[ContentArea, list[dict[str, Any]]]:
            """Generate questions for a single content area."""
            if count <= 0:
                return (area, [])
            try:
                questions = await self.generate_with_dedup(area, count)
                return (area, questions)
            except Exception as e:
                logger.error(f"Failed to generate questions for {area.value}: {e}")
                return (area, [])

        # Launch all content areas in parallel
        logger.info(
            f"Starting parallel generation across {len(distribution)} content areas"
        )
        tasks = [
            generate_for_area(area, count) for area, count in distribution.items()
        ]
        area_results = await asyncio.gather(*tasks)

        # Process results and store questions
        generated_by_area: dict[str, int] = {}
        total_generated = 0

        for area, questions in area_results:
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

            if questions:
                logger.info(f"Generated {len(questions)} questions for {area.value}")

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

    async def _generate_batch_with_semaphore(
        self,
        generator: Any,
        content_area: ContentArea,
        batch_size: int,
        batch_num: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        """
        Generate a single batch with rate limiting via semaphore.

        Returns:
            Tuple of (batch_num, questions)
        """
        async with self._generation_semaphore:
            try:
                batch = await generator.generate_question_batch(
                    content_area=content_area,
                    count=batch_size,
                )
                return (batch_num, batch or [])
            except Exception as e:
                logger.warning(
                    f"Batch {batch_num} failed for {content_area.value}: {e}"
                )
                return (batch_num, [])

    async def generate_with_dedup(
        self,
        content_area: ContentArea,
        count: int,
    ) -> list[dict[str, Any]]:
        """
        Generate questions with deduplication checking, using parallel batch generation.

        Uses asyncio.gather() to generate multiple batches concurrently,
        limited by the generation semaphore for rate limiting.

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

        batch_size = self.generation_batch_size
        # Calculate batches needed (allow for ~50% rejection rate)
        max_batches = (count * 2) // batch_size + 1

        # Generate all batches in parallel with semaphore limiting
        logger.info(
            f"[{content_area.value}] Starting parallel generation: "
            f"{max_batches} batches, {self.max_concurrent_generation} max concurrent"
        )

        batch_tasks = [
            self._generate_batch_with_semaphore(
                generator, content_area, batch_size, batch_num
            )
            for batch_num in range(max_batches)
        ]

        batch_results = await asyncio.gather(*batch_tasks)

        # Collect all generated questions
        all_questions: list[dict[str, Any]] = []
        batches_run = len([r for r in batch_results if r[1]])

        for batch_num, batch in sorted(batch_results, key=lambda x: x[0]):
            if batch:
                all_questions.extend(batch)

        total_generated = len(all_questions)
        logger.info(
            f"[{content_area.value}] Generated {total_generated} questions "
            f"from {batches_run} batches, now deduplicating..."
        )

        # Deduplicate questions
        unique_questions: list[dict[str, Any]] = []
        rejected_count = 0

        for question in all_questions:
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
        success_rate = (
            (len(unique_questions) / total_generated * 100)
            if total_generated > 0
            else 0
        )

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
        Generate questions without deduplication checks, using parallel batch generation.

        Use this for initial seeding when the pool is empty.

        Args:
            content_area: The content area to generate for
            count: Number of questions to generate

        Returns:
            List of question dicts
        """
        generator = get_question_generator()
        batch_size = self.generation_batch_size
        batches_needed = (count + batch_size - 1) // batch_size

        logger.info(
            f"[{content_area.value}] Starting parallel generation (no dedup): "
            f"{batches_needed} batches, {self.max_concurrent_generation} max concurrent"
        )

        # Generate all batches in parallel with semaphore limiting
        batch_tasks = [
            self._generate_batch_with_semaphore(
                generator, content_area, batch_size, batch_num
            )
            for batch_num in range(batches_needed)
        ]

        batch_results = await asyncio.gather(*batch_tasks)

        # Collect all generated questions in order
        questions: list[dict[str, Any]] = []
        for batch_num, batch in sorted(batch_results, key=lambda x: x[0]):
            questions.extend(batch)

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

        Uses embedding-based cosine similarity for efficient deduplication.
        Returns False (not a duplicate) if the check fails to avoid blocking.
        """
        if not existing_questions:
            return False

        result = await self.dedup_service.check_duplicate(
            new_question,
            existing_questions,
            threshold=self.dedup_threshold,
        )

        if result.is_duplicate:
            logger.debug(
                f"Duplicate rejected (similarity={result.similarity:.3f}): "
                f"{result.matched_question[:50] if result.matched_question else 'unknown'}..."
            )

        return result.is_duplicate


# Singleton instance
_pool_manager: Optional[PoolManager] = None


def get_pool_manager() -> PoolManager:
    """Get or create the pool manager instance."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = PoolManager()
    return _pool_manager
