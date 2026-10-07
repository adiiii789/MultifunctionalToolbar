# Lokaler Miku-TTS für den 3D-Assistenten

Text → **Edge-TTS** (Microsoft, online, Stimme `ja-JP-NanamiNeural`) → **RVC** (lokal, Miku-Stimmmodell) → WAV.
Das Plugin „3D Assistent“ startet den Dienst selbst, sobald er eingerichtet ist.

## Einrichten (einmalig)

1. **Python 3.12 (64 Bit)** von python.org installieren, falls noch nicht vorhanden
   (beim Installer den *py launcher* aktiviert lassen). 3.10 und 3.11 gehen auch.
2. **`setup_tts.bat`** doppelklicken. Die Frage nach DirectML:
   - **N** (Standard): läuft auf der CPU – am zuverlässigsten.
   - **J**: zusätzlich DirectML für die AMD-Grafikkarte – schneller, aber experimentell.
     Scheitert DirectML beim Sprechen, schaltet das Plugin automatisch auf CPU um.
3. Das Skript lädt ca. 1–1,4 GB (Pakete + Modelle) und spielt zum Schluss eine
   Probe ab (`test_miku.wav`). Danach die **Toolbar neu starten**.

Das Setup kann jederzeit erneut gestartet werden; Fertiges wird übersprungen.

## Einstellungen – `tts_config.json`

| Schlüssel     | Bedeutung                                                         |
|---------------|-------------------------------------------------------------------|
| `voice`       | Edge-TTS-Sprecherin, z. B. `ja-JP-NanamiNeural`, `en-US-AnaNeural` |
| `f0_up_key`   | Tonhöhe in Halbtönen (Nanami → Miku: 6)                            |
| `f0_method`   | `rmvpe` (besser) oder `pm` (schneller)                             |
| `index_rate`  | 0–1, Stärke des Stimm-Index (0 = aus, spart ~0,6 GB Arbeitsspeicher) |
| `protect`     | 0–0,5, schützt S/T/K-Laute vor Verzerrung                         |
| `rate`, `pitch`, `volume` | Edge-TTS vor der Umwandlung, z. B. `"+10%"`, `"+0Hz"` |
| `model`       | Ordner in `models/` (weitere Modelle siehe unten)                  |
| `threads`     | CPU-Kerne für die Berechnung, 0 = automatisch (halbe Kernzahl, max. 4) |
| `low_priority`| `true`: Dienst läuft mit niedriger Priorität                        |

Nach einer Änderung die Toolbar neu starten. Bereits erzeugte Sätze werden
dann neu berechnet (der Cache in `_a3d/tts/` hängt an dieser Datei).

## Start und Gerät

Oben in `3D Assistent.py`:
- `TTS_ENABLED = False` schaltet die Stimme komplett ab.
- `TTS_AUTOSTART = False` (Standard): Der Dienst lädt erst beim ersten Sprechen,
  nicht schon beim Öffnen des Fensters.


`TTS_DEVICE` oben in `3D Assistent.py`: `"auto"` (DirectML, falls installiert,
sonst CPU), `"cpu"` oder `"dml"`.

## Andere Stimmmodelle

Weitere Miku-Varianten liegen im Hugging-Face-Repo `NoCrypt/miku_RVC`:
`setup_tts.bat --model "1b_miku_mellow_rvc_(aple)"` lädt z. B. die sanftere
Version, danach in `tts_config.json` bei `model` eintragen. Jedes andere
RVC-v1/v2-Modell geht auch: Ordner in `models/` mit `.pth` (+ optional `.index`).

## Fehlersuche

- **Nach einem Absturz/harten Neustart des PCs: `repair_tts.bat`** ausführen. Es löscht
  Caches, legt eine kaputte `tts_config.json` neu an (alte als `tts_config.defekt.json`),
  vergleicht alle Modelldateien per Prüfsumme mit Hugging Face, lädt Defektes neu und
  testet die Pakete. Der Dienst repariert einen kaputten Cache zwar auch selbst, aber
  beschädigte Modelldateien findet nur die Reparatur.

- Protokolle: `logs/server.log` (Dienst) und `logs/dienst_start.log` (Start).
- Von Hand starten: `venv\Scripts\python.exe miku_tts_server.py --port 5071`
  und im Browser `http://127.0.0.1:5071/health` öffnen.
- Ohne Internet funktioniert Edge-TTS nicht – der Assistent bewegt dann nur den Mund.

## Hinweise

- Das Stimmmodell ist ein Fan-Modell ohne Lizenzangabe und imitiert die Stimme
  von Hatsune Miku (Crypton Future Media). Für private Nutzung gedacht – vor einer
  Veröffentlichung die Rechte klären.
- Edge-TTS nutzt einen Online-Dienst von Microsoft inoffiziell; er kann sich ändern.
- RVC-Code: offizielles Projekt *Retrieval-based-Voice-Conversion-WebUI* (MIT),
  fester Stand, siehe `RVC_COMMIT` in `setup_tts.py`.
