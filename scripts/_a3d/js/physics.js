/* physics.js - Federknochen für Haare, Krawatte, Rock, Ärmel + Kollision
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Sekundärbewegung: Federknochen (Spring Bones) für Haare, Krawatte, Rock
   -------------------------------------------------------------------------
   Prinzip wie bei VRM-SpringBones: Jeder Knochen hat eine "Spitze" als
   Massenpunkt. Pro Schritt wirken Trägheit, eine Rückstellkraft in die
   animierte Haltung (stiffness), Schwerkraft und Dämpfung (drag). Danach
   wird die Spitze aus Kollisionskörpern (Kugeln/Kapseln am Körper)
   herausgeschoben und der Knochen in ihre Richtung gedreht.
   Kollisionskörper werden in Weltkoordinaten der Ruhepose angegeben und
   beim Laden an ihren Knochen gehängt - so muss man die schrägen lokalen
   Achsen des Rigs nicht kennen.
   ========================================================================= */
const PHYSICS = {
  enabled: true,
  step: 1 / 60,          // feste Schrittweite für stabile Simulation
  maxSteps: 4,
  gravityDir: new THREE.Vector3(0, -1, 0)
};

// Kollisionskörper: Kugel = {bone, at, r}, Kapsel = {bone, from, to, r}
// Koordinaten = Welt-Position in der Ruhepose (Meter). Gruppen werden unten
// den Ketten zugeordnet.
const COLLIDERS = {
  body: [
    { bone: "頭",     at: [0, 1.47, 0.03],                  r: 0.115 },
    { bone: "首",     at: [0, 1.33, 0.03],                  r: 0.05 },
    { bone: "上半身2", from: [0, 1.14, 0.05], to: [0, 1.25, 0.04], r: 0.07 },
    { bone: "上半身",  from: [0, 1.02, 0.07], to: [0, 1.12, 0.06],  r: 0.065 },
    { bone: "下半身",  from: [0, 0.97, 0.075], to: [0, 0.88, 0.075], r: 0.105 }
  ],
  legs: [
    { bone: "足.L", from: [0.075, 0.84, 0.07],  to: [0.05, 0.47, 0.075],  r: 0.068 },
    { bone: "足.R", from: [-0.075, 0.84, 0.07], to: [-0.05, 0.47, 0.075], r: 0.068 }
  ],
  // Grobe Hülle des Rocks, damit Ärmel und Hände nicht hineinragen
  skirt: [
    { bone: "下半身", from: [0, 0.93, 0.075], to: [0, 0.80, 0.07], r: 0.155 }
  ],
  arms: [
    { bone: "腕.L",  from: "腕.L",  to: "ひじ.L", r: 0.04 },
    { bone: "腕.R",  from: "腕.R",  to: "ひじ.R", r: 0.04 },
    { bone: "ひじ.L", from: "ひじ.L", to: "手首.L", r: 0.035 },
    { bone: "ひじ.R", from: "ひじ.R", to: "手首.R", r: 0.035 },
    { bone: "手首.L", from: "手首.L", to: "中指１.L", r: 0.04 },
    { bone: "手首.R", from: "手首.R", to: "中指１.R", r: 0.04 }
  ]
};

// Ketten: Startknochen werden bis zum Ende verfolgt (bei Verzweigungen wird
// der Hauptstrang genommen, Nebenstränge stehen als eigene Wurzel drin).
// stiffness: [Wurzel, Spitze] wird entlang der Kette interpoliert.
const SPRING_CHAINS = [
  { name: "Zöpfe", roots: ["ツインテ1.L", "ツインテ1.R"],
    stiffness: [1.6, 0.7], drag: 0.28, gravity: 0.35, hitRadius: 0.03, tip: 0.15,
    colliders: ["body", "legs", "skirt", "arms"] },
  { name: "Zopf-Strähnen", roots: ["ツインテA1.L", "ツインテA1.R", "ツインテB1.L", "ツインテB1.R"],
    stiffness: [1.6, 0.7], drag: 0.28, gravity: 0.35, hitRadius: 0.03, tip: 0.15,
    colliders: ["body", "legs", "skirt", "arms"] },
  { name: "Pony", roots: ["前髪.L", "前髪.R", "前髪中", "前髪あほ毛.L", "前髪アホ毛.R"],
    stiffness: [4.0, 4.0], drag: 0.6, gravity: 0.05, hitRadius: 0.01, tip: 0.08,
    colliders: [] },
  { name: "Krawatte", roots: ["ネクタイ1"],
    stiffness: [2.5, 1.4], drag: 0.45, gravity: 0.3, hitRadius: 0.005, tip: 0.06,
    colliders: ["body"] },
  { name: "Rock", roots: ["横スカート.L", "横スカート.R", "前スカート.L", "前スカート.R", "後スカート.L", "後スカート.R"],
    stiffness: [3.0, 2.2], drag: 0.55, gravity: 0.15, hitRadius: 0.02, tip: 0.06,
    colliders: ["legs", "arms"] },
  { name: "Ärmel", roots: ["袖.L", "袖.R"],
    stiffness: [2.0, 2.0], drag: 0.5, gravity: 0.3, hitRadius: 0.05, tip: 0.12,
    colliders: ["skirt", "legs", "body"] }
];

let springJoints = [];      // in Verarbeitungsreihenfolge (Eltern vor Kindern)
let colliderShapes = {};    // Gruppe -> [{bone, a(local), b(local)|null, r}]
let physicsAccumulator = 0;
let physicsInitialized = false;

function boneByName(name) {
  if (!modelRoot) return null;
  return modelRoot.getObjectByName(name) ||
         modelRoot.getObjectByName(THREE.PropertyBinding.sanitizeNodeName(name));
}

function setupPhysics() {
  springJoints = [];
  colliderShapes = {};
  resetToRestPose();
  modelRoot.updateMatrixWorld(true);

  // Kollisionskörper an Knochen hängen (Weltkoordinaten -> lokale Koordinaten)
  const toLocal = (bone, p) => typeof p === "string"
    ? bone.worldToLocal(boneByName(p).getWorldPosition(new THREE.Vector3()))
    : bone.worldToLocal(new THREE.Vector3().fromArray(p));
  for (const [group, list] of Object.entries(COLLIDERS)) {
    colliderShapes[group] = [];
    for (const c of list) {
      const bone = boneByName(c.bone);
      if (!bone) continue;
      const named = [c.from, c.to].filter(p => typeof p === "string");
      if (named.some(n => !boneByName(n))) continue;          // Knochen fehlt -> weglassen
      colliderShapes[group].push(c.at
        ? { bone, a: toLocal(bone, c.at), b: null, r: c.r }
        : { bone, a: toLocal(bone, c.from), b: toLocal(bone, c.to), r: c.r });
    }
  }

  // Ketten aufbauen
  const pickChild = (bone) => {
    const kids = bone.children.filter(c => c.isBone);
    if (kids.length <= 1) return kids[0] || null;
    // Hauptstrang bevorzugen (Nebenstränge heißen ...A1 / ...B1)
    return kids.find(c => !/[AB]\d/.test(c.name)) || kids[0];
  };
  for (const chain of SPRING_CHAINS) {
    const groups = chain.colliders.map(g => colliderShapes[g] || []).flat();
    for (const rootName of chain.roots) {
      const list = [];
      for (let b = boneByName(rootName); b; b = pickChild(b)) list.push(b);
      list.forEach((bone, i) => {
        const child = pickChild(bone);
        const f = list.length > 1 ? i / (list.length - 1) : 0;
        const axis = child ? child.position.clone() : new THREE.Vector3(0, 1, 0);
        const scale = bone.getWorldScale(new THREE.Vector3()).x;
        const length = (child ? axis.length() : chain.tip) * scale;
        axis.normalize();
        const tail = bone.localToWorld(axis.clone().multiplyScalar(child ? child.position.length() : chain.tip));
        springJoints.push({
          bone, axis, length,
          stiffness: chain.stiffness[0] + (chain.stiffness[1] - chain.stiffness[0]) * f,
          drag: chain.drag, gravity: chain.gravity, hitRadius: chain.hitRadius,
          colliders: groups,
          current: tail.clone(), prev: tail.clone()
        });
      });
    }
  }
  physicsInitialized = true;
  console.log("Physik: " + springJoints.length + " Federknochen, " +
    Object.values(colliderShapes).flat().length + " Kollisionskörper");
}

const _seg = new THREE.Vector3(), _ca = new THREE.Vector3(), _cb = new THREE.Vector3(),
      _closest = new THREE.Vector3(), _push = new THREE.Vector3();

/** Schiebt Punkt p aus einer Kugel/Kapsel heraus (in place). */
function pushOut(p, shape, extra) {
  _ca.copy(shape.a).applyMatrix4(shape.bone.matrixWorld);
  if (shape.b) {
    _cb.copy(shape.b).applyMatrix4(shape.bone.matrixWorld);
    _seg.subVectors(_cb, _ca);
    const t = clamp(_push.subVectors(p, _ca).dot(_seg) / Math.max(_seg.lengthSq(), 1e-8), 0, 1);
    _closest.copy(_ca).addScaledVector(_seg, t);
  } else {
    _closest.copy(_ca);
  }
  const minDist = shape.r + extra;
  _push.subVectors(p, _closest);
  const d = _push.length();
  if (d < minDist && d > 1e-6) p.copy(_closest).addScaledVector(_push, minDist / d);
}

const _wp = new THREE.Vector3(), _pq2 = new THREE.Quaternion(), _restDir = new THREE.Vector3(),
      _next = new THREE.Vector3(), _inertia = new THREE.Vector3(), _toDir = new THREE.Vector3(),
      _rot = new THREE.Quaternion(), _local = new THREE.Quaternion();

function stepSpring(j, dt) {
  const bone = j.bone;
  bone.getWorldPosition(_wp);
  bone.parent.getWorldQuaternion(_pq2);
  // Richtung, in die der Knochen laut Animation zeigen möchte
  _restDir.copy(j.axis).applyQuaternion(bone.quaternion).applyQuaternion(_pq2);

  _inertia.subVectors(j.current, j.prev).multiplyScalar(1 - j.drag);
  _next.copy(j.current).add(_inertia)
       .addScaledVector(_restDir, j.stiffness * dt)
       .addScaledVector(PHYSICS.gravityDir, j.gravity * dt);
  // Länge erhalten
  _next.sub(_wp).normalize().multiplyScalar(j.length).add(_wp);
  // Kollision
  for (const shape of j.colliders) {
    pushOut(_next, shape, j.hitRadius);
    _next.sub(_wp).normalize().multiplyScalar(j.length).add(_wp);
  }
  j.prev.copy(j.current);
  j.current.copy(_next);

  // Knochen zur Spitze drehen (Weltdrehung in Elternraum umrechnen)
  _toDir.subVectors(_next, _wp).normalize();
  _rot.setFromUnitVectors(_restDir, _toDir);
  _local.copy(_pq2).invert().multiply(_rot).multiply(_pq2);
  bone.quaternion.premultiply(_local);
  bone.updateMatrixWorld(true);
}

function updatePhysics(dt) {
  if (!PHYSICS.enabled || !modelRoot) return;
  if (!physicsInitialized) setupPhysics();
  physicsAccumulator = Math.min(physicsAccumulator + dt, PHYSICS.step * PHYSICS.maxSteps);
  // Animierte Haltung merken, damit jeder Teilschritt von ihr ausgeht
  const animated = springJoints.map(j => j.bone.quaternion.clone());
  let steps = 0;
  while (physicsAccumulator >= PHYSICS.step) {
    springJoints.forEach((j, i) => j.bone.quaternion.copy(animated[i]));
    modelRoot.updateMatrixWorld(true);
    for (const j of springJoints) stepSpring(j, PHYSICS.step);
    physicsAccumulator -= PHYSICS.step;
    steps++;
  }
  if (steps === 0) {
    // Kein Schritt fällig: letzte simulierte Richtung trotzdem anwenden
    for (const j of springJoints) {
      j.bone.getWorldPosition(_wp);
      j.bone.parent.getWorldQuaternion(_pq2);
      _restDir.copy(j.axis).applyQuaternion(j.bone.quaternion).applyQuaternion(_pq2);
      _toDir.subVectors(j.current, _wp).normalize();
      _rot.setFromUnitVectors(_restDir, _toDir);
      _local.copy(_pq2).invert().multiply(_rot).multiply(_pq2);
      j.bone.quaternion.premultiply(_local);
      j.bone.updateMatrixWorld(true);
    }
  }
}

/** Haltung der Spitzen zurücksetzen (z. B. nach Umschalten) */
function resetPhysics() {
  for (const j of springJoints) {
    j.bone.updateMatrixWorld(true);
    const tail = j.bone.localToWorld(j.axis.clone().multiplyScalar(j.length / j.bone.getWorldScale(_wp).x));
    j.current.copy(tail); j.prev.copy(tail);
  }
}

/* Hände aus dem Rock halten: Liegt eine Hand in der Rock-Hülle, wird der
   Oberarm minimal nach außen gedreht, bis sie draußen ist (wirkt auch bei
   Gesten wie dem Verbeugen). */
function keepHandsOutOfSkirt() {
  const hull = colliderShapes.skirt || [];
  if (!hull.length) return;
  const sides = [[rig.armL, rig.wristL, rig.handTipL], [rig.armR, rig.wristR, rig.handTipR]];
  const p = new THREE.Vector3(), out = new THREE.Vector3(), shoulder = new THREE.Vector3();
  const from = new THREE.Vector3(), to = new THREE.Vector3(), q = new THREE.Quaternion();
  for (const [arm, wrist, tip] of sides) {
    if (!arm || !wrist || !tip) continue;
    for (let iter = 0; iter < 3; iter++) {
      let worst = null, depth = 0;
      for (const bone of [wrist, tip]) {
        bone.getWorldPosition(p);
        for (const shape of hull) {
          out.copy(p);
          pushOut(out, shape, 0.03);                 // 3 cm Abstand zum Stoff
          const d = out.distanceTo(p);
          if (d > depth) { depth = d; worst = { from: p.clone(), to: out.clone() }; }
        }
      }
      if (!worst) break;
      arm.getWorldPosition(shoulder);
      from.subVectors(worst.from, shoulder).normalize();
      to.subVectors(worst.to, shoulder).normalize();
      applyWorldRotation(arm, q.setFromUnitVectors(from, to));
    }
  }
}
