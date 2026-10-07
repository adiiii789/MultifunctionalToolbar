/* stations.js - Stationen für Präsentationen: Punkte, zu denen die Figur läuft
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Eine Station ist ein Platz auf der Bühne plus Blickrichtung am Ziel.
   Die Position wird als Anteil der Fensterbreite angegeben (0 = linker Rand,
   1 = rechter Rand) und erst beim Laufen in Meter umgerechnet - so passt sie
   auch, wenn das Fenster/Popup breiter oder schmaler wird.

   Feste Stationen (STATIONS_DEFAULT) + eigene (Panel: "＋ Station an
   Mausposition", gespeichert in _a3d/stations.json, getrennt nach Layout).

   Von außen nutzbar (z. B. aus Python per runJavaScript oder vom Board):
     walkTo("Board links")                 -> Promise, true wenn angekommen
     walkTo({ sx: 0.6, face: "left" })     -> beliebiger Punkt
     goHome()                              -> zurück zur Startposition
     getStations()                         -> Namen der Stationen im aktuellen Layout
   Beispiel Präsentation:
     await walkTo("Board links"); showOnBoard("board/folie1.html");
     playGesture("👉 Nach rechts zeigen"); speak("Hier sehen Sie ...");      */

// Blickrichtung am Ziel (Drehung um die Hochachse; + = zur rechten Bildschirmseite)
const STATION_FACES = {
  viewer: { yaw: 0,    label: "👀 zum Publikum" },
  right:  { yaw: 0.6,  label: "↗ nach rechts" },
  left:   { yaw: -0.6, label: "↖ nach links" }
};
const STATION_FACE_ORDER = ["viewer", "right", "left"];

/* Feste Stationen. Position:
     home: true          -> Startplatz (wo die Figur nach dem Laden steht)
     board: 0..1         -> Anteil der Board-Breite (0 = linke Kante), + offset
     sx: 0..1            -> Anteil der Fensterbreite
   layouts: in welchen Layouts sie angeboten wird ("wide" = mit Board). */
const STATIONS_DEFAULT = [
  { name: "Start",        icon: "🏠", home: true,                face: "viewer", layouts: ["wide", "narrow"] },
  { name: "Board links",  icon: "📋", board: 0, offset: 0.02,    face: "right",  layouts: ["wide"] },
  { name: "Board Mitte",  icon: "📋", board: 0.5, offset: 0,     face: "viewer", layouts: ["wide"] },
  { name: "Board rechts", icon: "📋", board: 1, offset: -0.02,   face: "left",   layouts: ["wide"] }
];
const STATIONS_FILE = "stations.json";
const STATIONS_KEY = "a3d.stations.v1";
let userStations = { wide: [], narrow: [] };   // eigene: {name, sx, face}
let currentStation = "Start";                  // zuletzt erreichte Station (für die Anzeige)

function stationLayout() { return typeof currentLayoutKey === "function" ? currentLayoutKey() : "wide"; }

/** Alle Stationen des aktuellen Layouts (feste zuerst). */
function stationList() {
  const lay = stationLayout();
  return STATIONS_DEFAULT.filter(s => s.layouts.includes(lay))
    .concat((userStations[lay] || []).map(s => Object.assign({ user: true, icon: "📍" }, s)));
}
function getStations() { return stationList().map(s => s.name); }
function findStation(name) { return stationList().find(s => s.name === name) || null; }

/** Fensteranteil (0..1) der Station; null = Startplatz. */
function stationScreenX(st) {
  if (st.home) return null;
  if (st.board != null) {
    const r = boardEl.getBoundingClientRect();
    return (r.left + st.board * r.width) / window.innerWidth + (st.offset || 0);
  }
  return st.sx;
}

/** Fensteranteil -> Weltposition x (Meter), passend zum Ziel-Kameraausschnitt.
    Die Kamera schaut gerade nach vorne: Startplatz (x = 0) liegt bei framing.screenX. */
function screenXToWorld(sx, z = 0) {
  const c = targetFraming();
  const tanHalf = Math.tan(THREE.MathUtils.degToRad(c.fov / 2));
  const dist = (c.viewHeight / 2) / tanHalf;
  const aspect = window.innerWidth / window.innerHeight;
  const camX = (1 - 2 * c.screenX) * (c.viewHeight / 2) * aspect;
  return camX + (sx * 2 - 1) * tanHalf * (dist - z) * aspect;
}

/** Zur Station gehen. target: Name oder {sx | x, z, face}. Liefert ein Promise:
    true = angekommen, false = unterwegs abgebrochen (neues Ziel, Clip, Stopp). */
function walkTo(target) {
  const st = typeof target === "string" ? findStation(target) : target;
  if (!st || !modelRoot) {
    console.warn("Station nicht gefunden: " + target);
    return Promise.resolve(false);
  }
  cancelWalkTarget();                                   // vorheriges Ziel verwerfen
  if (typeof currentAction !== "undefined" && currentAction) stopClip();
  idleEnabled = true;                                   // Atmen + Blick laufen beim Gehen weiter
  walk.mode = "none";
  if (typeof markActiveAnimation === "function") markActiveAnimation(IDLE_NAME);
  const face = STATION_FACES[st.face] || STATION_FACES.viewer;
  return new Promise(resolve => {
    walk.target = {
      name: st.name || null,
      pos: () => {
        if (st.x != null) return { x: st.x, z: st.z || 0 };
        const sx = stationScreenX(st);
        return { x: sx == null ? 0 : screenXToWorld(sx, st.z || 0), z: st.z || 0 };
      },
      yaw: face.yaw,
      done: ok => {
        if (ok && st.name) currentStation = st.name;
        if (!ok) currentStation = null;
        updateStationButtons();
        resolve(ok);
      }
    };
    currentStation = null;
    updateStationButtons();
  });
}
function goHome() { return walkTo("Start"); }

/* ---- Eigene Stationen speichern (über das Plugin, sonst localStorage) ---- */
function cleanUserStations(v) {
  const out = { wide: [], narrow: [] };
  if (v && typeof v === "object") {
    for (const lay of ["wide", "narrow"]) {
      for (const s of Array.isArray(v[lay]) ? v[lay] : []) {
        if (s && typeof s.name === "string" && isFinite(s.sx))
          out[lay].push({ name: s.name, sx: +s.sx, face: STATION_FACES[s.face] ? s.face : "viewer" });
      }
    }
  }
  return out;
}
(function loadStations() {
  try { userStations = cleanUserStations(JSON.parse(localStorage.getItem(STATIONS_KEY) || "null")); } catch (e) { /* egal */ }
  if (!/^https?:$/.test(location.protocol)) return;
  fetch(STATIONS_FILE + "?t=" + Date.now(), { cache: "no-store" })
    .then(r => (r.ok ? r.json() : null))
    .then(v => { if (v) { userStations = cleanUserStations(v); renderStationList(); } })
    .catch(() => {});
})();
function saveStations() {
  try { localStorage.setItem(STATIONS_KEY, JSON.stringify(userStations)); } catch (e) { /* egal */ }
  if (/^https?:$/.test(location.protocol)) {
    fetch(STATIONS_FILE, { method: "POST", headers: { "Content-Type": "application/json" },
                           body: JSON.stringify(userStations) })
      .then(r => { if (!r.ok) console.warn("Stationen: Speichern über das Plugin fehlgeschlagen (" + r.status + ")"); })
      .catch(() => {});
  }
}
/** Eigene Station hinzufügen (sx = Anteil der Fensterbreite). */
function addStation(name, sx, face = "viewer", layout = stationLayout()) {
  userStations[layout] = (userStations[layout] || []).filter(s => s.name !== name);
  userStations[layout].push({ name, sx, face });
  saveStations();
  renderStationList();
}
function removeStation(name, layout = stationLayout()) {
  userStations[layout] = (userStations[layout] || []).filter(s => s.name !== name);
  saveStations();
  renderStationList();
}

/* ---- Panel-Abschnitt "📍 Stationen" ---- */
let stationListEl = null;

function buildStationSection(panel) {
  panel.appendChild(makeHeading("📍 Stationen"));
  stationListEl = document.createElement("div");
  panel.appendChild(stationListEl);
  const add = document.createElement("button");
  add.textContent = "＋ Station an Mausposition";
  add.title = "Danach die Maus dorthin bewegen, wo die Figur stehen soll (nur links/rechts zählt)";
  add.onclick = startStationCapture;
  panel.appendChild(add);
  renderStationList();
  let lastLayout = stationLayout();
  window.addEventListener("resize", () => {
    const lay = stationLayout();
    if (lay === lastLayout) return;
    lastLayout = lay;
    renderStationList();
    // Board-Stationen gibt es im anderen Layout nicht -> zurück zum Start
    if (currentStation !== "Start" || walk.target) goHome();
  });
}

function renderStationList() {
  if (!stationListEl) return;
  stationListEl.textContent = "";
  for (const st of stationList()) {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;gap:0.4vw;";
    const go = document.createElement("button");
    go.textContent = st.icon + " " + st.name;
    go.dataset.station = st.name;
    go.style.cssText = "flex:1 1 auto;width:auto;";
    go.title = "Hingehen (" + (STATION_FACES[st.face] || STATION_FACES.viewer).label + ")";
    go.onclick = () => walkTo(st.name);
    row.appendChild(go);
    if (st.user) {
      const face = document.createElement("button");
      face.textContent = (STATION_FACES[st.face] || STATION_FACES.viewer).label.split(" ")[0];
      face.title = "Blickrichtung am Ziel: " + (STATION_FACES[st.face] || STATION_FACES.viewer).label + " (klicken zum Wechseln)";
      face.style.cssText = "flex:0 0 auto;width:auto;text-align:center;";
      face.onclick = () => {
        const next = STATION_FACE_ORDER[(STATION_FACE_ORDER.indexOf(st.face) + 1) % STATION_FACE_ORDER.length];
        addStation(st.name, st.sx, next);
      };
      const del = document.createElement("button");
      del.textContent = "✕";
      del.title = "Station löschen";
      del.style.cssText = "flex:0 0 auto;width:auto;text-align:center;";
      del.onclick = () => removeStation(st.name);
      row.append(face, del);
    }
    stationListEl.appendChild(row);
  }
  updateStationButtons();
}

function updateStationButtons() {
  if (!stationListEl) return;
  const going = walk.target && walk.target.name;
  for (const b of stationListEl.querySelectorAll("button[data-station]")) {
    b.classList.toggle("active", b.dataset.station === (going || currentStation));
    b.style.fontStyle = going && b.dataset.station === going ? "italic" : "";
  }
}

/** Neue Station: Countdown, dann zählt die waagerechte Mausposition. */
function startStationCapture() {
  if (lookCalRunning) return;                        // teilt sich die Sperre mit der Blick-Kalibrierung
  lookCalRunning = true;
  const box = document.createElement("div");
  box.style.cssText = "position:fixed;left:50%;top:10%;transform:translateX(-50%);z-index:10000;" +
    "background:rgba(18,22,30,0.9);color:#fff;padding:12px 18px;border-radius:10px;" +
    "font:14px 'Segoe UI',sans-serif;text-align:center;max-width:80vw;pointer-events:none;";
  document.body.appendChild(box);
  const line = (text, bold) => { const d = document.createElement("div"); d.textContent = text; if (bold) d.style.fontWeight = "600"; return d; };
  let left = LOOK_CAL_SECONDS;
  const render = () => setChildren(box,
    line("📍 Maus dorthin bewegen, wo die Figur stehen soll", true),
    line("Übernahme in " + left + " s – Klick im Fenster übernimmt sofort, Esc bricht ab"));
  render();
  const onClick = () => finish(true);
  const onKey = (e) => { if (e.key === "Escape") finish(false); };
  const timer = setInterval(() => { left--; if (left <= 0) finish(true); else render(); }, 1000);
  setTimeout(() => {
    window.addEventListener("mousedown", onClick, true);
    window.addEventListener("keydown", onKey, true);
  }, 0);
  function finish(ok) {
    clearInterval(timer);
    window.removeEventListener("mousedown", onClick, true);
    window.removeEventListener("keydown", onKey, true);
    lookCalRunning = false;
    if (ok) {
      const sx = clamp(mouseClientX / window.innerWidth, 0.02, 0.98);
      const used = new Set(getStations());
      let n = 1;
      while (used.has("Punkt " + n)) n++;
      addStation("Punkt " + n, sx, "viewer");
      setChildren(box, line("✔ Station „Punkt " + n + "“ gespeichert", true),
        line("Blickrichtung am Ziel über den Knopf daneben ändern"));
    } else {
      setChildren(box, line("Abgebrochen", true));
    }
    setTimeout(() => box.remove(), 1600);
  }
}
