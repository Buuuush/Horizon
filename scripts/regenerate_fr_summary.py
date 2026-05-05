import re
from pathlib import Path

SUMMARY_PATH = Path('data/summaries/horizon-2026-05-05-fr.html')

text = SUMMARY_PATH.read_text(encoding='utf-8')

# Split header, main items, footer
m = re.search(r"(<main class=\"items\">)(.*?)(</main>)", text, flags=re.S)
if not m:
    print('Could not find main items block')
    raise SystemExit(1)

header = text[: m.start(1)]
items_html = m.group(2)
footer = text[m.end(3) :]

# Find each article block
articles = re.findall(r"<article[^>]*>(.*?)</article>", items_html, flags=re.S)

new_items = []
for i, art in enumerate(articles, start=1):
    # extract title
    t_match = re.search(r"<h2 class=\"item-title\">.*?<a [^>]*>(.*?)</a>.*?</h2>", art, flags=re.S)
    title = t_match.group(1).strip() if t_match else f'Item {i}'
    # extract FR content
    fr_match = re.search(r"<section class=\"lang\">\s*<h3>FR</h3>\s*<div class=\"content\">(.*?)</div>\s*</section>", art, flags=re.S)
    fr = fr_match.group(1).strip() if fr_match else ''
    # clean HTML entities (basic)
    fr = fr.replace('&amp;', '&').replace('&#39;', "'")
    # Remove excessive whitespace
    fr = re.sub(r"\s+", ' ', fr).strip()

    md = f'<div class="fr-item">\n<pre>### {i}. {title}\n\n{fr}\n\n---</pre>\n</div>\n'
    new_items.append(md)

new_main = '<main class="items">\n' + '\n'.join(new_items) + '\n</main>'
new_text = header + new_main + footer
SUMMARY_PATH.write_text(new_text, encoding='utf-8')
print('Regenerated', SUMMARY_PATH)
