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
     g.shift(s)          Gewicht aufs linke (+1) oder rechte (-1) Bein verlagern
   Richtungen sind Körperrichtungen: +X = linke Seite der Figur
   (vom Betrachter aus rechts), +Y = oben, +Z = vorne.

   Damit eine Geste nicht wie ein Roboterarm wirkt:
   - Der ganze Körper macht mit (Gewicht aufs andere Bein, Oberkörper, Kopf) - die Füße
     bleiben dabei stehen, das regelt die Fuß-IK in walk.js.
   - Gelenke starten nacheinander (LAG), die Schulter hebt sich mit dem Arm (poseArm).
   - Eine gehaltene Pose steht nie ganz still (GESTURE.live).
   ========================================================================= */
const GESTURE = {
  live: 0.035,       // wie stark eine gehaltene Armpose "lebt" (0 = starr)
  shoulder: 0.20     // Schulter hebt sich mit, wenn der Arm über die Waagerechte geht (rad)
};

const mirror = v => dir(-v.x, v.y, v.z);
const LAG = { upper: 0, fore: 0.07, hand: 0.14 };   // Versatz der Gelenke in s (Schulter führt)

/** Arm ausrichten - Oberarm, Unterarm, Hand mit Versatz (overlapping action).
    opts.delay verschiebt den ganzen Arm (z. B. zweite Hand etwas später). */
function poseArm(side, upper, fore, hand, g, opts = {}) {
  const live = typeof g !== "number";
  const o = Object.assign({}, opts); delete o.delay;
  const e = d => (live ? g.env(d + (opts.delay || 0), o) : g);
  const sx = side === "L" ? 1 : -1;
  // Kleine, langsame Abweichung: Die Pose wird gehalten, aber nicht eingefroren
  const n = (k, seed) => (live ? GESTURE.live * k * smoothNoise(g.time * 1.3, seed + sx * 4.2) : 0);
  const wob = (v, k, seed) => dir(v.x + n(k, seed), v.y + n(k, seed + 1.7), v.z + n(k, seed + 3.1));
  // Schulter geht mit nach oben, je höher der Oberarm zeigt
  const lift = clamp((upper.y + 0.55) / 1.3, 0, 1);
  rotate(rig["shoulder" + side], AXIS.z, sx * GESTURE.shoulder * lift * e(LAG.upper));
  aim(rig["arm" + side],   rig["elbow" + side], wob(upper, 0.7, 1), e(LAG.upper));
  if (fore) aim(rig["elbow" + side], rig["wrist" + side], wob(fore, 1.2, 5), e(LAG.fore));
  if (hand) aim(rig["wrist" + side], rig["handTip" + side], wob(hand, 1.6, 9), e(LAG.hand));
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
    "🙂 Nicken": { dur: 1.7, face: "smile", apply: (t) => {
      // kurz hoch (Ausholen), zwei Nicker - der zweite kleiner; der Oberkörper nickt leicht verzögert mit
      const nod = x => keys(x, [[0, 0], [0.10, -0.06, "out"], [0.28, 0.30], [0.43, 0.04], [0.59, 0.21], [0.76, 0.03], [1, 0]]);
      turnHead(0, nod(t), 0.03 * Math.sin(t * Math.PI));
      rotate(rig.upper, AXIS.x, 0.05 * nod(Math.max(0, t - 0.05)));
      rotate(rig.shoulderL, AXIS.z, -0.03 * nod(t)); rotate(rig.shoulderR, AXIS.z, 0.03 * nod(t));
    } },
    "🙅 Kopfschütteln": { dur: 1.9, face: "doubtful", faceAmount: 0.6, apply: (t, g) => {
      const shake = x => keys(x, [[0, 0], [0.14, 0.34, "out"], [0.30, -0.32, "inOutSine"], [0.46, 0.26, "inOutSine"],
                                   [0.62, -0.18, "inOutSine"], [0.78, 0.08, "inOutSine"], [1, 0, "inOutSine"]]);
      turnHead(shake(t), 0.06 * g.env(0), -0.05 * shake(t));
      rotate(rig.upper, AXIS.y, -0.05 * shake(Math.max(0, t - 0.06)));   // Schultern leicht dagegen
    } },
    "🙇 Verbeugen": { dur: 2.8, face: "content", apply: (t, g) => {
      const bend = keys(t, [[0, 0], [0.08, -0.04, "out"], [0.38, 1], [0.62, 1], [1, 0]]);
      const head = keys(t, [[0, 0], [0.16, 0], [0.45, 1], [0.66, 1], [1, 0]]);   // Kopf folgt verzögert
      // Hüfte geht nach hinten (Gleichgewicht), Knie geben minimal nach - die Füße bleiben stehen
      translateBody(rig.center, 0, -0.012 * bend, -0.075 * bend);
      rotate(rig.upper, AXIS.x, 0.32 * bend);
      rotate(rig.upper2, AXIS.x, 0.16 * bend);
      rotate(rig.lower, AXIS.x, 0.10 * bend);
      rotate(rig.head, AXIS.x, 0.18 * head);
      poseArm("L", dir(0.07, -1.0, 0.30), dir(-0.10, -1.0, 0.35), null, g);
      poseArm("R", dir(-0.07, -1.0, 0.30), dir(0.10, -1.0, 0.35), null, g);
      hand("L", "flat", 0.6 * g.env(0.1)); hand("R", "flat", 0.6 * g.env(0.1));
      g.shift(0);
    } },
    "👋 Winken": { dur: 3.2, face: "friendly", apply: (t, g) => {
      const amp = keys(t, [[0, 0], [0.16, 0], [0.28, 1, "out"], [0.74, 1], [0.86, 0]]);
      // Hand schwenkt etwas schneller am Anfang, dann ruhiger; die Hand hängt dem Unterarm nach
      const ph = g.time * Math.PI * 2 * 2.3 + 0.5 * Math.sin(g.time * 2.1);
      const wave = Math.sin(ph) * amp, late = Math.sin(ph - 0.7) * amp;
      poseArm("R", dir(-0.85, 0.30, 0.35), dir(-0.15 + 0.32 * wave, 1.0, 0.25),
                   dir(-0.10 + 0.55 * late, 1.0, 0.15), g, { attack: 0.45 });
      hand("R", "wave", g.env(LAG.hand));
      orientPalm("R", dir(0, 0, 1), g.env(LAG.hand));                    // Handfläche zum Betrachter
      const e = g.env(0);
      g.shift(0.8);                                                       // Gewicht aufs linke Bein
      rotate(rig.upper, AXIS.z, (-0.05 + 0.012 * wave) * e);              // lehnt sich leicht in den Arm
      rotate(rig.upper, AXIS.y, -0.05 * e);
      turnHead(-0.06, -0.03, 0.10 + 0.02 * late, g.env(0.1));
      rotate(rig.armL, AXIS.z, -0.04 * e);                                // der andere Arm gleicht aus
    } },
    "🤔 Kopf neigen": { dur: 2.6, face: "curious", apply: (t, g) => {
      const r = keys(t, [[0, 0], [0.28, -0.24, "outBack"], [0.70, -0.21], [1, 0]]);
      turnHead(-r * 0.35, 0, r);
      rotate(rig.upper, AXIS.z, r * 0.12);                                // Oberkörper neigt sich ein wenig mit
      rotate(rig.shoulderL, AXIS.z, -r * 0.15);                           // eine Schulter kommt dem Kopf entgegen
      g.shift(-0.6);
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
      poseArm("R", mirror(up), mirror(fore), mirror(hd), g, { attack: 0.5, delay: 0.06 });
      for (const s of ["L", "R"]) { hand(s, "open", g.env(LAG.hand)); orientPalm(s, dir(0, 0.8, 0.6), g.env(LAG.hand)); }
      rotate(rig.upper, AXIS.x, (-0.04 + 0.25 * open) * g.env(0));        // richtet sich auf, lehnt sich dann leicht vor
      turnHead(0, keys(t, [[0, 0], [0.35, 0], [0.5, 0.12], [0.65, 0], [1, 0]]), 0);
      g.shift(0);
    } },

    // Erklären: Hände betonen abwechselnd, Oberkörper und Kopf gehen mit. Der Takt schwankt
    // leicht und nicht jede Betonung ist gleich stark - sonst wirkt es wie ein Metronom.
    "🤲 Argumentieren": { dur: 4.0, face: "engaged", apply: (t, g) => {
      const bt = g.time / 0.66 + 0.22 * smoothNoise(g.time * 0.9, 3.3);
      const strong = x => 0.65 + 0.35 * smoothNoise(Math.floor(x) * 2.7, 1.1);
      const beatL = pulse(bt, 0.28) * strong(bt), beatR = pulse(bt + 0.5, 0.28) * strong(bt + 0.5);
      const sway = Math.sin(g.time * 1.3 + 0.4 * Math.sin(g.time * 0.7));
      for (const [side, beat, sx] of [["L", beatL, 1], ["R", beatR, -1]]) {
        poseArm(side, dir(0.22 * sx, -0.95, 0.30),
                      dir((0.20 + 0.10 * sway * sx) * sx, -0.12 - 0.30 * beat, 1.0),
                      dir(0.25 * sx, -0.05 - 0.40 * beat, 0.9), g);
        hand(side, "half", g.env(LAG.hand));
        orientPalm(side, dir(-0.8 * sx, 0.5, 0.3), g.env(LAG.hand));      // Handflächen zueinander/oben
      }
      rotate(rig.upper, AXIS.y, 0.06 * sway * g.env(0));
      rotate(rig.upper, AXIS.x, 0.02 * (beatL + beatR) * g.env(0));
      turnHead(-0.06 * sway, 0.05 * (beatL + beatR), 0.04 * sway, g.env(0.05));
      g.shift(0.5 * sway);
    } },

    // Zeigefinger hoch: "Wichtig!" - mit kurzen Betonungen
    "☝️ Wichtiger Punkt": { dur: 3.0, face: "serious", apply: (t, g) => {
      const tap = beats(t, 0.32, 0.86, 3, 0.25);
      poseArm("R", dir(-0.30, -0.70, 0.50), dir(-0.10, 1.0, 0.30 + 0.30 * tap), dir(-0.05, 1.0, 0.25 + 0.35 * tap), g, { attack: 0.4 });
      hand("R", "point", g.env(LAG.hand));
      orientPalm("R", dir(0.5, 0, 1), g.env(LAG.hand));
      rotate(rig.upper, AXIS.x, (0.03 + 0.02 * tap) * g.env(0));          // beugt sich mit jeder Betonung leicht vor
      turnHead(-0.05, 0.08 * tap, 0.05, g.env(0.1));
      g.shift(0.5);
    } },

    "🤷 Achselzucken": { dur: 2.4, face: "doubtful", apply: (t, g) => {
      const up = keys(t, [[0, 0], [0.20, 1, "out"], [0.52, 1], [0.85, 0, "inOut"], [1, 0]]);   // schnell hoch, langsam runter
      rotate(rig.shoulderL, AXIS.z, 0.22 * up);
      rotate(rig.shoulderR, AXIS.z, -0.22 * up);
      const upper = dir(0.35, -0.95, 0.15), fore = dir(0.80, -0.10, 0.55), hd = dir(0.85, 0.05, 0.45);
      poseArm("L", upper, fore, hd, g);
      poseArm("R", mirror(upper), mirror(fore), mirror(hd), g, { delay: 0.03 });
      for (const s of ["L", "R"]) { hand(s, "open", g.env(LAG.hand)); orientPalm(s, dir(0, 1, 0.2), g.env(LAG.hand)); }
      turnHead(0, -0.05 * up, 0.14 * g.env(0.05));
      rotate(rig.upper, AXIS.z, 0.03 * g.env(0.05));
      g.shift(-0.7);
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
      g.shift(-0.8);
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
      translateBody(rig.center, 0, -0.008 * close * e, 0);                // federt bei jedem Klatschen leicht in die Knie
      rotate(rig.upper, AXIS.x, 0.03 * close * e);
      turnHead(0, 0.05 * close, 0.04 * Math.sin(g.time * 2.4) * e, e);
      g.shift(0);
    } },

    // Etwas zur rechten Bildschirmseite wegschieben bzw. von dort heranziehen (das Board, room.js)
    // internal: Die KI bekommt sie nicht als eigene Geste angeboten (assistant.js) - dafür gibt es [board.weg]
    "🫸 Schieben":    { dur: 2.6, face: "engaged", internal: true, apply: (t, g) => pushGesture(t, g, 1) },
    "🫷 Heranziehen": { dur: 2.6, face: "engaged", internal: true, apply: (t, g) => pushGesture(t, g, -1) }
  }
};

/** Zeigen zur Seite: erst der Blick, dann der Arm mit Schwung; der Körper lehnt sich mit. */
function pointTo(side, t, g) {
  const sx = side === "L" ? 1 : -1;
  const up = dir(0.85 * sx, 0.05, 0.50), fore = dir(0.80 * sx, 0.22, 0.55), hd = dir(0.80 * sx, 0.25, 0.50);
  poseArm(side, up, fore, hd, g, { attack: 0.45, delay: 0.12 });
  hand(side, "point", g.env(LAG.hand + 0.12));
  orientPalm(side, dir(0, -0.6, 0.8), g.env(LAG.hand + 0.12));
  rotate(rig.upper, AXIS.y, 0.12 * sx * g.env(0.05));
  rotate(rig.upper, AXIS.z, -0.03 * sx * g.env(0.05));
  g.shift(0.8 * sx);                                                     // Gewicht auf die Seite, zu der sie zeigt
  const look = keys(t, [[0, 0], [0.05, 0], [0.22, 1, "out"], [0.55, 1], [0.72, 0], [1, 0]]);
  turnHead(0.45 * sx * look, -0.03 * look, 0);
}

/** Schieben (sign 1) / Heranziehen (sign -1) zur rechten Bildschirmseite - unabhängig davon,
    wie die Figur gerade steht: Die Hände werden per IK an Punkte im Raum geführt. */
function pushGesture(t, g, sign) {
  // reach: 0 = Hände vor der Brust, 1 = Arme gestreckt
  const reach = sign > 0
    ? keys(t, [[0, 0], [0.20, 0.25, "out"], [0.32, 0.12], [0.62, 1, "inOut"], [0.80, 1], [1, 0.7]])
    : keys(t, [[0, 0], [0.26, 1, "out"], [0.40, 1], [0.74, 0.1, "inOut"], [1, 0]]);
  const e = g.env(0, { attack: 0.4 }), eh = g.env(LAG.hand, { attack: 0.4 });
  const chest = rig.upper2.getWorldPosition(new THREE.Vector3());
  const toBody = v => v.applyQuaternion(modelRoot.getWorldQuaternion(new THREE.Quaternion()).invert());
  for (const [side, dz] of [["L", -0.10], ["R", 0.10]]) {
    const p = chest.clone().add(dir(0.20 + 0.27 * reach, 0.03, 0.10 + dz));
    followTight[side] = 0.6 * clamp(e, 0, 1);
    solveLimb(rig["arm" + side], rig["elbow" + side], rig["wrist" + side], p, dir(0, -1, 0.2), e);
    aimWorld(rig["wrist" + side], rig["handTip" + side], dir(0.45, 1, 0), eh);   // Finger nach oben
    hand(side, "flat", eh);
    orientPalm(side, toBody(dir(1, 0, 0)), eh);                                  // Handflächen zum Board
  }
  // Körper dreht sich hin und legt sich hinein (beim Ziehen lehnt sie sich zurück)
  const lean = sign > 0 ? reach : 1 - reach;
  rotate(rig.upper, AXIS.y, 0.22 * e);
  rotate(rig.upper, AXIS.x, (sign > 0 ? 0.10 : -0.06) * lean * e);
  translateBody(rig.center, 0, -0.015 * lean * e, 0);
  turnHead(0.30, 0.04, 0, g.env(0));
  g.shift(0.6 * (sign > 0 ? reach : 1 - reach));
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
      attack: Math.min(0.4, dur * 0.18), release: Math.min(0.55, dur * 0.25) }, opts)),
    // Standbein vorgeben (idle.js: stance.bias), weich mit der Geste ein- und ausgeblendet
    shift: s => { stance.bias = stance.target + (s - stance.target) * clamp(g.env(0, { easeIn: "inOut" }), 0, 1); }
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
