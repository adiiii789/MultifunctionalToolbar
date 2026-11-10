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
  breathChest: 0.026,    // Brustkorb hebt sich
  breathShoulder: 0.021, // Schultern heben sich mit
  sway: 0.032,           // langsames Wiegen des Oberkörpers
  armSway: 0.040,        // Arme pendeln leicht (jeder für sich) und hängen dem Oberkörper nach
  // Gewichtsverlagerung: Becken wandert über ein Bein, Hüfte und Schultern kippen gegeneinander
  shift: 0.033,          // so weit wandert das Becken (m)
  shiftHip: 0.055,       // Becken kippt (rad): Hüfte des Standbeins höher
  shiftShoulder: 0.036,  // Schultern kippen dagegen
  shiftTime: 1.2,        // Dauer des Wechsels (s)
  shiftPauseMin: 5, shiftPauseMax: 13,   // so lange bleibt sie auf einem Bein stehen (s)
  // Kleine Eigenheiten zwischendurch (tief durchatmen, auf die Zehen wippen, Arme schwingen,
  // Schultern lockern): alle fidgetMin..fidgetMax Sekunden eine, zufällig. 0 bei fidgetAmount = aus.
  fidgetMin: 9, fidgetMax: 20, fidgetAmount: 0.6,
  freeFootPitch: 0.16,   // entlastetes Bein: Ferse leicht angehoben (rad) ...
  freeFootLift: 0.012,   // ... (m) ...
  freeFootTurn: 0.10,    // ... und Fuß etwas nach außen gedreht (rad)
  lookYaw: 0.32,         // max. Kopfdrehung beim Umschauen (rad)
  lookPitch: 0.10,
  lookPauseMin: 1.8, lookPauseMax: 5.5,
  mouseIdle: 6           // Maus so lange still (s) -> sie schaut sich wieder selbst um
};

const look = {
  yaw: 0, pitch: 0, roll: 0,            // aktuelle Kopfhaltung
  bodyYaw: 0, bodyPitch: 0,             // Oberkörper folgt verzögert
  tYaw: 0, tPitch: 0, tRoll: 0,         // Ziel
  eyeYaw: 0, eyePitch: 0,
  next: 0,                              // Zeitpunkt des nächsten Blickwechsels
  v: {},                                // Geschwindigkeiten für smoothDamp
  focus: null,                          // {x, y, until}: kurz auf einen Punkt im Fenster schauen (lookAtPoint)
  saccade: { yaw: 0, pitch: 0, next: 0, curYaw: 0, curPitch: 0 },   // kleine Augensprünge
  lastYaw: 0                            // Ziel beim letzten Blinzeln (großer Blickwechsel -> blinzeln)
};
// Anteile der Blickdrehung: Oberkörper dreht ein Stück mit, der Rest Hals + Kopf
const LOOK_SHARE = { upper: 0.14, upper2: 0.12, neck: 0.30, head: 0.44 };
const LOOK_TIME = { head: 0.32, body: 0.75, roll: 0.45 };   // Glättungszeiten in s (Oberkörper träger)

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

/** Kurz auf einen Punkt im Fenster schauen (px), z. B. auf etwas, das im Raum angeklickt wurde. */
function lookAtPoint(x, y, seconds = 2.5) {
  look.focus = { x, y, until: performance.now() / 1000 + seconds };
}

function updateLook(time, dt) {
  if (look.focus && time > look.focus.until) { look.focus = null; look.next = time + 0.6; }
  // Der Maus folgt sie nur, solange sie sich bewegt - sonst schaut sie sich wieder selbst um
  const mouseMoving = typeof mouseMovedAt === "undefined" || time - mouseMovedAt < IDLE.mouseIdle;
  const mouse = headFollow && mouseMoving ? getMouseLook() : null;
  const focus = look.focus ? getMouseLook(look.focus.x, look.focus.y) : null;
  if (typeof pet !== "undefined" && pet.active) {   // beim Streicheln nicht zur Hand hochschauen
    look.tYaw = 0; look.tPitch = 0; look.tRoll = 0;
  } else if (focus || mouse) {            // Maus übersteuert das Umschauen
    look.tYaw = (focus || mouse).yaw;
    look.tPitch = (focus || mouse).pitch;
    look.tRoll = -look.tYaw * 0.15;
    look.next = Math.min(look.next, time + 1.2);
  } else if (time >= look.next) {
    pickLookTarget(time);
  }
  // Bei einem großen Blickwechsel blinzelt man (face.js)
  if (Math.abs(look.tYaw - look.lastYaw) > 0.3) {
    look.lastYaw = look.tYaw;
    if (typeof requestBlink === "function") requestBlink();
  }
  // Augen stehen nie ganz still: kleine, schnelle Sprünge um das Blickziel
  const sc = look.saccade;
  if (time >= sc.next) {
    const still = Math.random() < 0.3;
    sc.yaw = still ? 0 : (Math.random() - 0.5) * 0.07;
    sc.pitch = still ? 0 : (Math.random() - 0.5) * 0.04;
    sc.next = time + 0.5 + Math.random() * 1.9;
  }
  sc.curYaw = damp(sc.curYaw, sc.yaw, 30, dt);
  sc.curPitch = damp(sc.curPitch, sc.pitch, 30, dt);
  // Augen springen schnell (Sakkade), der Kopf folgt weich hinterher (beschleunigen +
  // abbremsen statt gleichmäßig), der Oberkörper noch etwas träger.
  look.eyeYaw   = damp(look.eyeYaw,   look.tYaw,   14, dt);
  look.eyePitch = damp(look.eyePitch, look.tPitch, 14, dt);
  const sd = (key, target, time) => smoothDamp(look[key], target, look.v[key] || (look.v[key] = { v: 0 }), time, dt);
  look.yaw       = sd("yaw", look.tYaw, LOOK_TIME.head);
  look.pitch     = sd("pitch", look.tPitch, LOOK_TIME.head);
  look.roll      = sd("roll", look.tRoll, LOOK_TIME.roll);
  look.bodyYaw   = sd("bodyYaw", look.tYaw, LOOK_TIME.body);
  look.bodyPitch = sd("bodyPitch", look.tPitch, LOOK_TIME.body);
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

/* Gewichtsverlagerung im Stand: s = -1 (Gewicht rechts) .. +1 (Gewicht auf dem linken Bein).
   Alle paar Sekunden wechselt sie das Standbein oder steht kurz auf beiden. Becken und
   Füße dazu macht walk.js (updateFeet/applyLegs), die Kippung von Hüfte und Schultern applyIdle.
   Gesten können das Standbein vorgeben: stance.bias = -1..1 (gilt für dieses Bild). */
const stance = { s: 0, target: 0, v: { v: 0 }, next: 3, bias: null };
function updateStance(time, dt) {
  if (time >= stance.next) {
    const side = stance.target > 0 ? -1 : stance.target < 0 ? 1 : (Math.random() < 0.5 ? -1 : 1);
    stance.target = Math.random() < 0.2 ? 0 : side * (0.55 + Math.random() * 0.45);
    stance.next = time + IDLE.shiftPauseMin + Math.random() * (IDLE.shiftPauseMax - IDLE.shiftPauseMin);
  }
  let target = walk.target || walk.mode === "place" ? 0 : stance.target;
  if (stance.bias != null) target = stance.bias;
  stance.bias = null;
  stance.s = smoothDamp(stance.s, target, stance.v, IDLE.shiftTime, dt);
  updateFidget(time);
}

/* Kleine Eigenheiten im Stand - damit sie nicht minutenlang dieselbe Schleife zeigt.
   Jede ist eine kurze Hüllkurve (0..1..0); angewendet in applyIdle und (Zehenwippen) in walk.js. */
const FIDGETS = {
  breath: 3.0,     // tief durchatmen: Brust und Schultern hoch, dann sinken lassen
  toes: 2.4,       // auf die Zehenspitzen wippen
  arms: 2.8,       // beide Arme einmal locker vor und zurück schwingen
  shoulders: 2.4   // Schultern hochziehen und fallen lassen, Kopf kurz zur Seite
};
const fidget = { type: null, t0: 0, next: 6, v: 0, heel: 0, side: 1 };
function updateFidget(time) {
  fidget.v = 0; fidget.heel = 0;
  const busy = gesture || walk.weight > 0.05 || walk.target || (typeof pet !== "undefined" && pet.active);
  if (busy) { fidget.type = null; fidget.next = Math.max(fidget.next, time + 2); return; }
  if (!fidget.type && time >= fidget.next && IDLE.fidgetAmount > 0) {
    const types = Object.keys(FIDGETS);
    fidget.type = types[Math.floor(Math.random() * types.length)];
    fidget.t0 = time;
    fidget.side = Math.random() < 0.5 ? -1 : 1;
  }
  if (!fidget.type) return;
  const x = (time - fidget.t0) / FIDGETS[fidget.type];
  if (x >= 1) {
    fidget.type = null;
    fidget.next = time + IDLE.fidgetMin + Math.random() * (IDLE.fidgetMax - IDLE.fidgetMin);
    return;
  }
  fidget.x = x;
  fidget.v = Math.sin(Math.PI * x) ** 2 * IDLE.fidgetAmount;      // weich an- und abschwellen
  if (fidget.type === "toes") fidget.heel = keys(x, [[0, 0], [0.42, 1, "inOutSine"], [0.56, 1], [1, 0, "inOutSine"]]) * IDLE.fidgetAmount;
}

function applyFidget(w) {
  const v = fidget.v * w, x = fidget.x, s = fidget.side;
  if (v <= 0.001 && fidget.heel <= 0.001) return;
  switch (fidget.type) {
    case "breath":
      rotate(rig.upper2, AXIS.x, -0.07 * v);
      rotate(rig.shoulderL, AXIS.z, 0.10 * v); rotate(rig.shoulderR, AXIS.z, -0.10 * v);
      rotate(rig.head, AXIS.x, -0.06 * v + 0.10 * Math.max(0, Math.sin(Math.PI * (x - 0.55) / 0.45)) * w);  // Kopf hebt sich, sinkt beim Ausatmen
      break;
    case "toes":
      translateBody(rig.center, 0, 0.014 * fidget.heel * w, 0.006 * fidget.heel * w);
      rotate(rig.shoulderL, AXIS.z, 0.025 * fidget.heel * w); rotate(rig.shoulderR, AXIS.z, -0.025 * fidget.heel * w);
      break;
    case "arms": {
      const swing = Math.sin(x * Math.PI * 2) * Math.sin(Math.PI * x) * w * IDLE.fidgetAmount;
      rotate(rig.armL, AXIS.x, -0.22 * swing); rotate(rig.armR, AXIS.x, -0.22 * swing);
      rotate(rig.upper, AXIS.x, 0.03 * swing);
      break;
    }
    case "shoulders":
      rotate(rig.shoulderL, AXIS.z, 0.15 * v); rotate(rig.shoulderR, AXIS.z, -0.15 * v);
      rotate(rig.head, AXIS.z, 0.10 * s * v); rotate(rig.neck, AXIS.y, 0.08 * s * v);
      break;
  }
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

  // 1) Atmen: einatmen etwas schneller als ausatmen, danach eine kleine Pause.
  //    Brust hebt sich, Schultern gehen mit, der Kopf gleicht aus.
  const bp = time * 2 * Math.PI / IDLE.breathPeriod;
  const breath = Math.sin(bp + 0.45 * Math.sin(bp));
  const inhale = breath * 0.5 + 0.5;
  rotate(rig.upper,  AXIS.x, -IDLE.breathChest * 0.35 * inhale * w);
  rotate(rig.upper2, AXIS.x, -IDLE.breathChest * inhale * w);
  rotate(rig.neck,   AXIS.x,  IDLE.breathChest * 0.9 * inhale * w);
  rotate(rig.shoulderL, AXIS.z,  IDLE.breathShoulder * inhale * w);
  rotate(rig.shoulderR, AXIS.z, -IDLE.breathShoulder * inhale * w);

  // 2) Langsames Wiegen des Oberkörpers (beim Laufen kaum)
  const swayT = time * 0.35;
  const sw = w * (1 - 0.8 * walk.weight);
  const roll = t => IDLE.sway * smoothNoise(t * 0.35, 1.3);
  rotate(rig.upper, AXIS.z, roll(time) * sw);
  rotate(rig.upper, AXIS.y, IDLE.sway * 0.8 * smoothNoise(swayT * 0.8, 4.1) * sw);
  rotate(rig.upper, AXIS.x, IDLE.sway * 0.5 * smoothNoise(swayT * 0.6, 7.7) * sw);
  rotate(rig.lower, AXIS.z, -roll(time) * 0.3 * sw);

  // 3) Gewichtsverlagerung: Hüfte des Standbeins höher, Schultern kippen dagegen,
  //    der Kopf bleibt gerade (das Becken selbst wandert in walk.js über das Standbein)
  const st = stance.s * w * (1 - walk.weight);
  rotate(rig.lower,  AXIS.z,  IDLE.shiftHip * st);
  rotate(rig.lower,  AXIS.y,  0.05 * st);
  rotate(rig.upper,  AXIS.z, -IDLE.shiftShoulder * 0.6 * st);
  rotate(rig.upper2, AXIS.z, -IDLE.shiftShoulder * 0.4 * st);
  rotate(rig.upper,  AXIS.y, -0.03 * st);
  rotate(rig.neck,   AXIS.z,  IDLE.shiftShoulder * 0.7 * st);

  // 4) Blick: Oberkörper dreht (verzögert) ein Stück mit, Hals und Kopf den Rest,
  //    plus Mikrobewegung.
  const microYaw = 0.012 * smoothNoise(time * 0.9, 2.2);
  const microPitch = 0.010 * smoothNoise(time * 0.8, 5.4);
  const S = LOOK_SHARE;
  const bodyYaw = look.bodyYaw * w, bodyPitch = look.bodyPitch * w;
  rotate(rig.upper,  AXIS.y, bodyYaw * S.upper);
  rotate(rig.upper2, AXIS.y, bodyYaw * S.upper2);
  rotate(rig.upper2, AXIS.x, bodyPitch * 0.12);
  rotate(rig.lower,  AXIS.y, -bodyYaw * 0.04);                 // Becken minimal gegen
  // Hals + Kopf gleichen aus, damit die Summe genau dem Blick entspricht
  const restYaw = (look.yaw + microYaw) * w - bodyYaw * (S.upper + S.upper2);
  const restPitch = (look.pitch + microPitch) * w - bodyPitch * 0.12;
  const k = S.neck + S.head;
  rotate(rig.neck, AXIS.y, restYaw * S.neck / k);
  rotate(rig.neck, AXIS.x, restPitch * 0.4);
  rotate(rig.head, AXIS.y, restYaw * S.head / k);
  rotate(rig.head, AXIS.x, restPitch * 0.6);
  rotate(rig.head, AXIS.z, look.roll * w);
  rotate(rig.neck, AXIS.z, look.roll * 0.2 * w);

  // 5) Arme: hängen locker (erst jetzt ausrichten - so bleiben sie im Lot, wenn sich der
  //    Oberkörper neigt, statt steif mitzukippen), pendeln jeder für sich ein wenig und
  //    hängen dem Wiegen des Oberkörpers etwas nach. Unterarm und Hand folgen verzögert.
  const lag = (roll(time - 0.45) - roll(time)) * 1.2;
  for (const [side, sx, seed] of [["L", 1, 11.3], ["R", -1, 23.9]]) {
    const A = IDLE.armSway;
    const n = d => smoothNoise((time - d) * 0.42, seed), m = d => smoothNoise((time - d) * 0.33, seed + 5.1);
    const off = (d, kx, kz) => dir(lag * kx + A * kx * n(d) + 0.5 * st * IDLE.shiftShoulder * sx,
                                   0, A * kz * m(d) - 0.02 * breath);
    aim(rig["arm" + side],   rig["elbow" + side],   IDLE["upperArm" + side].clone().add(off(0, 0.6, 1.0)), w);
    aim(rig["elbow" + side], rig["wrist" + side],   IDLE["foreArm" + side].clone().add(off(0.25, 1.0, 1.6)), w);
    aim(rig["wrist" + side], rig["handTip" + side], IDLE["hand" + side].clone().add(off(0.45, 1.3, 2.0)), w);
  }

  // 6) Kleine Eigenheiten (tief durchatmen, Zehenwippen ...)
  applyFidget(w);

  // 7) Augen führen den Blick an (Vorsprung vor dem Kopf) und springen leicht umher
  const eyeYaw = clamp((look.eyeYaw - look.yaw) * 1.4 + look.saccade.curYaw, -0.25, 0.25) * w;
  const eyePitch = clamp((look.eyePitch - look.pitch) * 1.4 + look.saccade.curPitch, -0.15, 0.15) * w;
  for (const eye of [rig.eyeL, rig.eyeR]) {
    rotate(eye, AXIS.y, eyeYaw);
    rotate(eye, AXIS.x, eyePitch);
  }
}
