from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LeadTable(Base):
    __tablename__ = "leads"

    # Post Metadata
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    permalink: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str] = mapped_column(String, nullable=False)
    subreddit: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String, default="")  # Stored as comma-separated string

    # Gemini Analysis Results
    is_hiring: Mapped[bool] = mapped_column(default=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    extracted_budget: Mapped[str | None] = mapped_column(String, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_skills: Mapped[str | None] = mapped_column(String, nullable=True)  # Comma-separated

    # Pipeline & Outreach Tracking
    status: Mapped[str] = mapped_column(String, default="new")  # 'new', 'contacted', 'ignored'
    created_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
