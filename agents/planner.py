"""
agents/planner.py

Autonomous task planner.
"""

from __future__ import annotations


class Planner:

    def plan(
        self,
        goal: str,
    ):

        t = goal.lower()

        steps = []

        # ─────────────────────────────
        # Generic search workflow
        # ─────────────────────────────

        if "search" in t:

            query = (
                t.replace(
                    "search",
                    "",
                    1,
                ).strip()
            )

            steps.extend([

                (
                    "open_app",
                    {
                        "app_name": "chrome",
                        "verify": "Chrome",
                    },
                ),

                (
                    "wait",
                    {
                        "seconds": 2,
                    },
                ),

                (
                    "click_on_screen",
                    {
                        "query": "Search",
                        "verify": "Search",
                    },
                ),

                (
                    "type_text",
                    {
                        "text": query,
                    },
                ),

                (
                    "hotkey",
                    {
                        "keys": "enter",
                    },
                ),
            ])

        # ─────────────────────────────
        # LinkedIn internships
        # ─────────────────────────────

        if (
            "linkedin" in t
            or "internship" in t
        ):

            steps.extend([

                (
                    "open_app",
                    {
                        "app_name": "chrome",
                        "verify": "Chrome",
                    },
                ),

                (
                    "wait",
                    {
                        "seconds": 2,
                    },
                ),

                (
                    "open_url",
                    {
                        "url": "https://linkedin.com",
                    },
                ),
            ])

        return steps