"""
core/orchestrator_v2.py — Jarvis Orchestrator

Stable architecture:
- Browser router
- Screen router
- Screen agent tools
- Workflows
- EventBus HUD
- Ollama integration

CHANGES (drop-in upgrade — no other files need touching):
  1. Fuzzy tool matching    — triggers fire if keyword found ANYWHERE in sentence,
                              not just at t.startswith(). Longest trigger wins.
  2. Dynamic workflow params — spoken query/app extracted and injected into context
                              so workflows receive {query}, {app} etc. at runtime.
  3. LLM intent router      — _llm_route() now actually calls phi3 via Ollama and
                              returns a typed Intent instead of always returning None.
  4. Session history        — _history is written on every turn (user + assistant)
                              and passed to both _llm_route and _answer_question.
  5. Ollama timeout         — raised to 45s so phi3 has time to respond.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

from loguru import logger

from events.bus import Events, bus
from tools.base import registry as global_registry
from tools.builtin import load_all_tools

from agents.file_agent import (
    load_file_agent_tools,
    FileAgent,
)

from workflows.engine import WorkflowEngine
from workflows.builtin import get_builtin_workflows


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────

OLLAMA_TIMEOUT = 45   # seconds — was effectively 15 in planner.py


# ─────────────────────────────────────────────────────────────
# Intent Types
# ─────────────────────────────────────────────────────────────

class IntentType:
    WORKFLOW = "workflow"
    TOOL = "tool"
    QUESTION = "question"
    UNKNOWN = "unknown"


class Intent:

    def __init__(
        self,
        type: str,
        target: str = "",
        params: dict | None = None,
        raw: str = "",
    ):

        self.type = type
        self.target = target
        self.params = params or {}
        self.raw = raw

    def __repr__(self):

        return (
            f"Intent({self.type}, "
            f"target={self.target}, "
            f"params={self.params})"
        )


# ─────────────────────────────────────────────────────────────
# Workflow Triggers
# ─────────────────────────────────────────────────────────────

WORKFLOW_TRIGGERS = {

    "coding_mode": [
        "coding mode",
        "code mode",
    ],

    "study_mode": [
        "study mode",
    ],

    "focus_mode": [
        "focus mode",
    ],

    "internship_hunt": [
        "internship",
        "job search",
    ],

    "morning_routine": [
        "morning routine",
        "good morning",
        "start my day",
    ],

    "linkedin_jobs": [
        "linkedin jobs",
        "open jobs",
        "job boards",
    ],

    "summarize_screen": [
        "summarize screen",
        "read screen",
        "what's on screen",
        "what is on screen",
    ],

    "close_and_clean": [
        "close and clean",
        "clean desktop",
        "clear desktop",
        "organize downloads",
    ],

    "entertainment_mode": [
        "entertainment mode",
        "fun mode",
    ],
}


# ─────────────────────────────────────────────────────────────
# Tool Triggers
# ─────────────────────────────────────────────────────────────

TOOL_TRIGGERS = {

    "execute_goal": [
        "open ",
        "launch ",
        "start ",
        "search ",
        "youtube ",
    ],

    "close_app": [
        "close ",
        "quit ",
    ],

    "web_search": [
        "search for ",
        "google ",
        "look up ",
        "find information about ",
    ],

    "open_url": [
        "go to ",
        "navigate to ",
    ],

    "take_screenshot": [
        "screenshot",
    ],

    "organize_folder": [
        "organize downloads",
    ],
}

# ─────────────────────────────────────────────────────────────
# Param Extraction Helpers
# ─────────────────────────────────────────────────────────────

# Filler words stripped from the end of extracted targets
_TRAILING_FILLERS = (
    " for me", " please", " now", " thanks",
    " quickly", " asap", " right now",
)

# Patterns to pull a search/query value out of natural speech
_QUERY_PATTERNS = [

    r"search(?:\s+for)?\s+(.+)",

    r"look\s+up\s+(.+)",

    r"find(?:\s+information\s+(?:about|on))?\s+(.+)",

    r"google\s+(.+)",

    r"youtube(?:\s+for)?\s+(.+)",

    r"search youtube for\s+(.+)",

    r"can you search(?:\s+for)?\s+(.+)",

    r"please search(?:\s+for)?\s+(.+)",
]


def _extract_arg_after(text: str, trigger: str) -> str:

    idx = text.lower().find(trigger.lower())

    if idx == -1:
        return text.strip()

    arg = text[idx + len(trigger):].strip()

    # remove conversational filler
    fillers = [
        "for me",
        "please",
        "now",
        "thanks",
        "jarvis",
        "can you",
        "could you",
    ]

    for filler in fillers:

        arg = arg.replace(filler, "").strip()

    return arg


def _extract_query(text: str) -> Optional[str]:
    """
    Pull a search query from natural-language phrasing.
    Returns None if no pattern matches.
    """
    norm = text.lower().strip()
    for pat in _QUERY_PATTERNS:
        m = re.search(pat, norm)
        if m:
            return m.group(1).strip().rstrip(".")
    return None


# ─────────────────────────────────────────────────────────────
# Rule-based Routing  (FIXED: fuzzy tool matching)
# ─────────────────────────────────────────────────────────────

def rule_based_route(
    text: str,
) -> Optional[Intent]:

    t = text.lower().strip()

    # ── Workflows: trigger appears ANYWHERE in sentence (unchanged behaviour,
    #    workflows already used `in` not startswith — kept identical)
    for workflow_name, triggers in WORKFLOW_TRIGGERS.items():

        for trigger in triggers:

            if trigger in t:

                # FIX 2: extract dynamic params and attach to intent
                params: dict = {}
                query = _extract_query(text)
                if query:
                    params["query"] = query

                return Intent(
                    type=IntentType.WORKFLOW,
                    target=workflow_name,
                    params=params,
                    raw=text,
                )

    # ── Tools: FIX 1 — check trigger ANYWHERE, not just startswith.
    #    Longest trigger wins (avoids "open " matching inside "organize downloads").
    best_intent: Optional[Intent] = None
    best_len = 0

    for tool_name, triggers in TOOL_TRIGGERS.items():

        for trigger in triggers:

            if trigger in t and len(trigger) > best_len:

                arg = _extract_arg_after(text, trigger)

                best_intent = _build_tool_intent(
                    tool_name,
                    arg,
                    text,
                )

                best_len = len(trigger)

    if best_intent:
        return best_intent

    return None


def _build_tool_intent(
    tool_name: str,
    arg: str,
    raw: str,
) -> Intent:

    param_map = {

        "execute_goal": {
            "goal": f"open {arg.rstrip('.').strip()}",
        },

        "open_app": {
            "app_name": arg,
        },

        "close_app": {
            "app_name": arg,
        },

        "web_search": {
            "query": arg,
        },

        "open_url": {
            "url": arg,
        },

        "take_screenshot": {},

        "organize_folder": {},
    }

    return Intent(
        type=IntentType.TOOL,
        target=tool_name,
        params=param_map.get(
            tool_name,
            {},
        ),
        raw=raw,
    )


# ─────────────────────────────────────────────────────────────
# Browser Router
# ─────────────────────────────────────────────────────────────

try:

    from core.browser_router import (
        extend_rules as _extend_browser,
    )

    rule_based_route = _extend_browser(
        rule_based_route
    )

    logger.info(
        "Browser router wired"
    )

except Exception as e:

    logger.warning(
        f"Browser router unavailable: {e}"
    )


# ─────────────────────────────────────────────────────────────
# Screen Router
# ─────────────────────────────────────────────────────────────

try:

    from core.screen_router import (
        extend_rules as _extend_screen,
    )

    rule_based_route = _extend_screen(
        rule_based_route
    )

    logger.info(
        "Screen router wired"
    )

except Exception as e:

    logger.warning(
        f"Screen router unavailable: {e}"
    )


# ─────────────────────────────────────────────────────────────
# LLM Intent Router  (replaces the stub)
# ─────────────────────────────────────────────────────────────

_INTENT_SYSTEM = """\
You are an intent router for a desktop AI assistant called JARVIS.
Given the user's command (and recent conversation history), decide what to do.

Available workflows: {workflows}
Available tools: {tools}

Reply ONLY with a valid JSON object — no markdown, no explanation.
Schema:
{{
  "type": "workflow" | "tool" | "question",
  "target": "<workflow_name or tool_name, or empty string for question>",
  "params": {{}}
}}

Parameter hints:
- execute_goal  → {{"goal": "<full original command>"}}
- web_search    → {{"query": "<search terms>"}}
- open_url      → {{"url": "<url>"}}
- close_app     → {{"app_name": "<app>"}}
- workflow      → include {{"query": "..."}} if a search term was spoken

If the command is a question or casual conversation with no action, use type "question".
"""


async def _llm_intent_route(
    text: str,
    history: list[dict],
    llm,
) -> Optional[Intent]:
    """
    Ask phi3 to classify the command and extract params.
    Returns a typed Intent or None on failure/timeout.
    """
    import httpx

    # Build the prompt — tell phi3 what tools and workflows exist
    workflows_str = ", ".join(WORKFLOW_TRIGGERS.keys())
    tools_str = ", ".join(TOOL_TRIGGERS.keys())
    system = _INTENT_SYSTEM.format(
        workflows=workflows_str,
        tools=tools_str,
    )

    messages = history[-6:] + [{"role": "user", "content": text}]

    # Grab connection details from the already-initialised LLM client
    base_url = getattr(llm, "base_url", "http://localhost:11434")
    model = getattr(llm, "model", "phi3")

    payload = {
        "model":   model,
        "stream":  False,
        "system":  system,
        "messages": messages,
        "options": {"temperature": 0.0},
    }

    try:

        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:

            resp = await client.post(
                f"{base_url}/api/chat",
                json=payload,
            )

            resp.raise_for_status()
            raw_text = (
                resp.json()
                .get("message", {})
                .get("content", "")
                .strip()
            )

        # Strip markdown fences phi3 sometimes adds
        raw_text = re.sub(r"```(?:json)?|```", "", raw_text).strip()

        data = json.loads(raw_text)

        intent_type = data.get("type", "question")
        target      = data.get("target", "")
        params      = data.get("params", {})

        logger.debug(
            f"LLM intent: type={intent_type} "
            f"target={target} params={params}"
        )

        if intent_type == IntentType.WORKFLOW:
            return Intent(
                type=IntentType.WORKFLOW,
                target=target,
                params=params,
                raw=text,
            )

        if intent_type == IntentType.TOOL:
            return Intent(
                type=IntentType.TOOL,
                target=target,
                params=params,
                raw=text,
            )

        # "question" or anything else → fall through to _answer_question
        return Intent(
            type=IntentType.QUESTION,
            raw=text,
        )

    except (
        Exception  # covers TimeoutException, JSONDecodeError, ConnectError, etc.
    ) as e:

        logger.warning(
            f"LLM intent router failed ({type(e).__name__}): {e}"
        )

        return None


# ─────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────

class Orchestrator:

    def __init__(
        self,
        config: dict | None = None,
        hud=None,
    ):

        self.config = config or {}
        self.hud = hud

        self._registry = global_registry

        self._workflow_engine = WorkflowEngine(
            self._registry
        )

        self._file_agent = FileAgent()

        self._context: dict[str, Any] = {}
        self._history: list[dict] = []   # FIX 4: written every turn now

        self._llm = None

        self._boot()

    # ─────────────────────────────────────────

    def _boot(self):

        # Core tools
        load_all_tools()

        # File agent tools
        load_file_agent_tools()

        # Screen tools
        try:

            from tools.screen_tools import (
                load_screen_tools,
            )

            load_screen_tools()

            logger.info(
                "Screen tools loaded"
            )

        except Exception as e:

            logger.warning(
                f"Screen tools unavailable: {e}"
            )

        # Workflows
        self._workflow_engine.register_many(
            get_builtin_workflows()
        )

        if self.config:

            self._workflow_engine.load_from_toml(
                self.config
            )

        # LLM
        self._setup_llm()

        logger.info(
            f"Orchestrator ready: "
            f"{len(self._registry)} tools, "
            f"{len(self._workflow_engine.list_workflows())} workflows"
        )

        bus.emit_sync(
            Events.STARTUP,
            data={
                "tools": len(self._registry)
            },
        )

    # ─────────────────────────────────────────

    def _setup_llm(self):

        provider = (
            self.config
            .get("ai", {})
            .get("provider", "ollama")
        )

        try:

            if provider == "ollama":

                from llm.ollama_client import (
                    OllamaClient,
                )

                self._llm = OllamaClient(
                    model=self.config
                    .get("ai", {})
                    .get("model", "phi3"),

                    base_url=self.config
                    .get("ai", {})
                    .get(
                        "ollama_url",
                        "http://localhost:11434",
                    ),
                )

            logger.info(
                f"LLM: {provider}"
            )

        except Exception as e:

            logger.warning(
                f"LLM unavailable: {e}"
            )

            self._llm = None

    # ─────────────────────────────────────────

    def process(
        self,
        text: str,
    ) -> str:

        try:

            asyncio.get_running_loop()

            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:

                future = pool.submit(
                    asyncio.run,
                    self.process_async(text),
                )

                return future.result()

        except RuntimeError:

            return asyncio.run(
                self.process_async(text)
            )

    # ─────────────────────────────────────────

    async def process_async(
        self,
        text: str,
    ) -> str:

        text = text.strip()

        if not text:
            return ""

        logger.info(
            f"Processing: '{text}'"
        )

        await bus.emit(
            Events.COMMAND_RECEIVED,
            data={"text": text},
        )

        # FIX 4: record user turn BEFORE routing so LLM has context
        self._history.append(
            {"role": "user", "content": text}
        )

        intent = rule_based_route(text)

        # FIX 3: _llm_route now actually does something
        if intent is None and self._llm:

            intent = await self._llm_route(text)

        if (
            intent is None
            or intent.type == IntentType.QUESTION
        ):

            response = await self._answer_question(text)

        else:

            response = await self._execute_intent(intent)

        # FIX 4: record assistant turn
        self._history.append(
            {"role": "assistant", "content": response}
        )

        # Keep history bounded
        if len(self._history) > 20:
            self._history = self._history[-20:]

        return response

    # ─────────────────────────────────────────

    async def _execute_intent(
        self,
        intent: Intent,
    ) -> str:

        if intent.type == IntentType.WORKFLOW:

            return await self._run_workflow(
                intent.target,
                intent.params,    # FIX 2: pass extracted params
            )

        if intent.type == IntentType.TOOL:

            return await self._run_tool(
                intent.target,
                intent.params,
            )

        return "Unknown intent."

    # ─────────────────────────────────────────

    async def _run_workflow(
        self,
        name: str,
        params: dict | None = None,   # FIX 2: accept spoken params
    ) -> str:

        if name not in self._workflow_engine:

            return (
                f"Workflow '{name}' not found."
            )

        # FIX 2: merge spoken params into shared context so workflow
        # steps can reference {query}, {app} etc. as placeholders
        context = {**self._context, **(params or {})}

        result = await self._workflow_engine.run(
            name,
            context=context,
        )

        if result.succeeded:

            return (
                f"Workflow '{name}' completed."
            )

        return (
            f"Workflow '{name}' failed."
        )

    # ─────────────────────────────────────────

    async def _run_tool(
        self,
        name: str,
        params: dict,
    ) -> str:

        await bus.emit(
            Events.TOOL_EXECUTING,
            data={
                "tool": name,
                "params": params,
            },
        )

        result = await self._registry.execute(
            name,
            params,
        )

        await bus.emit(
            Events.TOOL_EXECUTED,
            data={
                "tool": name,
                "success": result.succeeded,
            },
        )

        if result.succeeded:

            return str(result.output)

        return (
            f"Sorry, that didn't work: "
            f"{result.error}"
        )

    # ─────────────────────────────────────────

    async def _llm_route(
        self,
        text: str,
    ) -> Optional[Intent]:
        # FIX 3: was always `return None` — now calls phi3
        return await _llm_intent_route(
            text,
            self._history,
            self._llm,
        )

    # ─────────────────────────────────────────

    async def _answer_question(
        self,
        text: str,
    ) -> str:

        if self._llm:

            try:

                # FIX 4: use self._history (already populated) instead of
                # a local `history` variable that was never written to
                return await self._llm.chat(
                    self._history[-10:] + [
                        {
                            "role": "user",
                            "content": text,
                        }
                    ]
                )

            except Exception as e:

                logger.warning(
                    f"LLM error: {e}"
                )

        return (
            "I don't know how to "
            "handle that yet."
        )

    # ─────────────────────────────────────────

    @property
    def speaker(self):
        from voice.speaker import Speaker
        if not hasattr(self, "_speaker"):
            self._speaker = Speaker()
        return self._speaker
