from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import QUrl, QEvent, QObject, pyqtSignal
import sys

# --- KONFIGURATION & THEMES ---

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


# --- CSS OVERRIDES ---
THEME_OVERRIDE_CSS = """
<style>
/* Global: Keine Schatten mehr erzwingen */
* { box-shadow: none !important; }

/* --- DARK THEME --- */
body.theme-dark {
  background: #2E2E2E !important;
  color: #f5f5f5 !important;
  --bg-color: #2E2E2E;
  --sidebar-bg: #252525;
  --item-bg: rgba(255,255,255,0.05);
  --border-color: rgba(255,255,255,0.1);
  --text-muted: #c5cfdc;
  --text-main: #f5f5f5;
  --hover-bg: rgba(255,255,255,0.1);
  --trash-hover: rgba(255, 100, 100, 0.2);
}

/* --- LIGHT THEME --- */
body.theme-light {
  background: #FFFFFF !important;
  color: #1f1f1f !important;
  --bg-color: #FFFFFF;
  --sidebar-bg: #F0F2F5;
  --item-bg: #ffffff;
  --border-color: #dfe3ef;
  --text-muted: #5f6b82;
  --text-main: #1f1f1f;
  --hover-bg: #e7ecf9;
  --trash-hover: #ffebeb;
}

body input, body textarea {
    background: var(--item-bg) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-main) !important;
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


class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("To-Do Plugin Pro")
        self.resize(1000, 750)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

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

        if self._current_mode == "Window":
            html = self._build_window_html(body_class)
        else:
            html = self._build_popup_html(body_class)

        self.browser.setHtml(html, QUrl("http://localhost/"))
        self.browser.loadFinished.connect(self._on_view_ready)

        app_instance = QApplication.instance()
        if app_instance is not None:
            self._theme_watcher = HostThemeWatcher(app_instance)
            self._theme_watcher.themeChanged.connect(self._on_host_theme_changed)
            self.destroyed.connect(self._cleanup_theme_watcher)

    # ---------------------------------------------------------
    # 1. WINDOW MODE HTML (Mit Folder Delete)
    # ---------------------------------------------------------
    def _build_window_html(self, body_class: str):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>To-Do Liste Pro</title>
<style>
  :root{
    --prio-high: #ef4444;
    --prio-med: #f59e0b;
    --prio-low: #10b981;
    --success: #10b981;
  }
  *{box-sizing: border-box; box-shadow: none !important; outline: none;}

  html, body{ 
      height:100%; margin:0; font-family: Inter, sans-serif; 
      overflow-x: hidden; overflow-y: hidden;
  }

  body {
    display: flex; background: var(--bg-color); color: var(--text-main);
  }

  .app-layout {
    display: flex; width: 100%; height: 100%; overflow-x: hidden;
  }

  /* SIDEBAR */
  .sidebar {
    width: 250px; background: var(--sidebar-bg);
    border-right: 1px solid var(--border-color);
    display: flex; flex-direction: column;
    padding: 20px 10px; flex-shrink: 0;
  }
  .sidebar h2 { margin: 0 0 15px 10px; font-size: 14px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 1px; }

  .folder-list { flex: 1; overflow-y: auto; overflow-x: hidden; }

  /* Neuer Style für Ordner-Zeilen */
  .folder-row {
    display: flex; justify-content: space-between; align-items: center;
    width: 100%; padding: 8px 10px;
    margin-bottom: 4px; border-radius: 6px;
    cursor: pointer; color: var(--text-main);
    transition: background 0.1s;
  }
  .folder-row:hover { background: var(--hover-bg); }
  .folder-row.active { background: var(--hover-bg); font-weight: bold; border-left: 3px solid var(--success); }

  .folder-info {
    flex: 1; display: flex; align-items: center; justify-content: space-between; padding-right: 5px; min-width: 0;
  }
  .folder-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .folder-count { font-size: 11px; color: var(--text-muted); background: var(--border-color); padding: 2px 6px; border-radius: 10px; margin-left: 8px;}

  /* Löschen Button für Ordner */
  .btn-folder-del {
    background: transparent; border: none; color: var(--text-muted);
    cursor: pointer; width: 24px; height: 24px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    opacity: 0; transition: all 0.2s; font-size: 16px; font-weight: bold;
  }
  .folder-row:hover .btn-folder-del { opacity: 1; }
  .btn-folder-del:hover { color: #ef4444; background: var(--trash-hover); }

  .add-folder-row { margin-top: 10px; display: flex; gap: 5px; }
  .add-folder-row input { flex: 1; padding: 6px; border-radius: 4px; font-size: 13px; }
  .icon-btn { background: var(--hover-bg); border: 1px solid var(--border-color); color: var(--text-main); border-radius: 4px; cursor: pointer; width: 30px; }

  /* MAIN CONTENT */
  .main { flex: 1; display: flex; flex-direction: column; padding: 20px; min-width: 0; overflow-x: hidden; }

  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
  header h1 { margin: 0; font-size: 24px; }

  .input-area {
    display: flex; gap: 10px; margin-bottom: 20px; background: var(--item-bg); padding: 10px; border-radius: 8px; border: 1px solid var(--border-color);
  }
  .input-area input { flex: 1; border: none !important; background: transparent !important; font-size: 16px; }

  .prio-select {
    background: transparent; color: var(--text-muted); border: 1px solid var(--border-color); border-radius: 6px; padding: 0 8px; cursor: pointer;
  }
  .prio-select option { background: var(--bg-color); color: var(--text-main); }

  .btn-add { background: var(--text-main); color: var(--bg-color); border: none; border-radius: 6px; padding: 0 20px; font-weight: bold; cursor: pointer; }

  .list { flex: 1; overflow-y: auto; overflow-x: hidden; }
  .item {
    display: flex; align-items: center; gap: 12px;
    padding: 12px; margin-bottom: 8px;
    background: var(--item-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    transition: transform 0.1s;
  }
  .item:hover { transform: translateX(2px); border-color: var(--text-muted); }

  .check {
    width: 22px; height: 22px; border-radius: 6px; border: 2px solid var(--text-muted);
    display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
  }
  .check.checked { background: var(--success); border-color: var(--success); color: white; }

  .prio-indicator {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  }
  .prio-high { background: var(--prio-high); box-shadow: 0 0 5px var(--prio-high); }
  .prio-med { background: var(--prio-med); }
  .prio-low { background: var(--prio-low); opacity: 0.5; }

  .text-content { flex: 1; min-width: 0; }
  .task-text { font-size: 15px; word-break: break-word; }
  .task-text.done { text-decoration: line-through; opacity: 0.5; }
  .task-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; display: flex; gap: 10px; }

  .badge { padding: 2px 6px; border-radius: 4px; background: var(--border-color); }

  .btn-del { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 16px; opacity: 0; transition: opacity 0.2s; }
  .item:hover .btn-del { opacity: 1; }
  .btn-del:hover { color: #ef4444; }

</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">

<div class="app-layout">
  <div class="sidebar">
    <h2>Ordner</h2>
    <div class="folder-list" id="folderList"></div>
    <div class="add-folder-row">
      <input id="newFolderInput" placeholder="Neuer Ordner..." />
      <button class="icon-btn" onclick="addFolder()">+</button>
    </div>
  </div>

  <div class="main">
    <header>
      <h1 id="headerTitle">Alle Aufgaben</h1>
      <button class="icon-btn" style="width:auto; padding:5px 10px;" onclick="clearDone()">Erledigte löschen</button>
    </header>

    <div class="input-area">
      <input id="newTask" placeholder="Neue Aufgabe eingeben..." />
      <select id="newPrio" class="prio-select">
        <option value="low">! Niedrig</option>
        <option value="med">!! Mittel</option>
        <option value="high">!!! Hoch</option>
      </select>
      <button class="btn-add" onclick="addTask()">Add</button>
    </div>

    <div class="list" id="taskList"></div>
  </div>
</div>

<script>
const KEY = 'todo_list_v1';
let data = { folders: [], todos: [] };
let activeFolderId = 'all'; 

function load() {
    const raw = localStorage.getItem(KEY);
    if (!raw) {
        data = { folders: [{id: 'f_default', name: 'Allgemein'}], todos: [] };
        activeFolderId = 'f_default';
        save();
        return;
    }
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
        const defaultId = 'f_default';
        data = {
            folders: [{id: defaultId, name: 'Allgemein'}],
            todos: parsed.map(t => ({...t, folderId: defaultId, prio: 'med'}))
        };
        activeFolderId = defaultId;
        save();
    } else {
        data = parsed;
        if (activeFolderId !== 'all' && !data.folders.find(f => f.id === activeFolderId)) {
            activeFolderId = 'all';
        }
    }
}

function save() { localStorage.setItem(KEY, JSON.stringify(data)); render(); }

function addFolder() {
    const inp = document.getElementById('newFolderInput');
    const name = inp.value.trim();
    if (!name) return;
    const id = 'f_' + Date.now();
    data.folders.push({id, name});
    inp.value = '';
    activeFolderId = id;
    save();
}

function deleteFolder(id, event) {
    if(event) event.stopPropagation(); // Verhindert, dass der Ordner ausgewählt wird beim Klicken

    if(!confirm('Diesen Ordner und alle darin enthaltenen Aufgaben wirklich löschen?')) return;

    // 1. Ordner entfernen
    data.folders = data.folders.filter(f => f.id !== id);

    // 2. Aufgaben in diesem Ordner entfernen
    data.todos = data.todos.filter(t => t.folderId !== id);

    // 3. Ansicht resetten, falls wir im gelöschten Ordner waren
    if(activeFolderId === id) {
        activeFolderId = 'all';
    }
    save();
}

function selectFolder(id) { activeFolderId = id; render(); }

function addTask() {
    const inp = document.getElementById('newTask');
    const prioInp = document.getElementById('newPrio');
    const text = inp.value.trim();
    if (!text) return;

    let targetFolder = activeFolderId;
    if (targetFolder === 'all') {
        targetFolder = data.folders.length > 0 ? data.folders[0].id : null;
        if(!targetFolder) { alert("Bitte erst einen Ordner erstellen!"); return; }
    }

    const newId = Date.now().toString(36) + Math.random().toString(36).substr(2);
    data.todos.push({
        id: newId, text: text, done: false, prio: prioInp.value,
        folderId: targetFolder, created: new Date().toISOString()
    });
    inp.value = ''; save();
}

function toggle(id) {
    const t = data.todos.find(x => x.id === id);
    if (t) { t.done = !t.done; save(); }
}

function del(id) {
    if(confirm('Aufgabe löschen?')) {
        data.todos = data.todos.filter(x => x.id !== id);
        save();
    }
}

function clearDone() {
    if(confirm('Alle erledigten Aufgaben im aktuellen Ordner löschen?')) {
        if (activeFolderId === 'all') {
            data.todos = data.todos.filter(t => !t.done);
        } else {
            data.todos = data.todos.filter(t => !(t.done && t.folderId === activeFolderId));
        }
        save();
    }
}

function updateText(id, txt) {
    const t = data.todos.find(x => x.id === id);
    if (t) { t.text = txt; save(); }
}

function render() {
    const fList = document.getElementById('folderList');
    fList.innerHTML = '';

    // "Alle" Button (nicht löschbar)
    const allDiv = document.createElement('div');
    const allCount = data.todos.filter(t => !t.done).length;
    allDiv.className = `folder-row ${activeFolderId === 'all' ? 'active' : ''}`;
    allDiv.innerHTML = `
        <div class="folder-info">
            <span class="folder-name">Alle Aufgaben</span> 
            <span class="folder-count">${allCount}</span>
        </div>
        <div style="width:24px;"></div> 
    `;
    allDiv.onclick = () => selectFolder('all');
    fList.appendChild(allDiv);

    // Benutzer-Ordner
    data.folders.forEach(f => {
        const div = document.createElement('div');
        const count = data.todos.filter(t => t.folderId === f.id && !t.done).length;
        div.className = `folder-row ${activeFolderId === f.id ? 'active' : ''}`;

        // Aufbau: Info-Bereich (Name+Count) + Löschen-Button
        div.innerHTML = `
            <div class="folder-info">
                <span class="folder-name">${f.name}</span>
                <span class="folder-count">${count}</span>
            </div>
            <button class="btn-folder-del" title="Ordner löschen" onclick="deleteFolder('${f.id}', event)">×</button>
        `;
        div.onclick = () => selectFolder(f.id);
        fList.appendChild(div);
    });

    const headerTitle = document.getElementById('headerTitle');
    if (activeFolderId === 'all') headerTitle.innerText = "Alle Aufgaben";
    else {
        const curr = data.folders.find(f => f.id === activeFolderId);
        headerTitle.innerText = curr ? curr.name : "Unbekannt";
    }

    const tList = document.getElementById('taskList');
    tList.innerHTML = '';

    let visibleTodos = data.todos;
    if (activeFolderId !== 'all') {
        visibleTodos = visibleTodos.filter(t => t.folderId === activeFolderId);
    }

    const prioScore = { high: 3, med: 2, low: 1 };
    visibleTodos.sort((a, b) => {
        if (a.done !== b.done) return a.done - b.done;
        const pA = prioScore[a.prio] || 1;
        const pB = prioScore[b.prio] || 1;
        return pB - pA;
    });

    visibleTodos.forEach(t => {
        const item = document.createElement('div');
        item.className = 'item';

        let folderName = '';
        if (activeFolderId === 'all') {
             const f = data.folders.find(x => x.id === t.folderId);
             if (f) folderName = `<span class="badge">${f.name}</span>`;
        }
        let prioLabel = '';
        if (t.prio === 'high') prioLabel = '<span style="color:var(--prio-high); font-weight:bold; font-size:11px;">HOCH</span>';

        item.innerHTML = `
            <div class="check ${t.done?'checked':''}" onclick="toggle('${t.id}')">${t.done?'✓':''}</div>
            <div class="prio-indicator prio-${t.prio||'low'}" title="Priorität: ${t.prio}"></div>
            <div class="text-content">
                <div class="task-text ${t.done?'done':''}" contenteditable="true" onblur="updateText('${t.id}', this.innerText)">${t.text}</div>
                <div class="task-meta">
                    ${folderName} ${prioLabel}
                </div>
            </div>
            <button class="btn-del" onclick="del('${t.id}')">×</button>
        `;
        tList.appendChild(item);
    });
}

document.getElementById('newTask').onkeydown = (e) => { if(e.key === 'Enter') addTask(); };
document.getElementById('newFolderInput').onkeydown = (e) => { if(e.key === 'Enter') addFolder(); };

load();
render();
</script>
</body>
</html>"""
        return template.replace("__BODY_CLASS__", body_class)

    # ---------------------------------------------------------
    # 2. POPUP MODE HTML (Gleich geblieben)
    # ---------------------------------------------------------
    def _build_popup_html(self, body_class: str):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>To-Do Popup</title>
<style>
  :root{
    --bg-color: #2e2e2e;
    --success: #10b981;
    --text-main: #e6eef8;
    --border-color: rgba(255,255,255,0.1);
    --prio-high: #ef4444;
    --prio-med: #f59e0b;
    --prio-low: #888;
  }
  *{ box-sizing: border-box; outline: none; box-shadow: none !important; }
  html, body { height: 100%; margin: 0; padding: 0; overflow: hidden; }
  body {
    background: var(--bg-color); color: var(--text-main);
    font-family: sans-serif; display: flex; flex-direction: column;
  }
  .app-container { display: flex; flex-direction: column; height: 100vh; padding: 12px; }

  .input-row { display: flex; gap: 8px; margin-bottom: 10px; border-bottom: 1px solid var(--border-color); padding-bottom: 5px; }
  input { flex: 1; background: transparent; border: none; color: inherit; font-size: 14px; }
  select { background: #333; color: #fff; border: 1px solid #555; border-radius: 4px; font-size: 11px; }

  .list { flex: 1; overflow-y: auto; }
  .item { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }

  .checkbox {
    width: 16px; height: 16px; border: 1px solid rgba(255,255,255,0.3); border-radius: 4px;
    margin-right: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center;
  }
  .checkbox:hover { border-color: var(--success); }

  .dot { width: 6px; height: 6px; border-radius: 50%; margin-right: 8px; }
  .dot-high { background: var(--prio-high); }
  .dot-med { background: var(--prio-med); }
  .dot-low { background: var(--prio-low); }

  .content { flex: 1; font-size: 14px; }
  .empty-msg { text-align: center; color: rgba(255,255,255,0.3); margin-top: 20px; font-size: 12px; }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">
  <div class="app-container">
    <div class="input-row">
      <input type="text" id="newInput" placeholder="Neue Aufgabe..." autocomplete="off">
      <select id="prioInput">
         <option value="low">Low</option>
         <option value="med">Med</option>
         <option value="high">High</option>
      </select>
    </div>
    <div class="list" id="todoList"></div>
  </div>

<script>
const KEY = 'todo_list_v1';
let data = { folders: [], todos: [] };

function load() {
    const raw = localStorage.getItem(KEY);
    if(raw) {
        const parsed = JSON.parse(raw);
        if(Array.isArray(parsed)) { 
             data = { folders: [{id:'def',name:'All'}], todos: parsed.map(t=>({...t, folderId:'def'})) };
        } else {
             data = parsed;
        }
    }
}
function save() { localStorage.setItem(KEY, JSON.stringify(data)); render(); }

function render() {
  const listEl = document.getElementById('todoList');
  listEl.innerHTML = '';
  const activeTodos = data.todos.filter(t => !t.done);

  const score = { high: 3, med: 2, low: 1 };
  activeTodos.sort((a,b) => (score[b.prio||'low']||1) - (score[a.prio||'low']||1));

  if (activeTodos.length === 0) {
    listEl.innerHTML = '<div class="empty-msg">Nichts zu tun!</div>';
    return;
  }

  activeTodos.forEach(todo => {
    const item = document.createElement('div');
    item.className = 'item';

    const dot = document.createElement('div');
    dot.className = 'dot dot-' + (todo.prio || 'low');

    const chk = document.createElement('div');
    chk.className = 'checkbox';
    chk.onclick = () => markDone(todo.id);

    const content = document.createElement('div');
    content.className = 'content';
    content.textContent = todo.text;

    item.appendChild(chk);
    item.appendChild(dot);
    item.appendChild(content);
    listEl.appendChild(item);
  });
}

function addTodo() {
  const text = document.getElementById('newInput').value.trim();
  const prio = document.getElementById('prioInput').value;
  if (!text) return;

  let fId = data.folders.length > 0 ? data.folders[0].id : 'default';
  if(data.folders.length === 0) data.folders.push({id: 'default', name: 'Allgemein'});

  data.todos.push({
    id: Date.now().toString(36) + Math.random().toString(36).substr(2),
    text: text, done: false, prio: prio, folderId: fId, created: new Date().toISOString()
  });
  save();
  document.getElementById('newInput').value = '';
}

function markDone(id) {
  const t = data.todos.find(x => x.id === id);
  if(t) { t.done = true; save(); }
}

document.getElementById('newInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') addTodo();
});

load();
render();
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


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PluginWidget(theme="dark", mode="Window")
    window.show()
    sys.exit(app.exec_())