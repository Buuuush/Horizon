#!/usr/bin/env python3
"""Replace missing French translations with English versions - using simple string replacement."""

import re
import argparse
from pathlib import Path


def fix_missing_french_translations_simple(bilingual_path: Path) -> int:
    """Replace 'Non disponible' articles in French section with English versions."""
    
    html = bilingual_path.read_text(encoding="utf-8")
    
    # Find the French tab content: <div class="tab-content active" data-lang="fr">...
    # and the English tab content: <div class="tab-content" data-lang="en">...
    
    fr_div_start = html.find('<div class="tab-content active" data-lang="fr">')
    en_div_start = html.find('<div class="tab-content" data-lang="en">')
    html_end = html.rfind('</div>')  # Last div
    
    if fr_div_start == -1 or en_div_start == -1:
        print("❌ Could not locate tab sections")
        return 1
    
    # Extract the sections
    fr_content_start = fr_div_start + len('<div class="tab-content active" data-lang="fr">')
    fr_content = html[fr_content_start:en_div_start]
    
    en_content_start = en_div_start + len('<div class="tab-content" data-lang="en">')
    en_content = html[en_content_start:html_end]
    
    # Find all items with "Non disponible" in French section
    non_disp_items = []
    for match in re.finditer(r'item-(\d+)"', fr_content):
        item_id = match.group(1)
        # Find the full article for this item
        article_pattern = rf'<article id="item-{item_id}">(.*?)</article>'
        article_match = re.search(article_pattern, fr_content, re.DOTALL)
        if article_match and 'Non disponible' in article_match.group(1):
            non_disp_items.append(item_id)
    
    if not non_disp_items:
        print("✅ No missing translations found")
        return 0
    
    print(f"Found {len(non_disp_items)} articles needing replacement")
    
    # For each item, replace French with English version
    for item_id in non_disp_items:
        # Get English article
        en_article_pattern = rf'<article id="item-{item_id}">(.*?)</article>'
        en_article_match = re.search(en_article_pattern, en_content, re.DOTALL)
        
        if not en_article_match:
            print(f"  ⚠️ No English article found for item-{item_id}")
            continue
        
        en_article_content = en_article_match.group(1)
        
        # Extract French header (keep French title)
        fr_article_pattern = rf'<article id="item-{item_id}">(.*?</header>)(.*?)</article>'
        fr_article_match = re.search(fr_article_pattern, fr_content, re.DOTALL)
        
        if not fr_article_match:
            print(f"  ⚠️ No French header found for item-{item_id}")
            continue
        
        fr_header = fr_article_match.group(1)
        
        # Get body from English (after </header>)
        en_body_match = re.search(r'</header>(.*)', en_article_content, re.DOTALL)
        if not en_body_match:
            print(f"  ⚠️ No English body found for item-{item_id}")
            continue
        
        en_body = en_body_match.group(1)
        
        # Build new French article with English body
        new_article = f'<article id="item-{item_id}">{fr_header}{en_body}</article>'
        old_article = fr_article_match.group(0)
        
        # Replace in HTML
        html = html.replace(old_article, new_article, 1)
        print(f"  ✅ Replaced item-{item_id}")
    
    # Write back
    bilingual_path.write_text(html, encoding="utf-8")
    print(f"✅ Fixed {len(non_disp_items)} articles")
    
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Replace missing French translations with English versions")
    parser.add_argument("--date", required=True, help="Summary date (YYYY-MM-DD)")
    return parser.parse_args()


def main():
    args = parse_args()
    bilingual_path = Path(f"data/summaries/horizon-{args.date}-bilingual.html")
    
    if not bilingual_path.exists():
        print(f"❌ File not found: {bilingual_path}")
        return 1
    
    return fix_missing_french_translations_simple(bilingual_path)


if __name__ == "__main__":
    raise SystemExit(main())
