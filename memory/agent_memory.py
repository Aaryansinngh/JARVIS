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
    # Remember app
    # ─────────────────────────────

    def remember_app(
        self,
        app: str,
    ):

        self.last_app = app

    # ─────────────────────────────
    # Remember query
    # ─────────────────────────────

    def remember_query(
        self,
        query: str,
    ):

        self.last_query = query

    # ─────────────────────────────
    # Remember action
    # ─────────────────────────────

    def remember_action(
        self,
        action: str,
    ):

        self.last_action = action

    # ─────────────────────────────
    # Remember UI locations
    # ─────────────────────────────

    def remember_ui(
        self,
        name: str,
        location,
    ):

        self.ui_locations[name] = location

    # ─────────────────────────────
    # Get UI location
    # ─────────────────────────────

    def get_ui(
        self,
        name: str,
    ):

        return self.ui_locations.get(
            name
        )