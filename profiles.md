# Horizon Profiles & Personalization

Profiles allow you to create custom scoring strategies for different interests or use cases.

## Quick Start

### Create a Profile

```bash
python -c "
from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager

storage = StorageManager()
pm = ProfileManager(storage)

# Create a new profile based on 'default'
profile = pm.create_profile(
    'ml-research',
    description='Focus on ML papers and research',
    base_profile='default'
)
print(f'✓ Created profile: {profile.name}')
"
```

### Activate a Profile

```bash
python -c "
from src.storage.manager import StorageManager

storage = StorageManager()
storage.set_active_profile('ml-research')
print('✓ Profile activated')
"
```

### Run with a Specific Profile

```bash
python -m src.main --profile ml-research
```

### View All Profiles

```bash
python -c "
from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager

storage = StorageManager()
pm = ProfileManager(storage)
pm.print_all_profiles()
"
```

## Profile Properties

Each profile has:

- **name** (string): Unique identifier (e.g., "default", "ml-research")
- **description** (string): Human-readable description
- **ai_score_threshold** (float, 0-10): Minimum score to include in summary
- **per_source_prompts** (dict): Custom scoring prompts per source
- **active_sources** (list): Which scrapers to run for this profile (empty = all)
- **created_at** (datetime): When profile was created
- **updated_at** (datetime): Last modification time
- **is_active** (bool): Whether this profile is currently active

## Use Cases

### 1. DevOps Profile

Focus on infrastructure, cloud, and deployment:

```bash
python -c "
from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager
from src.models import SourceType

storage = StorageManager()
pm = ProfileManager(storage)

# Create profile
profile = pm.create_profile('devops', description='Infrastructure & DevOps')

# Lower threshold (care about more items)
pm.edit_profile('devops', ai_score_threshold=5.0)

# Only scrape GitHub and RSS (where DevOps content lives)
pm.set_active_sources('devops', [SourceType.GITHUB, SourceType.RSS])

# Custom prompt for GitHub (emphasize ops/infrastructure)
custom_prompt = '''Score based on DevOps relevance:
- 9-10: Major infrastructure breakthrough (Kubernetes, Terraform, CI/CD)
- 7-8: Useful DevOps tool or technique
- 5-6: Interesting but niche DevOps content
- 3-4: Generic infrastructure news
- 0-2: Not relevant to DevOps
'''
pm.set_source_prompt('devops', SourceType.GITHUB, custom_prompt)

print('✓ DevOps profile created')
"
```

### 2. ML Research Profile

Focus on cutting-edge ML papers:

```bash
python -c "
from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager
from src.models import SourceType

storage = StorageManager()
pm = ProfileManager(storage)

# Create profile based on default
profile = pm.create_profile('ml-research', description='ML papers & breakthroughs')

# Higher threshold (only top papers)
pm.edit_profile('ml-research', ai_score_threshold=7.0)

# Customize Reddit scoring for ML community
reddit_prompt = '''Score ML discussions based on research value:
- 9-10: Novel architecture/technique, paper published at top venue
- 7-8: Significant paper or heated discussion of novel ideas
- 5-6: Interesting research but incremental
- 3-4: Routine updates or minor papers
- 0-2: Not research-related
'''
pm.set_source_prompt('ml-research', SourceType.REDDIT, reddit_prompt)

print('✓ ML Research profile created')
"
```

### 3. General News Profile

Broad interest in news and current events:

```bash
python -c "
from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager

storage = StorageManager()
pm = ProfileManager(storage)

# Create profile
profile = pm.create_profile('news', description='General news & current events')

# Lower threshold to catch more diverse stories
pm.edit_profile('news', ai_score_threshold=5.0)

print('✓ News profile created')
"
```

## Managing Profiles with Dashboard

1. Open http://localhost:5000
2. Go to **Settings** tab
3. Click a profile card to view its details
4. Click the profile to activate it

## Per-Source Scoring Prompts

Each source type has a default specialized prompt:

- **HN (Hacker News)**: Emphasis on technical innovation, community merit
- **GitHub**: Code impact, maintenance signals, release significance
- **Reddit**: Discussion quality, expertise indicators, debate value
- **RSS**: News quality, reporting accuracy, journalistic rigor
- **Twitter**: Influence, authority, discussion value
- **Telegram**: Channel authority, announcement significance

Override any by setting a custom prompt:

```python
pm.set_source_prompt(profile_name, SourceType.HACKERNEWS, custom_prompt)
```

## Feedback Learning

Profiles learn from your feedback:

1. **Submit feedback** via dashboard (👍/👎 on articles)
2. **View stats**: Dashboard → Feedback tab
3. **Get recommendations**: "Adjust threshold +2 for underscored items"
4. **Apply suggestions**: Dashboard or CLI

### View Feedback Statistics

```bash
python -c "
from src.storage.manager import StorageManager

storage = StorageManager()
stats = storage.get_feedback_stats('default')
print(f\"Total Feedback: {stats['total_feedback']}\")
print(f\"Accuracy: {stats['accuracy_rate']:.0f}%\")
print(f\"Misscored: {stats['misscored_items']}\")
"
```

### Get Recommendations

```bash
python -c "
from src.storage.manager import StorageManager
from src.ai.feedback_analyzer import FeedbackAnalyzer

storage = StorageManager()
fa = FeedbackAnalyzer(storage)
roadmap = fa.get_improvement_roadmap('default')

for rec in roadmap:
    print(f\"{rec['priority'].upper()}: {rec['title']}\")
    print(f\"  → {rec['action']}\")
"
```

## Cloning Profiles

Create a new profile based on an existing one:

```bash
python -c "
from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager

storage = StorageManager()
pm = ProfileManager(storage)

# Clone 'default' as 'ml-strict' with higher threshold
cloned = pm.clone_profile('default', 'ml-strict', description='Stricter ML profile')
pm.edit_profile('ml-strict', ai_score_threshold=8.0)

print(f'✓ Created {cloned.name} based on default')
"
```

## Deleting Profiles

```bash
python -c "
from src.storage.manager import StorageManager
from src.setup.profile_manager import ProfileManager

storage = StorageManager()
pm = ProfileManager(storage)

pm.delete_profile('ml-strict')
print('✓ Profile deleted')
"
```

## CLI Commands (Planned for Phase 4)

```bash
# View profiles
horizon --list-profiles

# Create profile
horizon --create-profile devops --description 'DevOps content'

# Activate profile
horizon --profile ml-research

# Manage thresholds
horizon --profile default --set-threshold 7.0

# Feedback stats
horizon --profile default --feedback-stats
```

## Tips

1. **Start with default**: Create new profiles based on 'default'
2. **Test thresholds**: Lower threshold = more items, higher = stricter
3. **Customize gradually**: Start with defaults, override per-source as needed
4. **Use feedback**: Let profiles learn from your 👍/👎 ratings
5. **Archive profiles**: Clone a profile before making big changes

## FAQ

**Q: Can I change a profile's name?**  
A: Not directly. Clone it with a new name and delete the old one.

**Q: How do I reset a profile to defaults?**  
A: Delete it and create a new one from 'default'.

**Q: Can profiles share feedback?**  
A: No, each profile has separate feedback and stats.

**Q: What happens if I delete the active profile?**  
A: It automatically switches to another profile.

**Q: Can I export/backup profiles?**  
A: They're stored in `data/horizon.db`. Backup this file.
