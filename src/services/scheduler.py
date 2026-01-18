"""
Scheduler service for AbaQuiz.

Handles scheduled question delivery and maintenance tasks using APScheduler.
"""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from src.config.constants import ContentArea
from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository
from src.services.question_generator import get_question_generator

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


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

        # Small delay between users to avoid rate limiting
        await asyncio.sleep(0.1)

    logger.info(
        f"Completed {period} delivery for {timezone}: "
        f"{success_count} success, {failure_count} failures"
    )


async def notify_admins_of_failure(
    application: Application,
    user_id: int,
    error: str,
) -> None:
    """
    Notify admins about a delivery failure.

    Args:
        application: Telegram bot application
        user_id: Failed user's Telegram ID
        error: Error message
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    for admin_id in settings.admin_users:
        admin_settings = await repo.get_admin_settings(admin_id)

        # Check if alerts are enabled (default to True)
        if admin_settings is None or admin_settings.get("alerts_enabled", True):
            try:
                await application.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"Delivery Failed\n\n"
                        f"User: {user_id}\n"
                        f"Error: {error}\n"
                        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"Action: Skipped delivery"
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")


async def maintain_question_pool() -> None:
    """
    Check question pool levels and generate questions if needed.

    Runs daily to ensure adequate questions in each content area.
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)
    generator = get_question_generator()

    logger.info("Starting question pool maintenance")

    # Get current pool counts
    pool_counts = await repo.get_question_pool_counts()

    for area in ContentArea:
        current_count = pool_counts.get(area.value, 0)

        if current_count < settings.pool_threshold_per_area:
            needed = settings.batch_size
            logger.info(
                f"Pool low for {area.value}: {current_count} questions. "
                f"Generating {needed} more."
            )

            try:
                questions = await generator.generate_batch(area, count=needed)

                # Store generated questions
                for q in questions:
                    await repo.create_question(
                        content=q["question"],
                        question_type=q.get("type", "multiple_choice"),
                        options=q["options"],
                        correct_answer=q["correct_answer"],
                        explanation=q["explanation"],
                        content_area=q["content_area"],
                    )

                logger.info(
                    f"Generated {len(questions)} questions for {area.value}"
                )

            except Exception as e:
                logger.error(f"Failed to generate questions for {area.value}: {e}")

    logger.info("Question pool maintenance completed")


async def reset_daily_limits() -> None:
    """
    Reset daily extra question counts for all users.

    Runs at midnight for each timezone.
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    try:
        count = await repo.reset_daily_extra_counts()
        logger.info(f"Reset daily limits for {count} users")
    except Exception as e:
        logger.error(f"Failed to reset daily limits: {e}")


def get_unique_timezones() -> list[str]:
    """Get list of unique timezones from common timezones."""
    from src.config.constants import COMMON_TIMEZONES

    return [tz for tz, _ in COMMON_TIMEZONES]


async def start_scheduler(application: Application) -> AsyncIOScheduler:
    """
    Initialize and start the APScheduler.

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

    # Schedule question delivery for each timezone
    timezones = get_unique_timezones()

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

        # Daily limit reset at midnight
        _scheduler.add_job(
            reset_daily_limits,
            CronTrigger(
                hour=0,
                minute=0,
                timezone=timezone,
            ),
            id=f"reset_limits_{timezone}",
            name=f"Reset daily limits for {timezone}",
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
