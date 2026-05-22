"""
agents/planner.py

Autonomous task planner for Jarvis.

Strategy
--------
1. Ask Ollama to parse the goal into a JSON step list.
2. If Ollama is unavailable or returns bad JSON, fall back to
   the original keyword-based planner so nothing breaks.

Step schema (same format used by ScreenAgent._execute_step):
    {"action": str, "target": str}

Supported actions
-----------------
  open        — open an app by icon name
  wait        — pause N seconds ("target" = float string)
  click       — OCR-locate and click a UI label
  type        — type text into focused field
  press       — press a keyboard key (enter, tab, escape …)
  scroll_up   — scroll up
  scroll_down — scroll down
  verify      — soft-check that text is visible on screen
  describe    — OCR-dump the full screen
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─── Ollama config ────────────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "phi3"          # swap for llama3, phi3, etc.
OLLAMA_TIMEOUT = 15               # seconds; keeps UI snappy

# ─── System prompt sent to the LLM ───────────────────────────────────────────

_SYSTEM = """
You are a desktop automation planner. Convert a user's goal into a
JSON array of steps. Each step has exactly two keys: "action" and "target".

Allowed actions (use ONLY these):
  open        target = app name (chrome, notepad, spotify …)
  wait        target = seconds as a string ("2.0")
  click       target = visible UI label to click (Search, OK, Submit …)
  type        target = text to type
  press       target = key name (enter, tab, escape, backspace …)
  scroll_up   target = "" (empty)
  scroll_down target = "" (empty)
  verify      target = short text expected to appear on screen
  describe    target = "" (empty)

Rules:
- Return ONLY a JSON array. No markdown, no explanation.
- Steps must be in correct execution order.
- For web searches: open chrome → wait 2s → click search bar → type query → press enter → verify first word of query.
- Keep target values short (one to four words).

Examples
--------
Goal: "open spotify"
[
  {"action": "open",  "target": "spotify"},
  {"action": "wait",  "target": "3.0"}
]

Goal: "search best Python tutorials"
[
  {"action": "open",  "target": "chrome"},
  {"action": "wait",  "target": "2.0"},
  {"action": "click", "target": "Search"},
  {"action": "type",  "target": "best Python tutorials"},
  {"action": "press", "target": "enter"},
  {"action": "verify","target": "Python"}
]

Goal: "scroll down"
[
  {"action": "scroll_down", "target": ""}
]
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Planner
# ─────────────────────────────────────────────────────────────────────────────

class Planner:
    """
    Converts a natural-language goal into an ordered list of step dicts.

    Usage
    -----
    planner = Planner()
    steps   = await planner.plan_async("search machine learning roadmap")
    # or synchronous (blocks event loop — use only outside async context):
    steps   = planner.plan("search machine learning roadmap")
    """

    # ── Async (preferred) ─────────────────────────────────────────────────────

    async def plan_async(self, goal: str) -> list[dict[str, str]]:
        """
        Ask Ollama for a step list. Falls back to keyword planner on any error.
        """
        try:
            steps = await self._llm_plan(goal)
            if steps:
                logger.info(
                    "[planner] LLM produced %d steps for: '%s'",
                    len(steps),
                    goal,
                )
                return steps
        except Exception as exc:
            logger.warning(
                "[planner] LLM planner failed (%s); using keyword fallback.",
                exc,
            )

        return self._keyword_plan(goal)

    # ── Sync wrapper (kept for backwards compatibility) ────────────────────────

    def plan(self, goal: str) -> list[dict[str, str]]:
        """
        Synchronous plan — calls keyword planner directly.
        Use plan_async() inside async code for LLM-powered planning.
        """
        return self._keyword_plan(goal)

    # ─────────────────────────────────────
    # LLM planner (Ollama)
    # ─────────────────────────────────────

    async def _llm_plan(self, goal: str) -> list[dict[str, str]]:
        """
        Call Ollama and parse the JSON step list from the response.
        Raises on timeout, HTTP error, or bad JSON so the caller can fall back.
        """
        prompt = f"Goal: \"{goal}\"\n\nRespond with only the JSON array of steps."

        payload = {
            "model" : OLLAMA_MODEL,
            "prompt": f"{_SYSTEM}\n\n{prompt}",
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            data = response.json()

        raw_text: str = data.get("response", "").strip()

        steps = self._parse_json_steps(raw_text)
        return self._validate_steps(steps)

    # ─────────────────────────────────────
    # JSON parsing helpers
    # ─────────────────────────────────────

    def _parse_json_steps(self, text: str) -> list[Any]:
        """
        Extract a JSON array from the LLM's raw response.
        Handles models that wrap JSON in markdown code fences.
        """
        # Strip markdown fences if present
        fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)

        # Find the first [...] block in the response
        bracket_match = re.search(r"\[.*\]", text, re.DOTALL)
        if bracket_match:
            text = bracket_match.group(0)

        return json.loads(text)

    _VALID_ACTIONS = frozenset({
        "open", "wait", "click", "type", "press",
        "scroll_up", "scroll_down", "verify", "describe",
    })

    def _validate_steps(
        self,
        steps: list[Any],
    ) -> list[dict[str, str]]:
        """
        Ensure every step has "action" and "target" keys,
        and that the action is in the allowed set.
        Drops invalid steps with a warning.
        """
        clean = []
        for step in steps:
            if not isinstance(step, dict):
                logger.warning("[planner] Skipping non-dict step: %s", step)
                continue
            action = str(step.get("action", "")).strip().lower()
            target = str(step.get("target", "")).strip()
            if action not in self._VALID_ACTIONS:
                logger.warning(
                    "[planner] Unknown action '%s' — skipping step.",
                    action,
                )
                continue
            clean.append({"action": action, "target": target})
        return clean

    # ─────────────────────────────────────
    # Keyword planner (fallback)
    # ─────────────────────────────────────

    _APP_LAUNCH_WAIT = "2.0"

    def _keyword_plan(self, goal: str) -> list[dict[str, str]]:
        """
        Original keyword-based planner.  Handles common patterns reliably
        without requiring Ollama.  Used as fallback and for sync callers.
        """
        g = goal.lower().strip()

        # ── "search <query>" ──────────────
        if g.startswith("search "):
            query_text = goal[7:].strip()
            first_word = query_text.split()[0] if query_text else "result"
            return [
                {"action": "open",   "target": "chrome"},
                {"action": "wait",   "target": "2.0"},
                {"action": "click",  "target": "Search"},
                {"action": "type",   "target": query_text},
                {"action": "press",  "target": "enter"},
                {"action": "verify", "target": first_word},
            ]

        # ── "open <app>" ──────────────────
        if g.startswith("open "):
            app = goal[5:].strip()
            return [
                {"action": "open", "target": app},
                {"action": "wait", "target": self._APP_LAUNCH_WAIT},
            ]

        # ── "click <target>" ──────────────
        if g.startswith("click "):
            return [{"action": "click", "target": goal[6:].strip()}]

        # ── "type <text>" ─────────────────
        if g.startswith("type "):
            return [{"action": "type", "target": goal[5:].strip()}]

        # ── "scroll down" ─────────────────
        if "scroll down" in g:
            return [{"action": "scroll_down", "target": ""}]

        # ── "scroll up" ───────────────────
        if "scroll up" in g:
            return [{"action": "scroll_up", "target": ""}]

        # ── "describe" / "screenshot" ─────
        if any(w in g for w in ("describe", "screenshot", "read screen")):
            return [{"action": "describe", "target": ""}]

        # ── LinkedIn / internship workflow ─
        if "linkedin" in g or "internship" in g:
            return [
                {"action": "open",  "target": "chrome"},
                {"action": "wait",  "target": "2.0"},
                {"action": "click", "target": "Search"},
                {"action": "type",  "target": "linkedin.com"},
                {"action": "press", "target": "enter"},
                {"action": "verify","target": "LinkedIn"},
            ]

        # ── Fallback: treat full goal as click ──
        logger.warning(
            "[planner] Unrecognised goal — defaulting to click: '%s'",
            goal,
        )
        return [{"action": "click", "target": goal}]
