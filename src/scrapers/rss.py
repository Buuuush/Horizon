"""RSS feed scraper implementation."""

import calendar
import logging
import os
import re
from datetime import datetime, timezone
from typing import List
from email.utils import parsedate_to_datetime
import httpx
import feedparser

from .base import BaseScraper
from ..models import ContentItem, SourceType, RSSSourceConfig

logger = logging.getLogger(__name__)


class RSSScraper(BaseScraper):
    """Scraper for RSS/Atom feeds."""

    def __init__(self, sources: List[RSSSourceConfig], http_client: httpx.AsyncClient):
        """Initialize RSS scraper.

        Args:
            sources: List of RSS feed configurations
            http_client: Shared async HTTP client
        """
        super().__init__({"sources": sources}, http_client)

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch RSS feed items.

        Args:
            since: Only fetch items published after this time

        Returns:
            List[ContentItem]: Fetched content items
        """
        items = []
        sources = self.config["sources"]

        for source in sources:
            if not source.enabled:
                continue

            feed_items = await self._fetch_feed(source, since)
            items.extend(feed_items)

        return items

    async def _fetch_feed(
        self,
        source: RSSSourceConfig,
        since: datetime
    ) -> List[ContentItem]:
        """Fetch items from a single RSS feed.

        Args:
            source: RSS feed configuration
            since: Only fetch items after this time

        Returns:
            List[ContentItem]: Feed content items
        """
        items = []

        try:
            # Expand environment variables in URL (e.g. ${LWN_TOKEN})
            feed_url = re.sub(
                r'\$\{(\w+)\}',
                lambda m: os.environ.get(m.group(1), m.group(0)).strip(),
                str(source.url),
            )

            # Fetch feed content
            response = await self.client.get(feed_url, follow_redirects=True)
            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.text)

            for entry in feed.entries:
                # Parse published date
                published_at = self._parse_date(entry)
                if not published_at or published_at < since:
                    continue

                # Generate unique ID from feed URL and entry ID
                feed_id = str(source.url).split("//")[1].replace("/", "_")
                entry_id = entry.get("id", entry.get("link", ""))
                unique_id = f"{feed_id}:{hash(entry_id)}"

                # Extract content
                content = self._extract_content(entry)

                item = ContentItem(
                    id=self._generate_id("rss", feed_id, str(hash(entry_id))),
                    source_type=SourceType.RSS,
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", str(source.url)),
                    content=content,
                    author=entry.get("author", source.name),
                    published_at=published_at,
                    metadata={
                        "feed_name": source.name,
                        "category": source.category,
                        "tags": [tag.term for tag in entry.get("tags", [])],
                    }
                )
                # Apply editorial quality filter to avoid noisy breaking/live posts
                try:
                    if self._is_low_quality(item):
                        continue
                except Exception:
                    # On any error in heuristics, keep the item rather than lose content
                    pass

                items.append(item)

        except httpx.HTTPError as e:
            logger.warning("Error fetching RSS feed %s: %s", source.name, e)
        except Exception as e:
            logger.warning("Error parsing RSS feed %s: %s", source.name, e)

        return items

    def _parse_date(self, entry: dict) -> datetime:
        """Parse publication date from feed entry.

        Args:
            entry: Feed entry data

        Returns:
            datetime: Parsed publication date or None
        """
        # Try different date fields
        for field in ["published", "updated", "created"]:
            if field in entry:
                try:
                    # Try parsing structured time first
                    if f"{field}_parsed" in entry and entry[f"{field}_parsed"]:
                        return datetime.fromtimestamp(
                            calendar.timegm(entry[f"{field}_parsed"]),
                            tz=timezone.utc
                        )
                    # Fallback to string parsing
                    date_str = entry[field]
                    return parsedate_to_datetime(date_str)
                except Exception:
                    continue

        return None

    def _extract_content(self, entry: dict) -> str:
        """Extract text content from feed entry.

        Args:
            entry: Feed entry data

        Returns:
            str: Extracted text content
        """
        # Try different content fields
        if "summary" in entry:
            return entry.summary
        elif "description" in entry:
            return entry.description
        elif "content" in entry and entry.content:
            # content is usually a list
            return entry.content[0].get("value", "")

        return ""

    def _is_low_quality(self, item: ContentItem) -> bool:
        """Filter generic or repetitive RSS noise based on title/content heuristics.

        Returns True if the item should be skipped.
        """
        bad_keywords = [
            "breaking news",
            "live updates",
            "as it happened",
            "watch live",
            "photo gallery",
            "top stories",
            "liveblog",
            "live blog",
            "updates",
        ]

        title = (item.title or "").lower()
        content = (item.content or "").lower()

        # Title-based heuristics
        if any(k in title for k in bad_keywords):
            return True

        # Short titles that look like link-dump / listicles
        if len(title.split()) <= 3 and len(title) < 40:
            # allow short but meaningful titles that contain ':' or '?' (questions/labels)
            if ":" not in title and "?" not in title:
                return True

        # Very short or empty content
        if not content or len(content.strip()) < 80:
            # if the feed entry has no substantial content and the title is generic, skip
            if any(k in title for k in ["photo", "gallery", "video", "watch"]):
                return True

        return False
