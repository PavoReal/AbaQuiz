"""
Application constants for AbaQuiz.

Contains BCBA content areas, achievement definitions, and other static values.
"""

from enum import Enum, IntEnum


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

# Difficulty levels for question filtering
DIFFICULTY_LEVELS: dict[int, dict[str, str]] = {
    1: {
        "name": "Basic Recall",
        "emoji": "1️⃣",
        "description": "Straightforward factual questions",
    },
    2: {
        "name": "Understanding",
        "emoji": "2️⃣",
        "description": "Demonstrate comprehension of concepts",
    },
    3: {
        "name": "Integration",
        "emoji": "3️⃣",
        "description": "Combine multiple concepts",
    },
    4: {
        "name": "Complex Analysis",
        "emoji": "4️⃣",
        "description": "Analyze complex scenarios",
    },
    5: {
        "name": "Evaluation/Synthesis",
        "emoji": "5️⃣",
        "description": "Highest-level critical thinking",
    },
}


# =============================================================================
# GAMIFICATION SYSTEM v2
# =============================================================================


class MasteryLevel(IntEnum):
    """Content mastery levels for each BCBA area."""

    NONE = 0
    BEGINNER = 1      # 10+ questions, 60%+ accuracy
    INTERMEDIATE = 2  # 30+ questions, 75%+ accuracy
    MASTER = 3        # 50+ questions, 85%+ accuracy


MASTERY_REQUIREMENTS: dict[MasteryLevel, dict] = {
    MasteryLevel.BEGINNER: {
        "min_questions": 10,
        "min_accuracy": 0.60,
        "emoji": "🌱",
        "name": "Beginner",
    },
    MasteryLevel.INTERMEDIATE: {
        "min_questions": 30,
        "min_accuracy": 0.75,
        "emoji": "🌿",
        "name": "Intermediate",
    },
    MasteryLevel.MASTER: {
        "min_questions": 50,
        "min_accuracy": 0.85,
        "emoji": "🌳",
        "name": "Master",
    },
}


class AchievementTier(str, Enum):
    """Tiers for tiered achievements."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"


ACHIEVEMENT_TIER_INFO: dict[AchievementTier, dict] = {
    AchievementTier.BRONZE: {"emoji": "🥉", "name": "Bronze"},
    AchievementTier.SILVER: {"emoji": "🥈", "name": "Silver"},
    AchievementTier.GOLD: {"emoji": "🥇", "name": "Gold"},
}


class TieredAchievementType(str, Enum):
    """New tiered achievement types (6 total, each with Bronze/Silver/Gold)."""

    SCHOLAR = "scholar"           # Questions answered milestone
    CONSISTENT = "consistent"     # Streak days milestone
    PRECISION = "precision"       # Accuracy percentage (50+ questions)
    SPECIALIST = "specialist"     # Mastered content areas
    CHALLENGER = "challenger"     # Weekly challenges completed
    RESILIENT = "resilient"       # Comebacks after absence


# Tiered achievement definitions with requirements per tier
TIERED_ACHIEVEMENTS: dict[TieredAchievementType, dict] = {
    TieredAchievementType.SCHOLAR: {
        "name": "Scholar",
        "description": "Answer questions",
        "badge": "📚",
        "tiers": {
            AchievementTier.BRONZE: {"count": 25, "description": "Answer 25 questions"},
            AchievementTier.SILVER: {"count": 100, "description": "Answer 100 questions"},
            AchievementTier.GOLD: {"count": 500, "description": "Answer 500 questions"},
        },
        "metric": "questions_answered",
    },
    TieredAchievementType.CONSISTENT: {
        "name": "Consistent",
        "description": "Maintain daily streaks",
        "badge": "🔥",
        "tiers": {
            AchievementTier.BRONZE: {"count": 7, "description": "7-day streak"},
            AchievementTier.SILVER: {"count": 30, "description": "30-day streak"},
            AchievementTier.GOLD: {"count": 100, "description": "100-day streak"},
        },
        "metric": "peak_streak",
    },
    TieredAchievementType.PRECISION: {
        "name": "Precision",
        "description": "Achieve high accuracy (50+ questions)",
        "badge": "🎯",
        "tiers": {
            AchievementTier.BRONZE: {"accuracy": 0.70, "description": "70% accuracy"},
            AchievementTier.SILVER: {"accuracy": 0.80, "description": "80% accuracy"},
            AchievementTier.GOLD: {"accuracy": 0.90, "description": "90% accuracy"},
        },
        "metric": "accuracy",
        "min_questions": 50,
    },
    TieredAchievementType.SPECIALIST: {
        "name": "Specialist",
        "description": "Master content areas",
        "badge": "🏆",
        "tiers": {
            AchievementTier.BRONZE: {"count": 1, "description": "Master 1 area"},
            AchievementTier.SILVER: {"count": 3, "description": "Master 3 areas"},
            AchievementTier.GOLD: {"count": 6, "description": "Master 6 areas"},
        },
        "metric": "mastered_areas",
    },
    TieredAchievementType.CHALLENGER: {
        "name": "Challenger",
        "description": "Complete weekly challenges",
        "badge": "⚡",
        "tiers": {
            AchievementTier.BRONZE: {"count": 4, "description": "Complete 4 challenges"},
            AchievementTier.SILVER: {"count": 12, "description": "Complete 12 challenges"},
            AchievementTier.GOLD: {"count": 52, "description": "Complete 52 challenges"},
        },
        "metric": "challenges_completed",
    },
    TieredAchievementType.RESILIENT: {
        "name": "Resilient",
        "description": "Come back after absences",
        "badge": "💪",
        "tiers": {
            AchievementTier.BRONZE: {"count": 1, "description": "1 comeback"},
            AchievementTier.SILVER: {"count": 3, "description": "3 comebacks"},
            AchievementTier.GOLD: {"count": 5, "description": "5 comebacks"},
        },
        "metric": "comebacks",
    },
}


# Mapping old achievements to new tiered achievements for migration
ACHIEVEMENT_MIGRATION_MAP: dict[AchievementType, tuple[TieredAchievementType, AchievementTier]] = {
    AchievementType.FIRST_STEPS: (TieredAchievementType.SCHOLAR, AchievementTier.BRONZE),
    AchievementType.CENTURY_CLUB: (TieredAchievementType.SCHOLAR, AchievementTier.SILVER),
    AchievementType.KNOWLEDGE_SEEKER: (TieredAchievementType.SCHOLAR, AchievementTier.GOLD),
    AchievementType.WEEK_WARRIOR: (TieredAchievementType.CONSISTENT, AchievementTier.BRONZE),
    AchievementType.MONTHLY_MASTER: (TieredAchievementType.CONSISTENT, AchievementTier.SILVER),
    AchievementType.STREAK_LEGEND: (TieredAchievementType.CONSISTENT, AchievementTier.GOLD),
}


# Streak decay configuration
STREAK_DECAY_CONFIG: dict[str, int] = {
    "decay_rate_per_day": 1,    # Lose 1 streak point per missed day (after grace)
    "grace_period_days": 1,     # First missed day = no decay
    "max_decay_per_period": 7,  # Cap weekly decay at 7 regardless of days missed
}


# Weekly challenge types
class ChallengeType(str, Enum):
    """Types of weekly challenges."""

    QUESTIONS_ANSWERED = "questions_answered"  # Answer X questions this week
    CORRECT_ANSWERS = "correct_answers"        # Get X correct this week
    AREA_FOCUS = "area_focus"                  # Answer X questions in specific area
    ACCURACY_TARGET = "accuracy_target"        # Achieve X% accuracy for the week
    STREAK_MAINTAIN = "streak_maintain"        # Don't miss any days this week


CHALLENGE_TEMPLATES: list[dict] = [
    {
        "type": ChallengeType.QUESTIONS_ANSWERED,
        "description_template": "Answer {target} questions this week",
        "targets": [10, 14, 20],  # Easy, Medium, Hard
        "bonus_points": [25, 50, 100],
    },
    {
        "type": ChallengeType.CORRECT_ANSWERS,
        "description_template": "Get {target} questions correct this week",
        "targets": [7, 10, 14],
        "bonus_points": [30, 60, 120],
    },
    {
        "type": ChallengeType.AREA_FOCUS,
        "description_template": "Answer {target} questions in {area}",
        "targets": [5, 7, 10],
        "bonus_points": [25, 50, 100],
        "requires_area": True,
    },
    {
        "type": ChallengeType.ACCURACY_TARGET,
        "description_template": "Achieve {target}% accuracy this week (min 7 questions)",
        "targets": [70, 80, 90],
        "bonus_points": [40, 80, 150],
        "min_questions": 7,
    },
    {
        "type": ChallengeType.STREAK_MAINTAIN,
        "description_template": "Answer at least one question every day this week",
        "targets": [7],  # Always 7 days
        "bonus_points": [75],
    },
]


# Comeback bonus configuration
COMEBACK_CONFIG: dict[str, int | list] = {
    "min_inactive_days": 7,           # Minimum days inactive to qualify
    "bonus_multiplier": 2,            # Points multiplier for first question back
    "bonus_questions": 3,             # Number of bonus questions to offer
    "bonus_expiry_hours": 48,         # Hours until bonus expires
    "inactive_thresholds": [7, 14, 30],  # Days for escalating bonuses
    "bonus_points": [25, 50, 100],       # Points for each threshold
}


# Seasonal event types
class SeasonalEventType(str, Enum):
    """Types of seasonal events."""

    DOUBLE_POINTS = "double_points"        # 2x points for all questions
    FOCUS_AREA = "focus_area"              # Bonus for specific area
    SPEED_CHALLENGE = "speed_challenge"    # Bonus for quick answers
    MARATHON = "marathon"                  # Answer many questions


# Leaderboard configuration
LEADERBOARD_CONFIG: dict[str, int | list] = {
    "display_count": 10,           # Number of users to show on leaderboard
    "snapshot_periods": ["weekly", "monthly", "all_time"],
    "points_for_ranking": True,    # Use points (not streaks) for ranking
}


# Silly animal names for anonymous leaderboard display
ANIMAL_ADJECTIVES: list[str] = [
    "Agile", "Bold", "Calm", "Daring", "Eager", "Fierce", "Gentle", "Happy",
    "Icy", "Jolly", "Keen", "Lively", "Mighty", "Noble", "Odd", "Proud",
    "Quick", "Rare", "Swift", "Tough", "Unique", "Vivid", "Wise", "Zesty",
    "Amber", "Bright", "Cosmic", "Dusty", "Epic", "Fluffy", "Golden", "Hazy",
]

ANIMAL_NAMES: list[str] = [
    "Aardvark", "Bear", "Capybara", "Dolphin", "Eagle", "Fox", "Giraffe",
    "Hedgehog", "Ibex", "Jackal", "Koala", "Lemur", "Moose", "Narwhal",
    "Otter", "Panda", "Quokka", "Raccoon", "Sloth", "Tiger", "Urial",
    "Viper", "Walrus", "Xerus", "Yak", "Zebra", "Alpaca", "Badger",
    "Chinchilla", "Dingo", "Elephant", "Flamingo", "Gecko", "Hippo",
]
