import re
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config import settings

def detect_cv_template(url, title=""):
    """Detect whether to use Fulltime or Working Student CV template based on job URL/title."""
    text_to_check = (url + " " + title).lower()
    
    for keyword in settings.STUDENT_KEYWORDS:
        if keyword in text_to_check:
            print(f"   [CV] Detected student/intern position (keyword: '{keyword}') -> Using Working Student CV")
            return settings.CV_TEMPLATE_STUDENT
    
    print("   [CV] Full-time position detected -> Using Fulltime CV")
    return settings.CV_TEMPLATE_FULLTIME

def clean_filename(text):
    return re.sub(r'[^a-zA-Z0-9_\-]', '', text.replace(' ', '_'))[:50]
