from datetime import datetime, timezone
from types import SimpleNamespace

from src.models import AIConfig, Config, FilteringConfig, ContentItem, Profile, SourceType, SourcesConfig
from src.orchestrator import HorizonOrchestrator
from src.storage.manager import StorageManager


def _make_item(item_id: str, source_type: SourceType, *, feed_name: str | None = None, subreddit: str | None = None) -> ContentItem:
    metadata = {}
    if feed_name:
        metadata["feed_name"] = feed_name
    if subreddit:
        metadata["subreddit"] = subreddit

    return ContentItem(
        id=item_id,
        source_type=source_type,
        title=f"Item {item_id}",
        url=f"https://example.com/{item_id}",
        published_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
        ai_score=8.0,
        metadata=metadata,
    )


def _make_orchestrator(tmp_path) -> HorizonOrchestrator:
    storage = StorageManager(data_dir=str(tmp_path))
    config = Config(
        ai=AIConfig(
            provider="openai",
            model="gpt-4",
            api_key_env="OPENAI_API_KEY",
        ),
        sources=SourcesConfig(),
        filtering=FilteringConfig(),
    )
    return HorizonOrchestrator(config, storage, profile=None, broadcast_callback=None)


def test_balance_source_diversity_limits_dominant_source_family(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    items = [
        _make_item("rss-1", SourceType.RSS, feed_name="Feed A"),
        _make_item("rss-2", SourceType.RSS, feed_name="Feed A"),
        _make_item("rss-3", SourceType.RSS, feed_name="Feed A"),
        _make_item("rss-4", SourceType.RSS, feed_name="Feed A"),
        _make_item("hn-1", SourceType.HACKERNEWS),
        _make_item("reddit-1", SourceType.REDDIT, subreddit="machinelearning"),
    ]

    balanced = orchestrator._balance_source_diversity(items)

    assert len(balanced) == 3
    assert [item.id for item in balanced] == ["rss-1", "hn-1", "reddit-1"]


def test_balance_source_diversity_keeps_multiple_feeds(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    items = [
        _make_item("rss-a-1", SourceType.RSS, feed_name="Feed A"),
        _make_item("rss-a-2", SourceType.RSS, feed_name="Feed A"),
        _make_item("rss-b-1", SourceType.RSS, feed_name="Feed B"),
        _make_item("rss-b-2", SourceType.RSS, feed_name="Feed B"),
        _make_item("rss-c-1", SourceType.RSS, feed_name="Feed C"),
        _make_item("rss-c-2", SourceType.RSS, feed_name="Feed C"),
    ]

    balanced = orchestrator._balance_source_diversity(items)

    assert len(balanced) == 3
    assert [item.id for item in balanced] == ["rss-a-1", "rss-b-1", "rss-c-1"]


def test_balance_source_diversity_respects_profile_limits(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)
    orchestrator.profile = Profile(
        name="balanced",
        max_items_per_source_type=2,
        max_items_per_sub_source=1,
    )
    items = [
        _make_item("rss-a-1", SourceType.RSS, feed_name="Feed A"),
        _make_item("rss-a-2", SourceType.RSS, feed_name="Feed A"),
        _make_item("rss-b-1", SourceType.RSS, feed_name="Feed B"),
        _make_item("rss-b-2", SourceType.RSS, feed_name="Feed B"),
        _make_item("hn-1", SourceType.HACKERNEWS),
    ]

    balanced = orchestrator._balance_source_diversity(items)

    assert len(balanced) == 3
    assert [item.id for item in balanced] == ["rss-a-1", "rss-b-1", "hn-1"]
