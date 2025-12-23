# --- tray_launcher.py (HTML lightswitch + safe back + search + stability + TABS v2 + Settings) ---

# TO MAKE EXE OF TRAYLAUNCHER USE FOLLOWING COMMAND IN TERMINAL:
# pyinstaller --noconsole --onefile --icon=ProgrammIcon.ico --add-data "scripts;scripts" tray_launcher.py

try:
    import pytz
    import dateutil.rrule
    import icalendar
    import uuid
except ImportError:
    print("WARNUNG: Optionale Plugin-Abhängigkeiten (pytz, dateutil, icalendar) fehlen.")

import sys
import os
import subprocess
import importlib.util
import traceback

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QHBoxLayout, QLabel,
    QStackedWidget, QMessageBox, QScrollArea, QLineEdit, QFileDialog,
    QTabWidget, QTabBar, QDialog, QRadioButton, QButtonGroup
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
new QWebChannel(qt.webChannelTransport, ch => {{ window.media = ch.objects.media; }});
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

# --- Theme & Global Config ---
theme = "dark"
mode = "Window"
use_glass_mode = True  # Default: Glas an (damit auch forced Dark Mode)


def is_dark():
    # Wenn Glas an ist, ist es immer Dark für die UI-Logik
    if use_glass_mode:
        return True
    return theme == "dark"


def current_stylesheet():
    if use_glass_mode:
        # Glas/Transparent Basis -> Text weiß
        return "QWidget { background-color: transparent; color: #FFFFFF; }"
    else:
        # Opaque Basis
        if is_dark():
            return "QWidget { background-color: #2E2E2E; color: #FFFFFF; }"
        else:
            return "QWidget { background-color: #F0F0F0; color: #000000; }"


def glass_css():
    """Liefert CSS für Container: Entweder Glas (nur Dark) oder Opaque (Dark/Light)."""
    if use_glass_mode:
        # Transparenter Glas-Look (nur Dark Mode erlaubt)
        return ("background: rgba(18,18,22,0.55);"
                "border: 1px solid rgba(255,255,255,0.08);"
                "border-radius: 14px;")
    else:
        # Opaque / Solide Styles
        if theme == "light":
            # Hell & Solide
            return ("background: #FFFFFF;"
                    "border: 1px solid #CCC;"
                    "border-radius: 14px; color: #333;")
        else:
            # Dunkel & Solide
            return ("background: #2E2E2E;"
                    "border: 1px solid #444;"
                    "border-radius: 14px; color: #FFF;")


def glass_button_css():
    """Button-Look (Base, Hover) abhängig von Modus."""
    if use_glass_mode:
        # Glas Dark
        base = ("background: rgba(255,255,255,0.08);"
                "color: #f1f1f1;"
                "border: 1px solid rgba(255,255,255,0.12);"
                "border-radius: 10px;")
        hover = "background: rgba(255,255,255,0.14);"
    else:
        # Opaque
        if theme == "light":
            base = ("background: #E0E0E0;"
                    "color: #1a1a1a;"
                    "border: 1px solid #BBB;"
                    "border-radius: 10px;")
            hover = "background: #D0D0D0;"
        else:
            base = ("background: #3E3E3E;"
                    "color: #f1f1f1;"
                    "border: 1px solid #555;"
                    "border-radius: 10px;")
            hover = "background: #4E4E4E;"
    return base, hover


def set_theme(new_theme, app=None):
    global theme
    theme = new_theme
    # Property setzen, damit Listener reagieren
    if app is not None:
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

        try:
            raw_entries = os.listdir(self.current_path)
        except Exception:
            raw_entries = []
        filtered = [e for e in raw_entries if not e.startswith("_")]

        q = (getattr(self, "_search_query", "") or "").strip().lower()
        if q:
            filtered = [e for e in filtered if q in e.lower()]

        def group_key(name: str):
            nl = name.lower();
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
        base_btn, hover_btn = glass_button_css()
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if isinstance(w, QPushButton):
                if w.objectName() == "back_button":
                    w.setMinimumHeight(40)
                    w.setStyleSheet(f"""
                        QPushButton {{
                            {base_btn}
                            font-weight: 600;
                            padding: 8px 12px;
                        }}
                        QPushButton:hover {{ {hover_btn} }}
                    """)
                else:
                    entry_type = w.property("entry_type")
                    if entry_type == "folder":
                        w.setStyleSheet(f"""
                            QPushButton {{
                                {base_btn}
                                font-weight: 600;
                            }}
                            QPushButton:hover {{ {hover_btn} }}
                        """)
                    elif entry_type == "file":
                        w.setStyleSheet(f"""
                            QPushButton {{
                                {base_btn}
                            }}
                            QPushButton:hover {{ {hover_btn} }}
                        """)
            else:
                if w and w.property("entry_type") == "file_html_inline":
                    w.setStyleSheet(f"""
                        QWidget {{
                            {glass_css()}
                            padding: 8px;
                        }}
                        QWidget:hover {{
                            background: {'rgba(255,255,255,0.18)' if is_dark() else 'rgba(0,0,0,0.05)'};
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
                b = QPushButton("Im Standardbrowser öffnen");
                layout.addWidget(b)
                b.clicked.connect(lambda: __import__("webbrowser").open('file://' + os.path.abspath(html_path)))
        else:
            layout.addWidget(QLabel("PyQtWebEngine nicht installiert."))
            b = QPushButton("Im Standardbrowser öffnen");
            layout.addWidget(b)
            b.clicked.connect(lambda: __import__("webbrowser").open('file://' + os.path.abspath(html_path)))


class ThemeBridge(QObject):
    def __init__(self, main_window=None, popup=None):
        super().__init__()
        self.main_window = main_window
        self.popup = popup

    @pyqtSlot()
    def toggleTheme(self):
        # Wenn Glass Mode aktiv ist, ignorieren wir das Toggle, da Light Mode im Glass Mode unerwünscht ist.
        if use_glass_mode:
            return
        if self.main_window:
            self.main_window.toggle_theme()

    @pyqtSlot()
    def goBackToExplorer(self):
        if self.popup and getattr(self.popup, "isVisible", lambda: False)():
            self.popup.show_explorer()
        elif self.main_window:
            self.main_window.go_back_to_explorer()


# --- SETTINGS DIALOG ---
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setFixedSize(300, 200)
        self.setStyleSheet("""
            QDialog { background: #333; color: #FFF; }
            QRadioButton { color: #FFF; font-size: 14px; padding: 5px; }
            QPushButton { background: #555; color: #FFF; border: 1px solid #777; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background: #666; }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Design-Modus wählen:", self))

        self.group = QButtonGroup(self)

        self.rb_opaque = QRadioButton("Klassisch (Opaque)\n[Light & Dark möglich]")
        self.rb_glass = QRadioButton("Transparent (Glas)\n[Nur Dark Mode]")

        self.group.addButton(self.rb_opaque)
        self.group.addButton(self.rb_glass)
        layout.addWidget(self.rb_opaque)
        layout.addWidget(self.rb_glass)

        # Set current state
        if use_glass_mode:
            self.rb_glass.setChecked(True)
        else:
            self.rb_opaque.setChecked(True)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Speichern")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def accept(self):
        global use_glass_mode, theme
        old_glass = use_glass_mode

        if self.rb_glass.isChecked():
            use_glass_mode = True
            theme = "dark"  # Force Dark
        else:
            use_glass_mode = False
            # Theme beibehalten oder default

        super().accept()

        # Trigger update on parent
        if self.parent() and hasattr(self.parent(), "refresh_all_styles"):
            self.parent().refresh_all_styles()


class PopupWindow(ButtonContentMixin, QWidget):
    def __init__(self, app=None):
        super().__init__()
        self.IS_POPUP = True
        self.app = app
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

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
        self.layout.setContentsMargins(0, 0, 0, 0);
        self.layout.setSpacing(0)

        self.init_button_state()

        self.scroll_area = QScrollArea();
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self._update_scrollbar_theme()
        self.scroll_area.setWidget(self.explorer_container)

        self.pages = QStackedWidget();
        self.pages.addWidget(self.scroll_area)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8);
        self.main_layout.setSpacing(4)
        self.main_layout.addWidget(self.html_toolbar);
        self.main_layout.addWidget(self.pages)

        # Initiale Styles
        self.setStyleSheet("")
        self.explorer_container.setStyleSheet(glass_css())
        self.pages.setStyleSheet("background: transparent;")

        self._update_relative_size();
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(500);
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
        page_widget.setParent(None);
        QTimer.singleShot(0, page_widget.deleteLater)

    def _update_scrollbar_theme(self):
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: rgba(0,0,0,0.04);
                width: 10px; margin: 0; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {'rgba(255,255,255,0.28)' if is_dark() else 'rgba(0,0,0,0.25)'};
                min-height: 20px; border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

    def _update_relative_size(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geo = screen.geometry();
        self.width_size = int(geo.width() * 0.15);
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
                    display: flex;
                    align-items: center;
                    justify-content: flex-start;
                    height: 32px;
                    padding: 0 8px;
                    gap: 8px;
                }}
                .toolbar-btn {{
                    padding: 4px 10px;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 500;
                    cursor: pointer;
                    background: transparent !important;
                    transition: background .3s, color .3s, border-color .3s;
                    min-height: 28px;
                    min-width: 80px;
                    outline: none;
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
                }});
                window.setBtnMode = function(m) {{
                    ['explorerBtn'].forEach(function(id){{
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
        container = QWidget();
        v = QVBoxLayout(container);
        v.setContentsMargins(8, 8, 8, 8)
        header = QLabel(f"🧩 Plugin: {title}");
        header.setStyleSheet("font-weight:600;font-size:15px;margin-bottom:6px;")
        v.addWidget(header);
        v.addWidget(widget)
        self.pages.addWidget(container);
        self.pages.setCurrentWidget(container)
        self.show_toolbar_with_theme_check()

    def show_explorer(self):
        self._safe_close_active_page()
        self.pages.setCurrentWidget(self.scroll_area)
        if WEBENGINE_AVAILABLE: self.html_toolbar.setVisible(False)

    def show_popup(self):
        self._update_scrollbar_theme();
        self.add_buttons(self.layout);
        self.update_button_styles(self.layout)
        self._build_html_toolbar();
        self._update_relative_size();
        self.setFixedSize(self.width_size, self.height_size)

        # Styles aktualisieren je nach Modus
        self.explorer_container.setStyleSheet(glass_css())

        cur = QCursor.pos();
        start_x, start_y = cur.x(), cur.y()
        end_x, end_y = start_x - self.width_size, start_y - self.height_size
        self.animation.setStartValue(QRect(start_x, start_y + 50, self.width_size, self.height_size))
        self.animation.setEndValue(QRect(end_x, end_y, self.width_size, self.height_size))
        self.animation.start();
        self.show();
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore();
        self.hide()


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app, popup=None):
        super().__init__()
        self.setWindowIcon(QIcon("ProgrammIcon.ico") if os.path.exists("ProgrammIcon.ico") else QIcon())
        self.app = app;
        self.popup = popup
        self._update_relative_size();
        self.setMinimumSize(self.width_size, self.height_size)

        # Translucent Attribut ist wichtig für Glas-Modus
        # Im Opaque Modus stört es nicht zwingend, aber wir müssen den Background dann solid malen.
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._search_query = ""

        self.central = QWidget();
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

        # --- Suchfeld ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search plugins...")
        self.search_input.setFixedHeight(max(28, int(self.height_size * 0.08)))
        self.search_input.setFixedWidth(220)
        self._update_searchbar_theme()

        toolbar.addWidget(self.html_toolbar);
        toolbar.addStretch();
        toolbar.addWidget(self.search_input)

        # --- Settings Button ---
        self.settings_button = QPushButton("⚙️")
        self.settings_button.setFixedHeight(max(28, int(self.height_size * 0.08)))
        self.settings_button.setFixedWidth(40)
        self.settings_button.clicked.connect(self.open_settings)
        self._update_settings_btn_style()
        toolbar.addWidget(self.settings_button)

        # --- Beenden-Button ---
        self.exit_button = QPushButton("Beenden")
        self.exit_button.setFixedHeight(max(28, int(self.height_size * 0.08)))
        self.exit_button.clicked.connect(self.app.quit)
        self._update_exit_btn_style()
        toolbar.addWidget(self.exit_button)

        tb = QWidget();
        tb.setLayout(toolbar);
        self.central_layout.addWidget(tb)

        self.pages = QStackedWidget()

        self.button_container = QWidget()

        # Styles anwenden
        self.central.setStyleSheet(glass_css())
        self.button_container.setStyleSheet(glass_css())
        self.pages.setStyleSheet("background: transparent;")

        self.layout = QVBoxLayout(self.button_container);
        self.layout.setContentsMargins(0, 0, 0, 0);
        self.layout.setSpacing(0)

        self.scroll_area = QScrollArea();
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame);
        self._update_scrollbar_theme()
        self.scroll_area.setWidget(self.button_container)

        self.pages.addWidget(self.scroll_area);

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabBar().setDrawBase(False)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.pages.addWidget(self.tab_widget)

        self.central_layout.addWidget(self.pages)
        self.setCentralWidget(self.central)

        self.init_button_state();
        self.add_buttons(self.layout)
        self.set_plugin_loader(self.load_plugin_from_path)
        self._update_tab_style()

        # Initial Searchbar Event
        self.search_input.textChanged.connect(self.search_plugins)

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()

    def refresh_all_styles(self):
        # Wird vom SettingsDialog aufgerufen
        set_theme(theme, self.app)

        # 1. Update CSS Vars
        self.central.setStyleSheet(glass_css())
        self.button_container.setStyleSheet(glass_css())

        # 2. Update Element Styles
        self.update_button_styles(self.layout)
        self._update_searchbar_theme()
        self._update_exit_btn_style()
        self._update_settings_btn_style()
        self._update_tab_style()
        self._update_scrollbar_theme()

        # 3. Update HTML Toolbar (Hide Toggle if Glass Mode)
        self._build_html_toolbar()

        if WEBENGINE_AVAILABLE:
            safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

        # 4. Popup Refresh if active
        if self.popup:
            self.popup.explorer_container.setStyleSheet(glass_css())
            self.popup.update_button_styles(self.popup.layout)
            self.popup._update_scrollbar_theme()

    def _update_settings_btn_style(self):
        if use_glass_mode:
            self.settings_button.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255,255,255,0.1); color: #fff;
                    border: 1px solid rgba(255,255,255,0.2); border-radius: 10px; font-size: 16px;
                }}
                QPushButton:hover {{ background: rgba(255,255,255,0.2); }}
            """)
        else:
            self.settings_button.setStyleSheet(f"""
                QPushButton {{
                    background: {'#444' if is_dark() else '#DDD'}; 
                    color: {'#FFF' if is_dark() else '#333'};
                    border: 1px solid {'#666' if is_dark() else '#AAA'};
                    border-radius: 10px; font-size: 16px;
                }}
                QPushButton:hover {{ background: {'#555' if is_dark() else '#CCC'}; }}
            """)

    def _update_exit_btn_style(self):
        self.exit_button.setStyleSheet(f"""
            QPushButton {{
                background: {'rgba(255,90,90,0.18)' if is_dark() else 'rgba(255,90,90,0.16)'};
                color: {'#ffecec' if is_dark() else '#3a1a1a'};
                font-weight: 700;
                border: 1px solid {'rgba(255,120,120,0.35)' if is_dark() else 'rgba(255,120,120,0.32)'};
                border-radius: 10px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: {'rgba(255,90,90,0.28)' if is_dark() else 'rgba(255,90,90,0.24)'};
            }}
        """)

    def close_tab(self, index):
        widget = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        if WEBENGINE_AVAILABLE:
            for view in widget.findChildren(QWebEngineView):
                try:
                    view.load(QUrl("about:blank"))
                except Exception:
                    pass
        widget.deleteLater()
        if self.tab_widget.count() == 0:
            self.go_back_to_explorer()

    def search_plugins(self):
        self._search_query = (self.search_input.text() or "").strip().lower()
        self.add_buttons(self.layout)

    def _open_link_as_plugin(self, qurl: QUrl):
        try:
            if qurl.isLocalFile():
                self.load_plugin_from_path(qurl.toLocalFile(), source_widget=self);
                return
            page = QWidget();
            v = QVBoxLayout(page);
            v.setContentsMargins(12, 12, 12, 12);
            v.setSpacing(8)
            if WEBENGINE_AVAILABLE:
                view = QWebEngineView(page)
                try:
                    view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
                except Exception:
                    pass
                view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                view.load(qurl);
                v.addWidget(view, 1)
            else:
                v.addWidget(QLabel("PyQtWebEngine nicht verfügbar."))
            self.tab_widget.addTab(page, "Link")
            self.tab_widget.setCurrentWidget(page)
            self.pages.setCurrentWidget(self.tab_widget)
            self.show_explorer_btn = True;
            self._build_html_toolbar()
            if WEBENGINE_AVAILABLE: safe_run_js(self.html_toolbar,
                                                f'window.setThemeUI && window.setThemeUI("{theme}");')
        except Exception as e:
            QMessageBox.critical(self, "Link öffnen fehlgeschlagen", str(e))

    def _update_scrollbar_theme(self):
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: rgba(0,0,0,0.04);
                width: 10px; margin: 0; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {'rgba(255,255,255,0.28)' if is_dark() else 'rgba(0,0,0,0.25)'}; min-height: 20px; border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        """)

    def _update_tab_style(self):
        if is_dark():
            tab_bg = "#222222";
            tab_fg = "#AAAAAA";
            sel_bg = "#3A4A6A";
            sel_fg = "#FFFFFF";
            hover_bg = "#333333";
            pane_border = "#3A4A6A"
        else:
            tab_bg = "#E0E0E0";
            tab_fg = "#555555";
            sel_bg = "#c2d1ff";
            sel_fg = "#000000";
            hover_bg = "#EAEAEA";
            pane_border = "#c2d1ff"

        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{ border-top: 2px solid {pane_border}; position: absolute; top: -1px; background: transparent; }}
            QTabBar::tab {{
                background: {tab_bg}; color: {tab_fg}; padding: 8px 20px; margin-right: 4px;
                border-top-left-radius: 8px; border-top-right-radius: 8px; border: none; min-width: 60px;
            }}
            QTabBar::tab:selected {{ background: {sel_bg}; color: {sel_fg}; font-weight: bold; }}
            QTabBar::tab:hover:!selected {{ background: {hover_bg}; }}
        """)

    def _update_searchbar_theme(self):
        if use_glass_mode:
            # Glas Style
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background: #292929; color: #ffffff;
                    padding: 8px 10px; border-radius: 12px;
                    border: 1.5px solid #777777; outline: none;
                }}
            """)
        else:
            # Opaque Style
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
        geo = screen.geometry();
        self.width_size = int(geo.width() * 0.4);
        self.height_size = int(geo.height() * 0.4)

    def _build_html_toolbar(self):
        mode = theme
        explorer_btn = f'<button id="explorerBtn" class="toolbar-btn {mode}" style="margin-left:1.5rem; display:{"inline-block" if self.show_explorer_btn else "none"};">← Explorer</button>'

        # Wenn Glas-Modus aktiv, verstecken wir den Switch, um Light-Mode Unfälle zu vermeiden
        switch_display = "none" if use_glass_mode else "block"

        html_code = f"""
        <!DOCTYPE html>
        <html lang="de">
        <head>
            <meta charset="UTF-8" />
            <title>Toolbar</title>
            <style>
                html, body {{ height: 100%; margin: 0; padding: 0; }}
                .toolbar-btn {{
                    padding: 0.25em 0.675em; border: 0.07em solid transparent; border-radius: 0.38em;
                    font-size: 1em; font-weight: 500; cursor: pointer; transition: background 0.3s, color 0.3s, border-color 0.3s;
                    min-height: 2.25em; min-width: 5em; background: transparent !important; outline: none;
                }}
                .light {{ background: #ffffff; color: #333; border-color: #dddddd; }}
                .dark  {{ background: #2c2c2c; color: #f5f5f5; border-color: #444; }}

                .toolbar-container {{
                    display: flex; align-items: center; height: 2.5rem; padding: 0 2vw; gap: 0.5em; background: transparent !important;
                }}

                /* Toggle Switch Container */
                .switch {{
                  display: {switch_display}; 
                  position: relative; width: 5rem; height: 2.5rem; cursor: pointer; user-select: none; margin-top: 0.4rem;
                }}
                .switch input {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; z-index: 3; }}
                .background {{
                  position: absolute; width: 5rem; height: 2rem; border-radius: 1.25rem;
                  border: 0.15rem solid #202020; background: linear-gradient(to right, #484848 0%, #202020 100%);
                  transition: all 0.3s; top: 0; left: 0; z-index: 1;
                }}
                .stars1, .stars2 {{ position: absolute; height: 0.2rem; width: 0.2rem; background: #FFFFFF; border-radius: 50%; transition: 0.3s all ease; }}
                .stars1 {{ top: 0.2em; right: 0.8em; }} .stars2 {{ top: 1.3em; right: 1.75em; }}
                .sun-moon {{
                  position: absolute; left: 0; top: 0; height: 1.5rem; width: 1.5rem; margin: 0.25rem;
                  background: #FFFDF2; border-radius: 50%; border: 0.15rem solid #DEE2C6; transition: all 0.5s ease; z-index: 2;
                }}
                .sun-moon .dots {{
                  position: absolute; top: 0.1em; left: 0.7em; height: 0.5rem; width: 0.5rem; background: #EFEEDB;
                  border: 0.15rem solid #DEE2C6; border-radius: 50%; transition: 0.4s all ease;
                }}
                .switch input:checked ~ .sun-moon {{
                  left: calc(100% - 2rem); background: #F5EC59; border-color: #E7C65C; transform: rotate(-25deg);
                }}
                .switch input:checked ~ .background {{
                  border: 0.15rem solid #78C1D5; background: linear-gradient(to right, #78C1D5 0%, #BBE7F5 100%);
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

                    if (toggle) {{
                        toggle.addEventListener("change", function() {{
                            bridge.toggleTheme();
                            if (explorerBtn) {{
                                if (toggle.checked) {{
                                    explorerBtn.classList.remove('dark'); explorerBtn.classList.add('light');
                                }} else {{
                                    explorerBtn.classList.remove('light'); explorerBtn.classList.add('dark');
                                }}
                            }}
                        }});
                    }}
                    if (explorerBtn) {{
                        explorerBtn.onclick = function() {{ bridge.goBackToExplorer(); }};
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
        if use_glass_mode:
            # Kein Toggle im Glass Mode
            return
        theme = "light" if is_dark() else "dark"
        set_theme(theme, self.app)
        self.refresh_all_styles()

    def go_back_to_explorer(self):
        self.pages.setCurrentWidget(self.scroll_area)
        self.show_explorer_btn = False
        self._build_html_toolbar()
        if WEBENGINE_AVAILABLE:
            safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def load_plugin_from_path(self, path: str, source_widget=None):
        try:
            plugin_mode = "Popup" if isinstance(source_widget, PopupWindow) else "Window"
            if plugin_mode == "Popup":
                if path.lower().endswith('.py'):
                    widget = self.load_python_plugin_widget(path, mode=plugin_mode)
                    if widget is None: return
                elif path.lower().endswith('.html'):
                    widget = HtmlPluginContainer(path)
                else:
                    subprocess.Popen([sys.executable, path]);
                    return
                source_widget.show_plugin_widget(widget, os.path.basename(path))
                return

            for i in range(self.tab_widget.count()):
                w = self.tab_widget.widget(i)
                if w.property("plugin_path") == path:
                    self.tab_widget.setCurrentIndex(i)
                    self.pages.setCurrentWidget(self.tab_widget)
                    self.show_explorer_btn = True
                    self._build_html_toolbar()
                    if WEBENGINE_AVAILABLE:
                        safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')
                    return

            if path.lower().endswith('.py'):
                widget = self.load_python_plugin_widget(path, mode=plugin_mode)
                if widget is None: return
            elif path.lower().endswith('.html'):
                widget = HtmlPluginContainer(path)
            else:
                subprocess.Popen([sys.executable, path]);
                return

            container = QWidget();
            v = QVBoxLayout(container);
            v.setContentsMargins(12, 12, 12, 12)
            v.addWidget(widget)
            container.setProperty("plugin_path", path)
            self.tab_widget.addTab(container, os.path.basename(path))
            self.tab_widget.setCurrentWidget(container)
            self.pages.setCurrentWidget(self.tab_widget)
            self.show_explorer_btn = True;
            self._build_html_toolbar()
            if WEBENGINE_AVAILABLE:
                safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

        except Exception as e:
            QMessageBox.critical(source_widget or self, "Fehler beim Laden", f"{e}")

    def load_python_plugin_widget(self, path: str, mode="Window"):
        try:
            spec = importlib.util.spec_from_file_location("plugin_module", path)
            mod = importlib.util.module_from_spec(spec);
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
            mode = "Popup";
            self.popup.show_popup()
        elif reason == QSystemTrayIcon.Trigger:
            if self.main_window.isMinimized() or not self.main_window.isVisible():
                mode = "Window";
                self.main_window.showNormal();
                self.main_window.activateWindow();
                self.main_window.raise_()
            else:
                self.main_window.activateWindow();
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
                        self.popup.html_toolbar.hide();
                        self.popup.html_toolbar.deleteLater()
                except Exception:
                    pass
                try:
                    if hasattr(self.main_window, "html_toolbar"):
                        self.main_window.html_toolbar.hide();
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