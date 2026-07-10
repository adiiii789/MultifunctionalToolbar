# =============================================================================
# Traylauncher.py  —  Multifunctional Toolbar (sauberer Nachbau)
# -----------------------------------------------------------------------------
# Systemtray-Launcher mit Popup-Panel und Hauptfenster (PyQt5 + WebEngine).
#
# NEU in diesem Nachbau: Plugin-Fähigkeiten werden per Übergabeparameter
# (Python-Konstanten) direkt IN der Plugin-Datei gesteuert, z. B.:
#
#     # mein_plugin.py
#     HTML_BUTTON   = True                         # Button wird als HTML gerendert
#     BUTTON_HTML   = "<div>🎵 Mein Button</div>"  # das HTML für den Button
#     BUTTON_HEIGHT = 80                           # Höhe des Buttons in px
#     OPACITY       = 0.85                         # Transparenz des Buttons (0..1)
#     NAME          = "Musik"                      # Anzeigename statt Dateiname
#     ICON          = "🎵"                         # Emoji/Text vor dem Namen
#     RUN_AS        = "widget"                     # "widget" | "process" | "browser"
#     ALLOW_POPUP   = True                         # im Rechtsklick-Popup anzeigen
#     ALLOW_WINDOW  = True                         # im Hauptfenster anzeigen
#     MEDIA_BRIDGE  = True                         # WebChannel-Mediensteuerung
#
# Die Parameter werden sicher per AST gelesen — die Plugin-Datei wird dafür
# NICHT ausgeführt. Für .html-Dateien funktionieren die gleichen Parameter
# als führende HTML-Kommentare:  <!-- html_button: true -->
#
# Abwärtskompatibel: Der Dateiname-Prefix "[html]" und die Funktion
# get_inline_html(mode) funktionieren weiterhin unverändert.
#
# EXE bauen:
#   pyinstaller --noconsole --onefile --icon=ProgrammIcon.ico --add-data "scripts;scripts" Traylauncher.py
# =============================================================================

try:
    import pytz
    import dateutil.rrule
    import icalendar
    import uuid
except ImportError:
    print("WARNUNG: Optionale Plugin-Abhängigkeiten (pytz, dateutil, icalendar) fehlen.")

import sys
import os
import re
import ast
import subprocess
import importlib.util
import traceback

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QHBoxLayout, QLabel,
    QStackedWidget, QMessageBox, QScrollArea, QLineEdit,
    QTabWidget, QGraphicsOpacityEffect
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


# =============================================================================
# Globale Konfiguration (Zusatzfeature: Fenster-Transparenz)
# =============================================================================
POPUP_OPACITY = 0.97        # Transparenz des Rechtsklick-Popups (1.0 = deckend)
MAIN_WINDOW_OPACITY = 1.0   # Transparenz des Hauptfensters

# HTML-Explorer: Die Plugin-Liste wird als HTML gerendert (ui/explorer.html,
# frei anpassbar). Python liefert nur den Zustand (JSON) als Backend.
# Bei False oder ohne WebEngine wird der klassische Qt-Explorer verwendet.
HTML_EXPLORER = True

# Farbe der nativen Windows-Titelleiste (folgt dem Theme-Toggle).
# Die Leiste wird NICHT ersetzt — Snap/Andocken usw. bleiben erhalten.
# Dark-Mode: Win 10 1809+ / Win 11.  Eigene Farben: nur Win 11.
TITLEBAR_COLOR_DARK = "#2E2E2E"    # passend zum dunklen App-Hintergrund
TITLEBAR_COLOR_LIGHT = "#FFFFFF"   # passend zum hellen App-Hintergrund
TITLEBAR_TEXT_DARK = "#FFFFFF"     # Titeltext im Dark-Mode
TITLEBAR_TEXT_LIGHT = "#000000"    # Titeltext im Light-Mode


# =============================================================================
# Plugin-Parameter: sicheres Auslesen ohne Ausführung der Plugin-Datei
# =============================================================================
PLUGIN_META_KEYS = {
    "HTML_BUTTON",       # bool  – Button als Inline-HTML-Card rendern
    "BUTTON_HTML",       # str   – HTML-String für den Button
    "BUTTON_HTML_FILE",  # str   – Pfad (relativ zur Plugin-Datei) zu einer HTML-Datei für den Button
    "BUTTON_HEIGHT",     # int   – Höhe des Buttons / der Card in px
    "NAME",              # str   – Anzeigename
    "ICON",              # str   – Emoji/Text-Prefix vor dem Namen
    "OPACITY",           # float – Transparenz des Buttons (0..1)
    "RUN_AS",            # str   – "widget" (Standard) | "process" | "browser"
    "ALLOW_POPUP",       # bool  – Eintrag im Popup anzeigen (Standard True)
    "ALLOW_WINDOW",      # bool  – Eintrag im Hauptfenster anzeigen (Standard True)
    "MEDIA_BRIDGE",      # bool  – WebChannel "media" registrieren (Standard True)
    "PINNED",            # bool|int – Plugin oben in der Liste anpinnen; Zahl = Reihenfolge (kleiner = weiter oben)
}


def meta_pin_rank(meta: dict):
    """Sortier-Rang für PINNED: Zahl wenn angepinnt, sonst None."""
    pin = meta.get("PINNED")
    if pin is True:
        return 10**9  # angepinnt ohne Ordnungszahl: hinter nummerierten Pins
    if isinstance(pin, (int, float)) and not isinstance(pin, bool) and pin > 0:
        return int(pin)
    return None


def _parse_meta_literal(raw: str):
    """'true' / '0.5' / '"text"' → Python-Wert."""
    s = (raw or "").strip()
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        return ast.literal_eval(s)
    except Exception:
        return s  # als String übernehmen


def read_plugin_meta(path: str) -> dict:
    """
    Liest die Plugin-Parameter aus der Datei, ohne sie auszuführen.
    - .py:   Modul-Konstanten auf oberster Ebene (per AST, nur Literale)
    - .html: führende HTML-Kommentare  <!-- key: value -->
    - Kompatibilität: Dateiname-Prefix "[html]" setzt HTML_BUTTON = True
    """
    meta = {}
    lower_name = os.path.basename(path).lower()
    lower_path = path.lower()
    try:
        if lower_path.endswith(".py"):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                src = f.read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                tree = None
            if tree is not None:
                for node in tree.body:
                    if (isinstance(node, ast.Assign) and len(node.targets) == 1
                            and isinstance(node.targets[0], ast.Name)):
                        key = node.targets[0].id.upper()
                        if key in PLUGIN_META_KEYS:
                            try:
                                meta[key] = ast.literal_eval(node.value)
                            except Exception:
                                pass  # nur einfache Literale erlaubt
        elif lower_path.endswith(".html"):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(4096)
            for m in re.finditer(r"<!--\s*([A-Za-z_]+)\s*[:=]\s*(.+?)\s*-->", head):
                key = m.group(1).upper()
                if key in PLUGIN_META_KEYS:
                    meta[key] = _parse_meta_literal(m.group(2))
    except Exception:
        pass

    # Abwärtskompatibilität: [html]-Prefix im Dateinamen
    if lower_name.startswith("[html]"):
        meta.setdefault("HTML_BUTTON", True)
    return meta


def meta_opacity(meta: dict):
    """Gültige Button-Transparenz aus den Parametern, sonst None."""
    op = meta.get("OPACITY")
    if isinstance(op, (int, float)) and 0.0 < float(op) < 1.0:
        return float(op)
    return None


ICON_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp")


def meta_icon_path(meta: dict, plugin_path: str):
    """ICON darf statt Emoji auch eine Bilddatei sein.

    Zeigt ICON auf eine existierende Bilddatei (relativ zur Plugin-Datei
    oder absolut), wird deren absoluter Pfad geliefert — sonst None
    (dann gilt ICON als Emoji/Text)."""
    icon = meta.get("ICON")
    if not (isinstance(icon, str) and icon.strip()):
        return None
    s = icon.strip()
    if not s.lower().endswith(ICON_IMAGE_EXTS):
        return None
    cand = s if os.path.isabs(s) else os.path.join(
        os.path.dirname(os.path.abspath(plugin_path)), s)
    cand = os.path.abspath(cand)
    return cand if os.path.exists(cand) else None


def meta_display_name(meta: dict, entry: str) -> str:
    """Anzeigename aus NAME/ICON, sonst Dateiname (py ohne Endung)."""
    name = meta.get("NAME")
    if not (isinstance(name, str) and name.strip()):
        name = entry[:-3] if entry.lower().endswith(".py") else entry
    icon = meta.get("ICON")
    if (isinstance(icon, str) and icon.strip()
            and not icon.strip().lower().endswith(ICON_IMAGE_EXTS)):
        name = f"{icon.strip()} {name}"
    return name


# =============================================================================
# WebEngine-Hilfen
# =============================================================================
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


if WEBENGINE_AVAILABLE:
    class InlineInterceptPage(QWebEnginePage):
        """Fängt Linkklicks in Inline-Cards ab und delegiert sie an den Host."""

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


# =============================================================================
# Systemweite Dienste — ausgelagert nach services.py (Launcher managt nur)
# =============================================================================
try:
    from services import MediaControlBridge, apply_native_titlebar
except Exception:
    print("WARNUNG: services.py fehlt/fehlerhaft — Systemdienste laufen als No-op-Stub.")
    traceback.print_exc()

    class MediaControlBridge(QObject):  # Minimal-Stub, damit Cards nicht brechen
        themeChanged = pyqtSignal(str)
        mediaInfoChanged = pyqtSignal(str)

        @pyqtSlot(result=str)
        def getTheme(self):
            app = QApplication.instance()
            val = app.property("toolbar_theme") if app else None
            return val if isinstance(val, str) else "dark"

        @pyqtSlot()
        def requestMediaInfo(self):
            self.mediaInfoChanged.emit('{"available": false}')

        @pyqtSlot()
        def playPause(self):
            pass

        @pyqtSlot()
        def next(self):
            pass

        @pyqtSlot()
        def prev(self):
            pass

        @pyqtSlot()
        def stop(self):
            pass

        @pyqtSlot()
        def mute(self):
            pass

        @pyqtSlot()
        def volUp(self):
            pass

        @pyqtSlot()
        def volDown(self):
            pass

    def apply_native_titlebar(widget, dark, caption_color, text_color):
        pass


# =============================================================================
# Inline-HTML-Button (Card in der Liste)
# =============================================================================
class HtmlInlineButton(QWidget):
    """
    Kompakte HTML-Card in der Plugin-Liste.

    Inhalts-Priorität (gesteuert über die Plugin-Parameter):
      1. BUTTON_HTML       – HTML-String direkt aus der Plugin-Datei
      2. BUTTON_HTML_FILE  – HTML-Datei relativ zur Plugin-Datei
      3. .html-Datei       – wird direkt geladen (Original-Verhalten)
      4. .py + get_inline_html(mode) – Original-Verhalten (Kompatibilität)
      5. sonst             – Dateiinhalt als <pre>
    """

    def __init__(self, path: str = None, title_text: str = None,
                 min_height: int = 160, compact: bool = False,
                 meta: dict = None, **kwargs):
        super().__init__()
        if path is None:
            path = kwargs.pop("html_path", None)
        if path is None:
            raise ValueError("HtmlInlineButton requires 'path' (or 'html_path').")
        self.setProperty("entry_type", "file_html_inline")
        self.src_path = os.path.abspath(path)
        self.compact = compact
        self.meta = dict(meta) if meta else read_plugin_meta(self.src_path)
        self._opacity = meta_opacity(self.meta)

        # --- Höhe: Original-Berechnung, per BUTTON_HEIGHT übersteuerbar ---
        probe = QPushButton("Wg")
        base_h = max(28, probe.sizeHint().height())
        factor = 1.8 if not compact else 2.4
        target_h = int(base_h * factor)
        bh = self.meta.get("BUTTON_HEIGHT")
        if isinstance(bh, (int, float)) and bh > 0:
            target_h = int(bh)
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

                # WebChannel-Mediensteuerung (per Parameter abschaltbar)
                if self.meta.get("MEDIA_BRIDGE", True) is not False:
                    self.channel = QWebChannel(self.view.page())
                    self.media = MediaControlBridge(self)
                    self.channel.registerObject("media", self.media)
                    self.view.page().setWebChannel(self.channel)

                # Transparenz (OPACITY) nach dem Laden per CSS anwenden
                if self._opacity is not None:
                    self.view.loadFinished.connect(self._apply_opacity)

                self._load_content()
            except Exception:
                print("HtmlInlineButton init error:", traceback.format_exc())
                self._fallback_area(outer)
        else:
            self._fallback_area(outer)

    # --- Inhalt laden gemäß Parametern -------------------------------------
    def _load_content(self):
        mode_val = "popup" if self.compact else "window"
        lower = self.src_path.lower()
        base = QUrl.fromLocalFile(os.path.dirname(self.src_path) + os.sep)

        # 1) BUTTON_HTML direkt aus der Plugin-Datei
        button_html = self.meta.get("BUTTON_HTML")
        if isinstance(button_html, str) and button_html.strip():
            self.view.setHtml(self._wrap_no_scroll(button_html, mode_val), baseUrl=base)
            return

        # 2) BUTTON_HTML_FILE relativ zur Plugin-Datei
        html_file = self.meta.get("BUTTON_HTML_FILE")
        if isinstance(html_file, str) and html_file.strip():
            candidate = html_file
            if not os.path.isabs(candidate):
                candidate = os.path.join(os.path.dirname(self.src_path), candidate)
            candidate = os.path.abspath(candidate)
            if os.path.exists(candidate):
                self.view.load(self._url_with_mode(candidate, mode_val))
                return

        # 3) .html direkt laden (Original)
        if lower.endswith(".html"):
            self.view.load(self._url_with_mode(self.src_path, mode_val))
            return

        # 4) .py mit get_inline_html(mode) (Original / Kompatibilität)
        if lower.endswith(".py"):
            html = self._load_inline_html_from_py(self.src_path, mode_val)
            self.view.setHtml(html, baseUrl=base)
            return

        # 5) Fallback: Dateiinhalt als <pre>
        try:
            with open(self.src_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except Exception as e:
            raw = f"Fehler beim Lesen: {e}"
        esc = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = f"<!doctype html><meta charset='utf-8'><pre style='margin:0;padding:8px;font:13px/1.3 monospace;'>{esc}</pre>"
        self.view.setHtml(html, baseUrl=base)

    @staticmethod
    def _url_with_mode(path: str, mode_val: str) -> QUrl:
        url = QUrl.fromLocalFile(os.path.abspath(path))
        if url.hasQuery():
            parts = [p for p in url.query().split("&") if not p.startswith("mode=")]
            parts.append(f"mode={mode_val}")
            url.setQuery("&".join(parts))
        else:
            url.setQuery(f"mode={mode_val}")
        return url

    def _apply_opacity(self, ok=True):
        if self._opacity is not None:
            safe_run_js(self.view, f"document.body && (document.body.style.opacity='{self._opacity}');")

    def _load_inline_html_from_py(self, file_path: str, mode: str) -> str:
        try:
            spec = importlib.util.spec_from_file_location("inline_html_module", file_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            fn = getattr(mod, "get_inline_html", None)
            if not callable(fn):
                return (f"<!doctype html><meta charset='utf-8'><p style='margin:8px;color:#c00;'>"
                        f"Fehlende Funktion <code>get_inline_html(mode)</code> oder "
                        f"<code>BUTTON_HTML</code>-Parameter in {os.path.basename(file_path)}</p>")
            html = fn(mode=mode)
            if not isinstance(html, str):
                return "<!doctype html><meta charset='utf-8'><p style='margin:8px;color:#c00;'>get_inline_html() muss String liefern.</p>"
            return self._wrap_no_scroll(html, mode)
        except Exception:
            return (f"<!doctype html><meta charset='utf-8'><pre style='margin:8px;color:#c00;'>"
                    f"Fehler in {os.path.basename(file_path)}:\n{traceback.format_exc()}</pre>")

    def _wrap_no_scroll(self, inner_html: str, mode: str = "window") -> str:
        opacity_css = f"body{{opacity:{self._opacity};}}" if self._opacity is not None else ""
        return f"""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{{margin:0;padding:0;height:100%;overflow:hidden;background:transparent}}*{{box-sizing:border-box}}{opacity_css}</style>
{inner_html}
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
window.toolbarMode = "{mode}";
new QWebChannel(qt.webChannelTransport, ch => {{ window.media = ch.objects.media; }});
['wheel','touchmove'].forEach(evt => window.addEventListener(evt, e => e.preventDefault(), {{passive:false}}));
window.addEventListener('keydown', e => {{ const blocked=['ArrowUp','ArrowDown','PageUp','PageDown',' '];
  if(e.ctrlKey||blocked.includes(e.key)){{e.preventDefault();e.stopPropagation();}} }}, true);
</script>"""

    def eventFilter(self, obj, event):
        if obj is getattr(self, "view", None):
            et = event.type()
            if et in (QEvent.Wheel, QEvent.Gesture, QEvent.NativeGesture):
                return True
            if et == QEvent.KeyPress:
                try:
                    key = event.key()
                    mods = event.modifiers()
                except Exception:
                    key, mods = None, 0
                if mods & Qt.ControlModifier:
                    return True
                if key in {Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Space}:
                    return True
        return super().eventFilter(obj, event)

    def _fallback_area(self, outer_layout: QVBoxLayout):
        btn = QPushButton("Im Browser öffnen")
        btn.clicked.connect(lambda: __import__("webbrowser").open('file://' + self.src_path))
        outer_layout.addWidget(btn)



# =============================================================================
# HTML-Explorer: UI liegt in ui/explorer.html (anpassbar), Python ist Backend
# =============================================================================
_PLUGIN_MODULE_CACHE = {}


def get_plugin_module(file_path):
    """Lädt ein Plugin-Modul einmalig (Cache per Änderungszeit).

    Dadurch behalten Card-Plugins ihren Zustand zwischen Aufrufen, und
    get_inline_html()/handle_call() laufen immer im selben Modul — die
    gesamte Plugin-Logik bleibt in der Plugin-Datei (geschlossenes System);
    der Launcher lädt und routet nur.
    """
    p = os.path.abspath(file_path)
    try:
        mtime = os.path.getmtime(p)
    except Exception:
        mtime = None
    cached = _PLUGIN_MODULE_CACHE.get(p)
    if cached and cached[0] == mtime:
        return cached[1]
    spec = importlib.util.spec_from_file_location("plugin_mod_" + str(abs(hash(p))), p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    _PLUGIN_MODULE_CACHE[p] = (mtime, mod)
    return mod


def load_inline_html_from_py_module(file_path, mode):
    """get_inline_html(mode) einer Plugin-Datei ausführen (Kompatibilität)."""
    try:
        mod = get_plugin_module(file_path)
        fn = getattr(mod, "get_inline_html", None)
        if not callable(fn):
            return ("<p style=\'margin:8px;color:#c00;\'>Fehlende Funktion "
                    "<code>get_inline_html(mode)</code> oder <code>BUTTON_HTML</code>-Parameter in "
                    + os.path.basename(file_path) + "</p>")
        html = fn(mode=mode)
        if not isinstance(html, str):
            return "<p style=\'margin:8px;color:#c00;\'>get_inline_html() muss String liefern.</p>"
        return html
    except Exception:
        esc = traceback.format_exc().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return ("<pre style=\'margin:8px;color:#c00;\'>Fehler in "
                + os.path.basename(file_path) + ":\n" + esc + "</pre>")


def wrap_card_html(inner_html, mode, opacity=None, plugin_path=""):
    """Wrapper für Card-Inhalte im HTML-Explorer (läuft in einem iframe).

    Stellt window.media (Media-Bridge des Explorers) und window.toolbarMode
    bereit, fängt Linkklicks ab und blockiert Scrollen — identisch zum
    Verhalten der alten Qt-Inline-Cards.
    """
    import json as _json
    opacity_css = ("body{opacity:" + str(opacity) + ";}") if opacity else ""
    return ("<!doctype html><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<style>html,body{margin:0;padding:0;height:100%;overflow:hidden;background:transparent}"
            "*{box-sizing:border-box}" + opacity_css + "</style>\n"
            + inner_html +
            "\n<script>\n"
            "window.toolbarMode = \"" + mode + "\";\n"
            "window.pluginPath = " + _json.dumps(plugin_path or "") + ";\n"
            "window.openPlugin = function(p){if(window.parent && window.parent.openPluginFromCard)"
            "{window.parent.openPluginFromCard(p || '', window.pluginPath);}};\n"
            "window.pluginCall = function(method, args, cb){"
            "if(window.parent && window.parent.pluginCallFromCard)"
            "{window.parent.pluginCallFromCard(window.pluginPath, method || '',"
            " JSON.stringify(args || {}), cb || function(){});}};\n"
            "(function(){function hook(){if(window.parent && window.parent.media)"
            "{window.media = window.parent.media;}else{setTimeout(hook,120);}}hook();})();\n"
            "document.addEventListener('click', function(e){"
            "var a = e.target && e.target.closest ? e.target.closest('a') : null;"
            "if(a && a.href){e.preventDefault();"
            "if(window.parent && window.parent.openLinkFromCard){window.parent.openLinkFromCard(a.href);}}}, true);\n"
            "['wheel','touchmove'].forEach(function(evt){window.addEventListener(evt,"
            "function(e){e.preventDefault();}, {passive:false});});\n"
            "window.addEventListener('keydown', function(e){"
            "var blocked=['ArrowUp','ArrowDown','PageUp','PageDown',' '];"
            "if(e.ctrlKey || blocked.indexOf(e.key)!==-1){e.preventDefault();e.stopPropagation();}}, true);\n"
            "</script>")


# Standard-UI des Explorers. Beim ersten Start wird sie nach ui/explorer.html
# geschrieben und kann dort frei angepasst werden (Farben, Layout, Effekte...).
# Die Optik entspricht exakt dem bisherigen Qt-Explorer.
EXPLORER_DEFAULT_HTML = """<!DOCTYPE html>
<html data-theme="dark">
<head>
<meta charset="utf-8">
<style>
  /* ==== Farbschema (identisch zum Qt-Original) ============================ */
  :root {
    --text: #fff;
    --folder-bg: #3A4A6A;  --folder-hover: #4B5B6B;
    --file-bg:   #3A3A3A;  --file-hover:   #505050;
    --card-bg:   transparent;  --card-hover:   transparent;
    --back-bg:   #666666;  --back-hover:   #777777;  --back-text: #FFFFFF;
    --scroll-track: #292929;  --scroll-handle: #666;
  }
  html[data-theme="light"] {
    --text: #000;
    --folder-bg: #c2d1ff;  --folder-hover: #a1b8ff;
    --file-bg:   #EEEEEE;  --file-hover:   #CCCCCC;
    --card-bg:   transparent;  --card-hover:   transparent;
    --back-bg:   #BBBBBB;  --back-hover:   #CCCCCC;  --back-text: #000000;
    --scroll-track: #ffffff;  --scroll-handle: #666;
  }
  html[data-theme="light"][data-compact="true"] {
    --scroll-track: #d6d6d6;  --scroll-handle: #999;
  }

  html, body { margin: 0; padding: 0; background: transparent; }
  body { font: 12px "Segoe UI", system-ui, sans-serif; color: var(--text); }

  ::-webkit-scrollbar { width: 10px; }
  ::-webkit-scrollbar-track { background: var(--scroll-track); border-radius: 5px; }
  ::-webkit-scrollbar-thumb { background: var(--scroll-handle); border-radius: 5px; min-height: 20px; }

  #list { display: flex; flex-direction: column; }

  .entry-btn {
    display: flex; align-items: center; justify-content: center;
    width: 100%; border: none; cursor: pointer;
    color: var(--text); font: inherit; padding: 0;
  }
  .folder { background: var(--folder-bg); }
  .folder:hover { background: var(--folder-hover); }
  .file { background: var(--file-bg); }
  .file:hover { background: var(--file-hover); }
  .entry-icon { height: 24px; width: 24px; object-fit: contain; margin-right: 8px; }
  .back { background: var(--back-bg); color: var(--back-text); font-weight: bold; min-height: 40px; }
  .back:hover { background: var(--back-hover); }

  .card {
    background: var(--card-bg); border-radius: 8px;
    padding-left: 8px; padding-right: 8px; box-sizing: border-box;
  }
  .card:hover { background: var(--card-hover); }
  .card iframe { border: none; width: 100%; display: block; background: transparent; }
</style>
</head>
<body>
<div id="list"></div>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  let state = null;

  function render() {
    if (!state) return;
    document.documentElement.setAttribute('data-theme', state.theme);
    document.documentElement.setAttribute('data-compact', state.compact ? 'true' : 'false');
    const list = document.getElementById('list');
    list.innerHTML = '';

    if (!state.isRoot) {
      const b = document.createElement('button');
      b.className = 'entry-btn back';
      b.textContent = '\u2190 Zur\u00fcck';
      b.onclick = () => window.explorer && window.explorer.goBack();
      list.appendChild(b);
    }

    for (const e of state.entries) {
      if (e.type === 'folder') {
        const b = document.createElement('button');
        b.className = 'entry-btn folder';
        b.style.minHeight = e.height + 'px';
        b.textContent = e.name;
        b.onclick = () => window.explorer && window.explorer.enterDir(e.path);
        list.appendChild(b);
      } else if (e.type === 'file') {
        const b = document.createElement('button');
        b.className = 'entry-btn file';
        b.style.minHeight = e.height + 'px';
        if (e.icon) {
          const im = document.createElement('img');
          im.className = 'entry-icon';
          im.src = e.icon;
          b.appendChild(im);
        }
        b.appendChild(document.createTextNode(e.label));
        if (e.opacity) b.style.opacity = e.opacity;
        b.onclick = () => window.explorer && window.explorer.open(e.path);
        list.appendChild(b);
      } else if (e.type === 'card') {
        const d = document.createElement('div');
        d.className = 'card';
        d.style.height = e.height + 'px';
        d.style.paddingTop = e.padTop + 'px';
        d.style.paddingBottom = e.padBottom + 'px';
        const f = document.createElement('iframe');
        f.setAttribute('scrolling', 'no');
        f.style.height = (e.height - e.padTop - e.padBottom) + 'px';
        if (e.kind === 'url') { f.src = e.url; } else { f.srcdoc = e.content; }
        d.appendChild(f);
        list.appendChild(d);
      }
    }
  }

  // Wird von Python (push_state) aufgerufen
  window.renderState = function (s) {
    if (typeof s === 'string') s = JSON.parse(s);
    state = s;
    render();
  };

  // Karten (iframes) melden Linkklicks hierher
  window.openLinkFromCard = function (url) {
    if (window.explorer) window.explorer.openLink(url);
  };

  // Karten koennen damit direkt Plugins oeffnen: openPlugin('Name.py')
  window.openPluginFromCard = function (p, from) {
    if (window.explorer) window.explorer.openPlugin(p || '', from || '');
  };

  // Backend-Aufrufe der Karten: pluginCall('methode', {...}, cb) im iframe
  window.pluginCallFromCard = function (path, method, argsJson, cb) {
    if (window.explorer) window.explorer.callPlugin(path, method, argsJson, cb);
  };

  new QWebChannel(qt.webChannelTransport, function (channel) {
    window.explorer = channel.objects.explorer;
    window.media = channel.objects.media;   // fuer Karten-iframes erreichbar
    window.explorer.getState(function (s) { window.renderState(s); });
  });
</script>
</body>
</html>
"""


def ensure_ui_file(app_root="."):
    """Legt ui/explorer.html beim ersten Start an (anpassbare Explorer-UI)."""
    try:
        ui_dir = os.path.abspath(os.path.join(app_root, "ui"))
        os.makedirs(ui_dir, exist_ok=True)
        ui_path = os.path.join(ui_dir, "explorer.html")
        if not os.path.exists(ui_path):
            with open(ui_path, "w", encoding="utf-8") as f:
                f.write(EXPLORER_DEFAULT_HTML)
        return ui_path
    except Exception:
        print("ui/explorer.html konnte nicht angelegt werden:", traceback.format_exc())
        return None


if WEBENGINE_AVAILABLE:
    class ExplorerBridge(QObject):
        """Backend-Schnittstelle des HTML-Explorers (QWebChannel: 'explorer')."""

        def __init__(self, host, parent=None):
            super().__init__(parent)
            self._host = host

        @pyqtSlot(result=str)
        def getState(self):
            import json
            try:
                return json.dumps(self._host._collect_state())
            except Exception:
                traceback.print_exc()
                return '{"theme": "dark", "compact": false, "isRoot": true, "entries": []}'

        @pyqtSlot(str)
        def open(self, path):
            QTimer.singleShot(0, lambda: self._host.run_script(path))

        @pyqtSlot(str)
        def enterDir(self, path):
            QTimer.singleShot(0, lambda: self._host.enter_directory(path))

        @pyqtSlot()
        def goBack(self):
            QTimer.singleShot(0, self._host.go_back)

        @pyqtSlot(str, str, str, result=str)
        def callPlugin(self, path, method, args_json):
            # Backend-Aufruf einer Card: routet zu handle_call(method, args)
            # im Plugin-Modul. Die Logik liegt vollständig in der Plugin-Datei,
            # der Launcher transportiert nur.
            import json
            try:
                p = os.path.abspath(path or "")
                root = os.path.abspath(getattr(self._host, "SCRIPT_FOLDER", "scripts"))
                try:
                    inside = os.path.commonpath([p, root]) == root
                except Exception:
                    inside = False
                if not inside or not p.lower().endswith(".py") or not os.path.exists(p):
                    return json.dumps({"ok": False, "error": "Pfad nicht erlaubt."})
                mod = get_plugin_module(p)
                fn = getattr(mod, "handle_call", None)
                if not callable(fn):
                    return json.dumps({"ok": False,
                                       "error": "Plugin hat kein handle_call(method, args)."})
                try:
                    args = json.loads(args_json) if args_json else {}
                except Exception:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result = fn(method or "", args)
                return json.dumps({"ok": True, "result": result}, default=str)
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e)})

        @pyqtSlot(str, str)
        def openPlugin(self, path, from_path):
            # Von Cards aufgerufen: openPlugin('Name.py') — relativ zum Ordner
            # der Card-Datei; ohne Argument wird die eigene Datei geöffnet.
            def _go():
                p = (path or "").strip()
                base = os.path.dirname(os.path.abspath(from_path)) if from_path else None
                if not p:
                    p = from_path or ""
                elif not os.path.isabs(p):
                    root = base or getattr(self._host, "current_path", None) or "."
                    p = os.path.join(root, p)
                p = os.path.abspath(p)
                if p and os.path.exists(p):
                    self._host.run_script(p)
            QTimer.singleShot(0, _go)

        @pyqtSlot(str)
        def openLink(self, url):
            def _go():
                fn = getattr(self._host, "_open_link_as_plugin", None)
                if callable(fn):
                    fn(QUrl(url))
                else:
                    import webbrowser
                    webbrowser.open(url)
            QTimer.singleShot(0, _go)


    class ExplorerView(QWebEngineView):
        """Der HTML-Explorer: rendert ui/explorer.html, Python liefert JSON."""

        def __init__(self, host, parent=None):
            super().__init__(parent)
            self._host = host
            try:
                self.page().setBackgroundColor(Qt.transparent)
            except Exception:
                pass
            try:
                s = self.page().settings()
                s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
                s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            except Exception:
                pass
            self.channel = QWebChannel(self.page())
            self.bridge = ExplorerBridge(host, self)
            self.channel.registerObject("explorer", self.bridge)
            # Systemweite Dienste aus services.py registrieren ("media", ...)
            try:
                from services import create_services
                self._services = create_services(self)
            except Exception:
                self._services = {"media": MediaControlBridge(self)}
            for _name, _obj in self._services.items():
                self.channel.registerObject(_name, _obj)
            self.media = self._services.get("media")
            self.page().setWebChannel(self.channel)
            self._load_ui()

        def _load_ui(self):
            ui_path = ensure_ui_file()
            if ui_path and os.path.exists(ui_path):
                self.load(QUrl.fromLocalFile(ui_path))
            else:
                base = QUrl.fromLocalFile(os.path.abspath(".") + os.sep)
                self.setHtml(EXPLORER_DEFAULT_HTML, baseUrl=base)

        def push_state(self):
            import json
            try:
                payload = json.dumps(json.dumps(self._host._collect_state()))
            except Exception:
                traceback.print_exc()
                return
            safe_run_js(self, "window.renderState && window.renderState(" + payload + ");")


# =============================================================================
# DPI & Theme
# =============================================================================
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

theme = "dark"   # "dark" | "light"
mode = "Window"


def is_dark():
    return theme == "dark"


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


def apply_titlebar_theme(widget):
    """Färbt die native Titelleiste passend zum App-Theme.

    Der eigentliche Systemdienst liegt in services.py (apply_native_titlebar);
    hier wird er nur mit dem aktuellen Theme und den Farbkonstanten aufgerufen.
    """
    apply_native_titlebar(
        widget,
        is_dark(),
        TITLEBAR_COLOR_DARK if is_dark() else TITLEBAR_COLOR_LIGHT,
        TITLEBAR_TEXT_DARK if is_dark() else TITLEBAR_TEXT_LIGHT,
    )  # z. B. dwmapi nicht verfügbar → native Standard-Leiste bleibt


# =============================================================================
# Beispiel-Plugins (werden beim ersten Start angelegt)
# =============================================================================
def ensure_sample_plugin(script_root: str):
    if not os.path.exists(script_root):
        os.makedirs(script_root, exist_ok=True)
    entries = [e for e in os.listdir(script_root) if not e.startswith("_")]
    if entries:
        return
    try:
        # --- Klassisches Widget-Plugin ---
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

        # --- Neues Parametersystem: HTML-Button per BUTTON_HTML ---
        demo_path = os.path.join(script_root, "musik_karte.py")
        with open(demo_path, "w", encoding="utf-8") as f:
            f.write(
                '# Demo für das neue Parametersystem: der Listen-Button ist eine HTML-Card.\n'
                'HTML_BUTTON = True\n'
                'BUTTON_HEIGHT = 72\n'
                'OPACITY = 0.9\n'
                'NAME = "Musik"\n'
                'ICON = "🎵"\n'
                'BUTTON_HTML = """\n'
                '<div style="display:flex;align-items:center;justify-content:center;height:100%;gap:10px;\n'
                '            font-family:system-ui;color:inherit;">\n'
                '  <button onclick="media.prev()"      style="font-size:16px;padding:4px 10px;border-radius:8px;border:none;cursor:pointer;">⏮</button>\n'
                '  <button onclick="media.playPause()" style="font-size:16px;padding:4px 14px;border-radius:8px;border:none;cursor:pointer;">⏯</button>\n'
                '  <button onclick="media.next()"      style="font-size:16px;padding:4px 10px;border-radius:8px;border:none;cursor:pointer;">⏭</button>\n'
                '</div>\n'
                '"""\n'
            )

        # --- HTML-Beispiel im Unterordner (Original-Verhalten) ---
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


# =============================================================================
# Gemeinsame Explorer-Logik (Popup + Hauptfenster)
# =============================================================================
class ButtonContentMixin:
    SCRIPT_FOLDER = "scripts"

    def _base_dir(self) -> str:
        return os.path.abspath(getattr(self, "SCRIPT_FOLDER", "scripts"))

    def _default_dir(self) -> str:
        return self._base_dir()

    def _resolve_path(self, p: str) -> str:
        if not p:
            return None
        p = os.path.expanduser(p.strip())
        if os.path.isabs(p):
            return os.path.abspath(p)
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
        self.refresh_explorer()

    def refresh_explorer(self):
        """Explorer neu aufbauen — HTML-Variante (push) oder Qt-Fallback."""
        if getattr(self, "use_html_explorer", False) and getattr(self, "explorer_view", None) is not None:
            self.explorer_view.push_state()
        elif getattr(self, "layout", None) is not None:
            self.add_buttons(self.layout)
            self.update_button_styles(self.layout)

    # --- Zustand für den HTML-Explorer (Python = reines Backend) -----------
    def _card_metrics(self, meta, compact):
        probe = QPushButton("Wg")
        base_h = max(28, probe.sizeHint().height())
        factor = 1.8 if not compact else 2.4
        target = int(base_h * factor)
        bh = meta.get("BUTTON_HEIGHT")
        if isinstance(bh, (int, float)) and bh > 0:
            target = int(bh)
        top = max(4, target // 8)
        bot = max(4, target // 8)
        return target, top, bot

    def _build_card_payload(self, path, meta, compact):
        mode_val = "popup" if compact else "window"
        opacity = meta_opacity(meta)
        target, top, bot = self._card_metrics(meta, compact)
        entry = {"type": "card", "path": path, "height": target,
                 "padTop": top, "padBottom": bot, "kind": "srcdoc", "content": ""}
        base_dir = os.path.dirname(os.path.abspath(path))
        src_html = None

        button_html = meta.get("BUTTON_HTML")
        if isinstance(button_html, str) and button_html.strip():
            src_html = button_html

        if src_html is None:
            html_file = meta.get("BUTTON_HTML_FILE")
            if isinstance(html_file, str) and html_file.strip():
                cand = html_file if os.path.isabs(html_file) else os.path.join(base_dir, html_file)
                cand = os.path.abspath(cand)
                if os.path.exists(cand):
                    try:
                        with open(cand, "r", encoding="utf-8", errors="replace") as f:
                            src_html = f.read()
                        base_dir = os.path.dirname(cand)
                    except Exception:
                        src_html = None

        if src_html is None and path.lower().endswith(".html"):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    src_html = f.read()
            except Exception as e:
                src_html = "<pre style='margin:8px;color:#c00;'>Fehler beim Lesen: " + str(e) + "</pre>"

        if src_html is None and path.lower().endswith(".py"):
            src_html = load_inline_html_from_py_module(path, mode_val)

        if src_html is None:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read()
            except Exception as e:
                raw = "Fehler beim Lesen: " + str(e)
            esc = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            src_html = "<pre style='margin:0;padding:8px;font:13px/1.3 monospace;'>" + esc + "</pre>"

        base_href = QUrl.fromLocalFile(base_dir + os.sep).toString()
        entry["content"] = wrap_card_html('<base href="' + base_href + '">' + src_html,
                                          mode_val, opacity, plugin_path=path)
        return entry

    def _collect_state(self):
        """Kompletter Explorer-Zustand als dict (wird als JSON an JS gegeben)."""
        is_popup = getattr(self, "IS_POPUP", False)
        cur = getattr(self, "current_path", None)
        root = os.path.abspath(self.SCRIPT_FOLDER)
        if not cur:
            return {"theme": theme, "compact": is_popup, "isRoot": True, "entries": []}

        try:
            raw_entries = os.listdir(cur)
        except Exception:
            raw_entries = []
        filtered = [e for e in raw_entries if not e.startswith("_")]
        q = (getattr(self, "_search_query", "") or "").strip().lower()
        if q:
            filtered = [e for e in filtered if q in e.lower()]

        prepared = []
        for entry in filtered:
            full = os.path.join(cur, entry)
            nl = entry.lower()
            if os.path.isdir(full):
                prepared.append((entry, full, None))
            elif nl.endswith(".py") or nl.endswith(".html"):
                prepared.append((entry, full, read_plugin_meta(full)))

        def group_key(item):
            entry, full, meta = item
            nl = entry.lower()
            pin = meta_pin_rank(meta) if meta else None
            if pin is not None:
                return (0, pin, nl)
            if nl.startswith("[html]"):
                return (1, 0, nl)
            if nl.endswith(".html"):
                return (2, 0, nl)
            if nl.endswith(".py"):
                return (3, 0, nl)
            if os.path.isdir(full):
                return (4, 0, nl)
            return (5, 0, nl)

        out = []
        for entry, full, meta in sorted(prepared, key=group_key):
            try:
                if meta is None:
                    out.append({"type": "folder", "name": entry, "path": full, "height": 60})
                    continue
                if is_popup and meta.get("ALLOW_POPUP") is False:
                    continue
                if (not is_popup) and meta.get("ALLOW_WINDOW") is False:
                    continue
                if meta.get("HTML_BUTTON"):
                    out.append(self._build_card_payload(full, meta, is_popup))
                    continue
                bh = meta.get("BUTTON_HEIGHT")
                height = int(bh) if isinstance(bh, (int, float)) and bh > 0 else 60
                ipath = meta_icon_path(meta, full)
                out.append({"type": "file", "label": meta_display_name(meta, entry),
                            "path": full, "height": height,
                            "opacity": meta_opacity(meta),
                            "icon": QUrl.fromLocalFile(ipath).toString() if ipath else None})
            except Exception:
                print("Fehler beim Zustandsaufbau:", traceback.format_exc())

        return {"theme": theme, "compact": is_popup,
                "isRoot": os.path.abspath(cur) == root, "entries": out}

    def add_buttons(self, layout):
        for i in reversed(range(layout.count())):
            it = layout.itemAt(i)
            w = it.widget() if it else None
            if w:
                w.setParent(None)

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

        # Einträge vorbereiten: Metadaten einmal lesen (für Sortierung & Buttons)
        prepared = []
        for entry in filtered:
            full = os.path.join(self.current_path, entry)
            nl = entry.lower()
            if os.path.isdir(full):
                prepared.append((entry, full, None))
            elif nl.endswith(".py") or nl.endswith(".html"):
                prepared.append((entry, full, read_plugin_meta(full)))
            # andere Dateitypen werden wie im Original ignoriert

        def group_key(item):
            entry, full, meta = item
            nl = entry.lower()
            # PINNED: immer ganz oben, Zahl bestimmt die Reihenfolge
            pin = meta_pin_rank(meta) if meta else None
            if pin is not None:
                return (0, pin, nl)
            if nl.startswith("[html]"):
                return (1, 0, nl)
            if nl.endswith(".html"):
                return (2, 0, nl)
            if nl.endswith(".py"):
                return (3, 0, nl)
            if os.path.isdir(full):
                return (4, 0, nl)
            return (5, 0, nl)

        entries = sorted(prepared, key=group_key)
        is_popup = getattr(self, "IS_POPUP", False)

        for entry, full_path, meta in entries:
            try:
                if meta is None:  # Ordner
                    b = QPushButton(entry)
                    b.clicked.connect(lambda _, p=full_path: self.enter_directory(p))
                    b.setProperty("entry_type", "folder")
                    b.setMinimumHeight(60)
                    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    layout.addWidget(b)
                    continue

                # Sichtbarkeit je Kontext (ALLOW_POPUP / ALLOW_WINDOW)
                if is_popup and meta.get("ALLOW_POPUP") is False:
                    continue
                if (not is_popup) and meta.get("ALLOW_WINDOW") is False:
                    continue

                # HTML-Button (Inline-Card), inkl. [html]-Prefix-Kompatibilität
                if meta.get("HTML_BUTTON"):
                    card = HtmlInlineButton(html_path=full_path, compact=is_popup, meta=meta)
                    card.setProperty("entry_type", "file_html_inline")
                    layout.addWidget(card)
                    continue

                # Normaler Button (Original-Stil), Parameter übersteuern Details
                b = QPushButton(meta_display_name(meta, entry))
                ipath = meta_icon_path(meta, full_path)
                if ipath:
                    from PyQt5.QtCore import QSize
                    b.setIcon(QIcon(ipath))
                    b.setIconSize(QSize(24, 24))
                b.clicked.connect(lambda _, p=full_path: self.run_script(p))
                b.setProperty("entry_type", "file")
                bh = meta.get("BUTTON_HEIGHT")
                b.setMinimumHeight(int(bh) if isinstance(bh, (int, float)) and bh > 0 else 60)
                b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                op = meta_opacity(meta)
                if op is not None:
                    eff = QGraphicsOpacityEffect(b)
                    eff.setOpacity(op)
                    b.setGraphicsEffect(eff)
                layout.addWidget(b)
            except Exception:
                print("Fehler beim Buttonbau:", traceback.format_exc())

        self.update_button_styles(layout)

    def enter_directory(self, path):
        setattr(self, "_search_query", "")
        self.current_path = path
        self.refresh_explorer()

    def go_back(self):
        setattr(self, "_search_query", "")
        parent = os.path.dirname(self.current_path)
        root = os.path.abspath(self.SCRIPT_FOLDER)
        try:
            if os.path.commonpath([parent, root]) == root:
                self.current_path = parent
                QTimer.singleShot(0, self.refresh_explorer)
                return
        except Exception:
            print("Back-Fehler:", traceback.format_exc())
        self.current_path = root
        QTimer.singleShot(0, self.refresh_explorer)

    def run_script(self, path):
        try:
            meta = read_plugin_meta(path)
            run_as = str(meta.get("RUN_AS") or "widget").lower()

            # RUN_AS = "process": immer als eigener Prozess starten
            if run_as == "process" and path.lower().endswith(".py"):
                subprocess.Popen([sys.executable, path])
                return
            # RUN_AS = "browser": HTML im Standardbrowser öffnen
            if run_as == "browser" and path.lower().endswith(".html"):
                import webbrowser
                webbrowser.open('file://' + os.path.abspath(path))
                return

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
                            QPushButton:hover {{ background-color: {'#4B5B6B' if is_dark() else '#a1b8ff'};
}}
                        """)
                    elif entry_type == "file":
                        w.setStyleSheet(f"""
                            QPushButton {{ background-color: {'#3A3A3A' if is_dark() else '#EEEEEE'}; color: {'#fff' if is_dark() else '#000'}; }}
                            QPushButton:hover {{ background-color: {'#505050' if is_dark() else '#CCCCCC'}; }}
                        """)
            else:
                if w and w.property("entry_type") == "file_html_inline":
                    w.setStyleSheet(f"""
                        QWidget {{ background-color: {'#354A3A' if is_dark() else '#d5f0d9'}; color: {'#fff' if is_dark() else '#000'}; border-radius: 8px; padding: 8px; }}
                        QWidget:hover {{ background-color: {'#456A4B' if is_dark() else '#bfe8c6'}; }}
                    """)


# =============================================================================
# HTML-Plugin-Container (geöffnetes HTML-Plugin)
# =============================================================================
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


# =============================================================================
# Theme-Bridge (HTML-Toolbar ↔ Qt)
# =============================================================================
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


# =============================================================================
# Popup (Rechtsklick auf das Tray-Icon)
# =============================================================================
class PopupWindow(ButtonContentMixin, QWidget):
    def __init__(self, app=None):
        super().__init__()
        self.IS_POPUP = True
        self.app = app
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowOpacity(POPUP_OPACITY)  # Zusatzfeature: Transparenz

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

        self.init_button_state()

        self.use_html_explorer = WEBENGINE_AVAILABLE and HTML_EXPLORER
        if self.use_html_explorer:
            # HTML-Explorer: komplette Liste wird in ui/explorer.html gerendert
            self.explorer_view = ExplorerView(host=self)
            self.explorer_root = self.explorer_view
        else:
            # Qt-Fallback (identisches Verhalten wie bisher)
            self.explorer_view = None
            self.explorer_container = QWidget()
            self.layout = QVBoxLayout(self.explorer_container)
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.setSpacing(0)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setFrameShape(QScrollArea.NoFrame)
            self._update_scrollbar_theme()
            self.scroll_area.setWidget(self.explorer_container)
            self.explorer_root = self.scroll_area

        self.pages = QStackedWidget()
        self.pages.addWidget(self.explorer_root)

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
        if self.pages.currentWidget() is self.explorer_root:
            return
        page_widget = self.pages.currentWidget()
        if not page_widget:
            return
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
        if getattr(self, "scroll_area", None) is None:
            return  # HTML-Explorer stylt seine Scrollbar selbst (ui/explorer.html)
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
                    display: flex;
                    align-items: center;
                    justify-content: flex-start; /* linksorientiert */
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
        if not WEBENGINE_AVAILABLE:
            return
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
        self.pages.setCurrentWidget(self.explorer_root)
        if WEBENGINE_AVAILABLE:
            self.html_toolbar.setVisible(False)

    def toggle_theme(self):
        global theme
        theme = "light" if is_dark() else "dark"
        set_theme(theme, self.app)
        self.refresh_explorer()
        safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def show_popup(self):
        self._update_scrollbar_theme()
        self.refresh_explorer()
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


# =============================================================================
# Hauptfenster (Linksklick auf das Tray-Icon) — mit Tabs
# =============================================================================
class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app, popup=None):
        super().__init__()
        self.setWindowIcon(QIcon("ProgrammIcon.ico") if os.path.exists("ProgrammIcon.ico") else QIcon())
        self.app = app
        self.popup = popup
        self._update_relative_size()
        self.setMinimumSize(self.width_size, self.height_size)
        if MAIN_WINDOW_OPACITY < 1.0:  # Zusatzfeature: Transparenz
            self.setWindowOpacity(MAIN_WINDOW_OPACITY)

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
        toolbar.addWidget(self.search_input)

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
        self.exit_button.clicked.connect(self.app.quit)
        toolbar.addWidget(self.exit_button)

        tb = QWidget()
        tb.setLayout(toolbar)
        self.central_layout.addWidget(tb)

        self.pages = QStackedWidget()

        self.use_html_explorer = WEBENGINE_AVAILABLE and HTML_EXPLORER
        if self.use_html_explorer:
            # HTML-Explorer: komplette Liste wird in ui/explorer.html gerendert
            self.explorer_view = ExplorerView(host=self)
            self.explorer_root = self.explorer_view
        else:
            # Qt-Fallback (identisches Verhalten wie bisher)
            self.explorer_view = None
            self.button_container = QWidget()
            self.layout = QVBoxLayout(self.button_container)
            self.layout.setContentsMargins(0, 0, 0, 0)
            self.layout.setSpacing(0)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setFrameShape(QScrollArea.NoFrame)
            self._update_scrollbar_theme()
            self.scroll_area.setWidget(self.button_container)
            self.explorer_root = self.scroll_area

        self.pages.addWidget(self.explorer_root)

        # --- TAB WIDGET für Plugins im Hauptfenster ---
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
        self.refresh_explorer()
        self.set_plugin_loader(self.load_plugin_from_path)
        self._update_tab_style()

    def showEvent(self, event):
        super().showEvent(event)
        # Native Titelleiste beim Anzeigen ans aktuelle Theme anpassen
        apply_titlebar_theme(self)

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
        self.refresh_explorer()

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

            # Öffne als Tab
            self.tab_widget.addTab(page, "Link")
            self.tab_widget.setCurrentWidget(page)
            self.pages.setCurrentWidget(self.tab_widget)

            self.show_explorer_btn = True
            self._build_html_toolbar()
            if WEBENGINE_AVAILABLE:
                safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')
        except Exception as e:
            QMessageBox.critical(self, "Link öffnen fehlgeschlagen", str(e))

    def _update_scrollbar_theme(self):
        if getattr(self, "scroll_area", None) is None:
            return  # HTML-Explorer stylt seine Scrollbar selbst (ui/explorer.html)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ background: transparent; }}
            QScrollBar:vertical {{
                background: {'#292929' if is_dark() else '#ffffff'};
                width: 10px; margin: 0; border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: #666; min-height: 20px; border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical
{{ background: none; height: 0; }}
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
                min-width: 60px; /* Small minimum width */
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
            print("Fehler beim Setzen der Toolbar HTML:", traceback.format_exc())

    def toggle_theme(self):
        global theme
        theme = "light" if is_dark() else "dark"
        set_theme(theme, self.app)
        self.refresh_explorer()
        self._update_scrollbar_theme()
        self._update_searchbar_theme()
        self._update_tab_style()
        apply_titlebar_theme(self)  # native Windows-Titelleiste mit umschalten
        if self.popup and self.popup.isVisible():
            self.popup.refresh_explorer()
            self.popup._update_scrollbar_theme()
        if WEBENGINE_AVAILABLE:
            safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def go_back_to_explorer(self):
        # Tabs bleiben offen — Plugins laufen im Hintergrund weiter.
        self.pages.setCurrentWidget(self.explorer_root)
        self.show_explorer_btn = False
        self._build_html_toolbar()
        if WEBENGINE_AVAILABLE:
            safe_run_js(self.html_toolbar, f'window.setThemeUI && window.setThemeUI("{theme}");')

    def load_plugin_from_path(self, path: str, source_widget=None):
        try:
            meta = read_plugin_meta(path)
            run_as = str(meta.get("RUN_AS") or "widget").lower()
            plugin_mode = "Popup" if isinstance(source_widget, PopupWindow) else "Window"

            # RUN_AS-Parameter: eigener Prozess / Browser statt Widget
            if run_as == "process" and path.lower().endswith(".py"):
                subprocess.Popen([sys.executable, path])
                return
            if run_as == "browser" and path.lower().endswith(".html"):
                import webbrowser
                webbrowser.open('file://' + os.path.abspath(path))
                return

            # --- POPUP-LOGIK (ohne Tabs) ---
            if plugin_mode == "Popup":
                if path.lower().endswith('.py'):
                    widget = self.load_python_plugin_widget(path, mode=plugin_mode)
                    if widget is None:
                        return
                elif path.lower().endswith('.html'):
                    widget = HtmlPluginContainer(path)
                else:
                    subprocess.Popen([sys.executable, path])
                    return

                source_widget.show_plugin_widget(widget, meta.get("NAME") or os.path.basename(path))
                return

            # --- HAUPTFENSTER-LOGIK (mit Tabs) ---
            # 1. Läuft das Plugin schon in einem Tab?
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

            # 2. Neues Plugin laden
            if path.lower().endswith('.py'):
                widget = self.load_python_plugin_widget(path, mode=plugin_mode)
                if widget is None:
                    return
            elif path.lower().endswith('.html'):
                widget = HtmlPluginContainer(path)
            else:
                subprocess.Popen([sys.executable, path])
                return

            # 3. Als Tab hinzufügen
            container = QWidget()
            v = QVBoxLayout(container)
            v.setContentsMargins(12, 12, 12, 12)
            v.addWidget(widget)

            container.setProperty("plugin_path", path)
            tab_title = meta.get("NAME") or os.path.basename(path)
            ipath = meta_icon_path(meta, path)
            if ipath:
                self.tab_widget.addTab(container, QIcon(ipath), tab_title)
            else:
                if isinstance(meta.get("ICON"), str) and meta["ICON"].strip():
                    tab_title = f"{meta['ICON'].strip()} {tab_title}"
                self.tab_widget.addTab(container, tab_title)
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


# =============================================================================
# Tray-Applikation
# =============================================================================
class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)
        self.setStyleSheet(current_stylesheet())
        self.setProperty("toolbar_theme", theme)
        if WEBENGINE_AVAILABLE and HTML_EXPLORER:
            ensure_ui_file()  # anpassbare Explorer-UI bereitstellen
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
        import ctypes
        import platform
        if platform.system().lower() == "windows":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"meinefirma.skriptstarter.1.0")
    except Exception:
        pass
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())
