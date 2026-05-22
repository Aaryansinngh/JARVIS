"""
tools/screen_tools.py

Stable OCR + autonomous screen tools for Jarvis
"""

from __future__ import annotations

import os
from pathlib import Path

import mss
import pytesseract
import pyautogui

from PIL import Image

from memory.shared_memory import memory

from tools.base import (
    tool,
    ToolResult,
    registry,
)

from agents.screen_agent import ScreenAgent

screen_agent = ScreenAgent()


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

    # ─────────────────────
    # Cached lookup first
    # ─────────────────────

    cached = memory.get_ui(
        query
    )

    if cached:

        x, y = cached

        pyautogui.moveTo(
            x,
            y,
            duration=0.2,
        )

        pyautogui.doubleClick()

        return ToolResult.ok(
            f'Clicked cached "{query}" '
            f'at ({x}, {y})'
        )

    # ─────────────────────
    # OCR fallback
    # ─────────────────────

    result = await _ocr_find(query)

    if not result.succeeded:

        return result

    data = result.output

    x = data["x"] + (data["width"] // 2)
    y = data["y"] + (data["height"] // 2)

    # ─────────────────────
    # Save coordinates
    # ─────────────────────

    memory.remember_ui(
        query,
        x,
        y,
    )

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
# Describe Screen Tool
# ─────────────────────────────────────────

@tool(
    name="describe_screen",
    description="Describe visible text on screen",
)
async def describe_screen():

    image_path = capture_screen()

    text = pytesseract.image_to_string(
        Image.open(image_path)
    )

    text = text.strip()

    if not text:

        return ToolResult.fail(
            "No visible text detected"
        )

    preview = text[:1500]

    return ToolResult.ok(
        preview
    )


# ─────────────────────────────────────────
# Scroll Down Tool
# ─────────────────────────────────────────

@tool(
    name="scroll_down",
    description="Scroll down",
)
async def scroll_down():

    pyautogui.scroll(-800)

    return ToolResult.ok(
        "Scrolled down"
    )


# ─────────────────────────────────────────
# Scroll Up Tool
# ─────────────────────────────────────────

@tool(
    name="scroll_up",
    description="Scroll up",
)
async def scroll_up():

    pyautogui.scroll(800)

    return ToolResult.ok(
        "Scrolled up"
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

        pyautogui.doubleClick()

        return ToolResult.ok(
            f'Clicked icon "{icon_name}"'
        )

    except Exception as e:

        return ToolResult.fail(
            f"Icon click failed: {e}"
        )


# ─────────────────────────────────────────
# Autonomous Goal Executor
# ─────────────────────────────────────────

@tool(
    name="execute_goal",
    description="Execute autonomous screen goal",
)
async def execute_goal(
    goal: str,
):

    await screen_agent.execute_goal(
        goal
    )

    return ToolResult.ok(
        f"Executed autonomous goal: {goal}"
    )


# ─────────────────────────────────────────
# Verify Text Tool
# ─────────────────────────────────────────

@tool(
    name="verify_text_visible",
    description="Verify text exists on screen",
)
async def verify_text_visible(
    query: str,
):

    # ─────────────────────
    # Cached verification
    # ─────────────────────

    cached = memory.get_ui(
        query
    )

    if cached:

        return ToolResult.ok(
            f'"{query}" cached'
        )

    # ─────────────────────
    # OCR fallback
    # ─────────────────────

    result = await _ocr_find(
        query
    )

    if result.succeeded:

        return ToolResult.ok(
            f'"{query}" visible'
        )

    return ToolResult.fail(
        f'"{query}" not visible'
    )


# ─────────────────────────────────────────
# Loader
# ─────────────────────────────────────────

def load_screen_tools():

    registry._tools["verify_text_visible"] = verify_text_visible

    registry._tools["execute_goal"] = execute_goal

    registry._tools["find_on_screen"] = find_on_screen

    registry._tools["click_on_screen"] = click_on_screen

    registry._tools["click_icon"] = click_icon

    registry._tools["describe_screen"] = describe_screen

    registry._tools["scroll_down"] = scroll_down

    registry._tools["scroll_up"] = scroll_up

    print(
        "[screen_tools] OCR tools loaded"
    )