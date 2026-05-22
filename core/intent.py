"""
core/intent.py — LLM Intent Parser
"""
import json
import os
from typing import Optional
from pydantic import BaseModel, Field
from utils.logger import logger
from utils.config import get, get_section


class Intent(BaseModel):
    action: str = Field(
        description=(
            "One of: open_app | open_website | web_search | send_email | "
            "send_whatsapp | type_text | click_element | take_screenshot | "
            "read_screen | play_music | set_reminder | run_script | "
            "system_command | run_workflow | answer_question | chitchat | unknown"
        )
    )
    target: Optional[str] = Field(None, description="App name, URL, recipient, or workflow name")
    query: Optional[str] = Field(None, description="Search query or message body")
    subject: Optional[str] = Field(None, description="Email subject line")
    parameters: dict = Field(default_factory=dict, description="Any extra structured params")
    confidence: float = Field(ge=0, le=1, description="How confident the model is (0-1)")
    plain_response: Optional[str] = Field(None, description="Direct answer for chitchat/questions")


def _build_system_prompt() -> str:
    workflows_section = get_section("workflows") or {}
    workflow_lines = ""
    if workflows_section:
        descriptions = [
            f'  - "{n}": {workflows_section[n].get("description", n)}'
            for n in workflows_section
        ]
        workflow_lines = (
            "\n\nKnown workflows (use action=run_workflow, target=<workflow_name>):\n"
            + "\n".join(descriptions)
        )

    return f"""You are Jarvis, an AI desktop assistant.

Your job is to parse user voice commands into structured JSON.

Rules:
1. Always respond with ONLY a JSON object — no markdown, no explanation.
2. Be generous in intent classification — prefer a specific action over "unknown".
3. For chitchat or knowledge questions, use action="answer_question" and put the answer in "plain_response".
4. Normalise app names: "vs code" -> "vscode", "chrome" -> "chrome", "notepad" -> "notepad".
5. Extract the core message for WhatsApp/email — clean it up, fix grammar.
6. For workflow triggers like "start coding mode", "study mode" -> use action="run_workflow" and put the workflow name in "target".{workflow_lines}

JSON Schema:
{{
  "action": "<action_name>",
  "target": "<app/url/recipient/workflow_name or null>",
  "query": "<search query / message body or null>",
  "subject": "<email subject or null>",
  "parameters": {{}},
  "confidence": 0.95,
  "plain_response": "<answer for questions, null otherwise>"
}}

Examples:
User: "open spotify"
-> {{"action":"open_app","target":"spotify","query":null,"subject":null,"parameters":{{}},"confidence":0.99,"plain_response":null}}

User: "start coding mode"
-> {{"action":"run_workflow","target":"coding_mode","query":null,"subject":null,"parameters":{{}},"confidence":0.97,"plain_response":null}}

User: "study mode"
-> {{"action":"run_workflow","target":"study_mode","query":null,"subject":null,"parameters":{{}},"confidence":0.96,"plain_response":null}}

User: "search for the weather in Bhopal"
-> {{"action":"web_search","target":null,"query":"weather in Bhopal","subject":null,"parameters":{{}},"confidence":0.97,"plain_response":null}}

User: "what is the capital of France"
-> {{"action":"answer_question","target":null,"query":"what is the capital of France","subject":null,"parameters":{{}},"confidence":0.99,"plain_response":"The capital of France is Paris."}}
"""


class IntentParser:
    def __init__(self):
        self.provider = get("ai", "provider", "openai")
        self.model = get("ai", "model", "gpt-4o")
        self.temperature = get("ai", "temperature", 0.2)
        self._client = None

    def _get_openai_client(self):
        if self._client is None:
            from openai import OpenAI
            api_key = get("ai", "openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("OpenAI API key not set.")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def parse(self, text: str, conversation_history: list[dict] = None) -> Intent:
        if not text.strip():
            return Intent(action="unknown", confidence=0.0)

        # ── FAST ROUTE — check rules before hitting LLM ───────────────────────
        from core.router import fast_route
        fast = fast_route(text)
        if fast:
            logger.info(f"Fast route: action={fast.action}, target={fast.target}")
            return fast
        # ── LLM fallback for everything else ──────────────────────────────────

        messages = [{"role": "system", "content": _build_system_prompt()}]
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": text})

        try:
            if self.provider == "openai":
                raw = self._call_openai(messages)
            elif self.provider == "ollama":
                raw = self._call_ollama(messages)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            data = json.loads(raw)
            intent = Intent(**data)
            logger.info(f"Intent: action={intent.action}, target={intent.target}, confidence={intent.confidence}")
            return intent

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}")
            return Intent(action="unknown", confidence=0.0)
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            return Intent(action="unknown", confidence=0.0)

    def _call_openai(self, messages: list) -> str:
        client = self._get_openai_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def _call_ollama(self, messages: list) -> str:
        import requests
        url = get("ai", "ollama_url", "http://localhost:11434") + "/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature},
        }
        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"]