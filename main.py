
"""
main.py — Jarvis Desktop Assistant — Entry Point
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

    hud = None

    overlay_enabled = config.get("overlay", {}).get("enabled", True)

    if overlay_enabled:

        try:

            from ui.overlay import OverlayHUD

            hud = OverlayHUD(
                position=config.get("overlay", {}).get(
                    "position",
                    "bottom-right",
                ),
                opacity=float(
                    config.get("overlay", {}).get(
                        "opacity",
                        0.93,
                    )
                ),
                auto_hide_ms=int(
                    config.get("overlay", {}).get(
                        "auto_hide_ms",
                        4000,
                    )
                ),
            )

            hud.start()

            hud.wire_eventbus()

            console.print(
                "[green]✓ Overlay HUD started[/green]"
            )

        except Exception as e:

            console.print(
                f"[yellow]⚠ Overlay HUD unavailable: {e}[/yellow]"
            )

            hud = None

    notif_enabled = config.get(
        "notifications",
        {},
    ).get("enabled", True)

    if notif_enabled:

        try:

            from ui.notifications import (
                wire_eventbus as wire_notifications,
            )

            wire_notifications()

            console.print(
                "[green]✓ Notifications wired[/green]"
            )

        except Exception as e:

            console.print(
                f"[yellow]⚠ Notifications unavailable: {e}[/yellow]"
            )

    return hud


def run_voice_mode(orchestrator):

    from voice.listener import VoiceListener
    from voice.transcriber import Transcriber
    from voice.speaker import Speaker
    from voice.wake_word import (
        WakeWordDetector,
        KeyboardTrigger,
    )

    listener   = VoiceListener()
    transcriber = Transcriber()
    speaker    = Speaker()

    _activated = threading.Event()
    _wake_lock = threading.Lock()

    def on_wake():
        if not _wake_lock.acquire(blocking=False):
            return  # already processing, ignore extra triggers

        console.print(
            "\n[bold cyan]🎙️  Listening...[/bold cyan]"
        )

        if orchestrator.hud:
            orchestrator.hud.listening()

        _activated.set()

    porcupine_key = get(
        "ai",
        "porcupine_key",
        "",
    )

    if porcupine_key:

        detector = WakeWordDetector(
            on_detected=on_wake,
            access_key=porcupine_key,
        )

    else:

        detector = KeyboardTrigger(
            on_detected=on_wake
        )

    detector.start()

    wake_word = get(
        "assistant",
        "wake_word",
        "jarvis",
    )

    console.print(
        f"\n[green]✓ Ready.[/green] "
        f"Say '[bold]{wake_word}[/bold]' "
        f"or press [bold]Ctrl+Space[/bold]."
    )

    console.print(
        "[dim]Press Ctrl+C to quit.[/dim]\n"
    )

    try:

        while True:

            _activated.wait()

            _activated.clear()

            audio = listener.listen_once()

            if len(audio) < 1000:

                console.print(
                    "[dim]No speech detected.[/dim]"
                )

                _wake_lock.release()
                continue

            text = transcriber.transcribe(audio)

            if not text:

                speaker.speak(
                    "I didn't catch that. Try again."
                )

                _wake_lock.release()
                continue

            console.print(f"[bold yellow]You said:[/bold yellow] {text}")

            response = orchestrator.process(text)

            if response:
                console.print(f"[bold cyan]Jarvis:[/bold cyan] {response}")
                speaker.speak(response)

            _wake_lock.release()

    except KeyboardInterrupt:

        console.print(
            "\n[yellow]Shutting down Jarvis...[/yellow]"
        )

        detector.stop()

        if orchestrator.hud:
            orchestrator.hud.stop()


def run_text_mode(orchestrator):

    console.print(
        "\n[green]Text mode active.[/green] "
        "Type commands, or 'quit' to exit.\n"
    )

    while True:

        try:

            text = input("[You]: ").strip()

            if text.lower() in (
                "quit",
                "exit",
                "bye",
            ):

                console.print(
                    "[yellow]Goodbye![/yellow]"
                )

                if orchestrator.hud:
                    orchestrator.hud.stop()

                break

            if text:

                response = orchestrator.process(text)

                if response:

                    console.print(
                        f"[bold cyan]Jarvis:[/bold cyan] {response}"
                    )

        except (KeyboardInterrupt, EOFError):

            console.print(
                "\n[yellow]Goodbye![/yellow]"
            )

            if orchestrator.hud:
                orchestrator.hud.stop()

            break


def run_setup():

    console.print(
        "\n[bold cyan]Jarvis Setup Wizard[/bold cyan]\n"
    )

    console.print(
        "1. Install dependencies:"
    )

    console.print(
        "   [green]pip install -r requirements.txt[/green]"
    )

    console.print(
        "\n2. Install Playwright browsers:"
    )

    console.print(
        "   [green]playwright install chromium[/green]"
    )

    console.print(
        "\n3. Set your OpenAI API key:"
    )

    console.print(
        "   [green]set OPENAI_API_KEY=sk-...[/green]"
    )

    console.print(
        "\n[green]Setup complete! "
        "Run: python main.py --text[/green]"
    )


def main():

    parser = argparse.ArgumentParser(
        description="Jarvis Desktop Assistant"
    )

    parser.add_argument(
        "--text",
        action="store_true",
        help="Text mode",
    )

    parser.add_argument(
        "--run",
        type=str,
        help="Execute one command",
    )

    parser.add_argument(
        "--setup",
        action="store_true",
        help="Show setup instructions",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--no-hud",
        action="store_true",
        help="Disable overlay HUD",
    )

    args = parser.parse_args()

    if args.setup:

        run_setup()

        return

    config_path = Path("config.toml")

    if not config_path.exists():

        console.print(
            "[red]config.toml not found.[/red]"
        )

        sys.exit(1)

    load_config(str(config_path))

    setup_logger(debug=args.debug)

    Path("./data").mkdir(exist_ok=True)

    Path("./credentials").mkdir(exist_ok=True)

    Path("./data/screenshots").mkdir(
        exist_ok=True
    )

    print_banner()

    from utils.config import get_section

    full_config = {
        "ai": get_section("ai"),
        "assistant": get_section("assistant"),
        "overlay": get_section("overlay"),
        "notifications": get_section("notifications"),
        "screen": get_section("screen"),
    }

    hud = None

    if not args.no_hud:

        hud = start_phase4(full_config)

    from core.orchestrator_v2 import (
        Orchestrator,
    )

    orchestrator = Orchestrator(
        config=full_config,
        hud=hud,
    )

    if args.run:

        response = orchestrator.process(
            args.run
        )

        console.print(
            f"\n[bold green]Response:[/bold green] {response}"
        )

        if hud:

            import time

            time.sleep(4)

            hud.stop()

    elif args.text:

        threading.Thread(
            target=run_text_mode,
            args=(orchestrator,),
            daemon=True,
        ).start()

        if hud:
            hud.root.mainloop()

    else:

        threading.Thread(
            target=run_voice_mode,
            args=(orchestrator,),
            daemon=True,
        ).start()

        if hud:
            hud.root.mainloop()


if __name__ == "__main__":
    main()