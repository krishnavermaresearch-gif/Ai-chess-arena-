# AI Arena ♟️🤖

**A lightweight, local-first chess platform where AI models play against each other — or you.**

Type any model name (OpenAI, Claude, Gemini, Grok, or local Ollama) and watch them battle. The backend uses native Python heuristics to evaluate positions, filter repetitions, and categorize moves — so even small LLMs play fast and clean.

## Features

- **Multi-provider AI** — OpenAI, Anthropic, Google Gemini, xAI Grok, and local Ollama
- **AI vs AI / Human vs AI** — Choose player types per side
- **Native heuristics** — Material evaluation, move categorization, anti-repetition filtering
- **Performance tracking** — Win/loss/draw stats per model saved to `stats.json`
- **In-app settings** — Paste API keys directly from the browser UI (⚙ Settings)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download frontend assets
python download_assets.py

# 3. Run the server
python main.py
# → Open http://localhost:8000
```

## API Keys

**Option A:** Click ⚙ Settings in the app UI and paste your keys.

**Option B:** Copy `.env.example` → `.env` and fill in your keys:
```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIzaSy...
XAI_API_KEY=xai-...
```

## Desktop App

```bash
# Run as a native desktop window (requires pywebview)
python desktop.py
```

## Build Standalone .exe

```bash
# Package into a standalone app (no Python needed on target PC)
python build.py
# → Output: dist/AIArena/AIArena.exe
```

## Project Structure

```
├── main.py              # FastAPI backend + AI routing + chess heuristics
├── desktop.py           # Native desktop launcher (pywebview)
├── build.py             # PyInstaller build script
├── download_assets.py   # Downloads frontend vendor libraries
├── index.html           # Main UI
├── style.css            # Styles
├── script.js            # Frontend game logic
├── requirements.txt     # Python dependencies
├── .env.example         # API key template
└── .gitignore
```
