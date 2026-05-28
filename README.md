# Guide Utilisateur : Utiliser Horizon

## 🚀 Démarrage Rapide

### Installation (5 min)

```bash
# Clone le repo
git clone https://github.com/your-org/horizon.git
cd horizon

# Crée l'environnement Python
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# Installe les dépendances
pip install -e .
pip install -e ".[dev]"  # Pour tester

# Configure les API keys
export $NVIDIA_API_KEY="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"
export OPENAI_API_KEY="your_openai_key"  # Si tu switches provider
```

### Édite la Configuration

```bash
# Copie l'exemple
cp data/config.example.json data/config.json

# Édite avec ton éditeur préféré
nano data/config.json
# Ou ouvre dans VS Code
```

**Config minimale** :

```json
{
  "ai": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.3
  },
  "sources": {
    "rss": [
      {
        "name": "Quanta Magazine",
        "url": "https://api.quantamagazine.org/feed/",
        "enabled": true
      }
    ],
    "hackernews": {
      "enabled": true,
      "fetch_top_stories": 30
    },
    "reddit": {
      "enabled": true,
      "subreddits": [
        {
          "subreddit": "MachineLearning",
          "enabled": true,
          "sort": "hot"
        }
      ]
    }
  },
  "filtering": {
    "ai_score_threshold": 7.0
  }
}
```

### Exécute le Pipeline

```bash
# Run complet (collecte → scoring → enrichment → HTML)
horizon --hours 336 --theme "informatique" --summary-format html

# Ou seulement 12 dernières heures
horizon --hours 12

# Filtrer par thème
horizon --theme "climate"

# Résultat dans
cat data/summaries/2026-05-10-bilingual.html
# Ouvre dans le navigateur
```

---

## 📖 Guide Détaillé

### 1. Comprendre les Sources

**Sources activées par défaut** :
- **Quanta Magazine** — Math, physics, deep science explainers
- **MIT Technology Review** — Tech & society
- **Aeon** — Philosophy, culture, long-form thinking
- **Hacker News** — Tech community picks (threshold: 100+ points)
- **Reddit MachineLearning, Science** — Community discussions
- **Ars Technica** — Tech in depth
- **Carbon Brief** — Climate science
- **Smithsonian** — History & culture

**À customiser** :
```json
"sources": {
  "rss": [
    {
      "name": "Noema",
      "url": "https://www.noemamag.com/feed/",
      "enabled": true,
      "category": "geopolitics"
    }
  ]
}
```

**Ajouter RSS feed** : 
1. Copie l'URL du feed (cherche `feed.xml` ou `.rss`)
2. Ajoute à config.json

**Disable source** : Set `"enabled": false`

### 2. Comprendre le Scoring IA

**Chaque article est noté 0-10** basé sur :

| Dimension | Meaning | Exemple Good | Exemple Bad |
|-----------|---------|--------------|-------------|
| **score** | Importance globale | 9 = Breakthrough scientist | 2 = Routine update |
| **source_reliability** | Crédibilité source | 9 = MIT Tech Review | 4 = Random blog |
| **explanatory_value** | Aide-t-il comprendre? | 9 = Deep explainer | 2 = "5 reasons" listicle |
| **novelty** | Réellement nouveau? | 10 = First coverage | 1 = 10ème article même sujet |
| **potential_impact** | Effets en cascade? | 9 = Climate policy change | 2 = Gadget release |
| **uncertainty** | Risk de bullshit? | 1 = Peer-reviewed study | 9 = Rumor from Twitter |

**Seuil = 7.0/10 par défaut** = filtrer ~70% du bruit.

**Veux articles plus strict?** : Augmente à 7.5-8.0  
**Veux voir plus niche?** : Baisse à 6.5

```json
"filtering": {
  "ai_score_threshold": 7.5
}
```

### 3. Anti-Mainstream Par Défaut

**Hosts pénalisés** (réduction score) :
- Bloomberg, Reuters, FT : -25%
- BBC, Al Jazeera, NYTimes : -20%

**Raison** : Ces médias "mainstream" domineraient scoring sans pénalité, mais pour utilisateur Horizon, c'est moins utile que Quanta/Aeon/spécialisés.

**Tags boostés** (augmentation score) :
- Science, history, climate : +25%
- Culture, infrastructure, energy : +20%

**Tags pénalisés** (réduction score) :
- Politics, geopolitics, breaking : -20%

**Customize :** Pas d'UI encore, faut éditer code (`src/ai/analyzer.py` lignes ~350-400).

### 4. Enrichissement : Quoi à Attendre

Chaque article sélectionné reçoit **enrichissement IA** :

```
Article original (RSS title + content):
"New Claude Model Beats Benchmarks"

APRÈS enrichissement:

✅ Title: "Anthropic's Claude AI Now Tops Industry Benchmarks"

✅ What's new: 
"Anthropic released Claude 4.5 with reasoning capabilities, 
achieving 91.4% on MMLU vs 89.2% previous. First model 
to pass novel reasoning tests."

✅ Why it matters:
"Indicates AI generalization improving. Affects trajectory of 
AI safety research and competitive landscape."

✅ Key details:
"Results on MMLU, GPQA, ArenaHard benchmarks. Ran 5 trillion 
tokens in training. Cost $150M."

✅ Background:
"MMLU = Massive Multitask Language Understanding, standard AI 
benchmark since 2020. Reasoning = ability to work through complex 
problem step-by-step, not just pattern-match."

✅ Community discussion:
"HN upvotes mixed — excitement on inference speed improvements, 
concerns on benchmark-gaming vs real-world usefulness."

✅ Sources: [3 URLs from web search supporting background]
```

---

## 📊 Output: Understanding the HTML

### Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>Horizon Daily — 2026-05-10</title>
  <style>/* Responsive design, dark mode, fonts */</ style>
</head>
<body>
  <div class="container">
    <!-- Tab switcher: FR / EN -->
    <div class="tab-switcher">
      <button data-lang="fr">Français</button>
      <button data-lang="en">English</button>
    </div>
    
    <!-- French content -->
    <div class="tab-content active" data-lang="fr">
      <header class="summary-header">
        <h1>Horizon Quotidien — 2026-05-10</h1>
        <p class="lead">25 sujets essentiels sélectionnés parmi 147 contenus collectés.</p>
        <nav class="toc">
          <!-- Table of contents with links -->
        </nav>
      </header>
      
      <main class="items">
        <!-- 25 articles, each with structure below -->
      </main>
    </div>
    
    <!-- English content (same articles) -->
    <div class="tab-content" data-lang="en">
      <!-- Same structure, English text -->
    </div>
  </div>
</body>
</html>
```

### Article Structure

```html
<article id="item-1">
  <header>
    <h2><a href="https://...">Title</a> <span>⭐ 8.2/10</span></h2>
    <div class="meta">
      rss · MIT Technology Review · May 10, 14:00
      · <a href="...">Discussion</a>
    </div>
  </header>
  
  <div class="lang-blocks">
    <section class="content-section">
      <h3>Ce qui est nouveau</h3>
      <div>Text explaining what happened...</div>
    </section>
    
    <section class="content-section">
      <h3>Pourquoi c'est important</h3>
      <div>Text on implications...</div>
    </section>
    
    <section class="content-section">
      <h3>Contexte</h3>
      <div>Background for non-experts...</div>
    </section>
  </div>
  
  <div class="tags">
    #science #AI #breakthrough
  </div>
  
  <details>
    <summary>Références</summary>
    <ul>
      <li><a href="...">Source 1 from web search</a></li>
      <li><a href="...">Source 2 from web search</a></li>
    </ul>
  </details>
</article>
```

### What the Score Means

| Score | Meaning |
|-------|---------|
| **9-10** | Groundbreaking — must read |
| **8-9** | High value — important update |
| **7-8** | Worth reading — solid news |
| **6-7** | Interesting niche — if interested |

**All shown articles are 7.0+** = filtered to quality.

---

## 🔧 Advanced Usage

### Run Daily (Cron)

```bash
# Add to crontab
0 8 * * * cd /path/to/horizon && .venv/bin/horizon --hours 336 --theme "informatique"

# Generates HTML daily at 8 AM
# Outputs to data/summaries/2026-05-{day}-bilingual.html
```

### Copy to GitHub Pages (Auto-Publish)

```bash
# Already set up! After `horizon` runs:
# 1. HTML generated to data/summaries/
# 2. Copied to docs/_posts/
# 3. Deploy GitHub Pages → docs/ folder
# 4. Your summary live at https://your-site.github.io/

# Jekyll renders docs/_posts/*.html as blog posts
```

### Use MCP Server (Claude Integration)

```python
# If running MCP server:
python -m src.mcp.server

# Then in Claude:
# @use horizon
# > List recent runs and their scores
# > Get articles about climate from last run
# > Filter high-score items (8+) by tag "science"
```

### Webhook Notification

```json
"webhook": {
  "enabled": true,
  "url_env": "HORIZON_WEBHOOK_URL",
  "platform": "slack",
  "delivery": "summary",
  "languages": ["en"]
}
```

Then set:
```bash
export HORIZON_WEBHOOK_URL="https://hooks.slack.com/..."
```

Post to Slack daily with article summaries.

---

## 🐛 Troubleshooting

### "No articles selected"
**Cause** : Threshold too high, or sources disabled.

**Fix** :
```bash
# Lower threshold
# Or check config.json sources are enabled
# Or run with lower hours window
horizon --hours 48
```

### "AI API rate limited"
**Cause** : Too many articles analyzed too fast.

**Fix** : Increase throttle_sec in config
```json
"ai": {
  "throttle_sec": 5
}
```

### "Web search finds nothing"
**Cause** : DuckDuckGo blocked or network issue.

**Fix** : Background will just be empty, article still included. Manual search added to references section.

### "HTML looks ugly on mobile"
**Fix** : Responsive design is built-in. Hard refresh browser cache.

### "I want to disable a source"
**Fix** :
```json
"sources": {
  "rss": [
    {
      "name": "Quanta",
      "enabled": false  // Disable this feed
    }
  ]
}
```

---

## 📚 What To Do With Output

### Option 1: Read in Browser
```bash
open data/summaries/2026-05-10-bilingual.html
# Or just drag-drop to browser
```

### Option 2: Email Yourself
```bash
# Set up email in config.json, enable subscribers
# Send to your email each morning
```

### Option 3: GitHub Pages
```bash
# Committed to docs/_posts/
# Auto-published as blog posts
# Share link with others
```

### Option 4: Integrate Elsewhere
```bash
# Copy HTML anywhere — static file, no deps
# Or parse data/api.json (if enabled) for custom rendering
```

---

## 💬 FAQ

**Q: Can I add my own RSS feed?**  
A: Yes! Add to `sources.rss` in config.json.

**Q: Can I change the scoring formula?**  
A: Currently no UI. Edit `src/ai/analyzer.py` lines ~350-400 (PENALIZED_TAGS, DEFAULT_TOPIC_BOOSTS).

**Q: Will my preferences be remembered?**  
A: Not yet (v0.1.0). Coming in v0.2 with profile manager UI.

**Q: Can I see articles I liked before?**  
A: Not yet. Archive feature coming in v0.2.

**Q: Can I use this for a team?**  
A: Currently single-user. Multi-user coming in v0.4.

**Q: How much does it cost?**  
A: Only API costs (NVIDIA/OpenAI). NVIDIA is ~$0.10/run, OpenAI ~$0.30/run. Open source tool itself = free.

**Q: Can I run this offline?**  
A: Sources yes (RSS local), but enrichment needs internet (web search + AI API).

---

## 🎯 Best Practices

### 1. Calibrate Your Threshold
- **Too high (8.0+)** = miss interesting stuff, only "obvious" news
- **Too low (6.0)** = too noisy, see fluff
- **Sweet spot** = 7.0-7.5 for most users

### 2. Curate Sources
- **Add** feeds you love (Noema, Axios, local journalism)
- **Remove** feeds too noisy (generic news)
- **Organize by topic** (climate feeds separate from tech)

### 3. Regular Reading
- Best as **daily ritual** (8 AM briefing)
- **Spend 20-30 min reading** (3-4 articles in depth)
- Too many daily = diluted attention, skip

### 4. Give Feedback (When Feature Arrives)
- Rate 👍/👎 articles
- Notes on why liked/disliked
- Helps IA improve recommendations

---

## 📞 Support & Community

- **Issues** : GitHub issues on repo
- **Discussions** : GitHub Discussions for ideas

---

**Happy reading! 🎉**

*Next article worth your time is coming tomorrow morning.*
