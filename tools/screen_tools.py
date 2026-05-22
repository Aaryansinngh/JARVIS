
"""
tools/screen_tools.py
Stable OCR + click tools for Jarvis
"""

from __future__ import annotations
import os

from pathlib import Path

import mss
import pytesseract
import pyautogui

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
# Shared OCR Logic
# ─────────────────────────────────────────

async def _ocr_find(
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
                {
                    "text": word,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                }
            )

    return ToolResult.fail(
        f'"{query}" not found'
    )


# ─────────────────────────────────────────
# Find Tool
# ─────────────────────────────────────────

@tool(
    name="find_on_screen",
    description="Find text on screen using OCR",
)
async def find_on_screen(
    query: str,
):

    result = await _ocr_find(query)

    if not result.succeeded:

        return result

    data = result.output

    return ToolResult.ok(
        (
            f'Found "{data["text"]}" '
            f'at ({data["x"]}, {data["y"]}) '
            f'size=({data["width"]}x{data["height"]})'
        )
    )


# ─────────────────────────────────────────
# Click Tool
# ─────────────────────────────────────────

@tool(
    name="click_on_screen",
    description="Find text on screen and click it",
)
async def click_on_screen(
    query: str,
):

    result = await _ocr_find(query)

    if not result.succeeded:

        return result

    data = result.output

    x = data["x"] + (data["width"] // 2)
    y = data["y"] + (data["height"] // 2)

    pyautogui.moveTo(
        x,
        y,
        duration=0.2,
    )

    pyautogui.doubleClick()

    return ToolResult.ok(
        f'Clicked "{query}" at ({x}, {y})'
    )


# ─────────────────────────────────────────
# Icon Click Tool
# ─────────────────────────────────────────

@tool(
    name="click_icon",
    description="Find an app icon on screen and click it",
)
async def click_icon(
    icon_name: str,
):

    try:

        icon_path = os.path.join(
            "assets",
            "icons",
            f"{icon_name}.png",
        )

        if not os.path.exists(icon_path):

            return ToolResult.fail(
                f"Missing icon: {icon_path}"
            )

        location = pyautogui.locateOnScreen(
            icon_path,
            confidence=0.8,
        )

        if location is None:

            return ToolResult.fail(
                f'Icon "{icon_name}" not found'
            )

        center = pyautogui.center(location)
         
        target_x = center.x
        target_y = center.y + 10

        pyautogui.moveTo(
           target_x,
           target_y,
           duration=0.2,
           )

        pyautogui.click(clicks=2, interval=0.15)

        return ToolResult.ok(
            f'Clicked icon "{icon_name}"'
        )

    except Exception as e:

        return ToolResult.fail(
            f"Icon click failed: {e}"
        )



# ─────────────────────────────────────────
# Loader
# ─────────────────────────────────────────

def load_screen_tools():

    registry._tools["find_on_screen"] = find_on_screen

    registry._tools["click_on_screen"] = click_on_screen

    registry._tools["click_icon"] = click_icon

    print(
        "[screen_tools] OCR tools loaded"
    )
