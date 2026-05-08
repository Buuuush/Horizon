import tempfile

from src.setup.profile_manager import ProfileManager
from src.storage.manager import StorageManager


def test_profile_diversity_limits_persist_and_clone():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = StorageManager(data_dir=tmpdir)
        manager = ProfileManager(storage)

        created = manager.create_profile(
            "balanced",
            description="Balanced briefing",
            ai_score_threshold=7.5,
            max_items_per_source_type=3,
            max_items_per_sub_source=1,
        )

        assert created.max_items_per_source_type == 3
        assert created.max_items_per_sub_source == 1

        edited = manager.edit_profile(
            "balanced",
            max_items_per_source_type=4,
            max_items_per_sub_source=2,
        )

        assert edited.max_items_per_source_type == 4
        assert edited.max_items_per_sub_source == 2

        cloned = manager.clone_profile("balanced", "balanced_clone")

        assert cloned.max_items_per_source_type == 4
        assert cloned.max_items_per_sub_source == 2
