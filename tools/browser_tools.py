"""
tools/browser_tools.py — Browser Tools for the ToolRegistry

Wraps every BrowserAgent action as a Tool so the WorkflowEngine
and Orchestrator can call them like any other capability.

Tools registered:
  browser_navigate    → go to a URL
  browser_search      → search and return results
  browser_click       → click element by selector or text
  browser_fill        → fill a single form field
  browser_fill_form   → fill multiple form fields
  browser_extract     → extract text from page or element
  browser_links       → extract all links from page
  browser_screenshot  → take a screenshot
  browser_scroll      → scroll the page
  browser_back        → go back
  browser_forward     → go forward
  browser_summary     → get page title + url + body text
  browser_close       → close the browser session
"""

from __future__ import annotations

from typing import Any

from loguru import logger

# Import base Tool infrastructure (matches your tools/base.py pattern)
try:
    from tools.base import Tool, ToolResult, registry
except ImportError:
    # Graceful stub for standalone testing
    class Tool:
        def __init__(self, name, description, parameters, handler):
            self.name = name
            self.description = description
            self.parameters = parameters
            self.handler = handler

    class ToolResult:
        def __init__(self, succeeded, output=None, error="", duration_ms=0.0):
            self.succeeded = succeeded
            self.output = output
            self.error = error
            self.duration_ms = duration_ms

    class _FakeRegistry:
        def register(self, tool): pass
    registry = _FakeRegistry()

from automation.browser_agent import BrowserAgent, BrowserResult


# ── Singleton browser session ─────────────────────────────────────────────────
# One shared browser instance per Jarvis process. Reused across tool calls
# so pages stay open between "navigate → click → fill" chains.

_agent: BrowserAgent | None = None


def get_agent(headless: bool = False) -> BrowserAgent:
    global _agent
    if _agent is None or not _agent._ready:
        _agent = BrowserAgent(headless=headless)
    return _agent


def _to_tool_result(br: BrowserResult) -> ToolResult:
    """Convert BrowserResult → ToolResult."""
    return ToolResult(
        succeeded=br.succeeded,
        output=br.output,
        error=br.error,
        duration_ms=br.duration_ms,
    )


# ── Tool handlers ─────────────────────────────────────────────────────────────

async def _navigate(params: dict) -> ToolResult:
    url = params.get("url", "")
    if not url:
        return ToolResult(False, error="url parameter required")
    agent = get_agent(headless=params.get("headless", False))
    result = await agent.navigate(url)
    return _to_tool_result(result)


async def _search(params: dict) -> ToolResult:
    query = params.get("query", "")
    if not query:
        return ToolResult(False, error="query parameter required")
    agent = get_agent(headless=params.get("headless", False))
    result = await agent.search(
        query=query,
        engine=params.get("engine", "google"),
        max_results=int(params.get("max_results", 8)),
    )
    return _to_tool_result(result)


async def _click(params: dict) -> ToolResult:
    target = params.get("target", "")
    if not target:
        return ToolResult(False, error="target parameter required")
    agent = get_agent()
    result = await agent.click(target)
    return _to_tool_result(result)


async def _fill(params: dict) -> ToolResult:
    selector = params.get("selector", "")
    value = params.get("value", "")
    if not selector or value is None:
        return ToolResult(False, error="selector and value parameters required")
    agent = get_agent()
    result = await agent.fill(
        selector=selector,
        value=value,
        press_enter=params.get("press_enter", False),
    )
    return _to_tool_result(result)


async def _fill_form(params: dict) -> ToolResult:
    fields = params.get("fields", {})
    if not fields:
        return ToolResult(False, error="fields dict required")
    agent = get_agent()
    result = await agent.fill_form(
        fields=fields,
        submit=params.get("submit", False),
    )
    return _to_tool_result(result)


async def _extract(params: dict) -> ToolResult:
    agent = get_agent()
    result = await agent.extract_text(selector=params.get("selector"))
    return _to_tool_result(result)


async def _links(params: dict) -> ToolResult:
    agent = get_agent()
    result = await agent.extract_links(selector=params.get("selector"))
    return _to_tool_result(result)


async def _screenshot(params: dict) -> ToolResult:
    agent = get_agent()
    result = await agent.screenshot(
        path=params.get("path"),
        full_page=params.get("full_page", False),
    )
    return _to_tool_result(result)


async def _scroll(params: dict) -> ToolResult:
    agent = get_agent()
    result = await agent.scroll(
        direction=params.get("direction", "down"),
        amount=int(params.get("amount", 500)),
    )
    return _to_tool_result(result)


async def _back(params: dict) -> ToolResult:
    agent = get_agent()
    return _to_tool_result(await agent.back())


async def _forward(params: dict) -> ToolResult:
    agent = get_agent()
    return _to_tool_result(await agent.forward())


async def _summary(params: dict) -> ToolResult:
    agent = get_agent()
    result = await agent.get_page_summary(
        max_chars=int(params.get("max_chars", 1500))
    )
    return _to_tool_result(result)


async def _close(params: dict) -> ToolResult:
    global _agent
    if _agent:
        await _agent.close()
        _agent = None
    return ToolResult(True, output="Browser closed")


# ── Tool definitions ──────────────────────────────────────────────────────────

BROWSER_TOOLS = [
    Tool(
        name="browser_navigate",
        description="Open a URL in the browser",
        parameters={"url": "str", "headless": "bool?"},
        handler=_navigate,
    ),
    Tool(
        name="browser_search",
        description="Search the web and return a list of results",
        parameters={"query": "str", "engine": "str?", "max_results": "int?", "headless": "bool?"},
        handler=_search,
    ),
    Tool(
        name="browser_click",
        description="Click an element on the current page by CSS selector or visible text",
        parameters={"target": "str"},
        handler=_click,
    ),
    Tool(
        name="browser_fill",
        description="Type a value into a single form field",
        parameters={"selector": "str", "value": "str", "press_enter": "bool?"},
        handler=_fill,
    ),
    Tool(
        name="browser_fill_form",
        description="Fill multiple form fields at once using label names",
        parameters={"fields": "dict", "submit": "bool?"},
        handler=_fill_form,
    ),
    Tool(
        name="browser_extract",
        description="Extract visible text from the current page or a specific element",
        parameters={"selector": "str?"},
        handler=_extract,
    ),
    Tool(
        name="browser_links",
        description="Extract all hyperlinks from the current page",
        parameters={"selector": "str?"},
        handler=_links,
    ),
    Tool(
        name="browser_screenshot",
        description="Take a screenshot of the current browser page",
        parameters={"path": "str?", "full_page": "bool?"},
        handler=_screenshot,
    ),
    Tool(
        name="browser_scroll",
        description="Scroll the current page up, down, to top, or to bottom",
        parameters={"direction": "str?", "amount": "int?"},
        handler=_scroll,
    ),
    Tool(
        name="browser_back",
        description="Go back to the previous page in browser history",
        parameters={},
        handler=_back,
    ),
    Tool(
        name="browser_forward",
        description="Go forward in browser history",
        parameters={},
        handler=_forward,
    ),
    Tool(
        name="browser_summary",
        description="Get the title, URL, and a text summary of the current page",
        parameters={"max_chars": "int?"},
        handler=_summary,
    ),
    Tool(
        name="browser_close",
        description="Close the browser session",
        parameters={},
        handler=_close,
    ),
]


def load_browser_tools():
    """Register all browser tools into the global registry. Call once at startup."""
    for tool in BROWSER_TOOLS:
        registry.register(tool)
    logger.info("Registered {} browser tools", len(BROWSER_TOOLS))
