"""
agents/retry_engine.py
Smart self-healing retry engine for Jarvis.

Instead of blindly retrying the same action,
this engine applies adaptive fallback strategies:
  - alternate OCR label variants
  - scroll-and-retry (up + down)
  - cached coordinate fallback
  - delayed backoff retries
  - app relaunch as last resort
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Awaitable, Callable, List, Optional

from memory.shared_memory import memory
from tools.base import ToolResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# Strategy Enum
# ─────────────────────────────────────────

class RetryStrategy(Enum):
    """
    Ordered list of recovery strategies.
    The engine works through these in sequence
    until one succeeds or all are exhausted.
    """

    ALTERNATE_LABELS   = auto()   # try synonym labels via OCR
    DELAYED_RETRY      = auto()   # wait, then retry original action
    SCROLL_DOWN_RETRY  = auto()   # scroll down, then retry
    SCROLL_UP_RETRY    = auto()   # scroll up, then retry
    COORDINATE_FALLBACK = auto()  # use cached coordinates directly
    REOPEN_APP         = auto()   # reopen the target application


# ─────────────────────────────────────────
# Config
# ─────────────────────────────────────────

@dataclass
class RetryConfig:
    """
    Tunable parameters for the retry engine.
    Callers can override defaults per-tool or per-goal.
    """

    # Maximum total attempts (original + retries)
    max_attempts: int = 5

    # Seconds to wait before a DELAYED_RETRY
    delay_seconds: float = 1.5

    # Strategies to apply, in order
    strategies: List[RetryStrategy] = field(
        default_factory=lambda: [
            RetryStrategy.ALTERNATE_LABELS,
            RetryStrategy.DELAYED_RETRY,
            RetryStrategy.SCROLL_DOWN_RETRY,
            RetryStrategy.SCROLL_UP_RETRY,
            RetryStrategy.COORDINATE_FALLBACK,
            RetryStrategy.REOPEN_APP,
        ]
    )


# ─────────────────────────────────────────
# Label Variants Registry
# ─────────────────────────────────────────

# Common UI labels and their known synonyms.
# Extend this dict as Jarvis learns new UIs.
LABEL_VARIANTS: dict[str, list[str]] = {
    "search"  : ["Search", "Google", "Find", "URL", "Address", "🔍"],
    "open"    : ["Open", "Launch", "Start", "Run"],
    "close"   : ["Close", "Exit", "Quit", "X", "✕"],
    "submit"  : ["Submit", "Send", "Go", "OK", "Confirm", "Apply"],
    "cancel"  : ["Cancel", "Dismiss", "Back", "No"],
    "save"    : ["Save", "Save As", "Export", "Done"],
    "new"     : ["New", "Create", "Add", "+", "New Tab"],
    "settings": ["Settings", "Preferences", "Options", "⚙", "Config"],
    "menu"    : ["Menu", "☰", "≡", "More", "⋮", "Options"],
    "back"    : ["Back", "←", "Previous", "Return"],
    "next"    : ["Next", "→", "Continue", "Forward"],
    "home"    : ["Home", "🏠", "Start", "Main"],
    "refresh" : ["Refresh", "Reload", "↺", "F5"],
    "copy"    : ["Copy", "Ctrl+C", "Duplicate"],
    "paste"   : ["Paste", "Ctrl+V", "Insert"],
    "delete"  : ["Delete", "Remove", "Trash", "🗑", "Del"],
    "edit"    : ["Edit", "Modify", "Change", "Update", "Rename"],
    "file"    : ["File", "Files", "Folder", "Directory", "📁"],
    "upload"  : ["Upload", "Attach", "Browse", "Choose File"],
    "download": ["Download", "Save", "Export", "Get"],
    "login"   : ["Login", "Sign In", "Log In", "Enter"],
    "logout"  : ["Logout", "Sign Out", "Log Out"],
    "profile" : ["Profile", "Account", "User", "Me", "Avatar"],
    "help"    : ["Help", "?", "Support", "Docs"],
    "share"   : ["Share", "Send To", "Export", "Forward"],
}


def get_label_variants(
    query: str,
) -> list[str]:
    """
    Return alternate OCR labels to try for a given query.
    Falls back to capitalisation variants if not in registry.
    """

    key = query.lower()

    if key in LABEL_VARIANTS:
        return [
            v for v in LABEL_VARIANTS[key]
            if v != query          # skip exact match (already tried)
        ]

    # Generic capitalisation fallbacks
    return list(
        {
            query.lower(),
            query.upper(),
            query.capitalize(),
            query.title(),
        }
        - {query}                  # exclude the original
    )


# ─────────────────────────────────────────
# Action Type alias
# ─────────────────────────────────────────

# An async callable that accepts a query string and returns ToolResult.
ActionFn = Callable[[str], Awaitable[ToolResult]]


# ─────────────────────────────────────────
# RetryEngine
# ─────────────────────────────────────────

class RetryEngine:
    """
    Smart, adaptive retry engine for Jarvis tool calls.

    Usage
    -----
    engine = RetryEngine(screen_tools=tools, config=RetryConfig())
    result = await engine.run(
        query="Search",
        action=click_on_screen,
        app_name="chrome",
    )
    """

    def __init__(
        self,
        screen_tools,
        config: Optional[RetryConfig] = None,
    ):
        # Injected screen tools (avoids circular imports)
        self._tools  = screen_tools

        # Engine configuration
        self._config = config or RetryConfig()


    # ─────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────

    async def run(
        self,
        query: str,
        action: ActionFn,
        app_name: Optional[str] = None,
    ) -> ToolResult:
        """
        Execute `action(query)` with adaptive fallback.

        Parameters
        ----------
        query     : the UI label / OCR target string
        action    : async callable(query) → ToolResult
        app_name  : optional app name used for REOPEN_APP strategy
        """

        attempt = 0

        # ── First attempt ──────────────────
        result = await action(query)

        if result.succeeded:
            logger.info(
                "[retry_engine] Succeeded on first attempt: %s",
                query,
            )
            return result

        logger.warning(
            "[retry_engine] First attempt failed for '%s'. "
            "Starting adaptive recovery...",
            query,
        )

        # ── Adaptive strategy loop ─────────
        for strategy in self._config.strategies:

            if attempt >= self._config.max_attempts:
                logger.error(
                    "[retry_engine] Max attempts (%d) reached for '%s'.",
                    self._config.max_attempts,
                    query,
                )
                break

            attempt += 1

            logger.info(
                "[retry_engine] Applying strategy: %s (attempt %d/%d)",
                strategy.name,
                attempt,
                self._config.max_attempts,
            )

            result = await self._apply_strategy(
                strategy=strategy,
                query=query,
                action=action,
                app_name=app_name,
            )

            if result.succeeded:
                logger.info(
                    "[retry_engine] Recovered via %s for '%s'.",
                    strategy.name,
                    query,
                )
                return result

        # ── All strategies exhausted ───────
        logger.error(
            "[retry_engine] All strategies exhausted for '%s'.",
            query,
        )

        return ToolResult.fail(
            f"[RetryEngine] Could not recover '{query}' "
            f"after {attempt} adaptive attempts."
        )


    # ─────────────────────────────────────
    # Strategy dispatcher
    # ─────────────────────────────────────

    async def _apply_strategy(
        self,
        strategy: RetryStrategy,
        query: str,
        action: ActionFn,
        app_name: Optional[str],
    ) -> ToolResult:
        """
        Dispatch to the appropriate strategy handler.
        Each handler returns a ToolResult.
        """

        dispatch = {
            RetryStrategy.ALTERNATE_LABELS   : self._strategy_alternate_labels,
            RetryStrategy.DELAYED_RETRY      : self._strategy_delayed_retry,
            RetryStrategy.SCROLL_DOWN_RETRY  : self._strategy_scroll_down_retry,
            RetryStrategy.SCROLL_UP_RETRY    : self._strategy_scroll_up_retry,
            RetryStrategy.COORDINATE_FALLBACK: self._strategy_coordinate_fallback,
            RetryStrategy.REOPEN_APP         : self._strategy_reopen_app,
        }

        handler = dispatch.get(strategy)

        if handler is None:
            return ToolResult.fail(
                f"Unknown strategy: {strategy}"
            )

        return await handler(
            query=query,
            action=action,
            app_name=app_name,
        )


    # ─────────────────────────────────────
    # Strategy: Alternate Labels
    # ─────────────────────────────────────

    async def _strategy_alternate_labels(
        self,
        query: str,
        action: ActionFn,
        **_,
    ) -> ToolResult:
        """
        Try known synonym labels for the query.
        E.g. "Search" → ["Google", "Find", "URL", "Address"]
        """

        variants = get_label_variants(query)

        if not variants:
            return ToolResult.fail(
                f"No label variants found for '{query}'"
            )

        for variant in variants:

            logger.debug(
                "[retry_engine] Trying alternate label: '%s'",
                variant,
            )

            result = await action(variant)

            if result.succeeded:
                # Cache successful variant → original mapping
                # store the successful variant's coords if available
                cached = memory.get_ui(variant)
                if cached:
                    x, y = cached
                    memory.remember_ui(query, x, y)
                return result

        return ToolResult.fail(
            f"All alternate labels failed for '{query}'"
        )


    # ─────────────────────────────────────
    # Strategy: Delayed Retry
    # ─────────────────────────────────────

    async def _strategy_delayed_retry(
        self,
        query: str,
        action: ActionFn,
        **_,
    ) -> ToolResult:
        """
        Wait for the UI to settle, then retry the original action.
        Useful when animations or page loads are still in progress.
        """

        logger.debug(
            "[retry_engine] Waiting %.1fs before retry...",
            self._config.delay_seconds,
        )

        await asyncio.sleep(self._config.delay_seconds)

        return await action(query)


    # ─────────────────────────────────────
    # Strategy: Scroll Down + Retry
    # ─────────────────────────────────────

    async def _strategy_scroll_down_retry(
        self,
        query: str,
        action: ActionFn,
        **_,
    ) -> ToolResult:
        """
        Scroll down to reveal off-screen content, then retry.
        """

        logger.debug(
            "[retry_engine] Scrolling down and retrying '%s'...",
            query,
        )

        await self._tools.scroll_down()

        await asyncio.sleep(0.5)    # let scroll settle

        return await action(query)


    # ─────────────────────────────────────
    # Strategy: Scroll Up + Retry
    # ─────────────────────────────────────

    async def _strategy_scroll_up_retry(
        self,
        query: str,
        action: ActionFn,
        **_,
    ) -> ToolResult:
        """
        Scroll up to reveal off-screen content, then retry.
        """

        logger.debug(
            "[retry_engine] Scrolling up and retrying '%s'...",
            query,
        )

        await self._tools.scroll_up()

        await asyncio.sleep(0.5)    # let scroll settle

        return await action(query)


    # ─────────────────────────────────────
    # Strategy: Coordinate Fallback
    # ─────────────────────────────────────

    async def _strategy_coordinate_fallback(
        self,
        query: str,
        **_,
    ) -> ToolResult:
        """
        If memory has cached (x, y) for this query or a known
        variant, click directly without OCR.
        """

        import pyautogui  # local import — keeps dependency optional

        # ── Check query itself ─────────────
        cached = memory.get_ui(query)

        # ── Check all variants if needed ───
        if not cached:
            for variant in get_label_variants(query):
                cached = memory.get_ui(variant)
                if cached:
                    logger.debug(
                        "[retry_engine] Coordinate cache hit via variant '%s'",
                        variant,
                    )
                    break

        if not cached:
            return ToolResult.fail(
                f"No cached coordinates for '{query}' or its variants"
            )

        # ── Extract coordinates ────────────
        # memory.get_ui() returns a (x, y) tuple
        click_x, click_y = cached

        logger.debug(
            "[retry_engine] Clicking cached coords (%d, %d) for '%s'",
            click_x,
            click_y,
            query,
        )

        pyautogui.moveTo(
            click_x,
            click_y,
            duration=0.2,
        )

        pyautogui.doubleClick()

        return ToolResult.ok(
            f"[CoordFallback] Clicked cached position "
            f"({click_x}, {click_y}) for '{query}'"
        )


    # ─────────────────────────────────────
    # Strategy: Reopen App
    # ─────────────────────────────────────

    async def _strategy_reopen_app(
        self,
        query: str,
        action: ActionFn,
        app_name: Optional[str],
        **_,
    ) -> ToolResult:
        """
        Last-resort: reopen the target application and retry.
        Only fires when app_name is provided.
        """

        if not app_name:
            return ToolResult.fail(
                "REOPEN_APP strategy skipped: no app_name provided"
            )

        logger.warning(
            "[retry_engine] Reopening '%s' as last-resort recovery...",
            app_name,
        )

        # Attempt to launch via click_icon tool
        icon_result = await self._tools.click_icon(app_name)

        if not icon_result.succeeded:
            return ToolResult.fail(
                f"Could not reopen '{app_name}': {icon_result.error}"
            )

        # Wait for app to load before retrying
        await asyncio.sleep(2.5)

        return await action(query)
