import logging
from pprint import pprint

from reddit_lead_gen.adapters.reddit_client import RedditClient
from reddit_lead_gen.core.classifier import LeadClassifier

# Set logging to DEBUG to capture detailed logs
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def debug_specific_post(target_post_id: str, subreddit: str = "forhire") -> None:
    print(f"\n--- 🔍 DEBUGGING POST ID: {target_post_id} ---")

    client = RedditClient()
    classifier = LeadClassifier()

    clean_id = target_post_id

    # Fetch recent posts from the target subreddit
    print(f"📡 Fetching posts from r/{subreddit}...")
    posts = client.fetch_subreddit_posts(subreddit)
    pprint(posts[9])

    # Locate the target post in fetched batch
    target_post = next((p for p in posts if p.id == clean_id), None)

    if not target_post:
        print(f"⚠️ Post {target_post_id} not found in the latest RSS feed batch for r/{subreddit}.")
        print("Note: RSS feeds only hold the ~25 newest posts. If older, pass the raw text manually.")
        return

    print("\n📄 POST DETAILS:")
    print(f"Title: {target_post.title}")
    print(f"Author: u/{target_post.author}")
    print(f"Link: {target_post.permalink}")
    print(f"Body Sample: {target_post.body[:200]}...\n")

    # Test Stage-1: Keyword Filter
    print("--- STAGE 1: KEYWORD FILTER ---")
    is_keyword_match = classifier.is_keyword_candidate(target_post)

    if not is_keyword_match:
        print("❌ REJECTED AT STAGE 1")
        print("Reason: Post failed the fast local keyword matching check (e.g., missing hiring tags or required skills).")
        return
    else:
        print("✅ PASSED STAGE 1 (Keyword candidate matched)")

    # Test Stage-2: Gemini LLM Classification
    print("\n--- STAGE 2: GEMINI LLM CLASSIFICATION ---")
    score, analysis = classifier.classify_lead(target_post)

    if not analysis:
        print("❌ REJECTED AT STAGE 2")
        print("Reason: Gemini API failed to parse post or returned empty structured output.")
        return

    print("\n📊 GEMINI ANALYSIS RESULT:")
    pprint(analysis.model_dump())

    print(f"\nFinal Score: {score}")
    if score >= 0.7:
        print("✅ ACCEPTED: High-value lead score met threshold (>= 0.7).")
    else:
        print(f"❌ REJECTED AT STAGE 2: Score ({score}) below threshold (0.7).")
        print(f"Reasoning from LLM: {analysis.reasoning}")


if __name__ == "__main__":
    debug_specific_post("t3_1w268y4", subreddit="forhire")
