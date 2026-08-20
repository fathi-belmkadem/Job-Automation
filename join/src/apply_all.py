import asyncio
import os
import pandas as pd
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Add project root to path to allow importing config
sys.path.append(str(Path(__file__).parent.parent))
from config import settings
from src.apply import tailor_documents, compile_pdf, apply_to_job, detect_cv_template, clean_filename

# Note: genai.configure moved to ai_agent.py

async def main():
    if not os.path.exists(settings.FILTERED_JOBS_FILE):
        print("Excel file not found.")
        return

    df = pd.read_excel(settings.FILTERED_JOBS_FILE)
    if "Application Status" not in df.columns:
        df["Application Status"] = ""
        
    pending_df = df[(df["Filter Status"] == "Kept (Deep)") & (df["Application Status"].isna() | (df["Application Status"] == ""))]
    if pending_df.empty:
        print("No pending jobs found.")
        return

    print(f"Found {len(pending_df)} pending jobs.")
        
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False) 
            try:
                context = await browser.new_context(storage_state=settings.SESSION_FILE)
            except:
                print("   [Warn] Session file invalid/missing. Creating new context.")
                context = await browser.new_context()
                
            page = await context.new_page()
            
            count = 0
            for index, row in pending_df.iterrows():
                url = row["URL"]
                title_place = row.get("Title", "Unknown")
                print(f"\n[{count+1}/{len(pending_df)}] Processing: {url}")
                
                try:
                    # 1. Scrape Description
                    try:
                        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    except Exception as ex:
                        print(f"   [Error] Could not load URL: {ex}")
                        df.at[index, "Application Status"] = f"Error: Url Load ({str(ex)[:50]})"
                        continue

                    desc = await page.inner_text("body")
                    
                    try: page_title = await page.locator("h1").first.innerText()
                    except: page_title = title_place
                    
                    page_company = "Company"
                    if "/companies/" in url:
                        try:
                             page_company = url.split("/companies/")[1].split("/")[0].replace("-", " ").title()
                        except: pass
                    
                    # Check for "Already Applied"
                    if any(x in desc.lower() for x in ["you have already applied", "already applied", "bereits beworben"]):
                        print("   [Skip] Already applied (detected on page).")
                        df.at[index, "Application Status"] = "Applied (Manual)"
                        df.to_excel(settings.FILTERED_JOBS_FILE, index=False)
                        continue
                    
                    # 2. Folder Setup
                    clean_t = clean_filename(page_title)
                    clean_c = clean_filename(page_company) 
                    folder_name = f"{clean_t}_{clean_c}_{index}"
                    job_dir = settings.APPLICATIONS_DIR / folder_name
                    job_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 3. Check / Generate PDF
                    # 3. Check / Generate PDF / Load LaTeX
                    pdf_cv_name = f"{settings.PDF_NAME_PREFIX}_CV.pdf"
                    pdf_cl_name = f"{settings.PDF_NAME_PREFIX}_CoverLetter.pdf"
                    tex_cv_name = f"{settings.PDF_NAME_PREFIX}_CV.tex"
                    tex_cl_name = f"{settings.PDF_NAME_PREFIX}_CoverLetter.tex"
                    
                    path_cv = job_dir / pdf_cv_name
                    path_cl = job_dir / pdf_cl_name
                    path_cv_tex = job_dir / tex_cv_name
                    path_cl_tex = job_dir / tex_cl_name
                    
                    cv_tex, cl_tex = None, None

                    if path_cv.exists() and path_cl.exists():
                        print("   [Info] PDFs already exist. Using cached.")
                    elif path_cv_tex.exists() and path_cl_tex.exists():
                        print("   [Info] LaTeX files exist but PDFs are missing. Attempting re-compilation...")
                        with open(path_cv_tex, "r", encoding="utf-8") as f: cv_tex = f.read()
                        with open(path_cl_tex, "r", encoding="utf-8") as f: cl_tex = f.read()
                        
                        compile_pdf(cv_tex, str(job_dir), f"{settings.PDF_NAME_PREFIX}_CV")
                        compile_pdf(cl_tex, str(job_dir), f"{settings.PDF_NAME_PREFIX}_CoverLetter")
                    else:
                        print("   [AI] No cached documents found. Tailoring with AI...")
                        cv_template = detect_cv_template(url, page_title)
                        cv_tex, cl_tex = await tailor_documents(desc, page_title, page_company, cv_template)
                        
                        if cv_tex and cl_tex:
                            # compile_pdf saves .tex immediately
                            compile_pdf(cv_tex, str(job_dir), f"{settings.PDF_NAME_PREFIX}_CV")
                            compile_pdf(cl_tex, str(job_dir), f"{settings.PDF_NAME_PREFIX}_CoverLetter")
                        else:
                            print("   [Skip] Tailoring failed.")
                            df.at[index, "Application Status"] = "Error: Tailoring"
                            continue
                    
                    if not path_cv.exists():
                        print("   [Skip] CV PDF missing (compilation failed).")
                        df.at[index, "Application Status"] = "Error: Compilation"
                        continue

                    # 4. Apply
                    result = await apply_to_job(page, url, str(path_cv), str(path_cl), desc)
                    
                    if result == "Expired":
                        df.at[index, "Filter Status"] = "Expired"
                        df.at[index, "Application Status"] = "Skipped (Expired)"
                        print("   [Skip] Job is no longer available.")
                    elif result:
                        df.at[index, "Application Status"] = "Applied"
                        print("   [Success] Applied!")
                    else:
                        df.at[index, "Application Status"] = "Failed"
                        print("   [Failed] Could not submit.")
                    
                    df.to_excel(settings.FILTERED_JOBS_FILE, index=False)
                    count += 1
                    
                except Exception as e:
                    print(f"   [Error] Process Loop Exception: {e}")
                    df.at[index, "Application Status"] = f"Error: {str(e)}"
                    df.to_excel(settings.FILTERED_JOBS_FILE, index=False)

            await browser.close()
    finally:
        pass

if __name__ == "__main__":
    asyncio.run(main())
