"""
agents/screen_agent.py
Autonomous screen agent for Jarvis.

Changes vs previous version
----------------------------
1. _ToolProxy now uses inspect.signature() to discover param names
   automatically — no more hardcoded per-tool maps.
2. execute_goal() calls Planner.plan_async() for LLM-powered planning,
   falling back to keyword planning if Ollama is unavailable.
3. ScreenAgent.execute_goal accepts app_name as an optional hint
   forwarded to RetryEngine's REOPEN_APP strategy.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from typing import List, Optional

import pyautogui

from events.bus import bus as event_bus
from memory.shared_memory import memory
from tools.base import ToolResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# Constants
# ─────────────────────────────────────────

APP_LAUNCH_WAIT = 2.0
STEP_WAIT       = 0.4
TYPE_INTERVAL   = 0.05


# ─────────────────────────────────────────
# FunctionTool proxy (auto-inspect)
# ─────────────────────────────────────────

class _ToolProxy:
    """
    Wraps FunctionTool objects (produced by @tool decorator) into plain
    async callables so the rest of the agent can call them naturally.

    Instead of a hardcoded param-name map, we inspect the underlying
    function signature to find the first positional parameter name.
    This means new tools work automatically without updating any map.
    """

    def __init__(self, module):
        self._mod = module

    def _wrap(self, name: str):
        tool_obj = getattr(self._mod, name)

        # Discover the first parameter name from the real function signature.
        # FunctionTool stores the original function as ._fn (or .fn).
        first_param: str | None = None
        try:
            fn = getattr(tool_obj, "_fn", None) or getattr(tool_obj, "fn", None)
            if fn is None and callable(tool_obj):
                fn = tool_obj
            if fn is not None:
                params = list(inspect.signature(fn).parameters.keys())
                # Skip 'self' for bound methods
                params = [p for p in params if p != "self"]
                if params:
                    first_param = params[0]
        except (TypeError, ValueError):
            pass

        async def _caller(*args, **kwargs):
            # If called positionally (e.g. action("Search")), map
            # the first argument to the discovered parameter name.
            if args and not kwargs:
                if first_param:
                    kwargs = {first_param: args[0]}
                else:
                    # Try common param names in order
                    for key in ("icon_name", "query", "goal", "text"):
                        try:
                            return await tool_obj.run(**{key: args[0]})
                        except TypeError:
                            continue
                    return await tool_obj.run(args[0])
                    return  # unreachable, keeps linter happy
            return await tool_obj.run(**kwargs)

        # Preserve the original name for debugging
        _caller.__name__ = name
        return _caller

    def __getattr__(self, name: str):
        obj = getattr(self._mod, name)
        # Only proxy FunctionTool-like objects (have a .run coroutine)
        if hasattr(obj, "run") and callable(obj.run):
            return self._wrap(name)
        return obj


# ─────────────────────────────────────────
# Screen Agent
# ─────────────────────────────────────────

class ScreenAgent:
    """
    Executes autonomous, multi-step screen goals.

    Responsibilities
    ----------------
    - Parse a high-level goal into ordered steps via LLM (Ollama)
      with keyword-planner fallback
    - Execute each step through the tool registry
    - Use RetryEngine for self-healing on failure
    - Emit EventBus events so the HUD stays updated
    - Cache successful UI coordinates via shared memory (persisted)
    """

    def __init__(self):
        self._tools  = None   # _ToolProxy, lazy
        self._retry  = None   # RetryEngine, lazy
        self._planner = None  # Planner, lazy

    # ─────────────────────────────────────
    # Lazy initialisation
    # ─────────────────────────────────────

    def _ensure_tools(self):
        if self._tools is not None:
            return
        import tools.screen_tools as st
        self._tools = _ToolProxy(st)

    def _ensure_retry_engine(self):
        if self._retry is not None:
            return
        self._ensure_tools()
        from agents.retry_engine import RetryEngine, RetryConfig
        self._retry = RetryEngine(
            screen_tools=self._tools,
            config=RetryConfig(),
        )

    def _ensure_planner(self):
        if self._planner is not None:
            return
        from agents.planner import Planner
        self._planner = Planner()

    # ─────────────────────────────────────
    # EventBus helpers
    # ─────────────────────────────────────

    def _emit(self, event: str, payload: dict | None = None):
        try:
            event_bus.emit_sync(event, data=payload or {}, source="screen_agent")
        except Exception as exc:
            logger.warning("[screen_agent] EventBus emit failed: %s", exc)

    # ─────────────────────────────────────
    # Goal executor (public entry point)
    # ─────────────────────────────────────

    async def execute_goal(
        self,
        goal: str,
        app_name: Optional[str] = None,
    ) -> List[ToolResult]:
        """
        Execute a high-level goal string.

        Parameters
        ----------
        goal     : natural-language goal, e.g. "search machine learning roadmap"
        app_name : optional app name hint for RetryEngine REOPEN_APP strategy

        Returns
        -------
        list of ToolResult, one per executed step.
        """
        self._ensure_retry_engine()
        self._ensure_planner()

        logger.info("[screen_agent] Executing goal: '%s'", goal)
        self._emit("agent:goal_start", {"goal": goal})

        # ── LLM-powered planning (async, with keyword fallback) ──
        steps = await self._planner.plan_async(goal)

        results = []

        for step in steps:

            self._emit("agent:step_start", {"step": step})

            result = await self._execute_step(step=step, app_name=app_name)
            results.append(result)

            if not result.succeeded:
                logger.error(
                    "[screen_agent] Step failed and could not recover: %s", step
                )
                self._emit(
                    "agent:step_failed",
                    {"step": step, "error": result.error},
                )
                break   # abort workflow on unrecoverable failure

            self._emit(
                "agent:step_done",
                {"step": step, "output": str(result.output)},
            )

            await asyncio.sleep(STEP_WAIT)

        self._emit(
            "agent:goal_done",
            {"goal": goal, "success": all(r.succeeded for r in results)},
        )

        return results

    # ─────────────────────────────────────
    # Step executor
    # ─────────────────────────────────────

    async def _execute_step(
        self,
        step: dict,
        app_name: Optional[str],
    ) -> ToolResult:
        """
        Execute one workflow step, applying RetryEngine for UI-targeting steps.

        Step dict schema:  {"action": str, "target": str}
        """
        action = step.get("action", "")
        target = step.get("target", "")

        if action == "open":
            return await self._act_open(target)

        if action == "wait":
            seconds = float(target) if target else APP_LAUNCH_WAIT
            await asyncio.sleep(seconds)
            return ToolResult.ok(f"Waited {seconds}s")

        if action == "type":
            return await self._act_type(target)

        if action == "press":
            return await self._act_press(target)

        if action == "scroll_down":
            return await self._tools.scroll_down()

        if action == "scroll_up":
            return await self._tools.scroll_up()

        if action in ("screenshot", "describe"):
            return await self._tools.describe_screen()

        if action == "verify":
            return await self._act_verify_with_retry(
                target=target, app_name=app_name
            )

        if action in ("click", "find"):
            return await self._act_click_with_retry(
                target=target, app_name=app_name
            )

        return ToolResult.fail(f"Unknown step action: '{action}'")

    # ─────────────────────────────────────
    # Individual action handlers
    # ─────────────────────────────────────

    async def _act_open(self, app_name: str) -> ToolResult:
        import subprocess
        import sys

        launchers = {
            "chrome"  : ["start", "chrome"],
            "notepad" : ["notepad"],
            "spotify" : ["start", "spotify"],
            "explorer": ["explorer"],
            "edge"    : ["start", "msedge"],
        }

        cmd = launchers.get(app_name.lower())

        if cmd:
            subprocess.Popen(cmd, shell=True)
            await asyncio.sleep(APP_LAUNCH_WAIT)
            return ToolResult.ok(f"Opened {app_name}")

        # Fallback: try icon click
        result = await self._tools.click_icon(app_name)
        if result.succeeded:
            await asyncio.sleep(APP_LAUNCH_WAIT)
        return result
    async def _act_type(self, text: str) -> ToolResult:
        pyautogui.write(text, interval=TYPE_INTERVAL)
        return ToolResult.ok(f"Typed: '{text}'")

    async def _act_press(self, key: str) -> ToolResult:
        pyautogui.press(key)
        return ToolResult.ok(f"Pressed: '{key}'")

    async def _act_click_with_retry(
        self,
        target: str,
        app_name: Optional[str],
    ) -> ToolResult:
        """
        Click a UI element by OCR label with RetryEngine fallback.

        Flow
        ----
        1. Check memory cache → instant click if hit
        2. Call RetryEngine.run(click_on_screen) on miss/fail
        3. Cache successful coordinates for future runs
        """
        # ── Cache-first ────────────────────
        cached = memory.get_ui(target)
        if cached:
            x, y = cached
            logger.debug(
                "[screen_agent] Cache hit for '%s' → (%d, %d)", target, x, y
            )
            pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.doubleClick()
            return ToolResult.ok(f"[Cache] Clicked '{target}' at ({x}, {y})")

        # ── RetryEngine path ───────────────
        result = await self._retry.run(
            query=target,
            action=self._tools.click_on_screen,
            app_name=app_name,
        )

        if result.succeeded:
            await self._cache_if_found(target)

        return result

    async def _act_verify_with_retry(
        self,
        target: str,
        app_name: Optional[str],
    ) -> ToolResult:
        """
        Verify text is visible on screen (soft-fail — OCR may miss browser text).
        """
        result = await self._retry.run(
            query=target,
            action=self._tools.verify_text_visible,
            app_name=app_name,
        )

        if not result.succeeded:
            logger.warning(
                "[screen_agent] Verify soft-fail for '%s' — "
                "OCR may have missed rendered text. Continuing.",
                target,
            )
            return ToolResult.ok(
                f"[Verify] Could not confirm '{target}' via OCR "
                f"(soft-fail — goal may still have succeeded)"
            )

        return result

    # ─────────────────────────────────────
    # Coordinate caching helper
    # ─────────────────────────────────────

    async def _cache_if_found(self, query: str):
        """
        After a successful click, run a quick OCR find and persist
        the coordinates in shared memory for future runs.
        """
        try:
            from tools.screen_tools import _ocr_find
            ocr_result = await _ocr_find(query)
            if ocr_result.succeeded and isinstance(ocr_result.output, dict):
                data = ocr_result.output
                memory.remember_ui(
                    query,
                    int(data.get("x", 0)),
                    int(data.get("y", 0)),
                )
                logger.debug("[screen_agent] Cached coordinates for '%s'.", query)
        except Exception as exc:
            logger.warning(
                "[screen_agent] Could not cache coordinates for '%s': %s",
                query, exc,
            )
