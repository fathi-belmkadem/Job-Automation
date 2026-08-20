import subprocess
import sys
import time
import os
import argparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def run_step(command, description):
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}\n")
    
    start_t = time.time()
    try:
        # Run the command
        # If command is a string, split it. If list, use as is.
        cmd_list = command.split() if isinstance(command, str) else command
        
        # We run in SCRIPTS_DIR so imports like 'from config' work if sys.path hook is there
        # but also so 'python harvest.py' finds harvest.py
        subprocess.run(cmd_list, check=True, shell=True, cwd=SCRIPTS_DIR)
        
        duration = time.time() - start_t
        print(f"\n>>> SUCCESS: {description} completed in {duration:.1f}s.\n")
        
    except subprocess.CalledProcessError as e:
        print(f"\n!!! FAILURE: {description} failed. Exit code: {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n!!! FAILURE: {description} crashed. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XING Job Automation - Master Pipeline")
    parser.add_argument(
        "--steps", "-s",
        nargs="+",
        help="List of steps to run (1-5) or 'all'. Defaults to 'all'.\n1: Harvest, 2: Filter, 3: Enrich, 4: Classify, 5: Apply",
        default=["all"]
    )
    args = parser.parse_args()

    print("------------------------------------------------------------")
    print("   XING JOB AUTOMATION - MASTER PIPELINE")
    print("------------------------------------------------------------")
    
    python_exe = sys.executable

    steps_to_run = args.steps
    if "all" in steps_to_run:
        steps_to_run = ["1", "2", "3", "4", "5"]
    
    # Ensure they are strings for comparison
    steps_to_run = [str(s) for s in steps_to_run]

    # 1. Harvest
    if "1" in steps_to_run:
        run_step([python_exe, "harvest.py"], "1. Harvesting New Jobs")
    
    # 2. Filter
    if "2" in steps_to_run:
        run_step([python_exe, "filters.py"], "2. Filtering & Selecting Jobs")
    
    # 3. Enrich
    if "3" in steps_to_run:
        run_step([python_exe, "enrich_jobs.py"], "3. Enriching Job Details")
    
    # 4. Classify
    if "4" in steps_to_run:
        classify_cmd = [python_exe, "-c", "from application_manager import classify_all_jobs; classify_all_jobs()"]
        run_step(classify_cmd, "4. Classifying Job Types")
    
    # 5. Apply
    if "5" in steps_to_run:
        run_step([python_exe, "apply_all.py"], "5. Auto-Applying")
    
    print("\n" + "="*60)
    print("PIPELINE COMPLETE - ALL REQUESTED STEPS FINISHED SUCCESSFULLY")
    print("="*60)
