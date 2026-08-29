import asyncio
import logging
from typing import AsyncGenerator, List, Set
from reddit_lead_gen.adapters.reddit_client import RedditClient

logger = logging.getLogger(__name__)


class AdaptiveRedditListener:
    """Poller that adjusts its delay based on average subreddit posting frequency."""

    def __init__(
        self,
        client: RedditClient,
        subreddits: List[str],
        min_interval: int = 30,    # Minimum sleep: 30 seconds
        max_interval: int = 300,   # Maximum sleep: 5 minutes (300 seconds)
        window_size: int = 10      # Number of recent intervals to average
    ) -> None:
        self.client = client
        self.subreddits = subreddits
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.window_size = window_size
        
        self.seen_ids: Set[str] = set()
        self._timestamps: List[float] = []
        self._current_sleep = min_interval

    def _update_adaptive_sleep(self, new_timestamps: List[float]) -> None:
        """Calculates moving average of post intervals and updates sleep time."""
        if not new_timestamps:
            # If no new posts, slowly back off up to the max threshold
            self._current_sleep = min(self._current_sleep * 1.5, self.max_interval)
            return

        # Add new timestamps and keep only the recent window
        self._timestamps.extend(new_timestamps)
        self._timestamps = sorted(self._timestamps)[-self.window_size:]

        if len(self._timestamps) < 2:
            return

        # Calculate average time difference between consecutive posts (in seconds)
        diffs = [
            self._timestamps[i] - self._timestamps[i - 1]
            for i in range(1, len(self._timestamps))
        ]
        avg_gap = sum(diffs) / len(diffs)

        # Target fetching at half the average arrival rate (clamped between min and max)
        target_sleep = avg_gap / 2.0
        self._current_sleep = max(self.min_interval, min(target_sleep, self.max_interval))

        logger.debug(
            f"Avg post gap: {avg_gap:.1f}s | Next sleep interval set to: {self._current_sleep:.1f}s"
        )

    async def listen(self, fetch_limit: int = 25) -> AsyncGenerator[dict, None]:
        """Runs the adaptive loop, yielding unseen post payloads."""
        combined_subs = "+".join(self.subreddits)
        logger.info(f"Starting adaptive listener for r/{combined_subs}")

        while True:
            try:
                # 1. Fetch latest posts across subreddits
                posts = await self.client.fetch_recent_posts(combined_subs, limit=fetch_limit)
                
                new_posts = []
                new_timestamps = []

                # 2. Extract new, unseen posts (sorted oldest to newest)
                for post in reversed(posts):
                    if post.id not in self.seen_ids:
                        self.seen_ids.add(post.id)
                        new_posts.append(post)
                        new_timestamps.append(post.created_utc)

                # Keep local memory set under control
                if len(self.seen_ids) > 2000:
                    self.seen_ids = set(list(self.seen_ids)[-1000:])

                # Update sleep duration based on recent post velocity
                self._update_adaptive_sleep(new_timestamps)

                # Yield new posts downstream to classification pipeline
                for post in new_posts:
                    yield {
                        "id": post.id,
                        "title": post.title,
                        "body": post.selftext,
                        "url": post.url,
                        "permalink": f"https://reddit.com{post.permalink}",
                        "author": post.author.name if post.author else "[deleted]",
                        "created_utc": post.created_utc,
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "subreddit": post.subreddit.display_name,
                    }

            except Exception as e:
                logger.error(f"Error in adaptive listener: {e}. Backing off.")
                self._current_sleep = min(self._current_sleep * 2, self.max_interval)

            # 5. Sleep for the dynamically calculated interval
            logger.info(f"Sleeping for {self._current_sleep:.1f} seconds...")
            await asyncio.sleep(self._current_sleep)
