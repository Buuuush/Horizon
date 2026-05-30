"""Unit tests for daily summary rendering."""

from datetime import datetime, timezone

import pytest

from src.ai.summarizer import DailySummarizer
from src.models import ContentItem, SourceType


def _make_item(idx: int) -> ContentItem:
    item = ContentItem(
        id=f"rss:item-{idx}",
        source_type=SourceType.RSS,
        title=f"Important Item {idx}",
        url=f"https://example.com/items/{idx}",
        content="content",
        author="tester",
        published_at=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = f"Summary for item {idx}."
    item.ai_tags = ["AI", "News"]
    return item


def test_generate_webhook_overview_lists_items_without_full_details():
    summarizer = DailySummarizer()
    items = [_make_item(1), _make_item(2)]

    result = summarizer.generate_webhook_overview(
        items,
        date="2026-04-25",
        total_fetched=10,
        language="en",
    )

    assert "From 10 items, 2 important content pieces were selected" in result
    assert "1. [Important Item 1](https://example.com/items/1)" in result
    assert "2. [Important Item 2](https://example.com/items/2)" in result
    assert "Summary for item 1." not in result


def test_generate_webhook_item_renders_single_item_detail():
    summarizer = DailySummarizer()

    result = summarizer.generate_webhook_item(
        _make_item(1),
        language="en",
        index=1,
        total=2,
    )

    assert result.startswith("Item 1/2")
    assert "## [Important Item 1](https://example.com/items/1)" in result
    assert "Summary for item 1." in result
    assert "**Tags**: `#AI`, `#News`" in result


def test_generate_webhook_item_includes_discussion_link_when_distinct():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://news.ycombinator.com/item?id=1"

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "tester · Apr 25, 08:00 · [Discussion](https://news.ycombinator.com/item?id=1)" in result


def test_generate_webhook_item_omits_discussion_link_when_same_as_item_url():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = item.url

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "[Discussion](https://example.com/items/1)" not in result


def test_generate_webhook_item_uses_localized_discussion_label():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://www.reddit.com/r/python/comments/abc123/test/"

    result = summarizer.generate_webhook_item(
        item,
        language="zh",
        index=1,
        total=1,
    )

    assert "[社区讨论](https://www.reddit.com/r/python/comments/abc123/test/)" in result


@pytest.mark.asyncio
async def test_generate_summary_translates_english_fields_only_at_render_time():
    class FakeTranslator:
        available = True

        async def translate_to_french(self, texts):
            return [f"FR: {text}" for text in texts]

    summarizer = DailySummarizer(translator=FakeTranslator())
    item = _make_item(1)
    item.metadata.update({
        "title_en": "English title",
        "whats_new_en": "What happened in English.",
        "why_it_matters_en": "Why it matters in English.",
        "key_details_en": "Key details in English.",
        "background_en": "Background in English.",
        "community_discussion_en": "Community discussion in English.",
        "evidence_note_en": "Evidence note in English.",
    })

    result = await summarizer.generate_summary(
        [item],
        date="2026-04-25",
        total_fetched=10,
        language="fr",
    )

    assert "FR: English title" in result
    assert "FR: What happened in English." in result
    assert "FR: Background in English." in result
    assert "English title" not in item.metadata.get("title_fr", "") or item.metadata.get("title_fr", "").startswith("FR:")


@pytest.mark.asyncio
async def test_generate_summary_renders_ai_scores_in_html():
    summarizer = DailySummarizer()
    item = _make_item(1)

    result = await summarizer.generate_summary(
        [item],
        date="2026-04-25",
        total_fetched=10,
        language="en",
    )

    assert "Important Item 1" in result
    assert "<span class=\"score\">" in result
    assert "⭐" in result


@pytest.mark.asyncio
async def test_generate_summary_renders_editorial_article_structure():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata.update({
        "title_fr": "Titre éditorial",
        "whats_new_fr": "Il s'est passé quelque chose de nouveau.",
        "why_it_matters_fr": "Cela change la donne pour plusieurs acteurs.",
        "key_details_fr": "Voici les détails les plus concrets.",
        "background_fr": "Un peu de contexte pour comprendre le sujet.",
        "community_discussion_fr": "La discussion reste nuancée.",
        "evidence_note_fr": "Les sources disponibles sont solides.",
    })

    result = await summarizer.generate_summary(
        [item],
        date="2026-04-25",
        total_fetched=10,
        language="fr",
    )

    assert "<p class=\"article-lead\">" in result
    assert "<section class=\"article-section\">" in result
    assert "<blockquote>" in result
    assert "<section class=\"article-background\">" in result
