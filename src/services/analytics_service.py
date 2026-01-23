"""
Analytics service for AbaQuiz.

Orchestrates the computation and storage of analytics snapshots.
"""

from datetime import date, datetime, timedelta
from typing import Any, Optional

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import Repository, get_repository

logger = get_logger(__name__)

# Global service instance
_analytics_service: Optional["AnalyticsService"] = None


class AnalyticsService:
    """Service for computing and storing analytics snapshots."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.churn_days = 7  # Users inactive for 7 days are considered churned

    async def compute_daily_snapshots(
        self,
        target_date: date,
    ) -> dict[str, Any]:
        """
        Compute all system-wide daily snapshots.

        This includes:
        - Daily system snapshot
        - Hourly activity breakdown

        Args:
            target_date: The date to compute snapshots for

        Returns:
            Dict with results summary
        """
        logger.info(f"Computing daily system snapshots for {target_date}")

        # Aggregate and save system snapshot
        system_stats = await self.repo.aggregate_daily_system_stats(target_date)
        await self.repo.save_daily_system_snapshot(system_stats)
        logger.info(f"Saved daily system snapshot for {target_date}")

        # Aggregate and save hourly activity
        hourly_data = await self.repo.aggregate_hourly_activity(target_date)
        hours_saved = await self.repo.save_hourly_activity(hourly_data)
        logger.info(f"Saved {hours_saved} hourly activity records for {target_date}")

        return {
            "date": target_date.isoformat(),
            "system_snapshot_saved": True,
            "hourly_records_saved": hours_saved,
            "active_users_1d": system_stats["active_users_1d"],
            "total_answers": system_stats["total_correct"] + system_stats["total_incorrect"],
        }

    async def compute_user_snapshots_for_timezone(
        self,
        timezone: str,
        target_date: date,
    ) -> dict[str, Any]:
        """
        Compute and save user daily snapshots for all users in a timezone.

        Called at midnight for each timezone.

        Args:
            timezone: The timezone to process
            target_date: The date to compute snapshots for (usually yesterday)

        Returns:
            Dict with results summary
        """
        logger.info(f"Computing user snapshots for {timezone} on {target_date}")

        users = await self.repo.get_users_by_timezone(timezone)
        if not users:
            logger.debug(f"No users found in timezone {timezone}")
            return {"timezone": timezone, "users_processed": 0, "date": target_date.isoformat()}

        saved_count = 0
        active_count = 0

        for user in users:
            user_id = user["id"]
            try:
                user_stats = await self.repo.aggregate_user_daily_stats(
                    user_id=user_id,
                    target_date=target_date,
                    user_timezone=timezone,
                )
                await self.repo.save_user_daily_snapshot(user_stats)
                saved_count += 1

                if user_stats["was_active"]:
                    active_count += 1

            except Exception as e:
                logger.error(f"Failed to compute snapshot for user {user_id}: {e}")

        logger.info(
            f"Saved {saved_count} user snapshots for {timezone} "
            f"({active_count} active users)"
        )

        return {
            "timezone": timezone,
            "date": target_date.isoformat(),
            "users_processed": saved_count,
            "active_users": active_count,
        }

    async def compute_weekly_retention(
        self,
        week_start: date,
    ) -> dict[str, Any]:
        """
        Compute weekly retention metrics.

        Called on Sunday/Monday after the week ends.

        Args:
            week_start: The Monday that starts the week being analyzed

        Returns:
            Dict with retention metrics
        """
        logger.info(f"Computing weekly retention for week starting {week_start}")

        week_end = week_start + timedelta(days=6)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)
        two_weeks_ago_start = prev_week_start - timedelta(days=7)

        # Get active users this week
        active_this_week = await self.repo.get_active_user_ids_in_period(
            week_start, week_end
        )

        # Get active users last week
        active_last_week = await self.repo.get_active_user_ids_in_period(
            prev_week_start, prev_week_end
        )

        # Get active users two weeks ago
        active_two_weeks_ago = await self.repo.get_active_user_ids_in_period(
            two_weeks_ago_start, prev_week_end - timedelta(days=7)
        )

        # Get new users this week
        new_users_this_week = await self.repo.get_new_user_ids_in_period(
            week_start, week_end
        )

        # Calculate metrics
        retained = active_this_week & active_last_week
        churned = active_last_week - active_this_week
        reactivated = active_this_week & active_two_weeks_ago - active_last_week
        new_this_week = active_this_week & new_users_this_week

        retention_rate = len(retained) / len(active_last_week) if active_last_week else 0
        churn_rate = len(churned) / len(active_last_week) if active_last_week else 0

        # Tier retention
        tier_retention = {}
        for tier in ["easy", "medium", "hard"]:
            active_tier_this_week = await self.repo.get_users_active_with_tier(
                week_start, week_end, tier
            )
            active_tier_last_week = await self.repo.get_users_active_with_tier(
                prev_week_start, prev_week_end, tier
            )
            retained_tier = active_tier_this_week & active_tier_last_week

            tier_retention[tier] = {
                "active": len(active_tier_this_week),
                "retained": len(retained_tier),
                "retention_rate": (
                    len(retained_tier) / len(active_tier_last_week)
                    if active_tier_last_week
                    else 0
                ),
            }

        data = {
            "week_start": week_start.isoformat(),
            "active_users": len(active_this_week),
            "retained_from_last_week": len(retained),
            "churned_this_week": len(churned),
            "reactivated_this_week": len(reactivated),
            "new_this_week": len(new_this_week),
            "retention_rate": retention_rate,
            "churn_rate": churn_rate,
            "tier_retention": tier_retention,
        }

        await self.repo.save_weekly_retention_snapshot(data)
        logger.info(
            f"Weekly retention for {week_start}: "
            f"{len(active_this_week)} active, "
            f"{retention_rate:.1%} retention, "
            f"{churn_rate:.1%} churn"
        )

        return data


async def get_analytics_service() -> AnalyticsService:
    """Get or create the global analytics service instance."""
    global _analytics_service
    if _analytics_service is None:
        settings = get_settings()
        repo = await get_repository(settings.database_path)
        _analytics_service = AnalyticsService(repo)
    return _analytics_service


async def compute_daily_analytics(timezone: str) -> dict[str, Any]:
    """
    Compute daily analytics for a timezone.

    Called by the scheduler at midnight for each timezone.
    Computes snapshots for yesterday (the day that just ended).

    Args:
        timezone: The timezone that just hit midnight

    Returns:
        Dict with computation results
    """
    service = await get_analytics_service()
    yesterday = date.today() - timedelta(days=1)

    # Compute user snapshots for this timezone
    user_result = await service.compute_user_snapshots_for_timezone(timezone, yesterday)

    # For Pacific timezone, also compute system-wide snapshots
    # (only once daily, not per timezone)
    system_result = None
    if timezone == "America/Los_Angeles":
        system_result = await service.compute_daily_snapshots(yesterday)

        # Check if today is Monday - compute weekly retention
        if date.today().weekday() == 0:  # Monday
            week_start = date.today() - timedelta(days=7)  # Previous Monday
            await service.compute_weekly_retention(week_start)

    return {
        "timezone": timezone,
        "user_result": user_result,
        "system_result": system_result,
    }
