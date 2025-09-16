import sys
import os
import subprocess
import importlib.util
import traceback
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QHBoxLayout, QLabel,
    QStackedWidget, QMessageBox, QScrollArea
)
from PyQt5.QtGui import QCursor, QIcon, QColor, QGuiApplication
from PyQt5.QtCore import (
    Qt, QRect, QPoint, QFileSystemWatcher, QObject, pyqtSlot, QUrl, QPropertyAnimation, QEasingCurve
)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
    from PyQt5.QtWebChannel import QWebChannel

    WEBENGINE_AVAILABLE = True
except Exception:
    WEBENGINE_AVAILABLE = False

from screeninfo import get_monitors
import ctypes

# --- High DPI Scaling aktivieren ---
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
# -----------------------------------

# --- Globale Theme-Variable ---
theme = "dark"


def is_dark():
    global theme
    return theme == "dark"


dark_mode_stylesheet = """
    QWidget {
        background-color: #2E2E2E;
        color: #FFFFFF;
        transition: background-color 0.5s ease, color 0.5s ease;
    }
    QPushButton {
        transition: background-color 0.5s ease, color 0.5s ease;
    }
"""

light_mode_stylesheet = """
    QWidget {
        background-color: #FFFFFF;
        color: #000000;
        transition: background-color 0.5s ease, color 0.5s ease;
    }
    QPushButton {
        transition: background-color 0.5s ease, color 0.5s ease;
    }
"""

def current_stylesheet():
    return dark_mode_stylesheet if is_dark() else light_mode_stylesheet


def set_theme(new_theme, app=None):
    global theme
    theme = new_theme
    if app is not None:
        app.setStyleSheet(current_stylesheet())

# -----------------------------

def ensure_sample_plugin(script_root: str):
    if not os.path.exists(script_root):
        os.makedirs(script_root, exist_ok=True)
    entries = [e for e in os.listdir(script_root) if not e.startswith("_")]
    if entries:
        return
    sample_path = os.path.join(script_root, "timer_plugin.py")
    sample_code = r'''from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtCore import QTimer

class PluginWidget(QWidget):
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
    try:
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write(sample_code)
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
    except Exception:
        print("Fehler beim Anlegen der Beispiel-Plugins und HTML:", traceback.format_exc())


class ButtonContentMixin:
    SCRIPT_FOLDER = "scripts"

    def init_button_state(self):
        self.current_path = os.path.abspath(self.SCRIPT_FOLDER)
        ensure_sample_plugin(self.current_path)
        if not os.path.exists(self.current_path):
            os.makedirs(self.current_path)
        self.watcher = QFileSystemWatcher()
        try:
            if os.path.exists(self.current_path):
                self.watcher.addPath(self.current_path)
        except Exception:
            print("Fehler beim Hinzufügen des Watchers:", traceback.format_exc())
        try:
            self.watcher.directoryChanged.connect(self.on_directory_changed)
        except Exception:
            print("Fehler beim Verbinden des Watchersignals:", traceback.format_exc())
        self.plugin_loader = None

    def set_plugin_loader(self, loader_callable):
        self.plugin_loader = loader_callable

    def on_directory_changed(self, path):
        self.add_buttons(self.layout)

    def add_buttons(self, layout):
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)
        if hasattr(self, "watcher"):
            try:
                paths = self.watcher.directories()
                if paths and paths != self.current_path:
                    self.watcher.removePaths(paths)
                    self.watcher.addPath(self.current_path)
            except Exception:
                print("Fehler beim Aktualisieren des Watchers:", traceback.format_exc())
        if self.current_path != os.path.abspath(self.SCRIPT_FOLDER):
            back_button = QPushButton("← Zurück")
            back_button.clicked.connect(self.go_back)
            back_button.setObjectName("back_button")
            layout.addWidget(back_button)
        try:
            entries = sorted(os.listdir(self.current_path))
        except Exception:
            entries = []
        for entry in entries:
            if entry.startswith("_"):
                continue
            full_path = os.path.join(self.current_path, entry)
            try:
                if os.path.isdir(full_path):
                    button = QPushButton(entry)
                    button.clicked.connect(lambda _, p=full_path: self.enter_directory(p))
                    button.setProperty("entry_type", "folder")
                elif entry.endswith(".py") or entry.endswith(".html"):
                    display_name = entry[:-3] if entry.endswith(".py") else entry
                    button = QPushButton(display_name)
                    button.clicked.connect(lambda _, p=full_path: self.run_script(p))
                    button.setProperty("entry_type", "file")
                else:
                    continue
                button.setMinimumHeight(60)
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                layout.addWidget(button)
            except Exception:
                print("Fehler beim Erstellen eines Buttons:", traceback.format_exc())
        self.update_button_styles(layout)

    def enter_directory(self, path):
        self.current_path = path
        self.add_buttons(self.layout)

    def go_back(self):
        parent = os.path.dirname(self.current_path)
        root = os.path.abspath(self.SCRIPT_FOLDER)
        try:
            if os.path.commonpath([parent, root]) == root:
                self.current_path = parent
                self.add_buttons(self.layout)
                return
        except Exception:
            print("Fehler beim Zurückgehen im Verzeichnis:", traceback.format_exc())
        self.current_path = root
        self.add_buttons(self.layout)

    def run_script(self, path):
        try:
            if callable(getattr(self, "plugin_loader", None)):
                self.plugin_loader(path, source_widget=self)
            else:
                if path.endswith('.py'):
                    subprocess.Popen([sys.executable, path])
                elif path.endswith('.html'):
                    import webbrowser
                    webbrowser.open('file://' + os.path.abspath(path))
        except Exception:
            print("Fehler beim Ausführen des Skripts:", traceback.format_exc())

    def update_button_styles(self, layout):
        for i in range(layout.count()):
            button = layout.itemAt(i).widget()
            if isinstance(button, QPushButton):
                if button.objectName() == "back_button":
                    button.setMinimumHeight(40)
                    button.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {'#666666' if is_dark() else '#BBBBBB'};
                            color: {'#FFFFFF' if is_dark() else '#000000'};
                            font-weight: bold;
                        }}
                        QPushButton:hover {{
                            background-color: {'#777777' if is_dark() else '#CCCCCC'};
                        }}
                    """)
                else:
                    entry_type = button.property("entry_type")
                    if entry_type == "folder":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A4A6A' if is_dark() else '#c2d1ff'};
                                color: {'#FFFFFF' if is_dark() else '#000000'};
                            }}
                            QPushButton:hover {{
                                background-color: {'#4B5B6B' if is_dark() else '#a1b8ff'};
                            }}
                        """)
                    elif entry_type == "file":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A3A3A' if is_dark() else '#EEEEEE'};
                                color: {'#FFFFFF' if is_dark() else '#000000'};
                            }}
                            QPushButton:hover {{
                                background-color: {'#505050' if is_dark() else '#CCCCCC'};
                            }}
                        """)


class HtmlPluginContainer(QWidget):
    def __init__(self, html_path: str):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel(f"HTML: {os.path.basename(html_path)}")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        if WEBENGINE_AVAILABLE:
            try:
                view = QWebEngineView(self)
                view.load(QUrl.fromLocalFile(os.path.abspath(html_path)))
                view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
                layout.addWidget(view)
            except Exception:
                msg = QLabel("PyQtWebEngine ist nicht installiert oder Laden fehlgeschlagen. Öffne die Datei extern.")
                layout.addWidget(msg)
                open_btn = QPushButton("Im Standardbrowser öffnen")
                layout.addWidget(open_btn)

                def _open():
                    import webbrowser
                    webbrowser.open('file://' + os.path.abspath(html_path))

                open_btn.clicked.connect(_open)
        else:
            msg = QLabel("PyQtWebEngine ist nicht installiert. Öffne die Datei extern.")
            layout.addWidget(msg)
            open_btn = QPushButton("Im Standardbrowser öffnen")
            layout.addWidget(open_btn)

            def _open2():
                import webbrowser
                webbrowser.open('file://' + os.path.abspath(html_path))

            open_btn.clicked.connect(_open2)


class PopupWindow(ButtonContentMixin, QWidget):
    def __init__(self, app=None):
        super().__init__()
        self.app = app
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.channel = QWebChannel()
        self.bridge = ThemeBridge(main_window=None, popup=self)
        self.channel.registerObject("bridge", self.bridge)

        self.html_toolbar = QWebEngineView(self) if WEBENGINE_AVAILABLE else QWidget(self)
        if WEBENGINE_AVAILABLE:
            self.html_toolbar.setFixedHeight(40)
            self.html_toolbar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.html_toolbar.page().setWebChannel(self.channel)
            self.html_toolbar.loadFinished.connect(self._on_toolbar_load_finished)
            self.html_toolbar.setVisible(False)

        self._build_html_toolbar()

        self.explorer_container = QWidget()
        self.layout = QVBoxLayout(self.explorer_container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.init_button_state()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background: #292929;
                width: 10px;
                margin: 0;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #666;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                height: 0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.scroll_area.setWidget(self.explorer_container)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.scroll_area)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)
        self.main_layout.addWidget(self.html_toolbar)
        self.main_layout.addWidget(self.pages)

        self.update_relative_size()
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def update_relative_size(self):
        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        geometry = screen.geometry()
        self.width_size = int(geometry.width() * 0.15)
        self.height_size = int(geometry.height() * 0.5)

    def _build_html_toolbar(self):
        mode = theme
        explorer_btn = f'<button id="explorerBtn" class="toolbar-btn {mode}">← Explorer</button>'
        html_code = f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8" />
            <title>Toolbar</title>
            <style>
                html, body {{
                    background: rgba(0, 0, 0, 0) !important;
                    margin: 0;
                    overflow: hidden !important;
                }}
                .toolbar-btn {{
                    padding: 4px 10px;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 0.3s, color 0.3s, border-color 0.3s;
                    margin-right: 8px;
                    min-height: 28px;
                    min-width: 80px;
                    background: transparent !important;
                    outline: none;
                }}
                .light {{ background: #ffffff; color: #333; border-color: #dddddd; }}
                .dark  {{ background: #2c2c2c; color: #f5f5f5; border-color: #444; }}
                .toolbar-container {{
                    display: flex;
                    align-items: center;
                    height: 32px;
                }}
            </style>
        </head>
        <body>
            <div class="toolbar-container">
                {explorer_btn}
            </div>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                var eb = null;
                function updateBtnMode(mode) {{
                    var eb = document.getElementById("explorerBtn");
                    if (eb) {{
                        eb.className = "toolbar-btn " + mode;
                    }}
                }}
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.bridge = channel.objects.bridge;
                    eb = document.getElementById("explorerBtn");
                    eb.onclick = function() {{
                        bridge.goBackToExplorer();
                    }};
                    window.setBtnMode = updateBtnMode;
                    setTimeout(function() {{
                        updateBtnMode("{mode}");
                    }}, 0);
                }});
            </script>
        </body>
        </html>
        """
        if WEBENGINE_AVAILABLE:
            self.html_toolbar.setHtml(html_code)
            self.html_toolbar.setAttribute(Qt.WA_TranslucentBackground, True)
            self.html_toolbar.setAttribute(Qt.WA_OpaquePaintEvent, False)
            self.html_toolbar.page().setBackgroundColor(QColor(0, 0, 0, 0))

    def _on_toolbar_load_finished(self, ok):
        if ok:
            js = f'window.setBtnMode && window.setBtnMode("{theme}");'
            self.html_toolbar.page().runJavaScript(js)

    def show_toolbar_with_theme_check(self):
        self.html_toolbar.setVisible(True)
        js = f'window.setBtnMode && window.setBtnMode("{theme}");'
        self.html_toolbar.page().runJavaScript(js)

    def add_buttons(self, layout):
        super().add_buttons(layout)

    def show_plugin_widget(self, widget: QWidget, title: str = ""):
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 8, 8, 8)
        header = QLabel(f"🧩 Plugin: {title}")
        header.setStyleSheet("font-weight: bold; font-size: 15px; margin-bottom: 6px;")
        v.addWidget(header)
        v.addWidget(widget)
        self.pages.addWidget(container)
        self.pages.setCurrentWidget(container)
        self.show_toolbar_with_theme_check()

    def show_explorer(self):
        self.pages.setCurrentWidget(self.scroll_area)
        self.html_toolbar.setVisible(False)

    def toggle_theme(self):
        global theme
        theme = "light" if is_dark() else "dark"
        set_theme(theme, self.app)
        self.update_button_styles(self.layout)
        js = f'window.setBtnMode && window.setBtnMode("{theme}");'
        self.html_toolbar.page().runJavaScript(js)

    def show_popup(self):
        self.add_buttons(self.layout)
        self.update_button_styles(self.layout)
        self._build_html_toolbar()
        self.update_relative_size()
        self.setFixedSize(self.width_size, self.height_size)
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


class ThemeBridge(QObject):
    def __init__(self, main_window=None, popup=None):
        super().__init__()
        self.main_window = main_window
        self.popup = popup

    @pyqtSlot()
    def toggleTheme(self):
        if self.main_window:
            self.main_window.toggle_theme()

    @pyqtSlot()
    def goBackToExplorer(self):
        if self.popup and self.popup.isVisible():
            self.popup.show_explorer()
        elif self.main_window:
            self.main_window.go_back_to_explorer()


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app, popup=None):
        super().__init__()
        self.setWindowIcon(QIcon("ProgrammIcon.ico") if os.path.exists("ProgrammIcon.ico") else QIcon())
        self.app = app
        self.popup = popup
        self.update_relative_size()
        self.setMinimumSize(self.width_size, self.height_size)

        self.central = QWidget()
        self.central_layout = QVBoxLayout(self.central)
        self.central_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.html_toolbar = QWebEngineView() if WEBENGINE_AVAILABLE else QWidget()
        if WEBENGINE_AVAILABLE:
            try:
                self.html_toolbar.page().setBackgroundColor(Qt.transparent)
                self.html_toolbar.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
            except Exception:
                pass
        self.show_explorer_btn = False
        self._build_html_toolbar()
        if WEBENGINE_AVAILABLE:
            try:
                self.channel = QWebChannel()
                self.bridge = ThemeBridge(main_window=self, popup=self.popup)
                self.channel.registerObject("bridge", self.bridge)
                self.html_toolbar.page().setWebChannel(self.channel)
            except Exception:
                pass

        if WEBENGINE_AVAILABLE:
            self.html_toolbar.setFixedHeight(44)
            self.html_toolbar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        toolbar.addWidget(self.html_toolbar)
        toolbar.addStretch()

        tb = QWidget()
        tb.setLayout(toolbar)
        self.central_layout.addWidget(tb)

        self.pages = QStackedWidget()

        self.button_container = QWidget()
        self.layout = QVBoxLayout(self.button_container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background: #292929;
                width: 10px;
                margin: 0;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #666;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
                height: 0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.scroll_area.setWidget(self.button_container)

        self.pages.addWidget(self.scroll_area)
        self.central_layout.addWidget(self.pages)
        self.setCentralWidget(self.central)

        self.init_button_state()
        self.add_buttons(self.layout)
        self.set_plugin_loader(self.load_plugin_from_path)

    def update_relative_size(self):
        screen = QGuiApplication.screenAt(self.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        geometry = screen.geometry()
        self.width_size = int(geometry.width() * 0.4)
        self.height_size = int(geometry.height() * 0.4)

    def _build_html_toolbar(self):
        mode = theme
        # Explorer-Button nur wenn show_explorer_btn True ist
        explorer_btn = f'<button id="explorerBtn" class="toolbar-btn {mode}" style="margin-left:1.5rem; display:{"inline-block" if self.show_explorer_btn else "none"};">← Explorer</button>'

        html_code = f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8" />
            <title>Toolbar</title>
            <style>
                html, body {{
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }}

                .toolbar-btn {{
                    padding: 0.25em 0.675em;
                    border: 0.07em solid transparent;
                    border-radius: 0.38em;
                    font-size: 1em;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 0.3s, color 0.3s, border-color 0.3s;
                    min-height: 2.25em;
                    min-width: 5em;
                    background: transparent !important;
                    outline: none;
                }}
                .light {{ background: #ffffff; color: #333; border-color: #dddddd; }}
                .dark  {{ background: #2c2c2c; color: #f5f5f5; border-color: #444; }}

                .toolbar-container {{
                    display: flex;
                    align-items: center;
                    height: 2.5rem;
                    padding: 0 2vw;
                    gap: 0.5em;
                    background: transparent !important;
                }}

                /* --- Toggle Switch bleibt unverändert --- */
                .switch {{
                  position: relative;
                  width: 5rem;
                  height: 2.5rem;
                  cursor: pointer;
                  user-select: none;
                  margin-top: 0.4rem;
                }}

                .switch input {{
                  position: absolute;
                  top: 0;
                  left: 0;
                  width: 100%;
                  height: 100%;
                  margin: 0;
                  opacity: 0;
                  cursor: pointer;
                  z-index: 3;
                }}

                .background {{
                  position: absolute;
                  width: 5rem;
                  height: 2rem;
                  border-radius: 1.25rem;
                  border: 0.15rem solid #202020;
                  background: linear-gradient(to right, #484848 0%, #202020 100%);
                  transition: all 0.3s;
                  top: 0;
                  left: 0;
                  z-index: 1;
                }}

                .fill {{
                  position: fixed;
                  top: 0;
                  right: 0;
                  bottom: 2rem;
                  left: 0;
                  background: #484848;
                  transition: 0.75s all ease;
                }}

                .switch input:checked ~ .fill {{
                  background: #E9F8FD;
                }}

                .stars1,
                .stars2 {{
                  position: absolute;
                  height: 0.2rem;
                  width: 0.2rem;
                  background: #FFFFFF;
                  border-radius: 50%;
                  transition: 0.3s all ease;
                }}
                .stars1 {{ top: 0.2em; right: 0.8em; }}
                .stars2 {{ top: 1.3em; right: 1.75em; }}

                .stars1:after,
                .stars1:before,
                .stars2:after,
                .stars2:before {{
                  position: absolute;
                  content: "";
                  display: block;
                  height: 0.125rem;
                  width: 0.125rem;
                  background: #FFFFFF;
                  border-radius: 50%;
                  transition: 0.2s all ease;
                }}

                .sun-moon {{
                  position: absolute;
                  left: 0;
                  top: 0;
                  height: 1.5rem;
                  width: 1.5rem;
                  margin: 0.25rem;
                  background: #FFFDF2;
                  border-radius: 50%;
                  border: 0.15rem solid #DEE2C6;
                  transition: all 0.5s ease;
                  z-index: 2;
                }}

                .sun-moon .dots {{
                  position: absolute;
                  top: 0.1em;
                  left: 0.7em;
                  height: 0.5rem;
                  width: 0.5rem;
                  background: #EFEEDB;
                  border: 0.15rem solid #DEE2C6;
                  border-radius: 50%;
                  transition: 0.4s all ease;
                }}

                .switch input:checked ~ .sun-moon {{
                  left: calc(100% - 2rem);
                  background: #F5EC59;
                  border-color: #E7C65C;
                  transform: rotate(-25deg);
                }}

                .switch input:checked ~ .sun-moon .dots,
                .switch input:checked ~ .sun-moon .dots:after,
                .switch input:checked ~ .sun-moon .dots:before {{
                  background: #FFFFFF;
                  border-color: #FFFFFF;
                }}

                .switch input:checked ~ .background {{
                  border: 0.15rem solid #78C1D5;
                  background: linear-gradient(to right, #78C1D5 0%, #BBE7F5 100%);
                }}
            </style>
        </head>
        <body>
            <div class="toolbar-container">
                <div class="switch">
                    <label for="toggle">
                        <input id="toggle" class="toggle-switch" type="checkbox" {'checked' if mode == "light" else ''} />
                        <div class="sun-moon"><div class="dots"></div></div>
                        <div class="background"><div class="stars1"></div><div class="stars2"></div></div>
                    </label>
                </div>
                {explorer_btn}
            </div>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.bridge = channel.objects.bridge;
                    const toggle = document.getElementById("toggle");
                    const explorerBtn = document.getElementById("explorerBtn");

                    toggle.addEventListener("change", function() {{
                        bridge.toggleTheme();
                        // Explorer-Button in Echtzeit anpassen
                        if (explorerBtn) {{
                            if (toggle.checked) {{
                                explorerBtn.classList.remove('dark');
                                explorerBtn.classList.add('light');
                            }} else {{
                                explorerBtn.classList.remove('light');
                                explorerBtn.classList.add('dark');
                            }}
                        }}
                    }});

                    if (explorerBtn) {{
                        explorerBtn.onclick = function() {{
                            bridge.goBackToExplorer();
                        }};
                    }}
                }});
            </script>
        </body>
        </html>
        """
        try:
            if WEBENGINE_AVAILABLE:
                self.html_toolbar.setHtml(html_code)
        except Exception:
            import traceback
            print("Fehler beim Setzen der Toolbar HTML:", traceback.format_exc())

    def toggle_theme(self):
        global theme
        theme = "light" if is_dark() else "dark"
        set_theme(theme, self.app)
        self.update_button_styles(self.layout)
        if self.popup:
            self.popup.update_button_styles(self.popup.layout)

        # Den Explorer-Button im WebEngine nach Themewechsel neu updaten
        if WEBENGINE_AVAILABLE:
            js = f'window.setBtnMode && window.setBtnMode("{theme}");'
            try:
                self.html_toolbar.page().runJavaScript(js)
            except Exception:
                pass

    def go_back_to_explorer(self):
        self.pages.setCurrentWidget(self.scroll_area)
        self.show_explorer_btn = False
        self._build_html_toolbar()
        # Explorer-Button beim Zurücksetzen auch updaten
        if WEBENGINE_AVAILABLE:
            js = f'window.setBtnMode && window.setBtnMode("{theme}");'
            try:
                self.html_toolbar.page().runJavaScript(js)
            except Exception:
                pass

    def load_plugin_from_path(self, path: str, source_widget=None):
        try:
            if path.lower().endswith('.py'):
                widget = self.load_python_plugin_widget(path)
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
                source_widget.show_plugin_widget(widget, os.path.basename(path))
            else:
                container = QWidget()
                v = QVBoxLayout(container)
                v.setContentsMargins(12, 12, 12, 12)
                header = QLabel(f"🧩 Plugin: {os.path.basename(path)}")
                header.setStyleSheet("font-weight:bold; font-size:15px; margin-bottom:8px;")
                v.addWidget(header)
                v.addWidget(widget)
                self.pages.addWidget(container)
                self.pages.setCurrentWidget(container)
                self.show_explorer_btn = True
                self._build_html_toolbar()
                # Explorer-Button beim Anzeigen des Plugins updaten
                if WEBENGINE_AVAILABLE:
                    js = f'window.setBtnMode && window.setBtnMode("{theme}");'
                    try:
                        self.html_toolbar.page().runJavaScript(js)
                    except Exception:
                        pass
        except Exception as e:
            QMessageBox.critical(source_widget or self, "Fehler beim Laden", f"{e}")

    def load_python_plugin_widget(self, path: str, mode="window"):
        try:
            spec = importlib.util.spec_from_file_location("plugin_module", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, "PluginWidget", None)
            if cls is not None and isinstance(cls, type):
                return cls()
            return None
        except Exception:
            return None


class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)
        self.setStyleSheet(current_stylesheet())
        self.popup = PopupWindow(app=self)
        self.main_window = MainAppWindow(self, popup=self.popup)
        self.popup.set_plugin_loader(self.main_window.load_plugin_from_path)
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon("TrayIcon.ico") if os.path.exists("TrayIcon.ico") else QIcon())
        self.tray.setVisible(True)
        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:
            self.popup.show_popup()
        elif reason == QSystemTrayIcon.Trigger:
            if self.main_window.isMinimized() or not self.main_window.isVisible():
                self.main_window.showNormal()
                self.main_window.activateWindow()
                self.main_window.raise_()
            else:
                self.main_window.activateWindow()
                self.main_window.raise_()


if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"meinefirma.skriptstarter.1.0")
    except Exception:
        pass
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())
