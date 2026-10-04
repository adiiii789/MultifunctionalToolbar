/* gestures.js - Gesten und Moderationsgesten
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Gesten (laufen über Idle/Laufen bzw. über einem Clip)
   t = Fortschritt 0..1, e = Hüllkurve (weich rein/raus)
   Richtungen sind Körperrichtungen: +X = linke Seite der Figur
   (vom Betrachter aus rechts), +Y = oben, +Z = vorne.
   ========================================================================= */
function envelope(t, attack = 0.2, release = 0.25) {
  const ease = x => x * x * (3 - 2 * x);     // smoothstep
  if (t < attack) return ease(t / attack);
  if (t > 1 - release) return ease((1 - t) / release);
  return 1;
}
const ease01 = x => { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); };

/** Ganzen Arm ausrichten: Oberarm, Unterarm, Hand (Richtungen im Körperraum).
    side = "L" oder "R". Fehlende Richtung = Teil bleibt wie er ist. */
function poseArm(side, upper, fore, hand, w) {
  aim(rig["arm" + side],   rig["elbow" + side], upper, w);
  if (fore) aim(rig["elbow" + side], rig["wrist" + side], fore, w);
  if (hand) aim(rig["wrist" + side], rig["handTip" + side], hand, w);
}
/** Spiegelt eine Körperrichtung für die andere Seite (X umdrehen). */
const mirror = v => dir(-v.x, v.y, v.z);
/** Kopf (und anteilig Hals) drehen: yaw +links/-rechts (Figur), pitch +runter */
function turnHead(yaw, pitch, roll, w) {
  rotate(rig.neck, AXIS.y, yaw * 0.35 * w);
  rotate(rig.neck, AXIS.x, pitch * 0.35 * w);
  rotate(rig.head, AXIS.y, yaw * 0.65 * w);
  rotate(rig.head, AXIS.x, pitch * 0.65 * w);
  rotate(rig.head, AXIS.z, roll * w);
}

const GESTURE_GROUPS = {
  "🤸 Gesten": {
    "🙂 Nicken": { dur: 1.5, apply: (t, e) => {
      const nod = Math.pow(Math.sin(t * Math.PI * 2), 2);         // zwei Nicker
      turnHead(0, 0.32 * nod, 0, e);
    } },
    "🙅 Kopfschütteln": { dur: 1.6, apply: (t, e) => {
      turnHead(0.42 * Math.sin(t * Math.PI * 5), 0, 0, e);
    } },
    "🙇 Verbeugen": { dur: 2.4, apply: (t, e) => {
      rotate(rig.upper, AXIS.x, 0.45 * e);
      rotate(rig.lower, AXIS.x, 0.08 * e);
      rotate(rig.head, AXIS.x, 0.18 * e);
      poseArm("L", dir(0.05, -1.0, 0.25), null, null, e * 0.8);
      poseArm("R", dir(-0.05, -1.0, 0.25), null, null, e * 0.8);
    } },
    "👋 Winken": { dur: 2.8, apply: (t, e) => {
      const wave = Math.sin(t * Math.PI * 9);
      poseArm("R", dir(-0.85, 0.30, 0.35), dir(-0.15 + 0.45 * wave, 1.0, 0.25),
                   dir(-0.10 + 0.55 * wave, 1.0, 0.15), e);
      turnHead(0, 0, 0.10, e);
      rotate(rig.upper, AXIS.z, -0.04 * e);
    } },
    "🤔 Kopf neigen": { dur: 2.2, apply: (t, e) => {
      turnHead(0.08, 0, -0.22, e);
    } }
  },

  "🎤 Moderation": {
    // Zeigt zur Seite (vom Betrachter aus rechts), schaut kurz hin, dann zurück zum Publikum
    "👉 Nach rechts zeigen": { dur: 3.2, apply: (t, e) => {
      const look = ease01(t / 0.2) * (1 - ease01((t - 0.55) / 0.25));
      poseArm("L", dir(0.85, 0.05, 0.50), dir(0.80, 0.22, 0.55), dir(0.80, 0.25, 0.50), e);
      rotate(rig.upper, AXIS.y, 0.12 * e);
      turnHead(0.45 * look, -0.03 * look, 0, e);
    } },
    "👈 Nach links zeigen": { dur: 3.2, apply: (t, e) => {
      const look = ease01(t / 0.2) * (1 - ease01((t - 0.55) / 0.25));
      poseArm("R", dir(-0.85, 0.05, 0.50), dir(-0.80, 0.22, 0.55), dir(-0.80, 0.25, 0.50), e);
      rotate(rig.upper, AXIS.y, -0.12 * e);
      turnHead(-0.45 * look, -0.03 * look, 0, e);
    } },
    // Beide Hände öffnen sich nach vorne: "Hier sehen Sie ..."
    "🙌 Präsentieren": { dur: 3.0, apply: (t, e) => {
      const open = 0.15 * Math.sin(t * Math.PI);                  // öffnet sich weiter
      const up = dir(0.40, -0.80, 0.55), fore = dir(0.45 + open, 0.05, 0.90), hand = dir(0.55 + open, 0.15, 0.80);
      poseArm("L", up, fore, hand, e);
      poseArm("R", mirror(up), mirror(fore), mirror(hand), e);
      rotate(rig.upper, AXIS.x, -0.04 * e);                        // leicht aufrichten
      turnHead(0, -0.05 + 0.08 * Math.pow(Math.sin(t * Math.PI * 2), 2), 0, e);
    } },
    // Rhythmische Handbewegungen beim Erklären, Hände wechseln sich ab
    "🤲 Argumentieren": { dur: 4.0, apply: (t, e, g) => {
      const time = t * (g.dur || 4.0);
      const beatL = Math.pow(Math.max(0, Math.sin(time * 5.2)), 2);
      const beatR = Math.pow(Math.max(0, Math.sin(time * 5.2 + 2.1)), 2);
      const sway = Math.sin(time * 1.3);
      for (const [side, beat, sx] of [["L", beatL, 1], ["R", beatR, -1]]) {
        poseArm(side, dir(0.22 * sx, -0.95, 0.30),
                      dir((0.20 + 0.10 * sway * sx) * sx, -0.15 - 0.30 * beat, 1.0),
                      dir(0.25 * sx, -0.05 - 0.35 * beat, 0.9), e);
      }
      rotate(rig.upper, AXIS.y, 0.06 * sway * e);
      turnHead(-0.06 * sway, 0.05 * (beatL + beatR), 0.04 * sway, e);
    } },
    // Zeigefinger-Geste "Wichtig!": Hand vor der Brust nach oben, kurze Betonungen
    "☝️ Wichtiger Punkt": { dur: 2.8, apply: (t, e) => {
      const tap = Math.pow(Math.max(0, Math.sin(t * Math.PI * 6)), 3);
      poseArm("R", dir(-0.30, -0.70, 0.50), dir(-0.10, 1.0, 0.30 + 0.35 * tap), dir(-0.05, 1.0, 0.25 + 0.4 * tap), e);
      turnHead(-0.05, 0.10 * tap, 0.05, e);
    } },
    "🤷 Achselzucken": { dur: 2.2, apply: (t, e) => {
      const up = Math.sin(clamp(t * 1.4, 0, 1) * Math.PI);        // Schultern hoch und runter
      rotate(rig.shoulderL, AXIS.z, 0.22 * up * e);
      rotate(rig.shoulderR, AXIS.z, -0.22 * up * e);
      const upper = dir(0.35, -0.95, 0.15), fore = dir(0.80, -0.10, 0.55), hand = dir(0.85, 0.05, 0.45);
      poseArm("L", upper, fore, hand, e);
      poseArm("R", mirror(upper), mirror(fore), mirror(hand), e);
      turnHead(0, -0.05, 0.14, e);
    } },
    // Hand ans Kinn, der andere Arm stützt den Ellbogen
    "🤔 Nachdenken": { dur: 3.6, apply: (t, e) => {
      poseArm("R", dir(-0.10, -0.85, 0.55), null, null, e);
      const chin = bodyPointFrom(rig.head, 0, 0.05, 0.10);
      aimAt(rig.elbowR, rig.wristR, chin, e);
      aimAt(rig.wristR, rig.handTipR, bodyPointFrom(rig.head, 0, 0.09, 0.11), e);
      poseArm("L", dir(0.10, -1.0, 0.15), dir(-0.75, -0.05, 0.65), dir(-0.85, 0.0, 0.5), e);
      turnHead(0.12, -0.10, -0.12, e);
    } },
    "👏 Klatschen": { dur: 2.4, apply: (t, e) => {
      const clap = 0.5 + 0.5 * Math.cos(t * Math.PI * 12);       // 0 = Hände zusammen
      const center = bodyPointFrom(rig.upper2, 0, -0.05, 0.25);
      poseArm("L", dir(0.25, -0.75, 0.55), null, null, e);
      poseArm("R", dir(-0.25, -0.75, 0.55), null, null, e);
      aimAt(rig.elbowL, rig.wristL, offsetBody(center, 0.04 + 0.10 * clap, 0, 0), e);
      aimAt(rig.elbowR, rig.wristR, offsetBody(center, -0.04 - 0.10 * clap, 0, 0), e);
      turnHead(0, 0.05, 0, e);
    } }
  }
};
// Flache Liste aller Gesten (Name -> Definition)
const GESTURES = Object.assign({}, ...Object.values(GESTURE_GROUPS));

/** Spielt eine Geste; dur überschreibt optional die Standarddauer. */
function playGesture(name, dur) {
  if (!GESTURES[name]) return;
  gesture = { name: name, t0: performance.now(), dur: dur || GESTURES[name].dur };
}

function applyGesture() {
  if (!gesture) return;
  const g = GESTURES[gesture.name];
  const t = (performance.now() - gesture.t0) / 1000 / gesture.dur;
  if (t >= 1) { gesture = null; return; }
  const attack = Math.min(0.2, 0.6 / gesture.dur), release = Math.min(0.25, 0.7 / gesture.dur);
  g.apply(t, envelope(t, attack, release), gesture);
}

// Beim Sprechen automatisch gestikulieren (Schalter im Panel)
const talkGestures = { enabled: false, minChars: 20 };   // aus: wird später anders gelöst

function buildGestureSection(panel) {
  for (const [title, group] of Object.entries(GESTURE_GROUPS)) {
    const h = document.createElement("h4");
    h.textContent = title;
    h.style.marginTop = "1vh";
    panel.appendChild(h);
    Object.keys(group).forEach(name => {
      const b = document.createElement("button");
      b.textContent = name;
      b.onclick = () => playGesture(name);
      panel.appendChild(b);
    });
  }
  const toggle = (label, get, set) => {
    const b = document.createElement("button");
    const update = () => { b.textContent = label + ": " + (get() ? "an" : "aus"); b.classList.toggle("active", get()); };
    b.onclick = () => { set(!get()); update(); };
    update();
    panel.appendChild(b);
  };
  toggle("🗣 Gesten beim Sprechen", () => talkGestures.enabled, v => { talkGestures.enabled = v; });
  toggle("👀 Kopf folgt Maus", () => headFollow, v => { headFollow = v; });
}
