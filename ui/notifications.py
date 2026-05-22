"""
ui/notifications.py — Jarvis Phase 4 Windows Toast Notifications

Background notifications for completed workflows and events.
Uses winotify for native Windows toasts.

Examples:
    notify("Downloads organized", "47 files moved to folders")
    notify_workflow_done("internship_hunt", "3 job boards are open")
    notify_error("Gmail failed", "Check your credentials")

Auto-wires to EventBus when wire_eventbus() is called.
"""

from __future__ import annotations

import platform
import threading
from typing import Optional
from pathlib import Path


IS_WINDOWS = platform.system() == "Windows"

# Icon paths (fallback to None if missing)
_ICON_DIR  = Path(__file__).parent.parent / "assets"
_ICON_INFO = str(_ICON_DIR / "jarvis_info.ico")  if (_ICON_DIR / "jarvis_info.ico").exists()  else ""
_ICON_WARN = str(_ICON_DIR / "jarvis_warn.ico")  if (_ICON_DIR / "jarvis_warn.ico").exists()  else ""
_ICON_ERR  = str(_ICON_DIR / "jarvis_error.ico") if (_ICON_DIR / "jarvis_error.ico").exists() else ""


# ── Low-level toast ────────────────────────────────────────────────────────────

def _send_toast(title: str, message: str, icon_path: str = "", duration: str = "short"):
    """
    Fire a native Windows toast notification (non-blocking, runs in thread).
    duration: "short" (7s) | "long" (25s)
    """
    if not IS_WINDOWS:
        # Graceful fallback for dev on Mac/Linux
        print(f"[NOTIFY] {title}: {message}")
        return

    def _fire():
        try:
            from winotify import Notification, audio
            toast = Notification(
                app_id="Jarvis Assistant",
                title=title,
                msg=message,
                duration=duration,
                icon=icon_path,
            )
            toast.set_audio(audio.Default, loop=False)
            toast.show()
        except ImportError:
            # winotify not installed — silent fallback
            print(f"[NOTIFY] {title}: {message}")
            print("  → pip install winotify for native Windows toasts")
        except Exception as e:
            print(f"[NOTIFY] Toast failed: {e}")

    threading.Thread(target=_fire, daemon=True).start()


# ── Public API ─────────────────────────────────────────────────────────────────

def notify(title: str, message: str = "", duration: str = "short"):
    """Generic info notification."""
    _send_toast(f"◈ {title}", message, icon_path=_ICON_INFO, duration=duration)


def notify_done(title: str, message: str = ""):
    """Success notification (green checkmark feel)."""
    _send_toast(f"✓ {title}", message, icon_path=_ICON_INFO)


def notify_error(title: str, message: str = ""):
    """Error notification."""
    _send_toast(f"✗ {title}", message, icon_path=_ICON_ERR)


def notify_workflow_done(workflow_name: str, detail: str = ""):
    """Notify that a workflow completed — with friendly message."""
    friendly = {
        "morning_routine":    "Mail, calendar and news are ready.",
        "internship_hunt":    "Internship boards are open. Good luck.",
        "coding_mode":        "VS Code, terminal and Chrome are set up.",
        "study_mode":         "Notion and lofi music ready. Focus up.",
        "focus_mode":         "Distractions closed. Time to work.",
        "entertainment_mode": "Spotify and YouTube ready.",
        "internship_search":  "Job boards open. Time to apply.",
        "linkedin_jobs":      "LinkedIn Jobs is ready.",
        "google_search":      "Search results are in.",
    }
    msg = detail or friendly.get(workflow_name, f"{workflow_name} completed.")
    _send_toast(f"◈ {workflow_name.replace('_', ' ').title()}", msg, icon_path=_ICON_INFO)


def notify_file_organized(moved: int, skipped: int, folder: str = "Downloads"):
    """Specific notification for file organization."""
    msg = f"{moved} files organized"
    if skipped:
        msg += f", {skipped} skipped"
    _send_toast(f"◈ {folder} Organized", msg, icon_path=_ICON_INFO)


# ── EventBus integration ───────────────────────────────────────────────────────

def wire_eventbus():
    """
    Subscribe to the Jarvis EventBus so notifications fire automatically.
    Call once at startup after EventBus is available.
    """
    try:
        from events.bus import bus, Events

        @bus.on(Events.WORKFLOW_COMPLETED)
        async def on_workflow(event):
            name   = event.data.get("workflow", "")
            detail = event.data.get("result", "")
            notify_workflow_done(name, str(detail)[:100] if detail else "")

        @bus.on(Events.TOOL_EXECUTED)
        async def on_tool(event):
            if not event.data.get("succeeded", True):
                tool  = event.data.get("tool", "action")
                error = event.data.get("error", "Unknown error")
                notify_error(f"{tool} failed", str(error)[:100])

        @bus.on("file_agent.organized")
        async def on_organized(event):
            moved   = event.data.get("moved", 0)
            skipped = event.data.get("skipped", 0)
            folder  = event.data.get("folder", "Downloads")
            notify_file_organized(moved, skipped, folder)

        print("[notifications] EventBus wired ✓")

    except ImportError:
        print("[notifications] EventBus not available — notifications will fire manually only")


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Firing test notifications...")
    notify("Jarvis Ready", "Phase 4 notifications are working.")
    import time; time.sleep(1)
    notify_done("Workflow Complete", "Morning routine finished in 4.2s")
    time.sleep(1)
    notify_error("Gmail Failed", "Check your API credentials in config.toml")
