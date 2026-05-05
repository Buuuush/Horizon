"""Manages caching of enrichment results to avoid re-fetching."""

import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from ..models import EnrichmentCache
from ..storage.manager import StorageManager


class CacheManager:
    """Manages enrichment cache to avoid re-fetching background knowledge."""

    def __init__(self, storage: StorageManager):
        self.storage = storage

    @staticmethod
    def _hash_url(url: str) -> str:
        """Create SHA-256 hash of URL for efficient lookup."""
        return hashlib.sha256(url.encode()).hexdigest()

    def get_cached_enrichment(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get cached enrichment for a URL if it still exists and is fresh.
        
        Args:
            url: URL to look up
            
        Returns:
            Enrichment data dict if cache hit and fresh, None otherwise
        """
        cached = self.storage.get_enrichment_cache(url)
        if cached is None:
            return None

        # Normalize related_stories back to simple list when possible
        normalized = []
        for rs in cached.related_stories:
            if isinstance(rs, dict) and list(rs.keys()) == ["title"]:
                normalized.append(rs["title"])
            else:
                normalized.append(rs)

        return {
            "background_knowledge": cached.background_knowledge,
            "related_stories": normalized,
            "cached_at": cached.cached_at.isoformat(),
            "ttl_days": cached.ttl_days,
        }

    def save_enrichment(
        self,
        url: str,
        background_knowledge: str,
        related_stories: list = None,
        ttl_days: int = 30,
    ) -> None:
        """
        Save enrichment result to cache.
        
        Args:
            url: URL that was enriched
            background_knowledge: Enrichment result text
            related_stories: Optional list of related story dicts
            ttl_days: How many days to keep this cache entry
        """
        # Normalize related_stories: allow list of strings or dicts
        normalized_related = []
        for rs in (related_stories or []):
            if isinstance(rs, dict):
                normalized_related.append(rs)
            else:
                # If a simple string was provided, wrap it into a dict
                normalized_related.append({"title": str(rs)})

        cache = EnrichmentCache(
            url_hash=self._hash_url(url),
            url=url,
            background_knowledge=background_knowledge,
            related_stories=normalized_related,
            cached_at=datetime.utcnow(),
            ttl_days=ttl_days,
        )
        self.storage.save_enrichment_cache(cache)

    def invalidate_url(self, url: str) -> None:
        """Remove cache entry for a specific URL."""
        self.storage.delete_enrichment_cache(url)

    def clear_expired_cache(self) -> int:
        """Delete all expired cache entries. Returns count of deleted entries."""
        return self.storage.clear_expired_cache()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cache (would require DB query)."""
        # This is a placeholder - in a real implementation, we'd query the DB
        return {
            "status": "Cache system active",
            "note": "Use clear_expired_cache() to remove stale entries",
        }
