"""
automation/browser.py — Browser control using Playwright

Can:
- Open URLs
- Search Google / YouTube / any site
- Fill forms
- Click buttons
- Read page content
- Take screenshots of web pages

Setup: After pip install playwright, run: playwright install chromium
"""
import asyncio
from utils.logger import logger


class BrowserController:
    """
    Headless or headed browser automation.
    Uses Playwright's Python bindings.
    """

    def __init__(self, headless: bool = False):
        """
        headless=False means you SEE the browser window (better for demos).
        headless=True runs in the background (faster, no window).
        """
        self.headless = headless
        self._browser = None
        self._page = None
        self._playwright = None

    async def _ensure_browser(self):
        """Start browser if not already running."""
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._page = await self._browser.new_page()
            logger.info("Browser started.")

    async def navigate(self, url: str) -> str:
        """Navigate to a URL and return the page title."""
        await self._ensure_browser()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await self._page.title()
        logger.info(f"Navigated to: {url} — '{title}'")
        return title

    async def search_google(self, query: str) -> list[dict]:
        """
        Search Google and return top results.
        Returns list of {title, url, snippet} dicts.
        """
        await self._ensure_browser()
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        await self._page.goto(search_url, wait_until="domcontentloaded")

        results = []
        try:
            # Extract search result cards
            items = await self._page.query_selector_all("div.g")
            for item in items[:5]:
                title_el = await item.query_selector("h3")
                link_el = await item.query_selector("a")
                snippet_el = await item.query_selector("div[data-sncf]")

                title = await title_el.inner_text() if title_el else ""
                url = await link_el.get_attribute("href") if link_el else ""
                snippet = await snippet_el.inner_text() if snippet_el else ""

                if title and url:
                    results.append({"title": title, "url": url, "snippet": snippet})
        except Exception as e:
            logger.error(f"Google scraping failed: {e}")

        logger.info(f"Found {len(results)} results for '{query}'")
        return results

    async def search_youtube(self, query: str) -> str:
        """Open YouTube search and play the first result."""
        await self._ensure_browser()
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await self._page.goto(url, wait_until="domcontentloaded")

        # Click first video result
        first = await self._page.query_selector("ytd-video-renderer a#video-title")
        if first:
            await first.click()
            await asyncio.sleep(2)
            title = await self._page.title()
            logger.info(f"Playing YouTube: {title}")
            return title
        return ""

    async def get_page_text(self) -> str:
        """Get the visible text content of the current page."""
        await self._ensure_browser()
        return await self._page.inner_text("body")

    async def click(self, selector: str):
        """Click an element by CSS selector."""
        await self._ensure_browser()
        await self._page.click(selector)

    async def type_text(self, selector: str, text: str):
        """Type text into a form field."""
        await self._ensure_browser()
        await self._page.fill(selector, text)

    async def screenshot(self, path: str = "screenshot.png"):
        """Take a screenshot of the current page."""
        await self._ensure_browser()
        await self._page.screenshot(path=path)
        logger.info(f"Screenshot saved: {path}")

    async def close(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()
            self._browser = None
            logger.info("Browser closed.")

    # ── Sync wrappers (for non-async callers) ──────────────────────────────────

    def navigate_sync(self, url: str) -> str:
        return asyncio.run(self.navigate(url))

    def search_google_sync(self, query: str) -> list[dict]:
        return asyncio.run(self.search_google(query))

    def search_youtube_sync(self, query: str) -> str:
        return asyncio.run(self.search_youtube(query))
