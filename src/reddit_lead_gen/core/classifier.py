import logging
from typing import Tuple

from google import genai
from google.genai import types
from groq import Groq

from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.models.reddit import RedditRSSPost
from reddit_lead_gen.providers import GeminiProvider, GroqProvider
from reddit_lead_gen.settings import settings


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
    def __init__(self) -> None:
        if settings.pipeline.llm_model == "gemini":
            self.provider = GeminiProvider(api_key=settings.gemini_api_key)
        elif settings.pipeline.llm_model == "groq":
            self.provider = GroqProvider(api_key=settings.groq_api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {settings.pipeline.llm_model}")

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

    def classify_lead(self, post: RedditRSSPost) -> Tuple[float, LeadAnalysis | None]:
        """Stage 2: LLM Intent Analysis."""
        tags_str = ", ".join(post.tags) if post.tags else "None"

        prompt = _build_classifier_prompt(post)

        try:
            score, analysis = self.provider.analyze(prompt)

            return score, analysis

        except Exception as e:
            logging.error(f"LLM Classification failed for post {post.id}: {e}")
            return 0.0, None
