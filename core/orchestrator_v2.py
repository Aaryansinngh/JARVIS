
"""
core/orchestrator_v2.py — Jarvis Orchestrator (Stable Version)

- Screen router disabled
- Screen tools enabled
- Browser routing fixed
- URL opening fixed
- Internship workflow compatible
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from loguru import logger

from events.bus import Events, bus
from tools.base import registry as global_registry
from tools.builtin import load_all_tools
from agents.file_agent import (
    load_file_agent_tools,
    FileAgent,
)
from workflows.engine import (
    WorkflowEngine,
)
from workflows.builtin import (
    get_builtin_workflows,
)


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

WORKFLOW_TRIGGERS: dict[str, list[str]] = {

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
}


# ─────────────────────────────────────────────────────────────
# Tool Triggers
# ─────────────────────────────────────────────────────────────

TOOL_TRIGGERS: dict[str, list[str]] = {

    "open_app": [
      "launch ",
      "open ",
      "start ",
     ],
    "close_app": [
        "close ",
        "quit ",
    ],

    "web_search": [
        "search for ",
        "google ",
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
# Rule-based Routing
# ─────────────────────────────────────────────────────────────

def rule_based_route(
    text: str,
) -> Optional[Intent]:

    t = text.lower().strip()

    for workflow_name, triggers in WORKFLOW_TRIGGERS.items():

        for trigger in triggers:

            if trigger in t:

                return Intent(
                    type=IntentType.WORKFLOW,
                    target=workflow_name,
                    raw=text,
                )

    for tool_name, triggers in TOOL_TRIGGERS.items():

        for trigger in triggers:

            if t.startswith(trigger):

                arg = t.split(
                    trigger,
                    1,
                )[-1].strip()

                return _build_tool_intent(
                    tool_name,
                    arg,
                    text,
                )

    return None


def _build_tool_intent(
    tool_name: str,
    arg: str,
    raw: str,
) -> Intent:

    param_map = {

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

    logger.debug(
        "Browser router wired"
    )

except ImportError:

    logger.warning(
        "Browser router unavailable"
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

    logger.debug(
        "Screen router wired"
    )

except ImportError:

    logger.warning(
        "Screen router unavailable"
    )


# ─────────────────────────────────────────────────────────────
# Screen Router Disabled
# ─────────────────────────────────────────────────────────────



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
        self._history: list[dict] = []

        self._llm = None

        self._boot()

    # ─────────────────────────────────────────

    def _boot(self):

        load_all_tools()

        load_file_agent_tools()

        from tools.screen_tools import (
            load_screen_tools,
        )

        load_screen_tools()

        self._workflow_engine.register_many(
            get_builtin_workflows()
        )

        if self.config:

            self._workflow_engine.load_from_toml(
                self.config
            )

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

        intent = rule_based_route(text)

        if (
            intent is None
            and self._llm
        ):

            intent = await self._llm_route(
                text
            )

        if (
            intent is None
            or intent.type == IntentType.QUESTION
        ):

            return await self._answer_question(
                text
            )

        return await self._execute_intent(
            intent
        )

    # ─────────────────────────────────────────

    async def _execute_intent(
        self,
        intent: Intent,
    ) -> str:

        if intent.type == IntentType.WORKFLOW:

            return await self._run_workflow(
                intent.target
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
    ) -> str:

        if name not in self._workflow_engine:

            return (
                f"Workflow '{name}' not found."
            )

        result = await self._workflow_engine.run(
            name,
            context=self._context,
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
    ):

        return None

    # ─────────────────────────────────────────

    async def _answer_question(
        self,
        text: str,
    ) -> str:

        if self._llm:

            try:

                history = self._history[-10:]

                return await self._llm.chat(
                    history + [
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

        class _Speaker:

            async def speak(
                self,
                text: str,
            ):

                from tools.base import registry

                await registry.execute(
                    "speak",
                    {"text": text},
                )

        return _Speaker()

