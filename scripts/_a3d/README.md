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
    ├── pose.js        Rig-Knochen, Helfer (dir, aim, rotate), Ablauf pro Frame (updatePose)
    ├── idle.js        natürliches Idle: IDLE (Armhaltung, Atmen, Wiegen, Umschauen)
    ├── gestures.js    GESTURE_GROUPS: Gesten + Moderation, Gesten beim Sprechen
    ├── walk.js        WALK: Laufen auf der Stelle / Herumlaufen
    ├── physics.js     SPRING_CHAINS + COLLIDERS: Haare, Krawatte, Rock, Ärmel
    ├── face.js        LIPSYNC, VISEMES: Lippensync, Blinzeln, Taste M
    ├── panel.js       Bedienpanel (Darstellung, Animationen) und Umschalten
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
| Lauftempo, Schrittlänge, Weg     | walk.js          | `WALK`                       |
| Haar-/Rock-Steifigkeit           | physics.js       | `SPRING_CHAINS`              |
| Kollision mit dem Körper         | physics.js       | `COLLIDERS`                  |
| Sprechtempo, Mundöffnung         | face.js          | `LIPSYNC`                    |
| Hintergrundbild, Board-Fläche    | stage.js         | `STAGE.background`, `STAGE.board` |
| Position/Größe der Figur         | stage.js         | `STAGE.character`            |
| Aufrechte Haltung / Neigung    | idle.js          | `IDLE.lean`, `IDLE.spine`    |

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
  `playAnimation(name)`, `showOnBoard(urlOderHtml)`, `clearBoard()`.
- Blickverfolgung: Das Plugin schickt die Mausposition ~30x/s per
  `setExternalMouse(x, y)` an den Viewer. So folgt der Kopf auch über dem
  Board-iframe und außerhalb des Fensters (ganzer Bildschirm). Im normalen
  Browser ohne Plugin folgt er nur innerhalb der Seite.
