/* panel.js - Seitenpanel: Darstellung, Blick, Idle/Laufen, Stationen, Clips, Gesten, Mimik, Shape Keys
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

document.getElementById("brightness").addEventListener("input", function(){
  renderStyle.brightness = parseFloat(this.value);
  applyLighting();
});

/** Ein-/Aus-Schalter als Button: "Label: an/aus". */
function makeToggle(label, get, set) {
  const b = document.createElement("button");
  const update = () => { b.textContent = label + ": " + (get() ? "an" : "aus"); b.classList.toggle("active", get()); };
  b.onclick = () => { set(!get()); update(); };
  update();
  return b;
}

function makeHeading(text) {
  const h = document.createElement("h4");
  h.textContent = text;
  h.style.marginTop = "1vh";
  return h;
}

/* -------------------------
   Darstellung (vor "🎬 Animationen" eingefügt)
   ------------------------- */
function buildStyleSection(panel) {
  const anchor = document.getElementById("anim-heading");
  const add = (el) => panel.insertBefore(el, anchor);
  const h = document.createElement("h4");
  h.textContent = "🎨 Darstellung";
  add(h);
  const toggles = [
    ["Anime-Shader", "anime", applyRenderStyle],
    ["Konturlinien", "outline", () => {}],
    ["Physik (Haare/Rock)", "physics", () => { PHYSICS.enabled = renderStyle.physics; resetPhysics(); }],
    ["Augen verdecken (Tiefe)", "eyeDepth", applyEyeDepth],
    ["🎥 Kamera frei (Debug)", "debugCamera", () => setDebugCamera(renderStyle.debugCamera)]
  ];
  toggles.forEach(([label, key, onChange]) =>
    add(makeToggle(label, () => renderStyle[key], v => { renderStyle[key] = v; onChange(); })));
  buildLookSection(panel);              // direkt darunter, damit es ohne Scrollen sichtbar ist
  buildVoiceSection(panel);             // Stimme + Lautstärke (voice.js)
  panel.style.display = "block";
}

/* -------------------------
   Bewegung: Idle / Laufen auf der Stelle / Ruhepose
   ------------------------- */
const IDLE_NAME = "🌿 Natürliches Idle";
const WALK_PLACE_NAME = "🚶 Laufen (auf der Stelle)";

function animButton(label, name) {
  const b = document.createElement("button");
  b.textContent = label;
  b.dataset.anim = name;
  b.onclick = () => playAnimation(name);
  return b;
}

function setupAnimationPanel(skippedClips = 0) {
  const panel = document.getElementById("anim-panel");
  panel.appendChild(animButton(IDLE_NAME, IDLE_NAME));
  panel.appendChild(animButton(WALK_PLACE_NAME, WALK_PLACE_NAME));
  const stopBtn = document.createElement("button");
  stopBtn.textContent = "⏹ Stopp (Ruhepose)";
  stopBtn.onclick = stopAnimation;
  panel.appendChild(stopBtn);

  buildStationSection(panel);           // Stationen für Präsentationen (stations.js)

  // Blender-Clips, gruppiert nach Kategorie (<Kategorie>_<Name>)
  const cats = getClipCategories();
  panel.appendChild(makeHeading("🎞 Clips"));
  if (skippedClips > 0) {
    const note = document.createElement("div");
    note.style.cssText = "font-size:1.2vh;opacity:0.6;margin:0.5vh 0;";
    note.textContent = skippedClips + " kaputte Clips ausgeblendet (Dauer 0/NaN, z. B. MMD-Reste)";
    panel.appendChild(note);
  }
  if (!Object.keys(cats).length) {
    const note = document.createElement("div");
    note.style.cssText = "font-size:1.2vh;opacity:0.6;margin:0.5vh 0;";
    note.textContent = "Keine Clips im Modell. In Blender als <Kategorie>_<Name> anlegen.";
    panel.appendChild(note);
  } else {
    panel.appendChild(makeToggle("🔁 Clips wiederholen", () => CLIPS.loop, v => { CLIPS.loop = v; }));
    for (const [cat, names] of Object.entries(cats)) {
      const h = makeHeading("📁 " + cat);
      h.classList.add("sub");            // Unterabschnitt (einklappbar innerhalb von "Clips")
      h.style.fontSize = "0.9em";
      h.style.opacity = "0.8";
      panel.appendChild(h);
      for (const name of names) {
        const { label, clip } = clipLibrary.clips[name];
        panel.appendChild(animButton(label + "  (" + clip.duration.toFixed(1) + "s)", name));
      }
    }
  }

  buildGestureSection(panel);           // Gesten + Moderation (gestures.js)

  // Mimik zum Ausprobieren (kurzer Ausdruck, 2.5 s)
  panel.appendChild(makeHeading("😊 Mimik"));
  for (const name of Object.keys(EXPRESSIONS).filter(n => n !== "neutral")) {
    const b = document.createElement("button");
    b.textContent = name;
    b.onclick = () => setExpression(name, 1, 2.5);
    panel.appendChild(b);
  }
  buildShapeKeySection(panel);          // einzelne Shape Keys von Hand (zum Testen)
  organizePanelSections(panel);         // alle Abschnitte einklappbar machen
  panel.style.display = "block";
}

/* -------------------------
   Shape Keys von Hand setzen (wie in Blender) - zum Testen der Morphs.
   Ein Schieberegler > 0 überschreibt Mimik, Lippensync und Blinzeln für
   diesen Shape Key; zurück auf 0 gibt ihn wieder frei.
   ------------------------- */
function buildShapeKeySection(panel) {
  panel.appendChild(makeHeading("🧪 Shape Keys"));
  const info = document.createElement("div");
  info.style.cssText = "font-size:1.2vh;opacity:0.7;margin:0 0 0.6vh 0;";
  const gl2 = renderer && renderer.capabilities && renderer.capabilities.isWebGL2;
  info.textContent = gl2 ? "WebGL 2: alle Shape Keys gleichzeitig möglich"
                         : "WebGL 1: höchstens " + MORPH_LIMIT_WEBGL1 + " Shape Keys gleichzeitig sichtbar (die stärksten)";
  panel.appendChild(info);
  const mesh = morphMeshes[0];
  if (!mesh) { info.textContent = "Keine Shape Keys im Modell gefunden."; return; }
  const sliders = [];
  const reset = document.createElement("button");
  reset.textContent = "↺ Alle freigeben (0)";
  reset.onclick = () => { clearMorphOverrides(); sliders.forEach(s => { s.input.value = 0; s.out.textContent = "0.00"; }); };
  panel.appendChild(reset);
  const names = Object.entries(mesh.morphTargetDictionary)
    .sort((a, b) => a[1] - b[1]).map(e => e[0])
    .filter(n => !/^mmd_sdef/i.test(n));              // SDEF-Daten aus MMD, keine echten Shape Keys
  for (const name of names) {
    const row = document.createElement("label");
    row.style.cssText = "display:flex;align-items:center;gap:0.4vw;font-size:1.3vh;margin:0.2vh 0;";
    const text = document.createElement("span");
    text.textContent = name;
    text.style.cssText = "flex:0 0 42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
    text.title = name;
    const input = document.createElement("input");
    input.type = "range"; input.min = "0"; input.max = "1"; input.step = "0.01"; input.value = "0";
    input.style.cssText = "flex:1 1 auto;min-width:0;";
    const out = document.createElement("span");
    out.textContent = "0.00";
    out.style.cssText = "flex:0 0 3.2em;text-align:right;font-variant-numeric:tabular-nums;";
    input.oninput = () => { const v = parseFloat(input.value); out.textContent = v.toFixed(2); setMorphOverride(name, v); };
    row.append(text, input, out);
    panel.appendChild(row);
    sliders.push({ input, out });
  }
}

/* -------------------------
   Einklappbare Abschnitte: Jede Überschrift (h4) wird zum Klapp-Kopf, alles
   bis zur nächsten Überschrift gehört dazu. h4.sub = Unterabschnitt (z. B.
   Clip-Kategorien innerhalb von "Clips"). Der Zustand wird gespeichert
   (panel_state.json über das Plugin, sonst localStorage).
   ------------------------- */
const PANEL_OPEN_BY_DEFAULT = ["💡", "🎨", "👀", "🔊", "🎬"];   // diese Abschnitte starten offen
const PANEL_STATE_KEY = "a3d.panelState.v1";
const PANEL_STATE_FILE = "panel_state.json";
let panelState = {};                 // Titel -> true (eingeklappt) / false (offen)
const panelSections = [];            // { title, setCollapsed }

(function loadPanelState() {
  try { panelState = JSON.parse(localStorage.getItem(PANEL_STATE_KEY) || "{}") || {}; } catch (e) { /* egal */ }
  if (!/^https?:$/.test(location.protocol)) return;
  fetch(PANEL_STATE_FILE + "?t=" + Date.now(), { cache: "no-store" })
    .then(r => (r.ok ? r.json() : null))
    .then(v => {
      if (!v || typeof v !== "object") return;
      panelState = v;
      for (const s of panelSections) if (s.title in panelState) s.setCollapsed(!!panelState[s.title], false);
    })
    .catch(() => {});
})();

let panelStateTimer = null;
function savePanelState() {
  try { localStorage.setItem(PANEL_STATE_KEY, JSON.stringify(panelState)); } catch (e) { /* egal */ }
  if (!/^https?:$/.test(location.protocol)) return;
  clearTimeout(panelStateTimer);                    // mehrere Klicks kurz hintereinander = ein Speichern
  panelStateTimer = setTimeout(() => {
    fetch(PANEL_STATE_FILE, { method: "POST", headers: { "Content-Type": "application/json" },
                              body: JSON.stringify(panelState) }).catch(() => {});
  }, 400);
}

/** Titel ohne Zusatz in Klammern als Schlüssel ("👀 Blick (Popup)" -> "👀 Blick"). */
function sectionKey(h) { return h.textContent.replace(/\s*\(.*\)\s*$/, "").trim(); }

function makeSection(h, isSub) {
  const wrap = document.createElement("div");
  const body = document.createElement("div");
  const title = (isSub ? "↳ " : "") + sectionKey(h);
  const arrow = document.createElement("span");
  arrow.style.cssText = "display:inline-block;width:1.1em;opacity:0.8;";
  h.insertBefore(arrow, h.firstChild);
  h.style.cursor = "pointer";
  h.style.userSelect = "none";
  h.title = "Klicken zum Ein-/Ausklappen";
  wrap.append(h, body);
  const setCollapsed = (collapsed, save = true) => {
    body.style.display = collapsed ? "none" : "";
    arrow.textContent = collapsed ? "▸" : "▾";
    h.style.marginBottom = collapsed ? "0.4vh" : "";
    if (save) { panelState[title] = collapsed; savePanelState(); }
  };
  const byDefault = isSub ? false : !PANEL_OPEN_BY_DEFAULT.some(p => title.startsWith(p));
  setCollapsed(title in panelState ? !!panelState[title] : byDefault, false);
  h.onclick = () => setCollapsed(body.style.display !== "none");
  panelSections.push({ title, setCollapsed });
  return { wrap, body };
}

function organizePanelSections(panel) {
  let section = null, sub = null;
  for (const n of [...panel.childNodes]) {
    const isHeading = n.nodeType === 1 && n.tagName === "H4";
    if (isHeading && !n.classList.contains("sub")) {
      section = makeSection(n, false); sub = null;
      panel.appendChild(section.wrap);
    } else if (isHeading && section) {
      sub = makeSection(n, true);
      section.body.appendChild(sub.wrap);
    } else if (section) {
      (sub || section).body.appendChild(n);
    } else {
      panel.appendChild(n);                             // vor der ersten Überschrift: bleibt oben
    }
  }
}

/* -------------------------
   Blick: Mausverfolgung + Kalibrierung der Blickmitte
   Steht oben im Panel (direkt nach "Darstellung"), damit es in jedem Layout
   ohne Scrollen sichtbar ist. Gilt nur für diesen Modus (Popup ODER Fenster);
   kalibriert wird immer das gerade aktive Layout - das andere Layout erst,
   wenn das Fenster entsprechend breit/schmal ist (im Popup: "⇔ Breit").
   ------------------------- */
const LOOK_CAL_SECONDS = 3;          // Zeit, um die Maus an die gewünschte Stelle zu bringen
const LOOK_LAYOUT_NAMES = { wide: "Breit", narrow: "Schmal" };
const lookRows = {};                 // Layout -> { cal, reset, status }
let lookCalRunning = false;

function buildLookSection(panel) {
  const anchor = document.getElementById("anim-heading");
  const add = (el) => panel.insertBefore(el, anchor);
  add(makeHeading("👀 Blick (" + (VIEW_MODE === "popup" ? "Popup" : "Fenster") + ")"));
  add(makeToggle("Kopf folgt Maus", () => headFollow, v => { headFollow = v; }));
  for (const key of LOOK_LAYOUTS) {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;gap:0.4vw;";
    const cal = document.createElement("button");
    cal.textContent = "🎯 Blickmitte " + LOOK_LAYOUT_NAMES[key];
    cal.style.cssText = "flex:1 1 auto;width:auto;";
    cal.onclick = () => startLookCalibration();
    const reset = document.createElement("button");
    reset.textContent = "↺";
    reset.title = "Blickmitte " + LOOK_LAYOUT_NAMES[key] + " zurücksetzen (Standard)";
    reset.style.cssText = "flex:0 0 auto;width:auto;text-align:center;";
    reset.onclick = () => resetLookCalibration(key);
    row.append(cal, reset);
    add(row);
    const status = document.createElement("div");
    status.style.cssText = "font-size:1.2vh;opacity:0.7;margin:-0.2vh 0 0.6vh 0;";
    add(status);
    lookRows[key] = { cal, reset, status };
  }
  if (anchor) anchor.style.marginTop = "1vh";
  updateLookStatus();
  window.addEventListener("resize", updateLookStatus);   // Layout kann wechseln
}

function updateLookStatus() {
  const active = currentLayoutKey();
  const std = typeof STAGE.lookCenter === "string"
    ? (STAGE.lookCenter === "screen" ? "Bildschirmmitte" : "Fenstermitte") : "eigener Punkt";
  const hint = VIEW_MODE === "popup"
    ? (active === "narrow" ? "Popup mit „⇔ Breit“ verbreitern, dann kalibrieren"
                           : "Popup mit „⇤ Schmal“ verkleinern, dann kalibrieren")
    : "Fenster " + (active === "narrow" ? "breiter" : "schmaler") + " ziehen, dann kalibrieren";
  for (const key of LOOK_LAYOUTS) {
    const r = lookRows[key];
    if (!r) continue;
    const isActive = key === active;
    r.cal.disabled = !isActive;
    r.cal.style.opacity = isActive ? "" : "0.45";
    r.cal.style.cursor = isActive ? "" : "default";
    r.cal.title = isActive ? "Danach die Maus dorthin bewegen, wo die Figur geradeaus schauen soll" : hint;
    const c = lookCalibration[key];
    r.status.textContent = (isActive ? "● aktiv: " : "○ ") +
      (c ? "kalibriert (" + Math.round(c.x * 100) + " % / " + Math.round(c.y * 100) + " % des Fensters)"
         : "Standard (" + std + ")");
  }
}

/** Kalibrierung des aktiven Layouts: Countdown, dann wird die aktuelle
    Mausposition übernommen. Klick im Fenster übernimmt sofort, Esc bricht ab.
    Die Mausposition kommt auch von außerhalb des Fensters (setExternalMouse). */
function startLookCalibration() {
  if (lookCalRunning) return;
  lookCalRunning = true;
  const layout = currentLayoutKey();
  const which = (layout === "wide" ? "breites" : "schmales") + " Layout";
  const box = document.createElement("div");
  box.style.cssText = "position:fixed;left:50%;top:10%;transform:translateX(-50%);z-index:10000;" +
    "background:rgba(18,22,30,0.9);color:#fff;padding:12px 18px;border-radius:10px;" +
    "font:14px 'Segoe UI',sans-serif;text-align:center;max-width:80vw;pointer-events:none;";
  document.body.appendChild(box);
  const line = (text, bold) => { const d = document.createElement("div"); d.textContent = text; if (bold) d.style.fontWeight = "600"; return d; };

  let left = LOOK_CAL_SECONDS;
  const render = () => setChildren(box,
    line("🎯 Blickmitte, " + which + ": Maus dorthin bewegen, wo sie geradeaus schauen soll", true),
    line("Übernahme in " + left + " s – Klick im Fenster übernimmt sofort, Esc bricht ab"));
  render();

  const onClick = () => finish(true);
  const onKey = (e) => { if (e.key === "Escape") finish(false); };
  const timer = setInterval(() => { left--; if (left <= 0) finish(true); else render(); }, 1000);
  // Erst nach diesem Klick lauschen, sonst zählt der Klick auf den Knopf selbst
  setTimeout(() => {
    window.addEventListener("mousedown", onClick, true);
    window.addEventListener("keydown", onKey, true);
  }, 0);

  function finish(ok) {
    clearInterval(timer);
    window.removeEventListener("mousedown", onClick, true);
    window.removeEventListener("keydown", onKey, true);
    lookCalRunning = false;
    if (ok && currentLayoutKey() !== layout) {
      // Fenstergröße hat sich währenddessen geändert -> lieber nichts speichern
      setChildren(box, line("Layout hat gewechselt – bitte nochmal kalibrieren", true));
    } else if (ok) {
      const p = calibrateLookCenterHere();
      const inside = p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1;
      setChildren(box, line("✔ Blickmitte gespeichert (" + which + ")", true),
        line(inside ? "Markiert für einen Moment" : "Punkt liegt außerhalb des Fensters"));
      if (inside) flashMarker(mouseClientX, mouseClientY);
    } else {
      setChildren(box, line("Kalibrierung abgebrochen", true));
    }
    updateLookStatus();
    setTimeout(() => box.remove(), 1800);
  }
}

/** Inhalt eines Elements ersetzen (statt replaceChildren, das ältere QtWebEngine nicht kennt). */
function setChildren(el, ...nodes) {
  el.textContent = "";
  for (const n of nodes) el.appendChild(n);
}

/** Kurzes Fadenkreuz an der gespeicherten Stelle. */
function flashMarker(x, y) {
  const m = document.createElement("div");
  m.style.cssText = "position:fixed;width:26px;height:26px;margin:-13px 0 0 -13px;z-index:10000;" +
    "border:2px solid #ffcc33;border-radius:50%;pointer-events:none;box-shadow:0 0 0 2px rgba(0,0,0,0.4);" +
    "left:" + x + "px;top:" + y + "px;transition:opacity 0.4s;";
  document.body.appendChild(m);
  setTimeout(() => { m.style.opacity = "0"; }, 1200);
  setTimeout(() => m.remove(), 1700);
}

function markActiveAnimation(name) {
  document.querySelectorAll("#anim-panel button[data-anim]").forEach(b =>
    b.classList.toggle("active", b.dataset.anim === name));
}

/** Idle, Laufen auf der Stelle oder ein Clip aus der GLB (voller Name, z. B. "Tanz_Drehen").
    Beim Laufen läuft das Idle mit (Atmen, Blick). */
function playAnimation(name) {
  if (name === IDLE_NAME || name === WALK_PLACE_NAME) {
    stopClip();
    cancelWalkTarget();                  // Weg zu einer Station abbrechen (bleibt stehen)
    idleEnabled = true;
    walk.mode = name === WALK_PLACE_NAME ? "place" : "none";
    markActiveAnimation(name);
    return true;
  }
  return playClip(name);                 // setzt Idle/Laufen selbst aus
}

function stopAnimation() {
  stopClip();
  cancelWalkTarget();
  idleEnabled = false;
  walk.mode = "none";
  markActiveAnimation(null);
}
