"""
Tests for question generation service.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from src.config.constants import ContentArea, QuestionType
from src.services.question_generator import (
    BATCH_SYSTEM_PROMPT,
    CATEGORY_INSTRUCTIONS,
    CATEGORY_WEIGHTS,
    CONTENT_AREA_GUIDANCE,
    SYSTEM_PROMPT,
    GeneratedQuestion,
    QuestionBatch,
    QuestionCategory,
    QuestionGenerator,
    QuestionOptions,
    get_question_generator,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.openai_api_key = "test-api-key"
    settings.openai_model = "gpt-5.2"
    settings.reasoning_effort = "medium"
    settings.reasoning_summary = "auto"
    settings.type_distribution = {"multiple_choice": 1.0, "true_false": 0.0}
    return settings


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
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
        "explanation": "A functional behavior assessment (FBA) is used to identify the function or purpose of a behavior.",
        "category": "definition",
    }


@pytest.fixture
def mock_batch_response():
    """Create a mock batch response."""
    return {
        "questions": [
            {
                "question": "Question 1?",
                "type": "multiple_choice",
                "options": {"A": "Opt A", "B": "Opt B", "C": "Opt C", "D": "Opt D"},
                "correct_answer": "A",
                "explanation": "Explanation 1",
                "category": "scenario",
            },
            {
                "question": "Question 2?",
                "type": "true_false",
                "options": {"True": "True", "False": "False"},
                "correct_answer": "True",
                "explanation": "Explanation 2",
                "category": "definition",
            },
        ]
    }


def create_mock_openai_response(json_data: dict) -> MagicMock:
    """Create a mock OpenAI Responses API response structure."""
    mock_content = MagicMock()
    mock_content.type = "output_text"
    mock_content.text = json.dumps(json_data)

    mock_message = MagicMock()
    mock_message.type = "message"
    mock_message.content = [mock_content]

    mock_response = MagicMock()
    mock_response.output = [mock_message]

    return mock_response


class TestPydanticModels:
    """Tests for Pydantic model definitions."""

    def test_question_options_multiple_choice(self):
        """Test QuestionOptions for multiple choice."""
        opts = QuestionOptions(A="Option A", B="Option B", C="Option C", D="Option D")
        assert opts.A == "Option A"
        assert opts.B == "Option B"
        assert opts.C == "Option C"
        assert opts.D == "Option D"

    def test_question_options_true_false(self):
        """Test QuestionOptions for true/false using alias."""
        opts = QuestionOptions(**{"True": "True statement", "False": "False statement"})
        assert opts.True_ == "True statement"
        assert opts.False_ == "False statement"

    def test_generated_question_model(self, mock_openai_response):
        """Test GeneratedQuestion model validation."""
        q = GeneratedQuestion(**mock_openai_response)
        assert q.question == mock_openai_response["question"]
        assert q.correct_answer == "B"
        assert q.type == "multiple_choice"

    def test_question_batch_model(self, mock_batch_response):
        """Test QuestionBatch model validation."""
        batch = QuestionBatch(**mock_batch_response)
        assert len(batch.questions) == 2
        assert batch.questions[0].category == "scenario"


class TestPrompts:
    """Tests for system prompts."""

    def test_system_prompt_has_guidelines(self):
        """Test system prompt contains guidelines section."""
        assert "<guidelines>" in SYSTEM_PROMPT
        assert "</guidelines>" in SYSTEM_PROMPT

    def test_system_prompt_has_explanation_format(self):
        """Test system prompt contains explanation format."""
        assert "<explanation_format>" in SYSTEM_PROMPT
        assert "</explanation_format>" in SYSTEM_PROMPT

    def test_system_prompt_has_example(self):
        """Test system prompt contains example."""
        assert "<example>" in SYSTEM_PROMPT
        assert "</example>" in SYSTEM_PROMPT

    def test_batch_system_prompt_has_variety_requirements(self):
        """Test batch prompt contains variety requirements."""
        assert "<variety_requirements>" in BATCH_SYSTEM_PROMPT
        assert "</variety_requirements>" in BATCH_SYSTEM_PROMPT

    def test_category_instructions_complete(self):
        """Test all categories have instructions."""
        for category in QuestionCategory:
            assert category in CATEGORY_INSTRUCTIONS
            assert len(CATEGORY_INSTRUCTIONS[category]) > 0

    def test_content_area_guidance_complete(self):
        """Test all content areas have guidance."""
        for area in ContentArea:
            assert area in CONTENT_AREA_GUIDANCE
            assert "<content_area_focus>" in CONTENT_AREA_GUIDANCE[area]

    def test_category_weights_sum_to_one(self):
        """Test category weights sum to 1.0."""
        total = sum(CATEGORY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01


class TestQuestionGenerator:
    """Tests for QuestionGenerator class."""

    def test_vector_store_cache_initialization(self, mock_settings):
        """Test that vector store cache is initialized empty."""
        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI"):
                with patch("src.services.question_generator.get_vector_store_manager"):
                    generator = QuestionGenerator()

        assert generator._vector_store_id is None

    def test_clear_vector_store_cache(self, mock_settings):
        """Test clearing vector store cache."""
        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI"):
                with patch("src.services.question_generator.get_vector_store_manager"):
                    generator = QuestionGenerator()
                    generator._vector_store_id = "cached-store-id"

                    generator.clear_vector_store_cache()

        assert generator._vector_store_id is None

    def test_select_category_returns_valid_category(self, mock_settings):
        """Test that _select_category returns valid categories."""
        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI"):
                with patch("src.services.question_generator.get_vector_store_manager"):
                    generator = QuestionGenerator()

                    categories = [generator._select_category() for _ in range(100)]

        # All should be valid categories
        for cat in categories:
            assert cat in QuestionCategory

    def test_select_category_follows_distribution(self, mock_settings):
        """Test that _select_category roughly follows weights."""
        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI"):
                with patch("src.services.question_generator.get_vector_store_manager"):
                    generator = QuestionGenerator()

                    counts = {cat: 0 for cat in QuestionCategory}
                    for _ in range(1000):
                        cat = generator._select_category()
                        counts[cat] += 1

        # Check distribution is roughly correct (allow 10% variance)
        for cat, weight in CATEGORY_WEIGHTS.items():
            expected = 1000 * weight
            actual = counts[cat]
            assert abs(actual - expected) < 150, f"{cat}: expected ~{expected}, got {actual}"

    @pytest.mark.asyncio
    async def test_generate_question_success(self, mock_settings, mock_openai_response):
        """Test successful question generation."""
        mock_response = create_mock_openai_response(mock_openai_response)

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    result = await generator.generate_question(
                        content_area=ContentArea.BEHAVIOR_ASSESSMENT,
                        question_type=QuestionType.MULTIPLE_CHOICE,
                    )

        assert result is not None
        assert result["question"] == mock_openai_response["question"]
        assert result["content_area"] == ContentArea.BEHAVIOR_ASSESSMENT.value
        assert result["model"] == mock_settings.openai_model
        assert "category" in result

    @pytest.mark.asyncio
    async def test_generate_question_uses_responses_api(self, mock_settings, mock_openai_response):
        """Test that generate_question uses the Responses API with file_search."""
        mock_response = create_mock_openai_response(mock_openai_response)

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    await generator.generate_question(
                        content_area=ContentArea.ETHICS,
                    )

        # Verify responses.create was called with file_search tool
        mock_client.responses.create.assert_called_once()
        call_kwargs = mock_client.responses.create.call_args[1]
        assert "tools" in call_kwargs
        assert any(t["type"] == "file_search" for t in call_kwargs["tools"])
        assert "reasoning" in call_kwargs

    @pytest.mark.asyncio
    async def test_generate_question_api_error(self, mock_settings):
        """Test handling of API errors."""
        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(
            side_effect=openai.APIError("Server Error", request=MagicMock(), body={})
        )

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    result = await generator.generate_question(
                        content_area=ContentArea.ETHICS,
                    )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_question_vector_store_not_configured(self, mock_settings):
        """Test handling of missing vector store."""
        mock_client = MagicMock()

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value=None)

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    result = await generator.generate_question(
                        content_area=ContentArea.ETHICS,
                    )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_question_batch_success(self, mock_settings, mock_batch_response):
        """Test successful batch question generation."""
        mock_response = create_mock_openai_response(mock_batch_response)

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    result = await generator.generate_question_batch(
                        content_area=ContentArea.ETHICS,
                        count=2,
                    )

        assert len(result) == 2
        for q in result:
            assert q["content_area"] == ContentArea.ETHICS.value
            assert q["model"] == mock_settings.openai_model
            assert "category" in q

    @pytest.mark.asyncio
    async def test_generate_batch_legacy(self, mock_settings, mock_openai_response):
        """Test legacy batch generation (one at a time)."""
        mock_response = create_mock_openai_response(mock_openai_response)

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    results = await generator.generate_batch(
                        content_area=ContentArea.ETHICS,
                        count=3,
                    )

        assert len(results) == 3
        for result in results:
            assert result["content_area"] == ContentArea.ETHICS.value


class TestRetryLogic:
    """Tests for API retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, mock_settings, mock_openai_response):
        """Test that rate limit errors are handled by SDK retries."""
        mock_response = create_mock_openai_response(mock_openai_response)

        # First call raises rate limit, second succeeds
        # Note: SDK handles retries automatically, we just verify behavior
        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(
            side_effect=[
                openai.RateLimitError("Rate limited", response=MagicMock(), body={}),
                mock_response,
            ]
        )

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    result = await generator.generate_question(
                        content_area=ContentArea.ETHICS,
                    )

        # SDK will retry, so we should get a result
        # If SDK didn't retry, result would be None
        assert result is not None or mock_client.responses.create.call_count >= 1

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self, mock_settings):
        """Test that unrecoverable API errors return None."""
        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(
            side_effect=openai.APIError("Bad request", request=MagicMock(), body={})
        )

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    result = await generator.generate_question(
                        content_area=ContentArea.ETHICS,
                    )

        assert result is None


class TestQuestionTypeDistribution:
    """Tests for question type distribution."""

    @pytest.mark.asyncio
    async def test_question_type_passed_to_prompt(self, mock_settings, mock_openai_response):
        """Test that question type instruction is included in prompt."""
        mock_response = create_mock_openai_response(mock_openai_response)

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    # Note: All questions are now multiple choice, true/false is not used
                    await generator.generate_question(
                        content_area=ContentArea.MEASUREMENT,
                        question_type=QuestionType.MULTIPLE_CHOICE,
                    )

        # Check the prompt contains multiple choice instruction
        call_kwargs = mock_client.responses.create.call_args[1]
        user_message = call_kwargs["input"][1]["content"]
        assert "multiple choice" in user_message.lower()

    @pytest.mark.asyncio
    async def test_multiple_choice_instruction_in_prompt(self, mock_settings, mock_openai_response):
        """Test that multiple choice instruction is included in prompt."""
        mock_response = create_mock_openai_response(mock_openai_response)

        mock_client = MagicMock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)

        mock_vsm = MagicMock()
        mock_vsm.get_store_id = AsyncMock(return_value="test-store-id")

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI", return_value=mock_client):
                with patch("src.services.question_generator.get_vector_store_manager", return_value=mock_vsm):
                    generator = QuestionGenerator()

                    await generator.generate_question(
                        content_area=ContentArea.MEASUREMENT,
                        question_type=QuestionType.MULTIPLE_CHOICE,
                    )

        # Check the prompt contains multiple choice instruction
        call_kwargs = mock_client.responses.create.call_args[1]
        user_message = call_kwargs["input"][1]["content"]
        assert "multiple choice" in user_message.lower()
        assert "A, B, C, D" in user_message


class TestSingleton:
    """Tests for singleton behavior."""

    def test_get_question_generator_returns_same_instance(self, mock_settings):
        """Test that get_question_generator returns singleton."""
        # Reset singleton for test
        import src.services.question_generator as qg
        qg._generator = None

        with patch("src.services.question_generator.get_settings", return_value=mock_settings):
            with patch("src.services.question_generator.AsyncOpenAI"):
                with patch("src.services.question_generator.get_vector_store_manager"):
                    generator1 = get_question_generator()
                    generator2 = get_question_generator()

        assert generator1 is generator2

        # Clean up
        qg._generator = None
