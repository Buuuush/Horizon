#!/usr/bin/env python3
"""Find articles with missing French translations."""

import re
from pathlib import Path

html = Path('data/summaries/horizon-2026-05-05-bilingual.html').read_text(encoding='utf-8')

# Find all French 'Non disponible' blocks and their item IDs
pattern = r'<article id="item-(\d+)">(.*?<em>Non disponible\.</em>.*?)</article>'
matches = list(re.finditer(pattern, html, re.DOTALL))

print(f'Found {len(matches)} articles with Non disponible')

for m in matches:
    item_id = m.group(1)
    print(f'  item-{item_id}')
