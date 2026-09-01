import asyncio
import logging
import time
from typing import Dict, List

from reddit_lead_gen.adapters.reddit_client import RedditClient
from reddit_lead_gen.core.pipeline import LeadPipeline
from reddit_lead_gen.settings import settings


class SubredditTracker:
    """Tracks state and dynamic polling backoff for a single subreddit."""

    def __init__(
        self,
        name: str,
        base_interval: int | None = None,
        min_interval: int | None = None,
        max_interval: int | None = None,
    ) -> None:
        self.name = name

        # Fall back to global settings defaults if specific override isn't provided
        self.current_interval = float(
            base_interval
            if base_interval is not None
            else settings.polling.default_base_interval
        )
        self.min_interval = float(
            min_interval
            if min_interval is not None
            else settings.polling.default_min_interval
        )
        self.max_interval = float(
            max_interval
            if max_interval is not None
            else settings.polling.default_max_interval
        )

        self.last_polled_at: float = 0.0

    def is_due(self, now: float) -> bool:
        """Checks if enough time has elapsed to poll this specific subreddit."""
        return (now - self.last_polled_at) >= self.current_interval

    def update_interval(self, total_fetched: int, new_posts_count: int) -> None:
        """Adjusts ONLY this subreddit's interval based on its own velocity."""
        if total_fetched == 0:
            self.current_interval = min(self.max_interval, self.current_interval * 1.25)
            return

        new_ratio = new_posts_count / total_fetched

        if new_ratio > 0.30:
            # High activity on THIS subreddit -> speed up
            self.current_interval = max(self.min_interval, self.current_interval * 0.75)
            logging.info(
                f"⚡ [r/{self.name}] High activity ({new_ratio:.0%} new). Fast-polling set to {int(self.current_interval)}s"
            )
        elif new_ratio < 0.10:
            # Low activity on THIS subreddit -> back off
            self.current_interval = min(self.max_interval, self.current_interval * 1.50)
            logging.info(
                f"🐢 [r/{self.name}] Low activity ({new_ratio:.0%} new). Back-off set to {int(self.current_interval)}s"
            )


class MultiSubredditAdaptiveListener:
    """Monitors multiple subreddits asynchronously with isolated, per-subreddit polling rates."""

    def __init__(
        self,
        subreddits: List[str],
        pipeline: LeadPipeline | None = None,
        reddit_client: RedditClient | None = None,
        poll_tick_seconds: int | None = None,
    ) -> None:
        self.pipeline = pipeline or LeadPipeline()
        self.client = reddit_client or RedditClient()
        self.poll_tick = poll_tick_seconds or settings.polling.poll_tick_seconds

        target_subs = subreddits or settings.target_subreddits.active
        self.trackers: Dict[str, SubredditTracker] = {}

        # Read specific overrides from settings.subreddits dict
        for sub in target_subs:
            override = settings.subreddits.get(sub)
            if override:
                self.trackers[sub] = SubredditTracker(
                    name=sub,
                    base_interval=override.base_interval,
                    min_interval=override.min_interval,
                    max_interval=override.max_interval,
                )
            else:
                self.trackers[sub] = SubredditTracker(name=sub)

    async def start(self) -> None:
        """Continuous ticker loop that checks individual subreddit readiness."""
        logging.info(
            f"🎧 Starting Independent Per-Subreddit Listener for: {list(self.trackers.keys())}"
        )

        while True:
            now = time.time()

            for sub_name, tracker in self.trackers.items():
                if tracker.is_due(now):
                    # Update timestamp immediately to lock execution
                    tracker.last_polled_at = now
                    await self._poll_subreddit(tracker)

            # Short tick sleep (keeps ticker light without locking CPU)
            await asyncio.sleep(self.poll_tick)

    async def _poll_subreddit(self, tracker: SubredditTracker) -> None:
        """Polls a single subreddit, runs posts through pipeline, and updates tracker."""
        try:
            logging.info(f"📡 Polling r/{tracker.name}...")
            posts = self.client.fetch_subreddit_posts(tracker.name)

            new_posts_count = 0
            for post in posts:
                # Deduplication check before pipeline execution
                is_unseen = not self.pipeline.db.is_post_seen(post.id)
                lead = self.pipeline.process_post(post)

                if lead is not None or is_unseen:
                    new_posts_count += 1

            # Adjust this subreddit's interval
            tracker.update_interval(len(posts), new_posts_count)

        except Exception as e:
            logging.error(f"❌ Error polling r/{tracker.name}: {e}", exc_info=True)
            # Apply slight backoff on error
            tracker.current_interval = min(
                tracker.max_interval, tracker.current_interval * 1.25
            )
