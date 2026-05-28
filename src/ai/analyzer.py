"""Content analysis using AI."""

import asyncio
import json
import re
import sys
import random
from typing import List, Optional
from tenacity import RetryError, retry, stop_after_attempt, retry_if_exception
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from collections import Counter
from math import log2
from urllib.parse import urlparse

from .client import AIClient
from .prompts import CONTENT_ANALYSIS_SYSTEM, CONTENT_ANALYSIS_USER, SCORING_PROMPTS_BY_SOURCE
from .utils import parse_json_response
from ..models import ContentItem, Profile

DEFAULT_THROTTLE_SEC = 0.0


def _unwrap_exception(exc: Exception) -> Exception:
    """Return the deepest cause for robust status-code detection."""
    root = exc
    if isinstance(root, RetryError):
        root = root.last_attempt.exception()
    while getattr(root, "__cause__", None) is not None:
        root = root.__cause__
    return root


def _extract_status_code(exc: Exception) -> Optional[int]:
    """Extract HTTP status code from OpenAI-compatible exceptions when available."""
    root = _unwrap_exception(exc)
    status_code = getattr(root, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(root, "response", None)
    if response is not None:
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            return response_status

    return None


def _extract_retry_after_seconds(exc: Exception) -> Optional[float]:
    """Best-effort extraction of Retry-After header from provider response."""
    root = _unwrap_exception(exc)
    response = getattr(root, "response", None)
    if response is None:
        return None

    headers = getattr(response, "headers", None)
    if not headers:
        return None

    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    if retry_after is None:
        return None

    try:
        value = float(retry_after)
    except (TypeError, ValueError):
        return None

    if value <= 0:
        return None
    return value


def _is_retryable_analysis_exception(exc: Exception) -> bool:
    """Retry only for transient API failures (rate-limit and 5xx)."""
    status_code = _extract_status_code(exc)
    if status_code is None:
        return False
    return status_code == 429 or status_code >= 500


def _analysis_wait_seconds(retry_state) -> float:
    """Adaptive wait: prefer Retry-After, otherwise exponential backoff + jitter."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc:
        retry_after = _extract_retry_after_seconds(exc)
        if retry_after is not None:
            return min(max(retry_after, 1.0), 120.0)

    attempt = retry_state.attempt_number
    # 2, 4, 8, 16, 32 ... capped at 60s, with small jitter to avoid herd effects.
    base = min(2 ** attempt, 60)
    jitter = random.uniform(0.0, 1.5)
    return base + jitter


class ContentAnalyzer:
    """Analyzes content items using AI to determine importance."""

    def __init__(self, ai_client: AIClient, profile: Optional[Profile] = None):
        self.client = ai_client
        self.profile = profile

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        """Try multiple strategies to extract a JSON object from an AI response.

        Returns the parsed dict, or None if all strategies fail.
        """
        return parse_json_response(response)

    def _get_throttle_sec(self) -> float:
        """Return the configured inter-item throttle, clamped to zero or above."""
        config = getattr(self.client, "config", None)
        throttle_sec = getattr(config, "throttle_sec", DEFAULT_THROTTLE_SEC)
        return max(throttle_sec, 0.0)

    async def analyze_batch(self, items: List[ContentItem]) -> List[ContentItem]:
        if not items:
            return []

        # Pre-compute simple duplication and entropy heuristics across batch
        def _normalize_title(t: str) -> str:
            if not t:
                return ""
            s = re.sub(r"\W+", " ", t.lower()).strip()
            return s

        titles = [_normalize_title(i.title or "") for i in items]
        title_counts = Counter(titles)

        def _shannon_entropy(text: str) -> float:
            if not text:
                return 0.0
            freqs = Counter(text)
            length = len(text)
            ent = 0.0
            for _c, cnt in freqs.items():
                p = cnt / length
                ent -= p * log2(p)
            return ent

        for itm, norm in zip(items, titles):
            itm.metadata.setdefault("heuristics", {})
            itm.metadata["heuristics"]["dup_count"] = int(title_counts.get(norm, 0))
            itm.metadata["heuristics"]["title_entropy"] = float(_shannon_entropy(itm.title or ""))

        throttle_sec = self._get_throttle_sec()
        # Limit to 3 concurrent analysis to avoid API rate limiting
        semaphore = asyncio.Semaphore(3)

        async def analyze_with_semaphore(item):
            async with semaphore:
                try:
                    await self._analyze_item(item)
                    return item
                except Exception as e:
                    root = _unwrap_exception(e)
                    status_code = _extract_status_code(e)
                    message = str(root)
                    if status_code is not None:
                        print(f"Erreur lors de l'analyse de l'élément {item.id} : {type(root).__name__} (statut {status_code}) {message}")
                    else:
                        print(f"Erreur lors de l'analyse de l'élément {item.id} : {type(root).__name__} {message}")
                    item.ai_score = 0.0
                    item.ai_reason = "Analyse échouée"
                    item.ai_summary = item.title
                    return item

        # When throttling is configured, analyze sequentially and sleep between items
        # to avoid bursty API traffic and satisfy deterministic behavior.
        if throttle_sec > 0:
            analyzed_items = []
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                transient=True,
            ) as progress:
                task = progress.add_task("Analyse", total=len(items))
                for idx, item in enumerate(items):
                    analyzed = await analyze_with_semaphore(item)
                    analyzed_items.append(analyzed)
                    progress.advance(task)
                    if idx < len(items) - 1:
                        await asyncio.sleep(throttle_sec)
            return analyzed_items

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Analyse", total=len(items))

            async def track_and_analyze(item):
                result = await analyze_with_semaphore(item)
                progress.advance(task)
                return result

            analyzed_items = await asyncio.gather(*[track_and_analyze(item) for item in items])

        return analyzed_items

    @retry(
        stop=stop_after_attempt(7),
        wait=_analysis_wait_seconds,
        retry=retry_if_exception(_is_retryable_analysis_exception),
    )
    async def _analyze_item(self, item: ContentItem) -> None:
        """Analyze a single content item.

        Args:
            item: Content item to analyze (modified in-place)
        """
        # Prepare content section
        content_section = ""
        if item.content:
            # Split off comments if present
            content_text = item.content
            if "--- Top Comments ---" in content_text:
                main, comments_part = content_text.split("--- Top Comments ---", 1)
                content_section = f"Content: {main.strip()[:1200]}"
            else:
                content_section = f"Content: {content_text[:1500]}"

        # Prepare discussion section (comments, engagement)
        discussion_parts = []
        if item.content and "--- Top Comments ---" in item.content:
            comments_part = item.content.split("--- Top Comments ---", 1)[1]
            discussion_parts.append(f"Community Comments:\n{comments_part[:1500]}")

        meta = item.metadata
        engagement_items = []
        if meta.get("score"):
            engagement_items.append(f"score: {meta['score']}")
        if meta.get("descendants"):
            engagement_items.append(f"{meta['descendants']} comments")
        if meta.get("favorite_count"):
            engagement_items.append(f"{meta['favorite_count']} likes")
        if meta.get("retweet_count"):
            engagement_items.append(f"{meta['retweet_count']} retweets")
        if meta.get("reply_count"):
            engagement_items.append(f"{meta['reply_count']} replies")
        if meta.get("views"):
            engagement_items.append(f"{meta['views']} views")
        if meta.get("bookmarks"):
            engagement_items.append(f"{meta['bookmarks']} bookmarks")
        if meta.get("upvote_ratio"):
            engagement_items.append(f"upvote ratio: {meta['upvote_ratio']:.0%}")
        if engagement_items:
            discussion_parts.append(f"Engagement: {', '.join(engagement_items)}")
        if meta.get("discussion_url"):
            discussion_parts.append(f"Discussion: {meta['discussion_url']}")
        if meta.get("community_note"):
            discussion_parts.append(f"Community Note: {meta['community_note']}")

        discussion_section = "\n".join(discussion_parts) if discussion_parts else ""

        # Determine which system prompt to use based on profile or source
        system_prompt = CONTENT_ANALYSIS_SYSTEM
        if self.profile and item.source_type.value in self.profile.per_source_prompts:
            # Use custom prompt from profile
            system_prompt = self.profile.per_source_prompts[item.source_type.value]
        elif item.source_type.value in SCORING_PROMPTS_BY_SOURCE:
            # Use built-in per-source prompt
            system_prompt = SCORING_PROMPTS_BY_SOURCE[item.source_type.value]

        # Generate user prompt
        user_prompt = CONTENT_ANALYSIS_USER.format(
            title=item.title,
            source=f"{item.source_type.value}",
            author=item.author or "Unknown",
            url=str(item.url),
            content_section=content_section,
            discussion_section=discussion_section
        )

        # Get AI completion
        response = await self.client.complete(
            system=system_prompt,
            user=user_prompt,
        )

        # Debug: log raw response to data/ volume (persists between containers)
        debug_log_path = "data/ai_debug.log"
        try:
            with open(debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{item.id}] Response length: {len(response or '')}\n")
                if response:
                    preview = (response or '')[:400]
                    f.write(f"Preview: {preview}\n")
                else:
                    f.write("Response was empty/None\n")
        except Exception as e:
            pass  # Silently ignore debug logging errors

        # Parse JSON response with robust fallback
        result = self._parse_json_response(response)
        if result is None:
            # Emit the raw response to stdout for debugging and tests that
            # expect to see the unparsed AI output followed by a warning.
            try:
                print(f"Réponse brute pour {item.id}: {response}")
            except Exception:
                # Ensure we never raise while trying to log debug info
                pass
            print(f"Avertissement : impossible d'analyser la réponse d'analyse pour {item.id}, valeurs par défaut utilisées")
            item.ai_score = 0.0
            item.ai_reason = "Échec de l'analyse de la réponse"
            item.ai_summary = item.title
            item.ai_tags = []
            return

        # Update item with analysis results
        base_score = float(result.get("score", 0))
        source_reliability = float(result.get("source_reliability", 0))
        explanatory_value = float(result.get("explanatory_value", 0))
        novelty = float(result.get("novelty", 0))
        potential_impact = float(result.get("potential_impact", 0))
        uncertainty = float(result.get("uncertainty", 5))

        # Blend importance with explicit quality dimensions.
        # Uncertainty is inverted so lower uncertainty increases quality.
        quality_score = (
            0.25 * source_reliability
            + 0.20 * explanatory_value
            + 0.20 * novelty
            + 0.25 * potential_impact
            + 0.10 * (10.0 - uncertainty)
        )
        final_score = max(0.0, min(10.0, 0.65 * base_score + 0.35 * quality_score))

        item.ai_score = final_score
        item.ai_reason = result.get("reason", "")
        item.ai_summary = result.get("summary", item.title)
        item.ai_tags = result.get("tags", [])
        item.metadata["ai_quality"] = {
            "base_score": base_score,
            "source_reliability": source_reliability,
            "explanatory_value": explanatory_value,
            "novelty": novelty,
            "potential_impact": potential_impact,
            "uncertainty": uncertainty,
            "quality_score": quality_score,
            "final_score": final_score,
        }

        # --- Post-adjustments to better match editorial goals ---
        # Apply host penalties (mainstream outlets) and topic boosts (science, history, etc.)
        try:
            parsed = urlparse(str(item.url))
            host = (parsed.hostname or "").lstrip("www.")
        except Exception:
            host = ""

        # Built-in penalized hosts (fraction to reduce score)
        PENALIZED_HOSTS = {
            "bloomberg.com": 0.25,
            "reuters.com": 0.25,
            "ft.com": 0.22,
            "bbc.com": 0.20,
            "france24.com": 0.18,
            "nytimes.com": 0.22,
            "aljazeera.com": 0.18,
            "theguardian.com": 0.18,
        }
        # Merge per-profile preferences if present
        if self.profile and getattr(self.profile, "penalized_hosts", None):
            try:
                PENALIZED_HOSTS.update({k.lower(): float(v) for k, v in self.profile.penalized_hosts.items()})
            except Exception:
                pass

        host_penalty = float(PENALIZED_HOSTS.get(host, 0.0))
        if host_penalty and host_penalty > 0:
            final_score = max(0.0, final_score * (1.0 - host_penalty))

        # If anti_mainstream_bonus is enabled in the global config, amplify
        # penalties for mainstream hosts and increase topic boosts.
        try:
            cfg = getattr(self.client, "config", None)
            anti_flag = False
            if cfg and getattr(cfg, "filtering", None):
                anti_flag = bool(getattr(cfg.filtering, "anti_mainstream_bonus", False))
        except Exception:
            anti_flag = False

        if anti_flag and host_penalty:
            # apply extra 10% penalty on top of declared host_penalty
            final_score = max(0.0, final_score * (1.0 - (host_penalty * 1.10)))

        # Topic boosts (default editorial preferences)
        # Strong default boosts for non-mainstream, culturally rich topics
        DEFAULT_TOPIC_BOOSTS = {
            "science": 0.25,
            "archaeology": 0.25,
            "history": 0.22,
            "energy": 0.18,
            "linguistics": 0.22,
            "climate": 0.22,
            "urbanism": 0.20,
            "math": 0.18,
            "infrastructure": 0.20,
            "agriculture": 0.18,
            "demography": 0.18,
            "culture": 0.18,
            "archaeology": 0.25,
            "space": 0.20,
            "ecology": 0.20,
            "linguistics": 0.22,
            "internet culture": 0.18,
            "web culture": 0.18,
        }
        topic_boosts = DEFAULT_TOPIC_BOOSTS.copy()
        if self.profile and getattr(self.profile, "topic_boosts", None):
            try:
                profile_boosts = {k.lower(): float(v) for k, v in self.profile.topic_boosts.items()}
                topic_boosts.update(profile_boosts)
            except Exception:
                pass

        if item.ai_tags:
            for tag in item.ai_tags:
                t = str(tag).lower()
                if t in topic_boosts and topic_boosts[t] > 0:
                    boost = float(topic_boosts[t])
                    if anti_flag:
                        boost = boost * 1.5
                    final_score = min(10.0, final_score * (1.0 + boost))

        # Penalize items whose AI tags fall into clearly mainstream categories
        PENALIZED_TAGS = {
            "politics": 0.20,
            "geopolitics": 0.20,
            "market": 0.20,
            "finance": 0.20,
            "economy": 0.18,
            "breaking": 0.25,
        }
        if item.ai_tags:
            for tag in item.ai_tags:
                tt = str(tag).lower()
                if tt in PENALIZED_TAGS:
                    pen = float(PENALIZED_TAGS[tt])
                    if anti_flag:
                        pen = min(0.9, pen * 1.25)
                    final_score = max(0.0, final_score * (1.0 - pen))

        # Penalize clearly "breaking" / live updates which tend to age quickly
        title_l = (item.title or "").lower()
        BREAKING_KEYWORDS = ["breaking", "live", "just in", "update", "reported", "attack", "strike", "drones"]
        if any(k in title_l for k in BREAKING_KEYWORDS) or any(k in (tag.lower() for tag in (item.ai_tags or [])) for k in ["breaking", "live"]):
            final_score = final_score * 0.85

        # Penalize generic market headlines that lack explanatory value / novelty
        GENERIC_MARKET_KEYWORDS = ["earnings", "profits", "beat forecasts", "beat expectations", "stocks", "market", "record run"]
        if any(k in title_l for k in GENERIC_MARKET_KEYWORDS) and explanatory_value < 4 and novelty < 3:
            final_score = final_score * 0.65

        # --- Rarity / duplication heuristics ---
        try:
            heur = item.metadata.get("heuristics", {})
            dup_count = int(heur.get("dup_count", 1))
            title_entropy = float(heur.get("title_entropy", 0.0))
        except Exception:
            dup_count = 1
            title_entropy = 0.0

        # If the title appears only once in the batch and has high entropy, boost it
        if dup_count <= 1 and title_entropy > 3.5:
            # small rarity bonus
            bonus = 1.10 if anti_flag else 1.05
            final_score = min(10.0, final_score * bonus)

        # If many duplicates, downrank to prefer unique items
        if dup_count > 2:
            final_score = final_score * 0.75

        # Rebound final score into allowed range and store final quality
        final_score = max(0.0, min(10.0, final_score))
        item.ai_score = final_score
        # Append a short note to the reason to make adjustments visible
        adjustments = []
        if host_penalty:
            adjustments.append(f"host_penalty={host_penalty:.2f}")
        # report top matched topic boosts
        matched_boosts = [t for t in (item.ai_tags or []) if t.lower() in topic_boosts]
        if matched_boosts:
            adjustments.append(f"topic_boosts={','.join(matched_boosts)}")
        if adjustments:
            item.ai_reason = (item.ai_reason or "") + " | adjustments: " + ",".join(adjustments)
        # Update stored metric
        item.metadata["ai_quality"]["final_score"] = final_score
