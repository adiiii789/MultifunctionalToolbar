# 3D-Assistent – Dateiübersicht

Alles liegt in `scripts/_a3d/`. Das Plugin `3D_Assistent.py` steuert nur noch die Popup-Größe (`POPUP_WIDTH`, `POPUP_HEIGHT`).

```
_a3d/
├── viewer.html        Grundgerüst: Panel, Chat, lädt CSS und Skripte
├── css/viewer.css     Aussehen von Panel, Chat, Bühne
├── assets/            Hintergrundbild (stage_background.png – austauschbar)
├── board/             Inhalte fürs Smartboard (start.html = Startseite)
├── vendor/            three.js r147 (lokal, damit es ohne Internet läuft)
├── models/model.glb   das Modell
└── js/
    ├── toon-shader.js Anime-Shader: TOON_STYLES (Farben, Sättigung), Materialgruppen, Licht
    ├── core.js        gemeinsame Variablen (Szene, Kamera, Mixer) und Chat
    ├── pose.js        Rig-Knochen, Helfer (dir, aim, rotate, turnHead), Ablauf pro Frame (updatePose)
    ├── motion.js      EASE, keys(): Easing-Kurven, Keyframes, Feder-Glättung (smoothDamp)
    ├── hands.js       HAND_POSES: Fingerposen (locker, Faust, Zeigen ...), orientPalm()
    ├── idle.js        natürliches Idle: IDLE (Armhaltung, Atmen, Wiegen, Umschauen)
    ├── gestures.js    GESTURE_GROUPS: Gesten + Moderation, Gesten beim Sprechen
    ├── pet.js         PET: Streicheln am Kopf (Augen ><, Kopf neigt sich)
    ├── walk.js        WALK: Laufen auf der Stelle
    ├── stations.js    STATIONS_DEFAULT: Punkte, zu denen die Figur läuft (walkTo)
    ├── clips.js       CLIPS: Blender-Animationen aus der GLB, Kategorien, Überblenden
    ├── physics.js     SPRING_CHAINS + COLLIDERS: Haare, Krawatte, Rock, Ärmel
    ├── voice.js       VOICE: Stimme (lokaler Miku-TTS über das Plugin), Lautstärke, Mund folgt dem Audio
    ├── face.js        LIPSYNC, VISEMES: Lippensync, Blinzeln, Taste M
    ├── expressions.js MORPHS, EXPRESSIONS: Mimik aus Shape Keys (Original- und eigene Namen)
    ├── panel.js       Bedienpanel (Darstellung, Idle/Laufen, Clips nach Kategorie, Mimik, Mausblick)
    ├── stage.js       STAGE: Hintergrund, Board-Fläche, Figur-Position, Mausblick, Debug-Kamera
    └── main.js        Setup, Modell laden, Kamera, Render-Schleife – startet alles
```

## Wo stelle ich was ein?

| Was                              | Datei            | Konstante                    |
|----------------------------------|------------------|------------------------------|
| Schattenfarben, Sättigung, Rim   | toon-shader.js   | `TOON_STYLES`                |
| Helligkeit des Lichts            | toon-shader.js   | `LIGHTING`                   |
| Armhaltung, Atmen, Umschauen     | idle.js          | `IDLE`                       |
| Neue Geste hinzufügen            | gestures.js      | `GESTURE_GROUPS`             |
| Lauftempo, Schwung               | walk.js          | `WALK`                       |
| Haar-/Rock-Steifigkeit           | physics.js       | `SPRING_CHAINS`              |
| Kollision mit dem Körper         | physics.js       | `COLLIDERS`                  |
| Sprechtempo, Mundöffnung         | face.js          | `LIPSYNC`                    |
| Hintergrundbild, Board-Fläche    | stage.js         | `STAGE.background`, `STAGE.board` |
| Position/Größe der Figur         | stage.js         | `STAGE.character`            |
| Wo die Figur geradeaus schaut    | stage.js         | `STAGE.lookCenter` ("screen", "window", {x,y}) |
| Überblendzeit, Loop-Standard     | clips.js         | `CLIPS`                      |
| Aufrechte Haltung / Neigung      | idle.js          | `IDLE.lean`, `IDLE.spine`    |
| Wie stark der Oberkörper beim Blick mitdreht | idle.js | `LOOK_SHARE`, `LOOK_TIME` |
| Ausdrücke (Mimik) anpassen/neu   | expressions.js   | `EXPRESSIONS`                |
| Shape-Key-Namen zuordnen         | expressions.js   | `MORPHS`                     |
| Fingerposen                      | hands.js         | `HAND_POSES`                 |
| Easing-Kurven                    | motion.js        | `EASE`                       |

## Eigene Animationen aus Blender

1. Pro Animation eine eigene **Action** anlegen und ihr einen **Fake User** geben.
2. Benennen nach `<Kategorie>_<Name>`, z. B. `Begruessung_Winken`. Getrennt wird
   am ersten `_`, ohne `_` landet der Clip unter „Sonstige“.
3. Export als glTF Binary nach `models/model.glb`, Animation an, Modus „Actions“.
4. Knochen-, Material- und Shape-Key-Namen sowie die Ruhepose nicht verändern.
5. Haare, Pony, Krawatte, Rock und Ärmel nicht keyen – das macht die Physik.
   Mimik nicht im Clip animieren, sondern per `setExpression()` / `setMood()`.

Während ein Clip läuft, sind das Idle, die lockere Fingerpose und das
Rock-Ausweichen der Hände aus. Der Mausblick wird weiterhin oben drauf gerechnet.

## Augen-Ebenen (Tiefen-Vorlauf)

Augenweiß/Lidstrich, Pupillen und Highlights sind halbtransparent. Damit ein
Shape Key, der das Lid davorschiebt (z. B. `X)`, `-_-`), die Augen wirklich
verdeckt, schreibt je ein unsichtbarer Zwilling vorher die Tiefe
(`addDepthPrepass` in toon-shader.js). Schalter im Panel: „Augen verdecken (Tiefe)“.
Flackert etwas an den Augenrändern, `DEPTH_PREPASS_OFFSET` erhöhen.

## Stimme (lokaler Miku-TTS)

`speak(text)` spricht mit Mikus Stimme, sobald der TTS-Dienst eingerichtet ist
(`scripts/_a3d_tts/setup_tts.bat`, Anleitung dort im README). Panel → „🔊 Stimme“:
an/aus, **Lautstärke 0–150 %** (unabhängig von Windows, wird gespeichert),
„▶ Probe“ und der Status des Dienstes. Lange Texte werden in Sätze geteilt:
Satz 1 läuft schon, während Satz 2 erzeugt wird. Die Mundöffnung folgt der
Lautstärke des Audios, die Mundformen kommen weiter aus dem Text. Ohne Dienst
(oder ohne Internet für Edge-TTS) bewegt sich wie bisher nur der Mund.
Von außen: `setVoiceVolume(0..1.5)`, `setVoiceEnabled(true/false)`, `getVoiceStatus()`.

## Streicheln

Mit der Maus 2–3 Mal über den Kopf hin und her fahren (ohne Klick): Die Augen
gehen zu (`X)`), sie lächelt leicht, neigt den Kopf in die Streichelrichtung
und zieht die Schultern minimal hoch. Etwa 1 s nach der letzten Bewegung hört
es auf. Panel → „🤸 Gesten“: Knopf „🤗 Streicheln“ und Schalter „🖐 Streicheln
mit der Maus“. Von außen: `petHead(sekunden)`. Empfindlichkeit, Trefferbereich
und Stärke der Bewegung: `PET` in pet.js.

## Stationen (Präsentation)

Panel → „📍 Stationen“: Klick auf eine Station und die Figur läuft hin (dreht
sich erst in Laufrichtung, am Ziel in die eingestellte Blickrichtung).
Fest eingebaut: Start, Board links/Mitte/rechts (nur im breiten Layout).
„＋ Station an Mausposition“ legt eigene Punkte an (Countdown wie bei der
Blickmitte, nur die waagerechte Position zählt); der Knopf daneben wechselt die
Blickrichtung am Ziel (👀 Publikum / ↗ rechts / ↖ links), ✕ löscht.
Gespeichert in `_a3d/stations.json`, getrennt nach breitem und schmalem Layout.
Positionen sind Anteile der Fensterbreite, passen also auch nach „⇔ Breit“.

Für Abläufe aus Python oder vom Board:

```js
await walkTo("Board links");
showOnBoard("board/folie1.html");
playGesture("👉 Nach rechts zeigen");
speak("Hier sehen Sie die Zahlen aus dem dritten Quartal.");
await walkTo({ sx: 0.6, face: "left" });   // beliebiger Punkt
await goHome();
```

Tempo: `WALK.stride` / `WALK.cadence` in walk.js. Feste Stationen anpassen:
`STATIONS_DEFAULT` in stations.js (`board: 0..1` = Anteil der Board-Breite,
`offset` = Versatz als Anteil der Fensterbreite, `face` = Blickrichtung).

## Panel

Jede Überschrift im Panel ist ein Klapp-Abschnitt (▾ offen / ▸ zu), die
Clip-Kategorien sind Unterabschnitte von „🎞 Clips“. Welche Abschnitte offen
sind, merkt sich das Plugin in `_a3d/panel_state.json`. Standardmäßig offen:
Helligkeit, Darstellung, Blick, Animationen (`PANEL_OPEN_BY_DEFAULT` in panel.js).

„🧪 Shape Keys“ zeigt jeden Shape Key des Modells als Schieberegler (wie in
Blender). Ein Wert > 0 überschreibt Mimik, Lippensync und Blinzeln für diesen
Shape Key; „↺ Alle freigeben“ gibt alle wieder frei. Oben steht, ob der
Viewer mit WebGL 2 läuft (alle Shape Keys gleichzeitig) oder WebGL 1 (max. 8).

## Blickmitte kalibrieren

Panel → „👀 Blick“ (direkt unter „Darstellung“). Popup und Fenster haben
getrennte Kalibrierungen (das Plugin öffnet den Viewer mit `?mode=popup` bzw.
`?mode=window`), jeweils für das schmale und das breite Layout. Kalibriert wird
das gerade aktive Layout – im Popup also erst mit „⇔ Breit“ verbreitern, um
das breite Layout einzustellen.

Nach dem Klick die Maus innerhalb von 3 Sekunden dorthin bewegen, wo die
Figur geradeaus schauen soll (auch außerhalb des Fensters). Klick im Fenster
übernimmt sofort, Esc bricht ab, ↺ setzt auf den Standard (`STAGE.lookCenter`).

- Gespeichert als Anteil der Fenstergröße (wandert mit dem Fenster mit).
- Läuft die Figur zu einer Station, wandert die Blickmitte mit ihr mit
  (`STAGE.lookFollowsFigure`). Kalibriert wird immer relativ zum Startplatz,
  auch wenn sie gerade woanders steht.
- Dateien: `look_calibration_popup.json` / `look_calibration_window.json` in
  `_a3d/`, geschrieben über den Server des Plugins (`do_POST`). localStorage
  allein reicht nicht, weil der Server bei jedem Start einen neuen Port bekommt.

## Eigenes Hintergrundbild

1. PNG nach `assets/` legen und `STAGE.background` anpassen.
2. Die weiße Board-Fläche im Bild in Pixeln ausmessen (z. B. in Paint) und als
   Anteil der Bildgröße eintragen: `left = x / Bildbreite`, `top = y / Bildhöhe`,
   `width = Breite / Bildbreite`, `height = Höhe / Bildhöhe`.
3. Zum Prüfen im Panel „🎥 Kamera frei (Debug)“ einschalten – die Board-Fläche
   wird dann gestrichelt umrandet.

## Wichtig

- Die Skripte sind normale `<script>`-Dateien und teilen sich ihre Variablen.
  Die **Reihenfolge in viewer.html** muss erhalten bleiben (z. B. braucht
  `idle.js` die Funktion `dir()` aus `pose.js`, `main.js` startet alles am Ende).
- Eine neue Datei bindest du vor `main.js` in viewer.html ein.
- Von außen (z. B. aus Python per `runJavaScript`) nutzbar:
  `speak(text)`, `stopSpeaking()`, `isSpeaking()`, `playGesture(name)`,
  `walkTo(stationOderPunkt)`, `goHome()`, `getStations()`, `addStation(name, sx, face)`,
  `playAnimation(name)` ("🌿 Natürliches Idle", "🚶 Laufen (auf der Stelle)" oder ein Clipname), `stopAnimation()`,
  `playClip(name, { loop: true/false })`, `stopClip()`, `getClipCategories()`,
  `setLookCenter(x, y)` (Blickmittelpunkt in Fenster-px, `null` = zurück auf `STAGE.lookCenter`),
  `getLookCalibration()`, `setLookCalibration(objOderJson)`, `resetLookCalibration("wide"|"narrow"|"all")`,
  `setScreenInfo(fensterX, fensterY, bildschirmX, bildschirmY, breite, höhe)` (schickt das Plugin), `showOnBoard(urlOderHtml)`, `clearBoard()`,
  `setExpression(name, stärke, sekunden)`, `setMood(name, stärke)`.
- Blickverfolgung: Das Plugin schickt die Mausposition ~30x/s per
  `setExternalMouse(x, y)` an den Viewer. So folgt der Kopf auch über dem
  Board-iframe und außerhalb des Fensters (ganzer Bildschirm). Im normalen
  Browser ohne Plugin folgt er nur innerhalb der Seite.
