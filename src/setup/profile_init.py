"""Initialize default profile from existing config.json."""

from pathlib import Path
from datetime import datetime
from typing import List

from ..models import Profile, Config, SourceType
from ..storage.manager import StorageManager


def migrate_config_to_profiles(storage: StorageManager, config: Config) -> None:
    """
    Auto-migrate existing config.json to SQLite profiles on first run.
    
    Creates a "default" profile with settings from config.json.
    """
    # Check if we already have profiles
    existing_profiles = storage.get_all_profiles()
    if existing_profiles:
        return  # Already migrated

    # Determine which sources are enabled in config
    active_sources: List[SourceType] = []

    if config.sources.github and len(config.sources.github) > 0:
        if any(s.enabled for s in config.sources.github):
            active_sources.append(SourceType.GITHUB)

    if config.sources.hackernews.enabled:
        active_sources.append(SourceType.HACKERNEWS)

    if config.sources.rss and any(r.enabled for r in config.sources.rss):
        active_sources.append(SourceType.RSS)

    if config.sources.reddit.enabled:
        active_sources.append(SourceType.REDDIT)

    if config.sources.telegram.enabled:
        active_sources.append(SourceType.TELEGRAM)

    if config.sources.twitter and config.sources.twitter.enabled:
        active_sources.append(SourceType.TWITTER)

    # Create default profile from config settings
    default_profile = Profile(
        name="default",
        description="Auto-migrated from config.json",
        ai_score_threshold=config.filtering.ai_score_threshold,
        per_source_prompts={},  # No per-source overrides initially
        active_sources=active_sources,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        is_active=True,
    )

    storage.save_profile(default_profile)
    print(f"✓ Migrated default profile from config.json")


def init_profiles(data_dir: str = "data") -> StorageManager:
    """
    Initialize profiles on first run.
    
    - Creates SQLite database if it doesn't exist
    - Auto-migrates config.json to "default" profile if needed
    - Returns initialized StorageManager
    """
    storage = StorageManager(data_dir)

    try:
        config = storage.load_config()
        migrate_config_to_profiles(storage, config)
    except FileNotFoundError as e:
        print(f"⚠ Warning: {e}")
        print("Please create config.json before running Horizon")
        raise

    # Verify at least one profile exists
    profiles = storage.get_all_profiles()
    if not profiles:
        raise RuntimeError("No profiles found after initialization")

    # Make sure one profile is active
    active = storage.get_active_profile()
    if not active:
        # Set first profile as active
        first_profile = profiles[0]
        first_profile.is_active = True
        storage.save_profile(first_profile)
        print(f"✓ Set '{first_profile.name}' as active profile")

    return storage
