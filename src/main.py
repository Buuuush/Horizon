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
    
    # Scraping arguments
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
    
    # Profile management arguments
    parser.add_argument(
      "--profile",
      type=str,
      help="Select active profile for scoring (default: uses current active profile)",
    )
    parser.add_argument(
      "--manage-profiles",
      action="store_true",
      help="Launch interactive profile manager (create, edit, delete profiles)",
    )
    parser.add_argument(
      "--clear-cache",
      action="store_true",
      help="Clear expired enrichment cache and exit",
    )
    parser.add_argument(
      "--show-feedback-stats",
      type=str,
      metavar="PROFILE",
      help="Show feedback statistics and recommendations for a profile",
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

        # Handle profile management commands
        if args.manage_profiles:
            from .setup.profile_manager import ProfileManager
            pm = ProfileManager(storage)
            pm.interactive_menu()
            return
        
        if args.clear_cache:
            from .ai.cache_manager import CacheManager
            cm = CacheManager(storage)
            cm.clear_expired_cache()
            console.print("[green]✓ Enrichment cache cleared[/green]")
            return
        
        if args.show_feedback_stats:
            from .ai.feedback_analyzer import FeedbackAnalyzer
            fa = FeedbackAnalyzer(storage)
            profile_name = args.show_feedback_stats
            
            summary = fa.get_feedback_summary(profile_name)
            console.print(f"\n[bold cyan]📊 Feedback Stats for Profile: {profile_name}[/bold cyan]")
            console.print(f"  Total: {summary['total_feedback']}")
            console.print(f"  Accuracy: {summary['accuracy_rate']}")
            console.print(f"  Misscored: {summary['misscored_items']}")
            console.print(f"  Favorites: {summary['favorites']}")
            
            roadmap = fa.get_improvement_roadmap(profile_name)
            if roadmap:
                console.print(f"\n[bold]💡 Recommendations:[/bold]")
                for rec in roadmap:
                    console.print(f"  [{rec['priority']}] {rec['title']}")
                    console.print(f"      → {rec['action']}")
            return
        
        # Select profile for scoring
        profile = None
        if args.profile:
            profile = storage.get_profile(args.profile)
            if not profile:
                console.print(f"[red]❌ Profile '{args.profile}' not found[/red]")
                sys.exit(1)
            storage.set_active_profile(args.profile)
            console.print(f"[green]✓ Profile activated: {args.profile}[/green]")
        
        # Try to get the WebSocket manager for broadcasting if web app is running
        # This will only work if the dashboard has been started in another process
        broadcast_callback = None
        try:
            # Check if web app module is already imported
            if 'src.web.app' in sys.modules:
                from .web.app import manager
                broadcast_callback = manager.broadcast
        except Exception:
            # No WebSocket broadcasting available - this is OK, just run without it
            pass
        
        # Create and run orchestrator with selected profile
        orchestrator = HorizonOrchestrator(
            config,
            storage,
            profile=profile,
            broadcast_callback=broadcast_callback,
        )
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
  "analysis_ai": {
    "provider": "openai",
    "model": "meta/llama-3.3-70b-instruct",
    "api_key_env": "NVIDIA_API_KEY",
    "base_url": "https://integrate.api.nvidia.com/v1",
    "temperature": 0.15,
    "max_tokens": 4096,
    "throttle_sec": 2.0,
    "languages": ["fr", "en"]
  },
  "enrichment_ai": {
    "provider": "openai",
    "model": "mistralai/mistral-large-3-675b-instruct-2512",
    "api_key_env": "NVIDIA_API_KEY",
    "base_url": "https://integrate.api.nvidia.com/v1",
    "temperature": 0.15,
    "max_tokens": 4096,
    "throttle_sec": 2.0,
    "languages": ["fr", "en"]
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
    "time_window_hours": 336
  }
}

Créez également un fichier .env avec :
ANTHROPIC_API_KEY=votre_clé_api_ici
GH_TOKEN=votre_jeton_github_ici (optionnel mais recommandé)
"""
    console.print(template)


if __name__ == "__main__":
    main()
