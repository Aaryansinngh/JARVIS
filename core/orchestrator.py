"""
core/orchestrator.py — The Central Brain of Jarvis
"""
from utils.logger import logger
from utils.config import get
from core.intent import IntentParser, Intent
from voice.speaker import Speaker
from automation.app_launcher import AppLauncher
from automation.browser import BrowserController
from automation.messaging import WhatsAppSender, EmailSender
from automation.desktop import DesktopController
from automation.screen_reader import ScreenReader
from memory.memory import ShortTermMemory, LongTermMemory, EpisodicMemory, UserPreferences
from safety.guardrails import SafetyGuard
from rich.console import Console

console = Console()


class Orchestrator:
    def __init__(self):
        logger.info("Initialising Jarvis Orchestrator...")
        self.name = get("assistant", "name", "Jarvis")

        self.intent_parser = IntentParser()
        self.speaker = Speaker()

        self._launcher  = None
        self._browser   = None
        self._whatsapp  = None
        self._email     = None
        self._desktop   = None
        self._screen    = None
        self._workflow  = None

        self.short_mem = ShortTermMemory(max_exchanges=get("memory", "context_window", 10))
        self.long_mem  = LongTermMemory(get("memory", "chroma_path", "./data/chroma"))
        self.episodes  = EpisodicMemory(get("memory", "sqlite_path", "./data/jarvis.db"))
        self.prefs     = UserPreferences()
        self.guard     = SafetyGuard()

        logger.info(f"{self.name} ready.")

    # ── Lazy loaders ──────────────────────────────────────────────────────────

    @property
    def launcher(self) -> AppLauncher:
        if self._launcher is None:
            self._launcher = AppLauncher()
        return self._launcher

    @property
    def browser(self) -> BrowserController:
        if self._browser is None:
            self._browser = BrowserController(headless=False)
        return self._browser

    @property
    def whatsapp(self) -> WhatsAppSender:
        if self._whatsapp is None:
            self._whatsapp = WhatsAppSender()
        return self._whatsapp

    @property
    def email(self) -> EmailSender:
        if self._email is None:
            self._email = EmailSender()
        return self._email

    @property
    def desktop(self) -> DesktopController:
        if self._desktop is None:
            self._desktop = DesktopController()
        return self._desktop

    @property
    def screen(self) -> ScreenReader:
        if self._screen is None:
            self._screen = ScreenReader()
        return self._screen

    @property
    def workflow(self):
        if self._workflow is None:
            from automation.workflow import WorkflowEngine
            self._workflow = WorkflowEngine(self.launcher, self.speaker)
        return self._workflow

    # ── Main entry point ──────────────────────────────────────────────────────

    def process(self, user_text: str) -> str:
        if not user_text.strip():
            return ""

        console.print(f"\n[bold cyan]You:[/bold cyan] {user_text}")
        self.short_mem.add("user", user_text)

        intent = self.intent_parser.parse(
            user_text,
            conversation_history=self.short_mem.get_history()[:-1],
        )

        response = self._execute(intent, user_text)

        self.short_mem.add("assistant", response)
        self.episodes.log(
            user_text=user_text,
            action=intent.action,
            target=intent.target or "",
            outcome=response[:100],
        )

        console.print(f"[bold green]{self.name}:[/bold green] {response}")
        self.speaker.speak(response)
        return response

    # ── Action Router ─────────────────────────────────────────────────────────

    def _execute(self, intent: Intent, raw_text: str) -> str:
        action = intent.action

        if action in ("answer_question", "chitchat"):
            return intent.plain_response or self._llm_answer(raw_text)

        elif action == "open_app":
            target = intent.target or ""
            if not self.guard.approve("open_app", target, f"Opening: {target}"):
                return "Action cancelled."
            success = self.launcher.open(target)
            return f"Opening {target}." if success else f"I couldn't find {target}. Is it installed?"

        elif action == "open_website":
            url = intent.target or intent.query or ""
            if not self.guard.approve("open_website", url, f"Opening: {url}"):
                return "Action cancelled."
            self.launcher.open_url(url)
            return f"Opening {url}."

        elif action == "web_search":
            query = intent.query or intent.target or raw_text
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            self.launcher.open_url(url)
            return f"Searching for: {query}"

        elif action == "run_workflow":
            name = intent.target or ""
            if not name:
                available = ", ".join(self.workflow.list_workflows())
                return f"Which workflow? Available: {available}"
            return self.workflow.run(name)

        elif action == "send_whatsapp":
            contact = intent.target or ""
            message = intent.query or ""
            if not contact or not message:
                return "I need both a contact name and a message."
            if not self.guard.approve("send_whatsapp", contact, f"Message: {message}"):
                return "Message cancelled."
            success = self.whatsapp.send_by_name(contact, message)
            return f"WhatsApp sent to {contact}." if success else f"Failed to send WhatsApp to {contact}."

        elif action == "send_email":
            to = intent.target or ""
            subject = intent.subject or "Message from Jarvis"
            body = intent.query or ""
            if not to or not body:
                return "I need a recipient and message."
            if not self.guard.approve("send_email", to, f"Subject: {subject}"):
                return "Email cancelled."
            success = self.email.send(to, subject, body)
            return f"Email sent to {to}." if success else f"Failed to send email to {to}."

        elif action == "take_screenshot":
            path = self.desktop.screenshot()
            return f"Screenshot saved to {path}."

        elif action == "read_screen":
            question = intent.query or "What is on the screen?"
            return self.screen.describe_screen(question)

        elif action == "type_text":
            text = intent.query or ""
            if text:
                self.desktop.type_text(text)
                return f"Typed: {text[:40]}"
            return "What should I type?"

        elif action == "system_command":
            cmd = intent.query or ""
            if not self.guard.is_safe_command(cmd):
                return "That command looks dangerous. I won't run it."
            if not self.guard.approve("run_script", "", f"Command: {cmd}"):
                return "Cancelled."
            import subprocess
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                return result.stdout[:200] or "Command executed."
            except Exception as e:
                return f"Command failed: {e}"

        else:
            return self._llm_answer(raw_text)

    def _llm_answer(self, question: str) -> str:
        import os
        from openai import OpenAI
        api_key = get("ai", "openai_api_key", "") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return "I'm not sure how to handle that. Try giving me a clearer command."
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=get("ai", "model", "gpt-4o"),
            messages=[
                {"role": "system", "content": f"You are {self.name}, a helpful desktop assistant. Be concise."},
                *self.short_mem.get_history()[-6:],
            ],
            max_tokens=300,
        )
        return resp.choices[0].message.content