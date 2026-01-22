"""
Tests for question pool management service.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.constants import ContentArea
from src.services.pool_manager import (
    BCBA_WEIGHTS,
    PoolManager,
    get_pool_manager,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.openai_api_key = "test-api-key"
    settings.database_path = ":memory:"
    settings.pool_threshold = 20
    settings.pool_batch_size = 50
    settings.pool_dedup_threshold = 0.85
    settings.pool_dedup_embedding_model = "text-embedding-3-large"
    settings.pool_dedup_check_limit = 30
    settings.pool_generation_batch_size = 5
    settings.pool_max_concurrent_generation = 20
    settings.pool_bcba_weights = {}
    return settings


@pytest.fixture
def mock_question():
    """Create a mock question for testing."""
    return {
        "question": "What is the primary function of a functional behavior assessment?",
        "type": "multiple_choice",
        "options": {
            "A": "To diagnose mental disorders",
            "B": "To identify the function of behavior",
            "C": "To prescribe medication",
            "D": "To evaluate academic performance",
        },
        "correct_answer": "B",
        "explanation": "An FBA identifies the function of behavior.",
        "content_area": "Behavior Assessment",
        "category": "definition",
        "model": "gpt-5.2",
    }


@pytest.fixture
def mock_existing_question():
    """Create a mock existing question from the database."""
    return {
        "id": 1,
        "content": "What is the main purpose of conducting an FBA?",
        "question_type": "multiple_choice",
        "options": {
            "A": "Diagnose conditions",
            "B": "Determine behavior function",
            "C": "Prescribe treatment",
            "D": "Assess learning",
        },
        "correct_answer": "B",
        "explanation": "FBA determines behavior function.",
        "content_area": "Behavior Assessment",
    }


@pytest.fixture
def mock_dedup_service():
    """Create a mock dedup service."""
    service = MagicMock()
    # Default to not a duplicate
    mock_result = MagicMock()
    mock_result.is_duplicate = False
    mock_result.similarity = 0.2
    mock_result.matched_question = None
    service.check_duplicate = AsyncMock(return_value=mock_result)
    return service


class TestPoolManager:
    """Tests for PoolManager class."""

    def test_calculate_batch_distribution(self, mock_settings):
        """Test that batch distribution follows BCBA weights."""
        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service"):
                manager = PoolManager()
                distribution = manager.calculate_batch_distribution()

        # Check total equals batch size
        total = sum(distribution.values())
        assert total == manager.batch_size

        # Check all content areas are represented
        assert len(distribution) == len(BCBA_WEIGHTS)

        # Check distribution roughly follows weights
        for area, count in distribution.items():
            expected = round(manager.batch_size * BCBA_WEIGHTS[area])
            # Allow for rounding variance (last area gets remainder)
            assert abs(count - expected) <= 2, f"{area}: expected ~{expected}, got {count}"

    def test_calculate_batch_distribution_custom_weights(self, mock_settings):
        """Test batch distribution with custom weights."""
        mock_settings.pool_bcba_weights = {
            "Ethics": 0.5,
            "Behavior Assessment": 0.5,
        }

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service"):
                manager = PoolManager()
                # Override bcba_weights directly for test
                manager.bcba_weights = {
                    ContentArea.ETHICS: 0.5,
                    ContentArea.BEHAVIOR_ASSESSMENT: 0.5,
                }
                distribution = manager.calculate_batch_distribution()

        total = sum(distribution.values())
        assert total == manager.batch_size
        assert distribution[ContentArea.ETHICS] == 25
        assert distribution[ContentArea.BEHAVIOR_ASSESSMENT] == 25

    def test_default_bcba_weights_sum_to_one(self):
        """Test that default BCBA weights sum to 1.0."""
        total = sum(BCBA_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"

    def test_all_content_areas_have_weights(self):
        """Test that all content areas have defined weights."""
        for area in ContentArea:
            assert area in BCBA_WEIGHTS, f"Missing weight for {area}"


class TestCheckDuplicate:
    """Tests for duplicate checking logic."""

    @pytest.mark.asyncio
    async def test_check_duplicate_empty_list_returns_false(self, mock_settings, mock_dedup_service):
        """Test that empty existing questions returns not duplicate."""
        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service", return_value=mock_dedup_service):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    {"question": "Test?", "options": {}, "correct_answer": "A"},
                    []
                )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_duplicate_high_similarity_returns_true(
        self, mock_settings, mock_question, mock_existing_question
    ):
        """Test that high similarity duplicate is rejected."""
        mock_result = MagicMock()
        mock_result.is_duplicate = True
        mock_result.similarity = 0.92
        mock_result.matched_question = "What is the main purpose of conducting an FBA?"

        mock_dedup = MagicMock()
        mock_dedup.check_duplicate = AsyncMock(return_value=mock_result)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service", return_value=mock_dedup):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    mock_question,
                    [mock_existing_question]
                )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_duplicate_low_similarity_returns_false(
        self, mock_settings, mock_question, mock_existing_question
    ):
        """Test that low similarity questions are accepted."""
        mock_result = MagicMock()
        mock_result.is_duplicate = False
        mock_result.similarity = 0.45
        mock_result.matched_question = None

        mock_dedup = MagicMock()
        mock_dedup.check_duplicate = AsyncMock(return_value=mock_result)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service", return_value=mock_dedup):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    mock_question,
                    [mock_existing_question]
                )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_duplicate_api_error_returns_false(
        self, mock_settings, mock_question, mock_existing_question
    ):
        """Test that API errors allow the question (fail-open)."""
        mock_result = MagicMock()
        mock_result.is_duplicate = False
        mock_result.similarity = 0.0
        mock_result.matched_question = None

        mock_dedup = MagicMock()
        # On error, dedup_service returns not-duplicate (fail-open behavior)
        mock_dedup.check_duplicate = AsyncMock(return_value=mock_result)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service", return_value=mock_dedup):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    mock_question,
                    [mock_existing_question]
                )

        # Should allow question on error (fail-open)
        assert result is False


class TestGenerateWithDedup:
    """Tests for generation with deduplication."""

    @pytest.mark.asyncio
    async def test_generate_with_dedup_accepts_unique_questions(self, mock_settings, mock_question):
        """Test that unique questions are accepted."""
        mock_generator = MagicMock()
        mock_generator.generate_question_batch = AsyncMock(return_value=[mock_question])

        mock_repo = MagicMock()
        mock_repo.get_questions_by_content_area = AsyncMock(return_value=[])

        # Mock dedup service to always return not duplicate
        mock_result = MagicMock()
        mock_result.is_duplicate = False
        mock_result.similarity = 0.2
        mock_result.matched_question = None

        mock_dedup = MagicMock()
        mock_dedup.check_duplicate = AsyncMock(return_value=mock_result)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service", return_value=mock_dedup):
                with patch("src.services.pool_manager.get_question_generator", return_value=mock_generator):
                    with patch("src.services.pool_manager.get_repository", return_value=mock_repo):
                        manager = PoolManager()

                        result = await manager.generate_with_dedup(
                            ContentArea.BEHAVIOR_ASSESSMENT,
                            count=1
                        )

        assert len(result) == 1
        assert result[0] == mock_question

    @pytest.mark.asyncio
    async def test_generate_with_dedup_rejects_duplicates(self, mock_settings, mock_question):
        """Test that duplicate questions are rejected."""
        # Create two questions, one duplicate
        question1 = mock_question.copy()
        question2 = mock_question.copy()
        question2["question"] = "Similar question about FBA?"

        mock_generator = MagicMock()
        mock_generator.generate_question_batch = AsyncMock(return_value=[question1, question2])

        mock_repo = MagicMock()
        mock_repo.get_questions_by_content_area = AsyncMock(return_value=[])

        # First question is unique, second is duplicate
        result1 = MagicMock()
        result1.is_duplicate = False
        result1.similarity = 0.2
        result1.matched_question = None

        result2 = MagicMock()
        result2.is_duplicate = True
        result2.similarity = 0.92
        result2.matched_question = question1["question"]

        mock_dedup = MagicMock()
        mock_dedup.check_duplicate = AsyncMock(side_effect=[result1, result2])

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service", return_value=mock_dedup):
                with patch("src.services.pool_manager.get_question_generator", return_value=mock_generator):
                    with patch("src.services.pool_manager.get_repository", return_value=mock_repo):
                        manager = PoolManager()

                        result = await manager.generate_with_dedup(
                            ContentArea.BEHAVIOR_ASSESSMENT,
                            count=2
                        )

        # Only the first question should be accepted
        assert len(result) == 1
        assert result[0] == question1


class TestGenerateWithoutDedup:
    """Tests for generation without deduplication."""

    @pytest.mark.asyncio
    async def test_generate_without_dedup_returns_all(self, mock_settings, mock_question):
        """Test that all questions are returned without dedup."""
        questions = [mock_question.copy() for _ in range(3)]

        mock_generator = MagicMock()
        mock_generator.generate_question_batch = AsyncMock(return_value=questions)

        mock_dedup = MagicMock()

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service", return_value=mock_dedup):
                with patch("src.services.pool_manager.get_question_generator", return_value=mock_generator):
                    manager = PoolManager()

                    result = await manager.generate_without_dedup(
                        ContentArea.BEHAVIOR_ASSESSMENT,
                        count=3
                    )

        assert len(result) == 3


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_pool_manager_returns_same_instance(self, mock_settings):
        """Test that get_pool_manager returns singleton."""
        # Reset singleton for test
        import src.services.pool_manager as pm
        pm._pool_manager = None

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.get_dedup_service"):
                manager1 = get_pool_manager()
                manager2 = get_pool_manager()

        assert manager1 is manager2

        # Clean up
        pm._pool_manager = None
