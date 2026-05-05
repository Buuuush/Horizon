"""CLI entry point for Horizon."""

import argparse
import asyncio
import sys
import os
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

from .storage.manager import StorageManager
from .orchestrator import HorizonOrchestrator


console = Console()

# Ensure UTF-8 mode and stdout/stderr are UTF-8 encoded. This helps Windows
# PowerShell and other terminals display accented characters correctly.
os.environ.setdefault("PYTHONUTF8", "1")
try:
  if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
  # Best-effort: if reconfigure is unavailable, continue without failing
  pass


def print_banner():
    """Print the application banner."""
    banner = r"""
[bold blue]
  _    _            _
 | |  | |          (_)
 | |__| | ___  _ __ _ ___  ___  _ __
 |  __  |/ _ \| '__| |_  / / _ \| '_ \
 | |  | | (_) | |  | |/ / | (_) | | | |
 |_|  |_|\___/|_|  |_/___| \___/|_| |_|
[/bold blue]
[cyan]  AI-Driven Information Aggregation System[/cyan]
    """
    console.print(banner)


def main():
    """Main CLI entry point."""
    print_banner()

    parser = argparse.ArgumentParser(description="Horizon - Système d'agrégation d'informations piloté par l'IA")
    parser.add_argument("--hours", type=int, help="Force fetch from last N hours")
    parser.add_argument(
      "--summary-format",
      choices=["html", "md"],
      default="html",
      help="Summary output format (default: html)",
    )
    parser.add_argument(
      "--theme",
      type=str,
      help="Optional theme filter (e.g. 'culture generale', 'informatique').",
    )
    args = parser.parse_args()

    try:
        # Load environment variables from .env file
        load_dotenv()

        # Ensure we're in the project directory or use data/ in current dir
        data_dir = Path("data")

        # Initialize storage manager
        storage = StorageManager(data_dir=str(data_dir))

        # Load configuration
        try:
            config = storage.load_config()
        except FileNotFoundError:
            console.print("[bold red]❌ Fichier de configuration introuvable ![/bold red]\n")
            console.print(
                "Exécutez [bold cyan]uv run horizon-wizard[/bold cyan] pour lancer l'assistant de configuration interactif,\n"
                "ou créez [cyan]data/config.json[/cyan] manuellement en vous basant sur le modèle :\n"
            )
            print_config_template()
            sys.exit(1)
        except Exception as e:
            console.print(f"[bold red]❌ Erreur de chargement de la configuration : {e}[/bold red]")
            sys.exit(1)

        # Create and run orchestrator
        orchestrator = HorizonOrchestrator(config, storage)
        asyncio.run(
          orchestrator.run(
            force_hours=args.hours,
            summary_format=args.summary_format,
            theme=args.theme,
          )
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrompu par l'utilisateur[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]❌ Erreur fatale : {e}[/bold red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def print_config_template():
    """Print configuration template."""
    template = """
{
  "version": "1.0",
  "ai": {
    "provider": "anthropic",
    "model": "claude-sonnet-4.5-20250929",
    "api_key_env": "ANTHROPIC_API_KEY",
    "temperature": 0.3,
    "max_tokens": 4096
  },
  "sources": {
    "github": [
      {
        "type": "user_events",
        "username": "torvalds",
        "enabled": true
      }
    ],
    "hackernews": {
      "enabled": true,
      "fetch_top_stories": 30,
      "min_score": 100
    },
    "rss": [
      {
        "name": "Example Blog",
        "url": "https://example.com/feed.xml",
        "enabled": true,
        "category": "software-engineering"
      }
    ]
  },
  "filtering": {
    "ai_score_threshold": 7.0,
    "time_window_hours": 24
  }
}

Créez également un fichier .env avec :
ANTHROPIC_API_KEY=votre_clé_api_ici
GITHUB_TOKEN=votre_jeton_github_ici (optionnel mais recommandé)
"""
    console.print(template)


if __name__ == "__main__":
    main()
