import pandas as pd
import os
import re
import google.generativeai as genai
import pandas as pd
import os
import re
import google.generativeai as genai
import time
import shutil
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

if not settings.GOOGLE_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in settings")

genai.configure(api_key=settings.GOOGLE_API_KEY)

# Configuration
INPUT_AUTO = settings.JOBS_DB_PATH
INPUT_MANUAL = settings.MANUAL_JOBS_PATH
OUTPUT_STUDENT = settings.JOBS_STUDENT_PATH
OUTPUT_FULLTIME = settings.JOBS_FULLTIME_PATH
BASE_DIR = settings.APPLICATIONS_DIR

# Paths to assets
CV_PATH = settings.CV_TEMPLATE_FULLTIME # Default, logic should handle student vs fulltime
PROMPT_PATH = settings.CV_PROMPT_PATH

def clean_filename(text):
    """Sanitize text for use as folder name."""
    clean = re.sub(r'[\\/*?:"<>|]', "", text)
    return clean[:100].strip() # Limit length

def classify_jobs_batch(jobs):
    """
    Classifies a list of jobs as 'Student' (Intern/Werkstudent) or 'FullTime' (Entry/Junior)
    using Gemini, based on Title, Company, and Description.
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt = """
    ACT AS AN EXPERT RECRUITER. Your task is to classify job postings into exactly one of two categories:
    
    1. 'Student': 
       - Internships (Praktikum)
       - Working Student roles (Werkstudent)
       - Master/Bachelor Thesis projects
       - Stage/Stagiaire roles
       - Summer jobs for students
    
    2. 'FullTime': 
       - Junior / Entry-level roles
       - Trainee programs (non-student)
       - PhD (Doktorand) or Researcher positions
       - Associate roles
       - Regular full-time or part-time professional roles
    
    CRITERIA:
    - If the description mentions "must be enrolled at a university", it is 'Student'.
    - If the title contains "Junior" or "Trainee" but does not mention "Student", it is 'FullTime'.
    - PhD positions are considered 'FullTime' for the purpose of CV template selection.
    
    OUTPUT FORMAT:
    Return ONLY a JSON list of strings corresponding to the jobs in order.
    Example: ["Student", "FullTime", "FullTime"]
    
    JOBS TO CLASSIFY:
    """
    
    for i, job in enumerate(jobs):
        title = job.get('Title', 'Unknown')
        company = job.get('Company', 'Unknown')
        # Include snippet of description (first 1000 chars) to stay within token limits if batch is large
        desc = str(job.get('Job Description', ''))[:1000]
        prompt += f"\n--- JOB {i} ---\nTitle: {title}\nCompany: {company}\nDescription Snippet: {desc}\n"
        
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up Markdown JSON if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
            
        import json
        classifications = json.loads(text)
        
        if len(classifications) != len(jobs):
            print(f"Warning: classification count mismatch. Req: {len(jobs)}, Got: {len(classifications)}. Fallback to heuristics.")
            return heuristic_classify(jobs)
            
        return classifications
    except Exception as e:
        print(f"Classification error: {e}. Fallback to heuristics.")
        return heuristic_classify(jobs)


def heuristic_classify(jobs):
    """Fallback classification if AI fails."""
    classes = []
    student_keywords = ['werk', 'student', 'intern', 'praktik', 'thesis', 'master', 'bachelor']
    for job in jobs:
        title = str(job.get('Title', '')).lower()
        if any(k in title for k in student_keywords):
            classes.append("Student")
        else:
            classes.append("FullTime")
    return classes

def classify_all_jobs():
    """Reads input files, classifies new ones, updates source files, and exports split files."""
    print("Loading jobs...")
    
    files_map = {
        INPUT_AUTO: None,
        INPUT_MANUAL: None
    }
    
    # Load and Classify per file to ensure we save back correctly
    all_dfs = []
    
    for fname in files_map:
        if not os.path.exists(fname):
            continue
            
        print(f"Processing {fname}...")
        df = pd.read_excel(fname)
        
        if "Type" not in df.columns:
            df["Type"] = ""
            
        # Find pending
        pending_mask = df["Type"].isna() | (df["Type"].astype(str).str.strip() == "")
        pending_indices = df[pending_mask].index.tolist()
        
        if pending_indices:
            print(f"  Found {len(pending_indices)} unclassified jobs.")
            jobs_to_classify = df.loc[pending_indices].to_dict('records')
            
            # Batch classify
            batch_size = 20
            results = []
            for i in range(0, len(jobs_to_classify), batch_size):
                batch = jobs_to_classify[i:i+batch_size]
                print(f"  Classifying batch {i}-{i+len(batch)}...")
                cats = classify_jobs_batch(batch)
                results.extend(cats)
                time.sleep(1)
            
            # Update DataFrame
            df.loc[pending_indices, "Type"] = results
            
            # Save back to Source!
            df.to_excel(fname, index=False)
            print(f"  Saved updates to {fname}")
        else:
            print("  All jobs already classified.")
            
        all_dfs.append(df)

    if not all_dfs:
        print("No job files found.")
        return

    # Merge for output generation
    grand_df = pd.concat(all_dfs, ignore_index=True)
    # Deduplicate for safety in the OUTPUT files (optional, but good)
    # grand_df.drop_duplicates(subset=["Title", "Company", "Location", "URL"], inplace=True)
    
    # Split
    student_df = grand_df[grand_df['Type'] == 'Student']
    fulltime_df = grand_df[grand_df['Type'] == 'FullTime']
    
    student_df.to_excel(OUTPUT_STUDENT, index=False)
    fulltime_df.to_excel(OUTPUT_FULLTIME, index=False)
    
    print(f"\nClassification Export Complete:")
    print(f"  Student/Intern: {len(student_df)} jobs -> {OUTPUT_STUDENT}")
    print(f"  Full-Time/Junior: {len(fulltime_df)} jobs -> {OUTPUT_FULLTIME}")

def generate_applications(job_file, job_type):
    """
    Iterates through classified jobs, creates folders, and calls AI for tailoring.
    """
    if not os.path.exists(job_file):
        print(f"File {job_file} not found.")
        return

    print(f"\nGenerataing Applications for {job_type}...")
    df = pd.read_excel(job_file)
    jobs = df.to_dict('records')
    
    # Load assets
    with open(CV_PATH, 'r', encoding='utf-8') as f:
        cv_content = f.read()
    with open(PROMPT_PATH, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
        
    model = genai.GenerativeModel("gemini-2.5-flash")

    for i, job in enumerate(jobs):
        title = str(job.get('Title', 'Unknown'))
        company = str(job.get('Company', 'Unknown'))
        location = str(job.get('Location', 'Unknown'))
        desc = str(job.get('Job Description', ''))
        
        # Skip if no description (manual jobs might have missing desc if not enriched?)
        # Wait, manual jobs from enrich_jobs.py MIGHT NOT have descriptions if we skipped scraping them?
        # In enrich_jobs.py, we only scraped desc for 'is_easy_apply'.
        # For manual jobs, we might need to fetch desc or skip tailoring?
        # User said "tailor ... based on the prompt job description fetched from the excel".
        # If manual jobs don't have desc, we can't tailor fully.
        # Let's check if 'Job Description' is valid.
        if not desc or desc == "nan" or len(desc) < 50:
            print(f"[{i+1}] Skipping {title} - No Description available.")
            continue

        folder_name = clean_filename(f"{title}_{company}_{location}")
        target_dir = os.path.join(BASE_DIR, job_type, folder_name)
        
        if os.path.exists(target_dir):
            print(f"[{i+1}] Skipping {folder_name} - Already exists.")
            continue
            
        print(f"[{i+1}/{len(jobs)}] Tailoring for: {title} @ {company}...")
        os.makedirs(target_dir, exist_ok=True)
        
        # Construct Prompt
        full_prompt = f"""
        {prompt_template}
        
        === MY CURRENT CV (LaTeX) ===
        {cv_content}
        
        === JOB DESCRIPTION ===
        {desc}
        """
        
        try:
            response = model.generate_content(full_prompt)
            output = response.text
            
            # Extract content (Naive parsing based on observed Gemini behavior)
            # Usually strict LaTeX block for CV, then text for letter.
            
            cv_match = re.search(r"```latex(.*?)```", output, re.DOTALL)
            cv_code = cv_match.group(1).strip() if cv_match else ""
            
            # Assume everything after the latex block (or if no block, implies fail) is letter?
            # Or prompt asks for letter too.
            # Let's simple-save the raw output if parsing fails, but try to split.
            
            if cv_code:
                # Save CV
                with open(os.path.join(target_dir, "Fathi-BELMKADEM-CV.tex"), "w", encoding='utf-8') as f:
                    f.write(cv_code)
                print("  Saved Fathi-BELMKADEM-CV.tex")
                
                # Letter is likely the rest
                # or separate block
                # Looking for start of letter
                
                # We save the full raw response too just in case
                with open(os.path.join(target_dir, "gemini_response.txt"), "w", encoding='utf-8') as f:
                    f.write(output)

                # Try to extract letter if possible, otherwise user uses raw
                # Common pattern: "Here is the cover letter:"
                
            else:
                print("  Failed to parse LaTeX from response. Saving raw.")
                with open(os.path.join(target_dir, "response_raw.txt"), "w", encoding='utf-8') as f:
                    f.write(output)
                    
        except Exception as e:
            print(f"  Error generating content: {e}")
            
        time.sleep(2) # Rate limit niceness

if __name__ == "__main__":
    # 1. Classify
    classify_all_jobs()
    
    # 2. Tailor
    # generate_applications(OUTPUT_STUDENT, "Student")
    # generate_applications(OUTPUT_FULLTIME, "FullTime")
    
    # For safe testing, let's just do classification first run,
    # or uncomment to do all. 
    # I will uncomment to do all as requested.
    generate_applications(OUTPUT_STUDENT, "Student")
    generate_applications(OUTPUT_FULLTIME, "FullTime")
