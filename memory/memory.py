"""
memory/ — Three-layer memory system for Jarvis

1. short_term.py  — In-session conversation history (Python list, disappears on restart)
2. long_term.py   — Semantic vector memory (ChromaDB, persists across sessions)
3. episodic.py    — SQLite log of every command and outcome

This file contains all three for simplicity.
"""

# ─── SHORT-TERM MEMORY ─────────────────────────────────────────────────────────

class ShortTermMemory:
    """
    Keeps the last N conversation exchanges in memory.
    Used to give the LLM conversational context.
    """

    def __init__(self, max_exchanges: int = 10):
        self.max_exchanges = max_exchanges
        self._history: list[dict] = []

    def add(self, role: str, content: str):
        """
        Add a message to history.
        role: "user" or "assistant"
        """
        self._history.append({"role": role, "content": content})
        # Keep only last N exchanges (each exchange = 2 messages)
        max_messages = self.max_exchanges * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

    def get_history(self) -> list[dict]:
        """Return conversation history for LLM context."""
        return self._history.copy()

    def clear(self):
        """Clear session memory."""
        self._history.clear()

    def last_user_message(self) -> str:
        for msg in reversed(self._history):
            if msg["role"] == "user":
                return msg["content"]
        return ""


# ─── LONG-TERM MEMORY ──────────────────────────────────────────────────────────

class LongTermMemory:
    """
    Semantic memory using ChromaDB + sentence-transformers.
    Stores facts, preferences, and past interactions as embeddings.
    Retrieves relevant memories using vector similarity search.
    """

    def __init__(self, persist_path: str = "./data/chroma"):
        self.persist_path = persist_path
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            client = chromadb.PersistentClient(path=self.persist_path)
            self._collection = client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def remember(self, text: str, metadata: dict = None):
        """
        Store a memory.

        Examples:
            memory.remember("User prefers dark mode")
            memory.remember("User's work email is user@company.com")
            memory.remember("User opened Spotify at 9pm to play jazz")
        """
        import uuid
        from utils.logger import logger

        coll = self._get_collection()
        doc_id = str(uuid.uuid4())
        coll.add(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id],
        )
        logger.debug(f"Stored memory: '{text[:60]}'")

    def recall(self, query: str, n: int = 5) -> list[str]:
        """
        Retrieve the most relevant memories for a given query.

        Returns list of memory strings, most relevant first.
        """
        coll = self._get_collection()
        if coll.count() == 0:
            return []

        results = coll.query(
            query_texts=[query],
            n_results=min(n, coll.count()),
        )
        return results["documents"][0] if results["documents"] else []

    def forget(self, query: str):
        """Remove memories matching a query (approximate)."""
        memories = self.recall(query, n=3)
        # In production: implement proper deletion by ID


# ─── EPISODIC MEMORY ───────────────────────────────────────────────────────────

from datetime import datetime
from pathlib import Path


class EpisodicMemory:
    """
    SQLite log of every command Jarvis executed.
    Like a personal activity diary — searchable, persistent.
    """

    def __init__(self, db_path: str = "./data/jarvis.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        import sqlite3
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    user_text   TEXT,
                    action      TEXT,
                    target      TEXT,
                    outcome     TEXT,
                    success     INTEGER DEFAULT 1
                )
            """)
            conn.commit()

    def log(self, user_text: str, action: str, target: str = "", outcome: str = "", success: bool = True):
        """Log a command execution."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO episodes (timestamp, user_text, action, target, outcome, success) VALUES (?,?,?,?,?,?)",
                (datetime.now().isoformat(), user_text, action, target, outcome, int(success)),
            )
            conn.commit()

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search command history."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, user_text, action, target, outcome FROM episodes "
                "WHERE user_text LIKE ? OR action LIKE ? OR target LIKE ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        return [
            {"timestamp": r[0], "user_text": r[1], "action": r[2], "target": r[3], "outcome": r[4]}
            for r in rows
        ]

    def recent(self, n: int = 5) -> list[dict]:
        """Get the N most recent commands."""
        return self.search("", limit=n)


# ─── USER PREFERENCES ──────────────────────────────────────────────────────────

import json


class UserPreferences:
    """
    Persistent key-value store for user preferences.
    Stored as JSON — tiny, human-readable, always available.
    """

    def __init__(self, path: str = "./data/preferences.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _save(self):
        self.path.write_text(json.dumps(self._data, indent=2))

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def all(self) -> dict:
        return self._data.copy()
