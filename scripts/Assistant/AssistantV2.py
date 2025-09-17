import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

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
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        base_path = os.path.abspath(os.path.dirname(__file__))
        html_path = os.path.join(base_path, "viewer.html")
        self.browser.setUrl(QUrl.fromLocalFile(html_path))

        page = WebEnginePage(self.browser)
        self.browser.setPage(page)

        self.browser.setUrl(QUrl("http://localhost:63342/MultifunctionalToolbar/scripts/Assistant/viewer.html?_ijt=r6k1lkdi0ebg1pdq3cffnkcjb5&_ij_reload=RELOAD_ON_SAVE"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PluginWidget()
    window.show()
    sys.exit(app.exec_())
