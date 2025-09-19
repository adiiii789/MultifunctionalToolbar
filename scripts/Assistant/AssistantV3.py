import sys
import os

from PyQt5 import QtWebEngineWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings


class WebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"JS-LOG (Level {level}): {message} (Line: {lineNumber}, Source: {sourceID})")

class PluginWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OBJ & MTL Viewer mit Three.js")
        self.resize(900, 700)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebGLEnabled, True)
        self.browser.settings().setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        self.browser.page().setDevToolsPage(QtWebEngineWidgets.QWebEnginePage())
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        base_path = os.path.abspath(os.path.dirname(__file__))
        #html_path = os.path.join(base_path, "viewer.html")
        #self.browser.setUrl(QUrl.fromLocalFile(html_path))

        page = WebEnginePage(self.browser)
        self.browser.setPage(page)

        self.browser.setUrl(QUrl("http://localhost:63342/MultifunctionalToolbar/scripts/Assistant/viewerV2.html?_ijt"
                                 "=nofrh9eoqr6kg2e48942flslqq&_ij_reload=RELOAD_ON_SAVE"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PluginWidget()
    window.show()
    sys.exit(app.exec_())
