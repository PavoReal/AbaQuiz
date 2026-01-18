"""Configuration module for AbaQuiz."""

from src.config.constants import (
    ACHIEVEMENTS,
    COMMON_TIMEZONES,
    CONTENT_AREA_ALIASES,
    AchievementType,
    ContentArea,
    Points,
    QuestionType,
)
from src.config.logging import (
    UserContextLogger,
    get_logger,
    log_user_action,
    setup_logging,
)
from src.config.settings import Settings, get_settings

__all__ = [
    # Settings
    "Settings",
    "get_settings",
    # Constants
    "ContentArea",
    "CONTENT_AREA_ALIASES",
    "QuestionType",
    "AchievementType",
    "ACHIEVEMENTS",
    "Points",
    "COMMON_TIMEZONES",
    # Logging
    "setup_logging",
    "get_logger",
    "log_user_action",
    "UserContextLogger",
]
