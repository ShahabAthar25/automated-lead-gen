import asyncio
import logging
import random
import time
from collections import deque
from typing import Tuple

from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.providers.base import BaseLLMProvider
from reddit_lead_gen.providers.utils import extract_status_code

logger = logging.getLogger(__name__)


class ProviderRateLimiter:
    """Tracks per-provider sliding window limits (RPM)."""

    def __init__(self, max_rpm: int, window_seconds: float = 60.0):
        self.max_rpm = max_rpm
        self.window_seconds = window_seconds
        self.timestamps: deque[float] = deque()
        self.cooldown_until: float = 0.0

    def can_consume(self) -> bool:
        now = time.time()

        # Check if we are in an active 429 penalty period
        if now < self.cooldown_until:
            return False

        # Clean up expired timestamps from rolling 60s window
        while self.timestamps and self.timestamps[0] <= now - self.window_seconds:
            self.timestamps.popleft()

        # Check if under RPM capacity
        return len(self.timestamps) < self.max_rpm

    def consume(self) -> None:
        self.timestamps.append(time.time())

    def penalize(self, cooldown_seconds: float = 30.0) -> None:
        """Blocks provider locally if remote 429 occurs."""
        now = time.time()
        self.cooldown_until = now + cooldown_seconds


class ModelRouter:
    """Coordinates classification requests with pacing, retries, and fallback."""

    def __init__(
        self,
        providers: list[BaseLLMProvider],
        rpm_limits: dict[str, int] | None = None,
        min_spacing_seconds: float = 5.0,
        max_retries: int = 3,
    ):
        self.providers = providers
        self.min_spacing_seconds = min_spacing_seconds
        self.max_retries = max_retries
        self.last_execution_time: float = 0.0
        self._lock = asyncio.Lock()

        limits = rpm_limits or {"Gemini": 10, "Groq": 20}
        self.limiters: dict[str, ProviderRateLimiter] = {
            p.name: ProviderRateLimiter(max_rpm=limits.get(p.name, 10))
            for p in providers
        }

    async def analyze(self, prompt: str) -> Tuple[float, LeadAnalysis | None]:
        async with self._lock:
            await self._enforce_spacing()
            errors = []

            for provider in self.providers:
                if not self._is_provider_available(provider.name):
                    continue

                try:
                    logger.info(f"Dispatching to provider: {provider.name}")
                    return await self._execute_with_retry(provider, prompt)
                except Exception as exc:
                    msg = f"Provider {provider.name} failed: {exc}"
                    logger.error(msg)
                    errors.append(msg)
                    logger.info("Failing over to next available provider...")

            raise RuntimeError(
                f"All LLM providers failed. Details: {'; '.join(errors)}"
            )

    # --- Private Helper Methods ---

    def _is_provider_available(self, provider_name: str) -> bool:
        limiter = self.limiters.get(provider_name)
        if limiter and not limiter.can_consume():
            logger.warning(
                f"Skipping {provider_name}: local RPM quota active ({limiter.max_rpm}/min)."
            )
            return False
        return True

    async def _enforce_spacing(self) -> None:
        now = time.time()
        elapsed = now - self.last_execution_time
        if elapsed < self.min_spacing_seconds:
            wait_time = self.min_spacing_seconds - elapsed
            logger.debug(f"Pacing request: sleeping for {wait_time:.2f}s...")
            await asyncio.sleep(wait_time)
        self.last_execution_time = time.time()

    async def _execute_with_retry(
        self, provider: BaseLLMProvider, prompt: str
    ) -> Tuple[float, LeadAnalysis | None]:
        limiter = self.limiters.get(provider.name)

        for attempt in range(1, self.max_retries + 1):
            try:
                score, analysis = await provider.analyze(prompt)
                if limiter:
                    limiter.consume()
                return score, analysis
            except Exception as exc:
                should_retry = await self._handle_execution_error(
                    provider, exc, attempt, limiter
                )
                if not should_retry:
                    raise exc

        raise RuntimeError(f"Provider {provider.name} exhausted retries.")

    async def _handle_execution_error(
        self,
        provider: BaseLLMProvider,
        exc: Exception,
        attempt: int,
        limiter: ProviderRateLimiter | None,
    ) -> bool:
        """Determines backoff strategy for errors. Returns True to retry, False to fail immediately."""
        status_code = extract_status_code(exc)

        # Rate Limit (429)
        if status_code == 429:
            if limiter:
                limiter.penalize(cooldown_seconds=30.0)

            if attempt == self.max_retries:
                logger.warning(
                    f"Provider {provider.name} exhausted retries on HTTP 429."
                )
                return False

            backoff = (2**attempt) + random.uniform(0.5, 1.5)
            logger.warning(
                f"HTTP 429 on {provider.name} (attempt {attempt}/{self.max_retries}). "
                f"Backing off {backoff:.2f}s..."
            )
            await asyncio.sleep(backoff)
            return True

        # Server Errors (500, 502, 503, 504)
        if status_code in (500, 502, 503, 504):
            if attempt == self.max_retries:
                logger.warning(
                    f"Provider {provider.name} exhausted retries on HTTP {status_code}."
                )
                return False

            backoff = (1.5**attempt) + random.uniform(0.1, 0.5)
            logger.warning(
                f"HTTP {status_code} on {provider.name} (attempt {attempt}/{self.max_retries}). "
                f"Retrying in {backoff:.2f}s..."
            )
            await asyncio.sleep(backoff)
            return True

        # Non-transient errors (400, 401, JSON validation, etc.)
        logger.error(
            f"Non-retryable error on {provider.name} (Code: {status_code}): {exc}"
        )
        return False
