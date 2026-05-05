import re
from pathlib import Path


def test_bilingual_fr_contains_numbered_sections():
    path = Path("data/summaries/horizon-2026-05-05-bilingual.html")
    assert path.exists(), f"Missing summary file: {path}"
    text = path.read_text(encoding="utf-8")

    # Ensure FR tab exists
    assert '<div class="tab-content active" data-lang="fr">' in text

    # Ensure at least one numbered FR section like '### 1.' is present
    assert re.search(r"###\s*1\.", text), "No numbered FR sections found (pattern '### 1.')"

    # Ensure we replaced main FR block with the fr-item wrapper
    assert '<div class="fr-item">' in text
