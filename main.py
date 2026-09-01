import logging
from pprint import pprint

from reddit_lead_gen.adapters import database
from reddit_lead_gen.adapters.database import DatabaseAdapter
from reddit_lead_gen.adapters.messaging import DiscordNotifier
from reddit_lead_gen.adapters.reddit_client import RedditClient
from reddit_lead_gen.core.classifier import LeadClassifier
from reddit_lead_gen.models.reddit import QualifiedLead

# Setup logging to see output in console
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> None:
    print("\n--- 🚀 STARTING DISCORD WEBHOOK & PIPELINE TEST ---")

    # 1. Initialize all adapters and services
    client = RedditClient()
    classifier = LeadClassifier()
    db = DatabaseAdapter()
    notifier = DiscordNotifier()

    # Check Webhook config
    if not notifier.webhook_url:
        logging.error(
            "❌ DISCORD_WEBHOOK_URL is missing from your .env file! "
            "Add it before running this test."
        )
        return

    # 2. Fetch fresh posts
    target_subreddit = "forhire"
    print(f"\n📡 Fetching posts from r/{target_subreddit}...")
    posts = client.fetch_subreddit_posts(target_subreddit)
    print(f"Fetched {len(posts)} posts.\n")

    alert_sent = False

    # 3. Process candidate posts
    for post in posts:
        # Check DB to avoid unnecessary re-analysis
        if db.is_post_seen(post.id):
            logging.info(f"⏭️ Post {post.id} already seen in DB. Skipping.")
            continue

        db.save_raw_post(post)

        # Stage 1: Fast keyword check
        if classifier.is_keyword_candidate(post):
            logging.info(f"🔍 Analyzing candidate post: {post.title[:50]}...")

            # Stage 2: Gemini classification
            score, analysis = classifier.classify_lead(post)

            if analysis and score >= 0.7:
                # Wrap into unified domain model
                lead = QualifiedLead(post=post, analysis=analysis, status="new")

                print("\n🔥 HIGH VALUE LEAD FOUND 🔥")
                pprint(lead.model_dump())

                # Save to SQLite
                db.save_lead(lead)

                # Send live alert to Discord
                print("📢 Dispatching Discord Webhook notification...")
                success = notifier.send_lead_alert(lead)

                if success:
                    print(
                        "✅ DISCORD ALERT SENT SUCCESSFULLY! Check your Discord channel.\n"
                    )
                    alert_sent = True
                    break  # Break after sending 1 test alert
                else:
                    print("❌ Failed to send Discord alert.\n")

    # 4. Fallback: Test with existing DB record if no new post triggered an alert
    if not alert_sent:
        print("\nℹ️ No new actionable posts found in current RSS batch.")
        print("Fetching existing lead from database to test Discord Webhook...")

        existing_leads = db.fetch_high_score_leads(min_score=0.7)
        if existing_leads:
            test_lead = existing_leads[0]
            print(f"Testing Webhook using existing lead: {test_lead.post.id}")
            success = notifier.send_lead_alert(test_lead)
            if success:
                print("✅ TEST ALERT SENT TO DISCORD SUCCESSFULLY!\n")
        else:
            print("⚠️ No qualified leads stored in database yet to send a test alert.")


if __name__ == "__main__":
    main()
