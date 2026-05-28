import pytest

from src.ai.summarizer import DailySummarizer


@pytest.mark.asyncio
async def test_bilingual_empty_state_renders_html_without_markdown_wrappers():
    summarizer = DailySummarizer()
    text = await summarizer.generate_bilingual_summary(
        items=[],
        date="2026-05-05",
        total_fetched=511,
    )

    assert '<div class="tab-content active" data-lang="fr">' in text
    assert '<div class="tab-content " data-lang="en">' in text
    assert '<section class="summary-header">' in text
    assert '<article id="item-1" class="empty-state">' in text
    assert '<div class="fr-item">' not in text
    assert "### 1." not in text
