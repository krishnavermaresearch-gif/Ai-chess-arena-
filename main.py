"""
AI Arena — Backend Server
FastAPI application with native Python chess heuristics and multi-provider AI routing.
"""

# ── Imports ──────────────────────────────────────────────────────
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import chess
import requests
import traceback
import os
import asyncio
import json
from dotenv import load_dotenv

# ── App Init ─────────────────────────────────────────────────────
load_dotenv()
app = FastAPI(title="AI Arena")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static/vendor", exist_ok=True)
app.mount("/static/vendor", StaticFiles(directory="static/vendor"), name="vendor")


# ══════════════════════════════════════════════════════════════════
#  STATIC FILE ROUTES
# ══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serve the main HTML page with no-cache headers."""
    with open("index.html", "r", encoding="utf-8") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"},
    )

@app.get("/style.css")
async def get_style():
    return FileResponse("style.css", media_type="text/css")

@app.get("/script.js")
async def get_script():
    return FileResponse("script.js", media_type="application/javascript")

@app.get("/health")
async def health():
    return {"status": "ok"}


# ══════════════════════════════════════════════════════════════════
#  API: SETTINGS (Save API Keys from UI)
# ══════════════════════════════════════════════════════════════════

@app.post("/api/settings")
async def save_settings(request: Request):
    """Save API keys to .env and hot-reload them into os.environ."""
    data = await request.json()
    key_map = {
        "OPENAI_API_KEY":    data.get("openai", ""),
        "ANTHROPIC_API_KEY": data.get("anthropic", ""),
        "GEMINI_API_KEY":    data.get("gemini", ""),
        "XAI_API_KEY":       data.get("xai", ""),
    }

    env_path = os.path.join(os.path.dirname(__file__) or ".", ".env")
    existing = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()

    for k, v in key_map.items():
        if v.strip():
            existing[k] = v.strip()
            os.environ[k] = v.strip()

    with open(env_path, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    return {"success": True, "message": "API keys saved and loaded!"}


# ══════════════════════════════════════════════════════════════════
#  API: GAME REPORT (Performance Tracking)
# ══════════════════════════════════════════════════════════════════

@app.post("/api/report")
async def report_game(request: Request):
    """Record win/loss/draw stats per model into stats.json."""
    data = await request.json()
    stats_file = "stats.json"

    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            stats = json.load(f)
    else:
        stats = {}

    wm = data.get("whiteModel", "unknown")
    bm = data.get("blackModel", "unknown")
    winner = data.get("winner")

    for model in (wm, bm):
        if model not in stats:
            stats[model] = {"wins": 0, "losses": 0, "draws": 0, "games": 0}

    stats[wm]["games"] += 1
    stats[bm]["games"] += 1

    if winner == "white":
        stats[wm]["wins"] += 1
        stats[bm]["losses"] += 1
    elif winner == "black":
        stats[bm]["wins"] += 1
        stats[wm]["losses"] += 1
    else:
        stats[wm]["draws"] += 1
        stats[bm]["draws"] += 1

    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=4)

    return {"success": True, "stats": stats}


# ══════════════════════════════════════════════════════════════════
#  CHESS ENGINE: Native Python Heuristics
# ══════════════════════════════════════════════════════════════════

def check_game_over(board: chess.Board):
    """Return (is_over, reason). Called before AND after each move."""
    if board.is_checkmate():
        loser = "White" if board.turn == chess.WHITE else "Black"
        return True, f"Checkmate — {loser} loses"
    if board.is_stalemate():
        return True, "Draw by stalemate"
    if board.is_insufficient_material():
        return True, "Draw — insufficient material"
    if board.is_seventyfive_moves():
        return True, "Draw — 75-move rule"
    if board.is_fivefold_repetition():
        return True, "Draw — fivefold repetition"
    if board.can_claim_draw():
        return True, "Draw available (50-move / threefold repetition)"
    return False, ""


def evaluate_material(board: chess.Board) -> int:
    """Return material score from White's perspective (positive = White ahead)."""
    piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    white = sum(len(board.pieces(p, chess.WHITE)) * v for p, v in piece_values.items())
    black = sum(len(board.pieces(p, chess.BLACK)) * v for p, v in piece_values.items())
    return white - black


def categorize_moves(board: chess.Board):
    """Categorize legal moves into checks, captures, and quiet moves.
    Filters out moves that would cause threefold repetition."""
    safe, checks, captures, quiets = [], [], [], []

    for m in board.legal_moves:
        board.push(m)
        is_repetition = board.can_claim_threefold_repetition()
        board.pop()
        if is_repetition:
            continue

        san = board.san(m)
        safe.append(san)
        if "+" in san or "#" in san:
            checks.append(san)
        elif "x" in san:
            captures.append(san)
        else:
            quiets.append(san)

    # Fallback: if all moves cause repetition, allow them anyway
    if not safe:
        safe = [board.san(m) for m in board.legal_moves]

    return safe, checks, captures, quiets


# ══════════════════════════════════════════════════════════════════
#  MULTI-PROVIDER AI ROUTING
# ══════════════════════════════════════════════════════════════════

SYSTEM_MSG = "You are a fast, structured chess engine. You output ONLY the legal move."


def _route_openai(model, prompt):
    """OpenAI: gpt-4o, o1-mini, etc."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise Exception("OPENAI_API_KEY not set. Click ⚙ Settings to add it.")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    r = requests.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _route_anthropic(model, prompt):
    """Anthropic: claude-3-5-sonnet, etc."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY not set. Click ⚙ Settings to add it.")
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    payload = {
        "model": model,
        "system": SYSTEM_MSG,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.1,
    }
    r = requests.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()


def _route_gemini(model, prompt):
    """Google Gemini: gemini-1.5-flash, gemini-2.5-flash, etc."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY not set. Click ⚙ Settings to add it.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_MSG}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1},
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _route_grok(model, prompt):
    """xAI Grok: grok-beta, grok-2, etc."""
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise Exception("XAI_API_KEY not set. Click ⚙ Settings to add it.")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    r = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _route_ollama(model, prompt):
    """Local Ollama: llama3, qwen2.5, etc."""
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": prompt}],
        "temperature": 0.1,
        "stream": False,
    }
    r = requests.post(f"{host}/api/chat", json=payload, timeout=180)
    if r.status_code != 200:
        raise Exception(f"Ollama Error {r.status_code}: {r.text[:200]}")
    return r.json()["message"]["content"].strip()


def route_to_provider(model, prompt):
    """Route the request to the correct AI provider based on model name prefix."""
    if model.startswith("gpt-") or model.startswith("o1-"):
        return _route_openai(model, prompt)
    elif model.startswith("claude-"):
        return _route_anthropic(model, prompt)
    elif model.startswith("gemini-"):
        return _route_gemini(model, prompt)
    elif model.startswith("grok-"):
        return _route_grok(model, prompt)
    else:
        return _route_ollama(model, prompt)


# ══════════════════════════════════════════════════════════════════
#  MOVE EXTRACTION (Parse AI response → legal SAN move)
# ══════════════════════════════════════════════════════════════════

def extract_move(ai_msg: str, board: chess.Board):
    """Parse the AI's text response and extract a valid SAN move.
    Returns (move_san, chat_text) or (None, error_text)."""
    ai_msg_clean = ai_msg.replace("`", "").replace('"', "").strip()
    lines = [l.strip() for l in ai_msg_clean.splitlines()]
    legal_set = set(board.san(m) for m in board.legal_moves)

    chosen_move = None
    chosen_line_idx = -1

    # Scan lines bottom-up (move is expected on the last line)
    for idx in range(len(lines) - 1, -1, -1):
        candidate = lines[idx].rstrip(".,!?").strip()
        if not candidate:
            continue

        # 1. Direct SAN match
        if candidate in legal_set:
            chosen_move, chosen_line_idx = candidate, idx
            break

        # 2. UCI format (e2e4, e7e8q)
        try:
            uci_move = chess.Move.from_uci(candidate)
            if uci_move in board.legal_moves:
                chosen_move, chosen_line_idx = board.san(uci_move), idx
                break
        except Exception:
            pass

        # 3. Word-level fallback
        for word in reversed(candidate.split()):
            w = word.rstrip(".,!?").strip()
            if w in legal_set:
                chosen_move, chosen_line_idx = w, idx
                break
            try:
                uci_move = chess.Move.from_uci(w)
                if uci_move in board.legal_moves:
                    chosen_move, chosen_line_idx = board.san(uci_move), idx
                    break
            except Exception:
                pass

        if chosen_move:
            break

    if not chosen_move:
        return None, ai_msg[:300]

    chat_text = "\n".join(lines[:chosen_line_idx]).strip() if chosen_line_idx > 0 else ""
    return chosen_move, chat_text or "*plays in silence*"


# ══════════════════════════════════════════════════════════════════
#  API: MOVE (Main game endpoint)
# ══════════════════════════════════════════════════════════════════

@app.post("/api/move")
async def get_move(request: Request):
    """Generate an AI chess move. Evaluates the board natively, routes to
    the correct AI provider, and parses the response into a legal SAN move."""
    data = await request.json()

    # Parse model name
    raw_model = data.get("model", "llama3").strip()
    if raw_model.startswith("ollama run "):
        raw_model = raw_model.replace("ollama run ", "", 1).strip()
    model = raw_model

    opponent_message = data.get("opponent_message", "")

    # Parse board
    fen = data.get("fen") or chess.STARTING_FEN
    try:
        board = chess.Board(fen)
    except Exception as e:
        return JSONResponse(
            {"success": False, "error": f"Invalid FEN: {e}", "log": "System error: invalid board state"},
            status_code=400,
        )

    # Check game over before move
    over, reason = check_game_over(board)
    if over:
        return JSONResponse({"success": False, "game_over": True, "reason": reason, "log": f"Game over: {reason}"})

    # Native heuristics
    safe_moves, checks, captures, quiets = categorize_moves(board)
    if not safe_moves:
        return JSONResponse({"success": False, "game_over": True, "reason": "No legal moves", "log": "No legal moves"})

    color_name = "White" if board.turn == chess.WHITE else "Black"
    mat_score = evaluate_material(board)
    if mat_score > 0:
        mat_str = f"White is ahead by +{mat_score} points."
    elif mat_score < 0:
        mat_str = f"Black is ahead by +{abs(mat_score)} points."
    else:
        mat_str = "Material is equal."

    history = data.get("history", "No moves yet.")
    opponent_line = f'\nOpponent/Chat said: "{opponent_message}"\n' if opponent_message else "\n"

    # Build prompt
    prompt = f"""You are a fast, ruthless, and purely analytical chess engine.
Make the absolute strongest move. Do not think out loud.
{opponent_line}
Game History (PGN): {history}

Current Board FEN: {board.fen()}
Evaluation: {mat_str}

Available Safe Legal Moves ({color_name}) [Pre-filtered against repetition]:
- Checks: {', '.join(checks) if checks else 'None'}
- Captures: {', '.join(captures) if captures else 'None'}
- Quiet: {', '.join(quiets) if quiets else 'None'}

INSTRUCTIONS:
1. Pick ONE move that maximizes your advantage.
2. DO NOT CHAT. DO NOT EXPLAIN.
3. OUTPUT ONLY THE EXACT MOVE STRING on a single line.
"""

    try:
        ai_msg = await asyncio.to_thread(route_to_provider, model, prompt)
        chosen_move, chat_text = extract_move(ai_msg, board)

        if not chosen_move:
            return JSONResponse(
                {"success": False, "error": "No valid move found", "log": f"{model} gave invalid response: '{chat_text}'"},
                status_code=400,
            )

        board.push_san(chosen_move)
        over, reason = check_game_over(board)

        return JSONResponse({
            "success": True,
            "move": chosen_move,
            "fen": board.fen(),
            "chat": chat_text,
            "game_over": over,
            "reason": reason if over else "",
            "log": f"{model} ({color_name}) → {chosen_move}",
        })

    except requests.exceptions.Timeout:
        return JSONResponse({"success": False, "error": "Request timed out", "log": f"Timeout waiting for {model}"}, status_code=504)
    except requests.exceptions.ConnectionError:
        return JSONResponse({"success": False, "error": "Cannot connect to AI provider", "log": "Connection refused"}, status_code=502)
    except requests.exceptions.RequestException as e:
        return JSONResponse({"success": False, "error": str(e), "log": f"Request error: {e}"}, status_code=502)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e), "log": f"Internal error: {e}"}, status_code=500)


# ══════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
