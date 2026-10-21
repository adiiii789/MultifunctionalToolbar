"""plugin_tools.py - Werkzeuge der Plugins für den KI-Assistenten (Seite des Launchers)

Ein Plugin bietet dem Assistenten Werkzeuge an, indem es oben in seiner Datei
ASSISTANT_TOOLS anlegt. Gelesen wird das per AST (wie die übrigen Plugin-Parameter) -
die Datei wird dafür nicht ausgeführt, neue Plugins tauchen ohne Neustart auf::

    ASSISTANT_TOOLS = {
        "timer_start": {
            "description": "Starts a countdown timer.",          # fürs Sprachmodell, am besten Englisch
            "parameters": {                                      # JSON-Schema je Argument
                "minutes": {"type": "number", "description": "Duration in minutes"},
            },
            "required": ["minutes"],                             # optional
            "window": True,                                      # optional, siehe unten
            "show": True,                                        # optional, siehe unten
            "board": False,                                      # optional, siehe unten
        },
    }

    def assistant_call(tool, args):                  # Werkzeuge ohne "window" - Modul-Ebene
        ...                                          # Rückgabe: Text oder JSON-taugliches Objekt
                                                     # Fehler: Exception mit verständlicher Meldung
    class PluginWidget(...):
        def assistant_call(self, tool, args): ...    # Werkzeuge mit "window": True - das offene Fenster
                                                     # (der Launcher öffnet es bei Bedarf als Tab)
        def on_assistant_change(self, tool, args, result): ...
                                                     # optional: offenes Fenster nach einem Aufruf
                                                     # auf Modul-Ebene aktualisieren (z. B. neu zeichnen)

"window": True ist für Plugins, deren Zustand nur im laufenden Fenster lebt (z. B. der
Countdown im Timer). Gibt assistant_call ein concurrent.futures.Future zurück, wartet der
Launcher auf dessen Ergebnis (z. B. für runJavaScript, dessen Antwort später kommt).

Board: Ist das Board des 3D-Assistenten zu sehen (breites Layout), erscheint jedes Plugin,
das er bedient, dort im Board-iframe - live und bedienbar (3D Assistent.py: show_on_board,
_BoardStream; das echte Fenster liegt verdeckt unter der 3D-Ansicht).
Dort erzeugte Fenster bleiben am Leben (ein Timer läuft weiter, auch wenn ausgeblendet).
"board": False schaltet das für ein Werkzeug ab.

"show": True zeigt das Plugin nach einem erfolgreichen Aufruf auch dann, wenn kein Board zu
sehen ist: als Tab im Hauptfenster (holt es nach vorne), damit man die Änderung sieht - z. B.
der Kalender nach einem neuen Termin. on_assistant_change kommt danach auch beim gerade
geöffneten Fenster an, es kann also zur Änderung springen. Für reine Abfragen weglassen,
sonst springt bei jeder Frage ein Fenster auf.

Eingebaut (gehört keinem Plugin): toolbar_list_plugins listet alle Plugins der Toolbar mit
Beschreibung - DESCRIPTION oben in der Plugin-Datei (ein Satz, was es macht), sonst der Docstring
oder die Beschreibungen seiner ASSISTANT_TOOLS. Wird bei jedem Aufruf neu gelesen.

Transport: Der Launcher startet einen HTTP-Server nur auf 127.0.0.1 mit zufälligem Port
und Token und legt beides in die Umgebungsvariablen TOOLBAR_TOOLS_URL und
TOOLBAR_TOOLS_TOKEN. Prozesse, die die Toolbar startet (KI-Dienst des 3D-Assistenten),
erben sie; ohne Token antwortet der Server nicht. Jeder Aufruf läuft im Qt-Hauptthread,
weil Plugins Fenster anfassen.

    GET  /tools                          -> [{"name", "description", "input_schema", "plugin"}]
    POST /call {"name", "arguments"}     -> {"ok": true, "result": ...} | {"ok": false, "error": "..."}
"""
from __future__ import annotations

import ast
import concurrent.futures
import hmac
import json
import logging
import os
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from PyQt5.QtCore import QObject, Qt, pyqtSignal

log = logging.getLogger("plugin_tools")

ENV_URL = "TOOLBAR_TOOLS_URL"
ENV_TOKEN = "TOOLBAR_TOOLS_TOKEN"
CALL_TIMEOUT_S = 60
MAX_BODY_BYTES = 64 * 1024


@dataclass(frozen=True)
class PluginTool:
    name: str                       # Name fürs Modell (bei Doppelungen mit Plugin-Präfix)
    tool: str                       # Name im Plugin (geht an assistant_call)
    plugin_path: str
    plugin_name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    window: bool = False
    show: bool = False
    board: bool = True


# --- ASSISTANT_TOOLS per AST lesen ----------------------------------------------
_cache: dict[str, tuple[float, dict]] = {}   # Pfad -> (mtime, ASSISTANT_TOOLS)


def read_assistant_tools(path: str) -> dict:
    """ASSISTANT_TOOLS einer Plugin-Datei (leer, wenn es keine gibt oder sie kein Literal ist)."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    cached = _cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    tools: dict = {}
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        if "ASSISTANT_TOOLS" in source:
            for node in ast.parse(source).body:
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "ASSISTANT_TOOLS"):
                    value = ast.literal_eval(node.value)
                    tools = value if isinstance(value, dict) else {}
    except (OSError, SyntaxError, ValueError) as error:
        log.warning("ASSISTANT_TOOLS in %s nicht lesbar: %s", path, error)
    _cache[path] = (mtime, tools)
    return tools


def _plugin_name(path: str) -> str:
    """Anzeigename: NAME aus der Datei, sonst der Dateiname."""
    try:
        with open(path, encoding="utf-8") as f:
            match = re.search(r'^NAME\s*=\s*["\'](.+?)["\']', f.read(), re.M)
        if match:
            return match.group(1)
    except OSError:
        pass
    return os.path.splitext(os.path.basename(path))[0]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "plugin"


def scan_tools(script_root: str) -> list[PluginTool]:
    """Alle Werkzeuge aller Plugins unter script_root (Ordner mit "_" am Anfang zählen nicht)."""
    found: list[PluginTool] = []
    names: set[str] = set()
    for folder, dirs, files in os.walk(script_root):
        dirs[:] = sorted(d for d in dirs if not d.startswith(("_", ".")) and d != "__pycache__")
        for file in sorted(files):
            if not file.endswith(".py") or file.startswith("_"):
                continue
            path = os.path.join(folder, file)
            tools = read_assistant_tools(path)
            if not tools:
                continue
            plugin = _plugin_name(path)
            for tool, spec in tools.items():
                if not isinstance(spec, dict) or not isinstance(spec.get("description"), str):
                    log.warning("Werkzeug %r in %s: description fehlt", tool, path)
                    continue
                name = _slug(str(tool))
                if name in names:                        # zwei Plugins mit gleichem Namen
                    name = f"{_slug(plugin)}_{name}"
                names.add(name)
                schema = {"type": "object", "properties": dict(spec.get("parameters") or {})}
                if spec.get("required"):
                    schema["required"] = list(spec["required"])
                found.append(PluginTool(name, str(tool), path, plugin, f"[{plugin}] {spec['description']}",
                                        schema, bool(spec.get("window")), bool(spec.get("show")),
                                        bool(spec.get("board", True))))
    return found


# --- Eingebaut: alle Plugins mit Beschreibung --------------------------------------
LIST_PLUGINS_TOOL = "toolbar_list_plugins"
LIST_PLUGINS_SPEC = PluginTool(
    LIST_PLUGINS_TOOL, LIST_PLUGINS_TOOL, "", "Toolbar",
    "[Toolbar] Lists all plugins (apps) of the user's toolbar with a short description of what each one "
    "does, its folder and the assistant tools it offers. Use it when the user asks what the toolbar or "
    "its plugins can do, or which plugin fits a task.",
    {"type": "object", "properties": {
        "query": {"type": "string",
                  "description": "Optional: only plugins whose name, folder or description contains this text"}}},
    board=False)
_INFO_KEYS = {"NAME", "ICON", "DESCRIPTION", "ALLOW_POPUP", "ALLOW_WINDOW", "RUN_AS", "ASSISTANT_TOOLS"}
_HTML_META = re.compile(r"<!--\s*(NAME|ICON|DESCRIPTION)\s*[:=]\s*(.+?)\s*-->", re.I)
_info_cache: dict[str, tuple[float, dict]] = {}   # Pfad -> (mtime, Angaben)


def read_plugin_info(path: str) -> dict:
    """NAME, ICON, DESCRIPTION, ALLOW_POPUP/-WINDOW, RUN_AS, ASSISTANT_TOOLS und Docstring einer
    Plugin-Datei - per AST, die Datei wird nicht ausgeführt (HTML-Plugins: <!-- KEY: Wert -->)."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    cached = _info_cache.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    info: dict = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            source = f.read()
        if path.lower().endswith(".html"):
            info = {m.group(1).upper(): m.group(2).strip().strip("\"'") for m in _HTML_META.finditer(source[:4096])}
        else:
            tree = ast.parse(source)
            for node in tree.body:
                if (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name) and node.targets[0].id in _INFO_KEYS):
                    try:
                        info[node.targets[0].id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError, SyntaxError):
                        pass
            info["__doc__"] = ast.get_docstring(tree) or ""
    except (OSError, SyntaxError, ValueError) as error:
        log.warning("Plugin-Angaben in %s nicht lesbar: %s", path, error)
    _info_cache[path] = (mtime, info)
    return info


def _describe(info: dict) -> str:
    """Beschreibung: DESCRIPTION, sonst erster Absatz des Docstrings, sonst die Werkzeuge."""
    text = info.get("DESCRIPTION")
    if isinstance(text, str) and text.strip():
        return " ".join(text.split())
    doc = str(info.get("__doc__") or "").strip()
    if doc:
        return " ".join(doc.split("\n\n")[0].split())[:300]
    tools = info.get("ASSISTANT_TOOLS")
    if isinstance(tools, dict):
        parts = [spec["description"] for spec in tools.values()
                 if isinstance(spec, dict) and isinstance(spec.get("description"), str)]
        if parts:
            return "Offers: " + " ".join(parts[:3])
    return ""


def list_plugins(script_root: str, query: str = "") -> list[dict]:
    """Alle Plugins der Toolbar (wie der Explorer: ohne Ordner/Dateien mit "_" am Anfang und ohne
    Plugins, die in beiden Ansichten ausgeblendet sind) mit Beschreibung und ihren Werkzeugen."""
    tools_by_path: dict[str, list[str]] = {}
    for tool in scan_tools(script_root):
        tools_by_path.setdefault(tool.plugin_path, []).append(tool.name)
    query = (query or "").strip().lower()
    plugins = []
    for folder, dirs, files in os.walk(script_root):
        dirs[:] = sorted(d for d in dirs if not d.startswith(("_", ".")) and d != "__pycache__")
        for file in sorted(files):
            if file.startswith("_") or not file.lower().endswith((".py", ".html")):
                continue
            path = os.path.join(folder, file)
            info = read_plugin_info(path)
            if info.get("ALLOW_POPUP") is False and info.get("ALLOW_WINDOW") is False:
                continue                              # in der Toolbar nirgends zu sehen
            entry = {"name": str(info.get("NAME") or os.path.splitext(file)[0]),
                     "folder": "" if folder == script_root
                     else os.path.relpath(folder, script_root).replace(os.sep, "/"),
                     "description": _describe(info)}
            if info.get("ICON"):
                entry["icon"] = str(info["ICON"])
            if tools_by_path.get(path):
                entry["assistant_tools"] = tools_by_path[path]
            if query and query not in " ".join(str(v) for v in entry.values()).lower():
                continue
            plugins.append(entry)
    return plugins


# --- Server ------------------------------------------------------------------------
class _Job:
    def __init__(self, tool: PluginTool, arguments: dict):
        self.tool = tool
        self.arguments = arguments
        self.done = threading.Event()
        self.result: Any = None
        self.error: str | None = None


class PluginToolServer(QObject):
    """HTTP-Schnittstelle für den Assistenten; führt Aufrufe im Qt-Hauptthread aus.

    load_module(path)  -> Modul des Plugins (für Werkzeuge ohne Fenster)
    find_widgets(path) -> offene PluginWidgets dieses Plugins (Hauptfenster, Popup)
    open_widget(path, board)  -> PluginWidget, bei Bedarf geöffnet (für "window": True)
    show_widget(path, force, allow_new, board)
                       -> Plugin zeigen: aufs Board des Assistenten, mit force ("show": True)
                          sonst als Tab im Hauptfenster
    """

    _requested = pyqtSignal(object)

    def __init__(self, script_root: str, load_module: Callable, find_widgets: Callable,
                 open_widget: Callable, show_widget: Callable | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.script_root = script_root
        self.load_module = load_module
        self.find_widgets = find_widgets
        self.open_widget = open_widget
        self.show_widget = show_widget
        self.token = secrets.token_urlsafe(24)
        self._requested.connect(self._execute, Qt.QueuedConnection)
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, name="plugin-tools", daemon=True).start()
        self._server = server
        url = "http://127.0.0.1:%d" % server.server_address[1]
        os.environ[ENV_URL] = url               # erben Prozesse, die die Toolbar startet
        os.environ[ENV_TOKEN] = self.token
        log.info("Plugin-Werkzeuge für den Assistenten unter %s", url)
        return url

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None

    def tools(self) -> list[PluginTool]:
        return [LIST_PLUGINS_SPEC, *scan_tools(self.script_root)]

    def call(self, name: str, arguments: dict) -> _Job:
        """Aus einem HTTP-Thread: Aufruf im Hauptthread ausführen lassen und darauf warten."""
        tool = next((t for t in self.tools() if t.name == name), None)
        job = _Job(tool, arguments)
        if tool is None:
            job.error = f"Unbekanntes Werkzeug: {name}"
            return job
        if tool is LIST_PLUGINS_SPEC:            # liest nur Dateien - kein Qt, gleich hier
            job.result = {"plugins": list_plugins(self.script_root, str(arguments.get("query") or ""))}
            return job
        self._requested.emit(job)
        if not job.done.wait(CALL_TIMEOUT_S):
            job.error = f"{name}: keine Antwort nach {CALL_TIMEOUT_S} s"
            return job
        if isinstance(job.result, concurrent.futures.Future):   # Antwort kommt später (z. B. JavaScript)
            try:
                job.result = job.result.result(CALL_TIMEOUT_S)
            except Exception as error:  # noqa: BLE001  # Fehler gehen als Text ans Modell
                job.error = str(error) or type(error).__name__
        return job

    def _execute(self, job: _Job) -> None:
        """Im Qt-Hauptthread."""
        tool = job.tool
        try:
            if tool.window:
                widget = self.open_widget(tool.plugin_path, board=tool.board)
                handler = getattr(widget, "assistant_call", None)
                if not callable(handler):
                    raise RuntimeError(f"{tool.plugin_name}: PluginWidget hat kein assistant_call")
                job.result = handler(tool.tool, job.arguments)
                self._show(tool)
            else:
                handler = getattr(self.load_module(tool.plugin_path), "assistant_call", None)
                if not callable(handler):
                    raise RuntimeError(f"{tool.plugin_name}: assistant_call fehlt in der Plugin-Datei")
                job.result = handler(tool.tool, job.arguments)
                self._show(tool)                                        # vor dem Nachziehen: neues Fenster zählt mit
                for widget in self.find_widgets(tool.plugin_path):      # offene Fenster nachziehen
                    refresh = getattr(widget, "on_assistant_change", None)
                    if callable(refresh):
                        try:
                            refresh(tool.tool, job.arguments, job.result)
                        except Exception:  # noqa: BLE001  # Anzeige - der Aufruf selbst hat geklappt
                            log.exception("on_assistant_change in %s fehlgeschlagen", tool.plugin_path)
        except Exception as error:  # noqa: BLE001  # Plugin-Code kann alles werfen - Text ans Modell
            log.warning("Werkzeug %s fehlgeschlagen: %s", tool.name, error)
            job.error = str(error) or type(error).__name__
        finally:
            job.done.set()

    def _show(self, tool: PluginTool) -> None:
        """Bedientes Plugin zeigen: aufs Board, bei "show" sonst als Tab (nicht für Abfragen
        ohne "show", wenn kein Board zu sehen ist)."""
        if self.show_widget is None or not (tool.show or tool.board):
            return
        try:
            self.show_widget(tool.plugin_path, force=tool.show, allow_new=not tool.window, board=tool.board)
        except Exception:  # noqa: BLE001  # Anzeige - der Aufruf selbst hat geklappt
            log.exception("%s ließ sich nicht anzeigen", tool.plugin_path)


def _make_handler(owner: PluginToolServer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _json(self, code: int, obj) -> None:
            body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            sent = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            if hmac.compare_digest(sent, owner.token):
                return True
            self._json(401, {"error": "nicht berechtigt"})
            return False

        def do_GET(self):
            if not self._authorized():
                return
            if self.path.split("?")[0] != "/tools":
                self._json(404, {"error": "unbekannter Pfad"})
                return
            self._json(200, [{"name": t.name, "description": t.description, "input_schema": t.input_schema,
                              "plugin": t.plugin_name} for t in owner.tools()])

        def do_POST(self):
            if not self._authorized():
                return
            if self.path.split("?")[0] != "/call":
                self._json(404, {"error": "unbekannter Pfad"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= MAX_BODY_BYTES:
                    raise ValueError("Größe")
                req = json.loads(self.rfile.read(length).decode("utf-8"))
                name, arguments = str(req["name"]), req.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise ValueError("arguments muss ein Objekt sein")
            except (ValueError, KeyError) as error:
                self._json(400, {"error": str(error)})
                return
            job = owner.call(name, arguments)
            if job.error:
                self._json(200, {"ok": False, "error": job.error})
            else:
                self._json(200, {"ok": True, "result": job.result})

    return Handler
