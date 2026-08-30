import logging
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from reddit_lead_gen.db.leads import Base, LeadTable
from reddit_lead_gen.models.reddit import QualifiedLead


class DatabaseAdapter:
    """
    Adapter bridging SQLAlchemy ORM operations with Pydantic domain models.
    """

    def __init__(self, db_url: str = "sqlite:///leads.db") -> None:
        self.engine = create_engine(
            db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
        )
        # Automatically create tables if they don't exist
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def is_post_seen(self, post_id: str) -> bool:
        """
        Check if a post has already been parsed and stored in the database.
        Used by the pipeline to skip duplicate processing.
        """
        with self.SessionLocal() as session:
            stmt = select(LeadTable.id).where(LeadTable.id == post_id)
            return session.scalar(stmt) is not None

    def save_lead(self, lead: QualifiedLead) -> None:
        """
        Persist or update a QualifiedLead model into the database.
        """
        with self.SessionLocal() as session:
            record = LeadTable(
                id=lead.post.id,
                title=lead.post.title,
                permalink=str(lead.post.permalink),
                author=lead.post.author,
                subreddit=lead.post.subreddit,
                body=lead.post.body,
                tags=",".join(lead.post.tags),
                is_hiring=lead.analysis.is_hiring,
                score=lead.analysis.score,
                extracted_budget=lead.analysis.extracted_budget,
                reasoning=lead.analysis.reasoning,
                matched_skills=",".join(lead.analysis.matched_skills),
                status=lead.status,
                created_utc=lead.post.created_utc,
                processed_at=datetime.now(timezone.utc),
            )
            session.merge(record)  # Upsert (insert or update)
            session.commit()
            logging.info(f"Saved lead {lead.post.id} to DB (Score: {lead.analysis.score})")

    def fetch_high_score_leads(self, min_score: float = 0.7) -> list[QualifiedLead]:
        """
        Fetch all actionable leads scoring above min_score as QualifiedLead objects.
        """
        with self.SessionLocal() as session:
            stmt = (
                select(LeadTable)
                .where(LeadTable.score >= min_score)
                .order_by(LeadTable.created_utc.desc())
            )
            records = session.scalars(stmt).all()
            return [QualifiedLead.from_db_record(rec) for rec in records]

    def update_lead_status(self, post_id: str, status: str) -> None:
        """
        Update outreach tracking status ('new', 'contacted', 'ignored').
        """
        with self.SessionLocal() as session:
            stmt = update(LeadTable).where(LeadTable.id == post_id).values(status=status)
            session.execute(stmt)
            session.commit()
            logging.info(f"Updated post {post_id} status to '{status}'")
