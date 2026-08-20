import pandas as pd
import google.generativeai as genai
import os
import json
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

if not settings.GOOGLE_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in settings")

genai.configure(api_key=settings.GOOGLE_API_KEY)

INPUT_FILE = settings.INTERMEDIATE_JOBS_PATH
OUTPUT_FILE = settings.FILTERED_JOBS_PATH

class JobFilter:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def filter_batch(self, jobs_batch: list[dict]) -> list[bool]:
        """
        Returns a list of booleans corresponding to the batch, True if relevant.
        """
        # Prepare text representation for AI
        job_lines = []
        for i, job in enumerate(jobs_batch):
            # Include location in prompt for better context (e.g. if Title is vague)
            loc = job.get('Location', 'Unknown')
            job_lines.append(f"{i}. Title: {job['Title']}, Company: {job['Company']}, Location: {loc}")
        
        # Pre-filter blacklist
        # We handle this by modifying the prompt? No, better to force the result to False in the loop later?
        # Actually easier to just continue or handle it after getting AI results? 
        # Safest: Use a blacklist mask and force those indices to False after AI returns (or before to save tokens, but that complicates the batching logic).
        # Let's force it after receiving results OR just rely on the AI prompt instructions if we trust it?
        # User said "fake company", better to HARD CODE it.
        # Let's add it to the prompt as a specific rule first, AND force-reject in code.

        
        jobs_text = "\n".join(job_lines)
        
        prompt = f"""
        ACT AS A STRICT TECHNICAL RECRUITER matching candidates to a specific profile (Cybersecurity Engineer + AI/ML Practitioner + Full Stack/Cloud Developer).
        
        YOUR GOAL: Filter this list of jobs to find ONLY relevant roles for a candidate with this hybrid skillset:
        - **Domains**: 
            - Cybersecurity (SIEM/SOAR/Wazuh, K8s Security, WAF, Penetration Testing, Malware Analysis, Network Security, Zero Trust).
            - AI/ML (RAG, LLMs, Deep Learning, Reinforcement Learning, Computer Vision).
            - Full Stack/Cloud (Python, Next.js, React Native, Node.js, FastAPI, Docker, Kubernetes, GCP, Supabase).
        - **Seniority**: Intern (Praktikant), Working Student (Werkstudent), Junior, Entry Level, Trainee.

        YOUR RULES (HARD REJECT - DO NOT KEEP):
        1.  **NO Non-Technical**: "Sales", "Recruiting", "HR", "Account Manager", "Marketing", "Customer Support" (unless L2/L3 Tech Support) -> REJECT.
        2.  **NO Senior/Leadership**: "Senior", "Lead", "Principal", "Head of", "Manager" (unless "Junior Manager" or "Trainee Manager"), "Director" -> REJECT.
        3.  **NO Pure Design**: "UI/UX Designer", "Graphic Designer", "Art Director" -> REJECT (Keep "Frontend/Full Stack Developer").
        4.  **NO Unrelated Engineering**: "Mechanical Engineer", "Civil Engineer", "Electrical Engineer" (Hardware focus), "SAP Consultant" (Functional) -> REJECT.
        
        **CRITICAL MATCHING INSTRUCTION (Allowed Topics)**:
        - **KEEP** "Cybersecurity", "Security Engineer", "Pentester", "SOC Analyst", or "Network Security" roles.
        - **KEEP** "DevOps", "Cloud Engineer", or "Site Reliability Engineer" roles if they involve Kubernetes, Docker, or Security (DevSecOps).
        - **KEEP** "AI Engineer", "Data Scientist", or "Machine Learning" roles.
        - **KEEP** "Frontend", "Backend", or "Full Stack" roles if they use Python, React, Next.js, Node.js, or React Native.
        - **KEEP** General "IT", "Infrastructure", "Systems Administration", or "IT Automation" roles.
        
        INPUT LIST (Index. Title, Company, Location):
        {jobs_text}
        
        OUTPUT:
        You MUST return a valid JSON array of objects. Do NOT wrap it in markdown ticks.
        Each object MUST have the following keys:
        - "index": integer (the index from the input list)
        - "decision": string (either "keep" or "reject")
        - "score": integer (0 to 100 representing how well it matches)
        - "reason": string (1-2 sentences explaining why it was kept or rejected based on the rules)
        
        Example:
        [
            {{"index": 0, "decision": "reject", "score": 10, "reason": "Role is purely functional SAP consulting, not aligned with DevOps."}},
            {{"index": 1, "decision": "keep", "score": 85, "reason": "Strong match: Title mentions Infrastructure and Automation."}}
        ]
        """
        
        # Retry logic for Rate Limits
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json"
                    )
                )
                text = response.text.strip()
                # Clean up markdown code blocks if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1]
                    if text.endswith("```"):
                        text = text.rsplit("\n", 1)[0]
                
                decisions = json.loads(text)
                
                # Convert list of indices to detailed results
                results = [{"keep": False, "score": "", "reason": ""} for _ in range(len(jobs_batch))]
                for item in decisions:
                    idx = item.get("index")
                    decision = item.get("decision", "").lower()
                    if idx is not None and 0 <= idx < len(jobs_batch):
                        results[idx]["score"] = item.get("score", "")
                        results[idx]["reason"] = item.get("reason", "")
                        if decision == "keep":
                            results[idx]["keep"] = True
                            print(f"  [KEEP] {jobs_batch[idx].get('Company')} - {jobs_batch[idx].get('Title')} (Score: {item.get('score')}): {item.get('reason')}")
                
                # HARD BLACKLIST OVERRIDE
                for idx, job in enumerate(jobs_batch):
                    if "tech staff solutions heidelberg gmbh" in str(job.get("Company", "")).lower():
                        results[idx]["keep"] = False
                        print(f"  [Filtered] Hard-blocked company: {job.get('Company')}")
                        
                return results
            except Exception as e:
                if "429" in str(e):
                    print(f"  Rate Limit Hit (429). Sleeping 60s... (Attempt {attempt+1}/{max_retries})")
                    import time
                    time.sleep(60)
                else:
                    print(f"  Error filtering batch: {e}")
                    # If it's a non-rate-limit error (e.g. safety), we might just fail this batch safely
                    return [{"keep": False, "score": "", "reason": "Error"} for _ in range(len(jobs_batch))]
        
        print("  Max retries exceeded. Skipping batch (Rejecting).")
        return [{"keep": False, "score": "", "reason": "Max Retries"} for _ in range(len(jobs_batch))]

    def run(self):
        if not os.path.exists(INPUT_FILE):
            print(f"Input file {INPUT_FILE} not found.")
            return

        print(f"Loading {INPUT_FILE}...")
        try:
            df = pd.read_csv(INPUT_FILE)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return
        
        if df.empty:
            print("No jobs to filter.")
            return

        # Add Filter Status column if missing
        if "Filter Status" not in df.columns:
            df["Filter Status"] = ""
            
        # Cast to object to prevent TypeError when assigning strings to an inferred float64 column
        df["Filter Status"] = df["Filter Status"].astype('object')

        # Pre-filter using Regex to save API calls
        import re
        bad_words_pattern = re.compile(r'\b(sales|recruiting|hr|account manager|marketing|senior|lead|principal|head of|director|manager)\b', re.IGNORECASE)
        
        pre_filter_rejected = 0
        for idx in df.index:
            status_val = df.at[idx, "Filter Status"]
            if pd.isna(status_val) or str(status_val).strip() == "" or str(status_val).strip().lower() == "nan":
                title = str(df.at[idx, "Title"]).lower()
                if bad_words_pattern.search(title) and "junior manager" not in title and "trainee manager" not in title:
                    df.at[idx, "Filter Status"] = "Rejected (Pre-Filter)"
                    pre_filter_rejected += 1
                    
        if pre_filter_rejected > 0:
            print(f"Pre-filtered and rejected {pre_filter_rejected} jobs based on title keywords.")
            df.to_csv(INPUT_FILE, index=False)

        # Identify pending jobs (Status is empty/NaN)
        # We process 'records' of pending jobs, but need to map back to dataframe indices
        pending_mask = df["Filter Status"].isna() | (df["Filter Status"].astype(str).str.strip() == "") | (df["Filter Status"].astype(str).str.strip().str.lower() == "nan")
        pending_indices = df[pending_mask].index.tolist()
        
        if not pending_indices:
            print("All jobs already filtered! Nothing to do.")
            return

        print(f"Found {len(pending_indices)} new jobs to filter out of {len(df)} total.")

        batch_size = 20
        # We don't really need 'keep_indices' for the whole file anymore, 
        # we append to filtered file incrementally.
        
        # Load existing filtered jobs to append to
        if os.path.exists(OUTPUT_FILE):
            filtered_df_accumulator = pd.read_excel(OUTPUT_FILE)
        else:
            filtered_df_accumulator = pd.DataFrame(columns=df.columns)
            
        total_pending = len(pending_indices)
        
        for i in range(0, total_pending, batch_size):
            # Get batch of DataFrame INDICES
            batch_idxs = pending_indices[i : i + batch_size]
            current_batch_df = df.loc[batch_idxs]
            batch_records = current_batch_df.to_dict('records')
            
            print(f"Processing batch {i} to {min(i+batch_size, total_pending)}...")
            
            # Run AI Filter
            results = self.filter_batch(batch_records)
            
            # Update Status in Main DF and Collect Kept Jobs
            batch_kept_rows = []
            
            for j, res in enumerate(results):
                original_idx = batch_idxs[j]
                df.at[original_idx, "AI Score"] = res["score"]
                df.at[original_idx, "AI Reason"] = res["reason"]
                
                if res["keep"]:
                    df.at[original_idx, "Filter Status"] = "Kept"
                    batch_kept_rows.append(df.loc[original_idx])
                else:
                    df.at[original_idx, "Filter Status"] = "Rejected"
            
            # Incremental Save to Filtered Output
            if batch_kept_rows:
                new_kept_df = pd.DataFrame(batch_kept_rows)
                # Drop Filter Status column for the output file if desired, or keep it
                if "Filter Status" in new_kept_df.columns:
                    new_kept_df = new_kept_df.drop(columns=["Filter Status"])
                    
                # Append to file (Conceptually)
                # We read accumulator, concat, and save.
                filtered_df_accumulator = pd.concat([filtered_df_accumulator, new_kept_df], ignore_index=True)
                filtered_df_accumulator.drop_duplicates(subset=["Title", "Company", "Location", "URL"], inplace=True)
                filtered_df_accumulator.to_excel(OUTPUT_FILE, index=False)
            
            # Save Progress to Input File (Marking as Done)
            df.to_csv(INPUT_FILE, index=False)
            
            # Rate Limiting
            import time
            time.sleep(2) # Reduced sleep since we are saving files which takes time

        print(f"\nFiltering complete. Total Kept Jobs: {len(filtered_df_accumulator)}")

if __name__ == "__main__":
    job_filter = JobFilter()
    job_filter.run()
