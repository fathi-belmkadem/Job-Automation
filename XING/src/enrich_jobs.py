
import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import os
import time
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

INPUT_FILE = settings.FILTERED_JOBS_PATH
OUTPUT_FILE_AUTO = settings.JOBS_DB_PATH
OUTPUT_FILE_MANUAL = settings.MANUAL_JOBS_PATH

def clean_description(text):
    """
    Cleans the raw job description by removing header/footer noise.
    """
    # Markers to start typical description
    start_markers = ["About this job", "Über diesen Job", "Stellenbeschreibung", "Job description"]
    # Markers that usually signal the end of the description
    end_markers = ["Salary forecast", "Gehaltsprognose", "About the company", "Über das Unternehmen", "Similar jobs", "Ähnliche Jobs", "Salary expectations"]
    
    lines = text.split('\n')
    start_idx = 0
    end_idx = len(lines)
    
    # improved start detection: look for marker in lines
    for i, line in enumerate(lines):
        if any(m.lower() in line.lower() for m in start_markers):
            start_idx = i
            break
            
    # improved end detection
    for i in range(start_idx, len(lines)):
        line = lines[i]
        if any(m.lower() in line.lower() for m in end_markers):
             # verify it's not just a casual mention (heuristic: usually short headers)
             if len(line.strip()) < 50: 
                end_idx = i
                break
    
    cleaned_lines = lines[start_idx:end_idx]
    # Remove empty lines from start/end
    clean_text = "\n".join(cleaned_lines).strip()
    return clean_text

async def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Input file {INPUT_FILE} not found.")
        return

    print(f"Loading {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE)
    if df.empty:
        print("No jobs to process.")
        return

    # Add Status Column if missing
    if "Enrichment Status" not in df.columns:
        df["Enrichment Status"] = ""

    # Load existing finished jobs to avoid duplicates in output
    existing_urls = set()
    if os.path.exists(OUTPUT_FILE_AUTO):
        try:
            existing_df = pd.read_excel(OUTPUT_FILE_AUTO)
            if "URL" in existing_df.columns:
                existing_urls = set(existing_df["URL"].dropna().astype(str).tolist())
        except: pass

    jobs = df.to_dict('records')
    
    # Files for appending
    # We will append to the excel files rather than rewriting whole list every time if possible, 
    # but pandas to_excel usually rewrites. 
    # Better approach: Update the 'df' in memory and save 'df' periodically (Input file).
    # And append new rows to Output file list and save periodically.
    
    jobs_to_save_auto = []
    jobs_to_save_manual = []
    
    # --- ROBUST BROWSER MANAGEMENT ---
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        s_path = os.path.join(settings.CONFIG_DIR, "session.json")
        context = await browser.new_context(storage_state=s_path) if os.path.exists(s_path) else await browser.new_context()
        page = await context.new_page()

        print(f"Processing {len(jobs)} jobs for enrichment...")
        
        jobs_processed_since_restart = 0
        
        for i in range(len(jobs)):
            # Proactive Restart every 50 jobs to clear leaks
            if jobs_processed_since_restart >= 50:
                print("  [Maintenance] Restarting browser to prevent memory leaks...")
                try:
                    await browser.close()
                except: pass
                
                browser = await p.chromium.launch(headless=False)
                s_path = os.path.join(settings.CONFIG_DIR, "session.json")
                context = await browser.new_context(storage_state=s_path) if os.path.exists(s_path) else await browser.new_context()
                page = await context.new_page()
                jobs_processed_since_restart = 0
                
            job = jobs[i]
            
            # RESUME CHECK
            status_val = job.get("Enrichment Status", "")
            is_pending = (
                status_val is None or 
                (isinstance(status_val, float) and pd.isna(status_val)) or 
                str(status_val).strip() == "" or 
                str(status_val).lower() == "nan"
            )

            if not is_pending:
                print(f"[{i+1}/{len(jobs)}] Skipping (Status: {status_val}): {job.get('Title')}")
                continue
                
            url = job.get('URL')
            
            # STRICT URL VALIDATION to prevent "NaN" JSON errors
            if not url or pd.isna(url) or str(url).strip() == "" or str(url).lower() == "nan": 
                print(f"[{i+1}/{len(jobs)}] Skipping (Invalid URL): {job.get('Title')}")
                df.at[i, "Enrichment Status"] = "Invalid URL"
                continue
            
            url = str(url).strip() # Ensure it's a clean string
            
            if url in existing_urls:
                 print(f"[{i+1}/{len(jobs)}] Skipping (Found in Output): {job.get('Title')}")
                 df.at[i, "Enrichment Status"] = "Done"
                 continue

            print(f"[{i+1}/{len(jobs)}] Checking: {job.get('Title')}...")
            
            # --- PAGE ACTION WITH CRASH RECOVERY ---
            try:
                try:
                    await page.goto(url, timeout=45000)
                except Exception as pg_e:
                    err_str = str(pg_e)
                    print(f"  Page Load Error: {err_str}")
                    
                    # Detect Crash
                    if "Connection closed" in err_str or "Target closed" in err_str:
                         print("  [CRITICAL] Browser crashed! Restarting...")
                         try:
                            await browser.close()
                         except: pass
                         
                         browser = await p.chromium.launch(headless=False)
                         s_path = os.path.join(settings.CONFIG_DIR, "session.json")
                         context = await browser.new_context(storage_state=s_path) if os.path.exists(s_path) else await browser.new_context()
                         page = await context.new_page()
                         jobs_processed_since_restart = 0
                         # Retry logic could go here, but for now we skip to avoid infinite loops on bad URLs
                         continue
                    else:
                         continue # Normal timeout/error

                # Wait for critical elements
                try:
                    await page.wait_for_selector("button[data-testid='apply-button'], a[data-testid='apply-button']", timeout=5000)
                except:
                    print("  Apply button not found (Expired?). Skipping.")
                    df.at[i, "Enrichment Status"] = "Expired/NoButton"
                    jobs_processed_since_restart += 1
                    continue

                # Check Apply Button Text
                apply_btns = page.locator("button[data-testid='apply-button'], a[data-testid='apply-button']")
                btn_text = ""
                
                # Iterate to find the first button with text (skipping icon-only buttons in 'Similar Jobs')
                for btn_idx in range(await apply_btns.count()):
                    txt = await apply_btns.nth(btn_idx).inner_text()
                    if txt.strip():
                        btn_text = txt.strip()
                        break
                
                keywords_discard = [
                    "employer website", "Firmenwebseite", "website des arbeitgebers", 
                    "with the employer", "beim arbeitgeber", "external", "extern"
                ]
                
                is_easy_apply = False
                
                if any(bad in btn_text.lower() for bad in keywords_discard):
                    print(f"  External Application ('{btn_text}'). Saving to Manual list.")
                    jobs_to_save_manual.append(job)
                    df.at[i, "Enrichment Status"] = "Done (Manual)"
                else:
                    print(f"  Button text: '{btn_text}' -> Keeping.")
                    is_easy_apply = True

                if is_easy_apply:
                    try:
                        desc_el = page.locator("#job-posting-description").first 
                        if not await desc_el.count():
                             desc_el = page.locator("main").first 
                        
                        raw_desc = await desc_el.inner_text()
                        description = clean_description(raw_desc)
                    except:
                        description = "Description extraction failed."
                    
                    job['Job Description'] = description
                    jobs_to_save_auto.append(job)
                    df.at[i, "Enrichment Status"] = "Done"
                    print("  Success: Added to final list.")
                
            except Exception as e:
                print(f"  Error processing job: {e}")
                # Critical check in outer loop too
                if "Connection closed" in str(e) or "Target closed" in str(e):
                     print("  [CRITICAL] Browser/Context crashed in logic block! Restarting...")
                     try:
                        await browser.close()
                     except: pass
                     browser = await p.chromium.launch(headless=False)
                     s_path = os.path.join(settings.CONFIG_DIR, "session.json")
                     context = await browser.new_context(storage_state=s_path) if os.path.exists(s_path) else await browser.new_context()
                     page = await context.new_page()
                     jobs_processed_since_restart = 0
                continue
            
            jobs_processed_since_restart += 1
            
            # INCREMENTAL SAVE
            if len(jobs_to_save_auto) >= 1 or len(jobs_to_save_manual) >= 1:
                # Save Output Auto
                if jobs_to_save_auto:
                    new_df = pd.DataFrame(jobs_to_save_auto)
                    if os.path.exists(OUTPUT_FILE_AUTO):
                        try:
                            old_df = pd.read_excel(OUTPUT_FILE_AUTO)
                            combined = pd.concat([old_df, new_df], ignore_index=True)
                            combined.drop_duplicates(subset=["Title", "Company", "Location", "URL"], inplace=True)
                            combined.to_excel(OUTPUT_FILE_AUTO, index=False)
                        except Exception as e:
                            print(f"  Error saving Auto jobs: {e}")
                    else:
                        new_df.to_excel(OUTPUT_FILE_AUTO, index=False)
                    
                    for j in jobs_to_save_auto:
                        existing_urls.add(str(j.get("URL")))
                    jobs_to_save_auto = [] 

                # Save Output Manual
                if jobs_to_save_manual:
                    if os.path.exists(OUTPUT_FILE_MANUAL):
                        try:
                            old_df = pd.read_excel(OUTPUT_FILE_MANUAL)
                            combined = pd.concat([old_df, pd.DataFrame(jobs_to_save_manual)], ignore_index=True)
                            combined.drop_duplicates(subset=["Title", "Company", "Location", "URL"], inplace=True)
                            combined.to_excel(OUTPUT_FILE_MANUAL, index=False)
                        except:
                             pd.DataFrame(jobs_to_save_manual).to_excel(OUTPUT_FILE_MANUAL, index=False)
                    else:
                        pd.DataFrame(jobs_to_save_manual).to_excel(OUTPUT_FILE_MANUAL, index=False)
                    jobs_to_save_manual = [] 

                # Save Source File
                df.to_excel(INPUT_FILE, index=False)

        try:
            await browser.close()
        except: pass
        
    print(f"\nEnrichment complete.")
    
if __name__ == "__main__":
    asyncio.run(main())
