# --- Plugin-Parameter (neues System) ---
NAME = "Bildersuche"
DESCRIPTION = ("Sucht Bilder im Internet (DuckDuckGo) und zeigt Vorschaubilder; ein Klick kopiert das Bild "
               "in die Zwischenablage.")
ICON = "🖼️"
# ----------------------------------------

# Werkzeug für den KI-Assistenten (siehe plugin_tools.py im Toolbar-Ordner). "window": Die Bilder
# stehen im Fenster (auf dem Board des Assistenten) - das Modell bekommt nur die Anzahl.
ASSISTANT_TOOLS = {
    "image_search": {
        "description": "Searches the internet for images and shows them to the user as a grid of previews; the "
                       "user can click an image to copy it to the clipboard. You only get the number of results "
                       "(no titles or links).",
        "parameters": {
            "query": {"type": "string", "description": "What to search for, e.g. 'sunset over the sea'"},
        },
        "required": ["query"],
        "window": True,
    },
}

# Bildersuche - Sicherheit:
#   - Vorschaubilder kommen über den Bild-Proxy der Suchmaschine (Bing-Thumbnails); den Server des
#     Originals kontaktiert die Toolbar erst, wenn man ein Bild kopiert (der sieht dann die IP-Adresse).
#   - Laden und Dekodieren über _web_images.py: nur öffentliche Adressen (auch nach Weiterleitungen),
#     nur JPEG/PNG/GIF/WebP, kein SVG, Größen- und Zeitlimit.
#   - Kopiert werden nur die Bildpixel (keine Links, kein HTML).
#   - Der KI-Assistent bekommt nur die Anzahl - Titel und Adressen stammen von fremden Seiten und
#     könnten Anweisungen an das Modell enthalten (Prompt Injection).
import importlib.util
import os
import sys
import threading
import urllib.parse
from concurrent.futures import Future, ThreadPoolExecutor

from PyQt5.QtCore import QObject, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QListView, QListWidget,
                             QListWidgetItem, QMainWindow, QPushButton, QVBoxLayout, QWidget)


def _load_helper():
    """_web_images.py aus diesem Ordner (gemeinsam mit Gifsuche.py; "_" = kein Plugin)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_web_images.py")
    spec = importlib.util.spec_from_file_location("toolbar_web_images", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


web = _load_helper()
ImageError, fetch_image, decode_image = web.ImageError, web.fetch_image, web.decode_image
STYLES, _detect_theme = web.STYLES, web.detect_theme

MAX_RESULTS = 60
SAFESEARCH = "moderate"          # "on" | "moderate" | "off"
REGION = "wt-wt"                 # weltweit; z. B. "de-de"
THUMB_MAX_BYTES = 2 * 1024 * 1024
IMAGE_MAX_BYTES = 15 * 1024 * 1024
THUMB_SIZE = QSize(176, 132)


def search_images(query: str) -> list[dict]:
    from ddgs import DDGS   # erst hier: lädt einiges
    results = DDGS().images(query, region=REGION, safesearch=SAFESEARCH, max_results=MAX_RESULTS)
    images = []
    for r in results or []:
        if r.get("thumbnail") and r.get("image"):
            images.append({"title": str(r.get("title") or ""), "image": str(r["image"]),
                           "thumbnail": str(r["thumbnail"]), "page": str(r.get("url") or ""),
                           "width": r.get("width"), "height": r.get("height")})
    return images


class _Bridge(QObject):
    """Ergebnisse aus den Hintergrund-Threads in den Qt-Hauptthread."""
    results = pyqtSignal(int, object)          # Suchlauf, Liste oder Fehlertext
    thumbnail = pyqtSignal(int, int, bytes)    # Suchlauf, Index, Bilddaten
    copied = pyqtSignal(int, bytes, str)       # Index, Bilddaten (leer = fehlgeschlagen), Hinweis


class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        super().__init__()
        self.setWindowTitle("🖼️ Bildersuche")
        self.resize(900, 600)
        root = QWidget(objectName="root")
        root.setAttribute(Qt.WA_StyledBackground, True)
        root.setStyleSheet(STYLES[_detect_theme()])
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self.input = QLineEdit(placeholderText="Bilder suchen … (z. B. Sonnenuntergang am Meer)")
        self.input.returnPressed.connect(self.start_search)
        button = QPushButton("Suchen")
        button.clicked.connect(self.start_search)
        row.addWidget(self.input, 1)
        row.addWidget(button)
        layout.addLayout(row)

        self.status = QLabel("Bilder aus dem Internet (DuckDuckGo, SafeSearch moderat).")
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

        hint = QLabel("Klick auf ein Bild: in Originalgröße in die Zwischenablage kopieren (dann z. B. mit Strg+V einfügen).")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._images = []                 # Treffer des aktuellen Suchlaufs
        self._run = 0
        self._pending = {}                # Suchlauf -> Future (Aufruf des Assistenten)
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bildersuche")
        self._placeholder = self._make_placeholder()
        self._bridge = _Bridge(self)
        self._bridge.results.connect(self._show_results)
        self._bridge.thumbnail.connect(self._show_thumbnail)
        self._bridge.copied.connect(self._finish_copy)

    def _make_placeholder(self):
        pixmap = QPixmap(THUMB_SIZE)
        pixmap.fill(Qt.transparent)
        return QIcon(pixmap)

    def _emit(self, signal, *args):
        try:
            signal.emit(*args)
        except RuntimeError:              # Fenster inzwischen geschlossen
            pass

    # --- Suche ------------------------------------------------------------------------
    def start_search(self, query=None) -> int:
        query = (self.input.text() if query is None or isinstance(query, bool) else str(query)).strip()
        self.input.setText(query)
        if not query:
            self.status.setText("Bitte einen Suchbegriff eingeben.")
            return 0
        self._run += 1
        run = self._run
        self.status.setText(f"Suche Bilder zu „{query}“ …")

        def work():
            try:
                result = search_images(query)
            except Exception as error:  # noqa: BLE001  # ddgs wirft je nach Backend Verschiedenes
                result = f"Suche fehlgeschlagen: {error}"
            self._emit(self._bridge.results, run, result)

        threading.Thread(target=work, name="bildersuche", daemon=True).start()
        return run

    def _show_results(self, run, result):
        future = self._pending.pop(run, None)
        if run != self._run:
            if future is not None:
                future.set_result({"note": "Superseded by a newer search."})
            return
        self.grid.clear()
        if isinstance(result, str):
            self._images = []
            self.status.setText(result)
            if future is not None:
                future.set_exception(RuntimeError(result))
            return
        self._images = result
        for index, image in enumerate(result):
            title = image["title"] or urllib.parse.urlsplit(image["page"]).hostname or "Bild"
            item = QListWidgetItem(self._placeholder, title if len(title) <= 28 else title[:27] + "…")
            host = urllib.parse.urlsplit(image["image"]).hostname or ""
            size = f" · {image['width']}×{image['height']}" if image.get("width") and image.get("height") else ""
            item.setToolTip(f"{image['title']}\n{host}{size}")
            item.setData(Qt.UserRole, index)
            self.grid.addItem(item)
            self._pool.submit(self._load_thumbnail, run, index, image["thumbnail"])
        self.status.setText(f"{len(result)} Bilder zu „{self.input.text()}“ - Klick kopiert ein Bild."
                            if result else f"Keine Bilder zu „{self.input.text()}“ gefunden.")
        if future is not None:
            future.set_result({"query": self.input.text(), "images": len(result),
                               "shown_to_user": "The images are shown in the image search window / on the board; "
                                                "the user can click one to copy it to the clipboard."})

    def _load_thumbnail(self, run, index, url):
        if run != self._run:
            return
        try:
            data = fetch_image(url, THUMB_MAX_BYTES)
        except ImageError:
            return                        # Platzhalter bleibt
        self._emit(self._bridge.thumbnail, run, index, data)

    def _show_thumbnail(self, run, index, data):
        if run != self._run or index >= self.grid.count():
            return
        try:
            image = decode_image(data)
        except ImageError:
            return
        pixmap = QPixmap.fromImage(image.scaled(THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.grid.item(index).setIcon(QIcon(pixmap))

    # --- Kopieren ---------------------------------------------------------------------
    def _copy(self, item):
        index = item.data(Qt.UserRole)
        if index is None or index >= len(self._images):
            return
        image = self._images[index]
        self.status.setText("Lade das Bild in Originalgröße …")

        def work():
            try:
                data, note = fetch_image(image["image"], IMAGE_MAX_BYTES), ""
            except ImageError as error:   # Original nicht ladbar - dann die Vorschau
                try:
                    data, note = fetch_image(image["thumbnail"], THUMB_MAX_BYTES), f"Original nicht ladbar ({error}), Vorschau kopiert"
                except ImageError as error2:
                    data, note = b"", f"Kopieren fehlgeschlagen: {error2}"
            self._emit(self._bridge.copied, index, data, note)

        self._pool.submit(work)

    def _finish_copy(self, index, data, note):
        if not data:
            self.status.setText(note)
            return
        try:
            image = decode_image(data)
        except ImageError as error:
            self.status.setText(f"Kopieren fehlgeschlagen: {error}")
            return
        QApplication.clipboard().setImage(image)   # nur Pixel, keine Links/HTML
        title = self._images[index]["title"] if index < len(self._images) else ""
        self.status.setText(f"✓ Kopiert ({image.width()}×{image.height()})" + (f": {title}" if title else "")
                            + (f" - {note}" if note else " - jetzt z. B. mit Strg+V einfügen."))

    # --- KI-Assistent (ASSISTANT_TOOLS oben) -----------------------------------------
    def assistant_call(self, tool, args):
        if tool != "image_search":
            raise ValueError(f"Unknown tool: {tool}")
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("Please give a search term.")
        future = Future()
        self._pending[self.start_search(query)] = future
        return future                         # der Launcher wartet auf das Ergebnis

    def closeEvent(self, event):
        self._run += 1                        # laufende Ladevorgänge verwerfen
        self._pool.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PluginWidget()
    w.show()
    sys.exit(app.exec_())
