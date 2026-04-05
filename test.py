import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            if asyncio.iscoroutinefunction(stealth):
                print("stealth is coroutine function")
                await stealth(page)
            else:
                res = stealth(page)
                if asyncio.iscoroutine(res):
                    print("stealth returned coroutine")
                    await res
                else:
                    print("stealth is sync function")
        except Exception as e:
            print(f"Error: {e}")
        await browser.close()
        print("Success!")

asyncio.run(main())
