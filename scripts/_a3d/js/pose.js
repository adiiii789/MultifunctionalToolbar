/* pose.js - Rig, Körperachsen-Helfer und der Pose-Ablauf pro Frame
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Pose-System: Rig, Helfer und Ablauf pro Frame
   -------------------------------------------------------------------------
   Das Rig stammt aus MMD -> Blender: Jeder Knochen hat eigene, schräg
   liegende lokale Achsen. Deshalb wird hier nie "rotation.x += ..."
   gerechnet, sondern immer in Körperachsen der Figur (Welt-Raum):
     +X = linke Seite der Figur, +Y = oben, +Z = vorne (Blickrichtung)
   Positiver Winkel um X  -> nach vorne neigen / nicken
   Positiver Winkel um Y  -> nach links (Figur) drehen
   Positiver Winkel um Z  -> zur rechten Schulter (Figur) neigen
   Jeder Frame startet in der Ruhepose, dann kommen Idle und Gesten dazu.
   ========================================================================= */
const AXIS = {
  x: new THREE.Vector3(1, 0, 0),
  y: new THREE.Vector3(0, 1, 0),
  z: new THREE.Vector3(0, 0, 1)
};

// Knochennamen (MMD-Standard) + englische Fallbacks für andere Modelle
const RIG_NAMES = {
  lower:     ["下半身", "Hips", "hips", "pelvis"],
  upper:     ["上半身", "Spine", "spine"],
  upper2:    ["上半身2", "Chest", "chest", "spine1"],
  neck:      ["首", "Neck", "neck"],
  head:      ["頭", "Head", "head"],
  eyeL:      ["目.L", "LeftEye", "eye.L"],
  eyeR:      ["目.R", "RightEye", "eye.R"],
  shoulderL: ["肩.L", "LeftShoulder", "shoulder.L"],
  shoulderR: ["肩.R", "RightShoulder", "shoulder.R"],
  armL:      ["腕.L", "LeftArm", "upper_arm.L"],
  armR:      ["腕.R", "RightArm", "upper_arm.R"],
  elbowL:    ["ひじ.L", "LeftForeArm", "forearm.L"],
  elbowR:    ["ひじ.R", "RightForeArm", "forearm.R"],
  wristL:    ["手首.L", "LeftHand", "hand.L"],
  wristR:    ["手首.R", "RightHand", "hand.R"],
  handTipL:  ["中指１.L", "LeftHandMiddle1"],
  handTipR:  ["中指１.R", "RightHandMiddle1"],
  center:    ["センター", "Hips", "hips"],
  legL:      ["足.L", "LeftUpLeg", "thigh.L"],
  legR:      ["足.R", "RightUpLeg", "thigh.R"],
  kneeL:     ["ひざ.L", "LeftLeg", "shin.L"],
  kneeR:     ["ひざ.R", "RightLeg", "shin.R"],
  ankleL:    ["足首.L", "LeftFoot", "foot.L"],
  ankleR:    ["足首.R", "RightFoot", "foot.R"]
};

let rig = {};             // Rollenname -> Bone
let restPose = [];        // [bone, Ruhe-Quaternion, Ruhe-Position]
let modelRoot = null;
let gesture = null;
let headFollow = true;         // Kopf folgt der Maus (Standard: an)
let idleEnabled = false;
let idleWeight = 0;       // weiches Ein-/Ausblenden des Idles (0..1)

function indexBones(root) {
  modelRoot = root;
  const map = {};
  root.traverse(o => { if (o.isBone) map[o.name] = o; });
  rig = {};
  for (const [role, names] of Object.entries(RIG_NAMES)) {
    // GLTFLoader entfernt Sonderzeichen aus Knotennamen ("腕.L" -> "腕L"),
    // deshalb beide Schreibweisen probieren.
    rig[role] = names.map(n => map[n] || map[THREE.PropertyBinding.sanitizeNodeName(n)])
                     .find(Boolean) || null;
  }
  restPose = Object.values(map).map(b => [b, b.quaternion.clone(), b.position.clone()]);
  const missing = Object.keys(rig).filter(k => !rig[k]);
  console.log("Rig: " + Object.keys(map).length + " Bones" +
    (missing.length ? ", fehlend: " + missing.join(", ") : ", alle Rollen gefunden"));
}

function resetToRestPose() {
  for (const [bone, q, p] of restPose) { bone.quaternion.copy(q); bone.position.copy(p); }
}

// --- Hilfsfunktionen: Drehungen im Körper-/Weltraum ------------------------
const _pq = new THREE.Quaternion(), _wq = new THREE.Quaternion(), _lq = new THREE.Quaternion();
const _va = new THREE.Vector3(), _vb = new THREE.Vector3();
const _identity = new THREE.Quaternion();

/** Dreht einen Knochen um eine Welt-Quaternion (Kinder drehen mit). */
function applyWorldRotation(bone, worldQ) {
  if (!bone) return;
  bone.parent.getWorldQuaternion(_pq);
  _lq.copy(_pq).invert().multiply(worldQ).multiply(_pq);   // in Elternraum umrechnen
  bone.quaternion.premultiply(_lq);
  bone.updateMatrixWorld(true);
}

/** Dreht einen Knochen um eine Körperachse (AXIS.x/y/z). */
function rotate(bone, axis, angle) {
  if (!bone || Math.abs(angle) < 1e-6) return;
  applyWorldRotation(bone, _wq.setFromAxisAngle(toWorldDir(axis, _ax), angle));
}

/** Körperrichtung -> Weltrichtung (das Modell kann beim Laufen gedreht sein). */
const _ax = new THREE.Vector3(), _bodyQ = new THREE.Quaternion();
function toWorldDir(v, out) {
  return out.copy(v).applyQuaternion(modelRoot ? modelRoot.getWorldQuaternion(_bodyQ) : _identity);
}
/** Weltpunkt: Position eines Knochens + Versatz in Körperrichtungen (Meter). */
function bodyPointFrom(bone, x, y, z) {
  const p = bone.getWorldPosition(new THREE.Vector3());
  return p.add(toWorldDir(dir(x, y, z), new THREE.Vector3()));
}
function offsetBody(point, x, y, z) {
  return point.clone().add(toWorldDir(dir(x, y, z), new THREE.Vector3()));
}
/** Knochen in Körperrichtungen verschieben (z. B. Hüfte absenken). */
function translateBody(bone, x, y, z) {
  if (!bone) return;
  const delta = toWorldDir(dir(x, y, z), new THREE.Vector3());
  bone.parent.getWorldQuaternion(_pq);
  bone.position.add(delta.applyQuaternion(_pq.invert()));
  bone.updateMatrixWorld(true);
}

/** Richtet den Knochen so aus, dass er (Richtung zum Kindknochen) auf
    targetDir zeigt. weight 0..1 mischt mit der aktuellen Haltung. */
function aim(bone, child, targetDir, weight = 1) {
  aimWorld(bone, child, toWorldDir(targetDir, new THREE.Vector3()), weight);
}
/** Wie aim(), aber auf einen Weltpunkt zielen (z. B. Hand zum Kinn). */
function aimAt(bone, child, point, weight = 1) {
  if (!bone) return;
  aimWorld(bone, child, point.clone().sub(bone.getWorldPosition(new THREE.Vector3())), weight);
}
function aimWorld(bone, child, worldDir, weight) {
  if (!bone || !child || weight <= 0) return;
  bone.getWorldPosition(_va);
  child.getWorldPosition(_vb);
  const current = _vb.sub(_va).normalize();
  const full = new THREE.Quaternion().setFromUnitVectors(current, _va.copy(worldDir).normalize());
  // Anteilig drehen: von "keine Drehung" (identity) bis "volle Drehung"
  const q = weight < 1 ? new THREE.Quaternion().slerpQuaternions(_identity, full, weight) : full;
  applyWorldRotation(bone, q);
}

const dir = (x, y, z) => new THREE.Vector3(x, y, z);

// --- Glattes Rauschen für lebendige, nicht-periodische Bewegung -----------
function smoothNoise(t, seed) {
  // Summe inkommensurabler Sinuswellen -> wirkt zufällig, ist aber stetig
  return (Math.sin(t * 1.0 + seed) * 0.5 +
          Math.sin(t * 2.17 + seed * 1.7) * 0.3 +
          Math.sin(t * 4.31 + seed * 2.9) * 0.2);
}
const damp = (current, target, rate, dt) => current + (target - current) * (1 - Math.exp(-rate * dt));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

/** Pro Frame: Ruhepose -> Clip (Mixer) -> Laufweg -> Idle -> Laufzyklus -> Gesten -> Physik */
function updatePose(dt) {
  if (!modelRoot) return;
  const time = performance.now() / 1000;
  resetToRestPose();
  if (mixer) mixer.update(dt);
  updateLocomotion(dt);                 // Position/Drehung des Modells beim Laufen
  modelRoot.updateMatrixWorld(true);

  idleWeight = damp(idleWeight, idleEnabled ? 1 : 0, 6, dt);
  updateLook(time, dt);
  if (idleWeight > 0.001) {
    applyIdle(time, idleWeight);
  } else if (headFollow) {
    // Ohne Idle trotzdem dem Mauszeiger folgen
    rotate(rig.head, AXIS.y, look.yaw);
    rotate(rig.head, AXIS.x, look.pitch);
  }
  applyWalk(dt, walk.weight);
  applyGesture();
  if (PHYSICS.enabled && physicsInitialized) keepHandsOutOfSkirt();
  updatePhysics(dt);
}

