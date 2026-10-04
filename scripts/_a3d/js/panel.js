/* panel.js - Seitenpanel: Darstellung, Animationen, Umschalten
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* -------------------------
   Animations-Panel: alle Clips des Modells anzeigen & abspielen
   ------------------------- */
let animClips = {};      // name -> THREE.AnimationClip
let currentAction = null;
let currentAnimName = null;

document.getElementById("brightness").addEventListener("input", function(){
  renderStyle.brightness = parseFloat(this.value);
  applyLighting();
});

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
    ["🎥 Kamera frei (Debug)", "debugCamera", () => setDebugCamera(renderStyle.debugCamera)]
  ];
  toggles.forEach(([label, key, onChange]) => {
    const b = document.createElement("button");
    const update = () => {
      b.textContent = label + ": " + (renderStyle[key] ? "an" : "aus");
      b.classList.toggle("active", renderStyle[key]);
    };
    b.onclick = () => { renderStyle[key] = !renderStyle[key]; update(); onChange(); };
    update();
    add(b);
  });
  panel.style.display = "block";
}

const IDLE_NAME = "🌿 Natürliches Idle";
const WALK_PLACE_NAME = "🚶 Laufen (auf der Stelle)";
const WALK_AROUND_NAME = "🚶 Herumlaufen";

function setupAnimationPanel(animations) {
  const panel = document.getElementById("anim-panel");
  let skipped = 0;
  const idleBtn = document.createElement("button");
  idleBtn.textContent = IDLE_NAME + " (prozedural)";
  idleBtn.dataset.anim = IDLE_NAME;
  idleBtn.onclick = () => playAnimation(IDLE_NAME);
  panel.appendChild(idleBtn);
  for (const name of [WALK_PLACE_NAME, WALK_AROUND_NAME]) {
    const b = document.createElement("button");
    b.textContent = name;
    b.dataset.anim = name;
    b.onclick = () => playAnimation(name);
    panel.appendChild(b);
  }
  animations.forEach((clip) => {
    // MMD-Konvertierungs-Reste: Einzelknochen-Physik-Actions mit kaputter
    // Dauer (NaN/0) — nicht abspielbar, daher ausblenden
    if (!isFinite(clip.duration) || clip.duration <= 0) { skipped++; return; }
    animClips[clip.name] = clip;
    console.log("Clip '" + clip.name + "': " + clip.duration.toFixed(2) + "s, " +
      clip.tracks.length + " Tracks");
    const btn = document.createElement("button");
    btn.textContent = clip.name + "  (" + clip.duration.toFixed(1) + "s)";
    btn.dataset.anim = clip.name;
    btn.onclick = () => playAnimation(clip.name);
    panel.appendChild(btn);
  });
  const stopBtn = document.createElement("button");
  stopBtn.textContent = "⏹ Stopp (Ruhepose)";
  stopBtn.onclick = stopAnimation;
  panel.appendChild(stopBtn);
  if (skipped > 0) {
    const note = document.createElement("div");
    note.style.cssText = "font-size:1.2vh;opacity:0.6;margin:0.5vh 0;";
    note.textContent = skipped + " Physik-Einzelclips ausgeblendet (MMD-Reste, nicht abspielbar)";
    panel.appendChild(note);
  }
  buildGestureSection(panel);
  panel.style.display = "block";
  console.log("Animations-Panel:", animations.map(a => a.name));
}

function markActiveAnimation(name) {
  document.querySelectorAll("#anim-panel button[data-anim]").forEach(b =>
    b.classList.toggle("active", b.dataset.anim === name));
}

function playAnimation(name) {
  const walkModes = { [IDLE_NAME]: "none", [WALK_PLACE_NAME]: "place", [WALK_AROUND_NAME]: "around" };
  if (name in walkModes) {
    // Prozedural: laufenden Clip ausblenden, Idle (und ggf. Laufen) weich einblenden
    if (currentAction) currentAction.fadeOut(0.4);
    currentAction = null;
    currentAnimName = name;
    idleEnabled = true;
    const mode = walkModes[name];
    if (mode === "around" && walk.mode !== "around") {
      // Auf der Ellipse dort einsteigen, wo das Modell gerade steht
      const { rx, rz } = WALK.path, pos = modelRoot.position;
      walk.a = Math.atan2(pos.x / rx, (pos.z + rz) / rz);
    }
    walk.mode = mode;
    markActiveAnimation(name);
    return;
  }
  walk.mode = "none";
  const clip = animClips[name];
  if (!clip || !mixer) return;
  idleEnabled = false;
  const next = mixer.clipAction(clip);
  if (currentAction && currentAction !== next) {
    // weich überblenden statt hart umschalten
    next.reset();
    next.play();
    currentAction.crossFadeTo(next, 0.35, false);
  } else {
    next.reset().play();
  }
  currentAction = next;
  currentAnimName = name;
  // Diagnose: läuft die Animation wirklich? (nach 1s Zeit und Gewicht prüfen)
  setTimeout(() => {
    if (currentAction && currentAnimName === name) {
      console.log("Diagnose '" + name + "': time=" + currentAction.time.toFixed(2) +
        " weight=" + currentAction.getEffectiveWeight().toFixed(2) +
        " running=" + currentAction.isRunning());
    }
  }, 1000);
  markActiveAnimation(name);
}

function stopAnimation() {
  if (mixer) mixer.stopAllAction();
  currentAction = null;
  currentAnimName = null;
  idleEnabled = false;
  walk.mode = "none";
  markActiveAnimation(null);
}
