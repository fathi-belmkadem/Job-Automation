import sys
import argparse
import subprocess
import os
from pathlib import Path

# Project root (parent of src)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Add project root to path for settings import
sys.path.append(str(PROJECT_ROOT))
from config import settings

def run_script(script_name, extra_args=None):
    """Runs a script as a subprocess to ensure clean state and event loops."""
    script_path = PROJECT_ROOT / "src" / script_name
    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)

    print(f"   > Executing {script_name}...")
    try:
        # Run in the project root so imports work as expected
        subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as e:
        print(f"   [Error] Script {script_name} failed with exit code {e.returncode}.")
    except Exception as e:
        print(f"   [Error] Failed to run {script_name}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Join.com Job Automation Pipeline")
    parser.add_argument("--fetch", action="store_true", help="Run URL fetching step")
    parser.add_argument("--filter", action="store_true", help="Run AI Job filtering step (Two-Pass)")
    parser.add_argument("--apply", action="store_true", help="Run Application step")
    parser.add_argument("--all", action="store_true", help="Run FULL pipeline")
    parser.add_argument(
        "--engine",
        choices=["google", "perplexity", "serpapi", "brave", "scrapingbee"],
        default=settings.DEFAULT_SEARCH_ENGINE,
        help=f"Search engine for URL fetching (default: {settings.DEFAULT_SEARCH_ENGINE})"
    )
    parser.add_argument(
        "--ai-provider",
        choices=["gemini", "openrouter"],
        default=settings.AI_PROVIDER,
        help=f"AI provider for filtering and application (default: {settings.AI_PROVIDER})"
    )

    args = parser.parse_args()
    
    # Set AI Provider in environment for sub-scripts
    os.environ["AI_PROVIDER"] = args.ai_provider
    
    # Default to all if no stage args provided
    if not (args.fetch or args.filter or args.apply or args.all):
        print("No arguments provided. running --all by default.")
        args.all = True

    if args.all or args.fetch:
        print("\n\n=== STEP 1: FETCHING URLS ===")
        run_script("fetch_urls.py", extra_args=[args.engine])
        
    if args.all or args.filter:
        print("\n\n=== STEP 2.0: FILTERING JOBS (Pass 1 - URL Slugs) ===")
        run_script("filter_jobs.py")
        
        print("\n\n=== STEP 2.1: ENRICHING JOBS (Scraping Descriptions) ===")
        run_script("enrich_jobs.py")
        
        print("\n\n=== STEP 2.2: DEEP FILTERING (Pass 2 - Descriptions) ===")
        run_script("filter_deep.py")
        
    if args.all or args.apply:
        print("\n\n=== STEP 3: APPLICATION PROCESSS ===")
        run_script("apply_all.py")

if __name__ == "__main__":
    main()
