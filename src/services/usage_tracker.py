"""
API usage tracking service for AbaQuiz.

Tracks Claude API usage for cost monitoring and analytics.
"""

from typing import Any, Optional

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository

logger = get_logger(__name__)


class UsageTracker:
    """Tracks and reports API usage."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
        model: Optional[str] = None,
    ) -> float:
        """
        Calculate estimated cost for API usage.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_write_tokens: Number of cache write tokens
            cache_read_tokens: Number of cache read tokens
            model: Model name (uses default if not specified)

        Returns:
            Estimated cost in USD
        """
        model = model or self.settings.claude_model
        pricing = self.settings.get_model_pricing(model)

        if not pricing:
            logger.warning(f"No pricing found for model {model}")
            return 0.0

        # Calculate cost (pricing is per million tokens)
        input_cost = (input_tokens / 1_000_000) * pricing.get("input_per_million", 0)
        output_cost = (output_tokens / 1_000_000) * pricing.get("output_per_million", 0)
        cache_write_cost = (cache_write_tokens / 1_000_000) * pricing.get(
            "cache_write_per_million", 0
        )
        cache_read_cost = (cache_read_tokens / 1_000_000) * pricing.get(
            "cache_read_per_million", 0
        )

        return input_cost + output_cost + cache_write_cost + cache_read_cost

    async def track_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None,
        cache_write_tokens: int = 0,
        cache_read_tokens: int = 0,
        content_area: Optional[str] = None,
    ) -> int:
        """
        Record API usage to database.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name
            cache_write_tokens: Number of cache write tokens
            cache_read_tokens: Number of cache read tokens
            content_area: Content area for the question

        Returns:
            Record ID
        """
        model = model or self.settings.claude_model
        estimated_cost = self.calculate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
            model=model,
        )

        repo = await get_repository(self.settings.database_path)

        record_id = await repo.record_api_usage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_write_tokens=cache_write_tokens,
            cache_read_tokens=cache_read_tokens,
            model=model,
            content_area=content_area,
            estimated_cost=estimated_cost,
        )

        logger.debug(
            f"Tracked API usage: {input_tokens} in, {output_tokens} out, "
            f"cost ${estimated_cost:.4f}"
        )

        return record_id

    async def get_usage_summary(
        self,
        hours: int = 24,
    ) -> dict[str, Any]:
        """
        Get usage summary for a time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Summary dict with totals and estimates
        """
        repo = await get_repository(self.settings.database_path)
        stats = await repo.get_api_usage_stats(hours=hours)

        return {
            "period_hours": hours,
            "total_calls": stats.get("total_calls") or 0,
            "input_tokens": stats.get("total_input_tokens") or 0,
            "output_tokens": stats.get("total_output_tokens") or 0,
            "cache_write_tokens": stats.get("total_cache_write_tokens") or 0,
            "cache_read_tokens": stats.get("total_cache_read_tokens") or 0,
            "estimated_cost": stats.get("total_cost") or 0.0,
        }


# Singleton instance
_tracker: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    """Get or create the usage tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
