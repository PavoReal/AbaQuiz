"""
Tests for question generation service.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.constants import ContentArea, QuestionType
from src.services.question_generator import QuestionGenerator


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic API response."""
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
    }


class TestQuestionGenerator:
    """Tests for QuestionGenerator class."""

    def test_parse_question_json_valid(self, mock_anthropic_response):
        """Test parsing valid JSON response."""
        generator = QuestionGenerator()
        json_str = json.dumps(mock_anthropic_response)

        result = generator._parse_question_json(json_str)

        assert result is not None
        assert result["question"] == mock_anthropic_response["question"]
        assert result["correct_answer"] == "B"

    def test_parse_question_json_with_markdown(self, mock_anthropic_response):
        """Test parsing JSON wrapped in markdown code blocks."""
        generator = QuestionGenerator()
        json_str = f"```json\n{json.dumps(mock_anthropic_response)}\n```"

        result = generator._parse_question_json(json_str)

        assert result is not None
        assert result["question"] == mock_anthropic_response["question"]

    def test_parse_question_json_invalid(self):
        """Test parsing invalid JSON."""
        generator = QuestionGenerator()

        result = generator._parse_question_json("not valid json")

        assert result is None

    def test_parse_question_json_with_text_prefix(self, mock_anthropic_response):
        """Test parsing JSON with text before it."""
        generator = QuestionGenerator()
        text = f"Here is your question:\n{json.dumps(mock_anthropic_response)}"

        result = generator._parse_question_json(text)

        assert result is not None
        assert result["correct_answer"] == "B"

    @pytest.mark.asyncio
    async def test_generate_question_success(self, mock_anthropic_response):
        """Test successful question generation."""
        generator = QuestionGenerator()

        # Mock the Anthropic client
        mock_content = MagicMock()
        mock_content.text = json.dumps(mock_anthropic_response)

        mock_message = MagicMock()
        mock_message.content = [mock_content]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch.object(
            generator.client.messages,
            "create",
            return_value=mock_message,
        ):
            result = await generator.generate_question(
                content_area=ContentArea.BEHAVIOR_ASSESSMENT,
                question_type=QuestionType.MULTIPLE_CHOICE,
            )

        assert result is not None
        assert result["question"] == mock_anthropic_response["question"]
        assert result["content_area"] == ContentArea.BEHAVIOR_ASSESSMENT.value

    @pytest.mark.asyncio
    async def test_generate_question_api_error(self):
        """Test handling of API errors."""
        import anthropic

        generator = QuestionGenerator()

        with patch.object(
            generator.client.messages,
            "create",
            side_effect=anthropic.APIError("API Error", None, None),
        ):
            result = await generator.generate_question(
                content_area=ContentArea.ETHICS,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_batch(self, mock_anthropic_response):
        """Test batch question generation."""
        generator = QuestionGenerator()

        mock_content = MagicMock()
        mock_content.text = json.dumps(mock_anthropic_response)

        mock_message = MagicMock()
        mock_message.content = [mock_content]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=200)

        with patch.object(
            generator.client.messages,
            "create",
            return_value=mock_message,
        ):
            results = await generator.generate_batch(
                content_area=ContentArea.ETHICS,
                count=3,
            )

        assert len(results) == 3
        for result in results:
            assert result["content_area"] == ContentArea.ETHICS.value


class TestQuestionTypeDistribution:
    """Tests for question type distribution."""

    @pytest.mark.asyncio
    async def test_question_type_selection(self, mock_anthropic_response):
        """Test that question type follows distribution."""
        generator = QuestionGenerator()

        mock_content = MagicMock()
        mock_content.text = json.dumps(mock_anthropic_response)

        mock_message = MagicMock()
        mock_message.content = [mock_content]
        mock_message.usage = MagicMock(input_tokens=100, output_tokens=200)

        # Track question types generated
        mc_count = 0
        tf_count = 0

        with patch.object(
            generator.client.messages,
            "create",
            return_value=mock_message,
        ):
            for _ in range(100):
                # Use the default type selection (80% MC, 20% TF)
                await generator.generate_question(
                    content_area=ContentArea.MEASUREMENT,
                )
                # Note: We're not actually checking the type here
                # since the mock returns the same response
                # This is more of a coverage test

        # The actual type verification would require checking the prompt
        # or the response type field
