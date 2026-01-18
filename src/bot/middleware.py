"""
Middleware decorators for AbaQuiz bot handlers.

Provides access control, rate limiting, and filtering.
"""

import random
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Callable, Coroutine, Optional

from telegram import Update
from telegram.ext import ContextTypes

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.database.repository import get_repository

logger = get_logger(__name__)

# Rate limit tracking: {user_id: [timestamps]}
_rate_limit_cache: dict[int, list[float]] = defaultdict(list)


def dm_only_middleware(
    func: Callable[..., Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Middleware to only allow direct messages (private chats).

    Group chats are silently ignored.
    """

    @wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not update.effective_chat:
            return None

        # Only allow private chats
        if update.effective_chat.type != "private":
            logger.debug(
                f"Ignored message from non-private chat: {update.effective_chat.id}"
            )
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


def ban_check_middleware(
    func: Callable[..., Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Middleware to block banned users.

    Banned users receive a random ABA-themed rejection message.
    """

    @wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not update.effective_user:
            return None

        user_id = update.effective_user.id
        settings = get_settings()
        repo = await get_repository(settings.database_path)

        if await repo.is_banned(user_id):
            # Send rejection message
            if update.effective_message and settings.rejection_messages:
                message = random.choice(settings.rejection_messages)
                message = message.format(user_id=user_id)
                await update.effective_message.reply_text(message)

            logger.info(f"Blocked banned user: {user_id}")
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


def rate_limit_middleware(
    requests_per_minute: Optional[int] = None,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, Any]]],
    Callable[..., Coroutine[Any, Any, Any]],
]:
    """
    Middleware to enforce rate limits.

    Args:
        requests_per_minute: Max requests per minute (uses config default if None)
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, Any]]
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @wraps(func)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if not update.effective_user:
                return None

            user_id = update.effective_user.id
            settings = get_settings()
            limit = requests_per_minute or settings.requests_per_minute

            now = time.time()
            minute_ago = now - 60

            # Clean old timestamps
            _rate_limit_cache[user_id] = [
                ts for ts in _rate_limit_cache[user_id] if ts > minute_ago
            ]

            # Check limit
            if len(_rate_limit_cache[user_id]) >= limit:
                logger.warning(f"Rate limit exceeded for user {user_id}")

                if update.effective_message:
                    await update.effective_message.reply_text(
                        "You're sending too many requests. Please slow down."
                    )
                return None

            # Record this request
            _rate_limit_cache[user_id].append(now)

            return await func(update, context, *args, **kwargs)

        return wrapper

    return decorator


def admin_middleware(
    func: Callable[..., Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Middleware to restrict access to admin users only.
    """

    @wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not update.effective_user:
            return None

        user_id = update.effective_user.id
        settings = get_settings()

        if not settings.is_admin(user_id):
            logger.warning(f"Non-admin user {user_id} tried to access admin command")

            if update.effective_message:
                await update.effective_message.reply_text(
                    "This command is only available to administrators."
                )
            return None

        return await func(update, context, *args, **kwargs)

    return wrapper


def ensure_user_exists(
    func: Callable[..., Coroutine[Any, Any, Any]]
) -> Callable[..., Coroutine[Any, Any, Any]]:
    """
    Middleware to ensure user exists in database before handler runs.

    Creates user if they don't exist.
    """

    @wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if not update.effective_user:
            return None

        user = update.effective_user
        settings = get_settings()
        repo = await get_repository(settings.database_path)

        # Check if user exists
        db_user = await repo.get_user_by_telegram_id(user.id)

        if not db_user:
            # Create new user
            await repo.create_user(
                telegram_id=user.id,
                username=user.username,
                timezone=settings.default_timezone,
            )
            logger.info(f"Auto-created user {user.id}")

        return await func(update, context, *args, **kwargs)

    return wrapper
