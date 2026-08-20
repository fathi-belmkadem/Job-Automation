import os
import time
import re
import random
import sys
import json
import requests
from pathlib import Path

# Add project root to path to allow importing config
sys.path.append(str(Path(__file__).parent.parent))
from config import settings

# Configuration for Regions and Keywords
# Priority order: DACH > Benelux > Others
REGION_CONFIG = settings.REGION_CONFIG


def search_perplexity(query, api_key):
    """
    Uses Perplexity API to find URLs matching the query.
    Returns a list of URLs.
    """
    url = "https://api.perplexity.ai/chat/completions"
    
    payload = {
        "model": "sonar-pro", 
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful research assistant. Your task is to find specific job posting URLs on join.com."
            },
            {
                "role": "user",
                "content": f"Find 10 ACTIVE and RECENT job posting URLs on join.com for '{query}'. IMPORTANT: Only include jobs that are currently open and accepting applications - do NOT include archived, expired, or closed job postings. Return ONLY a JSON list of valid URLs. Example: [\"https://join.com/companies/foo/jobs/123-bar\", ...]. Do not include any other text."
            }
        ],
        "temperature": 0.1
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Extract JSON list from content
        start = content.find('[')
        end = content.rfind(']') + 1
        if start != -1 and end != -1:
            json_str = content[start:end]
            urls = json.loads(json_str)
            return urls
        
        # Fallback if no JSON found, try to find URLs in text
        found_urls = re.findall(r'https://join\.com/companies/[\w-]+/[\w-]+', content)
        return found_urls
        
    except Exception as e:
        print(f"Perplexity API Error: {e}")
        if response and response.text:
             print(f"Response: {response.text}")
        return []


def search_brave(query, api_key, time_filter=True):
    """
    Uses Brave Search API to find URLs matching the query.
    Returns a list of URLs. Fetches up to 20 results.
    Args:
        time_filter: If True, apply SEARCH_TIME_LIMIT restriction (freshness). If False, skip it.
    """
    base_url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key
    }
    
    params = {
        "q": query,
        "count": 20
    }
    
    # Map our time limit settings to Brave's freshness parameter
    # Brave uses: pd (past 24 hours), pw (past week), pm (past month), py (past year)
    time_map = {
        "past_24h": "pd",
        "past_week": "pw",
        "past_month": "pm",
    }
    if time_filter and settings.SEARCH_TIME_LIMIT and settings.SEARCH_TIME_LIMIT in time_map:
        params["freshness"] = time_map[settings.SEARCH_TIME_LIMIT]
        
    try:
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("web", {}).get("results", [])
        return [item.get("url") for item in results if item.get("url")]
    except Exception as e:
        print(f"   [Error] Brave API Search Error: {e}")
        if 'response' in locals() and response.text:
            print(f"Response: {response.text}")
        return []

def search_scrapingbee(query, api_key, time_filter=True):
    """
    Uses ScrapingBee Google Search API to find URLs matching the query.
    Returns a list of URLs.
    Args:
        time_filter: If True, apply SEARCH_TIME_LIMIT restriction. If False, skip it.
    """
    base_url = "https://app.scrapingbee.com/api/v1/store/google"
    params = {
        "api_key": api_key,
        "search": query,
        "nb_results": 20
    }
    
    # Note: ScrapingBee's Google Search API might need extra params passed to Google via `extra_params`
    # if it supports the 'tbs' parameter for time filtering.
    time_map = {
        "past_24h": "qdr:d",
        "past_week": "qdr:w",
        "past_month": "qdr:m",
    }
    if time_filter and settings.SEARCH_TIME_LIMIT and settings.SEARCH_TIME_LIMIT in time_map:
        params["extra_params"] = f"tbs={time_map[settings.SEARCH_TIME_LIMIT]}"
        
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("organic_results", [])
        return [item.get("url") for item in results if item.get("url")]
    except Exception as e:
        print(f"   [Error] ScrapingBee API Search Error: {e}")
        if 'response' in locals() and response.text:
            print(f"Response: {response.text}")
        return []

def search_google(query, api_key, engine_id, time_filter=True):
    """
    Uses Google Custom Search JSON API to find URLs matching the query.
    Returns a list of URLs. Fetches up to 2 pages (20 results).
    Args:
        time_filter: If True, apply SEARCH_TIME_LIMIT date restriction. If False, skip it.
    """
    base_url = "https://www.googleapis.com/customsearch/v1"
    all_urls = []

    # Google Custom Search returns max 10 results per page
    for start_index in [1, 11]:
        params = {
            "key": api_key,
            "cx": engine_id,
            "q": query,
            "start": start_index,
            "num": 10,
        }

        # Map our time limit settings to Google's dateRestrict parameter
        time_map = {
            "past_24h": "d1",
            "past_week": "w1",
            "past_month": "m1",
        }
        if time_filter and settings.SEARCH_TIME_LIMIT and settings.SEARCH_TIME_LIMIT in time_map:
            params["dateRestrict"] = time_map[settings.SEARCH_TIME_LIMIT]

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if not items:
                break  # No more results

            for item in items:
                link = item.get("link", "")
                if link:
                    all_urls.append(link)

        except Exception as e:
            print(f"Google Search API Error: {e}")
            if 'response' in dir() and response and response.text:
                print(f"Response: {response.text}")
            break

    return all_urls



def search_serpapi(query, api_key, time_filter=True):
    """
    Uses SerpAPI (Google Engine) to find URLs matching the query.
    Returns a list of URLs. Fetches up to 2 pages (20 results).
    Handles 429 Rate Limits with exponential backoff.
    Args:
        time_filter: If True, apply SEARCH_TIME_LIMIT tbs restriction. If False, skip it.
    """
    base_url = "https://serpapi.com/search.json"
    all_urls = []

    # Map time limit settings to SerpAPI (Google) 'tbs' parameter (qdr:h, qdr:d, qdr:w, qdr:m)
    tbs = ""
    time_map = {
        "past_24h": "qdr:d",
        "past_week": "qdr:w",
        "past_month": "qdr:m",
    }
    if time_filter and settings.SEARCH_TIME_LIMIT and settings.SEARCH_TIME_LIMIT in time_map:
        tbs = time_map[settings.SEARCH_TIME_LIMIT]

    # Retry loop for 429 Rate Limits
    max_retries = 3
    backoff = 5  # Start with 5s

    for start_index in [0, 10]:
        params = {
            "api_key": api_key,
            "engine": "google",
            "q": query,
            "start": start_index,
            "num": 10,
        }
        if tbs:
            params["tbs"] = tbs

        for attempt in range(max_retries):
            try:
                response = requests.get(base_url, params=params)
                
                # Check specifics for 429 before raising other statuses
                if response.status_code == 429:
                    print(f"   [Rate Limit] SerpAPI 429. Sleeping {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2 # Exponential backoff
                    continue # Retry
                
                response.raise_for_status()
                data = response.json()

                # Check for error in response even if status is 200 (SerpAPI sometimes does this)
                if "error" in data:
                    print(f"SerpAPI Error: {data['error']}")
                    # If error is related to rate limit?
                    if "rate limit" in str(data['error']).lower():
                         print(f"   [Rate Limit] Sleeping {backoff}s...")
                         time.sleep(backoff)
                         backoff *= 2
                         continue
                    break

                items = data.get("organic_results", [])
                if not items:
                    break # Stop pagination if no results

                for item in items:
                    link = item.get("link", "")
                    if link:
                        all_urls.append(link)
                
                break # Success, exit retry loop, continue to next page (start_index)

            except Exception as e:
                print(f"SerpAPI Request Error: {e}")
                # Don't retry for generic exceptions unless needed
                break
    
    return all_urls


def fetch_urls(engine=None):
    """
    Fetch job URLs from join.com using the specified search engine.
    
    Args:
        engine: 'google', 'perplexity', 'serpapi', 'brave', or 'scrapingbee'. Defaults to settings.DEFAULT_SEARCH_ENGINE.
    """
    # Determine engine: explicit arg > env var > settings default
    if engine is None:
        engine = os.getenv("SEARCH_ENGINE", settings.DEFAULT_SEARCH_ENGINE)
    engine = engine.lower()

    # Validate API keys based on chosen engine
    if engine == "perplexity":
        api_key = settings.PERPLEXITY_API_KEY or os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            print("Error: PERPLEXITY_API_KEY not found in environment.")
            return
        print("Starting Multi-Region Search using Perplexity...")
    elif engine == "google":
        if not settings.GOOGLE_SEARCH_API_KEY:
            print("Error: GOOGLE_SEARCH_API_KEY not found in environment.")
            return
        if not settings.SEARCH_ENGINE_ID:
            print("Error: SEARCH_ENGINE_ID not found in environment.")
            return
        print("Starting Multi-Region Search using Google...")
    elif engine == "serpapi":
        api_key = settings.SERPAPI_KEY or os.getenv("SERPAPI_KEY")
        if not api_key:
             print("Error: SERPAPI_KEY not found in environment.")
             return
        print("Starting Multi-Region Search using SerpAPI...")
    elif engine == "brave":
        api_key = settings.BRAVE_API_KEY or os.getenv("BRAVE_API_KEY")
        if not api_key:
            print("Error: BRAVE_API_KEY not found in environment.")
            return
        print("Starting Multi-Region Search using Brave Search...")
    elif engine == "scrapingbee":
        api_key = settings.SCRAPINGBEE_API_KEY or os.getenv("SCRAPINGBEE_API_KEY")
        if not api_key:
            print("Error: SCRAPINGBEE_API_KEY not found in environment.")
            return
        print("Starting Multi-Region Search using ScrapingBee...")
    else:
        print(f"Error: Unknown search engine '{engine}'. Use 'google', 'perplexity', 'serpapi', 'brave', or 'scrapingbee'.")
        return

    # Load existing URLs
    all_urls = set()
    if os.path.exists(settings.URLS_FILE):
        with open(settings.URLS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip(): all_urls.add(line.strip())
    
    print(f"Pre-existing URLs: {len(all_urls)}")
    
    new_urls_count = 0

    # Search Loop
    for region_code, config in REGION_CONFIG.items():
        region_name = config['name']
        print(f"\n--- Region: {region_name} ({region_code.upper()}) ---")
        
        keywords = config['keywords']
        random.shuffle(keywords)

        for keyword in keywords:
            # Add time limit to the natural language query for Perplexity
            time_instruction = ""
            if settings.SEARCH_TIME_LIMIT and settings.SEARCH_TIME_LIMIT != "any_time":
                time_instruction = f" published in the {settings.SEARCH_TIME_LIMIT.replace('_', ' ')}"
            
            # Base query for structured engines (Google, SerpAPI)
            # Try specific query first: "{keyword} {region_name}"
            base_query = f"site:join.com/companies {keyword} {region_name}"
            
            # Natural language query for Perplexity
            perplexity_query = f"site:join.com/companies {keyword} in {region_name}{time_instruction}"
            
            print(f"Searching: '{base_query}' (Engine: {engine})")
            
            # Call the appropriate search engine
            urls = []
            if engine == "perplexity":
                urls = search_perplexity(perplexity_query, api_key)
            elif engine == "google":
                urls = search_google(base_query, settings.GOOGLE_SEARCH_API_KEY, settings.SEARCH_ENGINE_ID)
            elif engine == "serpapi":
                urls = search_serpapi(base_query, api_key)
            elif engine == "brave":
                urls = search_brave(base_query, api_key)
            elif engine == "scrapingbee":
                urls = search_scrapingbee(base_query, api_key)
                
            # Multi-stage fallback for structured engines if no results found
            if not urls and engine in ["google", "serpapi", "brave", "scrapingbee"]:
                # Stage 2: Same query but WITHOUT time filter
                print(f"   No results. Retrying without time filter...")
                if engine == "google":
                    urls = search_google(base_query, settings.GOOGLE_SEARCH_API_KEY, settings.SEARCH_ENGINE_ID, time_filter=False)
                elif engine == "serpapi":
                    urls = search_serpapi(base_query, api_key, time_filter=False)
                elif engine == "brave":
                    urls = search_brave(base_query, api_key, time_filter=False)
                elif engine == "scrapingbee":
                    urls = search_scrapingbee(base_query, api_key, time_filter=False)
            
            if not urls and engine in ["google", "serpapi", "brave", "scrapingbee"]:
                # Stage 3: Broader query (no region) without time filter
                broad_query = f"site:join.com/companies {keyword}"
                print(f"   Still no results. Retrying with broader query: '{broad_query}'...")
                if engine == "google":
                    urls = search_google(broad_query, settings.GOOGLE_SEARCH_API_KEY, settings.SEARCH_ENGINE_ID, time_filter=False)
                elif engine == "serpapi":
                    urls = search_serpapi(broad_query, api_key, time_filter=False)
                elif engine == "brave":
                    urls = search_brave(broad_query, api_key, time_filter=False)
                elif engine == "scrapingbee":
                    urls = search_scrapingbee(broad_query, api_key, time_filter=False)
            
            batch_new = 0
            if urls:
                for link in urls:
                    if is_valid_join_url(link):
                        if link not in all_urls:
                            all_urls.add(link)
                            new_urls_count += 1
                            batch_new += 1
                            with open(settings.URLS_FILE, "a", encoding="utf-8") as f:
                                f.write(link + "\n")
                                f.flush()
            
            print(f"   Found {batch_new} NEW URLs.")
            time.sleep(5) # Conservative delay to avoid 429s

    print(f"\nSearch Complete. Found {new_urls_count} NEW URLs.")

def is_valid_join_url(url):
    """
    Validates if the URL matches the expected pattern for a specific job posting on join.com.
    Pattern: https://join.com/companies/<company>/<id>-<title>
    """
    if not isinstance(url, str):
        return False
    if "join.com/companies/" not in url:
        return False
    
    parts = url.rstrip('/').split('/')
    if len(parts) < 6:
        return False
    
    # Check last part for digit-start (ID)
    job_slug = parts[-1] 
    if not re.match(r'^\d+', job_slug):
         return False
         
    return True

if __name__ == "__main__":
    # Support engine override via command-line arg (e.g. fetch_urls.py google)
    engine_arg = None
    if len(sys.argv) > 1:
        engine_arg = sys.argv[1]
    fetch_urls(engine=engine_arg)
