"""
ui/tray.py — System Tray Icon for Jarvis

Adds a Jarvis icon to the Windows system tray.
Right-click menu: Activate | Settings | History | Quit
"""
import threading
import sys
from PIL import Image, ImageDraw
from utils.logger import logger


def create_icon_image(size: int = 64, color: str = "#00d4ff") -> Image.Image:
    """Create a simple circle icon for the system tray."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color, outline="#ffffff")
    # Draw "J" letter
    draw.text((size // 2 - 6, size // 2 - 10), "J", fill="white")
    return img


class TrayApp:
    """System tray application for Jarvis."""

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self._icon = None

    def start(self):
        """Start the system tray icon in a background thread."""
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            import pystray

            menu = pystray.Menu(
                pystray.MenuItem("🎙️ Activate Jarvis", self._activate),
                pystray.MenuItem("📋 Recent Commands", self._show_history),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("⚙️ Settings", self._open_settings),
                pystray.MenuItem("❌ Quit", self._quit),
            )

            icon_image = create_icon_image()
            self._icon = pystray.Icon(
                name="Jarvis",
                icon=icon_image,
                title="Jarvis — AI Desktop Assistant",
                menu=menu,
            )
            self._icon.run()

        except ImportError:
            logger.warning("pystray not installed. System tray disabled.")
        except Exception as e:
            logger.error(f"Tray error: {e}")

    def _activate(self, icon, item):
        """Manually trigger Jarvis activation."""
        logger.info("Tray: Manual activation triggered.")

    def _show_history(self, icon, item):
        """Show recent command history."""
        if self.orchestrator:
            recent = self.orchestrator.episodes.recent(5)
            for r in recent:
                print(f"  [{r['timestamp'][:16]}] {r['user_text']}")

    def _open_settings(self, icon, item):
        """Open config.toml in the default editor."""
        import subprocess, os
        subprocess.Popen(["notepad.exe", "config.toml"], shell=True)

    def _quit(self, icon, item):
        """Quit Jarvis."""
        logger.info("Quit from tray.")
        icon.stop()
        sys.exit(0)

    def stop(self):
        if self._icon:
            self._icon.stop()
