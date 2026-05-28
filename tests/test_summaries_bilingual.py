import asyncio
from datetime import datetime, timezone

from src.ai.summarizer import DailySummarizer
from src.models import ContentItem, SourceType


def test_bilingual_empty_state_renders_html_without_markdown_wrappers():
    summarizer = DailySummarizer()
    text = asyncio.run(
        summarizer.generate_bilingual_summary(
            items=[],
            date="2026-05-05",
            total_fetched=511,
        )
    )

    assert '<div class="tab-content active" data-lang="fr">' in text
    assert '<div class="tab-content " data-lang="en">' in text
    assert '<section class="summary-header">' in text
    assert '<article id="item-1" class="empty-state">' in text
    assert '<div class="fr-item">' not in text
    assert "### 1." not in text


def test_bilingual_non_empty_state_renders_article_html_without_markdown_wrappers():
    summarizer = DailySummarizer()
    item = ContentItem(
        id="rss:item-1",
        source_type=SourceType.RSS,
        title="Important discovery",
        url="https://example.com/discovery",
        content="content",
        author="tester",
        published_at=datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
    )
    item.ai_score = 8.2
    item.metadata.update({
        "whats_new_en": "A major update happened.",
        "why_it_matters_en": "It impacts many developers.",
        "key_details_en": "Version 2.0 is now live.",
    })

    text = asyncio.run(
        summarizer.generate_bilingual_summary(
            items=[item],
            date="2026-05-05",
            total_fetched=10,
        )
    )

    assert "<article id=\"item-1\">" in text
    assert "<div class=\"article-body\">" in text
    assert '<div class="fr-item">' not in text
    assert "### 1." not in text
