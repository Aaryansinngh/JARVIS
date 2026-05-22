"""
core/screen_router.py — Jarvis Phase 4 Screen Command Router

Fast regex-based routing for screen understanding commands.
Zero LLM needed for common commands.

Patterns handled:
    "what's on my screen"       → describe_screen
    "what do I see"             → describe_screen
    "read my screen"            → read_screen_text
    "read the text on screen"   → read_screen_text
    "find the submit button"    → find_on_screen {query: "submit button"}
    "is there a login form"     → find_on_screen {query: "login form"}
    "summarize this page"       → summarize_page  (also handled by browser_router)
    "fill in the form"          → fill_form (needs params from LLM)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScreenRoute:
    tool:   str
    params: dict


_PATTERNS: list[tuple[re.Pattern, str, dict]] = [
    # describe_screen
    (re.compile(r"what(?:'s| is)(?: on)? (?:my )?screen", re.I),          "describe_screen",  {}),
    (re.compile(r"what (?:do i see|can i see|am i looking at)",  re.I),    "describe_screen",  {}),
    (re.compile(r"(?:look at|analyze|check) (?:my )?screen",     re.I),    "describe_screen",  {}),
    (re.compile(r"screen(?:shot)? description",                  re.I),    "describe_screen",  {}),

    # read_screen_text
    (re.compile(r"read (?:the )?(?:text (?:on|from) )?(?:my )?screen", re.I), "read_screen_text", {}),
    (re.compile(r"ocr (?:my )?screen",                               re.I),   "read_screen_text", {}),
    (re.compile(r"extract text from screen",                         re.I),   "read_screen_text", {}),
    (re.compile(r"what (?:text|words) (?:is|are) on (?:my )?screen", re.I),  "read_screen_text", {}),

    # summarize_page (screen version — works even without browser)
    (re.compile(r"summarize (?:this|the|current) (?:page|website|article|tab)", re.I), "summarize_page", {}),
    (re.compile(r"what(?:'s| is) (?:this|the) (?:page|article|website) about", re.I),  "summarize_page", {}),
    (re.compile(r"give me a summary of (?:this|the) page",                      re.I),  "summarize_page", {}),
    (re.compile(r"tldr (?:this|of this) page",                                  re.I),  "summarize_page", {}),
]

# find_on_screen has dynamic query extraction
_FIND_PATTERN = re.compile(
    r"(?:find|locate|where is|can you see|is there)(?: a| the| an)? (.+?)(?:\s+on(?:\s+(?:my\s+)?screen)?)?$",
    re.I,
)


def route_screen(text: str) -> Optional[ScreenRoute]:
    """
    Try to match a screen command. Returns ScreenRoute or None.
    """
    t = text.strip()

    # Static patterns
    for pattern, tool, params in _PATTERNS:
        if pattern.search(t):
            return ScreenRoute(tool=tool, params=params)

    # Dynamic find_on_screen
    m = _FIND_PATTERN.search(t)
    if m:
        query = m.group(1).strip().rstrip("?").strip()
        if query and len(query) > 2:
            return ScreenRoute(tool="find_on_screen", params={"query": query})

    return None


def extend_rules(existing_route_fn):
    """
    Decorator-style extender for orchestrator_v2.rule_based_route.
    Adds screen routing before the existing function's fallthrough.

    Usage in orchestrator_v2.py:
        from core.screen_router import extend_rules
        rule_based_route = extend_rules(rule_based_route)
    """
    def extended(text: str):
        screen = route_screen(text)
        if screen:
            try:
                from core.orchestrator_v2 import Intent, IntentType
                return Intent(
                    type=IntentType.TOOL,
                    target=screen.tool,
                    params=screen.params,
                )
            except ImportError:
                pass
        return existing_route_fn(text)
    return extended
