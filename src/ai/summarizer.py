"""Daily summary generation — pure programmatic rendering."""

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
        "header": "Horizon 每日速递",
        "source": "来源",
        "excerpt": "原文摘录",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
        "selected_items": "从 {total} 条内容中筛选出 {selected} 条重要资讯。",
        "empty_analyzed": "已分析 {total} 条内容，但没有达到重要性阈值的条目。",
        "empty_body": (
            "今日暂无重要动态，可能原因：\n"
            "- 今天关注的信息源较平静\n"
            "- AI 评分阈值设置过高\n"
            "- 信息源种类有待扩充\n\n"
            "建议：\n"
            "1. 在 config.json 中降低 `ai_score_threshold`\n"
            "2. 添加更多多样化的信息源\n"
            "3. 检查 AI 模型是否正常工作\n"
        ),
        "whats_new": "发生了什么",
        "why_it_matters": "为何重要",
        "key_details": "关键细节",
        "evidence": "来源可靠性",
    },
    "fr": {
        "header": "Horizon Quotidien",
        "source": "Source",
        "excerpt": "Extrait de l'article",
        "background": "Contexte",
        "discussion": "Discussion",
        "references": "Références",
        "tags": "Tags",
        "selected_items": "Parmi {total} contenus collectés, {selected} sujets essentiels ont été sélectionnés.",
        "empty_analyzed": "Analyse de {total} contenus : aucun n'a atteint le seuil d'importance.",
        "empty_body": (
            "Aucun développement important aujourd'hui. Cela peut indiquer :\n"
            "- Une journée calme dans vos sources suivies\n"
            "- Le seuil de score AI est trop élevé\n"
            "- Vos sources d'information nécessitent une extension\n\n"
            "Considérez :\n"
            "1. Baisser `ai_score_threshold` dans config.json\n"
            "2. Ajouter des sources plus variées\n"
            "3. Vérifier le bon fonctionnement du modèle AI\n"
        ),
        # Article section labels
        "whats_new": "Ce qui s'est passé",
        "why_it_matters": "Pourquoi c'est important",
        "key_details": "Points clés",
        "evidence": "Fiabilité des sources",
    },
}

# ---------------------------------------------------------------------------
# CSS helpers
# ---------------------------------------------------------------------------

_ARTICLE_CSS = """
/* ── Editorial article layout ─────────────────────────────────────────── */

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
            lang_label = "Français" if lang == "fr" else "English" if lang == "en" else "中文"
            tab_buttons.append(
                f'<button class="tab-button {active}" onclick="switchTab(this)" data-lang="{lang}">{lang_label}</button>'
            )
        tabs_html = "".join(tab_buttons)

        tab_contents = []
        for i, lang in enumerate(languages):
            active = "active" if i == 0 else ""
            content_html = summaries.get(lang, "")
            tab_contents.append(
                f'<div class="tab-content {active}" data-lang="{lang}">{content_html}</div>'
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
  <title>Horizon — {self._escape_html(date)}</title>
  <style>{css}</style>
  <script>
    function switchTab(button) {{
      const lang = button.getAttribute('data-lang');
      const allButtons = document.querySelectorAll('.tab-button');
      const allContents = document.querySelectorAll('.tab-content');
      allButtons.forEach(b => b.classList.remove('active'));
      allContents.forEach(c => c.classList.remove('active'));
      button.classList.add('active');
      document.querySelector(`.tab-content[data-lang="${{lang}}"]`).classList.add('active');
    }}
  </script>
</head>
<body>
  <div class="container">
    <div class="tab-switcher">
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
                f' <span class="toc-score">⭐️ {self._escape_html(str(score))}/10</span></a></li>'
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

        toc_title = {"fr": "Sommaire", "zh": "目录"}.get(language, "Contents")

        body = f"""
<section class="summary-header">
  <h1>{self._escape_html(labels['header'])} — {self._escape_html(date)}</h1>
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
            intro = "下面会按新闻逐条发送详情，你可以只看感兴趣的标题。\n\n"
        else:
            intro = "Details will be sent item by item so you can read only the topics you care about.\n\n"

        header = f"# {labels['header']} - {date}\n\n> {selected_line}\n\n{intro}"

        entries = []
        for i, item in enumerate(items, start=1):
            title = str(item.metadata.get(f"title_{language}") or item.title).replace("[", "(").replace("]", ")")
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            entries.append(f"{i}. [{title}]({item.url}) ⭐️ {score}/10")

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
        prefix = f"第 {index}/{total} 条\n\n" if language == "zh" else f"Item {index}/{total}\n\n"
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
                    f"{item.published_at.month}月{item.published_at.day}日 "
                    f"{item.published_at:%H:%M}"
                )
            else:
                day = item.published_at.strftime("%d").lstrip("0")
                source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " · ".join(source_parts)

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            discussion_url = str(discussion_url)
            if discussion_url != url:
                source_line += f' · [{labels["discussion"]}]({discussion_url})'

        lines = [
            f'<a id="item-{index}"></a>',
            f"## [{title}]({url}) ⭐️ {score}/10",
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
        source_line = " · ".join(source_parts)

        discussion_url = meta.get("discussion_url")
        if discussion_url and str(discussion_url) != str(item.url):
            source_line += (
                f' · <a href="{self._escape_html(str(discussion_url))}">'
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

                heading_tag = "h2" if section_index == 1 else "h3"
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
            (labels.get("whats_new", "Ce qui s'est passé"), whats_new),
            (labels.get("why_it_matters", "Pourquoi c'est important"), why_it_matters),
            (labels.get("key_details", "Points clés"), key_details),
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
                detailed_summary = "Non disponible en français pour le moment."
            fields = [("Résumé", detailed_summary)]

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
                f'<strong>{self._escape_html(labels.get("evidence", "Fiabilité"))}</strong> : '
                f"{self._escape_html(evidence_note)}</p>"
            )

        return f"""
<article id="item-{index}">
  <header>
    <h2 class="item-title"><a href="{url}">{title}</a>
      <span class="score">⭐️ {self._escape_html(str(score))}/10</span>
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
      <span class="score">⭐️ {self._escape_html(str(score))}/10</span>
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
  <h1>{self._escape_html(labels['header'])} — {self._escape_html(date)}</h1>
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
            "title": "'DM Serif Display', 'Iowan Old Style', 'Palatino Linotype', serif",
            "body": "'Source Serif 4', Georgia, serif",
            "ui": "'Manrope', 'Segoe UI', sans-serif",
        }

        if science_score >= policy_score + 2:
            palette = {
                "bg": "#f4fbfb", "paper": "#ffffff", "surface": "#f7fffe",
                "accent": "#007a79", "accent_soft": "#d6f3f2",
                "muted": "#58646e", "text": "#0e2a2f",
            }
        elif policy_score > science_score:
            palette = {
                "bg": "#f8f5f3", "paper": "#ffffff", "surface": "#fffbf8",
                "accent": "#9b3d2a", "accent_soft": "#f9e2dc",
                "muted": "#6e5b54", "text": "#2f211d",
            }
        elif language == "fr":
            palette = {
                "bg": "#f8f8fb", "paper": "#ffffff", "surface": "#fcfbff",
                "accent": "#325c9b", "accent_soft": "#e6eefb",
                "muted": "#5c6372", "text": "#1d2230",
            }
        elif language == "zh":
            palette = {
                "bg": "#f7fafc", "paper": "#ffffff", "surface": "#fbfdff",
                "accent": "#1369a0", "accent_soft": "#deedf8",
                "muted": "#5c6670", "text": "#112131",
            }
        else:
            palette = {
                "bg": "#f8f8f6", "paper": "#ffffff", "surface": "#fffefb",
                "accent": "#2f6a4f", "accent_soft": "#ddf1e6",
                "muted": "#5f665f", "text": "#1e2a1f",
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
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&family=Manrope:wght@500;700&display=swap');

:root {{
    --bg: {theme['bg']};
    --paper: {theme['paper']};
    --surface: {theme['surface']};
    --accent: {theme['accent']};
    --accent-2: color-mix(in srgb, var(--accent) 55%, #b73fd6);
    --accent-3: color-mix(in srgb, var(--accent) 40%, #f59e0b);
    --accent-soft: {theme['accent_soft']};
    --muted: {theme['muted']};
    --text: {theme['text']};
    --ring: color-mix(in srgb, var(--accent) 32%, transparent);
}}

* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
    color: var(--text);
    background:
        radial-gradient(1300px 420px at -10% -20%, var(--accent-soft), transparent 60%),
        radial-gradient(760px 300px at 88% -12%, color-mix(in srgb, var(--accent-2) 24%, transparent), transparent 66%),
        radial-gradient(640px 240px at 30% 0%, color-mix(in srgb, var(--accent-3) 18%, transparent), transparent 70%),
        var(--bg);
    font-family: {theme['body']};
    line-height: 1.78;
}}

.container {{ max-width: 1100px; margin: 1.5rem auto; padding: 1rem; }}

/* ── Page header ─────────────────────────────────────────────────────── */
.summary-header {{
    background: var(--paper);
    border: 1px solid color-mix(in srgb, var(--accent) 16%, transparent);
    border-radius: 24px;
    padding: 1.5rem 1.6rem 1.1rem;
    box-shadow: 0 18px 48px rgba(19, 33, 68, 0.08);
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
}}
.summary-header::after {{
    content: "";
    position: absolute;
    inset: auto -60px -80px auto;
    width: 220px; height: 220px;
    border-radius: 999px;
    background: radial-gradient(circle, color-mix(in srgb, var(--accent-2) 28%, transparent), transparent 70%);
    pointer-events: none;
}}
.summary-header h1 {{
    margin: 0;
    font-family: 'Fraunces', {theme['title']};
    letter-spacing: .01em;
    font-size: clamp(1.8rem, 3.6vw, 2.8rem);
    line-height: 1.15;
}}
.lead {{ margin: .55rem 0 1.1rem; color: var(--muted); font-size: 1.04rem; max-width: 78ch; }}

/* ── TOC ─────────────────────────────────────────────────────────────── */
.toc-title {{
    margin: 0 0 .45rem;
    font-family: {theme['ui']};
    font-size: .85rem;
    text-transform: uppercase;
    letter-spacing: .11em;
    color: var(--muted);
}}
.toc ul {{
    list-style: none; margin: 0; padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: .55rem;
}}
.toc li {{
    background: linear-gradient(160deg, var(--surface), color-mix(in srgb, var(--accent-soft) 48%, #ffffff));
    border: 1px solid color-mix(in srgb, var(--accent) 16%, transparent);
    border-radius: 10px;
    padding: .55rem .65rem;
    transition: transform .18s ease, box-shadow .18s ease;
}}
.toc li:hover {{ transform: translateY(-1px); box-shadow: 0 8px 20px color-mix(in srgb, var(--accent) 15%, transparent); }}
.toc a {{ text-decoration: none; color: var(--text); }}
.toc-score {{ color: var(--accent); font-family: {theme['ui']}; font-size: .85rem; font-weight: 600; }}

/* ── Article cards ───────────────────────────────────────────────────── */
.items {{ display: grid; gap: .95rem; }}
.items article {{
    background: var(--paper);
    border: 1px solid color-mix(in srgb, var(--accent) 15%, transparent);
    border-radius: 20px;
    padding: 1.4rem 1.6rem 1.1rem;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.05);
}}
.item-title {{
    font-family: 'Fraunces', {theme['title']};
    font-size: clamp(1.2rem, 2.2vw, 1.55rem);
    margin: 0 0 .3rem;
    line-height: 1.22;
}}
.item-title a {{ color: inherit; text-decoration: none; }}
.item-title a:hover {{ color: var(--accent); }}
.item-title a:focus-visible, .toc a:focus-visible, summary:focus-visible {{
    outline: 2px solid var(--ring);
    outline-offset: 2px;
    border-radius: 6px;
}}
.meta {{ color: var(--muted); font-family: {theme['ui']}; font-size: .88rem; margin-bottom: .9rem; }}
.score {{ color: var(--accent); margin-left: .45rem; font-weight: 700; font-family: {theme['ui']}; font-size: .95rem; }}

.article-body {{ border-top: 1px solid color-mix(in srgb, var(--accent) 10%, transparent); padding-top: 1rem; }}

.item-footer {{
    margin-top: 1rem;
    padding-top: .65rem;
    border-top: 1px solid color-mix(in srgb, var(--muted) 18%, transparent);
}}

.evidence-note {{
    margin: .8rem 0 0;
    color: var(--muted);
    font-size: .92rem;
    font-style: italic;
}}

.tags {{ color: var(--muted); font-family: {theme['ui']}; font-size: .88rem; margin-bottom: .45rem; }}
code {{ background: color-mix(in srgb, var(--accent-soft) 65%, #ffffff); border-radius: 8px; padding: .12rem .4rem; }}

details {{ margin-top: .5rem; }}
details summary {{ cursor: pointer; color: var(--accent); font-family: {theme['ui']}; font-size: .9rem; }}

/* ── Dark mode ───────────────────────────────────────────────────────── */
@media (prefers-color-scheme: dark) {{
    :root {{
        --bg: #0f1420; --paper: #161d2c; --surface: #1b2435;
        --accent: #7cb1ff; --accent-2: #c28cff; --accent-3: #ffc36c;
        --accent-soft: #1a2740; --muted: #a6b4cd; --text: #edf2ff;
        --ring: rgba(124, 177, 255, 0.55);
    }}
    body {{
        background:
            radial-gradient(1200px 420px at -10% -20%, #1a2740, transparent 60%),
            radial-gradient(760px 300px at 88% -12%, rgba(194, 140, 255, 0.2), transparent 66%),
            radial-gradient(640px 240px at 30% 0%, rgba(255, 195, 108, 0.14), transparent 70%),
            var(--bg);
    }}
    .summary-header, .items article {{ border-color: rgba(124,177,255,.24); box-shadow: 0 18px 44px rgba(0,0,0,.32); }}
    .toc li {{ border-color: rgba(124,177,255,.22); background: linear-gradient(170deg, #1b2435, #1f2a3f); }}
    code {{ background: rgba(124,177,255,.16); }}
    .article-background {{ background: linear-gradient(170deg, #1b2435, #1f2a3f); }}
}}

@media (max-width: 860px) {{
    .container {{ margin: .7rem auto; padding: .65rem; }}
}}
"""

    def _get_bilingual_css(self, theme: dict) -> str:
        """Generate CSS for the bilingual tabbed interface."""
        tab_css = f"""
.tab-switcher {{
    display: flex; gap: .5rem; margin-bottom: 1.5rem;
    border-bottom: 2px solid color-mix(in srgb, var(--accent) 20%, transparent);
}}
.tab-button {{
    background: transparent; border: none; color: var(--muted);
    font-family: {theme['ui']}; font-size: 1rem; font-weight: 600;
    padding: .75rem 1.2rem; cursor: pointer;
    transition: color .18s ease, border-color .18s ease;
    border-bottom: 3px solid transparent;
}}
.tab-button:hover {{ color: var(--text); }}
.tab-button.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
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
  <title>Horizon — {self._escape_html(date)}</title>
  <style>{css}</style>
</head>
<body>
  <div class="container">
    {body_html}
  </div>
</body>
</html>
"""