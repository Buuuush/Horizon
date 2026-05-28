import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from src.models import RedditConfig, RedditSubredditConfig
from src.scrapers.reddit import REDDIT_HEADERS, RedditScraper


def _make_config(fetch_comments: int = 1) -> RedditConfig:
    return RedditConfig(
        enabled=True,
        subreddits=[
            RedditSubredditConfig(
                subreddit="LocalLLaMA",
                enabled=True,
                sort="hot",
                fetch_limit=1,
                min_score=1,
            )
        ],
        users=[],
        fetch_comments=fetch_comments,
    )


def _listing_payload() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "abc123",
                        "title": "Test post",
                        "is_self": True,
                        "subreddit": "LocalLLaMA",
                        "permalink": "/r/LocalLLaMA/comments/abc123/test_post/",
                        "author": "tester",
                        "created_utc": now.timestamp(),
                        "score": 42,
                        "upvote_ratio": 0.97,
                        "num_comments": 5,
                        "selftext": "post body",
                    },
                }
            ]
        }
    }


def test_reddit_fetch_uses_browser_like_headers():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"data": {"children": []}})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = RedditScraper(_make_config(fetch_comments=0), client)

    asyncio.run(scraper.fetch(datetime.now(timezone.utc) - timedelta(hours=1)))
    asyncio.run(client.aclose())

    assert len(requests) == 1
    assert requests[0].headers["user-agent"] == REDDIT_HEADERS["User-Agent"]
    assert requests[0].headers["accept-language"] == REDDIT_HEADERS["Accept-Language"]
    assert requests[0].headers["referer"] == REDDIT_HEADERS["Referer"]


def test_reddit_comment_403_degrades_to_post_without_comments():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/hot.json"):
            return httpx.Response(200, json=_listing_payload())
        if "/comments/" in request.url.path:
            return httpx.Response(403, text="blocked")
        raise AssertionError(f"unexpected url: {request.url}")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = RedditScraper(_make_config(fetch_comments=3), client)

    items = asyncio.run(scraper.fetch(datetime.now(timezone.utc) - timedelta(hours=1)))
    asyncio.run(client.aclose())

    assert len(items) == 1
    assert items[0].title == "Test post"
    assert "Top Comments" not in (items[0].content or "")


def test_reddit_subreddit_403_uses_rss_fallback():
    rss_payload = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<feed xmlns=\"http://www.w3.org/2005/Atom\">
  <entry>
    <id>tag:reddit.com,2005:abc123</id>
    <title>Fallback post</title>
    <updated>2026-05-28T18:00:00Z</updated>
    <author><name>rss_user</name></author>
    <link href=\"https://www.reddit.com/r/LocalLLaMA/comments/abc123/fallback_post/\" />
    <content type=\"html\">&lt;p&gt;RSS summary&lt;/p&gt;</content>
  </entry>
</feed>
"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/hot.json"):
            return httpx.Response(403, text="blocked")
        if request.url.path.endswith("/.rss"):
            return httpx.Response(200, text=rss_payload, headers={"Content-Type": "application/atom+xml"})
        raise AssertionError(f"unexpected url: {request.url}")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    scraper = RedditScraper(_make_config(fetch_comments=0), client)

    items = asyncio.run(scraper.fetch(datetime(2026, 5, 28, 0, 0, tzinfo=timezone.utc)))
    asyncio.run(client.aclose())

    assert len(items) == 1
    assert items[0].title == "Fallback post"
    assert items[0].metadata.get("via") == "rss_fallback"
