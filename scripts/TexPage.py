from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import sys

# --- KONFIGURATION ---

# Die URL, die im "Window"-Modus (Hauptfenster) geladen wird
MAIN_WINDOW_URL = "https://www.texpage.com"  # <--- HIER DEINE WEBSITE EINTRAGEN!

# Der HTML-Inhalt, der im "Popup"-Modus geladen wird
POPUP_HTML_CONTENT = """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Plugin Hinweis</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background-color: #2E2E2E; /* dunkelgrau */
            font-family: Arial, sans-serif;
        }

        h1 {
            color: #FFFFFF; /* weiß */
            font-weight: bold;
            font-size: 2rem;
            text-align: center;
        }
    </style>
</head>
<body>
    <h1>Use this Plugin in the Main Window</h1>
</body>
</html>"""


# ---------------------

class PluginWidget(QMainWindow):
    """
    Ein minimalistisches Plugin, das basierend auf dem Modus entweder eine URL
    oder einen statischen HTML-Inhalt lädt.
    """

    def __init__(self, mode="Window", parent=None):
        super().__init__(parent)

        self._mode = mode

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central_widget)

        if self._mode == "Window":
            self.setWindowTitle("Web Plugin - Hauptfenster")
            self.resize(1000, 800)
            # Im "Window"-Modus: Lade die externe Website
            self.browser.setUrl(QUrl(MAIN_WINDOW_URL))

        elif self._mode == "Popup":
            self.setWindowTitle("Web Plugin - Hinweis")
            self.resize(500, 300)
            # Im "Popup"-Modus: Lade den statischen HTML-Inhalt
            self.browser.setHtml(POPUP_HTML_CONTENT)

        else:
            # Fallback für unbekannten Modus
            self.setWindowTitle("Web Plugin - Fehler")
            self.resize(400, 200)
            self.browser.setHtml("<h1>Fehler: Unbekannter Modus.</h1>")


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Beispiel 1: Startet im Hauptfenster (lädt die URL)
    window_mode_plugin = PluginWidget(mode="Window")
    window_mode_plugin.show()

    # Beispiel 2: Startet im Popup (lädt den HTML-Hinweis)
    # popup_mode_plugin = PluginWidget(mode="Popup")
    # popup_mode_plugin.move(100, 100) # Optional: Position anpassen
    # popup_mode_plugin.show()

    sys.exit(app.exec_())