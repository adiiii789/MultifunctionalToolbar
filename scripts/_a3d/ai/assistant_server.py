"""assistant_server.py - KI-Dienst für den 3D-Assistenten (startet das Plugin "3D Assistent")

Der PDA-Assistent (backend/: Ollama + MCP-Werkzeuge, Whisper, Piper) als kleiner
HTTP-Dienst, nur auf 127.0.0.1. Er läuft in einem eigenen Prozess mit eigener venv
(setup_ai.bat): Im Toolbar-Prozess ist PyQt5 schon geladen, und dann stürzt der Import
von onnxruntime (Piper, Whisper-Sprachfilter) ab - siehe backend/speech.py, load_before_qt.

Der Viewer fragt nicht direkt hier an, sondern über den Asset-Server des Plugins
(/ai/<pfad> wird 1:1 hierher weitergereicht, /tts fällt hierher zurück).

  GET  /health                       {"ok", "stt", "tts"}
  GET  /models                       {"models": [{"name", "tools"}], "current"} | 503 {"error"}
  POST /model     {"name"}           Sprachmodell wechseln (bleibt gespeichert)
  POST /chat      {"message", "avatar", "think"}  -> {"text", "view", "attachments"}
                  avatar = {"gestures": [...], "expressions": [...], "stations": [...]}:
                  was die Figur gerade kann - daraus entsteht die Anleitung für [aktionen]
                  think = Denkmodus für diese Nachricht (true/false; fehlt = config.OLLAMA_THINK)
  POST /reset                        neues Gespräch (Verlauf leeren)
  POST /stt/start                    Mikrofon-Aufnahme starten
  POST /stt/stop                     Aufnahme beenden -> {"text"}
  POST /stt/cancel                   Aufnahme verwerfen
  POST /tts       {"text"}           -> audio/wav (Piper, sonst Windows-Stimme)

In die andere Richtung: backend.presenter.push(reply) öffnet das Toolbar-Popup, und die
Figur sagt die Nachricht (z. B. ein Briefing aus einer Fähigkeit in backend/assistant/skills/).

Von Hand starten:  venv\\Scripts\\python.exe assistant_server.py --port 5072
"""
from __future__ import annotations

import argparse
import ctypes
import io
import hmac
import json
import logging
import os
import sys
import threading
import time
import traceback
import wave
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG_DIR = HERE / "logs"
sys.path.insert(0, str(HERE))
os.chdir(HERE)   # relative Pfade in mcp_servers.json

from backend import config, speech  # noqa: E402
from backend.assistant import ModelSelection, create_assistant  # noqa: E402
from backend.assistant.ollama import OllamaError  # noqa: E402
from backend.presenter import present  # noqa: E402

log = logging.getLogger("assistant_server")

MAX_BODY_BYTES = 64 * 1024
MAX_AVATAR_NAMES = 25   # pro Liste - lange Listen kosten kleine Modelle Kontext und Aufmerksamkeit

# Anleitung für die [aktionen] je Sprache (config.LANGUAGE). Kategorien und Namen versteht
# actions.js in beiden Sprachen; das Modell bekommt die passenden, damit es nicht mischt.
AVATAR_TEXT = {
    "de": {
        "intro": ("Du kannst deine 3D-Figur mit Aktionen in eckigen Klammern im Antworttext steuern. Sie "
                  "werden nicht angezeigt und nicht vorgelesen, sondern genau an dieser Stelle ausgeführt. "
                  "Setze höchstens zwei Aktionen pro Antwort und nur, wenn sie zum Inhalt passen. Verwende "
                  "ausschließlich die Namen aus diesen Listen, schreibe sonst keine eckigen Klammern. "
                  "Die Aktionen bewegen nur die Figur, am PC bewirken sie nichts. Werkzeuge wie web_search "
                  "oder timer_start schreibst du nie als Text, auch nicht in Klammern - die rufst du als echten "
                  "Werkzeugaufruf auf:"),
        "lists": [("geste", "Geste", "gestures"),
                  ("mimik", "kurzer Gesichtsausdruck", "expressions"),
                  ("station", "zu diesem Ort laufen", "stations")],
        "names_from": "NAME aus",
        "example": "Beispiel: [geste.winken] Hallo! [mimik.fröhlich] Schön, dass du da bist.",
    },
    "en": {
        "intro": ("You can control your 3D character with actions in square brackets inside your answer. "
                  "They are not shown or read aloud, but performed exactly at that point. Use at most two "
                  "actions per answer and only when they fit the content. Only use the names from these "
                  "lists and write no other square brackets. Actions only move your character, they do nothing "
                  "on the PC. Never write tools such as web_search or timer_start as text, not even in "
                  "brackets - call them as real tool calls:"),
        "lists": [("gesture", "gesture", "gestures_en"),
                  ("expression", "short facial expression", "expressions_en"),
                  ("walk", "walk to this place", "stations")],
        "names_from": "NAME from",
        "example": "Example: [gesture.wave] Hi! [expression.happy] Nice to see you.",
    },
}


# --- Assistent -----------------------------------------------------------------
class AssistantService:
    """Ein Assistent für die ganze Laufzeit; Anfragen nacheinander (der Verlauf ist nicht threadsicher)."""

    def __init__(self):
        self.assistant = create_assistant()
        self.base_instructions = getattr(self.assistant, "instructions", "")
        self.lock = threading.Lock()

    def chat(self, message: str, avatar: dict, think: bool | None = None) -> dict:
        with self.lock:
            model = getattr(self.assistant, "model", None)
            if model is not None and hasattr(model, "think"):
                model.think = config.OLLAMA_THINK if think is None else bool(think)
            if hasattr(self.assistant, "instructions"):
                self.assistant.instructions = "\n\n".join(
                    part for part in (self.base_instructions, avatar_instructions(avatar)) if part)
            reply = self.assistant.reply(message)
        return present(reply)

    def reset(self) -> None:
        with self.lock:
            self.assistant.reply("neu")

    def models(self) -> dict:
        if not isinstance(self.assistant, ModelSelection):
            return {"models": [], "current": None}
        return {"models": self.assistant.available_models(), "current": self.assistant.current_model()}

    def select_model(self, name: str) -> dict:
        if not isinstance(self.assistant, ModelSelection):
            raise ValueError("Dieser Assistent nutzt kein Sprachmodell")
        with self.lock:
            self.assistant.select_model(name)
        return {"current": name}


def avatar_instructions(avatar: dict) -> str:
    """Anleitung für [aktionen] (scripts/_a3d/viewer/js/actions.js) mit dem, was die Figur gerade kann."""
    if not isinstance(avatar, dict):
        return ""
    text = AVATAR_TEXT.get(config.LANGUAGE, AVATAR_TEXT["en"])
    lines = [f"[{category}.NAME] {what}, {text['names_from']}: {', '.join(names)}"
             for category, what, key in text["lists"] if (names := _names(avatar.get(key)))]
    if not lines:
        return ""
    return "\n".join([text["intro"], *lines, text["example"]])


def _names(value) -> list[str]:
    if not isinstance(value, list):
        return []
    names = [str(v).strip()[:40] for v in value if isinstance(v, str) and str(v).strip()]
    return list(dict.fromkeys(names))[:MAX_AVATAR_NAMES]


# --- Sprache -------------------------------------------------------------------
@cache
def speech_input():
    return speech.create_speech_input()


@cache
def synthesizer():
    """Piper, ersatzweise Windows-Stimme - ohne Abspielen: der Viewer spielt die WAV selbst
    (Lautstärke, Mund folgt dem Audio)."""
    synthesizers = []
    if speech._installed("piper"):
        synthesizers.append(speech.PiperSynthesizer(config.PIPER_VOICE, config.SPEECH_DIR / "piper"))
    if speech._installed("win32com"):
        synthesizers.append(speech.SapiSynthesizer(config.SPEECH_LANGUAGE or None))
    return speech.FallbackSynthesizer(synthesizers) if synthesizers else None


def tts_wav(text: str) -> bytes:
    text = speech.speakable(text)
    if not text:
        raise ValueError("kein Text")
    if synthesizer() is None:
        raise RuntimeError("Weder Piper noch die Windows-Stimme verfügbar")
    audio, sample_rate = synthesizer().synthesize(text)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)   # int16
        wav.setframerate(sample_rate)
        wav.writeframes(audio.tobytes())
    return buffer.getvalue()


# --- HTTP ----------------------------------------------------------------------
SERVICE: AssistantService | None = None
AI_TOKEN = os.environ.get("A3D_AI_TOKEN", "")   # vom Plugin; von Hand gestartet: ohne Token


class Handler(BaseHTTPRequestHandler):
    server_version = "A3dAssistant/1.0"

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _wav(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_BYTES:
            raise ValueError("Anfrage zu groß")
        data = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        if not isinstance(data, dict):
            raise ValueError("kein Objekt")
        return data

    def _authorized(self) -> bool:
        """Vom Plugin gestartet (A3D_AI_TOKEN): nur Anfragen mit diesem Token - sonst könnte jedes
        Programm auf dem PC (oder eine Webseite, die den Port errät) Miku Aufträge geben."""
        if not AI_TOKEN or hmac.compare_digest(self.headers.get("X-A3D-Token", ""), AI_TOKEN):
            return True
        self._json(403, {"error": "kein Zugriff"})
        return False

    def do_GET(self):
        path = self.path.split("?")[0]
        if not self._authorized():
            return
        try:
            if path == "/health":
                self._json(200, {"ok": True, "stt": speech_input() is not None, "tts": synthesizer() is not None})
            elif path == "/models":
                self._json(200, SERVICE.models())
            else:
                self._json(404, {"error": "unbekannter Pfad"})
        except OllamaError as e:
            self._json(503, {"error": str(e)})

    def do_POST(self):
        path = self.path.split("?")[0]
        if not self._authorized():
            return
        try:
            req = self._body()
            if path == "/chat":
                message = str(req.get("message", "")).strip()
                if not message:
                    raise ValueError("keine Nachricht")
                think = req.get("think")
                self._json(200, SERVICE.chat(message, req.get("avatar") or {},
                                             think if isinstance(think, bool) else None))
            elif path == "/reset":
                SERVICE.reset()
                self._json(200, {"ok": True})
            elif path == "/model":
                self._json(200, SERVICE.select_model(str(req.get("name", ""))))
            elif path == "/tts":
                self._wav(tts_wav(str(req.get("text", ""))))
            elif path.startswith("/stt/"):
                self._stt(path[len("/stt/"):])
            else:
                self._json(404, {"error": "unbekannter Pfad"})
        except ValueError as e:
            self._json(400, {"error": str(e)})
        except Exception as e:
            log.error("Fehler bei %s: %s\n%s", path, e, traceback.format_exc())
            self._json(500, {"error": "%s: %s" % (type(e).__name__, e)})

    def _stt(self, action):
        recorder = speech_input()
        if recorder is None:
            raise RuntimeError("Spracheingabe nicht verfügbar - faster-whisper/sounddevice installiert?")
        if action == "start":
            recorder.start()
            self._json(200, {"ok": True})
        elif action == "stop":
            self._json(200, {"text": recorder.stop()})
        elif action == "cancel":
            recorder.cancel()
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "unbekannter Pfad"})


def _process_alive(pid):
    """Läuft der Prozess noch? (Windows: ohne ihn zu beenden - os.kill wäre dort fatal.)"""
    if os.name == "nt":
        SYNCHRONIZE, WAIT_TIMEOUT = 0x00100000, 0x102
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _watch_parent(pid, server):
    while True:
        time.sleep(2)
        if not _process_alive(pid):
            log.info("Toolbar beendet - KI-Dienst fährt herunter")
            server.shutdown()
            return


def main():
    global SERVICE
    ap = argparse.ArgumentParser(description="KI-Dienst für den 3D-Assistenten (Ollama, MCP, Whisper, Piper)")
    ap.add_argument("--port", type=int, default=5072)
    ap.add_argument("--parent-pid", type=int, default=0, help="beenden, wenn dieser Prozess endet")
    args = ap.parse_args()

    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(LOG_DIR / "server.log", encoding="utf-8")])
    SERVICE = AssistantService()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    if args.parent_pid:
        threading.Thread(target=_watch_parent, args=(args.parent_pid, server), daemon=True).start()
    log.info("KI-Dienst läuft auf http://127.0.0.1:%d (Backend %s)", args.port, config.ASSISTANT_BACKEND)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
