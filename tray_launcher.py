import sys
import os
import subprocess
import importlib.util
import traceback
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QHBoxLayout, QLabel,
    QStackedWidget, QMessageBox, QScrollArea, QLineEdit, QSpacerItem, QFileDialog
)
from PyQt5.QtGui import QCursor, QIcon, QColor, QGuiApplication
from PyQt5.QtCore import (
    Qt, QRect, QPoint, QFileSystemWatcher, QObject, pyqtSlot, QUrl, QPropertyAnimation, QEasingCurve, QEvent
)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
    from PyQt5.QtWebChannel import QWebChannel

    WEBENGINE_AVAILABLE = True
except Exception:
    WEBENGINE_AVAILABLE = False

# --- Windows Media Control Bridge (for WebChannel) ---

class MediaControlBridge(QObject):
    """Play/Pause/Next/Prev/Volume via WebChannel (Windows)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        import platform
        self._is_windows = (platform.system().lower() == "windows")
        if self._is_windows:
            import ctypes
            self._user32 = ctypes.windll.user32
            self.VK_MEDIA_NEXT_TRACK = 0xB0
            self.VK_MEDIA_PREV_TRACK = 0xB1
            self.VK_MEDIA_STOP       = 0xB2
            self.VK_MEDIA_PLAY_PAUSE = 0xB3
            self.VK_VOLUME_MUTE      = 0xAD
            self.VK_VOLUME_DOWN      = 0xAE
            self.VK_VOLUME_UP        = 0xAF

    def _tap(self, vk):
        if not getattr(self, "_is_windows", False):
            return
        KEYEVENTF_KEYUP = 0x0002
        self._user32.keybd_event(vk, 0, 0, 0)
        self._user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

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
    """
    Zeigt Inline-UI im Button:
    - Unterstützt Dateien mit Präfix [HTML] sowohl als .html (geladen) als auch als .py (liefert HTML-String).
    - .py-Datei muss eine Funktion get_inline_html(mode: str) -> str bereitstellen.
    - mode = "popup" (compact=True) oder "window".
    - Scroll/Zoom-Eingaben (Wheel/Gesten/CTRL+Zoom/Keys) auf Qt-Ebene deaktiviert.
    - Stellt WebChannel-Objekt 'media' für window.media bereit (Mediatasten).
    """
    def __init__(self, path: str = None, title_text: str = None,
                 min_height: int = 160, compact: bool = False, **kwargs):
        super().__init__()

        # Back-compat alias
        if path is None:
            path = kwargs.pop("html_path", None)
        if path is None:
            raise ValueError("HtmlInlineButton requires 'path' (or 'html_path').")

        self.setProperty("entry_type", "file_html_inline")
        self.src_path = os.path.abspath(path)
        self.compact = compact

        # Zielhöhe relativ zur nativen Buttonhöhe (DPI/Theme-sicher)
        probe = QPushButton("Wg")
        probe.setFont(self.font())
        base_h = max(28, probe.sizeHint().height())
        factor = 1.80 if not compact else 2.50   # Window größer, Popup kompakter
        target_h = int(base_h * factor)

        # Außenmargen schlank
        outer_top = max(4, target_h // 8)
        outer_bot = max(4, target_h // 8)

        self.setMinimumHeight(target_h)
        self.setMaximumHeight(target_h)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, outer_top, 8, outer_bot)
        outer.setSpacing(0)

        if WEBENGINE_AVAILABLE:
            try:
                self.view = QWebEngineView(self)
                self.view.setAttribute(Qt.WA_TranslucentBackground, True)
                self.view.page().setBackgroundColor(Qt.transparent)

                # Scrollbars aus
                try:
                    self.view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
                    self.view.page().settings().setAttribute(QWebEngineSettings.FullScreenSupportEnabled, False)
                except Exception:
                    pass

                # Höhe exakt an Container anpassen
                self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                self.view.setFixedHeight(max(24, target_h - (outer_top + outer_bot)))

                # Scroll/Zoom auf Qt-Ebene blocken
                self.view.installEventFilter(self)

                # WebChannel registrieren (window.media in HTML nutzbar)
                self.channel = QWebChannel(self.view.page())
                self.media = MediaControlBridge(self)
                self.channel.registerObject("media", self.media)
                self.view.page().setWebChannel(self.channel)

                outer.addWidget(self.view)

                # Render je nach Dateityp
                mode_val = "popup" if compact else "window"
                lower = self.src_path.lower()
                if lower.endswith(".html"):
                    # Lokale HTML mit ?mode=
                    url = QUrl.fromLocalFile(self.src_path)
                    if url.hasQuery():
                        parts = [p for p in url.query().split("&") if not p.startswith("mode=")]
                        parts.append(f"mode={mode_val}")
                        url.setQuery("&".join(parts))
                    else:
                        url.setQuery(f"mode={mode_val}")
                    self.view.load(url)

                elif lower.endswith(".py"):
                    # Python liefert HTML-String (get_inline_html(mode))
                    html = self._load_inline_html_from_py(self.src_path, mode_val)
                    # setHtml mit baseUrl für evtl. relative Assets
                    base = QUrl.fromLocalFile(os.path.dirname(self.src_path) + os.sep)
                    self.view.setHtml(html, baseUrl=base)

                else:
                    # Fallback: als Text anzeigen
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
        """Lädt Modul dynamisch und ruft get_inline_html(mode) -> str auf."""
        try:
            import importlib.util, types
            spec = importlib.util.spec_from_file_location("inline_html_module", file_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            fn = getattr(mod, "get_inline_html", None)
            if not callable(fn):
                return f"<!doctype html><meta charset='utf-8'><p style='margin:8px;color:#c00;'>Fehlende Funktion <code>get_inline_html(mode)</code> in {os.path.basename(file_path)}</p>"
            html = fn(mode=mode)
            if not isinstance(html, str):
                return "<!doctype html><meta charset='utf-8'><p style='margin:8px;color:#c00;'>get_inline_html() muss einen String zurückgeben.</p>"
            return self._wrap_no_scroll(html)
        except Exception as e:
            return f"<!doctype html><meta charset='utf-8'><pre style='margin:8px;color:#c00;'>Fehler in {os.path.basename(file_path)}:\n{traceback.format_exc()}</pre>"

    def _wrap_no_scroll(self, inner_html: str) -> str:
        """Sorgt dafür, dass die gelieferte HTML im Button höhenstabil bleibt & kein Scroll/Zoom zulässt."""
        return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html,body{{margin:0;padding:0;height:100%;overflow:hidden!important;background:transparent}}
  *{{box-sizing:border-box}}
</style>
{inner_html}
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  // WebChannel anbinden -> window.media.* nutzbar
  new QWebChannel(qt.webChannelTransport, ch => {{ window.media = ch.objects.media; }});
  // Scroll & Zoom in der Seite zusätzlich blocken
  ['wheel','touchmove'].forEach(evt => window.addEventListener(evt, e => e.preventDefault(), {{passive:false}}));
  window.addEventListener('keydown', e => {{
    const blocked = ['ArrowUp','ArrowDown','PageUp','PageDown',' '];
    if (e.ctrlKey || blocked.includes(e.key)) {{ e.preventDefault(); e.stopPropagation(); }}
  }}, true);
</script>
"""

    # Scroll/Zoom-Eingaben in der View blockieren
    def eventFilter(self, obj, event):
        if obj is getattr(self, "view", None):
            et = event.type()
            if et in (QEvent.Wheel, QEvent.Gesture, QEvent.NativeGesture):
                return True
            if et == QEvent.KeyPress:
                key = getattr(event, "key", lambda: None)()
                mods = getattr(event, "modifiers", lambda: 0)()
                if mods & Qt.ControlModifier:
                    return True
                if key in {Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Space}:
                    return True
        return super().eventFilter(obj, event)

    def _fallback_area(self, outer_layout: QVBoxLayout):
        btn = QPushButton("Im Browser öffnen")
        btn.clicked.connect(lambda: __import__("webbrowser").open('file://' + self.src_path))
        outer_layout.addWidget(btn)



from screeninfo import get_monitors
import ctypes

# --- High DPI Scaling aktivieren ---
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
# -----------------------------------

# --- Globale Theme-Variable ---
theme = "dark"
mode = "Window"

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
    # --- Favorites & path utils ---
    def _base_dir(self) -> str:
        return os.path.abspath(getattr(self, "SCRIPT_FOLDER", "scripts"))

    def _default_dir(self) -> str:
        return self._base_dir()

    def _favorites_store_path(self):
        return os.path.join(self._base_dir(), "_folders.json")

    def _resolve_path(self, p: str) -> str:
        if not p: return None
        p = os.path.expanduser(p.strip())
        if os.path.isabs(p): return os.path.abspath(p)
        cur = getattr(self, "current_path", None)
        base = os.path.abspath(cur) if cur else self._base_dir()
        return os.path.abspath(os.path.normpath(os.path.join(base, p)))

    def _to_storable(self, abs_path: str) -> str:
        abs_path = os.path.abspath(abs_path)
        base = self._base_dir()
        try:
            rel = os.path.relpath(abs_path, base)
            if not rel.startswith(".."):
                rel = rel.replace("\\", "/")
                return "./" + rel if not rel.startswith("./") else rel
        except Exception:
            pass
        return abs_path

    def _load_favorites(self):
        self._favorite_dirs = []
        try:
            import json
            p = self._favorites_store_path()
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f) or []
                for item in data:
                    if isinstance(item, str):
                        ap = self._resolve_path(item)
                        if ap and os.path.isdir(ap):
                            self._favorite_dirs.append(ap)
        except Exception:
            print("Favoriten laden fehlgeschlagen:", traceback.format_exc())

    def _save_favorites(self):
        try:
            import json
            p = self._favorites_store_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            store = [self._to_storable(d) for d in self._favorite_dirs if os.path.isdir(d)]
            with open(p, "w", encoding="utf-8") as f:
                json.dump(store, f, ensure_ascii=False, indent=2)
        except Exception:
            print("Favoriten konnten nicht gespeichert werden:", traceback.format_exc())

    def _ensure_in_favorites(self, path):
        path = os.path.abspath(path)
        if not hasattr(self, "_favorite_dirs"):
            self._load_favorites()
        if path not in self._favorite_dirs:
            self._favorite_dirs.append(path)
            self._save_favorites()

    def _remove_from_favorites(self, path):
        path = os.path.abspath(path)
        if not hasattr(self, "_favorite_dirs"):
            self._load_favorites()
        if path in self._favorite_dirs:
            self._favorite_dirs.remove(path)
            self._save_favorites()

    def _render_favorites(self, container: QWidget):
        if container is None: return
        lay = container.layout()
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w: w.setParent(None)

        if not hasattr(self, "_favorite_dirs"):
            self._load_favorites()

        default_path = os.path.abspath(self._default_dir())

        def _add_chip(path: str, removable: bool):
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)

            name = os.path.basename(path.rstrip("\\/")) or path
            b = QPushButton(name)
            b.setToolTip(path)
            b.setMinimumHeight(28)
            b.clicked.connect(lambda _, p=path: self.enter_directory(p))
            if removable:
                b.setObjectName("fav_btn"); b.setProperty("entry_type", "favorite")
            else:
                b.setObjectName("fav_btn_default"); b.setProperty("entry_type", "favorite_default")
            hl.addWidget(b)

            if removable:
                x = QPushButton("✕")
                x.setObjectName("fav_remove_btn")
                x.setToolTip("Aus Favoriten entfernen")
                x.setFixedSize(24, 24)
                x.clicked.connect(lambda _, p=path, c=container: self._on_remove_favorite(p, c))
                hl.addWidget(x)

            lay.addWidget(row)

        _add_chip(default_path, removable=False)
        for p in self._favorite_dirs:
            ap = os.path.abspath(p)
            if ap != default_path and os.path.isdir(ap):
                _add_chip(ap, removable=True)

    def _on_remove_favorite(self, path, container):
        if os.path.abspath(path) == os.path.abspath(self._default_dir()):
            return
        self._remove_from_favorites(path)
        self._render_favorites(container)

    def _ensure_header_controls(self, layout):
        header = None
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w and w.objectName() == "files_header_controls":
                header = w; break
        if header is None:
            header = QWidget()
            header.setObjectName("files_header_controls")
            h = QHBoxLayout(header)
            h.setContentsMargins(8, 8, 8, 8)
            h.setSpacing(8)

            btn_add = QPushButton("＋ Ordner hinzufügen")
            btn_add.setObjectName("btn_add_folder")
            btn_add.setToolTip("Verzeichnis wählen (Dialog)")
            btn_add.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            btn_add.clicked.connect(self._add_directory_via_dialog)
            h.addWidget(btn_add)

            fav_wrap = QWidget()
            fav_wrap.setObjectName("favorites_wrap")
            fav_layout = QHBoxLayout(fav_wrap)
            fav_layout.setContentsMargins(0, 0, 0, 0)
            fav_layout.setSpacing(6)
            h.addWidget(fav_wrap)

            layout.insertWidget(0, header)
        self._render_favorites(header.findChild(QWidget, "favorites_wrap"))

    def _add_directory_via_dialog(self):
        start_dir = getattr(self, "current_path", None) or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Verzeichnis auswählen", start_dir)
        if not path: return
        self._ensure_in_favorites(path)
        if hasattr(self, "layout"):
            header = None
            for i in range(self.layout.count()):
                w = self.layout.itemAt(i).widget()
                if w and w.objectName() == "files_header_controls":
                    header = w; break
            if header:
                fav_wrap = header.findChild(QWidget, "favorites_wrap")
                if fav_wrap: self._render_favorites(fav_wrap)
        if hasattr(self, "enter_directory") and callable(self.enter_directory):
            self.enter_directory(path)
        else:
            self.current_path = path
            if hasattr(self, "refresh") and callable(self.refresh):
                self.refresh()

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
        # clear existing
        for i in reversed(range(layout.count())):
            it = layout.itemAt(i)
            w = it.widget() if it else None
            if w: w.setParent(None)

        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        # watcher
        if hasattr(self, "watcher"):
            try:
                paths = self.watcher.directories()
                if paths and paths != self.current_path:
                    self.watcher.removePaths(paths)
                    self.watcher.addPath(self.current_path)
            except Exception:
                print("Fehler beim Aktualisieren des Watchers:", traceback.format_exc())

        # back button
        if self.current_path != os.path.abspath(self.SCRIPT_FOLDER):
            back_button = QPushButton("← Zurück")
            back_button.clicked.connect(self.go_back)
            back_button.setObjectName("back_button")
            layout.addWidget(back_button)

        # header only if not popup
        if not getattr(self, "IS_POPUP", False):
            self._ensure_header_controls(layout)

        # list entries
        try:
            raw_entries = os.listdir(self.current_path)
        except Exception:
            raw_entries = []
        filtered = [e for e in raw_entries if not e.startswith("_")]

        def group_key(name: str):
            nl = name.lower()
            full = os.path.join(self.current_path, name)
            if nl.startswith("[html]"):  return (0, nl)
            if nl.endswith(".html"):     return (1, nl)
            if nl.endswith(".py"):       return (2, nl)
            if os.path.isdir(full):      return (3, nl)
            return (4, nl)

        entries = sorted(filtered, key=group_key)
        # Buttons erzeugen
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
                is_html_prefix = lower.startswith("[html]")

                if is_html_prefix:
                    # Inline anzeigen: unterstützt sowohl .html als auch .py
                    card = HtmlInlineButton(
                        html_path=full_path,
                        title_text=None,
                        compact=is_popup
                    )
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
            else:
                # Inline-HTML widget styling
                if button and button.property("entry_type") == "file_html_inline":
                    button.setStyleSheet(f"""
                        QWidget {{
                            background-color: {'#354A3A' if is_dark() else '#d5f0d9'};
                            color: {'#FFFFFF' if is_dark() else '#000000'};
                            border-radius: 8px;
                            padding: 8px;
                        }}
                        QWidget:hover {{
                            background-color: {'#456A4B' if is_dark() else '#bfe8c6'};
                        }}
                    """)

    def update_scrollbar_theme(self):
        if hasattr(self, "scroll_area") and self.scroll_area:
            self.scroll_area.setStyleSheet(f"""
                QScrollArea {{ background: transparent; }}
                QScrollBar:vertical {{
                    background: {'#292929' if is_dark() else '#ffffff'};
                    width: 10px;
                    margin: 0;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #666;
                    min-height: 20px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                    background: none;
                    height: 0;
                }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                    background: none;
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
        self.IS_POPUP = True
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
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: {'#292929' if theme=="dark" else '#ffffff'};
                width: 10px;
                margin: 0;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #666;
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
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

    def update_scrollbar_theme(self):
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: {'#292929' if is_dark() else '#d6d6d6'};
                width: 10px;
                margin: 0;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {'#666' if is_dark() else '#999'};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)

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
        self.update_scrollbar_theme()
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

        # --- Suchfeld (oben rechts) ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search plugins...")
        self.search_input.setFixedHeight(max(28, int(self.height_size * 0.08)))
        self.search_input.setFixedWidth(220)      # FIXED WIDTH OF SEARCH BAR
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
        self.search_input.returnPressed.connect(self.search_plugins)

        toolbar.addWidget(self.html_toolbar)
        toolbar.addStretch()
        toolbar.addWidget(self.search_input)  # ganz rechts

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
        # 🧠 Option 2: Hartes Task-Ende (wenn z. B. Prozesse hängen)
        # self.exit_button.clicked.connect(lambda: os._exit(0))

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
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: {'#292929' if theme=="dark" else '#ffffff'};
                width: 10px;
                margin: 0;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #666;
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                background: none;
                height: 0;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        self.scroll_area.setWidget(self.button_container)

        self.pages.addWidget(self.scroll_area)
        self.central_layout.addWidget(self.pages)
        self.setCentralWidget(self.central)

        self.init_button_state()
        self.add_buttons(self.layout)
        self.set_plugin_loader(self.load_plugin_from_path)

    def update_scrollbar_theme(self):
        if hasattr(self, "scroll_area") and self.scroll_area:
            self.scroll_area.setStyleSheet(f"""
                        QScrollArea {{ background: transparent; }}
                        QScrollBar:vertical {{
                            background: {'#292929' if theme == "dark" else '#ffffff'};
                            width: 10px;
                            margin: 0;
                            border-radius: 5px;
                        }}
                        QScrollBar::handle:vertical {{
                            background: {'#666' if theme == "dark" else '#999'};
                            min-height: 20px;
                            border-radius: 5px;
                        }}
                        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                            background: none;
                            height: 0;
                        }}
                        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                            background: none;
                        }}
                    """)
    def update_searchbar_theme(self):
        self.search_input.setStyleSheet(f"""
                    QLineEdit {{
                        background: {'#292929' if is_dark() else '#ffffff'};
                        color: {'#ffffff' if is_dark() else '#292929'};
                        padding: 8px 10px;
                        border-radius: 12px;
                        border: 1.5px solid {'#777777' if is_dark() else '#888888'};
                        outline: none;
                        transition: all 0.3s cubic-bezier(0.19, 1, 0.22, 1);
                        box-shadow: 0px 0px 20px -18px;
                    }}
                    QLineEdit:hover {{
                        border: 2px solid lightgrey;
                        box-shadow: 0px 0px 20px -17px;
                    }}
                    QLineEdit:active {{
                        transform: scale(0.95);
                    }}
                    QLineEdit:focus {{
                        border: 2px solid grey;
                    }}
                """)

    def update_relative_size(self):
        screen = QGuiApplication.screenAt(self.pos())
        if not screen:
            screen = QGuiApplication.primaryScreen()
        geometry = screen.geometry()
        self.width_size = int(geometry.width() * 0.4)
        self.height_size = int(geometry.height() * 0.4)

    def _build_html_toolbar(self):
        mode = theme
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

                /* --- Toggle Switch --- */
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

        # Scrollbar & Buttons im Hauptfenster aktualisieren
        self.update_button_styles(self.layout)
        self.update_scrollbar_theme()
        self.update_searchbar_theme()

        # Wenn Popup sichtbar ist, auch dort aktualisieren
        if self.popup and self.popup.isVisible():
            self.popup.update_button_styles(self.popup.layout)
            self.popup.update_scrollbar_theme()

        # Toolbar-Button im WebEngine aktualisieren
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
        if WEBENGINE_AVAILABLE:
            js = f'window.setBtnMode && window.setBtnMode("{theme}");'
            try:
                self.html_toolbar.page().runJavaScript(js)
            except Exception:
                pass

    def load_plugin_from_path(self, path: str, source_widget=None):
        try:
            plugin_mode = "Popup" if isinstance(source_widget, PopupWindow) else "Window"
            if path.lower().endswith('.py'):
                widget = self.load_python_plugin_widget(path, mode=plugin_mode)
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
                if WEBENGINE_AVAILABLE:
                    js = f'window.setBtnMode && window.setBtnMode("{theme}");'
                    try:
                        self.html_toolbar.page().runJavaScript(js)
                    except Exception:
                        pass
        except Exception as e:
            QMessageBox.critical(source_widget or self, "Fehler beim Laden", f"{e}")

    def load_python_plugin_widget(self, path: str, mode="Window"):
        try:
            spec = importlib.util.spec_from_file_location("plugin_module", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, "PluginWidget", None)
            if cls is not None and isinstance(cls, type):
                # Versuche, mode zu übergeben (einige Plugins erwarten mode)
                try:
                    return cls(mode=mode)
                except TypeError:
                    return cls()
            return None
        except Exception:
            return None

    def search_plugins(self):
        """Durchsucht den scripts-Ordner nach Plugins und zeigt Treffer im Hauptfenster an."""
        query = self.search_input.text().strip().lower()
        scripts_dir = os.path.abspath(getattr(self, "SCRIPT_FOLDER", "scripts"))

        if not query:
            # Leeres Suchfeld -> Explorer normal anzeigen
            self.pages.setCurrentWidget(self.scroll_area)
            self.current_path = scripts_dir
            self.add_buttons(self.layout)
            return

        # Dateien filtern
        all_entries = []
        for root, dirs, files in os.walk(scripts_dir):
            # Zuerst Ordner prüfen
            for d in dirs:
                if query in d.lower():
                    all_entries.append(os.path.join(root, d))
            # Dann Dateien prüfen
            for f in files:
                if f.lower().endswith((".py", ".html")):
                    name_only = f.rsplit(".", 1)[0].lower()  # Endung abschneiden
                    if query in name_only:
                        all_entries.append(os.path.join(root, f))

        if not all_entries:
            QMessageBox.information(self, "Keine Treffer", f"Keine Plugins gefunden für: {query}")
            return

        # Temporär current_path setzen auf einen virtuellen Pfad, damit add_buttons benutzt werden kann
        self._search_results = all_entries  # Zwischenspeicher für add_buttons

        # Wir erstellen einen "virtuellen" add_buttons-Aufruf
        self._add_search_buttons()

    def _add_search_buttons(self):
        """Erstellt Buttons für die Suchergebnisse ähnlich wie im Explorer."""
        layout = self.layout

        # Alte Buttons entfernen
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)

        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        for full_path in sorted(self._search_results):
            entry = os.path.basename(full_path)
            try:
                if os.path.isdir(full_path):
                    display_name = entry  # Ordnername bleibt unverändert
                    button = QPushButton(display_name)
                    button.clicked.connect(lambda _, p=full_path: self.enter_directory(p))
                    button.setProperty("entry_type", "folder")
                elif entry.endswith((".py", ".html")):
                    display_name = entry.rsplit(".", 1)[0]  # Dateiendung abschneiden
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


if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"meinefirma.skriptstarter.1.0")
    except Exception:
        pass
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())
