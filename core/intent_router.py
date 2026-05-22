"""
core/intent_router.py

Lightweight intent router for Jarvis.
"""

from __future__ import annotations

import re


class IntentRouter:

    def route(self, text: str) -> dict:

        t = text.lower().strip()

        # =====================================================
        # OPEN APP
        # =====================================================

        if "open" in t:

            match = re.search(
                r"open\s+(.*?)(?:\s+for me)?$",
                t
            )

            app = match.group(1).strip() if match else "chrome"

            app = (
                app
                .replace("please", "")
                .replace("can you", "")
                .replace("could you", "")
                .replace("jarvis", "")
                .strip()
            )

            return {
                "intent": "open_app",
                "app": app,
            }

        # =====================================================
        # YOUTUBE SEARCH
        # =====================================================

        if "youtube" in t and "search" not in t:

            query = (
                t
                .replace("search youtube for", "")
                .replace("youtube", "")
                .replace("search", "")
                .strip()
            )

            return {
                "intent": "youtube_search",
                "query": query,
            }

        # =====================================================
        # WEB SEARCH
        # =====================================================

        if "search" in t:

            query = (
                t
                .replace("search for", "")
                .replace("search", "")
                .strip()
            )

            return {
                "intent": "web_search",
                "query": query,
            }

        # =====================================================
        # FALLBACK
        # =====================================================

        return {
            "intent": "unknown",
            "text": text,
        }