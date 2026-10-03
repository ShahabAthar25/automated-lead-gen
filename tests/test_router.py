import asyncio
import time
from typing import Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai.errors import APIError as GeminiAPIError
from groq import APIStatusError as GroqAPIStatusError

from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.providers.base import BaseLLMProvider
from reddit_lead_gen.providers.router import ModelRouter, ProviderRateLimiter
from reddit_lead_gen.providers.utils import extract_status_code

# --- Fixtures & Mocks ---


class DummyProvider(BaseLLMProvider):
    """Mock LLM Provider for testing router behavior."""

    def __init__(self, name: str):
        self.name = name
        self.analyze = AsyncMock()

    async def analyze(self, prompt: str) -> Tuple[float, LeadAnalysis | None]:
        """Class-level declaration to satisfy abstract method check."""
        pass


@pytest.fixture
def mock_lead_analysis():
    return LeadAnalysis(
        is_hiring=True,
        score=0.9,
        reasoning="Very good looking",
    )


@pytest.fixture
def gemini_provider(mock_lead_analysis):
    provider = DummyProvider("Gemini")
    provider.analyze.return_value = (0.9, mock_lead_analysis)
    return provider


@pytest.fixture
def groq_provider(mock_lead_analysis):
    provider = DummyProvider("Groq")
    provider.analyze.return_value = (0.9, mock_lead_analysis)
    return provider


# --- 1. Tests for ProviderRateLimiter ---


def test_rate_limiter_rpm_capacity():
    limiter = ProviderRateLimiter(max_rpm=2, window_seconds=60.0)

    assert limiter.can_consume() is True
    limiter.consume()

    assert limiter.can_consume() is True
    limiter.consume()

    # 3rd request should exceed 2 RPM cap
    assert limiter.can_consume() is False


def test_rate_limiter_sliding_window_expiration():
    limiter = ProviderRateLimiter(max_rpm=1, window_seconds=60.0)
    base_time = 1000.0

    with patch("time.time", return_value=base_time):
        assert limiter.can_consume() is True
        limiter.consume()
        assert limiter.can_consume() is False

    # 30 seconds later, still inside the 60s window
    with patch("time.time", return_value=base_time + 30.0):
        assert limiter.can_consume() is False

    # 61 seconds later, the earlier timestamp has expired
    with patch("time.time", return_value=base_time + 61.0):
        assert limiter.can_consume() is True


def test_rate_limiter_cooldown_penalize():
    limiter = ProviderRateLimiter(max_rpm=10, window_seconds=60.0)
    base_time = 1000.0

    with patch("time.time", return_value=base_time):
        assert limiter.can_consume() is True
        # Apply 30s penalty
        limiter.penalize(cooldown_seconds=30.0)
        # Immediately blocked by cooldown
        assert limiter.can_consume() is False

    # 15 seconds later, still in cooldown period
    with patch("time.time", return_value=base_time + 15.0):
        assert limiter.can_consume() is False

    # 31 seconds later, cooldown has expired and capacity is available
    with patch("time.time", return_value=base_time + 31.0):
        assert limiter.can_consume() is True


# --- 2. Tests for Status Code Extraction Utility ---


def test_extract_status_code_groq_error():
    mock_response = MagicMock()
    mock_response.status_code = 429
    err = GroqAPIStatusError(message="Rate limited", response=mock_response, body=None)

    assert extract_status_code(err) == 429


def test_extract_status_code_gemini_error():
    err = GeminiAPIError(
        code=503, response_json={"error": {"message": "Service Unavailable"}}
    )
    assert extract_status_code(err) == 503


def test_extract_status_code_generic_status_code():
    class GenericHTTPError(Exception):
        status_code = 400

    assert extract_status_code(GenericHTTPError()) == 400


def test_extract_status_code_generic_code_int():
    class CodeError(Exception):
        code = 502

    assert extract_status_code(CodeError()) == 502


def test_extract_status_code_generic_code_non_int():
    class NonIntCodeError(Exception):
        code = "RESOURCE_EXHAUSTED"

    assert extract_status_code(NonIntCodeError()) is None


def test_extract_status_code_unknown():
    assert extract_status_code(ValueError("Unexpected error format")) is None


# --- 3. Tests for ModelRouter Behavior ---


@pytest.mark.asyncio
async def test_router_primary_provider_success(
    gemini_provider, groq_provider, mock_lead_analysis
):
    router = ModelRouter(
        providers=[gemini_provider, groq_provider], min_spacing_seconds=0.0
    )

    score, analysis = await router.analyze("Need Python Developer")

    assert score == 0.9
    assert analysis == mock_lead_analysis
    gemini_provider.analyze.assert_called_once_with("Need Python Developer")
    groq_provider.analyze.assert_not_called()


@pytest.mark.asyncio
async def test_router_enforces_inter_request_spacing(
    gemini_provider, mock_lead_analysis
):
    with patch(
        "reddit_lead_gen.providers.router.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        router = ModelRouter(providers=[gemini_provider], min_spacing_seconds=1.0)

        # First request has no pacing delay (last_execution_time was 0.0)
        await router.analyze("First Prompt")
        mock_sleep.assert_not_called()

        # Second prompt called immediately enforces spacing
        await router.analyze("Second Prompt")
        assert mock_sleep.call_count == 1
        sleep_duration = mock_sleep.call_args[0][0]
        assert 0.0 < sleep_duration <= 1.0
        assert gemini_provider.analyze.call_count == 2


@pytest.mark.asyncio
async def test_router_spacing_skipped_if_sufficient_time_elapsed(
    gemini_provider, mock_lead_analysis
):
    with patch(
        "reddit_lead_gen.providers.router.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        router = ModelRouter(providers=[gemini_provider], min_spacing_seconds=1.0)

        await router.analyze("First Prompt")

        # Simulate 2 seconds passing since last execution
        router.last_execution_time = time.time() - 2.0

        await router.analyze("Second Prompt")
        mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_router_failover_when_primary_fails(
    gemini_provider, groq_provider, mock_lead_analysis
):
    # Primary provider throws non-retryable exception
    gemini_provider.analyze.side_effect = RuntimeError("API Exception")

    router = ModelRouter(
        providers=[gemini_provider, groq_provider], min_spacing_seconds=0.0
    )

    score, analysis = await router.analyze("Need Python Developer")

    assert score == 0.9
    assert analysis == mock_lead_analysis
    gemini_provider.analyze.assert_called_once()
    groq_provider.analyze.assert_called_once_with("Need Python Developer")


@pytest.mark.asyncio
async def test_router_handles_429_retry_and_penalize(
    gemini_provider, groq_provider, mock_lead_analysis
):
    # Gemini throws 429 Rate Limit error
    err_429 = GeminiAPIError(
        code=429, response_json={"error": {"message": "Quota exceeded"}}
    )
    gemini_provider.analyze.side_effect = err_429

    with patch(
        "reddit_lead_gen.providers.router.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        router = ModelRouter(
            providers=[gemini_provider, groq_provider],
            min_spacing_seconds=0.0,
            max_retries=2,
        )

        # First request: Gemini retries 2x on 429, exhausts retries, fails over to Groq
        score, analysis = await router.analyze("Prompt 1")

        assert score == 0.9
        assert analysis == mock_lead_analysis
        assert gemini_provider.analyze.call_count == 2
        groq_provider.analyze.assert_called_once()
        # Backoff sleep was called for retry
        assert mock_sleep.call_count == 1

        # Second request: Gemini is now penalized, so router should skip it directly to Groq
        gemini_provider.analyze.reset_mock()
        groq_provider.analyze.reset_mock()

        score, analysis = await router.analyze("Prompt 2")

        assert score == 0.9
        gemini_provider.analyze.assert_not_called()  # Gemini skipped due to active cooldown!
        groq_provider.analyze.assert_called_once()


@pytest.mark.asyncio
async def test_router_handles_503_transient_retry(gemini_provider, mock_lead_analysis):
    err_503 = GeminiAPIError(
        code=503, response_json={"error": {"message": "Service Unavailable"}}
    )

    # Fails twice with 503, succeeds on 3rd attempt
    gemini_provider.analyze.side_effect = [
        err_503,
        err_503,
        (0.9, mock_lead_analysis),
    ]

    with patch(
        "reddit_lead_gen.providers.router.asyncio.sleep", new_callable=AsyncMock
    ) as mock_sleep:
        router = ModelRouter(
            providers=[gemini_provider], min_spacing_seconds=0.0, max_retries=3
        )

        score, analysis = await router.analyze("Prompt")

        assert score == 0.9
        assert gemini_provider.analyze.call_count == 3
        # Backoff was invoked twice before success
        assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_router_handles_5xx_exhaustion_failover(
    gemini_provider, groq_provider, mock_lead_analysis
):
    err_500 = GeminiAPIError(
        code=500, response_json={"error": {"message": "Internal Server Error"}}
    )
    gemini_provider.analyze.side_effect = err_500

    with patch(
        "reddit_lead_gen.providers.router.asyncio.sleep", new_callable=AsyncMock
    ):
        router = ModelRouter(
            providers=[gemini_provider, groq_provider],
            min_spacing_seconds=0.0,
            max_retries=2,
        )

        score, analysis = await router.analyze("Prompt")

        assert score == 0.9
        assert analysis == mock_lead_analysis
        assert gemini_provider.analyze.call_count == 2
        groq_provider.analyze.assert_called_once()


@pytest.mark.asyncio
async def test_router_skips_provider_exceeding_rpm_limit(
    gemini_provider, groq_provider, mock_lead_analysis
):
    router = ModelRouter(
        providers=[gemini_provider, groq_provider],
        rpm_limits={"Gemini": 1, "Groq": 10},
        min_spacing_seconds=0.0,
    )

    # First request: Gemini uses its 1 RPM capacity
    score, analysis = await router.analyze("Prompt 1")
    assert score == 0.9
    assert gemini_provider.analyze.call_count == 1
    groq_provider.analyze.assert_not_called()

    # Second request: Gemini's 1 RPM capacity is exhausted, router skips directly to Groq
    gemini_provider.analyze.reset_mock()
    score, analysis = await router.analyze("Prompt 2")
    assert score == 0.9
    gemini_provider.analyze.assert_not_called()
    groq_provider.analyze.assert_called_once()


@pytest.mark.asyncio
async def test_router_raises_exception_when_all_fail(
    gemini_provider, groq_provider
):
    gemini_provider.analyze.side_effect = RuntimeError("Gemini Down")
    groq_provider.analyze.side_effect = RuntimeError("Groq Down")

    router = ModelRouter(
        providers=[gemini_provider, groq_provider], min_spacing_seconds=0.0
    )

    with pytest.raises(RuntimeError, match="All LLM providers failed") as exc_info:
        await router.analyze("Prompt")

    assert "Gemini Down" in str(exc_info.value)
    assert "Groq Down" in str(exc_info.value)


def test_router_custom_rpm_limits(gemini_provider, groq_provider):
    router = ModelRouter(
        providers=[gemini_provider, groq_provider],
        rpm_limits={"Gemini": 5, "Groq": 25},
    )
    assert router.limiters["Gemini"].max_rpm == 5
    assert router.limiters["Groq"].max_rpm == 25


def test_router_default_rpm_limits(gemini_provider, groq_provider):
    router = ModelRouter(providers=[gemini_provider, groq_provider])
    assert router.limiters["Gemini"].max_rpm == 10
    assert router.limiters["Groq"].max_rpm == 20
