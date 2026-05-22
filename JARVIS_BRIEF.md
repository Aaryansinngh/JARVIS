# 🤖 JARVIS — Full Project Brief (Updated)

---

## ✅ Phase 1 — MVP (Complete)

Built a local AI desktop assistant running on Windows with Python.

- Voice pipeline: Whisper STT → pyttsx3 TTS → wake word detection
- App launcher: open/close Chrome, VSCode, Spotify, Discord, etc.
- Web search: opens Google with query in browser
- Desktop automation: PyAutoGUI for typing, hotkeys, screenshots
- Browser automation: Playwright for URL navigation
- Messaging: WhatsApp Web automation + Gmail API
- Memory: short-term context + ChromaDB vector store + SQLite episodic memory
- Safety: confirmation prompts, rate limiter, audit log
- UI: system tray icon via pystray
- Config: everything in config.toml
- LLM: Ollama (Phi3, local) or OpenAI GPT-4o

---

## ✅ Phase 2 — Smarter Architecture (Complete)

Evolved Jarvis from a command launcher into a proper AI copilot architecture.

**Tool Registry** (`tools/base.py`, `tools/builtin.py`)
Every capability is a self-describing, retryable, timeout-aware Tool object
registered in a central ToolRegistry. Adding a new capability takes 5 minutes.

**Workflow Engine** (`workflows/engine.py`, `workflows/builtin.py`)
Multi-step task execution with context passing, conditional branching,
abort-on-failure, and retry logic. TOML workflows load automatically.
Modes: coding_mode, study_mode, morning_routine, focus_mode, internship_hunt, etc.

**File Agent** (`agents/file_agent.py`)
Find files by name across the entire computer, list recent downloads,
organize Downloads folder by type, open files, extract text from PDFs.

**Event Bus** (`events/bus.py`)
Async pub/sub system that decouples all components. Every action emits
an event — the hook point for overlays, notifications, plugins in Phase 3+.

**Orchestrator v2** (`core/orchestrator_v2.py`)
New brain. Fast rule-based routing first (no LLM needed for simple commands),
falls through to Ollama for complex intent, maintains conversation history.

**Ollama Client** (`llm/ollama_client.py`)
Clean async REST client for Ollama with chat and completion support.

---

## ✅ Phase 3 — Browser Agent (Complete)

Jarvis now controls the browser like a human, not just opens URLs.

**Browser Agent** (`automation/browser_agent.py`)
Full Playwright wrapper with 13 high-level actions:
navigate, search, click, fill, fill_form, extract_text, extract_links,
screenshot, scroll, wait_for, back, forward, get_page_summary.

**Browser Tools** (`tools/browser_tools.py`)
All 13 browser actions registered as Tools in the ToolRegistry.
Plugs directly into the WorkflowEngine and Orchestrator.

**Browser Workflows** (`workflows/browser_workflows.py`)
Pre-built workflows: google_search, youtube_search, linkedin_jobs,
internship_search, open_and_summarize, browser_capture.

**Browser Router** (`core/browser_router.py`)
17 natural language patterns, zero LLM needed:
  - "search for X" → Google search
  - "play X on youtube" → YouTube search
  - "go to / navigate to URL" → browser navigate
  - "find internships for X" → opens Internshala + LinkedIn + Wellfound
  - "search linkedin for X" → LinkedIn jobs
  - "summarize this page" → extract + read page content
  - "click on X" → click element by text
  - "scroll down/up/top/bottom" → page scroll
  - "take a browser screenshot" → save screenshot

**Test suite** (`test_browser_agent.py`)
17/17 offline routing tests + live browser tests (navigate, search, extract).

---

## 🔜 Phase 4 — Intelligence Layer (Next)

### Screen Understanding
Jarvis reads what's on your screen using GPT-4o Vision or local OCR.
Commands: "what's on my screen", "summarize this page", "fill in this form".
Builds on existing `screen_reader.py` + new `agents/screen_agent.py`.

### Overlay UI
A floating transparent HUD that appears when Jarvis activates.
Shows: what it heard → what it's doing → result.
Built with CustomTkinter. Subscribes to the EventBus so it reacts automatically.
No polling — pure event-driven updates.

### Windows Toast Notifications
Background notifications for completed workflows using winotify.
"Your downloads are organized — 47 files moved."
"Internship boards are open. Good luck."

### Parallel Workflow Steps
WorkflowEngine gains a `parallel=True` flag so multiple apps open
simultaneously instead of sequentially. Cuts workflow time by 60%.

---

## 🔮 Phase 5 — Autonomous Agent (Future)

### Multi-step Planning
Jarvis receives a high-level goal and plans the steps itself.
"Prepare my internship application for Google" →
find resume → open it → check LinkedIn → draft cover letter → attach everything.
Uses a task graph where each node is a Tool call and edges are dependencies.

### Background Monitoring
Jarvis runs silently watching for triggers:
"remind me when it's 6pm"
"alert me if battery drops below 20%"
"tell me when a new email from boss arrives"
Built on the EventBus with scheduled async tasks.

### Plugin Architecture
Third-party skills that drop into `agents/` and self-register.
Anyone can add a Jarvis capability without touching core code.

### Memory Upgrade
ChromaDB vector search so Jarvis remembers past conversations,
your preferences, frequently used workflows.
"What did I work on last Tuesday?"

---

## 🚀 Phase 6 — End Goal

A fully autonomous AI operating system layer on your Windows machine.
Voice-first, always listening, proactively helpful.
Knows your schedule, your files, your habits.
Executes 20-step tasks without supervision.
Beautiful overlay UI. Works 100% locally, no cloud dependency.
Not a chatbot — an agent that actually does things.

---

## 🏗️ Current Project Structure

```
jarvis/
├── main.py                    ← Entry point
├── config.toml                ← All settings
├── requirements.txt
├── test_phase2.py             ← Phase 2 tests (all passing)
├── test_browser_agent.py      ← Phase 3 tests (17/17 passing)
│
├── core/
│   ├── orchestrator_v2.py     ← Central brain (Phase 2+3)
│   ├── browser_router.py      ← Browser intent routing (Phase 3) ← NEW
│   ├── intent.py
│   └── router.py
│
├── automation/
│   ├── browser_agent.py       ← Playwright wrapper (Phase 3) ← NEW
│   ├── browser.py
│   ├── app_launcher.py
│   ├── desktop.py
│   ├── messaging.py
│   └── screen_reader.py
│
├── tools/
│   ├── base.py                ← ToolRegistry (Phase 2)
│   ├── builtin.py             ← 10 built-in tools (Phase 2)
│   └── browser_tools.py       ← 13 browser tools (Phase 3) ← NEW
│
├── workflows/
│   ├── engine.py              ← WorkflowEngine (Phase 2)
│   ├── builtin.py             ← Built-in workflows (Phase 2+3)
│   └── browser_workflows.py   ← Browser workflows (Phase 3) ← NEW
│
├── agents/
│   └── file_agent.py          ← File operations (Phase 2)
│
├── events/
│   └── bus.py                 ← EventBus (Phase 2)
│
├── llm/
│   └── ollama_client.py       ← Ollama REST client (Phase 2)
│
├── voice/
│   ├── listener.py
│   ├── transcriber.py
│   ├── wake_word.py
│   └── speaker.py
│
├── memory/
│   └── memory.py
│
├── safety/
│   └── guardrails.py
│
└── ui/
    └── tray.py
```

---

## 🧰 Current Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| LLM         | Ollama + Phi3 (local), GPT-4o opt.  |
| Voice in    | Whisper (local STT)                 |
| Voice out   | pyttsx3 / ElevenLabs                |
| Browser     | Playwright (Phase 1 URLs + Phase 3 agent) |
| Desktop     | PyAutoGUI + pywinauto               |
| Memory      | ChromaDB + SQLite                   |
| Messaging   | WhatsApp Web + Gmail API            |
| UI          | CustomTkinter + pystray             |
| Config      | TOML                                |
| Events      | Custom async EventBus               |
| Tools       | Custom ToolRegistry (23 tools)      |
| Workflows   | Custom WorkflowEngine (13 workflows)|
