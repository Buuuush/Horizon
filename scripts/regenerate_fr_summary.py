import argparse
import re
from datetime import datetime, timezone
from pathlib import Path


def _default_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _extract_section(block: str, pattern: str) -> str:
    match = re.search(pattern, block, flags=re.S)
    return match.group(1).strip() if match else ""


def _rebuild_article(article_html: str, index: int) -> str:
    article_id = _extract_section(article_html, r"<article id=\"(item-\d+)\">") or f"item-{index}"
    title = _extract_section(article_html, r"<h2 class=\"item-title\">\s*<a [^>]*>(.*?)</a>") or f"Item {index}"
    url = _extract_section(article_html, r"<h2 class=\"item-title\">\s*<a href=\"([^\"]+)\"") or "#"
    score = _extract_section(article_html, r"<span class=\"score\">(.*?)</span>")
    meta = _extract_section(article_html, r"<div class=\"meta\">(.*?)</div>")

    fr_content = _extract_section(
        article_html,
        r"<section class=\"lang\">\s*<h3>FR</h3>\s*<div class=\"content\">(.*?)</div>\s*</section>",
    )
    if not fr_content:
        fr_content = _extract_section(article_html, r"<div class=\"content\">(.*?)</div>")
    if not fr_content:
        fr_content = "<em>Non disponible.</em>"

    tags_html = _extract_section(article_html, r"<div class=\"tags\">(.*?)</div>")
    refs_match = re.search(r"(<details>\s*<summary>.*?</summary>\s*<ul>.*?</ul>\s*</details>)", article_html, flags=re.S)
    refs_html = refs_match.group(1).strip() if refs_match else ""

    score_html = f" <span class=\"score\">{score}</span>" if score else ""
    meta_html = f"<div class=\"meta\">{meta}</div>" if meta else ""
    tags_block = f"<div class=\"tags\">{tags_html}</div>" if tags_html else ""

    return (
        f'<article id="{article_id}">\n'
        f'  <header>\n'
        f'    <h2 class="item-title"><a href="{url}">{title}</a>{score_html}</h2>\n'
        f'    {meta_html}\n'
        f'  </header>\n'
        f'  <div class="content">{fr_content}</div>\n'
        f'  {tags_block}\n'
        f'  {refs_html}\n'
        f'</article>'
    )


def _build_article_from_legacy_pre(item_id: str, title: str, content: str, score: str) -> str:
    score_html = f" <span class=\"score\">{score}</span>" if score else ""
    return (
        f'<article id="{item_id}">\n'
        f'  <header>\n'
        f'    <h2 class="item-title"><a href="#">{title}</a>{score_html}</h2>\n'
        f'  </header>\n'
        f'  <div class="content">{content}</div>\n'
        f'</article>'
    )


def regenerate(summary_path: Path) -> None:
    if not summary_path.exists():
        raise FileNotFoundError(f"Summary not found: {summary_path}")

    text = summary_path.read_text(encoding="utf-8")
    main_match = re.search(r"(<main class=\"items\">)(.*?)(</main>)", text, flags=re.S)
    if not main_match:
        raise ValueError("Could not locate <main class=\"items\"> block")

    items_html = main_match.group(2)
    article_blocks = re.findall(r"(<article[^>]*>.*?</article>)", items_html, flags=re.S)

    if article_blocks:
        rebuilt_articles = [_rebuild_article(article, i + 1) for i, article in enumerate(article_blocks)]
    else:
        # Legacy French format: <div class="fr-item"><pre>### n. title ... ---</pre></div>
        score_by_item = {
            idx: score
            for idx, score in re.findall(
                r'<li><a href="#item-(\d+)">.*?</a>\s*<span class="score">(.*?)</span></li>',
                text,
                flags=re.S,
            )
        }
        pre_items = re.findall(
            r"<div class=\"fr-item\">\s*<pre>\s*###\s*(\d+)\.\s*(.*?)\n\n(.*?)\n\n---\s*</pre>\s*</div>",
            items_html,
            flags=re.S,
        )
        if not pre_items:
            raise ValueError("No article blocks or legacy pre blocks found inside <main>")

        rebuilt_articles = []
        for idx, title, content in pre_items:
            item_id = f"item-{idx}"
            score = score_by_item.get(idx, "")
            rebuilt_articles.append(
                _build_article_from_legacy_pre(item_id=item_id, title=title.strip(), content=content.strip(), score=score)
            )

    new_main = '<main class="items">\n' + "\n\n".join(rebuilt_articles) + "\n</main>"
    new_text = text[: main_match.start()] + new_main + text[main_match.end() :]

    summary_path.write_text(new_text, encoding="utf-8")
    print(f"Regenerated: {summary_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate FR summary into FR-only article cards")
    parser.add_argument("--date", default=_default_date(), help="Summary date (YYYY-MM-DD)")
    parser.add_argument("--summary-path", help="Path to FR summary HTML")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_path = (
        Path(args.summary_path)
        if args.summary_path
        else Path(f"data/summaries/horizon-{args.date}-fr.html")
    )
    regenerate(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
