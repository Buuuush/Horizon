# Horizon Dashboard Setup Guide

## ✅ Dashboard is Ready!

The Horizon dashboard is now running on `http://localhost:5000` with full interactive article viewing and real-time progress updates.

### Latest Features (Phase 2B)

**Interactive Article Viewer:**
- 🎯 Click any article to view full content, metadata, and source link
- 👍👎 Rate articles inline with feedback buttons
- ⭐ Mark favorite articles for later review
- 📝 Add notes explaining your rating

**Real-time Progress (WebSocket):**
- 🔴 LIVE badge shows during scraping/analysis
- 📊 Real-time articles stream in as they're scored
- ✅ Auto-loads summary when complete
- 🔄 Progress percentage updates live

**Smart Notifications:**
- 🔔 Toast notifications for all actions
- ✅ Success/error/warning/info types
- ⏱️ Auto-dismiss after 3 seconds
- 🎨 Smooth slide-in/out animations

### Current Status

**✓ Completed Components:**
- SQLite storage layer with profiles, feedback, and enrichment cache
- 6 specialized scoring prompts (HN, GitHub, Reddit, RSS, Twitter, Telegram)
- Feedback analyzer with accuracy tracking and recommendations
- Enrichment cache manager (30-day TTL)
- Smart retry logic with exponential backoff (3-5 attempts per source)
- 40+ new RSS sources added to registry
- FastAPI-based web dashboard with profile management

**Configuration:**
- A default `config.json` has been created in `data/`
- On first run, profiles are auto-migrated from config.json to SQLite

### Dashboard Access

**URL:** http://localhost:5000

**Tabs:**
1. **Today** - View today's summary with interactive articles + real-time scraping
2. **Archive** - Browse past summaries by date
3. **Settings** - Manage profiles and view details
4. **Feedback** - View accuracy statistics and improvement recommendations

### Next Steps

#### Option 1: Run Full Pipeline (with profiles)
```bash
python -m src.main --profile default
```

#### Option 2: Test Dashboard Features
- Open http://localhost:5000
- Navigate to **Settings** tab to see profiles
- The "default" profile will be created automatically when you run the pipeline

#### Option 3: Manage Profiles (CLI)
```bash
# View all profiles
python -c "from src.storage.manager import StorageManager; from src.setup.profile_manager import ProfileManager; s=StorageManager(); p=ProfileManager(s); p.print_all_profiles()"

# Create a new profile
python -c "from src.storage.manager import StorageManager; from src.setup.profile_manager import ProfileManager; s=StorageManager(); p=ProfileManager(s); profile=p.create_profile('ml-research', description='Focus on ML papers'); print(f'Created profile: {profile.name}')"
```

### API Endpoints

The dashboard exposes the following API endpoints:

**Profile Management:**
- `GET /api/status` - System status
- `GET /api/profiles` - List all profiles
- `GET /api/profiles/{name}` - Get profile details
- `POST /api/profiles/{name}/activate` - Activate a profile

**Feedback & Learning:**
- `POST /api/feedback/{profile}` - Submit article feedback (👍/👎)
- `GET /api/feedback/{profile}/stats` - Feedback accuracy stats
- `GET /api/feedback/{profile}/recommendations` - Improvement suggestions

**Favorites (NEW):**
- `POST /api/favorites/{profile}` - Add/remove favorite article
- `GET /api/favorites/{profile}` - List favorite articles (paginated)

**Summaries:**
- `GET /api/summaries` - List past summaries with pagination
- `GET /api/summaries/{date}?language=en` - View specific summary

**Real-time (NEW - WebSocket):**
- `WS /ws/progress/{profile}` - Real-time scraping/analysis progress

**Health Check:**
- `GET /health` - Service health status

### Architecture

**Data Storage:**
- `data/horizon.db` - SQLite database (profiles, feedback, cache)
- `data/config.json` - AI & source configuration
- `data/summaries/` - Generated HTML summaries

**Components:**
- `src/web/app.py` - FastAPI server
- `src/storage/sqlite_manager.py` - SQLite backend
- `src/setup/profile_manager.py` - Profile CRUD
- `src/ai/feedback_analyzer.py` - Feedback analysis
- `src/ai/cache_manager.py` - Enrichment caching
- `data/rss_sources.json` - RSS feeds registry

### Troubleshooting

**Q: Dashboard shows "Storage not initialized"**
- A: Make sure `data/config.json` exists. A basic version has been created for you.
- Verify the config has valid AI provider settings (e.g., `OPENAI_API_KEY` environment variable)

**Q: API returns 503 Service Unavailable**
- A: Check that `data/config.json` exists and is valid JSON
- Look at server logs for initialization errors

**Q: Profiles tab shows error**
- A: Run the pipeline at least once: `python -m src.main --profile default`
- This will create the SQLite database and default profile

### Integration with Orchestrator

The orchestrator (`src/orchestrator.py`) needs to be updated to:
1. Load active profile via `storage.get_active_profile()`
2. Pass profile to `ContentAnalyzer(ai_client, profile=active_profile)`
3. Use cache manager for enrichments
4. Log profile_run metadata after generation

This integration is the next step in Phase 4.

### Features Implemented

#### Personalization (Phase 1A-1B)
- ✅ Multiple profiles with custom thresholds
- ✅ Per-source scoring prompts (different scoring strategies for each source type)
- ✅ Feedback learning (track which articles were misscored)
- ✅ Automatic recommendation generation

#### Dashboard (Phase 2A-2B)
- ✅ Profile management interface
- ✅ Feedback statistics display
- ✅ Summary browsing & viewing
- ✅ System status monitoring
- ✅ **Interactive article viewer modal** (NEW)
- ✅ **Real-time article feedback** (👍/👎) (NEW)
- ✅ **Favorites system with persistence** (NEW)
- ✅ **WebSocket real-time progress streaming** (NEW)
- ✅ **Toast notifications** (NEW)

#### Robustness (Phase 3A-3B)
- ✅ Enrichment caching (avoid re-fetching)
- ✅ Intelligent retry logic (exponential backoff)
- ✅ Circuit breaker (skip flaky sources)
- ✅ 40+ RSS sources registered (ready to add to config)

### What's Next?

**Phase 2C** - Advanced Dashboard Features (Optional):
- Auto-reconnect for WebSocket
- Advanced filtering (by score range, source, date)
- Full-text search
- Article export (CSV/PDF)
- Dark mode toggle
- Keyboard shortcuts

**Phase 4** - Integration & Tests:
- Update orchestrator to broadcast WebSocket messages
- CLI support for profile management
- Comprehensive test suite
- Docker updates
- Complete documentation
- Performance optimization

---

**Dashboard Status:** 🟢 Phase 2B Complete - Interactive Features Ready  
**Last Updated:** May 5, 2026
