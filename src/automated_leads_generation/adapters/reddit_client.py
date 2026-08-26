import logging
from typing import AsyncGenerator, Dict, List, Optional
import asyncpraw
from asyncpraw.exceptions import AsyncPRAWException
from asyncpraw.models import Submission

logger = logging.getLogger(__name__)


class RedditClient:
    """Async wrapper for Reddit API client operations using AsyncPRAW."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent
        self._username = username
        self._password = password
        self._reddit: Optional[asyncpraw.Reddit] = None

    async def connect(self) -> None:
        """Initialize the async Reddit session."""
        if not self._reddit:
            self._reddit = asyncpraw.Reddit(
                client_id=self._client_id,
                client_secret=self._client_secret,
                user_agent=self._user_agent,
                username=self._username,
                password=self._password,
            )
            logger.info("Reddit client session established.")

    async def close(self) -> None:
        """Close the async Reddit session."""
        if self._reddit:
            await self._reddit.close()
            self._reddit = None
            logger.info("Reddit client session closed.")

    async def __aenter__(self) -> "RedditClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def client(self) -> asyncpraw.Reddit:
        if not self._reddit:
            raise RuntimeError("Reddit client is not connected. Call connect() first.")
        return self._reddit

    async def fetch_recent_posts(
        self, subreddit_name: str, limit: int = 50
    ) -> List[Submission]:
        """Fetch latest posts for backfills or initial sync."""
        try:
            subreddit = await self.client.subreddit(subreddit_name)
            posts = []
            async for submission in subreddit.new(limit=limit):
                posts.append(submission)
            return posts
        except AsyncPRAWException as e:
            logger.error(f"Failed to fetch recent posts for r/{subreddit_name}: {e}")
            return []

    async def get_post_details(
        self, submission_id: str, fetch_comments: bool = False, max_comments: int = 10
    ) -> Dict:
        """Fetch detailed information for a single post."""
        try:
            submission: Submission = await self.client.submission(id=submission_id)
            await submission.load()

            # Check if hiring post already has competetion.
            total_comments = getattr(submission, "num_comments", 0)
            if max_comments_threshold is not None and total_comments > max_comments_threshold:
                logger.info(
                    f"Skipping post {submission_id} ('{submission.title[:30]}...'): "
                    f"{total_comments} comments exceeds threshold of {max_comments_threshold}."
                )
                return None  # Drop saturated lead instantly

            # Handle deleted or suspended authors safely
            author_name = submission.author.name if submission.author else "[deleted]"

            details = {
                "id": submission.id,
                "title": submission.title,
                "body": submission.selftext,
                "url": submission.url,
                "permalink": f"https://reddit.com{submission.permalink}",
                "author": author_name,
                "created_utc": submission.created_utc,
                "score": submission.score,
                "num_comments": submission.num_comments,
                "subreddit": submission.subreddit.display_name,
                "flair": submission.link_flair_text,
                "comments": [],
            }

            if fetch_comments and submission.num_comments > 0:
                await submission.comments.replace_more(limit=0)
                comments_list = submission.comments.list()[:max_comments]
                details["comments"] = [
                    {
                        "id": c.id,
                        "author": c.author.name if c.author else "[deleted]",
                        "body": c.body,
                        "score": c.score,
                    }
                    for c in comments_list
                ]

            return details
        except AsyncPRAWException as e:
            logger.error(f"Failed to fetch details for submission {submission_id}: {e}")
            raise

    async def get_author_profile(self, username: str) -> Optional[Dict]:
        """Fetch author metadata for spam checking & credibility scoring."""
        if username == "[deleted]":
            return None

        try:
            redditor = await self.client.redditor(username)
            await redditor.load()
            return {
                "username": redditor.name,
                "created_utc": getattr(redditor, "created_utc", None),
                "link_karma": getattr(redditor, "link_karma", 0),
                "comment_karma": getattr(redditor, "comment_karma", 0),
                "is_gold": getattr(redditor, "is_gold", False),
                "is_mod": getattr(redditor, "is_mod", False),
            }
        except Exception as e:
            logger.warning(f"Could not load redditor details for {username}: {e}")
            return None
