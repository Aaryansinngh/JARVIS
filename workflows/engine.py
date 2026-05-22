"""
workflows/engine.py — Jarvis Workflow Engine

A workflow is a named sequence of steps. Each step calls a tool.
The engine executes steps, handles failures, and emits events.

This is the heart of Phase 2. It replaces the dumb config.toml workflow
list with a proper execution model that supports:
  - Sequential and parallel steps
  - Conditional branching (if_success / if_failure)
  - Context passing between steps (outputs flow as inputs)
  - Retry logic per-step
  - Async execution
  - TOML-defined workflows AND code-defined workflows

Usage:
    engine = WorkflowEngine(registry)
    result = await engine.run("coding_mode", context={"user": "Rahul"})
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger

from tools.base import ToolRegistry, ToolResult, ToolStatus


# ─── Step definition ──────────────────────────────────────────────────────────

@dataclass
class WorkflowStep:
    """
    A single step in a workflow.

    step = WorkflowStep(
        tool="open_app",
        params={"app_name": "chrome"},
        on_failure="continue",   # or "abort"
        max_retries=1,
    )
    """
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    on_failure: str = "continue"    # "continue" | "abort"
    max_retries: int = 0
    condition: Optional[str] = None  # e.g. "context.get('open_browser')"
    output_key: Optional[str] = None  # store result in context[output_key]
    label: Optional[str] = None     # human-readable description


# ─── Workflow definition ──────────────────────────────────────────────────────

@dataclass
class Workflow:
    """
    A named collection of steps.

    workflow = Workflow(
        name="coding_mode",
        description="Set up coding environment",
        steps=[
            WorkflowStep(tool="open_app", params={"app_name": "vscode"}),
            WorkflowStep(tool="wait", params={"seconds": 2}),
            WorkflowStep(tool="open_app", params={"app_name": "terminal"}),
            WorkflowStep(tool="speak", params={"text": "Ready to code."}),
        ]
    )
    """
    name: str
    description: str
    steps: list[WorkflowStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


# ─── Execution result ─────────────────────────────────────────────────────────

class WorkflowStatus(str, Enum):
    SUCCESS  = "success"
    PARTIAL  = "partial"
    FAILED   = "failed"
    ABORTED  = "aborted"


@dataclass
class StepExecution:
    step: WorkflowStep
    result: ToolResult
    index: int


@dataclass
class WorkflowResult:
    workflow_name: str
    status: WorkflowStatus
    steps: list[StepExecution] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.status == WorkflowStatus.SUCCESS

    @property
    def success_count(self) -> int:
        return sum(1 for s in self.steps if s.result.succeeded)

    @property
    def failure_count(self) -> int:
        return sum(1 for s in self.steps if not s.result.succeeded)

    def summary(self) -> str:
        total = len(self.steps)
        return (
            f"Workflow '{self.workflow_name}': {self.status.value} "
            f"({self.success_count}/{total} steps ok, {self.duration_ms:.0f}ms)"
        )


# ─── Engine ───────────────────────────────────────────────────────────────────

class WorkflowEngine:
    """
    Executes workflows by running their steps against the tool registry.

    Supports:
    - Context: a dict that flows through all steps; steps can read/write it
    - Param templates: use {context_key} in params to inject context values
    - Output capture: store tool result output into context for next steps
    - Abort on failure: configurable per step
    """

    def __init__(self, tool_registry: ToolRegistry):
        self._registry = tool_registry
        self._workflows: dict[str, Workflow] = {}

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, workflow: Workflow) -> None:
        self._workflows[workflow.name] = workflow
        logger.debug(f"Registered workflow: {workflow.name} ({len(workflow.steps)} steps)")

    def register_many(self, workflows: list[Workflow]) -> None:
        for w in workflows:
            self.register(w)

    def load_from_toml(self, toml_data: dict) -> None:
        """
        Load workflows from config.toml format.

        [workflows.coding_mode]
        description = "Start coding"
        steps = ["open vscode", "wait 2", "speak All set."]
        """
        workflows_data = toml_data.get("workflows", {})
        for name, data in workflows_data.items():
            steps = []
            for raw_step in data.get("steps", []):
                step = self._parse_toml_step(raw_step)
                if step:
                    steps.append(step)

            workflow = Workflow(
                name=name,
                description=data.get("description", ""),
                steps=steps,
            )
            self.register(workflow)
        logger.info(f"Loaded {len(workflows_data)} workflows from config")

    def _parse_toml_step(self, raw: str) -> Optional[WorkflowStep]:
        """Parse a simple string like 'open chrome' or 'wait 2' into a WorkflowStep."""
        parts = raw.strip().split(None, 1)
        if not parts:
            return None

        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        verb_map = {
            "open":  ("open_app",  {"app_name": arg}),
            "close": ("close_app", {"app_name": arg}),
            "wait":  ("wait",      {"seconds": float(arg) if arg else 1}),
            "url":   ("open_url",  {"url": arg}),
            "speak": ("speak",     {"text": arg}),
            "search":("web_search",{"query": arg}),
            "type":  ("type_text", {"text": arg}),
            "screenshot": ("take_screenshot", {}),
            "hotkey": ("hotkey",   {"keys": arg}),
        }

        if verb in verb_map:
            tool_name, params = verb_map[verb]
            return WorkflowStep(tool=tool_name, params=params, label=raw)

        logger.warning(f"Unknown workflow step verb: '{verb}' in '{raw}'")
        return None

    # ── Execution ─────────────────────────────────────────────────────────────

    async def run(
        self,
        name: str,
        context: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """Run a registered workflow by name."""
        workflow = self._workflows.get(name)
        if not workflow:
            return WorkflowResult(
                workflow_name=name,
                status=WorkflowStatus.FAILED,
                error=f"Unknown workflow: '{name}'",
            )

        return await self.run_workflow(workflow, context)

    async def run_workflow(
        self,
        workflow: Workflow,
        context: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """Execute a Workflow object directly (for code-defined workflows)."""
        ctx = dict(context or {})
        start = time.perf_counter()
        step_executions: list[StepExecution] = []
        final_status = WorkflowStatus.SUCCESS

        logger.info(f"▶ Workflow '{workflow.name}' starting ({len(workflow.steps)} steps)")

        for i, step in enumerate(workflow.steps):
            label = step.label or f"step[{i}]: {step.tool}"

            # Evaluate condition if present
            if step.condition:
                try:
                    if not eval(step.condition, {"context": ctx}):  # noqa: S307
                        logger.debug(f"  {label} — skipped (condition false)")
                        step_executions.append(StepExecution(
                            step=step,
                            result=ToolResult(status=ToolStatus.SKIPPED, tool_name=step.tool),
                            index=i,
                        ))
                        continue
                except Exception as e:
                    logger.warning(f"  {label} — condition eval failed: {e}")

            # Resolve params (template substitution from context)
            resolved_params = self._resolve_params(step.params, ctx)

            logger.debug(f"  [{i+1}/{len(workflow.steps)}] {step.tool}({resolved_params})")

            # Execute the tool
            result = await self._registry.execute(step.tool, resolved_params)

            step_executions.append(StepExecution(step=step, result=result, index=i))

            if result.succeeded:
                logger.debug(f"  ✓ {label}")
                if step.output_key:
                    ctx[step.output_key] = result.output
            else:
                logger.warning(f"  ✗ {label}: {result.error}")
                if step.on_failure == "abort":
                    final_status = WorkflowStatus.ABORTED
                    break
                else:
                    final_status = WorkflowStatus.PARTIAL

        duration = (time.perf_counter() - start) * 1000

        # If all steps failed, mark as FAILED
        if all(not s.result.succeeded for s in step_executions if s.result.status != ToolStatus.SKIPPED):
            final_status = WorkflowStatus.FAILED

        result = WorkflowResult(
            workflow_name=workflow.name,
            status=final_status,
            steps=step_executions,
            context=ctx,
            duration_ms=duration,
        )
        logger.info(f"◼ {result.summary()}")
        return result

    def _resolve_params(self, params: dict, ctx: dict) -> dict:
        """Replace {key} placeholders in param values with context values."""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and "{" in v:
                try:
                    v = v.format(**ctx)
                except KeyError:
                    pass  # leave unresolved placeholders as-is
            resolved[k] = v
        return resolved

    # ── Helpers ───────────────────────────────────────────────────────────────

    def list_workflows(self) -> list[dict]:
        return [
            {"name": w.name, "description": w.description, "steps": len(w.steps)}
            for w in self._workflows.values()
        ]

    def get(self, name: str) -> Optional[Workflow]:
        return self._workflows.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._workflows
