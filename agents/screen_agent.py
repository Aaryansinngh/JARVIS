"""
agents/screen_agent.py

Autonomous screen interaction agent.
"""

from __future__ import annotations

import asyncio

from loguru import logger

from events.bus import (
    Events,
    bus,
)

from tools.base import registry

from agents.planner import Planner
from memory.agent_memory import AgentMemory

class ScreenAgent:

    def __init__(self):

        self.max_retries = 3

        self.planner = Planner()
        self.memory = AgentMemory()

    # ─────────────────────────────────────
    # Click text
    # ─────────────────────────────────────

    async def click_text(
        self,
        query: str,
    ):

        await bus.emit(
            Events.TOOL_EXECUTING,
            data={
                "tool": "screen_agent.click_text",
                "query": query,
            },
        )

        result = await registry.execute(
            "click_on_screen",
            {
                "query": query,
            },
        )

        await bus.emit(
            Events.TOOL_EXECUTED,
            data={
                "tool": "screen_agent.click_text",
                "success": result.succeeded,
            },
        )

        return result

    # ─────────────────────────────────────
    # Type text
    # ─────────────────────────────────────

    async def type_text(
        self,
        text: str,
    ):

        return await registry.execute(
            "type_text",
            {
                "text": text,
            },
        )

    # ─────────────────────────────────────
    # Scroll down
    # ─────────────────────────────────────

    async def scroll_down(self):

        return await registry.execute(
            "scroll_down",
            {},
        )

    # ─────────────────────────────────────
    # Scroll up
    # ─────────────────────────────────────

    async def scroll_up(self):

        return await registry.execute(
            "scroll_up",
            {},
        )

    # ─────────────────────────────────────
    # Describe screen
    # ─────────────────────────────────────

    async def describe_screen(self):

        return await registry.execute(
            "describe_screen",
            {},
        )

    # ─────────────────────────────────────
    # Execute Autonomous Plan
    # ─────────────────────────────────────

    async def execute_plan(
        self,
        goal: str,
    ):

        logger.info(
            f"[ScreenAgent] Planning: {goal}"
        )

        plan = self.planner.plan(
            goal
        )

        results = []

        for tool_name, params in plan:

            logger.info(
                f"[ScreenAgent] "
                f"Executing {tool_name}"
            )

            success = False

            for attempt in range(
                self.max_retries
            ):

                try:

                    # ─────────────────────
                    # Remove internal params
                    # ─────────────────────

                    tool_params = dict(
                        params
                    )

                    tool_params.pop(
                        "verify",
                        None,
                    )

                    # ─────────────────────
                    # Execute tool
                    # ─────────────────────

                    result = await registry.execute(
                        tool_name,
                        tool_params,
                    )

                    # ─────────────────────
                    # Verification
                    # ─────────────────────

                    verify_target = params.get(
                        "verify"
                    )

                    if verify_target:

                        verify_result = await registry.execute(
                            "verify_text_visible",
                            {
                                "query": verify_target,
                            },
                        )

                        if not verify_result.succeeded:

                            logger.warning(
                                f"[ScreenAgent] "
                                f"Verification failed: "
                                f"{verify_target}"
                            )

                            await asyncio.sleep(1)

                            continue

                        logger.info(
                            f"[ScreenAgent] "
                            f"Verified: "
                            f"{verify_target}"
                        )

                    await asyncio.sleep(1)

                    if result.succeeded:

                        success = True

                        logger.info(
                            f"[ScreenAgent] "
                            f"{tool_name} success"
                        )

                        break

                    logger.warning(
                        f"[ScreenAgent] "
                        f"{tool_name} failed "
                        f"(attempt {attempt+1})"
                    )

                except Exception as e:

                    logger.error(
                        f"[ScreenAgent] "
                        f"{tool_name} crashed: {e}"
                    )

                await asyncio.sleep(1)

            results.append(result)

            if not success:

                logger.error(
                    f"[ScreenAgent] "
                    f"Aborting workflow"
                )

                return results

        return results

    # ─────────────────────────────────────
    # Main Goal Executor
    # ─────────────────────────────────────

    async def execute_goal(
        self,
        goal: str,
    ):

        logger.info(
            f"[ScreenAgent] Goal: {goal}"
        )

        t = goal.lower()

        try:

            # ─────────────────────────────
            # Planned workflows
            # ─────────────────────────────

            if (
                "search" in t
                or "linkedin" in t
                or "internship" in t
                or "summarize" in t
            ):

                return await self.execute_plan(
                    goal
                )

            # ─────────────────────────────
            # Find + type
            # ─────────────────────────────

            if (
                "find" in t
                and "type" in t
            ):

                before_type, after_type = t.split(
                    "type",
                    1,
                )

                click_target = (
                    before_type
                    .replace("find", "")
                    .replace("and", "")
                    .strip()
                )

                type_target = (
                    after_type.strip()
                )

                result = await self.click_text(
                    click_target
                )

                if not result.succeeded:

                    return result

                await asyncio.sleep(
                    0.7
                )

                return await self.type_text(
                    type_target
                )

            # ─────────────────────────────
            # Click
            # ─────────────────────────────

            if t.startswith(
                "click "
            ):

                return await self.click_text(
                    t.replace(
                        "click ",
                        "",
                        1,
                    ).strip()
                )

            # ─────────────────────────────
            # Type
            # ─────────────────────────────

            if t.startswith(
                "type "
            ):

                return await self.type_text(
                    t.replace(
                        "type ",
                        "",
                        1,
                    ).strip()
                )

            # ─────────────────────────────
            # Scroll
            # ─────────────────────────────

            if (
                "scroll down" in t
            ):

                return await self.scroll_down()

            if (
                "scroll up" in t
            ):

                return await self.scroll_up()

            # ─────────────────────────────
            # Describe screen
            # ─────────────────────────────

            if (
                "what's on screen" in t
                or "what is on screen" in t
            ):

                return await self.describe_screen()

            return None

        except Exception as e:

            logger.error(
                f"[ScreenAgent] {e}"
            )

            raise