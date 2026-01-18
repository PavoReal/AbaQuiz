"""
Telegram command and callback handlers for AbaQuiz.

Handles all user interactions with the bot.
"""

import json
from datetime import date
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.bot import keyboards, messages
from src.bot.middleware import (
    ban_check_middleware,
    dm_only_middleware,
    ensure_user_exists,
    rate_limit_middleware,
)
from src.config.constants import (
    ACHIEVEMENTS,
    CONTENT_AREA_ALIASES,
    AchievementType,
    ContentArea,
    Points,
)
from src.config.logging import get_logger, log_user_action
from src.config.settings import get_settings
from src.database.repository import get_repository

logger = get_logger(__name__)


# =============================================================================
# Onboarding Handlers
# =============================================================================


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /start command - begin onboarding or welcome back."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    log_user_action(logger, user.id, "/start")

    # Check if user exists
    db_user = await repo.get_user_by_telegram_id(user.id)

    if db_user and db_user.get("onboarding_complete"):
        # Returning user
        await update.message.reply_text(
            "Welcome back! Use /quiz to get a practice question, "
            "or /help to see all commands.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # New user or incomplete onboarding - create/update user
    if not db_user:
        await repo.create_user(
            telegram_id=user.id,
            username=user.username,
            timezone=settings.default_timezone,
        )

    # Send welcome message
    await update.message.reply_text(
        messages.format_welcome_message(),
        parse_mode=ParseMode.MARKDOWN,
    )

    # Start onboarding - timezone selection
    await update.message.reply_text(
        messages.format_timezone_prompt(),
        reply_markup=keyboards.build_timezone_keyboard(),
    )

    # Store onboarding state
    context.user_data["onboarding_step"] = "timezone"


@dm_only_middleware
@ban_check_middleware
async def timezone_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle timezone selection callback."""
    if not update.callback_query or not update.effective_user:
        return

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data or ""

    if not data.startswith("timezone:"):
        return

    timezone = data.replace("timezone:", "")

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    if timezone == "custom":
        # Ask user to type timezone
        await query.edit_message_text(
            "Please type your timezone (e.g., 'America/New_York', 'Europe/London'):"
        )
        context.user_data["onboarding_step"] = "timezone_custom"
        return

    # Save timezone
    await repo.update_user(user_id, timezone=timezone)

    # Move to focus areas step
    await query.edit_message_text(
        messages.format_focus_areas_prompt(),
        reply_markup=keyboards.build_focus_areas_keyboard(),
    )
    context.user_data["onboarding_step"] = "focus_areas"
    context.user_data["selected_focus_areas"] = set()


@dm_only_middleware
@ban_check_middleware
async def focus_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle focus area selection callback."""
    if not update.callback_query or not update.effective_user:
        return

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data or ""

    if not data.startswith("focus:"):
        return

    action = data.replace("focus:", "")
    selected: set = context.user_data.get("selected_focus_areas", set())

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    if action == "all":
        # Clear selections (all areas equally)
        selected.clear()
    elif action == "done":
        # Save preferences and continue
        focus_list = list(selected) if selected else []
        await repo.update_user(user_id, focus_preferences=focus_list)

        # Show how it works
        await query.edit_message_text(
            messages.format_how_it_works(),
            parse_mode=ParseMode.MARKDOWN,
        )

        # Mark onboarding complete
        await repo.update_user(user_id, onboarding_complete=True)

        # Send first question
        await send_question_to_user(user_id, context, is_scheduled=False)
        context.user_data.pop("onboarding_step", None)
        context.user_data.pop("selected_focus_areas", None)
        return
    else:
        # Toggle area selection
        if action in selected:
            selected.discard(action)
        else:
            selected.add(action)

    context.user_data["selected_focus_areas"] = selected

    # Update keyboard
    await query.edit_message_text(
        messages.format_focus_areas_prompt(),
        reply_markup=keyboards.build_focus_areas_keyboard(selected),
    )


# =============================================================================
# Quiz Handlers
# =============================================================================


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
@ensure_user_exists
async def quiz_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /quiz command - request a practice question."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    log_user_action(logger, user.id, f"/quiz {' '.join(context.args or [])}")

    # Get user from database
    db_user = await repo.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Please use /start first.")
        return

    # Check daily limit
    if db_user["daily_extra_count"] >= settings.extra_questions_per_day:
        await update.message.reply_text(
            messages.format_daily_limit_reached(settings.extra_questions_per_day)
        )
        return

    # Check if area specified
    content_area: Optional[str] = None
    if context.args:
        area_query = " ".join(context.args).lower()
        # Look up in aliases
        content_area_enum = CONTENT_AREA_ALIASES.get(area_query)
        if content_area_enum:
            content_area = content_area_enum.value
        else:
            # Try exact match
            for area in ContentArea:
                if area.value.lower() == area_query:
                    content_area = area.value
                    break

        if not content_area:
            await update.message.reply_text(
                f"Unknown content area: '{area_query}'\n\n"
                "Use /areas to see available options."
            )
            return

    if content_area:
        # Send question from specified area
        await send_question_to_user(
            user.id,
            context,
            content_area=content_area,
            is_scheduled=False,
        )
    else:
        # Show area selection menu
        await update.message.reply_text(
            "Choose a content area for your question:",
            reply_markup=keyboards.build_content_area_keyboard(prefix="quiz"),
        )


@dm_only_middleware
@ban_check_middleware
async def quiz_area_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle content area selection for quiz."""
    if not update.callback_query or not update.effective_user:
        return

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data or ""

    if not data.startswith("quiz:"):
        return

    area = data.replace("quiz:", "")

    # Delete the menu message
    await query.delete_message()

    # Send question
    content_area = None if area == "random" else area
    await send_question_to_user(
        user_id,
        context,
        content_area=content_area,
        is_scheduled=False,
    )


async def send_question_to_user(
    user_id: int,
    context: ContextTypes.DEFAULT_TYPE,
    content_area: Optional[str] = None,
    is_scheduled: bool = True,
) -> bool:
    """
    Send a question to a user.

    Args:
        user_id: Telegram user ID
        context: Bot context
        content_area: Specific content area (None for algorithm selection)
        is_scheduled: Whether this is a scheduled question

    Returns:
        True if question was sent successfully
    """
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get user
    db_user = await repo.get_user_by_telegram_id(user_id)
    if not db_user:
        logger.warning(f"User {user_id} not found")
        return False

    internal_user_id = db_user["id"]

    # Select content area if not specified
    if not content_area:
        content_area = await select_content_area_for_user(internal_user_id, repo)

    # Get unseen question
    question = await repo.get_unseen_question_for_user(
        internal_user_id,
        content_area=content_area,
    )

    if not question:
        # No questions available
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="No new questions available right now. Check back later!",
            )
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
        return False

    # Format and send question
    question_text = messages.format_question(question)
    keyboard = keyboards.build_answer_keyboard(
        question_id=question["id"],
        question_type=question["question_type"],
        options=question.get("options"),
    )

    try:
        message = await context.bot.send_message(
            chat_id=user_id,
            text=question_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN,
        )

        # Record sent question
        await repo.record_sent_question(
            user_id=internal_user_id,
            question_id=question["id"],
            message_id=message.message_id,
            is_scheduled=is_scheduled,
        )

        # Increment daily count for non-scheduled questions
        if not is_scheduled:
            await repo.update_user(
                user_id,
                daily_extra_count=db_user["daily_extra_count"] + 1,
            )

        log_user_action(
            logger, user_id, f"[Question {question['id']}]", direction="<<"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send question to {user_id}: {e}")
        return False


async def select_content_area_for_user(
    user_id: int,
    repo,
) -> Optional[str]:
    """
    Select content area using hybrid algorithm.

    20% chance to target weak area, 80% weighted random.
    """
    import random

    settings = get_settings()

    # Get user preferences
    user = await repo.get_user_by_id(user_id)
    focus_prefs = []
    if user and user.get("focus_preferences"):
        try:
            focus_prefs = json.loads(user["focus_preferences"])
        except json.JSONDecodeError:
            pass

    # Roll for weak area targeting
    if random.random() < settings.weak_area_ratio:
        weak_area = await repo.get_user_weakest_area(
            user_id,
            min_answers=settings.min_answers_for_weak_calc,
        )
        if weak_area:
            return weak_area

    # Weighted random selection
    areas = [area.value for area in ContentArea]
    weights = []

    for area in areas:
        if area in focus_prefs:
            weights.append(settings.focus_preference_weight)
        else:
            weights.append(1.0)

    return random.choices(areas, weights=weights, k=1)[0]


# =============================================================================
# Answer Handler
# =============================================================================


@dm_only_middleware
@ban_check_middleware
async def answer_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle answer selection callback."""
    if not update.callback_query or not update.effective_user:
        return

    query = update.callback_query
    user = update.effective_user
    data = query.data or ""

    if not data.startswith("answer:"):
        return

    # Parse callback data
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("Invalid answer data")
        return

    _, question_id_str, user_answer = parts
    try:
        question_id = int(question_id_str)
    except ValueError:
        await query.answer("Invalid question ID")
        return

    settings = get_settings()
    repo = await get_repository(settings.database_path)

    # Get user
    db_user = await repo.get_user_by_telegram_id(user.id)
    if not db_user:
        await query.answer("Please use /start first")
        return

    internal_user_id = db_user["id"]

    # Check if already answered
    if await repo.has_user_answered_question(internal_user_id, question_id):
        await query.answer("You've already answered this question!")
        return

    # Get question
    question = await repo.get_question_by_id(question_id)
    if not question:
        await query.answer("Question not found")
        return

    # Check answer
    is_correct = user_answer.upper() == question["correct_answer"].upper()

    # Record answer
    await repo.record_answer(
        user_id=internal_user_id,
        question_id=question_id,
        user_answer=user_answer,
        is_correct=is_correct,
    )

    # Update streak
    today = date.today()
    new_streak, streak_increased = await repo.update_streak(internal_user_id, today)

    # Calculate points
    points = 0
    if is_correct:
        if new_streak >= 30:
            points = Points.CORRECT_WITH_STREAK_30
        elif new_streak >= 7:
            points = Points.CORRECT_WITH_STREAK_7
        else:
            points = Points.CORRECT_ANSWER

        # First question of day bonus
        stats = await repo.get_user_stats(internal_user_id)
        if stats and stats.get("last_answer_date") != today.isoformat():
            points += Points.FIRST_QUESTION_OF_DAY_BONUS

        await repo.add_points(internal_user_id, points)

    # Check for new achievements
    new_achievement = await check_achievements(internal_user_id, repo)

    # Format response
    if is_correct:
        response = messages.format_correct_answer(
            points_earned=points,
            streak=new_streak,
            new_achievement=new_achievement,
        )
    else:
        response = messages.format_incorrect_answer(
            correct_answer=question["correct_answer"],
            explanation=question["explanation"],
            streak_broken=not streak_increased and new_streak == 1,
        )

    await query.answer("Correct! ✅" if is_correct else "Incorrect ❌")

    # Edit original message to show result
    try:
        # Keep the question visible but disable buttons
        original_text = query.message.text if query.message else ""
        await query.edit_message_text(
            f"{original_text}\n\n{'─' * 20}\n\n{response}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")

    log_user_action(
        logger,
        user.id,
        f"Answer Q{question_id}: {user_answer} ({'✓' if is_correct else '✗'})",
    )


async def check_achievements(
    user_id: int,
    repo,
) -> Optional[AchievementType]:
    """
    Check and award any newly earned achievements.

    Returns the first newly unlocked achievement, if any.
    """
    stats = await repo.get_user_stats(user_id)
    if not stats:
        return None

    total_answered = await repo.get_total_questions_answered(user_id)
    current_streak = stats.get("current_streak", 0)

    new_achievement = None

    # Check question count achievements
    count_achievements = [
        (1, AchievementType.FIRST_STEPS),
        (100, AchievementType.CENTURY_CLUB),
        (500, AchievementType.KNOWLEDGE_SEEKER),
    ]

    for count, achievement in count_achievements:
        if total_answered >= count:
            if await repo.grant_achievement(user_id, achievement):
                new_achievement = new_achievement or achievement

    # Check streak achievements
    streak_achievements = [
        (7, AchievementType.WEEK_WARRIOR),
        (30, AchievementType.MONTHLY_MASTER),
        (100, AchievementType.STREAK_LEGEND),
    ]

    for days, achievement in streak_achievements:
        if current_streak >= days:
            if await repo.grant_achievement(user_id, achievement):
                new_achievement = new_achievement or achievement

    # Check content area mastery (90%+ with 20+ answers)
    area_stats = await repo.get_user_accuracy_by_area(user_id)
    mastery_achievements = [
        (ContentArea.ETHICS, AchievementType.ETHICS_EXPERT),
        (ContentArea.BEHAVIOR_ASSESSMENT, AchievementType.ASSESSMENT_ACE),
        (ContentArea.BEHAVIOR_CHANGE_PROCEDURES, AchievementType.PROCEDURES_PRO),
        (ContentArea.EXPERIMENTAL_DESIGN, AchievementType.DESIGN_SPECIALIST),
    ]

    for area, achievement in mastery_achievements:
        area_stat = area_stats.get(area.value, {})
        if area_stat.get("total", 0) >= 20 and area_stat.get("accuracy", 0) >= 0.9:
            if await repo.grant_achievement(user_id, achievement):
                new_achievement = new_achievement or achievement

    return new_achievement


# =============================================================================
# Stats Commands
# =============================================================================


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
@ensure_user_exists
async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /stats command."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    log_user_action(logger, user.id, "/stats")

    db_user = await repo.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Please use /start first.")
        return

    internal_user_id = db_user["id"]

    # Gather stats
    user_stats = await repo.get_user_stats(internal_user_id)
    total_answered = await repo.get_total_questions_answered(internal_user_id)
    overall_accuracy = await repo.get_overall_accuracy(internal_user_id)
    area_stats = await repo.get_user_accuracy_by_area(internal_user_id)

    response = messages.format_stats(
        total_answered=total_answered,
        overall_accuracy=overall_accuracy,
        current_streak=user_stats.get("current_streak", 0) if user_stats else 0,
        longest_streak=user_stats.get("longest_streak", 0) if user_stats else 0,
        total_points=user_stats.get("total_points", 0) if user_stats else 0,
        area_stats=area_stats,
    )

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
@ensure_user_exists
async def streak_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /streak command."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    log_user_action(logger, user.id, "/streak")

    db_user = await repo.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Please use /start first.")
        return

    user_stats = await repo.get_user_stats(db_user["id"])

    response = messages.format_streak(
        current=user_stats.get("current_streak", 0) if user_stats else 0,
        longest=user_stats.get("longest_streak", 0) if user_stats else 0,
    )

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
@ensure_user_exists
async def achievements_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /achievements command."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    log_user_action(logger, user.id, "/achievements")

    db_user = await repo.get_user_by_telegram_id(user.id)
    if not db_user:
        await update.message.reply_text("Please use /start first.")
        return

    achievements = await repo.get_user_achievements(db_user["id"])

    response = messages.format_achievements(achievements)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
async def areas_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /areas command."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    log_user_action(logger, user.id, "/areas")

    # Get user stats if they exist
    area_stats = None
    db_user = await repo.get_user_by_telegram_id(user.id)
    if db_user:
        area_stats = await repo.get_user_accuracy_by_area(db_user["id"])

    response = messages.format_areas_list(area_stats)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /help command."""
    if not update.effective_user or not update.message:
        return

    log_user_action(logger, update.effective_user.id, "/help")

    await update.message.reply_text(
        messages.format_help(),
        parse_mode=ParseMode.MARKDOWN,
    )


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
@ensure_user_exists
async def stop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /stop command - unsubscribe from daily questions."""
    if not update.effective_user or not update.message:
        return

    user = update.effective_user
    settings = get_settings()
    repo = await get_repository(settings.database_path)

    log_user_action(logger, user.id, "/stop")

    await repo.update_user(user.id, is_subscribed=False)

    await update.message.reply_text(
        "You've been unsubscribed from daily questions.\n\n"
        "You can still use /quiz for practice anytime.\n"
        "Use /start to resubscribe."
    )


@dm_only_middleware
@ban_check_middleware
@rate_limit_middleware()
@ensure_user_exists
async def settings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /settings command."""
    if not update.effective_user or not update.message:
        return

    log_user_action(logger, update.effective_user.id, "/settings")

    await update.message.reply_text(
        "⚙️ *Settings*\n\nChoose an option:",
        reply_markup=keyboards.build_settings_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


# Noop callback for section headers
async def noop_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle noop callbacks (section headers)."""
    if update.callback_query:
        await update.callback_query.answer()
