from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import QUrl, QEvent, QObject, pyqtSignal
import sys

THEME_LIGHT = "light"
THEME_DARK = "dark"
SUPPORTED_THEMES = {THEME_LIGHT, THEME_DARK}


def _detect_host_theme(default=THEME_DARK):
    app = QApplication.instance()
    if app is not None:
        value = app.property("toolbar_theme")
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in SUPPORTED_THEMES:
                return lowered
    return default


class HostThemeWatcher(QObject):
    themeChanged = pyqtSignal(str)

    def __init__(self, app_instance):
        super().__init__(app_instance)
        self._app = app_instance
        if self._app is not None:
            self._app.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self._app and event.type() == QEvent.DynamicPropertyChange:
            try:
                prop_name = event.propertyName().data().decode('utf-8')
            except Exception:
                prop_name = None
            if prop_name == "toolbar_theme":
                value = self._app.property("toolbar_theme")
                if isinstance(value, str):
                    self.themeChanged.emit(value.lower())
        return super().eventFilter(watched, event)

    def cleanup(self):
        if self._app is not None:
            try:
                self._app.removeEventFilter(self)
            except Exception:
                pass
            self._app = None


THEME_OVERRIDE_CSS = """
<style>
body.theme-dark {
  background: #2E2E2E !important;
  color: #f5f5f5 !important;
}
body.theme-dark .wrap {
  background: #2f2f2f !important;
  border: 1px solid #3b3b3b !important;
  color: #f5f5f5 !important;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6) !important;
}
body.theme-dark .sub,
body.theme-dark .small,
body.theme-dark .meta {
  color: #c5cfdc !important;
}
body.theme-dark input,
body.theme-dark textarea {
  background: #3A3A3A !important;
  border: 1px solid #4d4d4d !important;
  color: #f5f5f5 !important;
}
body.theme-dark .btn {
  background: #3A4A6A !important;
  color: #ffffff !important;
}
body.theme-dark .btn.ghost {
  border-color: rgba(255,255,255,0.2) !important;
  color: #f0f4ff !important;
  background: transparent !important;
}
body.theme-dark .item {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.08) !important;
}
body.theme-dark .filter-btn {
  border-color: rgba(255,255,255,0.08) !important;
  color: #d0d4de !important;
}
body.theme-dark .filter-btn.active {
  background: rgba(255,255,255,0.12) !important;
  color: #ffffff !important;
}

body.theme-light {
  background: #FFFFFF !important;
  color: #1f1f1f !important;
}
body.theme-light .wrap {
  background: #ffffff !important;
  border: 1px solid #dfe3ef !important;
  color: #1f1f1f !important;
  box-shadow: 0 18px 36px rgba(34,51,89,0.15) !important;
}
body.theme-light .sub,
body.theme-light .small,
body.theme-light .meta {
  color: #5f6b82 !important;
}
body.theme-light input,
body.theme-light textarea {
  background: #ffffff !important;
  border: 1px solid #cfd7e6 !important;
  color: #1f1f1f !important;
}
body.theme-light .btn {
  background: #3A4A6A !important;
  color: #ffffff !important;
}
body.theme-light .btn.ghost {
  border-color: #b8c3d6 !important;
  background: #eef1fb !important;
  color: #1f1f1f !important;
}
body.theme-light .list .item,
body.theme-light .item {
  background: #f4f6fb !important;
  border: 1px solid #dfe3ef !important;
  color: #1f1f1f !important;
}
body.theme-light .check {
  border-color: #cfd7e6 !important;
}
body.theme-light .filter-btn {
  border-color: #cfd7e6 !important;
  color: #4a5873 !important;
}
body.theme-light .filter-btn.active {
  background: #e7ecf9 !important;
  color: #1f1f1f !important;
  border-color: #b7c1d8 !important;
}
</style>
"""

THEME_SCRIPT = """
<script>
(function () {
  window.applyTheme = function(theme) {
    var normalized = (theme === 'light') ? 'theme-light' : 'theme-dark';
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(normalized);
    document.documentElement.style.colorScheme = normalized === 'theme-dark' ? 'dark' : 'light';
  };
})();
</script>
"""


# JavaScript-Dialoge (alert, confirm, prompt) aktivieren
class MyPage(QWebEnginePage):
    def javaScriptAlert(self, _, msg):
        print("Alert:", msg)

    def javaScriptConfirm(self, _, msg):
        print("Confirm:", msg)
        return True  # immer "OK"

    def javaScriptPrompt(self, _, msg, default, res):
        print("Prompt:", msg)
        res(default)
        return True


class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("To-Do Plugin")
        self.resize(900, 720)

        central = QWidget()
        layout = QVBoxLayout(central)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        normalized_theme = theme.lower() if isinstance(theme, str) else None
        host_theme = _detect_host_theme(normalized_theme if normalized_theme in SUPPORTED_THEMES else THEME_DARK)
        self._current_theme = host_theme if host_theme in SUPPORTED_THEMES else THEME_DARK
        self._current_mode = mode if mode in ("Window", "Popup") else "Window"
        self._view_ready = False
        self._theme_watcher = None

        body_class = f"theme-{self._current_theme}"
        html = (
            self._build_window_html(body_class)
            if self._current_mode == "Window"
            else self._build_popup_html(body_class)
        )
        self.browser.setHtml(html, QUrl("http://localhost/"))
        self.browser.loadFinished.connect(self._on_view_ready)

        app_instance = QApplication.instance()
        if app_instance is not None:
            self._theme_watcher = HostThemeWatcher(app_instance)
            self._theme_watcher.themeChanged.connect(self._on_host_theme_changed)
            self.destroyed.connect(self._cleanup_theme_watcher)

    def _build_window_html(self, body_class: str):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>To-Do Liste</title>
<style>
  :root{
    --bg: #2e2e2e;
    --card: #5b5b5b;
    --muted: #94a3b8;
    --accent: #888888;
    --accent-2: #666666;
    --success: #10b981;
    --danger: #ef4444;
    color-scheme: dark;
  }
  *{box-sizing: border-box}
  html,body{height:100%}
  body{
    margin:0;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    background: #2e2e2e;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:28px;
    color: #e6eef8;
  }

  .wrap{
    width: min(720px, 95%);
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    border-radius: 12px;
    box-shadow: 0 8px 30px rgba(23,23,23,0.7);
    padding: 20px;
    border: 1px solid rgba(255,255,255,0.03);
  }

  header{
    display:flex;
    gap:12px;
    align-items:center;
    margin-bottom:14px;
  }
  header h1{
    margin:0;
    font-size:20px;
    letter-spacing:0.4px;
  }
  header .sub{
    color:var(--muted);
    font-size:13px;
  }

  .add-row{
    display:flex;
    gap:10px;
    margin-bottom:12px;
  }
  .add-row input{
    flex:1;
    padding:10px 12px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.03);
    color:inherit;
    border-radius:8px;
    font-size:15px;
    outline:none;
  }
  .add-row input::placeholder{ color: #8fa3bf; }
  .btn{
    padding:10px 14px;
    border-radius:8px;
    background: #777777;
    border:none;
    color:white;
    font-weight:600;
    cursor:pointer;
    user-select:none;
  }
  .btn.ghost{
    background:transparent;
    border:1px solid rgba(255,255,255,0.04);
    color:var(--muted);
  }

  .list{
    margin:6px 0 12px 0;
    min-height: 80px;
  }
  .item{
    display:flex;
    gap:12px;
    align-items:center;
    padding:10px;
    border-radius:10px;
    margin-bottom:8px;
    background: linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0.01));
    border:1px solid rgba(255,255,255,0.02);
  }
  .item.dragging{ opacity:0.6; transform:scale(0.995); }
  .item .left{
    display:flex;
    gap:10px;
    align-items:center;
    flex:1;
  }
  .check{
    width:20px;height:20px;border-radius:6px;border:1px solid rgba(255,255,255,0.06);display:inline-flex;
    align-items:center;justify-content:center;cursor:pointer;
    user-select:none;
  }
  .check.checked{ background: linear-gradient(180deg,var(--success), #059669); border: none; color:white; }
  .text{
    font-size:15px;
    word-break:break-word;
  }
  .text.done{ text-decoration:line-through; opacity:0.6; color:#9fb2cf }
  .meta{
    display:flex;
    gap:8px;
    align-items:center;
    color:var(--muted);
    font-size:13px;
  }
  .controls{
    display:flex;
    gap:8px;
    align-items:center;
  }
  .icon-btn{
    border:none;background:transparent;color:var(--muted);cursor:pointer;padding:6px;border-radius:6px;
  }
  .icon-btn:hover{ background: rgba(255,255,255,0.02); color: white; }

  .footer{
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:12px;
    margin-top:8px;
    flex-wrap:wrap;
  }
  .filters{
    display:flex;
    gap:8px;
  }
  .filter-btn{
    padding:6px 10px;border-radius:8px;border:1px solid rgba(255,255,255,0.03);background:transparent;color:var(--muted);cursor:pointer;
  }
  .filter-btn.active{ background: rgba(255,255,255,0.03); color: white; border-color: rgba(255,255,255,0.06); }

  .small{ font-size:13px;color:var(--muted) }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">
  <div class="wrap" role="application" aria-label="To-Do Liste">
    <header>
      <div>
        <h1>To-Do Liste</h1>
        <div class="sub">Schnell Aufgaben erfassen • lokal gespeichert</div>
      </div>
    </header>

    <div class="add-row">
      <input id="newTask" placeholder="Neue Aufgabe eingeben und Enter drücken..." aria-label="Neue Aufgabe" />
      <button id="addBtn" class="btn">Hinzufügen</button>
    </div>

    <div class="list" id="list" aria-live="polite"></div>

    <div class="footer">
      <div class="small" id="count">0 Aufgaben</div>
      <div class="filters" role="tablist" aria-label="Filter">
        <button class="filter-btn active" data-filter="all">Alle</button>
        <button class="filter-btn" data-filter="active">Aktiv</button>
        <button class="filter-btn" data-filter="done">Erledigt</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button id="clearDone" class="btn ghost">Erledigte löschen</button>
        <button id="clearAll" class="btn ghost" title="Alle Aufgaben löschen">Alle löschen</button>
      </div>
    </div>
  </div>

<script>
const STORAGE_KEY = 'todo_list_v1';
let todos = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
let filter = 'all';
const listEl = document.getElementById('list');
const newTask = document.getElementById('newTask');
const addBtn = document.getElementById('addBtn');
const countEl = document.getElementById('count');

function save(){
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
  render();
}
function addTask(text){
  if(!text || !text.trim()) return;
  todos.push({ id: Date.now() + Math.random().toString(36).slice(2,8), text: text.trim(), done: false, created: new Date().toISOString() });
  save();
}
function toggleDone(id){ const it = todos.find(t => t.id === id); if(it) it.done = !it.done; save(); }
function removeTask(id){ todos = todos.filter(t => t.id !== id); save(); }
function clearDone(){ todos = todos.filter(t => !t.done); save(); }
function clearAll(){ if(!confirm('Wirklich alle Aufgaben löschen?')) return; todos = []; save(); }
function editTask(id, newText){ const it = todos.find(t => t.id === id); if(it) it.text = newText.trim(); save(); }
function reorder(newOrderIds){ const map = Object.fromEntries(todos.map(t => [t.id, t])); todos = newOrderIds.map(id => map[id]).filter(Boolean); save(); }
function filteredList(){ if(filter === 'all') return todos; if(filter === 'active') return todos.filter(t => !t.done); return todos.filter(t => t.done); }

function render(){
  listEl.innerHTML = '';
  const arr = filteredList();
  for(const t of arr){
    const item = document.createElement('div');
    item.className = 'item'; item.draggable = true; item.dataset.id = t.id;
    const left = document.createElement('div'); left.className = 'left';
    const chk = document.createElement('div'); chk.className = 'check' + (t.done ? ' checked' : ''); chk.title = t.done ? 'Markierung entfernen' : 'Als erledigt markieren'; chk.setAttribute('role','button');
    chk.addEventListener('click', () => toggleDone(t.id)); chk.innerHTML = t.done ? '✓' : '';
    const text = document.createElement('div'); text.className = 'text' + (t.done ? ' done' : ''); text.textContent = t.text; text.contentEditable = true; text.spellcheck = false; text.title = 'Zum bearbeiten klicken';
    text.addEventListener('blur', () => { if(text.textContent.trim() === '') { text.textContent = t.text; } else if(text.textContent.trim() !== t.text) { editTask(t.id, text.textContent); } });
    text.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ e.preventDefault(); text.blur(); } else if (e.key === 'Escape'){ text.textContent = t.text; text.blur(); } });
    left.appendChild(chk); left.appendChild(text);
    const controls = document.createElement('div'); controls.className = 'controls';
    const meta = document.createElement('div'); meta.className = 'meta'; const createdDate = new Date(t.created); meta.textContent = createdDate.toLocaleString();
    const delBtn = document.createElement('button'); delBtn.className = 'icon-btn'; delBtn.title = 'Löschen'; delBtn.innerHTML = '🗑'; delBtn.addEventListener('click', () => { if(confirm('Aufgabe löschen?')) removeTask(t.id); });
    controls.appendChild(meta); controls.appendChild(delBtn);
    item.appendChild(left); item.appendChild(controls); listEl.appendChild(item);
    item.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', t.id); item.classList.add('dragging'); });
    item.addEventListener('dragend', () => { item.classList.remove('dragging'); });
    item.addEventListener('dragover', (e) => { e.preventDefault(); const after = getDragAfterElement(listEl, e.clientY); const dragging = document.querySelector('.dragging'); if(after == null) { listEl.appendChild(dragging); } else { listEl.insertBefore(dragging, after); } });
    item.tabIndex = 0; item.addEventListener('keydown', (e) => { if(e.key === 'Delete') removeTask(t.id); if(e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggleDone(t.id); } });
  }
  const total = todos.length; const remaining = todos.filter(t => !t.done).length;
  countEl.textContent = `${remaining} offen — ${total} insgesamt`;
}
function getDragAfterElement(container, y){
  const draggableElements = [...container.querySelectorAll('.item:not(.dragging)')];
  return draggableElements.reduce((closest, child) => {
    const box = child.getBoundingClientRect(); const offset = y - box.top - box.height / 2;
    if(offset < 0 && offset > closest.offset){ return { offset: offset, element: child }; } else { return closest; }
  }, { offset: Number.NEGATIVE_INFINITY }).element;
}
addBtn.addEventListener('click', () => { addTask(newTask.value); newTask.value = ''; newTask.focus(); });
newTask.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ addTask(newTask.value); newTask.value = ''; } });
document.getElementById('clearDone').addEventListener('click', () => clearDone());
document.getElementById('clearAll').addEventListener('click', () => clearAll());
document.querySelectorAll('.filter-btn').forEach(btn => { btn.addEventListener('click', () => { document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); btn.classList.add('active'); filter = btn.dataset.filter; render(); }); });
listEl.addEventListener('drop', (e) => { e.preventDefault(); const ids = [...listEl.querySelectorAll('.item')].map(i => i.dataset.id); reorder(ids); });
render();
window.addEventListener('keydown', (e) => { if(e.ctrlKey && e.key.toLowerCase() === 'k'){ e.preventDefault(); newTask.focus(); } if(e.ctrlKey && e.key.toLowerCase() === 'b'){ e.preventDefault(); clearDone(); } });
</script>
</body>
</html>"""
        return template.replace("__BODY_CLASS__", body_class)
    def _build_popup_html(self, body_class: str):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>To-Do Liste</title>
<style>
  :root{
    --bg: #2e2e2e;
    --card: #5b5b5b;
    --muted: #94a3b8;
    --accent: #888888;
    --accent-2: #666666;
    --success: #10b981;
    --danger: #ef4444;
    color-scheme: dark;
  }
  *{box-sizing: border-box}
  html,body{height:100%}
  body{
    margin:0;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
    background: #2e2e2e;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:16px;
    color: #e6eef8;
  }

  .wrap{
    width: min(375px, 98vw);
    max-width: 375px;
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    border-radius: 12px;
    box-shadow: 0 8px 30px rgba(23,23,23,0.7);
    padding: 12px;
    border: 1px solid rgba(255,255,255,0.03);
    display: flex;
    flex-direction: column;
  }

  header{
    display:flex;
    flex-direction: column;
    gap:2px;
    align-items:flex-start;
    margin-bottom:10px;
    padding-bottom:4px;
    border-bottom:1px solid rgba(255,255,255,0.03);
  }
  header h1{
    margin:0;
    font-size:17px;
    letter-spacing:0.4px;
  }
  header .sub{
    color:var(--muted);
    font-size:12px;
    margin-top:3px;
  }

  .add-row{
    display:flex;
    flex-direction: column;
    gap:8px;
    margin-bottom:10px;
  }
  .add-row input{
    width:100%;
    padding:9px 10px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.03);
    color:inherit;
    border-radius:8px;
    font-size:15px;
    outline:none;
  }
  .add-row input::placeholder{ color: #8fa3bf; }
  .btn{
    width:100%;
    padding:9px 0;
    border-radius:8px;
    background: #777777;
    border:none;
    color:white;
    font-weight:600;
    cursor:pointer;
    user-select:none;
  }
  .btn.ghost{
    background:transparent;
    border:1px solid rgba(255,255,255,0.04);
    color:var(--muted);
  }

  .list{
    margin:4px 0 9px 0;
    min-height: 60px;
  }
  .item{
    display:flex;
    flex-direction:column;
    gap:8px;
    align-items:flex-start;
    padding:7px;
    border-radius:10px;
    margin-bottom:8px;
    background: linear-gradient(180deg, rgba(255,255,255,0.015), rgba(255,255,255,0.01));
    border:1px solid rgba(255,255,255,0.02);
  }
  .item.dragging{ opacity:0.6; transform:scale(0.995); }
  .item .left{
    display:flex;
    gap:8px;
    align-items:center;
    flex:1;
    width:100%;
  }
  .check{
    width:18px;height:18px;border-radius:5px;border:1px solid rgba(255,255,255,0.06);display:inline-flex;
    align-items:center;justify-content:center;cursor:pointer;
    user-select:none;
    font-size:14px;
  }
  .check.checked{ background: linear-gradient(180deg,var(--success), #059669); border: none; color:white; }
  .text{
    font-size:14px;
    word-break:break-word;
    flex:1;
  }
  .text.done{ text-decoration:line-through; opacity:0.6; color:#9fb2cf }
  .meta{
    display:flex;
    gap:6px;
    align-items:center;
    color:var(--muted);
    font-size:12px;
    margin-top:3px;
  }
  .controls{
    display:flex;
    gap:7px;
    align-items:center;
    margin-top:4px;
  }
  .icon-btn{
    border:none;background:transparent;color:var(--muted);cursor:pointer;padding:5px;border-radius:6px;font-size:17px;
  }
  .icon-btn:hover{ background: rgba(255,255,255,0.02); color: white; }

  .footer{
    display:flex;
    flex-direction:column;
    gap:10px;
    margin-top:6px;
    flex-wrap:wrap;
    align-items:flex-start;
  }
  .filters{
    display:flex;
    gap:7px;
    width:100%;
  }
  .filter-btn{
    padding:5px 8px;border-radius:8px;border:1px solid rgba(255,255,255,0.03);background:transparent;color:var(--muted);cursor:pointer;
    font-size:12px;
    width:auto;
  }
  .filter-btn.active{ background: rgba(255,255,255,0.03); color: white; border-color: rgba(255,255,255,0.06); }

  .small{ font-size:12px;color:var(--muted) }
  @media (max-width: 430px) {
    body { padding:4px; }
    .wrap { width: 100vw; max-width: 100vw; border-radius:0; box-shadow:none;}
  }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">
  <div class="wrap" role="application" aria-label="To-Do Liste">
    <header>
      <div>
        <h1>To-Do Liste</h1>
        <div class="sub">Schnell Aufgaben erfassen • lokal gespeichert</div>
      </div>
    </header>

    <div class="add-row">
      <input id="newTask" placeholder="Neue Aufgabe eingeben und Enter drücken..." aria-label="Neue Aufgabe" />
      <button id="addBtn" class="btn">Hinzufügen</button>
    </div>

    <div class="list" id="list" aria-live="polite"></div>

    <div class="footer">
      <div class="small" id="count">0 Aufgaben</div>
      <div class="filters" role="tablist" aria-label="Filter">
        <button class="filter-btn active" data-filter="all">Alle</button>
        <button class="filter-btn" data-filter="active">Aktiv</button>
        <button class="filter-btn" data-filter="done">Erledigt</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;width:100%">
        <button id="clearDone" class="btn ghost">Erledigte löschen</button>
        <button id="clearAll" class="btn ghost" title="Alle Aufgaben löschen">Alle löschen</button>
      </div>
    </div>
  </div>

<script>
const STORAGE_KEY = 'todo_list_v1';
let todos = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
let filter = 'all';
const listEl = document.getElementById('list');
const newTask = document.getElementById('newTask');
const addBtn = document.getElementById('addBtn');
const countEl = document.getElementById('count');

function save(){
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
  render();
}
function addTask(text){
  if(!text || !text.trim()) return;
  todos.push({ id: Date.now() + Math.random().toString(36).slice(2,8), text: text.trim(), done: false, created: new Date().toISOString() });
  save();
}
function toggleDone(id){ const it = todos.find(t => t.id === id); if(it) it.done = !it.done; save(); }
function removeTask(id){ todos = todos.filter(t => t.id !== id); save(); }
function clearDone(){ todos = todos.filter(t => !t.done); save(); }
function clearAll(){ if(!confirm('Wirklich alle Aufgaben löschen?')) return; todos = []; save(); }
function editTask(id, newText){ const it = todos.find(t => t.id === id); if(it) it.text = newText.trim(); save(); }
function reorder(newOrderIds){ const map = Object.fromEntries(todos.map(t => [t.id, t])); todos = newOrderIds.map(id => map[id]).filter(Boolean); save(); }
function filteredList(){ if(filter === 'all') return todos; if(filter === 'active') return todos.filter(t => !t.done); return todos.filter(t => t.done); }

function render(){
  listEl.innerHTML = '';
  const arr = filteredList();
  for(const t of arr){
    const item = document.createElement('div');
    item.className = 'item'; item.draggable = true; item.dataset.id = t.id;
    const left = document.createElement('div'); left.className = 'left';
    const chk = document.createElement('div'); chk.className = 'check' + (t.done ? ' checked' : ''); chk.title = t.done ? 'Markierung entfernen' : 'Als erledigt markieren'; chk.setAttribute('role','button');
    chk.addEventListener('click', () => toggleDone(t.id)); chk.innerHTML = t.done ? '✓' : '';
    const text = document.createElement('div'); text.className = 'text' + (t.done ? ' done' : ''); text.textContent = t.text; text.contentEditable = true; text.spellcheck = false; text.title = 'Zum bearbeiten klicken';
    text.addEventListener('blur', () => { if(text.textContent.trim() === '') { text.textContent = t.text; } else if(text.textContent.trim() !== t.text) { editTask(t.id, text.textContent); } });
    text.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ e.preventDefault(); text.blur(); } else if (e.key === 'Escape'){ text.textContent = t.text; text.blur(); } });
    left.appendChild(chk); left.appendChild(text);
    const controls = document.createElement('div'); controls.className = 'controls';
    const meta = document.createElement('div'); meta.className = 'meta'; const createdDate = new Date(t.created); meta.textContent = createdDate.toLocaleString();
    const delBtn = document.createElement('button'); delBtn.className = 'icon-btn'; delBtn.title = 'Löschen'; delBtn.innerHTML = '🗑'; delBtn.addEventListener('click', () => { if(confirm('Aufgabe löschen?')) removeTask(t.id); });
    controls.appendChild(meta); controls.appendChild(delBtn);
    item.appendChild(left); item.appendChild(controls); listEl.appendChild(item);
    item.addEventListener('dragstart', (e) => { e.dataTransfer.setData('text/plain', t.id); item.classList.add('dragging'); });
    item.addEventListener('dragend', () => { item.classList.remove('dragging'); });
    item.addEventListener('dragover', (e) => { e.preventDefault(); const after = getDragAfterElement(listEl, e.clientY); const dragging = document.querySelector('.dragging'); if(after == null) { listEl.appendChild(dragging); } else { listEl.insertBefore(dragging, after); } });
    item.tabIndex = 0; item.addEventListener('keydown', (e) => { if(e.key === 'Delete') removeTask(t.id); if(e.key === ' ' || e.key === 'Enter') { e.preventDefault(); toggleDone(t.id); } });
  }
  const total = todos.length; const remaining = todos.filter(t => !t.done).length;
  countEl.textContent = `${remaining} offen — ${total} insgesamt`;
}
function getDragAfterElement(container, y){
  const draggableElements = [...container.querySelectorAll('.item:not(.dragging)')];
  return draggableElements.reduce((closest, child) => {
    const box = child.getBoundingClientRect(); const offset = y - box.top - box.height / 2;
    if(offset < 0 && offset > closest.offset){ return { offset: offset, element: child }; } else { return closest; }
  }, { offset: Number.NEGATIVE_INFINITY }).element;
}
addBtn.addEventListener('click', () => { addTask(newTask.value); newTask.value = ''; newTask.focus(); });
newTask.addEventListener('keydown', (e) => { if(e.key === 'Enter'){ addTask(newTask.value); newTask.value = ''; } });
document.getElementById('clearDone').addEventListener('click', () => clearDone());
document.getElementById('clearAll').addEventListener('click', () => clearAll());
document.querySelectorAll('.filter-btn').forEach(btn => { btn.addEventListener('click', () => { document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active')); btn.classList.add('active'); filter = btn.dataset.filter; render(); }); });
listEl.addEventListener('drop', (e) => { e.preventDefault(); const ids = [...listEl.querySelectorAll('.item')].map(i => i.dataset.id); reorder(ids); });
render();
window.addEventListener('keydown', (e) => { if(e.ctrlKey && e.key.toLowerCase() === 'k'){ e.preventDefault(); newTask.focus(); } if(e.ctrlKey && e.key.toLowerCase() === 'b'){ e.preventDefault(); clearDone(); } });
</script>
</body>
</html>
"""
        return template.replace("__BODY_CLASS__", body_class)

    def _on_view_ready(self, ok: bool):
        self._view_ready = bool(ok)
        if ok:
            self._apply_theme_to_web(self._current_theme)

    def _apply_theme_to_web(self, theme: str):
        if not self._view_ready:
            return
        if theme not in SUPPORTED_THEMES:
            theme = THEME_DARK
        script = f'window.applyTheme && window.applyTheme("{theme}")'
        try:
            self.browser.page().runJavaScript(script)
        except Exception:
            pass

    def _on_host_theme_changed(self, theme: str):
        normalized = theme if theme in SUPPORTED_THEMES else THEME_DARK
        self._current_theme = normalized
        self._apply_theme_to_web(normalized)

    def _cleanup_theme_watcher(self):
        if self._theme_watcher:
            self._theme_watcher.cleanup()
            self._theme_watcher.deleteLater()
            self._theme_watcher = None

    def closeEvent(self, event):
        self._cleanup_theme_watcher()
        super().closeEvent(event)