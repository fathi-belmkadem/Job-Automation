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

from .ai_agent import find_element_with_ai, answer_questions, tailor_cover_letter
from .utils import handle_cookies

async def apply_to_job(page, url, cv_path, job_dir=None, job_data=None):
    print(f"   [APPLYING] {url}")
    
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Dismiss cookie banner if it exists
        await handle_cookies(page)
        
        # A. Click Apply
        # Check if it's an external apply (Apply on company site)
        # Usually "Easy Apply" has data-testid='apply-button'
        apply_btns = page.locator("button[data-testid='apply-button'], a[data-testid='apply-button']")
        apply_btn = None
        btn_text = ""
        
        # Iterate to find the actual button with text (skipping icon-only buttons from 'Similar Jobs')
        for btn_idx in range(await apply_btns.count()):
            txt = await apply_btns.nth(btn_idx).inner_text()
            if txt.strip():
                btn_text = txt.strip()
                apply_btn = apply_btns.nth(btn_idx)
                break
                
        # Fallback to first if all are empty
        if apply_btn is None and await apply_btns.count() > 0:
            apply_btn = apply_btns.first
            btn_text = await apply_btn.inner_text()
        
        if apply_btn is not None:
            print(f"   Found Apply Button: '{btn_text}'")

            # Check for external application text (French, English, German)
            external_keywords = [
                "consulter le site web", 
                "company site", 
                "arbeitgeber-website", 
                "website des arbeitgebers",
                "visit company website",
                "apply on company site",
                "auf unternehmenswebseite"
            ]
            
            if btn_text and any(k in btn_text.lower() for k in external_keywords):
                print(f"   Button text '{btn_text}' indicates external application. Skipping.")
                return "Skipped (External)"
            
            # Heuristic: If it says "Apply on company site" or similar, we might want to skip or handle differently
            # For now, we click. If it opens a new tab, we need to handle that.
            
            # We assume it opens the modal ON THIS PAGE.
            await apply_btn.click(force=True)
            await page.wait_for_timeout(4000)
            
            # Check if we were redirected?
            if "xing.com/jobs" not in page.url and "login" not in page.url:
                 print(f"   Redirected to external site ({page.url}). Marking as External.")
                 return "External Application"
                 
        else:
            print("   'Easy Apply' button not found via standard selectors. Trying AI...")
            ai_btn = await find_element_with_ai(page, "Apply to this job / Easy Apply")
            if ai_btn:
                print("   AI found Apply button. Clicking...")
                await ai_btn.click(force=True)
                await page.wait_for_timeout(4000)
            else:
                print("   'Easy Apply' button not found. Likely external.")
                return "Skipped (External/No Button)"


        # B. Click Edit (The "Secret" Step)
        print("   Looking for Edit button...")
        # English, German, French
        edit_btn = page.locator("button, a").filter(has_text=re.compile(r"Edit your application|Bewerbung bearbeiten|Modifier|Continuer", re.IGNORECASE)).first
        
        if await edit_btn.count() > 0:
            await edit_btn.click(force=True)
            await page.wait_for_timeout(3000)
        else:
            print("   Edit button not found (Might be already in form?). Proceeding...")

        # C. Navigate Multi-Step Form & CV Management
        upload_visible = False
        print("   Navigating multi-step form...")
        
        max_steps = 5
        remove_btn = None
        
        for step in range(max_steps):
            await page.wait_for_timeout(2000)
            
            # 1. Check if Upload is visible
            upload_btn = page.locator("button, span").filter(has_text=re.compile(r"Upload file|Upload CV|Lebenslauf hochladen|Télécharger|Importer", re.IGNORECASE)).first
            if await upload_btn.count() > 0 and await upload_btn.is_visible():
                upload_visible = True
                print("   Reached CV section (Upload visible).")
                break
                
            # 2. Check if Remove is visible
            remove_btn = page.locator("button[aria-label*='Remove'], button[aria-label*='Löschen'], button[aria-label*='Supprimer'], button[data-testid*='delete'], button[data-testid*='remove']").first
            
            if await remove_btn.count() == 0 or not await remove_btn.is_visible():
                cv_text = page.locator("text=CV").or_(page.locator("text=Lebenslauf")).first
                if await cv_text.count() > 0:
                     remove_btn = cv_text.locator("xpath=./following-sibling::div//button").first
                     if await remove_btn.count() == 0:
                         remove_btn = cv_text.locator("xpath=./ancestor::div[contains(@class, 'selectable-card')]//button").first

            if remove_btn and await remove_btn.count() > 0 and await remove_btn.is_visible():
                print("   Reached CV section (Existing CV found).")
                break
                
            # 3. If neither, try to click Continue
            if job_dir and job_data:
                cv_tex_path = os.path.join(job_dir, settings.FINAL_PDF_NAME.replace(".pdf", ".tex"))
                await answer_questions(page, job_data, cv_tex_path)
                
            continue_btn = page.locator("button").filter(has_text=re.compile(r"Continue|Next|Weiter|Fortfahren", re.IGNORECASE)).first
            if await continue_btn.count() > 0 and await continue_btn.is_visible():
                print(f"   Clicking Continue (Step {step+1})...")
                await continue_btn.click()
                await page.wait_for_timeout(3000)
            else:
                break
                
        # D. CV Removal (if needed)
        if not upload_visible and remove_btn and await remove_btn.count() > 0 and await remove_btn.is_visible():
            print("   Removing existing CV...")
            await remove_btn.click(force=True)
            try:
                # Wait for Upload CV OR Lebenslauf hochladen OR Upload file
                await page.wait_for_function(
                    "document.body.innerText.includes('Upload CV') || document.body.innerText.includes('Lebenslauf hochladen') || document.body.innerText.includes('Upload file')",
                    timeout=5000
                )
                upload_visible = True
            except:
                print("   Remove clicked, but Upload option didn't appear. Forcing upload visible flag.")
                upload_visible = True
        elif not upload_visible:
            print("   Could not find Remove button or Upload button.")

        # E. Upload
        if upload_visible:
            print("   Uploading CV...")
            target = page.locator("button, span").filter(has_text=re.compile(r"Upload file|Upload CV|Lebenslauf hochladen|Télécharger|Importer", re.IGNORECASE)).first
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await target.click(force=True)
            
            file_chooser = await fc_info.value
            await file_chooser.set_files(cv_path)
            
            # Wait for file to appear in UI (Same Name, but strict remove ensures state change)
            # Since we removed it first, appearance is proof.
            await page.wait_for_selector(f"text={settings.FINAL_PDF_NAME}", timeout=20000)
            print("   CV Upload Confirmed.")
            
        else:
            print("   Upload Failed (UI not ready).")
            if job_dir:
                await page.screenshot(path=os.path.join(job_dir, "error_upload_ui_not_ready.png"))
            # If we simply can't find upload/remove, maybe it's already perfect? 
            # But user said "force it". Failing safe.
            return "Failed (Upload Error)"
            
        # D2. Optional Documents
        # Check for "Add more documents"
        print("   Checking for Optional Documents...")
        add_more_btn = page.locator("div[class*='text-button-styles__InnerContent']").filter(has_text="Add more documents").first
        if await add_more_btn.count() == 0:
             # Try search by text strictly
             add_more_btn = page.locator("text=Add more documents (optional)").first
             if await add_more_btn.count() == 0:
                 add_more_btn = page.locator("text=Weitere Dokumente hinzufügen").first
                 if await add_more_btn.count() == 0:
                     add_more_btn = page.locator("text=Ajouter d'autres documents").first

        if await add_more_btn.count() > 0:
            print("   Start 'Optional Documents' Flow...")
            
            # 1. Generate Cover Letter
            cl_pdf_path = None
            if job_dir and job_data:
                # We need the CV tex path
                cv_tex_path = os.path.join(job_dir, settings.FINAL_PDF_NAME.replace(".pdf", ".tex"))
                cl_pdf_path = await tailor_cover_letter(
                    job_dir, 
                    job_data['Company'], 
                    job_data['Title'], 
                    job_data['Job Description'], 
                    cv_tex_path
                )
            
            # 2. Collect files to upload
            files_to_upload = []
            if cl_pdf_path:
                files_to_upload.append(cl_pdf_path)
                
            # Add Certificates
            if os.path.exists(settings.OPTIONAL_FILES_DIR):
                for f in os.listdir(settings.OPTIONAL_FILES_DIR):
                    if f.lower().endswith(".pdf"):
                        full_p = os.path.join(settings.OPTIONAL_FILES_DIR, f)
                        files_to_upload.append(full_p)
            
            print(f"   Files to upload: {len(files_to_upload)}")
            
            if files_to_upload:
                # SEQUENTIAL STRATEGY: 
                # 1. Upload Cover Letter First (highest priority).
                # 2. Try to upload additional files if the form allows.
                # 3. Gracefully stop if form only allows limited uploads.
                
                print("   [Sequential Upload] Starting...")
                uploaded_count = 0
                
                for i, f_path in enumerate(files_to_upload):
                    fname = os.path.basename(f_path)
                    print(f"   [Upload #{i+1}/{len(files_to_upload)}] Attempting: {fname}")
                    
                    try:
                        # Re-locate the "Add more" button each iteration (it may disappear after 1 upload)
                        add_more_current = page.locator("div[class*='text-button-styles__InnerContent']").filter(has_text="Add more documents").first
                        if await add_more_current.count() == 0:
                            add_more_current = page.locator("text=Add more documents (optional)").first
                        if await add_more_current.count() == 0:
                            add_more_current = page.locator("text=Weitere Dokumente hinzufügen").first
                        
                        # Check if "Add more" is still available
                        if await add_more_current.count() == 0 or not await add_more_current.is_visible():
                            if uploaded_count > 0:
                                print(f"   [Upload] 'Add more' button no longer visible after {uploaded_count} upload(s). Form limit reached - continuing without remaining files.")
                            else:
                                print(f"   [Upload] 'Add more' button not visible. Skipping optional uploads.")
                            break
                        
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await add_more_current.click(force=True)
                        file_chooser = await fc_info.value
                        
                        await file_chooser.set_files([f_path])
                        await page.wait_for_timeout(2000)
                        
                        # Validation: Check for Error messages
                        error_loc = page.locator("div[class*='FormElement-styles__Error'], div[role='alert'], p[class*='error'], span[class*='error']").first
                        if await error_loc.count() > 0 and await error_loc.is_visible():
                            err_text = await error_loc.inner_text()
                            print(f"   [Upload #{i+1}] Error detected: {err_text}")
                            if uploaded_count > 0:
                                print(f"   Successfully uploaded {uploaded_count} file(s) before limit. Continuing...")
                            else:
                                print(f"   First upload failed, but continuing with application...")
                            break
                        
                        uploaded_count += 1
                        print(f"   [Upload #{i+1}] Success.")
                        
                    except Exception as e:
                        print(f"   [Upload #{i+1}] Failed/Skipped: {e}")
                        if uploaded_count > 0:
                            print(f"   Already uploaded {uploaded_count} file(s). Continuing with application...")
                        # Continue to next file or proceed with application
                        continue
                
                if uploaded_count > 0:
                    print(f"   [Optional Docs] Uploaded {uploaded_count} of {len(files_to_upload)} file(s).")  

        else:
            print("   'Add more documents' not found. Skipping.")

        # E. Phone
        phone_loc = page.locator("input[type='tel'], input[name*='phone']").first
        if await phone_loc.count() > 0:
            await phone_loc.fill(settings.PHONE_NUMBER)

        # E2. Smart Questions
        if job_dir and job_data:
             cv_tex_path = os.path.join(job_dir, settings.FINAL_PDF_NAME.replace(".pdf", ".tex"))
             await answer_questions(page, job_data, cv_tex_path)

        # F. Submit
        submit_btn = page.locator("button[class*='SubmitButton'], button").filter(has_text=re.compile(r"Submit application|Bewerbung absenden|Envoyer|Postuler", re.IGNORECASE)).first
        
        if await submit_btn.count() == 0:
            print("   Submit button not found via standard selectors. Trying AI...")
            submit_btn = await find_element_with_ai(page, "Submit application / Send application")

        if submit_btn and await submit_btn.count() > 0:
            await submit_btn.scroll_into_view_if_needed()
            await asyncio.sleep(2)
            print("   Clicking Submit...")
            await submit_btn.click()
            
            # CRITICAL FIX: Wait for submission to actually happen
            print("   Waiting for submission to complete...")
            await asyncio.sleep(10) 
            
            # Optional: Check for success message
            if await page.locator("text=Application sent").or_(page.locator("text=successfully")).count() > 0:
                 print("   Confirmed: Success message detected.")
            
            print("   Submitted.")
            return f"Sent at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        else:
            print("   Submit button not found.")
            return "Failed (No Submit)"


    except Exception as e:
        print(f"   Apply Error: {e}")
        try:
            if job_dir:
                await page.screenshot(path=os.path.join(job_dir, "error_fatal_exception.png"))
        except:
            pass
        return f"Failed ({str(e)[:30]})"

