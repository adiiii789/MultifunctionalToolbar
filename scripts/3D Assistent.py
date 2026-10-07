# --- Plugin-Parameter (neues System) ---
NAME = "Assistent"
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
#   - Assets liegen in scripts/_a3d/ (Unterstrich = in der Toolbar
#     ausgeblendet). Modell: scripts/_a3d/models/AppearanceMikuBlender.glb
#   - Fehlt das Modell, zeigt der Viewer einen Hinweis statt schwarzem Fenster.

import atexit
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import types
import urllib.error
import urllib.request
from functools import partial
from urllib.parse import urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QTimer, QUrl, QPoint
from PyQt5.QtGui import QCursor, QGuiApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage

def _find_asset_dir():
    """Sucht den Ordner _a3d (mit viewer.html) - egal, ob das Plugin direkt in
    scripts/ oder in einem Unterordner davon liegt."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "_a3d"),                 # scripts/_a3d (Plugin in scripts/)
        os.path.join(here, "..", "_a3d"),           # Plugin in scripts/<Ordner>/
        os.path.join(here, "..", "..", "_a3d"),
        os.path.join(os.getcwd(), "scripts", "_a3d"),
    ]
    for cand in candidates:
        if os.path.isfile(os.path.join(cand, "viewer.html")):
            return os.path.abspath(cand)
    print("[3D Assistent] _a3d/viewer.html nicht gefunden. Gesucht in:\n  " +
          "\n  ".join(os.path.abspath(c) for c in candidates))
    return os.path.abspath(candidates[0])


ASSET_DIR = _find_asset_dir()
MOUSE_POLL_MS = 33   # Mausposition ~30x pro Sekunde an den Viewer schicken

# Vom Viewer beschreibbare Dateien (POST): nur diese, nur JSON, klein.
# Nötig, weil der Server bei jedem Start einen neuen Port bekommt - damit
# wechselt die Herkunft der Seite und der localStorage des Browsers ist weg.
# Blick-Kalibrierung: eine Datei pro Modus, damit Popup und Fenster unabhängig sind.
# panel_state.json: welche Abschnitte im Panel eingeklappt sind.
# stations.json: eigene Stationen (Punkte, zu denen die Figur läuft).
# viewer_settings.json: Stimme an/aus, Lautstärke.
WRITABLE_JSON = {"/look_calibration_popup.json", "/look_calibration_window.json",
                 "/panel_state.json", "/stations.json", "/viewer_settings.json"}
MAX_POST_BYTES = 8192

# Die Toolbar lädt dieses Modul bei jedem Öffnen des Fensters frisch. Asset-Server
# und TTS-Dienst sollen aber nur EINMAL pro Toolbar-Prozess laufen -> gemeinsamer
# Speicher, der das Neuladen überlebt.
_SHARED = sys.modules.setdefault("_a3d_shared_state", types.ModuleType("_a3d_shared_state"))
if not hasattr(_SHARED, "lock"):
    _SHARED.lock = threading.Lock()
    _SHARED.server = None
    _SHARED.port = None
    _SHARED.tts = None
_lock = _SHARED.lock


# =============================================================================
# Lokaler TTS (Miku-Stimme): eigener Dienst in scripts/_a3d_tts
# (eigene Python-Umgebung mit Torch/RVC, eingerichtet mit setup_tts.bat).
# Der Viewer schickt Text an POST /tts dieses Asset-Servers, wir reichen ihn an
# den Dienst weiter und legen die WAV in _a3d/tts/ ab.
# =============================================================================
TTS_DIR = os.path.abspath(os.path.join(ASSET_DIR, "..", "_a3d_tts"))
TTS_ENABLED = True         # False = Stimme komplett aus (Dienst wird nie gestartet)
TTS_AUTOSTART = False      # True = Dienst schon beim Öffnen laden; False = erst beim ersten Sprechen
TTS_DEVICE = "auto"        # "auto" = DirectML (AMD-GPU), falls installiert, sonst CPU; "cpu"; "dml"
TTS_CACHE_FILES = 30       # so viele zuletzt gesprochene Sätze bleiben in _a3d/tts/ (gleicher Satz = sofort);
                           # 0 = nichts aufheben (jede WAV wird kurz nach dem Abspielen gelöscht)
TTS_CACHE_DAYS = 7         # unabhängig davon: älter als so viele Tage -> löschen
TTS_TIMEOUT = 180          # Sekunden pro Satz


class TtsService:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.port = None
        self.device = TTS_DEVICE
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost ohne Proxy

    @staticmethod
    def python_exe():
        sub = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
        return os.path.join(TTS_DIR, "venv", *sub)

    def installed(self):
        return (os.path.isfile(self.python_exe())
                and os.path.isfile(os.path.join(TTS_DIR, "miku_tts_server.py"))
                and os.path.isdir(os.path.join(TTS_DIR, "models")))

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure_started(self):
        """Dienst starten, falls eingerichtet und noch nicht gestartet. Lädt ~10-30 s."""
        with self.lock:
            if not TTS_ENABLED or not self.installed():
                return False
            if self.running():
                return True
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
            s.close()
            os.makedirs(os.path.join(TTS_DIR, "logs"), exist_ok=True)
            log = open(os.path.join(TTS_DIR, "logs", "dienst_start.log"), "w", encoding="utf-8")
            self.proc = subprocess.Popen(
                [self.python_exe(), "miku_tts_server.py", "--port", str(self.port),
                 "--device", self.device, "--parent-pid", str(os.getpid())],
                cwd=TTS_DIR, stdout=log, stderr=subprocess.STDOUT,
                creationflags=0x08000000 if os.name == "nt" else 0)   # CREATE_NO_WINDOW
            print(f"[3D Assistent] TTS-Dienst gestartet (Port {self.port}, Gerät {self.device})")
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

    def status(self, start=True):
        if not TTS_ENABLED:
            return {"state": "disabled", "message": "Im Plugin ausgeschaltet (TTS_ENABLED)"}
        if not self.installed():
            return {"state": "missing", "message": "Nicht eingerichtet: scripts/_a3d_tts/setup_tts.bat ausführen"}
        if not self.running():
            if not start:
                return {"state": "idle", "message": "Startet beim ersten Sprechen"}
            self.ensure_started()
        if not self.running():
            return {"state": "error", "message": "Dienst beendet - siehe scripts/_a3d_tts/logs/"}
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

    def _post(self, text):
        req = urllib.request.Request(self._url("/tts"), data=json.dumps({"text": text}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        return self._opener.open(req, timeout=TTS_TIMEOUT).read()

    def synthesize(self, text):
        """Text -> WAV-Bytes. Scheitert DirectML, wird einmal auf CPU umgeschaltet."""
        st = self._wait_ready()
        if st["state"] != "ready":
            raise RuntimeError(st.get("message", "TTS nicht bereit"))
        try:
            return self._post(text)
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
                    return self._post(text)
            raise RuntimeError(info.get("error") or "TTS-Fehler %s" % e.code)


def tts_service():
    if _SHARED.tts is None:
        _SHARED.tts = TtsService()
        atexit.register(_SHARED.tts.stop)
    return _SHARED.tts


def _tts_to_file(text):
    """Erzeugt (oder findet im Cache) die WAV zum Text -> Pfad relativ zu _a3d/."""
    cfg = os.path.join(TTS_DIR, "tts_config.json")
    stamp = str(os.path.getmtime(cfg)) if os.path.isfile(cfg) else ""
    name = hashlib.sha1((stamp + "\n" + text).encode("utf-8")).hexdigest()[:20] + ".wav"
    out_dir = os.path.join(ASSET_DIR, "tts")
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, name)
    if not os.path.isfile(target):
        data = tts_service().synthesize(text)
        tmp = target + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    else:
        os.utime(target)                              # zuletzt benutzt
    cleanup_tts_cache()
    return "tts/" + name


TTS_PLAY_GRACE = 120       # s: so lange bleibt eine WAV mindestens liegen (Viewer lädt/spielt sie gerade)


def cleanup_tts_cache():
    """_a3d/tts/ aufräumen: nur die TTS_CACHE_FILES zuletzt benutzten Sätze behalten,
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
            print(f"[3D Assistent] Aufräumen von _a3d/tts fehlgeschlagen: {e}")
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

    def do_GET(self):
        if urlparse(self.path).path == "/tts_status":
            # Statusabfrage startet den Dienst nur, wenn TTS_AUTOSTART an ist
            self._send_json(200, tts_service().status(start=TTS_AUTOSTART))
            return
        super().do_GET()

    def _do_tts(self):
        """POST /tts {"text": "..."} -> {"url": "tts/<hash>.wav"}"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_POST_BYTES:
                raise ValueError("Größe")
            text = str(json.loads(self.rfile.read(length).decode("utf-8")).get("text", "")).strip()
            if not text:
                raise ValueError("kein Text")
        except Exception as e:
            self._send_json(400, {"error": str(e)})
            return
        try:
            self._send_json(200, {"url": _tts_to_file(text)})
        except Exception as e:
            print(f"[3D Assistent] TTS fehlgeschlagen: {e}")
            self._send_json(503, {"error": str(e)})

    def do_POST(self):
        """Speichert Einstellungen des Viewers (z. B. Blick-Kalibrierung) als
        JSON-Datei in _a3d/. Nur die Pfade aus WRITABLE_JSON sind erlaubt.
        Außerdem: POST /tts (Text -> Sprachausgabe, siehe oben)."""
        path = urlparse(self.path).path
        if path == "/tts":
            self._do_tts()
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


class _LoggingPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f"[3D Assistent JS] {message} (Zeile {line})")


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
        self.browser.setUrl(QUrl(
            "http://127.0.0.1:%d/viewer.html?mode=%s" % (port, str(mode).lower())))
        lay.addWidget(self.browser)
        self.setCentralWidget(central)

        # Blickverfolgung über den ganzen Bildschirm: Der Browser bekommt über
        # dem Board-iframe und außerhalb des Fensters keine Mausbewegungen.
        # Qt kennt die Cursorposition aber immer -> regelmäßig an den Viewer geben.
        self._last_mouse = None
        self._last_screen = None
        self._mouse_timer = QTimer(self)
        self._mouse_timer.setInterval(MOUSE_POLL_MS)
        self._mouse_timer.timeout.connect(self._send_mouse)
        self._mouse_timer.start()

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
