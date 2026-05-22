"""
test_phase2.py — Integration test for Phase 2 systems
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_tool_registry():
    print("\n─── Tool Registry ────────────────────────────────")
    from tools.base import ToolRegistry, ToolStatus
    from tools.builtin import load_all_tools, registry

    load_all_tools()
    tools = registry.list_tools()
    print(f"  ✓ Loaded {len(tools)} tools")
    for t in tools:
        print(f"    • {t.name}: {t.description[:50]}")

    result = await registry.execute("wait", {"seconds": 0.01})
    assert result.succeeded, f"Wait tool failed: {result.error}"
    print(f"  ✓ Wait tool executed in {result.duration_ms:.1f}ms")

    result = await registry.execute("nonexistent_tool", {})
    assert not result.succeeded
    print(f"  ✓ Unknown tool correctly fails: {result.error}")


async def test_workflow_engine():
    print("\n─── Workflow Engine ──────────────────────────────")
    from tools.base import registry
    from tools.builtin import load_all_tools
    from workflows.engine import WorkflowEngine, Workflow, WorkflowStep
    from workflows.builtin import get_builtin_workflows

    load_all_tools()
    engine = WorkflowEngine(registry)
    engine.register_many(get_builtin_workflows())

    workflows = engine.list_workflows()
    print(f"  ✓ Registered {len(workflows)} workflows")
    for w in workflows:
        print(f"    • {w['name']}: {w['steps']} steps")

    test_workflow = Workflow(
        name="test_sequence",
        description="Unit test",
        steps=[
            WorkflowStep(tool="wait", params={"seconds": 0.01}),
            WorkflowStep(tool="wait", params={"seconds": 0.01}),
        ],
    )
    engine.register(test_workflow)
    result = await engine.run("test_sequence")
    assert result.succeeded, f"Workflow failed: {result.error}"
    assert result.success_count == 2
    print(f"  ✓ Workflow executed: {result.summary()}")

    toml_data = {
        "workflows": {
            "toml_test": {
                "description": "From TOML",
                "steps": ["wait 0.01", "wait 0.01"],
            }
        }
    }
    engine.load_from_toml(toml_data)
    assert "toml_test" in engine
    result = await engine.run("toml_test")
    assert result.succeeded
    print(f"  ✓ TOML workflow loaded and executed")

    abort_workflow = Workflow(
        name="abort_test",
        description="Test abort on failure",
        steps=[
            WorkflowStep(tool="nonexistent", params={}, on_failure="abort"),
            WorkflowStep(tool="wait", params={"seconds": 0.01}),
        ],
    )
    engine.register(abort_workflow)
    result = await engine.run("abort_test")
    assert not result.succeeded
    assert result.success_count == 0
    print(f"  ✓ Abort on failure works correctly")


async def test_file_agent():
    print("\n─── File Agent ───────────────────────────────────")
    from agents.file_agent import FileAgent

    agent = FileAgent()

    result = await agent.find_file("python", max_results=3)
    if result.succeeded:
        print(f"  ✓ find_file('python'): {len(result.output)} results")
    else:
        print(f"  ✓ find_file('python'): no results (expected on test machine)")

    result = await agent.list_recent_files(folder="~", days=30, max_results=5)
    if result.succeeded:
        print(f"  ✓ list_recent_files: {len(result.output)} files found")
    else:
        print(f"  ~ list_recent_files: {result.error}")

    result = await agent.organize_folder(folder="~/Downloads", dry_run=True)
    if result.succeeded:
        data = result.output
        print(f"  ✓ organize dry run: would move {data['moved']} files, skip {data['skipped']}")
    else:
        print(f"  ~ organize: {result.error}")


async def test_event_bus():
    print("\n─── Event Bus ────────────────────────────────────")
    from events.bus import bus, Events

    received = []

    @bus.on(Events.TOOL_EXECUTED)
    async def on_tool(event):
        received.append(event.data)

    await bus.emit(Events.TOOL_EXECUTED, data={"tool": "test_tool"})
    assert len(received) == 1
    assert received[0]["tool"] == "test_tool"
    print(f"  ✓ Event emitted and received: {received[0]}")

    recent = bus.recent(5)
    assert len(recent) >= 1
    print(f"  ✓ Event history working: {len(recent)} events logged")


async def test_rule_routing():
    print("\n─── Rule-based Routing ───────────────────────────")
    from core.orchestrator_v2 import rule_based_route, IntentType

    cases = [
        ("start coding mode", IntentType.WORKFLOW, "coding_mode"),
        ("study mode", IntentType.WORKFLOW, "study_mode"),
        ("open chrome", IntentType.TOOL, "open_app"),
        ("search for python tutorials", IntentType.TOOL, "web_search"),
        ("take a screenshot", IntentType.TOOL, "take_screenshot"),
        ("find my resume", IntentType.TOOL, "find_file"),
    ]

    for text, expected_type, expected_target in cases:
        intent = rule_based_route(text)
        assert intent is not None, f"No intent for: '{text}'"
        assert intent.type == expected_type, f"Wrong type for '{text}': got {intent.type}"
        assert intent.target == expected_target, f"Wrong target for '{text}': got {intent.target}"
        print(f"  ✓ '{text}' → {intent.type}/{intent.target}")


async def main():
    print("=" * 50)
    print("  Jarvis Phase 2 — Integration Tests")
    print("=" * 50)

    tests = [
        test_tool_registry,
        test_workflow_engine,
        test_file_agent,
        test_event_bus,
        test_rule_routing,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"\n  ✗ {test_fn.__name__} FAILED: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 50)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
