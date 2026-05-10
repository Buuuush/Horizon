#!/usr/bin/env python3
"""Regenerate bilingual summary with proper header/TOC synchronization."""

import argparse
import re
from pathlib import Path
from datetime import datetime, timezone


def extract_body_content(html: str, language: str = "en") -> str:
    """Extract the body content between <div class="container"> markers.
    
    If the content uses Markdown in <pre> tags (poorly formatted), 
    convert it to a note about missing proper HTML format.
    """
    match = re.search(
        r'<div class="container">(.*)</div>\s*</body>',
        html,
        flags=re.S
    )
    if not match:
        raise ValueError("Could not locate body content in HTML")
    
    content = match.group(1).strip()
    
    # Check if using Markdown format (poor quality for bilingual display)
    if '<pre' in content and '<article' not in content:
        # This is Markdown format - log warning
        print(f"⚠️  Warning: {language.upper()} file using Markdown format in <pre> tags")
        print(f"   Consider regenerating with proper HTML article format")
    
    return content


def get_language_name(lang: str) -> str:
    """Get display name for language code."""
    return {
        "fr": "Français",
        "en": "English",
        "zh": "中文",
    }.get(lang, lang)


def fix_utf8_entities(html: str) -> str:
    """Convert HTML entities to UTF-8 characters for better display."""
    replacements = {
        '&#39;': "'",
        '&quot;': '"',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&apos;': "'",
        '&nbsp;': ' ',
    }
    for entity, char in replacements.items():
        html = html.replace(entity, char)
    return html


def regenerate_bilingual_full(fr_path: Path, en_path: Path, output_path: Path) -> None:
    """Generate bilingual HTML from separate French and English files."""
    if not fr_path.exists():
        raise FileNotFoundError(f"French summary not found: {fr_path}")
    if not en_path.exists():
        raise FileNotFoundError(f"English summary not found: {en_path}")

    fr_html = fr_path.read_text(encoding="utf-8")
    en_html = en_path.read_text(encoding="utf-8")

    fr_body = extract_body_content(fr_html, language="fr")
    en_body = extract_body_content(en_html, language="en")

    # Get the date from files
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', str(fr_path))
    date = date_match.group(1) if date_match else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build tab buttons
    languages = ["fr", "en"]
    tab_buttons_html = "".join(
        f'<button class="tab-button {"active" if i == 0 else ""}" '
        f'onclick="switchTab(this)" data-lang="{lang}">{get_language_name(lang)}</button>'
        for i, lang in enumerate(languages)
    )

    # Build tab contents
    tab_contents_html = (
        f'<div class="tab-content active" data-lang="fr">{fr_body}</div>'
        f'<div class="tab-content" data-lang="en">{en_body}</div>'
    )

    # Simple bilingual CSS
    css = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&family=Manrope:wght@500;700&display=swap');

:root {
    --bg: #f8f8fb;
    --paper: #ffffff;
    --surface: #fcfbff;
    --accent: #325c9b;
    --accent-2: color-mix(in srgb, var(--accent) 55%, #b73fd6);
    --accent-3: color-mix(in srgb, var(--accent) 40%, #f59e0b);
    --accent-soft: #e6eefb;
    --muted: #5c6372;
    --text: #1d2230;
    --ring: color-mix(in srgb, var(--accent) 32%, transparent);
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
    color: var(--text);
    background:
        radial-gradient(1300px 420px at -10% -20%, var(--accent-soft), transparent 60%),
        radial-gradient(760px 300px at 88% -12%, color-mix(in srgb, var(--accent-2) 24%, transparent), transparent 66%),
        radial-gradient(640px 240px at 30% 0%, color-mix(in srgb, var(--accent-3) 18%, transparent), transparent 70%),
        var(--bg);
    font-family: 'Source Serif 4', Georgia, serif;
    line-height: 1.78;
}

.container { max-width: 1100px; margin: 1.5rem auto; padding: 1rem; }

.tab-switcher {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
    border-bottom: 2px solid color-mix(in srgb, var(--accent) 20%, transparent);
}

.tab-button {
    background: transparent;
    border: none;
    color: var(--muted);
    font-family: 'Manrope', 'Segoe UI', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    padding: 0.75rem 1.2rem;
    cursor: pointer;
    transition: color 0.18s ease, border-color 0.18s ease;
    border-bottom: 3px solid transparent;
}

.tab-button:hover {
    color: var(--text);
}

.tab-button.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
}

.tab-content {
    display: none;
    animation: fadeIn 0.2s ease-in;
}

.tab-content.active {
    display: block;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@media (max-width: 860px) {
    .container { margin: .7rem auto; padding: .65rem; }
    .tab-switcher { flex-wrap: wrap; }
}

@media (prefers-color-scheme: dark) {
    :root {
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
    }

    body {
        background:
            radial-gradient(1200px 420px at -10% -20%, #1a2740, transparent 60%),
            radial-gradient(760px 300px at 88% -12%, rgba(194, 140, 255, 0.2), transparent 66%),
            radial-gradient(640px 240px at 30% 0%, rgba(255, 195, 108, 0.14), transparent 70%),
            var(--bg);
    }

    .summary-header,
    .items article {
        border-color: rgba(124, 177, 255, 0.24);
        box-shadow: 0 18px 44px rgba(0, 0, 0, 0.32);
    }

    .tab-switcher {
        border-bottom-color: rgba(124, 177, 255, 0.2);
    }

    code {
        background: rgba(124, 177, 255, 0.16);
    }
}
"""

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Horizon — {date}</title>
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
      {tab_buttons_html}
    </div>
    {tab_contents_html}
  </div>
</body>
</html>
"""

    # Fix UTF-8 encoding issues (convert HTML entities to UTF-8 characters)
    html = fix_utf8_entities(html)
    
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ Bilingual summary regenerated: {output_path}")
    print(f"   Encoding: UTF-8 with proper character display")


def parse_args():
    parser = argparse.ArgumentParser(description="Regenerate bilingual HTML from separate FR/EN summaries")
    parser.add_argument("--date", required=True, help="Summary date (YYYY-MM-DD)")
    return parser.parse_args()


def main():
    args = parse_args()
    fr_path = Path(f"data/summaries/horizon-{args.date}-fr.html")
    en_path = Path(f"data/summaries/horizon-{args.date}-en.html")
    output_path = Path(f"data/summaries/horizon-{args.date}-bilingual.html")

    regenerate_bilingual_full(fr_path, en_path, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
