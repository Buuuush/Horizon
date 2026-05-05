"""Content analysis using AI."""

import asyncio
import json
import re
from typing import List, Optional
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

from .client import AIClient
from .prompts import CONTENT_ANALYSIS_SYSTEM, CONTENT_ANALYSIS_USER
from .utils import parse_json_response
from ..models import ContentItem

DEFAULT_THROTTLE_SEC = 0.0


class ContentAnalyzer:
    """Analyzes content items using AI to determine importance."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client

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

        throttle_sec = self._get_throttle_sec()
        # Limit to 3 concurrent analysis to avoid API rate limiting
        semaphore = asyncio.Semaphore(3)

        async def analyze_with_semaphore(item):
            async with semaphore:
                try:
                    await self._analyze_item(item)
                    return item
                except Exception as e:
                    root = e
                    if isinstance(root, RetryError):
                        root = root.last_attempt.exception()
                    while getattr(root, "__cause__", None) is not None:
                        root = root.__cause__
                    status_code = getattr(root, "status_code", None)
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
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10)
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
                content_section = f"Content: {main.strip()[:800]}"
            else:
                content_section = f"Content: {content_text[:1000]}"

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
            system=CONTENT_ANALYSIS_SYSTEM,
            user=user_prompt,
        )

        # Parse JSON response with robust fallback
        result = self._parse_json_response(response)
        if result is None:
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
