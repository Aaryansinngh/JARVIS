
"""
tools/builtin.py — All built-in Jarvis tools

Drop-in replacement for the scattered automation modules.
Each tool is self-contained, testable, and registered automatically.

Import this module to load all tools into the global registry:
    from tools.builtin import load_all_tools
    load_all_tools()
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from tools.base import BaseTool, ToolMeta, ToolParam, ToolResult, ToolStatus, registry


# ─── App Launcher ─────────────────────────────────────────────────────────────

class OpenAppTool(BaseTool):
    meta = ToolMeta(
        name="open_app",
        description="Open a desktop application by name",
        params=[ToolParam("app_name", "str", "Name of the app to open (chrome, vscode, notepad, etc.)")],
        tags=["system", "app"],
        timeout_seconds=15.0,
    )

    APP_MAP: dict[str, str] = {
        "chrome":    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "vscode":    r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
        "notepad":   "notepad.exe",
        "explorer":  "explorer.exe",
        "terminal":  "wt.exe",
        "spotify":   "shell:AppsFolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify",
        "discord":   r"%LOCALAPPDATA%\Discord\Update.exe",
        "vlc":       r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        "excel":     r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
        "word":      r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
        "paint":     "mspaint.exe",
        "calc":      "calc.exe",
        "taskmgr":   "taskmgr.exe",
        "settings":  "ms-settings:",
    }

    async def run(self, app_name: str) -> ToolResult:
        name = app_name.lower().strip()
        path = self.APP_MAP.get(name, name)
        path = os.path.expandvars(path)

        try:
            if path.startswith("shell:") or path.startswith("ms-"):
                subprocess.Popen(["explorer.exe", path], shell=False)
            else:
                subprocess.Popen([path], shell=True)
            return ToolResult.ok(f"Opened {app_name}")
        except Exception as e:
            return ToolResult.fail(f"Could not open '{app_name}': {e}")


class CloseAppTool(BaseTool):
    meta = ToolMeta(
        name="close_app",
        description="Close a running application by process name",
        params=[ToolParam("app_name", "str", "App to close")],
        tags=["system", "app"],
    )

    PROCESS_MAP = {
        "chrome": "chrome.exe",
        "vscode": "Code.exe",
        "discord": "Discord.exe",
        "spotify": "Spotify.exe",
        "notepad": "notepad.exe",
    }

    async def run(self, app_name: str) -> ToolResult:
        process = self.PROCESS_MAP.get(app_name.lower(), f"{app_name}.exe")
        try:
            subprocess.run(["taskkill", "/F", "/IM", process], capture_output=True)
            return ToolResult.ok(f"Closed {app_name}")
        except Exception as e:
            return ToolResult.fail(str(e))


# ─── Browser ──────────────────────────────────────────────────────────────────

class OpenURLTool(BaseTool):
    meta = ToolMeta(
        name="open_url",
        description="Open a URL in the default browser",
        params=[ToolParam("url", "str", "Full URL to open")],
        tags=["browser", "web"],
    )

    async def run(self, url: str) -> ToolResult:
        import webbrowser
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        return ToolResult.ok(f"Opened {url}")


class WebSearchTool(BaseTool):
    meta = ToolMeta(
        name="web_search",
        description="Search the web using Google",
        params=[ToolParam("query", "str", "Search query")],
        tags=["browser", "web", "search"],
    )

    async def run(self, query: str) -> ToolResult:
        import urllib.parse
        import webbrowser
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        return ToolResult.ok(f"Searched: {query}")


# ─── Desktop Automation ───────────────────────────────────────────────────────

class TypeTextTool(BaseTool):
    meta = ToolMeta(
        name="type_text",
        description="Type text at the current cursor position",
        params=[ToolParam("text", "str", "Text to type")],
        tags=["desktop", "keyboard"],
    )

    async def run(self, text: str) -> ToolResult:
        try:
            import pyautogui
            pyautogui.write(text, interval=0.02)
            return ToolResult.ok(f"Typed: {text[:40]}")
        except ImportError:
            return ToolResult.fail("pyautogui not installed")


class HotkeyTool(BaseTool):
    meta = ToolMeta(
        name="hotkey",
        description="Press a keyboard shortcut",
        params=[ToolParam("keys", "str", "Keys to press, e.g. 'ctrl+c' or 'win+d'")],
        tags=["desktop", "keyboard"],
    )

    async def run(self, keys: str) -> ToolResult:
        try:
            import pyautogui
            key_list = [k.strip() for k in keys.split("+")]
            pyautogui.hotkey(*key_list)
            return ToolResult.ok(f"Pressed {keys}")
        except ImportError:
            return ToolResult.fail("pyautogui not installed")


class TakeScreenshotTool(BaseTool):
    meta = ToolMeta(
        name="take_screenshot",
        description="Take a screenshot and save it",
        params=[ToolParam("path", "str", "Save path", required=False, default="./data/screenshot.png")],
        tags=["desktop", "vision"],
    )

    async def run(self, path: str = "./data/screenshot.png") -> ToolResult:
        try:
            from PIL import ImageGrab
            save_path = Path(path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            img = ImageGrab.grab()
            img.save(save_path)
            return ToolResult.ok(str(save_path))
        except ImportError:
            return ToolResult.fail("Pillow not installed")


# ─── Wait ─────────────────────────────────────────────────────────────────────

class WaitTool(BaseTool):
    meta = ToolMeta(
        name="wait",
        description="Wait for a number of seconds",
        params=[ToolParam("seconds", "float", "How long to wait")],
        tags=["utility"],
    )

    async def run(self, seconds: float) -> ToolResult:
        import asyncio
        await asyncio.sleep(float(seconds))
        return ToolResult.ok(f"Waited {seconds}s")


# ─── Speak ────────────────────────────────────────────────────────────────────

class SpeakTool(BaseTool):
    meta = ToolMeta(
        name="speak",
        description="Speak text aloud using TTS",
        params=[ToolParam("text", "str", "Text to speak")],
        tags=["voice", "output"],
    )

    async def run(self, text: str) -> ToolResult:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return ToolResult.ok(f"Spoke: {text}")
        except ImportError:
            logger.info(f"[SPEAK] {text}")
            return ToolResult.ok(f"(TTS unavailable) {text}")


# ─── Clipboard ────────────────────────────────────────────────────────────────

class CopyToClipboardTool(BaseTool):
    meta = ToolMeta(
        name="copy_to_clipboard",
        description="Copy text to clipboard",
        params=[ToolParam("text", "str", "Text to copy")],
        tags=["desktop", "utility"],
    )

    async def run(self, text: str) -> ToolResult:
        try:
            import pyperclip
            pyperclip.copy(text)
            return ToolResult.ok("Copied to clipboard")
        except ImportError:
            return ToolResult.fail("pyperclip not installed")


# ─── Registration ─────────────────────────────────────────────────────────────

def load_all_tools() -> None:
    """Register every built-in tool into the global registry."""

    tools: list[BaseTool] = [
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

    registry.register_many(tools)
    logger.info(f"Loaded {len(tools)} built-in tools")

    # Load browser tools
    from tools.browser_tools import load_browser_tools
    load_browser_tools()

    # Screen tools temporarily disabled
    # Old API incompatible with BaseTool architecture
    # from tools.screen_tools import load_screen_tools
    # load_screen_tools()

