import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage

PORT = 8000

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
        self.browser.page().setDevToolsPage(QWebEnginePage())
        layout.addWidget(self.browser)
        self.setCentralWidget(central)
        page = WebEnginePage(self.browser)
        self.browser.setPage(page)
        self.browser.setUrl(QUrl(f"http://localhost:{PORT}/viewerV2.html"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PluginWidget()
    window.show()
    sys.exit(app.exec_())
