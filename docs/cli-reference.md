# CLI Reference Guide

## Quick Command Overview

```bash
# Profile Management
horizon --manage-profiles              # Launch interactive manager
horizon --profile <name>                # Select profile for run
horizon --show-feedback-stats <name>   # View accuracy metrics

# Cache Management  
horizon --clear-cache                  # Clear expired enrichment cache

# Pipeline Options
horizon                                 # Run with default (24h, default profile)
horizon --hours 48                      # Last 48 hours
horizon --theme "ML papers"            # Custom theme/description
horizon --summary-format html          # Output format (html, md)

# Combined Examples
horizon --profile ml-research --hours 48 --theme "ML & AI"
```

## Commands & Arguments

### Profile Management Commands

These commands execute standalone (before/instead of pipeline run):

#### `--manage-profiles`
Launch interactive profile manager menu.

```bash
horizon --manage-profiles
```

**Menu Options**:
1. Create new profile
2. Edit profile (change threshold)
3. Clone profile
4. Delete profile  
5. Set active profile
6. View all profiles
7. Exit

**Example Workflow**:
```
$ horizon --manage-profiles

Profile Manager
===============

Current Profiles:
  • default ✓ (threshold: 6.0)
  • ml-research (threshold: 7.5)
  • news (threshold: 6.5)

Options:
  1. Create new profile
  2. Edit profile
  3. Clone profile
  4. Delete profile
  5. Set active profile
  6. View all profiles
  7. Exit

Select option (1-7): 1

Profile name: ai-safety
Description: AI safety and alignment research
✓ Profile 'ai-safety' created with threshold 6.0
```

#### `--profile <name>`
Select which profile to use for the pipeline run.

```bash
horizon --profile ml-research

# With other pipeline options
horizon --profile ml-research --hours 24 --theme "ML & AI research"
```

**Behavior**:
- If profile doesn't exist: error, no run
- If profile exists: activate it temporarily for this run
- All scoring uses profile's threshold
- Per-source prompts applied from profile
- Feedback saved to profile's history

**Profile Selection Priority**:
1. `--profile <name>` if specified
2. Active profile if set via `set_active_profile()`
3. "default" profile if it exists
4. First available profile

#### `--show-feedback-stats <name>`
Display feedback statistics and improvement recommendations for a profile.

```bash
horizon --show-feedback-stats ml-research
```

**Output**:
```
📊 Feedback Statistics for 'ml-research'
========================================

Overall Accuracy
  Total feedback: 47
  Positive (👍): 38
  Negative (👎): 9
  Accuracy rate: 80.9%

Favorites
  Total marked: 12
  Favorite rate: 25.5%

Misscored Items
  Underscored (you liked, score < 5): 4
  Overscored (you disliked, score > 6): 2

Top Issues by Source
  Reddit: Underscored by 1.5 avg
  HN: Underscored by 0.8 avg
  GitHub: Overscored by 1.2 avg

Improvement Roadmap
  HIGH: Increase Reddit scoring by ~1.5 points
  HIGH: Decrease GitHub scoring by ~1.2 points
  MEDIUM: Add ML-specific prompt for Twitter
  LOW: Fine-tune HN score threshold
```

### Cache Management Commands

#### `--clear-cache`
Clear expired enrichment cache entries.

```bash
horizon --clear-cache
```

**Behavior**:
- Removes all cache entries past TTL
- Shows count of entries cleared
- Runs independently (before pipeline)

**Output**:
```
🧹 Clearing expired enrichment cache...
✓ Removed 14 expired entries
✓ Cache now has 203 valid entries
```

### Pipeline Options

These arguments are used during pipeline execution:

#### `--hours <number>`
Fetch items from last N hours (default: 24).

```bash
horizon --hours 48                    # Last 2 days
horizon --hours 1 --profile news      # Last hour, news profile
```

#### `--theme <string>`
Custom theme/description for the summary.

```bash
horizon --theme "AI & Machine Learning"
horizon --profile ml --theme "Latest ML Papers"
```

**Usage**: Appears in summary metadata and email subject.

#### `--summary-format <format>`
Output format for summary (default: html).

```bash
horizon --summary-format html
horizon --summary-format md          # Markdown
```

**Formats**:
- `html` - HTML page (default)
- `md` - Markdown file

### Combined Examples

#### Scenario 1: ML Research Daily
```bash
horizon --profile ml-research --hours 24 --theme "Top ML Papers"
```
- Uses ML research profile (8.0 threshold, custom Reddit/GitHub prompts)
- Fetches items from last 24 hours
- Generates summary titled "Top ML Papers"

#### Scenario 2: News Briefing
```bash
horizon --profile news --hours 12 --theme "Last 12 Hours News"
```
- Uses news profile (6.5 threshold, mainstream sources)
- Fetches items from last 12 hours
- Generates briefing

#### Scenario 3: Weekly Deep Dive
```bash
horizon --profile dev-ops --hours 168 --theme "Weekly DevOps Digest"
```
- Uses DevOps profile
- Fetches full week
- Markdown format for documentation

#### Scenario 4: Weekend Catch-up
```bash
horizon --profile all-sources --hours 72 --theme "Weekend Briefing"
```
- Uses a profile with all sources enabled
- Fetches 3 days
- HTML format for web viewing

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success - briefing generated |
| 1 | Error - invalid profile or config |
| 2 | Error - API failure or timeout |
| 3 | Error - no items collected |
| 4 | Error - initialization failed |

## Dashboard Commands

### Starting the Dashboard

```bash
# Run dashboard on http://localhost:5000
uvicorn src.web.app:app --host 0.0.0.0 --port 5000

# With auto-reload (development)
uvicorn src.web.app:app --reload

# Custom port
uvicorn src.web.app:app --port 8000
```

**Features**:
- View today's summary
- Browse past summaries  
- Rate articles (👍/👎)
- Mark favorites (⭐)
- Manage profiles
- View accuracy stats
- Get recommendations

### Dashboard API Endpoints

```bash
# Get all profiles
curl http://localhost:5000/api/profiles

# Get profile details
curl http://localhost:5000/api/profiles/ml-research

# Save feedback
curl -X POST http://localhost:5000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"item_id":"hn:12345","profile":"ml-research","rating":1}'

# Get feedback stats
curl http://localhost:5000/api/feedback?profile=ml-research

# Get today's summary
curl http://localhost:5000/api/summaries/today

# Get past summaries
curl http://localhost:5000/api/summaries?profile=ml-research
```

## Environment Variables

Key environment variables for configuration:

```bash
# API Keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."

# Optional
export HORIZON_DATA_DIR="./data"      # Data directory
export HORIZON_LOG_LEVEL="INFO"       # Log level
```

## Configuration Files

### data/config.json
Main configuration file with sources, models, filters:

```jsonc
{
  "ai": {
    "provider": "openai",
    "model": "gpt-4-turbo",
    "api_key_env": "OPENAI_API_KEY"
  },
  "sources": {
    "rss": [ /* RSS feeds */ ],
    "reddit": [ /* Subreddits */ ],
    "hackernews": { "enabled": true },
    "twitter": { "users": [ /* Twitter users */ ] }
  },
  "filtering": {
    "ai_score_threshold": 6.0
  },
  "outputs": {
    "email": { /* Email config */ },
    "webhook": { /* Webhook endpoints */ }
  }
}
```

### data/profiles.json
Stored profiles (auto-managed):

```jsonc
[
  {
    "name": "default",
    "description": "Default profile",
    "ai_score_threshold": 6.0,
    "per_source_prompts": {},
    "is_active": true,
    "created_at": "2026-05-01T10:00:00Z",
    "updated_at": "2026-05-05T14:30:00Z"
  },
  {
    "name": "ml-research",
    "description": "Machine learning & AI research",
    "ai_score_threshold": 7.5,
    "per_source_prompts": {
      "reddit": "Score ML research papers and discussions highly...",
      "github": "Score ML/AI projects and releases..."
    },
    "is_active": false,
    "created_at": "2026-05-02T12:00:00Z",
    "updated_at": "2026-05-05T09:15:00Z"
  }
]
```

## Troubleshooting

### Profile not found
```bash
# Check available profiles
horizon --manage-profiles
# Select option 6 to view all profiles
```

### Cache not clearing
```bash
# Verify cache was cleared
python -c "from src.ai.cache_manager import CacheManager; \
from src.storage.manager import StorageManager; \
CacheManager(StorageManager()).clear_expired_cache()"
```

### Feedback stats empty
```bash
# Verify profile has feedback
# First run with profile to generate feedback
horizon --profile test-profile --hours 24

# Then check stats
horizon --show-feedback-stats test-profile
```

### Dashboard not accessible
```bash
# Check if port 5000 is in use
lsof -i :5000

# Use different port
uvicorn src.web.app:app --port 8000
```

---

**See Also**: [Configuration Guide](configuration.md) · [Profiles Guide](profiles.md) · [Dashboard Guide](dashboard.md)
