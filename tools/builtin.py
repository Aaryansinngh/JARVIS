"""
tools/builtin.py — All built-in Jarvis tools
Stable updated version
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from loguru import logger

from tools.base import (
    BaseTool,
    ToolMeta,
    ToolParam,
    ToolResult,
    registry,
)


# ─────────────────────────────────────────
# Open App Tool
# ─────────────────────────────────────────

class OpenAppTool(BaseTool):

    meta = ToolMeta(
        name="open_app",
        description="Open a desktop application by name",
        params=[
            ToolParam(
                "app_name",
                "str",
                "Application name",
            )
        ],
        tags=["system", "app"],
        timeout_seconds=15.0,
    )

    APP_MAP = {

        "chrome":
            "chrome.exe",

        "google chrome":
            "chrome.exe",

        "vscode":
            os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
            ),

        "notepad":
            "notepad.exe",

        "explorer":
            "explorer.exe",

        "terminal":
            "wt.exe",

        "powershell":
            "powershell.exe",

        "cmd":
            "cmd.exe",

        "paint":
            "mspaint.exe",

        "calculator":
            "calc.exe",

        "calc":
            "calc.exe",

        "taskmgr":
            "taskmgr.exe",

        "settings":
            "ms-settings:",
    }

    async def run(
        self,
        app_name: str,
    ) -> ToolResult:

        try:

            name = app_name.lower().strip()

            target = self.APP_MAP.get(
                name,
                app_name,
            )

            target = os.path.expandvars(
                target
            )

            # Auto-detect Chrome
            if target == "chrome.exe":

                possible_paths = [

                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",

                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",

                    os.path.expandvars(
                        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
                    ),
                ]

                for path in possible_paths:

                    if os.path.exists(path):

                        target = path
                        break

            # Windows URI apps
            if (
                target.startswith("ms-")
                or target.startswith("shell:")
            ):

                subprocess.Popen(
                    ["explorer.exe", target],
                    shell=False,
                )

            else:

                subprocess.Popen(
                    [target],
                    shell=False,
                )

            return ToolResult.ok(
                f"Opened {app_name}"
            )

        except Exception as e:

            return ToolResult.fail(
                f"Could not open '{app_name}': {e}"
            )


# ─────────────────────────────────────────
# Close App Tool
# ─────────────────────────────────────────

class CloseAppTool(BaseTool):

    meta = ToolMeta(
        name="close_app",
        description="Close a running application",
        params=[
            ToolParam(
                "app_name",
                "str",
                "App name",
            )
        ],
        tags=["system", "app"],
    )

    PROCESS_MAP = {

        "chrome":
            "chrome.exe",

        "vscode":
            "Code.exe",

        "discord":
            "Discord.exe",

        "spotify":
            "Spotify.exe",

        "notepad":
            "notepad.exe",
    }

    async def run(
        self,
        app_name: str,
    ) -> ToolResult:

        process = self.PROCESS_MAP.get(
            app_name.lower(),
            f"{app_name}.exe",
        )

        try:

            subprocess.run(
                [
                    "taskkill",
                    "/F",
                    "/IM",
                    process,
                ],
                capture_output=True,
            )

            return ToolResult.ok(
                f"Closed {app_name}"
            )

        except Exception as e:

            return ToolResult.fail(
                str(e)
            )


# ─────────────────────────────────────────
# Open URL
# ─────────────────────────────────────────

class OpenURLTool(BaseTool):

    meta = ToolMeta(
        name="open_url",
        description="Open URL in browser",
        params=[
            ToolParam(
                "url",
                "str",
                "URL",
            )
        ],
        tags=["browser", "web"],
    )

    async def run(
        self,
        url: str,
    ) -> ToolResult:

        import webbrowser

        if not url.startswith(
            ("http://", "https://")
        ):

            url = "https://" + url

        webbrowser.open(url)

        return ToolResult.ok(
            f"Opened {url}"
        )


# ─────────────────────────────────────────
# Web Search
# ─────────────────────────────────────────

class WebSearchTool(BaseTool):

    meta = ToolMeta(
        name="web_search",
        description="Search Google",
        params=[
            ToolParam(
                "query",
                "str",
                "Search query",
            )
        ],
        tags=["browser", "search"],
    )

    async def run(
        self,
        query: str,
    ) -> ToolResult:

        import urllib.parse
        import webbrowser

        url = (
            "https://www.google.com/search?q="
            + urllib.parse.quote(query)
        )

        webbrowser.open(url)

        return ToolResult.ok(
            f"Searched: {query}"
        )


# ─────────────────────────────────────────
# Type Text
# ─────────────────────────────────────────

class TypeTextTool(BaseTool):

    meta = ToolMeta(
        name="type_text",
        description="Type text",
        params=[
            ToolParam(
                "text",
                "str",
                "Text",
            )
        ],
        tags=["desktop"],
    )

    async def run(
        self,
        text: str,
    ) -> ToolResult:

        try:

            import pyautogui

            pyautogui.write(
                text,
                interval=0.02,
            )

            return ToolResult.ok(
                f"Typed: {text[:40]}"
            )

        except ImportError:

            return ToolResult.fail(
                "pyautogui not installed"
            )


# ─────────────────────────────────────────
# Hotkey
# ─────────────────────────────────────────

class HotkeyTool(BaseTool):

    meta = ToolMeta(
        name="hotkey",
        description="Press keyboard shortcut",
        params=[
            ToolParam(
                "keys",
                "str",
                "Shortcut keys",
            )
        ],
        tags=["desktop"],
    )

    async def run(
        self,
        keys: str,
    ) -> ToolResult:

        try:

            import pyautogui

            key_list = [
                k.strip()
                for k in keys.split("+")
            ]

            pyautogui.hotkey(
                *key_list
            )

            return ToolResult.ok(
                f"Pressed {keys}"
            )

        except ImportError:

            return ToolResult.fail(
                "pyautogui not installed"
            )


# ─────────────────────────────────────────
# Screenshot
# ─────────────────────────────────────────

class TakeScreenshotTool(BaseTool):

    meta = ToolMeta(
        name="take_screenshot",
        description="Take screenshot",
        params=[
            ToolParam(
                "path",
                "str",
                "Save path",
                required=False,
                default="./data/screenshot.png",
            )
        ],
        tags=["vision"],
    )

    async def run(
        self,
        path: str = "./data/screenshot.png",
    ) -> ToolResult:

        try:

            from PIL import ImageGrab

            save_path = Path(path)

            save_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            img = ImageGrab.grab()

            img.save(save_path)

            return ToolResult.ok(
                str(save_path)
            )

        except ImportError:

            return ToolResult.fail(
                "Pillow not installed"
            )


# ─────────────────────────────────────────
# Wait Tool
# ─────────────────────────────────────────

class WaitTool(BaseTool):

    meta = ToolMeta(
        name="wait",
        description="Wait for seconds",
        params=[
            ToolParam(
                "seconds",
                "float",
                "Duration",
            )
        ],
        tags=["utility"],
    )

    async def run(
        self,
        seconds: float,
    ) -> ToolResult:

        import asyncio

        await asyncio.sleep(
            float(seconds)
        )

        return ToolResult.ok(
            f"Waited {seconds}s"
        )


# ─────────────────────────────────────────
# Speak Tool
# ─────────────────────────────────────────

class SpeakTool(BaseTool):

    meta = ToolMeta(
        name="speak",
        description="Speak text aloud",
        params=[
            ToolParam(
                "text",
                "str",
                "Text",
            )
        ],
        tags=["voice"],
    )

    async def run(
        self,
        text: str,
    ) -> ToolResult:

        try:

            import pyttsx3

            engine = pyttsx3.init()

            engine.say(text)

            engine.runAndWait()

            return ToolResult.ok(
                f"Spoke: {text}"
            )

        except ImportError:

            logger.info(
                f"[SPEAK] {text}"
            )

            return ToolResult.ok(
                f"(TTS unavailable) {text}"
            )


# ─────────────────────────────────────────
# Clipboard Tool
# ─────────────────────────────────────────

class CopyToClipboardTool(BaseTool):

    meta = ToolMeta(
        name="copy_to_clipboard",
        description="Copy text to clipboard",
        params=[
            ToolParam(
                "text",
                "str",
                "Text",
            )
        ],
        tags=["utility"],
    )

    async def run(
        self,
        text: str,
    ) -> ToolResult:

        try:

            import pyperclip

            pyperclip.copy(text)

            return ToolResult.ok(
                "Copied to clipboard"
            )

        except ImportError:

            return ToolResult.fail(
                "pyperclip not installed"
            )


# ─────────────────────────────────────────
# Registration
# ─────────────────────────────────────────

def load_all_tools():

    tools = [

        OpenAppTool(),

        CloseAppTool(),

        OpenURLTool(),

        WebSearchTool(),

        TypeTextTool(),

        HotkeyTool(),

        TakeScreenshotTool(),

        WaitTool(),

        SpeakTool(),

        CopyToClipboardTool(),
    ]

    registry.register_many(
        tools
    )

    logger.info(
        f"Loaded {len(tools)} built-in tools"
    )

    from tools.browser_tools import (
        load_browser_tools,
    )

    load_browser_tools()