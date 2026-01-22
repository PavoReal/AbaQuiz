"""
Admin notification service for AbaQuiz.

Provides comprehensive admin notifications with real-time alerts,
batching for medium-priority events, and daily summaries.
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository

if TYPE_CHECKING:
    from telegram.ext import Application

logger = get_logger(__name__)


class NotificationPriority(Enum):
    """Priority levels for notifications."""

    CRITICAL = "critical"  # Always send immediately
    HIGH = "high"  # Real-time + summary
    MEDIUM = "medium"  # Batch (5min) + summary
    LOW = "low"  # Summary only


class NotificationEventType(Enum):
    """Types of notification events."""

    # Critical - always send
    SYSTEM_ERROR = "system_error"
    DATABASE_ERROR = "database_error"

    # High - real-time + summary
    DELIVERY_FAILURE = "delivery_failure"
    API_ANOMALY = "api_anomaly"
    GENERATION_FAILED = "generation_failed"
    POOL_LOW = "pool_low"

    # Medium - batch + summary
    QUESTION_REPORT = "question_report"
    GENERATION_COMPLETE = "generation_complete"
    BAN_ACTION = "ban_action"

    # Low - summary only
    USER_MILESTONE = "user_milestone"
    NEW_USER = "new_user"
    ADMIN_ACTION = "admin_action"


# Priority mapping for each event type
EVENT_PRIORITIES: dict[NotificationEventType, NotificationPriority] = {
    NotificationEventType.SYSTEM_ERROR: NotificationPriority.CRITICAL,
    NotificationEventType.DATABASE_ERROR: NotificationPriority.CRITICAL,
    NotificationEventType.DELIVERY_FAILURE: NotificationPriority.HIGH,
    NotificationEventType.API_ANOMALY: NotificationPriority.HIGH,
    NotificationEventType.GENERATION_FAILED: NotificationPriority.HIGH,
    NotificationEventType.POOL_LOW: NotificationPriority.HIGH,
    NotificationEventType.QUESTION_REPORT: NotificationPriority.MEDIUM,
    NotificationEventType.GENERATION_COMPLETE: NotificationPriority.MEDIUM,
    NotificationEventType.BAN_ACTION: NotificationPriority.MEDIUM,
    NotificationEventType.USER_MILESTONE: NotificationPriority.LOW,
    NotificationEventType.NEW_USER: NotificationPriority.LOW,
    NotificationEventType.ADMIN_ACTION: NotificationPriority.LOW,
}

# Default behaviors for each event type
DEFAULT_BEHAVIORS: dict[NotificationEventType, dict[str, bool]] = {
    NotificationEventType.SYSTEM_ERROR: {"realtime": True, "summary": True},
    NotificationEventType.DATABASE_ERROR: {"realtime": True, "summary": True},
    NotificationEventType.DELIVERY_FAILURE: {"realtime": True, "summary": True},
    NotificationEventType.API_ANOMALY: {"realtime": True, "summary": True},
    NotificationEventType.GENERATION_FAILED: {"realtime": True, "summary": True},
    NotificationEventType.POOL_LOW: {"realtime": True, "summary": True},
    NotificationEventType.QUESTION_REPORT: {"realtime": True, "summary": True},
    NotificationEventType.GENERATION_COMPLETE: {"realtime": False, "summary": True},
    NotificationEventType.BAN_ACTION: {"realtime": True, "summary": True},
    NotificationEventType.USER_MILESTONE: {"realtime": False, "summary": True},
    NotificationEventType.NEW_USER: {"realtime": False, "summary": True},
    NotificationEventType.ADMIN_ACTION: {"realtime": False, "summary": True},
}


class NotificationService:
    """
    Service for sending admin notifications.

    Features:
    - Real-time alerts for critical/high priority events
    - Batching for medium priority events (every 5 minutes)
    - Daily summaries for all events
    - Per-admin, per-event-type granular controls
    - Deduplication within a time window
    """

    def __init__(self, application: "Application") -> None:
        self.application = application
        self.settings = get_settings()

        # Batch queue for medium priority events
        self._batch_queue: list[dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()

        # Deduplication tracking (event_type:key -> timestamp)
        self._recent_events: dict[str, datetime] = {}
        self._dedup_window_seconds = self.settings.notification_dedup_window_seconds

        # Batch flush interval (minutes)
        self._batch_interval_minutes = self.settings.notification_batch_interval_minutes

    async def notify(
        self,
        event_type: NotificationEventType,
        title: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
        dedup_key: Optional[str] = None,
    ) -> None:
        """
        Send a notification to admins.

        Args:
            event_type: Type of notification event
            title: Short title for the notification
            message: Detailed message body
            metadata: Optional metadata for logging/summaries
            dedup_key: Optional key for deduplication (prevents spam)
        """
        priority = EVENT_PRIORITIES.get(event_type, NotificationPriority.LOW)

        # Check deduplication
        if dedup_key:
            cache_key = f"{event_type.value}:{dedup_key}"
            now = datetime.now()
            if cache_key in self._recent_events:
                last_sent = self._recent_events[cache_key]
                if (now - last_sent).total_seconds() < self._dedup_window_seconds:
                    logger.debug(f"Skipping duplicate notification: {cache_key}")
                    return
            self._recent_events[cache_key] = now

        # Log the event
        repo = await get_repository(self.settings.database_path)
        log_id = await repo.log_notification_event(
            event_type=event_type.value,
            priority=priority.value,
            title=title,
            message=message,
            metadata=metadata,
        )

        # Determine handling based on priority
        if priority == NotificationPriority.CRITICAL:
            # Critical events always sent immediately to all admins
            await self._send_to_all_admins(event_type, title, message, log_id)
        elif priority == NotificationPriority.HIGH:
            # High priority events sent immediately if realtime is enabled
            await self._send_realtime(event_type, title, message, log_id)
        elif priority == NotificationPriority.MEDIUM:
            # Medium priority events are batched
            async with self._batch_lock:
                self._batch_queue.append({
                    "event_type": event_type,
                    "title": title,
                    "message": message,
                    "log_id": log_id,
                    "timestamp": datetime.now(),
                })
        # Low priority events are only logged for summaries

    async def _send_to_all_admins(
        self,
        event_type: NotificationEventType,
        title: str,
        message: str,
        log_id: int,
    ) -> None:
        """Send notification to all admins (for critical events)."""
        repo = await get_repository(self.settings.database_path)

        for admin_id in self.settings.admin_users:
            try:
                formatted_message = self._format_notification(
                    event_type, title, message
                )
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=formatted_message,
                )
                logger.info(f"Sent critical notification to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send notification to admin {admin_id}: {e}")

        await repo.mark_notification_sent(log_id)

    async def _send_realtime(
        self,
        event_type: NotificationEventType,
        title: str,
        message: str,
        log_id: int,
    ) -> None:
        """Send real-time notification to admins with realtime enabled."""
        repo = await get_repository(self.settings.database_path)
        default_behavior = DEFAULT_BEHAVIORS.get(event_type, {})

        for admin_id in self.settings.admin_users:
            # Check admin's settings for this event type
            settings = await repo.get_admin_notification_setting(
                admin_id, event_type.value
            )

            if settings:
                realtime_enabled = settings.get("realtime_enabled", True)
            else:
                realtime_enabled = default_behavior.get("realtime", True)

            if not realtime_enabled:
                continue

            try:
                formatted_message = self._format_notification(
                    event_type, title, message
                )
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=formatted_message,
                )
            except Exception as e:
                logger.error(f"Failed to send notification to admin {admin_id}: {e}")

        await repo.mark_notification_sent(log_id)

    async def flush_batch(self) -> None:
        """Flush batched notifications to admins."""
        async with self._batch_lock:
            if not self._batch_queue:
                return

            batch = self._batch_queue.copy()
            self._batch_queue.clear()

        if not batch:
            return

        logger.info(f"Flushing {len(batch)} batched notifications")

        # Group by event type
        by_type: dict[NotificationEventType, list[dict]] = defaultdict(list)
        for item in batch:
            by_type[item["event_type"]].append(item)

        repo = await get_repository(self.settings.database_path)

        for admin_id in self.settings.admin_users:
            messages_to_send = []

            for event_type, items in by_type.items():
                # Check admin's settings
                settings = await repo.get_admin_notification_setting(
                    admin_id, event_type.value
                )
                default_behavior = DEFAULT_BEHAVIORS.get(event_type, {})

                if settings:
                    realtime_enabled = settings.get("realtime_enabled", True)
                else:
                    realtime_enabled = default_behavior.get("realtime", True)

                if not realtime_enabled:
                    continue

                # Create batch summary message
                if len(items) == 1:
                    messages_to_send.append(self._format_notification(
                        event_type, items[0]["title"], items[0]["message"]
                    ))
                else:
                    summary = f"*{event_type.value.replace('_', ' ').title()}* ({len(items)} events)\n\n"
                    for item in items[:5]:  # Limit to 5 items per type
                        summary += f"- {item['title']}\n"
                    if len(items) > 5:
                        summary += f"_...and {len(items) - 5} more_\n"
                    messages_to_send.append(summary)

            if messages_to_send:
                try:
                    combined = "\n---\n".join(messages_to_send)
                    await self.application.bot.send_message(
                        chat_id=admin_id,
                        text=combined,
                    )
                except Exception as e:
                    logger.error(f"Failed to send batch to admin {admin_id}: {e}")

        # Mark all as sent
        for item in batch:
            await repo.mark_notification_sent(item["log_id"])

    async def send_daily_summary(self) -> None:
        """Send daily summary to admins."""
        repo = await get_repository(self.settings.database_path)

        # Get unsummarized events
        events = await repo.get_unsummarized_events(hours=24)
        event_counts = await repo.get_event_counts_by_type(hours=24)

        # Get system stats
        total_users = await repo.get_user_count()
        new_users = await repo.get_new_users_count(hours=24)
        active_users_count = await repo.get_active_user_count(days=1)
        total_questions = await repo.get_total_question_count()
        api_usage = await repo.get_api_usage_stats(hours=24)

        # Build summary message
        now = datetime.now()
        summary_lines = [
            f"*Daily Admin Summary*",
            f"{now.strftime('%Y-%m-%d')}\n",
            "*System Stats:*",
            f"  Users: {total_users} total, {new_users} new",
            f"  Active (24h): {active_users_count}",
            f"  Pool: {total_questions} questions\n",
        ]

        # API usage section
        if api_usage:
            total_calls = api_usage.get("total_calls") or 0
            total_cost = api_usage.get("total_cost") or 0.0
            summary_lines.extend([
                "*API Usage (24h):*",
                f"  Calls: {total_calls}",
                f"  Cost: ${total_cost:.3f}\n",
            ])

        # Events section
        if event_counts:
            summary_lines.append("*Events (24h):*")
            for event_type, count in sorted(event_counts.items()):
                summary_lines.append(f"  {event_type}: {count}")

        summary_text = "\n".join(summary_lines)

        # Send to admins with summary enabled
        for admin_id in self.settings.admin_users:
            # Check admin's general summary setting
            admin_settings = await repo.get_admin_settings(admin_id)
            if admin_settings and not admin_settings.get("summary_enabled", True):
                continue

            try:
                await self.application.bot.send_message(
                    chat_id=admin_id,
                    text=summary_text,
                )
                logger.info(f"Sent daily summary to admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to send summary to admin {admin_id}: {e}")

        # Mark events as summarized
        if events:
            event_ids = [e["id"] for e in events]
            await repo.mark_events_summarized(event_ids)

    def _format_notification(
        self,
        event_type: NotificationEventType,
        title: str,
        message: str,
    ) -> str:
        """Format a notification message."""
        priority = EVENT_PRIORITIES.get(event_type, NotificationPriority.LOW)

        # Add priority indicator for critical/high
        if priority == NotificationPriority.CRITICAL:
            prefix = "[CRITICAL] "
        elif priority == NotificationPriority.HIGH:
            prefix = ""
        else:
            prefix = ""

        return f"{prefix}*{title}*\n\n{message}"


# Global service instance
_notification_service: Optional[NotificationService] = None


def init_notification_service(application: "Application") -> NotificationService:
    """Initialize the global notification service."""
    global _notification_service
    _notification_service = NotificationService(application)
    logger.info("Notification service initialized")
    return _notification_service


def get_notification_service() -> Optional[NotificationService]:
    """Get the notification service instance."""
    return _notification_service


# =============================================================================
# Convenience Functions
# =============================================================================


async def notify_delivery_failure(user_id: int, error: str) -> None:
    """Notify admins of a question delivery failure."""
    service = get_notification_service()
    if not service:
        return

    await service.notify(
        event_type=NotificationEventType.DELIVERY_FAILURE,
        title="Delivery Failed",
        message=(
            f"User: {user_id}\n"
            f"Error: {error}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        metadata={"user_id": user_id, "error": error},
        dedup_key=str(user_id),
    )


async def notify_system_error(component: str, error: str) -> None:
    """Notify admins of a system error."""
    service = get_notification_service()
    if not service:
        return

    await service.notify(
        event_type=NotificationEventType.SYSTEM_ERROR,
        title=f"System Error: {component}",
        message=(
            f"Component: {component}\n"
            f"Error: {error}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        metadata={"component": component, "error": error},
    )


async def notify_database_error(operation: str, error: str) -> None:
    """Notify admins of a database error."""
    service = get_notification_service()
    if not service:
        return

    await service.notify(
        event_type=NotificationEventType.DATABASE_ERROR,
        title="Database Error",
        message=(
            f"Operation: {operation}\n"
            f"Error: {error}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        metadata={"operation": operation, "error": error},
    )


async def notify_question_report(
    question_id: int,
    user_id: int,
    report_type: str,
) -> None:
    """Notify admins of a question report."""
    service = get_notification_service()
    if not service:
        return

    report_labels = {
        "incorrect_answer": "Incorrect Answer",
        "confusing_wording": "Confusing Wording",
        "outdated_content": "Outdated Content",
        "other": "Other Issue",
    }
    label = report_labels.get(report_type, report_type)

    await service.notify(
        event_type=NotificationEventType.QUESTION_REPORT,
        title="Question Reported",
        message=(
            f"Question ID: {question_id}\n"
            f"Report Type: {label}\n"
            f"User: {user_id}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        metadata={
            "question_id": question_id,
            "user_id": user_id,
            "report_type": report_type,
        },
    )


async def notify_generation_complete(
    count: int,
    by_area: dict[str, int],
) -> None:
    """Notify admins that question generation completed."""
    service = get_notification_service()
    if not service:
        return

    area_summary = "\n".join(f"  {area}: {c}" for area, c in sorted(by_area.items()))

    await service.notify(
        event_type=NotificationEventType.GENERATION_COMPLETE,
        title="Generation Complete",
        message=(
            f"Generated: {count} questions\n"
            f"Distribution:\n{area_summary}"
        ),
        metadata={"count": count, "by_area": by_area},
    )


async def notify_generation_failed(error: str, content_area: Optional[str] = None) -> None:
    """Notify admins of a question generation failure."""
    service = get_notification_service()
    if not service:
        return

    message = f"Error: {error}\n"
    if content_area:
        message += f"Content Area: {content_area}\n"
    message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    await service.notify(
        event_type=NotificationEventType.GENERATION_FAILED,
        title="Generation Failed",
        message=message,
        metadata={"error": error, "content_area": content_area},
    )


async def notify_pool_low(avg_unseen: float, threshold: int) -> None:
    """Notify admins that the question pool is low."""
    service = get_notification_service()
    if not service:
        return

    await service.notify(
        event_type=NotificationEventType.POOL_LOW,
        title="Pool Low",
        message=(
            f"Avg unseen per active user: {avg_unseen:.1f}\n"
            f"Threshold: {threshold}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        metadata={"avg_unseen": avg_unseen, "threshold": threshold},
        dedup_key="pool_low",  # Prevent spam
    )


async def notify_ban_action(
    admin_id: int,
    target_id: int,
    action: str,
    reason: Optional[str] = None,
) -> None:
    """Notify admins of a ban/unban action."""
    service = get_notification_service()
    if not service:
        return

    message = (
        f"Admin: {admin_id}\n"
        f"Target: {target_id}\n"
        f"Action: {action}"
    )
    if reason:
        message += f"\nReason: {reason}"

    await service.notify(
        event_type=NotificationEventType.BAN_ACTION,
        title=f"User {action.title()}",
        message=message,
        metadata={
            "admin_id": admin_id,
            "target_id": target_id,
            "action": action,
            "reason": reason,
        },
    )


async def notify_api_anomaly(metric: str, value: Any, threshold: Any) -> None:
    """Notify admins of an API anomaly (unusual costs, errors, etc.)."""
    service = get_notification_service()
    if not service:
        return

    await service.notify(
        event_type=NotificationEventType.API_ANOMALY,
        title="API Anomaly Detected",
        message=(
            f"Metric: {metric}\n"
            f"Value: {value}\n"
            f"Threshold: {threshold}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        metadata={"metric": metric, "value": value, "threshold": threshold},
        dedup_key=metric,
    )


async def notify_new_user(telegram_id: int, username: Optional[str] = None) -> None:
    """Notify admins of a new user registration."""
    service = get_notification_service()
    if not service:
        return

    message = f"Telegram ID: {telegram_id}"
    if username:
        message += f"\nUsername: @{username}"

    await service.notify(
        event_type=NotificationEventType.NEW_USER,
        title="New User",
        message=message,
        metadata={"telegram_id": telegram_id, "username": username},
    )


async def notify_user_milestone(
    user_id: int,
    milestone: str,
    value: Any,
) -> None:
    """Notify admins of a user milestone."""
    service = get_notification_service()
    if not service:
        return

    await service.notify(
        event_type=NotificationEventType.USER_MILESTONE,
        title=f"User Milestone: {milestone}",
        message=(
            f"User: {user_id}\n"
            f"Milestone: {milestone}\n"
            f"Value: {value}"
        ),
        metadata={"user_id": user_id, "milestone": milestone, "value": value},
    )


async def notify_admin_action(
    admin_id: int,
    action: str,
    details: Optional[str] = None,
) -> None:
    """Notify admins of an admin action (for audit logging)."""
    service = get_notification_service()
    if not service:
        return

    message = f"Admin: {admin_id}\nAction: {action}"
    if details:
        message += f"\nDetails: {details}"

    await service.notify(
        event_type=NotificationEventType.ADMIN_ACTION,
        title="Admin Action",
        message=message,
        metadata={"admin_id": admin_id, "action": action, "details": details},
    )


def get_all_event_types() -> list[NotificationEventType]:
    """Get all notification event types."""
    return list(NotificationEventType)


def get_event_priority(event_type: NotificationEventType) -> NotificationPriority:
    """Get the priority for an event type."""
    return EVENT_PRIORITIES.get(event_type, NotificationPriority.LOW)


def get_default_behavior(event_type: NotificationEventType) -> dict[str, bool]:
    """Get the default behavior for an event type."""
    return DEFAULT_BEHAVIORS.get(event_type, {"realtime": False, "summary": True})
