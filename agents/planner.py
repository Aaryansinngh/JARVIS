
"""
agents/planner.py

Optimized Planner:
- Fast browser searches (NO OCR)
- Fast YouTube searches
- LLM planning fallback
- Conversation history support
- Reduced timeout
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Ollama config
# ─────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2:0.5b"
OLLAMA_TIMEOUT = 5


# ─────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────

_SYSTEM = """
You are JARVIS, an autonomous desktop AI agent.

Your job is to convert a user's goal into a step-by-step execution plan
for controlling a real computer desktop.

The computer can:
- open applications
- click UI elements
- type text
- press keyboard shortcuts
- scroll
- verify screen content
- describe the screen visually

IMPORTANT RULES:

1. Prefer FAST deterministic actions over OCR.
   Example:
   - use ctrl+l for browser search
   - use keyboard shortcuts whenever possible

2. Use OCR/visual actions ONLY when necessary.

3. Think step-by-step like a real desktop agent.

4. Plans should be minimal but complete.

5. The user goal may require:
   - searching
   - opening apps
   - navigating websites
   - summarizing information
   - interacting with desktop software

AVAILABLE ACTIONS:
- open
- wait
- click
- type
- press
- scroll_up
- scroll_down
- verify
- describe

ACTION FORMAT:
[
  {"action":"open","target":"chrome"},
  {"action":"press","target":"ctrl+l"},
  {"action":"type","target":"machine learning roadmap"},
  {"action":"press","target":"enter"}
]

PLANNING EXAMPLES:

User:
"search for python tutorials"

Plan:
[
  {"action":"open","target":"chrome"},
  {"action":"wait","target":"1"},
  {"action":"press","target":"ctrl+l"},
  {"action":"type","target":"python tutorials"},
  {"action":"press","target":"enter"}
]

User:
"open spotify"

Plan:
[
  {"action":"open","target":"spotify"}
]

User:
"summarize the current screen"

Plan:
[
  {"action":"describe","target":"screen"}
]

Return ONLY valid JSON.
No markdown.
No explanations.
""".strip()


# ─────────────────────────────────────────
# Planner
# ─────────────────────────────────────────

class Planner:

    _APP_LAUNCH_WAIT = "2.0"

    # =========================================================
    # PUBLIC API
    # =========================================================

    async def plan_async(
        self,
        goal: str,
        history: list[dict] | None = None,
    ) -> list[dict[str, str]]:

        try:

            steps = await self._llm_plan(
                goal,
                history=history or [],
            )

            if steps:

                logger.info(
                    "[planner] LLM produced %d steps",
                    len(steps),
                )

                return steps

        except Exception as exc:

            logger.warning(
                "[planner] LLM planner failed (%s); using keyword fallback.",
                exc,
            )

        return self._keyword_plan(goal)

    def plan(self, goal: str):
        return self._keyword_plan(goal)

    # =========================================================
    # LLM PLANNER
    # =========================================================

    async def _llm_plan(
        self,
        goal: str,
        history: list[dict] | None = None,
    ) -> list[dict[str, str]]:

        history_prefix = ""

        if history:

            recent = history[-6:]

            lines = []

            for turn in recent:

                role = turn.get("role", "user").capitalize()
                content = turn.get("content", "").strip()

                if content:
                    lines.append(f"{role}: {content}")

            if lines:
                history_prefix = (
                    "Recent conversation:\n"
                    + "\n".join(lines)
                    + "\n\n"
                )

        prompt = (
            f"{history_prefix}"
            f'Goal: "{goal}"\n\n'
            f"Respond ONLY with JSON."
        )

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"{_SYSTEM}\n\n{prompt}",
            "stream": False,
        }

        async with httpx.AsyncClient(
            timeout=OLLAMA_TIMEOUT
        ) as client:

            response = await client.post(
                OLLAMA_URL,
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

        raw_text = data.get("response", "").strip()

        steps = self._parse_json_steps(raw_text)

        return self._validate_steps(steps)

    # =========================================================
    # JSON HELPERS
    # =========================================================

    def _parse_json_steps(self, text: str):

        fenced = re.search(
            r"```(?:json)?\s*(\[.*?\])\s*```",
            text,
            re.DOTALL,
        )

        if fenced:
            text = fenced.group(1)

        bracket_match = re.search(
            r"\[.*\]",
            text,
            re.DOTALL,
        )

        if bracket_match:
            text = bracket_match.group(0)

        return json.loads(text)

    _VALID_ACTIONS = frozenset({
        "open",
        "wait",
        "click",
        "type",
        "press",
        "scroll_up",
        "scroll_down",
        "verify",
        "describe",
    })

    def _validate_steps(
        self,
        steps: list[Any],
    ) -> list[dict[str, str]]:

        clean = []

        for step in steps:

            if not isinstance(step, dict):
                continue

            action = str(
                step.get("action", "")
            ).strip().lower()

            target = str(
                step.get("target", "")
            ).strip()

            if action not in self._VALID_ACTIONS:
                continue

            clean.append({
                "action": action,
                "target": target,
            })

        return clean

    # =========================================================
    # KEYWORD FALLBACK PLANNER
    # =========================================================

    def _keyword_plan(
        self,
        goal: str,
    ) -> list[dict[str, str]]:

        g = goal.lower().strip()





        # =====================================================
        # FAST YOUTUBE SEARCH
        # =====================================================

        if "youtube" in g and "search" in g:

            query = (
                goal
                .replace("youtube", "")
                .replace("search", "")
                .strip()
            )

            return [
    {
        "action": "open",
        "target":
        f"https://www.youtube.com/results?search_query={query}"
    }
]

        # =====================================================
        # FAST SEARCH (NO OCR)
        # =====================================================

        if g.startswith("search "):

            query_text = (
                goal
                .replace("search for", "")
                .replace("search", "")
                .replace("for", "")
                .replace("on", "")
                .strip()
            )

            return [
    {
        "action": "open",
        "target":
        f"https://www.google.com/search?q={query_text}"
    }
]
        

                # =====================================================
        # OPEN APP (natural language aware)
        # =====================================================

        if "open" in g:

            match = re.search(
                r"open\s+(.*?)(?:\s+for me)?$",
                g
            )

            app = (
               match.group(1)
               .replace("again", "")
               .strip()
               if match else "chrome"
                )

            if app.lower() in ("it", "that", "them"):

                app = "LAST_APP"

            # clean common filler words
            app = (
                app
                .replace("please", "")
                .replace("can you", "")
                .replace("could you", "")
                .replace("jarvis", "")
                .strip()
            )

            return [
                {"action": "open", "target": app},
                {
                    "action": "wait",
                    "target": self._APP_LAUNCH_WAIT,
                },
            ]
        
                # =====================================================
        # CLOSE APP
        # =====================================================

        if "close" in g:

            import re

            match = re.search(
                r"close\s+(.*?)(?:\s+for me)?$",
                g
            )

            app = (
                match.group(1).strip()
                if match else "it"
            )

            return [
                {
                    "action": "close",
                    "target": app,
                }
            ]


        # =====================================================
        # CLICK
        # =====================================================

        if g.startswith("click "):

            return [
                {
                    "action": "click",
                    "target": goal[6:].strip(),
                }
            ]

        # =====================================================
        # TYPE
        # =====================================================

        if g.startswith("type "):

            return [
                {
                    "action": "type",
                    "target": goal[5:].strip(),
                }
            ]

        # =====================================================
        # SCROLL
        # =====================================================

        if "scroll down" in g:
            return [{"action": "scroll_down", "target": ""}]

        if "scroll up" in g:
            return [{"action": "scroll_up", "target": ""}]

        # =====================================================
        # SCREEN DESCRIPTION
        # =====================================================

        if any(
            w in g
            for w in (
                "describe",
                "screenshot",
                "read screen",
            )
        ):
            return [{"action": "describe", "target": ""}]

        # =====================================================
        # LINKEDIN / INTERNSHIP
        # =====================================================

        if "linkedin" in g or "internship" in g:

            return [
                {"action": "open",  "target": "chrome"},
                {"action": "wait",  "target": "1.0"},
                {"action": "press", "target": "ctrl+l"},
                {
                    "action": "type",
                    "target": "linkedin.com",
                },
                {"action": "press", "target": "enter"},
            ]

        # =====================================================
        # DEFAULT FALLBACK
        # =====================================================

        logger.warning(
            "[planner] Unknown goal → click fallback: '%s'",
            goal,
        )

        return [
            {
                "action": "click",
                "target": goal,
            }
        ]

