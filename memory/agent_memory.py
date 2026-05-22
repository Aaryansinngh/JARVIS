"""
memory/agent_memory.py

Persistent agent memory.
"""

from __future__ import annotations


class AgentMemory:

    def __init__(self):

        self.last_app = None

        self.last_query = None

        self.last_action = None

        self.ui_locations = {}

    # ─────────────────────────────
    # App memory
    # ─────────────────────────────

    def remember_app(
        self,
        app: str,
    ):

        self.last_app = app

    # ─────────────────────────────
    # Query memory
    # ─────────────────────────────

    def remember_query(
        self,
        query: str,
    ):

        self.last_query = query

    # ─────────────────────────────
    # Action memory
    # ─────────────────────────────

    def remember_action(
        self,
        action: str,
    ):

        self.last_action = action

    # ─────────────────────────────
    # UI coordinate memory
    # ─────────────────────────────

    def remember_ui(
        self,
        name: str,
        x: int,
        y: int,
    ):

        self.ui_locations[name] = (
            x,
            y,
        )

    # ─────────────────────────────

    def get_ui(
        self,
        name: str,
    ):

        return self.ui_locations.get(
            name
        )

    # ─────────────────────────────

    def has_ui(
        self,
        name: str,
    ):

        return (
            name in self.ui_locations
        )