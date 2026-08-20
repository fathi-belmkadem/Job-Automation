import asyncio
from playwright.async_api import async_playwright
import sys
from pathlib import Path

# Add project root to path to allow importing config
sys.path.append(str(Path(__file__).parent.parent))
from config import settings

async def login_and_save_state():
    async with async_playwright() as p:
        # Launch FIREFOX in visible mode (often bypasses bot detection better)
        browser = await p.firefox.launch(
            headless=False,
            args=[
                '--start-maximized'
            ]
        )
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        # --- Debugging Listeners ---
        page.on("console", lambda msg: print(f"Browser Console [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser Page Error: {err.message}"))
        
        async def handle_response(response):
            if response.status >= 400:
                print(f"Network Error [{response.status}]: {response.url}")
        
        page.on("response", handle_response)
        # ---------------------------

        print("Navigating to join.com...")
        await page.goto("https://join.com")

        print("\n" + "="*50)
        print("ACTION REQUIRED: Log in manually in the browser window.")
        print("Navigate to the login page if needed (candidates often login via application flow, but you can try to find a portal).")
        print("Once you are fully logged in, come back here.")
        print("="*50 + "\n")

        input("Press Enter here AFTER you have successfully logged in...")

        print("Saving session state...")
        await context.storage_state(path=settings.SESSION_FILE)
        print(f"Session saved to {settings.SESSION_FILE}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(login_and_save_state())
