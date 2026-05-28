"""Content enrichment using AI (second-pass analysis).

For items that pass the score threshold, this module:
1. Searches the web for relevant context (via DuckDuckGo)
2. Feeds search results + item content to AI to generate grounded background knowledge
3. Produces a full editorial HTML article (same quality as a hand-crafted news piece)
"""

import asyncio
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


# ──────────────────────────────────────────────────────────────────────────────
# HTML article template (mirrors the reference article's layout & CSS)
# ──────────────────────────────────────────────────────────────────────────────

ARTICLE_CSS = """
body {
    font-family: Georgia, serif;
    max-width: 900px;
    margin: auto;
    padding: 40px 20px;
    line-height: 1.8;
    color: #222;
    background: #fafafa;
}
article {
    background: white;
    padding: 40px;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}
header {
    margin-bottom: 40px;
    border-bottom: 1px solid #ddd;
    padding-bottom: 20px;
}
h1 {
    font-size: 2.4rem;
    margin-bottom: 10px;
    line-height: 1.2;
}
.meta {
    color: #666;
    font-size: 0.95rem;
}
.lead {
    font-size: 1.2rem;
    color: #444;
    margin-top: 20px;
}
h2 {
    margin-top: 40px;
    font-size: 1.7rem;
    border-left: 4px solid #222;
    padding-left: 12px;
}
blockquote {
    margin: 30px 0;
    padding: 20px;
    border-left: 5px solid #555;
    background: #f3f3f3;
    font-style: italic;
}
ul {
    padding-left: 25px;
}
footer {
    margin-top: 50px;
    border-top: 1px solid #ddd;
    padding-top: 20px;
    color: #666;
    font-size: 0.95rem;
}
"""

ARTICLE_HTML_TEMPLATE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<article>
  <header>
    <h1>{title}</h1>
    <p class="meta">{tags} • {year}</p>
    <p class="lead">{lead}</p>
  </header>
  {sections}
  <footer>{footer}</footer>
</article>
</body>
</html>"""

# ──────────────────────────────────────────────────────────────────────────────
# Prompt asking the AI to produce a structured editorial article
# ──────────────────────────────────────────────────────────────────────────────

ARTICLE_GENERATION_SYSTEM = """You are an expert tech journalist and editor.
Your task is to write a thorough, editorial-quality news article from the provided
information. Return ONLY a JSON object — no preamble, no markdown fences.

The JSON must have these keys:
{
  "title_en":   "Compelling English headline",
  "title_fr":   "Titre français accrocheur",
  "tags_en":    "Category • Sub-category",
  "tags_fr":    "Catégorie • Sous-catégorie",
  "lead_en":    "2-3 sentence editorial lead in English",
  "lead_fr":    "Chapeau éditorial de 2-3 phrases en français",
  "sections_en": [
    {
      "heading": "Section heading",
      "body":    "2-4 paragraph prose. May contain <ul><li>...</li></ul> or <blockquote>...</blockquote>."
    }
  ],
  "sections_fr": [
    {
      "heading": "Titre de section",
      "body":    "2-4 paragraphes. Peut contenir <ul><li>...</li></ul> ou <blockquote>...</blockquote>."
    }
  ],
  "footer_en": "Short attribution / source note",
  "footer_fr": "Courte note d'attribution / source"
}

Rules:
- Minimum 5 sections per language, each with a strong editorial heading.
- Use <blockquote> for at least one key quote or insight per article.
- Use <ul><li>…</li></ul> bullet lists where relevant (features, risks, takeaways…).
- Prose must be substantive: explain context, give concrete examples, discuss implications.
- Ground every claim in the provided web search results. Do not invent facts.
- Tone: authoritative yet accessible, like a quality tech magazine.
- Do NOT include HTML document boilerplate (no <html>, <head>, <body> tags) in the body fields.
"""

ARTICLE_GENERATION_USER = """## Item to cover
Title: {title}
URL:   {url}
Score: {score}/10  Reason: {reason}
Tags:  {tags}
AI summary: {summary}

## Original content (truncated)
{content}
{comments_section}

## Web search context
{web_context}

Write the full bilingual editorial article JSON now.
"""


# ──────────────────────────────────────────────────────────────────────────────
# Helper: build HTML from parsed AI JSON
# ──────────────────────────────────────────────────────────────────────────────

def _build_sections_html(sections: list) -> str:
    parts = []
    for sec in sections:
        heading = sec.get("heading", "")
        body = sec.get("body", "")
        # Wrap plain paragraphs: split on double-newlines, wrap in <p>
        paragraphs = []
        for chunk in body.split("\n\n"):
            chunk = chunk.strip()
            if not chunk:
                continue
            # Don't double-wrap already-tagged content
            if chunk.startswith("<"):
                paragraphs.append(chunk)
            else:
                # Handle single newlines as line breaks within a paragraph
                paragraphs.append(f"<p>{chunk.replace(chr(10), '<br>')}</p>")
        parts.append(
            f"<section>\n  <h2>{heading}</h2>\n  {''.join(paragraphs)}\n</section>"
        )
    return "\n\n".join(parts)


def _render_article(data: dict, lang: str, year: str) -> str:
    suffix = f"_{lang}"
    title    = data.get(f"title{suffix}", data.get("title_en", ""))
    tags     = data.get(f"tags{suffix}",  data.get("tags_en", ""))
    lead     = data.get(f"lead{suffix}",  data.get("lead_en", ""))
    sections = data.get(f"sections{suffix}", data.get("sections_en", []))
    footer   = data.get(f"footer{suffix}", data.get("footer_en", ""))

    sections_html = _build_sections_html(sections)

    return ARTICLE_HTML_TEMPLATE.format(
        lang=lang,
        title=title,
        css=ARTICLE_CSS,
        tags=tags,
        year=year,
        lead=lead,
        sections=sections_html,
        footer=footer,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main enricher
# ──────────────────────────────────────────────────────────────────────────────

class ContentEnricher:
    """Enriches high-scoring content items with background knowledge and full HTML articles."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client
        self.enriched_cache = {}  # Cache of enriched URLs to avoid re-enriching

    def _get_concurrency(self) -> int:
        config = getattr(self.client, "config", None)
        concurrency = getattr(config, "enrichment_concurrency", 6)
        return max(concurrency, 1)

    async def enrich_batch(self, items: List[ContentItem]) -> None:
        """Enrich items in-place with background knowledge and HTML articles."""
        if not items:
            return

        semaphore = asyncio.Semaphore(self._get_concurrency())

        async def enrich_with_semaphore(item: ContentItem) -> None:
            async with semaphore:
                url_key = str(item.url)
                if url_key in self.enriched_cache:
                    item.metadata.update(self.enriched_cache[url_key])
                    return
                try:
                    await self._enrich_item(item)
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

            async def track_and_enrich(item: ContentItem) -> None:
                await enrich_with_semaphore(item)
                progress.advance(task)

            await asyncio.gather(*[track_and_enrich(item) for item in items])

    async def _web_search(self, query: str, max_results: int = 5) -> list:
        """Search the web for context via DuckDuckGo."""
        try:
            stderr = sys.stderr
            sys.stderr = open(os.devnull, "w")
            try:
                ddgs = DDGS()
                results = await asyncio.to_thread(ddgs.text, query, max_results=max_results)
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
        return parse_json_response(response)

    async def _extract_concepts(self, item: ContentItem, content_text: str) -> List[str]:
        """Ask AI to identify concepts that need explanation (web search queries)."""
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
            return result.get("queries", [])[:3]
        except Exception:
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10)
    )
    async def _enrich_item(self, item: ContentItem) -> None:
        """Enrich a single item:
        1. Extract concepts → web search
        2. Generate bilingual editorial JSON
        3. Render full HTML articles (EN + FR)
        4. Keep backward-compatible plain-text metadata fields
        """
        import datetime

        # ── Split content / comments ──────────────────────────────────────────
        content_text = ""
        comments_text = ""
        if item.content:
            if "--- Top Comments ---" in item.content:
                main, comments_part = item.content.split("--- Top Comments ---", 1)
                content_text = main.strip()[:4000]
                comments_text = comments_part.strip()[:2000]
            else:
                content_text = item.content[:4000]

        # ── Step 1 : concept extraction → web search ─────────────────────────
        queries = await self._extract_concepts(item, content_text)

        all_results = []
        web_sections = []
        if queries:
            search_results = await asyncio.gather(
                *[self._web_search(query) for query in queries],
                return_exceptions=True,
            )
            for query, results in zip(queries, search_results):
                if isinstance(results, Exception):
                    continue
                if results:
                    all_results.extend(results)
                    lines = [f"- [{r['title']}]({r['url']}): {r['body']}" for r in results]
                    web_sections.append(f"**{query}:**\n" + "\n".join(lines))
        web_context = "\n\n".join(web_sections) if web_sections else ""
        available_urls = {r["url"]: r["title"] for r in all_results if r.get("url")}

        # ── Step 2 : generate bilingual editorial article JSON ────────────────
        year = str(datetime.datetime.utcnow().year)
        user_prompt = ARTICLE_GENERATION_USER.format(
            title=item.title,
            url=str(item.url),
            summary=item.ai_summary or item.title,
            score=item.ai_score or 0,
            reason=item.ai_reason or "",
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text,
            comments_section=(
                f"\n**Community Comments:**\n{comments_text}" if comments_text else ""
            ),
            web_context=web_context or "No web search results available.",
        )

        response = await self.client.complete(
            system=ARTICLE_GENERATION_SYSTEM,
            user=user_prompt,
        )

        result = self._parse_json_response(response)
        if result is None:
            print(
                f"Avertissement : impossible d'analyser la réponse d'enrichissement "
                f"pour {item.id}, enrichissement ignoré"
            )
            return

        # ── Step 3 : render full HTML for each language ───────────────────────
        for lang in ("en", "fr"):
            html = _render_article(result, lang, year)
            item.metadata[f"article_html_{lang}"] = html

            # Also store individual structured fields (useful for APIs / search)
            suffix = f"_{lang}"
            item.metadata[f"title{suffix}"]    = result.get(f"title{suffix}", "")
            item.metadata[f"lead{suffix}"]     = result.get(f"lead{suffix}", "")
            item.metadata[f"tags{suffix}"]     = result.get(f"tags{suffix}", "")
            item.metadata[f"footer{suffix}"]   = result.get(f"footer{suffix}", "")

            # Flatten sections into a plain-text detailed_summary
            sections = result.get(f"sections{suffix}", [])
            plain_parts = []
            for sec in sections:
                heading = sec.get("heading", "")
                body = re.sub(r"<[^>]+>", " ", sec.get("body", "")).strip()
                if heading or body:
                    plain_parts.append(f"{heading}\n{body}".strip())
            if not plain_parts:
                structured_fields = [
                    result.get(f"whats_new{suffix}", ""),
                    result.get(f"why_it_matters{suffix}", ""),
                    result.get(f"key_details{suffix}", ""),
                    result.get(f"background{suffix}", ""),
                    result.get(f"community_discussion{suffix}", ""),
                ]
                plain_parts = [
                    re.sub(r"\s+", " ", str(text)).strip()
                    for text in structured_fields
                    if str(text).strip()
                ]
            if plain_parts:
                item.metadata[f"detailed_summary{suffix}"] = "\n\n".join(plain_parts)

            item.metadata[f"background{suffix}"] = result.get(f"background{suffix}", "")

        # ── Step 4 : citation sources ─────────────────────────────────────────
        if result.get("sources") and available_urls:
            valid = [
                {"url": u, "title": available_urls[u]}
                for u in result["sources"]
                if u in available_urls
            ]
            if valid:
                item.metadata["sources"] = valid

        self._apply_evidence_adjustment(item, result)

        # ── Backward-compatible plain-text fallbacks ──────────────────────────
        item.metadata["detailed_summary"]   = item.metadata.get("detailed_summary_en", "")
        item.metadata["background"]         = item.metadata.get("background_en", "")
        item.metadata["community_discussion"] = ""        # no longer a separate field

    # ──────────────────────────────────────────────────────────────────────────
    # Evidence adjustment (unchanged from original)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _looks_sensational(title: str) -> bool:
        t = (title or "").lower()
        patterns = [
            r"\b(shocking|you won['']t believe|destroyed|annihilat|secret|exposed|mind[- ]blowing)\b",
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