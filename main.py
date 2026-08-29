from reddit_lead_gen.adapters.reddit_client import RedditClient

client = RedditClient()

posts = client.fetch_subreddit_posts("forhire")
