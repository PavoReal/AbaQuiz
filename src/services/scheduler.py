"""
Scheduler service for AbaQuiz.

Handles scheduled question delivery and maintenance tasks using APScheduler.
"""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository
from src.services.pool_manager import get_pool_manager

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None

# Track delivery statistics for diagnostics
_delivery_stats: dict[str, Any] = {
    "last_delivery": None,
    "total_deliveries": 0,
    "total_success": 0,
    "total_failures": 0,
    "by_timezone": {},
}


async def deliver_scheduled_questions(
    application: Application,
    timezone: str,
    is_morning: bool,
) -> None:
    """
    Deliver scheduled questions to all subscribed users in a timezone.

    Args:
        application: Telegram bot application
        timezone: User timezone string
        is_morning: True for morning delivery, False for evening
    """
    global _delivery_stats

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    period = "morning" if is_morning else "evening"
    logger.info(f"Starting {period} delivery for timezone {timezone}")

    # Get subscribed users in this timezone
    users = await repo.get_subscribed_users_by_timezone(timezone)

    if not users:
        logger.debug(f"No subscribed users in timezone {timezone}")
        return

    logger.info(f"Delivering to {len(users)} users in {timezone}")

    # Import here to avoid circular imports
    from src.bot.handlers import send_question_to_user

    success_count = 0
    failure_count = 0

    for user in users:
        telegram_id = user["telegram_id"]

        # Retry logic
        for attempt in range(settings.max_retries):
            try:
                success = await send_question_to_user(
                    user_id=telegram_id,
                    context=application,
                    is_scheduled=True,
                )

                if success:
                    success_count += 1
                    break
                else:
                    # No questions available or other soft failure
                    failure_count += 1
                    break

            except Exception as e:
                delay = settings.retry_delays[attempt] if attempt < len(settings.retry_delays) else 15
                logger.warning(
                    f"Delivery attempt {attempt + 1} failed for user {telegram_id}: {e}"
                )

                if attempt < settings.max_retries - 1:
                    await asyncio.sleep(delay)
                else:
                    failure_count += 1
                    logger.error(
                        f"All delivery attempts failed for user {telegram_id}"
                    )
                    # Notify admins about failure
                    await notify_admins_of_failure(
                        application,
                        telegram_id,
                        str(e),
                    )

        # Delay between users to avoid Telegram rate limiting
        # Telegram allows ~30 messages/second, use 50ms (20/sec) to be safe
        await asyncio.sleep(0.05)

        # Add extra delay every 25 users to avoid burst limits
        if (success_count + failure_count) % 25 == 0:
            await asyncio.sleep(1.0)

    logger.info(
        f"Completed {period} delivery for {timezone}: "
        f"{success_count} success, {failure_count} failures"
    )

    # Update delivery statistics
    _delivery_stats["last_delivery"] = datetime.now()
    _delivery_stats["total_deliveries"] += 1
    _delivery_stats["total_success"] += success_count
    _delivery_stats["total_failures"] += failure_count

    if timezone not in _delivery_stats["by_timezone"]:
        _delivery_stats["by_timezone"][timezone] = {
            "deliveries": 0,
            "success": 0,
            "failures": 0,
            "last_delivery": None,
        }
    _delivery_stats["by_timezone"][timezone]["deliveries"] += 1
    _delivery_stats["by_timezone"][timezone]["success"] += success_count
    _delivery_stats["by_timezone"][timezone]["failures"] += failure_count
    _delivery_stats["by_timezone"][timezone]["last_delivery"] = datetime.now()


async def notify_admins_of_failure(
    application: Application,
    user_id: int,
    error: str,
) -> None:
    """
    Notify admins about a delivery failure.

    Uses the new notification service for proper event tracking.

    Args:
        application: Telegram bot application
        user_id: Failed user's Telegram ID
        error: Error message
    """
    from src.services.notification_service import notify_delivery_failure

    await notify_delivery_failure(user_id, error)


def _parse_summary_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM time string into hour and minute."""
    try:
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 9, 0  # Default to 9:00 AM


async def flush_notification_batch() -> None:
    """Flush any batched notifications."""
    from src.services.notification_service import get_notification_service

    service = get_notification_service()
    if service:
        await service.flush_batch()


async def send_daily_admin_summary() -> None:
    """Send daily summary to admins."""
    from src.services.notification_service import get_notification_service

    service = get_notification_service()
    if service:
        await service.send_daily_summary()


async def check_question_pool() -> None:
    """
    Check question pool levels and generate questions if needed.

    Uses active-user-based threshold: generates when avg unseen
    questions per active user falls below the configured threshold.

    Runs daily to ensure adequate questions for active users.
    """
    logger.info("Starting question pool check")

    try:
        pool_manager = get_pool_manager()
        result = await pool_manager.check_and_replenish_pool()

        if result.get("skipped"):
            logger.info(
                f"Pool check skipped: {result.get('reason', 'unknown')}"
            )
        elif result["needed"]:
            logger.info(
                f"Pool replenishment complete: {result['generated']} questions added. "
                f"Distribution: {result['by_area']}"
            )
        else:
            logger.info(
                f"Pool sufficient: {result['avg_unseen']:.1f} avg unseen per active user "
                f"(threshold: {pool_manager.threshold})"
            )

    except Exception as e:
        logger.error(f"Question pool check failed: {e}")

    logger.info("Question pool check completed")


# Keep old function name as alias for backwards compatibility
maintain_question_pool = check_question_pool


async def reset_daily_limits(timezone: str) -> None:
    """
    Reset daily extra question counts for users in a specific timezone.

    Runs at midnight for each timezone, only affecting users in that timezone.

    Args:
        timezone: The timezone for which to reset limits
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    try:
        count = await repo.reset_daily_extra_counts_by_timezone(timezone)
        if count > 0:
            logger.info(f"Reset daily limits for {count} users in {timezone}")
    except Exception as e:
        logger.error(f"Failed to reset daily limits for {timezone}: {e}")


async def compute_daily_analytics_job(timezone: str) -> None:
    """
    Compute daily analytics snapshots for a timezone.

    Runs 5 minutes after midnight to ensure the day is complete.
    For Pacific timezone, also computes system-wide snapshots.

    Args:
        timezone: The timezone that just completed midnight
    """
    from src.services.analytics_service import compute_daily_analytics

    try:
        result = await compute_daily_analytics(timezone)
        user_count = result.get("user_result", {}).get("users_processed", 0)
        logger.info(f"Computed analytics for {timezone}: {user_count} user snapshots")

        if result.get("system_result"):
            logger.info(
                f"System snapshots computed: {result['system_result'].get('total_answers', 0)} answers"
            )
    except Exception as e:
        logger.error(f"Failed to compute analytics for {timezone}: {e}")


async def get_unique_user_timezones() -> list[str]:
    """
    Get list of unique timezones from actual subscribed users in the database.

    This queries the database to find all distinct timezones that have
    subscribed users, ensuring we only create scheduler jobs for timezones
    that actually have users.
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    try:
        users = await repo.get_subscribed_users()
        timezones = list(set(user["timezone"] for user in users if user.get("timezone")))

        # Always include default timezone even if no users yet
        if settings.default_timezone not in timezones:
            timezones.append(settings.default_timezone)

        logger.info(f"Found {len(timezones)} unique user timezones")
        return sorted(timezones)
    except Exception as e:
        logger.error(f"Failed to get user timezones: {e}")
        # Fallback to default timezone
        return [settings.default_timezone]


def get_unique_timezones() -> list[str]:
    """
    Get list of unique timezones from common timezones.

    DEPRECATED: Use get_unique_user_timezones() instead for database-driven timezones.
    This function is kept for backwards compatibility but should not be used.
    """
    from src.config.constants import COMMON_TIMEZONES

    return [tz for tz, _ in COMMON_TIMEZONES]


async def generate_weekly_challenges() -> None:
    """
    Generate new weekly challenges at the start of each week.

    Runs every Monday at midnight (Pacific) to create 3 challenges for the week.
    """
    from datetime import date, timedelta
    import random

    from src.config.constants import CHALLENGE_TEMPLATES, ChallengeType, ContentArea

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get Monday of current week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    logger.info(f"Generating weekly challenges for week starting {week_start}")

    # Check if challenges already exist for this week
    existing = await repo.get_current_week_challenges()
    if existing:
        logger.info(f"Challenges already exist for week {week_start}, skipping generation")
        return

    # Select 3 random challenge templates
    templates = random.sample(CHALLENGE_TEMPLATES, min(3, len(CHALLENGE_TEMPLATES)))

    challenges_created = 0
    for template in templates:
        challenge_type = template["type"]
        targets = template["targets"]
        bonuses = template["bonus_points"]

        # Pick a random difficulty level
        difficulty = random.randint(0, len(targets) - 1)
        target = targets[difficulty]
        bonus = bonuses[difficulty]

        # Handle area-specific challenges
        target_area = None
        description = template["description_template"]
        if template.get("requires_area"):
            # Pick a random content area
            areas = list(ContentArea)
            target_area = random.choice(areas).value
            description = description.format(target=target, area=target_area)
        else:
            description = description.format(target=target)

        # Create the challenge
        challenge_id = await repo.create_weekly_challenge(
            week_start=week_start,
            challenge_type=challenge_type.value,
            target_value=target,
            bonus_points=bonus,
            description=description,
            target_area=target_area,
        )

        if challenge_id:
            challenges_created += 1
            logger.info(f"Created challenge: {description} (target={target}, bonus={bonus})")

    logger.info(f"Generated {challenges_created} weekly challenges for week {week_start}")


async def start_scheduler(application: Application) -> AsyncIOScheduler:
    """
    Initialize and start the APScheduler.

    Creates jobs for:
    - Morning delivery (8 AM) for each user timezone
    - Evening delivery (8 PM) for each user timezone
    - Daily limit reset (midnight) for each user timezone
    - Pool maintenance (3 AM Pacific)
    - Weekly challenge generation (Monday 12:01 AM Pacific)

    Args:
        application: Telegram bot application

    Returns:
        The started scheduler instance
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return _scheduler

    settings = get_settings()
    _scheduler = AsyncIOScheduler()

    # Get timezones from actual users in the database
    timezones = await get_unique_user_timezones()
    logger.info(f"Setting up scheduler for {len(timezones)} timezones: {timezones}")

    for timezone in timezones:
        # Morning delivery
        _scheduler.add_job(
            deliver_scheduled_questions,
            CronTrigger(
                hour=settings.morning_quiz_hour,
                minute=0,
                timezone=timezone,
            ),
            args=[application, timezone, True],
            id=f"morning_{timezone}",
            name=f"Morning delivery for {timezone}",
            replace_existing=True,
        )

        # Evening delivery
        _scheduler.add_job(
            deliver_scheduled_questions,
            CronTrigger(
                hour=settings.evening_quiz_hour,
                minute=0,
                timezone=timezone,
            ),
            args=[application, timezone, False],
            id=f"evening_{timezone}",
            name=f"Evening delivery for {timezone}",
            replace_existing=True,
        )

        # Daily limit reset at midnight - now timezone-aware
        _scheduler.add_job(
            reset_daily_limits,
            CronTrigger(
                hour=0,
                minute=0,
                timezone=timezone,
            ),
            args=[timezone],
            id=f"reset_limits_{timezone}",
            name=f"Reset daily limits for {timezone}",
            replace_existing=True,
        )

        # Daily analytics computation - 5 minutes after midnight
        _scheduler.add_job(
            compute_daily_analytics_job,
            CronTrigger(
                hour=0,
                minute=5,
                timezone=timezone,
            ),
            args=[timezone],
            id=f"analytics_{timezone}",
            name=f"Daily analytics for {timezone}",
            replace_existing=True,
        )

    # Pool maintenance - run once daily at 3 AM Pacific
    _scheduler.add_job(
        maintain_question_pool,
        CronTrigger(
            hour=3,
            minute=0,
            timezone="America/Los_Angeles",
        ),
        id="pool_maintenance",
        name="Question pool maintenance",
        replace_existing=True,
    )

    # Notification batch flush - run every 5 minutes
    _scheduler.add_job(
        flush_notification_batch,
        CronTrigger(minute="*/5"),
        id="notification_batch_flush",
        name="Flush notification batches",
        replace_existing=True,
    )

    # Weekly challenge generation - Monday at 12:01 AM Pacific
    _scheduler.add_job(
        generate_weekly_challenges,
        CronTrigger(
            day_of_week="mon",
            hour=0,
            minute=1,
            timezone="America/Los_Angeles",
        ),
        id="weekly_challenges",
        name="Generate weekly challenges",
        replace_existing=True,
    )

    # Daily admin summary - parse time from settings
    summary_hour, summary_minute = _parse_summary_time(settings.summary_time)
    _scheduler.add_job(
        send_daily_admin_summary,
        CronTrigger(
            hour=summary_hour,
            minute=summary_minute,
            timezone="America/Los_Angeles",
        ),
        id="daily_admin_summary",
        name="Daily admin summary",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(f"Scheduler started with {len(_scheduler.get_jobs())} jobs")

    return _scheduler


def stop_scheduler() -> None:
    """Stop the scheduler if running."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the current scheduler instance."""
    return _scheduler


def get_delivery_stats() -> dict[str, Any]:
    """Get delivery statistics for diagnostics."""
    return _delivery_stats.copy()


async def get_scheduler_status() -> dict[str, Any]:
    """
    Get comprehensive scheduler status for diagnostics.

    Returns:
        Dictionary with scheduler state, jobs, and delivery stats
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get user timezone breakdown
    users = await repo.get_subscribed_users()
    timezone_user_counts: dict[str, int] = {}
    for user in users:
        tz = user.get("timezone", "Unknown")
        timezone_user_counts[tz] = timezone_user_counts.get(tz, 0) + 1

    # Get scheduled jobs info
    jobs_info = []
    if _scheduler:
        for job in _scheduler.get_jobs():
            next_run = job.next_run_time
            jobs_info.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
            })

    return {
        "running": _scheduler is not None and _scheduler.running if _scheduler else False,
        "total_jobs": len(jobs_info) if _scheduler else 0,
        "jobs": jobs_info,
        "delivery_stats": get_delivery_stats(),
        "subscribed_users": len(users),
        "users_by_timezone": timezone_user_counts,
        "morning_hour": settings.morning_quiz_hour,
        "evening_hour": settings.evening_quiz_hour,
    }


async def refresh_scheduler_timezones(application: Application) -> int:
    """
    Refresh scheduler jobs to include any new user timezones.

    This can be called when a user selects a new timezone to ensure
    their timezone has scheduler jobs.

    Args:
        application: Telegram bot application

    Returns:
        Number of new timezone jobs added
    """
    global _scheduler

    if _scheduler is None:
        logger.warning("Scheduler not running, cannot refresh timezones")
        return 0

    settings = get_settings()
    current_timezones = await get_unique_user_timezones()

    # Get existing job timezones
    existing_timezones = set()
    for job in _scheduler.get_jobs():
        if job.id.startswith("morning_"):
            existing_timezones.add(job.id.replace("morning_", ""))

    # Find new timezones
    new_timezones = set(current_timezones) - existing_timezones
    added_count = 0

    for timezone in new_timezones:
        logger.info(f"Adding scheduler jobs for new timezone: {timezone}")

        # Morning delivery
        _scheduler.add_job(
            deliver_scheduled_questions,
            CronTrigger(
                hour=settings.morning_quiz_hour,
                minute=0,
                timezone=timezone,
            ),
            args=[application, timezone, True],
            id=f"morning_{timezone}",
            name=f"Morning delivery for {timezone}",
            replace_existing=True,
        )

        # Evening delivery
        _scheduler.add_job(
            deliver_scheduled_questions,
            CronTrigger(
                hour=settings.evening_quiz_hour,
                minute=0,
                timezone=timezone,
            ),
            args=[application, timezone, False],
            id=f"evening_{timezone}",
            name=f"Evening delivery for {timezone}",
            replace_existing=True,
        )

        # Daily limit reset
        _scheduler.add_job(
            reset_daily_limits,
            CronTrigger(
                hour=0,
                minute=0,
                timezone=timezone,
            ),
            args=[timezone],
            id=f"reset_limits_{timezone}",
            name=f"Reset daily limits for {timezone}",
            replace_existing=True,
        )

        # Daily analytics computation
        _scheduler.add_job(
            compute_daily_analytics_job,
            CronTrigger(
                hour=0,
                minute=5,
                timezone=timezone,
            ),
            args=[timezone],
            id=f"analytics_{timezone}",
            name=f"Daily analytics for {timezone}",
            replace_existing=True,
        )

        added_count += 1

    if added_count > 0:
        logger.info(f"Added scheduler jobs for {added_count} new timezones")

    return added_count
