from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.ai.enricher import ContentEnricher
from src.ai.prompts import CONTENT_ENRICHMENT_SYSTEM, CONTENT_ENRICHMENT_USER
from src.models import ContentItem, SourceType


def test_enrichment_prompts_request_longer_fields():
    assert "whats_new" in CONTENT_ENRICHMENT_SYSTEM
    assert "2-3 complete sentences" in CONTENT_ENRICHMENT_SYSTEM
    assert "background" in CONTENT_ENRICHMENT_SYSTEM
    assert "3-5 sentences" in CONTENT_ENRICHMENT_SYSTEM
    assert "2-4 sentences" in CONTENT_ENRICHMENT_SYSTEM

    assert "<2-3 sentences in English>" in CONTENT_ENRICHMENT_USER
    assert "<3-5 sentences in English, or empty string>" in CONTENT_ENRICHMENT_USER


def test_enrichment_combines_background_into_detailed_summary(monkeypatch):
    class FakeClient:
        config = SimpleNamespace(throttle_sec=0)

        async def complete(self, system, user, temperature=None, max_tokens=None):
            return (
                '{'
                '"title_en": "Short title",'
                '"title_fr": "Titre court",'
                '"whats_new_en": "First change. Second detail.",'
                '"whats_new_fr": "Premier changement. Deuxième détail.",'
                '"why_it_matters_en": "It matters. Here is why.",'
                '"why_it_matters_fr": "C\'est important. Voici pourquoi.",'
                '"key_details_en": "Key fact one. Key fact two.",'
                '"key_details_fr": "Fait clé un. Fait clé deux.",'
                '"background_en": "Background one. Background two.",'
                '"background_fr": "Contexte un. Contexte deux.",'
                '"community_discussion_en": "Comment one. Comment two.",'
                '"community_discussion_fr": "Commentaire un. Commentaire deux.",'
                '"evidence_strength": 8,'
                '"evidence_note_en": "Good evidence.",'
                '"evidence_note_fr": "Bonne preuve.",'
                '"sources": ["https://example.com/source"]'
                '}'
            )

    enricher = ContentEnricher(FakeClient())
    item = ContentItem(
        id="rss:test:1",
        source_type=SourceType.RSS,
        title="Test item",
        url="https://example.com/item",
        content="Core content",
        published_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = "Short summary."

    async def fake_extract_concepts(item, content_text):
        return ["topic"]

    async def fake_web_search(query, max_results=5):
        return [
            {
                "title": "Source title",
                "url": "https://example.com/source",
                "body": "Source body",
            }
        ]

    monkeypatch.setattr(enricher, "_extract_concepts", fake_extract_concepts)
    monkeypatch.setattr(enricher, "_web_search", fake_web_search)

    asyncio.run(enricher._enrich_item(item))

    assert "First change." in item.metadata["detailed_summary_en"]
    assert "Background one." in item.metadata["detailed_summary_en"]
    assert "\n\n" in item.metadata["detailed_summary_en"]
    assert item.metadata["background_en"] == "Background one. Background two."
    assert item.metadata["sources"][0]["url"] == "https://example.com/source"
    assert item.ai_score >= 8.0
