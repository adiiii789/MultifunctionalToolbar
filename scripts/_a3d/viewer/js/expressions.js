/* expressions.js - Mimik: Ausdrücke als Mischung von Shape Keys, weich überblendet
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Ebenen (werden addiert, Ergebnis auf 0..1 begrenzt):
   1. Grundstimmung   setMood("smile", 0.3)            - bleibt, bis sie geändert wird
   2. Gesten-Mimik    automatisch aus GESTURE_GROUPS (face: "...")
   3. Kurzer Ausdruck setExpression("surprised", 1, 2)  - für 2 s, dann zurück
   4. Mikromimik im Idle (kurzes Lächeln beim Hinschauen, Brauen heben)
   Lippensync (a/i/u/e/o) läuft separat in face.js; Mund-Ausdrücke werden beim
   Sprechen automatisch abgeschwächt, damit sich nichts beißt. */

/* =========================================================================
   Shape Keys: Rolle -> [Originalname aus der PMX, umbenannter Name im GLB]
   Gesucht wird erst exakt (Groß/Klein zählt: "kind" ≠ "Kind"), dann ohne Groß/Klein.
   ========================================================================= */
const MORPHS = {
  // Mund
  mouthA: ["あ", "a"], mouthI: ["い", "i"], mouthU: ["う", "u"], mouthE: ["え", "e"], mouthO: ["お", "o"],
  mouthTriangle: ["▲", "o▲o"],          // kleines offenes Dreieck (überrascht, "oh")
  mouthPout:     ["∧", "o∧o"],          // Schmollmund / nachdenklich
  mouthCat:      ["ω", "oωo"],          // Katzenmund geschlossen
  mouthCatOpen:  ["ω□", "ωA"],          // Katzenmund offen (fröhlich)
  mouthWa:       ["ワ", "oワo"],         // weit offen, lachend
  mouthYu:       ["ゆ", "yu"],          // kleiner runder Mund
  mouthSmileOpen:["わらい口", "hehe mund"], // breites Lächeln, leicht offen
  mouthScream:   ["叫び", "scream"],
  mouthEh:       ["えー", "eeehh"],      // "ähh", skeptisch
  mouthSmirk:    ["にやり", ":)"],        // geschlossenes Lächeln
  // Augen
  blink:         ["まばたき", "Blinzeln"],
  eyesHappy:     ["笑い", "kind"],        // ^^ geschlossen lachend
  eyesSqueeze:   ["ｷﾞｭｯ", ">:)"],        // fest zugekniffen
  eyesHau:       ["はぅ", "X)"],          // ><
  eyesCalm:      ["なごみ", "-_-"],       // entspannt, fast zu
  eyesWide:      ["びっくり", "O_O"],      // weit offen, überrascht
  eyesHalf:      ["じと目", "Azusa"],      // halb geschlossen, skeptisch
  eyesSharp:     ["ｷﾘｯ", "evil"],         // entschlossen
  eyesDroopy:    ["たれ目", "Kind"],       // hängend, sanft
  eyesUpturned:  ["つり目", "eye alt"],
  eyesSmile:     ["笑い目", "hehe eye"],    // lächelnde Augen (Unterlid hoch)
  eyesNanu:      ["なぬ！", "Nani 1"],
  // Brauen
  browSerious:   ["真面目", ">:I"],
  browTroubled:  ["困る", "sad"],
  browSmile:     ["にこり", "aufmerksam"],
  browAngry:     ["怒り", "angry"],
  browFlat:      ["平行", "neutral"],
  browClose:     ["近", "shift"],
  browApart:     ["離", "unshift"],
  browShort:     ["短", "smol brow"],
  browUp:        ["上", "up brow"],
  browDown:      ["下", "down brow"],
  browForward:   ["前", "vor"],
  // Sonstiges
  pupilSmall:    ["瞳小", "insane"],
  pupilCat:      ["瞳縦", "cat"]
};

// Morphs, die die Augen schließen -> währenddessen nicht zusätzlich blinzeln
const EYE_CLOSERS = { blink: 1, eyesHappy: 1, eyesSqueeze: 1, eyesHau: 1, eyesCalm: 0.8, eyesHalf: 0.45 };
// Mund-Morphs der Ausdrücke -> beim Sprechen abschwächen
const MOUTH_ROLES = new Set(Object.keys(MORPHS).filter(k => k.startsWith("mouth")));

/* =========================================================================
   Ausdrücke = Mischung aus Rollen (Werte 0..1). Eigene einfach ergänzen.
   ========================================================================= */
const EXPRESSIONS = {
  neutral:   {},
  smile:     { mouthSmirk: 0.95, eyesSmile: 0.5, browSmile: 0.6 },
  friendly:  { mouthSmirk: 0.6, eyesSmile: 0.45, browSmile: 0.7, browUp: 0.25 },
  happy:     { eyesHappy: 0.9, mouthCatOpen: 0.55, browSmile: 0.8 },
  laugh:     { eyesHappy: 1.0, mouthWa: 0.65, browSmile: 0.9 },
  surprised: { eyesWide: 0.85, mouthTriangle: 0.7, browUp: 0.9 },
  curious:   { browUp: 0.55, mouthSmirk: 0.3, eyesWide: 0.15 },
  thinking:  { mouthPout: 0.6, browSerious: 0.45, browClose: 0.5, eyesHalf: 0.25 },
  doubtful:  { browTroubled: 0.8, mouthEh: 0.5, eyesDroopy: 0.35 },
  serious:   { browSerious: 0.6, eyesSharp: 0.7, browClose: 0.3, mouthPout: 0.2 },
  sad:       { browTroubled: 1.0, eyesDroopy: 0.9, eyesHalf: 0.25, mouthPout: 0.45 },
  proud:     { eyesCalm: 0.55, mouthSmirk: 0.8, browSmile: 0.5 },
  annoyed:   { eyesHalf: 0.6, mouthPout: 0.4, browAngry: 0.3 },
  content:   { eyesHappy: 0.75, mouthSmirk: 0.6, browSmile: 0.6 },      // zufrieden, Augen ^^ (Verbeugen)
  engaged:   { browUp: 0.3, mouthSmirk: 0.25, eyesSharp: 0.2 },         // bei der Sache (Erklären)
  petted:    { eyesHau: 1.0, mouthSmirk: 0.5, browSmile: 0.5 }          // gestreichelt: Augen >< (pet.js)
};

const expr = {
  mood: { name: "neutral", amount: 1 },
  temp: null,                 // {name, amount, t0, dur}
  idle: {},                   // Mikromimik: Rolle -> Wert
  idleNext: 3,
  weights: {},                // aktuell angezeigte Werte (geglättet)
  vel: {},                    // Geschwindigkeiten für smoothDamp
  gesture: null               // {name, amount} - von applyGesture jeden Frame gesetzt
};

/** Grundstimmung setzen (bleibt): setMood("smile", 0.3) */
function setMood(name, amount = 1) {
  if (EXPRESSIONS[name]) expr.mood = { name, amount };
}
/** Kurzer Ausdruck: setExpression("surprised", 1, 2) -> 2 s, dann zurück zur Stimmung */
function setExpression(name, amount = 1, seconds = 2) {
  if (EXPRESSIONS[name]) expr.temp = { name, amount, t0: performance.now() / 1000, dur: seconds };
}

// --- Morph-Auflösung: Rolle -> Index pro Mesh (exakt vor Groß/Klein) -------
function morphIndexExact(mesh, names) {
  const dict = mesh.morphTargetDictionary || {};
  for (const n of names) if (n in dict) return dict[n];
  for (const n of names) {
    const k = Object.keys(dict).find(x => x.toLowerCase() === n.toLowerCase());
    if (k !== undefined) return dict[k];
  }
  return -1;
}
function roleIndex(mesh, role) {
  if (!mesh.__roleCache) mesh.__roleCache = {};
  if (!(role in mesh.__roleCache)) mesh.__roleCache[role] = morphIndexExact(mesh, MORPHS[role] || [role]);
  return mesh.__roleCache[role];
}
function setRole(role, value) {
  for (const mesh of morphMeshes) {
    const i = roleIndex(mesh, role);
    if (i >= 0) mesh.morphTargetInfluences[i] = value;
  }
}

function addExpression(target, name, amount) {
  const e = EXPRESSIONS[name];
  if (!e || amount <= 0) return;
  for (const [role, v] of Object.entries(e)) target[role] = (target[role] || 0) + v * amount;
}

/* Mikromimik im Idle: ab und zu ein kurzes Lächeln oder Brauenheben,
   damit das Gesicht nicht eingefroren wirkt. */
function updateIdleMicro(time) {
  if (time >= expr.idleNext) {
    const r = Math.random();
    expr.idle = r < 0.35 ? { mouthSmirk: 0.35, eyesSmile: 0.2, browSmile: 0.3 }
              : r < 0.55 ? { browUp: 0.35 }
              : r < 0.7  ? { eyesSmile: 0.25 }
              : {};
    expr.idleUntil = time + 0.8 + Math.random() * 1.8;
    expr.idleNext = time + 3 + Math.random() * 6;
  }
  if (expr.idleUntil && time > expr.idleUntil) { expr.idle = {}; expr.idleUntil = 0; }
}

let eyeClosedness = 0;   // 0..1 - wird von face.js fürs Blinzeln genutzt

/* Shape Keys von Hand (Panel "🧪 Shape Keys"): überschreiben alles andere,
   solange der Wert > 0 ist. Angewendet ganz am Ende von updateFace(). */
const MORPH_LIMIT_WEBGL1 = 8;      // ohne WebGL 2 rendert three.js nur so viele gleichzeitig
const morphOverrides = {};         // Shape-Key-Name -> Wert
function setMorphOverride(name, value) {
  if (value > 0) { morphOverrides[name] = value; return; }
  delete morphOverrides[name];
  setMorph(name, 0);               // freigeben: Mimik/Lippensync setzen ihn ab jetzt wieder
}
function clearMorphOverrides() {
  for (const name of Object.keys(morphOverrides)) setMorphOverride(name, 0);
}
function applyMorphOverrides() {
  for (const [name, value] of Object.entries(morphOverrides)) setMorph(name, value);
}

function updateExpressions(dt) {
  const time = performance.now() / 1000;
  const target = {};
  addExpression(target, expr.mood.name, expr.mood.amount);
  if (idleEnabled) { updateIdleMicro(time); for (const [r, v] of Object.entries(expr.idle)) target[r] = (target[r] || 0) + v; }
  if (expr.gesture) addExpression(target, expr.gesture.name, expr.gesture.amount);
  if (typeof pet !== "undefined" && pet.weight > 0.002) addExpression(target, "petted", pet.weight);
  if (expr.temp) {
    const k = (time - expr.temp.t0) / expr.temp.dur;
    if (k >= 1) expr.temp = null;
    else addExpression(target, expr.temp.name, expr.temp.amount * gestureEnvelope(k, expr.temp.dur, { attack: 0.2, release: 0.4, easeIn: "out" }));
  }
  expr.gesture = null;

  // Beim Sprechen Mund-Ausdrücke abschwächen (Lippensync hat Vorrang)
  const speaking = typeof isSpeaking === "function" && isSpeaking() ? 1 : 0;
  expr.speak = damp(expr.speak || 0, speaking, 10, dt);

  eyeClosedness = 0;
  const roles = new Set([...Object.keys(target), ...Object.keys(expr.weights)]);
  for (const role of roles) {
    let goal = clamp(target[role] || 0, 0, 1);
    if (MOUTH_ROLES.has(role)) goal *= 1 - 0.75 * expr.speak;
    if (!expr.vel[role]) expr.vel[role] = { v: 0 };
    // weich mit Beschleunigen und Abbremsen (statt linear)
    const w = clamp(smoothDamp(expr.weights[role] || 0, goal, expr.vel[role], 0.12, dt), 0, 1);
    expr.weights[role] = w;
    setRole(role, w);
    if (EYE_CLOSERS[role]) eyeClosedness = Math.max(eyeClosedness, w * EYE_CLOSERS[role]);
    if (w < 1e-4 && goal === 0) { delete expr.weights[role]; setRole(role, 0); }
  }
}
