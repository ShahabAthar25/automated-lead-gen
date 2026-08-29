import logging
import feedparser
from reddit_lead_gen.models.reddit import RedditRSSPost
from reddit_lead_gen.settings import settings

SUBREDDIT_URL = "https://www.reddit.com/r/{}/new.rss?feed={}&user={}"


class RedditClient:
    def __init__(
        self,
        agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ) -> None:
        self.agent = agent

    def fetch_subreddit_posts(self, subreddit: str) -> list[RedditRSSPost]:
        url = SUBREDDIT_URL.format(subreddit, settings.reddit_feed_token, settings.reddit_username)
        feed = feedparser.parse(url, agent=self.agent)

        if hasattr(feed, "status") and feed.status != 200:
            logging.error(f"Unable to fetch RSS for r/{subreddit}. Status Code: {feed.status}")
            return []

        posts: list[RedditRSSPost] = []
        for entry in feed.get("entries", []):
            try:
                post_model = RedditRSSPost.from_rss_entry(entry, subreddit=subreddit)
                posts.append(post_model)
            except Exception as e:
                logging.warning(f"Failed to parse post {entry.get('id')}: {e}")

        return posts
