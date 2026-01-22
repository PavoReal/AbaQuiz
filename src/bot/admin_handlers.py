"""
Admin command handlers for AbaQuiz.

Handles user management, broadcasting, and system monitoring.
"""

import time
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.bot import keyboards, messages
from src.bot.middleware import admin_middleware, dm_only_middleware
from src.config.logging import get_logger, log_user_action
from src.config.settings import get_settings
from src.database.repository import get_repository

logger = get_logger(__name__)


def parse_user_arg(arg: str) -> int | str | None:
    """
    Parse user argument (ID or @username).

    Args:
        arg: User argument string

    Returns:
        Integer ID, username string, or None if invalid
    """
    if not arg:
        return None

    if arg.startswith("@"):
        return arg[1:]  # Return username without @

    try:
        return int(arg)
    except ValueError:
        return arg  # Treat as username


async def resolve_user(
    repo,
    arg: str,
) -> dict | None:
    """
    Resolve user from ID or username.

    Args:
        repo: Repository instance
        arg: User ID or @username

    Returns:
        User dict or None
    """
    parsed = parse_user_arg(arg)

    if parsed is None:
        return None

    if isinstance(parsed, int):
        return await repo.get_user_by_telegram_id(parsed)
    else:
        # Search by username
        users = await repo.get_all_users()
        for user in users:
            if user.get("username") == parsed:
                return user
        return None


# =============================================================================
# Admin Help
# =============================================================================


@dm_only_middleware
@admin_middleware
async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /admin command - show admin help."""
    if not update.effective_user or not update.message:
        return

    log_user_action(logger, update.effective_user.id, "/admin")

    await update.message.reply_text(
        messages.format_admin_help(),
        parse_mode=ParseMode.MARKDOWN,
    )


# =============================================================================
# User Management
# =============================================================================


@dm_only_middleware
@admin_middleware
async def users_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /users command - list users."""
    if not update.effective_user or not update.message:
        return

    log_user_action(logger, update.effective_user.id, f"/users {' '.join(context.args or [])}")

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Check for subcommand
    args = context.args or []
    show_active = len(args) > 0 and args[0].lower() == "active"

    if show_active:
        users = await repo.get_active_users(days=7)
        title = "Active Users (7 days)"
    else:
        # Get stats
        total_count = await repo.get_user_count()
        subscribed_count = await repo.get_subscribed_user_count()
        recent_users = await repo.get_recent_users(limit=5)
        new_24h = await repo.get_new_users_count(hours=24)

        lines = [
            "*User Statistics*\n",
            f"Total Users: {total_count}",
            f"Subscribed: {subscribed_count}",
            f"New (24h): {new_24h}",
            "\n*Recent Registrations:*",
        ]

        for user in recent_users:
            username = user.get("username") or "No username"
            created = user.get("created_at", "")[:10]
            lines.append(f"  {user['telegram_id']} (@{username}) - {created}")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Show active users list
    if not users:
        await update.message.reply_text(f"No {title.lower()} found.")
        return

    lines = [f"*{title}* ({len(users)} users)\n"]
    for user in users[:20]:  # Limit to 20
        username = user.get("username") or "No username"
        lines.append(f"  {user['telegram_id']} (@{username})")

    if len(users) > 20:
        lines.append(f"\n_...and {len(users) - 20} more_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


@dm_only_middleware
@admin_middleware
async def ban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /ban command - ban a user."""
    if not update.effective_user or not update.message:
        return

    args = context.args or []
    log_user_action(logger, update.effective_user.id, f"/ban {' '.join(args)}")

    if not args:
        await update.message.reply_text(
            "Usage: /ban <user_id|@username> [reason]"
        )
        return

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Parse user argument
    user_arg = args[0]
    reason = " ".join(args[1:]) if len(args) > 1 else None

    # Try to resolve user
    user = await resolve_user(repo, user_arg)
    if user:
        telegram_id = user["telegram_id"]
    else:
        # Try direct ID
        parsed = parse_user_arg(user_arg)
        if isinstance(parsed, int):
            telegram_id = parsed
        else:
            await update.message.reply_text(
                f"User not found: {user_arg}"
            )
            return

    # Check if trying to ban an admin
    if settings.is_admin(telegram_id):
        await update.message.reply_text("Cannot ban an administrator.")
        return

    # Ban the user
    was_banned = await repo.ban_user(
        telegram_id=telegram_id,
        banned_by=update.effective_user.id,
        reason=reason,
    )

    if was_banned:
        await update.message.reply_text(
            f"User {telegram_id} has been banned."
            + (f"\nReason: {reason}" if reason else "")
        )
        # Notify other admins
        from src.services.notification_service import notify_ban_action
        await notify_ban_action(
            admin_id=update.effective_user.id,
            target_id=telegram_id,
            action="banned",
            reason=reason,
        )
    else:
        await update.message.reply_text(
            f"User {telegram_id} is already banned."
        )


@dm_only_middleware
@admin_middleware
async def unban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /unban command - unban a user."""
    if not update.effective_user or not update.message:
        return

    args = context.args or []
    log_user_action(logger, update.effective_user.id, f"/unban {' '.join(args)}")

    if not args:
        await update.message.reply_text(
            "Usage: /unban <user_id|@username>"
        )
        return

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Parse user argument
    user_arg = args[0]

    # Try to resolve user
    user = await resolve_user(repo, user_arg)
    if user:
        telegram_id = user["telegram_id"]
    else:
        # Try direct ID
        parsed = parse_user_arg(user_arg)
        if isinstance(parsed, int):
            telegram_id = parsed
        else:
            await update.message.reply_text(
                f"User not found: {user_arg}"
            )
            return

    # Unban the user
    was_unbanned = await repo.unban_user(telegram_id)

    if was_unbanned:
        await update.message.reply_text(
            f"User {telegram_id} has been unbanned."
        )
        # Notify other admins
        from src.services.notification_service import notify_ban_action
        await notify_ban_action(
            admin_id=update.effective_user.id,
            target_id=telegram_id,
            action="unbanned",
        )
    else:
        await update.message.reply_text(
            f"User {telegram_id} was not banned."
        )


# =============================================================================
# Broadcast
# =============================================================================


@dm_only_middleware
@admin_middleware
async def broadcast_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /broadcast command - send message to all subscribers."""
    if not update.effective_user or not update.message:
        return

    args = context.args or []
    message_text = " ".join(args)

    log_user_action(logger, update.effective_user.id, f"/broadcast ({len(message_text)} chars)")

    if not message_text:
        await update.message.reply_text(
            "Usage: /broadcast <message>\n\n"
            "This will send a message to all subscribed users."
        )
        return

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get all subscribed users
    users = await repo.get_subscribed_users()

    if not users:
        await update.message.reply_text("No subscribed users to broadcast to.")
        return

    # Confirm broadcast
    await update.message.reply_text(
        f"Broadcasting to {len(users)} users...\n"
        f"Message: {message_text[:100]}{'...' if len(message_text) > 100 else ''}"
    )

    success_count = 0
    failure_count = 0

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["telegram_id"],
                text=f"*Announcement*\n\n{message_text}",
                parse_mode=ParseMode.MARKDOWN,
            )
            success_count += 1
        except Exception as e:
            failure_count += 1
            logger.warning(f"Failed to broadcast to {user['telegram_id']}: {e}")

    await update.message.reply_text(
        f"Broadcast complete!\n"
        f"Sent: {success_count}\n"
        f"Failed: {failure_count}"
    )


# =============================================================================
# API Usage
# =============================================================================


@dm_only_middleware
@admin_middleware
async def usage_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /usage command - show API usage stats."""
    if not update.effective_user or not update.message:
        return

    log_user_action(logger, update.effective_user.id, "/usage")

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get usage stats for last 24 hours
    stats = await repo.get_api_usage_stats(hours=24)

    total_calls = stats.get("total_calls") or 0
    input_tokens = stats.get("total_input_tokens") or 0
    output_tokens = stats.get("total_output_tokens") or 0
    cache_write = stats.get("total_cache_write_tokens") or 0
    cache_read = stats.get("total_cache_read_tokens") or 0
    total_cost = stats.get("total_cost") or 0.0

    lines = [
        "*API Usage (Last 24h)*\n",
        f"Total Calls: {total_calls}",
        f"Input Tokens: {input_tokens:,}",
        f"Output Tokens: {output_tokens:,}",
        f"Cache Write: {cache_write:,}",
        f"Cache Read: {cache_read:,}",
        f"\nEstimated Cost: ${total_cost:.4f}",
    ]

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


# =============================================================================
# Notification Settings
# =============================================================================


@dm_only_middleware
@admin_middleware
async def notify_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Handle /notify command - manage notification settings.

    Usage:
        /notify                    - Show settings overview
        /notify list               - List all event types with status
        /notify <event> realtime on|off
        /notify <event> summary on|off
        /notify all realtime on|off
        /notify all summary on|off
    """
    if not update.effective_user or not update.message:
        return

    args = context.args or []
    log_user_action(logger, update.effective_user.id, f"/notify {' '.join(args)}")

    settings = get_settings()
    repo = await get_repository(settings.database_path)
    admin_id = update.effective_user.id

    # Import notification service types
    from src.services.notification_service import (
        get_all_event_types,
        get_default_behavior,
        get_event_priority,
    )

    all_event_types = get_all_event_types()

    if not args:
        # Show settings overview
        admin_settings = await repo.get_admin_settings(admin_id)

        summary_enabled = (
            admin_settings.get("summary_enabled", True)
            if admin_settings
            else settings.default_summary_enabled
        )
        alerts_enabled = (
            admin_settings.get("alerts_enabled", True)
            if admin_settings
            else settings.default_alerts_enabled
        )

        await update.message.reply_text(
            "*Notification Settings*\n\n"
            f"Daily Summary: {'ON' if summary_enabled else 'OFF'}\n"
            f"Real-time Alerts: {'ON' if alerts_enabled else 'OFF'}\n\n"
            "*Commands:*\n"
            "`/notify list` - Show all event types\n"
            "`/notify <event> realtime on|off`\n"
            "`/notify <event> summary on|off`\n"
            "`/notify all realtime on|off`\n"
            "`/notify all summary on|off`\n"
            "`/notify summary on|off` - Global summary\n"
            "`/notify alerts on|off` - Global alerts",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Handle "list" subcommand
    if args[0].lower() == "list":
        lines = ["*Notification Settings*\n"]

        for event_type in all_event_types:
            priority = get_event_priority(event_type)
            default = get_default_behavior(event_type)

            # Get admin's custom settings for this event type
            event_settings = await repo.get_admin_notification_setting(
                admin_id, event_type.value
            )

            if event_settings:
                rt_enabled = event_settings.get("realtime_enabled", True)
                sum_enabled = event_settings.get("summary_enabled", True)
            else:
                rt_enabled = default.get("realtime", True)
                sum_enabled = default.get("summary", True)

            rt_status = "ON" if rt_enabled else "OFF"
            sum_status = "ON" if sum_enabled else "OFF"

            lines.append(
                f"`{event_type.value}` [{priority.value}]\n"
                f"  RT:{rt_status} SUM:{sum_status}"
            )

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # Handle legacy "summary on|off" and "alerts on|off" commands
    if len(args) == 2 and args[0].lower() in ("summary", "alerts"):
        setting_type = args[0].lower()
        setting_value = args[1].lower()

        if setting_value not in ("on", "off"):
            await update.message.reply_text("Value must be 'on' or 'off'.")
            return

        enabled = setting_value == "on"

        if setting_type == "summary":
            await repo.update_admin_settings(admin_id, summary_enabled=enabled)
        else:
            await repo.update_admin_settings(admin_id, alerts_enabled=enabled)

        await update.message.reply_text(
            f"{setting_type.title()} notifications {'enabled' if enabled else 'disabled'}."
        )
        return

    # Handle granular event settings: /notify <event> realtime|summary on|off
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: /notify <event> realtime|summary on|off\n"
            "Or: /notify all realtime|summary on|off"
        )
        return

    event_arg = args[0].lower()
    setting_type = args[1].lower()
    setting_value = args[2].lower()

    if setting_type not in ("realtime", "summary"):
        await update.message.reply_text(
            "Setting type must be 'realtime' or 'summary'."
        )
        return

    if setting_value not in ("on", "off"):
        await update.message.reply_text("Value must be 'on' or 'off'.")
        return

    enabled = setting_value == "on"

    # Handle "all" - update all event types
    if event_arg == "all":
        for event_type in all_event_types:
            if setting_type == "realtime":
                await repo.update_admin_notification_setting(
                    admin_id, event_type.value, realtime_enabled=enabled
                )
            else:
                await repo.update_admin_notification_setting(
                    admin_id, event_type.value, summary_enabled=enabled
                )

        await update.message.reply_text(
            f"{setting_type.title()} {'enabled' if enabled else 'disabled'} "
            f"for all {len(all_event_types)} event types."
        )
        return

    # Find matching event type
    matching_event = None
    for event_type in all_event_types:
        if event_type.value == event_arg:
            matching_event = event_type
            break

    if not matching_event:
        # Try partial match
        matches = [et for et in all_event_types if event_arg in et.value]
        if len(matches) == 1:
            matching_event = matches[0]
        elif len(matches) > 1:
            match_names = ", ".join(m.value for m in matches)
            await update.message.reply_text(
                f"Multiple matches found: {match_names}\n"
                "Please be more specific."
            )
            return
        else:
            await update.message.reply_text(
                f"Unknown event type: {event_arg}\n"
                "Use `/notify list` to see all event types.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    # Update the specific event setting
    if setting_type == "realtime":
        await repo.update_admin_notification_setting(
            admin_id, matching_event.value, realtime_enabled=enabled
        )
    else:
        await repo.update_admin_notification_setting(
            admin_id, matching_event.value, summary_enabled=enabled
        )

    await update.message.reply_text(
        f"{matching_event.value}: {setting_type} {'enabled' if enabled else 'disabled'}."
    )


# =============================================================================
# Scheduler Diagnostics
# =============================================================================


@dm_only_middleware
@admin_middleware
async def scheduler_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /scheduler command - show scheduler status and diagnostics."""
    if not update.effective_user or not update.message:
        return

    args = context.args or []
    log_user_action(logger, update.effective_user.id, f"/scheduler {' '.join(args)}")

    from src.services.scheduler import get_scheduler_status, refresh_scheduler_timezones

    # Check for subcommand
    if args and args[0].lower() == "refresh":
        # Refresh scheduler timezones
        added = await refresh_scheduler_timezones(context.application)
        await update.message.reply_text(
            f"Scheduler timezones refreshed.\n"
            f"Added jobs for {added} new timezone(s)."
        )
        return

    # Get scheduler status
    status = await get_scheduler_status()

    lines = [
        "*Scheduler Status*\n",
        f"Running: {'Yes' if status['running'] else 'NO'}\n",
        f"Total Jobs: {status['total_jobs']}",
        f"Morning Hour: {status['morning_hour']}:00",
        f"Evening Hour: {status['evening_hour']}:00",
        f"\n*Subscribed Users:* {status['subscribed_users']}",
    ]

    # Users by timezone
    if status["users_by_timezone"]:
        lines.append("\n*Users by Timezone:*")
        for tz, count in sorted(status["users_by_timezone"].items(), key=lambda x: -x[1]):
            lines.append(f"  {tz}: {count}")

    # Delivery statistics
    stats = status["delivery_stats"]
    if stats["last_delivery"]:
        lines.append(f"\n*Delivery Stats:*")
        lines.append(f"Last Delivery: {stats['last_delivery'].strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Total Deliveries: {stats['total_deliveries']}")
        lines.append(f"Success: {stats['total_success']}")
        lines.append(f"Failures: {stats['total_failures']}")

    # Upcoming jobs (next 5)
    if status["jobs"]:
        lines.append("\n*Next Scheduled Jobs:*")
        # Sort by next_run and take first 5
        upcoming = sorted(
            [j for j in status["jobs"] if j["next_run"]],
            key=lambda x: x["next_run"]
        )[:5]
        for job in upcoming:
            # Parse and format the time
            next_run = job["next_run"][:16].replace("T", " ")
            name = job["name"][:30]
            lines.append(f"  {next_run} - {name}")

    lines.append("\n_Use /scheduler refresh to add jobs for new timezones_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )


# =============================================================================
# Bonus Question Push
# =============================================================================


@dm_only_middleware
@admin_middleware
async def bonus_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /bonus command - push bonus question to all subscribed users."""
    if not update.effective_user or not update.message:
        return

    args = context.args or []
    log_user_action(logger, update.effective_user.id, f"/bonus {' '.join(args)}")

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Check if bonus was already sent today
    bonus_sent_today = await repo.was_bonus_sent_today()
    if bonus_sent_today:
        await update.message.reply_text(
            "A bonus question was already sent today.\n\n"
            "Bonus questions can only be sent once per day."
        )
        return

    # Get all subscribed users
    users = await repo.get_subscribed_users()

    if not users:
        await update.message.reply_text("No subscribed users to send bonus questions to.")
        return

    # Check for confirmation
    if not args or args[0].lower() != "confirm":
        await update.message.reply_text(
            f"Ready to send bonus questions to {len(users)} subscribed users.\n\n"
            f"Use /bonus confirm to proceed."
        )
        return

    await _execute_bonus_push(update, context, users, repo)


async def _execute_bonus_push(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    users: list[dict],
    repo,
) -> None:
    """Execute the bonus question push to all users."""
    await update.message.reply_text(
        f"Sending bonus questions to {len(users)} users..."
    )

    success_count = 0
    failure_count = 0
    no_questions_count = 0

    for user in users:
        telegram_id = user["telegram_id"]
        internal_user_id = user["id"]

        try:
            # Get unseen question for user
            question = await repo.get_unseen_question_for_user(internal_user_id)

            if not question:
                no_questions_count += 1
                continue

            # Format and send question
            question_text = messages.format_question(question)
            keyboard = keyboards.build_answer_keyboard(
                question_id=question["id"],
                question_type=question["question_type"],
                options=question.get("options"),
            )

            message = await context.bot.send_message(
                chat_id=telegram_id,
                text=f"*Bonus Question!*\n\n{question_text}",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN,
            )

            # Record sent question with is_bonus=True
            await repo.record_sent_question(
                user_id=internal_user_id,
                question_id=question["id"],
                message_id=message.message_id,
                is_scheduled=False,
                is_bonus=True,
            )

            # Track question shown for stats
            await repo.record_question_shown(question["id"])

            # Store sent time for response time tracking
            if "question_sent_times" not in context.bot_data:
                context.bot_data["question_sent_times"] = {}
            context.bot_data["question_sent_times"][
                f"{telegram_id}:{question['id']}"
            ] = time.time()

            success_count += 1

        except Exception as e:
            failure_count += 1
            logger.warning(f"Failed to send bonus question to {telegram_id}: {e}")

    # Report results
    result_lines = [
        "Bonus push complete!\n",
        f"Sent: {success_count}",
        f"Failed: {failure_count}",
    ]
    if no_questions_count > 0:
        result_lines.append(f"No unseen questions: {no_questions_count}")

    await update.message.reply_text("\n".join(result_lines))
