# 🤖 JARVIS — AI Desktop Assistant

A voice-controlled, LLM-powered desktop assistant for Windows.
Built with Python. Modular, extensible, production-ready.

```
Say "Jarvis" → Speak → Jarvis acts on your laptop
```

---

## ✅ What It Can Do (Out of the Box)

| Command | What Happens |
|---------|-------------|
| "Open Chrome" | Launches Chrome |
| "Search for weather in Bhopal" | Opens Google with your search |
| "Open YouTube and play lofi music" | Opens YouTube and plays |
| "Send WhatsApp to Rahul saying I'll be late" | Sends the message via WhatsApp Web |
| "Send email to boss@company.com — the report is ready" | Sends via Gmail |
| "Take a screenshot" | Captures and saves your screen |
| "What's on my screen?" | GPT-4o Vision reads your screen |
| "Type hello world" | Types text at the cursor |
| "What is the capital of France?" | Answers directly |

---

## 🚀 Quick Start (5 Minutes)

### Step 1 — Install Python dependencies

```bash
cd jarvis
pip install -r requirements.txt
```

### Step 2 — Install Playwright browsers

```bash
playwright install chromium
```

### Step 3 — Set your OpenAI API key

```bash
# Windows
set OPENAI_API_KEY=sk-your-key-here

# Or add it to config.toml:
# [ai]
# openai_api_key = "sk-your-key-here"
```

Get a key at: https://platform.openai.com

### Step 4 — Run in text mode (no mic needed for testing)

```bash
python main.py --text
```

### Step 5 — Run in voice mode

```bash
python main.py
```

Say **"Jarvis"** or press **Ctrl+Space** to activate.

---

## 🔧 Configuration

Edit `config.toml` to customise everything:

```toml
[assistant]
name = "Jarvis"
wake_word = "jarvis"

[ai]
provider = "openai"        # or "ollama" for free local AI
model = "gpt-4o"
openai_api_key = "sk-..."

[voice]
whisper_model = "base"    # tiny/base/small/medium/large
```

---

## 🆓 Using Ollama (Free, 100% Offline)

1. Install Ollama: https://ollama.ai
2. Download a model: `ollama pull llama3`
3. Change config.toml:
   ```toml
   [ai]
   provider = "ollama"
   model = "llama3"
   ```

---

## 📧 Gmail API Setup

1. Go to https://console.cloud.google.com
2. Create a new project → Enable **Gmail API**
3. Create **OAuth2 credentials** → Download as `credentials.json`
4. Move to `./credentials/gmail_credentials.json`
5. First run: a browser window opens to authorise → done

---

## 💬 WhatsApp Setup

1. Open Chrome → go to https://web.whatsapp.com
2. Scan QR code with your phone → stay logged in
3. Jarvis will use this session to send messages

---

## 🏗️ Project Structure

```
jarvis/
├── main.py              ← Entry point (run this)
├── config.toml          ← All settings
├── requirements.txt
├── core/
│   ├── orchestrator.py  ← Central brain
│   └── intent.py        ← LLM intent parser
├── voice/
│   ├── listener.py      ← Mic + VAD
│   ├── transcriber.py   ← Whisper STT
│   ├── wake_word.py     ← "Hey Jarvis" detection
│   └── speaker.py       ← TTS output
├── automation/
│   ├── app_launcher.py  ← Open/close apps
│   ├── browser.py       ← Playwright web control
│   ├── messaging.py     ← WhatsApp + Gmail
│   ├── desktop.py       ← PyAutoGUI mouse/keyboard
│   └── screen_reader.py ← GPT-4o Vision
├── memory/
│   └── memory.py        ← Short/long-term/episodic memory
├── safety/
│   └── guardrails.py    ← Confirmations, rate limiting, audit log
└── ui/
    └── tray.py          ← System tray icon
```

---

## 🛡️ Safety Features

- **Confirmation prompts** before sending messages, emails, or running scripts
- **Rate limiter** (10 actions/minute max)
- **Audit log** of every action at `./data/audit.log`
- **Command allow-list** — dangerous shell commands blocked
- **Failsafe**: move mouse to top-left corner to abort PyAutoGUI

---

## 📦 Package as .exe (Windows)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=icon.ico main.py
```

The `.exe` appears in `./dist/main.exe`.

---

## 🔮 Roadmap

### Phase 1 — MVP (Now) ✅
- [x] Voice → Whisper → LLM → action
- [x] App launching, web search, screenshots
- [x] WhatsApp and email
- [x] Safety guardrails
- [x] Memory system

### Phase 2 — Smarter (Next)
- [ ] Multi-step task planning ("open chrome, go to gmail, find emails from boss")
- [ ] Wake word with Porcupine (no key press needed)
- [ ] ElevenLabs premium voice
- [ ] OmniParser for precise UI element detection

### Phase 3 — Power User
- [ ] Custom skills/plugins system
- [ ] Calendar integration (Google Calendar API)
- [ ] Proactive reminders
- [ ] Full system tray GUI with conversation history
- [ ] Multi-monitor support

---

## ❓ Troubleshooting

**"No module named sounddevice"**
→ `pip install sounddevice`

**"Whisper download is slow"**
→ First run downloads the model. Subsequent runs are instant.

**"WhatsApp not sending"**
→ Make sure you're logged in to web.whatsapp.com in Chrome first.

**"OpenAI API error"**
→ Check your API key in config.toml or OPENAI_API_KEY env variable.

**"PyAutoGUI failsafe triggered"**
→ You moved the mouse to the top-left corner, which is the abort hotkey.
