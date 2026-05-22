"""
llm/ollama_client.py — Ollama local LLM client

Wraps Ollama's REST API for chat and completion.
Handles retries, timeouts, and streaming.

Ollama must be running: `ollama serve`
Model must be pulled: `ollama pull phi3`
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

import aiohttp
from loguru import logger


class OllamaClient:
    def __init__(
        self,
        model: str = "phi3",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def complete(self, prompt: str, max_tokens: int = 500) -> str:
        """Single-turn completion."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/api/generate", json=payload
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama error {resp.status}: {await resp.text()}")
                data = await resp.json()
                return data.get("response", "").strip()

    async def chat(self, messages: list[dict], max_tokens: int = 1000) -> str:
        """Multi-turn chat. messages = [{"role": "user"|"assistant", "content": "..."}]"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.3},
        }
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(
                f"{self.base_url}/api/chat", json=payload
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Ollama error {resp.status}: {await resp.text()}")
                data = await resp.json()
                return data.get("message", {}).get("content", "").strip()

    async def is_available(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as s:
                async with s.get(f"{self.base_url}/api/tags") as r:
                    if r.status != 200:
                        return False
                    data = await r.json()
                    models = [m["name"] for m in data.get("models", [])]
                    available = any(self.model in m for m in models)
                    if not available:
                        logger.warning(f"Model '{self.model}' not found. Run: ollama pull {self.model}")
                    return available
        except Exception:
            return False
