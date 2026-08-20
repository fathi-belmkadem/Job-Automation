import asyncio
from playwright.async_api import async_playwright
import json
import urllib.parse
# from models import Job -> sys path needed first? "models" is in src, so sibling import works fine if run as module or same dir.
# But harvest.py is run as script.
import hashlib
import time
import os
import sys
import pandas as pd
from typing import List

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings
from src.models import Job # Explicit import if needed, or if models is local sibling:
# If calling from src/harvest.py, "import models" works. But to be safe with "src.models":
# Let's keep "from models import Job" assuming it is finding it in CWD (src).
# Actually if we add root to sys.path, we can do "from src.models import Job" which is cleaner.

INTERMEDIATE_FILE = settings.INTERMEDIATE_JOBS_PATH
KEYWORDS_FILE = settings.KEYWORDS_PATH

def generate_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

async def scrape_keyword(page, keyword: str) -> List[Job]:
    print(f"\n=== Scraping for keyword: '{keyword}' ===")
    base_url = "https://www.xing.com/jobs/search"
    # Filter for 'ENTRY_LEVEL', 'INTERN', 'STUDENT' if possible via URL params, 
    # but user asked for keywords to handle it. 
    # We'll rely on the keyword specifics for now + AI filtering later.
    params = {
        "keywords": keyword,
        "sincePeriod": "LAST_WEEK", # Keep it fresh
        "sc_o": "job_search_button"
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    
    try:
        await page.goto(url, timeout=30000)
        # Wait for the main list container or "No results"
        try:
             await page.wait_for_selector("article[data-testid='job-search-result'], [data-testid='no-results-headline']", timeout=10000)
        except:
             print(f"Timeout waiting for results for '{keyword}'. Skipping.")
             return []
    except Exception as e:
        print(f"Navigation error for '{keyword}': {e}")
        return []

    # Cookie consent check (Shadow DOM robust)
    print("Checking for cookie consent (Usercentrics Shadow DOM)...")
    # Cookie consent check (Shadow DOM robust recursive with retry)
    print("Checking for cookie consent (Recursive Shadow DOM search)...")
    
    for attempt in range(3):
        try:
            # Wait a bit for banner to animate in
            await page.wait_for_timeout(2000) 
            
            # Use recursive JS to find the button anywhere in shadow roots
            clicked = await page.evaluate("""() => {
                function findAndClick(root) {
                    // Check current root for the button
                    const btn = root.querySelector('button[data-testid="uc-accept-all-button"]');
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    // Recurse into all shadow roots
                    const all = root.querySelectorAll('*');
                    for (const el of all) {
                        if (el.shadowRoot) {
                            if (findAndClick(el.shadowRoot)) return true;
                        }
                    }
                    return false;
                }
                return findAndClick(document.body);
            }""")
            
            if clicked:
                print("  Clicked cookie consent button via Recursive JS.")
                await page.wait_for_timeout(3000) # Wait for animation
                # Removed automatic session save here to avoid overwriting login state with a guest session
                break
            else:
                 print(f"  Cookie button not found (attempt {attempt+1}/3).")

                     
        except Exception as e:
            print(f"  Cookie check warning: {e}")

    # Clean up duplicate inits
    # Clean up duplicate inits
    start_time = time.time()
    harvested_jobs = []
    # Load existing IDs to prevent re-scraping historical jobs
    existing_ids = set()
    if os.path.exists(INTERMEDIATE_FILE):
        try:
            edf = pd.read_csv(INTERMEDIATE_FILE)
            # Assuming 'URL' is the unique key we can hash or use directly
            # We generate ID from URL in this script.
            if "URL" in edf.columns:
                for u in edf["URL"].dropna():
                    u_str = str(u)
                    full_url = u_str if u_str.startswith("http") else "https://www.xing.com" + u_str
                    existing_ids.add(generate_id(full_url))
            print(f"  Loaded {len(existing_ids)} existing jobs to ignore.")
        except Exception as e:
            print(f"  Warning loading existing jobs: {e}")

    seen_ids_local = set(existing_ids)
    no_change_count = 0
    max_retries_no_change = 3 # Reduced for faster switching
    
    while True:
        # 1. Scrape current visible
        current_count = len(harvested_jobs)
        cards = await page.locator("article[data-testid='job-search-result']").all()
        # print(f"  [Debug] Found {len(cards)} cards in DOM.") 
        
        for idx_card, card in enumerate(cards):
            try:
                # Fast data extraction
                link_el = card.locator("a[href*='/jobs/']").first
                url_suffix = await link_el.get_attribute("href", timeout=500) 
                if not url_suffix: continue
                
                full_url = url_suffix if url_suffix.startswith("http") else "https://www.xing.com" + url_suffix
                job_id = generate_id(full_url)
                
                if job_id in seen_ids_local:
                    continue
                
                title = await card.locator("[data-testid='job-teaser-list-title']").inner_text()
                
                company_el = card.locator("p[class*='Company']")
                company = await company_el.inner_text() if await company_el.count() > 0 else "Unknown"
                
                # Blacklist Check
                if "tech staff solutions heidelberg gmbh" in company.lower():
                     print(f"  [Blocked] Skipping blacklisted company: {company}")
                     continue
                
                # Robust Location Extraction
                location = "Unknown"
                # Strategy 1: Look for location container
                loc_el = card.locator("div[class*='location'] p").first
                if await loc_el.count() > 0:
                    location = await loc_el.inner_text()
                else:
                    # Strategy 2: Heuristic - Find p tag that isn't company or time
                    ps = await card.locator("p").all()
                    for p in ps:
                        txt = await p.inner_text()
                        if txt == company: continue
                        if any(x in txt for x in ["ago", "vor", "hours", "Stunden", "Tagen", "days"]): continue
                        if len(txt) > 60: continue # Skip long teaser text
                        location = txt
                        break # Found it

                # Validator: Ensure crucial fields exist
                if not title or not full_url:
                    print("  [Warning] Skipped job with missing Title or URL.")
                    continue
                    
                # Validator: Check for blocking/anti-bot artifacts
                if title.lower() in ["einloggen", "login", "anmelden", "security check"]:
                    print("  [CRITICAL] Possible soft-block detected (Login prompting). Pausing...")
                    await page.wait_for_timeout(5000)
                    continue

                job = Job(title=title.strip(), company=company.strip(), location=location.strip(), url=full_url, id=job_id)
                # print(f"  [Debug] Extracted: {job.title[:20]}... | {job.company} | {job.location}") # Verification
                if len(harvested_jobs) == 0:
                     print(f"  [Sample] {job.title} | {job.company} | {job.location}")
                
                harvested_jobs.append(job)
                seen_ids_local.add(job_id)
            except Exception as extract_err:
                # print(f"  [Debug] Extraction failed for a card: {extract_err}")
                continue
        
        new_count = len(harvested_jobs)
        
        if new_count == current_count:
            no_change_count += 1
            print(f"  [Info] No new jobs. DOM: {len(cards)} vs Scraped: {new_count}. Retry: {no_change_count}/{max_retries_no_change}")
            
            # SMART EXIT: If we have scraped everything visible, and we retried once, we are likely done.
            if len(cards) <= new_count and no_change_count >= 2:
                 print("  Synced with DOM and no new jobs loading. Ending keyword.")
                 break
                 
            await page.wait_for_timeout(1000) 
        else:
            no_change_count = 0
            print(f"  Count: {new_count} (+{new_count - current_count})")
            
            # PROGRESSIVE SAVE:
            temp_data = []
            for j in harvested_jobs:
                temp_data.append({
                    "Keyword": keyword,
                    "Title": j.title,
                    "Company": j.company,
                    "Location": j.location,
                    "URL": j.url,
                    "ScrapedAt": time.strftime("%Y-%m-%d %H:%M:%S")
                })
            save_intermediate(temp_data)

        # Stop conditions

        # Stop conditions
        if no_change_count >= max_retries_no_change:
            print("  Stuck: No new jobs for many cycles. Assuming end of list.")
            break
            
        if len(harvested_jobs) >= 200: 
            print("  Limit reached (200). Moving to next keyword.")
            break

        # 2. Trigger Load (Hybrid: JS for speed, Keys for events)
        # Fast JS scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)
        
        # Wiggle with keys to trigger lazy load listeners
        await page.keyboard.press("PageUp")
        await page.wait_for_timeout(200)
        await page.keyboard.press("End")
        await page.wait_for_timeout(800)

        # 3. Handle 'Show more' button
        show_more_selectors = [
            "button[data-testid='load-more-button']", 
            "button:has-text('Show more')",
            "button:has-text('Mehr anzeigen')",
            "button:has-text('Load more')"
        ]
        
        clicked_show_more = False
        for sel in show_more_selectors:
            try:
                # Use first() to get the handle
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=500): # Fast check
                    print(f"  Found 'Show more' ({sel}). Clicking...")
                    try:
                        await btn.hover()
                        await page.wait_for_timeout(200)
                        await btn.click()
                        print("  Clicked. Waiting for update...")
                        
                        # Wait for DOM to update
                        current_dom_count = len(cards)
                        try:
                            # Wait max 10s, but return immediately when found
                            await page.wait_for_function(
                                f"document.querySelectorAll('article[data-testid=\"job-search-result\"]').length > {current_dom_count}", 
                                timeout=10000 
                            )
                            print("  Success: List grew.")
                        except:
                            print("  Warning: List didn't grow after click (or timed out).")

                        clicked_show_more = True
                        no_change_count = 0 
                        break
                    except Exception as click_err:
                        print(f"  Click failed: {click_err}. Force clicking...")
                        await btn.click(force=True)
                        await page.wait_for_timeout(2000)
                        clicked_show_more = True
                        no_change_count = 0
                        break
            except:
                continue

    print(f"  Finished '{keyword}': {len(harvested_jobs)} jobs.")
    return harvested_jobs

def save_intermediate(new_jobs: List[dict]):
    if not new_jobs: 
        return

    print(f"  [Debug] Saving {len(new_jobs)} jobs. First item keys: {list(new_jobs[0].keys())}")
    # Verify first item content
    first_title = new_jobs[0].get('Title', 'MISSING')
    print(f"  [Debug] First Title: {first_title}")

    try:
        new_df = pd.DataFrame(new_jobs)
        
        # STRICT CLEANING: Drop rows with missing Title or URL
        before_len = len(new_df)
        new_df = new_df.dropna(subset=['Title', 'URL'])
        new_df = new_df[new_df['Title'].astype(str).str.strip() != ""]
        new_df = new_df[new_df['URL'].astype(str).str.strip() != ""]
        after_len = len(new_df)
        
        if before_len != after_len:
            print(f"  [Warning] Dropped {before_len - after_len} invalid rows from new batch.")

        if new_df.empty:
            print("  [Warning] new_df is empty after cleaning. Skipping save.")
            return

        if os.path.exists(INTERMEDIATE_FILE):
            try:
                existing_df = pd.read_csv(INTERMEDIATE_FILE)
                # Align columns if necessary? (Unlikely if we generated both)
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            except Exception as read_err:
                print(f"  Warning: Could not read existing {INTERMEDIATE_FILE}, starting fresh. ({read_err})")
                combined_df = new_df
        else:
            combined_df = new_df
            
        # Deduplicate
        combined_df.replace("", pd.NA, inplace=True)
        combined_df.dropna(subset=['Title', 'URL'], inplace=True)
        # Verify we don't have NaN titles
        null_titles = combined_df['Title'].isnull().sum()
        if null_titles > 0:
            print(f"  [CRITICAL] Found {null_titles} rows with NULL Title in combined_df! Dropping them.")
            combined_df = combined_df.dropna(subset=['Title'])

        combined_df.drop_duplicates(subset=["Title", "Company", "Location", "URL"], keep="last", inplace=True)
        
        try:
            combined_df.to_csv(INTERMEDIATE_FILE, index=False)
            print(f"Saved {len(combined_df)} total unique jobs to {INTERMEDIATE_FILE} (Appended {len(new_df)} new)")
        except Exception as save_err:
             print(f"  [ERROR] Failed to write CSV: {save_err}")

    except Exception as e:
        print(f"Error preparing data for save: {e}")

async def main():
    # Load keywords
    if not os.path.exists(KEYWORDS_FILE):
        print(f"No {KEYWORDS_FILE} found.")
        return

    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        keywords = json.load(f)

    if not keywords:
        print("No keywords found.")
        return
        
    all_jobs_data = []

    async with async_playwright() as p:
        # Initial Browser Launch
        browser = await p.chromium.launch(headless=False)
        context = await create_context(browser)
        page = await context.new_page()

        total_keywords = len(keywords)
        
        for idx, kw in enumerate(keywords):
            print(f"Processing {idx+1}/{total_keywords}: {kw}")
            
            try:
                # Check if page/browser is alive before starting
                if page.is_closed():
                     raise Exception("Page closed unexpectedly before start.")
                     
                jobs = await scrape_keyword(page, kw)
                
                for j in jobs:
                    all_jobs_data.append({
                        "Keyword": kw,
                        "Title": j.title,
                        "Company": j.company,
                        "Location": j.location,
                        "URL": j.url,
                        "ScrapedAt": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                if all_jobs_data:
                    save_intermediate(all_jobs_data)
                    
            except Exception as e:
                print(f"CRITICAL ERROR scraping '{kw}': {e}")
                print("  Attempting to restart browser environment...")
                
                # Hard Reset
                try:
                    await browser.close()
                except:
                    pass
                    
                try:
                    browser = await p.chromium.launch(headless=False)
                    context = await create_context(browser)
                    page = await context.new_page()
                    print("  Browser restarted successfully.")
                except Exception as restart_error:
                    print(f"  Failed to restart browser: {restart_error}")
                    break # Fatal

        print("\nAll keywords processed.")
        try:
            await browser.close()
        except:
            pass

async def create_context(browser):
    s_path = os.path.join(settings.CONFIG_DIR, "session.json")
    # Force locale to English to ensure text-based selectors ('Show more', etc.) work consistently
    context_args = {
        "locale": "en-GB",
        "timezone_id": "Europe/Berlin"
    }
    
    if os.path.exists(s_path):
        try:
            print(f"  Loading session from {s_path} (Forcing English locale)")
            return await browser.new_context(storage_state=s_path, **context_args)
        except Exception as e:
             print(f"  Could not load session.json: {e}. Creating fresh context.")
    
    return await browser.new_context(**context_args)


if __name__ == "__main__":
    asyncio.run(main())
