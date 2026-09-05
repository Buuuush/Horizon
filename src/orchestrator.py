"""Main orchestrator coordinating the entire workflow."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Callable, Any
from urllib.parse import urlparse
import re
from functools import lru_cache
import httpx
from rich.console import Console
import json

from .models import Config, ContentItem, Profile
from .storage.manager import StorageManager
from .services.email import EmailManager
from .services.webhook import WebhookNotifier
from .scrapers.github import GitHubScraper
from .scrapers.hackernews import HackerNewsScraper
from .scrapers.rss import RSSScraper
from .scrapers.reddit import RedditScraper
from .scrapers.telegram import TelegramScraper
from .scrapers.twitter import TwitterScraper
from .ai.client import create_ai_client
from .ai.analyzer import ContentAnalyzer
from .ai.summarizer import DailySummarizer
from .ai.enricher import ContentEnricher
from .ai.cache_manager import CacheManager
from .ai.tokens import get_usage_snapshot


class HorizonOrchestrator:
    """Orchestrates the complete workflow for content aggregation and analysis."""

    # Target number of items to deliver in one briefing.  Both the balancing
    # pass and the downstream hard cap use this constant so they stay in sync.
    _BALANCE_TARGET: int = 10

    _THEME_ALIASES: Dict[str, str] = {
        "full informatique": "informatique",
        "culture generale": "culture generale",
        "culture générale": "culture generale",
        "actualite generale": "actualite generale",
    }

    _THEME_EXPANSIONS: Dict[str, List[str]] = {
        "informatique": [
            "informatique",
            "technology",
            "software",
            "open source",
            "opensource",
            "devtools",
            "developer",
            "programming",
            "linux",
            "security",
            "cyber",
            "github",
            "gouv",
            "gouvernement",
            "lasuite",
            "dinum",
            "numerique-gouv",
            "betagouv",
        ],
        "culture generale": [
            "culture",
            "general culture",
            "culture generale",
            "culture générale",
            "history",
            "philosophy",
            "art",
            "arts",
            "society",
            "education",
            "media",
            "books",
            "literature",
            "cinema",
            "music",
            "science",
            "environment",
            "economy",
            "geopolitics",
            "world",
        ],
        "actualite generale": [
            "actualité",
            "actualite",
            "news",
            "world",
            "politics",
            "policy",
            "society",
            "culture",
            "science",
            "technology",
            "economy",
            "environment",
            "health",
            "education",
        ],
    }

    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        profile: Optional[Profile] = None,
        broadcast_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        """Initialize orchestrator.

        Args:
            config: Application configuration
            storage: Storage manager
            profile: Optional active profile for scoring (if None, uses active or default)
            broadcast_callback: Optional async callback to broadcast progress messages to WebSocket clients
        """
        self.config = config
        self.storage = storage
        self.profile = profile or storage.get_active_profile()
        self.cache_manager = CacheManager(storage)
        self.broadcast_callback = broadcast_callback
        self.console = Console()
        # Safely access optional config subsections (tests may pass MagicMock without attributes)
        email_cfg = getattr(config, "email", None)
        self.email_manager = (
            EmailManager(email_cfg, console=self.console) if email_cfg and getattr(email_cfg, "enabled", False) else None
        )

        webhook_cfg = getattr(config, "webhook", None)
        self.webhook_notifier = (
            WebhookNotifier(webhook_cfg, console=self.console)
            if webhook_cfg and getattr(webhook_cfg, "enabled", False)
            else None
        )
        
        if self.profile:
            self.console.print(f"📊 Profil actif: {self.profile.name} (seuil: {self.profile.ai_score_threshold})")
        else:
            self.console.print("[yellow]⚠️  Aucun profil sélectionné - utilisation des paramètres par défaut[/yellow]")

    def _get_ai_config(self, purpose: str):
        """Return the AI config for a given purpose, with backward-compatible fallback."""
        if purpose == "analysis":
            return getattr(self.config, "analysis_ai", None) or self.config.ai
        if purpose == "enrichment":
            return getattr(self.config, "enrichment_ai", None) or self.config.ai
        return self.config.ai

    async def _broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a progress message to WebSocket clients if callback is available.
        
        Args:
            message: Message dict to broadcast
        """
        if self.broadcast_callback:
            try:
                if asyncio.iscoroutinefunction(self.broadcast_callback):
                    await self.broadcast_callback(message)
                else:
                    self.broadcast_callback(message)
            except Exception as e:
                # Silently ignore broadcast errors - don't block pipeline on WebSocket issues
                self.console.print(f"[dim]ℹ️  WebSocket broadcast failed: {e}[/dim]", style="dim")

    async def run(self, force_hours: int = None, summary_format: str = "html", theme: Optional[str] = None) -> None:
        """Execute the complete workflow.

        Args:
            force_hours: Optional override for time window in hours
        """
        self.console.print("[bold cyan]🌅 Horizon - Démarrage de l'agrégation...[/bold cyan]\n")

        # Check email subscriptions if configured
        if self.email_manager and self.config.email and self.config.email.enabled:
            self.console.print("📧 Vérification des nouveaux abonnements par e-mail...")
            self.email_manager.check_subscriptions(self.storage)

        try:
            # 1. Determine time window
            since = self._determine_time_window(force_hours)
            self.console.print(f"📅 Récupération du contenu depuis : {since.strftime('%Y-%m-%d %H:%M:%S')}\n")

            # 2. Fetch content from all sources
            all_items = await self.fetch_all_sources(since)
            self.console.print(f"📥 {len(all_items)} éléments récupérés de toutes les sources\n")
            
            # Broadcast scraping complete
            await self._broadcast({
                "type": "progress",
                "stage": "scraping",
                "current": len(all_items),
                "total": len(all_items),
                "message": f"Scraped {len(all_items)} items from all sources",
            })

            if not all_items:
                self.console.print("[yellow]Aucun nouveau contenu trouvé. Sortie.[/yellow]")
                return

            # 3. Merge cross-source duplicates (same URL from different sources)
            merged_items = self.merge_cross_source_duplicates(all_items)
            if len(merged_items) < len(all_items):
                self.console.print(
                    f"🔗 {len(all_items) - len(merged_items)} doublons entre sources fusionnés "
                    f"→ {len(merged_items)} éléments uniques\n"
                )

            # Optional theme filtering: keep items whose RSS-configured category,
            # feed name, tags or title match the requested theme string.
            if theme:
                theme_terms = self._theme_terms(theme)
                filtered = []
                for item in merged_items:
                    meta = item.metadata or {}
                    feed_cat = str(meta.get("category", "") or "").lower()
                    feed_name = str(meta.get("feed_name", "") or "").lower()
                    tags = [t_.lower() for t_ in (meta.get("tags") or []) if isinstance(t_, str)]
                    title = (item.title or "").lower()

                    text_chunks = [feed_cat, feed_name, title, *tags]
                    match = any(
                        self._matches_theme_term(chunk, term)
                        for term in theme_terms
                        for chunk in text_chunks
                    )

                    if match:
                        filtered.append(item)

                self.console.print(f"🔎 Filtrage par thème '{theme}' → {len(filtered)} éléments retenus\n")
                merged_items = filtered
                if not merged_items:
                    self.console.print(f"[yellow]Aucun élément trouvé pour le thème '{theme}'. Sortie.[/yellow]")
                    return

            # 4. Analyze with AI
            analyzed_items = await self._analyze_content(merged_items)
            self.console.print(f"🤖 {len(analyzed_items)} éléments analysés avec l'IA\n")
            
            # Broadcast analysis progress
            await self._broadcast({
                "type": "progress",
                "stage": "analyzing",
                "current": len(analyzed_items),
                "total": len(merged_items),
                "message": f"Analyzed {len(analyzed_items)} items with AI",
            })

            # If a theme was requested, also filter based on AI-generated tags
            # and AI summary/title (taxonomy-aware matching).
            if theme:
                theme_terms = self._theme_terms(theme)
                ai_filtered = []
                for item in analyzed_items:
                    ai_tags = [tag.lower() for tag in (item.ai_tags or []) if isinstance(tag, str)]
                    title = (item.title or "").lower()
                    summary = (item.ai_summary or "").lower()

                    text_chunks = [title, summary, *ai_tags]
                    match = any(
                        self._matches_theme_term(chunk, term)
                        for term in theme_terms
                        for chunk in text_chunks
                    )

                    if match:
                        ai_filtered.append(item)

                self.console.print(f"🔎 Filtrage par thème via IA '{theme}' → {len(ai_filtered)} éléments retenus\n")
                analyzed_items = ai_filtered
                if not analyzed_items:
                    self.console.print(f"[yellow]Aucun élément trouvé pour le thème '{theme}' après analyse IA. Sortie.[/yellow]")
                    return

            # 5. Filter by score threshold
            # Use profile threshold if available, otherwise use config default
            threshold = self.profile.ai_score_threshold if self.profile else self.config.filtering.ai_score_threshold
            # Apply trending flags before score filtering
            for item in analyzed_items:
                # Hacker News trending
                if item.source_type.value == "hackernews":
                    score = item.metadata.get("score", 0)
                    if score > 2000:
                        item.is_trending_hn = True
                        item.trending_score += 100
                        item.selection_method = "viral_hn"
                # Reddit trending
                if item.source_type.value == "reddit":
                    comments = item.metadata.get("descendants") or item.metadata.get("num_comments") or 0
                    if comments > 500:
                        item.is_trending_reddit = True
                        item.trending_score += 50
                        if item.selection_method == "ai_only":
                            item.selection_method = "viral_reddit"
                # Default if no trending flags set
                if not getattr(item, "is_trending_hn", False) and not getattr(item, "is_trending_reddit", False):
                    item.selection_method = "ai_only"

            # Now filter by score threshold
            important_items = [
                item for item in analyzed_items
                if item.ai_score and item.ai_score >= threshold
            ]
            important_items.sort(key=lambda x: x.ai_score or 0, reverse=True)

            self.console.print(
                f"⭐️ {len(important_items)} éléments notés ≥ {threshold}\n"
            )
            
            # Broadcast scored items
            for item in important_items:
                await self._broadcast({
                    "type": "item_scored",
                    "item_id": item.id,
                    "title": item.title or "",
                    "source": item.source_type.value,
                    "score": item.ai_score or 0.0,
                    "url": item.url or "",
                    "summary": item.ai_summary or None,
                })

            # 5.5 Semantic deduplication: drop items covering the same topic
            deduped_items = await self.merge_topic_duplicates(important_items)
            if len(deduped_items) < len(important_items):
                self.console.print(
                    f"🧹 {len(important_items) - len(deduped_items)} doublons thématiques supprimés "
                    f"→ {len(deduped_items)} éléments uniques\n"
                )
            important_items = deduped_items

            # Keep the briefing diverse when one source family dominates the ranking.
            balanced_items = self._balance_source_diversity(important_items)
            if len(balanced_items) < len(important_items):
                self.console.print(
                    f"⚖️  Équilibrage des sources: {len(important_items) - len(balanced_items)} éléments retirés "
                    f"pour préserver la diversité\n"
                )
            important_items = balanced_items

            # 5.6 Optional second-stage Twitter reply expansion + targeted re-analysis
            await self._expand_twitter_discussion(important_items)

            # Show per-sub-source selection breakdown
            selected_counts: Dict[str, int] = defaultdict(int)
            for item in important_items:
                key = f"{item.source_type.value}/{self._sub_source_label(item)}"
                selected_counts[key] += 1
            for source_key, count in sorted(selected_counts.items()):
                self.console.print(f"      • {source_key}: {count}")
            self.console.print("")

            # 6. Search related stories + enrich with background knowledge (2nd AI pass)
            await self._enrich_important_items(important_items)

            # 6.5 Re-rank after evidence-based enrichment adjustments and keep top items only.
            important_items.sort(key=lambda x: x.ai_score or 0, reverse=True)
            max_items = self._BALANCE_TARGET
            if len(important_items) > max_items:
                dropped = len(important_items) - max_items
                important_items = important_items[:max_items]
                self.console.print(
                    f"🎯 Qualité: limitation aux {max_items} meilleurs items "
                    f"({dropped} éléments retirés)\n"
                )

            # 6.6 Drop items whose enriched content is still too thin.
            depth_filtered_items = self._filter_shallow_items(important_items)
            if len(depth_filtered_items) < len(important_items):
                removed = len(important_items) - len(depth_filtered_items)
                self.console.print(
                    f"🧱 Filtrage éditorial: {removed} éléments trop courts ou trop pauvres retirés\n"
                )
                if depth_filtered_items:
                    important_items = depth_filtered_items

            # 7. Generate and save bilingual daily summary with tabbed interface (FR/EN onglets)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            ai_client = create_ai_client(self._get_ai_config("enrichment"))
            output_ext = "html" if summary_format not in {"md"} else "md"

            if output_ext == "html":
                # Generate single bilingual HTML with onglets/tabs
                summarizer = DailySummarizer(ai_client)
                summary = await summarizer.generate_bilingual_summary(
                    important_items, today, len(all_items), languages=self.config.ai.languages
                )

                # Save to data/summaries/ with language suffix for compatibility
                summary_path = self.storage.save_daily_summary(
                    today,
                    summary,
                    language="bilingual",
                    extension=output_ext,
                )
                self.console.print(f"💾 Résumé bilingue (FR/EN) enregistré dans : {summary_path}\n")
                
                # Broadcast summary complete
                await self._broadcast({
                    "type": "summary_complete",
                    "profile_name": self.profile.name if self.profile else "default",
                    "language": "bilingual",
                    "path": str(summary_path),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "items_count": len(important_items),
                })

                # Copy to docs/ for GitHub Pages
                try:
                    from pathlib import Path

                    post_filename = f"{today}-summary.{output_ext}"
                    posts_dir = Path("docs/_posts")
                    posts_dir.mkdir(parents=True, exist_ok=True)

                    dest_path = posts_dir / post_filename

                    with open(dest_path, "w", encoding="utf-8") as f:
                        f.write(summary)

                    self.console.print(f"📄 Résumé bilingue copié vers GitHub Pages : {dest_path}\n")
                except Exception as e:
                    self.console.print(f"[yellow]⚠️  Échec de la copie du résumé vers docs/ : {e}[/yellow]\n")

                # Send email and webhook notifications for each language
                if self.email_manager and self.config.email and self.config.email.enabled:
                    for lang in self._get_ai_config("enrichment").languages:
                        self.console.print(f"📧 Envoi du résumé par e-mail {lang.upper()}...")
                        subscribers = self.storage.load_subscribers()
                        subject = f"Horizon Summary ({lang.upper()}) - {today}"
                        self.email_manager.send_daily_summary(summary, subject, subscribers)

                if self.webhook_notifier:
                    for lang in self._get_ai_config("enrichment").languages:
                        # Create a summarizer instance for webhook metadata
                        summarizer_for_webhook = DailySummarizer(ai_client)
                        await self.webhook_notifier.send_daily_summary(
                            summary=summary,
                            important_items=important_items,
                            all_items_count=len(all_items),
                            date=today,
                            lang=lang,
                            summarizer=summarizer_for_webhook,
                        )
            else:
                # For Markdown format, generate one per language (legacy behavior)
                for lang in self._get_ai_config("enrichment").languages:
                    summarizer = DailySummarizer(ai_client)
                    summary = await summarizer.generate_summary(important_items, today, len(all_items), language=lang)

                    # Save to data/summaries/
                    summary_path = self.storage.save_daily_summary(
                        today,
                        summary,
                        language=lang,
                        extension=output_ext,
                    )
                    self.console.print(f"💾 Résumé {lang.upper()} enregistré dans : {summary_path}\n")
                    
                    # Broadcast summary complete for this language
                    await self._broadcast({
                        "type": "summary_complete",
                        "profile_name": self.profile.name if self.profile else "default",
                        "language": lang,
                        "path": str(summary_path),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "items_count": len(important_items),
                    })

                    # Copy to docs/ for GitHub Pages
                    try:
                        from pathlib import Path

                        post_filename = f"{today}-summary-{lang}.{output_ext}"
                        posts_dir = Path("docs/_posts")
                        posts_dir.mkdir(parents=True, exist_ok=True)

                        dest_path = posts_dir / post_filename
                        final_content = summary

                        with open(dest_path, "w", encoding="utf-8") as f:
                            f.write(final_content)

                        self.console.print(f"📄 Résumé {lang.upper()} copié vers GitHub Pages : {dest_path}\n")
                    except Exception as e:
                        self.console.print(f"[yellow]⚠️  Échec de la copie du résumé {lang.upper()} vers docs/ : {e}[/yellow]\n")

                    # Send email if configured
                    if self.email_manager and self.config.email and self.config.email.enabled:
                        self.console.print(f"📧 Envoi du résumé par e-mail {lang.upper()}...")
                        subscribers = self.storage.load_subscribers()
                        subject = f"Horizon Summary ({lang.upper()}) - {today}"
                        self.email_manager.send_daily_summary(summary, subject, subscribers)

                    # Send webhook notification if configured
                    if self.webhook_notifier:
                        await self.webhook_notifier.send_daily_summary(
                            summary=summary,
                            important_items=important_items,
                            all_items_count=len(all_items),
                            date=today,
                            lang=lang,
                            summarizer=summarizer,
                        )


            self.console.print("[bold green]✅ Horizon terminé avec succès ![/bold green]")
            usage = get_usage_snapshot()
            if usage.total_tokens > 0:
                self.console.print(
                    f"\n🧮 Utilisation des jetons pour cette exécution : "
                    f"{usage.total_tokens} jetons "
                    f"(entrée : {usage.total_input_tokens}, sortie : {usage.total_output_tokens})"
                )
                for provider, u in sorted(usage.per_provider.items()):
                    if u.total <= 0:
                        continue
                    self.console.print(
                        f"   • {provider}: {u.total} tokens "
                        f"(in: {u.input_tokens}, out: {u.output_tokens})"
                    )

        except Exception as e:
            self.console.print(f"[bold red]❌ Erreur : {e}[/bold red]")

            # Send webhook failure notification if configured
            if self.webhook_notifier:
                await self.webhook_notifier.send_failure(
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    error_message=str(e),
                )

            raise

    def _determine_time_window(self, force_hours: int = None) -> datetime:
        if force_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=force_hours)
        else:
            hours = self.config.filtering.time_window_hours
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return since

    def _theme_terms(self, theme: str) -> List[str]:
        normalized = theme.strip().lower()
        canonical = self._THEME_ALIASES.get(normalized, normalized)
        expanded = self._THEME_EXPANSIONS.get(canonical, [])
        terms: List[str] = []
        seen = set()
        for term in [normalized, canonical, *expanded]:
            if term not in seen:
                seen.add(term)
                terms.append(term)
        return terms

    def _matches_theme_term(self, text: str, term: str) -> bool:
        if not text or not term:
            return False
        return self._theme_term_pattern(term).search(text) is not None

    @staticmethod
    @lru_cache(maxsize=256)
    def _theme_term_pattern(term: str) -> re.Pattern[str]:
        escaped = re.escape(term)
        pattern = escaped.replace(" ", r"\s+")
        return re.compile(rf"(?<!\w){pattern}(?!\w)")

    async def fetch_all_sources(self, since: datetime) -> List[ContentItem]:
        """Fetch content from all configured sources.

        This is a stable stage entry point for integrations such as MCP.

        Args:
            since: Fetch items published after this time

        Returns:
            List[ContentItem]: All fetched items
        """
        # Use a realistic User-Agent to reduce 403 from some feeds/servers.
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Horizon/0.1 (+https://github.com/horizon)"
        }
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            tasks = []

            # GitHub sources
            if self.config.sources.github:
                github_scraper = GitHubScraper(self.config.sources.github, client)
                tasks.append(self._fetch_with_progress("GitHub", github_scraper, since))

            # Hacker News
            if self.config.sources.hackernews.enabled:
                hn_scraper = HackerNewsScraper(self.config.sources.hackernews, client)
                tasks.append(self._fetch_with_progress("Hacker News", hn_scraper, since))

            # RSS feeds
            if self.config.sources.rss:
                rss_scraper = RSSScraper(self.config.sources.rss, client)
                tasks.append(self._fetch_with_progress("RSS Feeds", rss_scraper, since))

            # Reddit
            if self.config.sources.reddit.enabled:
                reddit_scraper = RedditScraper(self.config.sources.reddit, client)
                tasks.append(self._fetch_with_progress("Reddit", reddit_scraper, since))

            # Telegram
            if self.config.sources.telegram.enabled:
                telegram_scraper = TelegramScraper(self.config.sources.telegram, client)
                tasks.append(self._fetch_with_progress("Telegram", telegram_scraper, since))

            # Twitter
            if self.config.sources.twitter and self.config.sources.twitter.enabled:
                twitter_scraper = TwitterScraper(self.config.sources.twitter, client)
                tasks.append(self._fetch_with_progress("Twitter", twitter_scraper, since))

            # Fetch all concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten results
            all_items = []
            for result in results:
                if isinstance(result, Exception):
                    self.console.print(f"[red]Erreur lors de la récupération de la source : {result}[/red]")
                elif isinstance(result, list):
                    all_items.extend(result)

            return all_items

    async def _fetch_with_progress(self, name: str, scraper, since: datetime) -> List[ContentItem]:
        """Fetch from a scraper with progress indication.

        Args:
            name: Source name for display
            scraper: Scraper instance
            since: Fetch items after this time

        Returns:
            List[ContentItem]: Fetched items
        """
        self.console.print(f"🔍 Récupération de {name}...")
        items = await scraper.fetch(since)
        self.console.print(f"   {len(items)} éléments trouvés depuis {name}")

        # Show per-sub-source breakdown when there are multiple sub-sources
        sub_counts: Dict[str, int] = defaultdict(int)
        for item in items:
            sub_counts[self._sub_source_label(item)] += 1
        if len(sub_counts) > 1:
            for sub, count in sorted(sub_counts.items()):
                self.console.print(f"      • {sub}: {count}")

        return items

    @staticmethod
    def _sub_source_label(item: ContentItem) -> str:
        """Return a human-readable sub-source label for an item."""
        meta = item.metadata
        if meta.get("subreddit"):
            return f"r/{meta['subreddit']}"
        if meta.get("feed_name"):
            return meta["feed_name"]
        if meta.get("channel"):
            return f"@{meta['channel']}"
        if meta.get("repo"):
            return meta["repo"]
        return item.author or "unknown"

    def _balance_source_diversity(self, items: List[ContentItem]) -> List[ContentItem]:
        """Limit how many items from the same source family make it into the final briefing.

        The goal is to keep a diverse reading list when one source or feed is
        over-represented after scoring. This is intentionally lightweight and
        uses existing metadata only.
        """
        if len(items) <= 1:
            return items

        source_type_count = len({item.source_type.value for item in items})
        sub_source_count = len({self._sub_source_label(item) for item in items})

        max_per_source_type = len(items)
        if self.profile and self.profile.max_items_per_source_type is not None:
            max_per_source_type = self.profile.max_items_per_source_type
        elif source_type_count > 1:
            # Proportional cap: each source type gets at most ceil(target / num_types),
            # with a floor of 2 so no source type is silently excluded.
            max_per_source_type = max(2, -(-self._BALANCE_TARGET // source_type_count))

        max_per_sub_source = len(items)
        if self.profile and self.profile.max_items_per_sub_source is not None:
            max_per_sub_source = self.profile.max_items_per_sub_source
        elif sub_source_count > 1:
            # Proportional cap: each individual feed/subreddit/channel gets at most
            # ceil(target / num_sub_sources), with a floor of 2.  This prevents a
            # single feed from monopolising the briefing while still allowing
            # multiple high-scoring items from the same source to survive when the
            # pool is small (e.g. after strict theme + score filtering).
            max_per_sub_source = max(2, -(-self._BALANCE_TARGET // sub_source_count))

        source_type_counts: Dict[str, int] = defaultdict(int)
        sub_source_counts: Dict[str, int] = defaultdict(int)
        balanced: List[ContentItem] = []

        for item in items:
            source_type_key = item.source_type.value
            sub_source_key = f"{source_type_key}/{self._sub_source_label(item)}"

            if source_type_counts[source_type_key] >= max_per_source_type:
                continue
            if sub_source_counts[sub_source_key] >= max_per_sub_source:
                continue

            balanced.append(item)
            source_type_counts[source_type_key] += 1
            sub_source_counts[sub_source_key] += 1

        return balanced

    def merge_cross_source_duplicates(self, items: List[ContentItem]) -> List[ContentItem]:
        """Merge items that point to the same URL from different sources.

        This is a stable stage helper for integrations such as MCP.

        Keeps the item with the richest content and combines metadata.

        Args:
            items: Items to deduplicate

        Returns:
            List[ContentItem]: Deduplicated items
        """
        def normalize_url(url: str) -> str:
            parsed = urlparse(str(url))
            # Strip www prefix, trailing slashes, and fragments
            host = parsed.hostname or ""
            if host.startswith("www."):
                host = host[4:]
            path = parsed.path.rstrip("/")
            return f"{host}{path}"

        # Group by normalized URL
        url_groups: Dict[str, List[ContentItem]] = {}
        for item in items:
            key = normalize_url(str(item.url))
            url_groups.setdefault(key, []).append(item)

        merged = []
        for key, group in url_groups.items():
            if len(group) == 1:
                merged.append(group[0])
                continue

            # Pick the item with the richest content as primary
            primary = max(group, key=lambda x: len(x.content or ""))

            # Merge metadata and source info from other items
            all_sources = set()
            for item in group:
                all_sources.add(item.source_type.value)
                # Merge metadata (engagement, discussion, etc.)
                for mk, mv in item.metadata.items():
                    if mk not in primary.metadata or not primary.metadata[mk]:
                        primary.metadata[mk] = mv

                # Append content (e.g., comments from another source)
                if item is not primary and item.content:
                    if primary.content and item.content not in primary.content:
                        primary.content = (primary.content or "") + f"\n\n--- From {item.source_type.value} ---\n" + item.content

            primary.metadata["merged_sources"] = list(all_sources)
            merged.append(primary)

        return merged

    async def merge_topic_duplicates(self, items: List[ContentItem]) -> List[ContentItem]:
        """Merge items covering the same topic using AI semantic deduplication.

        This is a stable stage helper for integrations such as MCP.

        Sends all item titles, tags, and summaries to AI in a single call.
        Items must already be sorted by ai_score descending so that the first
        item in each duplicate group is always the highest-scored one.
        Content (comments) from duplicate items is merged into the primary.

        Falls back to returning items unchanged if the AI call fails.
        """
        if len(items) <= 1:
            return items

        from .ai.prompts import TOPIC_DEDUP_SYSTEM, TOPIC_DEDUP_USER
        from .ai.utils import parse_json_response

        # Build the item list for the prompt
        lines = []
        for i, item in enumerate(items):
            tags = ", ".join(item.ai_tags) if item.ai_tags else "—"
            summary = item.ai_summary or "—"
            lines.append(f"[{i}] {item.title}\n    Tags: {tags}\n    Summary: {summary}")
        items_text = "\n\n".join(lines)

        try:
            ai_client = create_ai_client(self._get_ai_config("analysis"))
            response = await ai_client.complete(
                system=TOPIC_DEDUP_SYSTEM,
                user=TOPIC_DEDUP_USER.format(items=items_text),
            )
            result = parse_json_response(response)
            if result is None:
                self.console.print("[yellow]  dédup : impossible d'analyser la réponse de l'IA, ignoré[/yellow]")
                return items

            duplicate_groups = result.get("duplicates", [])
        except Exception as e:
            self.console.print(f"[yellow]  dédup : l'appel IA a échoué ({e}), ignoré[/yellow]")
            return items

        if not duplicate_groups:
            return items

        # Build a set of indices to drop (all non-primary duplicates)
        drop_indices: set[int] = set()
        for group in duplicate_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            primary_idx = group[0]
            if primary_idx < 0 or primary_idx >= len(items):
                continue
            primary = items[primary_idx]
            for dup_idx in group[1:]:
                if not isinstance(dup_idx, int) or dup_idx < 0 or dup_idx >= len(items):
                    continue
                if dup_idx == primary_idx:
                    continue
                dup = items[dup_idx]
                # Merge comments/content from the duplicate into the primary
                if dup.content:
                    if not primary.content or dup.content not in primary.content:
                        label = dup.source_type.value
                        primary.content = (primary.content or "") + f"\n\n--- From {label} ---\n{dup.content}"
                self.console.print(
                    f"   [dim]dédup : conserver [{primary_idx}] {primary.title}[/dim]\n"
                    f"   [dim]        supprimer [{dup_idx}] {dup.title}[/dim]"
                )
                drop_indices.add(dup_idx)

        return [item for i, item in enumerate(items) if i not in drop_indices]

    async def _expand_twitter_discussion(self, items: List[ContentItem]) -> None:
        """Second-stage: fetch reply text for important Twitter items and re-analyze.

        Only runs when sources.twitter.fetch_reply_text is True.
        Bounded by max_tweets_to_expand to control cost.
        """
        tw_cfg = self.config.sources.twitter
        if not tw_cfg or not tw_cfg.enabled or not tw_cfg.fetch_reply_text:
            return

        from .models import SourceType

        twitter_items = [
            item for item in items
            if item.source_type == SourceType.TWITTER
        ][:tw_cfg.max_tweets_to_expand]

        if not twitter_items:
            return

        self.console.print(
            f"💬 Récupération du texte des réponses pour {len(twitter_items)} éléments Twitter..."
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Horizon/0.1 (+https://github.com/horizon)"
        }
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            scraper = TwitterScraper(tw_cfg, client)
            expanded = []
            for item in twitter_items:
                try:
                    reply_lines = await scraper.fetch_replies_for_item(item)
                    if TwitterScraper.append_discussion_content(item, reply_lines):
                        expanded.append(item)
                        self.console.print(
                            f"   💬 {len(reply_lines)} réponses ajoutées à : {item.title[:60]}"
                        )
                except Exception as exc:
                    self.console.print(
                        f"   [yellow]⚠️  Échec de la récupération des réponses pour {item.id} : {exc}[/yellow]"
                    )

        if not expanded:
            return

        self.console.print(
            f"   Réanalyse de {len(expanded)} éléments Twitter avec le contexte des réponses...\n"
        )
        ai_client = create_ai_client(self._get_ai_config("analysis"))
        analyzer = ContentAnalyzer(ai_client)
        await analyzer.analyze_batch(expanded)

    async def _enrich_important_items(self, items: List[ContentItem]) -> None:
        """Enrich items with background knowledge (2nd AI pass).

        For each item that passed the score threshold, call AI to generate
        background knowledge based on the item's actual content.

        Args:
            items: Important items to enrich (modified in-place)
        """
        if not items:
            return

        self.console.print("📚 Enrichissement avec des connaissances de base...")
        ai_client = create_ai_client(self._get_ai_config("enrichment"))
        enricher = ContentEnricher(ai_client)
        await enricher.enrich_batch(items)
        self.console.print(f"   {len(items)} éléments enrichis\n")

    @staticmethod
    def _has_sufficient_editorial_depth(item: ContentItem) -> bool:
        """Return True when an enriched item is substantive enough to publish."""
        meta = item.metadata

        text_parts = [
            str(item.ai_summary or "").strip(),
            str(meta.get("detailed_summary_en") or "").strip(),
            str(meta.get("detailed_summary_fr") or "").strip(),
            str(meta.get("background_en") or "").strip(),
            str(meta.get("background_fr") or "").strip(),
        ]
        combined_length = sum(len(part) for part in text_parts)

        sources = meta.get("sources") or []
        has_structure = any(len(part) >= 80 for part in text_parts[1:])
        has_multiple_sections = sum(bool(part) for part in text_parts[1:]) >= 2
        has_sources = len(sources) >= 1

        return combined_length >= 160 and has_structure and (has_sources or has_multiple_sections)

    def _filter_shallow_items(self, items: List[ContentItem]) -> List[ContentItem]:
        """Keep the richest items, but fall back to the original list if all are thin."""
        filtered = [item for item in items if self._has_sufficient_editorial_depth(item)]
        return filtered or items

    async def _analyze_content(self, items: List[ContentItem]) -> List[ContentItem]:
        """Analyze content items with AI.

        Args:
            items: Items to analyze

        Returns:
            List[ContentItem]: Analyzed items
        """
        self.console.print("🤖 Analyse du contenu avec l'IA...")

        ai_client = create_ai_client(self._get_ai_config("analysis"))
        analyzer = ContentAnalyzer(ai_client, profile=self.profile)

        return await analyzer.analyze_batch(items)

    async def _generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary.

        Args:
            items: Important items to include (already enriched with background/related)
            date: Date string
            total_fetched: Total items fetched
            language: Output language ("en" or "zh")

        Returns:
            str: Markdown summary
        """
        self.console.print("📝 Génération du résumé quotidien...")

        ai_client = create_ai_client(self._get_ai_config("enrichment"))
        summarizer = DailySummarizer(ai_client)

        return await summarizer.generate_summary(items, date, total_fetched, language=language)

    def _wrap_html_document(self, html_fragment: str, language: str, date: str) -> str:
        """Wrap HTML fragment in a complete HTML document with proper doctype and head.

        Args:
            html_fragment: The HTML content generated by the summarizer
            language: Language code (en, fr, etc.)
            date: Date string for the page

        Returns:
            str: Complete HTML document
        """
        lang_code = language if language in ["en", "fr"] else "en"
        title = f"Horizon Daily - {date}" if lang_code == "en" else f"Horizon Quotidien - {date}"

        return f"""<!DOCTYPE html>
<html lang="{lang_code}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <meta name="description" content="Daily news briefing curated by AI">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Iowan+Old+Style&display=swap" rel="stylesheet">
</head>
<body>
{html_fragment}
</body>
</html>"""
