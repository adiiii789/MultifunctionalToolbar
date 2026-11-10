# 3D-Assistent – Dateiübersicht

Der Viewer liegt in `scripts/_a3d/viewer/` (Übersicht aller Teile: `../README.md`). Das Plugin `3D_Assistent.py` steuert nur noch die Popup-Größe (`POPUP_WIDTH`, `POPUP_HEIGHT`) und dass das schmale Popup durchsichtig ist (`POPUP_TRANSPARENT`: ohne Popup-Hintergrund und ohne Bild, nur Figur und Chat).

```
_a3d/viewer/
├── viewer.html        Grundgerüst: Panel, Chat, lädt CSS und Skripte
├── css/viewer.css     Aussehen von Panel, Chat, Raum und Board
├── assets/            alte Hintergrundbilder (nur noch für `STAGE.background`, siehe unten)
├── board/             Inhalte fürs Smartboard (start.html = Startseite)
├── vendor/            three.js r147 (lokal, damit es ohne Internet läuft)
├── models/model.glb   das Modell
└── js/
    ├── toon-shader.js Anime-Shader: TOON_STYLES (Farben, Sättigung), Materialgruppen, Licht
    ├── core.js        gemeinsame Variablen (Szene, Kamera, Mixer) und Chat
    ├── pose.js        Rig-Knochen, Helfer (dir, aim, rotate, turnHead), Ablauf pro Frame (updatePose)
    ├── motion.js      EASE, keys(): Easing-Kurven, Keyframes, Feder-Glättung (smoothDamp)
    ├── hands.js       HAND_POSES: Fingerposen (locker, Faust, Zeigen ...), orientPalm()
    ├── idle.js        natürliches Idle: IDLE (Armhaltung, Atmen, Wiegen, Standbein wechseln, Umschauen)
    ├── gestures.js    GESTURE_GROUPS: Gesten + Moderation, Gesten beim Sprechen
    ├── pet.js         PET: Streicheln am Kopf (Augen ><, Kopf neigt sich)
    ├── walk.js        WALK: Gehen und Stehen – Schritte, Becken, Fuß-IK, Armschwung
    ├── stations.js    STATIONS_DEFAULT: Punkte, zu denen die Figur läuft (walkTo)
    ├── clips.js       CLIPS: Blender-Animationen aus der GLB, Kategorien, Überblenden
    ├── physics.js     SPRING_CHAINS + COLLIDERS: Haare, Krawatte, Rock, Ärmel
    ├── voice.js       VOICE: Stimme (lokaler Miku-TTS über das Plugin), Lautstärke, Mund folgt dem Audio
    ├── face.js        LIPSYNC, VISEMES: Lippensync, Blinzeln, Taste M
    ├── expressions.js MORPHS, EXPRESSIONS: Mimik aus Shape Keys (Original- und eigene Namen)
    ├── actions.js     [kategorie.funktion] im Chat ausführen
    ├── assistant.js   KI-Antworten (Ollama/MCP über scripts/_a3d/ai), Spracheingabe 🎤
    ├── panel.js       Bedienpanel (Darstellung, Idle/Laufen, Clips nach Kategorie, Mimik, Mausblick)
    ├── stage.js       STAGE: Lage von Raum und Board, Figur-Position, Mausblick, Debug-Kamera
    ├── room.js        ROOM: der Raum (Fenster, Uhr, Licht, Pflanze, Tafel) und das rollbare Board
    ├── room3d.js      ROOM3D: 3D-Raum aus models/room.glb (falls vorhanden), Himmel, Wasser
    └── main.js        Setup, Modell laden, Kamera, Render-Schleife – startet alles
```

## Wo stelle ich was ein?

| Was                              | Datei            | Konstante                    |
|----------------------------------|------------------|------------------------------|
| Schattenfarben, Sättigung, Rim   | toon-shader.js   | `TOON_STYLES`                |
| Helligkeit des Lichts            | toon-shader.js   | `LIGHTING`                   |
| Armhaltung, Atmen, Umschauen     | idle.js          | `IDLE`                       |
| Neue Geste hinzufügen            | gestures.js      | `GESTURE_GROUPS`             |
| Standbein wechseln (wie oft, wie stark) | idle.js   | `IDLE.shift…`, `IDLE.freeFoot…` |
| Wie lange sie der stillen Maus nachschaut | idle.js | `IDLE.mouseIdle`             |
| Lauftempo, Schritthöhe, Abrollen | walk.js          | `WALK`                       |
| Wie „lebendig“ gehaltene Gesten sind | gestures.js  | `GESTURE.live`, `GESTURE.shoulder` |
| Raum: Wind, Tageszeiten, Licht auf der Figur | room.js | `ROOM`                    |
| Farben des Raums je Tageszeit    | css/viewer.css   | `#room { --wall-top … }`     |
| Haar-/Rock-Steifigkeit           | physics.js       | `SPRING_CHAINS`              |
| Kollision mit dem Körper         | physics.js       | `COLLIDERS`                  |
| Sprechtempo, Mundöffnung         | face.js          | `LIPSYNC`                    |
| Board-Fläche, eigenes Hintergrundbild | stage.js    | `STAGE.board`, `STAGE.background` |
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

## Bewegung: Idle, Gehen, Gesten

Alles außer den Blender-Clips ist gerechnet, nicht aufgezeichnet. Damit es nicht starr wirkt:

- **Füße stehen fest (Fuß-IK, walk.js).** Die Beine werden jedes Bild so gestellt, dass die Füße
  an ihrem Platz bleiben – egal, was Becken und Oberkörper tun. Dadurch kann die Figur ihr
  **Gewicht verlagern** (Becken wandert über ein Bein, Hüfte und Schultern kippen gegeneinander,
  das andere Bein steht locker), sich verbeugen (Hüfte geht nach hinten) oder in die Knie federn.
- **Laufanimation:** Standard ist wieder die alte (gleichmäßiger Gangzyklus, `WALK.classic = true`,
  Werte in `WALK.old`). Panel → Animationen → „🚶 Alte Laufanimation: aus“ schaltet auf die neue um:
- **Gehen mit echten Schritten (neue Art).** Ein Fuß bleibt stehen, bis der andere aufsetzt; Ferse setzt auf,
  Fußspitze rollt ab. Die Figur läuft weich an, bremst vor dem Ziel ab und dreht sich mit kleinen
  Schritten statt wie auf einem Drehteller. Armschwung, Gegendrehung der Schultern und das Wippen
  des Beckens ergeben sich aus der Stellung der Füße.
- **Idle:** Atmen (einatmen schneller als ausatmen), Arme pendeln einzeln und hängen dem Oberkörper
  nach, Finger bewegen sich leicht, die Augen springen in kleinen Schritten, bei großen
  Blickwechseln blinzelt sie. Steht die Maus `IDLE.mouseIdle` Sekunden still, schaut sie sich
  wieder selbst um statt auf den Zeiger zu starren.
- **Gesten:** Der ganze Körper macht mit (`g.shift()` legt das Gewicht aufs passende Bein), die
  Schulter hebt sich mit dem Arm, der Blick geht dem Arm voraus, und eine gehaltene Pose steht
  nie ganz still.

- **Trägheit (pose.js, `FOLLOW`):** Oberkörper, Kopf und Arme nehmen ihre Zielhaltung nicht sofort
  ein, sondern folgen ihr wie etwas mit Masse – laufen nach, schwingen minimal über und pendeln
  aus, die Hand später als der Oberarm. `FOLLOW.amount = 0` schaltet das ab (zum Vergleichen),
  `speed`/`damping` je Knochen machen es schwerer oder straffer.
- **Kleine Eigenheiten (idle.js, `FIDGETS`):** alle paar Sekunden tief durchatmen, auf die Zehen
  wippen, die Arme schwingen oder die Schultern lockern (`IDLE.fidgetMin/Max`, `fidgetAmount`).

Während ein Clip läuft oder nach „⏹ Stopp (Ruhepose)“ ist die Fuß-IK aus.

**Technik:** Das Plugin zeigt den Viewer mit Qt WebEngine 5.15 (Chromium 83). Neuere CSS-/JS-Kurzformen
(z. B. `inset`, `replaceChildren`, `replaceAll`) gibt es dort nicht – nach Änderungen im Plugin testen,
nicht nur in einem aktuellen Browser.

**Bildrate:** Der Raum liegt unter dem 3D-Canvas. Was sich dort dauernd bewegt (Wolken, Vorhänge), muss
eine eigene kleine Ebene sein und darf nur per `transform`/`opacity` animiert werden; keine
Daueranimation, kein `mix-blend-mode`, kein `filter` in den großen Zeichnungen – sonst halbiert sich
die Bildrate (siehe Kommentar in room.js).

## Der Raum

Der Hintergrund ist ein gezeichnetes Klassenzimmer (room.js, SVG) hinter der Figur. Klicks gehen
durch die Figur hindurch auf den Raum:

| Was | Klick |
|---|---|
| 🪟 Fenster | auf/zu – offen weht Wind: Vorhänge bauschen sich, Haare und Rock bewegen sich |
| 🕐 Uhr | zeigt die echte Zeit; Miku sagt, wie spät es ist |
| 💡 Lichtschalter | Deckenlampen an/aus (abends und nachts von selbst an) |
| 🪴 Pflanze | raschelt; nach dreimal Gießen blüht sie |
| 🟩 Tafel (hinter dem Board) | mit der Maus malen, der Schwamm wischt |
| 📺 Board | am türkisen Griff links: klicken oder ziehen, dann rollt es zur Seite bzw. zurück |

Der Himmel im Fenster folgt der Uhrzeit (Tag / Abend / Nacht, `ROOM.hours`); das Licht auf der
Figur passt sich an (`ROOM.light`). Miku schaut hin, wenn etwas angeklickt wird.

Panel → „🏫 Raum“: **Miku schiebt das Board weg / holt es zurück** (sie läuft hin, schiebt bzw.
zieht und geht zurück), Board von selbst rollen, Fenster, Licht, Tageszeit, Tafel wischen und ob
sie mit Worten reagiert (`ROOM.talk`). Neuer Inhalt fürs Board holt ein weggerolltes Board zurück
(`ROOM.boardReturnsOnContent`). Der Zustand steht in `room_state.json`.

Im schmalen Fenster sieht man den Ausschnitt des Raums um die Figur (ohne Board), das schmale
Popup bleibt durchsichtig.

Von außen: `setBoardAside(true/false)`, `pushBoard(true/false)`, `setWindowOpen(…)`, `setLamp(…)`,
`setDaytime("auto"|"day"|"evening"|"night")`, `wipeChalkboard()`, `getRoomState()`,
`lookAtPoint(x, y, sekunden)`.

## 3D-Raum statt des gezeichneten Raums

Liegt ein Raum-Modell in `models/`, ersetzt es den gezeichneten Raum (room3d.js): Die Figur steht
dann wirklich im Modell, dahinter Himmel, als Boden eine Wasserfläche. Ohne Datei bleibt der
gezeichnete Raum.

1. Modell als **glTF** oder **GLB** besorgen und ablegen – entweder `models/room.glb` oder den
   entpackten Sketchfab-Ordner als `models/room/` (`scene.gltf`, `scene.bin`, `textures/`) bzw.
   `models/room/Arona room.glb`. Weitere Namen: `ROOM3D.files`.
2. Toolbar neu starten. Panel → „🧊 3D-Raum“ zeigt, ob es geladen wurde.
3. Dort mit den Reglern **Größe, Lage, Drehung und Wasserhöhe** einstellen, bis die Figur am
   gewünschten Platz steht (wird in `room_state.json` gespeichert). Die Figur steht immer bei
   x = 0, z = 0; verschoben wird der Raum um sie herum.

Himmel, Wasser (Lichtnetz) und die Färbung des Raums folgen der Tageszeit (`ROOM3D.looks`; nachts
Sternenhimmel und alles in Blau). „Drehung“ dreht den Raum um den Platz der Figur. Das Board lässt
sich weiter verschieben. Das Lichtnetz auf dem Wasser (Stärke, Maschengröße, Tempo) hat eigene Regler
im selben Panel-Abschnitt; von außen `setRoom3dGlint({ power, size, speed })`. Uhr, Pflanze, Fenster und Tafel des gezeichneten Raums gibt es im 3D-Raum
nicht. Abschalten: `ROOM3D.enabled = false` in room3d.js.

Gedacht für „Arona room“ von C4_62195 (Sketchfab, CC BY 4.0 – Urheber nennen, wenn du es
weitergibst). Die Modelldatei liegt nicht im Repository.

## Augen-Ebenen (Tiefen-Vorlauf)

Augenweiß/Lidstrich, Pupillen und Highlights sind halbtransparent. Damit ein
Shape Key, der das Lid davorschiebt (z. B. `X)`, `-_-`), die Augen wirklich
verdeckt, schreibt je ein unsichtbarer Zwilling vorher die Tiefe
(`addDepthPrepass` in toon-shader.js). Schalter im Panel: „Augen verdecken (Tiefe)“.
Flackert etwas an den Augenrändern, `DEPTH_PREPASS_OFFSET` erhöhen.

## Stimme (lokaler Miku-TTS)

`speak(text)` spricht mit Mikus Stimme, sobald der TTS-Dienst eingerichtet ist
(`scripts/_a3d/tts/setup_tts.bat`, Anleitung dort im README). Panel → „🔊 Stimme“:
an/aus, **Lautstärke 0–150 %** (unabhängig von Windows, wird gespeichert),
„▶ Probe“ und der Status des Dienstes. Lange Texte werden in Sätze geteilt:
Satz 1 läuft schon, während Satz 2 erzeugt wird. Die Mundöffnung folgt der
Lautstärke des Audios, die Mundformen kommen weiter aus dem Text. Ohne Dienst
(oder ohne Internet für Edge-TTS) bewegt sich wie bisher nur der Mund.
Von außen: `setVoiceVolume(0..1.5)`, `setVoiceEnabled(true/false)`, `getVoiceStatus()`.

## KI-Assistent (Ollama, MCP, Spracheingabe)

Mit eingerichtetem KI-Dienst (`scripts/_a3d/ai/setup_ai.bat`, Anleitung im README dort)
antwortet die Figur auf Chat-Nachrichten: lokales Sprachmodell aus Ollama, Werkzeuge von
MCP-Servern, Antwort wird gesprochen und ihre `[aktionen]` ausgeführt. **🎤** neben dem
Eingabefeld = sprechen statt tippen (Whisper), Esc bricht ab. **💭** daneben schaltet den
Denkmodus an/aus (gründlicher, aber langsamer). Die KI kann im Internet suchen (MCP-Server `web`). Panel → „🤖 KI-Assistent“:
an/aus, Modell, Ergebnisse aufs Board, neues Gespräch. Ohne Dienst oder mit „KI antwortet:
aus“ spricht die Figur wie bisher, was man tippt. Ist die Miku-Stimme nicht eingerichtet
oder offline, spricht Piper aus dem KI-Dienst. Die Stimme (Miku Englisch/Japanisch/Deutsch,
Piper) wählt man im Panel unter „🔊 Stimme“ (`TTS_VOICES` im Plugin).
Von außen: `askAssistant(text)`, `resetAssistant()`, `getAssistantStatus()`.
Nachrichten ohne Nutzereingabe (Toolbar-`push`, z. B. Erinnerung oder Briefing vom
KI-Dienst) kommen über `PluginWidget.on_push` → `receivePush({text, view})` an: Miku sagt
sie, sobald Figur und Stimme geladen sind.

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
Gespeichert in `_a3d/viewer/stations.json`, getrennt nach breitem und schmalem Layout.
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

## Aktionen im Chat: `[kategorie.funktion]`

Aktionen in eckigen Klammern werden **nicht angezeigt und nicht gesprochen**,
sondern ausgeführt – der Reihe nach, zusammen mit dem Text dazwischen:

```
[geste.winken] Hallo, ich bin Miku! [station.Board Mitte] Hier seht ihr die Zahlen. [mimik.fröhlich] Super, oder?
```

Chat zeigt „Hallo, ich bin Miku! Hier seht ihr die Zahlen. Super, oder?“. Ablauf:
winken + ersten Satz sprechen → zum Board laufen (wartet bis angekommen) →
zweiten Satz sprechen → fröhlich schauen + letzten Satz sprechen.
Eine neue Nachricht bricht den laufenden Ablauf ab.

Mit Stimme werden alle Sätze gleich zu Beginn angefordert (`prepareSpeech` in voice.js, zwei
gleichzeitig). Gesten, Mimik, Stimmung, Clips und Board-Aktionen vor einem Textstück starten erst,
wenn dessen Ton fertig ist – genau mit dem ersten Wort. `[station.…]` und `[pause.…]` laufen sofort
und werden abgewartet; der Ton entsteht währenddessen schon.

Schreibweise: `[kategorie.funktion]`, mit Wert `[kategorie.funktion(wert)]`.

| Kategorie | Beispiele | Wirkung |
|---|---|---|
| `geste` | `[geste.winken]`, `[geste.rechts zeigen]`, `[geste.streicheln]` | Geste; Teilwörter des Namens aus dem Panel reichen |
| `station` | `[station.Board Mitte]`, `[station.Start]` | hinlaufen, wartet bis angekommen |
| `mimik` | `[mimik.fröhlich]`, `[mimik.überrascht(4)]` | kurzer Ausdruck, optional Sekunden |
| `stimmung` | `[stimmung.lächeln]`, `[stimmung.neutral]` | Grundstimmung, bleibt |
| `clip` | `[clip.Tanz_Drehen]` | Blender-Animation |
| `board` | `[board.zeige(board/folie2.html)]`, `[board.zeige(<h1>Hi</h1>)]`, `[board.leeren]` | Board-Inhalt |
| `board` | `[board.weg]`, `[board.her]` | Miku schiebt das Board zur Seite / holt es zurück |
| `raum` | `[raum.fenster auf]`, `[raum.licht aus]`, `[raum.nacht]`, `[raum.auto]`, `[raum.tafel wischen]` | Fenster, Licht, Tageszeit, Tafel |
| `pause` | `[pause.1.5]` | warten (Sekunden) |
| `bewegung` | `[bewegung.idle]`, `[bewegung.laufen]`, `[bewegung.stopp]` | Grundbewegung |

- Groß/Klein ist egal, `_` und Leerzeichen sind gleich (`[station.board_mitte]`).
- Nur Klammern mit einer dieser Kategorien sind Aktionen. `[1]` oder
  `[siehe oben]` bleiben normaler Text – auch ein Tippfehler wie
  `[gest.winken]` erscheint im Chat, damit man ihn sieht.
- Geste und Mimik verwechselt (`[expression.explain]`, `[gesture.happy]`): wird in der
  anderen Kategorie gesucht und dort ausgeführt; die geschriebene Kategorie hat Vorrang.
- Bekannte Kategorie, aber unbekannte Funktion (`[geste.tanzen]`): wird
  ausgeblendet und übersprungen, Warnung in der Konsole (F12).
- Mimik: deutsche Namen wie oben oder die Schlüssel aus `EXPRESSIONS` in
  expressions.js; weitere deutsche Wörter in `EXPRESSION_ALIASES` (actions.js).
- Englische Kategorienamen gehen auch (`gesture`, `walk`, `expression`, …),
  siehe `ACTION_CATEGORIES`.

Von außen, z. B. aus Python per `runJavaScript` oder für eine spätere KI-Antwort:

```js
assistantMessage("[geste.nicken] Gern! [station.Board rechts] Da ist es.");  // als „Miku“ in den Chat + ausführen
runActions("[geste.verbeugen] Danke!");                                     // nur ausführen
stripActions("Text [geste.winken]");                                        // -> "Text"
```

Der Absendername steht in `ACTIONS.assistantName` (actions.js).

## Panel

Jede Überschrift im Panel ist ein Klapp-Abschnitt (▾ offen / ▸ zu), die
Clip-Kategorien sind Unterabschnitte von „🎞 Clips“. Welche Abschnitte offen
sind, merkt sich das Plugin in `_a3d/viewer/panel_state.json`. Standardmäßig offen:
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
  `_a3d/viewer/`, geschrieben über den Server des Plugins (`do_POST`). localStorage
  allein reicht nicht, weil der Server bei jedem Start einen neuen Port bekommt.

## Eigenes Hintergrundbild statt des Raums

1. PNG nach `assets/` legen und `STAGE.background` in stage.js darauf setzen (z. B. das alte
   `"assets/stage_background.png"`). `null` = der gezeichnete Raum.
2. Die weiße Board-Fläche im Bild in Pixeln ausmessen (z. B. in Paint) und als
   Anteil der Bildgröße eintragen: `left = x / Bildbreite`, `top = y / Bildhöhe`,
   `width = Breite / Bildbreite`, `height = Höhe / Bildhöhe`.
3. Zum Prüfen im Panel „🎥 Kamera frei (Debug)“ einschalten – die Board-Fläche
   wird dann gestrichelt umrandet.

Mit eigenem Bild gibt es nichts zum Anklicken und das Board lässt sich nicht verschieben (es ist
Teil des Bilds). `STAGE.narrow.background` setzt ein eigenes Bild nur fürs schmale Layout.

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
