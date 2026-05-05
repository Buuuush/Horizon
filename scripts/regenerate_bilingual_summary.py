from pathlib import Path
import re

fr_path = Path('data/summaries/horizon-2026-05-05-fr.html')
bi_path = Path('data/summaries/horizon-2026-05-05-bilingual.html')

fr_text = fr_path.read_text(encoding='utf-8')
bi_text = bi_path.read_text(encoding='utf-8')

# extract main from fr
m_fr = re.search(r"(<main class=\"items\">)(.*?)(</main>)", fr_text, flags=re.S)
if not m_fr:
    print('FR main block not found')
    raise SystemExit(1)
fr_main = m_fr.group(0)

# replace main block in bilingual's FR tab
# find start of FR tab_content div
fr_tab_start = re.search(r"<div class=\"tab-content active\" data-lang=\"fr\">", bi_text)
if not fr_tab_start:
    print('FR tab not found in bilingual')
    raise SystemExit(1)
# find the end of the FR tab div which is before the EN tab
en_tab_start = re.search(r"<div class=\"tab-content\s*\" data-lang=\"en\">", bi_text)
if not en_tab_start:
    print('EN tab start not found')
    raise SystemExit(1)

# we will replace the portion between the first <main class="items"> after FR tab and the closing </main> with fr_main
# find the existing FR main block in bilingual
m_bi_fr = re.search(r"(<div class=\"tab-content active\" data-lang=\"fr\">.*?)(<main class=\"items\">.*?</main>)(.*?)(</div>)", bi_text, flags=re.S)
if not m_bi_fr:
    print('Could not locate FR main in bilingual')
    raise SystemExit(1)

new_bi = bi_text[:m_bi_fr.start(2)] + fr_main + bi_text[m_bi_fr.end(2):]
bi_path.write_text(new_bi, encoding='utf-8')
print('Bilingual regenerated:', bi_path)
