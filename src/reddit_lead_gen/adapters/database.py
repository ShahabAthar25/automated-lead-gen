import logging
import re
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import joinedload, sessionmaker

from reddit_lead_gen.db.leads import Base, QualifiedLeadORM, RawPostORM
from reddit_lead_gen.models.reddit import QualifiedLead, RedditRSSPost


def determine_post_type(title: str) -> str:
    """Classifies post intent locally at ingestion time."""
    title_lower = title.lower()
    if re.search(
        r"\[\s*for\s*hire\s*\]|\(\s*for\s*hire\s*\)|^\s*for\s*hire", title_lower
    ):
        return "for_hire"
    elif re.search(r"\[\s*hiring\s*\]|\(\s*hiring\s*\)|^\s*hiring", title_lower):
        return "hiring"
    return "other"


class DatabaseAdapter:
    """
    Adapter bridging SQLAlchemy ORM operations with Pydantic domain models.
    """

    def __init__(self, db_url: str = "sqlite:///leads.db") -> None:
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        )
        # Automatically create tables if they don't exist
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def is_post_seen(self, post_id: str) -> bool:
        """Check if post exists in raw store."""
        with self.SessionLocal() as session:
            return (
                session.scalar(select(RawPostORM.id).where(RawPostORM.id == post_id))
                is not None
            )

    def save_raw_post(self, post: RedditRSSPost) -> bool:
        """
        Persists incoming RSS raw post immediately.
        Returns True if inserted, False if post was already seen.
        """
        with self.SessionLocal() as session:
            existing = session.scalar(
                select(RawPostORM.id).where(RawPostORM.id == post.id)
            )
            if existing:
                return False

            raw_record = RawPostORM(
                id=post.id,
                subreddit=post.subreddit,
                post_type=determine_post_type(post.title),
                title=post.title,
                author=post.author,
                permalink=str(post.permalink),
                body=post.body,
                created_utc=post.created_utc,
                fetched_at=datetime.now(timezone.utc),
            )
            session.add(raw_record)
            session.commit()
            return True

    def save_lead(self, lead: QualifiedLead) -> None:
        """
        Persist or update a QualifiedLead model into the database.
        """
        self.save_raw_post(lead.post)

        with self.SessionLocal() as session:
            record = QualifiedLeadORM(
                id=lead.post.id,
                is_hiring=lead.analysis.is_hiring,
                score=lead.analysis.score,
                extracted_budget=lead.analysis.extracted_budget,
                reasoning=lead.analysis.reasoning,
                matched_skills=",".join(lead.analysis.matched_skills),
                status=lead.status,
                processed_at=datetime.now(timezone.utc),
            )
            session.merge(record)  # Upsert (insert or update)
            session.commit()
            logging.info(
                f"Saved lead {lead.post.id} to DB (Score: {lead.analysis.score})"
            )

    def fetch_high_score_leads(self, min_score: float = 0.7) -> list[QualifiedLead]:
        """
        Fetch all actionable leads scoring above min_score as QualifiedLead objects.
        """
        with self.SessionLocal() as session:
            stmt = (
                select(QualifiedLeadORM)
                .where(QualifiedLeadORM.score >= min_score)
                .order_by(QualifiedLeadORM.created_utc.desc())
            )
            records = session.scalars(stmt).all()
            return [QualifiedLead.from_db_record(rec) for rec in records]

    def update_lead_status(self, post_id: str, status: str) -> None:
        """
        Update outreach tracking status ('new', 'contacted', 'ignored').
        """
        with self.SessionLocal() as session:
            stmt = (
                update(QualifiedLeadORM)
                .where(QualifiedLeadORM.id == post_id)
                .values(status=status)
            )
            session.execute(stmt)
            session.commit()
            logging.info(f"Updated post {post_id} status to '{status}'")

    def get_qualified_lead_by_id(self, post_id: str) -> QualifiedLead | None:
        """Fetches a qualified lead by ID with its raw post joined, returning a domain model."""
        with self.SessionLocal() as session:
            stmt = (
                select(QualifiedLeadORM)
                .options(joinedload(QualifiedLeadORM.raw_post))
                .where(QualifiedLeadORM.id == post_id)
            )
            record = session.scalar(stmt)
            if not record:
                return None

            return QualifiedLead.from_db_record(record)
