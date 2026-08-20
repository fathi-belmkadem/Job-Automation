import asyncio
import os
import pandas as pd
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
from config import settings

def clean_description(text):
    """
    Cleans raw job description text.
    """
    if not text: return ""
    # Remove excessive whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return "\n".join(lines)

async def main():
    if not os.path.exists(settings.FILTERED_JOBS_FILE):
        print(f"File not found: {settings.FILTERED_JOBS_FILE}")
        return

    df = pd.read_excel(settings.FILTERED_JOBS_FILE)
    if "Job Description" not in df.columns:
        df["Job Description"] = ""
    if "Enrichment Status" not in df.columns:
        df["Enrichment Status"] = ""

    pending_df = df[
        (df["Job Description"].isna() | (df["Job Description"] == "")) & 
        (df["Enrichment Status"] != "Skipped (Broken/Expired)")
    ]
    if pending_df.empty:
        print("No jobs need enrichment.")
        return

    print(f"Enriching {len(pending_df)} jobs...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=settings.SESSION_FILE) if os.path.exists(settings.SESSION_FILE) else await browser.new_context()
        page = await context.new_page()

        for index, row in pending_df.iterrows():
            url = row["URL"]
            print(f"   [{index}] Enriching: {url}")
            
            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
                
                # Check for "Job no longer available" or 404 indicators
                expired_keywords = ["no longer available", "nicht mehr verfügbar", "archived", "archiviert", "can't find this page", "seite nicht gefunden"]
                body_text = await page.inner_text("body")
                if any(k in body_text.lower() for k in expired_keywords):
                    df.at[index, "Filter Status"] = "Expired/404"
                    df.at[index, "Enrichment Status"] = "Skipped (Broken/Expired)"
                    print(f"      [Expired/404] Job is no longer available or page not found.")
                    continue

                # Try specific selectors first
                raw_text = ""
                selectors = [
                    '[data-testid="job-description"]',
                    '.job-description',
                    '#job-description',
                    'main article',
                    'main'
                ]
                
                for sel in selectors:
                    loc = page.locator(sel)
                    if await loc.count() > 0:
                        raw_text = await loc.inner_text()
                        if len(raw_text) > 100:
                            break
                
                if not raw_text:
                    raw_text = await page.inner_text("body")
                
                clean_text = clean_description(raw_text)
                
                if len(clean_text) > 100:
                    df.at[index, "Job Description"] = clean_text
                    df.at[index, "Enrichment Status"] = "Enriched"
                    print(f"      Success ({len(clean_text)} chars)")
                else:
                    df.at[index, "Enrichment Status"] = "Failed (Too Short)"
                    print(f"      Failed: Description too short ({len(clean_text)} chars).")
                
            except Exception as e:
                print(f"      Error: {e}")
                df.at[index, "Enrichment Status"] = f"Error: {str(e)[:30]}"
            
            # Incremental save
            df.to_excel(settings.FILTERED_JOBS_FILE, index=False)
            await asyncio.sleep(1)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
