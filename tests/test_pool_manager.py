"""
Tests for question pool management service.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.constants import ContentArea
from src.services.pool_manager import (
    BCBA_WEIGHTS,
    DEDUP_PROMPT,
    PoolManager,
    get_pool_manager,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.anthropic_api_key = "test-api-key"
    settings.database_path = ":memory:"
    settings.pool_threshold = 20
    settings.pool_batch_size = 50
    settings.pool_dedup_model = "claude-haiku-4-5"
    settings.pool_dedup_check_limit = 30
    settings.pool_dedup_confidence_threshold = "high"
    settings.pool_dedup_early_exit_batches = 3
    settings.pool_generation_batch_size = 5
    settings.pool_max_concurrent_generation = 20
    settings.pool_max_concurrent_dedup = 30
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
        "model": "claude-sonnet-4-5",
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


class TestPoolManager:
    """Tests for PoolManager class."""

    def test_calculate_batch_distribution(self, mock_settings):
        """Test that batch distribution follows BCBA weights."""
        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic"):
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
            with patch("src.services.pool_manager.AsyncAnthropic"):
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


class TestDedupPrompt:
    """Tests for the deduplication prompt."""

    def test_dedup_prompt_has_required_sections(self):
        """Test that dedup prompt contains all required sections."""
        assert "<similarity_criteria>" in DEDUP_PROMPT
        assert "</similarity_criteria>" in DEDUP_PROMPT
        assert "<examples>" in DEDUP_PROMPT
        assert "</examples>" in DEDUP_PROMPT
        assert "<confidence_levels>" in DEDUP_PROMPT
        assert "</confidence_levels>" in DEDUP_PROMPT
        assert "<output_format>" in DEDUP_PROMPT
        assert "</output_format>" in DEDUP_PROMPT

    def test_dedup_prompt_has_placeholders(self):
        """Test that dedup prompt has required placeholders."""
        assert "{new_question}" in DEDUP_PROMPT
        assert "{existing_questions}" in DEDUP_PROMPT

    def test_dedup_prompt_format(self):
        """Test that dedup prompt can be formatted."""
        formatted = DEDUP_PROMPT.format(
            new_question="Test question?",
            existing_questions="Existing question 1\nExisting question 2",
        )
        assert "Test question?" in formatted
        assert "Existing question 1" in formatted


class TestCheckDuplicate:
    """Tests for duplicate checking logic."""

    @pytest.mark.asyncio
    async def test_check_duplicate_empty_list_returns_false(self, mock_settings):
        """Test that empty existing questions returns not duplicate."""
        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic"):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    {"question": "Test?", "options": {}, "correct_answer": "A"},
                    []
                )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_duplicate_high_confidence_returns_true(
        self, mock_settings, mock_question, mock_existing_question
    ):
        """Test that high confidence duplicate is rejected."""
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "is_duplicate": True,
            "reason": "Tests same concept",
            "confidence": "high"
        })
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic", return_value=mock_client):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    mock_question,
                    [mock_existing_question]
                )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_duplicate_low_confidence_returns_false(
        self, mock_settings, mock_question, mock_existing_question
    ):
        """Test that low confidence duplicate is accepted."""
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "is_duplicate": True,
            "reason": "Related topic but different focus",
            "confidence": "low"
        })
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic", return_value=mock_client):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    mock_question,
                    [mock_existing_question]
                )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_duplicate_not_duplicate_returns_false(
        self, mock_settings, mock_question, mock_existing_question
    ):
        """Test that non-duplicate is accepted."""
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "is_duplicate": False,
            "reason": "Different concepts",
            "confidence": "high"
        })
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic", return_value=mock_client):
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
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic", return_value=mock_client):
                manager = PoolManager()

                result = await manager.check_duplicate(
                    mock_question,
                    [mock_existing_question]
                )

        # Should allow question on error (fail-open)
        assert result is False


class TestParseDedupResult:
    """Tests for dedup result parsing."""

    def test_parse_valid_json(self, mock_settings):
        """Test parsing valid JSON."""
        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic"):
                manager = PoolManager()

                result = manager._parse_dedup_result(
                    '{"is_duplicate": true, "reason": "test", "confidence": "high"}'
                )

        assert result["is_duplicate"] is True
        assert result["reason"] == "test"
        assert result["confidence"] == "high"

    def test_parse_json_with_text(self, mock_settings):
        """Test parsing JSON embedded in text."""
        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic"):
                manager = PoolManager()

                result = manager._parse_dedup_result(
                    'Here is my analysis: {"is_duplicate": false, "reason": "different", "confidence": "low"}'
                )

        assert result is not None
        assert result["is_duplicate"] is False

    def test_parse_invalid_returns_none(self, mock_settings):
        """Test parsing invalid content returns None."""
        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic"):
                manager = PoolManager()

                result = manager._parse_dedup_result("not valid json at all")

        assert result is None


class TestGenerateWithDedup:
    """Tests for generation with deduplication."""

    @pytest.mark.asyncio
    async def test_generate_with_dedup_accepts_unique_questions(self, mock_settings, mock_question):
        """Test that unique questions are accepted."""
        mock_generator = MagicMock()
        mock_generator.generate_question_batch = AsyncMock(return_value=[mock_question])

        mock_repo = MagicMock()
        mock_repo.get_questions_by_content_area = AsyncMock(return_value=[])

        # Mock dedup to always return False (not duplicate)
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = json.dumps({
            "is_duplicate": False,
            "reason": "unique",
            "confidence": "high"
        })
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic", return_value=mock_client):
                with patch("src.services.pool_manager.get_question_generator", return_value=mock_generator):
                    with patch("src.services.pool_manager.get_repository", return_value=mock_repo):
                        manager = PoolManager()

                        result = await manager.generate_with_dedup(
                            ContentArea.BEHAVIOR_ASSESSMENT,
                            count=1
                        )

        assert len(result) == 1
        assert result[0] == mock_question


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_pool_manager_returns_same_instance(self, mock_settings):
        """Test that get_pool_manager returns singleton."""
        # Reset singleton for test
        import src.services.pool_manager as pm
        pm._pool_manager = None

        with patch("src.services.pool_manager.get_settings", return_value=mock_settings):
            with patch("src.services.pool_manager.AsyncAnthropic"):
                manager1 = get_pool_manager()
                manager2 = get_pool_manager()

        assert manager1 is manager2

        # Clean up
        pm._pool_manager = None
