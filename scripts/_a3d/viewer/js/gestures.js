/* gestures.js - Gesten und Moderationsgesten (mit Easing, Fingern, Mimik)
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Aufbau einer Geste
   -------------------------------------------------------------------------
   "Name": {
     dur: 3.0,                 // Dauer in Sekunden
     face: "friendly",         // Ausdruck aus EXPRESSIONS (expressions.js), optional
     faceAmount: 1,            // Stärke des Ausdrucks
     apply: (t, g) => { ... }  // jeden Frame; t = Fortschritt 0..1
   }
   Helfer im apply (g):
     g.env(delay, opts)  Hüllkurve mit Schwung (outBack) rein, weich raus; delay in s
     g.time              Sekunden seit Start (für Rhythmus)
   Richtungen sind Körperrichtungen: +X = linke Seite der Figur
   (vom Betrachter aus rechts), +Y = oben, +Z = vorne.
   ========================================================================= */

const mirror = v => dir(-v.x, v.y, v.z);
const LAG = { upper: 0, fore: 0.07, hand: 0.14 };   // Versatz der Gelenke in s (Schulter führt)

/** Arm ausrichten - Oberarm, Unterarm, Hand mit Versatz (overlapping action). */
function poseArm(side, upper, fore, hand, g, opts = {}) {
  const e = d => (typeof g === "number" ? g : g.env(d, opts));
  aim(rig["arm" + side],   rig["elbow" + side], upper, e(LAG.upper));
  if (fore) aim(rig["elbow" + side], rig["wrist" + side], fore, e(LAG.fore));
  if (hand) aim(rig["wrist" + side], rig["handTip" + side], hand, e(LAG.hand));
}

/** Handpose für diese Geste vorgeben (wird mit der Idle-Pose gemischt). */
function hand(side, pose, weight) {
  const cur = handTargets[side];
  if (!cur || weight > cur.weight) handTargets[side] = { pose, weight };
}

// turnHead(yaw, pitch, roll, w) steht in pose.js (wird auch vom Mausblick genutzt).

/** Klatsch-/Betonungs-Takte zwischen t0 und t1 (0..1), count Schläge. */
function beats(t, t0, t1, count, peak = 0.3) {
  if (t < t0 || t > t1) return 0;
  return pulse((t - t0) / (t1 - t0) * count, peak);
}

const GESTURE_GROUPS = {
  "🤸 Gesten": {
    "🙂 Nicken": { dur: 1.6, face: "smile", apply: (t) => {
      // kurz hoch (Ausholen), zwei Nicker - der zweite kleiner
      const p = keys(t, [[0, 0], [0.10, -0.06, "out"], [0.28, 0.30], [0.43, 0.04], [0.59, 0.21], [0.76, 0.03], [1, 0]]);
      turnHead(0, p, 0);
    } },
    "🙅 Kopfschütteln": { dur: 1.8, face: "doubtful", faceAmount: 0.6, apply: (t, g) => {
      const y = keys(t, [[0, 0], [0.14, 0.34, "out"], [0.30, -0.32, "inOutSine"], [0.46, 0.26, "inOutSine"],
                          [0.62, -0.18, "inOutSine"], [0.78, 0.08, "inOutSine"], [1, 0, "inOutSine"]]);
      turnHead(y, 0.06 * g.env(0), 0);
    } },
    "🙇 Verbeugen": { dur: 2.6, face: "content", apply: (t, g) => {
      const bend = keys(t, [[0, 0], [0.08, -0.04, "out"], [0.38, 1], [0.62, 1], [1, 0]]);
      const head = keys(t, [[0, 0], [0.16, 0], [0.45, 1], [0.66, 1], [1, 0]]);   // Kopf folgt verzögert
      rotate(rig.upper, AXIS.x, 0.45 * bend);
      rotate(rig.lower, AXIS.x, 0.08 * bend);
      rotate(rig.head, AXIS.x, 0.18 * head);
      poseArm("L", dir(0.05, -1.0, 0.25), null, null, g);
      poseArm("R", dir(-0.05, -1.0, 0.25), null, null, g);
      hand("L", "flat", 0.6 * g.env(0.1)); hand("R", "flat", 0.6 * g.env(0.1));
    } },
    "👋 Winken": { dur: 3.0, face: "friendly", apply: (t, g) => {
      const amp = keys(t, [[0, 0], [0.18, 0], [0.30, 1, "out"], [0.78, 1], [0.88, 0]]);
      const wave = Math.sin(g.time * Math.PI * 2 * 2.4) * amp;          // Hand schwenkt
      poseArm("R", dir(-0.85, 0.30, 0.35), dir(-0.15 + 0.35 * wave, 1.0, 0.25),
                   dir(-0.10 + 0.50 * wave, 1.0, 0.15), g, { attack: 0.45 });
      hand("R", "wave", g.env(LAG.hand));
      orientPalm("R", dir(0, 0, 1), g.env(LAG.hand));                    // Handfläche zum Betrachter
      turnHead(-0.06, -0.02, 0.10, g.env(0.1));
      rotate(rig.upper, AXIS.z, -0.04 * g.env(0));
    } },
    "🤔 Kopf neigen": { dur: 2.4, face: "curious", apply: (t) => {
      const r = keys(t, [[0, 0], [0.28, -0.24, "outBack"], [0.70, -0.21], [1, 0]]);
      turnHead(-r * 0.35, 0, r);
    } }
  },

  "🎤 Moderation": {
    "👉 Nach rechts zeigen": { dur: 3.4, face: "friendly", faceAmount: 0.8, apply: (t, g) => pointTo("L", t, g) },
    "👈 Nach links zeigen":  { dur: 3.4, face: "friendly", faceAmount: 0.8, apply: (t, g) => pointTo("R", t, g) },

    // Beide Hände öffnen sich nach vorne: "Hier sehen Sie ..."
    "🙌 Präsentieren": { dur: 3.2, face: "friendly", apply: (t, g) => {
      const open = 0.15 * keys(t, [[0, 0], [0.3, 0], [0.6, 1, "inOutSine"], [1, 1]]);
      const up = dir(0.40, -0.80, 0.55), fore = dir(0.45 + open, 0.05, 0.90), hd = dir(0.55 + open, 0.15, 0.80);
      poseArm("L", up, fore, hd, g, { attack: 0.5 });
      poseArm("R", mirror(up), mirror(fore), mirror(hd), g, { attack: 0.5, delay: 0.04 });
      for (const s of ["L", "R"]) { hand(s, "open", g.env(LAG.hand)); orientPalm(s, dir(0, 0.8, 0.6), g.env(LAG.hand)); }
      rotate(rig.upper, AXIS.x, -0.04 * g.env(0));
      turnHead(0, keys(t, [[0, 0], [0.35, 0], [0.5, 0.12], [0.65, 0], [1, 0]]), 0);
    } },

    // Erklären: Hände betonen abwechselnd im Takt, Oberkörper und Kopf gehen mit
    "🤲 Argumentieren": { dur: 4.0, face: "engaged", apply: (t, g) => {
      const beatL = pulse(g.time / 0.62, 0.28), beatR = pulse(g.time / 0.62 + 0.5, 0.28);
      const sway = Math.sin(g.time * 1.3);
      for (const [side, beat, sx] of [["L", beatL, 1], ["R", beatR, -1]]) {
        poseArm(side, dir(0.22 * sx, -0.95, 0.30),
                      dir((0.20 + 0.10 * sway * sx) * sx, -0.12 - 0.30 * beat, 1.0),
                      dir(0.25 * sx, -0.05 - 0.40 * beat, 0.9), g);
        hand(side, "half", g.env(LAG.hand));
        orientPalm(side, dir(-0.8 * sx, 0.5, 0.3), g.env(LAG.hand));      // Handflächen zueinander/oben
      }
      rotate(rig.upper, AXIS.y, 0.06 * sway * g.env(0));
      turnHead(-0.06 * sway, 0.05 * (beatL + beatR), 0.04 * sway, g.env(0.05));
    } },

    // Zeigefinger hoch: "Wichtig!" - mit kurzen Betonungen
    "☝️ Wichtiger Punkt": { dur: 3.0, face: "serious", apply: (t, g) => {
      const tap = beats(t, 0.32, 0.86, 3, 0.25);
      poseArm("R", dir(-0.30, -0.70, 0.50), dir(-0.10, 1.0, 0.30 + 0.30 * tap), dir(-0.05, 1.0, 0.25 + 0.35 * tap), g, { attack: 0.4 });
      hand("R", "point", g.env(LAG.hand));
      orientPalm("R", dir(0.5, 0, 1), g.env(LAG.hand));
      turnHead(-0.05, 0.08 * tap, 0.05, g.env(0.1));
    } },

    "🤷 Achselzucken": { dur: 2.4, face: "doubtful", apply: (t, g) => {
      const up = keys(t, [[0, 0], [0.20, 1, "out"], [0.52, 1], [0.85, 0, "inOut"], [1, 0]]);   // schnell hoch, langsam runter
      rotate(rig.shoulderL, AXIS.z, 0.22 * up);
      rotate(rig.shoulderR, AXIS.z, -0.22 * up);
      const upper = dir(0.35, -0.95, 0.15), fore = dir(0.80, -0.10, 0.55), hd = dir(0.85, 0.05, 0.45);
      poseArm("L", upper, fore, hd, g);
      poseArm("R", mirror(upper), mirror(fore), mirror(hd), g);
      for (const s of ["L", "R"]) { hand(s, "open", g.env(LAG.hand)); orientPalm(s, dir(0, 1, 0.2), g.env(LAG.hand)); }
      turnHead(0, -0.05 * up, 0.14 * g.env(0.05));
    } },

    // Hand ans Kinn, der andere Arm stützt den Ellbogen
    "🤔 Nachdenken": { dur: 3.8, face: "thinking", apply: (t, g) => {
      const e = g.env(0, { attack: 0.6 }), eh = g.env(LAG.hand, { attack: 0.6 });
      reachTo("R", bodyPointFrom(rig.head, -0.02, -0.06, 0.10), e, dir(-0.2, -1, 0.1)); // Handgelenk unterm Kinn
      aimAt(rig.wristR, rig.handTipR, bodyPointFrom(rig.head, -0.01, 0.02, 0.12), eh);    // Knöchel ans Kinn
      hand("R", "chin", eh);
      poseArm("L", dir(0.10, -1.0, 0.15), dir(-0.75, -0.05, 0.65), dir(-0.85, 0.0, 0.5), g, { attack: 0.6, delay: 0.15 });
      hand("L", "half", g.env(0.3));
      const tilt = keys(t, [[0, 0], [0.25, 1, "out"], [0.55, 0.85], [0.75, 1], [1, 0]]);
      turnHead(0.12 * tilt, -0.10 * tilt, -0.12 * tilt);
    } },

    "👏 Klatschen": { dur: 2.6, face: "happy", apply: (t, g) => {
      const close = beats(t, 0.18, 0.86, 5, 0.38);                        // schnell zusammen, weich auseinander
      const e = g.env(0, { attack: 0.35 }), eh = g.env(LAG.hand);
      // Ellbogen am Körper, Unterarme nach vorn, Hände nach vorn-oben: so können
      // sich die Handflächen zueinander drehen und flach aufeinandertreffen.
      const center = bodyPointFrom(rig.upper2, 0, -0.08, 0.30);
      const gap = 0.035 + 0.10 * (1 - close);                            // halber Abstand der Handgelenke
      reachTo("L", offsetBody(center, gap, 0, 0), e);                     // IK: Hände treffen sich wirklich
      reachTo("R", offsetBody(center, -gap, 0, 0), e);
      aim(rig.wristL, rig.handTipL, dir(-0.25, 0.45, 1), eh);
      aim(rig.wristR, rig.handTipR, dir(0.25, 0.45, 1), eh);
      for (const s of ["L", "R"]) hand(s, "flat", eh);
      orientPalm("L", dir(-1, 0, 0), eh);                                 // Handflächen zueinander
      orientPalm("R", dir(1, 0, 0), eh);
      rotate(rig.upper, AXIS.x, 0.025 * close * e);                       // kleiner Wipper bei jedem Klatschen
      turnHead(0, 0.05 * close, 0, e);
    } }
  }
};

/** Zeigen zur Seite: Arm mit Schwung, Zeigefinger, Blick kurz hin und zurück. */
function pointTo(side, t, g) {
  const sx = side === "L" ? 1 : -1;
  const up = dir(0.85 * sx, 0.05, 0.50), fore = dir(0.80 * sx, 0.22, 0.55), hd = dir(0.80 * sx, 0.25, 0.50);
  poseArm(side, up, fore, hd, g, { attack: 0.45 });
  hand(side, "point", g.env(LAG.hand));
  orientPalm(side, dir(0, -0.6, 0.8), g.env(LAG.hand));
  rotate(rig.upper, AXIS.y, 0.12 * sx * g.env(0));
  const look = keys(t, [[0, 0], [0.12, 0], [0.28, 1, "out"], [0.55, 1], [0.72, 0], [1, 0]]);
  turnHead(0.45 * sx * look, -0.03 * look, 0);
}

// Flache Liste aller Gesten (Name -> Definition)
const GESTURES = Object.assign({}, ...Object.values(GESTURE_GROUPS));

/** Spielt eine Geste; dur überschreibt optional die Standarddauer. */
function playGesture(name, dur) {
  if (!GESTURES[name]) return;
  gesture = { name: name, t0: performance.now(), dur: dur || GESTURES[name].dur };
}

function applyGesture() {
  if (!gesture) return;
  const def = GESTURES[gesture.name];
  const elapsed = (performance.now() - gesture.t0) / 1000;
  const t = elapsed / gesture.dur;
  if (t >= 1) { gesture = null; return; }
  const dur = gesture.dur;
  const g = {
    time: elapsed, dur,
    env: (delay = 0, opts = {}) => gestureEnvelope(t, dur, Object.assign({ delay,
      attack: Math.min(0.4, dur * 0.18), release: Math.min(0.55, dur * 0.25) }, opts))
  };
  def.apply(t, g);
  if (def.face) {
    expr.gesture = { name: def.face, amount: (def.faceAmount || 1) *
      gestureEnvelope(t, dur, { attack: 0.25, release: 0.5, easeIn: "out" }) };
  }
}

// Beim Sprechen automatisch gestikulieren (Schalter im Panel)
const talkGestures = { enabled: false, minChars: 20 };   // aus: wird später anders gelöst

/** Panel-Abschnitt: eine Überschrift pro Gruppe, ein Knopf pro Geste. */
function buildGestureSection(panel) {
  for (const [title, group] of Object.entries(GESTURE_GROUPS)) {
    panel.appendChild(makeHeading(title));
    Object.keys(group).forEach(name => {
      const b = document.createElement("button");
      b.textContent = name;
      b.onclick = () => playGesture(name);
      panel.appendChild(b);
    });
    if (title === "🤸 Gesten") {            // Streicheln (pet.js) gehört zu den Gesten
      const p = document.createElement("button");
      p.textContent = "🤗 Streicheln";
      p.title = "Oder einfach mit der Maus ein paar Mal über den Kopf fahren";
      p.onclick = () => petHead(2.5);
      panel.appendChild(p);
      panel.appendChild(makeToggle("🖐 Streicheln mit der Maus", () => PET.enabled, v => { PET.enabled = v; }));
    }
  }
  panel.appendChild(makeToggle("🗣 Gesten beim Sprechen", () => talkGestures.enabled, v => { talkGestures.enabled = v; }));
}
