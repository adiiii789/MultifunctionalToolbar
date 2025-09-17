#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import sys
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView

class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("TEMP")
        self.resize(700, 520)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)
        self.browser.setFocus()  # wichtig für Tastatursteuerung

        # The HTML is embedded exactly as provided by you (no changes).
        self.html = """
        
        """

        # Load the HTML into the QWebEngineView
        self.browser.setHtml(self.html)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PluginWidget()
    w.show()
    sys.exit(app.exec_())
