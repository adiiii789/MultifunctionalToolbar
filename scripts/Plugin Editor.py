# --- Plugin-Parameter (neues System) ---
NAME = "Plugin Editor"
ICON = "🛠️"
ALLOW_POPUP = False
# ----------------------------------------

# Editor zum einfachen Erstellen und Bearbeiten von Plugins.
# Prinzip: Die CODE-BOX ist die einzige Quelle der Vorschau. Aus ihrem Inhalt
# werden BUTTON_HTML, WINDOW_HTML und POPUP_HTML (falls vorhanden) gezogen und
# auf die Vorschau-Tabs (Button / Window / Popup) verteilt — egal ob der Code
# aus dem Formular generiert, aus einer Datei geladen oder von Hand editiert
# wurde. Bei Cards mit get_inline_html(mode) rendert das Backend die Card beim
# Laden mit; bei Widget-Plugins wird der größte HTML-String im Code als
# Fenster-Vorschau (Näherung) extrahiert.

import os
import json

from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel


def _scripts_root():
    return os.path.abspath("scripts")


def _detect_host_theme(default="dark"):
    app = QApplication.instance()
    if app is not None:
        prop = app.property("toolbar_theme")
        if isinstance(prop, str) and prop.lower() in ("light", "dark"):
            return prop.lower()
    return default


class EditorBridge(QObject):
    """Backend des Editors: Dateien lesen/schreiben + Code analysieren."""

    def _safe_path(self, filename):
        rel = (filename or "").strip().replace(chr(92), "/")
        if not rel or not (rel.endswith(".py") or rel.endswith(".html")):
            return None
        parts = [x for x in rel.split("/") if x]
        if not parts or any(x.startswith("_") or x == ".." for x in parts):
            return None  # versteckte Dateien / Pfad-Ausbrüche
        root = _scripts_root()
        p = os.path.abspath(os.path.join(root, *parts))
        try:
            if os.path.commonpath([p, root]) != root:
                return None
        except Exception:
            return None
        return p

    @pyqtSlot(result=str)
    def listPlugins(self):
        try:
            root = _scripts_root()
            names = []
            for base, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if not d.startswith("_")]
                for e in files:
                    if e.endswith(".py") and not e.startswith("_"):
                        rel = os.path.relpath(os.path.join(base, e), root)
                        names.append(rel.replace(os.sep, "/"))
            return json.dumps(sorted(names))
        except Exception as e:
            return json.dumps({"error": str(e)})

    @pyqtSlot(str, result=str)
    def exists(self, filename):
        p = self._safe_path(filename)
        return json.dumps(bool(p and os.path.exists(p)))

    @pyqtSlot(str, str, result=str)
    def save(self, filename, content):
        p = self._safe_path(filename)
        if not p:
            return json.dumps({"ok": False,
                               "error": "Ungültiger Name (.py/.html nötig, kein führendes _)."})
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return json.dumps({"ok": True, "path": p})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    # ------------------------------------------------------------------
    # Analyse: Code → Formularfelder + Vorschau-HTML
    # ------------------------------------------------------------------
    def _parse_source(self, src):
        """Zerlegt Plugin-Quelltext per AST (ohne Ausführung)."""
        import ast as _ast
        try:
            tree = _ast.parse(src)
        except SyntaxError as e:
            return {"ok": False, "error": "Parse-Fehler: " + str(e)}
        known = {"NAME", "ICON", "HTML_BUTTON", "BUTTON_HEIGHT", "OPACITY",
                 "PINNED", "ALLOW_POPUP", "ALLOW_WINDOW", "RUN_AS", "MEDIA_BRIDGE",
                 "BUTTON_HTML", "WINDOW_HTML", "POPUP_HTML", "BUTTON_HTML_FILE"}
        fields = {}
        formable = True
        has_widget = False
        has_inline = False
        widget_cls = None
        for node in tree.body:
            if (isinstance(node, _ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], _ast.Name)):
                key = node.targets[0].id.upper()
                if key in known:
                    try:
                        fields[key] = _ast.literal_eval(node.value)
                        continue
                    except Exception:
                        formable = False
                        continue
                formable = False
            elif isinstance(node, (_ast.Import, _ast.ImportFrom)):
                continue
            elif isinstance(node, _ast.ClassDef) and node.name == "PluginWidget":
                has_widget = True
                widget_cls = node
                continue
            elif isinstance(node, _ast.FunctionDef) and node.name == "get_inline_html":
                has_inline = True
                formable = False  # eigene Card-Funktion, nicht formularisierbar
                continue
            elif isinstance(node, _ast.Expr) and isinstance(node.value, _ast.Constant):
                continue  # Docstring
            else:
                formable = False  # eigene Funktionen/Logik (z. B. handle_call)
        # --- Kanonische Struktur erkennen:  if mode == "Window": self.html = r-TQ ...
        def _mode_of_test(t):
            if not (isinstance(t, _ast.Compare) and len(t.comparators) == 1):
                return None
            c = t.comparators[0]
            if not (isinstance(c, _ast.Constant) and isinstance(c.value, str)):
                return None
            v = c.value.strip().lower()
            if v not in ("window", "popup"):
                return None
            return v if "id='mode'" in _ast.dump(t.left) else None

        def _largest_html(nodes, minlen=50):
            best = ""
            for n in nodes:
                for c in _ast.walk(n):
                    if isinstance(c, _ast.Constant) and isinstance(c.value, str):
                        s = c.value
                        if len(s) > len(best) and len(s) >= minlen and "<" in s:
                            best = s
            return best or None

        # Abwandlung: Modul-Variablen mit sprechenden Namen (z. B.
        # POPUP_HTML_CONTENT) den Feldern zuordnen, wenn sie HTML enthalten
        try:
            for node in tree.body:
                if (isinstance(node, _ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], _ast.Name)
                        and isinstance(node.value, _ast.Constant)
                        and isinstance(node.value.value, str)):
                    nm = node.targets[0].id.upper()
                    sv = node.value.value
                    if len(sv) > 100 and "<" in sv:
                        if "POPUP" in nm:
                            fields.setdefault("POPUP_HTML", sv)
                        elif "WINDOW" in nm or "MAIN" in nm or "BASE" in nm:
                            fields.setdefault("WINDOW_HTML", sv)
        except Exception:
            pass

        widget_simple = False
        if widget_cls is not None:
            win_c = pop_c = None
            for n in _ast.walk(widget_cls):
                if not isinstance(n, _ast.If):
                    continue
                m = _mode_of_test(n.test)
                is_elif = (len(n.orelse) == 1 and isinstance(n.orelse[0], _ast.If))
                if m == "window":
                    win_c = win_c or _largest_html(n.body, minlen=1)
                    if n.orelse and not is_elif:
                        pop_c = pop_c or _largest_html(n.orelse, minlen=1)
                elif m == "popup":
                    pop_c = pop_c or _largest_html(n.body, minlen=1)
                    if n.orelse and not is_elif:
                        win_c = win_c or _largest_html(n.orelse, minlen=1)
            if win_c is None:
                # Abwandlung: unbedingte Zuweisung (z. B. self._base_html = TQ...)
                win_c = _largest_html([widget_cls], minlen=200)
            if win_c is not None:
                fields.setdefault("WINDOW_HTML", win_c)
            if pop_c is not None:
                fields.setdefault("POPUP_HTML", pop_c)
            # "einfaches" Widget: nur __init__ → aus dem Formular reproduzierbar
            methods = [x for x in widget_cls.body if isinstance(x, _ast.FunctionDef)]
            widget_simple = (len(methods) == 1 and methods[0].name == "__init__")

        if has_widget and ("WINDOW_HTML" not in fields or not widget_simple):
            formable = False  # eigenes Widget, nicht 1:1 aus dem Formular erzeugbar

        # Fenster-HTML-Näherung: größter HTML-artiger String irgendwo im Code
        guess = None
        if has_widget and "WINDOW_HTML" not in fields:
            best = ""
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Constant) and isinstance(node.value, str):
                    s = node.value
                    low = s.lower()
                    if (len(s) > len(best) and len(s) > 200
                            and ("<html" in low or "<!doctype" in low or "<body" in low)):
                        best = s
            if best and best != fields.get("POPUP_HTML"):
                guess = best
        return {"ok": True, "fields": fields, "formable": formable,
                "hasWidget": has_widget, "hasInline": has_inline,
                "windowGuess": guess}

    @pyqtSlot(str, result=str)
    def parse(self, filename):
        """Datei laden + analysieren. Cards mit get_inline_html(mode) werden
        zusätzlich gerendert (window & popup) für die Vorschau."""
        p = self._safe_path(filename)
        if not p or not os.path.exists(p):
            return json.dumps({"ok": False, "error": "Datei nicht gefunden."})
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                src = f.read()
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
        r = self._parse_source(src)
        if not r.get("ok"):
            r["content"] = src
            return json.dumps(r)
        r["content"] = src
        if r.get("hasInline") and "BUTTON_HTML" not in r.get("fields", {}):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("editor_preview_mod", p)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                fn = getattr(mod, "get_inline_html", None)
                if callable(fn):
                    try:
                        r["cardWindow"] = fn(mode="window")
                    except Exception:
                        pass
                    try:
                        r["cardPopup"] = fn(mode="popup")
                    except Exception:
                        pass
            except Exception:
                pass
        return json.dumps(r)

    @pyqtSlot(str, result=str)
    def parseSource(self, content):
        """Live-Analyse des Code-Box-Inhalts (Quelle der Vorschau)."""
        return json.dumps(self._parse_source(content or ""))


class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        super().__init__()
        self.setWindowTitle("Plugin Editor")
        self.resize(1100, 720)
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView(central)
        self.channel = QWebChannel(self.view.page())
        self.bridge = EditorBridge(self)
        self.channel.registerObject("editor", self.bridge)
        self.view.page().setWebChannel(self.channel)
        html = EDITOR_HTML.replace("__THEME__", _detect_host_theme())
        base = QUrl.fromLocalFile(_scripts_root() + os.sep)
        self.view.setHtml(html, baseUrl=base)
        lay.addWidget(self.view)
        self.setCentralWidget(central)


# =============================================================================
# Editor-UI (HTML). Hinweis: enthält bewusst nirgends drei Anführungszeichen.
# =============================================================================
EDITOR_HTML = r'''<!DOCTYPE html>
<html data-theme="__THEME__">
<head>
<meta charset="utf-8">
<style>
  :root {
    --bg:#2E2E2E; --panel:#262626; --text:#f2f2f2; --muted:#9a9a9a;
    --border:#444; --input-bg:#1f1f1f; --accent:#3A4A6A; --accent-text:#fff;
    --list-bg:#2E2E2E; --ok:#3fa96a; --warn:#c05555;
  }
  html[data-theme="light"] {
    --bg:#f4f4f4; --panel:#ffffff; --text:#111; --muted:#666;
    --border:#ccc; --input-bg:#ffffff; --accent:#c2d1ff; --accent-text:#000;
    --list-bg:#FFFFFF;
  }
  html,body { margin:0; height:100%; }
  body { font:13px "Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text);
         display:flex; gap:10px; padding:10px; box-sizing:border-box; }
  .col { display:flex; flex-direction:column; gap:8px; min-width:0; }
  #left  { flex:1 1 46%; }
  #right { flex:1 1 54%; }
  .panel { background:var(--panel); border:1px solid var(--border); border-radius:10px;
           padding:10px; display:flex; flex-direction:column; gap:8px; }
  .panel h3 { margin:0 0 2px 0; font-size:13px; }
  .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  label { color:var(--muted); font-size:12px; }
  input[type=text], input[type=number], select, textarea {
    background:var(--input-bg); color:var(--text); border:1px solid var(--border);
    border-radius:7px; padding:5px 8px; font:inherit; }
  input[type=text] { min-width:110px; }
  input[type=number] { width:64px; }
  textarea { width:100%; box-sizing:border-box; resize:vertical;
             font:12px Consolas,monospace; white-space:pre; }
  button { background:var(--accent); color:var(--accent-text); border:none; border-radius:7px;
           padding:6px 12px; cursor:pointer; font:inherit; }
  button:hover { filter:brightness(1.12); }
  button.small { padding:4px 9px; font-size:12px; }
  .tabs { display:flex; gap:6px; }
  .tabs button { background:transparent; color:var(--muted); border:1px solid var(--border); }
  .tabs button.active { background:var(--accent); color:var(--accent-text); border-color:transparent; }
  #status { min-height:18px; font-size:12px; }
  #status.ok { color:var(--ok); } #status.err { color:var(--warn); }
  #previewWrap { flex:1; display:flex; flex-direction:column; gap:8px; min-height:0; }
  #stage { flex:1; overflow:auto; border:1px dashed var(--border); border-radius:10px;
           padding:14px; display:flex; align-items:flex-start; justify-content:center; }
  .device { background:var(--list-bg); border:1px solid var(--border); border-radius:6px;
            overflow:hidden; box-shadow:0 6px 22px rgba(0,0,0,.25); }
  .device .titlebar { height:22px; background:rgba(128,128,128,.18); display:flex;
            align-items:center; padding:0 8px; font-size:10px; color:var(--muted); gap:6px; }
  .dot { width:8px; height:8px; border-radius:50%; background:rgba(128,128,128,.45); }
  .card { border-radius:8px; padding-left:8px; padding-right:8px; box-sizing:border-box; }
  .card iframe, .win iframe { border:none; width:100%; height:100%; display:block; background:transparent; }
  .hint { font-size:11px; color:var(--muted); }
</style>
</head>
<body>
  <div class="col" id="left">
    <div class="panel">
      <h3>🛠️ Plugin erstellen / bearbeiten</h3>
      <div class="row">
        <label>Dateiname</label><input type="text" id="fname" value="Mein Plugin.py" style="flex:1">
        <label>Typ</label>
        <select id="ptype">
          <option value="card">HTML-Card (Button)</option>
          <option value="window">Fenster-Plugin (HTML)</option>
          <option value="both">Card + Fenster</option>
        </select>
      </div>
      <div class="row">
        <label>NAME</label><input type="text" id="pname" value="Mein Plugin">
        <label>ICON</label><input type="text" id="picon" value="✨" style="width:80px" title="Emoji/Text ODER Bilddatei, z. B. icon.png (relativ zur Plugin-Datei)">
        <label>HÖHE</label><input type="number" id="pheight" placeholder="auto">
        <label>OPACITY</label><input type="number" id="popacity" min="0.1" max="1" step="0.05" value="1">
      </div>
      <div class="row">
        <label><input type="checkbox" id="ppinned"> PINNED</label>
        <label><input type="checkbox" id="ppopup" checked> ALLOW_POPUP</label>
        <label><input type="checkbox" id="pwindow" checked> ALLOW_WINDOW</label>
        <label>RUN_AS</label>
        <select id="prunas"><option>widget</option><option>process</option><option>browser</option></select>
      </div>
    </div>
    <div class="panel" id="cardPanel">
      <h3>Button-HTML (Card in der Liste)</h3>
      <textarea id="cardHtml" rows="6"></textarea>
      <div class="hint">Verfügbar: media.playPause() usw., openPlugin('Name.py'), pluginCall('methode',{...},cb), window.toolbarMode</div>
    </div>
    <div class="panel" id="winPanel" style="display:none">
      <div class="row" style="justify-content:space-between">
        <h3>Fenster-HTML (Window-Inhalt)</h3>
        <label><input type="checkbox" id="sepPopup"> Popup-HTML getrennt</label>
      </div>
      <textarea id="winHtml" rows="8"></textarea>
      <div class="hint">Platzhalter __MODE__ wird zur Laufzeit durch Window/Popup ersetzt.</div>
    </div>
    <div class="panel" id="popPanel" style="display:none">
      <h3>Popup-HTML (schmale Rechtsklick-Ansicht)</h3>
      <textarea id="popHtml" rows="6"></textarea>
      <div class="hint">Wird nur im Popup verwendet; ohne Häkchen gilt das Fenster-HTML für beide.</div>
    </div>
    <div class="panel" style="flex:1; min-height:0">
      <div class="row" style="justify-content:space-between">
        <h3>Code (Quelle der Vorschau)</h3>
        <div class="row">
          <select id="loadSel" class="small"><option value="">— laden… —</option></select>
          <button class="small" id="btnSave">💾 Speichern</button>
        </div>
      </div>
      <textarea id="code" style="flex:1; min-height:120px"></textarea>
      <div id="status"></div>
    </div>
  </div>

  <div class="col" id="right">
    <div class="panel" id="previewWrap">
      <div class="row" style="justify-content:space-between">
        <div class="tabs">
          <button id="tabBtn" class="active">Button</button>
          <button id="tabWin">Window</button>
          <button id="tabPop">Popup</button>
        </div>
        <div class="row">
          <label>Vorschau-Theme</label>
          <select id="pvtheme"><option value="dark">dark</option><option value="light">light</option></select>
        </div>
      </div>
      <div id="stage"></div>
      <div class="hint" id="stageHint"></div>
    </div>
  </div>

<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
(function(){
  var TQ = '"' + '"' + '"';   // Python-Tripelquote, ohne sie hier zu schreiben
  window.onerror = function(msg, u, line){
    try {
      var s = document.getElementById('status');
      s.textContent = 'JS-Fehler: ' + msg + ' (Zeile ' + line + ')';
      s.className = 'err';
    } catch(e){}
  };
  var tab = 'btn';
  var rawMode = false;        // true: Datei mit eigenem Code — Formular erzeugt den Code NICHT neu
  var lastCardWin = null;     // von get_inline_html gerenderte Card (window), vom Laden
  var lastCardPop = null;     // dito (popup)
  var pv = null;              // Vorschau-Zustand, immer aus der CODE-BOX abgeleitet

  var el = function(id){ return document.getElementById(id); };

  el('cardHtml').value = [
    '<div style="display:flex;align-items:center;justify-content:center;height:100%;gap:10px;',
    '            font-family:system-ui;color:inherit;">',
    '  <span>✨ Mein Plugin</span>',
    '  <button onclick="media.playPause()" style="padding:4px 12px;border-radius:8px;border:none;cursor:pointer;">⏯</button>',
    '</div>'
  ].join('\n');

  el('winHtml').value = [
    '<!DOCTYPE html>',
    '<html><head><meta charset="utf-8"><style>',
    '  body { font-family: system-ui; margin: 16px; }',
    '</style></head><body>',
    '  <h2>✨ Mein Plugin (__MODE__)</h2>',
    '  <p>Inhalt hier…</p>',
    '</body></html>'
  ].join('\n');

  el('popHtml').value = [
    '<!DOCTYPE html>',
    '<html><head><meta charset="utf-8"><style>',
    '  body { font-family: system-ui; margin: 10px; font-size: 13px; }',
    '</style></head><body>',
    '  <h3>✨ Mein Plugin</h3>',
    '  <p>Kompakte Popup-Ansicht…</p>',
    '</body></html>'
  ].join('\n');

  function pyStr(s){ return JSON.stringify(String(s)); }
  function escTQ(s){ return String(s).split(TQ).join('\\"\\"\\"'); }
  function trimNL(s){ return String(s).replace(/^\n/, '').replace(/\n$/, ''); }

  // ---------- Code-Generator (Formular → Code-Box) ----------
  function buildCode(){
    var t = el('ptype').value;
    var L = [];
    L.push('# --- Plugin-Parameter (neues System) ---');
    if (el('pname').value.trim()) L.push('NAME = ' + pyStr(el('pname').value.trim()));
    if (el('picon').value.trim()) L.push('ICON = ' + pyStr(el('picon').value.trim()));
    if (t !== 'window') L.push('HTML_BUTTON = True');
    var h = parseInt(el('pheight').value, 10);
    if (h > 0) L.push('BUTTON_HEIGHT = ' + h);
    var op = parseFloat(el('popacity').value);
    if (op > 0 && op < 1) L.push('OPACITY = ' + op);
    if (el('ppinned').checked) L.push('PINNED = True');
    if (!el('ppopup').checked) L.push('ALLOW_POPUP = False');
    if (!el('pwindow').checked) L.push('ALLOW_WINDOW = False');
    if (el('prunas').value !== 'widget') L.push('RUN_AS = ' + pyStr(el('prunas').value));
    L.push('# ----------------------------------------');
    L.push('');
    if (t !== 'window') {
      L.push('BUTTON_HTML = ' + TQ);
      L.push(escTQ(el('cardHtml').value));
      L.push(TQ);
      L.push('');
    }
    // HTML-Block als Python-String: raw (r-TQ) wenn möglich, sonst escaped
    function pyBlock(content){
      var bs = String.fromCharCode(92);
      if (content.indexOf(TQ) === -1 && content.slice(-1) !== bs) {
        return { open: 'r' + TQ, body: content };
      }
      var body = content.split(bs).join(bs + bs).split(TQ).join(bs + '"' + bs + '"' + bs + '"');
      return { open: TQ, body: body };
    }
    if (t !== 'card') {
      L.push('import os');
      L.push('from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget');
      L.push('from PyQt5.QtCore import QUrl');
      L.push('from PyQt5.QtWebEngineWidgets import QWebEngineView');
      L.push('');
      L.push('');
      L.push('class PluginWidget(QMainWindow):');
      L.push('    def __init__(self, mode="Window"):');
      L.push('        super().__init__()');
      L.push('        central = QWidget()');
      L.push('        lay = QVBoxLayout(central)');
      L.push('        lay.setContentsMargins(0, 0, 0, 0)');
      L.push('        self.view = QWebEngineView(central)');
      var W = pyBlock(el('winHtml').value);
      if (el('sepPopup').checked) {
        var P = pyBlock(el('popHtml').value);
        L.push('        if mode == "Window":');
        L.push('            self.html = ' + W.open);
        L.push(W.body);
        L.push(TQ);
        L.push('        else:  # Popup');
        L.push('            self.html = ' + P.open);
        L.push(P.body);
        L.push(TQ);
      } else {
        L.push('        self.html = ' + W.open);
        L.push(W.body);
        L.push(TQ);
      }
      L.push('        html = self.html.replace("__MODE__", mode)');
      L.push('        base = QUrl.fromLocalFile(os.path.dirname(os.path.abspath(__file__)) + os.sep)');
      L.push('        self.view.setHtml(html, baseUrl=base)');
      L.push('        lay.addWidget(self.view)');
      L.push('        self.setCentralWidget(central)');
      L.push('');
    }
    return L.join('\n');
  }

  // ---------- Vorschau: IMMER aus der Code-Box abgeleitet ----------
  function buildPv(r){
    var f = (r && r.fields) || {};
    var cardWin = (typeof f.BUTTON_HTML === 'string') ? f.BUTTON_HTML
                : (r.hasInline && lastCardWin) ? lastCardWin : null;
    var cardPop = (typeof f.BUTTON_HTML === 'string') ? f.BUTTON_HTML
                : (r.hasInline && lastCardPop) ? lastCardPop : cardWin;
    var winHtml = (typeof f.WINDOW_HTML === 'string') ? f.WINDOW_HTML
                : (typeof r.windowGuess === 'string') ? r.windowGuess : null;
    return {
      ok: true,
      hasCard: !!f.HTML_BUTTON || cardWin != null,
      hasWin: !!r.hasWidget,
      cardWin: cardWin,
      cardPop: cardPop,
      winHtml: winHtml,
      popHtml: (typeof f.POPUP_HTML === 'string') ? f.POPUP_HTML : winHtml,
      guess: (typeof f.WINDOW_HTML !== 'string') && (typeof r.windowGuess === 'string'),
      height: (f.BUTTON_HEIGHT > 0) ? f.BUTTON_HEIGHT : null,
      opacity: (f.OPACITY > 0 && f.OPACITY < 1) ? f.OPACITY : null
    };
  }

  // Synchroner Mini-Parser direkt in JS: zieht BUTTON_HTML / WINDOW_HTML /
  // POPUP_HTML aus dem Code — die Vorschau funktioniert damit IMMER, auch
  // ganz ohne Backend. Die Bridge (parseSource) verfeinert nur noch.
  function localParse(code){
    var bs = String.fromCharCode(92);
    var escSeq = bs + '"' + bs + '"' + bs + '"';
    function grab(name){
      var m = code.match(new RegExp(name + '\\s*=\\s*' + TQ + '([\\s\\S]*?)' + TQ));
      return m ? m[1].split(escSeq).join(TQ) : null;
    }
    var f = {};
    var bh = grab('BUTTON_HTML');
    var wh = grab('WINDOW_HTML');
    var ph = grab('POPUP_HTML');
    if (bh !== null) f.BUTTON_HTML = bh;
    if (wh !== null) f.WINDOW_HTML = wh;
    if (ph !== null) f.POPUP_HTML = ph;
    function grabMode(which){
      var m = code.match(new RegExp('mode\\s*==\\s*"' + which + '"[^]{0,400}?self\\.(?:html|_base_html)\\s*=\\s*r?' + TQ + '([^]*?)' + TQ));
      return m ? m[1].split(escSeq).join(TQ) : null;
    }
    if (f.WINDOW_HTML == null) { var mw = grabMode('Window'); if (mw !== null) f.WINDOW_HTML = mw; }
    if (f.POPUP_HTML == null) { var mp = grabMode('Popup'); if (mp !== null) f.POPUP_HTML = mp; }
    if (f.WINDOW_HTML == null) {
      var sh = code.match(new RegExp('self\\.(?:html|_base_html)\\s*=\\s*r?' + TQ + '([^]*?)' + TQ));
      if (sh) f.WINDOW_HTML = sh[1].split(escSeq).join(TQ);
    }
    if (/HTML_BUTTON\s*=\s*True/.test(code)) f.HTML_BUTTON = true;
    var mh = code.match(/BUTTON_HEIGHT\s*=\s*(\d+)/);
    if (mh) f.BUTTON_HEIGHT = parseInt(mh[1], 10);
    var mo = code.match(/OPACITY\s*=\s*([0-9.]+)/);
    if (mo) f.OPACITY = parseFloat(mo[1]);
    return { ok: true, fields: f,
             hasWidget: /class\s+PluginWidget/.test(code),
             hasInline: /def\s+get_inline_html/.test(code),
             windowGuess: null };
  }

  var pvDeb;
  function previewFromCode(immediate){
    clearTimeout(pvDeb);
    pvDeb = setTimeout(function(){
      // 1) Sofort: lokale, synchrone Aufteilung → Vorschau steht immer
      var lr = null;
      try {
        lr = localParse(el('code').value);
        pv = buildPv(lr);
        renderStage();
      } catch(e) {
        el('stageHint').textContent = 'Vorschau-Fehler: ' + e;
      }
      // 2) Danach: Backend-Analyse verfeinert — lokale Treffer bleiben erhalten
      if (!window.editor) { return; }
      window.editor.parseSource(el('code').value, function(raw){
        try {
          var r = JSON.parse(raw);
          if (r.ok) {
            if (lr && lr.fields) {
              ['BUTTON_HTML', 'WINDOW_HTML', 'POPUP_HTML'].forEach(function(k){
                if (typeof r.fields[k] !== 'string' && typeof lr.fields[k] === 'string') {
                  r.fields[k] = lr.fields[k];
                }
              });
            }
            pv = buildPv(r); renderStage();
          }
          else { el('stageHint').textContent = 'Code hat gerade einen Syntaxfehler — Vorschau zeigt den letzten Stand.'; }
        } catch(e){}
      });
    }, immediate ? 0 : 400);
  }

  function stubHead(mode){
    return '<script>window.toolbarMode=' + JSON.stringify(mode) + ';' +
      'window.media=new Proxy({},{get:function(){return function(){};}});' +
      'window.openPlugin=function(){};window.pluginCall=function(){};<' + '/script>' +
      '<style>html,body{margin:0;padding:0;height:100%;overflow:hidden;background:transparent}<' + '/style>';
  }

  function makeCard(width, compact){
    var h = (pv && pv.height) ? pv.height : Math.round(32 * (compact ? 2.4 : 1.8));
    var pad = Math.max(4, Math.floor(h / 8));
    var wrap = document.createElement('div');
    wrap.className = 'card';
    wrap.style.width = width + 'px';
    wrap.style.height = h + 'px';
    wrap.style.paddingTop = pad + 'px';
    wrap.style.paddingBottom = pad + 'px';
    var f = document.createElement('iframe');
    f.setAttribute('scrolling', 'no');
    f.style.height = (h - 2 * pad) + 'px';
    var opCss = (pv && pv.opacity) ? '<style>body{opacity:' + pv.opacity + '}<' + '/style>' : '';
    var src = compact ? (pv && pv.cardPop) : (pv && pv.cardWin);
    f.srcdoc = stubHead(compact ? 'popup' : 'window') + opCss + (src || '');
    wrap.appendChild(f);
    return wrap;
  }

  function makeWindowFrame(w, hpx, mode, title, htmlSrc){
    var dev = document.createElement('div');
    dev.className = 'device win';
    dev.style.width = w + 'px'; dev.style.height = hpx + 'px';
    dev.style.display = 'flex'; dev.style.flexDirection = 'column';
    var tb = document.createElement('div');
    tb.className = 'titlebar';
    tb.innerHTML = '<span class="dot"></span><span class="dot"></span> ' + title;
    dev.appendChild(tb);
    var f = document.createElement('iframe');
    f.style.flex = '1';
    f.srcdoc = stubHead(mode) + String(htmlSrc || '').split('__MODE__').join(mode);
    dev.appendChild(f);
    return dev;
  }

  function renderStage(){
    document.documentElement.setAttribute('data-theme', el('pvtheme').value);
    var stage = el('stage'); stage.innerHTML = '';
    var hint = el('stageHint'); hint.textContent = '';
    if (!pv) { stage.textContent = 'Vorschau lädt…'; return; }

    if (tab === 'btn') {
      if (!pv.hasCard || !pv.cardWin) {
        stage.textContent = pv.hasWin
          ? 'Dieses Plugin hat keinen HTML-Button (normaler Listen-Button).'
          : 'Dieses Plugin ist ein reines Skript — normaler Listen-Button, keine Card.';
        return;
      }
      var box = document.createElement('div');
      box.appendChild(makeCard(560, false));
      var lbl = document.createElement('div'); lbl.className = 'hint'; lbl.style.margin = '10px 0 4px';
      lbl.textContent = 'Kompakt (Popup-Liste):'; box.appendChild(lbl);
      box.appendChild(makeCard(270, true));
      stage.appendChild(box);
      hint.textContent = 'So erscheint die Card im Hauptfenster (oben) und im Rechtsklick-Popup (unten).';
    } else if (tab === 'win') {
      if (!pv.hasWin) { stage.textContent = 'Dieses Plugin hat kein Fenster.'; return; }
      if (!pv.winHtml) { stage.textContent = 'Das Fenster-HTML liegt in eigenem Plugin-Code — Vorschau nicht möglich.'; return; }
      stage.appendChild(makeWindowFrame(620, 420, 'Window', 'Tab im Hauptfenster (~40% Bildschirm)', pv.winHtml));
      hint.textContent = 'Inhalt des Tabs im Hauptfenster.' + (pv.guess ? ' Aus dem Plugin-Code extrahiert — Näherung, Platzhalter/Theme können abweichen.' : '');
    } else {
      if (!pv.hasWin) { stage.textContent = 'Dieses Plugin hat kein Popup-Fenster.'; return; }
      if (!pv.popHtml) { stage.textContent = 'Das Fenster-/Popup-HTML liegt in eigenem Plugin-Code — Vorschau nicht möglich.'; return; }
      stage.appendChild(makeWindowFrame(270, 480, 'Popup', 'Popup (~15% Bildschirmbreite)', pv.popHtml));
      hint.textContent = 'Inhalt der schmalen Popup-Ansicht.' + (pv.guess ? ' Aus dem Plugin-Code extrahiert — Näherung.' : '');
    }
  }

  // ---------- Formular ----------
  function updatePanels(){
    var t = el('ptype').value;
    el('cardPanel').style.display = (t === 'window') ? 'none' : '';
    el('winPanel').style.display = (t === 'card') ? 'none' : '';
    el('popPanel').style.display = (t === 'card' || !el('sepPopup').checked) ? 'none' : '';
  }

  function formChanged(){
    updatePanels();
    if (!rawMode) { el('code').value = buildCode(); }
    previewFromCode();
  }

  var deb;
  ['fname','ptype','pname','picon','pheight','popacity','ppinned','ppopup','pwindow','prunas',
   'cardHtml','winHtml','popHtml','sepPopup'].forEach(function(id){
    el(id).addEventListener('input', function(){ clearTimeout(deb); deb = setTimeout(formChanged, 250); });
    el(id).addEventListener('change', function(){ clearTimeout(deb); deb = setTimeout(formChanged, 100); });
  });
  el('pvtheme').addEventListener('change', renderStage);

  // Code-Box: direkte Quelle der Vorschau (in beiden Modi)
  el('code').addEventListener('input', function(){ previewFromCode(); });

  function setTab(t, btn){
    tab = t;
    ['tabBtn','tabWin','tabPop'].forEach(function(id){ el(id).classList.remove('active'); });
    btn.classList.add('active');
    renderStage();
  }
  el('tabBtn').onclick = function(){ setTab('btn', this); };
  el('tabWin').onclick = function(){ setTab('win', this); };
  el('tabPop').onclick = function(){ setTab('pop', this); };

  // ---------- Laden / Speichern ----------
  function status(msg, ok){
    var s = el('status'); s.textContent = msg; s.className = ok ? 'ok' : 'err';
  }

  function refreshList(){
    if (!window.editor) return;
    window.editor.listPlugins(function(raw){
      try {
        var names = JSON.parse(raw);
        if (!Array.isArray(names)) return;
        var sel = el('loadSel');
        sel.innerHTML = '<option value="">— laden… —</option>';
        names.forEach(function(n){
          var o = document.createElement('option'); o.value = n; o.textContent = n;
          sel.appendChild(o);
        });
      } catch(e){}
    });
  }

  var DEFAULT_CARD = el('cardHtml').value;
  var DEFAULT_WIN = el('winHtml').value;
  var DEFAULT_POP = el('popHtml').value;

  function applyForm(r){
    var f = r.fields || {};
    // Erst zurücksetzen, damit nichts vom vorher geladenen Plugin stehen bleibt
    el('cardHtml').value = DEFAULT_CARD;
    el('winHtml').value = DEFAULT_WIN;
    el('popHtml').value = DEFAULT_POP;
    el('pname').value = ''; el('picon').value = '';
    if (typeof f.NAME === 'string') el('pname').value = f.NAME;
    if (typeof f.ICON === 'string') el('picon').value = f.ICON;
    el('pheight').value = (f.BUTTON_HEIGHT > 0) ? f.BUTTON_HEIGHT : '';
    el('popacity').value = (f.OPACITY > 0 && f.OPACITY < 1) ? f.OPACITY : 1;
    el('ppinned').checked = !!f.PINNED;
    el('ppopup').checked = (f.ALLOW_POPUP !== false);
    el('pwindow').checked = (f.ALLOW_WINDOW !== false);
    el('prunas').value = (typeof f.RUN_AS === 'string') ? f.RUN_AS : 'widget';
    if (typeof f.BUTTON_HTML === 'string') el('cardHtml').value = trimNL(f.BUTTON_HTML);
    if (typeof f.WINDOW_HTML === 'string') el('winHtml').value = trimNL(f.WINDOW_HTML);
    el('sepPopup').checked = (typeof f.POPUP_HTML === 'string');
    if (typeof f.POPUP_HTML === 'string') el('popHtml').value = trimNL(f.POPUP_HTML);
    var hasCard = !!f.HTML_BUTTON || (r.hasInline === true);
    var hasWin = !!r.hasWidget;
    el('ptype').value = (hasCard && hasWin) ? 'both' : (hasWin ? 'window' : 'card');
  }

  el('loadSel').addEventListener('change', function(){
    var n = this.value; if (!n || !window.editor) return;
    window.editor.parse(n, function(raw){
      var r;
      try { r = JSON.parse(raw); } catch(e){ status('Antwort unlesbar: ' + e, false); return; }
      el('fname').value = n;
      // Code-Box bekommt IMMER den Dateiinhalt — sie ist die Quelle der Vorschau
      if (typeof r.content === 'string') el('code').value = r.content;
      if (!r.ok) {
        rawMode = true;
        pv = null; renderStage();
        status('Geladen: ' + n + ' — ' + (r.error || 'Analyse fehlgeschlagen') + ' (Code trotzdem geladen).', false);
        return;
      }
      lastCardWin = (typeof r.cardWindow === 'string') ? r.cardWindow : null;
      lastCardPop = (typeof r.cardPopup === 'string') ? r.cardPopup : null;
      applyForm(r);
      updatePanels();
      rawMode = !r.formable;
      pv = buildPv(r);
      renderStage();
      status(r.formable
        ? 'Geladen: ' + n + ' — komplett ins Formular übernommen, direkt editierbar.'
        : 'Geladen: ' + n + ' — Vorschau aktiv. Enthält eigenen Code: gespeichert wird die Code-Box (Vorschau folgt ihr live).', true);
    });
  });

  el('btnSave').onclick = function(){
    if (!window.editor) { status('Bridge nicht verbunden.', false); return; }
    var name = el('fname').value.trim();
    var code = el('code').value;
    window.editor.exists(name, function(rawEx){
      if (JSON.parse(rawEx) && !confirm(name + ' existiert bereits. Überschreiben?')) return;
      window.editor.save(name, code, function(raw){
        var r = JSON.parse(raw);
        if (r.ok) { status('Gespeichert: ' + r.path + ' — erscheint sofort in der Liste.', true); refreshList(); }
        else status(r.error, false);
      });
    });
  };

  new QWebChannel(qt.webChannelTransport, function(ch){
    window.editor = ch.objects.editor;
    refreshList();
    el('code').value = buildCode();
    previewFromCode(true);
  });

  updatePanels();
  el('code').value = buildCode();
  previewFromCode(true);  // lokale Vorschau sofort, Bridge verfeinert später
})();
</script>
</body>
</html>
'''
