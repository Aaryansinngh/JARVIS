"""
ui/overlay.py — Jarvis Phase 4 Overlay HUD

A floating, transparent Iron Man-style HUD that appears when Jarvis activates.
Shows: what it heard → what it's doing → result.
Pure event-driven — subscribes to EventBus, zero polling.

Usage:
    from ui.overlay import OverlayHUD
    hud = OverlayHUD()
    hud.start()          # starts in background thread
    hud.stop()           # clean shutdown
"""

from __future__ import annotations

import threading
import time
import asyncio
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False
    print("[overlay] customtkinter not installed — HUD disabled. pip install customtkinter")


# ── State machine ──────────────────────────────────────────────────────────────

class HUDState(Enum):
    IDLE      = "idle"
    LISTENING = "listening"
    THINKING  = "thinking"
    ACTING    = "acting"
    DONE      = "done"
    ERROR     = "error"


@dataclass
class HUDFrame:
    state:   HUDState = HUDState.IDLE
    heard:   str = ""
    action:  str = ""
    result:  str = ""
    progress: float = 0.0   # 0.0 – 1.0


# ── Colors & theme ────────────────────────────────────────────────────────────

THEME = {
    "bg":           "#050d14",
    "panel":        "#0a1a24",
    "border":       "#0e4060",
    "cyan":         "#00d4ff",
    "cyan_dim":     "#007fa3",
    "cyan_glow":    "#00aadd",
    "text":         "#c8eaf5",
    "text_dim":     "#4a7a99",
    "white":        "#e8f4f8",
    "green":        "#00ff9d",
    "red":          "#ff3860",
    "yellow":       "#ffd600",
    "listening":    "#00d4ff",
    "thinking":     "#ffd600",
    "acting":       "#00ff9d",
    "done":         "#00ff9d",
    "error":        "#ff3860",
}

STATE_LABELS = {
    HUDState.IDLE:      "STANDBY",
    HUDState.LISTENING: "LISTENING",
    HUDState.THINKING:  "PROCESSING",
    HUDState.ACTING:    "EXECUTING",
    HUDState.DONE:      "COMPLETE",
    HUDState.ERROR:     "ERROR",
}

STATE_COLORS = {
    HUDState.IDLE:      THEME["text_dim"],
    HUDState.LISTENING: THEME["listening"],
    HUDState.THINKING:  THEME["thinking"],
    HUDState.ACTING:    THEME["acting"],
    HUDState.DONE:      THEME["done"],
    HUDState.ERROR:     THEME["error"],
}


# ── Main HUD class ─────────────────────────────────────────────────────────────

class OverlayHUD:
    """
    Floating Iron Man-style HUD overlay.

    The HUD runs in its own thread and is controlled via push() and state transitions.
    It auto-hides after showing a result, and re-appears on the next activation.
    """

    def __init__(
        self,
        width: int = 420,
        auto_hide_ms: int = 4000,
        position: str = "bottom-right",   # top-left | top-right | bottom-left | bottom-right | center
        opacity: float = 0.93,
    ):
        self.width       = width
        self.auto_hide_ms = auto_hide_ms
        self.position    = position
        self.opacity     = opacity

        self._frame      = HUDFrame()
        self._lock       = threading.Lock()
        self._root: Optional[any] = None
        self._thread: Optional[threading.Thread] = None
        self._running    = False
        self._hide_timer: Optional[str] = None   # tkinter after() id

        # Pulse animation state
        self._pulse      = 0.0
        self._pulse_dir  = 1

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Start the HUD in a background daemon thread."""
        if not HAS_CTK:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_tk, daemon=True, name="jarvis-hud")
        self._thread.start()

    def stop(self):
        """Gracefully stop the HUD."""
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def listening(self):
        """Jarvis is listening — show the HUD and animate."""
        self._update(HUDState.LISTENING, heard="", action="Listening...", result="")
        self._show()

    def heard(self, text: str):
        """User said something — show what was heard."""
        self._update(HUDState.THINKING, heard=text, action="Processing...", result="")

    def acting(self, action: str):
        """Jarvis is doing something — show what action."""
        self._update(HUDState.ACTING, action=action)

    def done(self, result: str):
        """Action completed — show result, then auto-hide."""
        self._update(HUDState.DONE, result=result)
        self._schedule_hide()

    def error(self, message: str):
        """Something went wrong."""
        self._update(HUDState.ERROR, result=message)
        self._schedule_hide()

    def hide(self):
        """Immediately hide the HUD."""
        if self._root:
            self._root.after(0, self._root.withdraw)

    # ── Internal state updates ────────────────────────────────────────────────

    def _update(self, state: HUDState, heard: str = None, action: str = None, result: str = None):
        with self._lock:
            self._frame.state = state
            if heard  is not None: self._frame.heard  = heard
            if action is not None: self._frame.action = action
            if result is not None: self._frame.result = result
        if self._root:
            self._root.after(0, self._refresh_ui)

    def _show(self):
        if self._root:
            if self._hide_timer:
                try:
                    self._root.after_cancel(self._hide_timer)
                except Exception:
                    pass
                self._hide_timer = None
            self._root.after(0, self._root.deiconify)

    def _schedule_hide(self):
        if self._root:
            self._root.after(0, self._refresh_ui)
            def do_hide():
                self._hide_timer = None
                self._root.withdraw()
                with self._lock:
                    self._frame = HUDFrame()
            if self._hide_timer:
                try:
                    self._root.after_cancel(self._hide_timer)
                except Exception:
                    pass
            self._hide_timer = self._root.after(self.auto_hide_ms, do_hide)

    # ── Tkinter UI ────────────────────────────────────────────────────────────

    def _run_tk(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._root = ctk.CTk()
        self._root.withdraw()   # start hidden
        self._root.overrideredirect(True)           # no title bar
        self._root.attributes("-topmost", True)     # always on top
        self._root.attributes("-alpha", self.opacity)
        self._root.configure(fg_color=THEME["bg"])
        self._root.resizable(False, False)

        self._build_ui()
        self._place_window()
        self._animate_pulse()

        self._root.mainloop()

    def _build_ui(self):
        root = self._root
        W = self.width

        # ── Outer border frame ──
        self._outer = ctk.CTkFrame(
            root,
            width=W, height=220,
            fg_color=THEME["panel"],
            border_color=THEME["border"],
            border_width=1,
            corner_radius=6,
        )
        self._outer.pack(padx=0, pady=0)
        self._outer.pack_propagate(False)

        # ── Top bar ──
        top = ctk.CTkFrame(self._outer, fg_color=THEME["bg"], corner_radius=0, height=32)
        top.pack(fill="x", padx=1, pady=(1, 0))
        top.pack_propagate(False)

        # Logo text
        ctk.CTkLabel(
            top, text="◈  J.A.R.V.I.S",
            font=("Courier New", 11, "bold"),
            text_color=THEME["cyan"],
        ).pack(side="left", padx=12, pady=6)

        # Status pill
        self._status_label = ctk.CTkLabel(
            top, text="● STANDBY",
            font=("Courier New", 9, "bold"),
            text_color=THEME["text_dim"],
        )
        self._status_label.pack(side="right", padx=12, pady=6)

        # ── Divider ──
        ctk.CTkFrame(self._outer, height=1, fg_color=THEME["border"]).pack(fill="x", padx=1)

        # ── Body ──
        body = ctk.CTkFrame(self._outer, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # Heard row
        heard_row = ctk.CTkFrame(body, fg_color="transparent")
        heard_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            heard_row, text="INPUT",
            font=("Courier New", 8, "bold"),
            text_color=THEME["cyan_dim"], width=52, anchor="w",
        ).pack(side="left")
        self._heard_label = ctk.CTkLabel(
            heard_row, text="—",
            font=("Courier New", 11),
            text_color=THEME["text"],
            anchor="w", wraplength=W - 100,
        )
        self._heard_label.pack(side="left", fill="x", expand=True)

        # Action row
        action_row = ctk.CTkFrame(body, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            action_row, text="ACTION",
            font=("Courier New", 8, "bold"),
            text_color=THEME["cyan_dim"], width=52, anchor="w",
        ).pack(side="left")
        self._action_label = ctk.CTkLabel(
            action_row, text="—",
            font=("Courier New", 11),
            text_color=THEME["white"],
            anchor="w", wraplength=W - 100,
        )
        self._action_label.pack(side="left", fill="x", expand=True)

        # Result row
        result_row = ctk.CTkFrame(body, fg_color="transparent")
        result_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            result_row, text="RESULT",
            font=("Courier New", 8, "bold"),
            text_color=THEME["cyan_dim"], width=52, anchor="w",
        ).pack(side="left")
        self._result_label = ctk.CTkLabel(
            result_row, text="—",
            font=("Courier New", 11),
            text_color=THEME["green"],
            anchor="w", wraplength=W - 100,
        )
        self._result_label.pack(side="left", fill="x", expand=True)

        # ── Progress bar ──
        ctk.CTkFrame(self._outer, height=1, fg_color=THEME["border"]).pack(fill="x", padx=1)
        self._progress = ctk.CTkProgressBar(
            self._outer,
            height=3,
            fg_color=THEME["bg"],
            progress_color=THEME["cyan"],
            corner_radius=0,
        )
        self._progress.pack(fill="x", padx=1, pady=(0, 1))
        self._progress.set(0)

    def _refresh_ui(self):
        with self._lock:
            f = HUDFrame(
                state=self._frame.state,
                heard=self._frame.heard,
                action=self._frame.action,
                result=self._frame.result,
            )

        color = STATE_COLORS[f.state]
        label = STATE_LABELS[f.state]

        self._status_label.configure(text=f"● {label}", text_color=color)
        self._heard_label.configure(text=f.heard or "—")
        self._action_label.configure(text=f.action or "—")

        result_color = THEME["red"] if f.state == HUDState.ERROR else THEME["green"]
        self._result_label.configure(text=f.result or "—", text_color=result_color)

        # Progress bar
        if f.state in (HUDState.LISTENING, HUDState.THINKING, HUDState.ACTING):
            self._progress.configure(progress_color=color)
        elif f.state == HUDState.DONE:
            self._progress.set(1.0)
        elif f.state == HUDState.ERROR:
            self._progress.configure(progress_color=THEME["red"])
            self._progress.set(1.0)

    def _animate_pulse(self):
        """Animate the progress bar pulsing during active states."""
        with self._lock:
            state = self._frame.state

        if state in (HUDState.LISTENING, HUDState.THINKING, HUDState.ACTING):
            self._pulse += 0.04 * self._pulse_dir
            if self._pulse >= 1.0:
                self._pulse = 1.0
                self._pulse_dir = -1
            elif self._pulse <= 0.0:
                self._pulse = 0.0
                self._pulse_dir = 1
            self._progress.set(self._pulse)

        if self._running:
            self._root.after(40, self._animate_pulse)

    def _place_window(self):
        self._root.update_idletasks()
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        w, h = self.width, 220
        pad = 20

        positions = {
            "top-left":     (pad, pad),
            "top-right":    (sw - w - pad, pad),
            "bottom-left":  (pad, sh - h - pad - 48),
            "bottom-right": (sw - w - pad, sh - h - pad - 48),
            "center":       ((sw - w) // 2, (sh - h) // 2),
        }
        x, y = positions.get(self.position, positions["bottom-right"])
        self._root.geometry(f"{w}x{h}+{x}+{y}")

    # ── EventBus integration ──────────────────────────────────────────────────

    def wire_eventbus(self):
        """
        Subscribe to the Jarvis EventBus so the HUD updates automatically.
        Call this after start().
        """
        try:
            from events.bus import bus, Events

            @bus.on(Events.WAKE_WORD_DETECTED)
            async def on_wake(event):
                self.listening()

            @bus.on(Events.SPEECH_RECOGNIZED)
            async def on_speech(event):
                self.heard(event.data.get("text", ""))

            @bus.on(Events.TOOL_EXECUTING)
            async def on_executing(event):
                self.acting(event.data.get("tool", "working..."))

            @bus.on(Events.TOOL_EXECUTED)
            async def on_executed(event):
                result = event.data.get("result", "Done")
                if event.data.get("succeeded", True):
                    self.done(str(result)[:80])
                else:
                    self.error(str(event.data.get("error", "Unknown error"))[:80])

            @bus.on(Events.WORKFLOW_COMPLETED)
            async def on_workflow(event):
                name = event.data.get("workflow", "workflow")
                self.done(f"{name} complete")

        except ImportError:
            print("[overlay] EventBus not available — wire manually")


# ── Singleton accessor ─────────────────────────────────────────────────────────

_hud: Optional[OverlayHUD] = None

def get_hud() -> OverlayHUD:
    global _hud
    if _hud is None:
        _hud = OverlayHUD()
    return _hud
