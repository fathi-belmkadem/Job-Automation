import pandas as pd
import os

def migrate_file(filepath, status_col, value="Legacy"):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    print(f"Migrating {filepath}...")
    try:
        df = pd.read_excel(filepath)
        if status_col not in df.columns:
            print(f"  Adding column '{status_col}'")
            df[status_col] = ""
        
        # Count pending
        pending_mask = df[status_col].isna() | (df[status_col].astype(str).str.strip() == "")
        count = pending_mask.sum()
        
        if count > 0:
            print(f"  Marking {count} rows as '{value}'...")
            df.loc[pending_mask, status_col] = value
            df.to_excel(filepath, index=False)
            print("  Done.")
        else:
            print("  No pending rows found.")
            
    except Exception as e:
        print(f"  Error migrating {filepath}: {e}")

if __name__ == "__main__":
    # 1. Harvested/Intermediate Jobs -> Filter Status
    # Mark as 'Old' effectively means "Already Filtered" or "Skipped Filtering"
    migrate_file("intermediate_jobs.xlsx", "Filter Status", "Old")
    
    # 2. Filtered Jobs -> Enrichment Status
    migrate_file("filtered_jobs.xlsx", "Enrichment Status", "Old")
    

