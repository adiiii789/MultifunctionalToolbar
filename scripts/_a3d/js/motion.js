/* motion.js - Easing, Keyframes, Feder-Glättung und versetzte Einsätze
   Teil des 3D-Assistenten (siehe viewer.html für die Ladereihenfolge).
   Alle Dateien sind klassische Skripte und teilen sich den globalen Bereich.

   Warum: Gleichmäßige (lineare/sinusförmige) Bewegungen wirken mechanisch.
   Natürlich wirken Bewegungen, die langsam anfangen, beschleunigen, leicht
   über das Ziel hinausgehen und sanft auslaufen - und bei denen nicht alle
   Gelenke gleichzeitig starten (Schulter führt, Hand folgt). */

/* =========================================================================
   Easing-Kurven: x 0..1 -> 0..1
   ========================================================================= */
const EASE = {
  linear:    x => x,
  in:        x => x * x * x,                                  // langsam los
  out:       x => 1 - Math.pow(1 - x, 3),                     // sanft auslaufen
  inOut:     x => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2,
  inOutSine: x => -(Math.cos(Math.PI * x) - 1) / 2,
  // leicht übers Ziel hinaus und zurück ("Schwung"); s = Stärke
  outBack:   x => { const s = 1.4, c = s + 1; return 1 + c * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2); },
  // kurz ausholen (Gegenbewegung), dann los
  inBack:    x => { const s = 1.4, c = s + 1; return c * x * x * x - s * x * x; },
  outQuad:   x => 1 - (1 - x) * (1 - x),
  inQuad:    x => x * x
};

/** Keyframes auswerten. frames = [[t, wert], [t, wert, "ease"], ...]
    t aufsteigend 0..1; "ease" gilt für den Weg ZU diesem Keyframe (Standard inOut). */
function keys(t, frames) {
  if (t <= frames[0][0]) return frames[0][1];
  for (let i = 1; i < frames.length; i++) {
    const [t1, v1, ease] = frames[i];
    if (t <= t1) {
      const [t0, v0] = frames[i - 1];
      const x = (t - t0) / Math.max(t1 - t0, 1e-6);
      return v0 + (v1 - v0) * (EASE[ease || "inOut"])(x);
    }
  }
  return frames[frames.length - 1][1];
}

/** Hüllkurve einer Geste mit eigener Ein-/Ausblend-Kurve.
    t = Fortschritt 0..1, dur = Dauer in s, delay = Verzögerung in s
    (für versetzte Gelenke: Schulter 0, Ellbogen 0.05, Hand 0.1 ...). */
function gestureEnvelope(t, dur, { delay = 0, attack = 0.35, release = 0.45,
                                   easeIn = "outBack", easeOut = "inOut" } = {}) {
  const s = t * dur - delay;                       // Sekunden seit (verzögertem) Start
  const end = dur - release;
  if (s <= 0) return 0;
  if (s < attack) return EASE[easeIn](s / attack);
  if (t * dur < end) return 1;
  return 1 - EASE[easeOut](clamp((t * dur - end) / release, 0, 1));
}

/** Kurzer Impuls innerhalb eines Takts (z. B. Klatschen, Betonung):
    schnell hin (easeIn), weich zurück (easeOut). phase 0..1 -> 0..1..0 */
function pulse(phase, peak = 0.3) {
  phase = ((phase % 1) + 1) % 1;
  return phase < peak ? EASE.in(phase / peak) : 1 - EASE.out((phase - peak) / (1 - peak));
}

/* =========================================================================
   Feder-Glättung (kritisch gedämpft): startet weich, beschleunigt, bremst ab.
   Im Gegensatz zu damp() (springt sofort los) wirkt das wie echte Muskeln.
   ========================================================================= */
/** state = {v: Geschwindigkeit}; smoothTime ~ Zeit bis zum Ziel in s. */
function smoothDamp(current, target, state, smoothTime, dt) {
  const omega = 2 / Math.max(smoothTime, 1e-4);
  const x = omega * dt;
  const exp = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
  const change = current - target;
  const temp = (state.v + omega * change) * dt;
  state.v = (state.v - omega * temp) * exp;
  return target + (change + temp) * exp;
}
