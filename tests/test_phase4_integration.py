"""Tests for profile manager and feedback learning system."""

import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager
from src.ai.feedback_analyzer import FeedbackAnalyzer
from src.ai.cache_manager import CacheManager
from src.models import Profile, FeedbackSignal, SourceType


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def storage(temp_data_dir):
    """Create a StorageManager instance with temporary storage."""
    return StorageManager(data_dir=temp_data_dir)


@pytest.fixture
def profile_manager(storage):
    """Create a ProfileManager instance."""
    return ProfileManager(storage)


class TestProfileManager:
    """Tests for profile management functionality."""

    def test_create_profile(self, profile_manager, storage):
        """Test creating a new profile."""
        profile = profile_manager.create_profile(
            "test_profile",
            description="Test profile for unit tests"
        )
        
        assert profile.name == "test_profile"
        assert profile.description == "Test profile for unit tests"
        assert profile.ai_score_threshold == 6.0  # Default
        
        # Verify it's stored
        retrieved = storage.get_profile("test_profile")
        assert retrieved is not None
        assert retrieved.name == "test_profile"

    def test_create_profile_with_threshold(self, profile_manager):
        """Test creating profile with custom threshold."""
        profile = profile_manager.create_profile(
            "strict_profile",
            description="Strict scoring",
            ai_score_threshold=8.0
        )
        
        assert profile.ai_score_threshold == 8.0

    def test_clone_profile(self, profile_manager, storage):
        """Test cloning a profile."""
        # Create base profile
        profile_manager.create_profile("base", description="Base profile")
        
        # Clone it
        cloned = profile_manager.clone_profile("base", "cloned", description="Cloned version")
        
        assert cloned.name == "cloned"
        assert cloned.description == "Cloned version"
        
        # Verify both exist
        assert storage.get_profile("base") is not None
        assert storage.get_profile("cloned") is not None

    def test_edit_profile(self, profile_manager, storage):
        """Test editing a profile."""
        # Create profile
        profile_manager.create_profile("editable", ai_score_threshold=6.0)
        
        # Edit it
        edited = profile_manager.edit_profile("editable", ai_score_threshold=7.5)
        
        assert edited.ai_score_threshold == 7.5
        
        # Verify change persisted
        retrieved = storage.get_profile("editable")
        assert retrieved.ai_score_threshold == 7.5

    def test_delete_profile(self, profile_manager, storage):
        """Test deleting a profile."""
        # Create and delete
        profile_manager.create_profile("deletable")
        profile_manager.delete_profile("deletable")
        
        # Verify it's gone
        assert storage.get_profile("deletable") is None

    def test_set_source_prompt(self, profile_manager, storage):
        """Test setting per-source custom prompt."""
        profile_manager.create_profile("custom_prompts")
        
        custom_prompt = "Score highly for technical innovation in HN posts"
        updated = profile_manager.set_source_prompt(
            "custom_prompts",
            SourceType.HACKERNEWS,
            custom_prompt
        )
        
        assert SourceType.HACKERNEWS in updated.per_source_prompts
        assert updated.per_source_prompts[SourceType.HACKERNEWS] == custom_prompt

    def test_remove_source_prompt(self, profile_manager):
        """Test removing per-source custom prompt."""
        profile_manager.create_profile("custom_prompts")
        
        # Set custom prompt
        profile_manager.set_source_prompt(
            "custom_prompts",
            SourceType.REDDIT,
            "Custom Reddit prompt"
        )
        
        # Remove it
        updated = profile_manager.remove_source_prompt(
            "custom_prompts",
            SourceType.REDDIT
        )
        
        assert SourceType.REDDIT not in updated.per_source_prompts

    def test_list_profiles(self, profile_manager):
        """Test listing all profiles."""
        profile_manager.create_profile("profile1")
        profile_manager.create_profile("profile2")
        profile_manager.create_profile("profile3")
        
        profiles = profile_manager.list_profiles()
        
        assert len(profiles) >= 3
        names = [p.name for p in profiles]
        assert "profile1" in names
        assert "profile2" in names
        assert "profile3" in names


class TestFeedbackAnalyzer:
    """Tests for feedback analysis and learning."""

    def test_get_feedback_summary_empty(self, storage):
        """Test feedback summary with no feedback."""
        analyzer = FeedbackAnalyzer(storage)
        
        # Create a profile first
        profile_manager = ProfileManager(storage)
        profile_manager.create_profile("test_profile")
        
        summary = analyzer.get_feedback_summary("test_profile")
        
        assert summary["total_feedback"] == 0
        assert summary["positive_feedback"] == 0
        assert summary["negative_feedback"] == 0
        assert summary["favorites"] == 0

    def test_save_and_retrieve_feedback(self, storage):
        """Test saving and retrieving feedback."""
        # Create profile
        profile_manager = ProfileManager(storage)
        profile_manager.create_profile("feedback_test")
        
        # Save feedback
        signal = FeedbackSignal(
            item_id="test:123",
            profile_name="feedback_test",
            user_rating=1,  # 👍
            is_favorite=False,
            notes="This was useful",
            timestamp=datetime.now(timezone.utc)
        )
        storage.save_feedback(signal)
        
        # Retrieve and verify
        analyzer = FeedbackAnalyzer(storage)
        summary = analyzer.get_feedback_summary("feedback_test")
        
        assert summary["total_feedback"] == 1
        assert summary["positive_feedback"] == 1

    def test_feedback_accuracy_calculation(self, storage):
        """Test accuracy rate calculation."""
        profile_manager = ProfileManager(storage)
        profile_manager.create_profile("accuracy_test")
        
        # Save multiple feedback signals
        for i in range(10):
            signal = FeedbackSignal(
                item_id=f"item:{i}",
                profile_name="accuracy_test",
                user_rating=1 if i < 8 else -1,
                is_favorite=i % 3 == 0,
                timestamp=datetime.now(timezone.utc)
            )
            storage.save_feedback(signal)
        
        analyzer = FeedbackAnalyzer(storage)
        summary = analyzer.get_feedback_summary("accuracy_test")
        
        assert summary["total_feedback"] == 10
        assert summary["positive_feedback"] == 8
        assert summary["negative_feedback"] == 2
        assert summary["favorites"] == 4

    def test_improvement_roadmap(self, storage):
        """Test improvement roadmap generation."""
        profile_manager = ProfileManager(storage)
        profile_manager.create_profile("roadmap_test")
        
        # Create feedback with some misscored items
        signals = [
            FeedbackSignal(
                item_id="low:1",
                profile_name="roadmap_test",
                user_rating=1,  # Liked but underscored
                timestamp=datetime.now(timezone.utc)
            ),
            FeedbackSignal(
                item_id="low:2",
                profile_name="roadmap_test",
                user_rating=1,
                timestamp=datetime.now(timezone.utc)
            ),
        ]
        
        for signal in signals:
            storage.save_feedback(signal)
        
        analyzer = FeedbackAnalyzer(storage)
        roadmap = analyzer.get_improvement_roadmap("roadmap_test")
        
        assert isinstance(roadmap, list)
        # Should have recommendations based on patterns


class TestCacheManager:
    """Tests for enrichment caching."""

    def test_save_and_retrieve_cache(self, storage):
        """Test saving and retrieving cached enrichment."""
        cache_manager = CacheManager(storage)
        
        test_url = "https://example.com/article"
        background = "This is background knowledge"
        related = ["Related story 1", "Related story 2"]
        
        # Save
        cache_manager.save_enrichment(
            test_url,
            background_knowledge=background,
            related_stories=related,
            ttl_days=30
        )
        
        # Retrieve
        cached = cache_manager.get_cached_enrichment(test_url)
        
        assert cached is not None
        assert cached["background_knowledge"] == background
        assert cached["related_stories"] == related

    def test_cache_expiry(self, storage):
        """Test that expired cache entries are not returned."""
        cache_manager = CacheManager(storage)
        
        test_url = "https://example.com/expired"
        
        # Save with 0 days TTL (expired immediately)
        cache_manager.save_enrichment(
            test_url,
            background_knowledge="Old data",
            related_stories=[],
            ttl_days=0  # Expired
        )
        
        # Retrieve should return None for expired entry
        cached = cache_manager.get_cached_enrichment(test_url)
        
        assert cached is None

    def test_invalidate_url(self, storage):
        """Test invalidating a cache entry."""
        cache_manager = CacheManager(storage)
        
        test_url = "https://example.com/invalid"
        
        # Save
        cache_manager.save_enrichment(
            test_url,
            background_knowledge="Data",
            related_stories=[]
        )
        
        # Invalidate
        cache_manager.invalidate_url(test_url)
        
        # Should not be retrievable
        cached = cache_manager.get_cached_enrichment(test_url)
        assert cached is None

    def test_clear_expired_cache(self, storage):
        """Test clearing expired cache entries."""
        cache_manager = CacheManager(storage)
        
        # Save valid and expired entries
        cache_manager.save_enrichment(
            "https://valid.com",
            background_knowledge="Valid",
            related_stories=[],
            ttl_days=30
        )
        
        cache_manager.save_enrichment(
            "https://expired.com",
            background_knowledge="Expired",
            related_stories=[],
            ttl_days=0
        )
        
        # Clear expired
        count = cache_manager.clear_expired_cache()
        
        assert count >= 1  # At least the expired one
        
        # Valid should still be there
        assert cache_manager.get_cached_enrichment("https://valid.com") is not None


class TestProfileIntegration:
    """Integration tests for profile system."""

    def test_complete_profile_workflow(self, storage):
        """Test complete workflow: create, customize, use, get feedback."""
        profile_manager = ProfileManager(storage)
        
        # Create a profile
        profile_manager.create_profile(
            "ml_research",
            description="Focus on ML papers",
            ai_score_threshold=7.0
        )
        
        # Customize it
        profile_manager.set_source_prompt(
            "ml_research",
            SourceType.REDDIT,
            "Score ML research papers highly"
        )
        
        # Activate it
        storage.set_active_profile("ml_research")
        active = storage.get_active_profile()
        assert active.name == "ml_research"
        
        # Add feedback
        signal = FeedbackSignal(
            item_id="ml_paper:1",
            profile_name="ml_research",
            user_rating=1,
            timestamp=datetime.now(timezone.utc)
        )
        storage.save_feedback(signal)
        
        # Check feedback stats
        analyzer = FeedbackAnalyzer(storage)
        summary = analyzer.get_feedback_summary("ml_research")
        assert summary["total_feedback"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
