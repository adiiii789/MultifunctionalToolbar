# --- Plugin-Parameter (neues System) ---
NAME = "Plugin Editor"
ICON = "🛠️"
ALLOW_POPUP = False
# ----------------------------------------

# Editor zum einfachen Erstellen von Plugins — mit Live-Vorschau, wie das
# Plugin als Button (Card), im Hauptfenster (Window) und im Popup aussieht.
# Links Formular + generierter Code, rechts Vorschau mit Dark/Light-Schalter.
# Speichern legt die Datei direkt im scripts-Ordner ab (Toolbar lädt sie
# durch den Datei-Watcher sofort).

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
    """Backend des Editors: Dateien im scripts-Ordner lesen/schreiben."""

    def _safe_path(self, filename):
        name = os.path.basename((filename or "").strip())
        if not name or not (name.endswith(".py") or name.endswith(".html")):
            return None
        if name.startswith("_"):
            return None  # mit "_" beginnende Dateien sind in der Toolbar versteckt
        return os.path.join(_scripts_root(), name)

    @pyqtSlot(result=str)
    def listPlugins(self):
        try:
            root = _scripts_root()
            names = sorted(e for e in os.listdir(root)
                           if e.endswith(".py") and not e.startswith("_")
                           and os.path.isfile(os.path.join(root, e)))
            return json.dumps(names)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @pyqtSlot(str, result=str)
    def load(self, filename):
        p = self._safe_path(filename)
        if not p or not os.path.exists(p):
            return json.dumps({"ok": False, "error": "Datei nicht gefunden."})
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return json.dumps({"ok": True, "content": f.read()})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def exists(self, filename):
        p = self._safe_path(filename)
        return json.dumps(bool(p and os.path.exists(p)))

    @pyqtSlot(str, result=str)
    def parse(self, filename):
        """Zerlegt ein Plugin per AST in Formularfelder.

        formable=True nur, wenn die Datei vollständig durch das Formular
        darstellbar ist (nur bekannte Konstanten, Imports und das generierte
        PluginWidget). Sonst wird der Roh-Code geliefert, damit beim Laden
        nichts verloren geht.
        """
        import ast as _ast
        p = self._safe_path(filename)
        if not p or not os.path.exists(p):
            return json.dumps({"ok": False, "error": "Datei nicht gefunden."})
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                src = f.read()
            tree = _ast.parse(src)
        except Exception as e:
            return json.dumps({"ok": False, "error": "Parse-Fehler: " + str(e)})

        known = {"NAME", "ICON", "HTML_BUTTON", "BUTTON_HEIGHT", "OPACITY",
                 "PINNED", "ALLOW_POPUP", "ALLOW_WINDOW", "RUN_AS", "MEDIA_BRIDGE",
                 "BUTTON_HTML", "WINDOW_HTML", "POPUP_HTML", "BUTTON_HTML_FILE"}
        fields = {}
        formable = True
        has_widget = False
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
                continue
            elif isinstance(node, _ast.Expr) and isinstance(node.value, _ast.Constant):
                continue  # Docstring/Kommentar-Ausdruck
            else:
                formable = False  # eigene Funktionen/Logik (z. B. handle_call)
        if has_widget and "WINDOW_HTML" not in fields:
            formable = False  # eigenes Widget, nicht aus dem Formular erzeugbar
        return json.dumps({"ok": True, "fields": fields, "formable": formable,
                           "hasWidget": has_widget, "content": src})

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
  /* --- Vorschau --- */
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
      <h3>🛠️ Plugin erstellen</h3>
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
      <textarea id="cardHtml" rows="7"></textarea>
      <div class="hint">Verfügbar: media.playPause() usw., openPlugin('Name.py'), window.toolbarMode</div>
    </div>
    <div class="panel" id="winPanel" style="display:none">
      <div class="row" style="justify-content:space-between">
        <h3>Fenster-HTML (Window-Inhalt)</h3>
        <label><input type="checkbox" id="sepPopup"> Popup-HTML getrennt</label>
      </div>
      <textarea id="winHtml" rows="9"></textarea>
      <div class="hint">Platzhalter __MODE__ wird zur Laufzeit durch Window/Popup ersetzt.</div>
    </div>
    <div class="panel" id="popPanel" style="display:none">
      <h3>Popup-HTML (schmale Rechtsklick-Ansicht)</h3>
      <textarea id="popHtml" rows="7"></textarea>
      <div class="hint">Wird nur im Popup verwendet; ohne Häkchen gilt das Fenster-HTML für beide.</div>
    </div>
    <div class="panel" style="flex:1; min-height:0">
      <div class="row" style="justify-content:space-between">
        <h3>Generierter Code</h3>
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
  var tab = 'btn';
  var rawMode = false;  // true: geladener Fremd-Code, Formular überschreibt ihn nicht
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

  // ---------- Code-Generator ----------
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
    if (t !== 'card') {
      L.push('import os');
      L.push('from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget');
      L.push('from PyQt5.QtCore import QUrl');
      L.push('from PyQt5.QtWebEngineWidgets import QWebEngineView');
      L.push('');
      L.push('WINDOW_HTML = ' + TQ);
      L.push(escTQ(el('winHtml').value));
      L.push(TQ);
      L.push('');
      if (el('sepPopup').checked) {
        L.push('POPUP_HTML = ' + TQ);
        L.push(escTQ(el('popHtml').value));
        L.push(TQ);
        L.push('');
      }
      L.push('');
      L.push('class PluginWidget(QMainWindow):');
      L.push('    def __init__(self, mode="Window"):');
      L.push('        super().__init__()');
      L.push('        central = QWidget()');
      L.push('        lay = QVBoxLayout(central)');
      L.push('        lay.setContentsMargins(0, 0, 0, 0)');
      L.push('        self.view = QWebEngineView(central)');
      if (el('sepPopup').checked) {
        L.push('        src = POPUP_HTML if str(mode).lower() == "popup" else WINDOW_HTML');
        L.push('        html = src.replace("__MODE__", mode)');
      } else {
        L.push('        html = WINDOW_HTML.replace("__MODE__", mode)');
      }
      L.push('        base = QUrl.fromLocalFile(os.path.dirname(os.path.abspath(__file__)) + os.sep)');
      L.push('        self.view.setHtml(html, baseUrl=base)');
      L.push('        lay.addWidget(self.view)');
      L.push('        self.setCentralWidget(central)');
      L.push('');
    }
    return L.join('\n');
  }

  // ---------- Vorschau ----------
  function stubHead(mode){
    return '<script>window.toolbarMode=' + JSON.stringify(mode) + ';' +
      'window.media=new Proxy({},{get:function(){return function(){};}});' +
      'window.openPlugin=function(){};<' + '/script>' +
      '<style>html,body{margin:0;padding:0;height:100%;overflow:hidden;background:transparent}<' + '/style>';
  }

  function cardHeights(compact){
    var h = parseInt(el('pheight').value, 10);
    if (!(h > 0)) h = Math.round(32 * (compact ? 2.4 : 1.8));
    var pad = Math.max(4, Math.floor(h / 8));
    return {h:h, pad:pad};
  }

  function makeCard(width, compact){
    var m = cardHeights(compact);
    var wrap = document.createElement('div');
    wrap.className = 'card';
    wrap.style.width = width + 'px';
    wrap.style.height = m.h + 'px';
    wrap.style.paddingTop = m.pad + 'px';
    wrap.style.paddingBottom = m.pad + 'px';
    var f = document.createElement('iframe');
    f.setAttribute('scrolling', 'no');
    f.style.height = (m.h - 2 * m.pad) + 'px';
    var op = parseFloat(el('popacity').value);
    var opCss = (op > 0 && op < 1) ? '<style>body{opacity:' + op + '}<' + '/style>' : '';
    f.srcdoc = stubHead(compact ? 'popup' : 'window') + opCss + el('cardHtml').value;
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
    var srcHtml = (htmlSrc == null) ? el('winHtml').value : htmlSrc;
    f.srcdoc = stubHead(mode) + String(srcHtml).split('__MODE__').join(mode);
    dev.appendChild(f);
    return dev;
  }

  function render(){
    document.documentElement.setAttribute('data-theme', el('pvtheme').value);
    var t = el('ptype').value;
    el('cardPanel').style.display = (t === 'window') ? 'none' : '';
    el('winPanel').style.display = (t === 'card') ? 'none' : '';
    el('popPanel').style.display = (t === 'card' || !el('sepPopup').checked) ? 'none' : '';
    if (!rawMode) { el('code').value = buildCode(); }

    var stage = el('stage'); stage.innerHTML = '';
    var hint = el('stageHint');
    if (tab === 'btn') {
      if (t === 'window') { stage.textContent = 'Dieser Typ hat keinen HTML-Button (normaler Listen-Button).'; hint.textContent=''; return; }
      var box = document.createElement('div');
      box.appendChild(makeCard(560, false));
      var lbl = document.createElement('div'); lbl.className='hint'; lbl.style.margin='10px 0 4px';
      lbl.textContent = 'Kompakt (Popup-Liste):'; box.appendChild(lbl);
      box.appendChild(makeCard(270, true));
      stage.appendChild(box);
      hint.textContent = 'So erscheint die Card im Hauptfenster (oben) und im Rechtsklick-Popup (unten).';
    } else if (tab === 'win') {
      if (t === 'card') { stage.textContent = 'Reine Card-Plugins haben kein Fenster.'; hint.textContent=''; return; }
      stage.appendChild(makeWindowFrame(620, 420, 'Window', 'Tab im Hauptfenster (~40% Bildschirm)', el('winHtml').value));
      hint.textContent = 'Inhalt des Tabs im Hauptfenster.';
    } else {
      if (t === 'card') { stage.textContent = 'Reine Card-Plugins haben kein Popup-Fenster.'; hint.textContent=''; return; }
      var popSrc = el('sepPopup').checked ? el('popHtml').value : el('winHtml').value;
      stage.appendChild(makeWindowFrame(270, 480, 'Popup', 'Popup (~15% Bildschirmbreite)', popSrc));
      hint.textContent = el('sepPopup').checked
        ? 'Inhalt der schmalen Popup-Ansicht (eigenes Popup-HTML).'
        : 'Inhalt der schmalen Popup-Ansicht (nutzt das Fenster-HTML).';
    }
  }

  function setTab(t, btn){
    tab = t;
    ['tabBtn','tabWin','tabPop'].forEach(function(id){ el(id).classList.remove('active'); });
    btn.classList.add('active');
    render();
  }
  el('tabBtn').onclick = function(){ setTab('btn', this); };
  el('tabWin').onclick = function(){ setTab('win', this); };
  el('tabPop').onclick = function(){ setTab('pop', this); };

  var deb;
  ['fname','ptype','pname','picon','pheight','popacity','ppinned','ppopup','pwindow','prunas',
   'cardHtml','winHtml','popHtml','sepPopup','pvtheme'].forEach(function(id){
    el(id).addEventListener('input', function(){ clearTimeout(deb); deb = setTimeout(render, 250); });
    el(id).addEventListener('change', function(){ clearTimeout(deb); deb = setTimeout(render, 100); });
  });

  // ---------- Speichern / Laden ----------
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

  function trimNL(s){ return String(s).replace(/^\n/, '').replace(/\n$/, ''); }

  el('loadSel').addEventListener('change', function(){
    var n = this.value; if (!n || !window.editor) return;
    window.editor.parse(n, function(raw){
      var r = JSON.parse(raw);
      if (!r.ok) { status(r.error, false); return; }
      el('fname').value = n;
      var f = r.fields || {};

      // Felder übernehmen, die die Datei tatsächlich setzt
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

      var hasCard = !!f.HTML_BUTTON;
      var hasWin = !!r.hasWidget;
      el('ptype').value = (hasCard && hasWin) ? 'both' : (hasWin ? 'window' : 'card');

      if (r.formable) {
        rawMode = false;  // Formular erzeugt den Code neu — direkt editierbar
        render();
        status('Geladen: ' + n + ' — ins Formular übernommen, direkt editierbar.', true);
      } else {
        rawMode = true;   // eigener Code: Code-Box zeigt das Original, bleibt maßgeblich
        el('code').value = r.content;
        render();
        status('Geladen: ' + n + ' — enthält eigenen Code. Gespeichert wird der Code links; das Formular dient nur der Vorschau.', true);
      }
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
  });

  render();
})();
</script>
</body>
</html>
'''
