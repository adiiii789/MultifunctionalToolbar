/* hands.js - Fingerposen (locker, Faust, Zeigen, flach, offen ...) + Handflächen drehen
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Prinzip: Beim Laden wird für jedes Fingerglied einmal die Beugeachse aus der
   Ruhepose berechnet (Fingerrichtung x Handflächen-Normale) und im lokalen
   Raum des Knochens gespeichert. Danach ist "Finger um 60° beugen" unabhängig
   davon, wie Arm und Hand gerade stehen. */

// Fingerknochen (MMD-Namen). Daumen hat 3 Glieder (0-2), die anderen 1-3.
const FINGER_BONES = {
  thumb:  ["親指０", "親指１", "親指２"],
  index:  ["人指１", "人指２", "人指３"],
  middle: ["中指１", "中指２", "中指３"],
  ring:   ["薬指１", "薬指２", "薬指３"],
  pinky:  ["小指１", "小指２", "小指３"]
};
const FINGERS = Object.keys(FINGER_BONES);

// Beugung je Glied bei curl = 1 (rad). Fingerspitzen beugen etwas weniger.
const CURL_ANGLES = {
  thumb:  [0.35, 0.55, 0.75],
  index:  [1.35, 1.55, 1.05],
  middle: [1.40, 1.60, 1.05],
  ring:   [1.40, 1.60, 1.05],
  pinky:  [1.45, 1.60, 1.05]
};
const SPREAD_ANGLES = { thumb: 0.30, index: 0.16, middle: 0.0, ring: -0.12, pinky: -0.26 };

/* Handposen: curl 0 = gestreckt, 1 = Faust; spread 0..1 = Finger spreizen;
   thumbIn 0..1 = Daumen über die Handfläche. Eigene Posen einfach ergänzen. */
const HAND_POSES = {
  relaxed: { thumb: 0.25, index: 0.22, middle: 0.30, ring: 0.38, pinky: 0.45, spread: 0.05, thumbIn: 0.15 },
  flat:    { thumb: 0.05, index: 0.02, middle: 0.02, ring: 0.03, pinky: 0.04, spread: 0.0,  thumbIn: 0.0 },
  open:    { thumb: 0.05, index: 0.06, middle: 0.10, ring: 0.14, pinky: 0.18, spread: 0.55, thumbIn: 0.0 },
  wave:    { thumb: 0.05, index: 0.0,  middle: 0.02, ring: 0.04, pinky: 0.06, spread: 0.45, thumbIn: 0.0 },
  half:    { thumb: 0.30, index: 0.35, middle: 0.45, ring: 0.55, pinky: 0.60, spread: 0.10, thumbIn: 0.25 },
  fist:    { thumb: 0.80, index: 1.0,  middle: 1.0,  ring: 1.0,  pinky: 1.0,  spread: 0.0,  thumbIn: 0.70 },
  point:   { thumb: 0.75, index: 0.0,  middle: 0.95, ring: 1.0,  pinky: 1.0,  spread: 0.0,  thumbIn: 0.60 },
  chin:    { thumb: 0.30, index: 0.45, middle: 0.75, ring: 0.85, pinky: 0.90, spread: 0.0,  thumbIn: 0.20 }
};

const hands = {
  ready: false,
  L: null, R: null,          // { fingers: {name: [{bone, curlAxis, spreadAxis}]}, palmNormal... }
  idlePose: "relaxed"
};

function setupHands() {
  resetToRestPose();
  modelRoot.updateMatrixWorld(true);
  for (const side of ["L", "R"]) {
    const wrist = rig["wrist" + side];
    const get = n => boneByName(n + "." + side);
    const chains = {};
    for (const f of FINGERS) chains[f] = FINGER_BONES[f].map(get);
    if (!wrist || FINGERS.some(f => chains[f].some(b => !b))) { hands[side] = null; continue; }

    // Handgeometrie in der Ruhepose (Welt): Fingerrichtung, Querachse, Handflächen-Normale
    const P = b => b.getWorldPosition(new THREE.Vector3());
    const w = P(wrist);
    const fingerDir = P(chains.middle[0]).sub(w).normalize();
    const across = P(chains.index[0]).sub(P(chains.pinky[0])).normalize();   // Richtung Daumenseite
    // Linke/rechte Hand gespiegelt -> Kreuzprodukt umdrehen, damit die Normale zur Handfläche zeigt
    const palm = side === "L" ? new THREE.Vector3().crossVectors(fingerDir, across)
                              : new THREE.Vector3().crossVectors(across, fingerDir);
    palm.normalize();

    const data = { wrist, palmLocal: null, fingers: {} };
    // Handflächen-Normale im lokalen Raum des Handgelenks speichern (für orientPalm)
    data.palmLocal = palm.clone().applyQuaternion(wrist.getWorldQuaternion(new THREE.Quaternion()).invert());
    data.fingerLocal = fingerDir.clone().applyQuaternion(wrist.getWorldQuaternion(new THREE.Quaternion()).invert());

    for (const f of FINGERS) {
      data.fingers[f] = chains[f].map((bone, i) => {
        const next = chains[f][i + 1] || null;
        const dirW = next ? P(next).sub(P(bone)).normalize()
                          : P(bone).sub(P(chains[f][i - 1])).normalize();
        // Beugen: dreht die Fingerrichtung Richtung Handfläche -> Achse = Richtung x Normale
        let curlW = new THREE.Vector3().crossVectors(dirW, palm).normalize();
        if (f === "thumb") {
          // Daumen beugt schräg über die Handfläche (Richtung kleiner Finger)
          curlW = new THREE.Vector3().crossVectors(dirW, palm.clone().addScaledVector(across, -0.8).normalize()).normalize();
        }
        const inv = bone.getWorldQuaternion(new THREE.Quaternion()).invert();
        return {
          bone,
          curlAxis: curlW.applyQuaternion(inv).normalize(),
          spreadAxis: palm.clone().applyQuaternion(inv).normalize(),
          thumbInAxis: across.clone().applyQuaternion(inv).normalize()
        };
      });
    }
    hands[side] = data;
  }
  hands.ready = true;
  console.log("Hände: " + ["L", "R"].filter(s => hands[s]).length + " Hände mit Fingern gefunden");
}

const _hq = new THREE.Quaternion();
function rotateLocal(bone, axis, angle) {
  if (Math.abs(angle) < 1e-5) return;
  bone.quaternion.multiply(_hq.setFromAxisAngle(axis, angle));
}

/** Mischt zwei Posen (a -> b mit Anteil t). Fehlende Werte = 0. */
function mixPose(a, b, t) {
  const out = {};
  for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) out[k] = (a[k] || 0) * (1 - t) + (b[k] || 0) * t;
  return out;
}
function resolvePose(p) { return typeof p === "string" ? (HAND_POSES[p] || HAND_POSES.relaxed) : p; }

/** Wendet eine Handpose an (name oder Objekt). Wird jeden Frame aufgerufen. */
function applyHandPose(side, pose, weight = 1) {
  const h = hands[side];
  if (!h || weight <= 0) return;
  pose = resolvePose(pose);
  const sign = side === "L" ? 1 : -1;
  for (const f of FINGERS) {
    const curl = (pose[f] || 0) * weight;
    const spread = (pose.spread || 0) * SPREAD_ANGLES[f] * weight * sign;
    h.fingers[f].forEach((j, i) => {
      rotateLocal(j.bone, j.curlAxis, curl * CURL_ANGLES[f][i]);
      if (i === 0) rotateLocal(j.bone, j.spreadAxis, spread);
      if (f === "thumb" && i === 0) rotateLocal(j.bone, j.thumbInAxis, -(pose.thumbIn || 0) * 0.5 * weight * sign);
    });
  }
  h.wrist.updateMatrixWorld(true);
}

/* Handfläche ausrichten: dreht den Unterarm (Handdreh-Knochen) um seine Achse,
   bis die Handfläche möglichst in targetDir (Körperrichtung) zeigt.
   Beispiel: Klatschen -> Handflächen zueinander, Achselzucken -> nach oben. */
const _pn = new THREE.Vector3(), _fa = new THREE.Vector3(), _tg = new THREE.Vector3(), _ra = new THREE.Quaternion();
function orientPalm(side, targetDir, weight = 1) {
  const h = hands[side];
  const twist = rig["twist" + side] || rig["elbow" + side];
  if (!h || !twist || weight <= 0) return;
  const elbow = rig["elbow" + side], wrist = rig["wrist" + side];
  // Drehachse = Unterarm-Richtung
  _fa.copy(wrist.getWorldPosition(new THREE.Vector3())).sub(elbow.getWorldPosition(new THREE.Vector3())).normalize();
  _pn.copy(h.palmLocal).applyQuaternion(wrist.getWorldQuaternion(_ra)).normalize();
  toWorldDir(targetDir, _tg).normalize();
  // beide Richtungen in die Ebene senkrecht zur Achse projizieren
  _pn.addScaledVector(_fa, -_pn.dot(_fa)); _tg.addScaledVector(_fa, -_tg.dot(_fa));
  if (_pn.lengthSq() < 1e-6 || _tg.lengthSq() < 1e-6) return;
  _pn.normalize(); _tg.normalize();
  const angle = Math.atan2(new THREE.Vector3().crossVectors(_pn, _tg).dot(_fa), _pn.dot(_tg));
  applyWorldRotation(twist, _wq.setFromAxisAngle(_fa, angle * weight));
}

/* Pro Frame: Handposen anwenden. Gesten geben über handTargets eine Pose und
   ein Gewicht vor, sonst gilt die lockere Idle-Pose.
   weight = Stärke der lockeren Pose (0 während eines Clips: Finger bleiben,
   wie die Animation sie stellt - eine Gesten-Handpose gilt trotzdem). */
const handTargets = { L: null, R: null };     // {pose, weight} - von Gesten gesetzt, jeden Frame neu
function updateHands(weight = 1) {
  if (!hands.ready) { if (modelRoot) setupHands(); else return; }
  for (const side of ["L", "R"]) {
    const g = handTargets[side];
    handTargets[side] = null;
    const gw = g ? clamp(g.weight, 0, 1.2) : 0;
    const w = Math.max(weight, Math.min(gw, 1));
    if (w <= 0.001) continue;
    const base = HAND_POSES[hands.idlePose];
    applyHandPose(side, g ? mixPose(base, resolvePose(g.pose), gw) : base, w);
  }
}
