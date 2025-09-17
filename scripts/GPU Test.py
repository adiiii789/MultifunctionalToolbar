import sys
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView

class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("QtWebEngine Hardware Acc Test")
        self.resize(900, 700)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)
        self.browser.setFocus()

        # Lade die Spezial-URL zum Hardware-Test
        self.browser.setUrl(QUrl("chrome://gpu"))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PluginWidget()
    w.show()
    sys.exit(app.exec_())
