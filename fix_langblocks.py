#!/usr/bin/env python3
"""Replace Non disponible French sections with English content in lang-blocks structure."""

import re
from pathlib import Path

def fix_lang_blocks_missing_translations(html_path: Path) -> int:
    """Replace <section class="lang"><h3>FR</h3><div>Non disponible</div> with English content."""
    
    html = html_path.read_text(encoding='utf-8')
    
    # Find all lang-blocks with "Non disponible" - more flexible regex
    count = 0
    
    # Find all lang-blocks sections
    pattern = r'<div class="lang-blocks">(.*?)</div>\s*<div class="tags">'
    
    def replace_non_disp(match):
        nonlocal count
        block_content = match.group(1)
        
        # Check if FR section has "Non disponible"
        if 'Non disponible' not in block_content:
            return match.group(0)
        
        # Extract EN content - find everything between EN header and FR header
        en_pattern = r'<h3>EN</h3><div class="content">(.*?)</div></section>'
        en_match = re.search(en_pattern, block_content, re.DOTALL)
        if not en_match:
            return match.group(0)
        
        en_content = en_match.group(1)
        
        # Replace FR Non disponible section with EN content
        new_block = re.sub(
            r'<h3>FR</h3><div class="content"><em>Non disponible\.</em></div>',
            f'<h3>FR</h3><div class="content">{en_content}</div>',
            block_content
        )
        
        count += 1
        return f'<div class="lang-blocks">{new_block}</div>\n    <div class="tags">'
    
    html = re.sub(
        pattern,
        replace_non_disp,
        html,
        flags=re.DOTALL
    )
    
    # Write back
    html_path.write_text(html, encoding='utf-8')
    print(f"✅ Fixed {count} missing translations in lang-blocks")
    
    return 0

if __name__ == '__main__':
    path = Path('data/summaries/horizon-2026-05-05-bilingual.html')
    fix_lang_blocks_missing_translations(path)
