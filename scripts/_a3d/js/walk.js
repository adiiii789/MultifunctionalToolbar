/* walk.js - Laufen: Gangzyklus für Beine, Hüfte, Arme + Gehen zu einem Ziel
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Laufen (prozedural, auf der Stelle)
   -------------------------------------------------------------------------
   Phase p läuft 2π pro Doppelschritt. sin(p) > 0 = linkes Bein vorne.
   Die Hüfte senkt sich, wenn die Beine gespreizt sind - so bleiben die Füße
   ohne IK ungefähr am Boden.
   Zwei Arten:
   - auf der Stelle (walk.mode = "place")
   - zu einem Ziel (walk.target, gesetzt von walkTo() in stations.js): erst
     in Laufrichtung eindrehen, hingehen, am Ziel in die gewünschte Richtung
     drehen, dann stehen bleiben.
   ========================================================================= */
const WALK = {
  cadence: 1.8,        // Schritte pro Sekunde
  thigh: 0.38,         // Oberschenkel-Schwung (rad)
  knee: 0.80,          // Kniebeuge in der Schwungphase
  hipYaw: 0.09,        // Becken dreht mit
  sway: 0.012,         // Gewichtsverlagerung seitlich (m)
  lean: 0.05,          // leichte Vorlage
  armSwing: 0.30,
  elbow: 0.30,
  legLength: 0.76,     // Hüfte bis Knöchel (für die Hüftabsenkung)
  stride: 0.40,        // Strecke pro Schritt (m) -> Tempo = stride * cadence
  turnRate: 4.5,       // wie schnell sie sich dreht (1/s)
  arriveDist: 0.015    // ab hier gilt das Ziel als erreicht (m)
};
// mode: none | place;  target: {pos(): {x, z}, yaw, done(ok)} oder null
const walk = { mode: "none", weight: 0, phase: 0, yaw: 0, target: null };

function dampAngle(cur, target, rate, dt) {
  let d = target - cur;
  d = Math.atan2(Math.sin(d), Math.cos(d));                    // kürzester Weg
  return cur + d * (1 - Math.exp(-rate * dt));
}

/** Pro Frame: Figur zum Ziel bewegen/drehen und Laufen weich ein-/ausblenden. */
function updateWalkWeight(dt) {
  const root = modelRoot;
  let moving = false;
  const t = walk.target;
  if (t) {
    const goal = t.pos();
    const dx = goal.x - root.position.x, dz = goal.z - root.position.z;
    const d = Math.hypot(dx, dz);
    let targetYaw;
    if (d > WALK.arriveDist) {
      targetYaw = Math.atan2(dx, dz);                            // Laufrichtung
      const facing = Math.cos(targetYaw - walk.yaw);
      if (facing > 0.5) {                                       // erst eindrehen, dann gehen
        const speed = WALK.stride * WALK.cadence * Math.max(walk.weight, 0.3) * facing;
        const step = Math.min(d, speed * dt);
        root.position.x += dx / d * step;
        root.position.z += dz / d * step;
      }
      moving = true;
    } else {
      root.position.x = goal.x;
      root.position.z = goal.z;
      targetYaw = t.yaw;                                        // am Ziel in Blickrichtung drehen
      const diff = Math.abs(Math.atan2(Math.sin(targetYaw - walk.yaw), Math.cos(targetYaw - walk.yaw)));
      moving = diff > 0.15;                                     // größere Drehung: mit kleinen Schritten
      if (diff < 0.03) { walk.target = null; t.done(true); }
    }
    walk.yaw = dampAngle(walk.yaw, targetYaw, WALK.turnRate, dt);
  }
  root.rotation.set(0, walk.yaw, 0);
  walk.weight = damp(walk.weight, walk.mode === "place" || moving ? 1 : 0, 4, dt);
}

/** Laufenden Weg abbrechen (Figur bleibt, wo sie gerade ist). */
function cancelWalkTarget() {
  const t = walk.target;
  walk.target = null;
  if (t) t.done(false);
}

function walkLeg(thigh, knee, ankle, s, c, w) {
  const swing = WALK.thigh * s;                                    // + = Bein vorne
  const bend = WALK.knee * Math.pow(Math.max(0, c), 1.5) + 0.05;   // Schwungphase: Knie hoch
  rotate(thigh, AXIS.x, -swing * w);
  rotate(knee, AXIS.x, bend * w);
  // Fuß ungefähr waagerecht halten, beim Abdrücken leicht strecken
  const toeOff = 0.25 * Math.max(0, -s) * Math.max(0, c);
  rotate(ankle, AXIS.x, (swing - bend - toeOff) * 0.9 * w);
}

function applyWalk(dt, w) {
  if (w <= 0.001) return;
  walk.phase += dt * WALK.cadence * Math.PI * Math.max(w, 0.2);
  const p = walk.phase, s = Math.sin(p), c = Math.cos(p);

  // Becken: absenken bei gespreizten Beinen, seitlich über das Standbein, mitdrehen
  const drop = WALK.legLength * (1 - Math.cos(WALK.thigh * Math.abs(s))) * 0.95;
  translateBody(rig.center, -WALK.sway * c * w, -drop * w, 0);
  rotate(rig.lower, AXIS.y, -WALK.hipYaw * s * w);

  walkLeg(rig.legL, rig.kneeL, rig.ankleL, s, c, w);
  walkLeg(rig.legR, rig.kneeR, rig.ankleR, -s, -c, w);

  // Oberkörper: Gegenrotation + leichte Vorlage
  rotate(rig.upper, AXIS.y, WALK.hipYaw * 1.4 * s * w);
  rotate(rig.upper, AXIS.x, WALK.lean * w);
  // Arme gegengleich zu den Beinen, Ellbogen beugt beim Vorschwingen
  rotate(rig.armL, AXIS.x, WALK.armSwing * s * w);
  rotate(rig.armR, AXIS.x, -WALK.armSwing * s * w);
  rotate(rig.elbowL, AXIS.x, -(0.12 + WALK.elbow * Math.max(0, -s)) * w);
  rotate(rig.elbowR, AXIS.x, -(0.12 + WALK.elbow * Math.max(0, s)) * w);
  // Kopf hält den Blick ruhig (gleicht Vorlage aus)
  rotate(rig.head, AXIS.x, -WALK.lean * 0.8 * w);
}
