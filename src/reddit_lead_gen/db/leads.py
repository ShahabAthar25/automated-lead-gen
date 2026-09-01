from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, String, Text, Index, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from typing import Optional


class Base(DeclarativeBase):
    pass

class RawPostORM(Base):
    """Stores all raw RSS posts categorized by intent at ingestion time."""
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g., "1w268y4"
    subreddit: Mapped[str] = mapped_column(String, index=True)
    
    post_type: Mapped[str] = mapped_column(String, index=True) # "hiring", "for_hire", or "other"
    
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String)
    permalink: Mapped[str] = mapped_column(String)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[str] = mapped_column(String, default="")  # Stored as comma-separated string
    created_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))

    # Optional 1-to-1 relationship to qualified lead evaluation
    qualified_lead: Mapped[Optional["QualifiedLeadORM"]] = relationship(
        back_populates="raw_post", uselist=False
    )

    __table_args__ = (
        Index("idx_sub_type_created", "subreddit", "post_type", "created_utc"),
    )


class QualifiedLeadORM(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String, ForeignKey("posts.id"), primary_key=True)

    # Gemini Analysis Results
    is_hiring: Mapped[bool] = mapped_column(default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    extracted_budget: Mapped[str | None] = mapped_column(String, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_skills: Mapped[str | None] = mapped_column(String, nullable=True)  # Comma-separated

    # Pipeline & Outreach Tracking
    status: Mapped[str] = mapped_column(String, default="new")  # 'new', 'contacted', 'ignored'
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship link back to RawPostORM
    raw_post: Mapped["RawPostORM"] = relationship(back_populates="qualified_lead")

