"""
automation/browser_agent.py — Jarvis Browser Agent

High-level Playwright wrapper. Each method is a discrete, composable action
that can be called directly or wired up as a Tool in the ToolRegistry.

Capabilities:
  navigate(url)                  → go to a URL, wait for load
  search(query, engine)          → web search, return list of results
  click(selector_or_text)        → smart click: CSS selector or visible text
  fill(selector, value)          → type into a field
  fill_form(fields)              → fill multiple fields at once {label: value}
  select(selector, value)        → choose a <select> option
  extract_text(selector?)        → pull text from page or specific element
  extract_links(selector?)       → return all href links on page
  screenshot(path?)              → save screenshot, return path
  wait_for(selector, timeout)    → wait for element to appear
  scroll(direction, amount)      → scroll page up/down/to element
  get_page_info()                → title + url + meta description
  get_page_summary()             → title + url + visible body text (trimmed)
  back() / forward()             → browser history navigation
  close()                        → shut down browser session
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class BrowserResult:
    succeeded: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    url: str = ""
    screenshots: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, output=None, url="", duration_ms=0.0, screenshots=None) -> "BrowserResult":
        return cls(True, output=output, url=url, duration_ms=duration_ms,
                   screenshots=screenshots or [])

    @classmethod
    def fail(cls, error: str, url="") -> "BrowserResult":
        return cls(False, error=error, url=url)


# ── Search engine URL templates ───────────────────────────────────────────────

SEARCH_ENGINES = {
    "google":     "https://www.google.com/search?q={query}",
    "bing":       "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "youtube":    "https://www.youtube.com/results?search_query={query}",
    "linkedin":   "https://www.linkedin.com/search/results/all/?keywords={query}",
    "github":     "https://github.com/search?q={query}",
    "internshala":"https://internshala.com/internships/keywords-{query}",
}

# Selectors for extracting search results per engine
RESULT_SELECTORS = {
    "google":     ("h3", "a[href]"),
    "bing":       ("h2", "a[href]"),
    "duckduckgo": ("h2", "a[href]"),
}


# ── BrowserAgent ──────────────────────────────────────────────────────────────

class BrowserAgent:
    """
    Stateful browser session. One instance = one browser tab.
    Use as an async context manager or call close() when done.

    Usage:
        agent = BrowserAgent(headless=False)
        await agent.navigate("https://google.com")
        results = await agent.search("python internships")
        await agent.close()
    """

    def __init__(
        self,
        headless: bool = False,
        screenshots_dir: str = "./data/screenshots",
        timeout_ms: int = 15_000,
    ):
        self.headless = headless
        self.screenshots_dir = Path(screenshots_dir)
        self.timeout_ms = timeout_ms

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._ready = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def _ensure_ready(self):
        """Lazy-initialise Playwright on first use."""
        if self._ready:
            return
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=["--start-maximized"],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()
            self._page.set_default_timeout(self.timeout_ms)
            self.screenshots_dir.mkdir(parents=True, exist_ok=True)
            self._ready = True
            logger.info("BrowserAgent ready (headless={})", self.headless)
        except Exception as e:
            raise RuntimeError(f"Failed to start browser: {e}") from e

    async def close(self):
        """Shut down the browser cleanly."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning("Error closing browser: {}", e)
        finally:
            self._ready = False
            self._page = None

    async def __aenter__(self):
        await self._ensure_ready()
        return self

    async def __aexit__(self, *_):
        await self.close()

    # ── Navigation ────────────────────────────────────────────────────────────

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> BrowserResult:
        """Navigate to a URL and wait for the page to load."""
        t0 = time.perf_counter()
        try:
            await self._ensure_ready()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            await self._page.goto(url, wait_until=wait_until)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug("Navigated to {} in {:.0f}ms", url, elapsed)
            return BrowserResult.ok(output=url, url=self._page.url, duration_ms=elapsed)
        except Exception as e:
            return BrowserResult.fail(f"Navigation failed: {e}", url=url)

    async def back(self) -> BrowserResult:
        try:
            await self._ensure_ready()
            await self._page.go_back()
            return BrowserResult.ok(url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(str(e))

    async def forward(self) -> BrowserResult:
        try:
            await self._ensure_ready()
            await self._page.go_forward()
            return BrowserResult.ok(url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(str(e))

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        engine: str = "google",
        max_results: int = 8,
    ) -> BrowserResult:
        """
        Navigate to a search engine and return structured results.
        Returns a list of {"title": ..., "url": ..., "snippet": ...} dicts.
        """
        t0 = time.perf_counter()
        try:
            await self._ensure_ready()
            template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["google"])
            from urllib.parse import quote_plus
            search_url = template.format(query=quote_plus(query))

            nav = await self.navigate(search_url)
            if not nav.succeeded:
                return nav

            # Small pause for JS-rendered results
            await self._page.wait_for_timeout(1500)

            results = await self._extract_search_results(engine, max_results)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("Search '{}' on {} → {} results", query, engine, len(results))
            return BrowserResult.ok(output=results, url=self._page.url, duration_ms=elapsed)
        except Exception as e:
            return BrowserResult.fail(f"Search failed: {e}")

    async def _extract_search_results(self, engine: str, max_results: int) -> list[dict]:
        """Extract title + url + snippet from search results page."""
        results = []
        try:
            if engine == "google":
                items = await self._page.query_selector_all("div.g, div[data-sokoban-container]")
                for item in items[:max_results * 2]:
                    try:
                        title_el = await item.query_selector("h3")
                        link_el  = await item.query_selector("a[href]")
                        snip_el  = await item.query_selector("div[data-sncf], div.IsZvec, span.aCOpRe")

                        title   = (await title_el.inner_text()).strip() if title_el else ""
                        href    = await link_el.get_attribute("href") if link_el else ""
                        snippet = (await snip_el.inner_text()).strip() if snip_el else ""

                        if title and href and href.startswith("http"):
                            results.append({"title": title, "url": href, "snippet": snippet})
                            if len(results) >= max_results:
                                break
                    except Exception:
                        continue

            elif engine in ("bing", "duckduckgo"):
                # Generic fallback: grab heading + nearest link
                headings = await self._page.query_selector_all("h2 a, h3 a")
                for el in headings[:max_results]:
                    try:
                        title = (await el.inner_text()).strip()
                        href  = await el.get_attribute("href") or ""
                        if title and href.startswith("http"):
                            results.append({"title": title, "url": href, "snippet": ""})
                    except Exception:
                        continue

            else:
                # For YouTube, LinkedIn, GitHub etc — just return page links
                links = await self._page.query_selector_all("a[href]")
                seen = set()
                for el in links:
                    try:
                        href  = await el.get_attribute("href") or ""
                        title = (await el.inner_text()).strip()
                        if href.startswith("http") and href not in seen and title:
                            results.append({"title": title[:80], "url": href, "snippet": ""})
                            seen.add(href)
                            if len(results) >= max_results:
                                break
                    except Exception:
                        continue

        except Exception as e:
            logger.warning("Result extraction error: {}", e)

        return results

    # ── Interaction ───────────────────────────────────────────────────────────

    async def click(self, selector_or_text: str) -> BrowserResult:
        """
        Click an element. Tries CSS selector first, then visible text match.
        """
        t0 = time.perf_counter()
        try:
            await self._ensure_ready()
            page = self._page

            # Try as CSS/XPath selector first
            try:
                await page.click(selector_or_text, timeout=3000)
                elapsed = (time.perf_counter() - t0) * 1000
                return BrowserResult.ok(url=page.url, duration_ms=elapsed)
            except Exception:
                pass

            # Fall back to text matching
            await page.get_by_text(selector_or_text, exact=False).first.click(timeout=5000)
            elapsed = (time.perf_counter() - t0) * 1000
            return BrowserResult.ok(url=page.url, duration_ms=elapsed)
        except Exception as e:
            return BrowserResult.fail(f"Click failed for '{selector_or_text}': {e}")

    async def fill(self, selector: str, value: str, press_enter: bool = False) -> BrowserResult:
        """Type a value into a form field."""
        try:
            await self._ensure_ready()
            await self._page.fill(selector, value)
            if press_enter:
                await self._page.press(selector, "Enter")
                await self._page.wait_for_load_state("domcontentloaded")
            return BrowserResult.ok(url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"Fill failed for '{selector}': {e}")

    async def fill_form(self, fields: dict[str, str], submit: bool = False) -> BrowserResult:
        """
        Fill multiple form fields intelligently.
        fields = {"Email": "me@example.com", "Password": "secret", ...}
        Tries label text, placeholder, name attr, and id matching.
        """
        try:
            await self._ensure_ready()
            filled = []
            failed = []

            for label, value in fields.items():
                success = await self._smart_fill(label, value)
                if success:
                    filled.append(label)
                else:
                    failed.append(label)

            if submit:
                try:
                    await self._page.keyboard.press("Enter")
                    await self._page.wait_for_load_state("domcontentloaded")
                except Exception:
                    pass

            result_data = {"filled": filled, "failed": failed}
            if failed:
                logger.warning("Could not fill fields: {}", failed)
            return BrowserResult.ok(output=result_data, url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"Form fill failed: {e}")

    async def _smart_fill(self, label: str, value: str) -> bool:
        """Try multiple strategies to find and fill a field."""
        page = self._page
        strategies = [
            lambda: page.get_by_label(label, exact=False).first.fill(value),
            lambda: page.get_by_placeholder(label, exact=False).first.fill(value),
            lambda: page.locator(f"[name='{label.lower()}']").first.fill(value),
            lambda: page.locator(f"[id='{label.lower()}']").first.fill(value),
            lambda: page.locator(f"input[name*='{label.lower()}']").first.fill(value),
        ]
        for strategy in strategies:
            try:
                await strategy()
                return True
            except Exception:
                continue
        return False

    async def select(self, selector: str, value: str) -> BrowserResult:
        """Choose an option in a <select> element."""
        try:
            await self._ensure_ready()
            await self._page.select_option(selector, label=value)
            return BrowserResult.ok(url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"Select failed: {e}")

    async def scroll(self, direction: str = "down", amount: int = 500) -> BrowserResult:
        """Scroll the page. direction: 'up' | 'down' | 'top' | 'bottom'."""
        try:
            await self._ensure_ready()
            if direction == "top":
                await self._page.evaluate("window.scrollTo(0, 0)")
            elif direction == "bottom":
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            elif direction == "up":
                await self._page.evaluate(f"window.scrollBy(0, -{amount})")
            else:
                await self._page.evaluate(f"window.scrollBy(0, {amount})")
            return BrowserResult.ok(url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"Scroll failed: {e}")

    async def wait_for(self, selector: str, timeout_ms: int = 10_000) -> BrowserResult:
        """Wait for an element to appear on the page."""
        try:
            await self._ensure_ready()
            await self._page.wait_for_selector(selector, timeout=timeout_ms)
            return BrowserResult.ok(url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"wait_for timed out for '{selector}': {e}")

    # ── Extraction ────────────────────────────────────────────────────────────

    async def extract_text(self, selector: Optional[str] = None) -> BrowserResult:
        """
        Extract visible text. If selector given, extracts from that element only.
        Otherwise returns the full page body text (cleaned up).
        """
        try:
            await self._ensure_ready()
            if selector:
                el = await self._page.query_selector(selector)
                if not el:
                    return BrowserResult.fail(f"Element not found: {selector}")
                text = await el.inner_text()
            else:
                text = await self._page.inner_text("body")

            # Clean excessive whitespace
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            return BrowserResult.ok(output=text, url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"Extract text failed: {e}")

    async def extract_links(self, selector: Optional[str] = None) -> BrowserResult:
        """Return all links on the page (or within a selector) as {text, url} dicts."""
        try:
            await self._ensure_ready()
            scope = selector or "body"
            els = await self._page.query_selector_all(f"{scope} a[href]")
            links = []
            for el in els:
                try:
                    href = await el.get_attribute("href") or ""
                    text = (await el.inner_text()).strip()
                    if href.startswith("http") and text:
                        links.append({"text": text[:100], "url": href})
                except Exception:
                    continue
            return BrowserResult.ok(output=links, url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"Extract links failed: {e}")

    async def get_page_info(self) -> BrowserResult:
        """Return basic page metadata: title, url, description."""
        try:
            await self._ensure_ready()
            title = await self._page.title()
            url = self._page.url
            desc = await self._page.evaluate(
                "document.querySelector('meta[name=\"description\"]')?.content || ''"
            )
            return BrowserResult.ok(
                output={"title": title, "url": url, "description": desc},
                url=url,
            )
        except Exception as e:
            return BrowserResult.fail(f"get_page_info failed: {e}")

    async def get_page_summary(self, max_chars: int = 1500) -> BrowserResult:
        """Return page title + url + trimmed body text. Good for LLM context."""
        try:
            await self._ensure_ready()
            info = await self.get_page_info()
            text_result = await self.extract_text()

            body = text_result.output or ""
            body_trimmed = body[:max_chars] + ("..." if len(body) > max_chars else "")

            summary = {
                "title":       info.output.get("title", "") if info.output else "",
                "url":         self._page.url,
                "description": info.output.get("description", "") if info.output else "",
                "body":        body_trimmed,
            }
            return BrowserResult.ok(output=summary, url=self._page.url)
        except Exception as e:
            return BrowserResult.fail(f"get_page_summary failed: {e}")

    # ── Screenshot ────────────────────────────────────────────────────────────

    async def screenshot(self, path: Optional[str] = None, full_page: bool = False) -> BrowserResult:
        """Take a screenshot. Auto-names file if path not given."""
        try:
            await self._ensure_ready()
            if not path:
                ts = int(time.time())
                path = str(self.screenshots_dir / f"screenshot_{ts}.png")
            await self._page.screenshot(path=path, full_page=full_page)
            logger.info("Screenshot saved: {}", path)
            return BrowserResult.ok(output=path, url=self._page.url, screenshots=[path])
        except Exception as e:
            return BrowserResult.fail(f"Screenshot failed: {e}")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def current_url(self) -> str:
        return self._page.url if self._page else ""
