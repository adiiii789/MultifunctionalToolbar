"""Zentrale Konfiguration des KI-Dienstes: Pfade, Ollama, Sprache.

Übernommen aus dem PDA (SWE_II_PDA/backend/config.py), ohne die Teile für das
Qt-Popup - die Oberfläche ist hier der 3D-Viewer (scripts/_a3d/viewer).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent   # scripts/_a3d/ai

# Sprache des Assistenten: "en" (Englisch) oder "de" (Deutsch). Bestimmt die Antworten des
# Sprachmodells, die Anleitung für die [aktionen], die Spracherkennung und die Piper-Stimme.
LANGUAGE = os.environ.get("PDA_LANGUAGE", "en")

# "ollama" (lokales Sprachmodell + MCP-Werkzeuge) oder "commands" (feste Befehle, ohne KI).
# Siehe backend/assistant/__init__.py (_BACKENDS).
ASSISTANT_BACKEND = os.environ.get("PDA_ASSISTANT_BACKEND", "ollama")

# Ollama (backend/assistant/ollama.py)
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("PDA_OLLAMA_MODEL", "")   # leer = zuletzt gewähltes bzw. erstes installiertes
OLLAMA_TIMEOUT_S = 300                # Laden eines großen Modells kann dauern
# num_ctx: Kontextfenster in Tokens. Ollamas Standard (4096) ist zu klein für Systemanweisung + Werkzeuge +
# Suchergebnisse/Webseiten + Denken - dann schneidet Ollama still den Anfang (auch die Anweisungen) ab.
# 16384 braucht bei qwen3.5:9b ~6 GB Grafikspeicher. num_predict: Obergrenze für eine Antwort samt
# Denken, damit es nicht endlos läuft (leere Antwort -> der Assistent fragt ohne Denken nach).
OLLAMA_OPTIONS: dict = {"num_ctx": 16384, "num_predict": 4096}
# Denkmodus von Modellen wie qwen3: False = sofort antworten (die Figur soll nicht lange schweigen),
# True = erst nachdenken (besser, aber deutlich langsamer), None = Standard des Modells.
OLLAMA_THINK: bool | None = False
# Antwortet das Modell ohne Werkzeug, prüft eine kurze Zusatzanfrage, ob die Bitte eins gebraucht hätte
# ("Ich stelle den Timer" ohne Aufruf), und holt den Aufruf nach. Kostet ~2 s bei Antworten ohne Werkzeug.
ASSISTANT_CHECK_MISSED_CALLS = True
ASSISTANT_MAX_TOOL_ROUNDS = 5         # Werkzeug-Runden pro Nachricht, gegen Endlosschleifen
ASSISTANT_MAX_HISTORY = 30            # Nachrichten im Verlauf, die das Modell sieht

# MCP-Server, deren Werkzeuge der Assistent nutzen kann (backend/integrations/mcp_client.py)
MCP_SERVERS_FILE = ROOT_DIR / "mcp_servers.json"
TEMPLATE_DIR = ROOT_DIR / "templates"   # Jinja2-Vorlagen der Ansichten fürs Board (backend/rendering.py)

# Eigene Daten (gewähltes Modell, Präferenzen) - in .gitignore
DATA_DIR = ROOT_DIR / "data"
PREFERENCES_FILE = DATA_DIR / "preferences.json"

# Sprache (backend/speech.py) - alles lokal; Modelle werden beim ersten Gebrauch geladen.
# Derselbe Ordner wie beim PDA, damit Whisper (~480 MB) und Piper nur einmal geladen werden.
APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "PersonalDigitalAgent"
SPEECH_DIR = Path(os.environ.get("PDA_SPEECH_DIR") or APP_DATA_DIR / "speech")
SPEECH_LANGUAGE = os.environ.get("PDA_SPEECH_LANGUAGE", LANGUAGE)     # leer = Whisper erkennt die Sprache
WHISPER_MODEL = os.environ.get("PDA_WHISPER_MODEL", "small")          # tiny, base, small, medium …
PIPER_VOICES = {"en": "en_US-amy-medium", "de": "de_DE-pavoque-low"}  # Stimmen: huggingface.co/rhasspy/piper-voices
PIPER_VOICE = os.environ.get("PDA_PIPER_VOICE") or PIPER_VOICES.get(LANGUAGE, PIPER_VOICES["en"])
