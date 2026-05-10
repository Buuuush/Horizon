#!/usr/bin/env python3
"""Convert French HTML from Markdown format to styled HTML articles."""

import re
from pathlib import Path


def convert_markdown_articles_to_html(html: str) -> str:
    """Convert <div class="fr-item"><pre>Markdown</pre></div> to proper articles."""
    
    # Pattern to find Markdown items in pre tags
    pattern = r'<div class="fr-item">\s*<pre>(.*?)</pre>\s*</div>'
    
    def convert_item(match):
        markdown_text = match.group(1)
        
        # Parse the markdown item
        # Format: ### N. Title\n\nContent\n\n---
        item_match = re.search(
            r'###\s+(\d+)\.\s+(.+?)\n\n(.+?)\n\n---',
            markdown_text,
            re.DOTALL
        )
        
        if not item_match:
            # Return original if can't parse
            return match.group(0)
        
        item_num = item_match.group(1)
        title = item_match.group(2).strip()
        content = item_match.group(3).strip()
        
        # Create proper HTML article
        html_article = f'''<article id="item-{item_num}">
  <header>
    <h2 class="item-title"><a href="#">{escape_html(title)}</a></h2>
  </header>
  <div class="content">{escape_html(content).replace(chr(10), "<br />")}</div>
</article>
'''
        return html_article
    
    # Replace all Markdown items with HTML articles
    return re.sub(pattern, convert_item, html, flags=re.DOTALL)


def escape_html(s: str) -> str:
    """Escape HTML special characters."""
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


def main():
    """Convert French HTML file to use proper article format."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix French HTML format")
    parser.add_argument("--date", required=True, help="Summary date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    fr_path = Path(f"data/summaries/horizon-{args.date}-fr.html")
    
    if not fr_path.exists():
        print(f"❌ File not found: {fr_path}")
        return 1
    
    html = fr_path.read_text(encoding="utf-8")
    
    # Check if needs conversion
    if '<div class="fr-item">' not in html:
        print(f"✅ French file already uses proper article format")
        return 0
    
    print(f"🔄 Converting Markdown articles to HTML...")
    converted_html = convert_markdown_articles_to_html(html)
    
    # Backup original
    backup_path = fr_path.with_suffix('.md.html')
    fr_path.rename(backup_path)
    print(f"📦 Backup saved: {backup_path}")
    
    # Save converted version
    fr_path.write_text(converted_html, encoding="utf-8")
    print(f"✅ French HTML format fixed: {fr_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
