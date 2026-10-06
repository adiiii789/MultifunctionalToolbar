# =============================================================================
# Befehle für BUTTON_HTML (onclick & <script>)
# -----------------------------------------------------------------------------
# Im onclick steht normales JavaScript; mehrere Befehle mit ; trennen.
# Dateinamen in EINFACHEN Anführungszeichen, da onclick="..." schon doppelte nutzt.
# Definiert in tray_launcher.py -> CARD_WRAPPER_HTML (Python-Seite: ExplorerBridge).
# Nur verfügbar mit HTML_EXPLORER = True (Standard).
#
# --- Plugin öffnen -----------------------------------------------------------
#   openPlugin()                       eigene Plugin-Datei öffnen
#   openPlugin('Timer.py')             anderes Plugin, relativ zum Ordner dieser Datei
#   openPlugin('Ordner/Timer.py')      relativer Pfad mit Unterordner
#   openPlugin('C:/Pfad/Plugin.py')    absoluter Pfad
#   -> Datei existiert nicht: passiert nichts. Wie geöffnet wird, bestimmt RUN_AS
#      des Ziel-Plugins.
#
# --- Python in DIESER Datei aufrufen ----------------------------------------
#   pluginCall('methode', {schluessel: wert}, callback)
#     methode   : beliebiger Text, geht an handle_call()
#     argumente : JS-Objekt, kommt in Python als dict an (optional)
#     callback  : bekommt die Antwort als JSON-TEXT -> JSON.parse() (optional)
#   Antwortformat: {"ok": true, "result": ...}  bzw.  {"ok": false, "error": "..."}
#   Benötigt in dieser Datei:
#       def handle_call(method, args):
#           if method == "zaehlen":
#               return {"wert": args.get("x", 0) + 1}
#   Hinweise: Datei muss im scripts-Ordner liegen. Das Modul bleibt geladen,
#   globale Variablen behalten ihren Wert zwischen Aufrufen.
#   Beispiel:
#       <button onclick="pluginCall('zaehlen', {x: 5}, r => {
#           const a = JSON.parse(r); if (a.ok) this.textContent = a.result.wert;
#       })">5</button>
#
# --- Mediensteuerung (aus services.py; ohne die Datei wirkungslos) ----------
#   media.playPause()  media.next()  media.prev()  media.stop()
#   media.mute()       media.volUp() media.volDown()
#   media.getTheme(t => ...)           liefert "dark" oder "light"
#
# --- Werte zum Lesen --------------------------------------------------------
#   toolbarMode                        "popup" oder "window"
#   pluginPath                         Pfad dieser Plugin-Datei
#
# --- Links ------------------------------------------------------------------
#   <a href="https://...">             öffnet als Tab im Hauptfenster
#
# --- Längerer Code ----------------------------------------------------------
#   Lieber in einen <script>-Block im BUTTON_HTML und im onclick nur aufrufen:
#       <script>
#         function klick(btn) {
#           pluginCall('zaehlen', {x: 1}, r => btn.textContent = JSON.parse(r).result.wert);
#         }
#       </script>
#       <button onclick="klick(this)">0</button>
#
#   Mehrere Befehle:  onclick="media.playPause(); openPlugin('Musik.py')"
# =============================================================================

# --- Plugin-Parameter (neues System) ---
NAME = "Vorlage Plugin mit Button"
ICON = ""
PINNED = False # True oder 1,2,... für prio
ALLOW_POPUP = False
ALLOW_WINDOW = False
HTML_BUTTON = True
BUTTON_HEIGHT = 234 # delete = auto
OPACITY = 0.5 # default 1

RUN_AS = "process" # default widget, "browser" possible
# ----------------------------------------
import os
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView

WINDOW_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body { font-family: system-ui; margin: 16px; }
</style></head><body>
  <h2>✨ Mein Plugin (__MODE__)</h2>
  <p>Inhalt hier…</p>
</body></html>
"""

BUTTON_HTML = """
<div style="display:flex;align-items:center;justify-content:center;height:100%;gap:10px;
            font-family:system-ui;color:inherit;">
  <span>Mein Plugin</span>
  <button onclick="media.playPause()" style="padding:4px 12px;border-radius:8px;border:none;cursor:pointer;">⏯</button>
</div>
"""

POPUP_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  body { font-family: system-ui; margin: 10px; font-size: 13px; }
</style></head><body>
  <h3>✨ Mein Plugin</h3>
  <p>Kompakte Popup-Ansicht…</p>
</body></html>
"""
# ----------------------------------------
class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        super().__init__()
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(central)
        if mode == "Window":
            self.html = WINDOW_HTML
        else:  # Popup
            self.html = POPUP_HTML
        html = self.html.replace("__MODE__", mode)
        base = QUrl.fromLocalFile(os.path.dirname(os.path.abspath(__file__)) + os.sep)
        self.view.setHtml(html, baseUrl=base)
        lay.addWidget(self.view)
        self.setCentralWidget(central)
