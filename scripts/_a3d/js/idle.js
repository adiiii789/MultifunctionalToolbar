/* idle.js - Natürliches Idle: Armhaltung, Atmen, Wiegen, Umschauen
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Natürliches Idle
   ========================================================================= */
const IDLE = {
  // Grundhaltung: Arme locker hängend, Ellbogen leicht gebeugt (Richtungen im Körperraum)
  upperArmL: dir( 0.24, -1.0, -0.10),  upperArmR: dir(-0.24, -1.0, -0.10),
  foreArmL:  dir( 0.30, -1.0, 0.42),  foreArmR:  dir(-0.30, -1.0, 0.42),
  handL:     dir( 0.10, -1.0, 0.30),  handR:     dir(-0.10, -1.0, 0.30),
  spine: dir(0, 2.0, -0.6),  // Richtung Becken -> Hals (natürliches leichtes Hohlkreuz)
  lean: 0.0,                 // Gesamtneigung Knöchel -> Augen in Grad (0 = senkrecht, + = nach vorne)
  headPitch: -0.04,          // Grundneigung des Kopfes (negativ = Blick etwas höher)
  breathPeriod: 4.2,     // Sekunden pro Atemzug
  breathChest: 0.022,    // Brustkorb hebt sich
  breathShoulder: 0.018, // Schultern heben sich mit
  sway: 0.028,           // langsames Wiegen des Oberkörpers
  lookYaw: 0.32,         // max. Kopfdrehung beim Umschauen (rad)
  lookPitch: 0.10,
  lookPauseMin: 1.8, lookPauseMax: 5.5
};

const look = {
  yaw: 0, pitch: 0, roll: 0,            // aktuelle Kopfhaltung
  tYaw: 0, tPitch: 0, tRoll: 0,         // Ziel
  eyeYaw: 0, eyePitch: 0,
  next: 0                               // Zeitpunkt des nächsten Blickwechsels
};

function pickLookTarget(time) {
  const r = Math.random();
  if (r < 0.45) {                          // zurück zum Betrachter
    look.tYaw = (Math.random() - 0.5) * 0.06;
    look.tPitch = (Math.random() - 0.5) * 0.04;
  } else {                                 // irgendwo hinschauen
    look.tYaw = (Math.random() * 2 - 1) * IDLE.lookYaw;
    look.tPitch = (Math.random() * 1.6 - 0.6) * IDLE.lookPitch;
  }
  // Leichte Kopfneigung, manchmal etwas deutlicher ("niedlicher" Tilt)
  look.tRoll = -look.tYaw * 0.25 + (Math.random() < 0.2 ? (Math.random() - 0.5) * 0.22 : 0);
  look.next = time + IDLE.lookPauseMin + Math.random() * (IDLE.lookPauseMax - IDLE.lookPauseMin);
}

function updateLook(time, dt) {
  const mouse = headFollow ? getMouseLook() : null;
  if (mouse) {                            // Maus übersteuert das Umschauen
    look.tYaw = mouse.yaw;
    look.tPitch = mouse.pitch;
    look.tRoll = -look.tYaw * 0.15;
  } else if (time >= look.next) {
    pickLookTarget(time);
  }
  // Augen springen schnell (Sakkade), der Kopf folgt weich hinterher
  look.eyeYaw   = damp(look.eyeYaw,   look.tYaw,   14, dt);
  look.eyePitch = damp(look.eyePitch, look.tPitch, 14, dt);
  look.yaw   = damp(look.yaw,   look.tYaw,   2.6, dt);
  look.pitch = damp(look.pitch, look.tPitch, 2.6, dt);
  look.roll  = damp(look.roll,  look.tRoll,  2.0, dt);
}

const _ankleMid = new THREE.Vector3(), _eyesPos = new THREE.Vector3(), _invRoot = new THREE.Quaternion();
function levelBody(w) {
  if (!rig.center || !rig.ankleL || !rig.ankleR || !rig.eyeL) return;
  rig.ankleL.getWorldPosition(_ankleMid).add(rig.ankleR.getWorldPosition(_eyesPos)).multiplyScalar(0.5);
  rig.eyeL.getWorldPosition(_eyesPos);
  _eyesPos.sub(_ankleMid).applyQuaternion(_invRoot.copy(modelRoot.quaternion).invert());
  const current = Math.atan2(_eyesPos.z, _eyesPos.y);                 // + = nach vorne
  rotate(rig.center, AXIS.x, (THREE.MathUtils.degToRad(IDLE.lean) - current) * w);
}

function applyIdle(time, w) {
  if (w <= 0) return;
  // 0) Aufrechte Haltung: Das Modell lehnt in der Ruhepose ~12° nach hinten.
  //    Wirbelsäule (Becken -> Hals) leicht nach vorne ausrichten.
  // Kopf soll dabei NICHT mitkippen (sonst schaut sie nach unten):
  // Kopf-Ausrichtung vorher merken und über den Hals wiederherstellen.
  const headBefore = rig.head ? rig.head.getWorldQuaternion(new THREE.Quaternion()) : null;
  aim(rig.upper, rig.neck, IDLE.spine, w);
  if (headBefore) {
    const headAfter = rig.head.getWorldQuaternion(new THREE.Quaternion());
    applyWorldRotation(rig.neck, headBefore.multiply(headAfter.invert()));
  }
  rotate(rig.head, AXIS.x, IDLE.headPitch * w);
  // Ganze Figur ins Lot bringen: Das Modell steht von Haus aus mit den Hüften
  // vor den Knöcheln (~2-3° Vorlage). Gemessen wird Knöchelmitte -> Augen.
  levelBody(w);
  // 1) Grundhaltung der Arme
  aim(rig.armL,   rig.elbowL,   IDLE.upperArmL, w);
  aim(rig.armR,   rig.elbowR,   IDLE.upperArmR, w);
  aim(rig.elbowL, rig.wristL,   IDLE.foreArmL,  w);
  aim(rig.elbowR, rig.wristR,   IDLE.foreArmR,  w);
  aim(rig.wristL, rig.handTipL, IDLE.handL,     w);
  aim(rig.wristR, rig.handTipR, IDLE.handR,     w);

  // 2) Atmen: Brust hebt sich minimal nach hinten, Schultern gehen mit
  const breath = Math.sin(time * 2 * Math.PI / IDLE.breathPeriod);
  const inhale = breath * 0.5 + 0.5;
  rotate(rig.upper2, AXIS.x, -IDLE.breathChest * inhale * w);
  rotate(rig.shoulderL, AXIS.z,  IDLE.breathShoulder * inhale * w);
  rotate(rig.shoulderR, AXIS.z, -IDLE.breathShoulder * inhale * w);
  // Arme schwingen ganz leicht mit dem Atem
  rotate(rig.armL, AXIS.x, -0.015 * breath * w);
  rotate(rig.armR, AXIS.x, -0.015 * breath * w);

  // 3) Langsames Wiegen / Gewichtsverlagerung (nur Oberkörper -> Füße bleiben stehen)
  const swayT = time * 0.35;
  const sw = w * (1 - 0.8 * walk.weight);   // beim Laufen kein zusätzliches Wiegen
  rotate(rig.upper, AXIS.z, IDLE.sway * smoothNoise(swayT, 1.3) * sw);
  rotate(rig.upper, AXIS.y, IDLE.sway * 0.8 * smoothNoise(swayT * 0.8, 4.1) * sw);
  rotate(rig.upper, AXIS.x, IDLE.sway * 0.5 * smoothNoise(swayT * 0.6, 7.7) * sw);
  rotate(rig.lower, AXIS.z, -IDLE.sway * 0.3 * smoothNoise(swayT, 1.3) * sw);

  // 4) Kopf: Umschauen, aufgeteilt auf Hals (40 %) und Kopf (60 %), plus Mikrobewegung
  const microYaw = 0.012 * smoothNoise(time * 0.9, 2.2);
  const microPitch = 0.010 * smoothNoise(time * 0.8, 5.4);
  const yaw = (look.yaw + microYaw) * w, pitch = (look.pitch + microPitch) * w, roll = look.roll * w;
  rotate(rig.neck, AXIS.y, yaw * 0.4);
  rotate(rig.neck, AXIS.x, pitch * 0.4);
  rotate(rig.head, AXIS.y, yaw * 0.6);
  rotate(rig.head, AXIS.x, pitch * 0.6);
  rotate(rig.head, AXIS.z, roll);

  // 5) Augen führen den Blick an (Vorsprung vor dem Kopf)
  const eyeYaw = clamp((look.eyeYaw - look.yaw) * 1.4, -0.25, 0.25) * w;
  const eyePitch = clamp((look.eyePitch - look.pitch) * 1.4, -0.15, 0.15) * w;
  for (const eye of [rig.eyeL, rig.eyeR]) {
    rotate(eye, AXIS.y, eyeYaw);
    rotate(eye, AXIS.x, eyePitch);
  }
}
