from reddit_lead_gen.adapters.reddit_client import RedditClient
from reddit_lead_gen.core.classifier import LeadClassifier

client = RedditClient()

posts = client.fetch_subreddit_posts("forhire")
leads_clasifier = LeadClassifier()

selected_posts = []
for post in posts:
    is_t1_posts = leads_clasifier.is_keyword_candidate(post)
    if is_t1_posts:
        selected_post = leads_clasifier.classify_lead(post)
        selected_posts.append(selected_post)

        __import__('pprint').pprint(selected_post)
