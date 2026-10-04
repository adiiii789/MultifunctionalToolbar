/* toon-shader.js - Anime-/Toon-Shader, Materialien, Licht
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich. */

/* =========================================================================
   Anime-/Toon-Shader
   -------------------------------------------------------------------------
   - Zwei harte Lichtstufen (Licht/Schatten) statt weichem PBR-Verlauf
   - Getönte Schatten je Materialgruppe (Haut warm, Haare/Stoff kühl)
   - Leichtes Rim-Light am Silhouettenrand
   - Konturlinien über THREE.OutlineEffect (Inverted Hull, kann Skinning
     und Morph-Targets, folgt also Animationen und Mimik)
   Die Werte pro Gruppe stehen in TOON_STYLES und lassen sich frei anpassen.
   Farben werden als sRGB-Hex angegeben (wie in einem Malprogramm).
   ========================================================================= */
const TOON_STYLES = {
  // saturation: 1 = Originalfarbe, >1 = kräftiger (wirkt v. a. auf das Türkis)
  //           Schattenfarbe  Schwelle  Weichheit  Rim   Sättigung   Kontur: Farbe, Dicke (0 = keine)
  face:    { shadow: 0xe9c4c4, threshold: -0.30, softness: 0.06, rim: 0.04, saturation: 1.05, line: 0x6b3a3a, width: 0.0028 },
  skin:    { shadow: 0xd59a9e, threshold:  0.05, softness: 0.03, rim: 0.08, saturation: 1.05, line: 0x6b3a3a, width: 0.0040 },
  hair:    { shadow: 0x5b98b3, threshold:  0.10, softness: 0.03, rim: 0.10, saturation: 1.35, line: 0x163f4a, width: 0.0050 },
  cloth:   { shadow: 0x838aa8, threshold:  0.10, softness: 0.03, rim: 0.06, saturation: 1.25, line: 0x15161f, width: 0.0050 },
  eyes:    { shadow: 0xffffff, threshold: -1.00, softness: 0.00, rim: 0.00, saturation: 1.20, line: 0x000000, width: 0 },
  overlay: { shadow: 0xffffff, threshold: -1.00, softness: 0.00, rim: 0.00, saturation: 1.00, line: 0x000000, width: 0 }
};

// Materialname (aus Blender) -> Gruppe. Erste passende Regel gewinnt.
const MATERIAL_RULES = [
  [/gesicht|face/i,                     "face"],
  [/augen|auge|eye|pupill|highlight/i,  "eyes"],
  [/haare schatten|hair.?shadow/i,      "overlay"],
  [/haut|skin|body/i,                   "skin"],
  [/haar|hair|straehn|strähn|zopf/i,    "hair"]
];
const DEFAULT_GROUP = "cloth";

// Diese Gruppen haben weiche Alpha-Kanten und bleiben echt transparent.
const BLENDED_GROUPS = new Set(["eyes", "overlay"]);

// Licht im Anime-Modus: fast alles kommt vom gerichteten Licht, damit die
// Schattenstufe sichtbar wird. Ambient hebt nur die Schatten minimal an.
const LIGHTING = {
  anime:    { ambient: 0.20, dir: 0.80 },   // Summe 1.0 = Texturfarbe 1:1 (nicht überbelichtet)
  standard: { ambient: 1.0,  dir: 0.6 }
};

function srgbColor(hex) {
  return new THREE.Color(hex).convertSRGBToLinear();
}

function groupForMaterial(name) {
  for (const [re, group] of MATERIAL_RULES) if (re.test(name || "")) return group;
  return DEFAULT_GROUP;
}

const TOON_SHADER_PARS = `
uniform vec3 uShadowColor;
uniform float uThreshold;
uniform float uSoftness;
uniform float uRim;
uniform float uSaturation;

// Ersetzt die Standard-Rampe von MeshToonMaterial:
// harter Übergang mit Anti-Aliasing (fwidth) und getöntem Schatten.
vec3 getGradientIrradiance( vec3 normal, vec3 lightDirection ) {
  float d = dot( normal, lightDirection );
  float w = max( fwidth( d ), uSoftness );
  float lit = smoothstep( uThreshold - w, uThreshold + w, d );
  return mix( uShadowColor, vec3( 1.0 ), lit );
}
`;

const TOON_SHADER_RIM = `
{
  // Rim-Light: heller Saum an den Rändern, wo die Fläche von der Kamera wegzeigt
  float facing = clamp( dot( normal, normalize( vViewPosition ) ), 0.0, 1.0 );
  float rim = smoothstep( 0.62, 0.92, 1.0 - facing );
  outgoingLight += diffuseColor.rgb * rim * uRim;
  // Sättigung anheben: Abstand zur Graustufe vergrößern
  float luma = dot( outgoingLight, vec3( 0.2126, 0.7152, 0.0722 ) );
  outgoingLight = max( mix( vec3( luma ), outgoingLight, uSaturation ), 0.0 );
}
#include <output_fragment>
`;

function createToonMaterial(original, group) {
  const style = TOON_STYLES[group];
  const blended = BLENDED_GROUPS.has(group);
  const mat = new THREE.MeshToonMaterial({
    name: original.name + " (Toon)",
    color: original.color ? original.color.clone() : new THREE.Color(0xffffff),
    map: original.map || null,
    side: original.side,
    transparent: blended,
    // Opake Teile: Alpha nur als Schnittkante -> keine Sortierfehler bei Haaren
    alphaTest: blended ? 0.01 : 0.5,
    depthWrite: !blended
  });
  const uniforms = {
    uShadowColor: { value: srgbColor(style.shadow) },
    uThreshold:   { value: style.threshold },
    uSoftness:    { value: style.softness },
    uRim:         { value: style.rim },
    uSaturation:  { value: style.saturation }
  };
  mat.userData.toonUniforms = uniforms;
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <gradientmap_pars_fragment>", TOON_SHADER_PARS)
      .replace("#include <output_fragment>", TOON_SHADER_RIM);
  };
  mat.customProgramCacheKey = () => "anime-toon-v2";

  mat.userData.outlineParameters = {
    thickness: style.width,
    color: srgbColor(style.line).toArray(),
    alpha: 1.0,
    visible: style.width > 0 && !blended,
    keepAlive: true
  };
  return mat;
}

/* Merkt sich Original- und Toon-Material jedes Meshes, damit man live
   umschalten kann (Panel: "Anime-Shader"). */
const styledMeshes = [];
const toonCache = new Map(); // Original-Material -> Toon-Material

function prepareMeshMaterials(mesh) {
  const original = mesh.material;
  if (!original || Array.isArray(original)) return;
  const group = groupForMaterial(original.name);

  // Standard-Modus aufräumen: Die Konvertierung hat jedes Material auf
  // "BLEND" gestellt und MMD-Sphere-Maps in den Metallic/Roughness-Slot
  // gelegt -> Sortierfehler und Plastik-Glanz. Beides hier entschärfen.
  if (!BLENDED_GROUPS.has(group)) {
    original.transparent = false;
    original.alphaTest = 0.5;
  }
  original.depthWrite = !BLENDED_GROUPS.has(group);
  original.metalnessMap = null;
  original.roughnessMap = null;
  original.metalness = 0;
  original.roughness = 1;
  original.needsUpdate = true;

  if (!toonCache.has(original)) toonCache.set(original, createToonMaterial(original, group));
  mesh.userData.materials = { standard: original, anime: toonCache.get(original) };
  mesh.userData.toonGroup = group;
  // Transparente Teile (Pupillen, Highlights, Haarschatten) nach den opaken zeichnen
  if (BLENDED_GROUPS.has(group)) mesh.renderOrder = 1;
  styledMeshes.push(mesh);
}

const renderStyle = { anime: true, outline: false, physics: true, debugCamera: false, brightness: 1.0 };

function applyRenderStyle() {
  styledMeshes.forEach(m => {
    m.material = renderStyle.anime ? m.userData.materials.anime : m.userData.materials.standard;
  });
  applyLighting();
}

function applyLighting() {
  if (!window.__lights) return;
  const l = renderStyle.anime ? LIGHTING.anime : LIGHTING.standard;
  window.__lights.ambient.intensity = l.ambient * renderStyle.brightness;
  window.__lights.dir.intensity = l.dir * renderStyle.brightness;
}
