import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import src.ai.analyzer as analyzer_module
from src.ai.analyzer import ContentAnalyzer
from src.ai.utils import parse_json_response
from src.models import ContentItem, SourceType


def _make_item(item_id: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=f"Item {item_id}",
        url="https://example.com/item",
        published_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
    )


def test_analyze_batch_does_not_sleep_by_default(monkeypatch):
    analyzer = ContentAnalyzer(SimpleNamespace())
    items = [_make_item("rss:test:1"), _make_item("rss:test:2")]
    sleep_calls = []

    async def fake_analyze_item(item):
        item.ai_score = 8.0

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(analyzer, "_analyze_item", fake_analyze_item)
    monkeypatch.setattr(analyzer_module.asyncio, "sleep", fake_sleep)

    result = asyncio.run(analyzer.analyze_batch(items))

    assert len(result) == 2
    assert sleep_calls == []


def test_analyze_batch_sleeps_between_items_when_throttle_configured(monkeypatch):
    client = SimpleNamespace(config=SimpleNamespace(throttle_sec=1.5))
    analyzer = ContentAnalyzer(client)
    items = [_make_item("rss:test:1"), _make_item("rss:test:2"), _make_item("rss:test:3")]
    sleep_calls = []

    async def fake_analyze_item(item):
        item.ai_score = 8.0

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(analyzer, "_analyze_item", fake_analyze_item)
    monkeypatch.setattr(analyzer_module.asyncio, "sleep", fake_sleep)

    asyncio.run(analyzer.analyze_batch(items))

    assert sleep_calls == [1.5, 1.5]


def test_parse_json_response_normalizes_full_width_punctuation():
    response = "  {＂score＂：8，＂reason＂：＂ok＂}  "

    result = parse_json_response(response)

    assert result == {"score": 8, "reason": "ok"}


def test_parse_json_response_accepts_python_like_json():
    response = "{'score': 8, 'reason': 'ok', 'tags': ['a', 'b'],}"

    result = parse_json_response(response)

    assert result == {"score": 8, "reason": "ok", "tags": ["a", "b"]}


def test_parse_json_response_repairs_bare_keys_and_json_literals():
    response = "score: 8, reason: 'ok', tags: ['a', 'b'], extra: null, featured: true"

    result = parse_json_response("{" + response + "}")

    assert result == {
        "score": 8,
        "reason": "ok",
        "tags": ["a", "b"],
        "extra": None,
        "featured": True,
    }


def test_analyze_item_logs_raw_response_when_parsing_fails(capsys):
    class FakeClient:
        config = SimpleNamespace(throttle_sec=0)

        async def complete(self, system, user, temperature=None, max_tokens=None):
            return "definitely not json"

    analyzer = ContentAnalyzer(FakeClient())
    item = _make_item("rss:test:broken")

    asyncio.run(analyzer._analyze_item(item))

    captured = capsys.readouterr().out
    assert "impossible d'analyser la réponse d'analyse" in captured
    assert "Réponse brute pour rss:test:broken" in captured
    assert "definitely not json" in captured
