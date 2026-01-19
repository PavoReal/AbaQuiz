"""
AbaQuiz - BCBA Exam Preparation Telegram Bot

Entry point for the application.

Usage:
    python -m src.main              # Run bot + web server
    python -m src.main --web-only   # Run web server only (no bot)
"""

import argparse
import asyncio
import signal

from src.config.logging import get_logger, setup_logging
from src.config.settings import get_settings
from src.database.migrations import initialize_database
from src.services.content_validator import validate_content_on_startup

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AbaQuiz - BCBA Exam Prep Bot")
    parser.add_argument(
        "--web-only",
        action="store_true",
        help="Run only the web admin server (no Telegram bot)",
    )
    # Database CLI commands
    parser.add_argument(
        "--db-list",
        action="store_true",
        help="List recent questions",
    )
    parser.add_argument(
        "--db-show",
        type=int,
        metavar="ID",
        help="Show question by ID",
    )
    parser.add_argument(
        "--db-stats",
        action="store_true",
        help="Show pool statistics",
    )
    parser.add_argument(
        "--db-validate",
        action="store_true",
        help="Validate all questions have proper options",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit for --db-list (default: 20)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON for external tools (use with --db-* commands)",
    )
    return parser.parse_args()


async def db_cli(args: argparse.Namespace) -> None:
    """Handle database CLI commands."""
    import json

    from src.database.repository import get_repository

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    try:
        use_json = args.json

        if args.db_stats:
            counts = await repo.get_question_pool_counts()
            total = await repo.get_total_question_count()
            if use_json:
                print(json.dumps({"total": total, "by_area": counts}, indent=2))
            else:
                print(f"\nQuestion Pool Stats ({total} total)\n" + "=" * 40)
                for area, count in sorted(counts.items()):
                    print(f"  {area}: {count}")

        elif args.db_list:
            result = await repo.browse_questions(page=1, per_page=args.limit)
            if use_json:
                # Output full question data as JSON array
                print(json.dumps(result["rows"], indent=2, default=str))
            else:
                print(f"\nRecent Questions ({result['total']} total)\n" + "=" * 60)
                for q in result["rows"]:
                    opts = q.get("options", {})
                    opt_keys = ",".join(opts.keys()) if opts else "NONE"
                    text = q["content"][:50] + "..." if len(q["content"]) > 50 else q["content"]
                    print(f"[{q['id']}] {q['content_area'][:15]:<15} opts={opt_keys:<10} {text}")

        elif args.db_show is not None:
            q = await repo.get_question_by_id(args.db_show)
            if q:
                print(json.dumps(q, indent=2, default=str))
            else:
                if use_json:
                    print(json.dumps({"error": f"Question {args.db_show} not found"}))
                else:
                    print(f"Question {args.db_show} not found")

        elif args.db_validate:
            result = await repo.browse_questions(page=1, per_page=9999)
            invalid = []
            for q in result["rows"]:
                opts = q.get("options", {})
                qtype = q.get("question_type", "multiple_choice")

                if qtype == "multiple_choice":
                    expected = {"A", "B", "C", "D"}
                    if not opts or set(opts.keys()) != expected:
                        invalid.append({"id": q["id"], "reason": f"MC missing keys: {list(opts.keys())}"})
                    elif any(not v for v in opts.values()):
                        invalid.append({"id": q["id"], "reason": "MC has empty option values"})
                elif qtype == "true_false":
                    if not opts or "True" not in opts or "False" not in opts:
                        invalid.append({"id": q["id"], "reason": f"TF missing keys: {list(opts.keys())}"})

            if use_json:
                print(json.dumps({
                    "total": result["total"],
                    "invalid_count": len(invalid),
                    "invalid": invalid,
                }, indent=2))
            else:
                if invalid:
                    print(f"\nFound {len(invalid)} invalid questions:\n" + "=" * 40)
                    for item in invalid:
                        print(f"  [{item['id']}] {item['reason']}")
                else:
                    print(f"\nAll {result['total']} questions have valid options")
    finally:
        await repo.close()


async def run_web_only() -> None:
    """Run only the web admin server."""
    from aiohttp import web
    from src.web.server import create_app

    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info("Starting AbaQuiz web server (web-only mode)...")

    # Initialize database
    await initialize_database(settings.database_path)
    logger.info("Database initialized")

    # Validate content files (warn on missing, don't fail)
    validate_content_on_startup(strict=False)

    # Create and start web server
    web_app = create_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, settings.web_host, settings.web_port)
    await site.start()
    logger.info(f"Admin web UI: http://{settings.web_host}:{settings.web_port}")

    # Wait for shutdown signal
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info("Web server running. Press Ctrl+C to stop.")
    await stop_event.wait()

    # Cleanup
    logger.info("Shutting down...")
    await runner.cleanup()
    logger.info("Web server stopped")


def register_handlers(application) -> None:
    """Register all bot handlers."""
    from telegram.ext import CallbackQueryHandler, CommandHandler

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
        health_command,
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
    application.add_handler(CommandHandler("health", health_command))

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


async def run_bot() -> None:
    """Initialize and run the bot with optional web server."""
    from telegram.ext import Application

    from src.services.scheduler import start_scheduler, stop_scheduler

    # Load settings (validates required env vars)
    settings = get_settings()

    # Set up logging
    setup_logging(settings.log_level)

    logger.info("Starting AbaQuiz bot...")

    # Initialize database
    await initialize_database(settings.database_path)
    logger.info("Database initialized")

    # Validate content files (warn on missing, don't fail)
    validate_content_on_startup(strict=False)

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

    # Start web server if enabled
    web_runner = None
    if settings.web_enabled:
        try:
            from aiohttp import web
            from src.web.server import create_app

            web_app = create_app()
            web_runner = web.AppRunner(web_app)
            await web_runner.setup()
            site = web.TCPSite(web_runner, settings.web_host, settings.web_port)
            await site.start()
            logger.info(f"Admin web UI: http://{settings.web_host}:{settings.web_port}")
        except ImportError:
            logger.warning("aiohttp not installed, web admin UI disabled")
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")

    logger.info("Bot initialized, starting polling...")

    # Use manual async lifecycle to avoid event loop conflicts
    # This is required when running async code before the bot starts
    stop_event = asyncio.Event()

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    async with application:
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        logger.info("Bot is running. Press Ctrl+C to stop.")

        # Wait until stop signal is received
        await stop_event.wait()

        # Graceful shutdown
        logger.info("Shutting down...")
        await application.updater.stop()
        await application.stop()

    # Cleanup web server
    if web_runner:
        await web_runner.cleanup()

    # Clean up scheduler on shutdown
    stop_scheduler()
    logger.info("Bot stopped")


def main() -> None:
    """Entry point."""
    args = parse_args()

    # DB CLI mode - read and exit
    if args.db_list or args.db_show is not None or args.db_stats or args.db_validate:
        asyncio.run(db_cli(args))
        return

    if args.web_only:
        asyncio.run(run_web_only())
    else:
        asyncio.run(run_bot())


if __name__ == "__main__":
    main()
