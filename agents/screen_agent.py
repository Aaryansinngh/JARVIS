
"""
agents/screen_agent.py
Autonomous screen agent for Jarvis.

Updated version:
- Fast-path simple commands (skip slow LLM planner)
- Conversation history support
- LLaVA visual grounding
- Retry engine integration
- Persistent coordinate caching
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

APP_LAUNCH_WAIT = 2.0
STEP_WAIT = 0.4
TYPE_INTERVAL = 0.05


class _ToolProxy:
    def __init__(self, module):
        self._mod = module

    def _wrap(self, name: str):
        tool_obj = getattr(self._mod, name)

        first_param = None

        try:
            fn = getattr(tool_obj, "_fn", None) or getattr(tool_obj, "fn", None)

            if fn is None and callable(tool_obj):
                fn = tool_obj

            if fn is not None:
                params = list(inspect.signature(fn).parameters.keys())
                params = [p for p in params if p != "self"]

                if params:
                    first_param = params[0]

        except Exception:
            pass

        async def _caller(*args, **kwargs):

            if args and not kwargs:

                if first_param:
                    kwargs = {first_param: args[0]}

                else:
                    for key in ("icon_name", "query", "goal", "text"):
                        try:
                            return await tool_obj.run(**{key: args[0]})
                        except TypeError:
                            continue

                    return await tool_obj.run(args[0])

            return await tool_obj.run(**kwargs)

        _caller.__name__ = name
        return _caller

    def __getattr__(self, name: str):
        obj = getattr(self._mod, name)

        if hasattr(obj, "run") and callable(obj.run):
            return self._wrap(name)

        return obj


class ScreenAgent:

    def __init__(self):
        self._tools = None
        self._retry = None
        self._planner = None

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

    def _emit(self, event: str, payload: dict | None = None):

        try:
            event_bus.emit_sync(event, data=payload or {}, source="screen_agent")
        except Exception as exc:
            logger.warning("[screen_agent] EventBus emit failed: %s", exc)

    async def execute_goal(
        self,
        goal: str,
        app_name: Optional[str] = None,
        history: Optional[List[dict]] = None,
    ) -> List[ToolResult]:

        self._ensure_retry_engine()
        self._ensure_planner()

        logger.info("[screen_agent] Executing goal: '%s'", goal)

        self._emit("agent:goal_start", {"goal": goal})

        # =========================================================
        # FAST PATH (skip slow LLM planner)
        # =========================================================

        goal_lower = goal.lower().strip()

        simple_prefixes = [
            "open ",
            "launch ",
            "start ",
            "close ",
        ]

        if any(goal_lower.startswith(p) for p in simple_prefixes):

            logger.info("[screen_agent] Using fast execution path")

            if goal_lower.startswith("open "):
                app = goal_lower.replace("open ", "").strip()
                result = await self._act_open(app)
                return [result]

            if goal_lower.startswith("launch "):
                app = goal_lower.replace("launch ", "").strip()
                result = await self._act_open(app)
                return [result]

            if goal_lower.startswith("start "):
                app = goal_lower.replace("start ", "").strip()
                result = await self._act_open(app)
                return [result]

        # =========================================================
        # LLM PLANNING
        # =========================================================

        steps = await self._planner.plan_async(
            goal,
            history=history or []
        )

        results = []

        for step in steps:

            self._emit("agent:step_start", {"step": step})

            result = await self._execute_step(
                step=step,
                app_name=app_name,
            )

            results.append(result)

             
            

            if not result.succeeded:

                logger.error(
                    "[screen_agent] Step failed: %s",
                    step,
                )

                self._emit(
                    "agent:step_failed",
                    {
                        "step": step,
                        "error": result.error,
                    },
                )

                break

            self._emit(
                "agent:step_done",
                {
                    "step": step,
                    "output": str(result.output),
                },
            )

            await asyncio.sleep(STEP_WAIT)

        self._emit(
            "agent:goal_done",
            {
                "goal": goal,
                "success": all(r.succeeded for r in results),
            },
        )

        return results

    async def _execute_step(
        self,
        step: dict,
        app_name: Optional[str],
    ) -> ToolResult:

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
                target=target,
                app_name=app_name,
            )

        if action in ("click", "find"):
            return await self._act_click_with_retry(
                target=target,
                app_name=app_name,
            )

        return ToolResult.fail(f"Unknown step action: '{action}'")

    async def _act_open(self, app_name: str) -> ToolResult:

        import subprocess
        import webbrowser

        app_name = app_name.strip()

        # =====================================================
        # DIRECT URL OPEN
        # =====================================================

        if (
            app_name.startswith("http://")
            or app_name.startswith("https://")
        ):

            webbrowser.open(app_name)

            return ToolResult.ok(
                f"Opened URL: {app_name}"
            )

        # =====================================================
        # APP LAUNCHERS
        # =====================================================

        launchers = {
            "chrome": [
                "start",
                "chrome",
                "--profile-directory=Default"
            ],

            "google chrome": [
                "start",
                "chrome",
                "--profile-directory=Default"
            ],

            "notepad": ["notepad"],

            "spotify": ["start", "spotify"],

            "explorer": ["explorer"],

            "edge": ["start", "msedge"],

            "microsoft edge": ["start", "msedge"],
        }

        cmd = launchers.get(app_name.lower())

        if cmd:
            subprocess.Popen(cmd, shell=True)

            await asyncio.sleep(APP_LAUNCH_WAIT)

            return ToolResult.ok(f"Opened {app_name}")

        result = await self._tools.click_icon(app_name)

        if result.succeeded:
            await asyncio.sleep(APP_LAUNCH_WAIT)

        return result

    async def _act_type(self, text: str) -> ToolResult:
        pyautogui.write(text, interval=TYPE_INTERVAL)
        return ToolResult.ok(f"Typed: '{text}'")

    
    async def _act_press(self, key: str) -> ToolResult:

        import asyncio

        key = key.lower().strip()

        # Handle key combinations like ctrl+l
        if "+" in key:

            keys = [k.strip() for k in key.split("+")]

            pyautogui.hotkey(*keys)

        else:

            pyautogui.press(key)

        await asyncio.sleep(0.3)

        return ToolResult.ok(f"Pressed: '{key}'")
    async def _act_click_with_retry(
        self,
        target: str,
        app_name: Optional[str],
    ) -> ToolResult:

        cached = memory.get_ui(target)

        if cached:

            x, y = cached

            pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.doubleClick()

            return ToolResult.ok(
                f"[Cache] Clicked '{target}' at ({x}, {y})"
            )

        ocr_probe = await self._tools.find_on_screen(target)

        if not ocr_probe.succeeded:

            llava_result = await self._llava_locate(target)

            if llava_result and llava_result.succeeded:
                return llava_result

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

        result = await self._retry.run(
            query=target,
            action=self._tools.verify_text_visible,
            app_name=app_name,
        )

        if not result.succeeded:

            logger.warning(
                "[screen_agent] Verify soft-fail for '%s'",
                target,
            )

            return ToolResult.ok(
                f"[Verify] Could not confirm '{target}'"
            )

        return result

