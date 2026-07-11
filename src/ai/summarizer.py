"""Daily summary generation ÔÇö pure programmatic rendering."""

import re
from html import unescape
from typing import List, Dict

from ..models import ContentItem
from .translation import DeepLTranslator


_CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_ASCII = r"[A-Za-z0-9]"


def _pangu(text: str) -> str:
    """Insert a space between CJK and ASCII letters/digits (Pangu spacing)."""
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "source": "Source",
        "excerpt": "Article Excerpt",
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
        "selected_items": "From {total} items, {selected} important content pieces were selected",
        "empty_analyzed": "Analyzed {total} items, but none met the importance threshold.",
        "empty_body": (
            "No significant developments today. This might indicate:\n"
            "- A quiet day in your tracked sources\n"
            "- The AI score threshold is too high\n"
            "- Your information sources need expansion\n\n"
            "Consider:\n"
            "1. Lowering the `ai_score_threshold` in config.json\n"
            "2. Adding more diverse information sources\n"
            "3. Checking if the AI model is working correctly\n"
        ),
        # Article section labels
        "whats_new": "What happened",
        "why_it_matters": "Why it matters",
        "key_details": "Key details",
        "evidence": "Source reliability",
    },
    "zh": {
        "header": "Horizon µ»ÅµùÑÚÇƒÚÇÆ",
        "source": "µØÑµ║É",
        "excerpt": "ÕÄƒµûçµæÿÕ¢ò",
        "background": "ÞâîµÖ»",
        "discussion": "þñ¥Õî║Þ«¿Þ«║",
        "references": "ÕÅéÞÇâÚô¥µÄÑ",
        "tags": "µáçþ¡¥",
        "selected_items": "õ╗Ä {total} µØíÕåàÕ«╣õ©¡þ¡øÚÇëÕç║ {selected} µØíÚçìÞªüÞÁäÞ«»ÒÇé",
        "empty_analyzed": "ÕÀ▓Õêåµ×É {total} µØíÕåàÕ«╣´╝îõ¢åµ▓íµ£ëÞ¥¥Õê░ÚçìÞªüµÇºÚÿêÕÇ╝þÜäµØíþø«ÒÇé",
        "empty_body": (
            "õ╗èµùÑµÜéµùáÚçìÞªüÕè¿µÇü´╝îÕÅ»Þâ¢ÕÄƒÕøá´╝Ü\n"
            "- õ╗èÕñ®Õà│µ│¿þÜäõ┐íµü»µ║ÉÞ¥âÕ╣│ÚØÖ\n"
            "- AI Þ»äÕêåÚÿêÕÇ╝Þ«¥þ¢«Þ┐çÚ½ÿ\n"
            "- õ┐íµü»µ║Éþºìþ▒╗µ£ëÕ¥àµë®Õàà\n\n"
            "Õ╗║Þ««´╝Ü\n"
            "1. Õ£¿ config.json õ©¡ÚÖìõ¢Ä `ai_score_threshold`\n"
            "2. µÀ╗Õèáµø┤ÕñÜÕñÜµáÀÕîûþÜäõ┐íµü»µ║É\n"
            "3. µúÇµƒÑ AI µ¿íÕ×ïµÿ»ÕÉªµ¡úÕ©©ÕÀÑõ¢£\n"
        ),
        "whats_new": "ÕÅæþöƒõ║åõ╗Çõ╣ê",
        "why_it_matters": "õ©║õ¢òÚçìÞªü",
        "key_details": "Õà│Úö«þ╗åÞèé",
        "evidence": "µØÑµ║ÉÕÅ»ÚØáµÇº",
    },
    "fr": {
        "header": "Horizon Quotidien",
        "source": "Source",
        "excerpt": "Extrait de l'article",
        "background": "Contexte",
        "discussion": "Discussion",
        "references": "R├®f├®rences",
        "tags": "Tags",
        "selected_items": "Parmi {total} contenus collect├®s, {selected} sujets essentiels ont ├®t├® s├®lectionn├®s.",
        "empty_analyzed": "Analyse de {total} contenus : aucun n'a atteint le seuil d'importance.",
        "empty_body": (
            "Aucun d├®veloppement important aujourd'hui. Cela peut indiquer :\n"
            "- Une journ├®e calme dans vos sources suivies\n"
            "- Le seuil de score AI est trop ├®lev├®\n"
            "- Vos sources d'information n├®cessitent une extension\n\n"
            "Consid├®rez :\n"
            "1. Baisser `ai_score_threshold` dans config.json\n"
            "2. Ajouter des sources plus vari├®es\n"
            "3. V├®rifier le bon fonctionnement du mod├¿le AI\n"
        ),
        # Article section labels
        "whats_new": "Ce qui s'est pass├®",
        "why_it_matters": "Pourquoi c'est important",
        "key_details": "Points cl├®s",
        "evidence": "Fiabilit├® des sources",
    },
}

# ---------------------------------------------------------------------------
# CSS helpers
# ---------------------------------------------------------------------------

_ARTICLE_CSS = """
/* ÔöÇÔöÇ Editorial article layout ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ */

.article-lead {{
    font-size: 1.18rem;
    color: var(--muted);
    line-height: 1.7;
    margin: .3rem 0 1.4rem;
    max-width: 72ch;
    font-style: italic;
}}

.article-section {{
    margin-top: 1.55rem;
}}

    .article-section {{
    font-family: {ui};
    font-size: .78rem;
.article-section h2 {{
.narrow {{
    margin: 0 0 .45rem;
    padding-bottom: .25rem;
    border-bottom: 1px solid color-mix(in srgb, var(--accent) 22%, transparent);
}}

.article-section h2 {{
.narrow {{
    font-size: 1.03rem;
    line-height: 1.85;
    color: var(--text);
}}

.article-section p {{
    margin: 0.25rem 0;
}}

.article-section .article-section-last {{
    font-size: 1.08rem;

.article-section h3 {{
    margin: .35rem 0 .15rem;
    font-size: 0.95rem;
    color: var(--muted);
}}
    font-weight: 600;
    margin-top: .45rem;
}}

.article-section p + p {{
    margin-top: .8rem;
}}

.article-background {{
    margin-top: 1.4rem;
    padding: 1rem 1.1rem;
    background: linear-gradient(170deg, var(--surface), color-mix(in srgb, var(--accent-soft) 30%, #fff));
    border-left: 3px solid var(--accent);
    border-radius: 0 10px 10px 0;
    font-size: .98rem;
    line-height: 1.78;
    color: var(--text);
}}

.article-background strong {{
    display: block;
    font-family: {ui};
    font-size: .78rem;
    text-transform: uppercase;
    letter-spacing: .1em;
    color: var(--accent);
    margin-bottom: .35rem;
}}

.article-discussion {{
    margin-top: 1.2rem;
    padding: .85rem 1rem;
    border-left: 3px solid color-mix(in srgb, var(--muted) 40%, transparent);
    font-style: italic;
    font-size: .98rem;
    color: var(--muted);
    line-height: 1.75;
}}

.article-discussion strong {{
    font-style: normal;
    font-family: {ui};
    font-size: .78rem;
    text-transform: uppercase;
    letter-spacing: .1em;
    display: block;
    margin-bottom: .3rem;
    color: var(--muted);
}}
"""


class DailySummarizer:
    """Generates daily summaries and renders them as HTML (bilingual tabs FR/EN)."""

    def __init__(self, ai_client=None, translator: DeepLTranslator | None = None):
        self.client = ai_client
        self.translator = translator if translator is not None else DeepLTranslator()

    @staticmethod
    def _clean_content_excerpt(content: str, max_len: int = 520) -> str:
        """Convert RSS/html-ish content into a readable plain-text excerpt."""
        if not content:
            return ""

        text = str(content)
        if "--- Top Comments ---" in text:
            text = text.split("--- Top Comments ---", 1)[0]

        text = re.sub(r"<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) <= max_len:
            return text
        return text[:max_len].rstrip() + "..."

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    async def generate_bilingual_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        languages: List[str] = None,
    ) -> str:
        """Generate bilingual summary with tabbed interface (FR/EN onglets)."""
        if not languages:
            languages = ["fr", "en"]

        await self._translate_items_for_french_render(items)

        summaries = {}
        for lang in languages:
            summary = await self.generate_summary(items, date, total_fetched, language=lang)
            body_start = summary.find('<div class="container">')
            body_end = summary.rfind("</div>")
            if body_start >= 0 and body_end > body_start:
                body = summary[body_start + len('<div class="container">') : body_end]
            else:
                body = summary
            summaries[lang] = body.strip()

        tab_buttons = []
        for i, lang in enumerate(languages):
            active = "active" if i == 0 else ""
            lang_label = "Fran├ºais" if lang == "fr" else "English" if lang == "en" else "õ©¡µûç"
            tab_buttons.append(
                f'<button class="tab-button {active}" role="tab" aria-selected="{str(i == 0).lower()}" onclick="switchTab(this)" data-lang="{lang}">{lang_label}</button>'
            )
        tabs_html = "".join(tab_buttons)

        tab_contents = []
        for i, lang in enumerate(languages):
            active = "active" if i == 0 else ""
            content_html = summaries.get(lang, "")
            tab_contents.append(
                f'<div class="tab-content {active}" data-lang="{lang}" role="tabpanel">{content_html}</div>'
            )
        contents_html = "".join(tab_contents)

        theme = self._choose_theme(languages[0], items)
        css = self._get_bilingual_css(theme)

        html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Horizon ÔÇö {self._escape_html(date)}</title>
  <style>{css}</style>
  <script>
    function switchTab(button) {{
      const lang = button.getAttribute('data-lang');
      const allButtons = document.querySelectorAll('.tab-button');
      const allContents = document.querySelectorAll('.tab-content');
            allButtons.forEach(b => {{
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
            }});
      allContents.forEach(c => c.classList.remove('active'));
      button.classList.add('active');
      button.setAttribute('aria-selected', 'true');
      document.querySelector(`.tab-content[data-lang="${{lang}}"]`).classList.add('active');
    }}
  </script>
</head>
<body>
  <div class="container">
    <div class="tab-switcher" role="tablist">
      {tabs_html}
    </div>
    {contents_html}
  </div>
</body>
</html>
"""
        return html

    async def _translate_items_for_french_render(self, items: List[ContentItem]) -> None:
        """Translate selected items to French right before rendering."""
        if not items or getattr(self.translator, "available", False) is not True:
            return

        pending: list[tuple[ContentItem, str, str]] = []
        for item in items:
            if item.metadata.get("_deepl_french_ready"):
                continue

            fields = [
                ("title_fr", str(item.metadata.get("title_en") or item.title or "").strip()),
                ("whats_new_fr", str(item.metadata.get("whats_new_en") or "").strip()),
                ("why_it_matters_fr", str(item.metadata.get("why_it_matters_en") or "").strip()),
                ("key_details_fr", str(item.metadata.get("key_details_en") or "").strip()),
                ("background_fr", str(item.metadata.get("background_en") or "").strip()),
                ("community_discussion_fr", str(item.metadata.get("community_discussion_en") or "").strip()),
                ("evidence_note_fr", str(item.metadata.get("evidence_note_en") or "").strip()),
            ]

            for target_key, source_text in fields:
                if source_text:
                    pending.append((item, target_key, source_text))

        if not pending:
            for item in items:
                item.metadata["_deepl_french_ready"] = True
            return

        translated = await self.translator.translate_to_french([source for _, _, source in pending])

        summary_fields = {
            "whats_new_fr",
            "why_it_matters_fr",
            "key_details_fr",
            "background_fr",
            "community_discussion_fr",
        }
        by_item: dict[int, list[str]] = {}
        for (item, target_key, _source_text), translated_text in zip(pending, translated):
            if translated_text:
                item.metadata[target_key] = translated_text
                by_item.setdefault(id(item), [])
                if target_key in summary_fields:
                    by_item[id(item)].append(translated_text)

        for item in items:
            translated_parts = by_item.get(id(item), [])
            if translated_parts:
                item.metadata["detailed_summary_fr"] = "\n\n".join(translated_parts)
            item.metadata["_deepl_french_ready"] = True

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary as a standalone HTML document."""
        labels = LABELS.get(language, LABELS["en"])

        if language == "fr":
            await self._translate_items_for_french_render(items)

        if not items:
            body = self._generate_empty_summary_html(date, total_fetched, labels)
            return self._wrap_html(date, body, language)

        theme = self._choose_theme(language, items)

        toc_entries = []
        for i, item in enumerate(items):
            _t = item.metadata.get(f"title_{language}") or item.title
            t = self._escape_html(str(_t).replace("[", "(").replace("]", ")"))
            if language == "zh":
                t = _pangu(t)
            score = item.ai_score or "?"
            toc_entries.append(
                f'<li><a href="#item-{i+1}">{t}'
                f' <span class="toc-score">Ô¡É´©Å {self._escape_html(str(score))}/10</span></a></li>'
            )
        toc_html = "\n".join(toc_entries)

        parts = []
        for i, item in enumerate(items):
            if language == "fr":
                parts.append(self._format_item_fr_html(item, labels, i + 1))
            else:
                parts.append(self._format_item_html(item, labels, language, i + 1))

        labels_lead = labels.get("selected_items", "").format(
            total=total_fetched, selected=len(items)
        )

        toc_title = {"fr": "Sommaire", "zh": "þø«Õ¢ò"}.get(language, "Contents")

        body = f"""
<section class="summary-header">
  <h1>{self._escape_html(labels['header'])}<br>{self._escape_html(date)}</h1>
  <p class="lead">{self._escape_html(labels_lead)}</p>
  <nav class="toc" aria-label="{self._escape_html(toc_title)}">
    <p class="toc-title">{self._escape_html(toc_title)}</p>
    <ul>{toc_html}</ul>
  </nav>
</section>
<main class="items">{''.join(parts)}</main>
"""

        return self._wrap_html(date, body, language, theme)

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if not items:
            return self._generate_empty_summary(date, total_fetched, labels)

        selected_line = labels.get("selected_items", "").format(
            total=total_fetched, selected=len(items)
        )

        if language == "zh":
            intro = "õ©ïÚØóõ╝Üµîëµû░Úù╗ÚÇÉµØíÕÅæÚÇüÞ»ªµâà´╝îõ¢áÕÅ»õ╗ÑÕÅ¬þ£ïµäƒÕà┤ÞÂúþÜäµáçÚóÿÒÇé\n\n"
        else:
            intro = "Details will be sent item by item so you can read only the topics you care about.\n\n"

        header = f"# {labels['header']} - {date}\n\n> {selected_line}\n\n{intro}"

        entries = []
        for i, item in enumerate(items, start=1):
            title = str(item.metadata.get(f"title_{language}") or item.title).replace("[", "(").replace("]", ")")
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            entries.append(f"{i}. [{title}]({item.url}) Ô¡É´©Å {score}/10")

        return header + "\n".join(entries)

    def generate_webhook_item(
        self,
        item: ContentItem,
        language: str,
        index: int,
        total: int,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        prefix = f"þ¼¼ {index}/{total} µØí\n\n" if language == "zh" else f"Item {index}/{total}\n\n"
        return prefix + self._format_item(item, labels, language, index).rstrip("-\n ")

    # ------------------------------------------------------------------
    # Markdown formatter (webhook)
    # ------------------------------------------------------------------

    def _format_item(self, item: ContentItem, labels: dict, language: str, index: int) -> str:
        """Format a single ContentItem into Markdown."""
        _title = item.metadata.get(f"title_{language}") or item.title
        title = str(_title).replace("[", "(").replace("]", ")")
        url = str(item.url)
        score = item.ai_score or "?"
        meta = item.metadata

        summary = (
            meta.get(f"detailed_summary_{language}")
            or meta.get("detailed_summary")
            or item.ai_summary
            or ""
        )
        background = meta.get(f"background_{language}") or meta.get("background") or ""
        discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        )

        if language == "zh":
            title = _pangu(title)
            summary = _pangu(summary)
            background = _pangu(background)
            discussion = _pangu(discussion)

        source_type = item.source_type.value
        source_parts = [source_type]
        if meta.get("subreddit"):
            source_parts.append(f"r/{meta['subreddit']}")
        if meta.get("feed_name"):
            source_parts.append(meta["feed_name"])
        else:
            source_parts.append(item.author or "unknown")
        if item.published_at:
            if language == "zh":
                source_parts.append(
                    f"{item.published_at.month}µ£ê{item.published_at.day}µùÑ "
                    f"{item.published_at:%H:%M}"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " ┬À ".join(source_parts)

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            discussion_url = str(discussion_url)
            if discussion_url != url:
                source_line += f' ┬À [{labels["discussion"]}]({discussion_url})'

        lines = [
            f'<a id="item-{index}"></a>',
            f"## [{title}]({url}) Ô¡É´©Å {score}/10",
            "",
            summary,
            "",
            source_line,
        ]

        if background:
            lines.append("")
            lines.append(f"**{labels['background']}**: {background}")

        sources = meta.get("sources") or []
        if sources:
            items_html = "".join(f'<li><a href="{s["url"]}">{s["title"]}</a></li>\n' for s in sources)
            lines += [
                "",
                f'<details><summary>{labels["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
            ]

        if discussion:
            lines.append("")
            lines.append(f"**{labels['discussion']}**: {discussion}")

        if item.ai_tags:
            tags_str = ", ".join([f"`#{t}`" for t in item.ai_tags])
            lines.append("")
            lines.append(f"**{labels['tags']}**: {tags_str}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines) + "\n\n"

    # ------------------------------------------------------------------
    # HTML article formatters
    # ------------------------------------------------------------------

    def _build_source_line_html(
        self, item: ContentItem, labels: dict, meta: dict
    ) -> str:
        """Build the escaped source/meta line common to all HTML renderers."""
        source_parts = [self._escape_html(item.source_type.value)]
        if meta.get("subreddit"):
            source_parts.append(self._escape_html(f"r/{meta['subreddit']}"))
        if meta.get("feed_name"):
            source_parts.append(self._escape_html(meta["feed_name"]))
        else:
            source_parts.append(self._escape_html(item.author or "unknown"))
        if item.published_at:
            day = item.published_at.strftime("%d").lstrip("0")
            source_parts.append(
                self._escape_html(item.published_at.strftime(f"%b {day}, %H:%M"))
            )
        source_line = " ┬À ".join(source_parts)

        discussion_url = meta.get("discussion_url")
        if discussion_url and str(discussion_url) != str(item.url):
            source_line += (
                f' ┬À <a href="{self._escape_html(str(discussion_url))}">'
                f'{self._escape_html(labels["discussion"])}</a>'
            )
        return source_line

    def _build_refs_html(self, references: list, labels: dict) -> str:
        """Build a <details> references block or empty string."""
        if not references:
            return ""
        items_html = "".join(
            f'<li><a href="{self._escape_html(s["url"])}">{self._escape_html(s["title"])}</a></li>'
            for s in references
        )
        return (
            f"<details><summary>{self._escape_html(labels['references'])}</summary>"
            f"<ul>{items_html}</ul></details>"
        )

    def _render_article_sections(
        self,
        fields: list[tuple[str, str]],
        background: str,
        discussion: str,
        labels: dict,
    ) -> str:
        """Render structured content fields as editorial article sections.

        Args:
            fields: list of (label, text) pairs for the main body sections
            background: background/context text
            discussion: community discussion text
            labels: localised label dict
        """
        html_parts = []

        # Lead paragraph = first non-empty field rendered as italic lede
        lead_done = False
        section_index = 0
        for section_label, text in fields:
            if not text:
                continue
            escaped = self._escape_html(text).replace("\n", "</p><p>")
            if not lead_done:
                html_parts.append(f'<p class="article-lead">{escaped}</p>')
                lead_done = True
            else:
                section_index += 1
                # Split into individual paragraphs, mark the last paragraph
                parts = escaped.split('</p><p>') if '</p><p>' in escaped else [escaped]
                para_html = []
                for i, p in enumerate(parts):
                    cls = "article-section-last" if i == len(parts) - 1 else ""
                    if cls:
                        para_html.append(f'<p class="{cls}">{p}</p>')
                    else:
                        para_html.append(f'<p>{p}</p>')

                heading_tag = "h2"
                html_parts.append(
                    f'<div class="article-section">'
                    + f"<{heading_tag}>{self._escape_html(section_label)}</{heading_tag}>"
                    + "".join(para_html)
                    + f"</div>"
                )

        if background:
            esc = self._escape_html(background).replace("\n", "</p><p>")
            html_parts.append(
                f'<div class="article-background">'
                f"<strong>{self._escape_html(labels.get('background', 'Background'))}</strong>"
                f"<p>{esc}</p>"
                f"</div>"
            )

        if discussion:
            esc = self._escape_html(discussion).replace("\n", "</p><p>")
            html_parts.append(
                f'<div class="article-discussion">'
                f"<strong>{self._escape_html(labels.get('discussion', 'Discussion'))}</strong>"
                f"<p>{esc}</p>"
                f"</div>"
            )

        return "".join(html_parts)

    def _format_item_fr_html(self, item: ContentItem, labels: dict, index: int) -> str:
        """Format a single ContentItem as a French-only editorial article card."""
        meta = item.metadata
        score = item.ai_score or "?"

        title_raw = meta.get("title_fr") or item.title
        title = self._escape_html(str(title_raw).replace("[", "(").replace("]", ")"))
        url = self._escape_html(str(item.url))

        # Gather structured fields in priority order
        whats_new = (meta.get("whats_new_fr") or "").strip()
        why_it_matters = (meta.get("why_it_matters_fr") or "").strip()
        key_details = (meta.get("key_details_fr") or "").strip()
        background = (meta.get("background_fr") or "").strip()
        discussion = (meta.get("community_discussion_fr") or "").strip()
        evidence_note = (meta.get("evidence_note_fr") or "").strip()

        fields = [
            (labels.get("whats_new", "Ce qui s'est pass├®"), whats_new),
            (labels.get("why_it_matters", "Pourquoi c'est important"), why_it_matters),
            (labels.get("key_details", "Points cl├®s"), key_details),
        ]

        # Fallback chain when structured fields are absent
        has_content = any(t for _, t in fields)
        if not has_content:
            detailed_summary = (meta.get("detailed_summary_fr") or "").strip()
            if not detailed_summary:
                detailed_summary = (meta.get("detailed_summary_en") or "").strip()
            if not detailed_summary:
                detailed_summary = self._clean_content_excerpt(item.content or "")
            if not detailed_summary:
                detailed_summary = "Non disponible en fran├ºais pour le moment."
            fields = [("R├®sum├®", detailed_summary)]

        article_body = self._render_article_sections(fields, background, discussion, labels)

        source_line = self._build_source_line_html(item, labels, meta)
        refs_html = self._build_refs_html(meta.get("sources") or [], labels)

        tags_html = ""
        if item.ai_tags:
            tags_html = ", ".join([f"<code>#{self._escape_html(t)}</code>" for t in item.ai_tags])

        evidence_html = ""
        if evidence_note:
            evidence_html = (
                f'<p class="evidence-note">'
                f'<strong>{self._escape_html(labels.get("evidence", "Fiabilit├®"))}</strong> : '
                f"{self._escape_html(evidence_note)}</p>"
            )

        return f"""
<article id="item-{index}">
  <header>
    <h2 class="item-title"><a href="{url}">{title}</a>
      <span class="score">Ô¡É´©Å {self._escape_html(str(score))}/10</span>
    </h2>
    <div class="meta">{source_line}</div>
  </header>
  <div class="article-body">{article_body}</div>
  {evidence_html}
  <footer class="item-footer">
    <div class="tags">{tags_html}</div>
    {refs_html}
  </footer>
</article>
"""

    def _format_item_html(self, item: ContentItem, labels: dict, language: str, index: int) -> str:
        """Format a single ContentItem as an editorial article card (EN / other languages)."""
        meta = item.metadata
        score = item.ai_score or "?"

        title_raw = meta.get(f"title_{language}") or item.title
        title = self._escape_html(str(title_raw).replace("[", "(").replace("]", ")"))
        url = self._escape_html(str(item.url))

        whats_new = (meta.get(f"whats_new_{language}") or "").strip()
        why_it_matters = (meta.get(f"why_it_matters_{language}") or "").strip()
        key_details = (meta.get(f"key_details_{language}") or "").strip()
        background = (meta.get(f"background_{language}") or meta.get("background") or "").strip()
        discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        ).strip()
        evidence_note = (meta.get(f"evidence_note_{language}") or "").strip()

        if language == "zh":
            whats_new = _pangu(whats_new)
            why_it_matters = _pangu(why_it_matters)
            key_details = _pangu(key_details)
            background = _pangu(background)
            discussion = _pangu(discussion)

        fields = [
            (labels.get("whats_new", "What happened"), whats_new),
            (labels.get("why_it_matters", "Why it matters"), why_it_matters),
            (labels.get("key_details", "Key details"), key_details),
        ]

        has_content = any(t for _, t in fields)
        if not has_content:
            fallback = (
                meta.get(f"detailed_summary_{language}")
                or meta.get("detailed_summary")
                or item.ai_summary
                or self._clean_content_excerpt(item.content or "")
                or "Not available."
            )
            if language == "zh":
                fallback = _pangu(fallback)
            fields = [("Summary", fallback)]

        article_body = self._render_article_sections(fields, background, discussion, labels)

        source_line = self._build_source_line_html(item, labels, meta)
        refs_html = self._build_refs_html(meta.get("sources") or [], labels)

        tags_html = ""
        if item.ai_tags:
            tags_html = ", ".join([f"<code>#{self._escape_html(t)}</code>" for t in item.ai_tags])

        evidence_html = ""
        if evidence_note:
            evidence_html = (
                f'<p class="evidence-note">'
                f'<strong>{self._escape_html(labels.get("evidence", "Source reliability"))}</strong>: '
                f"{self._escape_html(evidence_note)}</p>"
            )

        return f"""
<article id="item-{index}">
  <header>
    <h2 class="item-title"><a href="{url}">{title}</a>
      <span class="score">Ô¡É´©Å {self._escape_html(str(score))}/10</span>
    </h2>
    <div class="meta">{source_line}</div>
  </header>
  <div class="article-body">{article_body}</div>
  {evidence_html}
  <footer class="item-footer">
    <div class="tags">{tags_html}</div>
    {refs_html}
  </footer>
</article>
"""

    # ------------------------------------------------------------------
    # Empty state
    # ------------------------------------------------------------------

    def _markdownish_to_html(self, text: str) -> str:
        """Convert simple markdown-like bullets/numbering into HTML blocks."""
        if not text:
            return ""

        parts: list[str] = []
        in_ul = False
        in_ol = False

        def close_lists() -> None:
            nonlocal in_ul, in_ol
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            if in_ol:
                parts.append("</ol>")
                in_ol = False

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                close_lists()
                continue

            if line.startswith("- "):
                if in_ol:
                    parts.append("</ol>")
                    in_ol = False
                if not in_ul:
                    parts.append("<ul>")
                    in_ul = True
                parts.append(f"<li>{self._escape_html(line[2:].strip())}</li>")
                continue

            ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
            if ordered_match:
                if in_ul:
                    parts.append("</ul>")
                    in_ul = False
                if not in_ol:
                    parts.append("<ol>")
                    in_ol = True
                parts.append(f"<li>{self._escape_html(ordered_match.group(1).strip())}</li>")
                continue

            close_lists()
            parts.append(f"<p>{self._escape_html(line)}</p>")

        close_lists()
        return "".join(parts)

    def _generate_empty_summary_html(self, date: str, total_fetched: int, labels: dict) -> str:
        analyzed_line = labels.get("empty_analyzed", "").format(total=total_fetched)
        empty_html = self._markdownish_to_html(labels.get("empty_body", ""))
        return f"""
<section class="summary-header">
  <h1>{self._escape_html(labels['header'])}<br>{self._escape_html(date)}</h1>
  <p class="lead">{self._escape_html(analyzed_line)}</p>
</section>
<main class="items">
  <article id="item-1" class="empty-state">
    <div class="article-body">{empty_html}</div>
  </article>
</main>
"""

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        analyzed_line = labels.get("empty_analyzed", "").format(total=total_fetched)
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> {analyzed_line}\n\n"
            + labels["empty_body"]
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _escape_html(self, s: str) -> str:
        if s is None:
            return ""
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def _choose_theme(self, language: str, items: List[ContentItem]) -> dict:
        """Return a theme dict based on language and content heuristics."""
        text_blob = " ".join(
            [
                str(getattr(item, "title", "")) + " " + " ".join(getattr(item, "ai_tags", []) or [])
                for item in items
            ]
        ).lower()
        science_signals = ["science", "research", "space", "biology", "physics", "climate", "sante", "santé"]
        policy_signals = ["election", "war", "government", "court", "ukraine", "iran", "policy"]
        science_score = sum(1 for k in science_signals if k in text_blob)
        policy_score = sum(1 for k in policy_signals if k in text_blob)

        base_fonts = {
            "title": "'Outfit', 'Segoe UI', sans-serif",
            "body": "'Source Serif 4', Georgia, serif",
            "ui": "'Outfit', 'Segoe UI', sans-serif",
        }

        if science_score >= policy_score + 2:
            palette = {
                "bg": "#f3f7fb",
                "paper": "#ffffff",
                "surface": "#f8fcff",
                "primary": "#0f766e",
                "secondary": "#06b6d4",
                "accent": "#ec4899",
                "accent_soft": "#d9f4f5",
                "muted": "#5b6470",
                "text": "#10212a",
            }
        elif policy_score > science_score:
            palette = {
                "bg": "#f5f4f7",
                "paper": "#ffffff",
                "surface": "#faf8fc",
                "primary": "#6d28d9",
                "secondary": "#2563eb",
                "accent": "#f97316",
                "accent_soft": "#ece1ff",
                "muted": "#5f6270",
                "text": "#1c2230",
            }
        elif language == "fr":
            palette = {
                "bg": "#f3f4f6",
                "paper": "#ffffff",
                "surface": "#f8fafc",
                "primary": "#4f46e5",
                "secondary": "#06b6d4",
                "accent": "#ec4899",
                "accent_soft": "#e6eefb",
                "muted": "#6b7280",
                "text": "#1f2937",
            }
        elif language == "zh":
            palette = {
                "bg": "#f4f7fb",
                "paper": "#ffffff",
                "surface": "#f9fbfe",
                "primary": "#2563eb",
                "secondary": "#0ea5e9",
                "accent": "#f97316",
                "accent_soft": "#dbeafe",
                "muted": "#5b6472",
                "text": "#112131",
            }
        else:
            palette = {
                "bg": "#f3f4f6",
                "paper": "#ffffff",
                "surface": "#f8fafc",
                "primary": "#4f46e5",
                "secondary": "#06b6d4",
                "accent": "#ec4899",
                "accent_soft": "#e6eefb",
                "muted": "#6b7280",
                "text": "#1f2937",
            }

        return {**base_fonts, **palette}
    # ------------------------------------------------------------------
    # CSS generators
    # ------------------------------------------------------------------

    def _article_css(self, theme: dict) -> str:
        """Return the editorial article CSS block, formatted with theme values."""
        return _ARTICLE_CSS.format(ui=theme["ui"])

    def _base_css(self, theme: dict) -> str:
        """Return the shared structural/typographic CSS."""
        return f"""
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap');

:root {{
    --bg: {theme['bg']};
    --paper: {theme['paper']};
    --surface: {theme['surface']};
    --primary: {theme['primary']};
    --secondary: {theme['secondary']};
    --accent: {theme['accent']};
    --accent-soft: {theme['accent_soft']};
    --muted: {theme['muted']};
    --text: {theme['text']};
    --ring: color-mix(in srgb, var(--primary) 32%, transparent);
    --shadow-sm: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
    --shadow-colored: 0 20px 40px -10px rgba(79, 70, 229, 0.25);
    --radius-lg: 24px;
    --radius-md: 16px;
    --radius-sm: 8px;
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
    color: var(--text);
    background:
        radial-gradient(at 0% 0%, color-mix(in srgb, var(--primary) 10%, transparent) 0px, transparent 50%),
        radial-gradient(at 100% 0%, color-mix(in srgb, var(--secondary) 10%, transparent) 0px, transparent 50%),
        var(--bg);
    font-family: {theme['body']};
    font-size: 1.08rem;
    line-height: 1.78;
    -webkit-font-smoothing: antialiased;
}}

.container {{ max-width: 1000px; margin: 2rem auto; padding: 0 1.5rem; }}

.summary-header {{
    background: var(--paper);
    border-radius: var(--radius-lg);
    padding: 3rem;
    box-shadow: var(--shadow-lg);
    margin-bottom: 3rem;
    position: relative;
    overflow: hidden;
    border-top: 4px solid var(--primary);
}}
.summary-header::before {{
    content: "";
    position: absolute;
    top: 0; right: 0; width: 300px; height: 300px;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    filter: blur(80px);
    opacity: 0.15;
    border-radius: 50%;
    pointer-events: none;
}}
.summary-header h1 {{
    position: relative;
    margin: 0 0 1rem 0;
    font-family: {theme['title']};
    font-weight: 800;
    letter-spacing: -0.02em;
    font-size: clamp(2rem, 4vw, 3.5rem);
    line-height: 1.1;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    color: transparent;
}}
.summary-header .lead {{ position: relative; font-family: {theme['ui']}; font-size: 1.2rem; color: var(--muted); margin: 0 0 2rem 0; }}

.toc-title {{
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .15em;
    color: var(--primary);
    margin-bottom: 1rem;
    font-size: .9rem;
    font-family: {theme['ui']};
}}
.toc ul {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }}
.toc li {{ background: var(--bg); border-radius: var(--radius-md); transition: all .3s ease; border: 1px solid transparent; }}
.toc li:hover {{ transform: translateY(-3px) scale(1.01); background: var(--paper); border-color: color-mix(in srgb, var(--primary) 20%, transparent); box-shadow: var(--shadow-colored); }}
.toc a {{ display: flex; flex-direction: column; text-decoration: none; color: var(--text); padding: 1rem; font-family: {theme['ui']}; font-weight: 600; font-size: .95rem; line-height: 1.4; }}
.toc-score {{ margin-top: .5rem; display: inline-block; color: var(--accent); font-size: .85rem; font-weight: 800; background: color-mix(in srgb, var(--accent) 10%, transparent); padding: 2px 8px; border-radius: 99px; align-self: flex-start; }}

.items {{ display: flex; flex-direction: column; gap: 2.5rem; }}
.items article {{ background: var(--paper); border-radius: var(--radius-lg); padding: 2.5rem; box-shadow: var(--shadow-sm); transition: box-shadow .4s ease; border: 1px solid color-mix(in srgb, var(--text) 3%, transparent); }}
.items article:hover {{ box-shadow: var(--shadow-lg); }}
.item-title {{ font-size: clamp(1.5rem, 2.5vw, 2.2rem); font-weight: 800; line-height: 1.2; margin: 0 0 1rem 0; font-family: {theme['title']}; }}
.item-title a {{ color: var(--text); text-decoration: none; transition: color .2s; }}
.item-title a:hover {{ color: var(--primary); }}
.score {{ display: inline-flex; align-items: center; background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; padding: .3rem .8rem; border-radius: 99px; font-size: 1rem; font-weight: 800; vertical-align: middle; margin-left: .5rem; box-shadow: 0 4px 10px rgba(79, 70, 229, 0.3); font-family: {theme['ui']}; }}
.meta {{ color: var(--muted); font-size: .95rem; font-weight: 600; display: flex; align-items: center; gap: .5rem; margin-bottom: 2rem; }}
.meta::before {{ content: "📰"; }}
.item-title a:focus-visible, .toc a:focus-visible, summary:focus-visible {{ outline: 2px solid var(--ring); outline-offset: 2px; border-radius: 6px; }}
.article-body {{ border-top: 1px solid color-mix(in srgb, var(--primary) 10%, transparent); padding-top: 1rem; }}
.item-footer {{ margin-top: 1rem; padding-top: .65rem; border-top: 2px dashed color-mix(in srgb, var(--text) 5%, transparent); }}
.evidence-note {{ margin: .8rem 0 0; color: var(--muted); font-size: .92rem; font-style: italic; }}
.tags {{ display: flex; flex-wrap: wrap; gap: .5rem; color: var(--muted); font-family: {theme['ui']}; font-size: .88rem; margin-bottom: .45rem; }}
code {{ font-family: {theme['ui']}; background: color-mix(in srgb, var(--primary) 8%, #ffffff); color: var(--primary); font-weight: 600; border-radius: 99px; padding: .4rem 1rem; font-size: .85rem; transition: all .2s; }}
code:hover {{ background: var(--primary); color: white; transform: translateY(-2px); }}
details {{ margin-top: .5rem; }}
details summary {{ cursor: pointer; color: var(--primary); font-family: {theme['ui']}; font-size: .9rem; }}
.article-section ul {{ background: color-mix(in srgb, var(--bg) 88%, white); padding: 1.5rem 1.5rem 1.5rem 3rem; border-radius: var(--radius-md); margin: 1.5rem 0; }}
.article-section li {{ margin-bottom: .5rem; }}
.article-section li strong {{ color: var(--primary); font-family: {theme['ui']}; }}

@media (prefers-color-scheme: dark) {{
    :root {{
        --bg: #0b0f19; --paper: #131b2f; --surface: #192035;
        --primary: #818cf8; --secondary: #2dd4bf; --accent: #f472b6;
        --accent-soft: #1a2740; --muted: #9ca3af; --text: #f3f4f6;
        --ring: rgba(129, 140, 248, 0.55);
    }}
    body {{
        background:
            radial-gradient(at 0% 0%, rgba(129, 140, 248, 0.15) 0px, transparent 50%),
            radial-gradient(at 100% 0%, rgba(45, 212, 191, 0.1) 0px, transparent 50%),
            var(--bg);
    }}
    .summary-header {{ border-bottom: 1px solid rgba(255,255,255,0.05); }}
    .items article {{ border: 1px solid rgba(255,255,255,0.05); }}
    .toc li {{ background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); }}
    .toc li:hover {{ background: var(--paper); border-color: var(--primary); }}
    .article-section ul {{ background: rgba(255,255,255,0.03); }}
    .item-footer {{ border-top-color: rgba(255,255,255,0.1); }}
    code {{ background: rgba(129, 140, 248, 0.15); color: #c7d2fe; }}
}}

@media (max-width: 860px) {{
    .container {{ margin: .7rem auto; padding: .65rem; }}
    .summary-header {{ padding: 2rem 1.5rem; }}
    .items article {{ padding: 1.5rem; }}
    .score {{ margin-left: 0; margin-top: .5rem; display: inline-block; }}
}}
"""

    def _get_bilingual_css(self, theme: dict) -> str:
        """Generate CSS for the bilingual tabbed interface."""
        tab_css = f"""
.tab-switcher {{
    display: inline-flex;
    background: #e5e7eb;
    padding: 6px;
    border-radius: 99px;
    margin-bottom: 2rem;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
}}
.tab-button {{
    background: transparent;
    border: none;
    color: var(--muted);
    font-family: {theme['ui']};
    font-size: 1rem;
    font-weight: 600;
    padding: .6rem 1.5rem;
    border-radius: 99px;
    cursor: pointer;
    transition: all .3s ease;
}}
.tab-button:hover {{ color: var(--text); }}
.tab-button.active {{ background: var(--paper); color: var(--primary); box-shadow: var(--shadow-sm); }}
.tab-content {{ display: none; animation: fadeIn .2s ease-in; }}
.tab-content.active {{ display: block; }}
@keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@media (max-width: 860px) {{ .tab-switcher {{ flex-wrap: wrap; }} }}
"""
        return self._base_css(theme) + self._article_css(theme) + tab_css

    def _wrap_html(self, date: str, body_html: str, language: str, theme: dict = None) -> str:
        if theme is None:
            theme = self._choose_theme(language, [])

        css = self._base_css(theme) + self._article_css(theme)

        return f"""<!doctype html>
<html lang="{self._escape_html(language)}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Horizon ÔÇö {self._escape_html(date)}</title>
  <style>{css}</style>
</head>
<body>
  <div class="container">
    {body_html}
  </div>
</body>
</html>
"""
