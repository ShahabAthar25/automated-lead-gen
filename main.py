import logging
from pprint import pprint

from reddit_lead_gen.adapters import database
from reddit_lead_gen.adapters.database import DatabaseAdapter
from reddit_lead_gen.adapters.messaging import DiscordNotifier
from reddit_lead_gen.adapters.reddit_client import RedditClient
from reddit_lead_gen.core.classifier import LeadClassifier
from reddit_lead_gen.core.pipeline import LeadPipeline
from reddit_lead_gen.models.reddit import QualifiedLead

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    print("\n--- 🚀 STARTING DISCORD WEBHOOK & PIPELINE TEST ---")

    # Initialize all adapters and services
    client = RedditClient()
    db = DatabaseAdapter()
    classifier = LeadClassifier()
    notifier = DiscordNotifier()
    pipeline = LeadPipeline(db, classifier, notifier)

    # Check Webhook config
    if not notifier.webhook_url:
        logging.error(
            "❌ DISCORD_WEBHOOK_URL is missing from your .env file! "
            "Add it before running this test."
        )
        return

    # Fetch fresh posts
    target_subreddit = "forhire"
    print(f"\n📡 Fetching posts from r/{target_subreddit}...")
    posts = client.fetch_subreddit_posts(target_subreddit)
    print(f"Fetched {len(posts)} posts.\n")

    alert_sent = False

    # Process candidate posts
    for post in posts:

        lead = pipeline.process_post(post)
        if lead:
            alert_sent = True
            break


if __name__ == "__main__":
    main()
