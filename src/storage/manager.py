"""Storage manager for configuration and state persistence."""

import json
from datetime import datetime
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..models import Config, Profile, FeedbackSignal, EnrichmentCache
from .archive_db import get_session, ArchivedArticle
from .sqlite_manager import SQLiteManager


class StorageManager:
    """Manages file-based storage for configuration and state."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.config_path = self.data_dir / "config.json"
        self.summaries_dir = self.data_dir / "summaries"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite backend for profiles, feedback, and caching
        self.db = SQLiteManager(data_dir)

    def load_config(self) -> Config:
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create it based on the template in README.md"
            )

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # If a registry of RSS sources exists in data/rss_sources.json, merge
        # its entries into the loaded config so all profiles can use them.
        rss_registry_path = self.data_dir / "rss_sources.json"
        try:
            if rss_registry_path.exists():
                with open(rss_registry_path, "r", encoding="utf-8") as rf:
                    rss_data = json.load(rf)

                # Flatten nested 'sources' groups to a list of feeds
                registry_feeds = []
                for group in rss_data.get("sources", {}).values():
                    if isinstance(group, dict):
                        for _key, feed in group.items():
                            if not isinstance(feed, dict):
                                continue
                            feed_entry = {
                                "name": feed.get("name") or _key,
                                "url": feed.get("url"),
                                "enabled": feed.get("enabled", True),
                                "category": feed.get("category"),
                            }
                            if feed_entry["url"]:
                                registry_feeds.append(feed_entry)

                # Ensure path exists in config data
                data.setdefault("sources", {})
                data_sources = data["sources"]
                data_sources.setdefault("rss", [])

                # Build set of existing URLs to avoid duplicates
                existing_urls = set()
                for existing in data_sources.get("rss", []):
                    try:
                        existing_urls.add(str(existing.get("url")))
                    except Exception:
                        continue

                # Append registry feeds that are not already present
                for feed in registry_feeds:
                    if str(feed["url"]) not in existing_urls:
                        data_sources["rss"].append(feed)
                        existing_urls.add(str(feed["url"]))
        except Exception:
            # If registry parsing fails, ignore and proceed with loaded config
            pass

        return Config.model_validate(data)

    def save_config(self, config: Config, backup: bool = True) -> Path:
        """Save configuration to config.json, optionally backing up the existing file.

        Args:
            config: The Config object to save.
            backup: If True and config.json exists, copy it to config.json.bak first.

        Returns:
            Path to the saved config file.
        """
        if backup and self.config_path.exists():
            shutil.copy2(self.config_path, self.config_path.with_suffix(".json.bak"))

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config.model_dump(mode="json", exclude_none=True), f, indent=2, ensure_ascii=False)
            f.write("\n")

        return self.config_path

    def save_daily_summary(
        self,
        date: str,
        content: str,
        language: str = "en",
        extension: str = "html",
    ) -> Path:
        filename = f"horizon-{date}-{language}.{extension}"
        filepath = self.summaries_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath

    def load_subscribers(self) -> list:
        """Loads the list of email subscribers."""
        subscribers_path = self.data_dir / "subscribers.json"
        if not subscribers_path.exists():
            return []

        try:
            with open(subscribers_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def add_subscriber(self, email_addr: str):
        """Adds a new subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr not in subscribers:
            subscribers.append(email_addr)
            self._save_subscribers(subscribers)

    def remove_subscriber(self, email_addr: str):
        """Removes a subscriber email."""
        subscribers = self.load_subscribers()
        if email_addr in subscribers:
            subscribers.remove(email_addr)
            self._save_subscribers(subscribers)

    def _save_subscribers(self, subscribers: list):
        """Helper to save subscribers list."""
        subscribers_path = self.data_dir / "subscribers.json"
        with open(subscribers_path, "w", encoding="utf-8") as f:
            json.dump(subscribers, f, indent=2)

    # ===== Profile Management (SQLite backend) =====

    def get_all_profiles(self) -> List[Profile]:
        """Get all profiles."""
        return self.db.get_all_profiles()

    def get_profile(self, name: str) -> Optional[Profile]:
        """Get a specific profile by name."""
        return self.db.get_profile(name)

    def get_active_profile(self) -> Optional[Profile]:
        """Get the currently active profile."""
        return self.db.get_active_profile()

    def save_profile(self, profile: Profile) -> None:
        """Save or update a profile."""
        self.db.save_profile(profile)

    def set_active_profile(self, name: str) -> None:
        """Set the active profile by name."""
        self.db.set_active_profile(name)

    def delete_profile(self, name: str) -> None:
        """Delete a profile by name."""
        self.db.delete_profile(name)

    # ===== Feedback Management (SQLite backend) =====

    def save_feedback(self, feedback: FeedbackSignal) -> None:
        """Save user feedback on an article."""
        self.db.save_feedback(feedback)

    def get_feedback_for_item(self, item_id: str, profile_name: str) -> Optional[FeedbackSignal]:
        """Get feedback for a specific item in a profile."""
        return self.db.get_feedback_for_item(item_id, profile_name)

    def get_feedback_stats(self, profile_name: str) -> Dict[str, Any]:
        """Get feedback statistics for a profile."""
        return self.db.get_feedback_stats(profile_name)

    def get_misscored_items(self, profile_name: str) -> List[Dict[str, Any]]:
        """Get items that were misscored (feedback contradicts AI score)."""
        return self.db.get_misscored_items(profile_name)

    # ===== Enrichment Cache Management (SQLite backend) =====

    # ----- Archive Management -----
    # Uses the SQLite archive DB defined in src/storage/archive_db.py
    # Provides methods to insert articles and run search queries.


    def get_enrichment_cache(self, url: str) -> Optional[EnrichmentCache]:
        """Get cached enrichment for a URL, if still valid."""
        return self.db.get_enrichment_cache(url)

    def save_enrichment_cache(self, cache: EnrichmentCache) -> None:
        """Save enrichment cache entry."""
        self.db.save_enrichment_cache(cache)

    # ----- Archive Management -----
    def archive_item(self, item, profile_name: str) -> None:
        """Archive a ContentItem into the SQLite archive.

        ``item`` is expected to be a ``ContentItem`` model instance.
        """
        session = get_session()
        article = ArchivedArticle(
            id=item.id,
            title=item.title,
            url=str(item.url),
            source_type=item.source_type.value,
            source_name=getattr(item, "source_name", ""),
            ai_score=item.ai_score,
            tags=item.ai_tags,
            summary=item.ai_summary[:500] if getattr(item, "ai_summary", None) else "",
            whats_new=getattr(item, "metadata", {}).get("whats_new_en", "")[:500],
            why_it_matters=getattr(item, "metadata", {}).get("why_it_matters_en", "")[:500],
            background=getattr(item, "metadata", {}).get("background_en", "")[:500],
            published_at=item.published_at,
            fetched_at=item.fetched_at,
            run_date=datetime.utcnow().strftime("%Y-%m-%d"),
            profile_name=profile_name,
        )
        session.add(article)
        session.commit()
        session.close()

    def search_articles(self, *, q: str = "", tag: str = "", source: str = "", score_min: float = 0, score_max: float = 10, date_start: str = "", date_end: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        """Search archived articles.

        Returns a list of dicts with keys: id, title, url, score, source, tags, published.
        """
        session = get_session()
        query = session.query(ArchivedArticle)
        if q:
            query = query.filter(
                (ArchivedArticle.title.ilike(f"%{q}%")) |
                (ArchivedArticle.summary.ilike(f"%{q}%"))
            )
        if tag:
            query = query.filter(ArchivedArticle.tags.contains([tag]))
        if source:
            query = query.filter(ArchivedArticle.source_type == source)
        query = query.filter(ArchivedArticle.ai_score >= score_min, ArchivedArticle.ai_score <= score_max)
        if date_start:
            query = query.filter(ArchivedArticle.published_at >= datetime.fromisoformat(date_start))
        if date_end:
            query = query.filter(ArchivedArticle.published_at <= datetime.fromisoformat(date_end))
        results = query.order_by(ArchivedArticle.ai_score.desc()).limit(limit).all()
        session.close()
        return [
            {
                "id": r.id,
                "title": r.title,
                "url": r.url,
                "score": r.ai_score,
                "source": r.source_name,
                "tags": r.tags,
                "published": r.published_at.isoformat() if r.published_at else None,
            }
            for r in results
        ]
        """Save enrichment cache for a URL."""
        self.db.save_enrichment_cache(cache)

    def delete_enrichment_cache(self, url: str) -> None:
        """Delete enrichment cache for a URL."""
        self.db.delete_enrichment_cache(url)

    def clear_expired_cache(self) -> int:
        """Delete all expired cache entries. Returns count deleted."""
        return self.db.clear_expired_cache()

    # ===== Profile Run Tracking (SQLite backend) =====

    def save_profile_run(
        self,
        run_date,  # datetime
        profile_name: str,
        items_processed: int,
        items_scored: int,
        avg_score: float,
        language: str,
        summary_path: str,
    ) -> None:
        """Record metadata about a profile run."""
        self.db.save_profile_run(run_date, profile_name, items_processed, items_scored, avg_score, language, summary_path)

    def get_profile_runs(self, profile_name: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Get recent runs for a profile."""
        return self.db.get_profile_runs(profile_name, limit)
