import logging
from google import genai
from google.genai import types

from reddit_lead_gen.models.reddit import RedditRSSPost
from reddit_lead_gen.models.gemini import LeadAnalysis
from reddit_lead_gen.settings import settings

# Keywords that instantly disqualify a post without calling the LLM
DISQUALIFY_KEYWORDS = [
    "[for hire]",
    "for hire",
    "[forhire]",
    "offering my services",
    "hire me",
    "i am looking for work",
    "i will build",
]

# Keywords required to trigger an LLM check
TARGET_KEYWORDS = [
    "python", "bot", "scraper", "scraping", "automation", 
    "fastapi", "django", "discord", "api", "backend", "[hiring]"
]


class LeadClassifier:
    def __init__(self) -> None:
        # Uses the google-genai SDK
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def is_keyword_candidate(self, post: RedditRSSPost) -> bool:
        """Stage 1: Fast local keyword pre-filter."""
        title_lower = post.title.lower()
        body_lower = post.body.lower()
        combined_text = f"{title_lower} {body_lower}"

        if any(bad_kw in combined_text for bad_kw in DISQUALIFY_KEYWORDS):
            return False

        if not any(good_kw in combined_text for good_kw in TARGET_KEYWORDS):
            return False

        return True

    def classify_lead(self, post: RedditRSSPost) -> tuple[float, LeadAnalysis | None]:
        """Stage 2: LLM Intent Analysis."""
        if not self.is_keyword_candidate(post):
            return 0.0, None

        tags_str = ", ".join(post.tags) if post.tags else "None"

        prompt = f"""
        Analyze this Reddit post to determine if it is a legitimate client looking to hire a developer.
        
        Post Subreddit: r/{post.subreddit}
        Post Title: {post.title}
        Post Tags: {tags_str}
        Post Body:
        {post.body[:1500]}
        """

        try:
            # Force structured JSON response matching LeadAnalysis schema
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LeadAnalysis,
                    temperature=0.1,
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
