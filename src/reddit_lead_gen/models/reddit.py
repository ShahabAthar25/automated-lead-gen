import calendar
import time
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, HttpUrl

from reddit_lead_gen.models.gemini import LeadAnalysis


class RedditRSSPost(BaseModel):
    """
    Pydantic schema representing raw RSS feed entries transformed into 
    clean, structured post objects.
    """
    id: str = Field(description="RSS post ID (e.g., t3_1w1gymd)")
    title: str = Field(description="Title of the Reddit post")
    permalink: HttpUrl = Field(description="Direct URL to the post")
    author: str = Field(description="Username of the poster")
    body: str = Field(default="", description="Clean plain-text extracted from summary HTML")
    created_utc: datetime = Field(description="Timestamp when post was published")
    subreddit: str = Field(default="unknown", description="Subreddit name")
    tags: list[str] = Field(default_factory=list, description="Categories or flair tags")
    score: float = Field(default=0.0, description="Lead score assigned by classifier")
    
    # Placeholder for optional JSON comment-count fetch later
    num_comments: int | None = Field(default=None, description="Set via optional JSON check")

    @classmethod
    def from_rss_entry(cls, entry: dict, subreddit: str = "unknown") -> "RedditRSSPost":
        """
        Factory method to parse a raw feedparser dictionary into a validated 
        RedditRSSPost model instance.
        """
        # Clean HTML body & preserve embedded URLs (Text (http://...))
        raw_html = entry.get("summary", "")
        clean_body = ""
        if raw_html:
            soup = BeautifulSoup(raw_html, "html.parser")
            post_div = soup.find("div", class_="md")
            target = post_div if post_div else soup

            clean_body = target.get_text(separator="\n", strip=True)

        # Extract safe permalink from links list or fallback
        permalink = entry.get("link", "")
        if not permalink and "links" in entry and isinstance(entry["links"], list):
            permalink = entry["links"][0].get("href", "")

        # Timezone-aware timestamp conversion
        published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if published_struct and isinstance(published_struct, time.struct_time):
            timestamp = calendar.timegm(published_struct)
            created_utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            created_utc = datetime.now(timezone.utc)

        # Extract post ID (strips RSS path if present)
        raw_id = entry.get("id", "")
        clean_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id

        # Extract tag names safely
        raw_tags = entry.get("tags", [])
        tags = [
            t.get("term").strip() 
            for t in raw_tags 
            if isinstance(t, dict) and t.get("term") and isinstance(t.get("term"), str)
        ]

        #  Clean author username
        clean_author = entry.get("author", "unknown").replace("/u/", "").split("/")[-1]

        return cls(
            id=clean_id,
            title=entry.get("title", ""),
            permalink=permalink,
            author=clean_author,
            body=clean_body,
            created_utc=created_utc,
            subreddit=subreddit,
            tags=tags,
        )

class QualifiedLead(BaseModel):
    """
    Combined domain model representing a high-value lead 
    ready for database storage and alert notifications.
    """
    post: RedditRSSPost
    analysis: LeadAnalysis
    status: str = Field(default="new", description="Outreach status: 'new', 'contacted', 'ignored'")

    @property
    def is_actionable(self) -> bool:
        """Helper to verify lead quality."""
        return self.analysis.is_hiring and self.analysis.score >= 0.7
