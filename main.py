"""
main.py — Jarvis Desktop Assistant — Entry Point

Modes:
  1. Voice mode (default): wake word → listen → process → speak
  2. Text mode (--text): type commands in terminal (great for testing)
  3. Single command (--run "..."): run one command and exit

Usage:
  python main.py               # Voice mode with wake word
  python main.py --text        # Text mode (no mic needed)
  python main.py --run "open chrome"  # One-shot command
  python main.py --setup       # First-time setup wizard
"""

import sys
import argparse
import threading
from pathlib import Path

# ── Bootstrap paths ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.config import load_config, get
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_banner():
    """Print the startup banner."""
    console.print(
        Panel(
            Text.from_markup(
                "[bold cyan]  JARVIS[/bold cyan] [dim]— AI Desktop Assistant[/dim]\n"
                "[dim]  Voice-controlled • LLM-powered • Fully local[/dim]"
            ),
            border_style="cyan",
            padding=(1, 4),
        )
    )


def start_phase4(config: dict) -> object:
    """
    Boot Phase 4 systems: Overlay HUD + Toast Notifications.
    Returns the HUD instance (passed to Orchestrator).
    Safe to call — if deps are missing, returns None and logs a warning.
    """
    hud = None

    # ── Overlay HUD ───────────────────────────────────────────────────────────
    overlay_enabled = config.get("overlay", {}).get("enabled", True)
    if overlay_enabled:
        try:
            from ui.overlay import OverlayHUD
            hud = OverlayHUD(
                position=config.get("overlay", {}).get("position", "bottom-right"),
                opacity=float(config.get("overlay", {}).get("opacity", 0.93)),
                auto_hide_ms=int(config.get("overlay", {}).get("auto_hide_ms", 4000)),
            )
            hud.start()
            hud.wire_eventbus()
            console.print("[green]✓ Overlay HUD started[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Overlay HUD unavailable: {e}[/yellow]")
            hud = None

    # ── Toast Notifications ───────────────────────────────────────────────────
    notif_enabled = config.get("notifications", {}).get("enabled", True)
    if notif_enabled:
        try:
            from ui.notifications import wire_eventbus as wire_notifications
            wire_notifications()
            console.print("[green]✓ Notifications wired[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Notifications unavailable: {e}[/yellow]")

    return hud


def run_voice_mode(orchestrator):
    """Main loop: wake word → listen → process → speak."""
    from voice.listener import VoiceListener
    from voice.transcriber import Transcriber
    from voice.wake_word import WakeWordDetector, KeyboardTrigger

    listener    = VoiceListener()
    transcriber = Transcriber()

    _activated = threading.Event()

    def on_wake():
        console.print("\n[bold cyan]🎙️  Listening...[/bold cyan]")
        # Tell HUD we're listening
        if orchestrator.hud:
            orchestrator.hud.listening()
        _activated.set()

    porcupine_key = get("ai", "porcupine_key", "")
    if porcupine_key:
        detector = WakeWordDetector(on_detected=on_wake, access_key=porcupine_key)
    else:
        detector = KeyboardTrigger(on_detected=on_wake)

    detector.start()
    wake_word = get("assistant", "wake_word", "jarvis")
    console.print(f"\n[green]✓ Ready.[/green] Say '[bold]{wake_word}[/bold]' or press [bold]Ctrl+Space[/bold].")
    console.print("[dim]Press Ctrl+C to quit.[/dim]\n")

    try:
        while True:
            _activated.wait()
            _activated.clear()

            audio = listener.listen_once()

            if len(audio) < 1000:
                console.print("[dim]No speech detected.[/dim]")
                continue

            text = transcriber.transcribe(audio)
            if not text:
                orchestrator.speaker.speak("I didn't catch that. Try again.")
                continue

            orchestrator.process(text)

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down Jarvis...[/yellow]")
        detector.stop()
        if orchestrator.hud:
            orchestrator.hud.stop()


def run_text_mode(orchestrator):
    """Interactive text mode — type commands in the terminal."""
    console.print("\n[green]Text mode active.[/green] Type commands, or 'quit' to exit.\n")
    while True:
        try:
            text = input("[You]: ").strip()
            if text.lower() in ("quit", "exit", "bye"):
                console.print("[yellow]Goodbye![/yellow]")
                if orchestrator.hud:
                    orchestrator.hud.stop()
                break
            if text:
                response = orchestrator.process(text)
                if response:
                    console.print(f"[bold cyan]Jarvis:[/bold cyan] {response}")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            if orchestrator.hud:
                orchestrator.hud.stop()
            break


def run_setup():
    """First-time setup wizard."""
    console.print("\n[bold cyan]Jarvis Setup Wizard[/bold cyan]\n")
    console.print("1. Install dependencies:")
    console.print("   [green]pip install -r requirements.txt[/green]")
    console.print("\n2. Install Playwright browsers:")
    console.print("   [green]playwright install chromium[/green]")
    console.print("\n3. Set your OpenAI API key:")
    console.print("   [green]set OPENAI_API_KEY=sk-...[/green]  (Windows)")
    console.print("   [green]export OPENAI_API_KEY=sk-...[/green]  (Mac/Linux)")
    console.print("\n4. (Optional) Get a free Porcupine key for wake word:")
    console.print("   [green]https://console.picovoice.ai[/green]")
    console.print("\n5. (Optional) Set up Gmail API:")
    console.print("   [green]https://console.cloud.google.com → Enable Gmail API[/green]")
    console.print("\n6. Phase 4 extras:")
    console.print("   [green]pip install winotify pytesseract[/green]  (notifications + OCR)")
    console.print("\n[green]Setup complete! Run: python main.py --text[/green]")


def main():
    parser = argparse.ArgumentParser(description="Jarvis Desktop Assistant")
    parser.add_argument("--text",    action="store_true", help="Text mode (no microphone)")
    parser.add_argument("--run",     type=str,            help="Execute a single command and exit")
    parser.add_argument("--setup",   action="store_true", help="Show setup instructions")
    parser.add_argument("--debug",   action="store_true", help="Enable debug logging")
    parser.add_argument("--no-hud",  action="store_true", help="Disable overlay HUD")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    config_path = Path("config.toml")
    if not config_path.exists():
        console.print("[red]config.toml not found. Run with --setup for instructions.[/red]")
        sys.exit(1)

    load_config(str(config_path))
    setup_logger(debug=args.debug)

    Path("./data").mkdir(exist_ok=True)
    Path("./credentials").mkdir(exist_ok=True)
    Path("./data/screenshots").mkdir(exist_ok=True)

    print_banner()

    # ── Load full config for Phase 4 sections ─────────────────────────────────
    from utils.config import get_section
    full_config = {
        "ai":            get_section("ai"),
        "assistant":     get_section("assistant"),
        "overlay":       get_section("overlay"),
        "notifications": get_section("notifications"),
        "screen":        get_section("screen"),
    }

    # ── Phase 4: start HUD + notifications ────────────────────────────────────
    hud = None
    if not args.no_hud:
        hud = start_phase4(full_config)

    # ── Phase 2/3: orchestrator ────────────────────────────────────────────────
    from core.orchestrator_v2 import Orchestrator
    orchestrator = Orchestrator(config=full_config, hud=hud)

    if args.run:
        response = orchestrator.process(args.run)
        console.print(f"\n[bold green]Response:[/bold green] {response}")
        if hud:
            import time; time.sleep(4)   # let HUD show result before exit
            hud.stop()

    elif args.text:
        run_text_mode(orchestrator)

    else:
        run_voice_mode(orchestrator)


if __name__ == "__main__":
    main()
