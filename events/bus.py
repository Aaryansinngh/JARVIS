"""
events/bus.py — Jarvis Event Bus

Decouples components. Instead of:
    orchestrator.speaker.speak(text)      ← tight coupling

Use:
    bus.emit("speak", text=text)          ← anyone can listen

This is the foundation of Phase 3+ where background monitors,
UI overlays, and plugins need to react to Jarvis events.

Usage:
    from events.bus import bus

    # Subscribe
    @bus.on("workflow.completed")
    async def on_workflow_done(event):
        print(event.data)

    # Emit
    await bus.emit("workflow.completed", data={"name": "coding_mode"})
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine


@dataclass
class Event:
    name: str
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""


Handler = Callable[[Event], Coroutine]


class EventBus:
    """
    Simple async pub/sub event bus.

    Handlers are async functions. Errors in handlers are logged, not raised.
    """

    def __init__(self):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._history: list[Event] = []
        self._max_history = 100

    def on(self, event_name: str):
        """Decorator to subscribe to an event."""
        def decorator(fn: Handler) -> Handler:
            self._handlers[event_name].append(fn)
            return fn
        return decorator

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: Handler) -> None:
        if handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)

    async def emit(self, event_name: str, data: Any = None, source: str = "") -> None:
        event = Event(name=event_name, data=data, source=source)

        self._history.append(event)

        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        handlers = self._handlers.get(event_name, [])

        if not handlers:
            return

        results = await asyncio.gather(
            *[h(event) for h in handlers],
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, Exception):
                from loguru import logger
                logger.warning(f"Event handler error for '{event_name}': {r}")

    def emit_sync(self, event_name: str, data: Any = None, source: str = "") -> None:
        """Emit from synchronous code (creates a task on the running loop)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event_name, data, source))
        except RuntimeError:
            asyncio.run(self.emit(event_name, data, source))

    def recent(self, n: int = 10) -> list[Event]:
        return self._history[-n:]


# Global singleton
bus = EventBus()


# ─── Standard event names (use these constants, not strings) ──────────────────

class Events:

    # Command lifecycle
    COMMAND_RECEIVED  = "command.received"
    COMMAND_PROCESSED = "command.processed"

    # Workflow lifecycle
    WORKFLOW_STARTED   = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED    = "workflow.failed"

    # Tool lifecycle
    TOOL_EXECUTING = "tool.executing"
    TOOL_EXECUTED  = "tool.executed"
    TOOL_FAILED    = "tool.failed"

    # Voice
    WAKE_WORD_DETECTED = "voice.wake_word"
    SPEECH_RECOGNIZED  = "voice.recognized"
    SPEAKING           = "voice.speaking"

    # System
    ERROR    = "system.error"
    STARTUP  = "system.startup"
    SHUTDOWN = "system.shutdown"

    # File agent
    FILE_FOUND     = "file.found"
    FILE_ORGANIZED = "file.organized"