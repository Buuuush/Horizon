"""Content enrichment using AI (second-pass analysis).

For items that pass the score threshold, this module:
1. Searches the web for relevant context (via DuckDuckGo)
2. Feeds search results + item content to AI to generate grounded background knowledge
"""

import asyncio
import json
import re
import sys
import os
from typing import List, Optional
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from ddgs import DDGS

from .client import AIClient
from .prompts import (
    CONCEPT_EXTRACTION_SYSTEM, CONCEPT_EXTRACTION_USER,
    CONTENT_ENRICHMENT_SYSTEM, CONTENT_ENRICHMENT_USER,
)
from .utils import parse_json_response
from ..models import ContentItem


class ContentEnricher:
    """Enriches high-scoring content items with background knowledge."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client
        self.enriched_cache = {}  # Cache of enriched URLs to avoid re-enriching

    async def enrich_batch(self, items: List[ContentItem]) -> None:
        """Enrich items in-place with background knowledge.

        Args:
            items: Content items to enrich (modified in-place)
        """
        if not items:
            return

        # Limit to 6 concurrent enrichments (higher concurrency on fast CPUs)
        semaphore = asyncio.Semaphore(6)

        async def enrich_with_semaphore(item):
            async with semaphore:
                # Check cache first
                url_key = str(item.url)
                if url_key in self.enriched_cache:
                    # Apply cached enrichment metadata
                    item.metadata.update(self.enriched_cache[url_key])
                    return
                
                try:
                    await self._enrich_item(item)
                    # Cache the enrichment metadata
                    self.enriched_cache[url_key] = dict(item.metadata)
                except Exception as e:
                    print(f"Erreur lors de l'enrichissement de l'élément {item.id} : {e}")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Enriching", total=len(items))

            async def track_and_enrich(item):
                await enrich_with_semaphore(item)
                progress.advance(task)

            await asyncio.gather(*[track_and_enrich(item) for item in items])

    async def _web_search(self, query: str, max_results: int = 3) -> list:
        """Search the web for context via DuckDuckGo.

        Returns:
            List of dicts with keys: title, url, body
        """
        try:
            # Suppress primp "Impersonate ... does not exist" stderr warning
            stderr = sys.stderr
            sys.stderr = open(os.devnull, "w")
            try:
                ddgs = DDGS()
                results = ddgs.text(query, max_results=max_results)
            finally:
                sys.stderr.close()
                sys.stderr = stderr
        except Exception:
            return []

        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "body": r.get("body", "")}
            for r in (results or [])
        ]

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        """Try multiple strategies to extract a JSON object from an AI response.

        Returns the parsed dict, or None if all strategies fail.
        """
        return parse_json_response(response)

    async def _extract_concepts(self, item: ContentItem, content_text: str) -> List[str]:
        """Ask AI to identify concepts that need explanation.

        Args:
            item: Content item
            content_text: Extracted content text

        Returns:
            List of search queries for concepts that need explanation
        """
        user_prompt = CONCEPT_EXTRACTION_USER.format(
            title=item.title,
            summary=item.ai_summary or item.title,
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text[:1000],
        )

        try:
            response = await self.client.complete(
                system=CONCEPT_EXTRACTION_SYSTEM,
                user=user_prompt,
            )
            result = self._parse_json_response(response)
            if result is None:
                return []
            queries = result.get("queries", [])
            return queries[:1]
        except Exception:
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10)
    )
    async def _enrich_item(self, item: ContentItem) -> None:
        """Enrich a single item with background knowledge.

        Steps:
        1. Ask AI which concepts in the news need explanation
        2. Search the web for those concepts
        3. Ask AI to generate background based on search results

        Args:
            item: Content item to enrich (modified in-place via metadata)
        """
        # Extract content text and comments separately
        content_text = ""
        comments_text = ""
        if item.content:
            if "--- Top Comments ---" in item.content:
                main, comments_part = item.content.split("--- Top Comments ---", 1)
                content_text = main.strip()[:4000]
                comments_text = comments_part.strip()[:2000]
            else:
                content_text = item.content[:4000]

        # Step 1: AI identifies concepts to explain
        queries = await self._extract_concepts(item, content_text)

        # Step 2: Search web for each concept (in parallel)
        all_results = []
        web_sections = []
        if queries:
            search_results = await asyncio.gather(
                *[self._web_search(query) for query in queries],
                return_exceptions=True
            )
            for query, results in zip(queries, search_results):
                if isinstance(results, Exception):
                    continue
                if results:
                    all_results.extend(results)
                    lines = [f"- [{r['title']}]({r['url']}): {r['body']}" for r in results]
                    web_sections.append(f"**{query}:**\n" + "\n".join(lines))
        web_context = "\n\n".join(web_sections) if web_sections else ""

        # Index of available URLs for citation validation
        available_urls = {r["url"]: r["title"] for r in all_results if r.get("url")}

        # Step 3: AI generates background grounded in search results
        user_prompt = CONTENT_ENRICHMENT_USER.format(
            title=item.title,
            url=str(item.url),
            summary=item.ai_summary or item.title,
            score=item.ai_score or 0,
            reason=item.ai_reason or "",
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text,
            comments_section=f"\n**Community Comments:**\n{comments_text}" if comments_text else "",
            web_context=web_context or "No web search results available.",
        )

        response = await self.client.complete(
            system=CONTENT_ENRICHMENT_SYSTEM,
            user=user_prompt,
        )

        # Parse JSON response with robust fallback
        result = self._parse_json_response(response)
        if result is None:
            # Gracefully degrade: skip enrichment instead of raising
            # (raising would trigger retries that won't help with a parse error)
            print(f"Avertissement : impossible d'analyser la réponse d'enrichissement pour {item.id}, enrichissement ignoré")
            return

        # Combine structured sub-fields into per-language detailed_summary
        for lang in ("en", "fr"):
            # Title may be a dict like {"text": "..."} or a plain string
            title_key = f"title_{lang}"
            if title_key in result:
                val = result.get(title_key)
                if isinstance(val, dict):
                    item.metadata[title_key] = val.get("text", "") or str(val)
                else:
                    item.metadata[title_key] = str(val or "")

            # Aggregate descriptive fields into a detailed summary
            parts = []
            for field in ("whats_new", "why_it_matters", "key_details"):
                key = f"{field}_{lang}"
                raw = result.get(key, "")
                if isinstance(raw, dict):
                    text = raw.get("text", "")
                else:
                    text = str(raw or "")
                text = text.strip()
                if text:
                    parts.append(text)
            if parts:
                item.metadata[f"detailed_summary_{lang}"] = " ".join(parts)

            # Background and community discussion can also be dicts or strings
            bg_key = f"background_{lang}"
            if bg_key in result:
                val = result.get(bg_key)
                if isinstance(val, dict):
                    item.metadata[bg_key] = val.get("text", "") or str(val)
                else:
                    item.metadata[bg_key] = str(val or "")

            disc_key = f"community_discussion_{lang}"
            if disc_key in result:
                val = result.get(disc_key)
                if isinstance(val, dict):
                    item.metadata[disc_key] = val.get("text", "") or str(val)
                else:
                    item.metadata[disc_key] = str(val or "")

        # Store citation sources — only URLs that actually came from our search results
        if result.get("sources") and available_urls:
            valid = [
                {"url": u, "title": available_urls[u]}
                for u in result["sources"]
                if u in available_urls
            ]
            if valid:
                item.metadata["sources"] = valid

        self._apply_evidence_adjustment(item, result)

        # Backward-compatible fallback fields (English as default)
        item.metadata["detailed_summary"] = item.metadata.get("detailed_summary_en", "")
        item.metadata["background"] = item.metadata.get("background_en", "")
        item.metadata["community_discussion"] = item.metadata.get("community_discussion_en", "")

    @staticmethod
    def _looks_sensational(title: str) -> bool:
        t = (title or "").lower()
        patterns = [
            r"\b(shocking|you won[’']t believe|destroyed|annihilat|secret|exposed|mind[- ]blowing)\b",
            r"\b(incroyable|choc|scandale|révélé|hallucinant|explosif)\b",
            r"\b(breaking)\b",
        ]
        return any(re.search(p, t) for p in patterns) or title.count("!") >= 2

    def _apply_evidence_adjustment(self, item: ContentItem, result: dict) -> None:
        """Adjust ai_score using evidence quality from enrichment results."""
        sources = item.metadata.get("sources") or []
        domains = {
            (urlparse(str(s.get("url"))).hostname or "").lower().lstrip("www.")
            for s in sources
            if s.get("url")
        }
        domains = {d for d in domains if d}

        evidence_strength = result.get("evidence_strength")
        try:
            evidence_strength = float(evidence_strength) if evidence_strength is not None else None
        except Exception:
            evidence_strength = None

        score_delta = 0.0
        if len(domains) >= 2:
            score_delta += 0.7
        elif len(domains) == 1:
            score_delta += 0.2
        else:
            score_delta -= 0.9

        if evidence_strength is not None:
            if evidence_strength >= 7.0:
                score_delta += 0.3
            elif evidence_strength <= 4.0:
                score_delta -= 0.4

        if self._looks_sensational(item.title):
            if len(domains) == 0:
                score_delta -= 0.8
            elif len(domains) == 1:
                score_delta -= 0.4

        base = float(item.ai_score or 0.0)
        adjusted = max(0.0, min(10.0, base + score_delta))
        item.ai_score = adjusted
        item.metadata["evidence_adjustment"] = {
            "delta": round(score_delta, 3),
            "source_count": len(sources),
            "independent_domain_count": len(domains),
            "evidence_strength": evidence_strength,
            "sensational_title": self._looks_sensational(item.title),
            "score_before": base,
            "score_after": adjusted,
        }
        if score_delta < 0:
            item.ai_reason = (item.ai_reason or "") + " | Penalized for weak evidence."
        elif score_delta > 0:
            item.ai_reason = (item.ai_reason or "") + " | Boosted by corroborating evidence."
