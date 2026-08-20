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

async def compile_cv(job_dir):
    print(f"   [COMPILING] in {job_dir}")
    tex_file = settings.FINAL_PDF_NAME.replace(".pdf", ".tex")
    pdf_file = settings.FINAL_PDF_NAME
    
    tex_path = os.path.join(job_dir, tex_file)
    pdf_path = os.path.join(job_dir, pdf_file)
    
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1024:
        print("   PDF exists, skipping compile.")
        return True
        
    if not os.path.exists(tex_path):
        return False

    with open(tex_path, "r", encoding="utf-8") as f:
        tex_content = f.read()

    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{settings.LATEX_COMPILER_URL}/compile",
            json={"latex_code": tex_content},
            timeout=120,
        )

        if response.status_code == 200:
            with open(pdf_path, "wb") as f:
                f.write(response.content)
            print(f"   Compilation Success (PDF written, {os.path.getsize(pdf_path)} bytes).")
            return True
        else:
            print(f"   Compilation Failed (HTTP {response.status_code}): {response.text[:300]}")
            # Auto-Heal: Delete bad Tex file so we retry generation next time
            try:
                os.remove(tex_path)
                print("   Deleted bad .tex file to force regeneration.")
            except: pass
            return False
    except Exception as e:
        print(f"   LaTeX Compiler Error: {e}")
        return False
