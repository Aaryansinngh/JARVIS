"""
workflows/builtin.py — Pre-built Jarvis workflows (code-defined)

These are richer than the TOML workflows because they can use:
- Conditions
- Output passing
- Dynamic params
- Better descriptions

You can still define simple workflows in config.toml.
Define complex ones here.
"""

from __future__ import annotations

from workflows.engine import Workflow, WorkflowStep


def get_builtin_workflows() -> list[Workflow]:
    from workflows.browser_workflows import get_browser_workflows

    base = [
        _coding_mode(),
        _study_mode(),
        _morning_routine(),
        _focus_mode(),
        _entertainment_mode(),
        _internship_hunt(),
        _clean_desktop(),
    ] + get_browser_workflows()

    # Phase 4: parallel fast variants
    try:
        from workflows.parallel import get_parallel_workflows
        base += get_parallel_workflows()
    except ImportError:
        pass

    return base


def _coding_mode() -> Workflow:
    return Workflow(
        name="coding_mode",
        description="Set up full coding environment",
        tags=["dev", "productivity"],
        steps=[
            WorkflowStep(tool="open_app", params={"app_name": "vscode"},    label="Open VS Code"),
            WorkflowStep(tool="wait",     params={"seconds": 2}),
            WorkflowStep(tool="open_app", params={"app_name": "terminal"},  label="Open Terminal"),
            WorkflowStep(tool="wait",     params={"seconds": 1}),
            WorkflowStep(tool="open_app", params={"app_name": "chrome"},    label="Open Chrome"),
            WorkflowStep(tool="wait",     params={"seconds": 1}),
            WorkflowStep(tool="speak",    params={"text": "Coding mode ready. Let's build something great."}),
        ],
    )


def _study_mode() -> Workflow:
    return Workflow(
        name="study_mode",
        description="Set up study session with Notion and lofi music",
        tags=["productivity", "study"],
        steps=[
            WorkflowStep(tool="open_app",  params={"app_name": "chrome"}),
            WorkflowStep(tool="wait",      params={"seconds": 1.5}),
            WorkflowStep(tool="open_url",  params={"url": "https://notion.so"}),
            WorkflowStep(tool="wait",      params={"seconds": 1}),
            WorkflowStep(tool="open_url",  params={"url": "https://youtube.com/results?search_query=lofi+study+music"}),
            WorkflowStep(tool="speak",     params={"text": "Study mode ready. Focus up."}),
        ],
    )


def _morning_routine() -> Workflow:
    return Workflow(
        name="morning_routine",
        description="Open mail, calendar, and news for morning startup",
        tags=["productivity", "morning"],
        steps=[
            WorkflowStep(tool="open_app", params={"app_name": "chrome"}),
            WorkflowStep(tool="wait",     params={"seconds": 1.5}),
            WorkflowStep(tool="open_url", params={"url": "https://mail.google.com"}),
            WorkflowStep(tool="wait",     params={"seconds": 1}),
            WorkflowStep(tool="open_url", params={"url": "https://calendar.google.com"}),
            WorkflowStep(tool="wait",     params={"seconds": 1}),
            WorkflowStep(tool="open_url", params={"url": "https://news.google.com"}),
            WorkflowStep(tool="speak",    params={"text": "Good morning. Mail, calendar and news are open."}),
        ],
    )


def _focus_mode() -> Workflow:
    return Workflow(
        name="focus_mode",
        description="Close distractions, open VS Code",
        tags=["productivity", "focus"],
        steps=[
            WorkflowStep(tool="close_app", params={"app_name": "chrome"},  on_failure="continue"),
            WorkflowStep(tool="close_app", params={"app_name": "discord"}, on_failure="continue"),
            WorkflowStep(tool="close_app", params={"app_name": "spotify"}, on_failure="continue"),
            WorkflowStep(tool="wait",      params={"seconds": 1}),
            WorkflowStep(tool="open_app",  params={"app_name": "vscode"}),
            WorkflowStep(tool="speak",     params={"text": "Focus mode activated. Distractions closed."}),
        ],
    )


def _entertainment_mode() -> Workflow:
    return Workflow(
        name="entertainment_mode",
        description="Open Spotify and YouTube",
        tags=["entertainment"],
        steps=[
            WorkflowStep(tool="open_app", params={"app_name": "spotify"}),
            WorkflowStep(tool="wait",     params={"seconds": 1}),
            WorkflowStep(tool="open_app", params={"app_name": "chrome"}),
            WorkflowStep(tool="wait",     params={"seconds": 1.5}),
            WorkflowStep(tool="open_url", params={"url": "https://youtube.com"}),
            WorkflowStep(tool="speak",    params={"text": "Entertainment mode ready. Enjoy."}),
        ],
    )


def _internship_hunt() -> Workflow:
    return Workflow(
        name="internship_hunt",
        description="Open all internship job boards",
        tags=["career", "jobs"],
        steps=[
            WorkflowStep(tool="open_app", params={"app_name": "chrome"}),
            WorkflowStep(tool="wait",     params={"seconds": 1.5}),
            WorkflowStep(tool="open_url", params={"url": "https://www.linkedin.com/jobs/"}),
            WorkflowStep(tool="wait",     params={"seconds": 1}),
            WorkflowStep(tool="open_url", params={"url": "https://internshala.com"}),
            WorkflowStep(tool="wait",     params={"seconds": 1}),
            WorkflowStep(tool="open_url", params={"url": "https://wellfound.com/jobs"}),
            WorkflowStep(tool="speak",    params={"text": "Job boards open. Go get it."}),
        ],
    )


def _clean_desktop() -> Workflow:
    return Workflow(
        name="clean_desktop",
        description="Minimize all windows and show desktop",
        tags=["system", "utility"],
        steps=[
            WorkflowStep(tool="hotkey", params={"keys": "win+d"}, label="Show desktop"),
            WorkflowStep(tool="speak",  params={"text": "Desktop cleared."}),
        ],
    )
