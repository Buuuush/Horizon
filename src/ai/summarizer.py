"""Daily summary generation — pure programmatic rendering."""

import re
from typing import List, Dict

from ..models import ContentItem


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
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
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
    },
    "zh": {
        "header": "Horizon 每日速递",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
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
    },
    "fr": {
        "header": "Horizon Quotidien",
        "source": "Source",
        "background": "Contexte",
        "discussion": "Discussion",
        "references": "Références",
        "tags": "Tags",
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
    },
}


class DailySummarizer:
    """Generates daily summaries and renders them as HTML (bilingual blocks)."""

    def __init__(self, ai_client=None):
        self.client = ai_client

    async def generate_bilingual_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        languages: List[str] = None,
    ) -> str:
        """Generate bilingual summary with tabbed interface (FR/EN onglets).

        Generates summaries for each language and renders them in a single HTML
        document with language tabs at the top for easy switching.

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            languages: List of language codes (default: ["fr", "en"])

        Returns:
            str: HTML formatted summary with language tabs
        """
        if not languages:
            languages = ["fr", "en"]

        # Generate summaries for each language
        summaries = {}
        for lang in languages:
            summary = await self.generate_summary(
                items, date, total_fetched, language=lang
            )
            # Extract body from full HTML (remove DOCTYPE, html, head, body tags)
            body_start = summary.find("<div class=\"container\">")
            body_end = summary.rfind("</div>")
            if body_start >= 0 and body_end > body_start:
                body = summary[body_start + len("<div class=\"container\">") : body_end]
            else:
                body = summary
            summaries[lang] = body.strip()

        # Build tab buttons
        tab_buttons = []
        for i, lang in enumerate(languages):
            active = "active" if i == 0 else ""
            lang_label = "Français" if lang == "fr" else "English" if lang == "en" else "中文"
            tab_buttons.append(
                f'<button class="tab-button {active}" onclick="switchTab(this)" data-lang="{lang}">{lang_label}</button>'
            )
        tabs_html = "".join(tab_buttons)

        # Build tab content
        tab_contents = []
        for i, lang in enumerate(languages):
            active = "active" if i == 0 else ""
            tab_contents.append(
                f'<div class="tab-content {active}" data-lang="{lang}">{summaries.get(lang, "")}</div>'
            )
        contents_html = "".join(tab_contents)

        # Select theme from first language
        theme = self._choose_theme(languages[0], items)

        # Build CSS with tab styles
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

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate daily summary as a standalone HTML document.

        Items are rendered in score-descending order (already sorted by orchestrator).

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, either "en", "zh" or "fr"

        Returns:
            str: HTML formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        # If no items, reuse existing flow but wrapped into simple HTML
        if not items:
            body = self._generate_empty_summary(date, total_fetched, labels)
            return self._wrap_html(date, body, language)

        theme = self._choose_theme(language, items)

        # Table of contents (links to items)
        toc_entries = []
        for i, item in enumerate(items):
            _t = item.metadata.get(f"title_{language}") or item.title
            t = self._escape_html(str(_t).replace("[", "(").replace("]", ")"))
            if language == "zh":
                t = _pangu(t)
            score = item.ai_score or "?"
            toc_entries.append(f'<li><a href="#item-{i+1}">{t}</a> <span class="score">⭐ {score}/10</span></li>')
        toc_html = "\n".join(toc_entries)

        parts = []
        for i, item in enumerate(items):
            if language == "fr":
                parts.append(self._format_item_fr_html(item, labels, i + 1))
            else:
                parts.append(self._format_item_html(item, labels, language, i + 1))

        if language == "fr":
            lead = f"{len(items)} sujets essentiels sélectionnés parmi {total_fetched} contenus collectés."
            toc_title = "Sommaire"
        elif language == "zh":
            lead = f"已从 {total_fetched} 条内容中精选 {len(items)} 条重点。"
            toc_title = "目录"
        else:
            lead = f"{len(items)} essential stories selected from {total_fetched} collected items."
            toc_title = "Contents"

        body = f"""
<section class="summary-header">
  <h1>{self._escape_html(labels['header'])} — {self._escape_html(date)}</h1>
  <p class="lead">{self._escape_html(lead)}</p>
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

        if language == "zh":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 从 {total_fetched} 条内容中筛选出 {len(items)} 条重要资讯。\n\n"
                "下面会按新闻逐条发送详情，你可以只看感兴趣的标题。\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> Selected {len(items)} important items from {total_fetched} fetched items.\n\n"
                "Details will be sent item by item so you can read only the topics you care about.\n\n"
            )

        entries = []
        for i, item in enumerate(items, start=1):
            title = str(item.metadata.get(f"title_{language}") or item.title).replace("[", "(").replace("]", ")")
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            entries.append(f"{i}. [{title}]({item.url}) \u2b50\ufe0f {score}/10")

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

        # Source line with parts joined by " · ", link appended at end
        source_type = item.source_type.value
        source_parts = [source_type]
        if meta.get("subreddit"):
            source_parts.append(f"r/{meta['subreddit']}")
        if meta.get("feed_name"):
            source_parts.append(meta["feed_name"])
        else:
            source_parts.append(item.author or "unknown")
        if item.published_at:
            day = item.published_at.strftime("%d").lstrip("0")
            source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " \u00b7 ".join(source_parts)  # ·

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            discussion_url = str(discussion_url)
            if discussion_url != url:
                source_line += f' · [{labels["discussion"]}]({discussion_url})'

        lines = [
            f'<a id="item-{index}"></a>',
            f"## [{title}]({url}) \u2b50\ufe0f {score}/10",  # ⭐️
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

    def _format_item_fr_html(self, item: ContentItem, labels: dict, index: int) -> str:
        """Format a single ContentItem as a French-only HTML card.

        This avoids leaking English fallback content into the French tab.
        """
        meta = item.metadata

        title_raw = meta.get("title_fr") or item.title
        title = self._escape_html(str(title_raw).replace("[", "(").replace("]", ")"))
        url = self._escape_html(str(item.url))
        score = item.ai_score or "?"

        whats_new = (meta.get("whats_new_fr") or "").strip()
        why_it_matters = (meta.get("why_it_matters_fr") or "").strip()
        key_details = (meta.get("key_details_fr") or "").strip()
        background = (meta.get("background_fr") or "").strip()
        detailed_summary = (meta.get("detailed_summary_fr") or "").strip()
        evidence_note = (meta.get("evidence_note_fr") or "").strip()

        body_blocks = []
        if whats_new:
            body_blocks.append(("Ce qui est nouveau", whats_new))
        if why_it_matters:
            body_blocks.append(("Pourquoi c'est important", why_it_matters))
        if key_details:
            body_blocks.append(("Points clés", key_details))
        if background:
            body_blocks.append((labels["background"], background))

        if not body_blocks and detailed_summary:
            body_blocks.append(("Résumé", detailed_summary))

        if not body_blocks:
            body_blocks.append(("Résumé", "Non disponible en français pour le moment."))

        content_sections_list = []
        for section_title, section_text in body_blocks:
            section_html = self._escape_html(section_text).replace("\n", "<br />")
            content_sections_list.append(
                f'<section class="content-section"><h3>{self._escape_html(section_title)}</h3><div class="content">{section_html}</div></section>'
            )
        content_sections = "".join(content_sections_list)

        source_parts = [self._escape_html(item.source_type.value)]
        if meta.get("subreddit"):
            source_parts.append(self._escape_html(f"r/{meta['subreddit']}"))
        if meta.get("feed_name"):
            source_parts.append(self._escape_html(meta["feed_name"]))
        else:
            source_parts.append(self._escape_html(item.author or "unknown"))
        if item.published_at:
            day = item.published_at.strftime("%d").lstrip("0")
            source_parts.append(self._escape_html(item.published_at.strftime(f"%b {day}, %H:%M")))
        source_line = " \u00b7 ".join(source_parts)

        discussion_url = meta.get("discussion_url")
        if discussion_url and str(discussion_url) != str(item.url):
            source_line += f' · <a href="{self._escape_html(str(discussion_url))}">{self._escape_html(labels["discussion"])}</a>'

        tags_html = ""
        if item.ai_tags:
            tags_html = ", ".join([f"<code>#{self._escape_html(t)}</code>" for t in item.ai_tags])

        references = meta.get("sources") or []
        refs_html = ""
        if references:
            items_html = "".join(
                f'<li><a href="{self._escape_html(s["url"])}">{self._escape_html(s["title"])}</a></li>'
                for s in references
            )
            refs_html = f"<details><summary>{self._escape_html(labels['references'])}</summary><ul>{items_html}</ul></details>"

        evidence_html = ""
        if evidence_note:
            evidence_html = (
                f'<p class="evidence-note"><strong>Fiabilité</strong> : '
                f"{self._escape_html(evidence_note)}</p>"
            )

        html = f"""
<article id="item-{index}">
  <header>
    <h2 class="item-title"><a href="{url}">{title}</a> <span class="score">⭐ {score}/10</span></h2>
    <div class="meta">{source_line}</div>
  </header>
  <div class="lang-blocks fr-only">{content_sections}</div>
  {evidence_html}
  <div class="tags">{tags_html}</div>
  {refs_html}
</article>
"""

        return html

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {labels['header']} - {date}\n\n"
            f"> Analyzed {total_fetched} items, but none met the importance threshold.\n\n"
            + labels["empty_body"]
        )

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
        """Return a simple theme dict based on language and content heuristics.

        This is a lightweight 'AI-decides' heuristic: choose fonts and color palette
        that suit the target language and make the output pleasant to read.
        """
        text_blob = " ".join(
            [str(getattr(item, "title", "")) + " " + " ".join(getattr(item, "ai_tags", []) or []) for item in items]
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
                "bg": "#f4fbfb",
                "paper": "#ffffff",
                "surface": "#f7fffe",
                "accent": "#007a79",
                "accent_soft": "#d6f3f2",
                "muted": "#58646e",
                "text": "#0e2a2f",
            }
        elif policy_score > science_score:
            palette = {
                "bg": "#f8f5f3",
                "paper": "#ffffff",
                "surface": "#fffbf8",
                "accent": "#9b3d2a",
                "accent_soft": "#f9e2dc",
                "muted": "#6e5b54",
                "text": "#2f211d",
            }
        elif language == "fr":
            palette = {
                "bg": "#f8f8fb",
                "paper": "#ffffff",
                "surface": "#fcfbff",
                "accent": "#325c9b",
                "accent_soft": "#e6eefb",
                "muted": "#5c6372",
                "text": "#1d2230",
            }
        elif language == "zh":
            palette = {
                "bg": "#f7fafc",
                "paper": "#ffffff",
                "surface": "#fbfdff",
                "accent": "#1369a0",
                "accent_soft": "#deedf8",
                "muted": "#5c6670",
                "text": "#112131",
            }
        else:
            palette = {
                "bg": "#f8f8f6",
                "paper": "#ffffff",
                "surface": "#fffefb",
                "accent": "#2f6a4f",
                "accent_soft": "#ddf1e6",
                "muted": "#5f665f",
                "text": "#1e2a1f",
            }

        return {**base_fonts, **palette}

    def _get_bilingual_css(self, theme: dict) -> str:
        """Generate CSS for bilingual tabbed interface."""
        css = f"""
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

.tab-switcher {{
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
    border-bottom: 2px solid color-mix(in srgb, var(--accent) 20%, transparent);
}}

.tab-button {{
    background: transparent;
    border: none;
    color: var(--muted);
    font-family: {theme['ui']};
    font-size: 1rem;
    font-weight: 600;
    padding: 0.75rem 1.2rem;
    cursor: pointer;
    transition: color 0.18s ease, border-color 0.18s ease;
    border-bottom: 3px solid transparent;
}}

.tab-button:hover {{
    color: var(--text);
}}

.tab-button.active {{
    color: var(--accent);
    border-bottom-color: var(--accent);
}}

.tab-content {{
    display: none;
    animation: fadeIn 0.2s ease-in;
}}

.tab-content.active {{
    display: block;
}}

@keyframes fadeIn {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}

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
    width: 220px;
    height: 220px;
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

.toc-title {{
    margin: 0 0 .45rem;
    font-family: {theme['ui']};
    font-size: .85rem;
    text-transform: uppercase;
    letter-spacing: .11em;
    color: var(--muted);
}}

.toc ul {{
    list-style: none;
    margin: 0;
    padding: 0;
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

.toc li:hover {{
    transform: translateY(-1px);
    box-shadow: 0 8px 20px color-mix(in srgb, var(--accent) 15%, transparent);
}}

.toc a {{ text-decoration: none; color: var(--text); }}

.items {{ display: grid; gap: .95rem; }}

.items article {{
    background: var(--paper);
    border: 1px solid color-mix(in srgb, var(--accent) 15%, transparent);
    border-radius: 20px;
    padding: 1.15rem 1.2rem;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.05);
}}

.item-title {{
    font-family: 'Fraunces', {theme['title']};
    font-size: clamp(1.2rem, 2.2vw, 1.55rem);
    margin: 0 0 .55rem;
    line-height: 1.22;
}}

.item-title a {{ color: inherit; text-decoration: none; }}
.item-title a:hover {{ color: var(--accent); }}

.item-title a:focus-visible,
.toc a:focus-visible,
summary:focus-visible {{
    outline: 2px solid var(--ring);
    outline-offset: 2px;
    border-radius: 6px;
}}

.meta {{ color: var(--muted); font-family: {theme['ui']}; font-size: .9rem; margin-bottom: .7rem; }}
.score {{ color: var(--accent); margin-left: .45rem; font-weight: 700; font-family: {theme['ui']}; }}

.content {{ font-size: 1.03rem; line-height: 1.8; }}

.fr-only {{
    display: grid;
    gap: .72rem;
}}

.content-section {{
    background: linear-gradient(170deg, var(--surface), color-mix(in srgb, var(--accent-soft) 24%, #ffffff));
    border: 1px solid color-mix(in srgb, var(--accent) 12%, transparent);
    border-radius: 12px;
    padding: .78rem .85rem;
}}

.content-section h3 {{
    margin: 0 0 .35rem;
    font-family: {theme['ui']};
    font-size: .82rem;
    color: var(--muted);
    letter-spacing: .07em;
    text-transform: uppercase;
}}

.evidence-note {{
    margin: .7rem 0 0;
    color: var(--muted);
    font-size: .94rem;
}}

.tags {{ margin-top: .75rem; color: var(--muted); font-family: {theme['ui']}; font-size: .9rem; }}
code {{ background: color-mix(in srgb, var(--accent-soft) 65%, #ffffff); border-radius: 8px; padding: .12rem .4rem; }}

details {{ margin-top: .65rem; }}
details summary {{ cursor: pointer; color: var(--accent); font-family: {theme['ui']}; }}

@media (max-width: 860px) {{
    .container {{ margin: .7rem auto; padding: .65rem; }}
    .tab-switcher {{ flex-wrap: wrap; }}
}}

@media (prefers-color-scheme: dark) {{
    :root {{
        --bg: #0f1420;
        --paper: #161d2c;
        --surface: #1b2435;
        --accent: #7cb1ff;
        --accent-2: #c28cff;
        --accent-3: #ffc36c;
        --accent-soft: #1a2740;
        --muted: #a6b4cd;
        --text: #edf2ff;
        --ring: rgba(124, 177, 255, 0.55);
    }}

    body {{
        background:
            radial-gradient(1200px 420px at -10% -20%, #1a2740, transparent 60%),
            radial-gradient(760px 300px at 88% -12%, rgba(194, 140, 255, 0.2), transparent 66%),
            radial-gradient(640px 240px at 30% 0%, rgba(255, 195, 108, 0.14), transparent 70%),
            var(--bg);
    }}

    .summary-header,
    .items article {{
        border-color: rgba(124, 177, 255, 0.24);
        box-shadow: 0 18px 44px rgba(0, 0, 0, 0.32);
    }}

    .tab-switcher {{
        border-bottom-color: rgba(124, 177, 255, 0.2);
    }}

    code {{
        background: rgba(124, 177, 255, 0.16);
    }}
}}
"""
        return css

    def _wrap_html(self, date: str, body_html: str, language: str, theme: dict = None) -> str:
        if theme is None:
            theme = self._choose_theme(language, [])

        css = f"""
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
    width: 220px;
    height: 220px;
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

.toc-title {{
    margin: 0 0 .45rem;
    font-family: {theme['ui']};
    font-size: .85rem;
    text-transform: uppercase;
    letter-spacing: .11em;
    color: var(--muted);
}}

.toc ul {{
    list-style: none;
    margin: 0;
    padding: 0;
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

.toc li:hover {{
    transform: translateY(-1px);
    box-shadow: 0 8px 20px color-mix(in srgb, var(--accent) 15%, transparent);
}}

.toc a {{ text-decoration: none; color: var(--text); }}

.items {{ display: grid; gap: .95rem; }}

.items article {{
    background: var(--paper);
    border: 1px solid color-mix(in srgb, var(--accent) 15%, transparent);
    border-radius: 20px;
    padding: 1.15rem 1.2rem;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.05);
}}

.item-title {{
    font-family: 'Fraunces', {theme['title']};
    font-size: clamp(1.2rem, 2.2vw, 1.55rem);
    margin: 0 0 .55rem;
    line-height: 1.22;
}}

.item-title a {{ color: inherit; text-decoration: none; }}
.item-title a:hover {{ color: var(--accent); }}

.item-title a:focus-visible,
.toc a:focus-visible,
summary:focus-visible {{
    outline: 2px solid var(--ring);
    outline-offset: 2px;
    border-radius: 6px;
}}

.meta {{ color: var(--muted); font-family: {theme['ui']}; font-size: .9rem; margin-bottom: .7rem; }}
.score {{ color: var(--accent); margin-left: .45rem; font-weight: 700; font-family: {theme['ui']}; }}

.lang-blocks {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; }}

.lang {{
    background: linear-gradient(170deg, var(--surface), color-mix(in srgb, var(--accent-soft) 30%, #ffffff));
    border: 1px solid color-mix(in srgb, var(--accent) 12%, transparent);
    border-radius: 12px;
    padding: .75rem;
}}

.lang h3 {{
    margin: 0 0 .35rem;
    font-family: {theme['ui']};
    font-size: .8rem;
    color: var(--muted);
    letter-spacing: .08em;
    text-transform: uppercase;
}}

.content {{ font-size: 1.03rem; line-height: 1.8; }}

.fr-only {{
    display: grid;
    gap: .72rem;
}}

.content-section {{
    background: linear-gradient(170deg, var(--surface), color-mix(in srgb, var(--accent-soft) 24%, #ffffff));
    border: 1px solid color-mix(in srgb, var(--accent) 12%, transparent);
    border-radius: 12px;
    padding: .78rem .85rem;
}}

.content-section h3 {{
    margin: 0 0 .35rem;
    font-family: {theme['ui']};
    font-size: .82rem;
    color: var(--muted);
    letter-spacing: .07em;
    text-transform: uppercase;
}}

.evidence-note {{
    margin: .7rem 0 0;
    color: var(--muted);
    font-size: .94rem;
}}

.tags {{ margin-top: .75rem; color: var(--muted); font-family: {theme['ui']}; font-size: .9rem; }}
code {{ background: color-mix(in srgb, var(--accent-soft) 65%, #ffffff); border-radius: 8px; padding: .12rem .4rem; }}

details {{ margin-top: .65rem; }}
details summary {{ cursor: pointer; color: var(--accent); font-family: {theme['ui']}; }}

@media (max-width: 860px) {{
    .container {{ margin: .7rem auto; padding: .65rem; }}
    .lang-blocks {{ grid-template-columns: 1fr; }}
}}

@media (prefers-color-scheme: dark) {{
    :root {{
        --bg: #0f1420;
        --paper: #161d2c;
        --surface: #1b2435;
        --accent: #7cb1ff;
        --accent-2: #c28cff;
        --accent-3: #ffc36c;
        --accent-soft: #1a2740;
        --muted: #a6b4cd;
        --text: #edf2ff;
        --ring: rgba(124, 177, 255, 0.55);
    }}

    body {{
        background:
            radial-gradient(1200px 420px at -10% -20%, #1a2740, transparent 60%),
            radial-gradient(760px 300px at 88% -12%, rgba(194, 140, 255, 0.2), transparent 66%),
            radial-gradient(640px 240px at 30% 0%, rgba(255, 195, 108, 0.14), transparent 70%),
            var(--bg);
    }}

    .summary-header,
    .items article {{
        border-color: rgba(124, 177, 255, 0.24);
        box-shadow: 0 18px 44px rgba(0, 0, 0, 0.32);
    }}

    .toc li,
    .lang {{
        border-color: rgba(124, 177, 255, 0.22);
        background: linear-gradient(170deg, #1b2435, #1f2a3f);
    }}

    code {{
        background: rgba(124, 177, 255, 0.16);
    }}
}}
"""

        html = f"""
<!doctype html>
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

        return html

    def _format_item_html(self, item: ContentItem, labels: dict, language: str, index: int) -> str:
        """Format a single ContentItem as HTML. Shows bilingual blocks when available."""
        meta = item.metadata

        title_raw = item.metadata.get(f"title_{language}") or item.title
        title = self._escape_html(str(title_raw).replace("[", "(").replace("]", ")"))
        url = self._escape_html(str(item.url))
        score = item.ai_score or "?"

        # Gather summaries in EN and FR when available
        summary_en = (
            meta.get("detailed_summary_en")
            or meta.get("detailed_summary")
            or (item.ai_summary if language == "en" else None)
            or ""
        )
        summary_fr = (
            meta.get("detailed_summary_fr")
            or meta.get("detailed_summary")
            or (item.ai_summary if language == "fr" else None)
            or ""
        )

        if language == "zh":
            summary_en = _pangu(summary_en)
            summary_fr = _pangu(summary_fr)

        summary_en_html = self._escape_html(summary_en).replace("\n", "<br />")
        summary_fr_html = self._escape_html(summary_fr).replace("\n", "<br />")

        source_parts = [self._escape_html(item.source_type.value)]
        if meta.get("subreddit"):
            source_parts.append(self._escape_html(f"r/{meta['subreddit']}"))
        if meta.get("feed_name"):
            source_parts.append(self._escape_html(meta["feed_name"]))
        else:
            source_parts.append(self._escape_html(item.author or "unknown"))
        if item.published_at:
            day = item.published_at.strftime("%d").lstrip("0")
            source_parts.append(self._escape_html(item.published_at.strftime(f"%b {day}, %H:%M")))
        source_line = " \u00b7 ".join(source_parts)

        discussion_url = meta.get("discussion_url")
        if discussion_url and str(discussion_url) != str(item.url):
            source_line += f' · <a href="{self._escape_html(str(discussion_url))}">{self._escape_html(labels["discussion"])}</a>'

        tags_html = ""
        if item.ai_tags:
            tags_html = ", ".join([f"<code>#{self._escape_html(t)}</code>" for t in item.ai_tags])

        references = meta.get("sources") or []
        refs_html = ""
        if references:
            items_html = "".join(f'<li><a href="{self._escape_html(s["url"])}">{self._escape_html(s["title"])}</a></li>' for s in references)
            refs_html = f"<details><summary>{self._escape_html(labels['references'])}</summary><ul>{items_html}</ul></details>"

        html = f"""
<article id="item-{index}">
  <header>
    <h2 class="item-title"><a href="{url}">{title}</a> <span class="score">⭐ {score}/10</span></h2>
    <div class="meta">{source_line}</div>
  </header>
    <div class="lang-blocks">
        <section class="lang"><h3>EN</h3><div class="content">{summary_en_html or '<em>Not available.</em>'}</div></section>
        <section class="lang"><h3>FR</h3><div class="content">{summary_fr_html or '<em>Non disponible.</em>'}</div></section>
    </div>
  <div class="tags">{tags_html}</div>
  {refs_html}
</article>
"""

        return html
