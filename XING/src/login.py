import asyncio
from playwright.async_api import async_playwright
import os
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

async def main():
    async with async_playwright() as p:
        # Launch browser in non-headless mode so user can see it
        browser = await p.chromium.launch(headless=False)
        # Force English locale so session is captured in English
        context = await browser.new_context(locale="en-GB")
        page = await context.new_page()

        
        print("Navigating to XING login page...")
        try:
            await page.goto("https://login.xing.com/")
        except Exception as e:
            print(f"Error navigating to login page: {e}")
            return

        print("\n" + "="*50)
        print("PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW")
        print("="*50 + "\n")
        
        input("Press Enter in this terminal AFTER you have successfully logged in and can see your feed/homepage...")
        
        # Save storage state into the file.
        session_path = os.path.join(settings.CONFIG_DIR, "session.json")
        await context.storage_state(path=session_path)
        print(f"Session saved to {os.path.abspath(session_path)}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

