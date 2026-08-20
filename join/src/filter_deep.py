import asyncio
import os
import pandas as pd
import json
from src.ai_client import ai_client

class DeepFilter:
    def __init__(self):
        if settings.AI_PROVIDER == "openrouter" and not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY not found in settings")
        if settings.AI_PROVIDER == "gemini" and not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in settings")

    async def filter_batch(self, jobs_batch):
        """
        Sends a batch of full job descriptions to Gemini for deep analysis.
        """
        job_lines = []
        for i, job in enumerate(jobs_batch):
            title = job.get('Title', 'Unknown')
            company = job.get('Company', 'Unknown')
            desc = job.get('Job Description', '')[:2000] # Limit tokens
            job_lines.append(f"INDEX: {i}\nTITLE: {title}\nCOMPANY: {company}\nDESCRIPTION: {desc}\n---")

        jobs_text = "\n".join(job_lines)
        prompt = settings.DEEP_FILTER_PROMPT.format(jobs_text=jobs_text)
        
        text = await ai_client.generate_content(prompt, json_mode=True)
        if not text:
            return []

        try:
            # Clean potential markdown
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"): text = text[4:]
                text = text.strip()
            return json.loads(text)
        except Exception as e:
            print(f"   [DeepFilter] Parsing failed: {e}")
            return []

    def run_regex_filter(self, df):
        """
        Fast pre-filter using blocklist keywords.
        """
        blocklist = r'\b(senior|lead|principal|head of|director|manager|architect|expert|staff|vp|chief)\b'
        pattern = re.compile(blocklist, re.IGNORECASE)
        
        rejected_count = 0
        for index, row in df.iterrows():
            if row.get("Filter Status") == "Kept": # Only check what passed Pass 1
                title = str(row.get("Title", "")).lower()
                # Allow 'Junior Manager' or 'Trainee Manager'
                if pattern.search(title) and "junior" not in title and "trainee" not in title:
                    df.at[index, "Filter Status"] = "Rejected (Regex Deep)"
                    rejected_count += 1
        return rejected_count

    async def run(self):
        if not os.path.exists(settings.FILTERED_JOBS_FILE):
            print("Filtered jobs file not found.")
            return

        df = pd.read_excel(settings.FILTERED_JOBS_FILE)
        
        # 1. Regex Pass
        print("Running Regex Pre-Filter...")
        reg_rej = self.run_regex_filter(df)
        print(f"   Rejected {reg_rej} jobs via Regex.")
        
        # 2. AI Pass
        pending_df = df[(df["Filter Status"] == "Kept") & (df["Job Description"].notna())]
        if pending_df.empty:
            print("No jobs for Deep AI analysis.")
            df.to_excel(settings.FILTERED_JOBS_FILE, index=False)
            return

        print(f"Deep Filtering {len(pending_df)} jobs...")
        
        batch_size = 5
        pending_indices = pending_df.index.tolist()
        
        for i in range(0, len(pending_indices), batch_size):
            idxs = pending_indices[i : i + batch_size]
            batch_records = df.loc[idxs].to_dict('records')
            
            print(f"   Processing batch {i//batch_size + 1}...")
            results = await self.filter_batch(batch_records)
            
            for res in results:
                idx_in_batch = res.get("index")
                if idx_in_batch is not None and idx_in_batch < len(idxs):
                    orig_idx = idxs[idx_in_batch]
                    decision = res.get("decision", "reject")
                    reason = res.get("reason", "")
                    
                    if decision == "keep":
                        df.at[orig_idx, "Filter Status"] = "Kept (Deep)"
                        print(f"      [KEEP] {df.at[orig_idx, 'Title']}")
                    else:
                        df.at[orig_idx, "Filter Status"] = "Rejected (Deep)"
                        print(f"      [REJECT] {df.at[orig_idx, 'Title']}: {reason}")
            
            df.to_excel(settings.FILTERED_JOBS_FILE, index=False)
            await asyncio.sleep(2)

if __name__ == "__main__":
    filter_tool = DeepFilter()
    asyncio.run(filter_tool.run())
