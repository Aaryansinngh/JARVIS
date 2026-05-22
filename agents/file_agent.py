"""
agents/file_agent.py — Jarvis File Agent

Handles all file-related commands:
  "find my resume"           → searches common locations
  "organize my downloads"    → sorts by extension into subfolders
  "summarize this PDF"       → extracts text and sends to LLM
  "clean my desktop"         → moves files to organized locations
  "what's in my downloads?"  → lists recent files

Architecture:
  FileAgent exposes high-level async methods.
  Each method is also registered as a tool in the registry so
  workflows can call them like any other tool.
"""

from __future__ import annotations

import asyncio
import mimetypes
import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from tools.base import BaseTool, ToolMeta, ToolParam, ToolResult, registry


# ─── File Agent ───────────────────────────────────────────────────────────────

class FileAgent:
    """
    High-level file operations for Jarvis.

    Usage:
        agent = FileAgent()
        result = await agent.find_file("resume")
        result = await agent.organize_folder("~/Downloads")
    """

    # Where to look when searching
    SEARCH_ROOTS = [
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home() / "OneDrive",
        Path.home(),
    ]

    # Extension → folder mapping for organize_folder
    EXTENSION_MAP: dict[str, str] = {
        # Documents
        ".pdf":  "Documents/PDFs",
        ".docx": "Documents/Word",
        ".doc":  "Documents/Word",
        ".xlsx": "Documents/Excel",
        ".xls":  "Documents/Excel",
        ".pptx": "Documents/PowerPoint",
        ".ppt":  "Documents/PowerPoint",
        ".txt":  "Documents/Text",
        ".md":   "Documents/Markdown",
        # Images
        ".jpg":  "Images",
        ".jpeg": "Images",
        ".png":  "Images",
        ".gif":  "Images",
        ".webp": "Images",
        ".svg":  "Images/SVG",
        ".heic": "Images",
        # Videos
        ".mp4":  "Videos",
        ".mkv":  "Videos",
        ".mov":  "Videos",
        ".avi":  "Videos",
        # Audio
        ".mp3":  "Audio",
        ".wav":  "Audio",
        ".flac": "Audio",
        # Archives
        ".zip":  "Archives",
        ".rar":  "Archives",
        ".7z":   "Archives",
        ".tar":  "Archives",
        # Code
        ".py":   "Code/Python",
        ".js":   "Code/JavaScript",
        ".ts":   "Code/TypeScript",
        ".html": "Code/Web",
        ".css":  "Code/Web",
        ".json": "Code/Data",
        ".csv":  "Code/Data",
        # Installers
        ".exe":  "Installers",
        ".msi":  "Installers",
    }

    # ── Find ──────────────────────────────────────────────────────────────────

    async def find_file(
        self,
        query: str,
        max_results: int = 5,
        recent_days: Optional[int] = None,
    ) -> ToolResult:
        """
        Search for files by name across common locations.

        find_file("resume") → finds resume.pdf, My Resume.docx, etc.
        find_file("screenshot", recent_days=7) → recent screenshots only
        """
        query_lower = query.lower()
        found: list[dict] = []
        cutoff = None

        if recent_days:
            cutoff = datetime.now() - timedelta(days=recent_days)

        for root in self.SEARCH_ROOTS:
            if not root.exists():
                continue
            try:
                for path in root.rglob("*"):
                    if not path.is_file():
                        continue
                    if query_lower not in path.name.lower():
                        continue
                    if cutoff:
                        mtime = datetime.fromtimestamp(path.stat().st_mtime)
                        if mtime < cutoff:
                            continue
                    found.append({
                        "path": str(path),
                        "name": path.name,
                        "size_kb": round(path.stat().st_size / 1024, 1),
                        "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d"),
                    })
                    if len(found) >= max_results:
                        break
            except PermissionError:
                continue

        if not found:
            return ToolResult.fail(f"No files found matching '{query}'")

        # Sort by most recently modified
        found.sort(key=lambda x: x["modified"], reverse=True)
        return ToolResult.ok(found)

    # ── List recent files ─────────────────────────────────────────────────────

    async def list_recent_files(
        self,
        folder: str = "~/Downloads",
        days: int = 7,
        max_results: int = 20,
    ) -> ToolResult:
        """List files modified in the last N days in a folder."""
        root = Path(folder).expanduser()
        if not root.exists():
            return ToolResult.fail(f"Folder not found: {folder}")

        cutoff = time.time() - (days * 86400)
        files = []

        for path in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            if path.stat().st_mtime < cutoff:
                continue
            files.append({
                "name": path.name,
                "path": str(path),
                "size_kb": round(path.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "type": path.suffix.lstrip(".").upper() or "FILE",
            })
            if len(files) >= max_results:
                break

        if not files:
            return ToolResult.fail(f"No recent files in {folder}")

        return ToolResult.ok(files)

    # ── Organize ──────────────────────────────────────────────────────────────

    async def organize_folder(
        self,
        folder: str = "~/Downloads",
        dry_run: bool = False,
    ) -> ToolResult:
        """
        Sort files in a folder into subfolders by type.

        dry_run=True shows what WOULD happen without moving anything.
        """
        root = Path(folder).expanduser()
        if not root.exists():
            return ToolResult.fail(f"Folder not found: {folder}")

        moves: list[dict] = []
        errors: list[str] = []
        skipped = 0

        for path in root.iterdir():
            if not path.is_file():
                continue
            if path.name.startswith("."):
                skipped += 1
                continue

            ext = path.suffix.lower()
            subfolder = self.EXTENSION_MAP.get(ext, "Other")
            dest_dir = root / subfolder
            dest = dest_dir / path.name

            if dest == path:
                skipped += 1
                continue

            moves.append({"from": str(path), "to": str(dest), "type": subfolder})

            if not dry_run:
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    # Handle naming conflicts
                    if dest.exists():
                        stem = dest.stem
                        suffix = dest.suffix
                        counter = 1
                        while dest.exists():
                            dest = dest_dir / f"{stem}_{counter}{suffix}"
                            counter += 1
                    shutil.move(str(path), str(dest))
                except Exception as e:
                    errors.append(f"{path.name}: {e}")

        summary = {
            "moved": len(moves),
            "skipped": skipped,
            "errors": errors,
            "dry_run": dry_run,
            "moves": moves[:20],  # first 20 for display
        }
        return ToolResult.ok(summary)

    # ── Open file ─────────────────────────────────────────────────────────────

    async def open_file(self, path: str) -> ToolResult:
        """Open a file with its default application."""
        p = Path(path)
        if not p.exists():
            return ToolResult.fail(f"File not found: {path}")
        try:
            os.startfile(str(p))
            return ToolResult.ok(f"Opened {p.name}")
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", str(p)])
            return ToolResult.ok(f"Opened {p.name}")

    # ── Summarize (PDF / text) ────────────────────────────────────────────────

    async def summarize_file(
        self,
        path: str,
        llm_client=None,
        max_chars: int = 6000,
    ) -> ToolResult:
        """
        Extract text from a file and summarize it with the LLM.

        Supports: .txt, .md, .pdf, .py, .js, .html, .csv, .json
        Pass llm_client to get an actual AI summary; otherwise returns raw text.
        """
        p = Path(path)
        if not p.exists():
            return ToolResult.fail(f"File not found: {path}")

        # Extract text
        text = await self._extract_text(p, max_chars)
        if not text:
            return ToolResult.fail(f"Could not extract text from {p.name}")

        if llm_client is None:
            return ToolResult.ok({
                "file": p.name,
                "chars": len(text),
                "preview": text[:500],
                "note": "Pass llm_client for full AI summary",
            })

        # Summarize with LLM
        try:
            prompt = f"Summarize this document concisely:\n\n{text}"
            summary = await llm_client.complete(prompt)
            return ToolResult.ok({"file": p.name, "summary": summary})
        except Exception as e:
            return ToolResult.fail(f"LLM summarization failed: {e}")

    async def _extract_text(self, path: Path, max_chars: int) -> Optional[str]:
        ext = path.suffix.lower()

        if ext == ".pdf":
            return await self._extract_pdf(path, max_chars)

        if ext in {".txt", ".md", ".py", ".js", ".ts", ".html", ".css",
                   ".json", ".csv", ".toml", ".yaml", ".yml"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                return text[:max_chars]
            except Exception:
                return None

        return None

    async def _extract_pdf(self, path: Path, max_chars: int) -> Optional[str]:
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    chunk = page.extract_text() or ""
                    text_parts.append(chunk)
                    if sum(len(t) for t in text_parts) >= max_chars:
                        break
            return "\n".join(text_parts)[:max_chars]
        except ImportError:
            pass

        try:
            import PyPDF2
            text_parts = []
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text_parts.append(page.extract_text() or "")
                    if sum(len(t) for t in text_parts) >= max_chars:
                        break
            return "\n".join(text_parts)[:max_chars]
        except ImportError:
            return None

    # ── Delete with safety ────────────────────────────────────────────────────

    async def move_to_trash(self, path: str) -> ToolResult:
        """Move a file to trash instead of permanently deleting it."""
        p = Path(path)
        if not p.exists():
            return ToolResult.fail(f"File not found: {path}")
        try:
            import send2trash
            send2trash.send2trash(str(p))
            return ToolResult.ok(f"Moved {p.name} to trash")
        except ImportError:
            return ToolResult.fail("send2trash not installed (pip install send2trash)")


# ─── Register file agent tools ────────────────────────────────────────────────

class FindFileTool(BaseTool):
    meta = ToolMeta(
        name="find_file",
        description="Search for files by name across the computer",
        params=[
            ToolParam("query", "str", "Filename or keyword to search for"),
            ToolParam("recent_days", "int", "Only files modified in last N days", required=False, default=None),
        ],
        tags=["file", "search"],
    )

    def __init__(self):
        self._agent = FileAgent()

    async def run(self, query: str, recent_days: int = None) -> ToolResult:
        return await self._agent.find_file(query, recent_days=recent_days)


class OrganizeFolderTool(BaseTool):
    meta = ToolMeta(
        name="organize_folder",
        description="Sort files in a folder into subfolders by type",
        params=[
            ToolParam("folder", "str", "Folder to organize (default: Downloads)", required=False, default="~/Downloads"),
            ToolParam("dry_run", "bool", "Preview without moving files", required=False, default=False),
        ],
        tags=["file", "organize"],
        requires_confirmation=True,
    )

    def __init__(self):
        self._agent = FileAgent()

    async def run(self, folder: str = "~/Downloads", dry_run: bool = False) -> ToolResult:
        return await self._agent.organize_folder(folder, dry_run=dry_run)


class ListRecentFilesTool(BaseTool):
    meta = ToolMeta(
        name="list_recent_files",
        description="List files modified recently in a folder",
        params=[
            ToolParam("folder", "str", "Folder to list", required=False, default="~/Downloads"),
            ToolParam("days", "int", "How many days back to look", required=False, default=7),
        ],
        tags=["file"],
    )

    def __init__(self):
        self._agent = FileAgent()

    async def run(self, folder: str = "~/Downloads", days: int = 7) -> ToolResult:
        return await self._agent.list_recent_files(folder, days=days)


class OpenFileTool(BaseTool):
    meta = ToolMeta(
        name="open_file",
        description="Open a file with its default application",
        params=[ToolParam("path", "str", "Full path to the file")],
        tags=["file"],
    )

    def __init__(self):
        self._agent = FileAgent()

    async def run(self, path: str) -> ToolResult:
        return await self._agent.open_file(path)


class SummarizeFileTool(BaseTool):
    meta = ToolMeta(
        name="summarize_file",
        description="Extract and summarize the content of a file (PDF, text, code)",
        params=[ToolParam("path", "str", "Full path to the file")],
        tags=["file", "ai", "summarize"],
    )

    def __init__(self):
        self._agent = FileAgent()

    async def run(self, path: str) -> ToolResult:
        return await self._agent.summarize_file(path)


def load_file_agent_tools() -> None:
    """Register all file agent tools into the global registry."""
    tools = [
        FindFileTool(),
        OrganizeFolderTool(),
        ListRecentFilesTool(),
        OpenFileTool(),
        SummarizeFileTool(),
    ]
    registry.register_many(tools)
    logger.info(f"Loaded {len(tools)} file agent tools")
