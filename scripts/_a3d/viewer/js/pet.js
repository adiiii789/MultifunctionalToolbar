/* pet.js - Streicheln am Kopf: Augen zu (X), Kopf schmiegt sich leicht in die Bewegung
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Erkennung ohne Klick: Fährt die Maus mehrmals über den Kopf hin und her,
   sammelt sich "Streichel-Energie" an. Über der Schwelle beginnt die Geste,
   ohne Bewegung klingt sie nach kurzer Zeit wieder ab. Funktioniert auch mit
   der Mausposition vom Plugin (setExternalMouse), also auch über dem Board.
   Von außen: petHead(sekunden) - z. B. zum Testen. */

const PET = {
  enabled: true,
  headRadius: 0.11,     // Trefferkreis um den Oberkopf (m)
  headLift: 0.07,       // Mittelpunkt so weit über dem Kopfknochen (m)
  start: 2.0,           // Mausweg (in Kopf-Durchmessern) zum Starten - ca. 2-3 Striche
  decay: 0.5,           // wie schnell der gesammelte Weg wieder "vergessen" wird (1/s)
  release: 0.7,         // so lange ohne Streichelbewegung -> Ende ...
  minTime: 1.0,         // ... aber frühestens nach so vielen Sekunden
  tilt: 0.12,           // max. Neigung zur Streichelrichtung (rad)
  nod: 0.07             // Kopf leicht nach unten in die Hand (rad)
};

const pet = {
  energy: 0, active: false, since: 0, until: 0, lastStroke: -1e9,
  weight: 0, vel: { v: 0 },          // weiches Ein-/Ausblenden
  roll: 0, lastX: null, lastY: null, lastT: 0, vx: 0,
  circle: null                       // Kopfkreis vom letzten Bild (px)
};

/** Bei jeder Mausbewegung (Fenster und Plugin, siehe stage.js): Streichelweg
    sammeln. Direkt an den Ereignissen gemessen, damit schnelles Hin und Her
    auch bei niedriger Bildrate zählt. */
function petMouseMoved(x, y) {
  const now = performance.now() / 1000;
  const c = pet.circle;
  if (pet.lastX != null && c) {
    const dx = x - pet.lastX, dy = y - pet.lastY, moved = Math.hypot(dx, dy);
    const inside = (px, py) => Math.hypot(px - c.x, py - c.y) < c.r;
    // Nur Bewegung, die ganz auf dem Kopf liegt (Hineinfahren von außen zählt nicht)
    if (moved > 0.5 && inside(x, y) && inside(pet.lastX, pet.lastY)) {
      pet.energy += moved / (2 * c.r);                            // Mausweg in Kopf-Durchmessern
      const dt = Math.max(now - pet.lastT, 1 / 120);
      pet.vx += (dx / dt - pet.vx) * 0.3;                         // Streichelrichtung (px/s), geglättet
      pet.lastStroke = now;
    }
  }
  pet.lastX = x; pet.lastY = y; pet.lastT = now;
}

/** Streicheln von außen auslösen (z. B. Test-Knopf). */
function petHead(seconds = 2.5) {
  pet.until = performance.now() / 1000 + seconds;
}

const _petC = new THREE.Vector3(), _petE = new THREE.Vector3(), _petUp = new THREE.Vector3();

/** Oberkopf auf dem Bildschirm: Mittelpunkt + Radius in px (oder null). */
function headScreenCircle() {
  if (!rig.head || !camera) return null;
  rig.head.getWorldPosition(_petC);
  _petC.add(toWorldDir(_petUp.set(0, PET.headLift, 0), _petUp));
  _petE.copy(_petC).add(_petUp.set(PET.headRadius, 0, 0));      // Punkt am Rand -> Radius
  _petC.project(camera); _petE.project(camera);
  const W = window.innerWidth, H = window.innerHeight;
  const cx = (_petC.x + 1) / 2 * W, cy = (1 - _petC.y) / 2 * H;
  return { x: cx, y: cy, r: Math.max(8, Math.abs((_petE.x + 1) / 2 * W - cx)) };
}

/** Pro Frame (aus updatePose): Streicheln erkennen und anwenden. */
function updatePet(dt, time) {
  // --- Erkennen (Mausweg sammelt petMouseMoved) ---------------------------
  pet.circle = PET.enabled ? headScreenCircle() : null;
  pet.energy *= Math.exp(-PET.decay * dt);
  if (time - pet.lastStroke > 0.15) pet.vx = damp(pet.vx, 0, 6, dt);
  const forced = time < pet.until;
  if (!pet.active && (pet.energy > PET.start || forced)) { pet.active = true; pet.since = time; }
  if (pet.active && !forced && time - pet.lastStroke > PET.release && time - pet.since > PET.minTime) {
    pet.active = false;
    pet.energy = 0;
  }

  pet.weight = clamp(smoothDamp(pet.weight, pet.active ? 1 : 0, pet.vel, pet.active ? 0.18 : 0.35, dt), 0, 1);
  if (pet.weight < 0.002) return;

  // --- Anwenden: kleine Geste -------------------------------------------
  const w = pet.weight;
  // Kopf neigt sich in Streichelrichtung (Hand nach rechts -> Kopf zur rechten Bildschirmseite)
  const toward = clamp(-pet.vx / 900, -1, 1) * PET.tilt;
  pet.roll = damp(pet.roll, toward + 0.04 * Math.sin(time * 2.1), 5, dt);
  turnHead(0, PET.nod, pet.roll, w);
  // Schultern ganz leicht hoch (wohlig)
  rotate(rig.shoulderL, AXIS.z, 0.04 * w);
  rotate(rig.shoulderR, AXIS.z, -0.04 * w);
}
