import asyncio
import os
import pandas as pd
import json
from src.ai_client import ai_client

async def filter_url_batch(urls):
    """
    Sends a batch of URLs to AI to filter based on the semantic slug.
    """
    # Create a list representation
    batch_text = "\n".join([f"{i}. {url}" for i, url in enumerate(urls)])
    
    prompt = settings.FILTER_PROMPT.format(batch_text=batch_text)
    
    # Rate limit guard
    await asyncio.sleep(1)
    
    text = await ai_client.generate_content(prompt, json_mode=True)
    if not text:
        return []

    try:
        # Clean potential markdown
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
            text = text.strip()
            
        indices = json.loads(text)
        return indices
    except Exception as e:
        print(f"   [Batch Error] Parsing failed: {e}")
        return []

async def main():
    # Determine AI Provider readiness
    if settings.AI_PROVIDER == "openrouter" and not settings.OPENROUTER_API_KEY:
        print("CRITICAL: OPENROUTER_API_KEY not found in settings.")
        return
    if settings.AI_PROVIDER == "gemini" and not settings.GOOGLE_API_KEY:
        print("CRITICAL: GOOGLE_API_KEY not found in settings.")
        return

    # Determine Input File
    # Determine Input File
    # Always prioritize the raw URLS_FILE which is updated by fetch_urls.py
    if os.path.exists(settings.URLS_FILE):
        print(f"Using raw URLs from '{settings.URLS_FILE}'")
        input_file = settings.URLS_FILE
    elif os.path.exists(settings.URLS_VALIDATED_FILE):
        print(f"Using validated URLs from '{settings.URLS_VALIDATED_FILE}' (Fallback)")
        input_file = settings.URLS_VALIDATED_FILE
    else:
        print(f"No URL file found ({settings.URLS_FILE}).")
        return

    # Load URLs
    with open(input_file, "r", encoding="utf-8") as f:
        all_urls = [line.strip() for line in f if line.strip()]

    # Load existing KEPT URLs
    if os.path.exists(settings.FILTERED_JOBS_FILE):
        existing_df = pd.read_excel(settings.FILTERED_JOBS_FILE)
        kept_urls_set = set(existing_df["URL"].tolist())
    else:
        existing_df = pd.DataFrame(columns=["URL", "Title", "Filter Status"])
        kept_urls_set = set()
    
    # Load existing REJECTED URLs
    if os.path.exists(settings.REJECTED_URLS_FILE):
        with open(settings.REJECTED_URLS_FILE, "r", encoding="utf-8") as f:
            rejected_urls_set = set(line.strip() for line in f if line.strip())
    else:
        rejected_urls_set = set()
    
    # Only process URLs that are NOT already kept or rejected
    already_processed = kept_urls_set | rejected_urls_set
    pending_urls = [u for u in all_urls if u not in already_processed]

    print(f"Total URLs: {len(all_urls)}. Already Kept: {len(kept_urls_set)}. Already Rejected: {len(rejected_urls_set)}. NEW to Filter: {len(pending_urls)}")
    
    if len(pending_urls) == 0:
        print("No new URLs to filter. Exiting.")
        return
    
    kept_urls = []
    
    # Process in batches
    for i in range(0, len(pending_urls), settings.BATCH_SIZE):
        batch = pending_urls[i : i + settings.BATCH_SIZE]
        print(f"\nProcessing Batch {i//settings.BATCH_SIZE + 1} ({len(batch)} URLs)...")
        
        relevant_indices = await filter_url_batch(batch)
        
        print(f"   Kept {len(relevant_indices)} / {len(batch)}")
        
        batch_kept = []
        batch_kept_indices = set()
        for idx in relevant_indices:
            if 0 <= idx < len(batch):
                batch_kept.append(batch[idx])
                batch_kept_indices.add(idx)
                print(f"   + {batch[idx].split('/')[-1]}")
        
        kept_urls.extend(batch_kept)
        
        # Track rejected URLs (all indices NOT in kept)
        batch_rejected = [batch[idx] for idx in range(len(batch)) if idx not in batch_kept_indices]
        
        # Save rejected URLs to file (append)
        if batch_rejected:
            with open(settings.REJECTED_URLS_FILE, "a", encoding="utf-8") as f:
                for url in batch_rejected:
                    f.write(url + "\n")
        
        # Incremental Save (Validation for user)
        if batch_kept:
             new_df = pd.DataFrame(batch_kept, columns=["URL"])
             new_df["Title"] = new_df["URL"].apply(lambda x: x.split('/')[-1].split('-', 1)[1].replace('-', ' ').title() if '-' in x.split('/')[-1] else "Unknown")
             new_df["Filter Status"] = "Kept"
             
             if os.path.exists(settings.FILTERED_JOBS_FILE):
                 existing_df = pd.read_excel(settings.FILTERED_JOBS_FILE)
                 combined_df = pd.concat([existing_df, new_df], ignore_index=True)
             else:
                 combined_df = new_df
                 
             # Deduplicate output just in case
             combined_df.drop_duplicates(subset=["URL"], inplace=True)
             combined_df.to_excel(settings.FILTERED_JOBS_FILE, index=False)
             print(f"   Saved {len(new_df)} new jobs to {settings.FILTERED_JOBS_FILE}.")

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
