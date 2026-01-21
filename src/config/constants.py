"""
Application constants for AbaQuiz.

Contains BCBA content areas, achievement definitions, and other static values.
"""

from enum import Enum


class ContentArea(str, Enum):
    """BCBA 5th Edition Task List content areas."""

    # Section 1: Foundations
    PHILOSOPHICAL_UNDERPINNINGS = "Philosophical Underpinnings"
    CONCEPTS_AND_PRINCIPLES = "Concepts and Principles"
    MEASUREMENT = "Measurement, Data Display, and Interpretation"
    EXPERIMENTAL_DESIGN = "Experimental Design"

    # Section 2: Applications
    ETHICS = "Ethics"
    BEHAVIOR_ASSESSMENT = "Behavior Assessment"
    BEHAVIOR_CHANGE_PROCEDURES = "Behavior-Change Procedures"
    INTERVENTIONS = "Selecting and Implementing Interventions"
    SUPERVISION = "Personnel Supervision and Management"


# Shorthand aliases for /quiz command
CONTENT_AREA_ALIASES: dict[str, ContentArea] = {
    # Full names (lowercase)
    "philosophical underpinnings": ContentArea.PHILOSOPHICAL_UNDERPINNINGS,
    "concepts and principles": ContentArea.CONCEPTS_AND_PRINCIPLES,
    "measurement": ContentArea.MEASUREMENT,
    "experimental design": ContentArea.EXPERIMENTAL_DESIGN,
    "ethics": ContentArea.ETHICS,
    "behavior assessment": ContentArea.BEHAVIOR_ASSESSMENT,
    "behavior-change procedures": ContentArea.BEHAVIOR_CHANGE_PROCEDURES,
    "interventions": ContentArea.INTERVENTIONS,
    "supervision": ContentArea.SUPERVISION,
    # Short aliases
    "philosophy": ContentArea.PHILOSOPHICAL_UNDERPINNINGS,
    "philosophical": ContentArea.PHILOSOPHICAL_UNDERPINNINGS,
    "concepts": ContentArea.CONCEPTS_AND_PRINCIPLES,
    "principles": ContentArea.CONCEPTS_AND_PRINCIPLES,
    "data": ContentArea.MEASUREMENT,
    "experiment": ContentArea.EXPERIMENTAL_DESIGN,
    "design": ContentArea.EXPERIMENTAL_DESIGN,
    "assessment": ContentArea.BEHAVIOR_ASSESSMENT,
    "behavior change": ContentArea.BEHAVIOR_CHANGE_PROCEDURES,
    "procedures": ContentArea.BEHAVIOR_CHANGE_PROCEDURES,
    "intervention": ContentArea.INTERVENTIONS,
    "supervise": ContentArea.SUPERVISION,
    "management": ContentArea.SUPERVISION,
}


class QuestionType(str, Enum):
    """Types of quiz questions."""

    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"


class AchievementType(str, Enum):
    """Achievement/badge types."""

    # Milestones
    FIRST_STEPS = "first_steps"  # First question answered
    CENTURY_CLUB = "century_club"  # 100 questions answered
    KNOWLEDGE_SEEKER = "knowledge_seeker"  # 500 questions answered

    # Streaks
    WEEK_WARRIOR = "week_warrior"  # 7-day streak
    MONTHLY_MASTER = "monthly_master"  # 30-day streak
    STREAK_LEGEND = "streak_legend"  # 100-day streak

    # Performance
    PERFECT_WEEK = "perfect_week"  # 14/14 correct in a week

    # Content area mastery (90%+ accuracy with 20+ answers)
    ETHICS_EXPERT = "ethics_expert"
    ASSESSMENT_ACE = "assessment_ace"
    PROCEDURES_PRO = "procedures_pro"
    FOUNDATIONS_MASTER = "foundations_master"
    DESIGN_SPECIALIST = "design_specialist"


# Achievement definitions with requirements and display info
ACHIEVEMENTS: dict[AchievementType, dict] = {
    AchievementType.FIRST_STEPS: {
        "name": "First Steps",
        "description": "Answer your first question",
        "badge": "🎯",
        "requirement": {"type": "questions_answered", "count": 1},
    },
    AchievementType.CENTURY_CLUB: {
        "name": "Century Club",
        "description": "Answer 100 questions",
        "badge": "💯",
        "requirement": {"type": "questions_answered", "count": 100},
    },
    AchievementType.KNOWLEDGE_SEEKER: {
        "name": "Knowledge Seeker",
        "description": "Answer 500 questions",
        "badge": "📚",
        "requirement": {"type": "questions_answered", "count": 500},
    },
    AchievementType.WEEK_WARRIOR: {
        "name": "Week Warrior",
        "description": "Maintain a 7-day streak",
        "badge": "🔥",
        "requirement": {"type": "streak", "days": 7},
    },
    AchievementType.MONTHLY_MASTER: {
        "name": "Monthly Master",
        "description": "Maintain a 30-day streak",
        "badge": "⭐",
        "requirement": {"type": "streak", "days": 30},
    },
    AchievementType.STREAK_LEGEND: {
        "name": "Streak Legend",
        "description": "Maintain a 100-day streak",
        "badge": "👑",
        "requirement": {"type": "streak", "days": 100},
    },
    AchievementType.PERFECT_WEEK: {
        "name": "Perfect Week",
        "description": "Answer all 14 questions correctly in one week",
        "badge": "🏆",
        "requirement": {"type": "perfect_week", "correct": 14, "total": 14},
    },
    AchievementType.ETHICS_EXPERT: {
        "name": "Ethics Expert",
        "description": "90%+ accuracy in Ethics (20+ questions)",
        "badge": "⚖️",
        "requirement": {
            "type": "content_mastery",
            "area": ContentArea.ETHICS,
            "accuracy": 0.9,
            "min_answers": 20,
        },
    },
    AchievementType.ASSESSMENT_ACE: {
        "name": "Assessment Ace",
        "description": "90%+ accuracy in Behavior Assessment (20+ questions)",
        "badge": "📊",
        "requirement": {
            "type": "content_mastery",
            "area": ContentArea.BEHAVIOR_ASSESSMENT,
            "accuracy": 0.9,
            "min_answers": 20,
        },
    },
    AchievementType.PROCEDURES_PRO: {
        "name": "Procedures Pro",
        "description": "90%+ accuracy in Behavior-Change Procedures (20+ questions)",
        "badge": "🔧",
        "requirement": {
            "type": "content_mastery",
            "area": ContentArea.BEHAVIOR_CHANGE_PROCEDURES,
            "accuracy": 0.9,
            "min_answers": 20,
        },
    },
    AchievementType.FOUNDATIONS_MASTER: {
        "name": "Foundations Master",
        "description": "90%+ accuracy in all Section 1 areas (20+ questions each)",
        "badge": "🏛️",
        "requirement": {
            "type": "section_mastery",
            "section": 1,
            "accuracy": 0.9,
            "min_answers": 20,
        },
    },
    AchievementType.DESIGN_SPECIALIST: {
        "name": "Design Specialist",
        "description": "90%+ accuracy in Experimental Design (20+ questions)",
        "badge": "🔬",
        "requirement": {
            "type": "content_mastery",
            "area": ContentArea.EXPERIMENTAL_DESIGN,
            "accuracy": 0.9,
            "min_answers": 20,
        },
    },
}


# Points configuration
class Points:
    """Point values for various actions."""

    CORRECT_ANSWER = 10
    CORRECT_WITH_STREAK_7 = 15
    CORRECT_WITH_STREAK_30 = 20
    FIRST_QUESTION_OF_DAY_BONUS = 5


# Common timezones for selection (legacy - kept for compatibility)
COMMON_TIMEZONES = [
    ("America/Los_Angeles", "Pacific (PT)"),
    ("America/Denver", "Mountain (MT)"),
    ("America/Chicago", "Central (CT)"),
    ("America/New_York", "Eastern (ET)"),
    ("America/Anchorage", "Alaska (AKT)"),
    ("Pacific/Honolulu", "Hawaii (HT)"),
]

# Timezone regions with common timezones per region
TIMEZONE_REGIONS: dict[str, list[tuple[str, str]]] = {
    "americas": [
        ("America/New_York", "Eastern (ET) - New York"),
        ("America/Chicago", "Central (CT) - Chicago"),
        ("America/Denver", "Mountain (MT) - Denver"),
        ("America/Los_Angeles", "Pacific (PT) - Los Angeles"),
        ("America/Anchorage", "Alaska (AKT)"),
        ("America/Sao_Paulo", "São Paulo (BRT)"),
        ("America/Mexico_City", "Mexico City (CST)"),
    ],
    "europe": [
        ("Europe/London", "London (GMT/BST)"),
        ("Europe/Paris", "Paris / Berlin (CET)"),
        ("Europe/Moscow", "Moscow (MSK)"),
        ("Africa/Johannesburg", "Johannesburg (SAST)"),
        ("Africa/Lagos", "Lagos (WAT)"),
    ],
    "asia_pacific": [
        ("Asia/Dubai", "Dubai (GST)"),
        ("Asia/Kolkata", "India (IST)"),
        ("Asia/Singapore", "Singapore (SGT)"),
        ("Asia/Tokyo", "Tokyo (JST)"),
        ("Asia/Shanghai", "China (CST)"),
        ("Australia/Sydney", "Sydney (AEST)"),
        ("Pacific/Auckland", "Auckland (NZST)"),
    ],
}

REGION_LABELS: dict[str, str] = {
    "americas": "🌎 Americas",
    "europe": "🌍 Europe / Africa",
    "asia_pacific": "🌏 Asia / Pacific",
}
