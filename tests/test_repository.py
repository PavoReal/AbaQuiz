"""
Tests for database repository operations.
"""

from datetime import date, timedelta

import pytest

from src.config.constants import AchievementType


@pytest.mark.asyncio
async def test_create_user(repository, sample_user_data):
    """Test creating a new user."""
    user_id = await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
        username=sample_user_data["username"],
        timezone=sample_user_data["timezone"],
    )

    assert user_id is not None
    assert user_id > 0

    # Verify user was created
    user = await repository.get_user_by_telegram_id(sample_user_data["telegram_id"])
    assert user is not None
    assert user["telegram_id"] == sample_user_data["telegram_id"]
    assert user["username"] == sample_user_data["username"]
    assert user["timezone"] == sample_user_data["timezone"]


@pytest.mark.asyncio
async def test_update_user(repository, sample_user_data):
    """Test updating user fields."""
    # Create user first
    await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
        username=sample_user_data["username"],
    )

    # Update timezone
    await repository.update_user(
        sample_user_data["telegram_id"],
        timezone="Europe/London",
    )

    # Verify update
    user = await repository.get_user_by_telegram_id(sample_user_data["telegram_id"])
    assert user["timezone"] == "Europe/London"


@pytest.mark.asyncio
async def test_create_question(repository, sample_question):
    """Test creating a new question."""
    question_id = await repository.create_question(
        content=sample_question["content"],
        question_type=sample_question["question_type"],
        options=sample_question["options"],
        correct_answer=sample_question["correct_answer"],
        explanation=sample_question["explanation"],
        content_area=sample_question["content_area"],
    )

    assert question_id is not None
    assert question_id > 0

    # Verify question was created
    question = await repository.get_question_by_id(question_id)
    assert question is not None
    assert question["content"] == sample_question["content"]
    assert question["correct_answer"] == sample_question["correct_answer"]
    assert question["options"] == sample_question["options"]


@pytest.mark.asyncio
async def test_record_answer(repository, sample_user_data, sample_question):
    """Test recording a user answer."""
    # Create user and question
    user_id = await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
    )
    question_id = await repository.create_question(
        content=sample_question["content"],
        question_type=sample_question["question_type"],
        options=sample_question["options"],
        correct_answer=sample_question["correct_answer"],
        explanation=sample_question["explanation"],
        content_area=sample_question["content_area"],
    )

    # Record answer
    answer_id = await repository.record_answer(
        user_id=user_id,
        question_id=question_id,
        user_answer="B",
        is_correct=True,
    )

    assert answer_id is not None

    # Verify answer was recorded
    has_answered = await repository.has_user_answered_question(user_id, question_id)
    assert has_answered is True


@pytest.mark.asyncio
async def test_streak_calculation(repository, sample_user_data):
    """Test streak calculation logic."""
    user_id = await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
    )

    # First answer - should start streak at 1
    today = date.today()
    streak, increased = await repository.update_streak(user_id, today)
    assert streak == 1
    assert increased is True

    # Same day - should not change
    streak, increased = await repository.update_streak(user_id, today)
    assert streak == 1
    assert increased is False

    # Next day - should increase
    tomorrow = today + timedelta(days=1)
    streak, increased = await repository.update_streak(user_id, tomorrow)
    assert streak == 2
    assert increased is True

    # Skip a day - should reset
    day_after_skip = tomorrow + timedelta(days=2)
    streak, increased = await repository.update_streak(user_id, day_after_skip)
    assert streak == 1
    assert increased is False


@pytest.mark.asyncio
async def test_ban_unban_user(repository, sample_user_data):
    """Test banning and unbanning users."""
    telegram_id = sample_user_data["telegram_id"]

    # User should not be banned initially
    is_banned = await repository.is_banned(telegram_id)
    assert is_banned is False

    # Ban user
    was_banned = await repository.ban_user(
        telegram_id=telegram_id,
        reason="Test ban",
    )
    assert was_banned is True

    # Verify banned
    is_banned = await repository.is_banned(telegram_id)
    assert is_banned is True

    # Try to ban again - should return False
    was_banned = await repository.ban_user(telegram_id)
    assert was_banned is False

    # Unban user
    was_unbanned = await repository.unban_user(telegram_id)
    assert was_unbanned is True

    # Verify unbanned
    is_banned = await repository.is_banned(telegram_id)
    assert is_banned is False


@pytest.mark.asyncio
async def test_achievement_granting(repository, sample_user_data):
    """Test granting achievements."""
    user_id = await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
    )

    # Grant achievement
    was_granted = await repository.grant_achievement(
        user_id=user_id,
        achievement_type=AchievementType.FIRST_STEPS,
    )
    assert was_granted is True

    # Verify achievement
    has_achievement = await repository.has_achievement(
        user_id=user_id,
        achievement_type=AchievementType.FIRST_STEPS,
    )
    assert has_achievement is True

    # Try to grant again - should return False
    was_granted = await repository.grant_achievement(
        user_id=user_id,
        achievement_type=AchievementType.FIRST_STEPS,
    )
    assert was_granted is False


@pytest.mark.asyncio
async def test_get_unseen_question(repository, sample_user_data, sample_question):
    """Test getting unseen questions for a user."""
    user_id = await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
    )

    # Create a question
    question_id = await repository.create_question(
        content=sample_question["content"],
        question_type=sample_question["question_type"],
        options=sample_question["options"],
        correct_answer=sample_question["correct_answer"],
        explanation=sample_question["explanation"],
        content_area=sample_question["content_area"],
    )

    # Get unseen question
    question = await repository.get_unseen_question_for_user(user_id)
    assert question is not None
    assert question["id"] == question_id

    # Mark as sent
    await repository.record_sent_question(user_id, question_id)

    # Should not get the same question again
    question = await repository.get_unseen_question_for_user(user_id)
    assert question is None


@pytest.mark.asyncio
async def test_accuracy_calculation(repository, sample_user_data, sample_question):
    """Test accuracy calculation by area."""
    user_id = await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
    )

    # Create questions and record answers
    for i in range(5):
        q_id = await repository.create_question(
            content=f"Question {i}",
            question_type="multiple_choice",
            options={"A": "A", "B": "B", "C": "C", "D": "D"},
            correct_answer="B",
            explanation="Test",
            content_area="Behavior Assessment",
        )
        # 3 correct, 2 incorrect
        await repository.record_answer(
            user_id=user_id,
            question_id=q_id,
            user_answer="B" if i < 3 else "A",
            is_correct=i < 3,
        )

    # Check accuracy
    accuracy = await repository.get_overall_accuracy(user_id)
    assert accuracy == 0.6  # 3/5

    area_stats = await repository.get_user_accuracy_by_area(user_id)
    assert "Behavior Assessment" in area_stats
    assert area_stats["Behavior Assessment"]["accuracy"] == 0.6


@pytest.mark.asyncio
async def test_points_system(repository, sample_user_data):
    """Test points system."""
    user_id = await repository.create_user(
        telegram_id=sample_user_data["telegram_id"],
    )

    # Initial points should be 0
    stats = await repository.get_user_stats(user_id)
    assert stats["total_points"] == 0

    # Add points
    new_total = await repository.add_points(user_id, 10)
    assert new_total == 10

    # Add more points
    new_total = await repository.add_points(user_id, 5)
    assert new_total == 15


@pytest.mark.asyncio
async def test_get_subscribed_users_by_timezone(repository, sample_user_data):
    """Test getting subscribed users by timezone."""
    # Create users in different timezones
    await repository.create_user(
        telegram_id=111,
        username="user1",
        timezone="America/New_York",
    )
    await repository.create_user(
        telegram_id=222,
        username="user2",
        timezone="America/New_York",
    )
    await repository.create_user(
        telegram_id=333,
        username="user3",
        timezone="America/Los_Angeles",
    )

    # Unsubscribe one user
    await repository.update_user(222, is_subscribed=False)

    # Get users in New York timezone
    ny_users = await repository.get_subscribed_users_by_timezone("America/New_York")
    assert len(ny_users) == 1
    assert ny_users[0]["telegram_id"] == 111

    # Get users in LA timezone
    la_users = await repository.get_subscribed_users_by_timezone("America/Los_Angeles")
    assert len(la_users) == 1
    assert la_users[0]["telegram_id"] == 333
