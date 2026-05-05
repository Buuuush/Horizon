"""Profile management utilities for creating, editing, and deleting profiles."""

from typing import List, Optional
from datetime import datetime

from ..models import Profile, SourceType
from ..storage.manager import StorageManager


class ProfileManager:
    """Manages profile CRUD operations and profile-related queries."""

    def __init__(self, storage: StorageManager):
        self.storage = storage

    def create_profile(
        self,
        name: str,
        description: Optional[str] = None,
        base_profile: Optional[str] = None,
        ai_score_threshold: Optional[float] = None,
    ) -> Profile:
        """
        Create a new profile, optionally based on an existing one.
        
        Args:
            name: Unique profile name
            description: Optional description
            base_profile: If provided, clone this profile's settings
            ai_score_threshold: Override threshold for new profile
            
        Returns:
            The created Profile
        """
        # Check if profile already exists
        if self.storage.get_profile(name):
            raise ValueError(f"Profile '{name}' already exists")

        # Create new profile
        if base_profile:
            base = self.storage.get_profile(base_profile)
            if not base:
                raise ValueError(f"Base profile '{base_profile}' not found")

            new_profile = Profile(
                name=name,
                description=description or f"Clone of {base_profile}",
                ai_score_threshold=ai_score_threshold or base.ai_score_threshold,
                per_source_prompts=base.per_source_prompts.copy(),
                active_sources=base.active_sources.copy(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=False,
            )
        else:
            new_profile = Profile(
                name=name,
                description=description,
                ai_score_threshold=ai_score_threshold or 6.0,
                per_source_prompts={},
                active_sources=[],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=False,
            )

        self.storage.save_profile(new_profile)
        return new_profile

    def clone_profile(self, from_name: str, to_name: str, description: Optional[str] = None) -> Profile:
        """Clone an existing profile with a new name."""
        return self.create_profile(
            name=to_name,
            description=description,
            base_profile=from_name,
        )

    def edit_profile(
        self,
        name: str,
        description: Optional[str] = None,
        ai_score_threshold: Optional[float] = None,
        per_source_prompts: Optional[dict] = None,
        active_sources: Optional[List[SourceType]] = None,
    ) -> Profile:
        """Edit an existing profile's settings."""
        profile = self.storage.get_profile(name)
        if not profile:
            raise ValueError(f"Profile '{name}' not found")

        # Update fields
        if description is not None:
            profile.description = description
        if ai_score_threshold is not None:
            profile.ai_score_threshold = ai_score_threshold
        if per_source_prompts is not None:
            profile.per_source_prompts = per_source_prompts
        if active_sources is not None:
            profile.active_sources = active_sources

        profile.updated_at = datetime.utcnow()
        self.storage.save_profile(profile)
        return profile

    def delete_profile(self, name: str) -> None:
        """Delete a profile by name."""
        profile = self.storage.get_profile(name)
        if not profile:
            raise ValueError(f"Profile '{name}' not found")

        # Don't delete if it's the active profile
        if profile.is_active:
            # Switch to another profile first
            other_profiles = [p for p in self.storage.get_all_profiles() if p.name != name]
            if other_profiles:
                self.storage.set_active_profile(other_profiles[0].name)
            else:
                raise ValueError("Cannot delete the only profile. Create another profile first.")

        self.storage.delete_profile(name)

    def set_source_prompt(self, profile_name: str, source_type: SourceType, prompt: str) -> Profile:
        """Set a custom scoring prompt for a specific source in a profile."""
        profile = self.storage.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")

        profile.per_source_prompts[source_type.value] = prompt
        profile.updated_at = datetime.utcnow()
        self.storage.save_profile(profile)
        return profile

    def remove_source_prompt(self, profile_name: str, source_type: SourceType) -> Profile:
        """Remove custom scoring prompt for a source, reverting to default."""
        profile = self.storage.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")

        profile.per_source_prompts.pop(source_type.value, None)
        profile.updated_at = datetime.utcnow()
        self.storage.save_profile(profile)
        return profile

    def set_active_sources(self, profile_name: str, sources: List[SourceType]) -> Profile:
        """Set which sources are active for a profile."""
        profile = self.storage.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")

        profile.active_sources = sources
        profile.updated_at = datetime.utcnow()
        self.storage.save_profile(profile)
        return profile

    def list_profiles(self) -> List[Profile]:
        """Get list of all profiles with status."""
        profiles = self.storage.get_all_profiles()
        return sorted(profiles, key=lambda p: (not p.is_active, p.name))  # Active first, then alphabetical

    def print_profile_summary(self, profile: Profile) -> None:
        """Print a formatted summary of a profile."""
        active_marker = "● ACTIVE" if profile.is_active else ""
        print(f"\nProfile: {profile.name} {active_marker}")
        print(f"  Description: {profile.description or '(none)'}")
        print(f"  Score Threshold: {profile.ai_score_threshold}")
        print(f"  Active Sources: {', '.join(s.value for s in profile.active_sources) if profile.active_sources else '(all enabled)'}")
        print(f"  Custom Prompts: {len(profile.per_source_prompts)} source(s) customized")
        print(f"  Created: {profile.created_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Updated: {profile.updated_at.strftime('%Y-%m-%d %H:%M')}")

    def print_all_profiles(self) -> None:
        """Print all profiles in a summary table."""
        profiles = self.list_profiles()
        if not profiles:
            print("No profiles found.")
            return

        print("\nAll Profiles:")
        print("-" * 80)
        for profile in profiles:
            self.print_profile_summary(profile)
        print("-" * 80)

    def interactive_menu(self) -> None:
        """Launch interactive profile management menu."""
        while True:
            print("\n" + "=" * 60)
            print("  Profile Manager")
            print("=" * 60)
            
            profiles = self.list_profiles()
            if profiles:
                print("\nCurrent Profiles:")
                for i, p in enumerate(profiles, 1):
                    marker = " ✓" if p.is_active else ""
                    print(f"  {i}. {p.name}{marker}")
            
            print("\nOptions:")
            print("  1. Create new profile")
            print("  2. Edit profile")
            print("  3. Clone profile")
            print("  4. Delete profile")
            print("  5. Set active profile")
            print("  6. View all profiles")
            print("  7. Exit")
            
            choice = input("\nSelect option (1-7): ").strip()
            
            if choice == "1":
                name = input("Profile name: ").strip()
                desc = input("Description (optional): ").strip()
                self.create_profile(name, description=desc or None)
                print(f"✓ Profile '{name}' created")
            
            elif choice == "2":
                name = input("Profile name to edit: ").strip()
                profile = self.storage.get_profile(name)
                if not profile:
                    print(f"✗ Profile '{name}' not found")
                    continue
                
                threshold = input(f"New score threshold (current: {profile.ai_score_threshold}): ").strip()
                if threshold:
                    try:
                        self.edit_profile(name, ai_score_threshold=float(threshold))
                        print("✓ Profile updated")
                    except ValueError:
                        print("✗ Invalid threshold value")
            
            elif choice == "3":
                from_name = input("Source profile name: ").strip()
                to_name = input("New profile name: ").strip()
                try:
                    self.clone_profile(from_name, to_name)
                    print(f"✓ Profile '{to_name}' cloned from '{from_name}'")
                except Exception as e:
                    print(f"✗ Error: {e}")
            
            elif choice == "4":
                name = input("Profile name to delete: ").strip()
                try:
                    self.delete_profile(name)
                    print(f"✓ Profile '{name}' deleted")
                except Exception as e:
                    print(f"✗ Error: {e}")
            
            elif choice == "5":
                name = input("Profile name to activate: ").strip()
                profile = self.storage.get_profile(name)
                if not profile:
                    print(f"✗ Profile '{name}' not found")
                else:
                    self.storage.set_active_profile(name)
                    print(f"✓ Profile '{name}' is now active")
            
            elif choice == "6":
                self.print_all_profiles()
            
            elif choice == "7":
                print("Exiting profile manager...")
                break
            
            else:
                print("✗ Invalid option")
