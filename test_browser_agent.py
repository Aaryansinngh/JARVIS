"""
test_browser_agent.py — Integration tests for Phase 3 Browser Agent

Run with:
    python test_browser_agent.py              # full tests (opens real browser)
    python test_browser_agent.py --headless   # headless mode
    python test_browser_agent.py --offline    # routing/logic tests only (no browser)

Tests:
  1. Router            — pattern matching for browser commands (no browser needed)
  2. BrowserAgent      — navigate, search, extract, screenshot (needs internet)
  3. BrowserTools      — tool registry integration
  4. BrowserWorkflows  — workflow registration
"""

from __future__ import annotations

import asyncio
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# ── 1. Router tests (no browser, no network) ──────────────────────────────────

async def test_browser_router():
    print("\n─── Browser Router ───────────────────────────────")
    from core.browser_router import route_browser

    cases = [
        ("search for python tutorials",           "browser_search",   {"engine": "google"}),
        ("google machine learning courses",        "browser_search",   {"engine": "google"}),
        ("play lofi music on youtube",             "browser_search",   {"engine": "youtube"}),
        ("youtube search for coding tutorials",    "browser_search",   {"engine": "youtube"}),
        ("go to https://github.com",               "browser_navigate", {"url": "https://github.com"}),
        ("open www.internshala.com",               "browser_navigate", {}),
        ("navigate to notion.so",                  "browser_navigate", {}),
        ("summarize this page",                    "browser_summary",  {}),
        ("what's on the current page",             "browser_summary",  {}),
        ("take a browser screenshot",              "browser_screenshot", {}),
        ("scroll down",                            "browser_scroll",   {"direction": "down"}),
        ("scroll to top",                          "browser_scroll",   {"direction": "top"}),
        ("click on the Sign In button",            "browser_click",    {"target": "the Sign In button"}),
        ("find internships for python developer",  "workflow:internship_search", {}),
        ("search linkedin for backend jobs",       "workflow:linkedin_jobs", {}),
        ("open chrome",                            None, {}),   # should NOT match browser router
        ("what is the capital of France",          None, {}),   # should NOT match
    ]

    passed = 0
    failed = 0
    for text, expected_tool, expected_params in cases:
        result = route_browser(text)
        actual_tool = result.tool if result else None

        if actual_tool == expected_tool:
            # Check expected params are a subset of actual
            params_ok = all(
                result.params.get(k) == v
                for k, v in expected_params.items()
                if v  # only check non-empty expected values
            ) if result else True
            if params_ok:
                print(f"  ✓ '{text[:45]:<45}' → {actual_tool}")
                passed += 1
            else:
                print(f"  ✗ '{text[:45]:<45}' → params mismatch: {result.params}")
                failed += 1
        else:
            print(f"  ✗ '{text[:45]:<45}' → expected {expected_tool}, got {actual_tool}")
            failed += 1

    print(f"\n  Router: {passed} passed, {failed} failed")
    assert failed == 0, f"{failed} router test(s) failed"


# ── 2. BrowserAgent tests (needs browser + network) ───────────────────────────

async def test_browser_navigate(headless: bool):
    print("\n─── BrowserAgent: Navigate ───────────────────────")
    from automation.browser_agent import BrowserAgent

    async with BrowserAgent(headless=headless) as agent:
        result = await agent.navigate("https://example.com")
        assert result.succeeded, f"Navigate failed: {result.error}"
        assert "example.com" in result.url
        print(f"  ✓ navigate('example.com') → {result.url}")

        info = await agent.get_page_info()
        assert info.succeeded
        print(f"  ✓ get_page_info → title='{info.output['title']}'")

        summary = await agent.get_page_summary()
        assert summary.succeeded
        assert summary.output["title"]
        print(f"  ✓ get_page_summary → {len(summary.output['body'])} chars body")

        shot = await agent.screenshot()
        assert shot.succeeded
        assert Path(shot.output).exists()
        print(f"  ✓ screenshot → {shot.output}")
        Path(shot.output).unlink(missing_ok=True)  # clean up


async def test_browser_search(headless: bool):
    print("\n─── BrowserAgent: Search ─────────────────────────")
    from automation.browser_agent import BrowserAgent

    async with BrowserAgent(headless=headless) as agent:
        result = await agent.search("python programming language", engine="google", max_results=5)
        assert result.succeeded, f"Search failed: {result.error}"
        assert isinstance(result.output, list)
        print(f"  ✓ google search → {len(result.output)} results")
        for r in result.output[:3]:
            print(f"      • {r['title'][:60]}")

        result2 = await agent.search("lofi music", engine="youtube", max_results=4)
        assert result2.succeeded, f"YouTube search failed: {result2.error}"
        print(f"  ✓ youtube search → {len(result2.output)} results")


async def test_browser_extract(headless: bool):
    print("\n─── BrowserAgent: Extract ────────────────────────")
    from automation.browser_agent import BrowserAgent

    async with BrowserAgent(headless=headless) as agent:
        await agent.navigate("https://example.com")

        text_result = await agent.extract_text()
        assert text_result.succeeded
        assert len(text_result.output) > 10
        print(f"  ✓ extract_text → {len(text_result.output)} chars")

        link_result = await agent.extract_links()
        assert link_result.succeeded
        print(f"  ✓ extract_links → {len(link_result.output)} links")

        h1_result = await agent.extract_text("h1")
        if h1_result.succeeded:
            print(f"  ✓ extract_text('h1') → '{h1_result.output[:50]}'")


# ── 3. Tool registry integration ──────────────────────────────────────────────

async def test_browser_tools():
    print("\n─── Browser Tools Registry ───────────────────────")
    try:
        from tools.base import registry
        from tools.browser_tools import load_browser_tools, BROWSER_TOOLS

        load_browser_tools()
        print(f"  ✓ Registered {len(BROWSER_TOOLS)} browser tools")
        for t in BROWSER_TOOLS:
            print(f"      • {t.name}")
    except ImportError:
        print("  ~ Skipped (tools.base not available in test env)")


# ── 4. Workflow registration ───────────────────────────────────────────────────

async def test_browser_workflows():
    print("\n─── Browser Workflows ────────────────────────────")
    try:
        from workflows.engine import WorkflowEngine
        from tools.base import registry
        from tools.builtin import load_all_tools
        from tools.browser_tools import load_browser_tools
        from workflows.browser_workflows import get_browser_workflows

        load_all_tools()
        load_browser_tools()
        engine = WorkflowEngine(registry)
        workflows = get_browser_workflows()
        engine.register_many(workflows)

        listed = engine.list_workflows()
        browser_wfs = [w for w in listed if any(
            bw.name == w["name"] for bw in workflows
        )]
        print(f"  ✓ Registered {len(browser_wfs)} browser workflows")
        for w in browser_wfs:
            print(f"      • {w['name']}: {w['steps']} steps")
    except ImportError:
        print("  ~ Skipped (workflow engine not available in test env)")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(headless: bool = False, offline: bool = False):
    print("=" * 50)
    print("  Jarvis Phase 3 — Browser Agent Tests")
    print("=" * 50)

    tests_offline = [test_browser_router, test_browser_tools, test_browser_workflows]
    tests_online  = [
        lambda: test_browser_navigate(headless),
        lambda: test_browser_search(headless),
        lambda: test_browser_extract(headless),
    ]

    all_tests = tests_offline if offline else tests_offline + tests_online

    passed = failed = 0
    for test_fn in all_tests:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            import traceback
            name = getattr(test_fn, "__name__", str(test_fn))
            print(f"\n  ✗ {name} FAILED: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 50)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--offline",  action="store_true", help="Only run offline tests (no browser)")
    args = parser.parse_args()
    asyncio.run(main(headless=args.headless, offline=args.offline))
