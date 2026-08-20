import pandas as pd
import os

# We need to find jobs that are marked 'Done' in filtered_jobs.xlsx
# BUT are missing from final_jobs_auto.xlsx
# And revert their status to '' so they get processed again.

source_file = "filtered_jobs.xlsx"
dest_file = "final_jobs_auto.xlsx"

print("Repairing state...")

if not os.path.exists(source_file):
    print("Source file not found.")
    exit()

df_source = pd.read_excel(source_file)
df_dest = pd.DataFrame()
if os.path.exists(dest_file):
    df_dest = pd.read_excel(dest_file)

# Get set of URLs in destination
dest_urls = set()
if "URL" in df_dest.columns:
    dest_urls = set(df_dest["URL"].dropna().astype(str))

# Find jobs in source that are "Done" but NOT in dest
count_fixed = 0
for idx, row in df_source.iterrows():
    status = str(row.get("Enrichment Status", ""))
    url = str(row.get("URL", ""))
    
    if status == "Done" and url not in dest_urls:
        print(f"  Reverting: {row.get('Title')} (Was 'Done' but not found in destination)")
        df_source.at[idx, "Enrichment Status"] = "" # Reset
        count_fixed += 1

if count_fixed > 0:
    df_source.to_excel(source_file, index=False)
    print(f"Fixed {count_fixed} jobs. Please run enrich_jobs.py again.")
else:
    print("No inconsistencies found. Maybe they are Manual? Checks were for 'Done' (Auto).")
