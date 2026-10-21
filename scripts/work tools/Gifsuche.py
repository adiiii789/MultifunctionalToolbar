# --- Plugin-Parameter (neues System) ---
NAME = "GIF-Suche"
DESCRIPTION = ("Sucht animierte GIFs über KLIPY und zeigt sie als bewegte Vorschau; ein Klick kopiert das GIF "
               "(zum Einfügen in Chats, Mails, Dokumente).")
ICON = "🎞️"
# ----------------------------------------

# Werkzeug für den KI-Assistenten (siehe plugin_tools.py im Toolbar-Ordner). "window": Die GIFs
# stehen im Fenster (auf dem Board des Assistenten) - das Modell bekommt nur die Anzahl.
ASSISTANT_TOOLS = {
    "gif_search": {
        "description": "Searches animated GIFs (KLIPY) and shows them to the user as moving previews; the user can "
                       "click one to copy the GIF to the clipboard. You only get the number of results.",
        "parameters": {
            "query": {"type": "string", "description": "What the GIF should show, e.g. 'happy dance' or 'thank you'"},
        },
        "required": ["query"],
        "window": True,
    },
}

# GIF-Suche mit KLIPY (https://docs.klipy.com) - braucht einen eigenen, kostenlosen API-Schlüssel
# (https://partner.klipy.com, "API Keys"; im Testmodus 100 Anfragen pro Stunde). Er wird im Fenster
# eingegeben und lokal in CONFIG_FILE gespeichert (steht in .gitignore - nicht weitergeben).
# Vorgabe von KLIPY: Platzhalter im Suchfeld "Search KLIPY".
# Sicherheit wie in der Bildersuche (_web_images.py): nur öffentliche Adressen, nur GIF/WebP/JPEG/PNG,
# Größenlimits; das Modell bekommt nur die Anzahl. Kopieren: die GIF-Datei (bleibt animiert) plus das
# erste Bild - die Datei liegt in TEMP_DIR und wird nach einem Tag aufgeräumt.
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import Future, ThreadPoolExecutor

from PyQt5.QtCore import QMimeData, QObject, QSize, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QIcon, QMovie, QPixmap
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
                             QListWidgetItem, QMainWindow, QPushButton, QVBoxLayout, QWidget)


def _load_helper():
    """_web_images.py aus diesem Ordner (gemeinsam mit Bildersuche.py; "_" = kein Plugin)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_web_images.py")
    spec = importlib.util.spec_from_file_location("toolbar_web_images", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


web = _load_helper()

API_URL = "https://api.klipy.com/api/v1/{key}/gifs/search"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gifsuche_config.json")
TEMP_DIR = os.path.join(tempfile.gettempdir(), "Toolbar-GIFs")
PER_PAGE = 36                    # 8..50 laut KLIPY
CONTENT_FILTER = "medium"        # "off" | "low" | "medium" | "high"
LOCALE = "de"
PREVIEW_MAX_BYTES = 3 * 1024 * 1024
GIF_MAX_BYTES = 15 * 1024 * 1024
THUMB_SIZE = QSize(176, 132)
PREVIEW_SIZES = ("sm", "xs", "md")     # bewegte Vorschau
COPY_SIZES = ("md", "hd", "sm")        # zum Kopieren (md: gute Größe für Chats)


# --- Einstellungen (API-Schlüssel, anonyme Kennung für KLIPY) --------------------------
def load_config() -> dict:
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def customer_id(config: dict) -> str:
    """KLIPY möchte eine gleichbleibende Nutzerkennung - eine zufällige, nichts Persönliches."""
    if not config.get("customer_id"):
        config["customer_id"] = uuid.uuid4().hex
        save_config(config)
    return config["customer_id"]


# --- Suche -------------------------------------------------------------------------------
class KlipyError(Exception):
    """Fehler von KLIPY (Schlüssel ungültig, Limit erreicht ...) - Text fürs Fenster."""


def search_gifs(query: str, key: str, customer: str) -> list[dict]:
    params = urllib.parse.urlencode({"q": query, "page": 1, "per_page": PER_PAGE, "customer_id": customer,
                                     "locale": LOCALE, "content_filter": CONTENT_FILTER,
                                     "format_filter": "gif,jpg"})
    url = API_URL.format(key=urllib.parse.quote(key, safe="")) + "?" + params
    request = urllib.request.Request(url, headers={"User-Agent": web.USER_AGENT, "Accept": "application/json"})
    try:
        with web.OPENER.open(request, timeout=web.TIMEOUT_S) as response:
            body = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as error:       # Text ohne URL - die enthält den Schlüssel
        try:
            body = json.loads(error.read(65536).decode("utf-8"))
        except ValueError:
            raise KlipyError(f"KLIPY antwortet mit HTTP {error.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise KlipyError(f"KLIPY nicht erreichbar: {getattr(error, 'reason', error)}") from None
    if not body.get("result"):
        messages = (body.get("errors") or {}).get("message") or ["unbekannter Fehler"]
        raise KlipyError("KLIPY: " + " ".join(str(m) for m in messages))
    gifs = []
    for item in ((body.get("data") or {}).get("data") or []):
        files = item.get("file") or {}

        def pick(sizes, fmt):
            for size in sizes:
                entry = (files.get(size) or {}).get(fmt) or {}
                if entry.get("url"):
                    return entry
            return None
        preview, copy = pick(PREVIEW_SIZES, "gif"), pick(COPY_SIZES, "gif")
        if preview and copy:
            gifs.append({"id": str(item.get("slug") or item.get("id") or uuid.uuid4().hex),
                         "title": str(item.get("title") or ""), "preview": preview["url"],
                         "still": (pick(PREVIEW_SIZES, "jpg") or {}).get("url"), "gif": copy["url"],
                         "width": copy.get("width"), "height": copy.get("height")})
    return gifs


def _clean_temp() -> None:
    """Kopierte GIFs, die älter als ein Tag sind, aus TEMP_DIR löschen."""
    try:
        for entry in os.scandir(TEMP_DIR):
            if entry.is_file() and time.time() - entry.stat().st_mtime > 86400:
                os.remove(entry.path)
    except OSError:
        pass


class _Bridge(QObject):
    """Ergebnisse aus den Hintergrund-Threads in den Qt-Hauptthread."""
    results = pyqtSignal(int, object)          # Suchlauf, Liste oder Fehlertext
    preview = pyqtSignal(int, int, bytes)      # Suchlauf, Index, GIF-Daten
    copied = pyqtSignal(int, bytes, str)       # Index, GIF-Daten (leer = fehlgeschlagen), Hinweis


class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        super().__init__()
        self.setWindowTitle("🎞️ GIF-Suche")
        self.resize(900, 600)
        root = QWidget(objectName="root")
        root.setAttribute(Qt.WA_StyledBackground, True)
        root.setStyleSheet(web.STYLES[web.detect_theme()])
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self.input = QLineEdit(placeholderText="Search KLIPY")        # Vorgabe von KLIPY
        self.input.returnPressed.connect(self.start_search)
        button = QPushButton("Suchen")
        button.clicked.connect(self.start_search)
        key_button = QPushButton("🔑")
        key_button.setToolTip("KLIPY-API-Schlüssel eingeben/ändern")
        key_button.clicked.connect(lambda: self.key_row.setVisible(not self.key_row.isVisible()))
        row.addWidget(self.input, 1)
        row.addWidget(button)
        row.addWidget(key_button)
        layout.addLayout(row)

        # API-Schlüssel (nur sichtbar, solange keiner gespeichert ist - oder über 🔑)
        self.key_row = QWidget()
        key_layout = QHBoxLayout(self.key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self.key_input = QLineEdit(placeholderText="KLIPY-API-Schlüssel (kostenlos: partner.klipy.com → API Keys)")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.returnPressed.connect(self._save_key)
        save = QPushButton("Speichern")
        save.clicked.connect(self._save_key)
        key_layout.addWidget(self.key_input, 1)
        key_layout.addWidget(save)
        layout.addWidget(self.key_row)

        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.grid = QListWidget()
        self.grid.setViewMode(QListView.IconMode)
        self.grid.setIconSize(THUMB_SIZE)
        self.grid.setGridSize(QSize(THUMB_SIZE.width() + 16, THUMB_SIZE.height() + 34))
        self.grid.setResizeMode(QListView.Adjust)
        self.grid.setMovement(QListView.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setWordWrap(False)
        self.grid.setMouseTracking(True)
        self.grid.itemClicked.connect(self._copy)
        layout.addWidget(self.grid, 1)

        footer = QLabel("Klick auf ein GIF: kopieren (bleibt animiert beim Einfügen in Chats). · Powered by KLIPY")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        self._config = load_config()
        self._gifs = []
        self._movies = {}                 # Index -> (QMovie, QBuffer) der bewegten Vorschau
        self._run = 0
        self._pending = {}                # Suchlauf -> Future (Aufruf des Assistenten)
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="gifsuche")
        self._placeholder = self._make_placeholder()
        self._bridge = _Bridge(self)
        self._bridge.results.connect(self._show_results)
        self._bridge.preview.connect(self._show_preview)
        self._bridge.copied.connect(self._finish_copy)
        self._update_key_state()
        threading.Thread(target=_clean_temp, daemon=True).start()

    def _make_placeholder(self):
        pixmap = QPixmap(THUMB_SIZE)
        pixmap.fill(Qt.transparent)
        return QIcon(pixmap)

    def _emit(self, signal, *args):
        try:
            signal.emit(*args)
        except RuntimeError:              # Fenster inzwischen geschlossen
            pass

    # --- API-Schlüssel -------------------------------------------------------------------
    def _update_key_state(self):
        has_key = bool(self._config.get("api_key"))
        self.key_row.setVisible(not has_key)
        self.status.setText("GIFs von KLIPY - Suchbegriff eingeben." if has_key else
                            "Für die GIF-Suche brauchst du einen kostenlosen KLIPY-API-Schlüssel: partner.klipy.com "
                            "→ API Keys → Plattform anlegen, Schlüssel hier einfügen.")

    def _save_key(self):
        key = self.key_input.text().strip()
        if not key:
            return
        self._config["api_key"] = key
        save_config(self._config)
        self.key_input.clear()
        self._update_key_state()

    # --- Suche ------------------------------------------------------------------------
    def start_search(self, query=None) -> int:
        query = (self.input.text() if query is None or isinstance(query, bool) else str(query)).strip()
        self.input.setText(query)
        key = self._config.get("api_key")
        if not key:
            self._update_key_state()
            return 0
        if not query:
            self.status.setText("Bitte einen Suchbegriff eingeben.")
            return 0
        self._run += 1
        run, customer = self._run, customer_id(self._config)
        self.status.setText(f"Suche GIFs zu „{query}“ …")

        def work():
            try:
                result = search_gifs(query, key, customer)
            except KlipyError as error:
                result = str(error)
            except Exception as error:  # noqa: BLE001  # unerwartet - ins Fenster statt Absturz
                result = f"Suche fehlgeschlagen: {error}"
            self._emit(self._bridge.results, run, result)

        threading.Thread(target=work, name="gifsuche", daemon=True).start()
        return run

    def _stop_movies(self):
        for movie, _buffer in self._movies.values():
            movie.stop()
        self._movies.clear()

    def _show_results(self, run, result):
        future = self._pending.pop(run, None)
        if run != self._run:
            if future is not None:
                future.set_result({"note": "Superseded by a newer search."})
            return
        self._stop_movies()
        self.grid.clear()
        if isinstance(result, str):
            self._gifs = []
            self.status.setText(result)
            if future is not None:
                future.set_exception(RuntimeError(result))
            return
        self._gifs = result
        for index, gif in enumerate(result):
            title = gif["title"] or "GIF"
            item = QListWidgetItem(self._placeholder, title if len(title) <= 28 else title[:27] + "…")
            item.setToolTip(gif["title"])
            item.setData(Qt.UserRole, index)
            self.grid.addItem(item)
            self._pool.submit(self._load_preview, run, index, gif["preview"])
        self.status.setText(f"{len(result)} GIFs zu „{self.input.text()}“ - Klick kopiert ein GIF."
                            if result else f"Keine GIFs zu „{self.input.text()}“ gefunden.")
        if future is not None:
            future.set_result({"query": self.input.text(), "gifs": len(result),
                               "shown_to_user": "The GIFs are shown in the GIF search window / on the board; the "
                                                "user can click one to copy it."})

    def _load_preview(self, run, index, url):
        if run != self._run:
            return
        try:
            data = web.fetch_image(url, PREVIEW_MAX_BYTES)
        except web.ImageError:
            return                        # Platzhalter bleibt
        self._emit(self._bridge.preview, run, index, data)

    def _show_preview(self, run, index, data):
        if run != self._run or index >= self.grid.count():
            return
        try:
            _reader, buffer = web.image_reader(data)   # Format/Größe prüfen (nur GIF/WebP/JPEG/PNG)
        except web.ImageError:
            return
        buffer.seek(0)                    # die Prüfung hat den Kopf schon gelesen
        movie = QMovie(buffer, b"", self)
        if not movie.isValid():
            return
        item = self.grid.item(index)

        def frame(_number, movie=movie, item=item):
            pixmap = movie.currentPixmap().scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            item.setIcon(QIcon(pixmap))
        movie.frameChanged.connect(frame)
        self._movies[index] = (movie, buffer)
        movie.start()

    # --- Kopieren ---------------------------------------------------------------------
    def _copy(self, item):
        index = item.data(Qt.UserRole)
        if index is None or index >= len(self._gifs):
            return
        gif = self._gifs[index]
        self.status.setText("Lade das GIF …")

        def work():
            try:
                data, note = web.fetch_image(gif["gif"], GIF_MAX_BYTES), ""
            except web.ImageError as error:
                data, note = b"", f"Kopieren fehlgeschlagen: {error}"
            self._emit(self._bridge.copied, index, data, note)

        self._pool.submit(work)

    def _finish_copy(self, index, data, note):
        if not data:
            self.status.setText(note)
            return
        try:
            first_frame = web.decode_image(data)     # prüft Format und Größe
        except web.ImageError as error:
            self.status.setText(f"Kopieren fehlgeschlagen: {error}")
            return
        gif = self._gifs[index] if index < len(self._gifs) else {"id": uuid.uuid4().hex, "title": ""}
        os.makedirs(TEMP_DIR, exist_ok=True)
        safe_id = "".join(c for c in gif["id"] if c.isalnum() or c in "-_")[:60] or uuid.uuid4().hex
        path = os.path.join(TEMP_DIR, f"klipy-{safe_id}.gif")
        with open(path, "wb") as f:
            f.write(data)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])  # als Datei: bleibt beim Einfügen animiert
        mime.setData("image/gif", data)
        mime.setImageData(first_frame)            # für Programme, die nur Bilder annehmen
        QApplication.clipboard().setMimeData(mime)
        self.status.setText(f"✓ GIF kopiert ({first_frame.width()}×{first_frame.height()})"
                            + (f": {gif['title']}" if gif.get("title") else "") + " - jetzt mit Strg+V einfügen.")

    # --- KI-Assistent (ASSISTANT_TOOLS oben) -----------------------------------------
    def assistant_call(self, tool, args):
        if tool != "gif_search":
            raise ValueError(f"Unknown tool: {tool}")
        if not self._config.get("api_key"):
            raise ValueError("No KLIPY API key is set up yet - tell the user to enter one in the GIF search "
                             "window (free at partner.klipy.com).")
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("Please give a search term.")
        future = Future()
        self._pending[self.start_search(query)] = future
        return future                         # der Launcher wartet auf das Ergebnis

    def closeEvent(self, event):
        self._run += 1                        # laufende Ladevorgänge verwerfen
        self._stop_movies()
        self._pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PluginWidget()
    w.show()
    sys.exit(app.exec_())
