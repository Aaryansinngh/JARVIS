"""
tools/screen_tools.py — Jarvis Phase 4 Screen Understanding Tools

Registers ScreenAgent capabilities into the ToolRegistry.
Call load_screen_tools() once at startup (inside load_all_tools()).

Tools registered:
    describe_screen   — "What's on my screen?"
    read_screen_text  — OCR all visible text
    find_on_screen    — Find a UI element or text
    summarize_page    — Summarize browser page content
    fill_form         — Auto-fill visible form fields
"""

from __future__ import annotations

import asyncio
from tools.base import Tool, ToolResult, registry


# ── Tool definitions ───────────────────────────────────────────────────────────

SCREEN_TOOLS: list[Tool] = []


def _make_screen_agent():
    """Lazy-load ScreenAgent (avoids import errors if deps missing)."""
    from agents.screen_agent import ScreenAgent
    return ScreenAgent()


async def _describe_screen(params: dict) -> ToolResult:
    agent = _make_screen_agent()
    result = await agent.describe_screen()
    if result.succeeded:
        return ToolResult.ok(result.output, duration_ms=result.duration_ms)
    return ToolResult.fail(result.error)


async def _read_screen_text(params: dict) -> ToolResult:
    agent = _make_screen_agent()
    region = params.get("region")  # optional (x, y, w, h)
    result = await agent.read_text(region=region)
    if result.succeeded:
        return ToolResult.ok(result.output, duration_ms=result.duration_ms)
    return ToolResult.fail(result.error)


async def _find_on_screen(params: dict) -> ToolResult:
    query = params.get("query", "")
    if not query:
        return ToolResult.fail("query is required")
    agent = _make_screen_agent()
    result = await agent.find_on_screen(query)
    if result.succeeded:
        return ToolResult.ok(result.output, duration_ms=result.duration_ms)
    return ToolResult.fail(result.error)


async def _summarize_page(params: dict) -> ToolResult:
    agent = _make_screen_agent()
    result = await agent.summarize_page()
    if result.succeeded:
        return ToolResult.ok(result.output, duration_ms=result.duration_ms)
    return ToolResult.fail(result.error)


async def _fill_form(params: dict) -> ToolResult:
    fields = params.get("fields", {})
    if not fields:
        return ToolResult.fail("fields dict is required: {label: value, ...}")
    agent = _make_screen_agent()
    result = await agent.fill_form(fields)
    if result.succeeded:
        return ToolResult.ok(result.output, duration_ms=result.duration_ms)
    return ToolResult.fail(result.error)


# ── Registration ───────────────────────────────────────────────────────────────

def load_screen_tools():
    """Register all screen tools into the global ToolRegistry."""
    global SCREEN_TOOLS

    SCREEN_TOOLS = [
        Tool(
            name="describe_screen",
            description="Describe what is currently on the screen using GPT-4o Vision or OCR",
            fn=_describe_screen,
            params_schema={"type": "object", "properties": {}},
            timeout_s=20.0,
        ),
        Tool(
            name="read_screen_text",
            description="OCR all visible text on screen",
            fn=_read_screen_text,
            params_schema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "array",
                        "description": "Optional [x, y, w, h] to read a specific area",
                    }
                },
            },
            timeout_s=15.0,
        ),
        Tool(
            name="find_on_screen",
            description="Find a UI element, button, or text on screen",
            fn=_find_on_screen,
            params_schema={
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "What to find (e.g. 'Submit button', 'login form')"}
                },
            },
            timeout_s=20.0,
        ),
        Tool(
            name="summarize_page",
            description="Summarize the content of the current browser page by reading the screen",
            fn=_summarize_page,
            params_schema={"type": "object", "properties": {}},
            timeout_s=20.0,
        ),
        Tool(
            name="fill_form",
            description="Auto-detect and fill form fields on screen using GPT-4o Vision",
            fn=_fill_form,
            params_schema={
                "type": "object",
                "required": ["fields"],
                "properties": {
                    "fields": {
                        "type": "object",
                        "description": 'Dict of field label to value, e.g. {"Email": "a@b.com"}'
                    }
                },
            },
            timeout_s=60.0,
        ),
    ]

    for tool in SCREEN_TOOLS:
        registry.register(tool)

    print(f"[screen_tools] Registered {len(SCREEN_TOOLS)} screen tools")
