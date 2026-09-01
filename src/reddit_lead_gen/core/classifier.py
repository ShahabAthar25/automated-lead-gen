import logging

from google import genai
from google.genai import types

from reddit_lead_gen.models.gemini import LeadAnalysis
from reddit_lead_gen.models.reddit import RedditRSSPost
from reddit_lead_gen.settings import settings


def _build_classifier_prompt(post) -> str:
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
Body: {post.selftext}
Tags: {post.tags}

Evaluation Rules:
1. Is the poster explicitly looking to hire or pay for services matching the target services above?
2. Does the post violate any of the strict dealbreakers?
3. Assign a fit score from 0.0 to 1.0 based on how well this client match aligns with the target role and services.
"""


class LeadClassifier:
    def __init__(self) -> None:
        # Uses the google-genai SDK
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def is_keyword_candidate(self, post: RedditRSSPost) -> bool:
        """Stage 1: Fast local keyword pre-filter."""
        title_lower = post.title.lower()
        body_lower = post.body.lower()
        combined_text = f"{title_lower} {body_lower}"

        if not any(
            good_kw in combined_text for good_kw in settings.pipeline.candidate_keywords
        ):
            return False

        return True

    def classify_lead(self, post: RedditRSSPost) -> tuple[float, LeadAnalysis | None]:
        """Stage 2: LLM Intent Analysis."""
        if not self.is_keyword_candidate(post):
            return 0.0, None

        tags_str = ", ".join(post.tags) if post.tags else "None"

        prompt = _build_classifier_prompt(post)

        try:
            # Force structured JSON response matching LeadAnalysis schema
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LeadAnalysis,
                    temperature=1.0,
                ),
            )

            # Parse returned structured JSON into Pydantic model
            analysis = LeadAnalysis.model_validate_json(response.text)

            # If author is NOT hiring, force score to 0
            final_score = analysis.score if analysis.is_hiring else 0.0
            return final_score, analysis

        except Exception as e:
            logging.error(f"LLM Classification failed for post {post.id}: {e}")
            return 0.0, None
