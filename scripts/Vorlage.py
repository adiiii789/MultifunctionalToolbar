# --- Plugin-Parameter (neues System) ---
NAME = "Vorlage Plugin mit Button"
ICON = ""
DESCRIPTION = "Vorlage für neue Plugins mit allen Parametern." # ein Satz: was das Plugin macht
                                                               # (der KI-Assistent listet Plugins damit auf)
PINNED = False # True oder 1,2,... für prio
ALLOW_POPUP = False
ALLOW_WINDOW = False
HTML_BUTTON = True
BUTTON_HEIGHT = 234 # delete = auto
OPACITY = 0.5 # default 1

RUN_AS = "process" # default widget, "browser" possible
# ----------------------------------------

# --- KI-Assistent (optional, siehe plugin_tools.py) ---------------------
# Werkzeuge, die der Assistent aufrufen darf - einkommentieren und anpassen.
# Ohne "window": assistant_call() auf Modul-Ebene (unten), das Fenster muss nicht offen sein.
# Mit "window": True: PluginWidget.assistant_call(self, tool, args) - der Launcher öffnet das
# Fenster bei Bedarf als Tab (nicht mit RUN_AS = "process"). Beschreibungen am besten Englisch.
# "show": True zeigt das Plugin danach als Tab im Hauptfenster (für Änderungen, nicht für Abfragen).
# ASSISTANT_TOOLS = {
#     "beispiel_notiz": {
#         "description": "Saves a short note in my plugin.",
#         "parameters": {"text": {"type": "string", "description": "The note"}},
#         "required": ["text"],
#     },
# }
#
# def assistant_call(tool, args):
#     if tool == "beispiel_notiz":
#         return f"Saved: {args['text']}"          # Text oder JSON-taugliches Objekt
#     raise ValueError(f"Unknown tool: {tool}")    # Fehlermeldung geht ans Modell
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
