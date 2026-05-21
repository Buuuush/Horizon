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
    """Even a dominant feed keeps all its items when the pool is small.

    With 6 items across 3 source types (RSS, HN, Reddit) and 3 sub-sources,
    the proportional cap ceil(50/3) = 17 is larger than the 4 items from
    Feed A, so every item passes.
    """
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

    # All 6 items survive: the proportional cap (17) is larger than any sub-source size.
    assert len(balanced) == 6
    assert [item.id for item in balanced] == ["rss-1", "rss-2", "rss-3", "rss-4", "hn-1", "reddit-1"]


def test_balance_source_diversity_keeps_multiple_feeds(tmp_path):
    """With only one source type and a small pool, all items are kept.

    There are 3 sub-sources (Feed A, B, C), so the proportional sub-source
    cap is ceil(50/3) = 17.  Each feed has only 2 items (< 17), so the full
    list passes unchanged.
    """
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

    # All 6 items survive.
    assert len(balanced) == 6
    assert [item.id for item in balanced] == [
        "rss-a-1", "rss-a-2", "rss-b-1", "rss-b-2", "rss-c-1", "rss-c-2"
    ]


def test_balance_source_diversity_caps_per_sub_source_with_many_items(tmp_path):
    """With many items from a small number of feeds, each feed is capped at
    ceil(50 / num_sub_sources) to prevent monopolisation.
    """
    orchestrator = _make_orchestrator(tmp_path)
    items = (
        [_make_item(f"rss-a-{i}", SourceType.RSS, feed_name="Feed A") for i in range(20)]
        + [_make_item(f"rss-b-{i}", SourceType.RSS, feed_name="Feed B") for i in range(20)]
    )

    balanced = orchestrator._balance_source_diversity(items)

    # 1 source type → no source-type cap; 2 sub-sources → ceil(50/2) = 25 each.
    feed_a_count = sum(1 for item in balanced if item.id.startswith("rss-a-"))
    feed_b_count = sum(1 for item in balanced if item.id.startswith("rss-b-"))
    assert feed_a_count == 20
    assert feed_b_count == 20
    assert len(balanced) == 40


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


def test_editorial_depth_filter_drops_shallow_items(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)

    shallow_item = _make_item("rss-shallow", SourceType.RSS, feed_name="Feed A")
    shallow_item.ai_summary = "Too short."
    shallow_item.metadata.update({
        "detailed_summary_en": "Short.",
        "background_en": "",
        "sources": [],
    })

    rich_item = _make_item("rss-rich", SourceType.RSS, feed_name="Feed B")
    rich_item.ai_summary = "This item provides substantial context."
    rich_item.metadata.update({
        "detailed_summary_en": (
            "What happened, why it matters, and a few concrete details are described here. "
            "The item also adds background and a broader perspective for readers."
        ),
        "detailed_summary_fr": (
            "Ce qui s'est passé, pourquoi c'est important et plusieurs détails concrets sont expliqués ici. "
            "L'article ajoute aussi du contexte et une mise en perspective utile."
        ),
        "background_en": "Background context with more than enough substance for publication.",
        "sources": [{"url": "https://example.com/source", "title": "Source"}],
    })

    filtered = orchestrator._filter_shallow_items([shallow_item, rich_item])

    assert [item.id for item in filtered] == ["rss-rich"]


def test_editorial_depth_filter_keeps_original_list_if_all_thin(tmp_path):
    orchestrator = _make_orchestrator(tmp_path)

    item = _make_item("rss-thin", SourceType.RSS, feed_name="Feed A")
    item.ai_summary = "Tiny."
    item.metadata.update({"detailed_summary_en": "Tiny.", "background_en": ""})

    filtered = orchestrator._filter_shallow_items([item])

    assert filtered == [item]
