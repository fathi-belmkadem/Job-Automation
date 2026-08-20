import asyncio
from datetime import datetime
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config import settings
from .ai_agent import get_ai_answer, answer_questions

async def apply_to_job(page, url, cv_path, cl_path, job_desc):
    """
    Navigates to URL and fills the application form.
    """
    print(f"   [Playwright] Navigating to {url}...")
    try:
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # Check for expired job
        expired_keywords = ["no longer available", "nicht mehr verfügbar"]
        body_text = await page.inner_text("body")
        if any(k in body_text.lower() for k in expired_keywords):
            print(f"   [Playwright] Job is EXPIRED. Skipping.")
            return "Expired"

        print("   [Playwright] Starting application process...")
    except Exception as e:
        print(f"   [Error] Page load failed: {e}")
        return False
    
    # Click Apply Button with retry loop
    print("   [Apply] Clicking 'Apply' button...")
    applied_clicked = False
    max_apply_attempts = 3
    
    for attempt in range(max_apply_attempts):
        # Priority 1: data-testid (Standard Join.com)
        try:
            apply_btn = page.locator('button[data-testid="ApplyButton"]')
            if await apply_btn.count() > 0 and await apply_btn.first.is_visible():
                print("   [Apply] Found ApplyButton via data-testid.")
                await apply_btn.first.click(timeout=5000)
                applied_clicked = True
                break
        except: pass
        
        # Priority 2: Multilingual Text (expanded list)
        if not applied_clicked:
            apply_texts = [
                "Apply now", "Apply for this job", "Apply",
                "Jetzt bewerben", "Bewerben", "Bewerbung einreichen",
                "Postuler", "Postuler maintenant", "Candidater",
                "Quick Apply", "Easy Apply"
            ]
            for txt in apply_texts:
                try:
                    btn = page.get_by_role("button", name=txt)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click(timeout=5000)
                        applied_clicked = True
                        break
                except: pass
                
                # Also try text locator as fallback
                if not applied_clicked:
                    try:
                        btn = page.locator(f"button:has-text('{txt}')")
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await btn.first.click(timeout=5000)
                            applied_clicked = True
                            break
                    except: pass
            
            if applied_clicked:
                break
        
        if not applied_clicked and attempt < max_apply_attempts - 1:
            print(f"   [Apply] Button not found (attempt {attempt+1}/{max_apply_attempts}), waiting 2s...")
            await asyncio.sleep(2)
             
    if not applied_clicked:
        print("   [Error] Could not find Apply/Postuler button.")
        return False

    # Wait for form
    await page.wait_for_load_state("networkidle")

    # --- CV Upload ---
    # Delete existing if any (TrashIcon or 'Remove file')
    print("   [Form] Checking for existing CV...")
    remove_names = ["Remove file", "Datei löschen", "Supprimer le fichier", "Eliminar archivo", "Rimuovi file"]
    try:
        removed = False
        # Try TrashIcon first
        trash = page.locator('button:has(svg[name="TrashIcon"])')
        if await trash.count() > 0 and await trash.first.is_visible():
            print("   [Form] Removing existing CV (via icon)...")
            await trash.first.click()
            removed = True
        
        # Try by text if not removed
        if not removed:
            for name in remove_names:
                rm_btn = page.get_by_role("button", name=name)
                if await rm_btn.count() > 0 and await rm_btn.first.is_visible():
                    print(f"   [Form] Removing existing CV (via '{name}')...")
                    await rm_btn.first.click()
                    removed = True
                    break
        
        if removed:
            await asyncio.sleep(2)
            await page.wait_for_load_state("networkidle")
    except Exception as e:
        print(f"   [Warn] CV removal issue: {e}")

    # Upload CV
    print("   [Form] Uploading CV...")
    
    # Try direct input first
    file_input = page.locator("input[type='file']").first
    if await file_input.count() > 0:
         print("   [Form] Found file input. Setting files directly.")
         try:
            await file_input.set_input_files(cv_path, timeout=5000)
            print("   [Form] Upload successful (direct).")
            # Skip the file chooser logic
            await page.wait_for_timeout(3000)
         except Exception as e:
            print(f"   [Form] Direct upload failed: {e}. Trying via button...")
            # Fall through to button click
    
    # If direct didn't work or wasn't found, try button
    # Check if we still need to upload (maybe direct worked)
    # We'll check for upload buttons
    upload_names = ["Upload CV", "Importer le CV", "Lebenslauf", "Resume", "Upload", "Datei auswählen"]
    upload_btn = None
    for txt in upload_names:
        btn = page.locator(f"text={txt}").first
        if await btn.count() > 0 and await btn.first.is_visible():
            upload_btn = btn
            break
    
    if upload_btn:
        print(f"   [Form] Clicking '{await upload_btn.inner_text()}'...")
        try:
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await upload_btn.click()
                file_chooser = await fc_info.value
                await file_chooser.set_files(cv_path)
            print("   [Form] Upload successful (button).")
        except Exception as e:
             print(f"   [Error] File chooser failed: {e}")
    else:
        # Final check if it was actually uploaded already by direct method
        # If we see 'Remove file' or TrashIcon now, it means it's uploaded
        is_uploaded = await page.locator('button:has(svg[name="TrashIcon"])').count() > 0 or \
                      any([await page.get_by_role("button", name=n).count() > 0 for n in remove_names])
        
        if not is_uploaded:
             print("   [Error] No file input or Upload button found for CV.")
        else:
             print("   [Form] CV appears to be uploaded.")
                  
    print("   [Form] Waiting for upload to process...")
    await page.wait_for_timeout(5000) 
    
    # Continue after CV
    print("   [Form] Attempting to click Continue...")
    cont_clicked = False
    try:
        continue_names = ["Continue", "Continuer", "Weiter", "Next", "Suivant", "Avanti", 
                         "Continuar", "Siguiente", "Próximo", "Volgende", "Dalej", "Nästa",
                         "Verder", "Fortsæt", "Jatka", "Nastavi"]
        for name in continue_names:
            btn = page.get_by_role("button", name=name)
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click(timeout=5000)
                cont_clicked = True
                break
        
        if not cont_clicked:
            for txt in ["Continue", "Continuer", "Weiter", "Next", "Continuar", "Seguinte", "Avanti"]:
                btn = page.locator(f"button:has-text('{txt}')")
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click(timeout=5000)
                    cont_clicked = True
                    break
        
        if cont_clicked:
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
        else:
            print("   [Warn] No Continue button found. Proceeding anyway...")
            
    except Exception as e:
        print(f"   [Warn] Continue click issue: {e}. Proceeding anyway...")

    # --- Cover Letter ---
    page_content = await page.inner_text("body")
    cl_keywords = [
        "Cover letter", "cover_letter", "coverletter",
        "Anschreiben", "Motivationsschreiben",
        "Lettre de motivation",
        "Carta de presentación", "carta de motivación", "Cargue su carta",
        "Lettera di presentazione", "Lettera",
        "Carta de apresentação", "Carta de motivação",
        "Motivatiebrief", "List motywacyjny"
    ]
    is_cl_page = any(kw.lower() in page_content.lower() for kw in cl_keywords)
    
    if is_cl_page:
        print("   [Form] Processing Cover Letter...")
        # Check if already uploaded
        try:
            removed_cl = False
            trash_cl = page.locator('button:has(svg[name="TrashIcon"])')
            if await trash_cl.count() > 0 and await trash_cl.first.is_visible():
                print("   [Form] Removing existing Cover Letter...")
                await trash_cl.first.click()
                removed_cl = True
                await asyncio.sleep(1)
            
            if not removed_cl:
                for name in ["Remove file", "Datei löschen", "Supprimer le fichier"]:
                    btn = page.get_by_role("button", name=name)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        print(f"   [Form] Removing existing CL (via '{name}')...")
                        await btn.first.click()
                        removed_cl = True
                        await asyncio.sleep(1)
                        break
        except: pass

        print("   [Form] Uploading Cover Letter...")
        try:
            # Try direct
            file_input = page.locator("input[type='file']").first
            cl_uploaded = False
            if await file_input.count() > 0 and cl_path:
                try:
                    await file_input.set_input_files(cl_path, timeout=5000)
                    cl_uploaded = True
                    print("   [Form] CL upload successful (direct).")
                    await asyncio.sleep(2)
                except: pass
            
            # Try button if not uploaded
            if not cl_uploaded:
                cl_btn = None
                for txt in ["Upload", "Anschreiben hochladen", "Charger"]:
                    btn = page.locator(f"text={txt}").first
                    if await btn.count() > 0 and await btn.first.is_visible():
                        cl_btn = btn
                        break
                
                if cl_btn:
                    async with page.expect_file_chooser(timeout=10000) as fc_info:
                        await cl_btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(cl_path)
                    print("   [Form] CL upload successful (button).")
                    await asyncio.sleep(2)

            # Continue again
            continue_names = [
                "Continue", "Next", "Weiter", "Continuer", "Suivant", 
                "Continuar", "Siguiente", "Avanti", "Prossimo",
                "Próximo", "Volgende", "Dalej"
            ]
            for name in continue_names:
                btn = page.get_by_role("button", name=name)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click(timeout=5000)
                    break
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"   [Warn] Cover Letter upload issue: {e}. Proceeding...")

    # --- Questions (Smart Batching) ---
    max_steps = 6
    cv_tex_path = cv_path.replace(".pdf", ".tex")
    
    for i in range(max_steps):
        print(f"   [Form] Step {i+1}...")
        try:
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
            
            # Check if we are on Review Page
            review_texts = ["Review your application", "Revoir votre candidature", "Bewerbung überprüfen", "Submit application"]
            is_review = False
            for txt in review_texts:
                if await page.get_by_text(txt, exact=False).count() > 0:
                    is_review = True
                    break
            
            if is_review:
                print("   [Form] Reached Review Page.")
                break
                
            # Smart Questions Batching
            await answer_questions(page, job_desc, cv_tex_path)
            
            # Press Continue
            continue_clicked = False
            for cont_name in ["Weiter", "Continue", "Continuer", "Next", "Suivant", "Avanti",
                             "Continuar", "Siguiente", "Próximo", "Volgende", "Dalej"]:
                try:
                    btn = page.get_by_role("button", name=cont_name)
                    if await btn.count() > 0:
                        await btn.first.click(timeout=5000)
                        continue_clicked = True
                        break
                except: pass
            
            if not continue_clicked:
                # Check for probable submit button
                potential_submit = page.locator("button[type='submit'], button:has-text('Submit'), button:has-text('Send application')")
                if await potential_submit.count() > 0:
                     print("   [Form] No more continue buttons, but found Submit. Proceeding to submit.")
                     break
                else:
                    print("   [Form] No continue button found. Stopping steps.")
                    break
                
        except Exception as step_err:
            print(f"   [Error] Step {i+1} Exception: {step_err}")
            break

    # --- Submit ---
    print("   [Form] Checking for Submit Button...")
    submit_btn = None
    submit_names = [
        "Submit application", "Send application", "Submit", "Send", "Apply now",
        "Bestätigen & bewerben", "Bewerbung absenden", "Absenden", "Bewerben",
        "Confirmer et postuler", "Postuler", "Envoyer", "Candidater",
        "Enviar solicitud", "Enviar", "Solicitar", "Invia"
    ]
    
    for name in submit_names:
        btn = page.get_by_role("button", name=name)
        if await btn.count() > 0:
            submit_btn = btn.first
            break
            
    if not submit_btn:
        btn = page.locator("button[type='submit']")
        if await btn.count() > 0 and await btn.first.is_visible():
            submit_btn = btn.first
        
    if submit_btn and await submit_btn.count() > 0:
        print(f"   [Form] Clicking Submit Button...")
        try:
            await submit_btn.click()
            await asyncio.sleep(5)
            return True
        except Exception as e:
            print(f"   [Error] Submit click failed: {e}")
            return False
    else:
        print("   [Error] Submit button not found.")
        return False
