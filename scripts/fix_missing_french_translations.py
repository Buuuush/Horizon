#!/usr/bin/env python3
"""Replace missing French translations with English versions - robust version."""

import re
import argparse
from pathlib import Path


def fix_missing_french_translations_robust(bilingual_path: Path) -> int:
    """Replace 'Non disponible' articles in French section with English versions."""
    
    html = bilingual_path.read_text(encoding="utf-8")
    
    # Split HTML into three parts: before French tab, French content, English content, after
    # Find the split points
    fr_start = html.find('<div class="tab-content active" data-lang="fr">')
    fr_end = html.find('<div class="tab-content" data-lang="en">')
    en_end = html.find('</div>\n</div>\n</body>')
    
    if fr_start == -1 or fr_end == -1 or en_end == -1:
        print("❌ Could not locate tab sections in HTML")
        return 1
    
    html_before = html[:fr_start + len('<div class="tab-content active" data-lang="fr">')]
    fr_content = html[fr_start + len('<div class="tab-content active" data-lang="fr">'):fr_end]
    en_start_tag = '<div class="tab-content" data-lang="en">'
    html_middle = en_start_tag
    en_content = html[fr_end + len(en_start_tag):en_end]
    html_after = html[en_end:]
    
    # Find items with "Non disponible"
    non_disp_items = set()
    for match in re.finditer(r'<article id="item-(\d+)">', fr_content):
        item_id = match.group(1)
        article_start = match.start()
        article_end = fr_content.find('</article>', article_start) + len('</article>')
        article_text = fr_content[article_start:article_end]
        
        if 'Non disponible' in article_text:
            non_disp_items.add(item_id)
    
    if not non_disp_items:
        print("✅ No missing translations found")
        return 0
    
    print(f"Found {len(non_disp_items)} articles needing replacement: {non_disp_items}")
    
    # For each missing item, replace its French version with English version
    for item_id in non_disp_items:
        # Extract English article
        en_pattern = rf'<article id="item-{item_id}">(.*?)</article>'
        en_match = re.search(en_pattern, en_content, re.DOTALL)
        
        if not en_match:
            print(f"⚠️  Could not find English article item-{item_id}")
            continue
        
        en_article = en_match.group(1)
        
        # Extract French header (keep the title but replace content)
        fr_pattern = rf'<article id="item-{item_id}">(.*?</header>)(.*?)</article>'
        fr_match = re.search(fr_pattern, fr_content, re.DOTALL)
        
        if not fr_match:
            print(f"⚠️  Could not find French article header item-{item_id}")
            continue
        
        fr_header = fr_match.group(1)
        
        # Get content part from English (everything after </header>)
        en_content_part = re.sub(r'^.*?</header>', '', en_article, flags=re.DOTALL)
        
        # Build new article
        new_article = f'<article id="item-{item_id}">{fr_header}{en_content_part}</article>'
        
        # Replace in French content
        old_fr_article = fr_match.group(0)
        fr_content = fr_content.replace(old_fr_article, new_article, 1)
        print(f"   Replaced item-{item_id}")
    
    # Reconstruct full HTML
    new_html = html_before + fr_content + html_middle + en_content + html_after
    
    # Write back
    bilingual_path.write_text(new_html, encoding="utf-8")
    print(f"✅ Fixed {len(non_disp_items)} articles")
    print(f"   File saved: {bilingual_path}")
    
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
    
    return fix_missing_french_translations_robust(bilingual_path)


if __name__ == "__main__":
    raise SystemExit(main())
