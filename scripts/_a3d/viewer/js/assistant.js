/* assistant.js - KI-Assistent: Antworten vom lokalen KI-Dienst (Ollama + MCP), Spracheingabe 🎤
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Ablauf: Nachricht im Chat -> sendChatMessage (core.js) -> askAssistant(text)
     1. POST ai/chat {message, avatar} ans Plugin, das reicht sie an den KI-Dienst weiter
        (scripts/_a3d/ai: Assistent aus dem PDA mit Ollama und MCP-Werkzeugen).
        avatar = Gesten, Mimik und Stationen, die die Figur gerade kann - daraus lernt
        das Sprachmodell die [aktionen] (actions.js).
     2. Antwort -> assistantMessage(text): in den Chat, sprechen, Aktionen ausführen.
     3. Haben Werkzeuge Daten geliefert (Tabelle), zeigt das Board sie (breites Layout).
   💭 neben dem Eingabefeld: Denkmodus (Thinking) an/aus - gründlichere, aber langsamere Antworten;
   geht mit jeder Nachricht an den Dienst (Modelle ohne Denkmodus ignorieren ihn).
   🎤 neben dem Eingabefeld: Klick = Aufnahme starten, zweiter Klick = erkennen und senden,
   Esc = abbrechen. Erkannt wird im KI-Dienst (faster-whisper), nicht im Browser.
   Ohne KI-Dienst (oder "KI antwortet: aus") spricht die Figur wie bisher den eingegebenen Text.
   Nachrichten ohne Nutzereingabe (Toolbar-push, z. B. Erinnerung): receivePush({text, view}) -
   das Plugin ruft es aus PluginWidget.on_push auf.
   Fenster und Popup zeigen denselben Chat (shareChat, siehe "Fenster und Popup synchron").
   Von außen: askAssistant(text), resetAssistant(), getAssistantStatus(),
              receiveChatSync({sender, text}), restoreChat([...])                         */

const ASSISTANT = {
  enabled: true,            // KI antwortet (Panel); aus = die Figur spricht, was man schreibt
  viewOnBoard: true,        // Ergebnisse (Tabellen u. Ä. aus dem KI-Dienst) aufs Board
  toolCallsOnBoard: false,  // Bestätigung der Werkzeugaufrufe (Vorlage tool_calls) aufs Board - sonst nur Konsole
  webOnBoard: true,         // Webseite, die Miku gelesen/gefunden hat, aufs Board (board/web.html)
  webScripts: false,        // ... mit JavaScript - Chromium 83 hat bekannte Lücken, deshalb aus
  think: false,             // Denkmodus (💭 am Chat): erst nachdenken, dann antworten - langsamer
  thinkingFace: "thinking", // Mimik, solange die KI rechnet (Schlüssel aus EXPRESSIONS)
  statusPoll: 2000          // ms zwischen Statusabfragen, solange der Dienst startet
};
const assistant = {
  state: "unknown",         // unknown | idle | starting | ready | missing | disabled | error | offline
  info: {},                 // letzte Statusantwort ({stt, tts} vom Dienst)
  models: [], model: null, modelError: "",
  pending: 0,               // Anfragen, auf deren Antwort wir warten
  recording: false,
  transcribing: false
};
const assistantViaPlugin = /^https?:$/.test(location.protocol);
const micButton = document.getElementById("chat-mic");
const thinkButton = document.getElementById("chat-think");
let assistantPanel = null;   // Elemente im Panel (buildAssistantSection)

/* ---- Einstellungen (assistant_settings.json über das Plugin, sonst localStorage) ---- */
const ASSISTANT_SETTINGS_KEY = "a3d.assistantSettings.v1";
const ASSISTANT_SETTINGS_FILE = "assistant_settings.json";
function applyAssistantSettings(v) {
  if (!v || typeof v !== "object") return;
  if (typeof v.enabled === "boolean") ASSISTANT.enabled = v.enabled;
  if (typeof v.viewOnBoard === "boolean") ASSISTANT.viewOnBoard = v.viewOnBoard;
  if (typeof v.toolCallsOnBoard === "boolean") ASSISTANT.toolCallsOnBoard = v.toolCallsOnBoard;
  if (typeof v.webOnBoard === "boolean") ASSISTANT.webOnBoard = v.webOnBoard;
  if (typeof v.webScripts === "boolean") ASSISTANT.webScripts = v.webScripts;
  if (typeof v.think === "boolean") ASSISTANT.think = v.think;
  updateAssistantUi();
}
function saveAssistantSettings() {
  const v = { enabled: ASSISTANT.enabled, viewOnBoard: ASSISTANT.viewOnBoard,
              toolCallsOnBoard: ASSISTANT.toolCallsOnBoard, webOnBoard: ASSISTANT.webOnBoard,
              webScripts: ASSISTANT.webScripts, think: ASSISTANT.think };
  try { localStorage.setItem(ASSISTANT_SETTINGS_KEY, JSON.stringify(v)); } catch (e) { /* egal */ }
  if (!assistantViaPlugin) return;
  fetch(ASSISTANT_SETTINGS_FILE, { method: "POST", headers: { "Content-Type": "application/json" },
                                   body: JSON.stringify(v) }).catch(() => {});
}
(function loadAssistantSettings() {
  try { applyAssistantSettings(JSON.parse(localStorage.getItem(ASSISTANT_SETTINGS_KEY) || "null")); } catch (e) { /* egal */ }
  if (!assistantViaPlugin) return;
  fetch(ASSISTANT_SETTINGS_FILE + "?t=" + Date.now(), { cache: "no-store" })
    .then(r => (r.ok ? r.json() : null)).then(applyAssistantSettings).catch(() => {});
})();

function getAssistantStatus() {
  return Object.assign({ state: assistant.state, model: assistant.model, enabled: ASSISTANT.enabled }, assistant.info);
}

/** POST an den KI-Dienst (über das Plugin) -> JSON; wirft bei Fehlern. */
async function aiPost(path, body) {
  const r = await fetch("ai/" + path, { method: "POST", headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify(body || {}) });
  const res = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(res.error || "Fehler " + r.status);
  return res;
}

/* ---- Status des Dienstes und Modelle ---- */
function pollAssistantStatus() {
  if (!assistantViaPlugin) { assistant.state = "offline"; updateAssistantUi(); return; }
  fetch("ai/status?t=" + Date.now(), { cache: "no-store" })
    .then(r => (r.ok ? r.json() : { state: "offline" }))
    .catch(() => ({ state: "offline" }))
    .then(st => {
      const wasReady = assistant.state === "ready";
      assistant.state = st.state || "offline";
      assistant.info = st;
      if (assistant.state === "ready" && !wasReady) loadAssistantModels();
      updateAssistantUi();
      if (assistant.state === "starting") setTimeout(pollAssistantStatus, ASSISTANT.statusPoll);
    });
}

function loadAssistantModels() {
  fetch("ai/models?t=" + Date.now(), { cache: "no-store" })
    .then(async r => {
      const res = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(res.error || "Fehler " + r.status);
      assistant.models = res.models || [];
      assistant.model = res.current || null;
      assistant.modelError = "";
    })
    .catch(e => { assistant.models = []; assistant.model = null; assistant.modelError = e.message; })
    .then(updateAssistantUi);
}

function selectAssistantModel(name) {
  aiPost("model", { name })
    .then(res => { assistant.model = res.current; assistant.modelError = ""; })
    .catch(e => { assistant.modelError = e.message; })
    .then(updateAssistantUi);
}

/** Neues Gespräch: die KI vergisst den bisherigen Verlauf. */
function resetAssistant() {
  return aiPost("reset").then(() => {
    addMessage(ACTIONS.assistantName, "Neues Gespräch begonnen.");
    shareChat(ACTIONS.assistantName, "Neues Gespräch begonnen.");
  })
    .catch(e => addMessage("⚠", "Zurücksetzen fehlgeschlagen: " + e.message));
}

function assistantAvailable() {
  return ASSISTANT.enabled && ["ready", "idle", "starting"].includes(assistant.state);
}

/* ---- Chat ---- */
/** Von sendChatMessage (core.js): true = die KI antwortet, false = ohne KI weiter. Eigene
    [aktionen] in der Nachricht werden gleich ausgeführt, nur der Text geht an die KI. */
function askAssistant(message) {
  if (!assistantAvailable()) return false;
  const actions = parseActions(message).filter(p => p.action).map(p => p.action.raw).join(" ");
  const text = stripActions(message);
  if (actions) runActions(actions);
  if (text) requestAssistantReply(text);
  return true;
}

/** Was die Figur gerade kann - Namen so, wie actions.js sie versteht, auf Deutsch und Englisch
    (der KI-Dienst nimmt die Liste in seiner Sprache, config.LANGUAGE). */
function avatarAbilities() {
  const gestures = Object.keys(GESTURES).map(normName).filter(Boolean);
  const gesturesEn = Object.keys(GESTURE_ALIASES).filter(en => findBest(GESTURE_ALIASES[en], Object.keys(GESTURES)));
  const expressions = [], seen = new Set();
  for (const [alias, key] of Object.entries(EXPRESSION_ALIASES)) {   // ein deutscher Name je Ausdruck
    if (EXPRESSIONS[key] && !seen.has(key)) { seen.add(key); expressions.push(alias); }
  }
  const expressionsEn = [...seen];                                  // englisch = Schlüssel aus EXPRESSIONS
  return { gestures, gestures_en: gesturesEn, expressions, expressions_en: expressionsEn, stations: getStations() };
}

async function requestAssistantReply(text) {
  stopSpeaking();
  const waiting = addMessage(ACTIONS.assistantName, ASSISTANT.think ? "denkt gründlich nach 💭 …" : "denkt nach …");
  waiting.style.opacity = "0.6";
  assistant.pending++;
  setThinking(true);
  let reply;
  boardPlugin.turn = false;                         // setzt die Toolbar, wenn ein Plugin aufs Board kommt
  try {
    reply = await aiPost("chat", { message: text, avatar: avatarAbilities(), think: ASSISTANT.think });
  } catch (e) {
    reply = { error: e.message };
  }
  if (--assistant.pending === 0) setThinking(false);
  if (reply.error) {
    waiting.remove();
    addMessage("⚠", "KI nicht erreichbar: " + reply.error);
    pollAssistantStatus();
    return;
  }
  // Kam in dieser Runde ein Plugin aufs Board, bleibt es - Seite/Ansicht kommen danach (nach ✕)
  const keepPlugin = boardPlugin.turn && boardPlugin.active;
  if (reply.view) logToolCalls(reply.view);
  if (reply.page && ASSISTANT.webOnBoard && !stageState.narrow) {
    showWebPageOnBoard(reply.page.url, reply.page.title, ASSISTANT.webScripts, keepPlugin);
  } else if (reply.view) {
    showViewOnBoard(reply.view, keepPlugin);
  }
  if (reply.attachments && reply.attachments.length) console.info("Anhänge:", reply.attachments);
  shareChat(ACTIONS.assistantName, stripActions(reply.text || ""), true);   // + dieser Viewer nach vorne
  assistantMessage(reply.text || "", waiting);       // "denkt nach ..." bleibt, bis die Stimme einsetzt
}

/* ---- Fenster und Popup synchron ----
   Jede Chatzeile (Frage, Antwort, push) geht über das Plugin (POST chat/sync) an die anderen
   offenen Viewer: receiveChatSync zeigt sie dort, ohne zu sprechen. Ein neu geöffneter Viewer
   bekommt den bisherigen Chat über restoreChat. reveal = Antwort auf eine Frage: Das Plugin holt
   diesen Viewer nach vorne (Popup bzw. Fenster). */
const VIEWER_ID = new URLSearchParams(location.search).get("v") || "";
function shareChat(sender, text, reveal) {
  if (!assistantViaPlugin || !VIEWER_ID || !(text || reveal)) return;
  fetch("chat/sync?v=" + encodeURIComponent(VIEWER_ID), {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sender, text: text || "", reveal: !!reveal })
  }).catch(() => {});
}
function receiveChatSync(entry) {
  if (entry && entry.text) addMessage(entry.sender, entry.text);
}
function restoreChat(entries) {
  if (Array.isArray(entries)) entries.forEach(receiveChatSync);
}

/* ---- Nachrichten von außen (Toolbar-push über das Plugin, z. B. vom KI-Dienst) ---- */
let pushChain = Promise.resolve();

/** {text, view}: wie eine Antwort zeigen und sprechen - erst, wenn die Figur geladen ist,
    und nacheinander (eine zweite Nachricht schneidet die erste nicht ab). */
function receivePush(payload) {
  pushChain = pushChain.then(waitForFigure).then(() => {
    if (payload.view) showViewOnBoard(payload.view);
    shareChat(ACTIONS.assistantName, stripActions(String(payload.text || "")));
    return assistantMessage(String(payload.text || ""));
  }).catch(e => console.warn("push: " + e.message));
}

/** Modell geladen und Stimme bekannt - höchstens maxMs warten (ohne Modell trotzdem weiter). */
function waitForFigure(maxMs = 20000) {
  const t0 = Date.now();
  return new Promise(resolve => {
    const check = () => {
      if ((morphMeshes.length > 0 && voice.state !== "unknown") || Date.now() - t0 > maxMs) resolve();
      else setTimeout(check, 200);
    };
    check();
  });
}

function setThinking(on) {
  if (on) setExpression(ASSISTANT.thinkingFace, 0.8, 600);
  else if (expr.temp && expr.temp.name === ASSISTANT.thinkingFace) expr.temp = null;
}

/** Werkzeugaufrufe einer Antwort (Vorlage tool_calls) in die Konsole ("[3D Assistent JS] [Werkzeug] ...").
    Nur Werkzeug, Angaben und ✓/✗ - keine Ergebnisse (die können Privates enthalten, z. B. Dateinamen). */
function logToolCalls(view) {
  const calls = view && view.template === "tool_calls" && view.data && view.data.calls;
  if (!Array.isArray(calls)) return;
  for (const c of calls) {
    console.info("[Werkzeug] " + (c.error ? "✗ " : "✓ ") + c.name + " " + JSON.stringify(c.arguments));
  }
}

/** Ansicht aus einer Antwort aufs Board. Normalerweise hat der KI-Dienst sie schon mit Jinja
    gerendert ("html", Vorlagen in _a3d/ai/templates/, Daten maskiert); sonst wird eine einfache
    Tabelle aus "data" ({title, text, columns, rows}) gebaut - ebenfalls maskiert, denn
    Werkzeug-Ergebnisse (z. B. Mails) stammen von Dritten.
    Die Bestätigung der Werkzeugaufrufe (Vorlage tool_calls) hat einen eigenen Schalter im Panel.
    keepPlugin: ein Plugin auf dem Board bleibt, die Ansicht kommt danach (nach ✕). */
function showViewOnBoard(view, keepPlugin) {
  if (!view || stageState.narrow) return;
  if (!(view.template === "tool_calls" ? ASSISTANT.toolCallsOnBoard : ASSISTANT.viewOnBoard)) return;
  if (view.html) { showOnBoard(view.html, keepPlugin); return; }
  const d = view.data;
  if (!d || (!d.text && !(d.rows && d.rows.length))) return;
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let html = "<style>table{border-collapse:collapse;width:100%;font-size:0.9em}" +
             "th,td{border-bottom:1px solid #ccd5dc;padding:0.3em 0.5em;text-align:left;vertical-align:top}" +
             "th{background:#eef2f5}</style>";
  if (d.title) html += "<h2>" + esc(d.title) + "</h2>";
  if (d.text) html += "<p>" + esc(d.text) + "</p>";
  if (Array.isArray(d.rows) && d.rows.length) {
    html += "<table>";
    if (Array.isArray(d.columns)) html += "<tr>" + d.columns.map(c => "<th>" + esc(c) + "</th>").join("") + "</tr>";
    for (const row of d.rows) html += "<tr>" + (Array.isArray(row) ? row : [row]).map(c => "<td>" + esc(c) + "</td>").join("") + "</tr>";
    html += "</table>";
  }
  showOnBoard(html, keepPlugin);
}

/* ---- Spracheingabe (🎤) ---- */
async function toggleRecording() {
  if (assistant.transcribing) return;
  if (assistant.recording) { finishRecording(); return; }
  stopSpeaking();                                   // sonst nimmt das Mikrofon die Stimme mit auf
  try {
    await aiPost("stt/start");
    assistant.recording = true;
  } catch (e) {
    addMessage("⚠", "Mikrofon: " + e.message);
  }
  updateAssistantUi();
}

async function finishRecording() {
  assistant.recording = false;
  assistant.transcribing = true;
  updateAssistantUi();
  try {
    const res = await aiPost("stt/stop");           // erstes Mal: Whisper-Modell laden dauert etwas
    if (res.text) sendChatMessage(res.text);
    else addMessage("⚠", "Nichts verstanden.");
  } catch (e) {
    addMessage("⚠", "Spracherkennung: " + e.message);
  }
  assistant.transcribing = false;
  updateAssistantUi();
}

function cancelRecording() {
  if (!assistant.recording) return;
  assistant.recording = false;
  aiPost("stt/cancel").catch(() => {});
  updateAssistantUi();
}

micButton.addEventListener("click", toggleRecording);

/** Denkmodus an/aus (💭 am Chat). */
function setAssistantThink(on) {
  ASSISTANT.think = !!on;
  saveAssistantSettings();
  updateAssistantUi();
}
thinkButton.addEventListener("click", () => setAssistantThink(!ASSISTANT.think));
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (assistant.recording) cancelRecording();
  else if (isSpeaking()) { actionToken++; stopSpeaking(); }   // Vorlesen und laufenden Ablauf stoppen
});

/* ---- Panel-Abschnitt "🤖 KI-Assistent" (steht unter "🔊 Stimme") ---- */
function buildAssistantSection(panel) {
  const anchor = document.getElementById("anim-heading");
  const add = (el) => panel.insertBefore(el, anchor);
  add(makeHeading("🤖 KI-Assistent"));
  add(makeToggle("KI antwortet", () => ASSISTANT.enabled, v => {
    ASSISTANT.enabled = v; saveAssistantSettings(); updateAssistantUi();
  }));
  add(makeToggle("Ergebnisse aufs Board", () => ASSISTANT.viewOnBoard, v => {
    ASSISTANT.viewOnBoard = v; saveAssistantSettings();
  }));
  add(makeToggle("Werkzeugaufrufe aufs Board", () => ASSISTANT.toolCallsOnBoard, v => {
    ASSISTANT.toolCallsOnBoard = v; saveAssistantSettings();
  }));
  add(makeToggle("Webseiten aufs Board", () => ASSISTANT.webOnBoard, v => {
    ASSISTANT.webOnBoard = v; saveAssistantSettings();
  }));
  const scriptsToggle = makeToggle("Webseiten: Skripte erlauben ⚠", () => ASSISTANT.webScripts, v => {
    ASSISTANT.webScripts = v; saveAssistantSettings();
  });
  scriptsToggle.title = "Der Viewer ist Chromium 83 (2020) mit bekannten Sicherheitslücken - die meisten Angriffe " +
                        "brauchen JavaScript. Nur einschalten, wenn nötig (Seiten laufen trotzdem in einer Sandbox).";
  add(scriptsToggle);
  const model = document.createElement("select");
  model.title = "Sprachmodell (in Ollama installiert)";
  model.style.cssText = "display:block;width:100%;margin:0.4vh 0;padding:0.4vh;font-size:1.4vh;" +
                        "background:rgba(255,255,255,0.15);color:white;border:none;border-radius:0.4vh;";
  model.onchange = () => selectAssistantModel(model.value);
  add(model);
  const reset = document.createElement("button");
  reset.textContent = "🧹 Neues Gespräch";
  reset.onclick = resetAssistant;
  add(reset);
  const status = document.createElement("div");
  status.style.cssText = "font-size:1.2vh;opacity:0.7;margin:0.2vh 0 0.6vh 0;";
  add(status);
  assistantPanel = { model, status };
  updateAssistantUi();
}

function updateAssistantUi() {
  const ready = assistant.state === "ready";
  if (thinkButton) {
    thinkButton.style.display = assistantAvailable() ? "" : "none";
    thinkButton.classList.toggle("active", ASSISTANT.think);
    thinkButton.title = ASSISTANT.think
      ? "Denkmodus an: gründlichere, aber langsamere Antworten (Klick = aus)"
      : "Denkmodus aus: schnelle Antworten (Klick = an)";
  }
  if (micButton) {
    micButton.style.display = ready && assistant.info.stt ? "" : "none";
    micButton.textContent = assistant.recording ? "⏹" : assistant.transcribing ? "…" : "🎤";
    micButton.classList.toggle("recording", assistant.recording);
    micButton.title = assistant.recording ? "Klick = senden, Esc = abbrechen" : "Sprechen (Klick = Aufnahme starten)";
  }
  if (typeof chatInput !== "undefined" && chatInput) {
    chatInput.placeholder = assistant.recording ? "Ich höre zu … (Klick auf ⏹ = senden, Esc = abbrechen)"
      : assistantAvailable() ? "Frag " + ACTIONS.assistantName + " …" : "Schreibe hier...";
  }
  if (!assistantPanel) return;
  const { model, status } = assistantPanel;
  model.style.display = ready && assistant.models.length ? "" : "none";
  if (document.activeElement !== model) {
    model.textContent = "";                         // (replaceChildren kennt QtWebEngine 5.15 noch nicht)
    model.append(...assistant.models.map(m => {
      const o = document.createElement("option");
      o.value = m.name;
      o.textContent = m.name + (m.tools ? "" : " (ohne Werkzeuge)");
      o.style.color = "black";
      return o;
    }));
    if (assistant.model) model.value = assistant.model;
  }
  const i = assistant.info || {};
  status.textContent = ready
    ? (assistant.modelError ? "Ollama: " + assistant.modelError
       : assistant.model ? "Bereit" + (i.stt ? " – 🎤 Spracheingabe" : "") : "Kein Modell in Ollama installiert")
    : ({
        idle: "Startet bei der ersten Nachricht",
        starting: i.message || "Dienst startet …",
        missing: "Nicht eingerichtet: scripts/_a3d/ai/setup_ai.bat ausführen",
        disabled: "Im Plugin ausgeschaltet (AI_ENABLED)",
        error: "Fehler: " + (i.message || "unbekannt"),
        offline: "Kein Plugin – die Figur spricht nur den Text",
        unknown: "…"
      }[assistant.state] || assistant.state);
}

pollAssistantStatus();
