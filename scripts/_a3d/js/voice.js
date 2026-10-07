/* voice.js - Stimme: lokaler Miku-TTS über das Plugin, Lautstärke, Mund folgt dem Audio
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Ablauf: speak(text) (face.js) -> speakWithVoice(text)
     1. Text in Sätze teilen
     2. Satz 1 beim Plugin anfordern (POST /tts -> {url}) - das Plugin reicht ihn an
        den lokalen TTS-Dienst (scripts/_a3d_tts) weiter
     3. abspielen über Web Audio: Quelle -> Lautstärke (Gain) -> Analyse -> Lautsprecher
        Während Satz 1 läuft, wird Satz 2 schon erzeugt.
   Ohne Plugin/Dienst (oder bei Fehlern) spricht sie wie bisher stumm (nur Mund).
   Von außen: setVoiceVolume(0..1.5), setVoiceEnabled(true/false), getVoiceStatus() */

const VOICE = {
  enabled: true,            // Stimme an/aus (Panel)
  volume: 0.8,              // 0 .. 1.5 (Panel: 0 .. 150 %)
  maxPart: 200,             // längere Sätze werden an Kommas geteilt (Zeichen)
  statusPoll: 2000          // ms zwischen Statusabfragen, solange der Dienst lädt
};
const voice = {
  state: "unknown",         // unknown | idle | starting | ready | missing | disabled | error | offline
  info: {},                 // letzte Statusantwort
  token: 0,                 // erhöht sich bei jedem neuen speak/stop -> alte Abläufe brechen ab
  active: false,            // spricht gerade (inkl. Warten auf den nächsten Satz)
  ctx: null, gain: null, analyser: null, data: null,
  source: null,             // gerade spielender Satz
  env: 0                    // geglättete Lautstärke 0..1 (für den Mund)
};
const voiceViaPlugin = /^https?:$/.test(location.protocol);

/* ---- Einstellungen (viewer_settings.json über das Plugin, sonst localStorage) ---- */
const VOICE_SETTINGS_KEY = "a3d.viewerSettings.v1";
const VOICE_SETTINGS_FILE = "viewer_settings.json";
let voiceSaveTimer = null;
function applyVoiceSettings(v) {
  if (!v || typeof v !== "object") return;
  if (typeof v.voiceEnabled === "boolean") VOICE.enabled = v.voiceEnabled;
  if (isFinite(v.voiceVolume)) VOICE.volume = clamp(+v.voiceVolume, 0, 1.5);
  if (voice.gain) voice.gain.gain.value = VOICE.volume;
  if (typeof updateVoicePanel === "function") updateVoicePanel();
}
function saveVoiceSettings() {
  const v = { voiceEnabled: VOICE.enabled, voiceVolume: Math.round(VOICE.volume * 100) / 100 };
  try { localStorage.setItem(VOICE_SETTINGS_KEY, JSON.stringify(v)); } catch (e) { /* egal */ }
  if (!voiceViaPlugin) return;
  clearTimeout(voiceSaveTimer);                    // Schieberegler: erst speichern, wenn er ruht
  voiceSaveTimer = setTimeout(() => {
    fetch(VOICE_SETTINGS_FILE, { method: "POST", headers: { "Content-Type": "application/json" },
                                 body: JSON.stringify(v) }).catch(() => {});
  }, 500);
}
(function loadVoiceSettings() {
  try { applyVoiceSettings(JSON.parse(localStorage.getItem(VOICE_SETTINGS_KEY) || "null")); } catch (e) { /* egal */ }
  if (!voiceViaPlugin) return;
  fetch(VOICE_SETTINGS_FILE + "?t=" + Date.now(), { cache: "no-store" })
    .then(r => (r.ok ? r.json() : null)).then(applyVoiceSettings).catch(() => {});
})();

function setVoiceVolume(v) {
  VOICE.volume = clamp(+v || 0, 0, 1.5);
  if (voice.gain) voice.gain.gain.value = VOICE.volume;
  saveVoiceSettings();
  if (typeof updateVoicePanel === "function") updateVoicePanel();
}
function setVoiceEnabled(on) {
  VOICE.enabled = !!on;
  if (!VOICE.enabled) stopVoice();
  saveVoiceSettings();
  if (typeof updateVoicePanel === "function") updateVoicePanel();
}
function getVoiceStatus() { return Object.assign({ state: voice.state }, voice.info); }

/* ---- Status des Dienstes ---- */
function pollVoiceStatus() {
  if (!voiceViaPlugin) { voice.state = "offline"; return; }
  fetch("tts_status?t=" + Date.now(), { cache: "no-store" })
    .then(r => (r.ok ? r.json() : { state: "offline" }))
    .catch(() => ({ state: "offline" }))
    .then(st => {
      voice.state = st.state || "offline";
      voice.info = st;
      if (typeof updateVoicePanel === "function") updateVoicePanel();
      if (voice.state === "starting") setTimeout(pollVoiceStatus, VOICE.statusPoll);
    });
}
pollVoiceStatus();

/* ---- Audio ---- */
function voiceAudio() {
  if (!voice.ctx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    voice.ctx = new Ctx();
    voice.gain = voice.ctx.createGain();
    voice.gain.gain.value = VOICE.volume;
    voice.analyser = voice.ctx.createAnalyser();
    voice.analyser.fftSize = 1024;
    voice.data = new Float32Array(voice.analyser.fftSize);
    voice.gain.connect(voice.analyser);
    voice.analyser.connect(voice.ctx.destination);
  }
  if (voice.ctx.state === "suspended") voice.ctx.resume().catch(() => {});
  return voice.ctx;
}

/** Text in Sätze (bei sehr langen Sätzen zusätzlich an Kommas) teilen. */
function splitSentences(text) {
  const parts = [];
  for (const raw of text.replace(/\s+/g, " ").split(/(?<=[.!?。！？…])\s+|\n+/)) {
    let s = raw.trim();
    while (s.length > VOICE.maxPart) {             // an einem Komma vor maxPart teilen
      const cut = Math.max(s.lastIndexOf(", ", VOICE.maxPart), s.lastIndexOf("、", VOICE.maxPart));
      if (cut < 20) break;
      parts.push(s.slice(0, cut + 1));
      s = s.slice(cut + 1).trim();
    }
    if (s) parts.push(s);
  }
  // Sehr kurze Stücke ("Ja.") an den nächsten Satz hängen - weniger Pausen dazwischen
  const merged = [];
  for (const p of parts) {
    if (merged.length && merged[merged.length - 1].length < 12) merged[merged.length - 1] += " " + p;
    else merged.push(p);
  }
  return merged;
}

/** Einen Satz erzeugen lassen und als AudioBuffer laden. */
async function requestVoice(text) {
  const r = await fetch("tts", { method: "POST", headers: { "Content-Type": "application/json" },
                                 body: JSON.stringify({ text }) });
  const res = await r.json().catch(() => ({}));
  if (!r.ok || !res.url) throw new Error(res.error || "TTS-Fehler " + r.status);
  const audio = await (await fetch(res.url)).arrayBuffer();
  return await new Promise((ok, fail) => voiceAudio().decodeAudioData(audio, ok, fail));
}

/** Einen Satz abspielen; Promise endet, wenn er fertig ist (oder abgebrochen wurde). */
function playVoice(buffer, text, token) {
  return new Promise(resolve => {
    if (token !== voice.token) { resolve(); return; }
    const ctx = voiceAudio();
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(voice.gain);
    src.onended = () => { if (voice.source === src) voice.source = null; resolve(); };
    voice.source = src;
    startLipsync(text, buffer.duration);           // Mundformen auf die echte Länge strecken
    src.start();
  });
}

/** Von speak() (face.js): true = Stimme übernimmt, false = stumm weiter. */
function speakWithVoice(text) {
  // idle = eingerichtet, aber noch nicht geladen: die erste Anfrage startet den Dienst
  if (!VOICE.enabled || !["ready", "idle", "starting"].includes(voice.state) || !voiceAudio()) return false;
  const token = ++voice.token;
  if (voice.state === "idle") setTimeout(pollVoiceStatus, 1500);   // Panel zeigt "lädt ..."
  voice.active = true;
  const parts = splitSentences(text);
  (async () => {
    let next = requestVoice(parts[0]);
    for (let i = 0; i < parts.length; i++) {
      let buffer;
      try {
        buffer = await next;
      } catch (err) {
        console.warn("Stimme: " + err.message + " - spreche ohne Ton weiter");
        if (token === voice.token) {
          voice.active = false;
          startLipsync(parts.slice(i).join(" "));  // Rest stumm, damit der Mund nicht stehen bleibt
          pollVoiceStatus();
        }
        return;
      }
      if (token !== voice.token) return;
      if (i === 0 && voice.state !== "ready") pollVoiceStatus();      // Dienst ist jetzt bereit
      next = i + 1 < parts.length ? requestVoice(parts[i + 1]) : null;   // nächsten Satz schon erzeugen
      if (next) next.catch(() => {});              // Fehler erst beim Warten behandeln
      await playVoice(buffer, parts[i], token);
      if (token !== voice.token) return;
    }
    voice.active = false;
  })();
  return true;
}

function stopVoice() {
  voice.token++;
  voice.active = false;
  if (voice.source) {
    try { voice.source.stop(); } catch (e) { /* schon zu Ende */ }
    voice.source = null;
  }
}
function voiceActive() { return voice.active; }

/** Pro Frame (aus updateFace): geglättete Lautstärke 0..1, oder null ohne Audio. */
function voiceEnvelope(dt) {
  if (!voice.source || !voice.analyser) {
    voice.env = 0;
    return voice.active ? 0 : null;                // zwischen zwei Sätzen: Mund zu
  }
  voice.analyser.getFloatTimeDomainData(voice.data);
  let sum = 0;
  for (let i = 0; i < voice.data.length; i++) sum += voice.data[i] * voice.data[i];
  // Analyse liegt hinter der Lautstärke -> auf Lautstärke 1 zurückrechnen
  const rms = Math.sqrt(sum / voice.data.length) / Math.max(VOICE.volume, 0.05);
  const level = clamp((rms - 0.01) / 0.12, 0, 1);
  voice.env += (level - voice.env) * (1 - Math.exp(-(level > voice.env ? 30 : 12) * dt));  // schnell auf, langsamer zu
  return voice.env;
}

/* ---- Panel-Abschnitt "🔊 Stimme" (steht unter "Darstellung"/"Blick") ---- */
let voicePanel = null;

function buildVoiceSection(panel) {
  const anchor = document.getElementById("anim-heading");
  const add = (el) => panel.insertBefore(el, anchor);
  add(makeHeading("🔊 Stimme"));
  add(makeToggle("Stimme (Miku-TTS)", () => VOICE.enabled, setVoiceEnabled));
  const row = document.createElement("label");
  row.style.cssText = "display:flex;align-items:center;gap:0.5vw;font-size:1.4vh;margin:0.4vh 0;";
  const text = document.createElement("span");
  text.style.cssText = "flex:0 0 auto;";
  const slider = document.createElement("input");
  slider.type = "range"; slider.min = "0"; slider.max = "150"; slider.step = "1";
  slider.style.cssText = "flex:1 1 auto;min-width:0;";
  slider.oninput = () => setVoiceVolume(slider.value / 100);
  row.append(text, slider);
  add(row);
  const test = document.createElement("button");
  test.textContent = "▶ Probe";
  test.onclick = () => speak("Hello! I am Hatsune Miku. Nice to meet you!");
  add(test);
  const status = document.createElement("div");
  status.style.cssText = "font-size:1.2vh;opacity:0.7;margin:0.2vh 0 0.6vh 0;";
  add(status);
  voicePanel = { text, slider, status };
  updateVoicePanel();
}

function updateVoicePanel() {
  if (!voicePanel) return;
  const pct = Math.round(VOICE.volume * 100);
  voicePanel.text.textContent = "Lautstärke " + pct + " %";
  if (document.activeElement !== voicePanel.slider) voicePanel.slider.value = String(pct);
  const i = voice.info || {};
  const dev = i.device === "dml" ? "AMD-GPU (DirectML)" : i.device === "cpu" ? "CPU" : (i.device || "");
  voicePanel.status.textContent = {
    ready: "Bereit" + (dev ? " – " + dev : ""),
    idle: "Lädt beim ersten Sprechen (dauert dann etwas)",
    disabled: "Im Plugin ausgeschaltet (TTS_ENABLED)",
    starting: i.message || "Dienst startet …",
    missing: "Nicht eingerichtet: scripts/_a3d_tts/setup_tts.bat ausführen",
    error: "Fehler: " + (i.message || "unbekannt"),
    offline: "Kein Plugin – nur Mundbewegung",
    unknown: "…"
  }[voice.state] || voice.state;
}
