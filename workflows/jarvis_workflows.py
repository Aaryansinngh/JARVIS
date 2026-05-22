"""
workflows/jarvis_workflows.py

5 reliable workflows for Jarvis that use subprocess to open apps
instead of click_icon, so they work even without icon templates.

Add to workflows/builtin.py get_builtin_workflows():
    from workflows.jarvis_workflows import get_jarvis_workflows
    base += get_jarvis_workflows()
"""

from __future__ import annotations

from workflows.engine import Workflow, WorkflowStep


def get_jarvis_workflows() -> list[Workflow]:
    return [
        _morning_routine(),
        _web_search(),
        _linkedin_jobs(),
        _summarize_screen(),
        _close_and_clean(),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Morning Routine
# Opens Chrome → Gmail → Calendar → News
# ─────────────────────────────────────────────────────────────────────────────

def _morning_routine() -> Workflow:
    return Workflow(
        name="morning_routine",
        description="Open Gmail, Calendar and News to start the day",
        tags=["morning", "productivity"],
        steps=[
            WorkflowStep(
                tool="execute_goal",
                params={"goal": "open chrome"},
                label="Open Chrome",
            ),
            WorkflowStep(
                tool="wait",
                params={"seconds": 2},
            ),
            WorkflowStep(
                tool="open_url",
                params={"url": "https://mail.google.com"},
                label="Open Gmail",
            ),
            WorkflowStep(
                tool="wait",
                params={"seconds": 1},
            ),
            WorkflowStep(
                tool="open_url",
                params={"url": "https://calendar.google.com"},
                label="Open Calendar",
                on_failure="continue",
            ),
            WorkflowStep(
                tool="wait",
                params={"seconds": 1},
            ),
            WorkflowStep(
                tool="open_url",
                params={"url": "https://news.google.com"},
                label="Open News",
                on_failure="continue",
            ),
            WorkflowStep(
                tool="speak",
                params={"text": "Good morning. Gmail, Calendar and News are open."},
                on_failure="continue",
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Web Search
# Opens Chrome and searches a query via screen agent
# Trigger: "web search <query>"  or run by name with context query
# ─────────────────────────────────────────────────────────────────────────────

def _web_search() -> Workflow:
    return Workflow(
        name="web_search",
        description="Open Chrome and search a query",
        tags=["search", "browser"],
        steps=[
            WorkflowStep(
                tool="execute_goal",
                params={"goal": "search {query}"},
                label="Search query",
            ),
            WorkflowStep(
                tool="speak",
                params={"text": "Search complete."},
                on_failure="continue",
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. LinkedIn Jobs / Internship Hunt
# Opens LinkedIn Jobs + Internshala + Wellfound
# ─────────────────────────────────────────────────────────────────────────────

def _linkedin_jobs() -> Workflow:
    return Workflow(
        name="linkedin_jobs",
        description="Open LinkedIn Jobs, Internshala and Wellfound",
        tags=["jobs", "career", "internship"],
        steps=[
            WorkflowStep(
                tool="execute_goal",
                params={"goal": "open chrome"},
                label="Open Chrome",
            ),
            WorkflowStep(
                tool="wait",
                params={"seconds": 2},
            ),
            WorkflowStep(
                tool="open_url",
                params={"url": "https://www.linkedin.com/jobs/"},
                label="LinkedIn Jobs",
            ),
            WorkflowStep(
                tool="wait",
                params={"seconds": 1},
            ),
            WorkflowStep(
                tool="open_url",
                params={"url": "https://internshala.com/internships/"},
                label="Internshala",
                on_failure="continue",
            ),
            WorkflowStep(
                tool="wait",
                params={"seconds": 1},
            ),
            WorkflowStep(
                tool="open_url",
                params={"url": "https://wellfound.com/jobs?jobType=internship"},
                label="Wellfound",
                on_failure="continue",
            ),
            WorkflowStep(
                tool="speak",
                params={"text": "Job boards are open. Go get it."},
                on_failure="continue",
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Summarize Screen
# OCR-reads the current screen and speaks a summary
# ─────────────────────────────────────────────────────────────────────────────

def _summarize_screen() -> Workflow:
    return Workflow(
        name="summarize_screen",
        description="Read and summarize what is currently on screen via OCR",
        tags=["screen", "ocr", "summary"],
        steps=[
            WorkflowStep(
                tool="execute_goal",
                params={"goal": "describe"},
                label="OCR screen read",
                output_key="screen_text",
            ),
            WorkflowStep(
                tool="speak",
                params={"text": "Screen read complete. Here is what I found."},
                on_failure="continue",
            ),
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Close and Clean
# Win+D to show desktop, then organizes Downloads folder
# ─────────────────────────────────────────────────────────────────────────────

def _close_and_clean() -> Workflow:
    return Workflow(
        name="close_and_clean",
        description="Minimize all windows and organize Downloads folder",
        tags=["system", "utility", "clean"],
        steps=[
            WorkflowStep(
                tool="hotkey",
                params={"keys": "win+d"},
                label="Show desktop",
            ),
            WorkflowStep(
                tool="wait",
                params={"seconds": 1},
            ),
            WorkflowStep(
                tool="organize_folder",
                params={"folder": "~/Downloads", "dry_run": False},
                label="Organize Downloads",
                on_failure="continue",
            ),
            WorkflowStep(
                tool="speak",
                params={"text": "Desktop cleared and Downloads organized."},
                on_failure="continue",
            ),
        ],
    )
