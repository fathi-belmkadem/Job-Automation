import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        
        # Load session state if it exists
        session_path = os.path.join("config", "session.json")
        context_args = {"locale": "en-GB"}
        if os.path.exists(session_path):
            context = await browser.new_context(storage_state=session_path, **context_args)
        else:
            context = await browser.new_context(**context_args)
            
        page = await context.new_page()
        
        # Search query
        search_query = "Data Scientist"
        location = "Germany"
        test_url = f"https://www.xing.com/jobs/search?keywords={search_query}&location={location}"
        
        print(f"Navigating to test URL: {test_url}")
        try:
            await page.goto(test_url)
            await page.wait_for_load_state("networkidle")
            
            # Close search alert modal if it appears
            try:
                close_btn = page.locator("button[aria-label='Close']").first
                if await close_btn.is_visible(timeout=3000):
                    print("Closing search alert modal...")
                    await close_btn.click()
            except:
                pass

            # Loop to click "Show more" button a few times
            for i in range(3):
                print(f"Scroll iteration {i+1}")
                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)

                # Identify "Show more" button
                # Based on research: button:has-text("Show more") or button[data-testid='load-more-button']
                show_more_selectors = [
                    "button:has-text('Show more')",
                    "button:has-text('Mehr anzeigen')",
                    "button[data-testid='load-more-button']"
                ]
                
                found_btn = False
                for selector in show_more_selectors:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        print(f"Found '{selector}'. Clicking...")
                        await btn.click()
                        await page.wait_for_timeout(3000)
                        found_btn = True
                        break
                
                if not found_btn:
                    print("No 'Show more' button found or visible.")
                    break

            print(f"\nFinal URL: {page.url}")
            print(f"Page Title: {await page.title()}")
            
            # Check results
            cards = await page.locator("article[data-testid='job-search-result']").all()
            print(f"Found {len(cards)} job results after loading more.")
            
            # Take a screenshot to verify
            await page.screenshot(path="search_debug.png")
            print("Screenshot saved to search_debug.png")
                
        except Exception as e:
            print(f"Error: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

