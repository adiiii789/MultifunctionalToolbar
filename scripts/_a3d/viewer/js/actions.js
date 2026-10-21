/* actions.js - Aktionen im Chat: "[kategorie.funktion]" wird nicht angezeigt/gesprochen, sondern ausgeführt
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Beispiel:
     "[geste.winken] Hallo, ich bin Miku! [station.Board Mitte] Hier seht ihr die Zahlen. [mimik.fröhlich] Super, oder?"
   -> Chat zeigt:  Hallo, ich bin Miku! Hier seht ihr die Zahlen. Super, oder?
   -> Ablauf:      winken + "Hallo, ich bin Miku!" sprechen, dann zum Board laufen (warten
                   bis angekommen), "Hier seht ihr ..." sprechen, fröhlich schauen, "Super, oder?"
   Alles läuft der Reihe nach; eine neue Nachricht bricht den laufenden Ablauf ab.

   Schreibweise: [kategorie.funktion] oder [kategorie.funktion(wert)]
     [geste.winken]  [geste.rechts zeigen]  [geste.streicheln]
     [station.Board Mitte]  [station.Start]          läuft hin, wartet bis angekommen
     [mimik.fröhlich]  [mimik.überrascht(4)]         kurzer Ausdruck, optional Sekunden
     [stimmung.lächeln]  [stimmung.neutral]          Grundstimmung, bleibt
     [clip.Tanz_Drehen]                              Blender-Animation
     [board.zeige(board/folie2.html)]  [board.leeren]
     [pause.1.5]                                     warten (Sekunden)
     [bewegung.idle]  [bewegung.laufen]  [bewegung.stopp]
   Groß/Klein ist egal; Leerzeichen und "_" sind gleichwertig ("Board_Mitte").
   Nur Klammern mit bekannter Kategorie sind Aktionen - "[1]" oder "[siehe oben]"
   bleiben normaler Text. Unbekannte Funktion in bekannter Kategorie: wird
   ausgeblendet und übersprungen (Warnung in der Konsole).

   Von außen (Python per runJavaScript, Assistenten-Logik):
     assistantMessage("Text mit [aktionen]")   -> führt aus, zeigt als "Miku" im Chat, sobald die Stimme einsetzt
     runActions("Text mit [aktionen]")         -> nur ausführen, ohne Chat
     stripActions("Text [geste.winken]")       -> "Text"                                  */

const ACTIONS = {
  assistantName: "Miku",        // Absendername im Chat
  expressionSeconds: 2.5        // Standarddauer von [mimik.x]
};

// Kategorie (wie im Text geschrieben) -> interner Typ. Erster Eintrag = offizieller Name.
const ACTION_CATEGORIES = {
  geste: "gesture", gesture: "gesture",
  station: "walk", position: "walk", gehe: "walk", walk: "walk",
  mimik: "expression", expression: "expression",
  stimmung: "mood", mood: "mood",
  clip: "clip", animation: "clip",
  board: "board",
  pause: "pause", wait: "pause",
  bewegung: "motion", motion: "motion"
};

// Deutsche Namen für die Ausdrücke aus expressions.js (die englischen Schlüssel gehen auch)
const EXPRESSION_ALIASES = {
  "lächeln": "smile", "laecheln": "smile", "freundlich": "friendly", "fröhlich": "happy", "froehlich": "happy",
  "glücklich": "happy", "gluecklich": "happy", "lachen": "laugh", "überrascht": "surprised",
  "ueberrascht": "surprised", "neugierig": "curious", "nachdenklich": "thinking",
  "zweifelnd": "doubtful", "skeptisch": "doubtful", "ernst": "serious", "traurig": "sad", "stolz": "proud",
  "genervt": "annoyed", "zufrieden": "content", "engagiert": "engaged", "normal": "neutral"
};

// Englische Namen für die Gesten aus gestures.js (die deutschen gehen auch) - z. B. [gesture.wave]
const GESTURE_ALIASES = {
  "nod": "Nicken", "shake head": "Kopfschütteln", "bow": "Verbeugen", "wave": "Winken",
  "tilt head": "Kopf neigen", "point right": "Nach rechts zeigen", "present": "Präsentieren",
  "explain": "Argumentieren", "important point": "Wichtiger Punkt", "shrug": "Achselzucken",
  "think": "Nachdenken", "clap": "Klatschen"
};

const MOTION_FUNCTIONS = {
  idle: () => playAnimation(IDLE_NAME),
  laufen: () => playAnimation(WALK_PLACE_NAME),
  stopp: () => stopAnimation(), stop: () => stopAnimation()
};

/** Für Vergleiche: klein, ohne Emojis/Satzzeichen, "_" = Leerzeichen, Umlaute bleiben. */
function normName(s) {
  return String(s || "").toLowerCase().replace(/[^\p{L}\p{N}\s_]/gu, " ").replace(/_/g, " ").replace(/\s+/g, " ").trim();
}

/** Jedes Wort der Suche ist Anfang eines Worts im Namen ("rechts zeig" passt zu "nach rechts zeigen"). */
function wordsMatch(query, name) {
  const q = normName(query).split(" ").filter(Boolean), n = normName(name).split(" ");
  return q.length > 0 && q.every(w => n.some(x => x.startsWith(w)));
}
/** Genauer Name zuerst, sonst Wortanfänge. */
function findBest(query, names) {
  const nq = normName(query);
  return names.find(n => normName(n) === nq) || names.find(n => wordsMatch(query, n)) || null;
}

// [kategorie.rest] - Kategorie = Buchstaben, getrennt am ersten Punkt
const ACTION_RE = /\[\s*([A-Za-zÄÖÜäöüß]+)\s*\.\s*([^\[\]]{1,300}?)\s*\]/g;

/** Text in Abschnitte zerlegen: [{text}] und [{action: {category, kind, func, arg, raw}}] in Reihenfolge. */
function parseActions(message) {
  const parts = [];
  let last = 0, m;
  ACTION_RE.lastIndex = 0;
  while ((m = ACTION_RE.exec(message))) {
    const kind = ACTION_CATEGORIES[m[1].toLowerCase()];
    if (!kind) continue;                                  // keine Aktion -> bleibt Text
    if (m.index > last) parts.push({ text: message.slice(last, m.index) });
    // "fröhlich(4)" -> func "fröhlich", arg "4"
    const fm = m[2].match(/^([^()]*?)\s*\(([\s\S]*)\)$/);
    parts.push({ action: { category: m[1].toLowerCase(), kind, func: (fm ? fm[1] : m[2]).trim(),
                           arg: fm ? fm[2].trim() : "", raw: m[0] } });
    last = ACTION_RE.lastIndex;
  }
  if (last < message.length) parts.push({ text: message.slice(last) });
  return parts;
}

/** Nur der Text, ohne [Aktionen] (für Chat und Sprache). */
function stripActions(message) {
  return parseActions(String(message || "")).filter(p => p.text).map(p => p.text).join(" ")
    .replace(/\s+([.,!?;:])/g, "$1").replace(/\s+/g, " ").trim();
}

/** Geste zu einem Namen (deutsch, englischer Alias aus GESTURE_ALIASES oder Wortanfänge). */
function gestureName(value) {
  return findBest(GESTURE_ALIASES[normName(value)] || value, Object.keys(GESTURES));
}

function expressionName(value) {
  const n = normName(value);
  return EXPRESSION_ALIASES[n] || (EXPRESSIONS[n] ? n : findBest(value, Object.keys(EXPRESSIONS)));
}

const actionSleep = ms => new Promise(r => setTimeout(r, ms));
const actionNumber = s => parseFloat(String(s).replace(",", "."));

/** Eine Aktion ausführen. Gibt ein Promise zurück, wenn der Ablauf darauf warten soll. */
function executeAction(a) {
  const f = a.func, nf = normName(f);
  switch (a.kind) {
    case "gesture": {
      if (nf === "streicheln" || nf === "pet") { petHead(actionNumber(a.arg) > 0 ? actionNumber(a.arg) : 2.5); return null; }
      const name = gestureName(f);
      if (name) { playGesture(name); return null; }
      const face = expressionName(f);                 // falsche Kategorie erwischt (z. B. [gesture.happy])
      if (face) { setExpression(face, 1, ACTIONS.expressionSeconds); return null; }
      break;
    }
    case "walk": {
      const name = findBest(f, getStations());
      if (name) return walkTo(name);
      break;
    }
    case "expression": {
      const name = expressionName(f), secs = actionNumber(a.arg);
      if (name) { setExpression(name, 1, secs > 0 ? secs : ACTIONS.expressionSeconds); return null; }
      const gesture = gestureName(f);                 // falsche Kategorie erwischt (z. B. [expression.explain])
      if (gesture) { playGesture(gesture); return null; }
      break;
    }
    case "mood": {
      const name = expressionName(f);
      if (name) { setMood(name, 1); return null; }
      break;
    }
    case "clip": {
      const name = findBest(f, Object.keys(clipLibrary.clips));
      if (name) { playClip(name); return null; }
      break;
    }
    case "board": {
      if (/^(leeren|clear)$/.test(nf)) { clearBoard(); return null; }
      if (/^(zeige|zeigen|show)$/.test(nf) && a.arg) { showOnBoard(a.arg); return null; }
      break;
    }
    case "pause": {
      const s = actionNumber(a.arg || f);
      if (isFinite(s)) return actionSleep(clamp(s, 0, 60) * 1000);
      break;
    }
    case "motion":
      if (MOTION_FUNCTIONS[nf]) { MOTION_FUNCTIONS[nf](); return null; }
      break;
  }
  console.warn("Aktion nicht erkannt: " + a.raw);
  return null;
}

let actionToken = 0;
// Aktionen, die der Ablauf abwartet (statt sie mit dem nächsten Ton zu starten): Laufen, Pause
const ACTION_WAITS = new Set(["walk", "pause"]);

/** Text mit [Aktionen] der Reihe nach ausführen (Text wird gesprochen). Promise endet am Schluss
    (true = komplett, false = von einer neueren Nachricht abgebrochen). */
async function runActions(message, onSpeechStart) {
  const token = ++actionToken;
  // onSpeechStart: einmal, sobald die Stimme einsetzt (ohne Stimme: vor dem ersten Text, sonst am Ende)
  let speechStarted = false;
  const speechStart = () => {
    if (speechStarted) return;
    speechStarted = true;
    if (onSpeechStart) onSpeechStart();
  };
  try {
    return await runActionParts(message, token, speechStart);
  } finally {
    speechStart();                                   // abgebrochen/ohne Text: Nachricht trotzdem zeigen
  }
}

async function runActionParts(message, token, speechStart) {
  stopSpeaking();
  if (typeof cancelWalkTarget === "function") cancelWalkTarget();
  const parts = parseActions(String(message || ""));
  const speakable = text => /[\p{L}\p{N}]/u.test(text);   // reine Satzzeichen nicht sprechen

  // Mit Stimme: alle Textstücke gleich vertonen lassen (voice.js). Aktionen vor einem Textstück
  // gehen erst los, wenn dessen Ton fertig ist - sonst winkt die Figur Sekunden vor dem "Hallo".
  const texts = parts.filter(p => p.text).map(p => stripActions(p.text)).filter(speakable);
  const prepared = typeof prepareSpeech === "function" ? prepareSpeech(texts) : null;
  let nextText = 0;
  let waiting = [];                                  // Aktionen, die auf den nächsten Ton warten
  const run = async a => {
    try {
      const wait = executeAction(a);
      if (wait) await wait;
    } catch (e) {
      console.warn("Aktion " + a.raw + " fehlgeschlagen: " + e.message);
    }
  };
  const runWaiting = async () => {
    const list = waiting;
    waiting = [];
    for (const a of list) {
      if (token !== actionToken) return;
      await run(a);
    }
  };

  for (const part of parts) {
    if (token !== actionToken) return false;
    if (part.action) {
      if (prepared && !ACTION_WAITS.has(part.action.kind)) { waiting.push(part.action); continue; }
      await runWaiting();                            // Reihenfolge bleibt: Gesammeltes zuerst
      await run(part.action);                        // Laufen/Pause sofort - der Ton entsteht derweil
      continue;
    }
    const text = stripActions(part.text);
    if (!speakable(text)) continue;
    if (!prepared) {
      await runWaiting();
      speechStart();
      await speak(text);
      continue;
    }
    const segment = prepared[nextText++];
    await segment.ready;                             // erster Satz da -> jetzt setzt die Stimme ein
    if (token !== actionToken) return false;
    await runWaiting();                              // Gesten/Mimik genau mit dem Ton
    startTalkGesture(text);
    speechStart();                                   // Text im Chat genau mit dem Ton
    await segment.play();
  }
  await runWaiting();                                // Aktionen nach dem letzten Satz
  return token === actionToken;
}

/** Antwort des Assistenten: ausführen und den Text (ohne Aktionen) in den Chat - erst, wenn die
    Stimme einsetzt (höchstens TEXT_MAX_WAIT_MS später, falls die Stimme noch lädt).
    placeholder: Chat-Zeile ("denkt nach ..."), die bis dahin stehen bleibt. */
const TEXT_MAX_WAIT_MS = 12000;
function assistantMessage(message, placeholder) {
  const shown = stripActions(message);
  let done = false;
  const show = () => {
    if (done) return;
    done = true;
    clearTimeout(timer);
    if (placeholder) placeholder.remove();
    if (shown) addMessage(ACTIONS.assistantName, shown);
  };
  const timer = setTimeout(show, TEXT_MAX_WAIT_MS);
  return runActions(message, show);
}
