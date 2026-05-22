"""
core/screen_router.py
Stable screen routing
"""

from __future__ import annotations

from core.orchestrator_v2 import (
    Intent,
    IntentType,
)


def extend_rules(base_router):

    def router(text: str):

        t = text.lower().strip()

        # ─────────────────────────────────────
        # Click routing
        # ─────────────────────────────────────

        if t.startswith("click "):

            query = (
                t.replace("click ", "")
                .strip()
            )

            return Intent(
                type=IntentType.TOOL,
                target="click_on_screen",
                params={
                    "query": query
                },
                raw=text,
            )

        # ─────────────────────────────────────
        # OCR search routing
        # ─────────────────────────────────────

        if t.startswith("find "):

            query = (
                t.replace("find ", "")
                .strip()
            )

            return Intent(
                type=IntentType.TOOL,
                target="find_on_screen",
                params={
                    "query": query
                },
                raw=text,
            )

        return base_router(text)

    return router