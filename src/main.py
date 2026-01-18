"""
AbaQuiz - BCBA Exam Preparation Telegram Bot

Entry point for the application.
"""

import asyncio

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
)

from src.bot.admin_handlers import (
    admin_command,
    ban_command,
    broadcast_command,
    notify_command,
    unban_command,
    usage_command,
    users_command,
)
from src.bot.handlers import (
    achievements_command,
    answer_callback,
    areas_command,
    focus_callback,
    help_command,
    noop_callback,
    quiz_area_callback,
    quiz_command,
    settings_command,
    start_command,
    stats_command,
    stop_command,
    streak_command,
    timezone_callback,
)
from src.config.logging import get_logger, setup_logging
from src.config.settings import get_settings
from src.database.migrations import initialize_database
from src.services.scheduler import start_scheduler, stop_scheduler

logger = get_logger(__name__)


def register_handlers(application: Application) -> None:
    """Register all bot handlers."""
    # User command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("quiz", quiz_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("streak", streak_command))
    application.add_handler(CommandHandler("achievements", achievements_command))
    application.add_handler(CommandHandler("areas", areas_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("settings", settings_command))

    # Admin command handlers
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("usage", usage_command))
    application.add_handler(CommandHandler("notify", notify_command))

    # Callback query handlers
    application.add_handler(
        CallbackQueryHandler(answer_callback, pattern=r"^answer:")
    )
    application.add_handler(
        CallbackQueryHandler(timezone_callback, pattern=r"^timezone:")
    )
    application.add_handler(
        CallbackQueryHandler(focus_callback, pattern=r"^focus:")
    )
    application.add_handler(
        CallbackQueryHandler(quiz_area_callback, pattern=r"^quiz:")
    )
    application.add_handler(
        CallbackQueryHandler(noop_callback, pattern=r"^noop$")
    )

    logger.info("Registered all handlers")


async def main() -> None:
    """Initialize and run the bot."""
    # Load settings (validates required env vars)
    settings = get_settings()

    # Set up logging
    setup_logging(settings.log_level)

    logger.info("Starting AbaQuiz bot...")

    # Initialize database
    await initialize_database(settings.database_path)
    logger.info("Database initialized")

    # Build application
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    # Register handlers
    register_handlers(application)

    # Start scheduler for automated question delivery
    try:
        await start_scheduler(application)
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    logger.info("Bot initialized, starting polling...")

    try:
        # Run the bot
        await application.run_polling(drop_pending_updates=True)
    finally:
        # Clean up scheduler on shutdown
        stop_scheduler()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
