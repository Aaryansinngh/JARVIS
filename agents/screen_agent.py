"""
agents/screen_agent.py — Jarvis Phase 4 Screen Understanding Agent

Reads what's on your screen using GPT-4o Vision (cloud) or Tesseract OCR (local).
Builds on existing screen_reader.py infrastructure.

Capabilities:
    - describe_screen()      → "What's on my screen?"
    - find_on_screen(query)  → locate text or UI element
    - summarize_page()       → summarize current browser page content
    - read_text()            → OCR all visible text
    - fill_form(fields)      → detect form fields + fill them with PyAutoGUI

Usage:
    agent = ScreenAgent(provider="gpt4o")   # or "ocr" for 100% local
    result = await agent.describe_screen()
    print(result.output)
"""

from __future__ import annotations

import asyncio
import base64
import io
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


# ── Result type (same pattern as other agents) ─────────────────────────────────

@dataclass
class ScreenResult:
    succeeded: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    screenshot_path: Optional[str] = None

    @classmethod
    def ok(cls, output, duration_ms=0.0, screenshot_path=None):
        return cls(succeeded=True, output=output, duration_ms=duration_ms,
                   screenshot_path=screenshot_path)

    @classmethod
    def fail(cls, error: str, duration_ms=0.0):
        return cls(succeeded=False, error=error, duration_ms=duration_ms)


# ── Screen Agent ───────────────────────────────────────────────────────────────

class ScreenAgent:
    """
    Screen understanding agent.

    provider: "gpt4o"   → uses OpenAI GPT-4o Vision (best quality, needs API key)
              "ocr"     → uses Tesseract OCR (100% local, no API key)
              "auto"    → tries gpt4o, falls back to ocr
    """

    SCREENSHOTS_DIR = Path("./data/screenshots")

    def __init__(
        self,
        provider: str = "auto",
        openai_api_key: str = "",
        save_screenshots: bool = False,
    ):
        self.provider = provider
        self.openai_api_key = openai_api_key or self._load_key()
        self.save_screenshots = save_screenshots
        self.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_key(self) -> str:
        try:
            from utils.config import get
            return get("ai", "openai_api_key", "")
        except Exception:
            import os
            return os.environ.get("OPENAI_API_KEY", "")

    # ── Screenshots ───────────────────────────────────────────────────────────

    def _take_screenshot(self) -> Optional["Image.Image"]:
        if not HAS_PYAUTOGUI or not HAS_PIL:
            return None
        try:
            return pyautogui.screenshot()
        except Exception as e:
            print(f"[screen_agent] Screenshot failed: {e}")
            return None

    def _screenshot_to_b64(self, img: "Image.Image") -> str:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def _save_screenshot(self, img: "Image.Image") -> Optional[str]:
        if not self.save_screenshots:
            return None
        path = self.SCREENSHOTS_DIR / f"screen_{int(time.time())}.png"
        img.save(str(path))
        return str(path)

    # ── OCR (local, no API key) ───────────────────────────────────────────────

    async def _ocr_read(self, img: "Image.Image") -> str:
        if not HAS_TESSERACT:
            return "[Tesseract not installed. pip install pytesseract + install Tesseract binary]"
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, pytesseract.image_to_string, img)
        return text.strip()

    # ── GPT-4o Vision ─────────────────────────────────────────────────────────

    async def _gpt4o_describe(self, img: "Image.Image", prompt: str) -> str:
        if not self.openai_api_key:
            return "[No OpenAI API key. Set OPENAI_API_KEY or use provider='ocr']"
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)
            b64 = self._screenshot_to_b64(img)
            response = await client.chat.completions.create(
                model="gpt-4o",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{b64}",
                                    "detail": "high",
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[GPT-4o Vision error: {e}]"

    def _pick_provider(self) -> str:
        if self.provider == "auto":
            return "gpt4o" if self.openai_api_key else "ocr"
        return self.provider

    # ── Public API ────────────────────────────────────────────────────────────

    async def describe_screen(self) -> ScreenResult:
        """
        'What's on my screen?'
        Returns a natural language description of everything visible.
        """
        t0 = time.perf_counter()
        img = self._take_screenshot()
        if not img:
            return ScreenResult.fail("Could not take screenshot")

        path = self._save_screenshot(img)
        provider = self._pick_provider()

        if provider == "gpt4o":
            prompt = (
                "Describe what is on this screen in a concise, helpful way. "
                "Mention the main application, key content visible, and any "
                "important UI elements. Be specific and useful."
            )
            text = await self._gpt4o_describe(img, prompt)
        else:
            text = await self._ocr_read(img)
            if text:
                text = f"Screen text (OCR):\n{text[:2000]}"
            else:
                text = "Screen appears empty or no readable text found."

        ms = (time.perf_counter() - t0) * 1000
        return ScreenResult.ok(text, duration_ms=ms, screenshot_path=path)

    async def read_text(self, region: Optional[tuple] = None) -> ScreenResult:
        """
        OCR everything on screen (or a region). Returns raw text.
        region: (x, y, width, height) or None for full screen.
        """
        t0 = time.perf_counter()
        img = self._take_screenshot()
        if not img:
            return ScreenResult.fail("Could not take screenshot")

        if region:
            x, y, w, h = region
            img = img.crop((x, y, x + w, y + h))

        path = self._save_screenshot(img)
        text = await self._ocr_read(img)
        ms = (time.perf_counter() - t0) * 1000
        return ScreenResult.ok(text, duration_ms=ms, screenshot_path=path)

    async def find_on_screen(self, query: str) -> ScreenResult:
        """
        'Find the Submit button' / 'Is there a login form?'
        Returns location description and whether the element was found.
        """
        t0 = time.perf_counter()
        img = self._take_screenshot()
        if not img:
            return ScreenResult.fail("Could not take screenshot")

        path = self._save_screenshot(img)
        provider = self._pick_provider()

        if provider == "gpt4o":
            prompt = (
                f"I'm looking for: '{query}'\n"
                "Tell me:\n"
                "1. Is it visible on screen? (yes/no)\n"
                "2. If yes, describe exactly where it is (e.g. 'top-right corner', 'center of screen')\n"
                "3. What it looks like\n"
                "Be brief and direct."
            )
            text = await self._gpt4o_describe(img, prompt)
        else:
            raw = await self._ocr_read(img)
            found = query.lower() in raw.lower()
            text = (
                f"Found '{query}' in screen text." if found
                else f"'{query}' not found in visible text."
            )

        ms = (time.perf_counter() - t0) * 1000
        return ScreenResult.ok(text, duration_ms=ms, screenshot_path=path)

    async def summarize_page(self) -> ScreenResult:
        """
        'Summarize this page' — understands browser content and gives a summary.
        Works best with GPT-4o Vision.
        """
        t0 = time.perf_counter()
        img = self._take_screenshot()
        if not img:
            return ScreenResult.fail("Could not take screenshot")

        path = self._save_screenshot(img)
        provider = self._pick_provider()

        if provider == "gpt4o":
            prompt = (
                "This appears to be a browser window. Summarize the main content "
                "of the page visible on screen. Include: the page title/site, "
                "the key information or article content, and any important details. "
                "Be concise (3-5 sentences)."
            )
            text = await self._gpt4o_describe(img, prompt)
        else:
            raw = await self._ocr_read(img)
            # Simple extractive summary: first 500 chars of readable text
            lines = [l.strip() for l in raw.split("\n") if len(l.strip()) > 20]
            text = " ".join(lines[:8])[:500] if lines else "Could not extract page content."

        ms = (time.perf_counter() - t0) * 1000
        return ScreenResult.ok(text, duration_ms=ms, screenshot_path=path)

    async def fill_form(self, fields: dict[str, str]) -> ScreenResult:
        """
        Detect form fields and fill them.
        fields: {"Email": "user@example.com", "Name": "John"}

        Uses GPT-4o to locate fields, then PyAutoGUI to click + type.
        """
        if not HAS_PYAUTOGUI:
            return ScreenResult.fail("PyAutoGUI not available")

        t0 = time.perf_counter()
        img = self._take_screenshot()
        if not img:
            return ScreenResult.fail("Could not take screenshot")

        provider = self._pick_provider()
        filled = []
        errors = []

        if provider == "gpt4o":
            field_list = "\n".join(f"- {k}" for k in fields.keys())
            prompt = (
                f"This screen shows a form. I need to fill these fields:\n{field_list}\n\n"
                "For each field, give me the approximate screen coordinates (x, y) "
                "as a percentage of screen width/height (e.g. x=45%, y=30%). "
                "Format: FIELD_NAME: x=XX%, y=YY%\n"
                "If a field is not visible, say FIELD_NAME: not_found"
            )
            location_text = await self._gpt4o_describe(img, prompt)

            # Parse GPT response and click+type
            sw = img.width
            sh = img.height
            for line in location_text.split("\n"):
                for field_name, value in fields.items():
                    if line.startswith(field_name):
                        if "not_found" in line:
                            errors.append(f"{field_name}: not found on screen")
                        else:
                            try:
                                import re
                                xp = float(re.search(r"x=(\d+)%", line).group(1)) / 100
                                yp = float(re.search(r"y=(\d+)%", line).group(1)) / 100
                                ax = int(xp * sw)
                                ay = int(yp * sh)
                                await asyncio.sleep(0.3)
                                pyautogui.click(ax, ay)
                                await asyncio.sleep(0.2)
                                pyautogui.hotkey("ctrl", "a")
                                pyautogui.typewrite(value, interval=0.05)
                                filled.append(field_name)
                            except Exception as e:
                                errors.append(f"{field_name}: {e}")
        else:
            return ScreenResult.fail("fill_form requires GPT-4o Vision. Set OPENAI_API_KEY.")

        ms = (time.perf_counter() - t0) * 1000
        summary = {
            "filled": filled,
            "errors": errors,
            "total": len(fields),
        }
        return ScreenResult.ok(summary, duration_ms=ms)
