"""
automation/desktop.py — Desktop GUI automation

Controls:
- Mouse movement and clicks
- Keyboard typing and shortcuts
- Window management (focus, resize, move)
- Clipboard operations
- Screenshots
"""
import time
import subprocess
import pyperclip
from PIL import ImageGrab
from pathlib import Path
from utils.logger import logger


class DesktopController:
    """Control the desktop: type, click, hotkeys, windows."""

    def __init__(self):
        import pyautogui
        pyautogui.FAILSAFE = True   # Move mouse to top-left to abort
        pyautogui.PAUSE = 0.05      # Small delay between actions
        self.gui = pyautogui

    # ─── Keyboard ─────────────────────────────────────────────────────────────

    def type_text(self, text: str, interval: float = 0.02):
        """Type text at the current cursor position."""
        logger.debug(f"Typing: '{text[:40]}...'")
        self.gui.typewrite(text, interval=interval)

    def press_key(self, *keys: str):
        """
        Press a key or key combination.
        Examples:
            press_key("enter")
            press_key("ctrl", "c")     # Copy
            press_key("ctrl", "v")     # Paste
            press_key("alt", "tab")    # Switch windows
            press_key("win", "d")      # Show desktop
        """
        logger.debug(f"Pressing: {keys}")
        if len(keys) == 1:
            self.gui.press(keys[0])
        else:
            self.gui.hotkey(*keys)

    def copy_text(self) -> str:
        """Copy selected text and return it."""
        self.gui.hotkey("ctrl", "c")
        time.sleep(0.3)
        return pyperclip.paste()

    def paste_text(self, text: str):
        """Set clipboard and paste."""
        pyperclip.copy(text)
        self.gui.hotkey("ctrl", "v")

    # ─── Mouse ────────────────────────────────────────────────────────────────

    def click(self, x: int = None, y: int = None, button: str = "left"):
        """Click at coordinates, or at current position if no coords given."""
        if x and y:
            self.gui.click(x, y, button=button)
        else:
            self.gui.click(button=button)

    def double_click(self, x: int = None, y: int = None):
        if x and y:
            self.gui.doubleClick(x, y)
        else:
            self.gui.doubleClick()

    def right_click(self, x: int, y: int):
        self.gui.rightClick(x, y)

    def scroll(self, clicks: int = 3, direction: str = "down"):
        """Scroll the mouse wheel. direction='up' or 'down'."""
        amount = clicks if direction == "up" else -clicks
        self.gui.scroll(amount)

    def move_to(self, x: int, y: int, duration: float = 0.3):
        self.gui.moveTo(x, y, duration=duration)

    # ─── Screen ───────────────────────────────────────────────────────────────

    def screenshot(self, save_path: str = None) -> str:
        """
        Take a screenshot.
        Returns the file path.
        """
        path = save_path or "./data/screenshot.png"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img = ImageGrab.grab()
        img.save(path)
        logger.info(f"Screenshot saved: {path}")
        return path

    def find_on_screen(self, image_path: str, confidence: float = 0.9):
        """
        Find an image on screen and return its location.
        Returns (x, y) tuple or None.
        """
        try:
            loc = self.gui.locateCenterOnScreen(image_path, confidence=confidence)
            return loc
        except Exception:
            return None

    def click_image(self, image_path: str) -> bool:
        """Find image on screen and click it."""
        loc = self.find_on_screen(image_path)
        if loc:
            self.gui.click(loc)
            return True
        logger.warning(f"Image not found on screen: {image_path}")
        return False

    # ─── Windows ──────────────────────────────────────────────────────────────

    def switch_window(self):
        """Alt+Tab to switch to the previous window."""
        self.gui.hotkey("alt", "tab")

    def minimize_all(self):
        """Win+D to show the desktop."""
        self.gui.hotkey("win", "d")

    def lock_screen(self):
        """Win+L to lock the screen."""
        self.gui.hotkey("win", "l")

    def open_run_dialog(self, command: str):
        """Win+R then type a command."""
        self.gui.hotkey("win", "r")
        time.sleep(0.5)
        self.type_text(command)
        self.press_key("enter")

    # ─── Window Control via pywinauto ─────────────────────────────────────────

    def focus_window_by_title(self, title: str) -> bool:
        """Bring a window to focus by its title."""
        try:
            from pywinauto import Desktop
            desk = Desktop(backend="uia")
            win = desk.window(title_re=f".*{title}.*")
            win.set_focus()
            logger.info(f"Focused window: '{title}'")
            return True
        except Exception as e:
            logger.error(f"Failed to focus '{title}': {e}")
            return False
