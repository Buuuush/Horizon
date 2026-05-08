# Horizon Feedback Learning System

The feedback system learns from your article ratings to improve scoring accuracy over time.

## How It Works

### 1. Submit Feedback

After articles are scored and summarized, you can rate them:

- **👍 Thumbs Up**: "I liked this article, it deserved a higher score"
- **👎 Thumbs Down**: "I didn't like this article, it was overrated"
- **⭐ Favorite**: Mark articles to read later or revisit

### 2. Track Misscores

The system detects when scoring was off:

- **Underscored**: Article rated 👍 but AI score < threshold
- **Overscored**: Article rated 👎 but AI score ≥ threshold

Example:
```
Article about new ML technique
  AI Score: 5.5 (didn't make the cut)
  User Rating: 👍 (actually loved it)
  Analysis: UNDERSCORED by ~1.5 points
```

### 3. Analyze Patterns

Feedback analyzer identifies trends:

- Which sources are consistently misscored?
- Do certain topics always get wrong scores?
- How often is the threshold off?

### 4. Get Recommendations

Dashboard suggests improvements:

```
🔼 REDDIT: 3 ML posts rated 👍 were underscored
   → Adjust Reddit scoring to value research novelty more

🔽 HN: 2 low-effort posts rated 👎 were overscored  
   → Raise technical bar in HN scoring prompt
```

### 5. Apply Changes

Manually approve and apply suggestions:

```bash
# View recommendations
horizon --profile default --feedback-recommendations

# Apply to profile
horizon --profile default --apply-feedback-recommendations
```

## Dashboard Interface

### Feedback Tab

**Statistics Section:**
- **Total Feedback**: How many articles you've rated
- **Accuracy**: Percentage of scores you agreed with
- **Misscored**: Number of off-target scores
- **Favorites**: Articles marked for later

**Recommendations Section:**
- Prioritized suggestions (High / Medium / Low)
- Specific actions to improve scoring
- Applied to active profile

### Example Workflow

1. Generate summary with default profile
2. Go to dashboard → "Today" tab
3. Rate 5-10 articles (mix of 👍 and 👎)
4. Switch to "Feedback" tab
5. Review accuracy stats and suggestions
6. Apply recommendations to profile
7. Run pipeline again with updated profile
8. Compare results

## Using Feedback via API

### Submit Feedback

```bash
curl -X POST http://localhost:5000/api/feedback/default \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "hackernews:story:12345678",
    "user_rating": 1,
    "is_favorite": false,
    "notes": "Really insightful discussion"
  }'
```

### Get Feedback Stats

```bash
curl http://localhost:5000/api/feedback/default/stats
```

Response:
```json
{
  "total_feedback": 12,
  "positive_feedback": 8,
  "negative_feedback": 4,
  "favorites": 3,
  "misscored_items": 2,
  "accuracy_rate": "83.3%",
  "summary": "Accuracy: good (83.3%). 👍 8 positive, 👎 4 negative, ⭐ 3 favorites. ⚠️ 2 items were misscored."
}
```

### Get Recommendations

```bash
curl http://localhost:5000/api/feedback/default/recommendations
```

Response:
```json
{
  "recommendations": [
    {
      "priority": "high",
      "title": "Items rated 👍 were underscored",
      "action": "Consider raising thresholds by ~1.5 points for low-scoring items that users love."
    },
    {
      "priority": "medium",
      "title": "Source: reddit",
      "action": "🔼 REDDIT: 2 items rated 👍 were underscored. Adjust the REDDIT scoring prompt to value engagement/novelty more."
    }
  ]
}
```

## Programmatic Access

### Check Feedback Summary

```python
from src.storage.manager import StorageManager
from src.ai.feedback_analyzer import FeedbackAnalyzer

storage = StorageManager()
fa = FeedbackAnalyzer(storage)

# Get summary for a profile
summary = fa.get_feedback_summary('default')
print(f"Accuracy: {summary['accuracy_rate']}")
print(f"Misscored: {summary['misscored_items']}")
```

### Analyze Patterns

```python
# Get detailed patterns
patterns = fa.analyze_misscored_patterns('default')
for pattern in patterns['patterns']:
    print(f"{pattern['type']}: {pattern['count']} cases")
    
# Get per-source suggestions
suggestions = fa.suggest_source_specific_adjustments('default')
for source, suggestions_list in suggestions.items():
    print(f"Source {source}:")
    for suggestion in suggestions_list:
        print(f"  - {suggestion}")
```

### Get Improvement Roadmap

```python
# Prioritized list of improvements
roadmap = fa.get_improvement_roadmap('default')
for item in roadmap:
    print(f"{item['priority'].upper()}: {item['title']}")
    print(f"  Action: {item['action']}")
```

### Export Feedback

```python
# Export to CSV for analysis
fa.export_feedback_to_csv('default', 'feedback_export.csv')
```

## Interpreting Stats

### Accuracy Rate

- **90%+**: Excellent - profile is well-calibrated
- **80-89%**: Good - working well with minor adjustments
- **70-79%**: Fair - threshold or prompts need tuning
- **<70%**: Poor - consider major changes or profile reset

### Misscored Items

Count of articles where AI score contradicted your feedback:

- **0-1**: Profile is accurate, keep current settings
- **2-3**: Minor adjustments needed
- **4+**: Profile needs significant changes

## Common Scenarios

### Scenario 1: Too Many High Scores

**Symptom**: Many articles rated 👎 but had high AI scores

**Diagnosis**: Threshold too low or scoring too generous

**Fix**: 
```
Increase ai_score_threshold by +1-2 points
OR
Raise the bar in scoring prompts (stricter evaluation)
```

### Scenario 2: Too Many Low Scores

**Symptom**: Many articles rated 👍 but had low AI scores

**Diagnosis**: Threshold too high or scoring too strict

**Fix**:
```
Decrease ai_score_threshold by -1-2 points
OR
Relax scoring prompts (more inclusive)
```

### Scenario 3: Source-Specific Issues

**Symptom**: Reddit misscores but HN is accurate

**Diagnosis**: Per-source prompt not optimized for Reddit

**Fix**:
```python
# Customize Reddit prompt
pm.set_source_prompt('default', SourceType.REDDIT, 
  "Value discussion quality and diverse viewpoints more...")
```

### Scenario 4: All Sources Have Issues

**Symptom**: Multiple sources consistently misscored

**Diagnosis**: Global threshold/prompt needs adjustment

**Fix**:
```
Review and adjust CONTENT_ANALYSIS_SYSTEM prompt
Consider profile is meant for different use case
```

## Best Practices

1. **Rate at least 10 articles** before analyzing (minimum sample size)
2. **Be consistent**: Rate based on YOUR preferences, not general quality
3. **Check monthly**: Reviews feedback helps catch drift
4. **Create test profiles**: Try new scoring before applying to production
5. **Track changes**: Export CSV before major edits to see impact
6. **Document feedback**: Add notes on why you rated articles

## Tips for Effective Learning

### Do Rate...
- ✅ Articles you genuinely found useful or interesting
- ✅ Mix of technical and non-technical content
- ✅ Consistency across multiple profiles (if using several)
- ✅ Outliers (especially misscored items help most)

### Don't Rate...
- ❌ Based on source author (it's the content that matters)
- ❌ Based on engagement numbers (score independently)
- ❌ Too quickly (take time to read and form opinion)
- ❌ In batches without thinking (thoughtful ratings are better)

## FAQ

**Q: How long does feedback take to apply?**  
A: Immediately. Next time you run the pipeline, new scores use updated prompts.

**Q: Can I undo feedback?**  
A: Delete the rating (coming in Phase 2B), or just rate differently next time.

**Q: Does feedback affect other profiles?**  
A: No, each profile has separate feedback storage.

**Q: What if I make a profile worse with feedback?**  
A: Clone a fresh profile from 'default' or delete and recreate.

**Q: Can I see feedback from other profiles?**  
A: No, each profile has isolated feedback. Good for experimentation.

**Q: How are recommendations calculated?**  
A: Based on mismatch patterns in feedback (see `src/ai/feedback_analyzer.py`).

## Next Features (Phase 2B)

- Undo/edit feedback submissions
- Visual feedback trends over time
- A/B test profiles with feedback
- Automatic threshold optimization
- Export feedback reports
