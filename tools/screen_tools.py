"""
tools/screen_tools.py
Stable OCR screen tools for Jarvis
"""

from __future__ import annotations

from pathlib import Path

import mss
import pytesseract
from PIL import Image

from tools.base import (
    tool,
    ToolResult,
    registry,
)


# ─────────────────────────────────────────
# Screenshot helper
# ─────────────────────────────────────────

def capture_screen(
    path="data/screenshots/current.png",
):

    Path("data/screenshots").mkdir(
        parents=True,
        exist_ok=True,
    )

    with mss.mss() as sct:

        monitor = sct.monitors[1]

        screenshot = sct.grab(monitor)

        img = Image.frombytes(
            "RGB",
            screenshot.size,
            screenshot.rgb,
        )

        img.save(path)

    return path

# ─────────────────────────────────────────
# OCR Tool
# ─────────────────────────────────────────

@tool(
    name="find_on_screen",
    description="Find text on screen using OCR",
)
async def find_on_screen(
    query: str,
):

    if not query:

        return ToolResult.fail(
            "Missing query"
        )

    image_path = capture_screen()

    data = pytesseract.image_to_data(
        Image.open(image_path),
        output_type=pytesseract.Output.DICT,
    )

    words = data["text"]

    for i, word in enumerate(words):

        if query.lower() in word.lower():

            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]

            return ToolResult.ok(
                (
                    f'Found "{word}" '
                    f'at ({x}, {y}) '
                    f'size=({w}x{h})'
                )
            )

    return ToolResult.fail(
        f'"{query}" not found'
    )

# ─────────────────────────────────────────
# Loader
# ─────────────────────────────────────────

def load_screen_tools():

    registry._tools["find_on_screen"] = find_on_screen

    print(
        "[screen_tools] OCR tools loaded"
    )