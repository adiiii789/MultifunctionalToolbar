# --- Plugin-Parameter (neues System) ---
NAME = "Assistent"
DESCRIPTION = "3D-Assistentin Miku: Chat mit der lokalen KI per Text oder Sprache, bedient andere Plugins und zeigt sie auf ihrem Board."
ICON = ""
PINNED = 1
# Popup-Größe für den Knopf "⇔ Breit" neben "← Explorer" (Anteil des Bildschirms).
# Breiter als hoch -> der Viewer schaltet auf das breite Layout mit Board.
POPUP_WIDTH = 0.5
POPUP_HEIGHT = 0.6

HTML_BUTTON = True
BUTTON_HTML = """
<div style="display:flex;height:100%;gap:10px;
            font-family:system-ui;color:inherit;">
  <button onclick="openPlugin()" style="padding:4px 12px;border-radius:8px;border:none;cursor:pointer;">Assistant</button>
</div>
"""

# ----------------------------------------

# 3D-Assistent (Three.js + GLB-Modell mit Lippen-Sync und Blinzeln).
# Ursprung: AssistantV3.py + http_server.py + viewerV2.html — hier zu einem
# geschlossenen Plugin zusammengeführt:
#   - Eingebauter HTTP-Server (nur 127.0.0.1, zufälliger freier Port) für
#     viewer.html und das Modell, weil der GLTFLoader über file:// nicht
#     laden darf. Kein manuell gestarteter http_server.py mehr nötig.
#   - Alles liegt in scripts/_a3d/ (Unterstrich = in der Toolbar ausgeblendet):
#       viewer/  Web-Viewer, nur dieser Ordner wird ausgeliefert (Modell: viewer/models/model.glb)
#       tts/     Miku-Stimme (Edge-TTS + RVC), eigener Dienst
#       ai/      KI aus dem PDA (Ollama, MCP, Whisper, Piper), eigener Dienst
#   - Fehlt das Modell, zeigt der Viewer einen Hinweis statt schwarzem Fenster.

import atexit
import hashlib
import hmac
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import types
import urllib.error
import urllib.request
from functools import partial
from urllib.parse import parse_qs, quote, urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from PyQt5 import sip
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget, QVBoxLayout, QWidget
from PyQt5.QtCore import QBuffer, QIODevice, QObject, QPoint, QPointF, QRect, Qt, QTimer, QUrl, pyqtSignal
from PyQt5.QtGui import QCursor, QGuiApplication, QImage, QMouseEvent, QPainter, QRegion, QWheelEvent
from PyQt5.QtQuickWidgets import QQuickWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage

def _find_asset_dir():
    """Sucht den Ordner _a3d/viewer (mit viewer.html) - egal, ob das Plugin direkt in
    scripts/ oder in einem Unterordner davon liegt."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "_a3d", "viewer"),                 # Plugin in scripts/
        os.path.join(here, "..", "_a3d", "viewer"),           # Plugin in scripts/<Ordner>/
        os.path.join(here, "..", "..", "_a3d", "viewer"),
        os.path.join(os.getcwd(), "scripts", "_a3d", "viewer"),
    ]
    for cand in candidates:
        if os.path.isfile(os.path.join(cand, "viewer.html")):
            return os.path.abspath(cand)
    print("[3D Assistent] _a3d/viewer/viewer.html nicht gefunden. Gesucht in:\n  " +
          "\n  ".join(os.path.abspath(c) for c in candidates))
    return os.path.abspath(candidates[0])


ASSET_DIR = _find_asset_dir()
log = logging.getLogger("3D Assistent")
MOUSE_POLL_MS = 33   # Mausposition ~30x pro Sekunde an den Viewer schicken
BOARD_POLL_MS = 250  # Lage des Boards (für Plugins auf dem Board) abfragen
BOARD_FPS = 10       # Bilder pro Sekunde eines Plugins auf dem Board (board/plugin.html)
BOARD_JPEG_QUALITY = 85
BOARD_FRAME_WAIT_S = 1.0   # GET /board/frame wartet so lange auf ein neues Bild
BOARD_BAR_PX = 28    # Titelleiste in board/plugin.html (bis die Seite ihre Größe meldet)

# Vom Viewer beschreibbare Dateien (POST): nur diese, nur JSON, klein.
# Nötig, weil der Server bei jedem Start einen neuen Port bekommt - damit
# wechselt die Herkunft der Seite und der localStorage des Browsers ist weg.
# Blick-Kalibrierung: eine Datei pro Modus, damit Popup und Fenster unabhängig sind.
# panel_state.json: welche Abschnitte im Panel eingeklappt sind.
# stations.json: eigene Stationen (Punkte, zu denen die Figur läuft).
# viewer_settings.json: Stimme an/aus, Lautstärke.
# assistant_settings.json: KI an/aus, Ergebnisse aufs Board.
WRITABLE_JSON = {"/look_calibration_popup.json", "/look_calibration_window.json",
                 "/panel_state.json", "/stations.json", "/viewer_settings.json",
                 "/assistant_settings.json"}
MAX_POST_BYTES = 8192
MAX_AI_POST_BYTES = 64 * 1024
CHAT_LOG_MAX = 200     # Chatzeilen, die ein neu geöffneter Viewer (Fenster/Popup) nachgereicht bekommt
MAX_CHAT_TEXT = 8000   # Zeichen je geteilter Chatzeile

# Die Toolbar lädt dieses Modul bei jedem Öffnen des Fensters frisch. Asset-Server
# und TTS-Dienst sollen aber nur EINMAL pro Toolbar-Prozess laufen -> gemeinsamer
# Speicher, der das Neuladen überlebt.
_SHARED = sys.modules.setdefault("_a3d_shared_state", types.ModuleType("_a3d_shared_state"))
if not hasattr(_SHARED, "lock"):
    _SHARED.lock = threading.Lock()
    _SHARED.server = None
    _SHARED.port = None
    _SHARED.tts = None
if not hasattr(_SHARED, "board_streams"):
    _SHARED.board_streams = {}   # id -> _BoardStream (Plugin auf dem Board, siehe unten)
if not hasattr(_SHARED, "viewer_links"):
    _SHARED.viewer_links = {}    # id -> _ViewerLink (Fenster und Popup synchron, siehe unten)
    _SHARED.chat_log = []        # geteilte Chatzeilen {"sender", "text"} für neu geöffnete Viewer
if not hasattr(_SHARED, "token"):
    # Zugang zum Asset-Server (Viewer: viewer.html?k=..., js/token.js) und zum KI-Dienst. Ohne
    # könnte jedes Programm auf dem PC - oder eine Webseite, die den Port errät - Miku Aufträge
    # geben (z. B. Dateien suchen, Plugins bedienen). Neu bei jedem Start der Toolbar.
    _SHARED.token = secrets.token_urlsafe(24)
    _SHARED.ai_token = secrets.token_urlsafe(24)
TOKEN_HEADER = "X-A3D-Token"
_lock = _SHARED.lock


# =============================================================================
# Hilfsdienste (TTS, KI): jeder liegt in einem eigenen Ordner mit eigener
# Python-Umgebung (venv/) und läuft als Unterprozess auf einem freien
# localhost-Port. Er beendet sich selbst, wenn die Toolbar endet (--parent-pid).
# =============================================================================
class LocalService:
    folder = ""                # Ordner mit venv/ und dem Skript
    script = ""                # Server-Skript, versteht --port und --parent-pid
    label = ""                 # für Konsolenmeldungen

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.port = None
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost ohne Proxy

    def enabled(self):
        return True

    def start_args(self):
        return []

    def start_env(self):
        return {}

    def python_exe(self):
        sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
        return os.path.join(self.folder, "venv", *sub)

    def installed(self):
        return os.path.isfile(self.python_exe()) and os.path.isfile(os.path.join(self.folder, self.script))

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure_started(self):
        """Dienst starten, falls eingerichtet und noch nicht gestartet."""
        with self.lock:
            if not self.enabled() or not self.installed():
                return False
            if self.running():
                return True
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
            s.close()
            os.makedirs(os.path.join(self.folder, "logs"), exist_ok=True)
            log = open(os.path.join(self.folder, "logs", "dienst_start.log"), "w", encoding="utf-8")
            self.proc = subprocess.Popen(
                [self.python_exe(), self.script, "--port", str(self.port),
                 "--parent-pid", str(os.getpid()), *self.start_args()],
                cwd=self.folder, env={**os.environ, **self.start_env()}, stdout=log, stderr=subprocess.STDOUT,
                creationflags=0x08000000 if os.name == "nt" else 0)   # CREATE_NO_WINDOW
            print(f"[3D Assistent] {self.label} gestartet (Port {self.port})")
            return True

    def stop(self):
        with self.lock:
            if self.running():
                self.proc.terminate()
                try:
                    self.proc.wait(5)
                except Exception:
                    self.proc.kill()
            self.proc = None

    def _url(self, path):
        return "http://127.0.0.1:%d%s" % (self.port, path)


# =============================================================================
# Lokaler TTS (Miku-Stimme): eigener Dienst in scripts/_a3d/tts
# (eigene Python-Umgebung mit Torch/RVC, eingerichtet mit setup_tts.bat).
# Der Viewer schickt Text an POST /tts dieses Asset-Servers, wir reichen ihn an
# den Dienst weiter und legen die WAV in _a3d/viewer/tts/ ab.
# =============================================================================
TTS_DIR = os.path.abspath(os.path.join(ASSET_DIR, "..", "tts"))
TTS_ENABLED = True         # False = Stimme komplett aus (Dienst wird nie gestartet)
# Stimmen zur Auswahl im Panel ("🔊 Stimme"). engine "miku" = Edge-TTS-Sprecherin + RVC (online),
# "piper" = Piper im KI-Dienst (offline, Sprache wie LANGUAGE dort). f0_up_key = Tonhöhe für RVC in
# Halbtönen - gemessen, damit jede Sprecherin auf Mikus Tonlage kommt (Nanami 245 Hz + 6 = 347 Hz).
# Weitere Sprecherinnen: "edge-tts --list-voices" in der venv von _a3d/tts.
TTS_VOICES = {
    "miku_en": {"label": "Miku – Englisch", "engine": "miku", "voice": "en-US-AnaNeural", "f0_up_key": 2,
                "sample": "Hello! I am Hatsune Miku. Nice to meet you!"},
    "miku_ja": {"label": "Miku – Japanisch", "engine": "miku", "voice": "ja-JP-NanamiNeural", "f0_up_key": 6,
                "sample": "こんにちは！初音ミクです。よろしくね！"},
    "miku_de": {"label": "Miku – Deutsch", "engine": "miku", "voice": "de-DE-AmalaNeural", "f0_up_key": 7,
                "sample": "Hallo! Ich bin Hatsune Miku. Schön, dich kennenzulernen!"},
    "piper": {"label": "Piper (offline)", "engine": "piper",
              "sample": "Hello! I am Miku, speaking offline."},
}
TTS_DEFAULT_VOICE = "miku_en"   # bis im Panel etwas anderes gewählt wird (viewer_settings.json)
TTS_FALLBACK_PIPER = True  # Miku-Stimme geht nicht (z. B. offline) -> Piper aus dem KI-Dienst
TTS_AUTOSTART = False      # True = Dienst schon beim Öffnen laden; False = erst beim ersten Sprechen
TTS_DEVICE = "auto"        # "auto" = DirectML (AMD-GPU), falls installiert, sonst CPU; "cpu"; "dml"
TTS_CACHE_FILES = 30       # so viele zuletzt gesprochene Sätze bleiben in viewer/tts/ (gleicher Satz = sofort);
                           # 0 = nichts aufheben (jede WAV wird kurz nach dem Abspielen gelöscht)
TTS_CACHE_DAYS = 7         # unabhängig davon: älter als so viele Tage -> löschen
TTS_TIMEOUT = 180          # Sekunden pro Satz
TTS_RETRY_AFTER = 60       # s: nach einem Fehler der Miku-Stimme (z. B. offline) so lange gleich Piper nehmen


class TtsService(LocalService):
    folder = TTS_DIR
    script = "miku_tts_server.py"
    label = "TTS-Dienst"

    def __init__(self):
        super().__init__()
        self.device = TTS_DEVICE

    def enabled(self):
        return TTS_ENABLED

    def start_args(self):
        return ["--device", self.device]

    def installed(self):
        return super().installed() and os.path.isdir(os.path.join(TTS_DIR, "models"))

    def status(self, start=True):
        if not TTS_ENABLED:
            return {"state": "disabled", "message": "Im Plugin ausgeschaltet (TTS_ENABLED)"}
        if not self.installed():
            return {"state": "missing", "message": "Nicht eingerichtet: scripts/_a3d/tts/setup_tts.bat ausführen"}
        if not self.running():
            if not start:
                return {"state": "idle", "message": "Startet beim ersten Sprechen"}
            self.ensure_started()
        if not self.running():
            return {"state": "error", "message": "Dienst beendet - siehe scripts/_a3d/tts/logs/"}
        try:
            h = json.loads(self._opener.open(self._url("/health"), timeout=3).read())
        except Exception:
            return {"state": "starting", "message": "Dienst startet ..."}
        if h.get("ready"):
            return {"state": "ready", "device": h.get("device"), "model": h.get("model"), "voice": h.get("voice")}
        if h.get("error"):
            return {"state": "error", "message": h["error"]}
        return {"state": "starting", "message": "Stimmmodell wird geladen ..."}

    def _wait_ready(self, seconds=300):
        t0 = time.time()
        while time.time() - t0 < seconds:
            st = self.status()
            if st["state"] in ("ready", "error", "missing"):
                return st
            time.sleep(1)
        return {"state": "error", "message": "Zeitüberschreitung beim Laden"}

    def _post(self, text, overrides):
        body = json.dumps(dict(overrides, text=text)).encode("utf-8")
        req = urllib.request.Request(self._url("/tts"), data=body, headers={"Content-Type": "application/json"})
        return self._opener.open(req, timeout=TTS_TIMEOUT).read()

    def synthesize(self, text, overrides=None):
        """Text -> WAV-Bytes. overrides: z. B. {"voice", "f0_up_key"} statt tts_config.json.
        Scheitert DirectML, wird einmal auf CPU umgeschaltet."""
        overrides = overrides or {}
        st = self._wait_ready()
        if st["state"] != "ready":
            raise RuntimeError(st.get("message", "TTS nicht bereit"))
        try:
            return self._post(text, overrides)
        except urllib.error.HTTPError as e:
            try:
                info = json.loads(e.read().decode("utf-8"))
            except Exception:
                info = {}
            if e.code == 500 and info.get("device") == "dml":
                print("[3D Assistent] DirectML-Fehler - TTS läuft ab jetzt auf der CPU:", info.get("error"))
                self.stop()
                self.device = "cpu"
                self.ensure_started()
                st = self._wait_ready()
                if st["state"] == "ready":
                    return self._post(text, overrides)
            raise RuntimeError(info.get("error") or "TTS-Fehler %s" % e.code)


def tts_service():
    if _SHARED.tts is None:
        _SHARED.tts = TtsService()
        atexit.register(_SHARED.tts.stop)
    return _SHARED.tts


# =============================================================================
# KI-Assistent: eigener Dienst in scripts/_a3d/ai (übernommen aus dem PDA:
# Ollama + MCP-Werkzeuge, Spracheingabe mit Whisper, Piper-Stimme), eingerichtet
# mit setup_ai.bat. Eigener Prozess, weil onnxruntime (Whisper/Piper) im
# Toolbar-Prozess neben PyQt5 abstürzt. Der Viewer fragt über /ai/<pfad> dieses
# Asset-Servers an, wir reichen die Anfrage 1:1 an den Dienst weiter.
# =============================================================================
AI_DIR = os.path.abspath(os.path.join(ASSET_DIR, "..", "ai"))
AI_ENABLED = True          # False = kein KI-Dienst, der Chat lässt die Figur nur sprechen
AI_AUTOSTART = True        # Dienst schon beim Öffnen starten (leicht; Modelle lädt er erst bei Bedarf)
AI_TIMEOUT = 600           # Sekunden pro Anfrage (Ollama + Werkzeuge können dauern)


class AiService(LocalService):
    folder = AI_DIR
    script = "assistant_server.py"
    label = "KI-Dienst"

    def enabled(self):
        return AI_ENABLED

    def start_env(self):
        # Rückkanal für backend/presenter.push im Dienst: POST /push an diesen Asset-Server
        return {"A3D_PUSH_URL": "http://127.0.0.1:%d/push?k=%s" % (ensure_server(), _SHARED.token),
                "A3D_AI_TOKEN": _SHARED.ai_token}       # der Dienst nimmt nur Anfragen mit diesem Token an

    def status(self, start=True):
        if not AI_ENABLED:
            return {"state": "disabled", "message": "Im Plugin ausgeschaltet (AI_ENABLED)"}
        if not self.installed():
            return {"state": "missing", "message": "Nicht eingerichtet: scripts/_a3d/ai/setup_ai.bat ausführen"}
        if not self.running():
            if not start:
                return {"state": "idle", "message": "Startet bei der ersten Nachricht"}
            self.ensure_started()
        if not self.running():
            return {"state": "error", "message": "Dienst beendet - siehe scripts/_a3d/ai/logs/"}
        try:
            req = urllib.request.Request(self._url("/health"), headers={TOKEN_HEADER: _SHARED.ai_token})
            health = json.loads(self._opener.open(req, timeout=3).read())
        except Exception:
            return {"state": "starting", "message": "Dienst startet ..."}
        return dict(health, state="ready")

    def _wait_ready(self, seconds=60):
        t0 = time.time()
        while time.time() - t0 < seconds:
            st = self.status()
            if st["state"] in ("ready", "error", "missing", "disabled"):
                return st
            time.sleep(0.5)
        return {"state": "error", "message": "Zeitüberschreitung beim Start"}

    def request(self, method, path, body=None):
        """Anfrage an den Dienst -> (HTTP-Code, Content-Type, Bytes). Startet ihn bei Bedarf."""
        st = self._wait_ready()
        if st["state"] != "ready":
            raise RuntimeError(st.get("message", "KI-Dienst nicht bereit"))
        req = urllib.request.Request(self._url(path), data=body, method=method,
                                     headers={"Content-Type": "application/json", TOKEN_HEADER: _SHARED.ai_token})
        try:
            with self._opener.open(req, timeout=AI_TIMEOUT) as r:
                return r.status, r.headers.get("Content-Type", "application/json"), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type", "application/json"), e.read()

    def synthesize(self, text, overrides=None):
        """Text -> WAV-Bytes mit Piper (offline), ersatzweise Windows-Stimme."""
        code, _, data = self.request("POST", "/tts", json.dumps({"text": text}).encode("utf-8"))
        if code != 200:
            try:
                message = json.loads(data.decode("utf-8")).get("error")
            except Exception:
                message = None
            raise RuntimeError(message or "Piper-Fehler %s" % code)
        return data


def ai_service():
    if getattr(_SHARED, "ai", None) is None:
        _SHARED.ai = AiService()
        atexit.register(_SHARED.ai.stop)
    return _SHARED.ai


def tts_voice(voice_id):
    """Eintrag aus TTS_VOICES (unbekannt/leer -> TTS_DEFAULT_VOICE)."""
    return TTS_VOICES.get(voice_id) or TTS_VOICES[TTS_DEFAULT_VOICE]


def _tts_engines(voice_id):
    """Stimmen in der Reihenfolge, in der sie versucht werden: [(name, Dienst, overrides)]."""
    if not TTS_ENABLED:
        return []
    preset = tts_voice(voice_id)
    engines = []
    if preset["engine"] == "miku":
        miku_failed = time.time() - getattr(_SHARED, "tts_failed_at", 0) < TTS_RETRY_AFTER
        if tts_service().installed() and not (miku_failed and TTS_FALLBACK_PIPER):
            engines.append(("miku", tts_service(), {"voice": preset["voice"], "f0_up_key": preset["f0_up_key"]}))
    if (preset["engine"] == "piper" or TTS_FALLBACK_PIPER) and AI_ENABLED and ai_service().installed():
        engines.append(("piper", ai_service(), {}))
    return engines


def tts_voices():
    """Für die Auswahl im Panel: [{"id", "label", "sample"}], dazu die Standardstimme."""
    return {"voices": [{"id": k, "label": v["label"], "sample": v.get("sample", "")} for k, v in TTS_VOICES.items()],
            "default": TTS_DEFAULT_VOICE}


def tts_status(start, voice_id=""):
    """Status für das Panel: die Stimme, die für voice_id gerade dran ist (ggf. der Ersatz)."""
    engines = _tts_engines(voice_id)
    if not engines or engines[0][0] == "miku":
        return tts_service().status(start=start)
    st = ai_service().status(start=True)               # der KI-Dienst ist leicht, Piper lädt beim ersten Satz
    if st["state"] == "ready":
        if not st.get("tts"):
            return {"state": "error", "message": "Piper/Windows-Stimme fehlt im KI-Dienst"}
        return {"state": "ready", "device": "piper"}
    return st


def _tts_to_file(text, voice_id=""):
    """Erzeugt (oder findet im Cache) die WAV zum Text -> Pfad relativ zu viewer/.
    Geht die erste Stimme nicht (z. B. Miku ohne Internet), kommt die nächste dran."""
    cfg = os.path.join(TTS_DIR, "tts_config.json")
    stamp = str(os.path.getmtime(cfg)) if os.path.isfile(cfg) else ""
    out_dir = os.path.join(ASSET_DIR, "tts")
    os.makedirs(out_dir, exist_ok=True)
    engines = _tts_engines(voice_id)
    if not engines:
        raise RuntimeError("Keine Stimme eingerichtet")
    error = None
    for engine, service, overrides in engines:
        key = (stamp if engine == "miku" else engine) + json.dumps(overrides, sort_keys=True) + "\n" + text
        name = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20] + ".wav"
        target = os.path.join(out_dir, name)
        if os.path.isfile(target):
            os.utime(target)                          # zuletzt benutzt
        else:
            try:
                data = service.synthesize(text, overrides)
            except Exception as e:
                print(f"[3D Assistent] Stimme {engine} fehlgeschlagen: {e}")
                if engine == "miku":
                    _SHARED.tts_failed_at = time.time()
                error = e
                continue
            tmp = target + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, target)
        cleanup_tts_cache()
        return "tts/" + name
    raise error


TTS_PLAY_GRACE = 120       # s: so lange bleibt eine WAV mindestens liegen (Viewer lädt/spielt sie gerade)


def cleanup_tts_cache():
    """viewer/tts/ aufräumen: nur die TTS_CACHE_FILES zuletzt benutzten Sätze behalten,
    nichts älter als TTS_CACHE_DAYS, liegengebliebene .tmp-Reste weg. Dateien, die
    gerade erst erzeugt/benutzt wurden, bleiben in jedem Fall kurz stehen."""
    out_dir = os.path.join(ASSET_DIR, "tts")
    if not os.path.isdir(out_dir):
        return
    now = time.time()
    entries = []
    for n in os.listdir(out_dir):
        if n.endswith(".wav") or n.endswith(".tmp"):
            path = os.path.join(out_dir, n)
            try:
                entries.append((os.path.getmtime(path), path))
            except OSError:
                pass
    entries.sort(reverse=True)                        # zuletzt benutzt zuerst
    kept = 0
    for mtime, path in entries:
        age = now - mtime
        if age < TTS_PLAY_GRACE:                      # wird evtl. gerade abgespielt
            kept += path.endswith(".wav")
            continue
        if path.endswith(".tmp") or kept >= TTS_CACHE_FILES or age > TTS_CACHE_DAYS * 86400:
            try:
                os.remove(path)
            except OSError:                           # z. B. gerade in Benutzung - beim nächsten Mal
                pass
        else:
            kept += 1


def _cache_janitor():
    """Hintergrund: beim Start und dann alle 5 Minuten aufräumen (auch ohne neue Sätze)."""
    while True:
        try:
            cleanup_tts_cache()
        except Exception as e:
            print(f"[3D Assistent] Aufräumen von viewer/tts fehlgeschlagen: {e}")
        time.sleep(300)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # kein Konsolen-Spam pro Request

    def _send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self):
        """Token aus dem Header (Viewer, js/token.js) oder ?k= (push des KI-Dienstes)."""
        sent = self.headers.get(TOKEN_HEADER) or parse_qs(urlparse(self.path).query).get("k", [""])[0]
        if hmac.compare_digest(str(sent), _SHARED.token):
            return True
        self._send_json(403, {"error": "kein Zugriff"})
        return False

    def do_GET(self):
        path = urlparse(self.path).path
        # Statische Dateien des Viewers sind offen, alles Dynamische braucht das Token
        if path in ("/tts_status", "/tts_voices", "/board/frame") or path.startswith("/ai/"):
            if not self._authorized():
                return
        if path == "/tts_status":
            # Statusabfrage startet den Dienst nur, wenn TTS_AUTOSTART an ist
            voice_id = parse_qs(urlparse(self.path).query).get("voice", [""])[0]
            self._send_json(200, tts_status(start=TTS_AUTOSTART, voice_id=voice_id))
            return
        if path == "/tts_voices":
            self._send_json(200, tts_voices())
            return
        if path == "/ai/status":
            self._send_json(200, ai_service().status(start=AI_AUTOSTART))
            return
        if path.startswith("/ai/"):
            self._proxy_ai("GET")
            return
        if path == "/board/frame":
            self._board_frame()
            return
        super().do_GET()

    def _board_stream(self):
        stream = _SHARED.board_streams.get(parse_qs(urlparse(self.path).query).get("s", [""])[0])
        if stream is None:
            self._send_json(404, {"error": "kein Plugin auf dem Board"})
        return stream

    def _board_frame(self):
        """GET /board/frame?s=<id>&after=<nr> -> nächstes Bild (JPEG, X-Seq), 204 ohne neues."""
        stream = self._board_stream()
        if stream is None:
            return
        try:
            after = int(parse_qs(urlparse(self.path).query).get("after", ["-1"])[0])
        except ValueError:
            after = -1
        seq, frame = stream.wait_frame(after, BOARD_FRAME_WAIT_S)
        if seq == after or not frame:
            self.send_response(204)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Seq", str(seq))
        self.send_header("Content-Length", str(len(frame)))
        self.end_headers()
        self.wfile.write(frame)

    def _board_input(self):
        """POST /board/input?s=<id> {type, ...} -> Eingabe ans Plugin (Qt-Hauptthread)."""
        stream = self._board_stream()
        if stream is None:
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 4096:
                raise ValueError("Größe")
            event = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(event, dict):
                raise ValueError("kein Objekt")
            stream.input.emit(event)
        except RuntimeError:                # Fenster inzwischen zu
            self._send_json(404, {"error": "kein Plugin auf dem Board"})
            return
        except Exception as e:
            self._send_json(400, {"error": str(e)})
            return
        self.send_response(204)
        self.end_headers()

    def _proxy_ai(self, method):
        """/ai/<pfad> -> KI-Dienst /<pfad> (Antwort unverändert zurück)."""
        body = None
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= MAX_AI_POST_BYTES:
                self._send_json(400, {"error": "Anfrage zu groß"})
                return
            body = self.rfile.read(length)
        try:
            code, ctype, data = ai_service().request(method, self.path[len("/ai"):], body)
        except Exception as e:
            self._send_json(503, {"error": str(e)})
            return
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _do_tts(self):
        """POST /tts {"text": "...", "voice": "<id aus TTS_VOICES>"} -> {"url": "tts/<hash>.wav"}"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_POST_BYTES:
                raise ValueError("Größe")
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            text, voice_id = str(req.get("text", "")).strip(), str(req.get("voice", ""))
            if not text:
                raise ValueError("kein Text")
        except Exception as e:
            self._send_json(400, {"error": str(e)})
            return
        try:
            self._send_json(200, {"url": _tts_to_file(text, voice_id)})
        except Exception as e:
            print(f"[3D Assistent] TTS fehlgeschlagen: {e}")
            self._send_json(503, {"error": str(e)})

    def _do_push(self):
        """POST /push {"text", "view"} (vom KI-Dienst, backend/presenter.push): Toolbar-Popup
        mit der Figur öffnen, sie sagt den Text (services.push -> PluginWidget.on_push)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_AI_POST_BYTES:
                raise ValueError("Größe")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict) or not str(data.get("text", "")).strip():
                raise ValueError("kein Text")
        except Exception as e:
            self._send_json(400, {"error": str(e)})
            return
        self._send_json(200, {"ok": push_to_toolbar(data)})

    def _do_chat_sync(self):
        """POST /chat/sync?v=<viewer> {"sender", "text", "reveal"}: Chatzeile eines Viewers an alle
        offenen Viewer (Fenster und Popup zeigen denselben Chat, PluginWidget._on_chat_sync).
        reveal: Antwort auf eine Frage - der fragende Viewer kommt nach vorne."""
        viewer = parse_qs(urlparse(self.path).query).get("v", [""])[0]
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_AI_POST_BYTES:
                raise ValueError("Größe")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("kein Objekt")
        except Exception as e:
            self._send_json(400, {"error": str(e)})
            return
        entry = {"sender": str(data.get("sender", ""))[:100], "text": str(data.get("text", ""))[:MAX_CHAT_TEXT]}
        with _lock:
            if entry["text"]:
                _SHARED.chat_log.append(entry)
                del _SHARED.chat_log[:-CHAT_LOG_MAX]
            links = list(_SHARED.viewer_links.items())
        for link_id, link in links:
            try:
                link.chat.emit(dict(entry, own=link_id == viewer, reveal=bool(data.get("reveal"))))
            except RuntimeError:            # Fenster inzwischen zu
                pass
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        """Speichert Einstellungen des Viewers (z. B. Blick-Kalibrierung) als
        JSON-Datei in _a3d/viewer/. Nur die Pfade aus WRITABLE_JSON sind erlaubt.
        Außerdem: POST /tts (Text -> Sprachausgabe), /ai/... (KI-Dienst) und /push, siehe oben."""
        path = urlparse(self.path).path
        if not self._authorized():
            return
        if path == "/tts":
            self._do_tts()
            return
        if path.startswith("/ai/"):
            self._proxy_ai("POST")
            return
        if path == "/push":
            self._do_push()
            return
        if path == "/chat/sync":
            self._do_chat_sync()
            return
        if path == "/board/input":
            self._board_input()
            return
        if path not in WRITABLE_JSON:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_POST_BYTES:
                raise ValueError("Größe")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("kein Objekt")
            target = os.path.join(ASSET_DIR, path.lstrip("/"))
            tmp = target + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, target)          # atomar: nie halb geschriebene Datei
        except Exception as e:
            print(f"[3D Assistent] Speichern von {path} fehlgeschlagen: {e}")
            self.send_error(400)
            return
        self.send_response(204)
        self.end_headers()


def ensure_server():
    """Startet den Asset-Server einmalig (Daemon-Thread, nur localhost).

    Port 0 = das Betriebssystem wählt einen freien Port — keine Kollisionen.
    Der Server lebt, solange die Toolbar läuft (gemeinsam für alle Fenster)."""
    with _lock:
        if _SHARED.server is not None:
            return _SHARED.port
        handler = partial(_QuietHandler, directory=ASSET_DIR)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        srv.daemon_threads = True
        _SHARED.port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        threading.Thread(target=_cache_janitor, daemon=True).start()   # alte Sprach-WAVs aufräumen
        _SHARED.server = srv
        return _SHARED.port


def push_to_toolbar(data):
    """Popup der Toolbar mit diesem Plugin öffnen und data an on_push geben (services.push).
    False, wenn die Toolbar nicht läuft (Plugin allein gestartet)."""
    try:
        import services                      # liegt neben tray_launcher.py
    except ImportError:
        print("[3D Assistent] push: services.py nicht gefunden (Toolbar läuft nicht?)")
        return False
    return services.push(os.path.abspath(__file__), data)


def reveal_in_toolbar(widget):
    """Popup bzw. Hauptfenster mit diesem PluginWidget zeigen und nach vorne holen (services.reveal).
    False, wenn die Toolbar nicht läuft - dann das Fenster selbst nach vorne holen."""
    try:
        import services
    except ImportError:
        services = None
    reveal = getattr(services, "reveal", None)
    if callable(reveal) and reveal(widget):
        return True
    window = widget.window()
    if window.isMinimized() or not window.isVisible():
        window.showNormal()
    window.raise_()
    window.activateWindow()
    return False


class _LoggingPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f"[3D Assistent JS] {message} (Zeile {line})")


# =============================================================================
# Plugins auf dem Board. Bedient der Assistent ein Plugin der Toolbar (plugin_tools.py),
# legt der Launcher dessen Fenster hierher (show_on_board). Es liegt verdeckt unter der
# 3D-Ansicht (_BoardHost: Qt WebEngine legt seine Zeichenfläche bei durchsichtigem
# Seitenhintergrund immer obenauf) und rendert dort weiter. board/plugin.html im Board-iframe
# zeigt laufend Bilder davon und schickt Mausereignisse zurück - so liegt das Plugin wirklich
# im Board, Menü und Figur bleiben darüber.
# =============================================================================
class _BoardStream(QObject):
    """Bilder eines Plugins auf dem Board und Eingaben zurück. Die HTTP-Threads lesen
    frame/seq (wait_frame) und schicken Eingaben über das Signal in den Qt-Hauptthread.
    Liegt in _SHARED.board_streams, weil der HTTP-Server das Neuladen des Moduls überlebt."""
    input = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__(parent)
        self.id = secrets.token_urlsafe(12)
        self.cond = threading.Condition()
        self.frame = b""
        self.seq = 0

    def publish(self, frame):
        with self.cond:
            if frame == self.frame:
                return
            self.frame, self.seq = frame, self.seq + 1
            self.cond.notify_all()

    def wait_frame(self, after, timeout):
        """HTTP-Thread: bis zu timeout auf ein Bild nach Nummer after warten -> (seq, frame)."""
        with self.cond:
            self.cond.wait_for(lambda: self.seq != after, timeout)
            return self.seq, self.frame


class _ViewerLink(QObject):
    """Fenster und Popup synchron: Chatzeilen eines Viewers (POST /chat/sync) kommen hierüber in
    den Qt-Hauptthread zu jedem offenen PluginWidget. Liegt in _SHARED.viewer_links, weil der
    HTTP-Server das Neuladen des Moduls überlebt."""
    chat = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__(parent)
        self.id = secrets.token_urlsafe(12)


class _BoardHost(QWidget):
    """Hält die Plugins des Boards - verdeckt unter der 3D-Ansicht, für Mausklicks durchlässig
    (die gehen an den Viewer und kommen über board/plugin.html gezielt zurück)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack)
        self.hide()


class _NotReady(Exception):
    """Eine sichtbare Webansicht des Plugins hat noch keine fertige Zeichenfläche."""


def _capture_widget(widget):
    """Bild eines Plugin-Widgets. render() darf nie an ein Widget mit Webansicht darin (stürzt ab,
    auch mit ausgesparter Fläche): Teilbäume ohne Webansicht über render(), Webansichten direkt
    aus ihrer Zeichenfläche (QQuickWidget.grabFramebuffer), Container dazwischen nur einfärben -
    mit der Randfarbe der ersten Webansicht (Plugins färben ihren Rahmen meist per Stylesheet,
    das die Palette nicht kennt)."""
    frames = {}
    for view in widget.findChildren(QWebEngineView):
        if not view.isVisible():
            continue
        proxy = view.focusProxy()
        quick = sip.cast(proxy, QQuickWidget) if proxy is not None else None
        window = quick.quickWindow() if quick is not None else None
        if window is None or not window.isSceneGraphInitialized():
            raise _NotReady(view)
        frames[view] = quick.grabFramebuffer()
    first = next(iter(frames.values()), None)
    fill = (first.pixelColor(2, 2) if first is not None and first.width() > 2 and first.height() > 2
            else widget.palette().color(widget.backgroundRole()))
    dpr = widget.devicePixelRatioF()
    image = QImage(round(widget.width() * dpr), round(widget.height() * dpr), QImage.Format_RGB32)
    image.setDevicePixelRatio(dpr)
    image.fill(fill)
    painter = QPainter(image)
    try:
        _paint_widget(widget, widget, painter, frames, fill)
    finally:
        painter.end()
    return image


def _paint_widget(root, widget, painter, frames, fill):
    offset = widget.mapTo(root, QPoint(0, 0)) if widget is not root else QPoint(0, 0)
    if isinstance(widget, QWebEngineView):
        if widget in frames:
            painter.drawImage(QRect(offset, widget.size()), frames[widget])
        return
    if not widget.findChildren(QWebEngineView):
        widget.render(painter, offset, QRegion(), QWidget.DrawWindowBackground | QWidget.DrawChildren)
        return
    painter.fillRect(QRect(offset, widget.size()), fill)
    for child in widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
        if child.isVisible() and not child.isWindow():
            _paint_widget(root, child, painter, frames, fill)


_BOARD_BUTTONS = {0: Qt.LeftButton, 1: Qt.MiddleButton, 2: Qt.RightButton}


def _board_buttons(mask):
    """JS MouseEvent.buttons (1 links, 2 rechts, 4 Mitte) -> Qt."""
    buttons = Qt.NoButton
    for bit, button in ((1, Qt.LeftButton), (2, Qt.RightButton), (4, Qt.MiddleButton)):
        if int(mask or 0) & bit:
            buttons |= button
    return buttons


def _board_modifiers(event):
    mods = Qt.NoModifier
    for key, mod in (("shift", Qt.ShiftModifier), ("ctrl", Qt.ControlModifier), ("alt", Qt.AltModifier)):
        if event.get(key):
            mods |= mod
    return mods


class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        super().__init__()
        self.setWindowTitle("3D Assistent")
        self.resize(900, 700)
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        self.browser = QWebEngineView(central)
        self._page = _LoggingPage(self.browser)
        self.browser.setPage(self._page)

        # Durchsichtig: Ohne Hintergrundbild scheint der Popup-Hintergrund durch
        # (Glas-Modus: Glas, Opaque-Modus: Popup-Farbe) statt einer grauen Fläche.
        # Nebenbei verdeckt das die Plugins auf dem Board (_BoardHost): Bei durchsichtigem Hintergrund
        # legt Qt WebEngine seine Zeichenfläche immer obenauf (WA_AlwaysStackOnTop).
        self._page.setBackgroundColor(Qt.transparent)
        self.browser.setAttribute(Qt.WA_TranslucentBackground, True)
        for w in (self, central):
            w.setAttribute(Qt.WA_TranslucentBackground, True)
            w.setStyleSheet("background: transparent;")
        s = self.browser.settings()
        s.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        # Sprachausgabe ohne vorherigen Klick erlauben (sonst bleibt der Ton stumm)
        s.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        port = ensure_server()
        # TTS-Dienst optional schon jetzt im Hintergrund hochfahren (Modell laden dauert)
        if TTS_AUTOSTART:
            threading.Thread(target=tts_service().ensure_started, daemon=True).start()
        if AI_AUTOSTART:
            threading.Thread(target=ai_service().ensure_started, daemon=True).start()
        # Fenster und Popup synchron (siehe _ViewerLink): Der Viewer meldet sich mit ?v=<id>
        self._viewer_link = _ViewerLink(self)
        self._viewer_link.chat.connect(self._on_chat_sync)
        link_id = self._viewer_link.id
        _SHARED.viewer_links[link_id] = self._viewer_link
        self.destroyed.connect(lambda *_: _SHARED.viewer_links.pop(link_id, None))
        self.browser.setUrl(QUrl("http://127.0.0.1:%d/viewer.html?mode=%s&k=%s&v=%s"
                                 % (port, str(mode).lower(), _SHARED.token, link_id)))
        lay.addWidget(self.browser)
        self.setCentralWidget(central)
        # push-Nachrichten, die vor dem Laden der Seite kommen, warten hier
        self._loaded = False
        self._pending_pushes = []
        self._page.loadFinished.connect(self._on_load_finished)

        # Blickverfolgung über den ganzen Bildschirm: Der Browser bekommt über
        # dem Board-iframe und außerhalb des Fensters keine Mausbewegungen.
        # Qt kennt die Cursorposition aber immer -> regelmäßig an den Viewer geben.
        self._last_mouse = None
        self._last_screen = None
        self._mouse_timer = QTimer(self)
        self._mouse_timer.setInterval(MOUSE_POLL_MS)
        self._mouse_timer.timeout.connect(self._send_mouse)
        self._mouse_timer.start()

        # Plugins auf dem Board (siehe _BoardStream): Sie bleiben am Leben, auch wenn sie nicht
        # zu sehen sind (z. B. ein laufender Timer).
        self._closing = False               # Toolbar beendet sich (aboutToQuit)
        self._board_info = None             # letzte Antwort von boardInfo() im Viewer
        self._board_plugins = {}            # Pfad -> Plugin-Widget
        self._board_current = None          # Pfad des Plugins auf dem Board
        self._board_seq = 0                 # verwirft Abfragen von vor einem Wechsel
        self._board_size = None             # Bildfläche in board/plugin.html (CSS-Pixel)
        self._board_grab = None             # Ziel der gedrückten Maustaste (bekommt auch move/up)
        self._board_host = _BoardHost(self.browser)
        self._board_stream = _BoardStream(self)
        self._board_stream.input.connect(self._on_board_input)
        stream_id = self._board_stream.id
        _SHARED.board_streams[stream_id] = self._board_stream
        self.destroyed.connect(lambda *_: _SHARED.board_streams.pop(stream_id, None))
        self._board_timer = QTimer(self)
        self._board_timer.setInterval(BOARD_POLL_MS)
        self._board_timer.timeout.connect(self._poll_board)
        self._board_timer.start()
        self._board_capture_timer = QTimer(self)
        self._board_capture_timer.setInterval(1000 // BOARD_FPS)
        self._board_capture_timer.timeout.connect(self._capture_board)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._close_board_plugins)

    def _close_board_plugins(self):
        """Beim Beenden: Abfragen anhalten und Plugins des Boards jetzt schließen und löschen.
        Sonst zerstört erst das Aufräumen von Python ihre Webseiten - nach Qt WebEngine - bzw.
        landet eine späte runJavaScript-Antwort bei schon zerstörten Objekten (Absturz beim Beenden)."""
        self._closing = True
        self._board_capture_timer.stop()
        self._board_timer.stop()
        self._mouse_timer.stop()
        for widget in self._board_plugins.values():
            widget.close()
            sip.delete(widget)              # sofort - verzögertes Löschen läuft beim Beenden nicht mehr
        self._board_plugins.clear()

    # --- Plugins auf dem Board (aufgerufen vom Launcher) -----------------------------
    def board_available(self):
        """Board gerade zu sehen? (Fenster offen, breites Layout)"""
        info = self._board_info
        return bool(self._loaded and info and info.get("visible") and self.browser.isVisible()
                    and not self.window().isMinimized())

    def board_plugin(self, path):
        """Widget dieses Plugins auf dem Board (auch wenn gerade nicht zu sehen)."""
        return self._board_plugins.get(path)

    def board_plugins(self):
        return dict(self._board_plugins)

    def show_on_board(self, path, widget=None, title=""):
        """Plugin auf dem Board zeigen. widget: neu erzeugtes Plugin-Widget (ersetzt ein
        früheres desselben Plugins) oder None für das schon vorhandene."""
        old = self._board_plugins.get(path)
        if widget is not None and widget is not old:
            if old is not None:
                self._board_host.stack.removeWidget(old)
                old.close()
                old.deleteLater()
            self._board_plugins[path] = widget
            self._board_host.stack.addWidget(widget)
        widget = self._board_plugins.get(path)
        if widget is None:
            return None
        title = title or os.path.splitext(os.path.basename(path))[0]
        log.info("Board: zeige %s (Board-Lage aus dem Viewer: %s)", os.path.basename(path), self._board_info)
        self._board_host.stack.setCurrentWidget(widget)
        self._board_current = path
        self._board_seq += 1
        self._board_grab = None
        url = "board/plugin.html?s=%s&t=%s&k=%s" % (self._board_stream.id, quote(title), _SHARED.token)
        self._page.runJavaScript("window.showPluginOnBoard && showPluginOnBoard(%s);" % json.dumps(url))
        self._place_board_host()
        return widget

    def hide_board_plugin(self):
        """✕ in board/plugin.html: vom Board nehmen, das Plugin läuft weiter (ein Timer sagt
        trotzdem Bescheid)."""
        self._board_current = None
        self._board_seq += 1
        self._place_board_host()
        self._page.runJavaScript("window.hidePluginFromBoard && hidePluginFromBoard();")

    def _poll_board(self):
        if self._closing or not self._loaded or not self.browser.isVisible():
            return
        seq = self._board_seq
        self._page.runJavaScript("window.boardInfo ? boardInfo() : ''",
                                 lambda raw: self._on_board_info(raw, seq))

    def _on_board_info(self, raw, seq):
        if self._closing:                   # Antwort kam nach dem Beenden - nichts mehr anfassen
            return
        try:
            info = json.loads(raw) if raw else None
        except (TypeError, ValueError):
            info = None
        self._board_info = info
        if seq != self._board_seq:          # inzwischen gewechselt - Antwort ist veraltet
            return
        if self._board_current and info and not info.get("plugin"):
            log.info("Board: Viewer hat anderen Inhalt aufs Board gelegt - Plugin ausgeblendet")
            self._board_current = None
        self._place_board_host()

    def _place_board_host(self):
        """Host verdeckt unter das Board legen, so groß wie die Bildfläche in board/plugin.html.
        Nur dort (sichtbar, im Fenster) rendert das Plugin; sonst ausblenden und keine Bilder."""
        info = self._board_info
        host = self._board_host
        if not (self._board_current and info and info.get("visible") and self.browser.isVisible()):
            if host.isVisible():
                log.info("Board: Plugin aus (Plugin=%s, Board-Lage=%s)", self._board_current, info)
            host.hide()
            self._board_capture_timer.stop()
            return
        zoom = self.browser.zoomFactor()    # CSS-Pixel -> Widget-Pixel
        width, height = self._board_size or (info["w"], info["h"] - BOARD_BAR_PX)
        geometry = (round(info["x"] * zoom), round((info["y"] + BOARD_BAR_PX) * zoom),
                    max(50, round(width * zoom)), max(50, round(height * zoom)))
        if not host.isVisible() or host.geometry().getRect() != geometry:
            log.info("Board: Plugin an %s in %dx%d", geometry, self.browser.width(), self.browser.height())
        host.setGeometry(*geometry)
        host.show()
        if not self._board_capture_timer.isActive():
            self._board_capture_timer.start()

    def _capture_board(self):
        widget = self._board_host.stack.currentWidget()
        if widget is None or not self._board_host.isVisible():
            return
        try:
            image = _capture_widget(widget)
        except _NotReady:
            return                          # gleich noch einmal
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "JPG", BOARD_JPEG_QUALITY)
        self._board_stream.publish(bytes(buffer.data()))

    def _on_board_input(self, event):
        """Eingabe aus board/plugin.html (Qt-Hauptthread)."""
        kind = event.get("type")
        if kind == "close":
            self.hide_board_plugin()
        elif kind == "size":
            try:
                self._board_size = (max(1.0, float(event["w"])), max(1.0, float(event["h"])))
            except (KeyError, TypeError, ValueError):
                return
            self._place_board_host()
        elif kind in ("down", "up", "move", "dbl", "wheel"):
            try:
                self._board_mouse(kind, event)
            except (KeyError, TypeError, ValueError) as error:
                log.warning("Board: Eingabe %s verworfen: %s", event, error)

    def _board_mouse(self, kind, event):
        widget = self._board_host.stack.currentWidget()
        if widget is None or not self._board_current:
            return
        pos = QPoint(int(float(event["x"]) * widget.width()), int(float(event["y"]) * widget.height()))
        if kind in ("down", "dbl") or self._board_grab is None:
            target = self._board_target(widget, pos)
        else:
            target = self._board_grab      # gedrückt: Bewegung/Loslassen ans selbe Ziel
        local = target.mapFrom(widget, pos)
        position, global_pos = QPointF(local), QPointF(target.mapToGlobal(local))
        buttons, mods = _board_buttons(event.get("buttons")), _board_modifiers(event)
        if kind == "wheel":
            angle = QPoint(int(-float(event.get("dx", 0)) * 1.2), int(-float(event.get("dy", 0)) * 1.2))
            QApplication.sendEvent(target, QWheelEvent(position, global_pos, QPoint(), angle, buttons, mods,
                                                       Qt.NoScrollPhase, False))
            return
        button = _BOARD_BUTTONS.get(int(event.get("button", 0)), Qt.LeftButton)
        types = {"down": QMouseEvent.MouseButtonPress, "up": QMouseEvent.MouseButtonRelease,
                 "move": QMouseEvent.MouseMove, "dbl": QMouseEvent.MouseButtonDblClick}
        if kind == "move":
            button = Qt.NoButton
        if kind == "down":
            self._board_grab = target
            target.setFocus(Qt.MouseFocusReason)   # danach tippt man direkt ins Plugin
        QApplication.sendEvent(target, QMouseEvent(types[kind], position, position, global_pos,
                                                   button, buttons, mods))
        if kind == "up":
            self._board_grab = None

    @staticmethod
    def _board_target(widget, pos):
        """Tiefstes Widget an pos; in einer Webansicht deren Zeichenfläche (focusProxy)."""
        child = widget.childAt(pos) or widget
        node = child
        while node is not None and node is not widget:
            if isinstance(node, QWebEngineView):
                return node.focusProxy() or node
            node = node.parentWidget()
        return child

    def on_push(self, data):
        """Von der Toolbar (services.push): Die Figur sagt eine Nachricht, ohne dass der
        Nutzer gefragt hat - z. B. eine Erinnerung oder ein Briefing vom KI-Dienst.
        data: Text (darf [aktionen] enthalten) oder {"text": ..., "view": {...}}."""
        payload = data if isinstance(data, dict) else {"text": str(data or "")}
        if self._loaded:
            self._page.runJavaScript("window.receivePush && receivePush(%s);" % json.dumps(payload))
        else:
            self._pending_pushes.append(payload)

    def _on_chat_sync(self, entry):
        """Chatzeile aus einem Viewer (POST /chat/sync): Die anderen Viewer zeigen sie auch. Ist es
        die Antwort auf eine Frage aus diesem Viewer, kommt er nach vorne (Popup/Fenster)."""
        if entry.get("own"):
            if entry.get("reveal"):
                reveal_in_toolbar(self)
        elif self._loaded and entry.get("text"):
            self._page.runJavaScript("window.receiveChatSync && receiveChatSync(%s);"
                                     % json.dumps({"sender": entry["sender"], "text": entry["text"]}))

    def _on_load_finished(self, ok):
        self._loaded = ok
        if ok:
            with _lock:
                log_entries = list(_SHARED.chat_log)
            if log_entries:                 # bisheriger Chat aus dem anderen Viewer
                self._page.runJavaScript("window.restoreChat && restoreChat(%s);" % json.dumps(log_entries))
            pending, self._pending_pushes = self._pending_pushes, []
            for payload in pending:
                self.on_push(payload)

    def _send_mouse(self):
        if not self.browser.isVisible():
            return
        self._send_screen_info()
        pos = self.browser.mapFromGlobal(QCursor.pos())   # Fensterkoordinaten, auch negativ
        xy = (pos.x(), pos.y())
        if xy != self._last_mouse:
            self._last_mouse = xy
            self._page.runJavaScript(
                "window.setExternalMouse && setExternalMouse(%d, %d);" % xy)

    def _send_screen_info(self):
        """Lage des Viewers auf dem Bildschirm an den Viewer geben (für die
        Blickmitte: Bildschirmmitte und Kalibrierung). Nur bei Änderung."""
        origin = self.browser.mapToGlobal(QPoint(0, 0))
        center = self.browser.mapToGlobal(self.browser.rect().center())
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        g = screen.availableGeometry()                     # ohne Taskleiste
        info = (origin.x(), origin.y(), g.x(), g.y(), g.width(), g.height())
        if info != self._last_screen:
            self._last_screen = info
            self._page.runJavaScript(
                "window.setScreenInfo && setScreenInfo(%d, %d, %d, %d, %d, %d);" % info)
