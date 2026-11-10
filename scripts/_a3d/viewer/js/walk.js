/* walk.js - Laufen und Stehen: Standort, Schritte, Becken, Fuß-IK, Armschwung
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Beine (prozedural, mit Fuß-IK)
   -------------------------------------------------------------------------
   Die Füße stehen fest auf dem Boden. Bewegt sich die Figur weg (Gehen,
   Drehen), macht der Fuß einen Schritt dorthin, wo er als Nächstes gebraucht
   wird - beim Gehen im Takt abwechselnd, im Stand nur zum Nachsetzen. Das
   Becken senkt sich, so weit die Beine reichen (dadurch wippt die Figur beim
   Gehen von selbst), und lehnt sich über das Standbein. Die Beine selbst
   rechnet eine Zwei-Knochen-IK (solveLimb in pose.js).
   Daraus ergibt sich auch der Rest: Armschwung und Gegendrehung des
   Oberkörpers folgen der Stellung der Füße, nicht einer festen Sinuswelle.
   Zwei Arten:
   - auf der Stelle (walk.mode = "place"): der Boden läuft wie ein Laufband
   - zu einem Ziel (walk.target, gesetzt von walkTo() in stations.js): in
     Laufrichtung eindrehen, beschleunigen, vor dem Ziel abbremsen, am Ziel
     in die gewünschte Richtung drehen.
   ========================================================================= */
const WALK = {
  cadence: 1.8,        // Schritte pro Sekunde
  stride: 0.40,        // Strecke pro Schritt (m) -> Tempo = stride * cadence
  accel: 1.5,          // Anlaufen (m/s²)
  decel: 1.3,          // Abbremsen vor dem Ziel (m/s²)
  turnTime: 0.42,      // wie träge sie sich dreht (s; kleiner = schneller)
  swing: 0.72,         // Anteil eines Schritt-Takts, den der Fuß in der Luft ist
  stepHeight: 0.065,   // so hoch hebt sie den Fuß (m)
  toeOff: 0.50,        // Abrollen: Fußspitze zeigt beim Abheben nach unten (rad)
  heelStrike: 0.20,    // Ferse setzt zuerst auf (rad)
  hipYaw: 0.10,        // Becken dreht mit dem Schritt
  hipRoll: 0.035,      // Hüfte senkt sich auf der Seite des Schwungbeins
  sway: 0.018,         // Becken wandert über das Standbein (m)
  track: 1.3,          // Spurbreite beim Gehen (1 = Füße so eng wie im Stand; verhindert Überkreuzen)
  lean: 0.045,         // leichte Vorlage beim Gehen
  armSwing: 0.30,
  elbow: 0.30,
  kneeSoft: 0.988,     // Beine nie ganz durchstrecken (Anteil der Beinlänge)
  standTolerance: 0.05,// im Stand: erst ab so viel Abweichung nachsetzen (m)
  footTurn: 0.5,       // so weit darf ein stehender Fuß gegen den Körper verdreht sein (rad)
  footReach: 0.36,     // so weit darf ein stehender Fuß zurückbleiben (m)
  arriveDist: 0.006,   // ab hier gilt das Ziel als erreicht (m)

  // ---- Alte Laufanimation (classic: true) -----------------------------------------
  // Gleichmäßiger Gangzyklus wie früher: Beine, Hüfte und Arme schwingen als Welle,
  // die Figur gleitet mit festem Tempo zum Ziel und dreht sich auf der Stelle.
  // false = die neue Art mit einzelnen Schritten (oben). Im Stand bleiben die Füße in
  // beiden Fällen per IK am Boden (Gewichtsverlagerung im Idle). Umschalten: Panel -> Animationen.
  classic: true,
  old: {
    thigh: 0.38,         // Oberschenkel-Schwung (rad)
    knee: 0.80,          // Kniebeuge in der Schwungphase
    hipYaw: 0.09,        // Becken dreht mit
    sway: 0.012,         // Gewichtsverlagerung seitlich (m)
    lean: 0.05,          // leichte Vorlage
    armSwing: 0.30,
    elbow: 0.30,
    legLength: 0.76,     // Hüfte bis Knöchel (für die Hüftabsenkung)
    turnRate: 4.5,       // wie schnell sie sich dreht (1/s)
    arriveDist: 0.015    // ab hier gilt das Ziel als erreicht (m)
  }
};
// mode: none | place;  target: {pos(): {x, z}, yaw, done(ok)} oder null
const walk = { mode: "none", weight: 0, yaw: 0, yawVel: { v: 0 }, speed: 0, target: null,
               place: 0, tread: new THREE.Vector3(),      // place: Tempo des "Laufbands", tread: sein Weg
               phase: 0, classic: 0 };                    // alte Laufanimation: Phase des Gangzyklus, Anteil 0..1

const approach = (cur, target, step) => cur < target ? Math.min(target, cur + step) : Math.max(target, cur - step);
function walkSpeedMax() { return WALK.stride * WALK.cadence; }

/* ---- Alte Laufanimation: Standort (festes Tempo, Drehen auf der Stelle) ---- */
function dampAngle(cur, target, rate, dt) {
  return cur + angleDiff(target, cur) * (1 - Math.exp(-rate * dt));
}
function updateWalkRootClassic(dt) {
  const root = modelRoot, O = WALK.old, t = walk.target;
  let moving = false;
  if (t) {
    const goal = t.pos();
    const dx = goal.x - root.position.x, dz = goal.z - root.position.z;
    const d = Math.hypot(dx, dz);
    let targetYaw;
    if (d > O.arriveDist) {
      targetYaw = Math.atan2(dx, dz);                            // Laufrichtung
      const facing = Math.cos(targetYaw - walk.yaw);
      if (facing > 0.5) {                                       // erst eindrehen, dann gehen
        const speed = walkSpeedMax() * Math.max(walk.classic, 0.3) * facing;
        const step = Math.min(d, speed * dt);
        root.position.x += dx / d * step;
        root.position.z += dz / d * step;
      }
      moving = true;
    } else {
      root.position.x = goal.x;
      root.position.z = goal.z;
      targetYaw = t.yaw;                                        // am Ziel in Blickrichtung drehen
      const diff = Math.abs(angleDiff(targetYaw, walk.yaw));
      moving = diff > 0.15;                                     // größere Drehung: mit kleinen Schritten
      if (diff < 0.03) { walk.target = null; t.done(true); }
    }
    walk.yaw = dampAngle(walk.yaw, targetYaw, O.turnRate, dt);
  }
  walk.yawVel.v = 0; walk.speed = 0; walk.place = 0;
  root.rotation.set(0, walk.yaw, 0);
  walk.classic = damp(walk.classic, walk.mode === "place" || moving ? 1 : 0, 4, dt);
  walk.weight = walk.classic;                                   // Idle wiegt beim Laufen weniger (idle.js)
}

/* ---- Alte Laufanimation: Gangzyklus. Phase p läuft 2π pro Doppelschritt, sin(p) > 0 = linkes
   Bein vorne. Die Hüfte senkt sich, wenn die Beine gespreizt sind - so bleiben die Füße
   ungefähr am Boden. ---- */
function walkLegClassic(thigh, knee, ankle, s, c, w) {
  const O = WALK.old;
  const swing = O.thigh * s;                                       // + = Bein vorne
  const bend = O.knee * Math.pow(Math.max(0, c), 1.5) + 0.05;      // Schwungphase: Knie hoch
  rotate(thigh, AXIS.x, -swing * w);
  rotate(knee, AXIS.x, bend * w);
  // Fuß ungefähr waagerecht halten, beim Abdrücken leicht strecken
  const toeOff = 0.25 * Math.max(0, -s) * Math.max(0, c);
  rotate(ankle, AXIS.x, (swing - bend - toeOff) * 0.9 * w);
}
function applyWalkClassic(dt, w) {
  if (w <= 0.001) return;
  const O = WALK.old;
  walk.phase += dt * WALK.cadence * Math.PI * Math.max(w, 0.2);
  const p = walk.phase, s = Math.sin(p), c = Math.cos(p);
  // Becken: absenken bei gespreizten Beinen, seitlich über das Standbein, mitdrehen
  const drop = O.legLength * (1 - Math.cos(O.thigh * Math.abs(s))) * 0.95;
  translateBody(rig.center, -O.sway * c * w, -drop * w, 0);
  rotate(rig.lower, AXIS.y, -O.hipYaw * s * w);
  walkLegClassic(rig.legL, rig.kneeL, rig.ankleL, s, c, w);
  walkLegClassic(rig.legR, rig.kneeR, rig.ankleR, -s, -c, w);
  // Oberkörper: Gegenrotation + leichte Vorlage
  rotate(rig.upper, AXIS.y, O.hipYaw * 1.4 * s * w);
  rotate(rig.upper, AXIS.x, O.lean * w);
  // Arme gegengleich zu den Beinen, Ellbogen beugt beim Vorschwingen
  rotate(rig.armL, AXIS.x, O.armSwing * s * w);
  rotate(rig.armR, AXIS.x, -O.armSwing * s * w);
  rotate(rig.elbowL, AXIS.x, -(0.12 + O.elbow * Math.max(0, -s)) * w);
  rotate(rig.elbowR, AXIS.x, -(0.12 + O.elbow * Math.max(0, s)) * w);
  // Kopf hält den Blick ruhig (gleicht Vorlage aus)
  rotate(rig.head, AXIS.x, -O.lean * 0.8 * w);
}

/** Pro Frame: Figur zum Ziel bewegen und drehen (weich anlaufen und abbremsen). */
function updateWalkRoot(dt) {
  if (WALK.classic) return updateWalkRootClassic(dt);
  walk.classic = damp(walk.classic, 0, 4, dt);
  const root = modelRoot, t = walk.target;
  let targetYaw = walk.yaw, want = 0, dx = 0, dz = 0, d = 0;
  if (t) {
    const goal = t.pos();
    dx = goal.x - root.position.x; dz = goal.z - root.position.z;
    d = Math.hypot(dx, dz);
    if (d > WALK.arriveDist) {
      // Kurze Wege (ein, zwei Schritte) geht sie seitlich, ohne sich erst hinzudrehen
      const shuffle = d < 0.14 && walk.speed < 0.2;
      targetYaw = shuffle ? t.yaw : Math.atan2(dx, dz);
      const facing = shuffle ? 0.5 : Math.cos(angleDiff(targetYaw, walk.yaw));
      if (facing > 0.55 || shuffle)                              // erst eindrehen, dann gehen
        want = Math.min(walkSpeedMax() * facing, Math.sqrt(2 * WALK.decel * d) * 0.9 + 0.03);
    } else {
      root.position.x = goal.x;
      root.position.z = goal.z;
      walk.speed = 0;
      targetYaw = t.yaw;                                         // am Ziel in Blickrichtung drehen
      if (Math.abs(angleDiff(targetYaw, walk.yaw)) < 0.03 && feetSettled()) { walk.target = null; t.done(true); }
    }
  }
  walk.speed = approach(walk.speed, want, (want > walk.speed ? WALK.accel : WALK.decel * 1.6) * dt);
  if (t && d > WALK.arriveDist) {
    const step = Math.min(d, walk.speed * dt);
    root.position.x += dx / d * step;
    root.position.z += dz / d * step;
  }
  walk.yaw = smoothDamp(walk.yaw, walk.yaw + angleDiff(targetYaw, walk.yaw), walk.yawVel, WALK.turnTime, dt);
  root.rotation.set(0, walk.yaw, 0);
  // Laufen auf der Stelle: der Boden zieht unter den Füßen nach hinten weg
  walk.place = approach(walk.place, walk.mode === "place" ? walkSpeedMax() : 0, WALK.accel * dt);
  walk.tread.x += Math.sin(walk.yaw) * walk.place * dt;
  walk.tread.z += Math.cos(walk.yaw) * walk.place * dt;
}

/** Laufenden Weg abbrechen (Figur bleibt, wo sie gerade ist). */
function cancelWalkTarget() {
  const t = walk.target;
  walk.target = null;
  if (t) t.done(false);
}

/* =========================================================================
   Füße
   -------------------------------------------------------------------------
   Gerechnet wird in "Bodenkoordinaten" = Welt + Weg des Laufbands. Ein
   stehender Fuß behält dort seinen Platz; beim Laufen auf der Stelle rutscht
   er dadurch in der Welt nach hinten, genau wie auf einem Laufband.
   ========================================================================= */
const feet = {
  ready: false, L: null, R: null,
  timer: 0, next: "L",                 // Takt: wann der nächste Schritt starten darf, mit welchem Fuß
  body: new THREE.Vector3(), vel: new THREE.Vector3(), hasBody: false,
  shift: 0, shiftV: { v: 0 },          // Becken seitlich (m, + = zur linken Seite der Figur)
  drop: 0,                             // Becken abgesenkt (m, negativ)
  phase: 0, armPhase: 0, armV: { v: 0 }, forePhase: 0, foreV: { v: 0 },   // -1..1: + = linker Fuß vorne
  lift: 0                              // -1..1: + = linker Fuß in der Luft
};

function setupFeet() {
  if (!rig.legL || !rig.kneeL || !rig.ankleL || !rig.legR || !rig.kneeR || !rig.ankleR) { feet.ready = true; return; }
  modelRoot.updateMatrixWorld(true);
  const rootInv = modelRoot.getWorldQuaternion(new THREE.Quaternion()).invert();
  for (const side of ["L", "R"]) {
    const leg = rig["leg" + side], knee = rig["knee" + side], ankle = rig["ankle" + side];
    const P = b => b.getWorldPosition(new THREE.Vector3());
    feet[side] = {
      side, leg, knee, ankle,
      rest: modelRoot.worldToLocal(P(ankle)),                    // Knöchel in der Ruhepose (Figur-Raum)
      restQ: rootInv.clone().multiply(ankle.getWorldQuaternion(new THREE.Quaternion())),
      length: P(leg).distanceTo(P(knee)) + P(knee).distanceTo(P(ankle)),
      g: new THREE.Vector3(), yaw: walk.yaw,                     // Standplatz (Bodenkoordinaten) + Richtung
      swing: null,                                               // {t, dur, from, yawFrom, len}
      pos: new THREE.Vector3(), yawNow: walk.yaw, pitch: 0, up: 0 // Ziel dieses Frames (Welt)
    };
    footHome(feet[side], feet[side].g);
  }
  feet.ready = true;
}

const _home = new THREE.Vector3(), _to = new THREE.Vector3(), _hip = new THREE.Vector3(), _pole = new THREE.Vector3();
const _fq = new THREE.Quaternion(), _fq2 = new THREE.Quaternion();

/** Wo der Fuß unter dem Körper stehen würde (Bodenkoordinaten). ahead: Körper um diesen Weg voraus. */
function footHome(f, out, ahead) {
  const c = Math.cos(walk.yaw), s = Math.sin(walk.yaw);
  const x = f.rest.x * (1 + (WALK.track - 1) * walk.weight);
  out.set(modelRoot.position.x + walk.tread.x + c * x + s * f.rest.z, 0,
          modelRoot.position.z + walk.tread.z - s * x + c * f.rest.z);
  if (ahead) out.add(ahead);
  return out;
}
const flatDist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);

/** Stehen beide Füße ruhig an ihrem Platz? (walkTo wartet darauf, bevor es "angekommen" meldet) */
function feetSettled() {
  if (!feet.L) return true;
  return !feet.L.swing && !feet.R.swing &&
    flatDist(feet.L.g, footHome(feet.L, _home)) < WALK.standTolerance &&
    flatDist(feet.R.g, footHome(feet.R, _home)) < WALK.standTolerance;
}

/** Pro Frame: Schritte planen und die Ziele beider Füße für dieses Bild berechnen. */
function updateFeet(dt, w) {
  if (!feet.L) return;
  const root = modelRoot;
  // Geschwindigkeit des Körpers über dem Boden (inkl. Laufband)
  _to.set(root.position.x + walk.tread.x, 0, root.position.z + walk.tread.z);
  if (!feet.hasBody || dt <= 0) { feet.body.copy(_to); feet.hasBody = true; }
  const k = 1 - Math.exp(-18 * dt);
  feet.vel.x += ((_to.x - feet.body.x) / Math.max(dt, 1e-4) - feet.vel.x) * k;
  feet.vel.z += ((_to.z - feet.body.z) / Math.max(dt, 1e-4) - feet.vel.z) * k;
  feet.body.copy(_to);
  const speed = Math.hypot(feet.vel.x, feet.vel.z);
  const moving = speed > 0.08;
  if (!WALK.classic) walk.weight = damp(walk.weight, clamp(speed / walkSpeedMax(), 0, 1), 7, dt);

  // Alte Laufanimation: Die Beine laufen ihren Zyklus selbst (applyWalkClassic) - die Füße
  // bleiben dabei einfach unter dem Körper, damit die IK im Stand nahtlos übernimmt.
  if (w < 0.02 || WALK.classic) {                       // Clip/Ruhepose: Füße gehören nicht uns -> still mitführen
    for (const s of ["L", "R"]) { const f = feet[s]; footHome(f, f.g); f.yaw = walk.yaw; f.swing = null; }
    feet.timer = 0;
  }

  // --- Takt: Schritt starten, wenn ein Fuß ihn braucht -----------------------
  const interval = moving ? 1 / WALK.cadence : 0.4;      // im Stand kürzere, schnellere Nachsetzer
  feet.timer -= dt;
  const need = f => !f.swing && (
    flatDist(f.g, footHome(f, _home)) > (moving ? 0.03 : WALK.standTolerance) ||
    Math.abs(angleDiff(walk.yaw, f.yaw)) > (moving ? 0.12 : 0.22));
  if (feet.timer <= 0 && w >= 0.02) {
    const a = feet[feet.next], b = feet[feet.next === "L" ? "R" : "L"];
    let f = null;
    if (!moving && !a.swing && !b.swing && need(a) && need(b)) {
      // Aus dem Stand: beim Drehen beginnt der Fuß auf der Seite, zu der sie sich dreht
      const turn = angleDiff(walk.yaw, a.yaw);
      f = Math.abs(turn) > 0.1 ? feet[turn > 0 ? "R" : "L"] : a;
    } else if (need(a) && !b.swing) f = a;
    else if (need(b) && !a.swing) f = b;
    if (f) {
      f.swing = { t: 0, dur: interval * WALK.swing, from: f.g.clone(), yawFrom: f.yaw, len: 0 };
      feet.timer = interval;
      feet.next = f.side === "L" ? "R" : "L";
    }
  }

  // --- Ziel jedes Fußes für dieses Bild ------------------------------------
  const interval2 = 1 / WALK.cadence;
  for (const s of ["L", "R"]) {
    const f = feet[s], sw = f.swing;
    f.pitch = 0; f.up = 0;
    if (sw) {
      sw.t = Math.min(1, sw.t + dt / sw.dur);
      // Landeplatz: unter dem Körper, wie er beim Aufsetzen steht, plus ein halber Schritt voraus -
      // dann steht der Fuß in der Mitte seiner Standzeit genau unter der Hüfte.
      const lead = (1 - sw.t) * sw.dur + (2 - WALK.swing) * 0.5 * interval2;
      footHome(f, _to, _home.set(feet.vel.x * lead, 0, feet.vel.z * lead));
      sw.len = flatDist(sw.from, _to);
      const e = sw.t * sw.t * (3 - 2 * sw.t);                     // weich los, weich aufsetzen
      f.g.lerpVectors(sw.from, _to, e);
      f.yaw = sw.yawFrom + angleDiff(walk.yaw, sw.yawFrom) * e;
      const big = clamp(sw.len / 0.3, 0.2, 1);                    // kleine Nachsetzer: flacher, ohne Abrollen
      const bump = (x, a, b) => x <= a || x >= b ? 0 : Math.sin(Math.PI * (x - a) / (b - a));
      f.pitch = (WALK.toeOff * bump(sw.t, 0, 0.55) - WALK.heelStrike * bump(sw.t, 0.5, 1)) * big;
      f.up = WALK.stepHeight * (0.4 + 0.6 * big) * Math.pow(Math.sin(Math.PI * sw.t), 0.85)
           + Math.max(0, Math.sin(f.pitch)) * 0.07;               // Ferse hoch, Spitze bleibt über dem Boden
      if (sw.t >= 1) { f.g.copy(_to); f.yaw = walk.yaw; f.swing = null; }
    } else {
      // Stehender Fuß: nie weiter verdreht/gestreckt, als ein Bein kann (dann rutscht er mit)
      const off = angleDiff(f.yaw, walk.yaw);
      if (Math.abs(off) > WALK.footTurn) f.yaw = walk.yaw + Math.sign(off) * WALK.footTurn;
      const far = flatDist(f.g, footHome(f, _home));
      if (far > WALK.footReach) f.g.lerp(_home, 1 - WALK.footReach / far);
    }
    f.pos.set(f.g.x - walk.tread.x, f.rest.y + f.up, f.g.z - walk.tread.z);
    f.yawNow = f.yaw;
  }

  // --- Standbein im Idle: das entlastete Bein steht locker (Ferse leicht hoch) ----
  const relax = (1 - clamp(walk.weight * 4, 0, 1)) * (typeof stance !== "undefined" ? stance.s : 0);
  if (Math.abs(relax) > 0.01) {
    const f = feet[relax > 0 ? "R" : "L"], a = Math.abs(relax);
    if (!f.swing) { f.pitch += IDLE.freeFootPitch * a; f.pos.y += IDLE.freeFootLift * a; f.yawNow += (f.side === "L" ? 1 : -1) * IDLE.freeFootTurn * a; }
  }

  // --- Auf die Zehen wippen (idle.js: fidget) --------------------------------------
  const heel = typeof fidget !== "undefined" ? fidget.heel : 0;
  if (heel > 0.001) for (const s of ["L", "R"]) {
    const f = feet[s];
    if (!f.swing) { f.pitch += 0.20 * heel; f.pos.y += 0.016 * heel; }
  }

  // --- Was der Oberkörper daraus macht -------------------------------------
  // Schrittstellung: wie weit der linke Fuß vor dem rechten steht (in Laufrichtung des Körpers)
  const fx = Math.sin(walk.yaw), fz = Math.cos(walk.yaw);
  const ahead = f => (f.g.x - feet.body.x) * fx + (f.g.z - feet.body.z) * fz - f.rest.z;
  feet.phase = clamp((ahead(feet.L) - ahead(feet.R)) / (WALK.stride * 1.3), -1, 1);
  feet.armPhase = smoothDamp(feet.armPhase, feet.phase, feet.armV, 0.09, dt);     // Arme leicht verzögert,
  feet.forePhase = smoothDamp(feet.forePhase, feet.phase, feet.foreV, 0.16, dt);  // Unterarme noch etwas später
  feet.lift = (feet.L.up - feet.R.up) / WALK.stepHeight;
  // Becken über das Standbein; im Stand bestimmt die Gewichtsverlagerung (idle.js)
  const swayTo = feet.L.swing ? -1 : feet.R.swing ? 1 : 0;
  const shiftTo = swayTo * WALK.sway * (0.4 + 0.6 * walk.weight) +
                  (typeof stance !== "undefined" ? stance.s * IDLE.shift * (1 - walk.weight) : 0);
  feet.shift = smoothDamp(feet.shift, shiftTo, feet.shiftV, 0.2, dt);
}

/** Armschwung, Gegendrehung und Vorlage beim Gehen (vor den Gesten, damit diese Vorrang haben). */
function applyWalkUpper(dt, w) {
  if (walk.classic > 0.001) applyWalkClassic(dt, w * walk.classic);   // alte Laufanimation (ganzer Körper)
  if (WALK.classic) return;
  const ww = w * walk.weight;
  if (ww <= 0.001) return;
  const p = feet.phase;
  rotate(rig.upper, AXIS.y, WALK.hipYaw * 1.3 * p * ww);         // Schultern gegen das Becken
  rotate(rig.upper, AXIS.x, WALK.lean * ww);
  rotate(rig.upper, AXIS.z, -0.02 * feet.lift * ww);
  // Arme gegengleich zu den Beinen, Ellbogen beugt beim Vorschwingen, Hand zieht nach
  rotate(rig.armL, AXIS.x, WALK.armSwing * feet.armPhase * ww);
  rotate(rig.armR, AXIS.x, -WALK.armSwing * feet.armPhase * ww);
  rotate(rig.elbowL, AXIS.x, -(0.10 + WALK.elbow * Math.max(0, -feet.forePhase)) * ww);
  rotate(rig.elbowR, AXIS.x, -(0.10 + WALK.elbow * Math.max(0, feet.forePhase)) * ww);
  rotate(rig.wristL, AXIS.x, 0.12 * (feet.armPhase - feet.forePhase) * ww);
  rotate(rig.wristR, AXIS.x, -0.12 * (feet.armPhase - feet.forePhase) * ww);
  // Kopf hält den Blick ruhig (gleicht Vorlage und Drehung aus)
  rotate(rig.head, AXIS.x, -WALK.lean * 0.8 * ww);
  rotate(rig.neck, AXIS.y, -WALK.hipYaw * 0.9 * p * ww);
}

/** Becken verlagern und absenken, dann beide Beine per IK zu ihren Füßen (nach den Gesten -
    so bleiben die Füße auch stehen, wenn eine Geste die Hüfte bewegt, z. B. beim Verbeugen). */
function applyLegs(dt, w) {
  w *= 1 - walk.classic;                // alte Laufanimation stellt die Beine selbst; im Stand blendet die IK wieder ein
  if (!feet.L || w <= 0.001) return;
  // Becken: seitlich über das Standbein, dreht mit dem Schritt, Hüfte des Schwungbeins sinkt
  translateBody(rig.center, feet.shift * w, 0, 0);
  const ww = WALK.classic ? 0 : w * walk.weight;
  rotate(rig.lower, AXIS.y, -WALK.hipYaw * feet.phase * ww);
  rotate(rig.lower, AXIS.z, -WALK.hipRoll * feet.lift * ww);
  // Absenken, bis beide Beine ihren Fuß erreichen (leicht gebeugt statt durchgestreckt)
  let dy = 0;
  for (const s of ["L", "R"]) {
    const f = feet[s];
    f.leg.getWorldPosition(_hip);
    const h2 = (_hip.x - f.pos.x) ** 2 + (_hip.z - f.pos.z) ** 2;
    const reach = f.length * WALK.kneeSoft;
    dy = Math.min(dy, f.pos.y + Math.sqrt(Math.max(reach * reach - h2, 0.01)) - _hip.y);
  }
  feet.drop = damp(feet.drop, Math.max(dy, -0.25), 30, dt);       // kurz geglättet: kein Ruck beim Aufsetzen
  translateBody(rig.center, 0, feet.drop * w, 0);

  for (const s of ["L", "R"]) {
    const f = feet[s], sx = s === "L" ? 1 : -1;
    // Knie zeigt nach vorne (zwischen Körper- und Fußrichtung), minimal nach außen
    const yaw = walk.yaw + angleDiff(f.yawNow, walk.yaw) * 0.5;
    _pole.set(0.06 * sx, 0.05, 1).applyAxisAngle(AXIS.y, yaw);
    solveLimb(f.leg, f.knee, f.ankle, f.pos, _pole, w);
    // Fuß: flach auf dem Boden in seiner Richtung, beim Schritt abrollen
    _fq.setFromAxisAngle(AXIS.y, f.yawNow).multiply(_fq2.setFromAxisAngle(AXIS.x, f.pitch)).multiply(f.restQ);
    f.ankle.parent.getWorldQuaternion(_fq2);
    _fq.premultiply(_fq2.invert());
    if (w >= 0.999) f.ankle.quaternion.copy(_fq); else f.ankle.quaternion.slerp(_fq, w);
    f.ankle.updateMatrixWorld(true);
  }
}
