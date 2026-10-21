# 3D-Assistent

Alles für das Plugin `scripts/3D Assistent.py` (Unterstrich im Ordnernamen = in der Toolbar
ausgeblendet). Drei Teile, jeder mit eigenem README:

```
_a3d/
├── viewer/   Web-Viewer: three.js, Figur, Panel, Chat, Board        → viewer/README.md
├── tts/      Miku-Stimme: Edge-TTS + RVC, eigener Dienst (venv)     → tts/README.md
└── ai/       KI aus dem PDA: Ollama, MCP, Whisper, Piper (venv)    → ai/README.md
```

So hängt es zusammen:

```
Toolbar ── PluginWidget (3D Assistent.py) ── Asset-Server (127.0.0.1, liefert nur viewer/ aus)
                                                 ├─ POST /tts    → tts/  (Miku), sonst ai/ (Piper)
                                                 ├─ /ai/...      → ai/   (Chat, Modelle, 🎤)
                                                 └─ POST /push   ← ai/   (presenter.push)
services.push("3D Assistent.py", text) → Popup öffnet sich → PluginWidget.on_push → Viewer
```

- Die Dienste laufen als eigene Prozesse mit eigener venv: Ihre Pakete (Torch, onnxruntime)
  vertragen sich nicht mit PyQt5 im Toolbar-Prozess. Das Plugin startet sie selbst; sie
  beenden sich, wenn die Toolbar endet.
- Einrichten: `tts/setup_tts.bat` (Miku-Stimme) und `ai/setup_ai.bat` (KI). Beides optional –
  ohne `ai/` spricht die Figur nur, was man tippt; ohne `tts/` und `ai/` bewegt sie nur den Mund.
- Nur `viewer/` wird über HTTP ausgeliefert, damit z. B. `ai/mcp_servers/.env` (Mail-Passwort)
  nicht für lokale Seiten erreichbar ist.
