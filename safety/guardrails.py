"""
safety/guardrails.py — Safety, confirmation, rate limiting, audit logging

Every action passes through here before execution.
Think of it as the "are you sure?" layer.
"""
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm
from rich.panel import Panel
from utils.logger import logger
from utils.config import get

console = Console()


class SafetyGuard:
    """
    All automation actions should be approved through this class.

    Usage:
        guard = SafetyGuard()
        if guard.approve("send_email", "boss@company.com", "Sending email to boss"):
            email_sender.send(...)
    """

    def __init__(self):
        self.require_confirmation = set(get("safety", "require_confirmation", []))
        self.rate_limit = get("safety", "rate_limit", 10)
        self.audit_enabled = get("safety", "audit_log", True)
        self.audit_path = Path(get("safety", "audit_path", "./data/audit.log"))
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

        # Rate limiter: track timestamps of recent actions
        self._action_times: deque = deque()

    def approve(self, action: str, target: str = "", description: str = "") -> bool:
        """
        Check if an action is allowed.
        Returns True if it should proceed, False if blocked.

        Steps:
        1. Check rate limit
        2. Ask for confirmation if needed
        3. Log the decision
        """
        # ── 1. Rate limit check ──────────────────────────────────────────────
        now = time.time()
        minute_ago = now - 60
        # Remove old timestamps
        while self._action_times and self._action_times[0] < minute_ago:
            self._action_times.popleft()

        if len(self._action_times) >= self.rate_limit:
            logger.warning(f"Rate limit hit! Max {self.rate_limit} actions/minute.")
            console.print(
                f"[red]⚠ Rate limit: Too many actions ({self.rate_limit}/min max). Please wait.[/red]"
            )
            return False

        # ── 2. Confirmation for sensitive actions ────────────────────────────
        if action in self.require_confirmation:
            console.print(
                Panel(
                    f"[yellow]Action:[/yellow] [bold]{action}[/bold]\n"
                    f"[yellow]Target:[/yellow] {target}\n"
                    f"[yellow]Details:[/yellow] {description}",
                    title="[bold red]⚠ Confirmation Required[/bold red]",
                    border_style="red",
                )
            )
            approved = Confirm.ask("[bold]Proceed?[/bold]", default=False)
            if not approved:
                logger.info(f"Action '{action}' cancelled by user.")
                self._audit(action, target, description, approved=False)
                return False

        # ── 3. Log and allow ─────────────────────────────────────────────────
        self._action_times.append(now)
        self._audit(action, target, description, approved=True)
        return True

    def _audit(self, action: str, target: str, description: str, approved: bool):
        """Write to audit log."""
        if not self.audit_enabled:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "APPROVED" if approved else "DENIED"
        line = f"[{timestamp}] {status} | {action} | target={target} | {description}\n"
        with open(self.audit_path, "a", encoding="utf-8") as f:
            f.write(line)

    def is_safe_url(self, url: str) -> bool:
        """Basic URL safety check."""
        blocked_domains = ["malware", "phishing"]
        return not any(d in url.lower() for d in blocked_domains)

    def is_safe_command(self, command: str) -> bool:
        """Check if a shell/system command looks safe."""
        dangerous = ["rm -rf", "format", "del /f", "shutdown", "rd /s", "mkfs"]
        cmd_lower = command.lower()
        for d in dangerous:
            if d in cmd_lower:
                logger.warning(f"Blocked dangerous command: '{command}'")
                return False
        return True
