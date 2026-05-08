"""SQLite-based storage for profiles, feedback, and caching."""

import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
from contextlib import contextmanager

from ..models import Profile, FeedbackSignal, EnrichmentCache, SourceType


class SQLiteManager:
    """Manages SQLite-based persistent storage for profiles, feedback, and enrichment cache."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "horizon.db"
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema if it doesn't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    ai_score_threshold REAL DEFAULT 6.0,
                    max_items_per_source_type INTEGER,
                    max_items_per_sub_source INTEGER,
                    per_source_prompts TEXT DEFAULT '{}',
                    active_sources TEXT DEFAULT '[]',
                    created_at TEXT,
                    updated_at TEXT,
                    is_active BOOLEAN DEFAULT 0
                )
            """)

            cursor.execute("PRAGMA table_info(profiles)")
            existing_columns = {row["name"] for row in cursor.fetchall()}
            for column_name, column_type in (
                ("max_items_per_source_type", "INTEGER"),
                ("max_items_per_sub_source", "INTEGER"),
            ):
                if column_name not in existing_columns:
                    cursor.execute(f"ALTER TABLE profiles ADD COLUMN {column_name} {column_type}")

            # Feedback signals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    user_rating INTEGER,
                    is_favorite BOOLEAN DEFAULT 0,
                    ai_score_at_feedback REAL,
                    notes TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (profile_name) REFERENCES profiles(name)
                )
            """)

            # Create index for fast feedback lookup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_item_profile
                ON feedback_signals(item_id, profile_name)
            """)

            # Enrichment cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS enrichment_cache (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    background_knowledge TEXT NOT NULL,
                    related_stories TEXT DEFAULT '[]',
                    cached_at TEXT,
                    ttl_days INTEGER DEFAULT 30
                )
            """)

            # Profile runs table (metadata about each summary generation)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profile_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    items_processed INTEGER DEFAULT 0,
                    items_scored INTEGER DEFAULT 0,
                    avg_score REAL DEFAULT 0.0,
                    language TEXT DEFAULT 'en',
                    summary_path TEXT,
                    FOREIGN KEY (profile_name) REFERENCES profiles(name)
                )
            """)

    # ===== Profile Management =====

    def get_all_profiles(self) -> List[Profile]:
        """Get all profiles from database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles")
            rows = cursor.fetchall()

        profiles = []
        for row in rows:
            profile = Profile(
                name=row["name"],
                description=row["description"],
                ai_score_threshold=row["ai_score_threshold"],
                max_items_per_source_type=row["max_items_per_source_type"],
                max_items_per_sub_source=row["max_items_per_sub_source"],
                per_source_prompts=json.loads(row["per_source_prompts"]),
                active_sources=[SourceType(s) for s in json.loads(row["active_sources"])],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                is_active=bool(row["is_active"]),
            )
            profiles.append(profile)

        return profiles

    def get_profile(self, name: str) -> Optional[Profile]:
        """Get a specific profile by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE name = ?", (name,))
            row = cursor.fetchone()

        if not row:
            return None

        return Profile(
            name=row["name"],
            description=row["description"],
            ai_score_threshold=row["ai_score_threshold"],
            max_items_per_source_type=row["max_items_per_source_type"],
            max_items_per_sub_source=row["max_items_per_sub_source"],
            per_source_prompts=json.loads(row["per_source_prompts"]),
            active_sources=[SourceType(s) for s in json.loads(row["active_sources"])],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            is_active=bool(row["is_active"]),
        )

    def get_active_profile(self) -> Optional[Profile]:
        """Get the currently active profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE is_active = 1")
            row = cursor.fetchone()

        if not row:
            return None

        return Profile(
            name=row["name"],
            description=row["description"],
            ai_score_threshold=row["ai_score_threshold"],
            max_items_per_source_type=row["max_items_per_source_type"],
            max_items_per_sub_source=row["max_items_per_sub_source"],
            per_source_prompts=json.loads(row["per_source_prompts"]),
            active_sources=[SourceType(s) for s in json.loads(row["active_sources"])],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            is_active=bool(row["is_active"]),
        )

    def save_profile(self, profile: Profile) -> None:
        """Save or update a profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO profiles
                (name, description, ai_score_threshold, max_items_per_source_type, max_items_per_sub_source, per_source_prompts, active_sources, created_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.name,
                    profile.description,
                    profile.ai_score_threshold,
                    profile.max_items_per_source_type,
                    profile.max_items_per_sub_source,
                    json.dumps(profile.per_source_prompts),
                    json.dumps([s.value for s in profile.active_sources]),
                    profile.created_at.isoformat(),
                    datetime.utcnow().isoformat(),
                    profile.is_active,
                ),
            )

    def set_active_profile(self, name: str) -> None:
        """Set the active profile by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Deactivate all profiles
            cursor.execute("UPDATE profiles SET is_active = 0")
            # Activate the specified profile
            cursor.execute("UPDATE profiles SET is_active = 1 WHERE name = ?", (name,))

    def delete_profile(self, name: str) -> None:
        """Delete a profile by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM profiles WHERE name = ?", (name,))

    # ===== Feedback Management =====

    def save_feedback(self, feedback: FeedbackSignal) -> None:
        """Save user feedback on an article."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO feedback_signals
                (item_id, profile_name, user_rating, is_favorite, ai_score_at_feedback, notes, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback.item_id,
                    feedback.profile_name,
                    feedback.user_rating,
                    feedback.is_favorite,
                    feedback.ai_score_at_feedback,
                    feedback.notes,
                    feedback.timestamp.isoformat(),
                ),
            )

    def get_feedback_for_item(self, item_id: str, profile_name: str) -> Optional[FeedbackSignal]:
        """Get feedback for a specific item in a profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM feedback_signals WHERE item_id = ? AND profile_name = ? ORDER BY timestamp DESC LIMIT 1",
                (item_id, profile_name),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return FeedbackSignal(
            item_id=row["item_id"],
            profile_name=row["profile_name"],
            user_rating=row["user_rating"],
            is_favorite=bool(row["is_favorite"]),
            ai_score_at_feedback=row["ai_score_at_feedback"],
            notes=row["notes"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    def get_feedback_stats(self, profile_name: str) -> Dict[str, Any]:
        """Get feedback statistics for a profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total feedback count
            cursor.execute(
                "SELECT COUNT(*) as count FROM feedback_signals WHERE profile_name = ?",
                (profile_name,),
            )
            total_count = cursor.fetchone()["count"]

            # Positive feedback
            cursor.execute(
                "SELECT COUNT(*) as count FROM feedback_signals WHERE profile_name = ? AND user_rating = 1",
                (profile_name,),
            )
            positive_count = cursor.fetchone()["count"]

            # Negative feedback
            cursor.execute(
                "SELECT COUNT(*) as count FROM feedback_signals WHERE profile_name = ? AND user_rating = -1",
                (profile_name,),
            )
            negative_count = cursor.fetchone()["count"]

            # Favorites
            cursor.execute(
                "SELECT COUNT(*) as count FROM feedback_signals WHERE profile_name = ? AND is_favorite = 1",
                (profile_name,),
            )
            favorite_count = cursor.fetchone()["count"]

            # Misscored items (score too low but rated positive, or score too high but rated negative)
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM feedback_signals
                WHERE profile_name = ?
                AND (
                    (user_rating = 1 AND ai_score_at_feedback < 6)
                    OR (user_rating = -1 AND ai_score_at_feedback >= 6)
                )
                """,
                (profile_name,),
            )
            misscored_count = cursor.fetchone()["count"]

        return {
            "total_feedback": total_count,
            "positive": positive_count,
            "negative": negative_count,
            "favorites": favorite_count,
            "misscored_items": misscored_count,
            "accuracy_rate": (1 - misscored_count / total_count) * 100 if total_count > 0 else 0,
        }

    def get_misscored_items(self, profile_name: str) -> List[Dict[str, Any]]:
        """Get items that were misscored (feedback contradicts AI score)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT item_id, user_rating, ai_score_at_feedback, notes, timestamp
                FROM feedback_signals
                WHERE profile_name = ?
                AND (
                    (user_rating = 1 AND ai_score_at_feedback < 6)
                    OR (user_rating = -1 AND ai_score_at_feedback >= 6)
                )
                ORDER BY timestamp DESC
                """,
                (profile_name,),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    # ===== Enrichment Cache Management =====

    @staticmethod
    def _hash_url(url: str) -> str:
        """Create SHA-256 hash of URL for cache lookup."""
        return hashlib.sha256(url.encode()).hexdigest()

    def get_enrichment_cache(self, url: str) -> Optional[EnrichmentCache]:
        """Get cached enrichment for a URL, if still valid."""
        url_hash = self._hash_url(url)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM enrichment_cache WHERE url_hash = ?", (url_hash,))
            row = cursor.fetchone()

        if not row:
            return None

        cached_at = datetime.fromisoformat(row["cached_at"])
        ttl_days = row["ttl_days"]

        # Check if cache is still valid
        if datetime.utcnow() - cached_at > timedelta(days=ttl_days):
            # Cache expired, delete it
            self.delete_enrichment_cache(url)
            return None

        return EnrichmentCache(
            url_hash=row["url_hash"],
            url=row["url"],
            background_knowledge=row["background_knowledge"],
            related_stories=json.loads(row["related_stories"]),
            cached_at=cached_at,
            ttl_days=ttl_days,
        )

    def save_enrichment_cache(self, cache: EnrichmentCache) -> None:
        """Save enrichment cache for a URL."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO enrichment_cache
                (url_hash, url, background_knowledge, related_stories, cached_at, ttl_days)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cache.url_hash,
                    cache.url,
                    cache.background_knowledge,
                    json.dumps(cache.related_stories),
                    cache.cached_at.isoformat(),
                    cache.ttl_days,
                ),
            )

    def delete_enrichment_cache(self, url: str) -> None:
        """Delete enrichment cache for a URL."""
        url_hash = self._hash_url(url)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM enrichment_cache WHERE url_hash = ?", (url_hash,))

    def clear_expired_cache(self) -> int:
        """Delete all expired cache entries. Returns count deleted."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url_hash, cached_at, ttl_days FROM enrichment_cache")
            rows = cursor.fetchall()

            expired_hashes = []
            for row in rows:
                cached_at = datetime.fromisoformat(row["cached_at"])
                ttl_days = row["ttl_days"]
                if datetime.utcnow() - cached_at > timedelta(days=ttl_days):
                    expired_hashes.append(row["url_hash"])

            if expired_hashes:
                placeholders = ",".join("?" * len(expired_hashes))
                cursor.execute(f"DELETE FROM enrichment_cache WHERE url_hash IN ({placeholders})", expired_hashes)

        return len(expired_hashes)

    # ===== Profile Run Tracking =====

    def save_profile_run(
        self,
        run_date: datetime,
        profile_name: str,
        items_processed: int,
        items_scored: int,
        avg_score: float,
        language: str,
        summary_path: str,
    ) -> None:
        """Record metadata about a profile run."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO profile_runs
                (run_date, profile_name, items_processed, items_scored, avg_score, language, summary_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_date.isoformat(),
                    profile_name,
                    items_processed,
                    items_scored,
                    avg_score,
                    language,
                    summary_path,
                ),
            )

    def get_profile_runs(self, profile_name: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Get recent runs for a profile."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM profile_runs
                WHERE profile_name = ?
                ORDER BY run_date DESC
                LIMIT ?
                """,
                (profile_name, limit),
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]
