"""
automation/workflow.py — Workflow / Task Chain Engine

Reads workflows from config.toml and runs them step by step.

Step syntax:
    open <app>          — open an app
    url <https://...>   — open a URL
    wait <seconds>      — pause
    speak <message>     — Jarvis says something
    type <text>         — types text
    close <app>         — closes an app
    search <query>      — Google search
"""
import time
import re
from utils.logger import logger
from utils.config import get_section


class WorkflowEngine:
    """Executes named multi-step workflows defined in config.toml."""

    def __init__(self, launcher, speaker):
        self.launcher = launcher
        self.speaker = speaker
        self._workflows = self._load_workflows()
        logger.info(f"WorkflowEngine ready. {len(self._workflows)} workflows loaded.")

    def list_workflows(self) -> list[str]:
        return list(self._workflows.keys())

    def run(self, name: str) -> str:
        key = self._resolve(name)
        if not key:
            available = ", ".join(self._workflows.keys()) or "none defined"
            return f"I don't know a workflow called '{name}'. Available: {available}"

        workflow = self._workflows[key]
        steps = workflow.get("steps", [])
        desc = workflow.get("description", key)

        logger.info(f"Running workflow '{key}': {len(steps)} steps")
        self.speaker.speak(f"Starting {desc}.")

        for i, step in enumerate(steps, 1):
            logger.info(f"  Step {i}/{len(steps)}: {step}")
            self._execute_step(step)

        return f"{desc} complete."

    def _execute_step(self, step: str) -> str:
        step = step.strip()
        if not step or step.startswith("#"):
            return "skipped"

        parts = step.split(None, 1)
        command = parts[0].lower()
        argument = parts[1] if len(parts) > 1 else ""

        if command == "open":
            url_match = re.search(r'https?://\S+', argument)
            if url_match:
                self.launcher.open_url(url_match.group())
            else:
                self.launcher.open(argument)

        elif command == "url":
            self.launcher.open_url(argument)

        elif command == "wait":
            try:
                time.sleep(float(argument))
            except ValueError:
                pass

        elif command == "speak":
            self.speaker.speak(argument)

        elif command == "type":
            try:
                import pyautogui
                pyautogui.typewrite(argument, interval=0.05)
            except Exception as e:
                logger.error(f"type step failed: {e}")

        elif command == "close":
            self.launcher.close(argument)

        elif command == "search":
            url = f"https://www.google.com/search?q={argument.replace(' ', '+')}"
            self.launcher.open_url(url)

        else:
            logger.warning(f"Unknown workflow step: '{step}'")

    def _load_workflows(self) -> dict:
        workflows_section = get_section("workflows") or {}
        result = {}
        for name, data in workflows_section.items():
            if isinstance(data, dict) and "steps" in data:
                result[name.lower()] = data
        return result

    def _resolve(self, name: str) -> str | None:
        name = name.lower().strip()
        if name in self._workflows:
            return name
        name_us = name.replace(" ", "_")
        if name_us in self._workflows:
            return name_us
        for key in self._workflows:
            if name in key or key in name:
                return key
        return None