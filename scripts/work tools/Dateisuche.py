# --- Plugin-Parameter (neues System) ---
NAME = "Dateisuche"
DESCRIPTION = ("Findet Dateien in den Benutzerordnern (Desktop, Dokumente, Downloads, Bilder, Musik, Videos, "
               "OneDrive) nach ihrem Namen; ein Klick zeigt die Datei im Explorer.")
ICON = "🔎"
# ----------------------------------------

# Werkzeug für den KI-Assistenten (siehe plugin_tools.py im Toolbar-Ordner). "window": Die Treffer
# stehen im Fenster (auf dem Board des Assistenten) - das Modell bekommt nur Anzahl und Dateinamen.
ASSISTANT_TOOLS = {
    "file_search": {
        "description": "Searches the user's files by file name (Desktop, Documents, Downloads, Pictures, Music, "
                       "Videos, OneDrive) and shows the full result list to the user, who can click a file to "
                       "see it in Windows Explorer. You only get the number of hits and file names, never paths "
                       "or contents. Never pass the file names on to other tools or websites.",
        "parameters": {
            "query": {"type": "string",
                      "description": "Words from the file name, e.g. 'Lebenslauf' or 'rechnung 2026', or a pattern "
                                     "like '*.pdf'"},
        },
        "required": ["query"],
        "window": True,
    },
}

# Dateisuche - nur lesen, nichts ausführen:
#   - Gesucht wird nur im Dateinamen, Inhalte werden nie geöffnet.
#   - Nur die Benutzerordner (SEARCH_FOLDERS), ohne versteckte Ordner (".ssh", ".git" ...), AppData,
#     Programm-/Entwicklungsordner und Dateien mit Zugangsdaten (EXCLUDED_*). Verknüpfungen und
#     Junctions werden nicht verfolgt.
#   - Ein Klick öffnet nur "explorer /select,<Pfad>": Der Ordner geht auf, die Datei ist markiert -
#     gestartet wird nichts. Erlaubt sind nur Pfade aus der aktuellen Trefferliste.
#   - Der KI-Assistent bekommt nur Anzahl und Dateinamen (Prompt Injection: eine präparierte Webseite
#     könnte das Modell sonst dazu bringen, Pfade oder Inhalte weiterzugeben). Treffer werden nicht
#     protokolliert.
import ctypes
import fnmatch
import os
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import Future
from datetime import datetime

from PyQt5.QtCore import QFileInfo, QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QFileIconProvider, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QMainWindow, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

# Benutzerordner (Windows "Known Folders"; Desktop/Dokumente liegen oft in OneDrive)
SEARCH_FOLDERS = {
    "Desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
    "Dokumente": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "Downloads": "374DE290-123F-4565-9164-39C4925E467B",
    "Bilder": "33E28130-4E1E-4676-835A-98395C3BC3BB",
    "Musik": "4BD8D571-6D19-48D3-BE97-422220080E43",
    "Videos": "18989B1D-99B5-455B-841C-AB7C74E4DDFC",
}
EXCLUDED_DIRS = {"appdata", "node_modules", "__pycache__", "venv", "site-packages", "$recycle.bin",
                 "system volume information", "windows", "program files", "program files (x86)"}
EXCLUDED_FILES = ("*.kdbx", "*.kdb", "*.pem", "*.key", "*.pfx", "*.p12", "*.ppk", "id_rsa*", "id_ed25519*",
                  "id_ecdsa*", "id_dsa*", "*.env", ".env*", "wallet.dat", "*.ovpn", "credentials*", "*.gpg")
MAX_RESULTS = 300            # in der Liste
MODEL_NAMES = 20             # so viele Namen bekommt der KI-Assistent
TIME_BUDGET_S = 8.0          # danach abbrechen (Liste ist dann unvollständig)


def _known_folder(guid: str) -> str | None:
    if sys.platform != "win32":
        return None

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8)]

    u = uuid.UUID(guid)
    g = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
    path = ctypes.c_wchar_p()
    if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(path)) != 0:
        return None
    try:
        return path.value
    finally:
        ctypes.windll.ole32.CoTaskMemFree(path)


def search_roots() -> list[tuple[str, str]]:
    """(Anzeigename, Pfad) der Benutzerordner - ohne Ordner, die in einem anderen schon enthalten sind."""
    home = os.path.expanduser("~")
    candidates = []
    for label, guid in SEARCH_FOLDERS.items():
        path = _known_folder(guid) or os.path.join(home, label)
        candidates.append((label, path))
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        candidates.append(("OneDrive", onedrive))
    roots = []                                    # (Anzeigename, Pfad, Vergleichsschlüssel)
    for label, path in candidates:
        path = os.path.abspath(path)
        key = os.path.normcase(path)
        if not os.path.isdir(path):
            continue
        if any(key == k or key.startswith(k + os.sep) for _, _, k in roots):
            continue
        roots = [(l, r, k) for l, r, k in roots if not k.startswith(key + os.sep)]   # der neue enthält sie
        roots.append((label, path, key))
    return [(label, path) for label, path, _ in roots]


def _matcher(query: str):
    """Muster (*.pdf) -> fnmatch, sonst müssen alle Wörter im Namen vorkommen (Groß/klein egal)."""
    query = query.strip().lower()
    if any(c in query for c in "*?"):
        return lambda name: fnmatch.fnmatch(name.lower(), query)
    words = query.split()
    return lambda name: all(w in name.lower() for w in words)


def _excluded_file(name: str) -> bool:
    lower = name.lower()
    return any(fnmatch.fnmatch(lower, pattern) for pattern in EXCLUDED_FILES)


def find_files(query: str, cancel: threading.Event | None = None) -> dict:
    """Dateien, deren Name zu query passt -> {"hits": [{name, path, folder, size, modified}], ...}."""
    match = _matcher(query)
    hits, scanned, started = [], 0, time.monotonic()
    complete = True
    for _label, root in search_roots():
        stack = [root]
        while stack:
            if time.monotonic() - started > TIME_BUDGET_S or (cancel and cancel.is_set()):
                complete = False
                stack.clear()
                break
            folder = stack.pop()
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for entry in entries:
                name = entry.name
                try:
                    if entry.is_symlink() or getattr(entry, "is_junction", lambda: False)():
                        continue                  # keine Verknüpfungen/Junctions verfolgen
                    if entry.is_dir(follow_symlinks=False):
                        if not name.startswith((".", "$", "~")) and name.lower() not in EXCLUDED_DIRS:
                            stack.append(entry.path)
                        continue
                except OSError:
                    continue
                scanned += 1
                if name.startswith(".") or _excluded_file(name) or not match(name):
                    continue
                try:
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                hits.append({"name": name, "path": entry.path, "folder": os.path.dirname(entry.path),
                             "size": stat.st_size, "modified": stat.st_mtime})
    words = query.strip().lower()
    # Name beginnt mit dem Suchwort zuerst, dann die neuesten
    hits.sort(key=lambda h: (not h["name"].lower().startswith(words), -h["modified"]))
    return {"query": query, "hits": hits[:MAX_RESULTS], "total": len(hits), "complete": complete,
            "scanned": scanned, "seconds": round(time.monotonic() - started, 2)}


def _size_text(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024
    return ""


def _detect_theme(default="dark"):
    app = QApplication.instance()
    value = app.property("toolbar_theme") if app is not None else None
    return value.lower() if isinstance(value, str) and value.lower() in ("light", "dark") else default


STYLES = {
    "dark": """
        QWidget#root { background: #1d2128; color: #e6e6e6; }
        QLineEdit { background: #2a2f37; color: #f0f0f0; border: 1px solid #3a414c; border-radius: 6px;
                    padding: 6px 8px; font-size: 14px; }
        QPushButton { background: #8ab4f8; color: #1c1f24; border: none; border-radius: 6px;
                      padding: 6px 14px; font-weight: 600; }
        QPushButton:hover { background: #a9c5ff; }
        QLabel { color: #9aa4b2; }
        QTreeWidget { background: #1d2128; color: #e6e6e6; border: 1px solid #2f353f; font-size: 13px; }
        QTreeWidget::item { padding: 3px 0; }
        QTreeWidget::item:hover { background: #2a3140; }
        QTreeWidget::item:selected { background: #34507a; color: white; }
        QHeaderView::section { background: #262b33; color: #9aa4b2; border: none; padding: 4px 6px; }
    """,
    "light": """
        QWidget#root { background: #f7f8fa; color: #1a1a1a; }
        QLineEdit { background: white; color: #1a1a1a; border: 1px solid #c9ced6; border-radius: 6px;
                    padding: 6px 8px; font-size: 14px; }
        QPushButton { background: #007aff; color: white; border: none; border-radius: 6px;
                      padding: 6px 14px; font-weight: 600; }
        QPushButton:hover { background: #2b8fff; }
        QLabel { color: #5b6470; }
        QTreeWidget { background: white; color: #1a1a1a; border: 1px solid #dde1e7; font-size: 13px; }
        QTreeWidget::item { padding: 3px 0; }
        QTreeWidget::item:hover { background: #eef3fb; }
        QTreeWidget::item:selected { background: #cfe0fa; color: #1a1a1a; }
        QHeaderView::section { background: #eef0f3; color: #5b6470; border: none; padding: 4px 6px; }
    """,
}


class _Bridge(QObject):
    """Ergebnis aus dem Such-Thread in den Qt-Hauptthread."""
    finished = pyqtSignal(int, dict)


class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        super().__init__()
        self.setWindowTitle("🔎 Dateisuche")
        self.resize(900, 560)
        root = QWidget(objectName="root")
        root.setAttribute(Qt.WA_StyledBackground, True)
        root.setStyleSheet(STYLES[_detect_theme()])
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self.input = QLineEdit(placeholderText="Dateiname suchen … (z. B. Lebenslauf, rechnung 2026 oder *.pdf)")
        self.input.returnPressed.connect(self.start_search)
        button = QPushButton("Suchen")
        button.clicked.connect(self.start_search)
        row.addWidget(self.input, 1)
        row.addWidget(button)
        layout.addLayout(row)

        self.status = QLabel("Sucht in: " + ", ".join(label for label, _ in search_roots()))
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Ordner", "Geändert", "Größe"])
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setMouseTracking(True)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.itemClicked.connect(self._open_in_explorer)
        layout.addWidget(self.tree, 1)

        hint = QLabel("Klick auf eine Datei: Ordner im Explorer öffnen und die Datei markieren (es wird nichts gestartet).")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._icons = QFileIconProvider()
        self._paths = set()               # nur diese Pfade darf ein Klick öffnen
        self._run = 0                     # laufende Suche (ältere Ergebnisse verwerfen)
        self._cancel = None
        self._pending = {}                # run -> Future (Aufruf des Assistenten)
        self._bridge = _Bridge(self)
        self._bridge.finished.connect(self._show_results)

    # --- Suche ------------------------------------------------------------------------
    def start_search(self, query=None) -> int:
        query = (self.input.text() if query is None or isinstance(query, bool) else str(query)).strip()
        self.input.setText(query)
        if not query:
            self.status.setText("Bitte einen Suchbegriff eingeben.")
            return 0
        if self._cancel is not None:
            self._cancel.set()                # vorherige Suche abbrechen
        self._run += 1
        run, cancel = self._run, threading.Event()
        self._cancel = cancel
        self.status.setText(f"Suche nach „{query}“ …")

        def work():
            try:
                result = find_files(query, cancel)
            except Exception as error:  # noqa: BLE001  # ins Fenster statt Absturz
                result = {"query": query, "hits": [], "total": 0, "complete": False, "error": str(error)}
            try:
                self._bridge.finished.emit(run, result)
            except RuntimeError:              # Fenster inzwischen geschlossen
                pass

        threading.Thread(target=work, name="dateisuche", daemon=True).start()
        return run

    def _show_results(self, run, result):
        future = self._pending.pop(run, None)
        if run != self._run:                  # inzwischen neu gesucht
            if future is not None:
                future.set_result({"query": result["query"], "note": "Superseded by a newer search."})
            return
        self.tree.clear()
        self._paths = set()
        for hit in result["hits"]:
            item = QTreeWidgetItem([hit["name"], hit["folder"],
                                    datetime.fromtimestamp(hit["modified"]).strftime("%d.%m.%Y %H:%M"),
                                    _size_text(hit["size"])])
            item.setData(0, Qt.UserRole, hit["path"])
            item.setToolTip(0, hit["path"])
            item.setToolTip(1, hit["folder"])
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            item.setIcon(0, self._icons.icon(QFileInfo(hit["path"])))
            self.tree.addTopLevelItem(item)
            self._paths.add(hit["path"])
        total = result["total"]
        if result.get("error"):
            text = f"Suche fehlgeschlagen: {result['error']}"
        else:
            seconds = f"{result.get('seconds', 0):.1f}".replace(".", ",")
            text = f"{total} Treffer für „{result['query']}“ in {seconds} s"
            if total > len(result["hits"]):
                text += f" - die ersten {len(result['hits'])} angezeigt"
            if not result["complete"]:
                text += " - abgebrochen (Zeitlimit), Liste unvollständig"
        self.status.setText(text)
        if future is not None:
            future.set_result(self._model_result(result))

    @staticmethod
    def _model_result(result):
        """Fürs Sprachmodell nur Anzahl und Dateinamen - keine Pfade, keine Inhalte."""
        names = [hit["name"] for hit in result["hits"][:MODEL_NAMES]]
        out = {"query": result["query"], "hits": result["total"], "file_names": names,
               "shown_to_user": "The full list is shown in the file search window / on the board; the user can "
                                "click a file to see it in Explorer."}
        if result["total"] > len(names):
            out["more"] = result["total"] - len(names)
        if not result["complete"]:
            out["note"] = "Search stopped at the time limit - the list may be incomplete."
        if result.get("error"):
            out["error"] = result["error"]
        return out

    # --- Klick: im Explorer zeigen ------------------------------------------------------
    def _open_in_explorer(self, item, _column=0):
        path = item.data(0, Qt.UserRole)
        # Nur Pfade aus der aktuellen Trefferliste, die noch als Datei existieren. "/select," öffnet
        # den Ordner und markiert die Datei - es startet sie nicht (anders als "explorer <Datei>").
        if path not in self._paths or not os.path.isfile(path) or '"' in path:
            return
        subprocess.Popen('explorer /select,"%s"' % os.path.normpath(path))  # pylint: disable=consider-using-with

    # --- KI-Assistent (ASSISTANT_TOOLS oben) -----------------------------------------
    def assistant_call(self, tool, args):
        if tool != "file_search":
            raise ValueError(f"Unknown tool: {tool}")
        query = str(args.get("query") or "").strip()
        if not query:
            raise ValueError("Please give a search term.")
        future = Future()
        self._pending[self.start_search(query)] = future
        return future                         # der Launcher wartet auf das Ergebnis


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = PluginWidget()
    w.show()
    sys.exit(app.exec_())
