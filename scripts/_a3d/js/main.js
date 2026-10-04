/* main.js - Start: Three.js-Setup, Modell laden, Kamera, Render-Schleife
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* -------------------------
   Three.js Setup & Loader
   ------------------------- */
function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.set(0, 0.7, 1.7);

  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    console.log("✅ Renderer erstellt (WebGLRenderer)");
  } catch (e) {
    renderer = new THREE.WebGL1Renderer({ antialias: true, alpha: true });
    console.warn("⚠️ Fallback auf WebGL1Renderer");
  }

  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);     // transparent: dahinter liegt die Bühne (stage.js)
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  document.body.appendChild(renderer.domElement);
  setupDebugCameraControls();
  applyCameraFraming();                    // Figur links, Board rechts frei
  addGroundShadow();

  window.__lights = {};
  const ambientLight = new THREE.AmbientLight(0xffffff, 1.0);
  scene.add(ambientLight);
  window.__lights.ambient = ambientLight;

  // Hauptlicht hängt an der Kamera (schräg von vorne oben), damit das Gesicht
  // aus jedem Blickwinkel sauber beleuchtet ist - typisch für Anime-Look.
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
  directionalLight.position.set(1.2, 1.6, 1.0);
  directionalLight.target.position.set(0, 0, -3);
  camera.add(directionalLight);
  camera.add(directionalLight.target);
  window.__lights.dir = directionalLight;
  applyLighting();

  // Konturlinien (Inverted Hull); Parameter kommen pro Material aus TOON_STYLES
  outlineEffect = new THREE.OutlineEffect(renderer, {
    defaultThickness: 0.003,
    defaultColor: [0, 0, 0],
    defaultAlpha: 1.0,
    defaultKeepAlive: true
  });

  const loader = new THREE.GLTFLoader();
  loader.load("./models/model.glb",
    function (gltf) {
      gltf.scene.traverse((child) => {
        if (child.isMesh) {
          const mat = child.material;
          if (mat && mat.map) {
            mat.map.encoding = THREE.sRGBEncoding;
            mat.map.anisotropy = renderer.capabilities.getMaxAnisotropy();
            mat.map.needsUpdate = true;
          }
          prepareMeshMaterials(child);

          if (child.morphTargetInfluences && child.morphTargetInfluences.length > 0) {
            // Erstellt einen Cache für schnelle Lookup-Indexierung (lowercase -> index)
            child.__morphIndexCache = {};
            for (let key in child.morphTargetDictionary) {
              child.__morphIndexCache[key.toLowerCase()] = child.morphTargetDictionary[key];
            }
            morphMeshes.push(child);
            console.log(`Mesh geladen: ${child.name}, MorphTargets:`, Object.keys(child.morphTargetDictionary));
          }
        }
      });

      scene.add(gltf.scene);
      applyRenderStyle();
      buildStyleSection(document.getElementById("anim-panel"));
      indexBones(gltf.scene);
      document.getElementById("hint").style.display = "none";

      mixer = new THREE.AnimationMixer(gltf.scene);
      setupAnimationPanel(gltf.animations || []);
      playAnimation(IDLE_NAME);   // Standard: natürliches, prozedurales Idle

      console.log("Geladene Animationen:", (gltf.animations || []).map(a => a.name));
    },
    undefined,
    function (error) {
      console.error("❌ Fehler beim Laden:", error);
      document.getElementById("hint").innerHTML =
        "⚠️ Modell nicht gefunden.<br>Bitte <b>model.glb</b> nach " +
        "<code>scripts/_a3d/models/</code> kopieren und das Plugin neu öffnen.";
    }
  );

  scene.add(camera);

  window.addEventListener("resize", () => {
    renderer.setSize(window.innerWidth, window.innerHeight);
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    applyCameraFraming();
  });
}

/* -------------------------
   Animate Loop
   ------------------------- */
const __clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  const __dt = Math.min(__clock.getDelta(), 0.1);
  updatePose(__dt);
  updateGroundShadow();
  updateStageFraming(__dt);           // Figur gleitet bei Layoutwechsel an die neue Stelle

  updateFace(__dt);

  if (renderStyle.anime && renderStyle.outline) outlineEffect.render(scene, camera);
  else renderer.render(scene, camera);
}

/* -------------------------
   Start
   ------------------------- */
init();
animate();
