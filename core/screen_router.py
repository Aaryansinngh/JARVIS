"""
core/screen_router.py

Fast rule-based routing for screen actions.
Avoids unnecessary LLM calls.
"""

from __future__ import annotations

from core.orchestrator_v2 import (
    Intent,
    IntentType,
)


# ─────────────────────────────────────────
# Screen Router Extension
# ─────────────────────────────────────────

def extend_rules(
    previous_router,
):

    def route(
        text: str,
    ):

        t = text.lower().strip()

        # ─────────────────────────────────
        # Autonomous Goal Routing
        # ─────────────────────────────────

        if (
            "linkedin" in t
            or "internship" in t
            or "summarize" in t
            or "search" in t
        ):

            return Intent(
                type=IntentType.TOOL,
                target="execute_goal",
                params={
                    "goal": text,
                },
                raw=text,
            )

        # ─────────────────────────────────
        # Find + Type Compound Action
        # ─────────────────────────────────

        if (
            "find" in t
            and "type" in t
        ):

            return Intent(
                type=IntentType.TOOL,
                target="execute_goal",
                params={
                    "goal": text,
                },
                raw=text,
            )

        # ─────────────────────────────────
        # Click text
        # ─────────────────────────────────

        if t.startswith("click "):

            target = t.replace(
                "click ",
                "",
                1,
            ).strip()

            return Intent(
                type=IntentType.TOOL,
                target="click_on_screen",
                params={
                    "query": target,
                },
                raw=text,
            )

        # ─────────────────────────────────
        # Find text
        # ─────────────────────────────────

        if t.startswith("find "):

            target = t.replace(
                "find ",
                "",
                1,
            ).strip()

            return Intent(
                type=IntentType.TOOL,
                target="find_on_screen",
                params={
                    "query": target,
                },
                raw=text,
            )

        # ─────────────────────────────────
        # Type text
        # ─────────────────────────────────

        if t.startswith("type "):

            target = t.replace(
                "type ",
                "",
                1,
            ).strip()

            return Intent(
                type=IntentType.TOOL,
                target="type_text",
                params={
                    "text": target,
                },
                raw=text,
            )

        # ─────────────────────────────────
        # Scroll
        # ─────────────────────────────────

        if (
            "scroll down" in t
        ):

            return Intent(
                type=IntentType.TOOL,
                target="scroll_down",
                params={},
                raw=text,
            )

        if (
            "scroll up" in t
        ):

            return Intent(
                type=IntentType.TOOL,
                target="scroll_up",
                params={},
                raw=text,
            )

        # ─────────────────────────────────
        # What's on screen
        # ─────────────────────────────────

        if (
            "what's on screen" in t
            or "what is on screen" in t
        ):

            return Intent(
                type=IntentType.TOOL,
                target="describe_screen",
                params={},
                raw=text,
            )

        # ─────────────────────────────────
        # Fallback
        # ─────────────────────────────────

        return previous_router(
            text
        )

    return route