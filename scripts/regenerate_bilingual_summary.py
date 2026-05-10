import argparse
import re
from datetime import datetime, timezone
from pathlib import Path


def _default_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _extract_main_block(html: str) -> str:
    match = re.search(r"<main class=\"items\">.*?</main>", html, flags=re.S)
    if not match:
        raise ValueError("Could not locate <main class=\"items\"> block")
    return match.group(0)


def _replace_fr_main_in_bilingual(bilingual_html: str, fr_main: str) -> str:
    tab_match = re.search(
        r"(<div class=\"tab-content active\" data-lang=\"fr\">)(.*?)(</div>\s*<div class=\"tab-content\s*\" data-lang=\"en\">)",
        bilingual_html,
        flags=re.S,
    )
    if not tab_match:
        raise ValueError("Could not locate French tab block in bilingual summary")

    fr_inner = tab_match.group(2)
    main_match = re.search(r"<main class=\"items\">.*?</main>", fr_inner, flags=re.S)
    if not main_match:
        raise ValueError("Could not locate French <main> block inside bilingual summary")

    new_fr_inner = fr_inner[: main_match.start()] + fr_main + fr_inner[main_match.end() :]
    return bilingual_html[: tab_match.start(2)] + new_fr_inner + bilingual_html[tab_match.end(2) :]


def regenerate(fr_path: Path, bilingual_path: Path) -> None:
    if not fr_path.exists():
        raise FileNotFoundError(f"French summary not found: {fr_path}")
    if not bilingual_path.exists():
        raise FileNotFoundError(f"Bilingual summary not found: {bilingual_path}")

    fr_text = fr_path.read_text(encoding="utf-8")
    bilingual_text = bilingual_path.read_text(encoding="utf-8")

    fr_main = _extract_main_block(fr_text)
    updated_bilingual = _replace_fr_main_in_bilingual(bilingual_text, fr_main)

    bilingual_path.write_text(updated_bilingual, encoding="utf-8")
    print(f"Bilingual regenerated: {bilingual_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate bilingual summary FR tab from FR summary")
    parser.add_argument("--date", default=_default_date(), help="Summary date (YYYY-MM-DD)")
    parser.add_argument("--fr-path", help="Path to FR summary HTML")
    parser.add_argument("--bilingual-path", help="Path to bilingual summary HTML")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fr_path = Path(args.fr_path) if args.fr_path else Path(f"data/summaries/horizon-{args.date}-fr.html")
    bilingual_path = (
        Path(args.bilingual_path)
        if args.bilingual_path
        else Path(f"data/summaries/horizon-{args.date}-bilingual.html")
    )

    regenerate(fr_path, bilingual_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
