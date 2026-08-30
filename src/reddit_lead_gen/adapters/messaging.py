import logging
import httpx
from reddit_lead_gen.models.reddit import QualifiedLead
from reddit_lead_gen.settings import settings


class DiscordNotifier:
    """Sends high-value lead alerts to a private Discord channel via Webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url or settings.discord_webhook_url

    def send_lead_alert(self, lead: QualifiedLead) -> bool:
        """Format a QualifiedLead into a rich Discord embed and send it to discord"""
        if not self.webhook_url:
            logging.warning("Discord Webhook URL not configured. Skipping alert.")
            return False

        embed = {
            "title": f"🎯 {lead.post.title[:240]}",
            "url": str(lead.post.permalink),
            "color": 3066993,  # Emerald Green
            "fields": [
                {
                    "name": "💰 Budget",
                    "value": lead.analysis.extracted_budget or "Not specified",
                    "inline": True,
                },
                {
                    "name": "⭐ Score",
                    "value": f"`{lead.analysis.score:.2f}`",
                    "inline": True,
                },
                {
                    "name": "📍 Subreddit",
                    "value": f"r/{lead.post.subreddit}",
                    "inline": True,
                },
                {
                    "name": "👤 Author",
                    "value": f"u/{lead.post.author}",
                    "inline": True,
                },
                {
                    "name": "🧠 Reasoning",
                    "value": lead.analysis.reasoning or "No reasoning provided.",
                    "inline": False,
                },
            ],
            "footer": {"text": f"Post ID: {lead.post.id}"},
        }

        payload = {"embeds": [embed]}

        try:
            # Synchronous post call
            response = httpx.post(self.webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
        except Exception as e:
            logging.error(f"Error: {e}")
            return False
