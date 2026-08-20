import asyncio
import re
import json
import sys
import os
from pathlib import Path
from src.ai_client import ai_client

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config import settings

async def text_from_cv(cv_template=settings.CV_TEMPLATE_FULLTIME):
    """Reads the CV Latex file for context."""
    try:
        with open(cv_template, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

async def answer_questions(page, job_desc, cv_tex_path):
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
        info_path = settings.PERSONAL_INFO_FILE
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                personal_info = f.read().strip()
        else:
            personal_info = "Name: Fathi Belmkadem, Nationality: Tunisian, Location: Passau, Germany"
            
        prompt = settings.SMART_QUESTIONS_PROMPT.format(
            personal_info=personal_info,
            cv_content=cv_content[:2000],
            job_desc=job_desc[:2000],
            fields_json=json.dumps(fields, indent=2)
        )
        
        text = await ai_client.generate_content(prompt, json_mode=True)
        if not text:
            return
            
        actions = json.loads(text.strip())
        
        for action in actions:
            tid = action.get('target_id')
            act = action.get('action')
            val = action.get('value', '')
            
            if not tid or not act: continue
            
            loc = page.locator(f"id={tid}").first
            if await loc.count() == 0:
                loc = page.locator(f"[data-smart-id='{tid}']").first
                
            if await loc.count() > 0:
                try:
                    if act == 'fill':
                        await loc.fill(str(val))
                        print(f"   [SmartQuestions] Filled '{val[:30]}...'")
                    elif act == 'select':
                        try:
                            await loc.select_option(value=str(val), timeout=2000)
                            print(f"   [SmartQuestions] Selected '{val}' (by value)")
                        except:
                            try:
                                await loc.select_option(label=str(val), timeout=2000)
                                print(f"   [SmartQuestions] Selected '{val}' (by label)")
                            except:
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

async def get_ai_answer(context_text):
    """
    Asks Gemini for a short answer to a form question/input.
    """
    cv_text = await text_from_cv()
    personal_info = ""
    info_path = settings.PERSONAL_INFO_FILE
    if os.path.exists(info_path):
        with open(info_path, "r", encoding="utf-8") as f:
            personal_info = f.read().strip()
    
    prompt = settings.APPLY_PROMPT.format(
        profile_facts=personal_info,
        cv_text=cv_text[:4000],
        context_text=context_text
    )
    try:
        text = await ai_client.generate_content(prompt)
        if not text:
            return "Values alignment"
        return text.strip().replace('"', '').replace("'", "")
    except Exception as e:
        print(f"   [AI Debug] AI Error: {e}")
        return "Values alignment"

async def tailor_documents(job_desc, title, company, cv_template=settings.CV_TEMPLATE_FULLTIME):
    """
    Uses OpenRouter to tailor CV and Cover Letter.
    """
    print("   [AI] Tailoring documents using OpenRouter...")
    
    with open(cv_template, "r", encoding="utf-8") as f: cv_temp = f.read()
    with open(settings.CL_TEMPLATE, "r", encoding="utf-8") as f: cl_temp = f.read()
    with open(settings.PROMPT_FILE, "r", encoding="utf-8") as f: prompt_base = f.read()
    
    prompt = f"""
    {prompt_base}
    
    ===== JOB DESCRIPTION =====
    {job_desc[:3000]}
    
    ===== CV TEMPLATE =====
    {cv_temp[:4000]}
    
    ===== COVER LETTER TEMPLATE =====
    {cl_temp[:2000]}
    
    ===== CRITICAL: OUTPUT FORMAT (MANDATORY) =====
    ALL INPUT IS ABOVE. Generate the output NOW.
    
    You MUST output EXACTLY 2 code blocks:
    
    ```latex
    [Full tailored CV LaTeX code here]
    ```
    
    ```latex
    [Full tailored Cover Letter LaTeX code here]
    ```
    
    DO NOT ask questions. DO NOT explain. Just output the two LaTeX code blocks.
    """
    
    for attempt in range(2):
        try:
             text = await ai_client.generate_content(prompt)
             if not text: continue
             
             matches = re.findall(r"```(?:latex|tex)(.*?)```", text, re.DOTALL)
             
             cv_content, cl_content = None, None
             if len(matches) >= 2:
                 cv_content, cl_content = matches[0].strip(), matches[1].strip()
             elif len(matches) == 1:
                 content = matches[0].strip()
                 if "cv" in content.lower(): cv_content, cl_content = content, cl_temp
                 else: cv_content, cl_content = cv_temp, content
             else:
                 parts = text.split("\\documentclass") # Fixed backslash
                 if len(parts) >= 3:
                     cv_content, cl_content = "\\documentclass" + parts[1], "\\documentclass" + parts[2]
                 elif len(parts) == 2:
                      cv_content, cl_content = "\\documentclass" + parts[1], cl_temp
                 
             if cv_content and cl_content: 
                 print(f"   [AI] Generated CV ({len(cv_content)} chars) and CL ({len(cl_content)} chars).")
                 # Final Polish: Escape common problematic LaTeX chars that AI often forgets
                 def clean_tex(text):
                     # Replace raw underscores with escaped ones in text
                     # Avoid double escaping if AI already did it
                     text = text.replace(" _ ", " \\_ ")
                     # Only escape underscore if not already preceded by backslash
                     import re
                     text = re.sub(r'(?<!\\)_', r'\\_', text)
                     text = text.replace(" & ", " \\& ")
                     return text.strip()
                 
                 return clean_tex(cv_content), clean_tex(cl_content)
        except Exception as e:
             print(f"   [Error] Tailoring Attempt {attempt+1} Exception: {e}")
             await asyncio.sleep(2)
    
    print("   [Error] All tailoring attempts failed.")
    return None, None
