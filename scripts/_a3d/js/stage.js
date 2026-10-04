/* stage.js - Bühne: Hintergrundbild mit Smartboard, Board-Inhalt, Kamera-
   Ausschnitt (Figur links), Mausblick, Panel ein/aus, Debug-Kamera.
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Einstellungen
   ========================================================================= */
const STAGE = {
  // ---- Breites Layout (Popup breit / Hauptfenster): Figur links, Board rechts ----
  // Hintergrundbild (beliebiges PNG/JPG). Es wird fensterfüllend skaliert;
  // abgeschnitten wird auf der Seite von "align" gegenüber (rechts bleibt sichtbar).

  //TODO hier entfernen für transparency
  background: "assets/stage_background.png",

  align: "right",                       // "right" | "center" | "left"
  // Fläche des Smartboards IM BILD, als Anteil von Bildbreite/-höhe (0..1).
  // Bei eigenem Bild: Pixel-Ecke / Bildgröße, z. B. left = 800 / 1920.
  board: { left: 0.3067, top: 0.1389, width: 0.6313, height: 0.5648 },

  // ---- Schmales Layout (Popup schmal): eigenes Bild, kein Board, Figur mittig ----
  // Umgeschaltet wird, sobald das Fenster schmaler ist als narrowBelowAspect
  // (Breite / Höhe). Der Wechsel wird weich überblendet.
  narrowBelowAspect: 1.0,
  narrow: {
    //TODO hier entfernen für transparency
    background: "assets/stage_background_narrow.png",
    character: { screenX: 0.5, viewHeight: 2.0, targetY: 0.88 }
  },

  boardStart: "board/start.html",       // Anfangsinhalt des Boards (leer = nichts)
  // Chat sitzt im Streifen unter dem Board (Abstände in Pixeln)
  // minLeft: Chat beginnt frühestens hier (Anteil der Fensterbreite), damit er
  // nicht unter der Figur liegt, auch wenn das Board weiter links anfängt.
  chat: { gap: 10, bottom: 12, side: 8, minHeight: 70, minLeft: 0.36 },
  // Wo die Figur im Fenster steht und wie groß sie wirkt
  character: {
    screenX: 0.20,      // horizontale Position (0 = linker Rand, 1 = rechter Rand)
    viewHeight: 2.0,    // sichtbare Höhe in Metern (größer = Figur kleiner)
    targetY: 0.88,      // Höhe des Bildmittelpunkts in Metern
    fov: 30             // Brennweite (kleiner = weniger Verzerrung)
  },
  // Mausblick: wie stark der Kopf dem Abstand Maus <-> Augen folgt
  lookYawScale: 0.55,
  lookLimits: { yaw: 0.7, up: 0.25, down: 0.18 },
  // Wie stark der Kopf nach oben/unten folgt, wenn die Maus über/unter den
  // Augen ist (Maus auf Augenhöhe = geradeaus). Klein halten, sonst wirkt
  // der Blick schnell "zu tief", weil Chat und Board unterhalb liegen.
  lookPitchScale: 0.22,
  groundShadow: { radius: 0.32, opacity: 0.35 }   // weicher Schatten unter den Füßen
};

const stageState = {
  debugCamera: false,     // Kamera mit der Maus drehen/zoomen (nur zum Testen)
  panelVisible: false,
  narrow: false,          // aktuelles Layout
  framing: null           // aktueller (weich nachgeführter) Kamera-Ausschnitt
};

/* =========================================================================
   Hintergrund + Board-Fläche
   ========================================================================= */
const stageEl = document.getElementById("stage");
const panelEl = document.getElementById("anim-panel");
const stageImg = document.getElementById("stage-bg");
const narrowImg = document.getElementById("stage-narrow-bg");
const boardEl = document.getElementById("board");
const boardFrame = document.getElementById("board-frame");

/** Layout wählen: schmales Fenster -> eigenes Bild ohne Board, Figur mittig. */
function updateLayoutMode() {
  stageState.narrow = window.innerWidth / window.innerHeight < STAGE.narrowBelowAspect;
  document.body.classList.toggle("layout-narrow", stageState.narrow);
}
updateLayoutMode();   // sofort, damit die Figur nicht erst von der falschen Seite hereingleitet

function layoutStage() {
  const iw = stageImg.naturalWidth, ih = stageImg.naturalHeight;
  const W = window.innerWidth, H = window.innerHeight;
  updateLayoutMode();
  if (!iw || !ih) {                     // kein Bild: Board über die rechte Hälfte
    Object.assign(stageEl.style, { left: "0px", top: "0px", width: W + "px", height: H + "px" });
  } else {
    const s = Math.max(W / iw, H / ih);  // "cover": Fenster immer voll
    const sw = iw * s, sh = ih * s;
    const left = STAGE.align === "right" ? W - sw : STAGE.align === "left" ? 0 : (W - sw) / 2;
    Object.assign(stageEl.style, {
      left: left + "px", top: (H - sh) / 2 + "px", width: sw + "px", height: sh + "px"
    });
  }
  const b = STAGE.board;
  Object.assign(boardEl.style, {
    left: b.left * 100 + "%", top: b.top * 100 + "%",
    width: b.width * 100 + "%", height: b.height * 100 + "%"
  });
  layoutChatAndPanel();
}

/** Chat genau unter das Board setzen und die Leiste darüber enden lassen,
    damit sich Chat, Board und Gesten-Leiste nie überlappen. */
function layoutChatAndPanel() {
  const chat = document.getElementById("chat-container");
  const c = STAGE.chat, W = window.innerWidth, H = window.innerHeight;
  // Schmales Layout: kein Board -> Chat unten über die ganze Breite, max. ~32 % Höhe
  const r = stageState.narrow
    ? { left: 0, right: W, bottom: H * 0.68 - c.gap }
    : boardEl.getBoundingClientRect();
  const left = Math.max(c.side, r.left, stageState.narrow ? 0 : W * c.minLeft);
  const right = Math.min(W - c.side, r.right);
  const free = H - r.bottom - c.gap - c.bottom;          // Platz unter dem Board
  const height = Math.max(c.minHeight, free);
  Object.assign(chat.style, {
    left: left + "px", right: "auto", width: Math.max(160, right - left) + "px",
    bottom: c.bottom + "px", maxHeight: height + "px"
  });
  // Seitenleiste endet über dem Chat-Bereich
  const panelTop = panelEl.getBoundingClientRect().top || H * 0.07;
  const chatTop = H - c.bottom - height;
  panelEl.style.maxHeight = Math.max(150, chatTop - c.gap - panelTop) + "px";
}

stageImg.addEventListener("load", layoutStage);
stageImg.addEventListener("error", () => {
  console.warn("Hintergrundbild nicht gefunden: " + STAGE.background);
  stageImg.style.display = "none";
  layoutStage();
});
stageImg.src = STAGE.background;
narrowImg.addEventListener("error", () => {
  console.warn("Hintergrundbild (schmal) nicht gefunden: " + STAGE.narrow.background);
  narrowImg.style.display = "none";
});
narrowImg.src = STAGE.narrow.background;
window.addEventListener("resize", layoutStage);

/** Inhalt aufs Board bringen: URL/Dateipfad (iframe) oder HTML-Text. */
function showOnBoard(content) {
  content = String(content || "");
  const looksLikeUrl = /^(https?:|file:|\.{0,2}\/)|\.html?(\?|#|$)/i.test(content.trim());
  boardEl.classList.toggle("empty", !content);
  if (!content) { boardFrame.removeAttribute("srcdoc"); boardFrame.src = "about:blank"; return; }
  if (looksLikeUrl) {
    boardFrame.removeAttribute("srcdoc");
    boardFrame.src = content.trim();
  } else {
    boardFrame.srcdoc = "<!doctype html><meta charset='utf-8'>" +
      "<style>body{margin:0;padding:3%;font-family:'Segoe UI',sans-serif;color:#1d2a33}</style>" + content;
  }
}
function clearBoard() { showOnBoard(""); }
showOnBoard(STAGE.boardStart);

/* =========================================================================
   Kamera-Ausschnitt: Figur steht links, Board bleibt frei
   ========================================================================= */
/** Ziel-Ausschnitt des aktuellen Layouts (breit: STAGE.character, schmal: STAGE.narrow.character). */
function targetFraming() {
  return Object.assign({}, STAGE.character, stageState.narrow ? STAGE.narrow.character : {});
}

/** Pro Frame: Ausschnitt weich zum Ziel des Layouts bewegen (Figur gleitet
    beim Umschalten breit <-> schmal in die neue Position). */
function updateStageFraming(dt) {
  const target = targetFraming();
  if (!stageState.framing) { stageState.framing = target; applyCameraFraming(); return; }
  const f = stageState.framing;
  let changed = false;
  for (const key of ["screenX", "viewHeight", "targetY", "fov"]) {
    const next = damp(f[key], target[key], 8, dt);
    if (Math.abs(next - f[key]) > 1e-5) changed = true;
    f[key] = Math.abs(next - target[key]) < 1e-4 ? target[key] : next;
  }
  if (changed) applyCameraFraming();
}

function applyCameraFraming() {
  if (!camera || stageState.debugCamera) return;
  const c = stageState.framing || targetFraming();
  const aspect = window.innerWidth / window.innerHeight;
  const halfH = c.viewHeight / 2;
  const dist = halfH / Math.tan(THREE.MathUtils.degToRad(c.fov / 2));
  const halfW = halfH * aspect;
  const tx = (1 - 2 * c.screenX) * halfW;     // Kamera nach rechts schieben -> Figur links
  camera.fov = c.fov;
  camera.aspect = aspect;
  camera.position.set(tx, c.targetY, dist);
  camera.lookAt(tx, c.targetY, 0);
  camera.updateProjectionMatrix();
}

/* =========================================================================
   Mausblick: Kopf schaut zum Mauszeiger (auch Richtung Board)
   ========================================================================= */
const _ndc = new THREE.Vector2(), _headPos = new THREE.Vector3();
let mouseClientX = window.innerWidth * 0.6, mouseClientY = window.innerHeight * 0.4;
window.addEventListener("mousemove", (e) => { mouseClientX = e.clientX; mouseClientY = e.clientY; });

/** Mausposition von außen setzen (Fensterkoordinaten in px, dürfen auch
    außerhalb des Fensters liegen). Das Plugin ruft das ~30x/s auf, damit der
    Blick auch über dem Board-iframe und über den ganzen Bildschirm folgt. */
function setExternalMouse(x, y) {
  mouseClientX = x;
  mouseClientY = y;
}

/** Kopfdrehung (yaw/pitch, Körperraum) zum Mauszeiger. null = kein Ziel.
    Gerechnet wird mit dem Abstand Maus <-> Augen auf dem Bildschirm:
    Maus auf dem Gesicht = geradeaus, Maus aufs Board = Kopf dreht zum Board. */
function getMouseLook() {
  if (!camera || !rig.head || !modelRoot) return null;
  _ndc.set(mouseClientX / window.innerWidth * 2 - 1, -(mouseClientY / window.innerHeight) * 2 + 1);
  const eye = eyePosition(_headPos).project(camera);
  const L = STAGE.lookLimits;
  // Beim Herumlaufen ist die Figur gedreht: links/rechts dann in Körperrichtung umrechnen
  const facing = Math.cos(modelRoot.rotation.y);
  return {
    yaw: clamp((_ndc.x - eye.x) * STAGE.lookYawScale * facing, -L.yaw, L.yaw),
    pitch: clamp((eye.y - _ndc.y) * STAGE.lookPitchScale, -L.up, L.down)
  };
}

/** Augenposition (Mitte zwischen den Augenknochen, sonst Kopf + 15 cm). */
function eyePosition(out) {
  if (rig.eyeL && rig.eyeR) {
    rig.eyeL.getWorldPosition(out);
    return out.add(rig.eyeR.getWorldPosition(new THREE.Vector3())).multiplyScalar(0.5);
  }
  rig.head.getWorldPosition(out);
  out.y += 0.15;
  return out;
}

/* =========================================================================
   Bodenschatten: weicher Fleck unter den Füßen, folgt der Figur
   ========================================================================= */
let groundShadow = null;
function addGroundShadow() {
  const size = 128, cv = document.createElement("canvas");
  cv.width = cv.height = size;
  const g = cv.getContext("2d");
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, "rgba(0,0,0,1)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  const mat = new THREE.MeshBasicMaterial({
    map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false,
    opacity: STAGE.groundShadow.opacity
  });
  const r = STAGE.groundShadow.radius;
  groundShadow = new THREE.Mesh(new THREE.PlaneGeometry(r * 2, r * 1.2), mat);
  groundShadow.rotation.x = -Math.PI / 2;
  groundShadow.position.y = 0.002;
  groundShadow.renderOrder = -1;
  scene.add(groundShadow);
}
function updateGroundShadow() {
  if (groundShadow && modelRoot) {
    groundShadow.position.x = modelRoot.position.x;
    groundShadow.position.z = modelRoot.position.z + 0.03;
    groundShadow.rotation.z = -modelRoot.rotation.y;
  }
}

/* =========================================================================
   Rechte Leiste ein-/ausblenden
   ========================================================================= */
const panelToggle = document.getElementById("panel-toggle");
function setPanelVisible(visible) {
  stageState.panelVisible = visible;
  panelEl.classList.toggle("collapsed", !visible);
  panelToggle.textContent = visible ? "✕" : "☰";
  panelToggle.title = visible ? "Steuerung ausblenden" : "Steuerung einblenden";
}
panelToggle.addEventListener("click", () => setPanelVisible(!stageState.panelVisible));
setPanelVisible(false);

/* =========================================================================
   Debug-Kamera: mit der Maus drehen (ziehen) und zoomen (Mausrad)
   ========================================================================= */
const debugOrbit = { sph: new THREE.Spherical(), target: new THREE.Vector3(), dragging: false, x: 0, y: 0 };

function setDebugCamera(on) {
  stageState.debugCamera = on;
  renderer.domElement.style.pointerEvents = on ? "auto" : "none";   // sonst klickt man aufs Board
  boardEl.classList.toggle("debug", on);
  if (on) {
    debugOrbit.target.set(modelRoot ? modelRoot.position.x : 0, STAGE.character.targetY, 0);
    debugOrbit.sph.setFromVector3(camera.position.clone().sub(debugOrbit.target));
  } else {
    applyCameraFraming();
  }
}

function applyDebugOrbit() {
  const o = debugOrbit;
  o.sph.phi = clamp(o.sph.phi, 0.15, Math.PI - 0.15);
  o.sph.radius = clamp(o.sph.radius, 0.4, 10);
  camera.position.copy(o.target).add(new THREE.Vector3().setFromSpherical(o.sph));
  camera.lookAt(o.target);
}

function setupDebugCameraControls() {
  const el = renderer.domElement;
  el.addEventListener("mousedown", (e) => {
    debugOrbit.dragging = true; debugOrbit.x = e.clientX; debugOrbit.y = e.clientY;
  });
  window.addEventListener("mouseup", () => { debugOrbit.dragging = false; });
  window.addEventListener("mousemove", (e) => {
    if (!stageState.debugCamera || !debugOrbit.dragging) return;
    debugOrbit.sph.theta -= (e.clientX - debugOrbit.x) * 0.005;
    debugOrbit.sph.phi -= (e.clientY - debugOrbit.y) * 0.005;
    debugOrbit.x = e.clientX; debugOrbit.y = e.clientY;
    applyDebugOrbit();
  });
  el.addEventListener("wheel", (e) => {
    if (!stageState.debugCamera) return;
    e.preventDefault();
    debugOrbit.sph.radius *= 1 + Math.sign(e.deltaY) * 0.1;
    applyDebugOrbit();
  }, { passive: false });
  el.style.pointerEvents = "none";
}
