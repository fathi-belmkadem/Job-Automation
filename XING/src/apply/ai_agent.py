import asyncio
import os
import sys
import pandas as pd
import random
import re
import subprocess
import shutil
import requests
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

from .compiler import compile_cv

async def find_element_with_ai(page, description):
    """
    Fallback mechanism that uses Gemini to identify a selector if standard ones fail.
    Returns a locator if found.
    """
    print(f"   [AI-Selector] Attempting to find '{description}' via AI analysis of the DOM...")
    try:
        # Get simplified interactive elements
        elements = await page.evaluate("""() => {
            const results = [];
            const interactive = document.querySelectorAll('button, a, input, [role="button"]');
            interactive.forEach((el, i) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    results.push({
                        tag: el.tagName,
                        text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim(),
                        index: i
                    });
                }
            });
            return results;
        }""")
        
        # Filter elements with no text to save tokens
        elements = [e for e in elements if e['text']]
        
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Identify the index of the element that most likely represents the '{description}' button/link.
        Return ONLY the index as a number.
        
        Elements:
        {elements[:50]}
        """
        
        response = await generate_content_with_retry(model, prompt)
        match = re.search(r"\d+", response)
        if match:
            idx = int(match.group())
            # We use nth() on a generic locator to click the i-th interactive element
            # This is a bit risky but as a last resort fallback it's better than nothing.
            print(f"   [AI-Selector] AI suggested element index {idx}.")
            target = page.locator('button, a, input, [role="button"]').nth(idx)
            if await target.is_visible():
                return target
                
        return None
    except Exception as e:
        print(f"   [AI-Selector] Error: {e}")
        return None

async def answer_questions(page, job_data, cv_tex_path):
    """
    Detects custom questions (text, select, radio, checkbox) and uses AI to fill them in one pass.
    """
    print("   [SmartQuestions] Checking for custom questions...")
    try:
        # JS to extract all unanswered interactive form fields
        js_code = """
        () => {
            const fields = [];
            const elements = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="file"]), select, textarea');
            
            elements.forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                
                // Skip if already filled
                if ((el.type === 'text' || el.type === 'number' || el.type === 'date' || el.type === 'email' || el.tagName === 'TEXTAREA') && el.value) return;
                // For select, skip if not default
                if (el.tagName === 'SELECT' && el.selectedIndex > 0) return;
                // For checkbox/radio, skip if checked
                if ((el.type === 'checkbox' || el.type === 'radio') && el.checked) return;

                let label = '';
                if (el.id) {
                    const lbl = document.querySelector(`label[for="${el.id}"]`);
                    if (lbl) label = lbl.innerText.trim();
                }
                if (!label) label = el.placeholder || el.getAttribute('aria-label') || el.name || '';
                if (!label && el.parentElement) label = el.parentElement.innerText.split('\\n')[0].trim();

                let options = [];
                if (el.tagName === 'SELECT') {
                    options = Array.from(el.options).map(o => o.value + " (" + o.innerText.trim() + ")");
                } else if (el.type === 'radio') {
                    label = `Radio Option: ${label} (Group: ${el.name})`;
                } else if (el.type === 'checkbox') {
                    label = `Checkbox: ${label}`;
                }

                let targetId = el.id || el.getAttribute('data-smart-id');
                if (!targetId) {
                    targetId = 'smart-field-' + Math.random().toString(36).substr(2, 9);
                    el.setAttribute('data-smart-id', targetId);
                }

                fields.push({
                    target_id: targetId,
                    type: el.type || el.tagName.toLowerCase(),
                    label: label,
                    options: options
                });
            });
            return fields;
        }
        """
        
        import json
        fields = await page.evaluate(js_code)
        
        # Filter out phone numbers as they are handled separately
        fields = [f for f in fields if not any(k in f['label'].lower() for k in ["phone", "telefon", "mobile"])]
        
        if not fields:
            return
            
        print(f"   [SmartQuestions] Found {len(fields)} fields to analyze.")
            
        with open(cv_tex_path, "r", encoding="utf-8") as f:
            cv_content = f.read()
            
        # Read personal extra info
        personal_info = ""
        info_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "personal_info.txt")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                personal_info = f.read().strip()
            
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        ACT AS THE CANDIDATE. Based on my CV, Personal Info, and the Job Description, fill out these application form fields.
        
        PERSONAL INFO / CONTEXT:
        {personal_info}
        
        MY CV: 
        {cv_content[:2000]}... (truncated for context)
        
        JOB DESCRIPTION: 
        {job_data.get('Job Description', '')[:2000]}...
        
        FIELDS TO FILL:
        {json.dumps(fields, indent=2)}
        
        OUTPUT:
        You MUST return a valid JSON array of objects. Do NOT wrap in markdown ticks.
        Each object must have:
        - "target_id": string (exactly as provided in the FIELDS TO FILL)
        - "action": string ("fill", "select", or "check")
        - "value": string (the text to type, or the exact option value to select. Leave empty for "check")
        
        Rules:
        - Keep text answers very concise (1-2 sentences).
        - For numbers (salary), provide a reasonable integer (e.g., 60000).
        - For dates (availability), use YYYY-MM-DD.
        - ALWAYS consent to data privacy / terms (return action "check").
        - For radios (e.g. Yes/No), choose the correct one by returning "action": "check" for that specific target_id.
        - Only return actions for fields you are confident answering.
        """
        
        # Use structured outputs
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(response_mime_type="application/json")
        )
        
        actions = json.loads(response.text.strip())
        
        for action in actions:
            tid = action.get('target_id')
            act = action.get('action')
            val = action.get('value', '')
            
            if not tid or not act: continue
            
            # Locate by id or data-smart-id
            loc = page.locator(f"id={tid}").first
            if await loc.count() == 0:
                loc = page.locator(f"[data-smart-id='{tid}']").first
                
            if await loc.count() > 0:
                try:
                    if act == 'fill':
                        await loc.fill(str(val))
                        print(f"   [SmartQuestions] Filled '{val[:30]}...'")
                    elif act == 'select':
                        # Fast fail on exact matches
                        try:
                            await loc.select_option(value=str(val), timeout=2000)
                            print(f"   [SmartQuestions] Selected '{val}' (by value)")
                        except:
                            try:
                                await loc.select_option(label=str(val), timeout=2000)
                                print(f"   [SmartQuestions] Selected '{val}' (by label)")
                            except:
                                # Fallback: Partial match using JS
                                js_fallback = """
                                (select, searchStr) => {
                                    if (!select.options) return false;
                                    searchStr = String(searchStr).toLowerCase().trim();
                                    for (let opt of select.options) {
                                        let v = opt.value.toLowerCase();
                                        let t = opt.text.toLowerCase();
                                        if (v.includes(searchStr) || t.includes(searchStr) || searchStr.includes(v) || searchStr.includes(t)) {
                                            opt.selected = true;
                                            select.dispatchEvent(new Event('change', { bubbles: true }));
                                            return true;
                                        }
                                    }
                                    // If no text match, try to just select the second option as a blind fallback (index 1) to unblock the form
                                    if (select.options.length > 1) {
                                        select.selectedIndex = 1;
                                        select.dispatchEvent(new Event('change', { bubbles: true }));
                                        return true;
                                    }
                                    return false;
                                }
                                """
                                success = await loc.evaluate(js_fallback, str(val))
                                if success:
                                    print(f"   [SmartQuestions] Selected '{val}' (JS Fallback Match)")
                                else:
                                    print(f"   [SmartQuestions] WARNING: Failed to select any option for '{val}'")
                    elif act == 'check':
                        await loc.check(force=True)
                        print(f"   [SmartQuestions] Checked checkbox/radio")
                    await asyncio.sleep(0.5)
                except Exception as ex:
                    print(f"   [SmartQuestions] Failed action '{act}' on '{tid}': {ex}")
                    
    except Exception as e:
        print(f"   [SmartQuestions] Error processing form: {e}")

async def generate_content_with_retry(model, prompt, retries=5):
    base_delay = 10
    for attempt in range(retries):
        try:
            response = await model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                delay = base_delay * (2 ** attempt) + random.uniform(1, 5)
                print(f"   [Rate Limit] 429/Quota exceeded (Attempt {attempt+1}/{retries}). Sleeping {delay:.1f}s...")
                await asyncio.sleep(delay)
            else:
                print(f"   [Gemini Error] {e}")
                # For non-429 errors, we might retry once or just fail? 
                # Let's retry on any 5xx too? But usually only 429 or 503 is transient.
                if "500" in str(e) or "503" in str(e):
                     delay = 5
                     print(f"   [Server Error] Sleeping {delay}s...")
                     await asyncio.sleep(delay)
                     continue
                raise e
    raise Exception("Max retries exceeded for Gemini API.")

async def tailor_cv(job_index, company, title, location, description, template_path):
    print(f"\n[TAILORING] {title} @ {company} ({location})")
    
    # Safe Folder Name - STRICT ASCII to avoid Docker issues
    # Format: {Index}_{Title}_{Company}_{Location}
    # The Index guarantees uniqueness even if Title/Company/Location are identical.
    
    clean_title = re.sub(r'[^a-zA-Z0-9_\-]', '', title.replace(' ', '_'))
    clean_company = re.sub(r'[^a-zA-Z0-9_\-]', '', company.replace(' ', '_'))
    clean_location = re.sub(r'[^a-zA-Z0-9_\-]', '', location.replace(' ', '_'))
    
    folder_name = f"{job_index}_{clean_title}_{clean_company}_{clean_location}"[:100] # Increased limit slightly
    
    job_dir = os.path.join(settings.APPLICATIONS_DIR, folder_name)
    os.makedirs(job_dir, exist_ok=True)
    
    tex_out = os.path.join(job_dir, settings.FINAL_PDF_NAME.replace(".pdf", ".tex"))
    
    # 2.1 Check if already tailored
    if os.path.exists(tex_out):
        print("   Skipping generation (Tex file exists)")
        return job_dir, True

    # 2.2 Generate Content
    try:
        with open(settings.CV_PROMPT_PATH, "r", encoding="utf-8") as f:
            base_prompt = f.read()
            
        with open(template_path, "r", encoding="utf-8") as f:
            cv_template_content = f.read()
            
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Read Structure
        with open(settings.CV_TAILOR_STRUCTURE_PATH, "r", encoding="utf-8") as f:
            prompt_structure = f.read()
            
        # Fill Structure (Manual replace to avoid brace issues)
        prompt = prompt_structure.replace("{{base_prompt}}", base_prompt)
        prompt = prompt.replace("{{cv_template_content}}", cv_template_content)
        prompt = prompt.replace("{{description}}", description)
        
        print("   Sending to Gemini...")
        content = await generate_content_with_retry(model, prompt)
        
        # Clean Output
        cv_match = re.search(r"```(?:latex|tex)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if cv_match:
            content = cv_match.group(1).strip()
        elif "\\documentclass" in content:
            # Fallback if no ticks but contains latex start
            content = content[content.find("\\documentclass"):]
            
        with open(tex_out, "w", encoding="utf-8") as f:
            f.write(content.strip())
            
        print("   Tailoring Success.")
        return job_dir, True
        
    except Exception as e:
        print(f"   Tailoring Failed: {e}")
        return job_dir, False

async def tailor_cover_letter(job_dir, company, title, description, cv_tex_path):
    print(f"   [COVER LETTER] Generating for {title} @ {company}...")
    
    cl_tex_out = os.path.join(job_dir, "Fathi-BELMKADEM-CoverLetter.tex")
    cl_pdf_out = os.path.join(job_dir, "Fathi-BELMKADEM-CoverLetter.pdf")
    
    # Check if already exists
    if os.path.exists(cl_pdf_out) and os.path.getsize(cl_pdf_out) > 1000:
        print("   Cover Letter PDF exists.")
        return cl_pdf_out

    try:
        # Read Resources
        with open(settings.COVER_LETTER_PROMPT_PATH, "r", encoding="utf-8") as f:
            prompt_text = f.read()
        
        with open(settings.COVER_LETTER_TEMPLATE, "r", encoding="utf-8") as f:
            template_text = f.read()
            
        with open(cv_tex_path, "r", encoding="utf-8") as f:
            cv_content = f.read()
            
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Read Structure
        with open(settings.COVER_LETTER_STRUCTURE_PATH, "r", encoding="utf-8") as f:
            cl_structure = f.read()

        prompt = cl_structure.replace("{{base_prompt}}", prompt_text)
        prompt = prompt.replace("{{cv_content}}", cv_content)
        prompt = prompt.replace("{{description}}", description)
        prompt = prompt.replace("{{template_text}}", template_text)
        
        content = await generate_content_with_retry(model, prompt)
        
        # Clean Output
        cl_match = re.search(r"```(?:latex|tex)?\s*(.*?)\s*```", content, re.DOTALL | re.IGNORECASE)
        if cl_match:
            content = cl_match.group(1).strip()
        elif "\\documentclass" in content:
            content = content[content.find("\\documentclass"):]
            
        with open(cl_tex_out, "w", encoding="utf-8") as f:
            f.write(content.strip())
            
        # Compile via the self-hosted LaTeX compiler service
        print("   Compiling Cover Letter...")

        response = await asyncio.to_thread(
            requests.post,
            f"{settings.LATEX_COMPILER_URL}/compile",
            json={"latex_code": content.strip()},
            timeout=120,
        )

        if response.status_code == 200:
            with open(cl_pdf_out, "wb") as f:
                f.write(response.content)
            print(f"   Cover Letter Compiled Successfully ({os.path.getsize(cl_pdf_out)} bytes).")
            return cl_pdf_out
        else:
            print(f"   Cover Letter Compilation Failed (HTTP {response.status_code}): {response.text[:300]}")
            return None

    except Exception as e:
        print(f"   Cover Letter Generation Failed: {e}")
        return None

