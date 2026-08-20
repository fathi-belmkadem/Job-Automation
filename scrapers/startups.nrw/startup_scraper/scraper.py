import csv
import time
from playwright.sync_api import sync_playwright

def scrape_list(page):
    print("Navigating to list page...")
    page.goto("https://startups.nrw/organizations/startups")
    
    # Handle cookie banner if it appears
    try:
        page.get_by_text("Accept All").click(timeout=5000)
        print("Clicked cookie banner.")
    except:
        print("No cookie banner found or already accepted.")

    # Scroll to load all items
    last_height = page.evaluate("document.body.scrollHeight")
    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2) # Wait for content to load
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            # Try one more time to be sure
            time.sleep(2)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
        last_height = new_height
        print(f"Scrolled to height: {last_height}")
        
        # Limit for verification
        if last_height > 1000000: # High limit just in case
            print("Stopping scroll at high limit...")
            break 

    print("Finished scrolling.")
    
    # Extract links
    # Selector fixed: removed gap-2.5 due to dot issue, using other unique classes
    links = page.locator("a.flex.flex-col.p-5.w-full").evaluate_all("elements => elements.map(e => e.href)")
    print(f"Found {len(links)} startups.")
    
    # For verification/testing, let's limit to top 10 initially. 
    # User can remove this slice to scrape all.
    return list(set(links))

def scrape_details(page, url):
    try:
        page.goto(url, timeout=60000)
        # Random sleep to be nice
        time.sleep(0.5)
        
        # Data container
        data = {
            "Company Name": "",
            "Description": "",
            "Email": "",
            "Website": "",
            "Contact Name": ""
        }
        
        # Wait for potential content load
        try:
            page.wait_for_selector("span.font-semibold.text-gray-700", timeout=5000)
        except:
            pass

        # Company Name
        # Subagent found: span.text-sm.leading-6.break-word.font-semibold.text-gray-700
        # Also keeping fallback to p tag just in case
        name_loc = page.locator("span.font-semibold.text-gray-700")
        if name_loc.count() > 0:
            data["Company Name"] = name_loc.first.inner_text()
        else:
            name_loc_p = page.locator("p.font-semibold.text-gray-700")
            if name_loc_p.count() > 0:
                data["Company Name"] = name_loc_p.first.inner_text()
            else:
                 # Fallback: try finding any font-semibold in the main area if specific classes fail
                 # This might be risky but better than empty
                 pass
            
        # Description
        # Selector: span.font-normal.text-gray-500.text-sm.leading-6.break-word
        desc_loc = page.locator("span.font-normal.text-gray-500.text-sm.leading-6.break-word")
        if desc_loc.count() > 0:
            texts = desc_loc.all_inner_texts()
            # Clean up texts: remove newlines, multiple spaces
            cleaned_texts = [t.strip().replace("\n", " ") for t in texts if t.strip()]
            data["Description"] = " ".join(cleaned_texts)
            
        # Email
        # Selector: a[href^="mailto:"]
        email_loc = page.locator('a[href^="mailto:"]')
        if email_loc.count() > 0:
            data["Email"] = email_loc.first.inner_text()
            
        # Website
        # Selector: a[href^="http"]:not([href*="startups.nrw"])
        # We need to be careful not to pick up social media links as the "main" website if possible, 
        # but usually the main website is the first external link or specifically placed.
        # The browser agent suggested: a[target="_blank"][href^="http"]
        # Let's try to find one that looks like a homepage.
        # Website
        # Selector: a[href^="http"]:not([href*="startups.nrw"])
        # Prioritize links that look like main websites
        website_locs = page.locator('a[href^="http"]:not([href*="startups.nrw"]):not([href^="mailto:"])').all()
        for loc in website_locs:
            href = loc.get_attribute("href")
            # Filter out common social media and internal/unwanted links
            if not any(x in href for x in ["linkedin.com", "facebook.com", "instagram.com", "twitter.com", "uic.io", "google.com", "maps"]):
                 data["Website"] = href
                 break
        
        # Contact Name
        # This is tricky as noted. We'll look for simple cues or just leave empty if not specific.
        # Sometimes it's in a "Contact" section.
        # For now, we'll leave it empty or try to find a header "Contact Person"
        
        # Refined: Check if there's a specific contact card?
        # Based on inspection, it's not consistent. 
        # We'll just grab the email prefix if really needed, but sticking to scraped text for now.
        
        return data
        
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def main():
    with sync_playwright() as p:
        # Launch browser (headless=False to see what's happening during dev)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            detail_links = scrape_list(page)
            
            all_data = []
            for i, link in enumerate(detail_links):
                print(f"Scraping [{i+1}/{len(detail_links)}]: {link}")
                details = scrape_details(page, link)
                if details:
                    all_data.append(details)
                    
            # Save to CSV
            keys = ["Company Name", "Description", "Email", "Website", "Contact Name"]
            with open('startups_nrw.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(all_data)
                
            print("Done! Saved to startups_nrw.csv")
            
        finally:
            browser.close()

if __name__ == "__main__":
    main()
