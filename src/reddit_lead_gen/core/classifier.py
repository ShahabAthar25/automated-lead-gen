import asyncio
import logging
from typing import Tuple

from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.models.reddit import RedditRSSPost
from reddit_lead_gen.providers import (
    BaseLLMProvider,
    GeminiProvider,
    GroqProvider,
    ModelRouter,
)
from reddit_lead_gen.settings import settings

logger = logging.getLogger(__name__)


def _build_classifier_prompt(post: RedditRSSPost) -> str:
    """Builds a dynamic prompt tailored to the user's specific skill set and dealbreakers."""

    services_list = "\n".join([f"- {s}" for s in settings.user_profile.target_services])
    dealbreakers_list = "\n".join(
        [f"- {d}" for d in settings.user_profile.dealbreakers]
    )

    return f"""
You are an expert freelance lead qualifier acting on behalf of a **{settings.user_profile.primary_role}**.

Target Services Provided:
{services_list}

Strict Dealbreakers (Automatic Disqualification):
{dealbreakers_list}

---
Analyze the following Reddit post:
Subreddit: r/{post.subreddit}
Title: {post.title}
Body: {post.body}
Tags: {post.tags}

Evaluation Rules:
1. Is the poster explicitly looking to hire or pay for services matching the target services above?
2. Does the post violate any of the strict dealbreakers?
3. Assign a fit score from 0.0 to 1.0 based on how well this client match aligns with the target role and services.
"""


class LeadClassifier:
    def __init__(self, router: ModelRouter | None = None) -> None:
        self.router: ModelRouter = router or self._build_default_router()

    @property
    def provider(self) -> BaseLLMProvider | None:
        """Backwards compatibility for direct provider access."""
        return self.router.providers[0] if self.router.providers else None

    def _build_default_router(self) -> ModelRouter:
        """Constructs ModelRouter with providers prioritized based on configured llm_model."""
        providers: list[BaseLLMProvider] = []
        preferred = settings.pipeline.llm_model.lower()

        gemini_key = getattr(settings, "gemini_api_key", None)
        groq_key = getattr(settings, "groq_api_key", None)

        gemini = GeminiProvider(api_key=gemini_key) if gemini_key else None
        groq = GroqProvider(api_key=groq_key) if groq_key else None

        if preferred == "gemini":
            if gemini:
                providers.append(gemini)
            if groq:
                providers.append(groq)
        elif preferred == "groq":
            if groq:
                providers.append(groq)
            if gemini:
                providers.append(gemini)
        else:
            for p in (gemini, groq):
                if p:
                    providers.append(p)

        if not providers:
            raise ValueError(
                "No LLM providers available. Please set GEMINI_API_KEY or GROQ_API_KEY in .env."
            )

        rpm_limits = {
            "Gemini": getattr(settings.pipeline, "gemini_rpm", 10),
            "Groq": getattr(settings.pipeline, "groq_rpm", 20),
        }
        min_spacing = getattr(settings.pipeline, "min_spacing_seconds", 5.0)

        return ModelRouter(
            providers=providers,
            rpm_limits=rpm_limits,
            min_spacing_seconds=min_spacing,
        )

    def is_keyword_candidate(self, post: RedditRSSPost) -> bool:
        """Stage 1: Fast local keyword pre-filter."""
        title_lower = post.title.lower()
        body_lower = post.body.lower()
        combined_text = f"{title_lower} {body_lower}"

        if any(
            bad_kw in combined_text for bad_kw in settings.pipeline.disqualify_keywords
        ):
            return False

        if not any(
            good_kw in combined_text for good_kw in settings.pipeline.candidate_keywords
        ):
            return False

        return True

    async def classify_lead(
        self, post: RedditRSSPost
    ) -> Tuple[float, LeadAnalysis | None]:
        """Stage 2: LLM Intent Analysis via ModelRouter."""
        prompt = _build_classifier_prompt(post)

        try:
            return await self.router.analyze(prompt)
        except Exception as e:
            logging.error(f"LLM Classification failed for post {post.id}: {e}")
            return 0.0, None

    def classify_lead_sync(
        self, post: RedditRSSPost
    ) -> Tuple[float, LeadAnalysis | None]:
        """Synchronous wrapper for scripts and interactive inspection."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.classify_lead(post)).result()
        else:
            return asyncio.run(self.classify_lead(post))
