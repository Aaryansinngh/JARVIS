"""
core/screen_router.py
Minimal stable screen routing
"""

from __future__ import annotations

from core.orchestrator_v2 import (
    Intent,
    IntentType,
)


def extend_rules(base_router):

    def router(text: str):

        t = text.lower().strip()

        # OCR screen search

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