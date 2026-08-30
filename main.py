import logging
from pprint import pprint

from reddit_lead_gen.adapters.database import DatabaseAdapter
from reddit_lead_gen.adapters.reddit_client import RedditClient
from reddit_lead_gen.core.classifier import LeadClassifier
from reddit_lead_gen.models.reddit import QualifiedLead

# Setup logging to monitor pipeline events
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# 1. Initialize Adapters & Services
client = RedditClient()
classifier = LeadClassifier()
db = DatabaseAdapter()

print("--- 1. FETCHING POSTS ---")
posts = client.fetch_subreddit_posts("forhire")
print(f"Fetched {len(posts)} posts from r/forhire.")

saved_count = 0

print("\n--- 2. PROCESSING & CLASSIFYING ---")
for post in posts:
    # Check DB first to skip duplicate processing
    if db.is_post_seen(post.id):
        print(f"⏭️ Skipping {post.id} (already in DB)")
        continue

    # Fast Stage-1 local filter
    if classifier.is_keyword_candidate(post):
        # Stage-2 Gemini LLM classification
        score, analysis = classifier.classify_lead(post)

        if analysis and score >= 0.7:
            # Construct unified domain model
            lead = QualifiedLead(post=post, analysis=analysis, status="new")

            print("\n🔥 HIGH VALUE LEAD FOUND 🔥")
            pprint(lead.model_dump())

            # Save to SQLite database using DatabaseAdapter
            db.save_lead(lead)
            saved_count += 1

print(f"\nSuccessfully processed posts. Saved {saved_count} new leads to DB.")

print("\n--- 3. TESTING DB FETCH CAPABILITIES ---")
# Fetch back all high-scoring leads stored in the database
high_score_leads = db.fetch_high_score_leads(min_score=0.7)
print(f"Found {len(high_score_leads)} total qualified leads stored in DB:\n")

for stored_lead in high_score_leads:
    print(f"📌 [ID: {stored_lead.post.id}] {stored_lead.post.title}")
    print(f"   Score: {stored_lead.analysis.score} | Budget: {stored_lead.analysis.extracted_budget}")
    print(f"   Reasoning: {stored_lead.analysis.reasoning}")
    print(f"   Link: {stored_lead.post.permalink}\n")
