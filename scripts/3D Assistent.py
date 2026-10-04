# --- Plugin-Parameter (neues System) ---
NAME = "3D Assistent"
ICON = "🧍"
POPUP_WIDTH = 0.45   # Popup beim Öffnen auf 45 % der Bildschirmbreite verbreitern
POPUP_HEIGHT = 0.6   # ... und 60 % der Höhe (Ecke am Tray bleibt stehen)
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

import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor
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

_server = None
_port = None
_lock = threading.Lock()


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # kein Konsolen-Spam pro Request


def ensure_server():
    """Startet den Asset-Server einmalig (Daemon-Thread, nur localhost).

    Port 0 = das Betriebssystem wählt einen freien Port — keine Kollisionen.
    Der Server lebt, solange die Toolbar läuft (Modul wird gecacht)."""
    global _server, _port
    with _lock:
        if _server is not None:
            return _port
        handler = partial(_QuietHandler, directory=ASSET_DIR)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        srv.daemon_threads = True
        _port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        _server = srv
        return _port


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
        port = ensure_server()
        self.browser.setUrl(QUrl(
            "http://127.0.0.1:%d/viewer.html?mode=%s" % (port, str(mode).lower())))
        lay.addWidget(self.browser)
        self.setCentralWidget(central)

        # Blickverfolgung über den ganzen Bildschirm: Der Browser bekommt über
        # dem Board-iframe und außerhalb des Fensters keine Mausbewegungen.
        # Qt kennt die Cursorposition aber immer -> regelmäßig an den Viewer geben.
        self._last_mouse = None
        self._mouse_timer = QTimer(self)
        self._mouse_timer.setInterval(MOUSE_POLL_MS)
        self._mouse_timer.timeout.connect(self._send_mouse)
        self._mouse_timer.start()

    def _send_mouse(self):
        if not self.browser.isVisible():
            return
        pos = self.browser.mapFromGlobal(QCursor.pos())   # Fensterkoordinaten, auch negativ
        xy = (pos.x(), pos.y())
        if xy != self._last_mouse:
            self._last_mouse = xy
            self._page.runJavaScript(
                "window.setExternalMouse && setExternalMouse(%d, %d);" % xy)