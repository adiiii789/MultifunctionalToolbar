/* room3d.js - 3D-Raum als Hintergrund: ein Modell (GLB/glTF) mit Himmel und Wasser als Boden
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Liegt ein Raum-Modell in models/ (siehe ROOM3D.files), ersetzt es den gezeichneten Raum
   aus room.js. Ohne Datei bleibt alles beim gezeichneten Raum.

   Aufbau: Der 3D-Raum wird in ein EIGENES Canvas ganz hinten gezeichnet (unter dem Board),
   die Figur wie bisher in ihr Canvas ganz vorne - so bleibt das Board (eine normale Webseite)
   zwischen Raum und Figur. Beide Canvas nutzen dieselbe Kamera, die Figur steht also wirklich
   im Raum. Der Raum steht still; neu gezeichnet wird er nur, wenn sich die Kamera ändert,
   und für das Wasser ein paar Mal pro Sekunde (ROOM3D.water.fps) - das schont die Bildrate.

   Einrichten: Panel -> "🧊 3D-Raum": Größe, Lage, Drehung und Wasserhöhe mit den Reglern
   einstellen (wird in room_state.json gespeichert). Die Figur steht immer bei x = 0, z = 0 auf
   Höhe 0 und schaut nach +z (zur Kamera); verschoben wird der Raum um sie herum.

   Von außen: setRoom3dPlace({ scale, x, y, z, rot, water }), getRoom3dPlace()              */

const ROOM3D = {
  enabled: true,
  // Erste Datei, die es gibt, wird geladen. Sketchfab-Download "glTF": Ordner entpacken nach
  // models/room/ (scene.gltf + scene.bin + textures/). Oder eine einzelne models/room.glb.
  files: ["models/room.glb", "models/room/Arona room.glb", "models/room/scene.gltf", "models/room/scene.glb"],
  unlit: true,           // Texturen ohne Lichtberechnung zeigen (hell und flach, passt zum Anime-Look)
  height: 2.4,           // Das Modell wird so skaliert, dass der Raum so hoch ist (m) - egal in welchen Einheiten es gebaut ist
  // Teile des Modells, die nicht gezeigt werden (Namen wie in Blender):
  // Cube.141 = riesiger grauer Hintergrundwürfel, Cube = der Boden (stattdessen Wasser)
  hide: ["Cube.141", "Cube"],
  // Ausgangslage; die Regler im Panel überschreiben das (room_state.json)
  // (Werte für "Arona room": Fenster und zerbrochene Wand hinter der Figur, Tischstapel rechts)
  place: { scale: 1, x: 1.95, y: 0, z: -0.45, rot: 30, water: 0.02 },
  water: {
    enabled: true,
    size: 600,           // Kantenlänge der Wasserfläche (m) - reicht bis zum Horizont
    glint: 34,           // so weit um die Figur sieht man das Lichtnetz auf dem Wasser (m)
    tile: [2.9, 4.6],    // Kachelgröße der beiden Lichtnetz-Ebenen (m); verschieden, damit sich nichts wiederholt
    speed: 0.022,        // Kacheln pro Sekunde, die das Lichtnetz wandert
    fps: 20              // so oft wird der Raum für das Wasser neu gezeichnet (0 = Wasser steht)
  },
  // Lichtnetz: Regler im Panel (1 = wie in "water"/"looks" eingestellt); wird in room_state.json gespeichert
  glint: { power: 1, size: 1, speed: 1 },
  // Je Tageszeit: Himmel (oben, Mitte, Horizont), Wasser (Grundfarbe, Lichtnetz + Stärke),
  // Färbung des Raums (Wände, Tische) - nachts taucht alles in Blau
  looks: {
    day:     { sky: ["#2a86ea", "#7cc6ff", "#dff4ff"], water: "#2f8fe0", glint: "#e9fbff", glintPower: 0.26, tint: "#ffffff" },
    evening: { sky: ["#3b3f97", "#e98a78", "#ffd9a0"], water: "#8a5a8f", glint: "#ffe2c0", glintPower: 0.24, tint: "#ffd9cc" },
    night:   { sky: ["#071238", "#12408f", "#2f9fd0"], water: "#1458c8", glint: "#9fecff", glintPower: 0.27, tint: "#4a78e6" }
  }
};

const room3d = {
  ready: false, renderer: null, scene: null, camera: null,
  pivot: null, inner: null, water: null, glints: [], materials: [], dirty: true, lastDraw: 0, camKey: "", tod: null, file: null,
  custom: false,          // Lage im Panel verändert -> wird gespeichert (sonst gilt ROOM3D.place)
  glint: Object.assign({}, ROOM3D.glint), glintCustom: false,   // Lichtnetz: Stärke, Maschengröße, Tempo
  place: Object.assign({}, ROOM3D.place)
};

/* ---- Himmel: gemalt. Die Kamera schaut waagerecht, der Horizont liegt deshalb immer auf
   halber Bildhöhe - gemalt wird also nur die obere Hälfte, darunter liegt das Wasser. ---- */
function room3dSkyTexture(tod) {
  const W = 1600, H = 1024, HZ = H / 2;
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const g = cv.getContext("2d"), c = (ROOM3D.looks[tod] || ROOM3D.looks.day).sky;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const grad = g.createLinearGradient(0, 0, 0, HZ);
  grad.addColorStop(0, c[0]); grad.addColorStop(0.62, c[1]); grad.addColorStop(1, c[2]);
  g.fillStyle = grad; g.fillRect(0, 0, W, HZ);
  g.fillStyle = c[2]; g.fillRect(0, HZ, W, H - HZ);
  const glow = (x, y, r, color, alpha) => {
    const rg = g.createRadialGradient(x, y, 0, x, y, r);
    rg.addColorStop(0, color); rg.addColorStop(1, "rgba(0,0,0,0)");
    g.globalAlpha = alpha; g.fillStyle = rg; g.fillRect(x - r, y - r, r * 2, r * 2);
  };
  // Haufenwolke: Kreise auf einer flachen Unterkante, in der Mitte höher. Erst der helle Rand
  // (etwas größer, nach oben versetzt), dann der Körper - leicht weichgezeichnet.
  const cloud = (x, y, w, body, rim, alpha) => {
    const n = Math.max(5, Math.round(w / 26)), puffs = [];
    for (let k = 0; k < n; k++) {
      const t = (k + rnd(-0.3, 0.3)) / (n - 1), mid = Math.sin(Math.PI * clamp(t, 0, 1));
      puffs.push([x + (t - 0.5) * w, w * (0.045 + 0.085 * mid) * rnd(0.75, 1.25)]);
    }
    g.save();
    g.beginPath(); g.rect(0, 0, W, y); g.clip();                 // flache Unterkante
    g.filter = "blur(" + Math.max(1.5, w / 140).toFixed(1) + "px)";
    for (const [color, grow, lift] of [[rim, 1.14, 0.25], [body, 1, 0]]) {
      g.globalAlpha = alpha; g.fillStyle = color;
      g.beginPath();
      for (const [px, r] of puffs) { g.moveTo(px + r * grow, y - r * 0.55 - r * lift); g.arc(px, y - r * 0.55 - r * lift, r * grow, 0, 7); }
      g.rect(x - w * 0.5, y - w * 0.035, w, w * 0.04);
      g.fill();
    }
    g.restore();
  };
  if (tod === "night") {
    // Leuchten über dem Horizont und ein schräges Band wie eine Milchstraße
    glow(W * 0.55, HZ, W * 0.6, "#3fd6e6", 0.55);
    glow(W * 0.3, HZ * 0.55, W * 0.35, "#2a7fe0", 0.4);
    for (let i = 0; i < 26; i++) glow(W * (0.15 + i * 0.03) + rnd(-40, 40), HZ * (0.75 - i * 0.027) + rnd(-30, 30), rnd(70, 150), i % 3 ? "#3f8cf0" : "#59d8f0", 0.13);
    // Sterne: sehr viele feine, einige helle mit Schein, wenige mit Strahlen - dichter im Band
    g.globalCompositeOperation = "lighter";
    const star = (x, y, r, a, color) => { g.globalAlpha = a; g.fillStyle = color; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); };
    const colors = ["#ffffff", "#ffffff", "#cfe8ff", "#bfe0ff", "#fff3d6", "#a8f0ff"];
    for (let i = 0; i < 4200; i++) {
      let x = rnd(0, W), y = rnd(0, HZ) * rnd(0.3, 1);
      if (i % 3 === 0) { const t = Math.random(); x = W * (0.12 + t * 0.8) + rnd(-90, 90); y = HZ * (0.8 - t * 0.72) + rnd(-70, 70); }   // im Band
      star(x, y, rnd(0.35, 1.05), rnd(0.25, 0.9), colors[i % colors.length]);
    }
    for (let i = 0; i < 150; i++) {
      const x = rnd(0, W), y = rnd(0, HZ * 0.92), r = rnd(1.0, 1.9), col = colors[i % colors.length];
      glow(x, y, r * 6, col, 0.35); star(x, y, r, 1, "#ffffff");
    }
    for (let i = 0; i < 16; i++) {
      const x = rnd(0, W), y = rnd(0, HZ * 0.8), len = rnd(7, 15);
      glow(x, y, len * 1.6, "#bfeaff", 0.5); star(x, y, 2, 1, "#ffffff");
      g.globalAlpha = 0.8; g.strokeStyle = "#ffffff"; g.lineWidth = 1;
      g.beginPath(); g.moveTo(x - len, y); g.lineTo(x + len, y); g.moveTo(x, y - len); g.lineTo(x, y + len); g.stroke();
    }
    g.globalCompositeOperation = "source-over";
    // Wolken: dunkle Bänke mit türkis beleuchtetem Rand, zum Horizont hin dichter
    for (let i = 0; i < 7; i++) cloud(rnd(0, W), rnd(0.1, 0.5) * HZ, rnd(200, 520), "#0b2060", "#1c4fae", 0.8);
    for (let i = 0; i < 12; i++) cloud(rnd(0, W), rnd(0.58, 0.99) * HZ, rnd(220, 560), "#103487", "#3aa6d6", 0.85);
    glow(W * 0.55, HZ, W * 0.45, "#7fe6f0", 0.3);
  } else {
    const eve = tod === "evening";
    glow(W * 0.6, HZ, W * 0.6, eve ? "#fff0c0" : "#ffffff", eve ? 0.6 : 0.55);
    for (let i = 0; i < 6; i++) cloud(rnd(0, W), rnd(0.12, 0.5) * HZ, rnd(200, 520), eve ? "#e9a79c" : "#f4fbff", eve ? "#ffe6cf" : "#ffffff", 0.85);
    for (let i = 0; i < 10; i++) cloud(rnd(0, W), rnd(0.6, 0.99) * HZ, rnd(220, 560), eve ? "#d08a90" : "#e6f5ff", eve ? "#ffe0b8" : "#ffffff", 0.9);
  }
  g.globalAlpha = 1;
  const tex = new THREE.CanvasTexture(cv);
  tex.encoding = THREE.sRGBEncoding;
  return tex;
}

/* ---- Wasser: Lichtnetz wie am Grund von flachem Wasser. Eine nahtlose Kachel aus hellen,
   unregelmäßigen Maschen (Grenzen zwischen Zufallspunkten); zwei Ebenen davon wandern in
   verschiedene Richtungen und werden auf die Wasserfarbe addiert - so verformt sich das Netz
   ständig, ohne dass etwas berechnet werden muss. ---- */
let room3dGlintCanvas = null;
function room3dGlintTexture() {
  if (!room3dGlintCanvas) {
    const S = 256, N = 22, pts = [];
    for (let i = 0; i < N; i++) pts.push([Math.random(), Math.random()]);
    const cv = document.createElement("canvas");
    cv.width = cv.height = S;
    const g = cv.getContext("2d"), img = g.createImageData(S, S);
    const T = Math.PI * 2;
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      // Koordinaten leicht verbiegen (ganze Wellen pro Kachel -> bleibt nahtlos): gebogene statt gerader Maschen
      const u0 = x / S, v0 = y / S;
      const u = u0 + 0.028 * Math.sin(T * (2 * v0 + 0.3)) + 0.014 * Math.sin(T * (5 * v0 + 3 * u0));
      const w = v0 + 0.028 * Math.sin(T * (2 * u0 + 0.7)) + 0.014 * Math.sin(T * (4 * u0 - 3 * v0));
      let d1 = 9, d2 = 9;
      for (const p of pts) {
        let dx = Math.abs(u - p[0]) % 1, dy = Math.abs(w - p[1]) % 1;
        if (dx > 0.5) dx = 1 - dx;                              // über den Rand hinweg messen -> nahtlos
        if (dy > 0.5) dy = 1 - dy;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) d2 = d;
      }
      const e = d2 - d1;                                        // 0 genau auf der Grenze zwischen zwei Maschen
      const line = Math.max(0, 1 - e / 0.013), halo = Math.max(0, 1 - e / 0.07);
      // nicht jede Linie gleich hell: großflächig mal kräftiger, mal fast weg
      const vary = 0.55 + 0.45 * Math.sin(T * (u0 + 2 * v0)) * Math.sin(T * (3 * u0 - v0) + 1.3);
      const v = Math.min(1, (line * line * 0.9 + halo * halo * 0.16) * (0.35 + 0.65 * vary));
      const i = (y * S + x) * 4;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v * 255; img.data[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    room3dGlintCanvas = cv;
  }
  const tex = new THREE.CanvasTexture(room3dGlintCanvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = room3d.renderer.capabilities.getMaxAnisotropy();
  return tex;
}

/** Tageszeit aus room.js übernehmen: Himmel, Wasserfarbe, Färbung des Raums. */
function room3dApply() {
  if (!room3d.ready) return;
  const tod = typeof currentDaytime === "function" ? currentDaytime() : "day";
  if (tod === room3d.tod) return;
  room3d.tod = tod;
  const look = ROOM3D.looks[tod] || ROOM3D.looks.day;
  if (room3d.scene.background) room3d.scene.background.dispose();
  room3d.scene.background = room3dSkyTexture(tod);
  // Wasser läuft zum Horizont in dessen Farbe aus (Dunst)
  room3d.scene.fog = new THREE.Fog(new THREE.Color(look.sky[2]).convertSRGBToLinear(), 10, 70);
  if (room3d.water) room3d.water.material.color.set(look.water).convertSRGBToLinear();
  applyRoom3dGlint();
  const tint = new THREE.Color(look.tint).convertSRGBToLinear();
  for (const m of room3d.materials) m.color.copy(m.userData.baseColor).multiply(tint);
  room3d.dirty = true;
}

/* ---- Lichtnetz auf dem Wasser: Stärke, Maschengröße (Tempo wirkt in updateRoom3d) ---- */
function applyRoom3dGlint() {
  if (!room3d.ready) return;
  const look = ROOM3D.looks[room3d.tod] || ROOM3D.looks.day, G = room3d.glint, W = ROOM3D.water;
  room3d.glints.forEach((m, i) => {
    m.material.color.set(look.glint).convertSRGBToLinear().multiplyScalar(look.glintPower * G.power);
    m.visible = G.power > 0.001;
    const n = 2 * W.glint / (W.tile[i] * Math.max(G.size, 0.05));
    m.material.map.repeat.set(n, n);
  });
  room3d.dirty = true;
}
function setRoom3dGlint(glint, save = true) {
  for (const k of Object.keys(ROOM3D.glint)) if (glint && isFinite(glint[k])) room3d.glint[k] = +glint[k];
  room3d.glintCustom = Object.keys(ROOM3D.glint).some(k => Math.abs(room3d.glint[k] - ROOM3D.glint[k]) > 1e-6);
  applyRoom3dGlint();
  if (save && typeof saveRoom === "function") saveRoom();
  if (typeof updateRoom3dPanel === "function") updateRoom3dPanel();
}
function getRoom3dGlint() { return Object.assign({}, room3d.glint); }
function savedRoom3dGlint() { return room3d.glintCustom ? getRoom3dGlint() : null; }

/* ---- Lage des Raums ---- */
function applyRoom3dPlace() {
  if (!room3d.ready) return;
  const p = room3d.place;
  // Verschoben wird der Raum (inner), gedreht um den Platz der Figur (pivot) - so bleibt beim
  // Drehen stehen, wo sie steht, und nur die Blickrichtung in den Raum ändert sich.
  room3d.inner.position.set(p.x, 0, p.z);
  room3d.pivot.scale.setScalar(p.scale);
  room3d.pivot.position.y = p.y;
  room3d.pivot.rotation.y = -THREE.MathUtils.degToRad(p.rot);   // größerer Wert = Raum dreht im Uhrzeigersinn (von oben)
  if (room3d.water) room3d.water.position.y = p.water;
  room3d.glints.forEach((m, i) => { m.position.y = p.water + 0.004 * (i + 1); });
  room3d.dirty = true;
}
function setRoom3dPlace(place, save = true) {
  for (const k of Object.keys(ROOM3D.place)) if (place && isFinite(place[k])) room3d.place[k] = +place[k];
  room3d.custom = Object.keys(ROOM3D.place).some(k => Math.abs(room3d.place[k] - ROOM3D.place[k]) > 1e-6);
  applyRoom3dPlace();
  if (save && typeof saveRoom === "function") saveRoom();
  if (typeof updateRoom3dPanel === "function") updateRoom3dPanel();
}
function getRoom3dPlace() { return Object.assign({}, room3d.place); }
/** Nur eine selbst eingestellte Lage wird gespeichert - sonst gelten geänderte Vorgaben sofort. */
function savedRoom3dPlace() { return room3d.custom ? getRoom3dPlace() : null; }

/* ---- Laden ---- */
function room3dPrepare(model) {
  model.traverse(o => {
    if (!o.isMesh) return;
    o.frustumCulled = false;
    const mats = (Array.isArray(o.material) ? o.material : [o.material]).map(m => {
      if (m.map) { m.map.encoding = THREE.sRGBEncoding; m.map.anisotropy = room3d.renderer.capabilities.getMaxAnisotropy(); }
      if (!ROOM3D.unlit) return m;
      const basic = new THREE.MeshBasicMaterial({
        name: m.name, map: m.map || null, color: m.color ? m.color.clone() : new THREE.Color(0xffffff),
        transparent: m.transparent, opacity: m.opacity, alphaTest: m.alphaTest, side: m.side,
        vertexColors: m.vertexColors, depthWrite: m.depthWrite, fog: false
      });
      basic.userData.baseColor = basic.color.clone();          // Tageszeit färbt darauf (room3dApply)
      room3d.materials.push(basic);
      return basic;
    });
    o.material = Array.isArray(o.material) ? mats : mats[0];
  });
  // Ausgeblendete Teile (der Loader entfernt Punkte aus Namen: "Cube.141" -> "Cube141")
  const hidden = new Set(ROOM3D.hide.map(n => THREE.PropertyBinding.sanitizeNodeName(n)));
  model.traverse(o => { if (hidden.has(o.name)) o.visible = false; });
  // Auf Raumhöhe skalieren, auf den Boden stellen und mittig ausrichten
  // (setFromObject zählt unsichtbare Teile mit - deshalb selbst über die sichtbaren Meshes gehen)
  const measure = () => {
    const b = new THREE.Box3();
    model.updateMatrixWorld(true);
    model.traverse(o => {
      let shown = o.isMesh;
      for (let n = o; n && shown; n = n.parent) shown = n.visible;
      if (shown) b.expandByObject(o);
    });
    return b;
  };
  let box = measure();
  const size = box.getSize(new THREE.Vector3());
  if (size.y > 0) { model.scale.multiplyScalar(ROOM3D.height / size.y); box = measure(); }
  const c = box.getCenter(new THREE.Vector3());
  model.position.x -= c.x; model.position.z -= c.z; model.position.y -= box.min.y;
  console.log("3D-Raum: " + room3d.file + ", Größe (m): " + box.getSize(new THREE.Vector3()).toArray().map(v => v.toFixed(1)).join(" x "));
}

function room3dStart(gltf) {
  const canvas = document.createElement("canvas");
  canvas.id = "room3d";
  document.body.insertBefore(canvas, document.body.firstChild);
  room3d.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "high-performance" });
  room3d.renderer.outputEncoding = THREE.sRGBEncoding;
  room3d.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  room3d.renderer.setSize(window.innerWidth, window.innerHeight, false);
  room3d.scene = new THREE.Scene();
  room3d.camera = new THREE.PerspectiveCamera(30, 1, 0.1, 500);
  if (!ROOM3D.unlit) {
    room3d.scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const sun = new THREE.DirectionalLight(0xffffff, 0.7);
    sun.position.set(2, 5, 3);
    room3d.scene.add(sun);
  }
  room3d.pivot = new THREE.Group();
  room3d.inner = new THREE.Group();
  room3d.scene.add(room3d.pivot);
  room3d.pivot.add(room3d.inner);
  room3dPrepare(gltf.scene);
  room3d.inner.add(gltf.scene);
  if (ROOM3D.water.enabled) {
    const W = ROOM3D.water;
    // Wasserfläche bis zum Horizont ...
    room3d.water = new THREE.Mesh(new THREE.PlaneGeometry(W.size, W.size), new THREE.MeshBasicMaterial({ depthWrite: false }));
    room3d.water.rotation.x = -Math.PI / 2;
    room3d.water.renderOrder = 5;
    room3d.scene.add(room3d.water);
    // ... und darauf zwei Ebenen Lichtnetz: rund um die Figur, nach außen ausgeblendet (Eckfarben)
    W.tile.forEach((tile, i) => {
      const geo = new THREE.CircleGeometry(W.glint, 40);
      const col = new Float32Array(geo.attributes.position.count * 3);   // Mitte weiß, Rand schwarz
      col[0] = col[1] = col[2] = 1;
      geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
      const map = room3dGlintTexture();
      map.repeat.set(2 * W.glint / tile, 2 * W.glint / tile);
      map.rotation = i * 1.1;
      const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
        map, vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
      mesh.rotation.x = -Math.PI / 2;
      mesh.renderOrder = 6 + i;
      room3d.scene.add(mesh);
      room3d.glints.push(mesh);
    });
  }
  room3d.ready = true;
  document.body.classList.add("room-3d");        // viewer.css blendet den gezeichneten Raum aus
  window.addEventListener("resize", () => {
    room3d.renderer.setSize(window.innerWidth, window.innerHeight, false);
    room3d.dirty = true;
  });
  applyRoom3dPlace();
  room3dApply();
  if (typeof updateRoom3dPanel === "function") updateRoom3dPanel();
}

(function loadRoom3d() {
  if (!ROOM3D.enabled || STAGE.background) return;
  const wanted = new URLSearchParams(location.search).get("room");       // zum Testen: viewer.html?room=models/x.glb
  const files = wanted ? [wanted] : ROOM3D.files.slice();
  const next = () => {
    const file = files.shift();
    if (!file) { console.log("3D-Raum: keine Datei gefunden (" + ROOM3D.files.join(", ") + ") - gezeichneter Raum bleibt"); return; }
    // Erst nachsehen, ob es die Datei gibt - sonst meldet der Loader für jede fehlende einen Fehler
    fetch(file, { method: "HEAD" }).then(r => {
      if (!r.ok) return next();
      new THREE.GLTFLoader().load(file, gltf => { room3d.file = file; room3dStart(gltf); },
        undefined, e => { console.warn("3D-Raum: " + file + " ließ sich nicht laden", e); next(); });
    }).catch(next);
  };
  next();
})();

/** Pro Frame (main.js): Kamera der Figur übernehmen; zeichnen nur bei Bedarf. */
function updateRoom3d(dt) {
  if (!room3d.ready || !camera) return;
  if (document.body.classList.contains("view-popup") && stageState.narrow) return;   // durchsichtiges Popup: kein Raum
  const cam = room3d.camera;
  cam.position.copy(camera.position);
  cam.quaternion.copy(camera.quaternion);
  const key = cam.position.toArray().concat(cam.quaternion.toArray(), camera.fov, camera.aspect).map(v => v.toFixed(4)).join();
  if (key !== room3d.camKey) {
    room3d.camKey = key;
    cam.fov = camera.fov; cam.aspect = camera.aspect;
    cam.updateProjectionMatrix();
    room3d.dirty = true;
  }
  const now = performance.now() / 1000, W = ROOM3D.water;
  room3d.flow = (room3d.flow || 0) + dt * W.speed * room3d.glint.speed;
  const moving = room3d.glint.speed > 0 && room3d.glint.power > 0.001;
  const waterDue = room3d.water && moving && W.fps > 0 && now - room3d.lastDraw >= 1 / W.fps;
  if (!room3d.dirty && !waterDue) return;
  room3d.glints.forEach((m, i) => {                 // die beiden Netze wandern gegeneinander
    const o = m.material.map.offset, dir = i ? -1 : 1;
    // Weg statt Zeit * Tempo: sonst springt das Netz, wenn man am Tempo-Regler zieht
    o.x = (room3d.flow * dir) % 1; o.y = (room3d.flow * (0.7 + 0.5 * i)) % 1;
  });
  room3d.renderer.render(room3d.scene, cam);
  room3d.lastDraw = now;
  room3d.dirty = false;
}

/* ---- Panel-Abschnitt "🧊 3D-Raum": Lage und Lichtnetz einstellen ---- */
let updateRoom3dPanel = null;
function buildRoom3dSection(panel) {
  if (!ROOM3D.enabled || STAGE.background) return;
  panel.appendChild(makeHeading("🧊 3D-Raum"));
  const status = document.createElement("div");
  status.style.cssText = "font-size:1.2vh;opacity:0.7;margin:0 0 0.6vh 0;";
  panel.appendChild(status);
  const sliders = [];
  /** Eine Reihe Regler. get() liefert die Werte, set({key: wert}, speichern) übernimmt einen. */
  const addSliders = (defs, get, set) => {
    for (const [key, label, min, max, step] of defs) {
      const row = document.createElement("label");
      row.style.cssText = "display:flex;align-items:center;font-size:1.3vh;margin:0.2vh 0;";
      const text = document.createElement("span");
      text.textContent = label;
      text.style.cssText = "flex:0 0 38%;";
      const input = document.createElement("input");
      input.type = "range"; input.min = min; input.max = max; input.step = step;
      input.style.cssText = "flex:1 1 auto;min-width:0;margin:0 0.4vw;";
      const out = document.createElement("span");
      out.style.cssText = "flex:0 0 3.4em;text-align:right;font-variant-numeric:tabular-nums;";
      input.oninput = () => { out.textContent = (+input.value).toFixed(2); set({ [key]: +input.value }, false); };
      input.onchange = () => { if (typeof saveRoom === "function") saveRoom(); };     // speichern erst beim Loslassen
      row.append(text, input, out);
      panel.appendChild(row);
      sliders.push({ key, input, out, get });
    }
  };
  const note = text => { const d = document.createElement("div"); d.textContent = text; d.style.cssText = "font-size:1.3vh;font-weight:600;margin:0.8vh 0 0.2vh 0;"; panel.appendChild(d); };
  const button = (text, onclick) => { const b = document.createElement("button"); b.textContent = text; b.onclick = onclick; panel.appendChild(b); };

  note("Lage");
  addSliders([["scale", "Größe", 0.1, 4, 0.01], ["x", "links / rechts", -12, 12, 0.05], ["z", "vor / zurück", -12, 12, 0.05],
              ["y", "Höhe", -3, 3, 0.01], ["rot", "Drehung °", -180, 180, 1], ["water", "Wasserhöhe", -0.5, 0.5, 0.005]],
             () => room3d.place, setRoom3dPlace);
  button("↺ Lage zurücksetzen", () => setRoom3dPlace(ROOM3D.place));

  note("Lichtnetz auf dem Wasser");
  addSliders([["power", "Stärke", 0, 3, 0.05], ["size", "Maschengröße", 0.3, 3, 0.05], ["speed", "Tempo", 0, 4, 0.05]],
             () => room3d.glint, setRoom3dGlint);
  button("↺ Lichtnetz zurücksetzen", () => setRoom3dGlint(ROOM3D.glint));

  updateRoom3dPanel = () => {
    status.textContent = room3d.ready ? "Geladen: " + room3d.file
      : "Kein Modell gefunden. Datei nach models/room.glb legen (oder models/room/scene.gltf) und neu öffnen.";
    for (const s of sliders) { const v = s.get()[s.key]; s.input.value = v; s.out.textContent = (+v).toFixed(2); }
  };
  updateRoom3dPanel();
}
