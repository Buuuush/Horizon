#!/usr/bin/env python3
"""Convert HTML entities to UTF-8 characters."""

from pathlib import Path

html_path = Path('data/summaries/horizon-2026-05-05-bilingual.html')
html = html_path.read_text(encoding='utf-8')

# Map of HTML entities to UTF-8 characters
replacements = {
    '&#39;': "'",
    '&quot;': '"',
    '&amp;': '&',
    '&lt;': '<',
    '&gt;': '>',
    '&apos;': "'",
    '&nbsp;': ' ',
}

original_len = len(html)
for entity, char in replacements.items():
    before = html.count(entity)
    html = html.replace(entity, char)
    if before > 0:
        print(f"Replaced {before} instances of {entity}")

html_path.write_text(html, encoding='utf-8')
print(f"\n✅ Encoding fixed with UTF-8 proper character display")
