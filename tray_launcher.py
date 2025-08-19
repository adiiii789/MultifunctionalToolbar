import sys
import os
import subprocess
import importlib.util
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QHBoxLayout, QLabel,
    QStackedWidget, QMessageBox
)
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, QPoint, QFileSystemWatcher
from screeninfo import get_monitors

import ctypes

# Optional: HTML-Ansicht (falls PyQtWebEngine installiert ist)
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False

# ------------------------------
# Stylesheets
# ------------------------------
# Dark Mode Stylesheet
dark_mode_stylesheet = """
    QWidget {
        background-color: #2E2E2E;
        color: #FFFFFF;
    }
"""

# Light Mode Stylesheet
light_mode_stylesheet = """
    QWidget {
        background-color: #FFFFFF;
        color: #000000;
    }
"""


# ------------------------------
# Hilfsfunktionen
# ------------------------------

def ensure_sample_plugin(script_root: str):
    """Erzeugt ein Beispiel-Plugin, wenn der Ordner leer ist."""
    if not os.path.exists(script_root):
        os.makedirs(script_root, exist_ok=True)

    entries = [e for e in os.listdir(script_root) if not e.startswith("_")]
    if entries:
        return  # Schon Inhalte vorhanden

    # Beispiel-Plugin schreiben
    sample_path = os.path.join(script_root, "timer_plugin.py")
    sample_code = r'''from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtCore import QTimer

class PluginWidget(QWidget):
    """Ein simples Timer-Plugin als Beispiel.
    Start/Stop-Knöpfe und Sekundenanzeige.
    """
    def __init__(self):
        super().__init__()
        self.setObjectName("TimerPlugin")
        layout = QVBoxLayout(self)

        title = QLabel("⏱️ Timer-Plugin")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title)

        self.label = QLabel("0 s")
        self.label.setStyleSheet("font-size: 24px;")
        layout.addWidget(self.label)

        btn_row = QHBoxLayout()
        start_btn = QPushButton("Start")
        stop_btn = QPushButton("Stop")
        reset_btn = QPushButton("Reset")
        btn_row.addWidget(start_btn)
        btn_row.addWidget(stop_btn)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_time)
        self.seconds = 0

        start_btn.clicked.connect(self.timer.start)
        stop_btn.clicked.connect(self.timer.stop)
        reset_btn.clicked.connect(self.reset)

    def update_time(self):
        self.seconds += 1
        self.label.setText(f"{self.seconds} s")

    def reset(self):
        self.seconds = 0
        self.label.setText("0 s")
'''
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write(sample_code)

    # Beispiel-HTML-Plugin anlegen (falls WebEngine verfügbar)
    html_dir = os.path.join(script_root, "html_timer")
    os.makedirs(html_dir, exist_ok=True)
    html_index = os.path.join(html_dir, "index.html")
    html_code = r'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>HTML Timer</title>
<style>
  body { font-family: system-ui, Arial, sans-serif; margin: 16px; }
  h1 { font-size: 20px; }
  .time { font-size: 32px; margin: 12px 0; }
  button { padding: 8px 12px; margin-right: 8px; }
</style>
</head>
<body>
  <h1>⏱️ HTML Timer (Demo)</h1>
  <div class="time" id="t">0 s</div>
  <button onclick="start()">Start</button>
  <button onclick="stop()">Stop</button>
  <button onclick="reset()">Reset</button>
  <script>
    let sec = 0; let itv = null;
    function tick(){ sec++; document.getElementById('t').textContent = sec + ' s'; }
    function start(){ if(!itv) itv = setInterval(tick, 1000); }
    function stop(){ if(itv){ clearInterval(itv); itv = null; } }
    function reset(){ sec = 0; document.getElementById('t').textContent = '0 s'; }
  </script>
</body>
</html>'''
    with open(html_index, "w", encoding="utf-8") as f:
        f.write(html_code)


# ------------------------------
# ButtonContentMixin
# ------------------------------
class ButtonContentMixin:
    SCRIPT_FOLDER = "scripts"

    def init_button_state(self):
        self.current_path = os.path.abspath(self.SCRIPT_FOLDER)
        ensure_sample_plugin(self.current_path)

        if not os.path.exists(self.current_path):
            os.makedirs(self.current_path)

        # QFileSystemWatcher für Änderungen im aktuellen Verzeichnis
        self.watcher = QFileSystemWatcher()
        self.watcher.addPath(self.current_path)
        self.watcher.directoryChanged.connect(self.on_directory_changed)

        # Optional: ein Loader-Callback (vom MainWindow gesetzt)
        self.plugin_loader = None

    def set_plugin_loader(self, loader_callable):
        self.plugin_loader = loader_callable

    def on_directory_changed(self, path):
        # Aktuelle Buttons aktualisieren, wenn sich etwas im Ordner ändert
        self.add_buttons(self.layout)

    def add_buttons(self, layout):
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        # watcher an neuen Pfad anpassen
        if hasattr(self, "watcher"):
            paths = self.watcher.directories()
            if paths and paths[0] != self.current_path:
                self.watcher.removePaths(paths)
                self.watcher.addPath(self.current_path)

        if self.current_path != os.path.abspath(self.SCRIPT_FOLDER):
            back_button = QPushButton("← Zurück")
            back_button.clicked.connect(self.go_back)
            back_button.setObjectName("back_button")
            layout.addWidget(back_button)

        entries = sorted(os.listdir(self.current_path))
        for entry in entries:
            if entry.startswith("_"):
                continue  # Alles mit "_" ignorieren

            full_path = os.path.join(self.current_path, entry)

            if os.path.isdir(full_path):
                button = QPushButton(entry)
                button.clicked.connect(lambda _, p=full_path: self.enter_directory(p))
                button.setProperty("entry_type", "folder")
            elif entry.endswith(".py") or entry.endswith(".html"):
                # Dateiname ohne .py anzeigen
                display_name = entry[:-3] if entry.endswith(".py") else entry
                button = QPushButton(display_name)
                button.clicked.connect(lambda _, p=full_path: self.run_script(p))
                button.setProperty("entry_type", "file")
            else:
                continue

            button.setMinimumHeight(60)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(button)

        self.update_button_styles(layout)

    def enter_directory(self, path):
        self.current_path = path
        self.add_buttons(self.layout)

    def go_back(self):
        parent = os.path.dirname(self.current_path)
        root = os.path.abspath(self.SCRIPT_FOLDER)
        if os.path.commonpath([parent, root]) == root:
            self.current_path = parent
            self.add_buttons(self.layout)

    def run_script(self, path):
        try:
            if callable(getattr(self, "plugin_loader", None)):
                self.plugin_loader(path, source_widget=self)
                # Explorer-Button sichtbar machen
                self.back_to_explorer_btn.show()
            else:
                if path.endswith('.py'):
                    subprocess.Popen([sys.executable, path])
                elif path.endswith('.html'):
                    import webbrowser
                    webbrowser.open('file://' + os.path.abspath(path))
        except Exception as e:
            #print(f"Fehler beim Starten/Laden von {path}: {e}")
            pass

    def update_button_styles(self, layout):
        dark_mode = getattr(self, "dark_mode", True)
        for i in range(layout.count()):
            button = layout.itemAt(i).widget()
            if isinstance(button, QPushButton):
                if button.objectName() == "back_button":
                    button.setMinimumHeight(40)
                    button.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {'#666666' if dark_mode else '#BBBBBB'};
                            color: {'#FFFFFF' if dark_mode else '#000000'};
                            font-weight: bold;
                        }}
                        QPushButton:hover {{
                            background-color: {'#777777' if dark_mode else '#CCCCCC'};
                        }}
                    """)
                else:
                    entry_type = button.property("entry_type")
                    if entry_type == "folder":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A4A6A' if dark_mode else '#c2d1ff'};
                                color: {'#FFFFFF' if dark_mode else '#000000'};
                            }}
                            QPushButton:hover {{
                                background-color: {'#4B5B6B' if dark_mode else '#a1b8ff'};
                            }}
                        """)
                    elif entry_type == "file":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A3A3A' if dark_mode else '#EEEEEE'};
                                color: {'#FFFFFF' if dark_mode else '#000000'};
                            }}
                            QPushButton:hover {{
                                background-color: {'#505050' if dark_mode else '#CCCCCC'};
                            }}
                        """)

# ------------------------------
# Custom Title Bar
# ------------------------------
class CustomTitleBar(QWidget):
    def __init__(self, parent, title=""):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: transparent")

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold")

        self.minimize_button = QPushButton("▁")
        self.minimize_button.setFixedSize(30, 28)
        self.minimize_button.setStyleSheet(self.button_style())
        self.minimize_button.clicked.connect(self.parent.showMinimized)

        self.maximize_button = QPushButton("▢")
        self.maximize_button.setFixedSize(30, 28)
        self.maximize_button.setStyleSheet(self.button_style())
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)

        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(30, 28)
        self.close_button.setStyleSheet(self.button_style(close=True))
        self.close_button.clicked.connect(parent.close)

        self.layout.addWidget(self.title_label)
        self.layout.addStretch()
        self.layout.addWidget(self.minimize_button)
        self.layout.addWidget(self.maximize_button)
        self.layout.addWidget(self.close_button)

        self.old_pos = None

    def button_style(self, close=False):
        base = """
            QPushButton {
                border: none;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: %s;
            }
        """
        if close:
            hover_color = "#E81123"  # Rotes Hover für Close
        else:
            hover_color = "#CCCCCC"  # Graues Hover für andere Buttons
        return base % hover_color

    def toggle_maximize_restore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.maximize_button.setText("▢")
        else:
            self.parent.showMaximized()
            self.maximize_button.setText("❐")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.parent.move(self.parent.pos() + delta)
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None


# ------------------------------
# Plugin-Container Widgets
# ------------------------------
class HtmlPluginContainer(QWidget):
    """Zeigt eine lokale HTML-Datei im eingebetteten View, wenn verfügbar."""
    def __init__(self, html_path: str):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel(f"HTML: {os.path.basename(html_path)}")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        if WEBENGINE_AVAILABLE:
            view = QWebEngineView(self)
            view.load(Qt.QUrl.fromLocalFile(os.path.abspath(html_path)))
            layout.addWidget(view)
        else:
            msg = QLabel("PyQtWebEngine ist nicht installiert. Öffne die Datei extern.")
            layout.addWidget(msg)
            open_btn = QPushButton("Im Standardbrowser öffnen")
            layout.addWidget(open_btn)
            def _open():
                import webbrowser
                webbrowser.open('file://' + os.path.abspath(html_path))
            open_btn.clicked.connect(_open)


# ------------------------------
# PopupWindow
# ------------------------------
class PopupWindow(ButtonContentMixin, QWidget):
    def __init__(self):
        super().__init__()
        self.dark_mode = True  # Muss vor add_buttons gesetzt sein

        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)

        self.init_button_state()
        self.add_buttons(self.layout)

        screen = get_monitors()[0]
        self.width_size = int(screen.width * 0.15)
        self.height_size = int(screen.height * 0.5)
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def show_explorer(self):
        """Zeige wieder die Liste der Skript-Buttons"""
        # Alle bisherigen Inhalte entfernen
        for i in reversed(range(self.layout.count())):
            w = self.layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # Buttons erneut hinzufügen
        self.add_buttons(self.layout)
        self.update_button_styles(self.layout)
        self.back_to_explorer_btn.hide()

    def show_popup(self):
        self.add_buttons(self.layout)
        self.update_button_styles(self.layout)

        cursor_pos = QCursor.pos()
        start_x = cursor_pos.x()
        start_y = cursor_pos.y()
        end_x = start_x - self.width_size
        end_y = start_y - self.height_size

        self.animation.setStartValue(QRect(start_x, start_y + 50, self.width_size, self.height_size))
        self.animation.setEndValue(QRect(end_x, end_y, self.width_size, self.height_size))
        self.animation.start()
        self.show()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def show_plugin_widget(self, widget: QWidget, title: str = ""):
        """Zeigt ein Plugin direkt im Popup an (wie im Hauptfenster)"""
        # Alle bisherigen Inhalte entfernen
        for i in reversed(range(self.layout.count())):
            w = self.layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 8, 8, 8)

        header = QLabel(f"🧩 Plugin: {title}")
        header.setStyleSheet("font-weight: bold; font-size: 15px; margin-bottom: 6px;")
        v.addWidget(header)
        v.addWidget(widget)

        self.layout.addWidget(container)

        # Popup-Größe anpassen
        container.adjustSize()
        self.adjustSize()



# ------------------------------
# MainAppWindow mit QStackedWidget
# ------------------------------
class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app, popup=None):
        super().__init__()
        self.setWindowIcon(QIcon("ProgrammIcon.ico"))
        self.app = app
        self.popup = popup

        self.dark_mode = False

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(900, 620)

        self.central = QWidget()
        self.central_layout = QVBoxLayout(self.central)
        self.central_layout.setContentsMargins(0, 0, 0, 0)

        self.title_bar = CustomTitleBar(self, "Skript Starter – Hauptfenster")
        self.central_layout.addWidget(self.title_bar)

        # Toggle-Button bleibt oben sichtbar
        toolbar = QHBoxLayout()
        self.toggle_button = QPushButton("Wechsle Theme")
        self.toggle_button.clicked.connect(self.toggle_theme)
        self.back_to_explorer_btn = QPushButton("← Explorer")
        self.back_to_explorer_btn.clicked.connect(self.go_back_to_explorer)
        self.back_to_explorer_btn.hide()  # erst mal unsichtbar

        toolbar.addWidget(self.toggle_button)
        toolbar.addWidget(self.back_to_explorer_btn)
        toolbar.addStretch()
        tb = QWidget(); tb.setLayout(toolbar)
        self.central_layout.addWidget(tb)

        # Explorer: separater Container für Skript-Buttons
        self.button_container = QWidget()
        self.layout = QVBoxLayout(self.button_container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Seitenverwaltung
        self.pages = QStackedWidget()
        self.pages.addWidget(self.button_container)  # Index 0: Explorer
        self.central_layout.addWidget(self.pages)

        self.setCentralWidget(self.central)

        # Init Buttons
        self.init_button_state()
        self.add_buttons(self.layout)

        # Plugin-Loader an Mixin durchreichen
        self.set_plugin_loader(self.load_plugin_from_path)

        # Theme setzen
        self.toggle_theme()

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.app.setStyleSheet(dark_mode_stylesheet if self.dark_mode else light_mode_stylesheet)
        self.update_button_styles(self.layout)
        if self.popup:
            self.popup.dark_mode = self.dark_mode
            self.popup.update_button_styles(self.popup.layout)

    def go_back_to_explorer(self):
        self.back_to_explorer_btn.hide()
        self.pages.setCurrentWidget(self.button_container)

    # --------------------------
    # Plugin laden/anzeigen
    # --------------------------
    def load_plugin_from_path(self, path: str, source_widget=None):
        """Plugin im Hauptfenster oder Popup laden"""
        try:
            if path.lower().endswith('.py'):
                mode = "popup" if isinstance(source_widget, PopupWindow) else "window"
                widget = self.load_python_plugin_widget(path, mode=mode)
                if widget is None:
                    QMessageBox.warning(source_widget or self, "Kein Plugin",
                                        f"{os.path.basename(path)} enthält keine Klasse 'PluginWidget'.")
                    return
            elif path.lower().endswith('.html'):
                widget = HtmlPluginContainer(path)
            else:
                subprocess.Popen([sys.executable, path])
                return

            if isinstance(source_widget, PopupWindow):
                # Im Popup anzeigen
                source_widget.show_plugin_widget(widget, os.path.basename(path))
            else:
                # Hauptfenster
                container = QWidget()
                v = QVBoxLayout(container)
                v.setContentsMargins(12, 12, 12, 12)
                header = QLabel(f"🧩 Plugin: {os.path.basename(path)}")
                header.setStyleSheet("font-weight:bold; font-size:15px; margin-bottom:8px;")
                v.addWidget(header)
                v.addWidget(widget)
                self.pages.addWidget(container)
                self.pages.setCurrentWidget(container)
                self.back_to_explorer_btn.show()

        except Exception as e:
            QMessageBox.critical(source_widget or self, "Fehler beim Laden", f"{e}")

    def load_python_plugin_widget(self, path: str, mode="window"):
        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, 'PluginWidget'):
            # Übergibt theme + mode an Plugin
            widget = module.PluginWidget(
                theme="dark" if self.dark_mode else "light",
                mode=mode
            )
            return widget
        return None

    def show_plugin_widget(self, widget: QWidget, title: str = ""):
        # Optional: Titel über Plugin zeigen
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(12, 12, 12, 12)
        header = QLabel(f"🧩 Plugin: {title}")
        header.setStyleSheet("font-weight: bold; font-size: 15px; margin-bottom: 8px;")
        v.addWidget(header)
        v.addWidget(widget)

        # Seite einfügen & anzeigen
        self.pages.addWidget(container)
        self.pages.setCurrentWidget(container)

        self.back_to_explorer_btn.show()


# ------------------------------
# TrayApp
# ------------------------------
class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)
        self.setStyleSheet(dark_mode_stylesheet)

        self.popup = PopupWindow()
        self.main_window = MainAppWindow(self, popup=self.popup)

        # Verbinde Popup-Mixin mit dem Plugin-Loader des MainWindows
        self.popup.set_plugin_loader(self.main_window.load_plugin_from_path)

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon("TrayIcon.ico"))
        self.tray.setVisible(True)

        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:
            self.popup.show_popup()
        elif reason == QSystemTrayIcon.Trigger:
            # Linksklick auf Tray-Icon: Fenster anzeigen oder in den Vordergrund holen
            if self.main_window.isMinimized() or not self.main_window.isVisible():
                self.main_window.showNormal()   # Fenster wiederherstellen, falls minimiert
                self.main_window.activateWindow()
                self.main_window.raise_()
            else:
                # Wenn schon sichtbar, einfach in den Vordergrund bringen
                self.main_window.activateWindow()
                self.main_window.raise_()


# ------------------------------
# Einstiegspunkt
# ------------------------------
if __name__ == "__main__":
    # Windows: Application ID setzen (Taskleisten-Gruppierung/Icon)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"meinefirma.skriptstarter.1.0")
    except Exception:
        pass

    app = TrayApp(sys.argv)
    sys.exit(app.exec_())