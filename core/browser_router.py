
"""
core/browser_router.py — Rule-based routing for browser commands
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class BrowserIntent:
    tool: str
    params: dict
    confidence: float = 1.0


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _strip(text: str) -> str:
    return text.strip().rstrip(".")


# ─────────────────────────────────────────────────────────────
# Main Router
# ─────────────────────────────────────────────────────────────

def route_browser(text: str) -> Optional[BrowserIntent]:

    t = text.lower().strip()

    # ─────────────────────────────────────────────────────────
    # Internship Search
    # ─────────────────────────────────────────────────────────

    if re.search(r"internship|internships", t):

        role_match = re.search(r"(?:for|in)\s+(.+)$", t)

        query = (
            role_match.group(1).strip()
            if role_match
            else "software engineer"
        )

        return BrowserIntent(
            tool="workflow:internship_search",
            params={"query": query},
        )

    # ─────────────────────────────────────────────────────────
    # LinkedIn Jobs
    # ─────────────────────────────────────────────────────────

    if re.search(r"linkedin", t) and re.search(r"job|jobs|intern", t):

        return BrowserIntent(
            tool="workflow:linkedin_jobs",
            params={},
        )

    # ─────────────────────────────────────────────────────────
    # YouTube Search
    # ─────────────────────────────────────────────────────────

    m = re.search(
        r"(?:play|search|find|look up)\s+(.+?)\s+on\s+youtube",
        t,
    )

    if m:

        query = _strip(m.group(1))

        return BrowserIntent(
            tool="youtube_search",
            params={
                "query": query
            },
        )

    m = re.search(
        r"youtube\s+(?:search\s+)?(?:for\s+)?(.+)$",
        t,
    )

    if m:

        query = _strip(m.group(1))

        return BrowserIntent(
            tool="youtube_search",
            params={
                "query": query
            },
        )

    # ─────────────────────────────────────────────────────────
    # Google Search
    # ─────────────────────────────────────────────────────────

    m = re.search(
        r"^(?:google|search(?:\s+(?:google|the\s+web))?\s+(?:for)?)\s+(.+)$",
        t,
    )

    if m:

        return BrowserIntent(
            tool="web_search",
            params={
                "query": _strip(m.group(1))
            },
        )

    m = re.search(
        r"^search\s+(?:for\s+)?(.+)$",
        t,
    )

    if m:

        return BrowserIntent(
            tool="web_search",
            params={
                "query": _strip(m.group(1))
            },
        )

    # ─────────────────────────────────────────────────────────
    # Open URL
    # ─────────────────────────────────────────────────────────

    m = re.search(
        r"(?:go to|open|navigate to|visit|browse to)\s+(https?://\S+|www\.\S+|\S+\.\S+)",
        t,
    )

    if m:

        url = m.group(1)

        return BrowserIntent(
            tool="open_url",
            params={"url": url},
        )

    if re.match(r"^https?://\S+$", t) or re.match(r"^www\.\S+\.\S+$", t):

        return BrowserIntent(
            tool="open_url",
            params={"url": t},
        )

    # ─────────────────────────────────────────────────────────
    # Screenshot
    # ─────────────────────────────────────────────────────────

    if re.search(r"\bbrowser\s+screenshot\b", t):

        return BrowserIntent(
            tool="take_screenshot",
            params={
                "path": "./data/browser_capture.png"
            },
        )

    return None


# ─────────────────────────────────────────────────────────────
# Integration Hook
# ─────────────────────────────────────────────────────────────

def extend_rules(rule_based_route_fn):

    from core.orchestrator_v2 import IntentType

    def patched_route(text: str):

        result = rule_based_route_fn(text)

        if result is not None:
            return result

        browser_intent = route_browser(text)

        if browser_intent is None:
            return None

        if browser_intent.tool.startswith("workflow:"):

            workflow_name = browser_intent.tool.split(":", 1)[1]

            return type(
                "Intent",
                (),
                {
                    "type": IntentType.WORKFLOW,
                    "target": workflow_name,
                    "params": browser_intent.params,
                },
            )()

        return type(
            "Intent",
            (),
            {
                "type": IntentType.TOOL,
                "target": browser_intent.tool,
                "params": browser_intent.params,
            },
        )()

    return patched_route

