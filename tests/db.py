import logging
from datetime import datetime, timezone

from reddit_lead_gen.adapters.database import DatabaseAdapter
from reddit_lead_gen.models.gemini import LeadAnalysis
from reddit_lead_gen.models.reddit import QualifiedLead, RedditRSSPost

logging.basicConfig(level=logging.INFO)


def create_sample_post(post_id: str = "test_101", title: str = "[Hiring] Python Developer Needed") -> RedditRSSPost:
    """Helper factory to create mock RedditRSSPost objects."""
    return RedditRSSPost(
        id=post_id,
        title=title,
        permalink="https://reddit.com/r/forhire/comments/test_101",
        author="test_client",
        body="Looking for a Python dev to build an automation tool. Budget is $500.",
        created_utc=datetime.now(timezone.utc),
        subreddit="forhire",
        tags=["Hiring"],
    )


def test_database_pipeline():
    # 1. Initialize DB with in-memory SQLite URL for isolated testing
    db = DatabaseAdapter(db_url="sqlite:///:memory:")
    logging.info("✅ In-memory SQLite database initialized.")

    # -------------------------------------------------------------
    # TEST 1: Raw Post Ingestion & Tagging
    # -------------------------------------------------------------
    raw_hiring = create_sample_post("post_001", "[Hiring] Python Scraping Specialist")
    raw_for_hire = create_sample_post("post_002", "[For Hire] Full-Stack Developer for $30/hr")

    # Insert raw posts
    assert db.save_raw_post(raw_hiring) is True, "First insertion of post_001 should succeed."
    assert db.save_raw_post(raw_for_hire) is True, "First insertion of post_002 should succeed."

    # Test Duplicate Handling
    assert db.save_raw_post(raw_hiring) is False, "Duplicate insertion should return False."
    assert db.is_post_seen("post_001") is True, "is_post_seen should detect post_001."
    assert db.is_post_seen("unseen_999") is False, "is_post_seen should return False for unseen IDs."
    logging.info("✅ Raw post ingestion and duplicate checking passed.")

    # -------------------------------------------------------------
    # TEST 2: Saving Qualified Lead (Gemini Analysis)
    # -------------------------------------------------------------
    analysis = LeadAnalysis(
        is_hiring=True,
        score=0.9,
        extracted_budget="$500 fixed",
        matched_skills=["Python", "Web Scraping", "SQLAlchemy"],
        reasoning="Strong client intent with clear deliverables and budget.",
    )
    qualified_lead = QualifiedLead(
        post=raw_hiring,
        analysis=analysis,
        status="new"
    )

    # Save qualified lead (this tests foreign key linking & upsert logic)
    db.save_lead(qualified_lead)
    logging.info("✅ Qualified lead saved to DB successfully.")

    # -------------------------------------------------------------
    # TEST 3: Fetching and Reconstructing Qualified Lead
    # -------------------------------------------------------------
    reconstructed_lead = db.get_qualified_lead_by_id("post_001")
    
    assert reconstructed_lead is not None, "Failed to retrieve lead from database."
    assert reconstructed_lead.post.id == "post_001"
    assert reconstructed_lead.post.title == "[Hiring] Python Scraping Specialist"
    assert reconstructed_lead.analysis.score == 0.9
    assert reconstructed_lead.analysis.matched_skills == ["Python", "Web Scraping", "SQLAlchemy"]
    assert reconstructed_lead.is_actionable is True
    
    logging.info("✅ Lead reconstruction from DB record (with joined RawPost) verified!")

    print("\n🎉 ALL DATABASE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_database_pipeline()
