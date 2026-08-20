import asyncio
import os
import sys
import pandas as pd
import random
import re
import subprocess
import shutil
from datetime import datetime
from playwright.async_api import async_playwright
import google.generativeai as genai

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

# --- CONFIGURATION used from settings ---
# settings.JOBS_DB_PATH
# settings.APPLICATIONS_DIR
# settings.CV_PROMPT_PATH
# settings.CV_TEMPLATE_STUDENT
# settings.CV_TEMPLATE_FULLTIME
# settings.LATEX_COMPILER_URL
# settings.PHONE_NUMBER
# settings.FINAL_PDF_NAME
# settings.COVER_LETTER_TEMPLATE
# settings.COVER_LETTER_PROMPT_PATH
# settings.OPTIONAL_FILES_DIR
# settings.GOOGLE_API_KEY

if not settings.GOOGLE_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env (checked via settings)")
genai.configure(api_key=settings.GOOGLE_API_KEY)

# --- 1. CLASSIFICATION & TEMPLATE SELECTION ---

from apply.utils import get_cv_template
from apply.compiler import compile_cv
from apply.ai_agent import tailor_cv, tailor_cover_letter
from apply.browser import apply_to_job

async def main():
    print("--- XING AUTO-APPLY ---")
    
    if not os.path.exists(settings.JOBS_DB_PATH):
        print("Excel not found.")
        return
        
    df = pd.read_excel(settings.JOBS_DB_PATH)
    if "Status" not in df.columns:
        df["Status"] = ""
        
    # Get pending jobs
    pending_jobs = df[df["Status"].isna() | (df["Status"].astype(str).str.strip() == "")].index.tolist()
    print(f"Found {len(pending_jobs)} jobs to process.")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) 
        # Optionally load session
        session_path = "session.json" # OR settings.SESSION_PREFIX + ".json"
        # We need to find session.json. It was moved to config/session.json or output?
        # My settings said CONFIG_DIR/session (prefix).
        # Let's assume it is config/session.json
        session_path = os.path.join(settings.CONFIG_DIR, "session.json")
        context_args = {"locale": "en-GB"}
        if os.path.exists(session_path):
             context = await browser.new_context(storage_state=session_path, **context_args)
        else:
             context = await browser.new_context(**context_args)
        
        for idx in pending_jobs:

            row = df.loc[idx]
            title = str(row.get("Title", ""))
            company = str(row.get("Company", ""))
            location = str(row.get("Location", "Unknown"))
            url = str(row.get("URL", ""))
            desc = str(row.get("Job Description", ""))
            
            if not url or "xing.com" not in url:
                print(f"Skipping Invalid URL: {url}")
                continue
                
            job_type = str(row.get("Type", ""))
            
            # 1. Template
            template_path = get_cv_template(title, company, job_type)
            
            # 2. Tailor
            # Pass Index (idx) to ensure uniqueness
            job_dir, success = await tailor_cv(idx, company, title, location, desc, template_path)
            if not success:
                print("Tailor failed. Skipping.")
                continue
                
            # 3. Compile
            success = await compile_cv(job_dir)
            if not success:
                print("Compile failed. Skipping.")
                continue
                
            # 4. Apply
            cv_path = os.path.join(job_dir, settings.FINAL_PDF_NAME)
            page = await context.new_page()
            job_data = {
                "Company": company,
                "Title": title,
                "Job Description": desc
            }
            try:
                status = await apply_to_job(page, url, cv_path, job_dir=job_dir, job_data=job_data)
            finally:
                await page.close()
                
            # 5. Update Status
            df.at[idx, "Status"] = status
            df.to_excel(settings.JOBS_DB_PATH, index=False)
            print(f"   Status Updated: {status}\n")
            
            await asyncio.sleep(random.uniform(5, 10))
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
