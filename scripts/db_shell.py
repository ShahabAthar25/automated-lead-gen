import code
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from tabulate import tabulate

from reddit_lead_gen.adapters.database import DatabaseAdapter
from reddit_lead_gen.db.leads import QualifiedLeadORM, RawPostORM
from reddit_lead_gen.models.reddit import QualifiedLead

logging.basicConfig(level=logging.WARNING)  # Keep logs quiet for shell usability

# Initialize Database Adapter
db = DatabaseAdapter()


# ==========================================
# HELPER QUERY FUNCTIONS (Table Output)
# ==========================================


def get_last_posts(limit: int = 10, subreddit: str | None = None) -> None:
    """Prints the last N raw posts in a clean table format."""
    with db.SessionLocal() as session:
        stmt = select(RawPostORM).order_by(RawPostORM.created_utc.desc())
        if subreddit:
            stmt = stmt.where(RawPostORM.subreddit == subreddit)
        stmt = stmt.limit(limit)

        posts = session.scalars(stmt).all()
        if not posts:
            print("📭 No raw posts found.")
            return

        table_data = [
            [
                p.id,
                p.subreddit,
                p.post_type,
                p.title[:40] + "...",
                p.author,
                p.created_utc.strftime("%Y-%m-%d %H:%M"),
            ]
            for p in posts
        ]
        headers = ["ID", "Subreddit", "Type", "Title", "Author", "Created (UTC)"]
        print(tabulate(table_data, headers=headers, tablefmt="psql"))


def get_leads(limit: int = 10, min_score: float = 0.0) -> None:
    """Prints qualified leads meeting the minimum score in a clean table format."""
    with db.SessionLocal() as session:
        stmt = (
            select(QualifiedLeadORM)
            .options(joinedload(QualifiedLeadORM.raw_post))
            .where(QualifiedLeadORM.score >= min_score)
            .order_by(QualifiedLeadORM.score.desc())
            .limit(limit)
        )
        records = session.scalars(stmt).all()
        if not records:
            print("📭 No qualified leads found matching criteria.")
            return

        table_data = [
            [
                r.id,
                r.raw_post.subreddit if r.raw_post else "N/A",
                f"{r.score:.2f}",
                r.extracted_budget or "None",
                r.raw_post.title[:35] + "..." if r.raw_post else "N/A",
                r.status,
            ]
            for r in records
        ]
        headers = ["ID", "Sub", "Score", "Budget", "Title", "Status"]
        print(tabulate(table_data, headers=headers, tablefmt="psql"))


def get_post_by_id(post_id: str) -> None:
    """Inspects a single raw post and its Gemini evaluation if qualified."""
    with db.SessionLocal() as session:
        raw = session.scalar(select(RawPostORM).where(RawPostORM.id == post_id))
        if not raw:
            print(f"❌ Post ID '{post_id}' not found in raw_posts.")
            return

        print(f"\n📄 [RAW POST DETAILS: {raw.id}]")
        print(f"Subreddit : r/{raw.subreddit}")
        print(f"Type      : {raw.post_type}")
        print(f"Title     : {raw.title}")
        print(f"Author    : {raw.author}")
        print(f"Permalink : {raw.permalink}")
        print(f"Created   : {raw.created_utc}")
        print(
            f"Body Preview:\n{raw.body[:300]}...\n" if raw.body else "Body: (Empty)\n"
        )

        qualified = session.scalar(
            select(QualifiedLeadORM).where(QualifiedLeadORM.id == post_id)
        )
        if qualified:
            print(f"🌟 [GEMINI QUALIFICATION]")
            print(f"Score     : {qualified.score}")
            print(f"Is Hiring : {qualified.is_hiring}")
            print(f"Budget    : {qualified.extracted_budget}")
            print(f"Skills    : {qualified.matched_skills}")
            print(f"Reasoning : {qualified.reasoning}")
        else:
            print("ℹ️ This post did not qualify as a lead.")


def market_stats(days: int = 7) -> None:
    """Shows post type breakdown ([Hiring] vs [For Hire]) per subreddit."""
    from sqlalchemy import func

    with db.SessionLocal() as session:
        stmt = select(
            RawPostORM.subreddit, RawPostORM.post_type, func.count(RawPostORM.id)
        ).group_by(RawPostORM.subreddit, RawPostORM.post_type)
        results = session.execute(stmt).all()
        if not results:
            print("📭 No data available for stats.")
            return

        table_data = [[row[0], row[1], row[2]] for row in results]
        print(
            tabulate(
                table_data, headers=["Subreddit", "Post Type", "Count"], tablefmt="psql"
            )
        )


# ==========================================
# BOOT INTERACTIVE SHELL
# ==========================================
if __name__ == "__main__":
    banner = """
======================================================
🛠️  REDDIT LEAD GEN - DATABASE INSPECTION SHELL
======================================================
Pre-loaded variables:
  - db             : DatabaseAdapter instance
  - session        : Active SQLAlchemy session factory (db.SessionLocal())

Available Helper Functions:
  - get_last_posts(limit=10, subreddit=None)
  - get_leads(limit=10, min_score=0.0)
  - get_post_by_id("post_id_here")
  - market_stats()
======================================================
"""
    print(banner)

    # Expose helper objects to interactive scope
    local_vars = {
        "db": db,
        "session": db.SessionLocal,
        "get_last_posts": get_last_posts,
        "get_leads": get_leads,
        "get_post_by_id": get_post_by_id,
        "market_stats": market_stats,
    }

    code.interact(local=local_vars)
