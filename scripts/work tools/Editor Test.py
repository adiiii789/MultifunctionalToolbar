# Test-Artefakt des Plugin-Editors — bewusst in beiden Ansichten ausgeblendet
NAME = "Editor Test"
ICON = "🧪"
HTML_BUTTON = True
BUTTON_HEIGHT = 70
OPACITY = 0.9
ALLOW_POPUP = False
ALLOW_WINDOW = False

BUTTON_HTML = """
<div>Test-Card</div>
"""

WINDOW_HTML = """
<!DOCTYPE html>
<html><body><h2>Fenster (__MODE__)</h2></body></html>
"""

POPUP_HTML = """
<!DOCTYPE html>
<html><body><h3>Popup kompakt</h3></body></html>
"""

import os
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView


class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        super().__init__()
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(central)
        src = POPUP_HTML if str(mode).lower() == "popup" else WINDOW_HTML
        html = src.replace("__MODE__", mode)
        base = QUrl.fromLocalFile(os.path.dirname(os.path.abspath(__file__)) + os.sep)
        self.view.setHtml(html, baseUrl=base)
        lay.addWidget(self.view)
        self.setCentralWidget(central)
