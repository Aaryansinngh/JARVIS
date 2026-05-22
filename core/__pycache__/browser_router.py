"""
core/browser_router.py — Rule-based routing for browser commands

Plugs into orchestrator_v2.py's rule_based_route() function.
Import extend_rules() and call it once at startup to add browser
intent patterns to the existing rule table.

Patterns handled:
  "search for X"                    → browser_search {query: X}
  "google X"                        → browser_search {query: X, engine: google}
  "youtube X / play X on youtube"   → browser_search {query: X, engine: youtube}
  "go to / open / navigate to URL"  → browser_navigate {url: URL}
  "what's on this page / summarize" → browser_summary {}
  "take a browser screenshot"       → browser_screenshot {}
  "click X"                         → browser_click {target: X}
  "scroll down/up"                  → browser_scroll {direction: ...}
  "find internships for X"          → workflow: internship_search
  "search linkedin for X"           → workflow: linkedin_jobs
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class BrowserIntent:
    tool: str           # tool name OR "workflow:<name>"
    params: dict
    confidence: float = 1.0


# ── Pattern matching helpers ──────────────────────────────────────────────────

def _strip(text: str) -> str:
    return text.strip().rstrip(".")


def route_browser(text: str) -> Optional[BrowserIntent]:
    """
    Try to match a browser intent from natural language.
    Returns BrowserIntent or None if no match.
    """
    t = text.lower().strip()

    # ── Internship / job search workflows ─────────────────────────────────────
    if re.search(r"linkedin", t) and re.search(r"job|intern|search", t):
        return BrowserIntent(tool="workflow:linkedin_jobs", params={})

    if re.search(r"internship", t):
        role_match = re.search(r"(?:for|in)\s+(.+)$", t)
        query = role_match.group(1).strip() if role_match else "software engineer internship"
        return BrowserIntent(tool="workflow:internship_search", params={"query": query})

    # ── YouTube ────────────────────────────────────────────────────────────────
    m = re.search(r"(?:play|search|find|look up)\s+(.+?)\s+on\s+youtube", t)
    if m:
        return BrowserIntent(
            tool="browser_search",
            params={"query": _strip(m.group(1)), "engine": "youtube"},
        )
    m = re.search(r"youtube\s+(?:search\s+)?(?:for\s+)?(.+)$", t)
    if m:
        return BrowserIntent(
            tool="browser_search",
            params={"query": _strip(m.group(1)), "engine": "youtube"},
        )

    # ── Google search ──────────────────────────────────────────────────────────
    m = re.search(r"^(?:google|search(?:\s+(?:google|the\s+web))?\s+(?:for)?)\s+(.+)$", t)
    if m:
        return BrowserIntent(
            tool="browser_search",
            params={"query": _strip(m.group(1)), "engine": "google"},
        )
    m = re.search(r"^search\s+(?:for\s+)?(.+)$", t)
    if m:
        return BrowserIntent(
            tool="browser_search",
            params={"query": _strip(m.group(1)), "engine": "google"},
        )

    # ── Navigate to URL ────────────────────────────────────────────────────────
    m = re.search(
        r"(?:go to|open|navigate to|visit|browse to)\s+(https?://\S+|www\.\S+|\S+\.\S+)",
        t,
    )
    if m:
        url = m.group(1)
        return BrowserIntent(tool="browser_navigate", params={"url": url})

    # URL typed directly
    if re.match(r"^https?://\S+$", t) or re.match(r"^www\.\S+\.\S+$", t):
        return BrowserIntent(tool="browser_navigate", params={"url": t})

    # ── Page summarize ─────────────────────────────────────────────────────────
    if re.search(r"\b(summarize|summary|what.s on|read|describe)\b.*(page|screen|site|tab)\b", t) or \
       re.search(r"\b(what.s on|what is on)\s+(this|the)\s+(page|screen)\b", t):
        return BrowserIntent(tool="browser_summary", params={})

    # ── Screenshot ─────────────────────────────────────────────────────────────
    if re.search(r"\bbrowser\s+screenshot\b", t) or \
       re.search(r"\bscreenshot\s+(of\s+)?(the\s+)?browser\b", t):
        return BrowserIntent(tool="browser_screenshot", params={})

    # ── Click ──────────────────────────────────────────────────────────────────
    m = re.search(r"^click\s+(?:on\s+)?(.+)$", t)
    if m and not re.search(r"\b(app|program|icon)\b", t):
        return BrowserIntent(tool="browser_click", params={"target": _strip(m.group(1))})

    # ── Scroll ─────────────────────────────────────────────────────────────────
    m = re.search(r"scroll\s+(down|up|to\s+top|to\s+bottom)", t)
    if m:
        direction = m.group(1).replace("to ", "")
        return BrowserIntent(tool="browser_scroll", params={"direction": direction})

    # ── Extract / copy text ────────────────────────────────────────────────────
    if re.search(r"(?:extract|copy|get|grab)\s+(?:the\s+)?text\s+(?:from\s+)?(?:the\s+)?(?:page|site)", t):
        return BrowserIntent(tool="browser_extract", params={})

    return None


# ── Integration hook ──────────────────────────────────────────────────────────

def extend_rules(rule_based_route_fn):
    """
    Wrap the existing rule_based_route function to add browser routing.
    
    Usage in orchestrator_v2.py startup:
    
        from core.browser_router import extend_rules
        rule_based_route = extend_rules(rule_based_route)

    Or call route_browser() directly inside your existing rule_based_route.
    """
    from core.orchestrator_v2 import IntentType

    def patched_route(text: str):
        # Try existing rules first
        result = rule_based_route_fn(text)
        if result is not None:
            return result

        # Try browser rules
        browser_intent = route_browser(text)
        if browser_intent is None:
            return None

        # Convert to your IntentType format
        if browser_intent.tool.startswith("workflow:"):
            workflow_name = browser_intent.tool.split(":", 1)[1]
            return type("Intent", (), {
                "type":   IntentType.WORKFLOW,
                "target": workflow_name,
                "params": browser_intent.params,
            })()
        else:
            return type("Intent", (), {
                "type":   IntentType.TOOL,
                "target": browser_intent.tool,
                "params": browser_intent.params,
            })()

    return patched_route
