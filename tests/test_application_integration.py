import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reddit_lead_gen.core.classifier import LeadClassifier
from reddit_lead_gen.core.listener import MultiSubredditAdaptiveListener, SubredditTracker
from reddit_lead_gen.core.pipeline import LeadPipeline
from reddit_lead_gen.models.analysis import LeadAnalysis
from reddit_lead_gen.models.reddit import RedditRSSPost
from reddit_lead_gen.providers.router import ModelRouter


@pytest.fixture
def sample_post():
    return RedditRSSPost(
        id="test_post_001",
        title="[Hiring] Need Python Developer to build scraping bot",
        permalink="https://reddit.com/r/forhire/comments/test_post_001",
        author="client_dev",
        body="Looking for a Python dev to create a scraper for market data. Budget $500.",
        created_utc=datetime.now(timezone.utc),
        subreddit="forhire",
        tags=["Hiring"],
    )


@pytest.fixture
def non_candidate_post():
    return RedditRSSPost(
        id="test_post_002",
        title="[For Hire] Full Stack Dev available for hire",
        permalink="https://reddit.com/r/forhire/comments/test_post_002",
        author="freelancer_joe",
        body="I can build web apps and python tools for you. Cheap rates.",
        created_utc=datetime.now(timezone.utc),
        subreddit="forhire",
        tags=["For Hire"],
    )


@pytest.fixture
def mock_analysis():
    return LeadAnalysis(
        is_hiring=True,
        score=0.92,
        reasoning="Explicit hiring intent with budget.",
        extracted_budget="$500",
        matched_skills=["Python", "Web Scraping"],
    )


# --- Tests: LeadClassifier Integration with ModelRouter ---


@pytest.mark.asyncio
async def test_classifier_routes_all_requests_to_model_router(
    sample_post, mock_analysis
):
    mock_router = MagicMock(spec=ModelRouter)
    mock_router.analyze = AsyncMock(return_value=(0.92, mock_analysis))

    classifier = LeadClassifier(router=mock_router)
    score, analysis = await classifier.classify_lead(sample_post)

    assert score == 0.92
    assert analysis == mock_analysis
    mock_router.analyze.assert_called_once()
    called_prompt = mock_router.analyze.call_args[0][0]
    assert sample_post.title in called_prompt
    assert "forhire" in called_prompt


def test_classifier_sync_wrapper_calls_router(sample_post, mock_analysis):
    mock_router = MagicMock(spec=ModelRouter)
    mock_router.analyze = AsyncMock(return_value=(0.92, mock_analysis))

    classifier = LeadClassifier(router=mock_router)
    score, analysis = classifier.classify_lead_sync(sample_post)

    assert score == 0.92
    assert analysis == mock_analysis
    mock_router.analyze.assert_called_once()


def test_classifier_default_router_creation():
    with patch(
        "reddit_lead_gen.core.classifier.settings"
    ) as mock_settings:
        mock_settings.pipeline.llm_model = "gemini"
        mock_settings.pipeline.gemini_rpm = 10
        mock_settings.pipeline.groq_rpm = 20
        mock_settings.pipeline.min_spacing_seconds = 3.0
        mock_settings.gemini_api_key = "dummy-gemini-key"
        mock_settings.groq_api_key = "dummy-groq-key"

        classifier = LeadClassifier()

        assert isinstance(classifier.router, ModelRouter)
        assert len(classifier.router.providers) == 2
        # Primary provider is Gemini because llm_model == "gemini"
        assert classifier.router.providers[0].name == "Gemini"
        assert classifier.router.providers[1].name == "Groq"
        assert classifier.provider.name == "Gemini"
        assert classifier.router.min_spacing_seconds == 3.0


# --- Tests: LeadPipeline Integration with ModelRouter ---


@pytest.mark.asyncio
async def test_pipeline_routes_candidate_posts_through_router(
    sample_post, mock_analysis
):
    mock_router = MagicMock(spec=ModelRouter)
    mock_router.analyze = AsyncMock(return_value=(0.92, mock_analysis))

    mock_db = MagicMock()
    mock_db.is_post_seen.return_value = False

    mock_notifier = MagicMock()
    mock_notifier.webhook_url = "https://discord.com/api/webhooks/mock"
    mock_notifier.send_lead_alert.return_value = True

    pipeline = LeadPipeline(
        db=mock_db,
        router=mock_router,
        notifier=mock_notifier,
        min_score=0.7,
    )

    lead = await pipeline.process_post(sample_post)

    assert lead is not None
    assert lead.analysis == mock_analysis
    mock_router.analyze.assert_called_once()
    mock_db.save_raw_post.assert_called_once_with(sample_post)
    mock_db.save_lead.assert_called_once()
    mock_notifier.send_lead_alert.assert_called_once()


@pytest.mark.asyncio
async def test_pipeline_skips_router_for_disqualified_keyword_post(
    non_candidate_post,
):
    mock_router = MagicMock(spec=ModelRouter)
    mock_router.analyze = AsyncMock()

    mock_db = MagicMock()
    mock_db.is_post_seen.return_value = False

    pipeline = LeadPipeline(db=mock_db, router=mock_router)
    lead = await pipeline.process_post(non_candidate_post)

    assert lead is None
    # Model router is never called for non-candidate posts, preserving API quotas
    mock_router.analyze.assert_not_called()
    mock_db.save_raw_post.assert_called_once_with(non_candidate_post)


# --- Tests: MultiSubredditAdaptiveListener Integration ---


@pytest.mark.asyncio
async def test_listener_awaits_pipeline_process_post(sample_post):
    mock_pipeline = MagicMock()
    mock_pipeline.db.is_post_seen.return_value = False
    mock_pipeline.process_post = AsyncMock(return_value=None)

    mock_client = MagicMock()
    mock_client.fetch_subreddit_posts.return_value = [sample_post]

    listener = MultiSubredditAdaptiveListener(
        subreddits=["forhire"],
        pipeline=mock_pipeline,
        reddit_client=mock_client,
    )

    tracker = SubredditTracker("forhire")
    await listener._poll_subreddit(tracker)

    mock_client.fetch_subreddit_posts.assert_called_once_with("forhire")
    mock_pipeline.process_post.assert_called_once_with(sample_post)
