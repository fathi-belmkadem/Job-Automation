import os
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
# Settings is in project_root/config/settings.py
# So project_root is two levels up
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
DEBUG_DIR = os.path.join(PROJECT_ROOT, "debug")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")

# Load Environment Variables
ENV_PATH = os.path.join(CONFIG_DIR, ".env")
load_dotenv(ENV_PATH)
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    # Try looking in root just in case (though we moved it)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

# Data Files (Output/Input)
JOBS_DB_PATH = os.path.join(OUTPUT_DIR, "final_jobs_auto.xlsx")
HARVESTED_JOBS_PATH = os.path.join(OUTPUT_DIR, "harvested_jobs.json")
INTERMEDIATE_JOBS_PATH = os.path.join(OUTPUT_DIR, "intermediate_jobs.csv")
FILTERED_JOBS_PATH = os.path.join(OUTPUT_DIR, "filtered_jobs.xlsx")
MANUAL_JOBS_PATH = os.path.join(OUTPUT_DIR, "final_jobs_manual.xlsx")
JOBS_STUDENT_PATH = os.path.join(OUTPUT_DIR, "jobs_student.xlsx")
JOBS_FULLTIME_PATH = os.path.join(OUTPUT_DIR, "jobs_fulltime.xlsx")
KEYWORDS_PATH = os.path.join(CONFIG_DIR, "keywords.json")
URL_LIST_PATH = os.path.join(CONFIG_DIR, "url.txt")
SESSION_PREFIX = os.path.join(CONFIG_DIR, "session") # session.json

# Directories
APPLICATIONS_DIR = os.path.join(OUTPUT_DIR, "My_Applications")
OPTIONAL_FILES_DIR = os.path.join(PROJECT_ROOT, "Optional_files")

# Prompts & Templates
PROMPTS_DIR = os.path.join(CONFIG_DIR, "prompts")
CV_PROMPT_PATH = os.path.join(PROMPTS_DIR, "prompt.txt")
CV_TAILOR_STRUCTURE_PATH = os.path.join(PROMPTS_DIR, "cv_tailor_structure.txt")
COVER_LETTER_PROMPT_PATH = os.path.join(PROMPTS_DIR, "CoverLetter_Prompt.txt")
COVER_LETTER_STRUCTURE_PATH = os.path.join(PROMPTS_DIR, "cover_letter_structure.txt")

CV_TEMPLATE_STUDENT = os.path.join(TEMPLATES_DIR, "Workingstudent_intern_cv.tex")
CV_TEMPLATE_FULLTIME = os.path.join(TEMPLATES_DIR, "Fulltime_CV.tex")
COVER_LETTER_TEMPLATE = os.path.join(TEMPLATES_DIR, "Fathi-BELMKADEM-CoverLetter.tex")

# User Data
PHONE_NUMBER = "015511712618"
FINAL_PDF_NAME = "Fathi-BELMKADEM-CV.pdf"

# LaTeX Compiler Service (self-hosted, see latex-self-hosted/)
LATEX_COMPILER_URL = os.getenv("LATEX_COMPILER_URL", "http://localhost:5000")
