# --- tray_launcher.py (HTML lightswitch + safe back + search + stability + TABS v2 Design + POMODORO v2 + SETTINGS) ---

# TO MAKE EXE OF TRAYLAUNCHER USE FOLLOWING COMMAND IN TERMINAL:    pyinstaller --noconsole --onefile --icon=ProgrammIcon.ico --add-data "scripts;scripts" tray_launcher.py

try:
    import pytz
    import dateutil.rrule
    import icalendar
    import uuid
except ImportError:
    print("WARNUNG: Optionale Plugin-Abhängigkeiten (pytz, dateutil, icalendar) fehlen.")

import sys
import os
import json
import subprocess
import importlib.util
import traceback

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QHBoxLayout, QLabel,
    QStackedWidget, QMessageBox, QScrollArea, QLineEdit, QFileDialog,
    QTabWidget, QTabBar, QMenu, QInputDialog, QAction,
    QProgressBar, QCheckBox, QListWidget, QListWidgetItem, QGroupBox, QFormLayout, QFrame
)
from PyQt5.QtGui import QCursor, QIcon, QColor, QGuiApplication
from PyQt5.QtCore import (
    Qt, QRect, QFileSystemWatcher, QObject, pyqtSlot, QUrl,
    QPropertyAnimation, QEasingCurve, QEvent, QTimer, pyqtSignal
)

# --- WebEngine optional laden ---
WEBENGINE_AVAILABLE = False
try:
    try:
        from PyQt5.QtWebEngine import QtWebEngine

        QtWebEngine.initialize()
    except Exception:
        pass
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEnginePage
    from PyQt5.QtWebChannel import QWebChannel

    WEBENGINE_AVAILABLE = True
except Exception:
    WEBENGINE_AVAILABLE = False


# --- CONFIG MANAGER (NEU) ---
class ConfigManager:
    FILE_NAME = "launcher_settings.json"
    DEFAULT = {
        "pomodoro_visible": True,
        "pomodoro_style": "large",  # "small" or "large"
        "hidden_plugins": []
    }

    @staticmethod
    def load_config():
        if not os.path.exists(ConfigManager.FILE_NAME):
            return ConfigManager.DEFAULT.copy()
        try:
            with open(ConfigManager.FILE_NAME, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults to ensure keys exist
                config = ConfigManager.DEFAULT.copy()
                config.update(data)
                return config
        except Exception:
            return ConfigManager.DEFAULT.copy()

    @staticmethod
    def save_config(config):
        try:
            with open(ConfigManager.FILE_NAME, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print("Fehler beim Speichern der Config:", e)


def safe_run_js(view: 'QWebEngineView', script: str):
    if not WEBENGINE_AVAILABLE or view is None:
        return
    try:
        page = view.page()
        if page is None:
            return
        page.runJavaScript(script)
    except Exception:
        pass


class InlineInterceptPage(QWebEnginePage):
    def __init__(self, on_open_link=None, parent=None):
        super().__init__(parent)
        self._on_open_link = on_open_link
        self._child_pages = []

    def _delegate(self, url: QUrl):
        if callable(self._on_open_link):
            try:
                self._on_open_link(url)
            except Exception:
                traceback.print_exc()

    def acceptNavigationRequest(self, url, nav_type, isMainFrame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            self._delegate(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, isMainFrame)

    def createWindow(self, _type):
        page = QWebEnginePage(self)
        self._child_pages.append(page)

        def _on_url_changed(u: QUrl):
            try:
                self._delegate(u)
            finally:
                try:
                    page.urlChanged.disconnect(_on_url_changed)
                except Exception:
                    pass

                def _cleanup():
                    try:
                        if page in self._child_pages:
                            self._child_pages.remove(page)
                    except Exception:
                        pass
                    try:
                        page.deleteLater()
                    except Exception:
                        pass

                QTimer.singleShot(0, _cleanup)

        page.urlChanged.connect(_on_url_changed)
        return page


class HtmlPluginContainerExternal(QWidget):
    def __init__(self, url: QUrl):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"🔗 {url.toString()}"))
        if WEBENGINE_AVAILABLE:
            view = QWebEngineView(self)
            try:
                view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
            except Exception:
                pass
            view.load(url)
            lay.addWidget(view)
        else:
            lay.addWidget(QLabel("PyQtWebEngine nicht verfügbar."))


# --- Windows Media Control Bridge (für Inline-HTML) ---
class MediaControlBridge(QObject):
    themeChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        import platform
        self._is_windows = (platform.system().lower() == "windows")
        if self._is_windows:
            import ctypes
            self._user32 = ctypes.windll.user32
            self.VK_MEDIA_NEXT_TRACK = 0xB0
            self.VK_MEDIA_PREV_TRACK = 0xB1
            self.VK_MEDIA_STOP = 0xB2
            self.VK_MEDIA_PLAY_PAUSE = 0xB3
            self.VK_VOLUME_MUTE = 0xAD
            self.VK_VOLUME_DOWN = 0xAE
            self.VK_VOLUME_UP = 0xAF

        self._app = QApplication.instance()
        self._theme = self._read_theme()
        if self._app is not None:
            self._app.installEventFilter(self)
        self.destroyed.connect(self._detach_theme_watcher)

    def _read_theme(self):
        if self._app is not None:
            val = self._app.property("toolbar_theme")
            if isinstance(val, str):
                return val.lower()
        return "dark"

    def _update_theme(self, value):
        value = (value or "").lower()
        if value not in ("light", "dark"):
            return
        if value != self._theme:
            self._theme = value
            self.themeChanged.emit(self._theme)

    def _tap(self, vk):
        if not getattr(self, "_is_windows", False): return
        KEYEVENTF_KEYUP = 0x0002
        self._user32.keybd_event(vk, 0, 0, 0)
        self._user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    def eventFilter(self, watched, event):
        if watched is self._app and event.type() == QEvent.DynamicPropertyChange:
            try:
                prop = event.propertyName().data().decode('utf-8')
            except Exception:
                prop = None
            if prop == "toolbar_theme":
                self._update_theme(self._app.property("toolbar_theme"))
        return super().eventFilter(watched, event)

    def _detach_theme_watcher(self):
        if self._app is not None:
            try:
                self._app.removeEventFilter(self)
            except Exception:
                pass
            self._app = None

    @pyqtSlot(result=str)
    def getTheme(self):
        return self._theme

    @pyqtSlot()
    def playPause(self):
        self._tap(self.VK_MEDIA_PLAY_PAUSE)

    @pyqtSlot()
    def next(self):
        self._tap(self.VK_MEDIA_NEXT_TRACK)

    @pyqtSlot()
    def prev(self):
        self._tap(self.VK_MEDIA_PREV_TRACK)

    @pyqtSlot()
    def stop(self):
        self._tap(self.VK_MEDIA_STOP)

    @pyqtSlot()
    def mute(self):
        self._tap(self.VK_VOLUME_MUTE)

    @pyqtSlot()
    def volUp(self):
        self._tap(self.VK_VOLUME_UP)

    @pyqtSlot()
    def volDown(self):
        self._tap(self.VK_VOLUME_DOWN)


class HtmlInlineButton(QWidget):
    def __init__(self, path: str = None, title_text: str = None,
                 min_height: int = 160, compact: bool = False, **kwargs):
        super().__init__()
        if path is None:
            path = kwargs.pop("html_path", None)
        if path is None:
            raise ValueError("HtmlInlineButton requires 'path' (or 'html_path').")
        self.setProperty("entry_type", "file_html_inline")
        self.src_path = os.path.abspath(path)
        self.compact = compact

        probe = QPushButton("Wg")
        base_h = max(28, probe.sizeHint().height())
        factor = 1.8 if not compact else 2.4
        target_h = int(base_h * factor)
        top = max(4, target_h // 8)
        bot = max(4, target_h // 8)
        self.setMinimumHeight(target_h)
        self.setMaximumHeight(target_h)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, top, 8, bot)
        outer.setSpacing(0)

        if WEBENGINE_AVAILABLE:
            try:
                self.view = QWebEngineView(self)

                def _handle_open_link(qurl: QUrl):
                    host = self.parent()
                    while host and not hasattr(host, "_open_link_as_plugin"):
                        host = host.parent()
                    if host and callable(getattr(host, "_open_link_as_plugin", None)):
                        host._open_link_as_plugin(qurl)
                    else:
                        import webbrowser
                        webbrowser.open(qurl.toString())

                self._page = InlineInterceptPage(on_open_link=_handle_open_link, parent=self.view)
                self.view.setPage(self._page)

                self.view.setAttribute(Qt.WA_TranslucentBackground, True)
                try:
                    self.view.page().setBackgroundColor(Qt.transparent)
                except Exception:
                    pass
                try:
                    self.view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
                    self.view.page().settings().setAttribute(QWebEngineSettings.FullScreenSupportEnabled, False)
                except Exception:
                    pass

                self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.view.setFixedHeight(max(24, target_h - (top + bot)))
                self.view.installEventFilter(self)

                outer.addWidget(self.view)

                self.channel = QWebChannel(self.view.page())
                self.media = MediaControlBridge(self)
                self.channel.registerObject("media", self.media)
                self.view.page().setWebChannel(self.channel)

                mode_val = "popup" if compact else "window"
                lower = self.src_path.lower()
                if lower.endswith(".html"):
                    url = QUrl.fromLocalFile(self.src_path)
                    if url.hasQuery():
                        parts = [p for p in url.query().split("&") if not p.startswith("mode=")]
                        parts.append(f"mode={mode_val}")
                        url.setQuery("&".join(parts))
                    else:
                        url.setQuery(f"mode={mode_val}")
                    self.view.load(url)
                elif lower.endswith(".py"):
                    html = self._load_inline_html_from_py(self.src_path, mode_val)
                    base = QUrl.fromLocalFile(os.path.dirname(self.src_path) + os.sep)
                    self.view.setHtml(html, baseUrl=base)
                else:
                    try:
                        with open(self.src_path, "r", encoding="utf-8", errors="replace") as f:
                            raw = f.read()
                    except Exception as e:
                        raw = f"Fehler beim Lesen: {e}"
                    esc = (raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
                    html = f"<!doctype html><meta charset='utf-8'><pre style='margin:0;padding:8px;font:13px/1.3 monospace;'>{esc}</pre>"
                    base = QUrl.fromLocalFile(os.path.dirname(self.src_path) + os.sep)
                    self.view.setHtml(html, baseUrl=base)
            except Exception:
                print("HtmlInlineButton init error:", traceback.format_exc())
                self._fallback_area(outer)
        else:
            self._fallback_area(outer)

    def _load_inline_html_from_py(self, file_path: str, mode: str) -> str:
        try:
            spec = importlib.util.spec_from_file_location("inline_html_module", file_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            fn = getattr(mod, "get_inline_html", None)
            if not callable(fn):
                return f"<!doctype html><meta charset='utf-8'><p style='margin:8px;color:#c00;'>Fehlende Funktion <code>get_inline_html(mode)</code> in {os.path.basename(file_path)}</p>"
            html = fn(mode=mode)
            if not isinstance(html, str):
                return "<!doctype html><meta charset='utf-8'><p style='margin:8px;color:#c00;'>get_inline_html() muss String liefern.</p>"
            return self._wrap_no_scroll(html)
        except Exception:
            return f"<!doctype html><meta charset='utf-8'><pre style='margin:8px;color:#c00;'>Fehler in {os.path.basename(file_path)}:\n{traceback.format_exc()}</pre>"

    def _wrap_no_scroll(self, inner_html: str) -> str:
        return f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{{margin:0;padding:0;height:100%;overflow:hidden;background:transparent}}*{{box-sizing:border-box}}</style>
{inner_html}
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
new QWebChannel(qt.webChannelTransport, ch => {{ window.media = ch.objects.media;
}});
['wheel','touchmove'].forEach(evt => window.addEventListener(evt, e => e.preventDefault(), {{passive:false}}));
window.addEventListener('keydown', e => {{ const blocked=['ArrowUp','ArrowDown','PageUp','PageDown',' '];
  if(e.ctrlKey||blocked.includes(e.key)){{e.preventDefault();e.stopPropagation();}} }}, true);
</script>"""

    def eventFilter(self, obj, event):
        if obj is getattr(self, "view", None):
            et = event.type()
            if et in (QEvent.Wheel, QEvent.Gesture, QEvent.NativeGesture): return True
            if et == QEvent.KeyPress:
                try:
                    key = event.key();
                    mods = event.modifiers()
                except Exception:
                    key, mods = None, 0
                if mods & Qt.ControlModifier: return True
                if key in {Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Space}: return True
        return super().eventFilter(obj, event)

    def _fallback_area(self, outer_layout: QVBoxLayout):
        btn = QPushButton("Im Browser öffnen")
        btn.clicked.connect(lambda: __import__("webbrowser").open('file://' + self.src_path))
        outer_layout.addWidget(btn)


# --- DPI ---
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

# --- Theme globals ---
theme = "dark"  # "dark" | "light"
mode = "Window"


def is_dark(): return theme == "dark"


def current_stylesheet():
    return """
        QWidget { background-color: #2E2E2E; color: #FFFFFF; }
    """ if is_dark() else """
        QWidget { background-color: #FFFFFF; color: #000000; }
    """


def set_theme(new_theme, app=None):
    global theme
    theme = new_theme
    if app is not None:
        app.setStyleSheet(current_stylesheet())
        app.setProperty("toolbar_theme", theme)
    else:
        inst = QApplication.instance()
        if inst is not None:
            inst.setProperty("toolbar_theme", theme)


def ensure_sample_plugin(script_root: str):
    if not os.path.exists(script_root):
        os.makedirs(script_root, exist_ok=True)
    entries = [e for e in os.listdir(script_root) if not e.startswith("_")]
    if entries: return
    try:
        sample_path = os.path.join(script_root, "timer_plugin.py")
        with open(sample_path, "w", encoding="utf-8") as f:
            f.write(
                "from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout\n"
                "from PyQt5.QtCore import QTimer\n\n"
                "class PluginWidget(QWidget):\n"
                "    def __init__(self, mode='Window'):\n"
                "        super().__init__()\n"
                "        layout = QVBoxLayout(self)\n"
                "        title = QLabel('⏱️ Timer-Plugin')\n"
                "        title.setStyleSheet('font-weight: bold; font-size: 16px;')\n"
                "        layout.addWidget(title)\n"
                "        self.label = QLabel('0 s')\n"
                "        self.label.setStyleSheet('font-size: 24px;')\n"
                "        layout.addWidget(self.label)\n"
                "        row = QHBoxLayout()\n"
                "        start_btn = QPushButton('Start')\n"
                "        stop_btn = QPushButton('Stop')\n"
                "        reset_btn = QPushButton('Reset')\n"
                "        row.addWidget(start_btn); row.addWidget(stop_btn); row.addWidget(reset_btn)\n"
                "        layout.addLayout(row)\n"
                "        self.timer = QTimer(self); self.timer.setInterval(1000)\n"
                "        self.timer.timeout.connect(self.update_time)\n"
                "        self.seconds = 0\n"
                "        start_btn.clicked.connect(self.timer.start)\n"
                "        stop_btn.clicked.connect(self.timer.stop)\n"
                "        reset_btn.clicked.connect(self.reset)\n"
                "    def update_time(self):\n"
                "        self.seconds += 1; self.label.setText(f'{self.seconds} s')\n"
                "    def reset(self):\n"
                "        self.seconds = 0; self.label.setText('0 s')\n"
            )
        html_dir = os.path.join(script_root, "html_timer")
        os.makedirs(html_dir, exist_ok=True)
        with open(os.path.join(html_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write("""<!DOCTYPE html><meta charset="utf-8">
<title>HTML Timer</title>
<style>body{font-family:system-ui,Arial;margin:16px}.time{font-size:32px;margin:12px 0}button{padding:8px 12px;margin-right:8px}</style>
<h1>⏱️ HTML Timer (Demo)</h1><div class="time" id="t">0 s</div>
<button onclick="start()">Start</button><button onclick="stop()">Stop</button><button onclick="reset()">Reset</button>
<script>
let sec=0,itv=null;function tick(){sec++;document.getElementById('t').textContent=sec+' s'}
function start(){if(!itv)itv=setInterval(tick,1000)}function stop(){if(itv){clearInterval(itv);itv=null}}
function reset(){sec=0;document.getElementById('t').textContent='0 s'}
</script>""")
    except Exception:
        print("Fehler beim Anlegen der Beispiel-Plugins/HTML:", traceback.format_exc())


class ButtonContentMixin:
    SCRIPT_FOLDER = "scripts"

    def _base_dir(self) -> str:
        return os.path.abspath(getattr(self, "SCRIPT_FOLDER", "scripts"))

    def _default_dir(self) -> str:
        return self._base_dir()

    def _resolve_path(self, p: str) -> str:
        if not p: return None
        p = os.path.expanduser(p.strip())
        if os.path.isabs(p): return os.path.abspath(p)
        cur = getattr(self, "current_path", None)
        base = os.path.abspath(cur) if cur else self._base_dir()
        return os.path.abspath(os.path.normpath(os.path.join(base, p)))

    def init_button_state(self):
        self.current_path = os.path.abspath(self.SCRIPT_FOLDER)
        ensure_sample_plugin(self.current_path)
        if not os.path.exists(self.current_path):
            os.makedirs(self.current_path)
        self.watcher = QFileSystemWatcher(self)
        try:
            if os.path.exists(self.current_path):
                self.watcher.addPath(self.current_path)
                self.watcher.directoryChanged.connect(self.on_directory_changed)
        except Exception:
            print("Watcher-Probleme:", traceback.format_exc())
        self.plugin_loader = None

    def set_plugin_loader(self, loader_callable):
        self.plugin_loader = loader_callable

    def on_directory_changed(self, path):
        self.add_buttons(self.layout)

    def add_buttons(self, layout):
        for i in reversed(range(layout.count())):
            it = layout.itemAt(i)
            w = it.widget() if it else None
            if w: w.setParent(None)

        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        if self.current_path != os.path.abspath(self.SCRIPT_FOLDER):
            back_button = QPushButton("← Zurück")
            back_button.clicked.connect(self.go_back)
            back_button.setObjectName("back_button")
            layout.addWidget(back_button)

        # Header (Favoriten/… weggelassen, Fokus: Stabilität & Suche)

        try:
            raw_entries = os.listdir(self.current_path)
        except Exception:
            raw_entries = []

        # --- FILTER LOGIK (NEU) ---
        config = ConfigManager.load_config()
        hidden_items = config.get("hidden_plugins", [])

        filtered = [e for e in raw_entries if not e.startswith("_") and e not in hidden_items]

        q = (getattr(self, "_search_query", "") or "").strip().lower()
        if q:
            filtered = [e for e in filtered if q in e.lower()]

        def group_key(name: str):
            nl = name.lower()
            full = os.path.join(self.current_path, name)
            if nl.startswith("[html]"):  return (0, nl)
            if nl.endswith(".html"):     return (1, nl)
            if nl.endswith(".py"):       return (2, nl)
            if os.path.isdir(full):      return (3, nl)
            return (4, nl)

        entries = sorted(filtered, key=group_key)
        is_popup = getattr(self, "IS_POPUP", False)

        for entry in entries:
            full_path = os.path.join(self.current_path, entry)
            try:
                if os.path.isdir(full_path):
                    b = QPushButton(entry)
                    b.clicked.connect(lambda _, p=full_path: self.enter_directory(p))
                    b.setProperty("entry_type", "folder")
                    b.setMinimumHeight(60)
                    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    layout.addWidget(b)
                    continue

                lower = entry.lower()
                if lower.startswith("[html]"):
                    card = HtmlInlineButton(html_path=full_path, compact=is_popup)
                    card.setProperty("entry_type", "file_html_inline")
                    layout.addWidget(card)
                    continue

                if lower.endswith(".py"):
                    b = QPushButton(entry[:-3])
                    b.clicked.connect(lambda _, p=full_path: self.run_script(p))
                    b.setProperty("entry_type", "file")
                    b.setMinimumHeight(60)
                    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    layout.addWidget(b)
                    continue

                if lower.endswith(".html"):
                    b = QPushButton(entry)
                    b.clicked.connect(lambda _, p=full_path: self.run_script(p))
                    b.setProperty("entry_type", "file")
                    b.setMinimumHeight(60)
                    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    layout.addWidget(b)
                    continue
            except Exception:
                print("Fehler beim Buttonbau:", traceback.format_exc())

        self.update_button_styles(layout)

    def enter_directory(self, path):
        setattr(self, "_search_query", "")
        self.current_path = path
        self.add_buttons(self.layout)

    def go_back(self):
        setattr(self, "_search_query", "")
        parent = os.path.dirname(self.current_path)
        root = os.path.abspath(self.SCRIPT_FOLDER)
        try:
            if os.path.commonpath([parent, root]) == root:
                self.current_path = parent
                QTimer.singleShot(0, lambda: self.add_buttons(self.layout))
                return
        except Exception:
            print("Back-Fehler:", traceback.format_exc())
        self.current_path = root
        QTimer.singleShot(0, lambda: self.add_buttons(self.layout))

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
            print("Skriptstart fehlgeschlagen:", traceback.format_exc())

    def update_button_styles(self, layout):
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, QPushButton):
                if w.objectName() == "back_button":
                    w.setMinimumHeight(40)
                    w.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {'#666666' if is_dark() else '#BBBBBB'};
                            color: {'#FFFFFF' if is_dark() else '#000000'};
                            font-weight: bold;
                        }}
                        QPushButton:hover {{ background-color: {'#777777' if is_dark() else '#CCCCCC'}; }}
                    """)
                else:
                    entry_type = w.property("entry_type")
                    if entry_type == "folder":
                        w.setStyleSheet(f"""
                            QPushButton {{ background-color: {'#3A4A6A' if is_dark() else '#c2d1ff'};
                            color: {'#fff' if is_dark() else '#000'}; }}
                            QPushButton:hover {{ background-color: {'#4B5B6B' if is_dark() else '#a1b8ff'}; }}
                        """)
                    elif entry_type == "file":
                        w.setStyleSheet(f"""
                            QPushButton {{ background-color: {'#3A3A3A' if is_dark() else '#EEEEEE'}; color: {'#fff' if is_dark() else '#000'}; }}
                            QPushButton:hover {{ background-color: {'#505050' if is_dark() else '#CCCCCC'}; }}
                        """)
            else:
                if w and w.property("entry_type") == "file_html_inline":
                    w.setStyleSheet(f"""
                        QWidget {{ background-color: {'#354A3A' if is_dark() else '#d5f0d9'};
                            color: {'#fff' if is_dark() else '#000'}; border-radius: 8px; padding: 8px;
                        }}
                        QWidget:hover {{ background-color: {'#456A4B' if is_dark() else '#bfe8c6'};
                        }}
                    """)


class HtmlPluginContainer(QWidget):
    def __init__(self, html_path: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"HTML: {os.path.basename(html_path)}"))
        if WEBENGINE_AVAILABLE:
            try:
                view = QWebEngineView(self)
                view.load(QUrl.fromLocalFile(os.path.abspath(html_path)))
                try:
                    view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
                except Exception:
                    pass
                layout.addWidget(view)
            except Exception:
                layout.addWidget(QLabel("PyQtWebEngine-Fehler. Öffne extern."))
                b = QPushButton("Im Standardbrowser öffnen")
                layout.addWidget(b)
                b.clicked.connect(lambda: __import__("webbrowser").open('file://' + os.path.abspath(html_path)))
        else:
            layout.addWidget(QLabel("PyQtWebEngine nicht installiert."))
            b = QPushButton("Im Standardbrowser öffnen")
            layout.addWidget(b)
            b.clicked.connect(lambda: __import__("webbrowser").open('file://' + os.path.abspath(html_path)))


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
        if self.popup and getattr(self.popup, "isVisible", lambda: False)():
            self.popup.show_explorer()
        elif self.main_window:
            self.main_window.go_back_to_explorer()


class PopupWindow(ButtonContentMixin, QWidget):
    def __init__(self, app=None):
        super().__init__()
        self.IS_POPUP = True
        self.app = app
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        self.channel = None
        self.bridge = ThemeBridge(main_window=None, popup=self)

        self.html_toolbar = QWebEngineView(self) if WEBENGINE_AVAILABLE else QWidget(self)
        if WEBENGINE_AVAILABLE:
            self.html_toolbar.setFixedHeight(40)
            self.html_toolbar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.channel = QWebChannel(self.html_toolbar.page())
            self.channel.registerObject("bridge", self.bridge)
            self.html_toolbar.page().setWebChannel(self.channel)
            self.html_toolbar.setVisible(False)
            try:
                self.html_toolbar.page().setBackgroundColor(QColor(0, 0, 0, 0))
            except Exception:
                pass

        self._build_html_toolbar()

        self.explorer_container = QWidget()
        self.layout = QVBoxLayout(self.explorer_container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.init_button_state()

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self._update_scrollbar_theme()
        self.scroll_area.setWidget(self.explorer_container)

        self.pages = QStackedWidget()
        self.pages.addWidget(self.scroll_area)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(4)
        self.main_layout.addWidget(self.html_toolbar)
        self.main_layout.addWidget(self.pages)

        self._update_relative_size()
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def _safe_close_active_page(self):
        if self.pages.currentWidget() is self.scroll_area: return
        page_widget = self.pages.currentWidget()
        if not page_widget: return
        if WEBENGINE_AVAILABLE:
            try:
                for view in page_widget.findChildren(QWebEngineView):
                    try:
                        view.load(QUrl("about:blank"))
                    except Exception:
                        pass
            except Exception:
                pass
        try:
            self.pages.removeWidget(page_widget)
        except Exception:
            pass
        page_widget.setParent(None)
        QTimer.singleShot(0, page_widget.deleteLater)

    def _update_scrollbar_theme(self):
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: {'#292929' if is_dark() else '#d6d6d6'};
                width: 10px; margin: 0; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {'#666' if is_dark() else '#999'};
                min-height: 20px; border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

    def _update_relative_size(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geo = screen.geometry()
        self.width_size = int(geo.width() * 0.15)
        self.height_size = int(geo.height() * 0.5)

    def _build_html_toolbar(self):
        if not WEBENGINE_AVAILABLE:
            return
        mode_now = theme
        explorer_btn_html = f'<button id="explorerBtn" class="toolbar-btn {mode_now}">← Explorer</button>'
        html_code = f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8" />
            <title>Toolbar</title>
            <style>
                html, body {{ background: rgba(0,0,0,0) !important; margin: 0; overflow: hidden !important; }}
                .toolbar-container {{
                    display: flex; align-items: center;
                    justify-content: flex-start; /* linksorientiert */
                    height: 32px; padding: 0 8px; gap: 8px;
                }}
                .toolbar-btn {{
                    padding: 4px 10px; border: 1px solid transparent;
                    border-radius: 6px; font-size: 12px; font-weight: 500;
                    cursor: pointer; background: transparent !important;
                    transition: background .3s, color .3s, border-color .3s;
                    min-height: 28px; min-width: 80px; outline: none;
                }}
                .light {{ background: #ffffff; color: #333; border-color: #dddddd; }}
                .dark  {{ background: #2c2c2c; color: #f5f5f5; border-color: #444; }}
            </style>
        </head>
        <body>
            <div class="toolbar-container">
                {explorer_btn_html}
            </div>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script>
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.bridge = channel.objects.bridge;
                    const eb = document.getElementById("explorerBtn");
                    if (eb) eb.onclick = function() {{ bridge.goBackToExplorer(); }};
                    const themeBtn = document.getElementById("themeBtn");
                    if (themeBtn) themeBtn.onclick = function() {{ bridge.toggleTheme(); }};
                }});
                window.setBtnMode = function(m) {{
                    ['explorerBtn','themeBtn'].forEach(function(id){{
                        var el = document.getElementById(id);
                        if (el) el.className = "toolbar-btn " + m;
                    }});
                }}
            </script>
        </body>
        </html>
        """
        self.html_toolbar.setHtml(html_code)

    def show_toolbar_with_theme_check(self):
        if not WEBENGINE_AVAILABLE: return
        self.html_toolbar.setVisible(True)
        safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def show_plugin_widget(self, widget: QWidget, title: str = ""):
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(8, 8, 8, 8)
        header = QLabel(f"🧩 Plugin: {title}")
        header.setStyleSheet("font-weight:600;font-size:15px;margin-bottom:6px;")
        v.addWidget(header)
        v.addWidget(widget)
        self.pages.addWidget(container)
        self.pages.setCurrentWidget(container)
        self.show_toolbar_with_theme_check()

    def show_explorer(self):
        self._safe_close_active_page()
        self.pages.setCurrentWidget(self.scroll_area)
        if WEBENGINE_AVAILABLE: self.html_toolbar.setVisible(False)

    def toggle_theme(self):
        global theme
        theme = "light" if is_dark() else "dark"
        set_theme(theme, self.app)
        self.update_button_styles(self.layout)
        safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def show_popup(self):
        self._update_scrollbar_theme()
        self.add_buttons(self.layout)
        self.update_button_styles(self.layout)
        self._build_html_toolbar()
        self._update_relative_size()
        self.setFixedSize(self.width_size, self.height_size)
        cur = QCursor.pos()
        start_x, start_y = cur.x(), cur.y()
        end_x, end_y = start_x - self.width_size, start_y - self.height_size
        self.animation.setStartValue(QRect(start_x, start_y + 50, self.width_size, self.height_size))
        self.animation.setEndValue(QRect(end_x, end_y, self.width_size, self.height_size))
        self.animation.start()
        self.show()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


# --- POMODORO WIDGET (NEU - ERWEITERT) ---
class PomodoroToolbarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.work_minutes = 25
        self.break_minutes = 5
        self.is_work_phase = True  # True = Work, False = Break
        self.remaining_seconds = self.work_minutes * 60
        self.total_seconds = self.remaining_seconds

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)

        # 1. Der Button/Text Teil
        self.btn = QPushButton()
        self.btn.clicked.connect(self._toggle_timer)
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn.customContextMenuRequested.connect(self._show_context_menu)
        self.btn.setFixedHeight(30)
        self.layout.addWidget(self.btn)

        # 2. Die Progress Bar (rechts daneben)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(14)
        self.progress.setFixedWidth(80)  # Breite des Balkens
        self.layout.addWidget(self.progress)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

        self._update_text()
        self.update_style()
        self.apply_config()  # Initial Konfiguration anwenden

    def apply_config(self):
        config = ConfigManager.load_config()
        visible = config.get("pomodoro_visible", True)
        style = config.get("pomodoro_style", "large")

        self.setVisible(visible)

        if style == "large":
            self.progress.setVisible(True)
            self.btn.setFixedWidth(120)
        else:
            self.progress.setVisible(False)
            self.btn.setFixedWidth(150)

        self.update_style()

    def update_style(self):
        # Passt sich dem Stil der SearchBar an
        bg_color = '#292929' if is_dark() else '#ffffff'
        text_color = '#ffffff' if is_dark() else '#3a3a3a'
        border_color = '#777777' if is_dark() else '#888888'
        hover_border = '#555555'

        # Progress Bar Farben
        prog_bg = '#444' if is_dark() else '#ddd'
        prog_chunk = '#4CAF50' if self.is_work_phase else '#2196F3'  # Grün für Arbeit, Blau für Pause

        self.btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1.5px solid {border_color};
                border-radius: 12px;
                padding: 0 12px;
                font-family: monospace;
                font-weight: bold;
                font-size: 13px;
                outline: none;
            }}
            QPushButton:hover {{
                border: 2px solid {hover_border};
            }}
        """)

        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {border_color};
                border-radius: 7px;
                background-color: {prog_bg};
            }}
            QProgressBar::chunk {{
                background-color: {prog_chunk};
                border-radius: 6px;
            }}
        """)

    def _tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self._update_text()
        else:
            self.timer.stop()
            self.start_alarm()  # --- ALARM AUSLÖSEN ---
            self._switch_phase()

    def start_alarm(self):
        # 1. Visuelles Signal: Taskleisten-Icon blinken lassen (Windows Standard)
        app = QApplication.instance()
        if app:
            app.alert(self.window(), 3000)  # Blinkt für 3 Sekunden oder bis Fokus

        # 2. Visuelles Signal: Button blinkt orange/rot
        self.blink_count = 0
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self._blink_tick)
        self.blink_timer.start(500)  # Alle 500ms umschalten

    def _blink_tick(self):
        self.blink_count += 1
        if self.blink_count % 2 == 1:
            # Alarm-Farbe (Orange/Rot)
            self.btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff5500;
                    color: #ffffff;
                    border: 2px solid #ff0000;
                    border-radius: 12px;
                    padding: 0 12px;
                    font-family: monospace;
                    font-weight: bold;
                    font-size: 13px;
                }
            """)
        else:
            # Normaler Style
            self.update_style()

        if self.blink_count >= 8:  # Nach 4 Mal Blinken (8 Ticks) aufhören
            self.blink_timer.stop()
            self.update_style()

    def _switch_phase(self):
        self.is_work_phase = not self.is_work_phase
        base_min = self.work_minutes if self.is_work_phase else self.break_minutes
        self.remaining_seconds = base_min * 60
        self.total_seconds = self.remaining_seconds  # Reset total for progress

        # Visueller Hinweis, dass Phase vorbei ist (Text ändert sich)
        icon = "🍅" if self.is_work_phase else "☕"
        phase_name = "Work" if self.is_work_phase else "Break"
        self.btn.setText(f"🔔 {phase_name}!")
        self.update_style()

    def _toggle_timer(self):
        if hasattr(self, 'blink_timer') and self.blink_timer.isActive():
            self.blink_timer.stop()
            self.update_style()
            return  # Klick während Alarm stoppt nur den Alarm

        if self.timer.isActive():
            self.timer.stop()
            self._update_text(paused=True)
        else:
            if self.total_seconds == 0: self.total_seconds = self.remaining_seconds or 1
            self.timer.start()
            self._update_text(paused=False)

    def _update_text(self, paused=False):
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        icon = "🍅" if self.is_work_phase else "☕"
        state_icon = "⏸" if paused else ""
        if not self.timer.isActive() and not paused:
            # Stopped completely or just initialized
            state_icon = "▶"

        self.btn.setText(f"{icon} {mins:02d}:{secs:02d} {state_icon}")

        # Update Progress Bar
        if self.total_seconds > 0:
            # Prozent der vergangen Zeit
            elapsed = self.total_seconds - self.remaining_seconds
            perc = int((elapsed / self.total_seconds) * 100)
            # Oder restzeit? User wollte "restzeit bzw absolvierte zeit"
            # Hier: Füllstand = absolvierte Zeit
            self.progress.setValue(perc)
        else:
            self.progress.setValue(0)

    def _show_context_menu(self, pos):
        menu = QMenu(self)

        action_reset = QAction("Reset Timer", self)
        action_reset.triggered.connect(self._reset_timer)
        menu.addAction(action_reset)

        menu.addSeparator()

        action_set_work = QAction("Set Work Time...", self)
        action_set_work.triggered.connect(self._set_work_time)
        menu.addAction(action_set_work)

        action_set_break = QAction("Set Break Time...", self)
        action_set_break.triggered.connect(self._set_break_time)
        menu.addAction(action_set_break)

        menu.exec_(self.btn.mapToGlobal(pos))

    def _reset_timer(self):
        self.timer.stop()
        if hasattr(self, 'blink_timer'): self.blink_timer.stop()
        self.is_work_phase = True
        self.remaining_seconds = self.work_minutes * 60
        self.total_seconds = self.remaining_seconds
        self._update_text()
        self.update_style()

    def _set_work_time(self):
        val, ok = QInputDialog.getInt(self, "Pomodoro Settings", "Work minutes:", self.work_minutes, 1, 120)
        if ok:
            self.work_minutes = val
            self._reset_timer()

    def _set_break_time(self):
        val, ok = QInputDialog.getInt(self, "Pomodoro Settings", "Break minutes:", self.break_minutes, 1, 60)
        if ok:
            self.break_minutes = val
            if not self.is_work_phase:  # If currently in break, reset to new break time
                self.remaining_seconds = self.break_minutes * 60
                self.total_seconds = self.remaining_seconds
            self._update_text()


# --- EINSTELLUNGEN WIDGET (NEU) ---
class SettingsWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # Header
        lbl = QLabel("⚙ Einstellungen")
        lbl.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.layout.addWidget(lbl)

        # --- Pomodoro Section ---
        gb_pomo = QGroupBox("Pomodoro Timer")
        form_pomo = QFormLayout(gb_pomo)

        self.cb_pomo_visible = QCheckBox("In Taskleiste anzeigen")
        self.cb_pomo_visible.clicked.connect(self.save_settings)

        self.cb_pomo_style = QCheckBox("Große Ansicht (mit Balken)")
        self.cb_pomo_style.clicked.connect(self.save_settings)

        form_pomo.addRow("Sichtbarkeit:", self.cb_pomo_visible)
        form_pomo.addRow("Stil:", self.cb_pomo_style)
        self.layout.addWidget(gb_pomo)

        # --- Plugins Section ---
        gb_plugins = QGroupBox("Plugins verwalten")
        v_plugins = QVBoxLayout(gb_plugins)
        v_plugins.addWidget(QLabel("Wähle Plugins ab, die im Explorer ausgeblendet werden sollen:"))

        self.list_plugins = QListWidget()
        v_plugins.addWidget(self.list_plugins)
        self.list_plugins.itemChanged.connect(self.save_plugins_list)

        self.layout.addWidget(gb_plugins)

        self.load_values()

    def load_values(self):
        config = ConfigManager.load_config()
        self.cb_pomo_visible.setChecked(config.get("pomodoro_visible", True))
        self.cb_pomo_style.setChecked(config.get("pomodoro_style", "large") == "large")

        # Populate List
        self.list_plugins.clear()
        base_dir = self.main_window._base_dir()
        if os.path.exists(base_dir):
            all_files = sorted([f for f in os.listdir(base_dir) if not f.startswith("_")])
            hidden = config.get("hidden_plugins", [])
            for f in all_files:
                item = QListWidgetItem(f)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if f in hidden:
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setCheckState(Qt.Checked)
                self.list_plugins.addItem(item)

    def save_settings(self):
        config = ConfigManager.load_config()
        config["pomodoro_visible"] = self.cb_pomo_visible.isChecked()
        config["pomodoro_style"] = "large" if self.cb_pomo_style.isChecked() else "small"
        ConfigManager.save_config(config)

        # Apply immediately
        if hasattr(self.main_window, "pomodoro"):
            self.main_window.pomodoro.apply_config()

    def save_plugins_list(self, item):
        hidden = []
        for i in range(self.list_plugins.count()):
            it = self.list_plugins.item(i)
            if it.checkState() == Qt.Unchecked:
                hidden.append(it.text())

        config = ConfigManager.load_config()
        config["hidden_plugins"] = hidden
        ConfigManager.save_config(config)

        # Refresh Main Window Explorer
        self.main_window.add_buttons(self.main_window.layout)


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app, popup=None):
        super().__init__()
        self.setWindowIcon(QIcon("ProgrammIcon.ico") if os.path.exists("ProgrammIcon.ico") else QIcon())
        self.app = app
        self.popup = popup
        self._update_relative_size()
        self.setMinimumSize(self.width_size, self.height_size)

        self._search_query = ""

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
                self.channel = QWebChannel(self.html_toolbar.page())
                self.bridge = ThemeBridge(main_window=self, popup=self.popup)
                self.channel.registerObject("bridge", self.bridge)
                self.html_toolbar.page().setWebChannel(self.channel)
            except Exception:
                pass

        if WEBENGINE_AVAILABLE:
            self.html_toolbar.setFixedHeight(44)
            self.html_toolbar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # --- Suchfeld (oben rechts) ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search plugins...")
        self.search_input.setFixedHeight(max(28, int(self.height_size * 0.08)))
        self.search_input.setFixedWidth(220)  # FIXED WIDTH OF SEARCH BAR
        self.search_input.textChanged.connect(self.search_plugins)
        self.search_input.setStyleSheet(f"""
                   QLineEdit {{
                       background: {'#292929' if is_dark() else '#ffffff'};
                       color: {'#ffffff' if is_dark() else '#3a3a3a'};
                       padding: 8px 10px;
                       border-radius: 12px;
                       border: 1.5px solid {'#777777' if is_dark() else '#888888'};
                       outline: none;
                       transition: all 0.3s cubic-bezier(0.19, 1, 0.22, 1);
                       box-shadow: 0px 0px 20px -18px;
                   }}
                   QLineEdit:hover {{
                       border: 2px solid #555555;
                       box-shadow: 0px 0px 20px -17px;
                   }}
                   QLineEdit:active {{
                       transform: scale(0.95);
                   }}
                   QLineEdit:focus {{
                       border: 2px solid grey;
                   }}
               """)

        toolbar.addWidget(self.html_toolbar)
        toolbar.addStretch()

        # --- POMODORO TIMER ---
        self.pomodoro = PomodoroToolbarWidget()
        toolbar.addWidget(self.pomodoro)

        # Abstandhalter zwischen Pomodoro und Suche
        spacer_label = QLabel(" ")
        spacer_label.setFixedWidth(5)
        toolbar.addWidget(spacer_label)

        toolbar.addWidget(self.search_input)

        # --- EINSTELLUNGEN BUTTON (NEU) ---
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setToolTip("Einstellungen")
        self.settings_btn.setFixedHeight(max(28, int(self.height_size * 0.08)))
        self.settings_btn.setFixedWidth(40)
        self.settings_btn.clicked.connect(self.open_settings)
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {'#444' if is_dark() else '#ddd'};
                color: {'#fff' if is_dark() else '#000'};
                border: none; border-radius: 10px; font-size: 16px;
            }}
            QPushButton:hover {{ background-color: {'#555' if is_dark() else '#ccc'}; }}
        """)
        toolbar.addWidget(self.settings_btn)

        # --- Beenden-Button ---
        self.exit_button = QPushButton("Beenden")
        self.exit_button.setFixedHeight(max(28, int(self.height_size * 0.08)))
        self.exit_button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#aa3333' if is_dark() else '#ff5555'};
                                color: white;
                                font-weight: bold;
                                border: none;
                                border-radius: 10px;
                                padding: 6px 12px;
                            }}
                            QPushButton:hover {{
                                background-color: {'#cc4444' if is_dark() else '#ff6666'};
                            }}
                        """)
        # 🧠 Option 1: Sauber beenden
        self.exit_button.clicked.connect(self.app.quit)
        toolbar.addWidget(self.exit_button)

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
        self._update_scrollbar_theme()
        self.scroll_area.setWidget(self.button_container)

        self.pages.addWidget(self.scroll_area)
        # --- TAB WIDGET for Main Window Plugins ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabBar().setDrawBase(False)  # Clean look without base line
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.pages.addWidget(self.tab_widget)

        self.central_layout.addWidget(self.pages)
        self.setCentralWidget(self.central)

        self.init_button_state()
        self.add_buttons(self.layout)
        self.set_plugin_loader(self.load_plugin_from_path)
        self._update_tab_style()

    def open_settings(self):
        # Check ob Settings Tab schon offen
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Einstellungen":
                self.tab_widget.setCurrentIndex(i)
                self.pages.setCurrentWidget(self.tab_widget)
                self.show_explorer_btn = True
                self._build_html_toolbar()
                return

        # Neuen Tab erstellen
        settings_page = SettingsWidget(self)
        self.tab_widget.addTab(settings_page, "Einstellungen")
        self.tab_widget.setCurrentWidget(settings_page)
        self.pages.setCurrentWidget(self.tab_widget)

        self.show_explorer_btn = True
        self._build_html_toolbar()
        if WEBENGINE_AVAILABLE:
            safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def close_tab(self, index):
        widget = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)

        # Plugin aufräumen / stoppen
        if WEBENGINE_AVAILABLE:
            for view in widget.findChildren(QWebEngineView):
                try:
                    view.load(QUrl("about:blank"))
                except Exception:
                    pass
        widget.deleteLater()

        # Wenn keine Tabs mehr da sind, zurück zum Explorer
        if self.tab_widget.count() == 0:
            self.go_back_to_explorer()

    def search_plugins(self):
        self._search_query = (self.search_input.text() or "").strip().lower()
        self.add_buttons(self.layout)

    def _open_link_as_plugin(self, qurl: QUrl):
        try:
            if qurl.isLocalFile():
                self.load_plugin_from_path(qurl.toLocalFile(), source_widget=self)
                return
            page = QWidget()
            v = QVBoxLayout(page)
            v.setContentsMargins(12, 12, 12, 12)
            v.setSpacing(8)
            if WEBENGINE_AVAILABLE:
                view = QWebEngineView(page)
                try:
                    view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
                except Exception:
                    pass
                view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                view.load(qurl)
                v.addWidget(view, 1)
            else:
                v.addWidget(QLabel("PyQtWebEngine nicht verfügbar."))

            # Öffne als Tab statt Page Stack Widget ersetzen
            self.tab_widget.addTab(page, "Link")
            self.tab_widget.setCurrentWidget(page)
            self.pages.setCurrentWidget(self.tab_widget)

            self.show_explorer_btn = True
            self._build_html_toolbar()
            if WEBENGINE_AVAILABLE: safe_run_js(self.html_toolbar,
                                                f'window.setThemeUI && window.setThemeUI("{theme}");')
        except Exception as e:
            QMessageBox.critical(self, "Link öffnen fehlgeschlagen", str(e))

    def _update_scrollbar_theme(self):
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: {'#292929' if is_dark() else '#ffffff'};
                width: 10px; margin: 0; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #666;
                min-height: 20px; border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

    def _update_tab_style(self):
        # Modern Flat/Card Design
        if is_dark():
            tab_bg = "#222222"
            tab_fg = "#AAAAAA"
            sel_bg = "#3A4A6A"  # Matching the 'Folder' blue-ish tone
            sel_fg = "#FFFFFF"
            hover_bg = "#333333"
            pane_border = "#3A4A6A"
        else:
            tab_bg = "#E0E0E0"
            tab_fg = "#555555"
            sel_bg = "#c2d1ff"  # Matching the Light 'Folder' tone
            sel_fg = "#000000"
            hover_bg = "#EAEAEA"
            pane_border = "#c2d1ff"

        # Dynamisches Padding und Mindestbreite
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border-top: 2px solid {pane_border};
                position: absolute;
                top: -1px;
                background: transparent;
            }}
            QTabBar::tab {{
                background: {tab_bg};
                color: {tab_fg};
                padding: 8px 20px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border: none;
                min-width: 60px;
                /* Small minimum width */
            }}
            QTabBar::tab:selected {{
                background: {sel_bg};
                color: {sel_fg};
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background: {hover_bg};
            }}
        """)

    def _update_searchbar_theme(self):
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {'#292929' if is_dark() else '#ffffff'};
                color: {'#ffffff' if is_dark() else '#292929'};
                padding: 8px 10px; border-radius: 12px;
                border: 1.5px solid {'#777777' if is_dark() else '#888888'};
                outline: none;
            }}
        """)

    def _update_relative_size(self):
        screen = QGuiApplication.screenAt(self.pos()) or QGuiApplication.primaryScreen()
        geo = screen.geometry()
        self.width_size = int(geo.width() * 0.4)
        self.height_size = int(geo.height() * 0.4)

    def _build_html_toolbar(self):
        mode = theme
        explorer_btn = f'<button id="explorerBtn" class="toolbar-btn {mode}" style="margin-left:1.5rem;display:{"inline-block" if self.show_explorer_btn else "none"};">← Explorer</button>'

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
                    display: flex; align-items: center;
                    height: 2.5rem;
                    padding: 0 2vw;
                    gap: 0.5em;
                    background: transparent !important;
                }}

                /* --- Toggle Switch --- */
                .switch {{
                  position: relative; width: 5rem;
                  height: 2.5rem;
                  cursor: pointer;
                  user-select: none;
                  margin-top: 0.4rem;
                }}

                .switch input {{
                  position: absolute; top: 0;
                  left: 0;
                  width: 100%;
                  height: 100%;
                  margin: 0;
                  opacity: 0;
                  cursor: pointer;
                  z-index: 3;
                }}

                .background {{
                  position: absolute; width: 5rem;
                  height: 2rem;
                  border-radius: 1.25rem;
                  border: 0.15rem solid #202020;
                  background: linear-gradient(to right, #484848 0%, #202020 100%);
                  transition: all 0.3s;
                  top: 0;
                  left: 0;
                  z-index: 1;
                }}

                .stars1,
                .stars2 {{
                  position: absolute; height: 0.2rem;
                  width: 0.2rem;
                  background: #FFFFFF;
                  border-radius: 50%;
                  transition: 0.3s all ease;
                }}
                .stars1 {{ top: 0.2em; right: 0.8em; }}
                .stars2 {{ top: 1.3em; right: 1.75em; }}

                .sun-moon {{
                  position: absolute; left: 0;
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
                  position: absolute; top: 0.1em;
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
                self.html_toolbar.setAttribute(Qt.WA_TranslucentBackground, True)
                self.html_toolbar.setAttribute(Qt.WA_OpaquePaintEvent, False)
                try:
                    self.html_toolbar.page().setBackgroundColor(QColor(0, 0, 0, 0))
                except Exception:
                    pass
        except Exception:
            import traceback
            print("Fehler beim Setzen der Toolbar HTML:", traceback.format_exc())

    def toggle_theme(self):
        global theme
        theme = "light" if is_dark() else "dark"
        set_theme(theme, self.app)
        self.update_button_styles(self.layout)
        self._update_scrollbar_theme()
        self._update_searchbar_theme()
        self._update_tab_style()  # Styles for Tabs update

        # Update Pomodoro Style
        if hasattr(self, 'pomodoro'):
            self.pomodoro.update_style()

        # Update Settings Button
        btn_bg = '#444' if is_dark() else '#ddd'
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {btn_bg}; color: {'#fff' if is_dark() else '#000'}; border-radius: 10px; font-size: 16px; }}
            QPushButton:hover {{ background-color: {'#555' if is_dark() else '#ccc'}; }}
        """)

        if self.popup and self.popup.isVisible():
            self.popup.update_button_styles(self.popup.layout)
            self.popup._update_scrollbar_theme()
        if WEBENGINE_AVAILABLE:
            safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def go_back_to_explorer(self):
        # Wir schließen die Tabs NICHT. Wir wechseln nur die Ansicht.
        # Damit laufen Plugins im Hintergrund weiter.
        self.pages.setCurrentWidget(self.scroll_area)
        self.show_explorer_btn = False
        self._build_html_toolbar()
        if WEBENGINE_AVAILABLE:
            safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def load_plugin_from_path(self, path: str, source_widget=None):
        try:
            plugin_mode = "Popup" if isinstance(source_widget, PopupWindow) else "Window"

            # --- POPUP LOGIC (Old logic, no tabs) ---
            if plugin_mode == "Popup":
                if path.lower().endswith('.py'):
                    widget = self.load_python_plugin_widget(path, mode=plugin_mode)
                    if widget is None: return
                elif path.lower().endswith('.html'):
                    widget = HtmlPluginContainer(path)
                else:
                    subprocess.Popen([sys.executable, path])
                    return

                source_widget.show_plugin_widget(widget, os.path.basename(path))
                return

            # --- MAIN WINDOW LOGIC (With Tabs) ---
            # 1. Check if plugin is already running in a tab
            for i in range(self.tab_widget.count()):
                w = self.tab_widget.widget(i)
                if w.property("plugin_path") == path:
                    # Switch to existing tab
                    self.tab_widget.setCurrentIndex(i)
                    self.pages.setCurrentWidget(self.tab_widget)
                    self.show_explorer_btn = True
                    self._build_html_toolbar()
                    if WEBENGINE_AVAILABLE:
                        safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')
                    return

            # 2. Load new plugin
            if path.lower().endswith('.py'):
                widget = self.load_python_plugin_widget(path, mode=plugin_mode)
                if widget is None: return
            elif path.lower().endswith('.html'):
                widget = HtmlPluginContainer(path)
            else:
                subprocess.Popen([sys.executable, path])
                return

            # 3. Add to tabs
            container = QWidget()
            v = QVBoxLayout(container)
            v.setContentsMargins(12, 12, 12, 12)
            # Im Tab brauchen wir den Header "Plugin: Name" nicht zwingend, da der Tab-Reiter den Namen hat.
            # Aber wir lassen das Widget sauber im Container.
            v.addWidget(widget)

            container.setProperty("plugin_path", path)
            self.tab_widget.addTab(container, os.path.basename(path))
            self.tab_widget.setCurrentWidget(container)

            self.pages.setCurrentWidget(self.tab_widget)
            self.show_explorer_btn = True
            self._build_html_toolbar()
            if WEBENGINE_AVAILABLE:
                safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

        except Exception as e:
            QMessageBox.critical(source_widget or self, "Fehler beim Laden", f"{e}")

    def load_python_plugin_widget(self, path: str, mode="Window"):
        try:
            spec = importlib.util.spec_from_file_location("plugin_module", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, "PluginWidget", None)
            if cls is not None and isinstance(cls, type):
                try:
                    return cls(mode=mode)
                except TypeError:
                    return cls()
            return None
        except Exception:
            return None


class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)
        self.setStyleSheet(current_stylesheet())
        self.setProperty("toolbar_theme", theme)
        self.popup = PopupWindow(app=self)
        self.main_window = MainAppWindow(self, popup=self.popup)
        self.popup.set_plugin_loader(self.main_window.load_plugin_from_path)
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon("TrayIcon.ico") if os.path.exists("TrayIcon.ico") else QIcon())
        self.tray.setVisible(True)
        self.tray.activated.connect(self.on_tray_activated)
        self.aboutToQuit.connect(self.teardown)

    def on_tray_activated(self, reason):
        global mode
        if reason == QSystemTrayIcon.Context:
            mode = "Popup"
            self.popup.show_popup()
        elif reason == QSystemTrayIcon.Trigger:
            if self.main_window.isMinimized() or not self.main_window.isVisible():
                mode = "Window"
                self.main_window.showNormal()
                self.main_window.activateWindow()
                self.main_window.raise_()
            else:
                self.main_window.activateWindow()
                self.main_window.raise_()

    def teardown(self):
        try:
            try:
                self.tray.activated.disconnect(self.on_tray_activated)
            except Exception:
                pass
            if WEBENGINE_AVAILABLE:
                try:
                    if hasattr(self.popup, "html_toolbar"):
                        self.popup.html_toolbar.hide()
                        self.popup.html_toolbar.deleteLater()
                except Exception:
                    pass
                try:
                    if hasattr(self.main_window, "html_toolbar"):
                        self.main_window.html_toolbar.hide()
                        self.main_window.html_toolbar.deleteLater()
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    try:
        import ctypes, platform

        if platform.system().lower() == "windows":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"meinefirma.skriptstarter.1.0")
    except Exception:
        pass
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())