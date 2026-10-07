/* clips.js - Animationen aus der GLB (z. B. in Blender erstellt): Kategorien,
   Abspielen, Überblenden, Rückkehr ins Idle.
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Namensschema der Actions in Blender:  <Kategorie>_<Name>
     "Begruessung_Winken"       -> Kategorie "Begruessung", Name "Winken"
     "Tanz_Kurz_Drehen"         -> Kategorie "Tanz",        Name "Kurz Drehen"
     "Strecken"  (ohne "_")     -> Kategorie "Sonstige"
   Getrennt wird am ERSTEN Unterstrich, weitere werden im Panel zu Leerzeichen.

   Von außen nutzbar:
     playClip("Begruessung_Winken")                 - mit Panel-Einstellung (Loop an/aus)
     playClip("Begruessung_Winken", { loop: false }) - einmal, danach zurück ins Idle
     stopClip()                                      - ausblenden, zurück ins Idle
     getClipCategories()  -> { "Begruessung": ["Begruessung_Winken", ...], ... } */

const CLIPS = {
  separator: "_",          // trennt Kategorie und Name
  otherCategory: "Sonstige",
  fade: 0.35,              // Überblendzeit in s (Clip <-> Clip, Clip <-> Idle)
  loop: true               // Standard für playClip ohne Angabe (im Panel umschaltbar)
};

let mixer = null;
const clipLibrary = {
  clips: {},               // voller Name -> { clip, category, label }
  categories: {}           // Kategorie -> [volle Namen] (Reihenfolge wie in der Datei)
};
let currentAction = null;
let currentClipName = null;
let clipWeight = 0;        // 0..1, geglättet: wie stark gerade ein Clip läuft

/** "Kategorie_Name_mit_Rest" -> { category: "Kategorie", label: "Name mit Rest" } */
function parseClipName(name) {
  const i = name.indexOf(CLIPS.separator);
  if (i <= 0 || i >= name.length - 1) return { category: CLIPS.otherCategory, label: name };
  return { category: name.slice(0, i), label: name.slice(i + 1).split(CLIPS.separator).join(" ") };
}

/** Beim Laden: Mixer anlegen und alle abspielbaren Clips einsortieren.
    Gibt die Zahl der übersprungenen (kaputten) Clips zurück. */
function setupClips(root, animations) {
  mixer = new THREE.AnimationMixer(root);
  mixer.addEventListener("finished", (e) => {
    // Einmal-Clip ist durch -> weich zurück ins Idle
    if (e.action === currentAction) playAnimation(IDLE_NAME);
  });
  let skipped = 0;
  for (const clip of animations) {
    // MMD-Konvertierungs-Reste: Einzelknochen-Actions mit kaputter Dauer (NaN/0)
    if (!isFinite(clip.duration) || clip.duration <= 0) { skipped++; continue; }
    const { category, label } = parseClipName(clip.name);
    clipLibrary.clips[clip.name] = { clip, category, label };
    (clipLibrary.categories[category] = clipLibrary.categories[category] || []).push(clip.name);
  }
  console.log("Clips:", getClipCategories(), skipped ? "(" + skipped + " kaputte übersprungen)" : "");
  return skipped;
}

/** Kategorien -> Clipnamen; "Sonstige" steht immer am Ende. */
function getClipCategories() {
  const out = {};
  const cats = Object.keys(clipLibrary.categories);
  for (const c of cats.filter(c => c !== CLIPS.otherCategory).concat(cats.filter(c => c === CLIPS.otherCategory)))
    out[c] = clipLibrary.categories[c].slice();
  return out;
}

/** Clip abspielen. opts.loop: true = wiederholen, false = einmal, dann zurück ins Idle. */
function playClip(name, opts = {}) {
  const entry = clipLibrary.clips[name];
  if (!entry || !mixer) { console.warn("Clip nicht gefunden: " + name); return false; }
  const loop = opts.loop !== undefined ? opts.loop : CLIPS.loop;
  const fade = opts.fade !== undefined ? opts.fade : CLIPS.fade;

  const next = mixer.clipAction(entry.clip);
  next.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
  next.clampWhenFinished = !loop;          // Einmal-Clip hält den letzten Frame, bis er ausgeblendet ist
  next.reset();
  next.play();
  if (currentAction && currentAction !== next) currentAction.crossFadeTo(next, fade, false);
  else if (!currentAction) next.fadeIn(fade);

  currentAction = next;
  currentClipName = name;
  idleEnabled = false;                     // Idle blendet aus (Mausblick bleibt aktiv)
  walk.mode = "none";
  cancelWalkTarget();                      // Clip spielt dort, wo die Figur gerade steht
  markActiveAnimation(name);
  return true;
}

/** Laufenden Clip ausblenden (danach entscheidet der Aufrufer, was kommt). */
function stopClip(fade = CLIPS.fade) {
  if (currentAction) currentAction.fadeOut(fade);
  currentAction = null;
  currentClipName = null;
}

/** Pro Frame (aus updatePose, direkt nach der Ruhepose). */
function updateClips(dt) {
  if (mixer) mixer.update(dt);
  clipWeight = damp(clipWeight, currentAction ? 1 : 0, 1 / Math.max(CLIPS.fade, 0.05) * 2.5, dt);
}
