"""
tools/base.py — Tool abstraction layer for Jarvis

Every capability Jarvis has is a Tool. Tools are:
- Self-describing (name, description, params schema)
- Executable with a standard interface
- Registerable and discoverable
- Retryable with backoff
- Observable (emit events on start/success/failure)

Usage:
    @tool(name="open_app", description="Open a desktop application")
    def open_app(app_name: str) -> ToolResult:
        ...

    registry = ToolRegistry()
    registry.register(open_app)
    result = await registry.execute("open_app", {"app_name": "chrome"})
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from loguru import logger


# ─── Result ───────────────────────────────────────────────────────────────────

class ToolStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass
class ToolResult:
    status: ToolStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    tool_name: str = ""

    @classmethod
    def ok(cls, output: Any = None, tool_name: str = "") -> "ToolResult":
        return cls(status=ToolStatus.SUCCESS, output=output, tool_name=tool_name)

    @classmethod
    def fail(cls, error: str, tool_name: str = "") -> "ToolResult":
        return cls(status=ToolStatus.FAILURE, error=error, tool_name=tool_name)

    @property
    def succeeded(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    def __str__(self) -> str:
        if self.succeeded:
            return f"✓ {self.tool_name}: {self.output}"
        return f"✗ {self.tool_name}: {self.error}"


# ─── Tool metadata ────────────────────────────────────────────────────────────

@dataclass
class ToolParam:
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolMeta:
    name: str
    description: str
    params: list[ToolParam] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    max_retries: int = 0
    timeout_seconds: float = 120.0


# ─── Base Tool class ──────────────────────────────────────────────────────────

class BaseTool:
    """
    All tools inherit from this. Subclass and implement `run()`.

    class OpenAppTool(BaseTool):
        meta = ToolMeta(name="open_app", description="Open a desktop app")

        async def run(self, app_name: str) -> ToolResult:
            ...
    """
    meta: ToolMeta

    async def run(self, **kwargs) -> ToolResult:
        raise NotImplementedError

    async def execute(self, **kwargs) -> ToolResult:
        """Execute with timing, retries, and error capture."""
        start = time.perf_counter()
        last_error = ""

        attempts = self.meta.max_retries + 1
        for attempt in range(attempts):
            try:
                if attempt > 0:
                    wait = 2 ** attempt
                    logger.debug(f"Retry {attempt}/{self.meta.max_retries} for {self.meta.name}, waiting {wait}s")
                    await asyncio.sleep(wait)

                result = await asyncio.wait_for(
                    self.run(**kwargs),
                    timeout=self.meta.timeout_seconds
                )
                result.tool_name = self.meta.name
                result.duration_ms = (time.perf_counter() - start) * 1000
                return result

            except asyncio.TimeoutError:
                last_error = f"Timed out after {self.meta.timeout_seconds}s"
                logger.warning(f"{self.meta.name} timed out (attempt {attempt+1})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"{self.meta.name} failed: {e} (attempt {attempt+1})")
                logger.debug(traceback.format_exc())

        duration = (time.perf_counter() - start) * 1000
        return ToolResult(
            status=ToolStatus.FAILURE,
            error=last_error,
            duration_ms=duration,
            tool_name=self.meta.name,
        )


# ─── Functional decorator ─────────────────────────────────────────────────────

def tool(
    name: str,
    description: str,
    tags: list[str] | None = None,
    requires_confirmation: bool = False,
    max_retries: int = 0,
    timeout_seconds: float = 120.0,
):
    """
    Decorator to turn a plain async function into a registered Tool.

    @tool(name="take_screenshot", description="Capture the screen")
    async def take_screenshot(path: str = "./screenshot.png") -> ToolResult:
        ...
    """
    def decorator(fn: Callable) -> BaseTool:
        # Build params from function signature
        sig = inspect.signature(fn)
        params = []
        for pname, param in sig.parameters.items():
            annotation = param.annotation
            type_str = annotation.__name__ if hasattr(annotation, "__name__") else str(annotation)
            params.append(ToolParam(
                name=pname,
                type=type_str,
                description="",
                required=param.default is inspect.Parameter.empty,
                default=None if param.default is inspect.Parameter.empty else param.default,
            ))

        meta = ToolMeta(
            name=name,
            description=description,
            params=params,
            tags=tags or [],
            requires_confirmation=requires_confirmation,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )

        class FunctionTool(BaseTool):
            pass

        FunctionTool.meta = meta

        if asyncio.iscoroutinefunction(fn):
            async def _run(self, **kwargs):
                return await fn(**kwargs)
        else:
            async def _run(self, **kwargs):
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, functools.partial(fn, **kwargs))

        FunctionTool.run = _run
        FunctionTool.__name__ = name
        instance = FunctionTool()
        return instance

    return decorator


# ─── Registry ─────────────────────────────────────────────────────────────────

class ToolRegistry:
    """
    Central registry for all Jarvis tools.

    registry = ToolRegistry()
    registry.register(my_tool)
    result = await registry.execute("my_tool", {"arg": "value"})
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, t: BaseTool) -> None:
        if t.meta.name in self._tools:
            logger.warning(f"Tool '{t.meta.name}' already registered — overwriting")
        self._tools[t.meta.name] = t
        logger.debug(f"Registered tool: {t.meta.name}")

    def register_many(self, tools: list[BaseTool]) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self, tag: str | None = None) -> list[ToolMeta]:
        tools = self._tools.values()
        if tag:
            tools = [t for t in tools if tag in t.meta.tags]
        return [t.meta for t in tools]

    async def execute(self, name: str, params: dict[str, Any] | None = None) -> ToolResult:
        t = self._tools.get(name)
        if not t:
            return ToolResult.fail(f"Unknown tool: '{name}'")
        return await t.execute(**(params or {}))

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# ─── Global singleton ─────────────────────────────────────────────────────────
registry = ToolRegistry()
