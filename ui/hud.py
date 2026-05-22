import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
import customtkinter as ctk
from queue import Queue
import threading
import asyncio

from events.bus import bus, Events


class JarvisHUD:

    def __init__(self):

        self.queue = Queue()

        ctk.set_appearance_mode("dark")

        self.root = ctk.CTk()

        self.root.title("Jarvis HUD")

        self.root.geometry("520x160+1180+40")

        self.root.attributes("-topmost", True)

        self.root.overrideredirect(True)

        self.root.attributes("-alpha", 0.93)

        self.root.configure(fg_color="#0f172a")

        self.frame = ctk.CTkFrame(
            self.root,
            corner_radius=20,
            fg_color="#111827",
        )

        self.frame.pack(
            fill="both",
            expand=True,
            padx=6,
            pady=6,
        )

        self.title = ctk.CTkLabel(
            self.frame,
            text="JARVIS",
            font=("Segoe UI", 28, "bold"),
            text_color="#38bdf8",
        )

        self.title.pack(pady=(14, 4))

        self.status = ctk.CTkLabel(
            self.frame,
            text="Idle",
            font=("Segoe UI", 18),
            wraplength=460,
        )

        self.status.pack(pady=(8, 16))

        self.root.after(100, self.process_queue)

        self.setup_event_handlers()

    # ─────────────────────────────────────────

    def set_status(self, text):

        self.queue.put(text)

    # ─────────────────────────────────────────

    def process_queue(self):

        while not self.queue.empty():

            text = self.queue.get()

            self.status.configure(text=text)

        self.root.after(100, self.process_queue)

    # ─────────────────────────────────────────

    def setup_event_handlers(self):

        @bus.on(Events.COMMAND_RECEIVED)
        async def on_command(event):

            text = event.data.get("text", "")

            self.set_status(f"🎤 {text}")

        @bus.on(Events.TOOL_EXECUTING)
        async def on_tool(event):

            tool = event.data.get("tool", "")

            self.set_status(f"⚡ Running: {tool}")

        @bus.on(Events.TOOL_EXECUTED)
        async def on_done(event):

            tool = event.data.get("tool", "")

            success = event.data.get("success", False)

            if success:
                self.set_status(f"✅ Finished: {tool}")
            else:
                self.set_status(f"❌ Failed: {tool}")

    # ─────────────────────────────────────────

    def run(self):

        self.root.mainloop()


hud = JarvisHUD()

hud.run()