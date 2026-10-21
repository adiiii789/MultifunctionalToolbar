# KI-Dienst für den 3D-Assistenten

Der Assistent aus dem PDA-Projekt (`SWE_II_PDA`): **Ollama** (lokales Sprachmodell) mit
Werkzeugen von **MCP-Servern**, **Spracheingabe** mit faster-whisper und **Piper** als
Offline-Stimme. Das Plugin „3D Assistent“ startet den Dienst selbst; die Figur zeigt die
Antworten im Chat, spricht sie und führt die `[aktionen]` darin aus.

```
_a3d/ai/
├── assistant_server.py   HTTP-Dienst (nur 127.0.0.1), wird vom Plugin gestartet
├── backend/              aus dem PDA übernommen (ohne Qt-Popup, Bridge, Jinja)
│   ├── config.py         Einstellungen: Ollama, Denkmodus, Whisper, Piper
│   ├── assistant/        OllamaAssistant, Tool-Calling, feste Befehle, skills/
│   ├── integrations/     MCP-Client (stdio) - weitere Integrationen hierher
│   └── speech.py         Mikrofon + Whisper, Piper / Windows-Stimme
├── mcp_servers/          eigene MCP-Server: pda_server.py (Uhrzeit, Rechnen, E-Mail),
│                         web_server.py (Websuche, Webseiten lesen)
├── mcp_servers.json      welche MCP-Server laufen (Format wie Claude Desktop)
├── setup_ai.bat          Einrichtung: venv/, Pakete, Sprachmodelle vorab laden
└── venv/, data/, logs/   lokal, nicht im Repo
```

## Einrichten (einmalig)

1. [Ollama](https://ollama.com) installieren und ein Modell mit Tool-Calling laden, z. B.
   `ollama pull qwen3:8b` (klein: `llama3.2:3b`).
2. **`setup_ai.bat`** doppelklicken: legt `venv/` an, installiert die Pakete und lädt das
   Whisper-Modell (~480 MB) und die Piper-Stimme (~60 MB) vorab. Liegen sie vom PDA schon in
   `%APPDATA%\PersonalDigitalAgent\speech`, werden sie von dort genommen.
3. Toolbar neu starten.

Warum ein eigener Prozess? In der Toolbar ist PyQt5 schon geladen, und dann stürzt der Import
von onnxruntime (Piper, Whisper) ab – siehe `load_before_qt` in `backend/speech.py`.

## Im Viewer

- **Chat**: Nachricht tippen → die KI antwortet (Sprache: `LANGUAGE`, Standard Englisch) („denkt nach …“, die Figur schaut nachdenklich).
  Die Antwort darf `[gesture.wave]`, `[expression.happy]`, `[walk.Board Mitte]` enthalten
  (auf Deutsch `[geste.winken]` …) –
  welche Namen es gibt, schickt der Viewer bei jeder Nachricht mit.
- **💭** neben dem Eingabefeld: Denkmodus an/aus (blau = an). An: das Modell überlegt erst –
  gründlichere Antworten, aber deutlich langsamer. Wird gespeichert und gilt ab der nächsten Nachricht.
- **🎤** neben dem Eingabefeld: Klick = Aufnahme, zweiter Klick = erkennen und senden,
  **Esc** = abbrechen. Esc während sie spricht = Vorlesen stoppen.
- **Panel → „🤖 KI-Assistent“**: KI an/aus (aus = die Figur spricht, was man tippt),
  Werkzeug-Ergebnisse aufs Board, Modell wählen, „Neues Gespräch“.
- Feste Befehle wie im PDA: `hilfe`, `uhrzeit`, `system`, `neu`.

## Websuche

Der MCP-Server `web` (`mcp_servers/web_server.py`, Logik in `web.py`) gibt dem Modell zwei Werkzeuge:

- `web_search` – sucht über [ddgs](https://pypi.org/project/ddgs/) (DuckDuckGo & Co.), ohne API-Schlüssel
- `web_fetch` – liest den Text einer Seite (ohne Menüs/Skripte), lange Seiten in Teilen

Das Modell nutzt sie von selbst für aktuelle Fragen (Nachrichten, Wetter, Versionen …), sicherer mit
„Search the web: …“. `web_fetch` ruft nur öffentliche Adressen auf, auch nach Weiterleitungen –
eine Webseite kann das Modell so nicht dazu bringen, Dienste auf diesem PC (127.0.0.1) oder Geräte im
Heimnetz anzusprechen. Abschalten: in `mcp_servers.json` bei `"web"` `"disabled": true` eintragen.

## Plugins der Toolbar steuern

Plugins mit `ASSISTANT_TOOLS` (Timer, Kalender …, Konvention im Haupt-README und in
`plugin_tools.py`) erscheinen hier als Werkzeuge: `backend/integrations/toolbar.py` holt sie bei der
Toolbar ab (`TOOLBAR_TOOLS_URL`/`TOOLBAR_TOOLS_TOKEN`, vom Plugin geerbt) und frischt die Liste alle
10 s auf. Von Hand gestartet (ohne Toolbar) gibt es diese Werkzeuge nicht.

## Ansichten aufs Board (Jinja)

Wie im PDA rendert der Dienst Ansichten (`TemplateView`) mit Jinja2: `backend/rendering.py`, Vorlagen in
`templates/` (`default.html.j2` für Titel/Text/Tabelle, `tool_calls.html.j2` als Bestätigung der
Werkzeugaufrufe, Farben in `theme.css`, Layout in `view.css`). Die Antwort von `/chat` enthält das fertige
HTML unter `view.html`; der Viewer zeigt es im Board-iframe (Sandbox ohne Skripte). Autoescaping ist an -
Werkzeug-Ergebnisse von Dritten werden nie als HTML ausgeführt. Die Bestätigung der Werkzeugaufrufe
(`tool_calls`) steht im Viewer in der Konsole; aufs Board nur mit dem Panel-Schalter „Werkzeugaufrufe
aufs Board“ (liegt dort gerade ein Plugin, erscheint sie nach ✕). Hinweis: Der Viewer ist Chromium 83 (QtWebEngine 5.15) - z. B. kein
`gap` bei Flexbox.

## Von sich aus sprechen (push)

Wie `presenter.push` im PDA – nur öffnet sich hier das Toolbar-Popup, und Miku sagt die Nachricht:

```python
from backend.assistant import AssistantReply
from backend.presenter import push
push(AssistantReply("[geste.winken] Guten Morgen! Heute hast du drei Termine."))
```

Gedacht für Fähigkeiten in `backend/assistant/skills/` (z. B. ein Briefing um 7 Uhr). Weg:
Dienst → `POST /push` am Asset-Server des Plugins (`A3D_PUSH_URL`) → `services.push` →
`PluginWidget.on_push` → `receivePush` im Viewer.

## Stimme

Im Panel unter „🔊 Stimme“ auswählbar (gespeichert in `viewer/viewer_settings.json`):

| Auswahl | Sprecherin (Edge-TTS) → RVC | `f0_up_key` |
|---|---|---|
| Miku – Englisch (Standard) | `en-US-AnaNeural` | +2 |
| Miku – Japanisch | `ja-JP-NanamiNeural` | +6 |
| Miku – Deutsch | `de-DE-AmalaNeural` | +7 |
| Piper (offline) | Piper aus diesem Dienst, Sprache wie `LANGUAGE` | – |

Die Tonhöhen sind gemessen: Jede Sprecherin landet nach RVC auf Mikus Tonlage (Nanami 245 Hz
+ 6 Halbtöne ≈ 347 Hz). Ändern oder ergänzen: `TTS_VOICES` oben in `3D Assistent.py`, Standard
`TTS_DEFAULT_VOICE`. Geht die Miku-Stimme nicht (z. B. offline), spricht Piper
(`TTS_FALLBACK_PIPER`); das Panel zeigt dann „Miku gerade nicht erreichbar“.

## Einstellungen

| Was | Wo |
|---|---|
| **Sprache** (Antworten, Spracherkennung, Piper-Stimme, Aktionsnamen): `"en"` oder `"de"` | `LANGUAGE` in `backend/config.py` bzw. `PDA_LANGUAGE` |
| Ollama-Adresse, Optionen, Werkzeug-Runden | `backend/config.py` |
| Denkmodus – im Chat per 💭; `OLLAMA_THINK` gilt nur für Anfragen ohne Angabe | `OLLAMA_THINK` in `backend/config.py` |
| Kontextfenster (`num_ctx`, Standard 16384 – Ollamas 4096 reicht für Webseiten + Denken nicht) | `OLLAMA_OPTIONS` in `backend/config.py` |
| Whisper-Modell, Piper-Stimme (Standard je Sprache: `PIPER_VOICES`) | `backend/config.py` bzw. `PDA_WHISPER_MODEL`, `PDA_SPEECH_LANGUAGE`, `PDA_PIPER_VOICE` |
| Persönlichkeit / Systemanweisung | `BASE_INSTRUCTIONS` in `backend/assistant/ollama_assistant.py` |
| Anleitung für die `[aktionen]` (je Sprache) | `AVATAR_TEXT` in `assistant_server.py` |
| Dienst an/aus, beim Öffnen starten | `AI_ENABLED`, `AI_AUTOSTART` in `3D Assistent.py` |
| MCP-Server hinzufügen | `mcp_servers.json` (`"disabled": true` schaltet einen ab) |
| E-Mail senden/lesen | `mcp_servers/.env.example` → `mcp_servers/.env` |

Nach Änderungen die Toolbar neu starten.

## Fehlersuche

- Protokolle: `logs/server.log` (Dienst) und `logs/dienst_start.log` (Start).
- Von Hand starten: `venv\Scripts\python.exe assistant_server.py --port 5072`, dann im Browser
  `http://127.0.0.1:5072/health` bzw. `/models`.
- „Ollama ist nicht erreichbar“: Ollama starten (Tray-Icon bzw. `ollama serve`).

## Abgleich mit dem PDA

`backend/` und `mcp_servers/` sind Kopien aus `SWE_II_PDA`. Abweichungen:
`config.py` (Pfade, `OLLAMA_THINK`, `LANGUAGE`), `assistant/ollama.py` (Parameter `think`),
`assistant/__init__.py` (reicht `OLLAMA_THINK` und `LANGUAGE` durch), `assistant/ollama_assistant.py`
(`BASE_INSTRUCTIONS` je Sprache: Miku, gesprochene Antworten; leere Antwort im Denkmodus -> Nachfrage
ohne Denken; als Text geschriebene Werkzeugaufrufe wie `[web_search query="…"]` werden ausgeführt,
`calls_written_as_text`), `assistant/llm.py` + `ollama.py` (Feld `thinking` im Verlauf), neu: `presenter.py`,
`mcp_servers/web.py`, `mcp_servers/web_server.py`.
