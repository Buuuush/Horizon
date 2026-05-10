#!/usr/bin/env python3
from pathlib import Path
import re

html = Path('data/summaries/horizon-2026-05-05-bilingual.html').read_text(encoding='utf-8')

# Find item-1 in fr section
fr_div_start = html.find('<div class="tab-content active" data-lang="fr">')
en_div_start = html.find('<div class="tab-content" data-lang="en">')

fr_content_start = fr_div_start + len('<div class="tab-content active" data-lang="fr">')
fr_content = html[fr_content_start:en_div_start]

# Get item-1
match = re.search(r'<article id="item-1">(.*?)</article>', fr_content, re.DOTALL)
if match:
    content = match.group(1)
    if 'Non disponible' in content:
        print('Found Non disponible in item-1')
        print(content[:400])
    else:
        print('NO Non disponible in item-1')
        print(content[:400])
else:
    print('item-1 not found in French section')
    
# Also check what the actual text is for items 1, 13, 18, 19
for item_id in ['1', '13', '18', '19']:
    match = re.search(rf'<article id="item-{item_id}">(.*?)</article>', fr_content, re.DOTALL)
    if match:
        content = match.group(1)
        has_non = 'Non disponible' in content
        print(f"item-{item_id}: has_non_dispo={has_non}")
        # Show first 100 chars
        print(f"  Content start: {content[:100]}")
