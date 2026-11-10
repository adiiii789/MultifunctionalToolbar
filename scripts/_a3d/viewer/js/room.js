/* room.js - Der Raum: helles Klassenzimmer mit Dingen zum Anklicken und rollbarem Board
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Der Raum ist kein Bild, sondern wird hier gezeichnet (SVG, 1920 x 1080) und liegt
   wie bisher das Hintergrundbild HINTER der 3D-Figur. Klicks gehen durch die Figur
   hindurch auf den Raum (das 3D-Canvas lässt Mausklicks durch).

   Zum Anklicken:
     🪟 Fenster      auf/zu - bei offenem Fenster weht Wind (Vorhänge, Haare, Rock)
     🕐 Uhr          zeigt die echte Zeit; Klick: Miku sagt, wie spät es ist
     💡 Lichtschalter Deckenlampen an/aus
     🌤 Himmel        folgt der Tageszeit (Tag / Abend / Nacht), im Panel umschaltbar
     🪴 Pflanze      raschelt; nach ein paar Mal Gießen blüht sie
     🟩 Tafel        hinter dem Board: mit der Maus malen, Schwamm wischt
     📺 Board        am Griff links zur Seite schieben (ziehen oder klicken) und zurück

   Von außen (z. B. aus Python per runJavaScript):
     setBoardAside(true/false)    Board rollt zur Seite / zurück
     pushBoard(true/false)        Miku läuft hin und schiebt es weg / zieht es heran
     setWindowOpen(true/false), setLamp(true/false), setDaytime("auto"|"day"|"evening"|"night")
     wipeChalkboard(), getRoomState()                                                     */

const ROOM = {
  talk: true,                   // Miku sagt etwas zu angeklickten Dingen (z. B. die Uhrzeit)
  boardReturnsOnContent: true,  // neuer Inhalt fürs Board holt ein weggeschobenes Board zurück
  slideSeconds: 1.25,           // so lange rollt das Board
  floorY: 0.868,                // hier stehen die Rollen des Boards (Anteil der Raumhöhe)
  wind: 0.55,                   // Stärke des Winds bei offenem Fenster (wirkt auf physics.js)
  // Tageszeit nach der Uhr (Stunde, ab der sie gilt)
  hours: { day: 6, evening: 17, night: 20 },
  // Licht auf der Figur je Stimmung: Farbe + Helligkeit (toon-shader.js: applyLighting)
  light: {
    day:        { color: 0xffffff, level: 1.00 },
    evening:    { color: 0xfff3e8, level: 0.98 },
    night:      { color: 0xd3dcf5, level: 0.78 },   // Lampe aus
    nightLamp:  { color: 0xfff6ea, level: 0.96 }    // Lampe an
  }
};

const room = {
  windowOpen: false, lamp: null,     // lamp: null = automatisch (abends/nachts an)
  daytime: "auto",                   // auto | day | evening | night
  boardAside: false,
  water: 0,                          // wie oft die Pflanze gegossen wurde
  wind: 0, pushToken: 0, drag: null
};
const ROOM_KEY = "a3d.room.v1", ROOM_FILE = "room_state.json";
const roomEl = document.getElementById("room");
const chalkEl = document.getElementById("chalk");
const boardUnit = document.getElementById("board-unit");
const boardGrip = document.getElementById("board-grip");

/* =========================================================================
   Zeichnung. Koordinaten wie ein 1920 x 1080 großes Bild.
   -------------------------------------------------------------------------
   WICHTIG für die Bildrate: Der Raum liegt unter dem 3D-Canvas, das 60x pro Sekunde
   neu gezeichnet wird. Alles, was sich im Raum DAUERND bewegt, darf deshalb nur eine
   kleine eigene Ebene sein, die der Browser bloß verschiebt (transform/opacity) -
   niemals ein Teil der großen Zeichnung, sonst wird sie jedes Bild neu gemalt
   (gemessen: 28 statt 60 Bilder/s). Darum:
     hinten   (.room-back)   Wand, Boden, Himmel, Tafel            - steht still
     Wolken   (.room-sky)    drei kleine Ebenen, nur verschoben
     vorne    (.room-front)  Fensterrahmen, Uhr, Schalter, Pflanze  - ändert sich nur bei Klick
     Vorhänge (.curtain)     zwei kleine Ebenen, nur verzerrt
     Zeiger   (#clock-hands) winzig, 1x pro Sekunde
   Keine mix-blend-mode- oder filter-Effekte: Die erzwingen ebenfalls Neuzeichnen.
   Farben stehen als CSS-Variablen in viewer.css (#room) - Tag/Abend/Nacht schalten nur die um.
   ========================================================================= */
const em = v => (v / 19.2).toFixed(3) + "em";      // Zeichnungs-Pixel -> em (1em = 1 % der Raumbreite)

function roomBackSvg() {
  // Dielenfugen laufen auf einen Fluchtpunkt zu - gibt dem flachen Boden Tiefe
  let planks = "";
  for (let x = -1200; x <= 3200; x += 150) {
    const x2 = 960 + (x - 960) * 1.39;
    planks += `<line x1="${x}" y1="896" x2="${x2.toFixed(0)}" y2="1080"/>`;
  }
  const lamp = x => `
    <g class="lamp" transform="translate(${x} 0)">
      <rect x="-2" y="0" width="4" height="34" fill="#9aa9bd"/>
      <path d="M-46 62 Q-40 30 0 30 Q40 30 46 62 Z" fill="#f7fafe" stroke="#b9c7d9" stroke-width="2"/>
      <ellipse class="lamp-bulb" cx="0" cy="62" rx="44" ry="7"/>
      <ellipse class="lamp-glow" cx="0" cy="96" rx="210" ry="110" fill="url(#lampGlow)"/>
    </g>`;
  const stars = [[70,170],[120,260],[180,150],[230,330],[300,210],[350,400],[395,170],[90,420],[260,480],[330,300],[150,360],[400,280]]
    .map(([x, y], i) => `<circle cx="${x}" cy="${y}" r="${1.2 + (i % 3) * 0.6}"/>`).join("");
  return `
<svg class="room-back" viewBox="0 0 1920 1080" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="wallG" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="var(--wall-top)"/><stop offset="1" stop-color="var(--wall-bottom)"/></linearGradient>
    <linearGradient id="skyG" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="var(--sky-top)"/><stop offset="0.75" stop-color="var(--sky-bottom)"/>
      <stop offset="1" stop-color="var(--sky-horizon)"/></linearGradient>
    <linearGradient id="floorG" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="var(--floor-top)"/><stop offset="1" stop-color="var(--floor-bottom)"/></linearGradient>
    <linearGradient id="chalkG" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#2f6f5e"/><stop offset="1" stop-color="#245a4d"/></linearGradient>
    <linearGradient id="shaftG" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="var(--sun)" stop-opacity="0.5"/><stop offset="1" stop-color="var(--sun)" stop-opacity="0"/></linearGradient>
    <radialGradient id="lampGlow"><stop offset="0" stop-color="#fff3cf" stop-opacity="0.7"/>
      <stop offset="1" stop-color="#fff3cf" stop-opacity="0"/></radialGradient>
    <radialGradient id="bloomG"><stop offset="0" stop-color="var(--sun)" stop-opacity="0.45"/>
      <stop offset="1" stop-color="var(--sun)" stop-opacity="0"/></radialGradient>
  </defs>

  <!-- Wand, Sockel, Boden -->
  <rect width="1920" height="900" fill="url(#wallG)"/>
  <line x1="0" y1="96" x2="1920" y2="96" stroke="var(--wall-line)" stroke-width="2" opacity="0.5"/>
  <rect y="770" width="1920" height="130" fill="var(--panel)"/>
  <rect y="764" width="1920" height="10" fill="var(--trim)"/>
  <g stroke="var(--wall-line)" stroke-width="2" opacity="0.55">
    ${Array.from({ length: 13 }, (_, i) => `<line x1="${i * 160}" y1="776" x2="${i * 160}" y2="880"/>`).join("")}
  </g>
  <rect y="896" width="1920" height="184" fill="url(#floorG)"/>
  <g stroke="var(--floor-line)" stroke-width="2" opacity="0.6">${planks}
    <line x1="0" y1="948" x2="1920" y2="948" opacity="0.5"/><line x1="0" y1="1020" x2="1920" y2="1020" opacity="0.5"/></g>
  <rect y="880" width="1920" height="18" fill="var(--trim)"/>
  <rect y="896" width="1920" height="3" fill="#00000022"/>

  <!-- Deckenlampen (Klick auf den Schalter) -->
  ${lamp(250)}${lamp(880)}${lamp(1500)}

  <!-- Tafel an der Wand (hinter dem Board): gemalt wird auf dem Canvas #chalk darüber -->
  <g id="chalkboard">
    <rect x="648" y="173" width="1114" height="546" rx="6" fill="#c9a877" stroke="#a8875b" stroke-width="3"/>
    <rect x="664" y="189" width="1082" height="512" fill="url(#chalkG)"/>
    <g fill="none" stroke="#f4f7f2" stroke-width="4" stroke-linecap="round" opacity="0.75">
      <path d="M720 620 q30 -40 60 0 t60 0 t60 0"/>
      <path d="M1560 260 l26 52 l56 6 l-42 38 l12 56 l-52 -30 l-50 30 l12 -56 l-42 -38 l56 -6 z"/>
    </g>
    <text x="730" y="290" class="chalk-text" font-size="54">Heute:</text>
    <text x="730" y="360" class="chalk-text" font-size="38">Mit der Maus malen ✎</text>
    <rect x="648" y="719" width="1114" height="16" rx="3" fill="#b9966a"/>
    <rect x="700" y="709" width="46" height="10" rx="3" fill="#ffffff"/><rect x="756" y="709" width="34" height="10" rx="3" fill="#ffd9e2"/>
    <rect x="800" y="709" width="40" height="10" rx="3" fill="#cfefff"/>
    <g class="hot" data-act="sponge"><title>Tafel wischen</title>
      <rect x="1640" y="694" width="84" height="25" rx="5" fill="#f2c94c"/><rect x="1640" y="694" width="84" height="9" rx="4" fill="#5b7fb5"/></g>
  </g>

  <!-- Blick aus dem Fenster: Himmel, Sonne/Mond, Hügel (die Wolken ziehen als eigene Ebenen davor) -->
  <rect x="50" y="134" width="372" height="502" fill="url(#skyG)"/>
  <g class="stars" fill="#ffffff">${stars}</g>
  <circle class="sun-halo" cx="330" cy="215" r="52"/><circle class="sun" cx="330" cy="215" r="34"/>
  <g class="moon"><circle cx="310" cy="220" r="30" fill="#f4f1dc"/><circle cx="296" cy="212" r="27" fill="var(--sky-top)"/></g>
  <path class="hills" d="M50 636 V560 q60 -40 120 -8 q50 -46 110 -6 q60 -30 142 6 V636 Z"/>
  <path class="hills near" d="M50 636 V596 q90 -30 170 0 q90 -34 202 4 V636 Z"/>
  <!-- Sonnenlicht fällt durchs Fenster auf Wand und Boden -->
  <path class="shaft" d="M60 660 L436 660 L760 1080 L210 1080 Z" fill="url(#shaftG)"/>
  <ellipse class="bloom" cx="236" cy="380" rx="420" ry="420" fill="url(#bloomG)"/>
</svg>`;
}

function roomFrontSvg() {
  return `
<svg class="room-front" viewBox="0 0 1920 1080" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
  <defs><clipPath id="paneClip"><rect x="50" y="134" width="372" height="502" rx="4"/></clipPath></defs>
  <!-- Fenster: Rahmen und Scheiben. Der rechte Flügel schiebt sich beim Öffnen nach links. -->
  <g id="window" class="hot" data-act="window"><title>Fenster öffnen / schließen</title>
    <rect x="50" y="134" width="372" height="502" fill="#ffffff" fill-opacity="0"/>
    <g clip-path="url(#paneClip)">
      <g class="sash-move">
        <rect x="236" y="134" width="186" height="502" fill="#bfe3ff" opacity="0.18"/>
        <path d="M262 150 L330 150 L250 320 L236 320 Z M360 150 L390 150 L300 350 L276 350 Z" fill="#ffffff" opacity="0.28"/>
        <rect x="236" y="134" width="186" height="502" fill="none" stroke="#ffffff" stroke-width="12"/>
        <rect x="244" y="370" width="8" height="46" rx="4" fill="#9fb3c8"/>
      </g>
    </g>
    <rect x="50" y="134" width="186" height="502" fill="#bfe3ff" opacity="0.14"/>
    <path d="M70 150 L130 150 L60 300 L50 300 L50 190 Z" fill="#ffffff" opacity="0.25"/>
    <rect x="50" y="134" width="372" height="502" rx="4" fill="none" stroke="#ffffff" stroke-width="16"/>
    <rect x="231" y="134" width="10" height="502" fill="#ffffff"/>
    <rect x="50" y="380" width="186" height="8" fill="#ffffff"/>
    <rect x="42" y="126" width="388" height="518" rx="8" fill="none" stroke="var(--frame-edge)" stroke-width="3"/>
    <rect x="26" y="640" width="420" height="20" rx="5" fill="#ffffff" stroke="var(--frame-edge)" stroke-width="3"/>
  </g>
  <rect x="0" y="100" width="500" height="12" rx="6" fill="#dfe8f2" stroke="var(--frame-edge)" stroke-width="2"/>

  <!-- Uhr (die Zeiger sind eine eigene kleine Ebene: #clock-hands) -->
  <g id="clock" class="hot" data-act="clock"><title>Wie spät ist es?</title>
    <circle cx="520" cy="58" r="42" fill="#ffffff" stroke="#3fb9d6" stroke-width="7"/>
    <g stroke="#8fa3b8" stroke-width="3" stroke-linecap="round">
      ${Array.from({ length: 12 }, (_, i) => `<line x1="520" y1="${i % 3 ? 24 : 22}" x2="520" y2="${i % 3 ? 28 : 31}" transform="rotate(${i * 30} 520 58)"/>`).join("")}
    </g>
  </g>

  <!-- Lichtschalter -->
  <g id="switch" class="hot" data-act="lamp"><title>Licht an / aus</title>
    <rect x="505" y="236" width="30" height="46" rx="5" fill="#ffffff" stroke="var(--frame-edge)" stroke-width="2.5"/>
    <rect class="switch-knob" x="513" y="243" width="14" height="18" rx="3" fill="#3fb9d6"/>
  </g>

  <!-- Pflanze -->
  <g id="plant" class="hot" data-act="plant"><title>Pflanze gießen</title>
    <g class="plant-leaves">
      <path d="M100 800 Q60 720 30 690 Q80 700 104 770 Z" fill="#5cc48a"/>
      <path d="M100 800 Q96 690 120 640 Q140 700 112 790 Z" fill="#49b37b"/>
      <path d="M104 800 Q150 730 190 716 Q160 770 112 808 Z" fill="#6fd39a"/>
      <path d="M98 800 Q70 760 44 760 Q70 790 100 812 Z" fill="#3fa56f"/>
      <g class="flower"><circle cx="122" cy="640" r="9" fill="#ff9db5"/><circle cx="110" cy="632" r="9" fill="#ffb3c6"/>
        <circle cx="134" cy="632" r="9" fill="#ffb3c6"/><circle cx="122" cy="624" r="9" fill="#ff9db5"/><circle cx="122" cy="633" r="6" fill="#ffe27a"/></g>
    </g>
    <path d="M62 800 H142 L132 900 H72 Z" fill="#ffffff" stroke="var(--frame-edge)" stroke-width="3"/>
    <rect x="56" y="792" width="92" height="16" rx="6" fill="#3fb9d6"/>
    <ellipse cx="102" cy="902" rx="52" ry="7" fill="#00000018"/>
  </g>
</svg>`;
}

/** Kleine, eigene Ebenen für alles, was sich dauernd bewegt (siehe oben). */
function roomLayersHtml() {
  const cloud = (cls, y, scale) => `
    <svg class="cloud ${cls}" viewBox="0 0 202 78" style="top:${em(y - 134)};width:${em(202 * scale)};height:${em(78 * scale)}">
      <ellipse cx="60" cy="40" rx="60" ry="26"/><ellipse cx="105" cy="30" rx="46" ry="30"/>
      <ellipse cx="150" cy="42" rx="52" ry="24"/><ellipse cx="100" cy="52" rx="84" ry="18"/></svg>`;
  const curtain = (cls, x, d) => `
    <svg class="curtain ${cls}" viewBox="${x} 110 96 580" preserveAspectRatio="none"
         style="left:${em(x)};top:${em(110)};width:${em(96)};height:${em(580)}">
      <defs><linearGradient id="g-${cls}" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#ffffff" stop-opacity="0.95"/><stop offset="0.25" stop-color="#d8ecfb" stop-opacity="0.9"/>
        <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.95"/><stop offset="0.75" stop-color="#cfe6f9" stop-opacity="0.9"/>
        <stop offset="1" stop-color="#f4faff" stop-opacity="0.95"/></linearGradient></defs>
      <path d="${d}" fill="url(#g-${cls})"/></svg>`;
  return {
    sky: `<div class="room-sky" style="left:${em(50)};top:${em(134)};width:${em(372)};height:${em(502)}">
      ${cloud("cloud-a", 180, 1.0)}${cloud("cloud-b", 330, 0.7)}${cloud("cloud-c", 430, 1.25)}</div>`,
    top: curtain("curtain-l", 8, "M8 110 H92 Q84 300 96 470 Q104 600 84 690 H12 Q22 520 14 380 Q8 240 8 110 Z") +
         curtain("curtain-r", 398, "M400 110 H486 Q494 250 482 400 Q474 560 490 690 H416 Q398 590 408 460 Q416 300 400 110 Z") + `
    <svg id="clock-hands" viewBox="478 16 84 84" style="left:${em(478)};top:${em(16)};width:${em(84)};height:${em(84)}">
      <line id="clock-h" x1="520" y1="58" x2="520" y2="38" stroke="#2c3e55" stroke-width="5" stroke-linecap="round"/>
      <line id="clock-m" x1="520" y1="58" x2="520" y2="28" stroke="#2c3e55" stroke-width="3.5" stroke-linecap="round"/>
      <line id="clock-s" x1="520" y1="64" x2="520" y2="25" stroke="#ff6b8b" stroke-width="1.6" stroke-linecap="round"/>
      <circle cx="520" cy="58" r="4" fill="#2c3e55"/></svg>`
  };
}
function roomHtml() {
  const layers = roomLayersHtml();
  return roomBackSvg() + layers.sky + roomFrontSvg() + layers.top;
}

/* =========================================================================
   Tageszeit, Licht, Fenster
   ========================================================================= */
function currentDaytime() {
  if (room.daytime !== "auto") return room.daytime;
  const h = new Date().getHours() + new Date().getMinutes() / 60, H = ROOM.hours;
  return h >= H.night || h < H.day ? "night" : h >= H.evening ? "evening" : "day";
}
function lampIsOn() { return room.lamp == null ? currentDaytime() !== "day" : room.lamp; }

function applyRoomState() {
  const tod = currentDaytime(), lamp = lampIsOn();
  for (const t of ["day", "evening", "night"]) roomEl.classList.toggle("tod-" + t, t === tod);
  roomEl.classList.toggle("lamp-on", lamp);
  roomEl.classList.toggle("window-open", room.windowOpen);
  roomEl.classList.toggle("bloom-flower", room.water >= 3);
  document.getElementById("room-shade").className = "tod-" + tod + (lamp ? " lamp-on" : "");
  // Licht auf der Figur passend zur Stimmung im Raum
  const L = ROOM.light;
  window.roomLight = tod === "night" ? (lamp ? L.nightLamp : L.night) : L[tod];
  if (typeof applyLighting === "function") applyLighting();
  if (typeof room3dApply === "function") room3dApply();           // Himmel und Wasser des 3D-Raums
  if (typeof updateRoomPanel === "function") updateRoomPanel();
}
function setWindowOpen(on) { room.windowOpen = !!on; saveRoom(); applyRoomState(); }
function setLamp(on) { room.lamp = on == null ? null : !!on; saveRoom(); applyRoomState(); }
function setDaytime(mode) {
  room.daytime = ["day", "evening", "night"].includes(mode) ? mode : "auto";
  room.lamp = null;                               // Lampe richtet sich wieder nach der Tageszeit
  saveRoom(); applyRoomState();
}
function getRoomState() {
  return { windowOpen: room.windowOpen, lamp: lampIsOn(), daytime: currentDaytime(), boardAside: room.boardAside };
}

/* Zustand merken (über das Plugin in room_state.json, sonst localStorage) */
function saveRoom() {
  const data = JSON.stringify({ windowOpen: room.windowOpen, lamp: room.lamp, daytime: room.daytime,
                                boardAside: room.boardAside, water: room.water,
                                place3d: typeof savedRoom3dPlace === "function" ? savedRoom3dPlace() : room.place3d,
                                glint3d: typeof savedRoom3dGlint === "function" ? savedRoom3dGlint() : room.glint3d });
  try { localStorage.setItem(ROOM_KEY, data); } catch (e) { /* egal */ }
  if (/^https?:$/.test(location.protocol))
    fetch(ROOM_FILE, { method: "POST", headers: { "Content-Type": "application/json" }, body: data }).catch(() => {});
}
function restoreRoom(v) {
  if (!v || typeof v !== "object") return;
  room.windowOpen = !!v.windowOpen;
  room.lamp = v.lamp == null ? null : !!v.lamp;
  room.daytime = ["day", "evening", "night"].includes(v.daytime) ? v.daytime : "auto";
  room.water = +v.water || 0;
  room.place3d = v.place3d || null;               // Lage des 3D-Raums (room3d.js)
  if (room.place3d && typeof setRoom3dPlace === "function") setRoom3dPlace(room.place3d, false);
  room.glint3d = v.glint3d || null;               // Lichtnetz auf dem Wasser (room3d.js)
  if (room.glint3d && typeof setRoom3dGlint === "function") setRoom3dGlint(room.glint3d, false);
  applyRoomState();
  if (v.boardAside) setBoardAside(true, { instant: true, save: false });
}

/* =========================================================================
   Miku reagiert auf das, was angeklickt wird
   ========================================================================= */
/** Hinschauen (Mitte des Elements), dazu optional Mimik und ein Satz. */
function roomReact(el, { face, seconds = 2.5, say } = {}) {
  if (el && typeof lookAtPoint === "function") {
    const r = el.getBoundingClientRect();
    lookAtPoint(r.left + r.width / 2, r.top + r.height / 2, seconds);
  }
  if (face && typeof setExpression === "function") setExpression(face, 1, seconds);
  if (say && ROOM.talk && typeof isSpeaking === "function" && !isSpeaking()) {
    if (typeof addMessage === "function") addMessage(ACTIONS.assistantName, say);
    speak(say);
  }
}

const ROOM_ACTIONS = {
  window(el) {
    setWindowOpen(!room.windowOpen);
    roomReact(el, { face: room.windowOpen ? "happy" : "content", seconds: 2.2 });
  },
  clock(el) {
    const d = new Date(), mm = String(d.getMinutes()).padStart(2, "0");
    roomReact(el, { face: "friendly", seconds: 3, say: "Es ist " + d.getHours() + " Uhr " + (mm === "00" ? "" : mm) + "." });
  },
  lamp(el) {
    setLamp(!lampIsOn());
    roomReact(el, { face: lampIsOn() ? "smile" : "surprised", seconds: 1.8 });
  },
  plant(el) {
    room.water++;
    saveRoom();
    el.classList.remove("rustle"); void el.getBoundingClientRect(); el.classList.add("rustle");   // Animation neu starten
    applyRoomState();
    roomReact(el, { face: room.water === 3 ? "happy" : "smile", seconds: 2,
                    say: room.water === 3 ? "Oh, sie blüht!" : "" });
  },
  sponge(el) { wipeChalkboard(); roomReact(el, { face: "content", seconds: 1.5 }); }
};

/* =========================================================================
   Tafel: mit der Maus malen (Canvas über der gezeichneten Tafel)
   ========================================================================= */
const CHALK = { left: 664, top: 189, width: 1082, height: 512 };   // grüne Fläche in der Zeichnung
let chalkCtx = null, chalkLast = null;
function setupChalkboard() {
  chalkEl.width = CHALK.width; chalkEl.height = CHALK.height;
  Object.assign(chalkEl.style, { left: CHALK.left / 19.2 + "%", top: CHALK.top / 10.8 + "%",
                                 width: CHALK.width / 19.2 + "%", height: CHALK.height / 10.8 + "%" });
  chalkCtx = chalkEl.getContext("2d");
  chalkCtx.lineCap = chalkCtx.lineJoin = "round";
  const at = e => { const r = chalkEl.getBoundingClientRect();
    return { x: (e.clientX - r.left) / r.width * CHALK.width, y: (e.clientY - r.top) / r.height * CHALK.height }; };
  chalkEl.addEventListener("pointerdown", e => {
    chalkEl.setPointerCapture(e.pointerId);
    chalkLast = at(e);
    document.getElementById("chalkboard").classList.add("used");   // Hinweistext ausblenden
  });
  chalkEl.addEventListener("pointermove", e => {
    if (!chalkLast) return;
    const p = at(e);
    // Kreide: mehrere dünne, leicht versetzte Striche statt einer glatten Linie
    for (let i = 0; i < 3; i++) {
      const j = () => (Math.random() - 0.5) * 2.4;
      chalkCtx.strokeStyle = "rgba(246,248,244," + (0.35 + Math.random() * 0.3) + ")";
      chalkCtx.lineWidth = 2.5 + Math.random() * 2.5;
      chalkCtx.beginPath(); chalkCtx.moveTo(chalkLast.x + j(), chalkLast.y + j()); chalkCtx.lineTo(p.x + j(), p.y + j()); chalkCtx.stroke();
    }
    chalkLast = p;
    if (typeof lookAtPoint === "function") lookAtPoint(e.clientX, e.clientY, 1.5);   // sie schaut beim Malen zu
  });
  const end = () => { chalkLast = null; };
  chalkEl.addEventListener("pointerup", end);
  chalkEl.addEventListener("pointercancel", end);
}
function wipeChalkboard() {
  chalkEl.classList.add("wipe");                    // kurz ausblenden, dann leeren
  setTimeout(() => { chalkCtx.clearRect(0, 0, CHALK.width, CHALK.height); chalkEl.classList.remove("wipe"); }, 380);
}

/* =========================================================================
   Board: rollt zur Seite und zurück
   -------------------------------------------------------------------------
   Das Board (#board-unit: Rahmen, Bildfläche, Ständer mit Rollen) wird nur per
   transform verschoben - Lage und Größe "zu Hause" bleiben, wie stage.js sie setzt
   (boardHomeRect). Maße in em: 1em = 1 % der Raumbreite (stage.js setzt font-size).
   ========================================================================= */
/** So weit rollt das Board nach rechts (in em): bis nur noch der Griff zu sehen ist. */
function boardAsideEm() { return 100 - STAGE.board.left * 100 - 0.2; }

function applyBoardOffset(em, animate) {
  boardUnit.classList.toggle("sliding", !!animate);
  boardUnit.style.setProperty("--dx", em.toFixed(3) + "em");
  boardUnit.style.setProperty("--roll", (em / 0.75).toFixed(3) + "rad");     // Rollen drehen sich mit (Radius 0.75em)
}

/** Board zur Seite (true) oder zurück (false). opts.instant: ohne Animation. */
function setBoardAside(aside, opts = {}) {
  if (!document.body.classList.contains("room-builtin")) return;   // eigenes Hintergrundbild: Board ist Teil des Bilds
  aside = !!aside;
  const changed = aside !== room.boardAside;
  room.boardAside = aside;
  boardUnit.style.setProperty("--slide", ROOM.slideSeconds + "s");
  applyBoardOffset(aside ? boardAsideEm() : 0, !opts.instant);
  boardUnit.classList.toggle("aside", aside);
  boardGrip.title = aside ? "Board zurückholen" : "Board zur Seite schieben (klicken oder ziehen)";
  if (changed && !opts.instant) {                   // leichtes Nachwippen am Ende der Fahrt
    boardUnit.classList.remove("settle"); void boardUnit.offsetWidth; boardUnit.classList.add("settle");
  }
  if (opts.save !== false && changed) saveRoom();
  if (typeof updateRoomPanel === "function") updateRoomPanel();
  if (typeof layoutChatAndPanel === "function") layoutChatAndPanel();
}
function toggleBoard() { setBoardAside(!room.boardAside); }

/* Griff: klicken = umschalten, ziehen = Board folgt der Maus und rastet beim Loslassen ein */
function setupBoardGrip() {
  boardGrip.addEventListener("pointerdown", e => {
    boardGrip.setPointerCapture(e.pointerId);
    const em = stageEl.getBoundingClientRect().width / 100;
    room.drag = { x: e.clientX, start: room.boardAside ? boardAsideEm() : 0, em, moved: false, cur: 0, v: 0, last: e.clientX };
    room.drag.cur = room.drag.start;
    e.preventDefault();
  });
  boardGrip.addEventListener("pointermove", e => {
    const d = room.drag;
    if (!d) return;
    if (Math.abs(e.clientX - d.x) > 4) d.moved = true;
    if (!d.moved) return;
    d.v = e.clientX - d.last; d.last = e.clientX;
    d.cur = clamp(d.start + (e.clientX - d.x) / d.em, 0, boardAsideEm());
    applyBoardOffset(d.cur, false);
    if (typeof lookAtPoint === "function") lookAtPoint(e.clientX, e.clientY, 1.5);
  });
  const end = () => {
    const d = room.drag;
    if (!d) return;
    room.drag = null;
    if (!d.moved) { toggleBoard(); roomReact(boardGrip, { seconds: 2 }); return; }
    // Schwung entscheidet, sonst die nähere Seite
    const aside = Math.abs(d.v) > 3 ? d.v > 0 : d.cur > boardAsideEm() / 2;
    room.boardAside = !aside;                       // damit setBoardAside den Wechsel bemerkt (speichern, Nachwippen)
    setBoardAside(aside);
  };
  boardGrip.addEventListener("pointerup", end);
  boardGrip.addEventListener("pointercancel", end);
}

/** Miku macht es selbst: läuft zum Board, schiebt es weg (true) bzw. zieht es heran (false)
    und geht zurück an ihren Platz. Ohne Figur/Board (schmales Layout) rollt es einfach so. */
async function pushBoard(aside = true) {
  aside = !!aside;
  if (aside === room.boardAside) return true;
  const token = ++room.pushToken;
  const wait = s => new Promise(r => setTimeout(r, s * 1000));
  if (stageState.narrow || !modelRoot || !idleEnabled || !document.body.classList.contains("room-builtin")) {
    setBoardAside(aside);
    return true;
  }
  const r = boardHomeRect(), W = window.innerWidth;
  // Wegschieben: links neben dem Board. Heranziehen: weit rechts, das Board rollt hinter ihr vorbei.
  const sx = aside ? r.left / W - 0.05 : Math.min(0.82, r.right / W - 0.12);
  if (!await walkTo({ sx: clamp(sx, 0.06, 0.9), face: "right" }) || token !== room.pushToken) return false;
  const name = aside ? "🫸 Schieben" : "🫷 Heranziehen";
  playGesture(name);
  await wait(GESTURES[name].dur * (aside ? 0.34 : 0.38));   // Board setzt sich in Bewegung, wenn die Arme drücken/ziehen
  if (token !== room.pushToken) return false;
  setBoardAside(aside);
  await wait(GESTURES[name].dur * 0.62 + 0.2);
  if (token === room.pushToken && !walk.target) goHome();
  return true;
}

/* =========================================================================
   Pro Frame + Uhr
   ========================================================================= */
/** Aus der Render-Schleife (main.js): Wind bei offenem Fenster - in Böen, von links nach rechts. */
function updateRoom(dt) {
  const t = performance.now() / 1000;
  const windy = room.windowOpen && !stageState.narrow ? 1 : 0;
  room.wind = damp(room.wind, windy, 1.2, dt);
  const gust = 0.45 + 0.55 * Math.max(0, smoothNoise(t * 0.7, 9.1) + 0.35 * Math.sin(t * 3.1));
  if (typeof PHYSICS !== "undefined" && PHYSICS.wind) PHYSICS.wind.set(ROOM.wind * room.wind * gust, 0, 0.25 * ROOM.wind * room.wind * gust);
}

let lastDaytime = null;
function updateClock() {
  const d = new Date();
  const set = (id, deg) => document.getElementById(id).setAttribute("transform", "rotate(" + deg.toFixed(1) + " 520 58)");
  set("clock-h", (d.getHours() % 12 + d.getMinutes() / 60) * 30);
  set("clock-m", (d.getMinutes() + d.getSeconds() / 60) * 6);
  set("clock-s", d.getSeconds() * 6);
  const tod = currentDaytime();
  if (tod !== lastDaytime) { lastDaytime = tod; applyRoomState(); }     // Abend/Nacht bricht an
}

/* =========================================================================
   Panel-Abschnitt "🏫 Raum"
   ========================================================================= */
let updateRoomPanel = null;
function buildRoomSection(panel) {
  panel.appendChild(makeHeading("🏫 Raum"));
  const push = document.createElement("button");
  push.onclick = () => pushBoard(!room.boardAside);
  push.title = "Miku läuft hin und schiebt das Board weg bzw. holt es zurück";
  const roll = document.createElement("button");
  roll.onclick = toggleBoard;
  roll.title = "Board rollt von selbst (wie ein Klick auf den Griff links am Board)";
  const tod = document.createElement("button");
  const order = ["auto", "day", "evening", "night"], names = { auto: "Uhrzeit", day: "Tag", evening: "Abend", night: "Nacht" };
  tod.onclick = () => setDaytime(order[(order.indexOf(room.daytime) + 1) % order.length]);
  const wipe = document.createElement("button");
  wipe.textContent = "🧽 Tafel wischen";
  wipe.onclick = wipeChalkboard;
  // Fenster und Licht lassen sich auch im Raum anklicken - darum hier eigene Knöpfe statt makeToggle
  const win = document.createElement("button"), light = document.createElement("button");
  win.onclick = () => setWindowOpen(!room.windowOpen);
  light.onclick = () => setLamp(!lampIsOn());
  panel.append(push, roll, win, light, tod, wipe,
    makeToggle("💬 Miku reagiert mit Worten", () => ROOM.talk, v => { ROOM.talk = v; }));
  updateRoomPanel = () => {
    push.textContent = room.boardAside ? "🫷 Miku holt das Board zurück" : "🫸 Miku schiebt das Board weg";
    roll.textContent = room.boardAside ? "📺 Board zurückrollen" : "📺 Board zur Seite rollen";
    tod.textContent = "🌤 Tageszeit: " + names[room.daytime] +
      (room.daytime === "auto" ? " (" + names[currentDaytime()] + ")" : "");
    win.textContent = "🪟 Fenster offen: " + (room.windowOpen ? "an" : "aus");
    win.classList.toggle("active", room.windowOpen);
    light.textContent = "💡 Licht: " + (lampIsOn() ? "an" : "aus");
    light.classList.toggle("active", lampIsOn());
  };
  updateRoomPanel();
}

/* =========================================================================
   Start
   ========================================================================= */
(function setupRoom() {
  const builtin = !STAGE.background;                 // eigenes Hintergrundbild -> kein gezeichneter Raum
  document.body.classList.toggle("room-builtin", builtin);
  if (!builtin) return;
  roomEl.innerHTML = roomHtml();
  roomEl.addEventListener("click", e => {
    const hot = e.target.closest ? e.target.closest(".hot") : null;
    if (hot && ROOM_ACTIONS[hot.dataset.act]) ROOM_ACTIONS[hot.dataset.act](hot);
  });
  setupChalkboard();
  setupBoardGrip();
  applyRoomState();
  updateClock();
  setInterval(updateClock, 1000);
  try { restoreRoom(JSON.parse(localStorage.getItem(ROOM_KEY) || "null")); } catch (e) { /* egal */ }
  if (/^https?:$/.test(location.protocol))
    fetch(ROOM_FILE + "?t=" + Date.now(), { cache: "no-store" })
      .then(r => (r.ok ? r.json() : null)).then(restoreRoom).catch(() => {});
  layoutStage();
})();
