"""
memory/agent_memory.py

AgentMemory — session memory with disk persistence for UI coordinates.

Persistent  (saved to memory/agent_memory_data.json):
    ui_locations    {name: [x, y]}

Session-only (reset on restart):
    recent_queries, recent_apps, recent_actions
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MEMORY_FILE = Path(__file__).parent / "agent_memory_data.json"


class AgentMemory:
    """
    Stores UI coordinates, recent queries, apps, and actions.

    UI coordinate cache persists across restarts via JSON.
    All other stores are session-only.
    """

    def __init__(self, memory_file: Path | None = None):
        self._file: Path = memory_file or _MEMORY_FILE

        # Persistent
        self.ui_locations: dict[str, tuple[int, int]] = {}

        # Session-only
        self.recent_queries: list[str] = []
        self.recent_apps:    list[str] = []
        self.recent_actions: list[str] = []

        self._load()

    # ─────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────

    def _load(self) -> None:
        """Load ui_locations from disk. Silent no-op if file missing."""
        if not self._file.exists():
            return
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
            for name, coords in raw.get("ui_locations", {}).items():
                self.ui_locations[name] = (int(coords[0]), int(coords[1]))
            logger.info(
                "[memory] Loaded %d UI locations from %s",
                len(self.ui_locations),
                self._file,
            )
        except Exception as exc:
            logger.warning("[memory] Could not load memory file: %s", exc)

    def _save(self) -> None:
        """Persist ui_locations to disk as JSON."""
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "ui_locations": {
                    name: list(coords)
                    for name, coords in self.ui_locations.items()
                }
            }
            self._file.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[memory] Could not save memory file: %s", exc)

    def clear_ui_cache(self) -> None:
        """Wipe persisted UI coordinate cache (disk + session)."""
        self.ui_locations.clear()
        if self._file.exists():
            self._file.unlink()
        logger.info("[memory] UI coordinate cache cleared.")

    # ─────────────────────────────────────
    # UI coordinate API
    # ─────────────────────────────────────

    def remember_ui(self, name: str, x: int, y: int) -> None:
        """Cache UI element coordinates and persist to disk."""
        self.ui_locations[name] = (x, y)
        self._save()
        logger.debug("[memory] Remembered UI '%s' at (%d, %d)", name, x, y)

    def get_ui(self, name: str) -> tuple[int, int] | None:
        """Return cached (x, y) for a UI element, or None on miss."""
        return self.ui_locations.get(name)

    def has_ui(self, name: str) -> bool:
        """Return True if coordinates for name are cached."""
        return name in self.ui_locations

    # ─────────────────────────────────────
    # Session stores
    # ─────────────────────────────────────

    def remember_query(self, query: str) -> None:
        self.recent_queries.append(query)

    def remember_app(self, app: str) -> None:
        self.recent_apps.append(app)

    def remember_action(self, action: str) -> None:
        self.recent_actions.append(action)
