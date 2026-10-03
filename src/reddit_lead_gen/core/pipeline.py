import asyncio
import logging

from reddit_lead_gen.adapters.database import DatabaseAdapter
from reddit_lead_gen.adapters.messaging import DiscordNotifier
from reddit_lead_gen.core.classifier import LeadClassifier
from reddit_lead_gen.models.reddit import QualifiedLead, RedditRSSPost
from reddit_lead_gen.providers.router import ModelRouter
from reddit_lead_gen.settings import settings


class LeadPipeline:
    def __init__(
        self,
        db: DatabaseAdapter | None = None,
        classifier: LeadClassifier | None = None,
        notifier: DiscordNotifier | None = None,
        min_score: float | None = None,
        router: ModelRouter | None = None,
    ) -> None:
        self.db: DatabaseAdapter = db or DatabaseAdapter()
        self.classifier: LeadClassifier = classifier or LeadClassifier(router=router)
        self.notifier: DiscordNotifier = notifier or DiscordNotifier()
        self.min_score = min_score or settings.pipeline.min_lead_score

    async def process_post(self, post: RedditRSSPost) -> QualifiedLead | None:
        """
        Classifies post and stores them in the database. Skips all duplicate posts.
        """

        if self.db.is_post_seen(post.id):
            logging.info(f"⏭️ Post {post.id} already seen in DB. Skipping.")
            return None

        # Persist raw post immediately for market research
        self.db.save_raw_post(post)

        # Stage 1: Fast keyword candidate filter
        if not self.classifier.is_keyword_candidate(post):
            return None

        logging.info(f"🔍 Analyzing candidate post: {post.title[:50]}...")

        # Stage 2: LLM classification via ModelRouter
        score, analysis = await self.classifier.classify_lead(post)

        if not analysis or score < self.min_score:
            return None  # Will add disapproved leads later for testing and checking

        # Build domain model
        lead = QualifiedLead(post=post, analysis=analysis, status="new")
        logging.info(f"🔥 HIGH VALUE LEAD FOUND: {lead.post.id} (Score: {score:.2f})")

        # Save qualified lead to database
        self.db.save_lead(lead)

        # Dispatch Discord notification
        if self.notifier.webhook_url:
            logging.info("📢 Dispatching Discord Webhook notification...")
            success = self.notifier.send_lead_alert(lead)
            if success:
                logging.info("✅ Discord alert sent successfully.")
            else:
                logging.error("❌ Failed to send Discord alert.")

        return lead

    def process_post_sync(self, post: RedditRSSPost) -> QualifiedLead | None:
        """Synchronous wrapper for scripts and testing."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.process_post(post)).result()
        else:
            return asyncio.run(self.process_post(post))
