"""
Centralized settings for the Join.com job application automation pipeline.
All paths and constants are defined here for easy management.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# --- DIRECTORY STRUCTURE ---
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_DIR = PROJECT_ROOT / "config"
SRC_DIR = PROJECT_ROOT / "src"
OUTPUT_DIR = PROJECT_ROOT / "output"
DEBUG_DIR = PROJECT_ROOT / "debug"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
PROMPTS_DIR = CONFIG_DIR / "prompts"

# --- ENVIRONMENT VARIABLES ---
load_dotenv(CONFIG_DIR / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "deepseek/deepseek-v4-flash:free"
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY")

# --- FILE PATHS ---
# Session & Configuration
SESSION_FILE = CONFIG_DIR / "session.json"
PERSONAL_INFO_FILE = CONFIG_DIR / "personal_info.txt"

# Templates
CV_TEMPLATE_FULLTIME = TEMPLATES_DIR / "Fulltime_CV.tex"
CV_TEMPLATE_STUDENT = TEMPLATES_DIR / "Workingstudent_intern_cv.tex"
CL_TEMPLATE = TEMPLATES_DIR / "Fathi_BELMKADEM_CoverLetter.tex"

# Prompts
PROMPT_FILE = PROMPTS_DIR / "prompt.txt"
COVER_LETTER_PROMPT = PROMPTS_DIR / "CoverLetter_Prompt.txt"
SMART_QUESTIONS_PROMPT_FILE = PROMPTS_DIR / "smart_questions_prompt.txt"
DEEP_FILTER_PROMPT_FILE = PROMPTS_DIR / "deep_filter_prompt.txt"

# Output
FILTERED_JOBS_FILE = OUTPUT_DIR / "filtered_jobs.xlsx"
APPLICATIONS_DIR = OUTPUT_DIR / "My_Applications"
URLS_FILE = OUTPUT_DIR / "urls.txt"
URLS_VALIDATED_FILE = OUTPUT_DIR / "urls_validated.txt"
REJECTED_URLS_FILE = OUTPUT_DIR / "rejected_urls.txt"
RECENT_URLS_FILE = OUTPUT_DIR / "recent_urls.txt"

# --- LATEX COMPILER SERVICE (self-hosted, see latex-self-hosted/) ---
LATEX_COMPILER_URL = os.getenv("LATEX_COMPILER_URL", "http://localhost:5000")

# --- MODEL SETTINGS ---
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")  # Options: "gemini", "openrouter"
GEMINI_MODEL = "gemini-3-flash-preview"
GEMINI_MODEL_FILTER = "gemini-2.5-flash"

# --- APPLICATION SETTINGS ---
TEST_MODE = False  # Run on ALL jobs when False
USE_PERPLEXITY = True  # Toggle to use Perplexity for CV/CL tailoring
BATCH_SIZE = 50  # For URL filtering
SEARCH_TIME_LIMIT = "past_month"  # Options: "past_week", "past_month", "past_24h", "any_time"
DEFAULT_SEARCH_ENGINE = "serpapi"  # Options: "google", "perplexity", "serpapi"

# --- USER PROFILE CONSTANTS ---
# These are used for auto-filling application forms
USER_PHONE = "+4915511712618"
PDF_NAME_PREFIX = "Fathi_BELMKADEM"

# Working student / intern detection keywords
import json

# ... (Previous imports)

# --- LOAD EXTERNAL CONFIGURATIONS ---

# 1. Search Keywords
SEARCH_KEYWORDS_FILE = CONFIG_DIR / "search_keywords.json"
REGION_CONFIG = {}
if SEARCH_KEYWORDS_FILE.exists():
    with open(SEARCH_KEYWORDS_FILE, "r", encoding="utf-8") as f:
        REGION_CONFIG = json.load(f)

# 2. Prompts
FILTER_PROMPT_FILE = PROMPTS_DIR / "filter_prompt.txt"
FILTER_PROMPT = ""
if FILTER_PROMPT_FILE.exists():
    with open(FILTER_PROMPT_FILE, "r", encoding="utf-8") as f:
        FILTER_PROMPT = f.read()

APPLY_PROMPT_FILE = PROMPTS_DIR / "apply_prompt.txt"
APPLY_PROMPT = ""
if APPLY_PROMPT_FILE.exists():
    with open(APPLY_PROMPT_FILE, "r", encoding="utf-8") as f:
        APPLY_PROMPT = f.read()

SMART_QUESTIONS_PROMPT = ""
if SMART_QUESTIONS_PROMPT_FILE.exists():
    with open(SMART_QUESTIONS_PROMPT_FILE, "r", encoding="utf-8") as f:
        SMART_QUESTIONS_PROMPT = f.read()

DEEP_FILTER_PROMPT = ""
if DEEP_FILTER_PROMPT_FILE.exists():
    with open(DEEP_FILTER_PROMPT_FILE, "r", encoding="utf-8") as f:
        DEEP_FILTER_PROMPT = f.read()

# Working student / intern detection keywords
STUDENT_KEYWORDS = [
    "werkstudent", "working student", "student", "intern", "internship",
    "praktikum", "praktikant", "stagiaire", "stage", "trainee",
    "thesis", "abschlussarbeit", "masterarbeit", "bachelorarbeit",
    "junior developer", "junior engineer", "entry level",
    "junior data", "junior security", "junior cyber", "junior ai", 
    "junior machine learning", "pfe", "pflichtpraktikum", "voluntary internship",
    "summer intern", "werkstudierenden", "end of studies"
]

# --- HELPER FUNCTIONS ---
def ensure_directories():
    """Create all required directories if they don't exist."""
    for directory in [OUTPUT_DIR, DEBUG_DIR, APPLICATIONS_DIR, PROMPTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# Ensure output directories exist on import
ensure_directories()
