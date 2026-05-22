"""
workflows/browser_workflows.py — Pre-built browser workflows
"""

from __future__ import annotations

try:
    from workflows.engine import Workflow, WorkflowStep
except ImportError:
    from dataclasses import dataclass, field
    from typing import Any

    @dataclass
    class WorkflowStep:
        tool: str
        params: dict = field(default_factory=dict)
        on_failure: str = "continue"
        label: str = ""

    @dataclass
    class Workflow:
        name: str
        description: str
        steps: list


def get_browser_workflows() -> list[Workflow]:

    return [

        # ─────────────────────────────────────────────────────────────
        # Google Search
        # ─────────────────────────────────────────────────────────────

        Workflow(
            name="google_search",
            description="Search Google",
            steps=[
                WorkflowStep(
                    tool="web_search",
                    params={"query": "AI tutorials"},
                    label="Google Search",
                ),
                WorkflowStep(
                    tool="speak",
                    params={"text": "Search completed."},
                    on_failure="continue",
                ),
            ],
        ),

        # ─────────────────────────────────────────────────────────────
        # YouTube Search
        # ─────────────────────────────────────────────────────────────

        Workflow(
            name="youtube_search",
            description="Search YouTube",
            steps=[
                WorkflowStep(
                    tool="open_url",
                    params={"url": "https://www.youtube.com"},
                    label="Open YouTube",
                ),
                WorkflowStep(
                    tool="speak",
                    params={"text": "YouTube opened."},
                    on_failure="continue",
                ),
            ],
        ),

        # ─────────────────────────────────────────────────────────────
        # LinkedIn Jobs
        # ─────────────────────────────────────────────────────────────

        Workflow(
            name="linkedin_jobs",
            description="Open LinkedIn Jobs",
            steps=[
                WorkflowStep(
                    tool="open_url",
                    params={
                        "url": "https://www.linkedin.com/jobs/"
                    },
                    label="Open LinkedIn Jobs",
                ),
                WorkflowStep(
                    tool="speak",
                    params={"text": "LinkedIn Jobs opened."},
                    on_failure="continue",
                ),
            ],
        ),

        # ─────────────────────────────────────────────────────────────
        # Internship Search
        # ─────────────────────────────────────────────────────────────

        Workflow(
            name="internship_search",
            description="Open internship websites",
            steps=[

                WorkflowStep(
                    tool="open_url",
                    params={
                        "url": "https://internshala.com/internships/"
                    },
                    label="Open Internshala",
                ),

                WorkflowStep(
                    tool="wait",
                    params={"seconds": 1},
                ),

                WorkflowStep(
                    tool="open_url",
                    params={
                        "url": "https://www.linkedin.com/jobs/internship-jobs/"
                    },
                    label="Open LinkedIn Internships",
                ),

                WorkflowStep(
                    tool="wait",
                    params={"seconds": 1},
                ),

                WorkflowStep(
                    tool="open_url",
                    params={
                        "url": "https://wellfound.com/jobs?jobType=internship"
                    },
                    label="Open Wellfound",
                ),

                WorkflowStep(
                    tool="speak",
                    params={
                        "text": "Internship websites are open."
                    },
                    on_failure="continue",
                ),
            ],
        ),

        # ─────────────────────────────────────────────────────────────
        # Browser Screenshot
        # ─────────────────────────────────────────────────────────────

        Workflow(
            name="browser_capture",
            description="Capture browser screenshot",
            steps=[
                WorkflowStep(
                    tool="take_screenshot",
                    params={"path": "./data/browser_capture.png"},
                    label="Take Screenshot",
                ),
                WorkflowStep(
                    tool="speak",
                    params={"text": "Screenshot saved."},
                    on_failure="continue",
                ),
            ],
        ),

    ]