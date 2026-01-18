"""
Logging configuration for AbaQuiz.

Sets up structured logging with user ID prefixes for tracking.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(numeric_level)
    stdout_handler.setFormatter(formatter)
    root_logger.addHandler(stdout_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class UserContextLogger:
    """
    Logger wrapper that includes user context in messages.

    Usage:
        logger = UserContextLogger(get_logger(__name__), user_id=12345)
        logger.info("User started quiz")  # Outputs: [12345] User started quiz
    """

    def __init__(
        self,
        logger: logging.Logger,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> None:
        self._logger = logger
        self._user_id = user_id
        self._username = username

    def _format_message(self, message: str) -> str:
        """Add user context prefix to message."""
        if self._user_id:
            prefix = f"[{self._user_id}]"
            if self._username:
                prefix = f"[{self._user_id}|@{self._username}]"
            return f"{prefix} {message}"
        return message

    def debug(self, message: str, *args, **kwargs) -> None:
        self._logger.debug(self._format_message(message), *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        self._logger.info(self._format_message(message), *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        self._logger.warning(self._format_message(message), *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self._logger.error(self._format_message(message), *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        self._logger.exception(self._format_message(message), *args, **kwargs)


def log_user_action(
    logger: logging.Logger,
    user_id: int,
    action: str,
    direction: str = ">>",
) -> None:
    """
    Log a user action in the standard format.

    Args:
        logger: Logger instance
        user_id: Telegram user ID
        action: Action description (e.g., "/quiz ethics")
        direction: ">>" for incoming, "<<" for outgoing
    """
    logger.info(f"[{user_id}] {direction} {action}")
