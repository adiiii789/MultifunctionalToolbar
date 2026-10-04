"""Multifunctional Toolbar - Systemtray-Launcher fuer Plugins (PyQt5 + WebEngine).

Linksklick auf das Tray-Icon oeffnet das Hauptfenster (Plugins als Tabs),
Rechtsklick das kompakte Popup. Plugins liegen im Ordner ``scripts``.

Plugin-Parameter
----------------
Plugins steuern ihre Darstellung ueber Konstanten in der eigenen Datei.
Die Werte werden per AST gelesen, die Datei wird dafuer NICHT ausgefuehrt::

    HTML_BUTTON   = True                         # Button als HTML-Card rendern
    BUTTON_HTML   = "<div>Mein Button</div>"     # HTML der Card
    BUTTON_HTML_FILE = "card.html"               # alternativ: HTML-Datei (relativ)
    BUTTON_HEIGHT = 80                           # Hoehe in px
    OPACITY       = 0.85                         # Transparenz (0..1)
    NAME          = "Musik"                      # Anzeigename statt Dateiname
    ICON          = "🎵"                         # Emoji/Text oder Bilddatei
    RUN_AS        = "widget"                     # "widget" | "process" | "browser"
    ALLOW_POPUP   = True                         # im Popup anzeigen
    ALLOW_WINDOW  = True                         # im Hauptfenster anzeigen
    MEDIA_BRIDGE  = True                         # WebChannel-Mediensteuerung
    PINNED        = 1                            # True oder Zahl: oben anpinnen

In .html-Dateien gehen dieselben Parameter als fuehrende Kommentare:
``<!-- html_button: true -->``. Der Dateiname-Prefix ``[html]`` und
``get_inline_html(mode)`` funktionieren weiterhin.

EXE bauen::

    pyinstaller --noconsole --onefile --icon=ProgrammIcon.ico --add-data "scripts;scripts" tray_launcher.py
"""
from __future__ import annotations

import ast
import contextlib
import ctypes
import html
import importlib.util
import json
import logging
import os
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from string import Template
from types import ModuleType
from collections.abc import Callable
from typing import NamedTuple

from PyQt5.QtCore import (
    QEasingCurve, QEvent, QFileSystemWatcher, QObject, QPropertyAnimation,
    QRect, QSize, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot,
)
from PyQt5.QtGui import QColor, QCursor, QGuiApplication, QIcon
from PyQt5.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QStackedWidget, QSystemTrayIcon, QTabWidget,
    QVBoxLayout, QWidget,
)

# Diese Pakete nutzt kein Launcher-Code, aber Plugins (Kalender o. Ae.).
# Der Import sorgt dafuer, dass PyInstaller sie mit in die EXE packt.
try:
    import dateutil.rrule  # noqa: F401  # pylint: disable=unused-import
    import icalendar  # noqa: F401  # pylint: disable=unused-import
    import pytz  # noqa: F401  # pylint: disable=unused-import
except ImportError:
    print("WARNUNG: Optionale Plugin-Abhaengigkeiten (pytz, dateutil, icalendar) fehlen.")

# --- WebEngine ist optional: ohne sie laeuft der klassische Qt-Explorer ------
try:
    from PyQt5.QtWebChannel import QWebChannel  # pylint: disable=ungrouped-imports
    from PyQt5.QtWebEngine import QtWebEngine
    from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineSettings, QWebEngineView
    QtWebEngine.initialize()  # muss vor dem QApplication-Objekt passieren
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

log = logging.getLogger("tray_launcher")


# =============================================================================
# Konfiguration
# =============================================================================
SCRIPT_FOLDER = "scripts"             # Plugin-Ordner
SETTINGS_FILE = "settings.json"       # gespeicherter Design-Modus + Theme
UI_FOLDER = "ui"                      # anpassbare Explorer-Oberflaeche
APP_TITLE = "Multifunctional Toolbar"
APP_USER_MODEL_ID = "meinefirma.skriptstarter.1.0"
PROGRAM_ICON = "ProgrammIcon.ico"
TRAY_ICON = "TrayIcon.ico"

POPUP_OPACITY = 0.97                  # Transparenz des Rechtsklick-Popups (1.0 = deckend)
MAIN_WINDOW_OPACITY = 1.0             # Transparenz des Hauptfensters

# Plugin-Liste als HTML (ui/explorer.html). False/ohne WebEngine -> Qt-Explorer.
HTML_EXPLORER = True

# Farbe der nativen Windows-Titelleiste (Snap/Andocken bleiben erhalten).
TITLEBAR_COLORS = {
    # Theme: (Hintergrund, Text)
    "dark": ("#2E2E2E", "#FFFFFF"),
    "light": ("#FFFFFF", "#000000"),
}

DEFAULT_BUTTON_HEIGHT = 60
FOLDER_BUTTON_HEIGHT = 60
BACK_BUTTON_HEIGHT = 40
ICON_SIZE = 24
ICON_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp")

# PINNED = True ohne Zahl landet hinter allen nummerierten Pins.
UNNUMBERED_PIN_RANK = 10**9


# =============================================================================
# Einstellungen & Theme
# =============================================================================
@dataclass
class AppSettings:
    """Laufzeit-Einstellungen; ersetzt die frueheren globalen Variablen."""

    theme: str = "dark"          # "dark" | "light" (nur im Opaque-Modus relevant)
    glass_mode: bool = True      # Glas = durchscheinend, immer dunkel

    @property
    def dark(self) -> bool:
        return self.glass_mode or self.theme == "dark"

    @property
    def effective_theme(self) -> str:
        return "dark" if self.dark else "light"

    def load(self, path: str = SETTINGS_FILE) -> None:
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            log.warning("%s konnte nicht gelesen werden: %s", path, exc)
            return
        if isinstance(data.get("glass_mode"), bool):
            self.glass_mode = data["glass_mode"]
        if data.get("theme") in ("dark", "light"):
            self.theme = data["theme"]

    def save(self, path: str = SETTINGS_FILE) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"glass_mode": self.glass_mode, "theme": self.theme}, f, indent=2)
        except OSError as exc:
            log.warning("%s konnte nicht geschrieben werden: %s", path, exc)


SETTINGS = AppSettings()

# Farben des deckenden (Opaque-)Modus je Theme.
OPAQUE_COLORS = {
    "dark": {
        "window": "#2E2E2E", "text": "#FFFFFF",
        "folder": "#3A4A6A", "folder_hover": "#4B5B6B",
        "file": "#3A3A3A", "file_hover": "#505050",
        "back": "#666666", "back_hover": "#777777",
        "card": "#354A3A", "card_hover": "#456A4B",
        "input_bg": "#292929", "input_fg": "#FFFFFF", "input_border": "#777777",
        "exit": "#AA3333", "exit_hover": "#CC4444",
        "tool_btn": "#444444", "tool_btn_hover": "#555555", "tool_btn_fg": "#FFFFFF", "tool_btn_border": "#666666",
        "btn": "#3E3E3E", "btn_hover": "#4E4E4E", "btn_fg": "#F1F1F1", "btn_border": "#555555",
        "box": "#383838",
        "tab": "#222222", "tab_fg": "#AAAAAA", "tab_sel": "#3A4A6A", "tab_sel_fg": "#FFFFFF", "tab_hover": "#333333",
        "scroll_track": "#292929", "scroll_handle": "#666666",
        "scroll_track_compact": "#292929", "scroll_handle_compact": "#666666",
    },
    "light": {
        "window": "#FFFFFF", "text": "#000000",
        "folder": "#C2D1FF", "folder_hover": "#A1B8FF",
        "file": "#EEEEEE", "file_hover": "#CCCCCC",
        "back": "#BBBBBB", "back_hover": "#CCCCCC",
        "card": "#D5F0D9", "card_hover": "#BFE8C6",
        "input_bg": "#FFFFFF", "input_fg": "#292929", "input_border": "#888888",
        "exit": "#FF5555", "exit_hover": "#FF6666",
        "tool_btn": "#DDDDDD", "tool_btn_hover": "#CCCCCC", "tool_btn_fg": "#333333", "tool_btn_border": "#AAAAAA",
        "btn": "#E0E0E0", "btn_hover": "#D0D0D0", "btn_fg": "#1A1A1A", "btn_border": "#BBBBBB",
        "box": "#F0F0F0",
        "tab": "#E0E0E0", "tab_fg": "#555555", "tab_sel": "#C2D1FF", "tab_sel_fg": "#000000", "tab_hover": "#EAEAEA",
        "scroll_track": "#FFFFFF", "scroll_handle": "#666666",
        "scroll_track_compact": "#D6D6D6", "scroll_handle_compact": "#999999",
    },
}

# Glas-Look (nur Dark).
GLASS_PANEL = ("background: rgba(18,18,22,0.55); border: 1px solid rgba(255,255,255,0.08);"
               " border-radius: 14px;")
GLASS_BUTTON = ("background: rgba(255,255,255,0.08); color: #F1F1F1;"
                " border: 1px solid rgba(255,255,255,0.12); border-radius: 10px;")
GLASS_BUTTON_HOVER = "background: rgba(255,255,255,0.14);"


def colors() -> dict:
    """Farbtabelle des aktuellen Themes (Opaque-Modus)."""
    return OPAQUE_COLORS[SETTINGS.effective_theme]


def app_stylesheet() -> str:
    if SETTINGS.glass_mode:
        # Transparente Basis - die Fenster-Container malen den Glas-Look.
        return "QWidget { background-color: transparent; color: #FFFFFF; }"
    c = colors()
    return f"QWidget {{ background-color: {c['window']}; color: {c['text']}; }}"


def panel_css() -> str:
    """Hintergrund der Fenster-Container (Glas oder deckend)."""
    if SETTINGS.glass_mode:
        return GLASS_PANEL
    return f"background: {colors()['window']}; border: none; border-radius: 0px;"


def scrollbar_css(compact: bool = False) -> str:
    if SETTINGS.glass_mode:
        track, handle = "rgba(0,0,0,0.04)", "rgba(255,255,255,0.28)"
    else:
        suffix = "_compact" if compact else ""
        track, handle = colors()["scroll_track" + suffix], colors()["scroll_handle" + suffix]
    return f"""
        QScrollArea {{ background: transparent; }}
        QScrollBar:vertical {{ background: {track}; width: 10px; margin: 0; border-radius: 5px; }}
        QScrollBar::handle:vertical {{ background: {handle}; min-height: 20px; border-radius: 5px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ background: none; height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    """


def button_css(base: str, hover: str, extra: str = "") -> str:
    return (f"QPushButton {{ {base} {extra} }}"
            f" QPushButton:hover {{ {hover} }}")


def apply_app_theme(app: QApplication | None = None) -> None:
    """Globales Stylesheet + Theme-Property setzen (Cards lesen die Property)."""
    app = app or QApplication.instance()
    if app is not None:
        app.setStyleSheet(app_stylesheet())
        app.setProperty("toolbar_theme", SETTINGS.effective_theme)


# =============================================================================
# Systemdienste aus services.py (Mediensteuerung, Titelleiste)
# =============================================================================
class _StubMediaBridge(QObject):
    """Ersatz, falls services.py fehlt - Cards brechen dann nicht.

    Methoden-/Signalnamen sind camelCase, weil JavaScript sie so aufruft.
    """

    themeChanged = pyqtSignal(str)  # noqa: N815
    mediaInfoChanged = pyqtSignal(str)  # noqa: N815

    @pyqtSlot(result=str)
    def getTheme(self) -> str:  # noqa: N802
        return SETTINGS.effective_theme

    @pyqtSlot()
    def requestMediaInfo(self) -> None:  # noqa: N802
        self.mediaInfoChanged.emit('{"available": false}')

    @pyqtSlot()
    def playPause(self) -> None:  # noqa: N802
        """No-op."""

    @pyqtSlot()
    def next(self) -> None:
        """No-op."""

    @pyqtSlot()
    def prev(self) -> None:
        """No-op."""

    @pyqtSlot()
    def stop(self) -> None:
        """No-op."""

    @pyqtSlot()
    def mute(self) -> None:
        """No-op."""

    @pyqtSlot()
    def volUp(self) -> None:  # noqa: N802
        """No-op."""

    @pyqtSlot()
    def volDown(self) -> None:  # noqa: N802
        """No-op."""


def _stub_titlebar(_widget, _dark, _caption_color, _text_color) -> None:
    """Ohne services.py bleibt die native Standard-Titelleiste."""


# noinspection PyBroadException
try:
    import services as _services
except Exception as _exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
    # Bewusst breit: Ein Fehler in services.py darf den Launcher nicht stoppen.
    log.warning("services.py fehlt/fehlerhaft (%r) - Systemdienste laufen als No-op-Stub.", _exc)
    _services = None

MediaControlBridge = getattr(_services, "MediaControlBridge", _StubMediaBridge)
apply_native_titlebar = getattr(_services, "apply_native_titlebar", _stub_titlebar)


def create_services(parent: QObject) -> dict:
    """Alle Systemdienste fuer den WebChannel des Explorers ("media", ...)."""
    factory = getattr(_services, "create_services", None)
    if callable(factory):
        return factory(parent)
    return {"media": MediaControlBridge(parent)}


def apply_titlebar_theme(widget: QWidget) -> None:
    caption, text = TITLEBAR_COLORS[SETTINGS.effective_theme]
    apply_native_titlebar(widget, SETTINGS.dark, caption, text)


# =============================================================================
# Plugin-Parameter (PluginMeta)
# =============================================================================
PLUGIN_META_KEYS = frozenset({
    "HTML_BUTTON", "BUTTON_HTML", "BUTTON_HTML_FILE", "BUTTON_HEIGHT", "NAME", "ICON",
    "OPACITY", "RUN_AS", "ALLOW_POPUP", "ALLOW_WINDOW", "MEDIA_BRIDGE", "PINNED",
})
_HTML_META_COMMENT = re.compile(r"<!--\s*([A-Za-z_]+)\s*[:=]\s*(.+?)\s*-->")


def _is_number(value) -> bool:
    # bool ist in Python eine Unterklasse von int (True == 1) und muss raus.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _text(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _positive_int(value) -> int | None:
    return int(value) if _is_number(value) and value > 0 else None


def _flag(value, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _opacity(value) -> float | None:
    return float(value) if _is_number(value) and 0.0 < value < 1.0 else None


def _pin_rank(value) -> int | None:
    """PINNED = True -> angepinnt ohne Reihenfolge, Zahl > 0 -> Reihenfolge."""
    if isinstance(value, bool):
        return UNNUMBERED_PIN_RANK if value else None
    return _positive_int(value)


def _parse_html_meta_value(raw: str):
    """'true' / '0.5' / '"text"' aus einem HTML-Kommentar -> Python-Wert."""
    low = raw.strip().lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        return ast.literal_eval(raw.strip())
    except (ValueError, SyntaxError):
        return raw.strip()


def _raw_meta_from_python(path: str) -> dict:
    with open(path, encoding="utf-8", errors="replace") as f:
        source = f.read()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    meta = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        key = node.targets[0].id.upper()
        if key not in PLUGIN_META_KEYS:
            continue
        with contextlib.suppress(ValueError, TypeError):  # nur einfache Literale erlaubt
            meta[key] = ast.literal_eval(node.value)
    return meta


def _raw_meta_from_html(path: str) -> dict:
    with open(path, encoding="utf-8", errors="replace") as f:
        head = f.read(4096)
    return {m.group(1).upper(): _parse_html_meta_value(m.group(2))
            for m in _HTML_META_COMMENT.finditer(head)
            if m.group(1).upper() in PLUGIN_META_KEYS}


@dataclass(frozen=True)
class PluginMeta:
    """Geprüfte Plugin-Parameter. Ungueltige Werte fallen auf den Standard zurueck."""

    html_button: bool = False
    button_html: str | None = None
    button_html_file: str | None = None
    button_height: int | None = None
    name: str | None = None
    icon: str | None = None
    opacity: float | None = None
    run_as: str = "widget"
    allow_popup: bool = True
    allow_window: bool = True
    media_bridge: bool = True
    pin_rank: int | None = None

    @classmethod
    def from_file(cls, path: str) -> PluginMeta:
        raw = {}
        lower = path.lower()
        try:
            if lower.endswith(".py"):
                raw = _raw_meta_from_python(path)
            elif lower.endswith(".html"):
                raw = _raw_meta_from_html(path)
        except OSError as exc:
            log.warning("Plugin-Parameter von %s nicht lesbar: %s", path, exc)
        if os.path.basename(lower).startswith("[html]"):  # Abwaertskompatibilitaet
            raw.setdefault("HTML_BUTTON", True)
        return cls(
            html_button=bool(raw.get("HTML_BUTTON", False)),
            button_html=_text(raw.get("BUTTON_HTML")),
            button_html_file=_text(raw.get("BUTTON_HTML_FILE")),
            button_height=_positive_int(raw.get("BUTTON_HEIGHT")),
            name=_text(raw.get("NAME")),
            icon=_text(raw.get("ICON")),
            opacity=_opacity(raw.get("OPACITY")),
            run_as=str(raw.get("RUN_AS") or "widget").lower(),
            allow_popup=_flag(raw.get("ALLOW_POPUP"), True),
            allow_window=_flag(raw.get("ALLOW_WINDOW"), True),
            media_bridge=_flag(raw.get("MEDIA_BRIDGE"), True),
            pin_rank=_pin_rank(raw.get("PINNED")),
        )

    @property
    def icon_is_image(self) -> bool:
        return bool(self.icon) and self.icon.lower().endswith(ICON_IMAGE_EXTS)

    def icon_path(self, plugin_path: str) -> str | None:
        """Absoluter Pfad, wenn ICON auf eine existierende Bilddatei zeigt."""
        if not self.icon_is_image:
            return None
        candidate = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(plugin_path)), self.icon))
        return candidate if os.path.exists(candidate) else None

    def display_name(self, filename: str) -> str:
        name = self.name or (filename[:-3] if filename.lower().endswith(".py") else filename)
        if self.icon and not self.icon_is_image:
            name = f"{self.icon} {name}"
        return name

    def tab_title(self, plugin_path: str) -> str:
        return self.name or os.path.basename(plugin_path)


def card_metrics(meta: PluginMeta, compact: bool) -> tuple[int, int, int]:
    """Hoehe und Innenabstand (oben, unten) einer HTML-Card."""
    probe = QPushButton("Wg")
    base_height = max(28, probe.sizeHint().height())
    probe.deleteLater()
    height = meta.button_height or int(base_height * (2.4 if compact else 1.8))
    padding = max(4, height // 8)
    return height, padding, padding


# =============================================================================
# Plugin-Module laden & starten
# =============================================================================
_MODULE_CACHE: dict[str, tuple[float | None, ModuleType]] = {}


def load_plugin_module(path: str, *, cached: bool = True) -> ModuleType:
    """Plugin-Datei als Modul laden.

    ``cached=True``: einmal pro Dateiaenderung laden. Card-Plugins behalten so
    ihren Zustand, und get_inline_html()/handle_call() laufen im selben Modul.
    ``cached=False``: frisch laden (fuer PluginWidget-Fenster).
    Fehler im Plugin-Code werden an den Aufrufer weitergereicht.
    """
    path = os.path.abspath(path)
    mtime = os.path.getmtime(path) if os.path.exists(path) else None
    if cached and path in _MODULE_CACHE and _MODULE_CACHE[path][0] == mtime:
        return _MODULE_CACHE[path][1]
    spec = importlib.util.spec_from_file_location(f"plugin_{abs(hash(path))}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Kein Python-Modul: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if cached:
        _MODULE_CACHE[path] = (mtime, module)
    return module


def error_html(title: str, details: str = "") -> str:
    body = html.escape(title) + ("\n" + html.escape(details) if details else "")
    return f"<pre style='margin:8px;color:#c00;white-space:pre-wrap;'>{body}</pre>"


def inline_html_from_module(path: str, mode: str) -> str:
    """get_inline_html(mode) eines Plugins (Kompatibilitaet)."""
    name = os.path.basename(path)
    # noinspection PyBroadException
    try:
        func = getattr(load_plugin_module(path), "get_inline_html", None)
        if not callable(func):
            return error_html(f"Fehlende Funktion get_inline_html(mode) oder BUTTON_HTML-Parameter in {name}")
        result = func(mode=mode)
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # Bewusst breit: Plugin-Code kann jeden Fehler werfen, die Card zeigt ihn an.
        log.warning("Fehler in %s: %r", name, exc)
        return error_html(f"Fehler in {name}:", repr(exc))
    if not isinstance(result, str):
        return error_html("get_inline_html() muss einen String liefern.")
    return result


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as exc:
        return error_html(f"Fehler beim Lesen von {os.path.basename(path)}:", str(exc))


class CardSource(NamedTuple):
    """Inhalt einer Card: entweder fertiges HTML oder eine HTML-Datei."""

    html: str | None
    file: str | None
    base_dir: str


def resolve_card_source(path: str, meta: PluginMeta, mode: str) -> CardSource:
    """Waehlt den Card-Inhalt nach Prioritaet:

    1. BUTTON_HTML  2. BUTTON_HTML_FILE  3. .html-Datei
    4. .py mit get_inline_html(mode)  5. Dateiinhalt als <pre>
    """
    base_dir = os.path.dirname(os.path.abspath(path))
    if meta.button_html:
        return CardSource(meta.button_html, None, base_dir)
    if meta.button_html_file:
        candidate = os.path.abspath(os.path.join(base_dir, meta.button_html_file))
        if os.path.exists(candidate):
            return CardSource(None, candidate, os.path.dirname(candidate))
    if path.lower().endswith(".html"):
        return CardSource(None, os.path.abspath(path), base_dir)
    if path.lower().endswith(".py"):
        return CardSource(inline_html_from_module(path, mode), None, base_dir)
    content = html.escape(read_text(path))
    return CardSource(f"<pre style='margin:0;padding:8px;font:13px/1.3 monospace;'>{content}</pre>",
                      None, base_dir)


def open_in_browser(path_or_url: str) -> None:
    url = path_or_url if "://" in path_or_url else QUrl.fromLocalFile(os.path.abspath(path_or_url)).toString()
    webbrowser.open(url)


def launch_external(path: str, meta: PluginMeta) -> bool:
    """RUN_AS = "process"/"browser" ausfuehren. True, wenn erledigt."""
    lower = path.lower()
    if meta.run_as == "process" and lower.endswith(".py"):
        subprocess.Popen([sys.executable, path])  # pylint: disable=consider-using-with
        return True
    if meta.run_as == "browser" and lower.endswith(".html"):
        open_in_browser(path)
        return True
    return False


def is_inside_script_folder(path: str) -> bool:
    root = os.path.abspath(SCRIPT_FOLDER)
    try:
        return os.path.commonpath([os.path.abspath(path), root]) == root
    except ValueError:  # z. B. anderes Laufwerk unter Windows
        return False


# =============================================================================
# HTML-Vorlagen (Toolbars, Card-Wrapper, Explorer)
# =============================================================================
TOOLBAR_BUTTON_CSS = """
    .toolbar-btn {
        padding: 4px 10px; border: 1px solid transparent; border-radius: 6px;
        font-size: 12px; font-weight: 500; cursor: pointer; outline: none;
        background: transparent !important; min-height: 28px; min-width: 80px;
        transition: background .3s, color .3s, border-color .3s;
    }
    .light { color: #333; border-color: #dddddd; }
    .dark  { color: #f5f5f5; border-color: #444; }
"""

POPUP_TOOLBAR_HTML = Template("""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"><title>Toolbar</title>
<style>
    html, body { background: transparent !important; margin: 0; overflow: hidden !important; }
    .toolbar-container { display: flex; align-items: center; height: 32px; padding: 0 8px; gap: 8px; }
    $button_css
</style></head>
<body>
<div class="toolbar-container">
    <button id="explorerBtn" class="toolbar-btn $mode">&larr; Explorer</button>
</div>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
    new QWebChannel(qt.webChannelTransport, function (channel) {
        var bridge = channel.objects.bridge;
        document.getElementById("explorerBtn").onclick = function () { bridge.goBackToExplorer(); };
    });
</script>
</body></html>
""")

MAIN_TOOLBAR_HTML = Template("""<!DOCTYPE html>
<html lang="de"><head><meta charset="UTF-8"><title>Toolbar</title>
<style>
    html, body { height: 100%; margin: 0; padding: 0; background: transparent; }
    $button_css
    .toolbar-container { display: flex; align-items: center; height: 2.5rem; padding: 0 2vw; gap: 0.5em; }
    #explorerBtn { margin-left: 1.5rem; display: $explorer_display; }

    /* --- Theme-Switch (im Glas-Modus ausgeblendet) --- */
    .switch { display: $switch_display; position: relative; width: 5rem; height: 2.5rem;
              cursor: pointer; user-select: none; margin-top: 0.4rem; }
    .switch input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0;
                    opacity: 0; cursor: pointer; z-index: 3; }
    .background { position: absolute; top: 0; left: 0; width: 5rem; height: 2rem; border-radius: 1.25rem;
                  border: 0.15rem solid #202020; background: linear-gradient(to right, #484848 0%, #202020 100%);
                  transition: all 0.3s; z-index: 1; }
    .stars1, .stars2 { position: absolute; height: 0.2rem; width: 0.2rem; background: #FFFFFF;
                       border-radius: 50%; transition: 0.3s all ease; }
    .stars1 { top: 0.2em; right: 0.8em; }
    .stars2 { top: 1.3em; right: 1.75em; }
    .sun-moon { position: absolute; left: 0; top: 0; height: 1.5rem; width: 1.5rem; margin: 0.25rem;
                background: #FFFDF2; border-radius: 50%; border: 0.15rem solid #DEE2C6;
                transition: all 0.5s ease; z-index: 2; }
    .sun-moon .dots { position: absolute; top: 0.1em; left: 0.7em; height: 0.5rem; width: 0.5rem;
                      background: #EFEEDB; border: 0.15rem solid #DEE2C6; border-radius: 50%;
                      transition: 0.4s all ease; }
    .switch input:checked ~ .sun-moon { left: calc(100% - 2rem); background: #F5EC59;
                                        border-color: #E7C65C; transform: rotate(-25deg); }
    .switch input:checked ~ .background { border: 0.15rem solid #78C1D5;
                                          background: linear-gradient(to right, #78C1D5 0%, #BBE7F5 100%); }
</style></head>
<body>
<div class="toolbar-container">
    <div class="switch">
        <label for="toggle">
            <input id="toggle" type="checkbox" $checked>
            <div class="sun-moon"><div class="dots"></div></div>
            <div class="background"><div class="stars1"></div><div class="stars2"></div></div>
        </label>
    </div>
    <button id="explorerBtn" class="toolbar-btn $mode">&larr; Explorer</button>
</div>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
    new QWebChannel(qt.webChannelTransport, function (channel) {
        var bridge = channel.objects.bridge;
        var toggle = document.getElementById("toggle");
        var explorerBtn = document.getElementById("explorerBtn");
        toggle.addEventListener("change", function () {
            bridge.toggleTheme();
            explorerBtn.className = "toolbar-btn " + (toggle.checked ? "light" : "dark");
        });
        explorerBtn.onclick = function () { bridge.goBackToExplorer(); };
    });
</script>
</body></html>
""")

# Wrapper fuer Cards im HTML-Explorer (iframe). Stellt window.media,
# window.toolbarMode, openPlugin() und pluginCall() bereit, faengt Links ab
# und blockiert Scrollen.
CARD_WRAPPER_HTML = Template("""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{margin:0;padding:0;height:100%;overflow:hidden;background:transparent}
*{box-sizing:border-box}$opacity_css</style>
$content
<script>
window.toolbarMode = $mode;
window.pluginPath = $plugin_path;
window.openPlugin = function (p) {
    if (window.parent && window.parent.openPluginFromCard) window.parent.openPluginFromCard(p || "", window.pluginPath);
};
window.pluginCall = function (method, args, cb) {
    if (window.parent && window.parent.pluginCallFromCard) {
        window.parent.pluginCallFromCard(window.pluginPath, method || "",
                                         JSON.stringify(args || {}), cb || function () {});
    }
};
(function hook() {
    if (window.parent && window.parent.media) { window.media = window.parent.media; } else { setTimeout(hook, 120); }
})();
document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest ? e.target.closest("a") : null;
    if (a && a.href) {
        e.preventDefault();
        if (window.parent && window.parent.openLinkFromCard) window.parent.openLinkFromCard(a.href);
    }
}, true);
["wheel", "touchmove"].forEach(function (evt) {
    window.addEventListener(evt, function (e) { e.preventDefault(); }, {passive: false});
});
window.addEventListener("keydown", function (e) {
    var blocked = ["ArrowUp", "ArrowDown", "PageUp", "PageDown", " "];
    if (e.ctrlKey || blocked.indexOf(e.key) !== -1) { e.preventDefault(); e.stopPropagation(); }
}, true);
</script>""")

# Wrapper fuer Cards im Qt-Explorer (eigene QWebEngineView pro Card).
QT_CARD_WRAPPER_HTML = Template("""<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{margin:0;padding:0;height:100%;overflow:hidden;background:transparent}
*{box-sizing:border-box}$opacity_css</style>
$content
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
window.toolbarMode = $mode;
if (window.qt && qt.webChannelTransport) {
    new QWebChannel(qt.webChannelTransport, function (ch) { window.media = ch.objects.media; });
}
["wheel", "touchmove"].forEach(function (evt) {
    window.addEventListener(evt, function (e) { e.preventDefault(); }, {passive: false});
});
window.addEventListener("keydown", function (e) {
    var blocked = ["ArrowUp", "ArrowDown", "PageUp", "PageDown", " "];
    if (e.ctrlKey || blocked.indexOf(e.key) !== -1) { e.preventDefault(); e.stopPropagation(); }
}, true);
</script>""")


def _opacity_css(opacity: float | None) -> str:
    return f"body{{opacity:{opacity};}}" if opacity is not None else ""


def wrap_card_html(content: str, mode: str, opacity: float | None, plugin_path: str) -> str:
    return CARD_WRAPPER_HTML.substitute(
        content=content, mode=json.dumps(mode), plugin_path=json.dumps(plugin_path or ""),
        opacity_css=_opacity_css(opacity))


# Standard-Oberflaeche des HTML-Explorers. Wird beim ersten Start nach
# ui/explorer.html geschrieben und kann dort frei angepasst werden.
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

  /* ==== Glas-Modus (Einstellungen → Transparent, nur Dark) =============== */
  html[data-glass="true"] {
    --text: #f1f1f1;
    --folder-bg: rgba(255,255,255,0.08);  --folder-hover: rgba(255,255,255,0.14);
    --file-bg:   rgba(255,255,255,0.08);  --file-hover:   rgba(255,255,255,0.14);
    --card-bg:   rgba(18,18,22,0.55);     --card-hover:   rgba(255,255,255,0.18);
    --back-bg:   rgba(255,255,255,0.08);  --back-hover:   rgba(255,255,255,0.14);  --back-text: #f1f1f1;
    --scroll-track: rgba(0,0,0,0.04);  --scroll-handle: rgba(255,255,255,0.28);
    --btn-border: 1px solid rgba(255,255,255,0.12);
    --btn-radius: 10px;
    --card-border: 1px solid rgba(255,255,255,0.08);
  }
  html[data-glass="true"] .folder,
  html[data-glass="true"] .back { font-weight: 600; }

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
    border: var(--btn-border, none); border-radius: var(--btn-radius, 0);
    box-sizing: border-box;
  }
  .folder { background: var(--folder-bg); }
  .folder:hover { background: var(--folder-hover); }
  .file { background: var(--file-bg); }
  .file:hover { background: var(--file-hover); }
  .entry-icon { height: 24px; width: 24px; object-fit: contain; margin-right: 8px; }
  .back { background: var(--back-bg); color: var(--back-text); font-weight: bold; min-height: 40px; }
  .back:hover { background: var(--back-hover); }

  .card {
    background: var(--card-bg); border-radius: 8px; border: var(--card-border, none);
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
    document.documentElement.setAttribute('data-glass', state.glass ? 'true' : 'false');
    const list = document.getElementById('list');
    list.innerHTML = '';

    if (!state.isRoot) {
      const b = document.createElement('button');
      b.className = 'entry-btn back';
      b.textContent = '← Zurück';
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


def ensure_ui_file() -> str | None:
    """Legt ui/explorer.html beim ersten Start an und liefert den Pfad."""
    ui_path = os.path.abspath(os.path.join(UI_FOLDER, "explorer.html"))
    try:
        os.makedirs(os.path.dirname(ui_path), exist_ok=True)
        if not os.path.exists(ui_path):
            with open(ui_path, "w", encoding="utf-8") as f:
                f.write(EXPLORER_DEFAULT_HTML)
    except OSError as exc:
        log.warning("ui/explorer.html konnte nicht angelegt werden: %s", exc)
        return None
    return ui_path


# =============================================================================
# Beispiel-Plugins (werden angelegt, wenn der Plugin-Ordner leer ist)
# =============================================================================
SAMPLE_TIMER_PLUGIN = """\
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class PluginWidget(QWidget):
    def __init__(self, mode='Window'):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel('⏱️ Timer-Plugin')
        title.setStyleSheet('font-weight: bold; font-size: 16px;')
        layout.addWidget(title)
        self.label = QLabel('0 s')
        self.label.setStyleSheet('font-size: 24px;')
        layout.addWidget(self.label)
        row = QHBoxLayout()
        start_btn, stop_btn, reset_btn = QPushButton('Start'), QPushButton('Stop'), QPushButton('Reset')
        for btn in (start_btn, stop_btn, reset_btn):
            row.addWidget(btn)
        layout.addLayout(row)
        self.seconds = 0
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_time)
        start_btn.clicked.connect(self.timer.start)
        stop_btn.clicked.connect(self.timer.stop)
        reset_btn.clicked.connect(self.reset)

    def update_time(self):
        self.seconds += 1
        self.label.setText(f'{self.seconds} s')

    def reset(self):
        self.seconds = 0
        self.label.setText('0 s')
"""

SAMPLE_MUSIC_CARD = '''\
# Demo fuer das Parametersystem: der Listen-Button ist eine HTML-Card.
HTML_BUTTON = True
BUTTON_HEIGHT = 72
OPACITY = 0.9
NAME = "Musik"
ICON = "🎵"
BUTTON_HTML = """
<style>
  .row { display:flex; align-items:center; justify-content:center; height:100%; gap:10px; font-family:system-ui; }
  .row button { font-size:16px; padding:4px 10px; border-radius:8px; border:none; cursor:pointer; }
</style>
<div class="row">
  <button onclick="media.prev()">⏮</button>
  <button onclick="media.playPause()">⏯</button>
  <button onclick="media.next()">⏭</button>
</div>
"""
'''

SAMPLE_HTML_TIMER = """<!DOCTYPE html><meta charset="utf-8">
<title>HTML Timer</title>
<style>
  body { font-family: system-ui, Arial; margin: 16px; }
  .time { font-size: 32px; margin: 12px 0; }
  button { padding: 8px 12px; margin-right: 8px; }
</style>
<h1>⏱️ HTML Timer (Demo)</h1><div class="time" id="t">0 s</div>
<button onclick="start()">Start</button><button onclick="stop()">Stop</button><button onclick="reset()">Reset</button>
<script>
let sec=0,itv=null;function tick(){sec++;document.getElementById('t').textContent=sec+' s'}
function start(){if(!itv)itv=setInterval(tick,1000)}function stop(){if(itv){clearInterval(itv);itv=null}}
function reset(){sec=0;document.getElementById('t').textContent='0 s'}
</script>"""


def ensure_sample_plugins(script_root: str) -> None:
    os.makedirs(script_root, exist_ok=True)
    if any(not e.startswith("_") for e in os.listdir(script_root)):
        return
    samples = {
        "timer_plugin.py": SAMPLE_TIMER_PLUGIN,
        "musik_karte.py": SAMPLE_MUSIC_CARD,
        os.path.join("html_timer", "index.html"): SAMPLE_HTML_TIMER,
    }
    try:
        for rel_path, content in samples.items():
            full = os.path.join(script_root, rel_path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
    except OSError as exc:
        log.warning("Beispiel-Plugins konnten nicht angelegt werden: %s", exc)


# =============================================================================
# WebEngine-Bausteine (nur mit PyQtWebEngine)
# =============================================================================
def run_js(view, script: str) -> None:
    if WEBENGINE_AVAILABLE and view is not None and view.page() is not None:
        view.page().runJavaScript(script)


def make_web_view(parent: QWidget | None = None, *, transparent: bool = True):
    """QWebEngineView ohne Scrollbars, optional mit transparentem Hintergrund."""
    view = QWebEngineView(parent)
    if transparent:
        view.page().setBackgroundColor(QColor(0, 0, 0, 0))
    view.page().settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
    return view


if WEBENGINE_AVAILABLE:
    class InlineInterceptPage(QWebEnginePage):
        """Faengt Linkklicks in Inline-Cards ab und reicht sie an den Host weiter."""

        def __init__(self, on_open_link: Callable[[QUrl], None], parent=None):
            super().__init__(parent)
            self._on_open_link = on_open_link
            self._child_pages: list[QWebEnginePage] = []

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802 (Qt-API)
            if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
                self._on_open_link(url)
                return False
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        def createWindow(self, _window_type):  # noqa: N802 (Qt-API)
            # target="_blank": Hilfsseite anlegen, deren erste URL weiterleiten
            page = QWebEnginePage(self)
            self._child_pages.append(page)

            def on_url_changed(url: QUrl):
                page.urlChanged.disconnect(on_url_changed)
                self._on_open_link(url)
                self._child_pages.remove(page)
                QTimer.singleShot(0, page.deleteLater)

            page.urlChanged.connect(on_url_changed)
            return page

    class ExplorerBridge(QObject):
        """Backend des HTML-Explorers (QWebChannel-Objekt "explorer")."""

        def __init__(self, host: ExplorerMixin, parent=None):
            super().__init__(parent)
            self._host = host

        @pyqtSlot(result=str)
        def getState(self) -> str:  # noqa: N802 (JS-API)
            return json.dumps(self._host.collect_state())

        @pyqtSlot(str)
        def open(self, path: str) -> None:
            QTimer.singleShot(0, lambda: self._host.run_script(path))

        @pyqtSlot(str)
        def enterDir(self, path: str) -> None:  # noqa: N802 (JS-API)
            QTimer.singleShot(0, lambda: self._host.enter_directory(path))

        @pyqtSlot()
        def goBack(self) -> None:  # noqa: N802 (JS-API)
            QTimer.singleShot(0, self._host.go_back)

        @pyqtSlot(str, str, str, result=str)
        def callPlugin(self, path: str, method: str, args_json: str) -> str:  # noqa: N802 (JS-API)
            """Card-Aufruf pluginCall(method, args) -> handle_call(method, args) im Plugin."""
            return json.dumps(call_plugin(path, method, args_json), default=str)

        @pyqtSlot(str, str)
        def openPlugin(self, path: str, from_path: str) -> None:  # noqa: N802 (JS-API)
            """openPlugin('Name.py') aus einer Card - relativ zum Ordner der Card."""
            target = (path or "").strip() or from_path
            if target and not os.path.isabs(target):
                base = os.path.dirname(os.path.abspath(from_path)) if from_path else self._host.current_path
                target = os.path.join(base, target)
            if target and os.path.exists(target):
                QTimer.singleShot(0, lambda: self._host.run_script(os.path.abspath(target)))

        @pyqtSlot(str)
        def openLink(self, url: str) -> None:  # noqa: N802 (JS-API)
            QTimer.singleShot(0, lambda: self._host.open_link(QUrl(url)))

    class ExplorerView(QWebEngineView):
        """HTML-Explorer: rendert ui/explorer.html, Python liefert den Zustand als JSON."""

        def __init__(self, host: ExplorerMixin, parent=None):
            super().__init__(parent)
            self._host = host
            self.page().setBackgroundColor(Qt.transparent)
            settings = self.page().settings()
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

            self.channel = QWebChannel(self.page())
            self.bridge = ExplorerBridge(host, self)
            self.channel.registerObject("explorer", self.bridge)
            self.services = create_services(self)
            for name, service in self.services.items():
                self.channel.registerObject(name, service)
            self.page().setWebChannel(self.channel)

            ui_path = ensure_ui_file()
            if ui_path:
                self.load(QUrl.fromLocalFile(ui_path))
            else:
                self.setHtml(EXPLORER_DEFAULT_HTML, baseUrl=QUrl.fromLocalFile(os.path.abspath(".") + os.sep))

        def push_state(self) -> None:
            payload = json.dumps(json.dumps(self._host.collect_state()))
            run_js(self, f"window.renderState && window.renderState({payload});")
else:
    InlineInterceptPage = ExplorerBridge = ExplorerView = None  # pylint: disable=invalid-name


def call_plugin(path: str, method: str, args_json: str) -> dict:
    """Leitet einen Card-Aufruf an handle_call(method, args) des Plugins weiter."""
    path = os.path.abspath(path or "")
    if not (is_inside_script_folder(path) and path.lower().endswith(".py") and os.path.exists(path)):
        return {"ok": False, "error": "Pfad nicht erlaubt."}
    try:
        args = json.loads(args_json) if args_json else {}
    except ValueError:
        args = {}
    if not isinstance(args, dict):
        args = {}
    # noinspection PyBroadException
    try:
        handler = getattr(load_plugin_module(path), "handle_call", None)
        if not callable(handler):
            return {"ok": False, "error": "Plugin hat kein handle_call(method, args)."}
        return {"ok": True, "result": handler(method or "", args)}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Bewusst breit: Fehler im Plugin gehen als Antwort an die Card zurueck.
        log.exception("handle_call in %s fehlgeschlagen", path)
        return {"ok": False, "error": str(exc)}


# =============================================================================
# HTML-Card im Qt-Explorer (nur wenn HTML_EXPLORER aus ist)
# =============================================================================
class HtmlInlineButton(QWidget):
    """Kompakte HTML-Card in der Qt-Plugin-Liste (eigene QWebEngineView)."""

    BLOCKED_KEYS = frozenset({Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown, Qt.Key_Space})

    def __init__(self, path: str, meta: PluginMeta, compact: bool = False):
        super().__init__()
        self.setProperty("entry_type", "file_html_inline")
        self.src_path = os.path.abspath(path)
        self.meta = meta
        self.compact = compact
        self.view = None
        self.channel = None
        self.media = None

        height, pad_top, pad_bottom = card_metrics(meta, compact)
        self.setFixedHeight(height)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, pad_top, 8, pad_bottom)
        outer.setSpacing(0)

        if not WEBENGINE_AVAILABLE:
            fallback = QPushButton("Im Browser öffnen")
            fallback.clicked.connect(lambda: open_in_browser(self.src_path))
            outer.addWidget(fallback)
            return

        self.view = make_web_view(self)
        self.view.setPage(InlineInterceptPage(self._open_link, parent=self.view))
        page = self.view.page()
        page.setBackgroundColor(Qt.transparent)
        page.settings().setAttribute(QWebEngineSettings.ShowScrollBars, False)
        page.settings().setAttribute(QWebEngineSettings.FullScreenSupportEnabled, False)
        self.view.setAttribute(Qt.WA_TranslucentBackground, True)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.view.setFixedHeight(max(24, height - pad_top - pad_bottom))
        self.view.installEventFilter(self)
        outer.addWidget(self.view)

        if meta.media_bridge:
            self.channel = QWebChannel(page)
            self.media = MediaControlBridge(self)
            self.channel.registerObject("media", self.media)
            page.setWebChannel(self.channel)
        self._load_content()

    def _open_link(self, url: QUrl) -> None:
        host = self.parent()
        while host is not None and not hasattr(host, "open_link"):
            host = host.parent()
        if host is not None:
            host.open_link(url)
        else:
            webbrowser.open(url.toString())

    def _load_content(self) -> None:
        mode = "popup" if self.compact else "window"
        source = resolve_card_source(self.src_path, self.meta, mode)
        if source.file:
            url = QUrl.fromLocalFile(source.file)
            url.setQuery(f"mode={mode}")
            self.view.load(url)
            if self.meta.opacity is not None:  # Opacity per JS, da Datei fremdes HTML ist
                self.view.loadFinished.connect(self._apply_opacity)
        else:
            page_html = QT_CARD_WRAPPER_HTML.substitute(
                content=source.html, mode=json.dumps(mode), opacity_css=_opacity_css(self.meta.opacity))
            self.view.setHtml(page_html, baseUrl=QUrl.fromLocalFile(source.base_dir + os.sep))

    def _apply_opacity(self, _ok: bool = True) -> None:
        run_js(self.view, f"document.body && (document.body.style.opacity='{self.meta.opacity}');")

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt-API)
        """Scrollen und Navigationstasten in der Card unterdruecken."""
        if obj is self.view:
            if event.type() in (QEvent.Wheel, QEvent.Gesture, QEvent.NativeGesture):
                return True
            if event.type() == QEvent.KeyPress and (
                    event.modifiers() & Qt.ControlModifier or event.key() in self.BLOCKED_KEYS):
                return True
        return super().eventFilter(obj, event)


class HtmlPluginContainer(QWidget):
    """Geoeffnetes HTML-Plugin (Tab oder Popup-Seite)."""

    def __init__(self, html_path: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"HTML: {os.path.basename(html_path)}"))
        if WEBENGINE_AVAILABLE:
            view = make_web_view(self, transparent=False)
            view.load(QUrl.fromLocalFile(os.path.abspath(html_path)))
            layout.addWidget(view)
        else:
            layout.addWidget(QLabel("PyQtWebEngine nicht installiert."))
            button = QPushButton("Im Standardbrowser öffnen")
            button.clicked.connect(lambda: open_in_browser(html_path))
            layout.addWidget(button)


# =============================================================================
# Gemeinsame Explorer-Logik (Popup + Hauptfenster)
# =============================================================================
class ExplorerEntry(NamedTuple):
    name: str
    path: str
    meta: PluginMeta | None  # None = Ordner

    @property
    def sort_key(self) -> tuple:
        """Angepinnt > [html]-Dateien > .html > .py > Ordner, jeweils alphabetisch."""
        lower = self.name.lower()
        if self.meta is not None and self.meta.pin_rank is not None:
            return 0, self.meta.pin_rank, lower
        if lower.startswith("[html]"):
            return 1, 0, lower
        if lower.endswith(".html"):
            return 2, 0, lower
        if lower.endswith(".py"):
            return 3, 0, lower
        return 4, 0, lower


class ExplorerMixin:
    """Plugin-Liste: Navigation, Suche, Zustand fuer HTML- bzw. Qt-Explorer."""

    IS_POPUP = False

    # Werden in init_explorer() gesetzt (hier deklariert fuer Lesbarkeit/IDE).
    current_path: str = ""
    search_query: str = ""
    plugin_loader: Callable | None = None
    explorer_view = None             # ExplorerView (HTML-Explorer)
    button_layout: QVBoxLayout | None = None  # Qt-Explorer
    scroll_area: QScrollArea | None = None
    explorer_root: QWidget | None = None
    watcher: QFileSystemWatcher | None = None

    # --- Aufbau -------------------------------------------------------------
    def init_explorer(self) -> None:
        """Explorer (HTML oder Qt) erzeugen; danach liegt er in self.explorer_root."""
        root = os.path.abspath(SCRIPT_FOLDER)
        ensure_sample_plugins(root)
        self.current_path = root
        self.watcher = QFileSystemWatcher([root], self)
        self.watcher.directoryChanged.connect(self.refresh_explorer)

        if WEBENGINE_AVAILABLE and HTML_EXPLORER:
            self.explorer_view = ExplorerView(host=self)
            self.explorer_root = self.explorer_view
        else:
            container = QWidget()
            self.button_layout = QVBoxLayout(container)
            self.button_layout.setContentsMargins(0, 0, 0, 0)
            self.button_layout.setSpacing(0)
            self.button_layout.setAlignment(Qt.AlignTop)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setFrameShape(QScrollArea.NoFrame)
            self.scroll_area.setWidget(container)
            self.update_scrollbar_style()
            self.explorer_root = self.scroll_area

    def set_plugin_loader(self, loader: Callable) -> None:
        self.plugin_loader = loader

    @property
    def at_root(self) -> bool:
        return os.path.abspath(self.current_path) == os.path.abspath(SCRIPT_FOLDER)

    # --- Navigation ---------------------------------------------------------
    def refresh_explorer(self, *_args) -> None:
        if self.explorer_view is not None:
            self.explorer_view.push_state()
        elif self.button_layout is not None:
            self.build_qt_buttons()

    def enter_directory(self, path: str) -> None:
        self.search_query = ""
        self.current_path = path
        self.refresh_explorer()

    def go_back(self) -> None:
        self.search_query = ""
        parent = os.path.dirname(self.current_path)
        self.current_path = parent if is_inside_script_folder(parent) else os.path.abspath(SCRIPT_FOLDER)
        QTimer.singleShot(0, self.refresh_explorer)

    def run_script(self, path: str) -> None:
        if launch_external(path, PluginMeta.from_file(path)):
            return
        if self.plugin_loader is not None:
            self.plugin_loader(path, source_widget=self)
        elif path.lower().endswith(".py"):
            subprocess.Popen([sys.executable, path])  # pylint: disable=consider-using-with
        elif path.lower().endswith(".html"):
            open_in_browser(path)

    def open_link(self, url: QUrl) -> None:
        """Linkklick aus einer Card. Standard: Systembrowser."""
        webbrowser.open(url.toString())

    # --- Eintraege ----------------------------------------------------------
    def list_entries(self) -> list[ExplorerEntry]:
        """Sichtbare Ordner/Plugins im aktuellen Ordner, sortiert und gefiltert."""
        try:
            names = os.listdir(self.current_path)
        except OSError:
            names = []
        query = self.search_query.strip().lower()
        entries = []
        for name in names:
            if name.startswith("_") or (query and query not in name.lower()):
                continue
            path = os.path.join(self.current_path, name)
            if os.path.isdir(path):
                entries.append(ExplorerEntry(name, path, None))
            elif name.lower().endswith((".py", ".html")):
                meta = PluginMeta.from_file(path)
                if meta.allow_popup if self.IS_POPUP else meta.allow_window:
                    entries.append(ExplorerEntry(name, path, meta))
        return sorted(entries, key=lambda e: e.sort_key)

    # --- HTML-Explorer: Zustand als dict (geht als JSON an ui/explorer.html) --
    def collect_state(self) -> dict:
        items = []
        for entry in self.list_entries():
            if entry.meta is None:
                items.append({"type": "folder", "name": entry.name, "path": entry.path,
                              "height": FOLDER_BUTTON_HEIGHT})
            elif entry.meta.html_button:
                items.append(self._card_state(entry))
            else:
                icon = entry.meta.icon_path(entry.path)
                items.append({
                    "type": "file", "label": entry.meta.display_name(entry.name), "path": entry.path,
                    "height": entry.meta.button_height or DEFAULT_BUTTON_HEIGHT,
                    "opacity": entry.meta.opacity,
                    "icon": QUrl.fromLocalFile(icon).toString() if icon else None,
                })
        return {"theme": SETTINGS.effective_theme, "glass": SETTINGS.glass_mode,
                "compact": self.IS_POPUP, "isRoot": self.at_root, "entries": items}

    def _card_state(self, entry: ExplorerEntry) -> dict:
        mode = "popup" if self.IS_POPUP else "window"
        height, pad_top, pad_bottom = card_metrics(entry.meta, self.IS_POPUP)
        source = resolve_card_source(entry.path, entry.meta, mode)
        content = source.html if source.html is not None else read_text(source.file)
        base_href = QUrl.fromLocalFile(source.base_dir + os.sep).toString()
        return {
            "type": "card", "kind": "srcdoc", "path": entry.path, "height": height,
            "padTop": pad_top, "padBottom": pad_bottom,
            "content": wrap_card_html(f'<base href="{base_href}">' + content, mode,
                                      entry.meta.opacity, entry.path),
        }

    # --- Qt-Explorer (Fallback ohne WebEngine) --------------------------------
    def build_qt_buttons(self) -> None:
        layout = self.button_layout
        while layout.count():
            widget = layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not self.at_root:
            back = QPushButton("← Zurück")
            back.setObjectName("back_button")
            back.setMinimumHeight(BACK_BUTTON_HEIGHT)
            back.clicked.connect(self.go_back)
            layout.addWidget(back)

        for entry in self.list_entries():
            layout.addWidget(self._make_qt_entry(entry))
        self.update_button_styles()

    def _make_qt_entry(self, entry: ExplorerEntry) -> QWidget:
        if entry.meta is None:
            button = QPushButton(entry.name)
            button.setProperty("entry_type", "folder")
            button.setMinimumHeight(FOLDER_BUTTON_HEIGHT)
            button.clicked.connect(lambda _=False, p=entry.path: self.enter_directory(p))
        elif entry.meta.html_button:
            return HtmlInlineButton(entry.path, entry.meta, compact=self.IS_POPUP)
        else:
            button = QPushButton(entry.meta.display_name(entry.name))
            button.setProperty("entry_type", "file")
            button.setMinimumHeight(entry.meta.button_height or DEFAULT_BUTTON_HEIGHT)
            button.clicked.connect(lambda _=False, p=entry.path: self.run_script(p))
            icon = entry.meta.icon_path(entry.path)
            if icon:
                button.setIcon(QIcon(icon))
                button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            if entry.meta.opacity is not None:
                effect = QGraphicsOpacityEffect(button)
                effect.setOpacity(entry.meta.opacity)
                button.setGraphicsEffect(effect)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return button

    def update_button_styles(self) -> None:
        if self.button_layout is None:
            return
        if SETTINGS.glass_mode:
            styles = {
                "back": button_css(GLASS_BUTTON, GLASS_BUTTON_HOVER, "font-weight: 600; padding: 8px 12px;"),
                "folder": button_css(GLASS_BUTTON, GLASS_BUTTON_HOVER, "font-weight: 600;"),
                "file": button_css(GLASS_BUTTON, GLASS_BUTTON_HOVER),
                "card": (f"QWidget {{ {GLASS_PANEL} padding: 8px; }}"
                         " QWidget:hover { background: rgba(255,255,255,0.18); }"),
            }
        else:
            c = colors()
            styles = {
                "back": button_css(f"background-color: {c['back']}; color: {c['text']};",
                                   f"background-color: {c['back_hover']};", "font-weight: bold;"),
                "folder": button_css(f"background-color: {c['folder']}; color: {c['text']};",
                                     f"background-color: {c['folder_hover']};"),
                "file": button_css(f"background-color: {c['file']}; color: {c['text']};",
                                   f"background-color: {c['file_hover']};"),
                "card": (f"QWidget {{ background-color: {c['card']}; color: {c['text']};"
                         f" border-radius: 8px; padding: 8px; }}"
                         f" QWidget:hover {{ background-color: {c['card_hover']}; }}"),
            }
        for i in range(self.button_layout.count()):
            widget = self.button_layout.itemAt(i).widget()
            if widget is None:
                continue
            if widget.objectName() == "back_button":
                widget.setStyleSheet(styles["back"])
            else:
                kind = {"folder": "folder", "file": "file", "file_html_inline": "card"}.get(
                    widget.property("entry_type"))
                if kind:
                    widget.setStyleSheet(styles[kind])

    def update_scrollbar_style(self) -> None:
        if self.scroll_area is not None:  # HTML-Explorer stylt seine Scrollbar selbst
            self.scroll_area.setStyleSheet(scrollbar_css(compact=self.IS_POPUP))


# =============================================================================
# Bruecke HTML-Toolbar <-> Qt
# =============================================================================
class ThemeBridge(QObject):
    """QWebChannel-Objekt "bridge" der Toolbars."""

    def __init__(self, main_window: MainAppWindow | None = None, popup: PopupWindow | None = None):
        super().__init__()
        self.main_window = main_window
        self.popup = popup

    @pyqtSlot()
    def toggleTheme(self) -> None:  # noqa: N802 (JS-API)
        if self.main_window is not None:
            self.main_window.toggle_theme()

    @pyqtSlot()
    def goBackToExplorer(self) -> None:  # noqa: N802 (JS-API)
        if self.popup is not None and self.popup.isVisible():
            self.popup.show_explorer()
        elif self.main_window is not None:
            self.main_window.go_back_to_explorer()


# =============================================================================
# Einstellungsseite (im Hauptfenster, ueber den ⚙️-Button)
# =============================================================================
class SettingsPage(QWidget):
    def __init__(self, main_window: MainAppWindow):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Einstellungen")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.group_box = QFrame()
        box_layout = QVBoxLayout(self.group_box)
        heading = QLabel("Design-Modus:")
        heading.setStyleSheet("font-size: 16px; font-weight: 600; background: transparent;")
        box_layout.addWidget(heading)

        self.rb_opaque = QRadioButton("Klassisch (Opaque)\n[Volldeckend, Light & Dark Mode verfügbar]")
        self.rb_glass = QRadioButton("Transparent (Glas)\n[Durchscheinend, nur Dark Mode]")
        self.mode_group = QButtonGroup(self)
        for radio in (self.rb_opaque, self.rb_glass):
            radio.setStyleSheet("QRadioButton { font-size: 14px; padding: 5px; background: transparent; }"
                                " QRadioButton::indicator { width: 16px; height: 16px; }")
            self.mode_group.addButton(radio)
            box_layout.addWidget(radio)
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        layout.addWidget(self.group_box)
        layout.addStretch()

        self.btn_back = QPushButton("Speichern & Zurück")
        self.btn_back.setFixedHeight(40)
        self.btn_back.clicked.connect(self.save_and_back)
        layout.addWidget(self.btn_back)

        self.update_style()

    def update_style(self) -> None:
        (self.rb_glass if SETTINGS.glass_mode else self.rb_opaque).setChecked(True)
        if SETTINGS.glass_mode:
            base, hover, box_bg = GLASS_BUTTON, GLASS_BUTTON_HOVER, "rgba(255,255,255,0.05)"
        else:
            c = colors()
            base = (f"background: {c['btn']}; color: {c['btn_fg']};"
                    f" border: 1px solid {c['btn_border']}; border-radius: 6px;")
            hover, box_bg = f"background: {c['btn_hover']};", c["box"]
        self.btn_back.setStyleSheet(button_css(base, hover, "font-weight: bold;"))
        self.group_box.setStyleSheet(f"QFrame {{ background: {box_bg}; border-radius: 8px; padding: 10px; }}")
        self.setStyleSheet(f"color: {'#FFFFFF' if SETTINGS.dark else '#000000'};")

    def on_mode_changed(self, _button) -> None:
        SETTINGS.glass_mode = self.rb_glass.isChecked()
        if SETTINGS.glass_mode:
            SETTINGS.theme = "dark"  # Glas gibt es nur in Dark
        SETTINGS.save()
        self.main_window.refresh_all_styles()

    def save_and_back(self) -> None:
        SETTINGS.save()
        self.main_window.go_back_to_explorer()


# =============================================================================
# Popup (Rechtsklick auf das Tray-Icon)
# =============================================================================
class PopupWindow(ExplorerMixin, QWidget):
    IS_POPUP = True
    SLIDE_IN_OFFSET = 50   # px unterhalb der Endposition
    ANIMATION_MS = 500

    def __init__(self):
        super().__init__()
        self.setObjectName("popupRoot")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowOpacity(POPUP_OPACITY)
        # Fenster selbst durchsichtig; den Hintergrund malt apply_root_style()
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.bridge = ThemeBridge(popup=self)
        self.channel = None
        if WEBENGINE_AVAILABLE:
            self.toolbar = make_web_view(self)
            self.toolbar.setFixedHeight(40)
            self.toolbar.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.channel = QWebChannel(self.toolbar.page())
            self.channel.registerObject("bridge", self.bridge)
            self.toolbar.page().setWebChannel(self.channel)
        else:
            self.toolbar = QWidget(self)
        self.toolbar.setVisible(False)
        self.build_toolbar()

        self.init_explorer()
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("QStackedWidget { background: transparent; }")
        self.pages.addWidget(self.explorer_root)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.pages)

        self.apply_root_style()
        self.width_size, self.height_size = self._target_size()
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(self.ANIMATION_MS)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    @staticmethod
    def _target_size() -> tuple[int, int]:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geo = screen.geometry()
        return int(geo.width() * 0.15), int(geo.height() * 0.5)

    def apply_root_style(self) -> None:
        self.setStyleSheet(f"#popupRoot {{ {panel_css()} }}")

    def refresh_styles(self) -> None:
        self.apply_root_style()
        self.update_scrollbar_style()
        self.build_toolbar()
        self.refresh_explorer()

    def build_toolbar(self) -> None:
        if WEBENGINE_AVAILABLE:
            self.toolbar.setHtml(POPUP_TOOLBAR_HTML.substitute(
                button_css=TOOLBAR_BUTTON_CSS, mode=SETTINGS.effective_theme))

    def show_plugin_widget(self, widget: QWidget, title: str = "") -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        header = QLabel(f"🧩 Plugin: {title}")
        header.setStyleSheet("font-weight:600;font-size:15px;margin-bottom:6px;")
        layout.addWidget(header)
        layout.addWidget(widget)
        self.pages.addWidget(container)
        self.pages.setCurrentWidget(container)
        self.toolbar.setVisible(WEBENGINE_AVAILABLE)

    def show_explorer(self) -> None:
        self._close_active_page()
        self.pages.setCurrentWidget(self.explorer_root)
        self.toolbar.setVisible(False)

    def _close_active_page(self) -> None:
        page = self.pages.currentWidget()
        if page is None or page is self.explorer_root:
            return
        stop_web_views(page)
        self.pages.removeWidget(page)
        page.setParent(None)
        QTimer.singleShot(0, page.deleteLater)

    def show_popup(self) -> None:
        self.refresh_styles()
        self.width_size, self.height_size = self._target_size()
        self.setFixedSize(self.width_size, self.height_size)
        cursor = QCursor.pos()
        end = QRect(cursor.x() - self.width_size, cursor.y() - self.height_size,
                    self.width_size, self.height_size)
        start = QRect(cursor.x(), cursor.y() + self.SLIDE_IN_OFFSET, self.width_size, self.height_size)
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.start()
        self.show()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt-API)
        event.ignore()
        self.hide()


def stop_web_views(widget: QWidget) -> None:
    """Laufende Web-Inhalte (Audio, Timer ...) eines Plugins beenden."""
    if WEBENGINE_AVAILABLE:
        for view in widget.findChildren(QWebEngineView):
            view.load(QUrl("about:blank"))


# =============================================================================
# Hauptfenster (Linksklick auf das Tray-Icon) - Plugins als Tabs
# =============================================================================
class MainAppWindow(ExplorerMixin, QMainWindow):
    def __init__(self, app: QApplication, popup: PopupWindow | None = None):
        super().__init__()
        self.app = app
        self.popup = popup
        self.show_explorer_button = False

        self.setWindowTitle(APP_TITLE)
        if os.path.exists(PROGRAM_ICON):
            self.setWindowIcon(QIcon(PROGRAM_ICON))
        self.width_size, self.height_size = self._target_size()
        self.setMinimumSize(self.width_size, self.height_size)
        if MAIN_WINDOW_OPACITY < 1.0:
            self.setWindowOpacity(MAIN_WINDOW_OPACITY)
        # Glas: durchsichtiges Fenster, den Hintergrund malt self.central
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # --- Toolbar-Zeile: HTML-Toolbar | Suche | ⚙️ | Beenden ---
        control_height = max(28, int(self.height_size * 0.08))
        self.bridge = ThemeBridge(main_window=self, popup=self.popup)
        self.channel = None
        self.toolbar = self._create_web_toolbar()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search plugins...")
        self.search_input.setFixedSize(220, control_height)
        self.search_input.textChanged.connect(self.on_search_changed)
        self.settings_button = QPushButton("⚙️")
        self.settings_button.setFixedSize(40, control_height)
        self.settings_button.clicked.connect(self.open_settings)
        self.exit_button = QPushButton("Beenden")
        self.exit_button.setFixedHeight(control_height)
        self.exit_button.clicked.connect(self.app.quit)

        self.central = QWidget()
        self.central.setObjectName("centralRoot")
        central_layout = QVBoxLayout(self.central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self._toolbar_row())

        self.init_explorer()
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabBar().setDrawBase(False)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.settings_page = SettingsPage(self)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("QStackedWidget { background: transparent; }")
        for page in (self.explorer_root, self.tab_widget, self.settings_page):
            self.pages.addWidget(page)
        central_layout.addWidget(self.pages)
        self.setCentralWidget(self.central)

        self.set_plugin_loader(self.load_plugin_from_path)
        self.refresh_all_styles()

    @staticmethod
    def _target_size() -> tuple[int, int]:
        geo = QGuiApplication.primaryScreen().geometry()
        return int(geo.width() * 0.4), int(geo.height() * 0.4)

    def _create_web_toolbar(self) -> QWidget:
        if not WEBENGINE_AVAILABLE:
            return QWidget()
        toolbar = make_web_view()
        toolbar.setFixedHeight(44)
        toolbar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        toolbar.setAttribute(Qt.WA_TranslucentBackground, True)
        self.channel = QWebChannel(toolbar.page())
        self.channel.registerObject("bridge", self.bridge)
        toolbar.page().setWebChannel(self.channel)
        return toolbar

    def _toolbar_row(self) -> QWidget:
        row = QHBoxLayout()
        row.addWidget(self.toolbar)
        row.addStretch()
        for widget in (self.search_input, self.settings_button, self.exit_button):
            row.addWidget(widget)
        container = QWidget()
        container.setLayout(row)
        return container

    # --- Toolbar & Styles ---------------------------------------------------
    def build_toolbar(self) -> None:
        if WEBENGINE_AVAILABLE:
            self.toolbar.setHtml(MAIN_TOOLBAR_HTML.substitute(
                button_css=TOOLBAR_BUTTON_CSS,
                mode=SETTINGS.effective_theme,
                explorer_display="inline-block" if self.show_explorer_button else "none",
                switch_display="none" if SETTINGS.glass_mode else "block",
                checked="" if SETTINGS.dark else "checked",
            ))

    def set_explorer_button_visible(self, visible: bool) -> None:
        if visible != self.show_explorer_button:
            self.show_explorer_button = visible
            self.build_toolbar()

    def refresh_all_styles(self, rebuild_toolbar: bool = True) -> None:
        """Alles neu stylen (nach Wechsel Glas/Opaque oder Theme)."""
        apply_app_theme(self.app)
        self.central.setStyleSheet(f"#centralRoot {{ {panel_css()} }}")
        self._style_search_input()
        self._style_settings_button()
        self._style_exit_button()
        self._style_tabs()
        self.update_scrollbar_style()
        self.settings_page.update_style()
        self.refresh_explorer()
        if rebuild_toolbar:
            self.build_toolbar()
        if self.isVisible():  # sonst erledigt das showEvent
            apply_titlebar_theme(self)
        if self.popup is not None:
            self.popup.refresh_styles()

    def _style_search_input(self) -> None:
        if SETTINGS.glass_mode:
            bg, fg, border = "rgba(255,255,255,0.08)", "#FFFFFF", "rgba(255,255,255,0.18)"
        else:
            c = colors()
            bg, fg, border = c["input_bg"], c["input_fg"], c["input_border"]
        self.search_input.setStyleSheet(f"""
            QLineEdit {{ background: {bg}; color: {fg}; padding: 8px 10px; border-radius: 12px;
                         border: 1.5px solid {border}; outline: none; }}
            QLineEdit:hover {{ border: 2px solid #555555; }}
            QLineEdit:focus {{ border: 2px solid grey; }}
        """)

    def _style_settings_button(self) -> None:
        if SETTINGS.glass_mode:
            base = ("background: rgba(255,255,255,0.1); color: #FFFFFF;"
                    " border: 1px solid rgba(255,255,255,0.2);")
            hover = "background: rgba(255,255,255,0.2);"
        else:
            c = colors()
            base = (f"background: {c['tool_btn']}; color: {c['tool_btn_fg']};"
                    f" border: 1px solid {c['tool_btn_border']};")
            hover = f"background: {c['tool_btn_hover']};"
        self.settings_button.setStyleSheet(button_css(base, hover, "border-radius: 10px; font-size: 16px;"))

    def _style_exit_button(self) -> None:
        shape = "font-weight: bold; border-radius: 10px; padding: 6px 12px;"
        if SETTINGS.glass_mode:
            base = "background: rgba(255,90,90,0.18); color: #FFECEC; border: 1px solid rgba(255,120,120,0.35);"
            hover = "background: rgba(255,90,90,0.28);"
        else:
            base = f"background-color: {colors()['exit']}; color: white; border: none;"
            hover = f"background-color: {colors()['exit_hover']};"
        self.exit_button.setStyleSheet(button_css(base, hover, shape))

    def _style_tabs(self) -> None:
        c = colors()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{ border-top: 2px solid {c['tab_sel']}; position: absolute; top: -1px;
                                background: transparent; }}
            QTabBar::tab {{ background: {c['tab']}; color: {c['tab_fg']}; padding: 8px 20px; margin-right: 4px;
                            border-top-left-radius: 8px; border-top-right-radius: 8px; border: none;
                            min-width: 60px; }}
            QTabBar::tab:selected {{ background: {c['tab_sel']}; color: {c['tab_sel_fg']}; font-weight: bold; }}
            QTabBar::tab:hover:!selected {{ background: {c['tab_hover']}; }}
        """)

    # --- Aktionen -----------------------------------------------------------
    def toggle_theme(self) -> None:
        if SETTINGS.glass_mode:
            return  # kein Light-Mode im Glas-Modus
        SETTINGS.theme = "light" if SETTINGS.dark else "dark"
        SETTINGS.save()
        # Toolbar nicht neu laden, sonst springt die Switch-Animation zurueck
        self.refresh_all_styles(rebuild_toolbar=False)

    def open_settings(self) -> None:
        self.settings_page.update_style()
        self.pages.setCurrentWidget(self.settings_page)
        self.set_explorer_button_visible(True)

    def go_back_to_explorer(self) -> None:
        # Tabs bleiben offen - Plugins laufen im Hintergrund weiter.
        self.pages.setCurrentWidget(self.explorer_root)
        self.set_explorer_button_visible(False)

    def on_search_changed(self, text: str) -> None:
        self.search_query = text.strip().lower()
        self.refresh_explorer()

    def close_tab(self, index: int) -> None:
        widget = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        stop_web_views(widget)
        widget.deleteLater()
        if self.tab_widget.count() == 0:
            self.go_back_to_explorer()

    def _show_tab(self, widget: QWidget) -> None:
        self.tab_widget.setCurrentWidget(widget)
        self.pages.setCurrentWidget(self.tab_widget)
        self.set_explorer_button_visible(True)

    def open_link(self, url: QUrl) -> None:
        """Linkklick aus einer Card: lokale Plugins laden, Webseiten als Tab."""
        if url.isLocalFile():
            self.load_plugin_from_path(url.toLocalFile(), source_widget=self)
            return
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        if WEBENGINE_AVAILABLE:
            view = make_web_view(page, transparent=False)
            view.load(url)
            layout.addWidget(view, 1)
        else:
            layout.addWidget(QLabel("PyQtWebEngine nicht verfügbar."))
        self.tab_widget.addTab(page, "Link")
        self._show_tab(page)

    # --- Plugins laden ------------------------------------------------------
    def load_plugin_from_path(self, path: str, source_widget: QWidget | None = None) -> None:
        meta = PluginMeta.from_file(path)
        if launch_external(path, meta):
            return
        in_popup = isinstance(source_widget, PopupWindow)
        if not in_popup and self._focus_existing_tab(path):
            return
        widget = self._create_plugin_widget(path, "Popup" if in_popup else "Window", source_widget)
        if widget is None:
            return
        if in_popup:
            source_widget.show_plugin_widget(widget, meta.tab_title(path))
        else:
            self._add_plugin_tab(widget, path, meta)

    def _focus_existing_tab(self, path: str) -> bool:
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i).property("plugin_path") == path:
                self._show_tab(self.tab_widget.widget(i))
                return True
        return False

    def _create_plugin_widget(self, path: str, mode: str, parent: QWidget | None) -> QWidget | None:
        lower = path.lower()
        if lower.endswith(".html"):
            return HtmlPluginContainer(path)
        if not lower.endswith(".py"):
            subprocess.Popen([sys.executable, path])  # pylint: disable=consider-using-with
            return None
        name = os.path.basename(path)
        # noinspection PyBroadException
        try:
            widget_class = getattr(load_plugin_module(path, cached=False), "PluginWidget", None)
            if not isinstance(widget_class, type):
                QMessageBox.information(parent or self, "Plugin", f"{name} hat keine Klasse PluginWidget.")
                return None
            try:
                return widget_class(mode=mode)
            except TypeError:  # PluginWidget ohne mode-Parameter
                return widget_class()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # Bewusst breit: Plugin-Code kann jeden Fehler werfen.
            log.exception("Plugin %s konnte nicht geladen werden", name)
            QMessageBox.critical(parent or self, "Fehler beim Laden", f"{name}:\n{exc}")
            return None

    def _add_plugin_tab(self, widget: QWidget, path: str, meta: PluginMeta) -> None:
        container = QWidget()
        container.setProperty("plugin_path", path)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(widget)
        title = meta.tab_title(path)
        icon = meta.icon_path(path)
        if icon:
            self.tab_widget.addTab(container, QIcon(icon), title)
        else:
            if meta.icon:
                title = f"{meta.icon} {title}"
            self.tab_widget.addTab(container, title)
        self._show_tab(container)

    def showEvent(self, event) -> None:  # noqa: N802 (Qt-API)
        super().showEvent(event)
        apply_titlebar_theme(self)  # native Titelleiste ans Theme anpassen


# =============================================================================
# Tray-Applikation
# =============================================================================
class TrayApp(QApplication):
    def __init__(self, argv: list[str]):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)
        SETTINGS.load()
        apply_app_theme(self)

        self.popup = PopupWindow()
        self.main_window = MainAppWindow(self, popup=self.popup)
        self.popup.set_plugin_loader(self.main_window.load_plugin_from_path)

        self.tray = QSystemTrayIcon(self)
        if os.path.exists(TRAY_ICON):
            self.tray.setIcon(QIcon(TRAY_ICON))
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.setVisible(True)
        self.aboutToQuit.connect(self.teardown)

    def on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Context:
            self.popup.show_popup()
        elif reason == QSystemTrayIcon.Trigger:
            window = self.main_window
            if window.isMinimized() or not window.isVisible():
                window.showNormal()
            window.activateWindow()
            window.raise_()

    def teardown(self) -> None:
        """Web-Views vor dem Beenden freigeben (vermeidet WebEngine-Warnungen)."""
        self.tray.hide()
        for window in (self.popup, self.main_window):
            stop_web_views(window)
            window.toolbar.deleteLater()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    if sys.platform == "win32":  # eigenes Taskleisten-Icon statt python.exe
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    app = TrayApp(sys.argv)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())