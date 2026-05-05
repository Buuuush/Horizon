# Phase 4: Integration & Testing

## Overview

Phase 4 completes the Horizon system by integrating all previously developed features into the production pipeline, adding comprehensive testing, and updating deployment infrastructure.

## Completed Tasks

### 1. ✅ Orchestrator Profile Integration

**File**: `src/orchestrator.py`

**Changes**:
- Added `Profile` import and `CacheManager` import
- Updated `__init__` to accept optional `profile` parameter
- Initialize `CacheManager` for enrichment caching
- Use profile's `ai_score_threshold` instead of config default
- Pass profile to `ContentAnalyzer` for per-source prompt selection
- Display active profile info in console output

**Code Flow**:
```python
orchestrator = HorizonOrchestrator(config, storage, profile=active_profile)
# Inside run():
threshold = self.profile.ai_score_threshold if self.profile else config_threshold
analyzer = ContentAnalyzer(ai_client, profile=self.profile)
```

**Impact**:
- Scoring now uses profile-specific thresholds
- Per-source prompts applied automatically
- Different profiles can have different sensitivity levels

### 2. ✅ CLI Profile Selection

**File**: `src/main.py`

**New Arguments**:
- `--profile NAME` - Select which profile to use for scoring
- `--manage-profiles` - Launch interactive profile manager
- `--clear-cache` - Clear expired enrichment cache entries
- `--show-feedback-stats PROFILE` - Display accuracy metrics and recommendations

**Workflow Examples**:

```bash
# Run with specific profile
python -m src.main --profile ml-research --hours 24

# Launch profile manager
python -m src.main --manage-profiles

# Clear stale enrichment cache
python -m src.main --clear-cache

# View feedback statistics
python -m src.main --show-feedback-stats ml-research
```

**Implementation Details**:
- Before running pipeline, check for special commands
- Handle --manage-profiles → launch ProfileManager.interactive_menu()
- Handle --clear-cache → run CacheManager.clear_expired_cache()
- Handle --show-feedback-stats → display FeedbackAnalyzer results
- Load selected profile and pass to orchestrator

### 3. ✅ Interactive Profile Manager

**File**: `src/setup/profile_manager.py`

**New Method**: `interactive_menu()`

**Menu Options**:
```
1. Create new profile
2. Edit profile (modify threshold)
3. Clone profile (duplicate existing)
4. Delete profile
5. Set active profile
6. View all profiles
7. Exit
```

**Features**:
- Display current profiles with active indicator (✓)
- Interactive prompts for all operations
- Input validation
- Error handling with user feedback
- Non-destructive operations (confirmation for deletes)

**Usage**:
```bash
$ python -m src.main --manage-profiles

Profile Manager
==============

Current Profiles:
  1. default ✓
  2. ml-research
  3. news

Options:
  1. Create new profile
  2. Edit profile
  ...
  7. Exit

Select option (1-7): 1
Profile name: strict-ml
Description (optional): Only top-tier ML papers
✓ Profile 'strict-ml' created
```

### 4. ✅ Comprehensive Test Suite

**File**: `tests/test_phase4_integration.py`

**Test Classes**:

#### TestProfileManager
- `test_create_profile` - Creating new profiles
- `test_create_profile_with_threshold` - Custom thresholds
- `test_clone_profile` - Profile cloning
- `test_edit_profile` - Profile editing
- `test_delete_profile` - Profile deletion
- `test_set_source_prompt` - Custom per-source prompts
- `test_remove_source_prompt` - Removing custom prompts
- `test_list_profiles` - Listing all profiles

#### TestFeedbackAnalyzer
- `test_get_feedback_summary_empty` - Empty feedback handling
- `test_save_and_retrieve_feedback` - Feedback persistence
- `test_feedback_accuracy_calculation` - Accuracy rate computation
- `test_improvement_roadmap` - Recommendation generation

#### TestCacheManager
- `test_save_and_retrieve_cache` - Cache storage/retrieval
- `test_cache_expiry` - TTL enforcement
- `test_invalidate_url` - Manual cache invalidation
- `test_clear_expired_cache` - Batch cleanup

#### TestProfileIntegration
- `test_complete_profile_workflow` - End-to-end workflow

**Running Tests**:
```bash
# Run all Phase 4 tests
pytest tests/test_phase4_integration.py -v

# Run specific test class
pytest tests/test_phase4_integration.py::TestProfileManager -v

# Run specific test
pytest tests/test_phase4_integration.py::TestProfileManager::test_create_profile -v

# Run with coverage
pytest tests/test_phase4_integration.py --cov=src
```

## Architecture Updates

### Data Flow with Profiles

```
main.py (CLI args)
    ↓
Load config + storage
    ↓
Select profile (--profile or active)
    ↓
HorizonOrchestrator(config, storage, profile)
    ↓
orchestrator.run()
    ↓
ContentAnalyzer(ai_client, profile)
    ↓
Analyze with per-source prompts from profile
    ↓
Filter by profile.ai_score_threshold
    ↓
Store ProfileRun metadata
    ↓
Save summary
```

### Cache Integration

```
Orchestrator
    ↓
CacheManager initialized
    ↓
During enrichment:
    - Check cache for URL (get_cached_enrichment)
    - If miss: fetch + analyze
    - Store in cache with TTL
    ↓
Clear expired cache on --clear-cache
```

## Profile-aware Workflow

### Scenario: ML Research Profile

```bash
# 1. Create ML-focused profile
python -m src.main --manage-profiles
  → Create "ml-research"
  → Set threshold to 8.0
  → Set custom Reddit prompt for research quality

# 2. Run pipeline with profile
python -m src.main --profile ml-research

# 3. Result:
  - Uses threshold 8.0 (vs default 6.0)
  - Scores Reddit posts with ML-specific criteria
  - Filters to only top ML content

# 4. Check feedback
python -m src.main --show-feedback-stats ml-research
  → Shows accuracy rate
  → Shows misscored items
  → Recommends adjustments
```

## CLI Commands Reference

### Profile Management

```bash
# Create/edit profiles interactively
horizon --manage-profiles

# View stats for profile
horizon --show-feedback-stats default
horizon --show-feedback-stats ml-research

# Clear cache
horizon --clear-cache

# Run with specific profile
horizon --profile ml-research
horizon --profile news --hours 24

# Run with all options
horizon --profile strict-ml --hours 12 --theme "ML papers" --summary-format html
```

### Command Priority

1. `--manage-profiles` - Launches manager, exits after
2. `--clear-cache` - Clears cache, exits after
3. `--show-feedback-stats` - Shows stats, exits after
4. `--profile` - Used during normal pipeline run
5. `--hours`, `--theme`, `--summary-format` - Pipeline options (used with pipeline)

## Dependency Requirements

**pyproject.toml** (already updated):
```toml
dependencies = [
    # ... existing ...
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
]
```

**Testing**:
```bash
pip install pytest pytest-cov
```

## Docker Integration

### Dockerfile Updates (Planned for Phase 5)

```dockerfile
# Expose dashboard port
EXPOSE 5000

# Mount data volume for persistent storage
VOLUME ["/app/data"]

# CLI examples
CMD ["python", "-m", "uvicorn", "src.web.app:app", "--host", "0.0.0.0", "--port", "5000"]
```

### docker-compose.yml Updates (Planned for Phase 5)

```yaml
services:
  horizon:
    build: .
    ports:
      - "5000:5000"  # Dashboard
    volumes:
      - ./data:/app/data  # Persistent storage
    environment:
      - PYTHONUNBUFFERED=1
```

## Validation Checklist

- ✅ Profile passed to ContentAnalyzer
- ✅ Profile threshold used in filtering
- ✅ CLI arguments parse correctly
- ✅ Profile selection works
- ✅ Interactive menu functional
- ✅ Cache manager integrates
- ✅ Test suite comprehensive
- ⏳ Docker setup
- ⏳ End-to-end integration test

## Testing Strategy

### Unit Tests
- Profile CRUD operations
- Feedback analysis calculations
- Cache expiry logic
- Prompt selection

### Integration Tests
- Full profile workflow
- Pipeline with profile
- Dashboard feedback loop
- Cache hit/miss scenarios

### End-to-end Tests (Next Phase)
- Complete pipeline run with profile
- Feedback collection → recommendation → profile update
- Multiple profiles scoring same content

## Known Limitations

1. **Profile selection persistence**: If no --profile specified, uses active profile; doesn't auto-create default
2. **WebSocket integration**: Orchestrator doesn't yet broadcast progress to dashboard (Phase 2B planned)
3. **Batch operations**: No CLI option to apply feedback recommendations automatically
4. **Profile versioning**: No history tracking of profile changes

## Future Enhancements

### Phase 4B (Planned)
- [ ] Orchestrator broadcasts WebSocket messages during scraping
- [ ] Dashboard receives live progress updates
- [ ] Auto-apply feedback recommendations
- [ ] Profile change history/undo

### Phase 5 (Planned)
- [ ] Docker Compose updates
- [ ] Production deployment guide
- [ ] Performance benchmarking
- [ ] Load testing

### Phase 6 (Planned)
- [ ] Multi-user profiles (authentication)
- [ ] Profile sharing/templates
- [ ] AI-suggested profile optimization
- [ ] Advanced analytics

## Documentation Files

### New
- `docs/phase-4-integration.md` (this file)
- `tests/test_phase4_integration.py`

### Updated
- `docs/dashboard.md` - Added CLI reference
- `docs/profiles.md` - Added interactive manager section
- `pyproject.toml` - Dependencies verified

## Troubleshooting

### Profile not found error
```bash
# Check available profiles
python -m src.main --manage-profiles
# See option 6: View all profiles

# Create if missing
python -m src.main --manage-profiles
# Option 1: Create new profile
```

### Cache not clearing
```bash
# Manual cache clear
python -m src.main --clear-cache

# Verify cache was cleared
python -c "from src.ai.cache_manager import CacheManager; from src.storage.manager import StorageManager; cm = CacheManager(StorageManager()); cm.clear_expired_cache()"
```

### Feedback stats not showing
```bash
# Verify profile exists
python -m src.main --manage-profiles
# See option 6

# Check if profile has feedback
python -m src.main --show-feedback-stats profile-name

# If empty, run pipeline with profile first
python -m src.main --profile profile-name
```

---

**Status**: ✅ Phase 4A Complete - Orchestrator & CLI Integration  
**Next**: Phase 4B - WebSocket Broadcasting & Full Testing  
**Date**: May 5, 2026
