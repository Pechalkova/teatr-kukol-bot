```python
import asyncio
from playwright.async_api import async_playwright

TEST_URL = (
    "https://tce.by/shows.html?"
    "base=RkZDMTE2MUQtMTNFNy00NUIyLTg0QzYtMURDMjRBNTc1ODA0"
    "&data=4967"
)


async def main():
    print("========================================")
    print("TEST TCE WITH BROWSER")
    print("========================================")
    print("URL:")
    print(TEST_URL)
    print()

    async with async_playwright() as p:
        print("Запускаем Chromium...")

        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page(
            viewport={"width": 1366, "height": 900},
            locale="ru-RU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        try:
            print("Открываем страницу...")

            response = await page.goto(
                TEST_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            print()
            print("HTTP STATUS:", response.status if response else "NO RESPONSE")
            print("FINAL URL:", page.url)
            print()

            print("TITLE:")
            print(await page.title())
            print()

            print("WAIT 10 SECONDS FOR JAVASCRIPT...")
            await page.wait_for_timeout(10000)

            print()
            print("FINAL URL AFTER WAIT:")
            print(page.url)

            print()
            print("TITLE AFTER WAIT:")
            print(await page.title())

            print()
            print("PAGE TEXT:")
            print("----------------------------------------")

            text = await page.locator("body").inner_text()

            print(text[:5000])

            print("----------------------------------------")
            print()

            if "Making sure you're not a bot" in text:
                print("RESULT: ANUBIS CHALLENGE IS STILL ACTIVE")
            elif "Киви" in text or "КИВИ" in text:
                print("RESULT: EVENT PAGE LOADED")
            else:
                print("RESULT: PAGE LOADED, BUT EVENT TEXT NOT FOUND")

        except Exception as e:
            print()
            print("ERROR:")
            print(repr(e))

        finally:
            await browser.close()

    print()
    print("========================================")
    print("TEST FINISHED")
    print("========================================")


asyncio.run(main())
