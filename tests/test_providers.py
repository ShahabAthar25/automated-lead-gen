from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.providers.gemini import GeminiProvider
from reddit_lead_gen.providers.groq import GroqProvider


# --- GeminiProvider Tests ---


def test_gemini_provider_init():
    with patch("reddit_lead_gen.providers.gemini.genai.Client") as mock_client_cls:
        provider = GeminiProvider(api_key="fake-gemini-key")
        assert provider.name == "Gemini"
        mock_client_cls.assert_called_once_with(api_key="fake-gemini-key")


@pytest.mark.asyncio
async def test_gemini_provider_analyze_hiring_true():
    with patch("reddit_lead_gen.providers.gemini.genai.Client"):
        provider = GeminiProvider(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.text = (
            '{"is_hiring": true, "score": 0.88, "reasoning": "Clear hiring intent"}'
        )
        provider.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        score, analysis = await provider.analyze("Prompt text")

        assert score == 0.88
        assert isinstance(analysis, LeadAnalysis)
        assert analysis.is_hiring is True
        assert analysis.score == 0.88
        assert analysis.reasoning == "Clear hiring intent"


@pytest.mark.asyncio
async def test_gemini_provider_analyze_not_hiring_forces_score_zero():
    with patch("reddit_lead_gen.providers.gemini.genai.Client"):
        provider = GeminiProvider(api_key="fake-key")

        mock_response = MagicMock()
        mock_response.text = (
            '{"is_hiring": false, "score": 0.75, "reasoning": "Self promotion post"}'
        )
        provider.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        score, analysis = await provider.analyze("Prompt text")

        # Score must be overridden to 0.0 when is_hiring is False
        assert score == 0.0
        assert analysis is not None
        assert analysis.is_hiring is False


# --- GroqProvider Tests ---


def test_groq_provider_init():
    with patch("reddit_lead_gen.providers.groq.AsyncGroq") as mock_groq_cls:
        provider = GroqProvider(api_key="fake-groq-key")
        assert provider.name == "Groq"
        mock_groq_cls.assert_called_once_with(api_key="fake-groq-key")


@pytest.mark.asyncio
async def test_groq_provider_analyze_clean_json():
    with patch("reddit_lead_gen.providers.groq.AsyncGroq"):
        provider = GroqProvider(api_key="fake-key")

        mock_choice = MagicMock()
        mock_choice.message.content = (
            '{"is_hiring": true, "score": 0.95, "reasoning": "Looking for lead dev"}'
        )
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        provider.client.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )

        score, analysis = await provider.analyze("Prompt text")

        assert score == 0.95
        assert isinstance(analysis, LeadAnalysis)
        assert analysis.is_hiring is True
        assert analysis.score == 0.95
        assert analysis.reasoning == "Looking for lead dev"


@pytest.mark.asyncio
async def test_groq_provider_analyze_markdown_fence_stripping():
    with patch("reddit_lead_gen.providers.groq.AsyncGroq"):
        provider = GroqProvider(api_key="fake-key")

        mock_choice = MagicMock()
        mock_choice.message.content = (
            '```json\n{"is_hiring": true, "score": 0.92, "reasoning": "Fenced output"}\n```'
        )
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        provider.client.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )

        score, analysis = await provider.analyze("Prompt text")

        assert score == 0.92
        assert isinstance(analysis, LeadAnalysis)
        assert analysis.is_hiring is True
        assert analysis.score == 0.92


@pytest.mark.asyncio
async def test_groq_provider_analyze_not_hiring_forces_score_zero():
    with patch("reddit_lead_gen.providers.groq.AsyncGroq"):
        provider = GroqProvider(api_key="fake-key")

        mock_choice = MagicMock()
        mock_choice.message.content = (
            '{"is_hiring": false, "score": 0.85, "reasoning": "Looking for work"}'
        )
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        provider.client.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )

        score, analysis = await provider.analyze("Prompt text")

        # Score must be overridden to 0.0 when is_hiring is False
        assert score == 0.0
        assert analysis is not None
        assert analysis.is_hiring is False


@pytest.mark.asyncio
async def test_groq_provider_analyze_empty_response():
    with patch("reddit_lead_gen.providers.groq.AsyncGroq"):
        provider = GroqProvider(api_key="fake-key")

        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]

        provider.client.chat.completions.create = AsyncMock(
            return_value=mock_completion
        )

        score, analysis = await provider.analyze("Prompt text")

        assert score == 0.0
        assert analysis is None
