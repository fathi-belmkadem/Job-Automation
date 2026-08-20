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

def get_cv_template(title, company, job_type=None):
    """
    Decides which CV template to use based on job type or title.
    """
    # 1. Use Explicit Classification if available
    if job_type:
        jt = str(job_type).lower()
        if "student" in jt:
             print(f"   [Classify] Type '{job_type}' -> Student Template")
             return settings.CV_TEMPLATE_STUDENT
        if "fulltime" in jt:
             print(f"   [Classify] Type '{job_type}' -> Full Time Template")
             return settings.CV_TEMPLATE_FULLTIME
             
    # 2. Fallback Heuristic
    t = title.lower()
    student_keywords = ['werk', 'student', 'intern', 'praktik', 'thesis', 'master', 'bachelor', 'stage', 'stagiaire']
    
    if any(k in t for k in student_keywords):
        print(f"   [Classify] '{title}' (Heuristic) -> Student/Intern")
        return settings.CV_TEMPLATE_STUDENT
    
    # Default to Full Time
    print(f"   [Classify] '{title}' (Heuristic) -> Full Time")
    return settings.CV_TEMPLATE_FULLTIME

async def handle_cookies(page):
    """
    Dismisses common cookie banners (Usercentrics, etc.) if present.
    """
    try:
        # Usercentrics common button texts
        accept_texts = [
            "Accept all", 
            "Alles akzeptieren", 
            "Alle akzeptieren", 
            "Tout accepter",
            "Accept",
            "Akzeptieren"
        ]
        
        # We look for a button inside the usercentrics container
        # Usercentrics usually uses a shadow DOM, Playwright locators handle this.
        for text in accept_texts:
            btn = page.locator("button").filter(has_text=re.compile(f"^{text}$", re.IGNORECASE)).first
            if await btn.count() > 0 and await btn.is_visible():
                print(f"   [Cookies] Dismissing banner with button: '{text}'")
                await btn.click()
                try:
                    # Wait for the overlay to disappear
                    overlay = page.locator("#usercentrics-cmp-ui").first
                    if await overlay.count() > 0:
                        await overlay.wait_for(state="hidden", timeout=5000)
                except:
                    pass
                await asyncio.sleep(1)
                return True
        
        # Fallback: check for the specific usercentrics button via data-testid or aria-label if known
        # But text search is usually robust across languages if we have enough variations.
        
        # Check for another common cookie banner pattern if Usercentrics isn't found
        overlay = page.locator("#usercentrics-cmp-ui, .cmp-container, #onetrust-banner-sdk").first
        if await overlay.count() > 0:
             # Try to find ANY button inside that looks like "Accept"
             accept_btn = overlay.locator("button").filter(has_text=re.compile("Accept|Akzeptieren|Zustimmen|Agree", re.IGNORECASE)).first
             if await accept_btn.count() > 0:
                 print("   [Cookies] Dismissing banner via container search...")
                 await accept_btn.click()
                 try:
                     # Wait for it to disappear
                     await overlay.wait_for(state="hidden", timeout=5000)
                 except:
                     pass
                 await asyncio.sleep(1)
                 return True

    except Exception as e:
        print(f"   [Cookies] Error handling cookies: {e}")
    
    return False
