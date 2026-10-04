/* walk.js - Laufen: Gangzyklus und Bewegung im Raum
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Laufen (prozedural): Gangzyklus für Beine, Hüfte, Arme + Bewegung im Raum
   -------------------------------------------------------------------------
   Phase p läuft 2π pro Doppelschritt. sin(p) > 0 = linkes Bein vorne.
   Die Hüfte senkt sich, wenn die Beine gespreizt sind - so bleiben die Füße
   ohne IK ungefähr am Boden.
   ========================================================================= */
const WALK = {
  cadence: 1.8,        // Schritte pro Sekunde
  stride: 0.40,        // Strecke pro Schritt (m) -> Tempo = stride * cadence
  thigh: 0.38,         // Oberschenkel-Schwung (rad)
  knee: 0.80,          // Kniebeuge in der Schwungphase
  hipYaw: 0.09,        // Becken dreht mit
  sway: 0.012,         // Gewichtsverlagerung seitlich (m)
  lean: 0.05,          // leichte Vorlage
  armSwing: 0.30,
  elbow: 0.30,
  legLength: 0.76,     // Hüfte bis Knöchel (für die Hüftabsenkung)
  // Weg beim Herumlaufen: Ellipse vor der Kamera, beginnt im Ursprung
  path: { rx: 0.9, rz: 0.45 }
};
const walk = { mode: "none", weight: 0, phase: 0, a: 0, yaw: 0 };  // mode: none | place | around

function dampAngle(cur, target, rate, dt) {
  let d = target - cur;
  d = Math.atan2(Math.sin(d), Math.cos(d));                    // kürzester Weg
  return cur + d * (1 - Math.exp(-rate * dt));
}

/** Bewegt das Modell durch den Raum und bestimmt, ob gelaufen wird. */
function updateLocomotion(dt) {
  const root = modelRoot;
  const speed = WALK.stride * WALK.cadence;
  const { rx, rz } = WALK.path;
  let moving = false, targetYaw = 0;
  if (walk.mode === "around") {
    // Ellipse: x = rx·sin a, z = rz·cos a - rz  (a = 0 -> Ursprung)
    const len = Math.hypot(rx * Math.cos(walk.a), rz * Math.sin(walk.a));
    walk.a += speed * walk.weight * dt / Math.max(len, 1e-3);
    root.position.set(rx * Math.sin(walk.a), 0, rz * Math.cos(walk.a) - rz);
    targetYaw = Math.atan2(rx * Math.cos(walk.a), -rz * Math.sin(walk.a));
    moving = true;
  } else {
    const d = Math.hypot(root.position.x, root.position.z);
    if (d > 0.02) {                                             // zurück zur Mitte laufen
      const step = Math.min(d, speed * Math.max(walk.weight, 0.3) * dt);
      targetYaw = Math.atan2(-root.position.x, -root.position.z);
      // erst eindrehen, dann gehen
      const facing = Math.cos(targetYaw - walk.yaw);
      if (facing > 0.5) {
        root.position.x -= root.position.x / d * step;
        root.position.z -= root.position.z / d * step;
      }
      moving = true;
    } else {
      root.position.set(0, 0, 0);
      targetYaw = 0;                                            // zum Betrachter drehen
      moving = Math.abs(Math.atan2(Math.sin(walk.yaw), Math.cos(walk.yaw))) > 0.15;
    }
  }
  walk.yaw = dampAngle(walk.yaw, targetYaw, 4, dt);
  root.rotation.set(0, walk.yaw, 0);
  const wantWalk = walk.mode !== "none" || moving;
  walk.weight = damp(walk.weight, wantWalk ? 1 : 0, 4, dt);
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
