/* face.js - Mimik: Lippensync, Blinzeln, Taste M
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Mimik: Lippensynchronisation, Blinzeln, manueller Mund (Taste M)
   -------------------------------------------------------------------------
   Lippensync-Prinzip:
   1. Text -> Folge von Mundformen (Visemen) mit Dauer, inkl. deutscher
      Laute (sch, ch, ei, au, eu, ie, ä, ö, ü). Mehrere Buchstaben, die
      gleich aussehen, werden zusammengefasst.
   2. Jede Mundform ist eine MISCHUNG der Morphs a/i/u/e/o (z. B. "ö" =
      halb o, halb e), nicht nur ein einzelner Morph.
   3. Koartikulation: Gegen Ende eines Lauts wird schon zur nächsten Form
      übergeblendet - die Formen gehen ineinander über.
   4. Zum Schluss folgt der Mund dem Ziel mit einer kurzen Glättung
      (~40 ms), damit nichts ruckelt.
   Von außen nutzbar: speak(text), stopSpeaking(), isSpeaking()
   (z. B. später aus Python per runJavaScript, passend zu einer TTS-Ausgabe).
   ========================================================================= */
const LIPSYNC = {
  morphs: { A: "a", I: "i", U: "u", E: "e", O: "o" },  // Morph-Namen im Modell
  unit: 0.062,          // Sekunden pro "Lauteinheit" (kleiner = schneller sprechen)
  intensity: 0.9,       // maximale Mundöffnung (0..1)
  blendIn: 0.45,        // Anteil eines Lauts, der in den nächsten überblendet
  smoothing: 26,        // wie schnell der Mund dem Ziel folgt (1/s)
  variation: 0.15       // zufällige Stärke-Schwankung je Silbe (lebendiger)
};

// Mundformen als Morph-Mischung + relative Dauer (in LIPSYNC.unit)
const VISEMES = {
  rest:   { w: {},                         d: 1.0 },
  a:      { w: { A: 1.0 },                 d: 1.6 },
  e:      { w: { E: 0.85, I: 0.1 },        d: 1.4 },
  i:      { w: { I: 0.85 },                d: 1.3 },
  o:      { w: { O: 0.9 },                 d: 1.6 },
  u:      { w: { U: 0.9 },                 d: 1.5 },
  ae:     { w: { E: 0.6, A: 0.35 },        d: 1.5 },
  oe:     { w: { O: 0.55, E: 0.35 },       d: 1.5 },
  ue:     { w: { U: 0.6, I: 0.3 },         d: 1.5 },
  closed: { w: {},                         d: 0.9 },   // m, b, p: Lippen zu
  lip:    { w: { I: 0.18, U: 0.08 },       d: 0.8 },   // f, v, w: Unterlippe
  teeth:  { w: { E: 0.22, I: 0.18 },       d: 0.7 },   // s, z, t, d, n, l, ...
  round:  { w: { U: 0.45, O: 0.15 },       d: 1.0 },   // sch, ch, j
  open:   { w: { A: 0.25, E: 0.15 },       d: 0.7 },   // h, k, g, r
};

// Text -> Liste von Visem-Namen (Reihenfolge = Prüfreihenfolge, längste zuerst)
const PHONEME_RULES = [
  ["sch", ["round"]], ["tsch", ["round"]], ["ch", ["round"]],
  ["ei", ["a", "i"]], ["ai", ["a", "i"]], ["au", ["a", "u"]],
  ["eu", ["o", "i"]], ["äu", ["o", "i"]], ["ie", ["i"]],
  ["ä", ["ae"]], ["ö", ["oe"]], ["ü", ["ue"]], ["y", ["ue"]],
  ["a", ["a"]], ["e", ["e"]], ["i", ["i"]], ["o", ["o"]], ["u", ["u"]],
  ["m", ["closed"]], ["b", ["closed"]], ["p", ["closed"]],
  ["f", ["lip"]], ["v", ["lip"]], ["w", ["lip"]],
  ["j", ["round"]],
  ["h", ["open"]], ["k", ["open"]], ["g", ["open"]], ["r", ["open"]], ["q", ["open"]],
  ["s", ["teeth"]], ["ß", ["teeth"]], ["z", ["teeth"]], ["c", ["teeth"]], ["x", ["teeth"]],
  ["t", ["teeth"]], ["d", ["teeth"]], ["n", ["teeth"]], ["l", ["teeth"]]
];
const PAUSE_CHARS = { " ": 0.8, ",": 3, ";": 3, ":": 3, ".": 5, "!": 5, "?": 5, "\n": 5 };

function textToVisemes(text) {
  const src = text.toLowerCase();
  const out = [];
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (ch in PAUSE_CHARS) {
      const prev = out[out.length - 1];
      if (prev && prev.v === "rest") prev.d = Math.max(prev.d, PAUSE_CHARS[ch]);   // ", " = eine Pause
      else out.push({ v: "rest", d: PAUSE_CHARS[ch] });
      i++;
      continue;
    }
    const rule = PHONEME_RULES.find(([pat]) => src.startsWith(pat, i));
    if (!rule) { i++; continue; }                         // Ziffern, Emojis usw. überspringen
    for (const v of rule[1]) {
      const prev = out[out.length - 1];
      if (prev && prev.v === v) prev.d += VISEMES[v].d * 0.4;   // "ss", "mm": nur verlängern
      else out.push({ v: v, d: VISEMES[v].d });
    }
    i += rule[0].length;
  }
  out.push({ v: "rest", d: 2 });                          // am Ende Mund schließen
  // Zeitleiste in Sekunden + leichte Variation der Stärke
  let t = 0;
  return out.map(seg => {
    const dur = seg.d * LIPSYNC.unit;
    const gain = 1 - LIPSYNC.variation + Math.random() * LIPSYNC.variation * 2;
    const item = { v: seg.v, start: t, dur: dur, gain: gain };
    t += dur;
    return item;
  });
}

const lipsync = {
  timeline: [],
  startTime: 0,
  weights: { A: 0, I: 0, U: 0, E: 0, O: 0 },   // aktuell angezeigte (geglättete) Werte
};

/** Text sprechen: mit Stimme (voice.js, lokaler TTS), sonst nur Mundbewegung. */
function speak(text) {
  text = String(text || "").trim();
  if (!text) return;
  stopSpeaking();
  // Längere Sätze mit den Händen begleiten (Schalter "Gesten beim Sprechen")
  if (talkGestures.enabled && text.length >= talkGestures.minChars && !gesture) {
    const tl = textToVisemes(text), last = tl[tl.length - 1];
    playGesture("🤲 Argumentieren", Math.max(1.5, last.start + last.dur - 0.3));
  }
  if (typeof speakWithVoice === "function" && speakWithVoice(text)) return;
  startLipsync(text);
}

/** Mundbewegung aus dem Text. duration (s): auf die echte Länge des Audios strecken. */
function startLipsync(text, duration) {
  const tl = textToVisemes(text);
  if (duration > 0 && tl.length) {
    const last = tl[tl.length - 1], k = duration / (last.start + last.dur);
    for (const seg of tl) { seg.start *= k; seg.dur *= k; }
  }
  lipsync.timeline = tl;
  lipsync.startTime = performance.now() / 1000;
}

function stopSpeaking() {
  lipsync.timeline = [];
  if (typeof stopVoice === "function") stopVoice();
}
function isSpeaking() {
  if (typeof voiceActive === "function" && voiceActive()) return true;
  const tl = lipsync.timeline;
  return tl.length > 0 && performance.now() / 1000 - lipsync.startTime < tl[tl.length - 1].start + tl[tl.length - 1].dur;
}

/** Ziel-Mischung zum Zeitpunkt t: aktueller Laut, gegen Ende in den nächsten geblendet */
function lipsyncTarget(t) {
  const target = { A: 0, I: 0, U: 0, E: 0, O: 0 };
  const tl = lipsync.timeline;
  if (!tl.length) return target;
  let k = tl.findIndex(seg => t < seg.start + seg.dur);
  if (k < 0) { lipsync.timeline = []; return target; }      // fertig
  const cur = tl[k], next = tl[k + 1];
  const local = (t - cur.start) / cur.dur;                  // 0..1 innerhalb des Lauts
  const blendStart = 1 - LIPSYNC.blendIn;
  let mix = 0;
  if (next && local > blendStart) {
    const x = (local - blendStart) / LIPSYNC.blendIn;
    mix = x * x * (3 - 2 * x);                              // smoothstep
  }
  const add = (seg, f) => {
    for (const [k2, val] of Object.entries(VISEMES[seg.v].w)) target[k2] += val * seg.gain * f;
  };
  add(cur, 1 - mix);
  if (next) add(next, mix);
  return target;
}

// --- Morph-Zugriff (Index-Cache pro Mesh) ----------------------------------
// Erst exakt suchen, dann ohne Groß/Klein - im Modell gibt es "kind" UND "Kind".
function morphIndex(mesh, name) {
  if (!mesh.__morphExactCache) mesh.__morphExactCache = {};
  if (!(name in mesh.__morphExactCache)) mesh.__morphExactCache[name] = morphIndexExact(mesh, [name]);
  return mesh.__morphExactCache[name];
}
function setMorph(name, value) {
  for (const mesh of morphMeshes) {
    const idx = morphIndex(mesh, name);
    if (idx >= 0) mesh.morphTargetInfluences[idx] = value;
  }
}

// --- Blinzeln -------------------------------------------------------------
const BLINK = { morph: "Blinzeln", close: 0.07, hold: 0.03, open: 0.11, minGap: 1.5, maxGap: 5.5 };
const blink = { phase: "wait", t: 0, next: 2 };

function updateBlink(dt) {
  if (manualMouthOpen) {               // Ausdruck "X)" schließt die Augen selbst -> nicht blinzeln
    blink.phase = "wait"; blink.t = 0;
    setMorph(BLINK.morph, 0);
    return;
  }
  blink.t += dt;
  let value = 0;
  if (blink.phase === "wait") {
    if (blink.t >= blink.next) { blink.phase = "blink"; blink.t = 0; }
  } else {
    const total = BLINK.close + BLINK.hold + BLINK.open;
    if (blink.t < BLINK.close) value = blink.t / BLINK.close;
    else if (blink.t < BLINK.close + BLINK.hold) value = 1;
    else if (blink.t < total) value = 1 - (blink.t - BLINK.close - BLINK.hold) / BLINK.open;
    else {
      blink.phase = "wait"; blink.t = 0;
      // manchmal Doppelblinzeln, sonst zufällige Pause
      blink.next = Math.random() < 0.15 ? 0.12 : BLINK.minGap + Math.random() * (BLINK.maxGap - BLINK.minGap);
    }
  }
  // Hält ein Ausdruck die Augen schon (halb) geschlossen, nur den Rest blinzeln
  setMorph(BLINK.morph, value * (1 - eyeClosedness));
}

// --- Manueller Mund (Taste M, z. B. zum Testen) ----------------------------
const MANUAL_MOUTH_MORPH = "X)";
let manualMouthOpen = false;
window.addEventListener("keydown", (event) => {
  if (event.target === chatInput) return;                    // nicht beim Tippen im Chat
  if (event.key.toLowerCase() === "m") {
    manualMouthOpen = !manualMouthOpen;
    setMorph(MANUAL_MOUTH_MORPH, manualMouthOpen ? 1 : 0);
  }
});

function updateFace(dt) {
  updateExpressions(dt);           // Mimik (expressions.js) - vor dem Blinzeln
  updateBlink(dt);
  const t = performance.now() / 1000 - lipsync.startTime;
  const target = lipsyncTarget(t);
  // Läuft echtes Audio (voice.js), folgt die Mundöffnung seiner Lautstärke:
  // Mundformen aus dem Text, Öffnung aus dem Audio; in Pausen geht der Mund zu.
  const env = typeof voiceEnvelope === "function" ? voiceEnvelope(dt) : null;
  if (env !== null) {
    const sum = target.A + target.I + target.U + target.E + target.O;
    const open = 0.3 + 0.7 * env;
    for (const key of Object.keys(target)) target[key] *= open;
    if (sum < 0.15) {                // Text ohne Lautregeln (z. B. Japanisch): nur nach Lautstärke
      target.A = Math.max(target.A, 0.75 * env);
      target.O = Math.max(target.O, 0.2 * env);
    }
    if (env < 0.04) for (const key of Object.keys(target)) target[key] *= env / 0.04;
  }
  for (const key of Object.keys(lipsync.weights)) {
    const goal = Math.min(1, target[key]) * LIPSYNC.intensity;
    lipsync.weights[key] = damp(lipsync.weights[key], goal, LIPSYNC.smoothing, dt);
    setMorph(LIPSYNC.morphs[key], lipsync.weights[key]);
  }
  applyMorphOverrides();           // Shape Keys von Hand (Panel) haben das letzte Wort
}
