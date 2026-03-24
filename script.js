/* ── State ── */
let board      = null;
let game       = new Chess();
let isPlaying  = false;
let retryCount = 0;
let lastOpponentMessage = "";
let moveNumber = 1;
let scores     = { white: 0, draws: 0, black: 0 };

const MAX_RETRIES = 3;

/* ── Settings: Save API Keys ── */
document.addEventListener("DOMContentLoaded", () => {
  const saveBtn = document.getElementById("saveKeysBtn");
  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      const body = {
        openai: document.getElementById("key_openai").value,
        anthropic: document.getElementById("key_anthropic").value,
        gemini: document.getElementById("key_gemini").value,
        xai: document.getElementById("key_xai").value,
      };
      try {
        const r = await fetch("/api/settings", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) });
        const d = await r.json();
        const status = document.getElementById("settingsStatus");
        status.textContent = d.success ? "✅ Keys saved & loaded!" : "❌ Error saving keys.";
        status.style.display = "block";
        if (d.success) setTimeout(() => { document.getElementById("settingsModal").style.display = "none"; status.style.display = "none"; }, 1500);
      } catch(e) { alert("Failed to save keys: " + e.message); }
    });
  }
});

/* ── DOM helpers ── */
const $id = id => document.getElementById(id);

function addLog(msg, type = "sys") {
  const el  = document.createElement("div");
  el.className = type === "sys" ? "log-sys" : `log-entry ${type}`;
  const ts  = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  el.textContent = `[${ts}] ${msg}`;
  $id("logs").appendChild(el);
  $id("logs").scrollTop = 99999;
}

function addChat(color, modelName, msg) {
  const log = $id("aiChat");
  const placeholder = log.querySelector(".chat-placeholder");
  if (placeholder) placeholder.remove();

  const entry = document.createElement("div");
  entry.className = "chat-entry";
  entry.innerHTML = `<span class="chat-name ${color}">${modelName} (${color})</span>
                     <span class="chat-body">${escapeHtml(msg)}</span>`;
  log.appendChild(entry);
  log.scrollTop = 99999;
}

function escapeHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function setStatus(msg) {
  $id("gameStatus").textContent = msg;
}

function updatePlayerTags() {
  $id("nameWhite").textContent = $id("whiteType").value === "human" ? "Human" : ($id("whiteModel").value || "White");
  $id("nameBlack").textContent = $id("blackType").value === "human" ? "Human" : ($id("blackModel").value || "Black");
}

function setThinking(color, active) {
  const el = color === "white" ? $id("thinkWhite") : $id("thinkBlack");
  el.style.display = active ? "inline" : "none";
}

function updateControls() {
  $id("startBtn").disabled = isPlaying;
  $id("stopBtn").disabled  = !isPlaying;
}

function addMoveToken(san, color, moveNum, isFirst) {
  const list = $id("moveHistory");
  if (isFirst) {
    const num = document.createElement("span");
    num.className = "move-token num";
    num.textContent = `${moveNum}.`;
    list.appendChild(num);
  }
  const tok = document.createElement("span");
  tok.className = `move-token ${color}`;
  tok.textContent = san;
  list.appendChild(tok);
  list.scrollTop = 99999;
}

function updateScores() {
  $id("scoreWhite").textContent = scores.white;
  $id("scoreDraws").textContent = scores.draws;
  $id("scoreBlack").textContent = scores.black;
}

function handleGameOver(reason) {
  isPlaying = false;
  setThinking("white", false);
  setThinking("black", false);
  updateControls();

  const msg = reason || "Game over";
  setStatus(msg);
  addLog(`⬜ ${msg}`, "sys");

  let winner = "draw";
  if (msg.toLowerCase().includes("white loses") || msg.toLowerCase().includes("black wins")) {
    scores.black++;
    winner = "black";
  } else if (msg.toLowerCase().includes("black loses") || msg.toLowerCase().includes("white wins")) {
    scores.white++;
    winner = "white";
  } else {
    scores.draws++;
  }
  updateScores();

  const wm = $id("whiteModel").value.trim() || "unknown";
  const bm = $id("blackModel").value.trim() || "unknown";
  fetch("/api/report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whiteModel: wm, blackModel: bm, winner, reason: msg })
  });
}

/* ── Main game loop ── */
async function makeAiMove() {
  if (!isPlaying) return;

  const turn      = game.turn();
  const colorName = turn === "w" ? "white" : "black";
  const type      = $id(colorName + "Type").value;
  const model     = $id(colorName + "Model").value.trim();
  const delay     = parseInt($id("delay").value, 10) || 1200;

  if (type === "human") {
    setStatus(`${colorName === "w" ? "White" : "Black"}'s turn (Human)…`);
    addLog(`Waiting for human (${colorName}) to move…`, "sys");
    return;
  }

  setThinking(colorName, true);
  setThinking(colorName === "white" ? "black" : "white", false);
  setStatus(`${colorName === "w" ? "White" : "Black"}'s turn…`);
  addLog(`Asking ${model} (${colorName})…`, "sys");

  try {
    const resp = await fetch("/api/move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fen: game.fen(),
        history: game.pgn(),
        model,
        opponent_message: lastOpponentMessage
      })
    });

    const data = await resp.json();

    // Server-side game-over detection (pre-move)
    if (data.game_over && !data.success) {
      setThinking(colorName, false);
      handleGameOver(data.reason || data.log);
      return;
    }

    if (data.success) {
      retryCount = 0;

      // Apply move to local chess.js instance
      const result = game.move(data.move, { sloppy: true });
      if (!result) {
        // Move rejected by local chess.js — treat as invalid
        addLog(`⚠ Local chess.js rejected move "${data.move}" — retrying`, "error");
        setThinking(colorName, false);
        if (retryCount < MAX_RETRIES) {
          retryCount++;
          setTimeout(makeAiMove, 1500);
        } else {
          addLog("Max retries reached — stopping.", "error");
          isPlaying = false;
          updateControls();
          setThinking(colorName, false);
        }
        return;
      }

      board.position(game.fen());

      // Add to move history
      const isWhiteMove = (colorName === "white");
      addMoveToken(data.move, colorName, moveNumber, isWhiteMove);
      if (!isWhiteMove) moveNumber++;

      addLog(data.log, colorName);

      if (data.chat) {
        lastOpponentMessage = data.chat;
        addChat(colorName, model, data.chat);
      }

      setThinking(colorName, false);

      // Check game over (server reported, or local)
      const localOver = game.game_over();
      if (data.game_over || localOver) {
        let reason = data.reason;
        if (!reason) {
          if (game.in_checkmate())   reason = `Checkmate — ${colorName === "white" ? "Black" : "White"} loses`;
          else if (game.in_draw())   reason = "Draw";
          else                       reason = "Game over";
        }
        handleGameOver(reason);
        return;
      }

      // Update status (check?)
      if (game.in_check()) {
        const nextColor = game.turn() === "w" ? "White" : "Black";
        setStatus(`${nextColor} is in check!`);
      } else {
        const nextColor = game.turn() === "w" ? "White" : "Black";
        setStatus(`${nextColor} to move`);
      }

      if (isPlaying) setTimeout(makeAiMove, delay);

    } else {
      // Failed move
      setThinking(colorName, false);
      addLog(data.log || data.error, "error");
      if (retryCount < MAX_RETRIES) {
        retryCount++;
        addLog(`Retrying… (${retryCount}/${MAX_RETRIES})`, "sys");
        setTimeout(makeAiMove, 1800);
      } else {
        addLog("Max retries reached — stopping.", "error");
        isPlaying = false;
        updateControls();
      }
    }

  } catch (err) {
    setThinking(colorName, false);
    addLog(`Fetch error: ${err.message}`, "error");
    isPlaying = false;
    updateControls();
  }
}

/* ── Button handlers ── */
$id("startBtn").addEventListener("click", () => {
  if ($id("whiteType").value === "ai" && !$id("whiteModel").value.trim()) {
    alert("Please enter a model name for White.");
    return;
  }
  if ($id("blackType").value === "ai" && !$id("blackModel").value.trim()) {
    alert("Please enter a model name for Black.");
    return;
  }

  game.reset();
  board.start();
  isPlaying      = true;
  retryCount     = 0;
  moveNumber     = 1;
  lastOpponentMessage = "";

  $id("moveHistory").innerHTML = "";
  $id("aiChat").innerHTML = '<span class="chat-placeholder">Chat will appear here…</span>';
  $id("logs").innerHTML   = "";

  updatePlayerTags();
  updateControls();
  setStatus("White to move");
  addLog("── New game started ──", "sys");
  makeAiMove();
});

$id("stopBtn").addEventListener("click", () => {
  isPlaying = false;
  setThinking("white", false);
  setThinking("black", false);
  updateControls();
  setStatus("Stopped.");
  addLog("Game stopped by user.", "sys");
});

$id("flipBtn").addEventListener("click", () => {
  board.flip();
});

$id("sendChatBtn").addEventListener("click", () => {
  const input = $id("userChatInput");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";
  addChat("sys", "Human", msg);
  lastOpponentMessage += (lastOpponentMessage ? "\n" : "") + "Human audience says: " + msg;
});

$id("userChatInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $id("sendChatBtn").click();
});

function onDragStart(source, piece, position, orientation) {
  if (!isPlaying) return false;
  const turn = game.turn();
  const colorName = turn === "w" ? "white" : "black";
  const type = $id(colorName + "Type").value;
  
  if (type !== "human") return false;
  if ((turn === "w" && piece.search(/^b/) !== -1) ||
      (turn === "b" && piece.search(/^w/) !== -1)) {
    return false;
  }
}

function onDrop(source, target) {
  const turn = game.turn();
  const colorName = turn === "w" ? "white" : "black";
  const move = game.move({ from: source, to: target, promotion: "q" });

  if (move === null) return "snapback";

  const isWhiteMove = (colorName === "white");
  addMoveToken(move.san, colorName, moveNumber, isWhiteMove);
  if (!isWhiteMove) moveNumber++;

  addLog(`Human (${colorName}) → ${move.san}`, colorName);

  if (game.game_over()) {
    let reason = "Game over";
    if (game.in_checkmate()) reason = `Checkmate — ${colorName === "white" ? "Black" : "White"} loses`;
    else if (game.in_draw()) reason = "Draw";
    handleGameOver(reason);
    return;
  }

  if (game.in_check()) {
    const nextColor = game.turn() === "w" ? "White" : "Black";
    setStatus(`${nextColor} is in check!`);
  } else {
    const nextColor = game.turn() === "w" ? "White" : "Black";
    setStatus(`${nextColor} to move`);
  }

  // Allow opponent to respond
  setTimeout(makeAiMove, parseInt($id("delay").value, 10) || 1200);
}

function onSnapEnd() {
  board.position(game.fen());
}

/* ── Board init ── */
jQuery(document).ready(function () {
  board = Chessboard("board1", {
    position: "start",
    draggable: true,
    pieceTheme: "https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png",
    onDragStart: onDragStart,
    onDrop: onDrop,
    onSnapEnd: onSnapEnd
  });
  jQuery(window).resize(board.resize);
  updatePlayerTags();
});
