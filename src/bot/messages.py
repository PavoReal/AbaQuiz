"""
Message templates for AbaQuiz.

Contains all bot message text and formatting functions.
"""

from typing import Any, Optional

from src.config.constants import ACHIEVEMENTS, DIFFICULTY_LEVELS, AchievementType, ContentArea


def format_source_citation(
    citation: dict[str, Any] | None,
    expanded: bool = False,
) -> tuple[str, bool]:
    """
    Format source citation for display.

    Args:
        citation: Citation dict with section, heading, quote fields
        expanded: Whether to show the full quote

    Returns:
        Tuple of (formatted_text, has_expandable_quote)
    """
    if not citation:
        return ("", False)

    section = citation.get("section", "")
    heading = citation.get("heading", "")
    quote = citation.get("quote", "")

    # If no meaningful content, return empty
    if not section and not heading and not quote:
        return ("", False)

    lines = [
        "────────────────────",
        "📖 *Source*",
    ]

    if section:
        lines.append(f"Section: {section}")
    if heading:
        lines.append(f"Heading: {heading}")

    # Truncate quote if not expanded and > 100 chars
    has_expandable = False
    if quote:
        if not expanded and len(quote) > 100:
            # Truncate at word boundary
            truncated = quote[:100].rsplit(" ", 1)[0]
            if len(truncated) < 50:
                # If truncation at word boundary is too short, just cut at 100
                truncated = quote[:100]
            quote_display = f'_"{truncated}..."_'
            has_expandable = True
        else:
            quote_display = f'_"{quote}"_'
        lines.append("")
        lines.append(quote_display)

    return ("\n".join(lines), has_expandable)


def format_welcome_message() -> str:
    """Format the initial welcome message for new users."""
    return """Welcome to AbaQuiz! 🎓

I'll help you prepare for the BCBA exam with daily quiz questions on Applied Behavior Analysis.

Let's set up your preferences to get started..."""


def format_timezone_prompt() -> str:
    """Format the timezone selection prompt."""
    return """First, let's set your timezone so I can send questions at the right time.

Select your timezone:"""


def format_focus_areas_prompt() -> str:
    """Format the focus areas selection prompt."""
    return """Which BCBA content areas would you like to focus on?

Select the areas you want to prioritize (they'll appear more often in your questions), or choose "All areas equally" for balanced coverage.

You can select multiple areas:"""


def format_how_it_works() -> str:
    """Format the how-it-works explanation."""
    return """Here's how AbaQuiz works:

📅 **Daily Questions**: You'll receive questions at 8 AM and 8 PM (your time)

📝 **On-demand Practice**: Use /quiz anytime for extra practice

📊 **Track Progress**: Use /stats to see your performance

🔥 **Build Streaks**: Answer at least one question daily to maintain your streak!

Ready for your first question?"""


def format_question(
    question: dict[str, Any],
    show_area: bool = True,
) -> str:
    """
    Format a quiz question for display.

    Args:
        question: Question dict with content, options, content_area
        show_area: Whether to show the content area tag

    Returns:
        Formatted question text
    """
    content = question["content"]
    options = question.get("options", {})
    content_area = question.get("content_area", "")
    question_type = question.get("question_type", "multiple_choice")

    lines = []

    # Add content area tag
    if show_area and content_area:
        lines.append(f"📚 *{content_area}*\n")

    # Add question text
    lines.append(content)
    lines.append("")

    # Add options for multiple choice
    if question_type == "multiple_choice" and options:
        for key in ["A", "B", "C", "D"]:
            if key in options:
                lines.append(f"*{key}.* {options[key]}")

    return "\n".join(lines)


def format_correct_answer(
    explanation: Optional[str] = None,
    points_earned: int = 0,
    streak: int = 0,
    new_achievement: Optional[AchievementType] = None,
    source_citation: Optional[dict[str, Any]] = None,
    expanded: bool = False,
) -> tuple[str, bool]:
    """
    Format feedback for a correct answer.

    Args:
        explanation: Brief explanation (optional for correct answers)
        points_earned: Points earned for this answer
        streak: Current streak count
        new_achievement: Newly unlocked achievement (if any)
        source_citation: Source citation dict (section, heading, quote)
        expanded: Whether to show expanded quote

    Returns:
        Tuple of (formatted_message, has_expandable_quote)
    """
    lines = ["✅ *Correct!*"]

    if explanation:
        lines.append(f"\n{explanation}")

    # Add points and streak info
    stats_parts = []
    if points_earned > 0:
        stats_parts.append(f"+{points_earned} points")
    if streak > 0:
        stats_parts.append(f"🔥 {streak} day streak")

    if stats_parts:
        lines.append(f"\n{' | '.join(stats_parts)}")

    # Add achievement notification
    if new_achievement:
        achievement = ACHIEVEMENTS.get(new_achievement, {})
        badge = achievement.get("badge", "🏆")
        name = achievement.get("name", new_achievement.value)
        lines.append(f"\n\n🎉 *Achievement Unlocked!*\n{badge} {name}")

    # Add source citation if available
    has_expandable = False
    if source_citation:
        citation_text, has_expandable = format_source_citation(source_citation, expanded)
        if citation_text:
            lines.append(f"\n{citation_text}")

    return ("\n".join(lines), has_expandable)


def format_incorrect_answer(
    correct_answer: str,
    explanation: str,
    streak_broken: bool = False,
    source_citation: Optional[dict[str, Any]] = None,
    expanded: bool = False,
) -> tuple[str, bool]:
    """
    Format feedback for an incorrect answer.

    Args:
        correct_answer: The correct answer
        explanation: Detailed explanation
        streak_broken: Whether the streak was broken
        source_citation: Source citation dict (section, heading, quote)
        expanded: Whether to show expanded quote

    Returns:
        Tuple of (formatted_message, has_expandable_quote)
    """
    lines = [f"❌ *Incorrect*\n\nThe correct answer was: *{correct_answer}*"]

    if explanation:
        lines.append(f"\n📖 *Explanation:*\n{explanation}")

    if streak_broken:
        lines.append("\n\n💔 Your streak has been reset. Keep practicing!")

    # Add source citation if available
    has_expandable = False
    if source_citation:
        citation_text, has_expandable = format_source_citation(source_citation, expanded)
        if citation_text:
            lines.append(f"\n{citation_text}")

    return ("\n".join(lines), has_expandable)


def format_stats(
    total_answered: int,
    overall_accuracy: float,
    current_streak: int,
    longest_streak: int,
    total_points: int,
    area_stats: dict[str, dict[str, Any]],
) -> str:
    """
    Format user statistics display.

    Args:
        total_answered: Total questions answered
        overall_accuracy: Overall accuracy (0-1)
        current_streak: Current streak days
        longest_streak: Longest streak days
        total_points: Total points earned
        area_stats: Per-area statistics

    Returns:
        Formatted stats message
    """
    lines = ["📊 *Your Statistics*\n"]

    # Overall stats
    accuracy_pct = overall_accuracy * 100
    lines.append(f"📝 Questions Answered: {total_answered}")
    lines.append(f"✅ Overall Accuracy: {accuracy_pct:.1f}%")
    lines.append(f"⭐ Total Points: {total_points:,}")
    lines.append(f"🔥 Current Streak: {current_streak} days")
    lines.append(f"🏆 Longest Streak: {longest_streak} days")

    # Per-area breakdown
    if area_stats:
        lines.append("\n*Performance by Area:*")
        for area, stats in sorted(area_stats.items()):
            total = stats.get("total", 0)
            accuracy = stats.get("accuracy", 0) * 100

            # Determine indicator
            if accuracy >= 80:
                indicator = "🟢"
            elif accuracy >= 60:
                indicator = "🟡"
            else:
                indicator = "🔴"

            lines.append(f"{indicator} {area}: {accuracy:.0f}% ({total})")

    return "\n".join(lines)


def format_streak(current: int, longest: int) -> str:
    """
    Format streak display.

    Args:
        current: Current streak days
        longest: Longest streak days

    Returns:
        Formatted streak message
    """
    # Create visual streak indicator
    if current == 0:
        fire = "No active streak"
    elif current < 7:
        fire = "🔥" * current
    elif current < 30:
        fire = "🔥" * 7 + f" +{current - 7}"
    else:
        fire = "🔥" * 7 + f" 🌟 {current} days!"

    lines = [
        "🔥 *Streak Status*\n",
        f"Current: {current} days",
        fire,
        f"\nLongest: {longest} days",
    ]

    if current > 0 and current == longest:
        lines.append("\n🎉 You're at your personal best!")

    return "\n".join(lines)


def format_achievements(
    unlocked: list[dict[str, Any]],
    show_progress: bool = True,
) -> str:
    """
    Format achievements display.

    Args:
        unlocked: List of unlocked achievement dicts
        show_progress: Whether to show progress toward next achievements

    Returns:
        Formatted achievements message
    """
    lines = ["🏆 *Your Achievements*\n"]

    if not unlocked:
        lines.append("You haven't unlocked any achievements yet.")
        lines.append("\nKeep answering questions to earn badges!")
    else:
        # Group by type
        for achievement in unlocked:
            achievement_type = achievement.get("achievement_type")
            try:
                at = AchievementType(achievement_type)
                info = ACHIEVEMENTS.get(at, {})
                badge = info.get("badge", "🏆")
                name = info.get("name", achievement_type)
                desc = info.get("description", "")
                lines.append(f"{badge} *{name}*")
                if desc:
                    lines.append(f"   _{desc}_")
            except ValueError:
                lines.append(f"🏆 {achievement_type}")

    return "\n".join(lines)


def format_areas_list(
    area_stats: Optional[dict[str, dict[str, Any]]] = None,
) -> str:
    """
    Format list of BCBA content areas.

    Args:
        area_stats: Optional per-area stats to show accuracy

    Returns:
        Formatted areas list
    """
    lines = ["📚 *BCBA Content Areas*\n"]

    lines.append("*Section 1: Foundations*")
    section_1 = [
        ContentArea.PHILOSOPHICAL_UNDERPINNINGS,
        ContentArea.CONCEPTS_AND_PRINCIPLES,
        ContentArea.MEASUREMENT,
        ContentArea.EXPERIMENTAL_DESIGN,
    ]
    for area in section_1:
        stat_str = ""
        if area_stats and area.value in area_stats:
            acc = area_stats[area.value]["accuracy"] * 100
            stat_str = f" ({acc:.0f}%)"
        lines.append(f"  • {area.value}{stat_str}")

    lines.append("\n*Section 2: Applications*")
    section_2 = [
        ContentArea.ETHICS,
        ContentArea.BEHAVIOR_ASSESSMENT,
        ContentArea.BEHAVIOR_CHANGE_PROCEDURES,
        ContentArea.INTERVENTIONS,
        ContentArea.SUPERVISION,
    ]
    for area in section_2:
        stat_str = ""
        if area_stats and area.value in area_stats:
            acc = area_stats[area.value]["accuracy"] * 100
            stat_str = f" ({acc:.0f}%)"
        lines.append(f"  • {area.value}{stat_str}")

    lines.append("\n_Use /quiz [area] to practice a specific area_")
    lines.append("_Example: /quiz ethics_")

    return "\n".join(lines)


def format_help() -> str:
    """Format help message with available commands."""
    return """*AbaQuiz Commands*

📝 *Quiz*
/quiz - Get a practice question
/quiz [area] - Question from specific area
/daily - View latest daily question
/areas - List content areas

📊 *Progress*
/stats - View your statistics
/streak - View your streak
/achievements - View your badges

⚙️ *Settings*
/settings - Manage preferences
/difficulty - Set minimum question difficulty
/stop - Unsubscribe from daily questions
/start - Resubscribe

❓ *Help*
/help - Show this message

_Questions are sent daily at 8 AM and 8 PM your time._"""


def format_difficulty_prompt(current_level: int) -> str:
    """
    Format the difficulty selection prompt.

    Args:
        current_level: User's current minimum difficulty level (1-5)
    """
    current_info = DIFFICULTY_LEVELS.get(current_level, DIFFICULTY_LEVELS[1])

    lines = [
        "📊 *Difficulty Setting*\n",
        f"Current: {current_info['emoji']} *{current_info['name']}*\n",
        "Choose the minimum difficulty level for your questions:\n",
    ]

    for level, info in DIFFICULTY_LEVELS.items():
        lines.append(f"{info['emoji']} *{info['name']}*")
        lines.append(f"   _{info['description']}_\n")

    lines.append("_Higher levels show only harder questions._")

    return "\n".join(lines)


def format_difficulty_updated(new_level: int) -> str:
    """
    Format confirmation after difficulty change.

    Args:
        new_level: The new minimum difficulty level (1-5)
    """
    info = DIFFICULTY_LEVELS.get(new_level, DIFFICULTY_LEVELS[1])
    return (
        f"✅ Difficulty updated to {info['emoji']} *{info['name']}*\n\n"
        f"You'll now receive questions at difficulty level {new_level} or higher."
    )


def format_daily_limit_reached(limit: int) -> str:
    """Format message when daily extra question limit is reached."""
    return f"""You've reached your daily limit of {limit} extra questions.

Your limit will reset at midnight (your timezone).

Don't forget - you'll receive your scheduled questions at 8 AM and 8 PM!"""


def format_admin_help() -> str:
    """Format admin help message."""
    return """*Admin Commands*

👥 *User Management*
/users - List all users
/users active - Active users (7 days)
/ban <user> - Ban a user
/unban <user> - Unban a user
/delete <user> - Delete user data

📊 *User Data*
/history <user> - User progress
/stats <user> - User statistics
/reset streak <user> - Reset streak
/grant achievement <user> <badge>
/adjust points <user> <amount>

📢 *System*
/broadcast <message> - Message all users
/bonus confirm - Push bonus question to all users (1x/day)
/usage - API usage stats
/notify - Notification settings
/scheduler - Scheduler status & diagnostics

_<user> can be @username or user ID_"""


def format_no_daily_questions(timezone: str) -> str:
    """Format message when user has no daily questions yet."""
    return f"""You haven't received any daily questions yet.

Daily questions are delivered at:
  - 8:00 AM ({timezone})
  - 8:00 PM ({timezone})

In the meantime, use /quiz to practice anytime!"""


def format_daily_question_summary(question_data: dict[str, Any]) -> str:
    """Format a summary of an answered daily question."""
    content = question_data["content"]
    content_area = question_data.get("content_area", "")
    user_answer = question_data["user_answer"]
    correct_answer = question_data["correct_answer"]
    is_correct = question_data["is_correct"]
    explanation = question_data.get("explanation", "")
    options = question_data.get("options", {})
    question_type = question_data.get("question_type", "multiple_choice")

    lines = ["*Your latest daily question:*\n"]

    if content_area:
        lines.append(f"_{content_area}_\n")

    lines.append(content)
    lines.append("")

    # Show options for multiple choice with markers
    if question_type == "multiple_choice" and options:
        for key in ["A", "B", "C", "D"]:
            if key in options:
                marker = ""
                if key.upper() == correct_answer.upper():
                    marker = " [Correct]"
                elif key.upper() == user_answer.upper():
                    marker = " [Your answer]"
                lines.append(f"*{key}.* {options[key]}{marker}")
        lines.append("")

    if is_correct:
        lines.append("*Result:* Correct!")
    else:
        lines.append(f"*Result:* Incorrect")
        lines.append(f"You answered: *{user_answer}*")
        lines.append(f"Correct answer: *{correct_answer}*")

    if explanation:
        lines.append(f"\n*Explanation:*\n{explanation}")

    return "\n".join(lines)
