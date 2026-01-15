from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import QUrl, QEvent, QObject, pyqtSignal
import sys
import json

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
  --col-bg: #2a2a2a; 
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
  --col-bg: #f4f5f7;
}

body input, body textarea, body select {
    background: var(--item-bg) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-main) !important;
}
/* Damit Kalender-Icon im Dark Mode sichtbar bleibt */
::-webkit-calendar-picker-indicator {
    filter: invert(1);
    opacity: 0.6;
    cursor: pointer;
}
body.theme-light ::-webkit-calendar-picker-indicator {
    filter: invert(0);
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
        self.setWindowTitle("To-Do Plugin Pro (Realtime Deadlines)")
        self.resize(1100, 800)

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
    # 1. WINDOW MODE HTML (Mit Realtime Deadlines)
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
    --urgent: #f59e0b;
    --overdue: #ef4444;
  }
  *{box-sizing: border-box; box-shadow: none !important; outline: none;}

  html, body{ 
      height:100%; margin:0; font-family: Inter, sans-serif; 
      overflow: hidden; 
  }

  body { display: flex; background: var(--bg-color); color: var(--text-main); }

  .app-layout { display: flex; width: 100%; height: 100%; overflow: hidden; }

  /* SIDEBAR */
  .sidebar {
    width: 240px; background: var(--sidebar-bg);
    border-right: 1px solid var(--border-color);
    display: flex; flex-direction: column;
    padding: 20px 10px; flex-shrink: 0;
  }
  .sidebar h2 { margin: 0 0 15px 10px; font-size: 13px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 1px; }

  .folder-list { flex: 1; overflow-y: auto; overflow-x: hidden; }

  .folder-row {
    display: flex; justify-content: space-between; align-items: center;
    width: 100%; padding: 8px 10px;
    margin-bottom: 4px; border-radius: 6px;
    cursor: pointer; color: var(--text-main);
    transition: background 0.1s;
  }
  .folder-row:hover { background: var(--hover-bg); }
  .folder-row.active { background: var(--hover-bg); font-weight: bold; border-left: 3px solid var(--success); }

  .folder-info { flex: 1; display: flex; align-items: center; justify-content: space-between; padding-right: 5px; min-width: 0; }
  .folder-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .folder-count { font-size: 11px; color: var(--text-muted); background: var(--border-color); padding: 2px 6px; border-radius: 10px; margin-left: 8px;}

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

  /* MAIN CONTENT */
  .main { flex: 1; display: flex; flex-direction: column; padding: 20px; min-width: 0; height: 100%; }

  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 15px; flex-shrink: 0;}
  header h1 { margin: 0; font-size: 22px; }

  .header-controls { display: flex; gap: 10px; }

  .view-toggle {
    display: flex; background: var(--item-bg); border: 1px solid var(--border-color);
    border-radius: 6px; overflow: hidden;
  }
  .view-btn {
    padding: 6px 12px; cursor: pointer; border: none; background: transparent; color: var(--text-muted); font-size: 13px; font-weight: 600;
  }
  .view-btn.active { background: var(--hover-bg); color: var(--text-main); }
  .view-btn:hover:not(.active) { background: rgba(0,0,0,0.05); }

  .icon-btn { background: var(--hover-bg); border: 1px solid var(--border-color); color: var(--text-main); border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0 10px;}

  /* INPUT AREA */
  .input-area {
    display: flex; gap: 10px; margin-bottom: 15px; background: var(--item-bg); padding: 10px; border-radius: 8px; border: 1px solid var(--border-color); flex-shrink: 0; flex-wrap: wrap; align-items: center;
  }
  .input-main-row { display: flex; flex: 1; gap: 10px; width: 100%; align-items: center; }

  .input-area input[type="text"] { flex: 1; border: none !important; background: transparent !important; font-size: 15px; }

  .prio-select { background: transparent; color: var(--text-muted); border: 1px solid var(--border-color); border-radius: 6px; padding: 4px 8px; cursor: pointer; height: 32px; }
  .prio-select option { background: var(--bg-color); color: var(--text-main); }

  .btn-add { background: var(--text-main); color: var(--bg-color); border: none; border-radius: 6px; padding: 0 20px; font-weight: bold; cursor: pointer; height: 32px; }

  /* Deadline Input Styling */
  .deadline-wrapper { display: flex; align-items: center; gap: 8px; padding-left: 8px; border-left: 1px solid var(--border-color); height: 32px;}
  .dl-checkbox-label { font-size: 12px; color: var(--text-muted); cursor: pointer; user-select: none; display: flex; align-items: center; gap: 4px;}
  .dl-input { background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 4px; padding: 2px 5px; font-size: 12px; display: none; }
  .dl-input.visible { display: block; }

  /* --- DEADLINE BADGES --- */
  .dl-badge {
      display: inline-flex; align-items: center; gap: 4px;
      font-size: 11px; padding: 2px 6px; border-radius: 4px;
      margin-right: 8px; transition: background 0.3s, color 0.3s;
  }
  .dl-normal { color: var(--text-muted); background: var(--border-color); }
  .dl-urgent { color: #fff; background: var(--urgent); font-weight: bold; }
  .dl-overdue { color: #fff; background: var(--overdue); font-weight: bold; animation: pulse 2s infinite; }

  @keyframes pulse { 0% {opacity:1;} 50% {opacity:0.8;} 100% {opacity:1;} }

  /* --- LIST VIEW STYLES --- */
  .list-view { flex: 1; overflow-y: auto; overflow-x: hidden; display: block; }
  .item {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 12px; margin-bottom: 6px;
    background: var(--item-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    transition: transform 0.1s;
  }
  .item:hover { transform: translateX(2px); border-color: var(--text-muted); }

  .check {
    width: 20px; height: 20px; border-radius: 5px; border: 2px solid var(--text-muted);
    display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
  }
  .check.checked { background: var(--success); border-color: var(--success); color: white; font-size: 12px; }

  .prio-indicator { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .prio-high { background: var(--prio-high); box-shadow: 0 0 5px var(--prio-high); }
  .prio-med { background: var(--prio-med); }
  .prio-low { background: var(--prio-low); opacity: 0.5; }

  .text-content { flex: 1; min-width: 0; }
  .task-text { font-size: 14px; word-break: break-word; }
  .task-text.done { text-decoration: line-through; opacity: 0.5; }
  .task-meta { font-size: 10px; color: var(--text-muted); margin-top: 4px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;}
  .badge { padding: 1px 5px; border-radius: 3px; background: var(--border-color); }

  .btn-del { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 16px; opacity: 0; transition: opacity 0.2s; }
  .item:hover .btn-del { opacity: 1; }
  .btn-del:hover { color: #ef4444; }

  /* --- KANBAN BOARD STYLES --- */
  .board-view { 
      flex: 1; display: none; overflow-x: auto; overflow-y: hidden;
      gap: 15px; padding-bottom: 10px; height: 100%;
  }

  .kanban-col {
      flex: 1; min-width: 260px; max-width: 350px;
      background: var(--col-bg);
      border-radius: 8px;
      display: flex; flex-direction: column;
      border: 1px solid var(--border-color);
      height: 100%;
  }

  .col-header {
      padding: 12px; font-weight: bold; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px;
      border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between;
      background: rgba(0,0,0,0.02);
  }
  .col-count { background: var(--border-color); border-radius: 10px; padding: 2px 8px; font-size: 11px; color: var(--text-main); }

  .col-body {
      flex: 1; overflow-y: auto; padding: 10px;
      display: flex; flex-direction: column; gap: 8px;
  }

  .board-card {
      background: var(--item-bg); border: 1px solid var(--border-color);
      border-radius: 6px; padding: 10px; cursor: grab;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      transition: transform 0.2s, box-shadow 0.2s;
  }
  .board-card:active { cursor: grabbing; }
  .board-card:hover { border-color: var(--text-muted); box-shadow: 0 2px 5px rgba(0,0,0,0.1); }

  .card-top { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .card-text { font-size: 14px; line-height: 1.4; margin-bottom: 8px; color: var(--text-main); }
  .card-text.done { text-decoration: line-through; opacity: 0.6; }
  .card-footer { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }

  .drag-over { background: var(--hover-bg); border: 2px dashed var(--text-muted); }

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
      <div class="header-controls">
        <div class="view-toggle">
            <button class="view-btn active" id="btnViewList" onclick="switchView('list')">Liste</button>
            <button class="view-btn" id="btnViewBoard" onclick="switchView('board')">Trello</button>
        </div>
        <button class="icon-btn" title="Erledigte löschen" onclick="clearDone()">Clear Done</button>
      </div>
    </header>

    <div class="input-area">
      <div class="input-main-row">
          <input type="text" id="newTask" placeholder="Neue Aufgabe eingeben..." />

          <select id="newPrio" class="prio-select">
            <option value="low">! Niedrig</option>
            <option value="med" selected>!! Mittel</option>
            <option value="high">!!! Hoch</option>
          </select>

          <div class="deadline-wrapper">
             <label class="dl-checkbox-label">
                <input type="checkbox" id="hasDeadlineToggle" onchange="toggleDateInput()"> Deadline?
             </label>
             <input type="datetime-local" id="deadlineInput" class="dl-input" />
          </div>

          <button class="btn-add" onclick="addTask()">Add</button>
      </div>
    </div>

    <div class="list-view" id="listView"></div>

    <div class="board-view" id="boardView">
        <div class="kanban-col" ondragover="allowDrop(event)" ondrop="drop(event, 'todo')" ondragleave="removeDragStyle(event)">
            <div class="col-header"><span style="border-left: 3px solid #888; padding-left:8px;">To Do</span><span id="cnt-todo" class="col-count">0</span></div>
            <div class="col-body" id="col-todo"></div>
        </div>
        <div class="kanban-col" ondragover="allowDrop(event)" ondrop="drop(event, 'doing')" ondragleave="removeDragStyle(event)">
            <div class="col-header"><span style="border-left: 3px solid #f59e0b; padding-left:8px;">In Progress</span><span id="cnt-doing" class="col-count">0</span></div>
            <div class="col-body" id="col-doing"></div>
        </div>
        <div class="kanban-col" ondragover="allowDrop(event)" ondrop="drop(event, 'done')" ondragleave="removeDragStyle(event)">
            <div class="col-header"><span style="border-left: 3px solid #10b981; padding-left:8px;">Done</span><span id="cnt-done" class="col-count">0</span></div>
            <div class="col-body" id="col-done"></div>
        </div>
    </div>

  </div>
</div>

<script>
const KEY = 'todo_list_v2_kanban'; 
let data = { folders: [], todos: [] };
let activeFolderId = 'all'; 
let currentView = 'list'; 

function load() {
    let raw = localStorage.getItem(KEY);
    if (!raw) {
        const oldRaw = localStorage.getItem('todo_list_v1');
        if (oldRaw) {
            const oldData = JSON.parse(oldRaw);
            if(Array.isArray(oldData)) {
                 data = { folders: [{id: 'f_default', name: 'Allgemein'}], todos: oldData.map(t => ({...t, folderId: 'f_default'})) };
            } else {
                 data = oldData;
            }
        } else {
            data = { folders: [{id: 'f_default', name: 'Allgemein'}], todos: [] };
            activeFolderId = 'f_default';
        }
    } else {
        data = JSON.parse(raw);
    }
    // Migration
    data.todos.forEach(t => {
        if (!t.status) t.status = t.done ? 'done' : 'todo';
        if (!t.deadline) t.deadline = null; 
    });
    if (activeFolderId !== 'all' && !data.folders.find(f => f.id === activeFolderId)) {
        activeFolderId = 'all';
    }
}

function save() { localStorage.setItem(KEY, JSON.stringify(data)); render(); }

// --- UI HELPER & REALTIME UPDATE ---
function toggleDateInput() {
    const chk = document.getElementById('hasDeadlineToggle');
    const inp = document.getElementById('deadlineInput');
    if (chk.checked) {
        inp.classList.add('visible');
        inp.focus();
    } else {
        inp.classList.remove('visible');
        inp.value = ''; 
    }
}

function getDeadlineInfo(isoString) {
    if (!isoString) return null;
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = date - now;
    const diffHrs = diffMs / (1000 * 60 * 60);
    const diffDays = diffMs / (1000 * 60 * 60 * 24);

    const formatted = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});

    let status = 'normal'; 
    let relativeText = '';

    if (diffMs < 0) {
        status = 'overdue';
        const overdueDays = Math.abs(Math.ceil(diffDays));
        if (overdueDays < 1) relativeText = "Seit heute überfällig";
        else relativeText = `Seit ${Math.floor(Math.abs(diffDays))} Tagen überfällig`;
    } else if (diffHrs < 24) {
        status = 'urgent';
        const h = Math.floor(diffHrs);
        if (h === 0) {
            const m = Math.floor(diffMs / (1000 * 60));
            relativeText = `In ${m} Min.`;
        }
        else relativeText = `In ca. ${h} Std.`;
    } else {
        relativeText = formatted;
    }

    return { formatted, status, relativeText };
}

function getDeadlineHtml(isoString) {
    const info = getDeadlineInfo(isoString);
    if (!info) return '';
    // WICHTIG: data-deadline Attribut für Realtime-Updates
    return `<span class="dl-badge dl-${info.status}" data-deadline="${isoString}" title="${info.formatted}">⏰ ${info.relativeText}</span>`;
}

// Diese Funktion sucht alle Badges im DOM und aktualisiert Text/Farbe
function updateRealtimeDeadlines() {
    const badges = document.querySelectorAll('.dl-badge[data-deadline]');
    badges.forEach(badge => {
        const iso = badge.getAttribute('data-deadline');
        if (iso) {
            const info = getDeadlineInfo(iso);
            if (info) {
                // Klasse aktualisieren (Farbe ändert sich sofort)
                badge.className = `dl-badge dl-${info.status}`;
                // Text aktualisieren
                badge.innerHTML = `⏰ ${info.relativeText}`;
            }
        }
    });
}

// --- DRAG AND DROP ---
function drag(ev, id) {
    ev.dataTransfer.setData("text/plain", id);
    ev.dataTransfer.effectAllowed = "move";
}
function allowDrop(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.add('drag-over');
}
function removeDragStyle(ev) {
    ev.currentTarget.classList.remove('drag-over');
}
function drop(ev, newStatus) {
    ev.preventDefault();
    ev.currentTarget.classList.remove('drag-over');
    const id = ev.dataTransfer.getData("text/plain");
    const t = data.todos.find(x => x.id === id);
    if (t) {
        t.status = newStatus;
        t.done = (newStatus === 'done');
        save();
    }
}

// --- VIEW SWITCHING ---
function switchView(mode) {
    currentView = mode;
    document.getElementById('btnViewList').className = mode === 'list' ? 'view-btn active' : 'view-btn';
    document.getElementById('btnViewBoard').className = mode === 'board' ? 'view-btn active' : 'view-btn';
    const listEl = document.getElementById('listView');
    const boardEl = document.getElementById('boardView');
    if (mode === 'list') {
        listEl.style.display = 'block';
        boardEl.style.display = 'none';
    } else {
        listEl.style.display = 'none';
        boardEl.style.display = 'flex';
    }
    render();
}

// --- ACTIONS ---
function addFolder() {
    const inp = document.getElementById('newFolderInput');
    const name = inp.value.trim();
    if (!name) return;
    const id = 'f_' + Date.now();
    data.folders.push({id, name});
    inp.value = ''; activeFolderId = id; save();
}

function deleteFolder(id, event) {
    if(event) event.stopPropagation();
    if(!confirm('Ordner wirklich löschen?')) return;
    data.folders = data.folders.filter(f => f.id !== id);
    data.todos = data.todos.filter(t => t.folderId !== id);
    if(activeFolderId === id) activeFolderId = 'all';
    save();
}

function selectFolder(id) { activeFolderId = id; render(); }

function addTask() {
    const inp = document.getElementById('newTask');
    const prioInp = document.getElementById('newPrio');
    const hasDeadline = document.getElementById('hasDeadlineToggle').checked;
    const deadlineVal = document.getElementById('deadlineInput').value;

    const text = inp.value.trim();
    if (!text) return;

    let targetFolder = activeFolderId;
    if (targetFolder === 'all') {
        targetFolder = data.folders.length > 0 ? data.folders[0].id : null;
        if(!targetFolder) { alert("Bitte erst einen Ordner erstellen!"); return; }
    }

    let finalDeadline = null;
    if (hasDeadline && deadlineVal) {
        finalDeadline = new Date(deadlineVal).toISOString();
    }

    const newId = Date.now().toString(36) + Math.random().toString(36).substr(2);
    data.todos.push({
        id: newId, text: text, done: false, status: 'todo',
        prio: prioInp.value, folderId: targetFolder, 
        created: new Date().toISOString(),
        deadline: finalDeadline
    });

    inp.value = '';
    document.getElementById('hasDeadlineToggle').checked = false;
    toggleDateInput(); 
    save();
}

function toggle(id) {
    const t = data.todos.find(x => x.id === id);
    if (t) { 
        t.done = !t.done; 
        if (t.done) t.status = 'done'; else t.status = 'todo'; 
        save(); 
    }
}
function del(id) {
    if(confirm('Aufgabe löschen?')) {
        data.todos = data.todos.filter(x => x.id !== id);
        save();
    }
}
function clearDone() {
    if(confirm('Erledigte löschen?')) {
        const condition = (t) => {
            const folderMatch = activeFolderId === 'all' || t.folderId === activeFolderId;
            return !(t.done && folderMatch);
        };
        data.todos = data.todos.filter(condition);
        save();
    }
}
function updateText(id, txt) {
    const t = data.todos.find(x => x.id === id);
    if (t) { t.text = txt; save(); }
}

// --- RENDERER ---
function render() {
    renderFolders();
    const headerTitle = document.getElementById('headerTitle');
    if (activeFolderId === 'all') headerTitle.innerText = "Alle Aufgaben";
    else {
        const curr = data.folders.find(f => f.id === activeFolderId);
        headerTitle.innerText = curr ? curr.name : "Unbekannt";
    }

    let visibleTodos = data.todos;
    if (activeFolderId !== 'all') {
        visibleTodos = visibleTodos.filter(t => t.folderId === activeFolderId);
    }

    if (currentView === 'list') renderList(visibleTodos);
    else renderBoard(visibleTodos);
}

function renderFolders() {
    const fList = document.getElementById('folderList');
    fList.innerHTML = '';
    const allDiv = document.createElement('div');
    const allCount = data.todos.filter(t => !t.done).length;
    allDiv.className = `folder-row ${activeFolderId === 'all' ? 'active' : ''}`;
    allDiv.innerHTML = `
        <div class="folder-info"><span class="folder-name">Alle Aufgaben</span> <span class="folder-count">${allCount}</span></div>
        <div style="width:24px;"></div> 
    `;
    allDiv.onclick = () => selectFolder('all');
    fList.appendChild(allDiv);

    data.folders.forEach(f => {
        const div = document.createElement('div');
        const count = data.todos.filter(t => t.folderId === f.id && !t.done).length;
        div.className = `folder-row ${activeFolderId === f.id ? 'active' : ''}`;
        div.innerHTML = `
            <div class="folder-info"><span class="folder-name">${f.name}</span><span class="folder-count">${count}</span></div>
            <button class="btn-folder-del" title="Ordner löschen" onclick="deleteFolder('${f.id}', event)">×</button>
        `;
        div.onclick = () => selectFolder(f.id);
        fList.appendChild(div);
    });
}

function renderList(todos) {
    const tList = document.getElementById('listView');
    tList.innerHTML = '';
    const prioScore = { high: 3, med: 2, low: 1 };

    const sorted = [...todos].sort((a, b) => {
        if (a.done !== b.done) return a.done - b.done;

        if (!a.done) {
             const now = new Date().getTime();
             const aDl = a.deadline ? new Date(a.deadline).getTime() : Infinity;
             const bDl = b.deadline ? new Date(b.deadline).getTime() : Infinity;
             const aOver = aDl < now;
             const bOver = bDl < now;
             if (aOver !== bOver) return bOver - aOver; 
        }

        const pA = prioScore[a.prio] || 1;
        const pB = prioScore[b.prio] || 1;
        return pB - pA;
    });

    sorted.forEach(t => {
        const item = document.createElement('div');
        item.className = 'item';

        let folderName = '';
        if (activeFolderId === 'all') {
             const f = data.folders.find(x => x.id === t.folderId);
             if (f) folderName = `<span class="badge">${f.name}</span>`;
        }

        const deadlineHtml = t.done ? '' : getDeadlineHtml(t.deadline);

        item.innerHTML = `
            <div class="check ${t.done?'checked':''}" onclick="toggle('${t.id}')">${t.done?'✓':''}</div>
            <div class="prio-indicator prio-${t.prio||'low'}" title="${t.prio}"></div>
            <div class="text-content">
                <div class="task-text ${t.done?'done':''}" contenteditable="true" onblur="updateText('${t.id}', this.innerText)">${t.text}</div>
                <div class="task-meta">
                    ${deadlineHtml} ${folderName}
                </div>
            </div>
            <button class="btn-del" onclick="del('${t.id}')">×</button>
        `;
        tList.appendChild(item);
    });
}

function renderBoard(todos) {
    const cols = { todo: document.getElementById('col-todo'), doing: document.getElementById('col-doing'), done: document.getElementById('col-done') };
    Object.values(cols).forEach(c => c.innerHTML = '');
    const groups = { todo: [], doing: [], done: [] };
    const prioScore = { high: 3, med: 2, low: 1 };

    todos.sort((a, b) => (prioScore[b.prio]||1) - (prioScore[a.prio]||1));
    todos.forEach(t => {
        let s = t.status || (t.done ? 'done' : 'todo');
        if(!groups[s]) s = 'todo';
        groups[s].push(t);
    });

    document.getElementById('cnt-todo').innerText = groups.todo.length;
    document.getElementById('cnt-doing').innerText = groups.doing.length;
    document.getElementById('cnt-done').innerText = groups.done.length;

    const createCard = (t) => {
        const card = document.createElement('div');
        card.className = 'board-card';
        card.draggable = true;
        card.ondragstart = (e) => drag(e, t.id);

        let folderBadge = '';
        if (activeFolderId === 'all') {
             const f = data.folders.find(x => x.id === t.folderId);
             if (f) folderBadge = `<span class="badge" style="font-size:10px;">${f.name}</span>`;
        }

        const deadlineHtml = t.done ? '' : getDeadlineHtml(t.deadline);

        card.innerHTML = `
            <div class="card-top">
                <div class="prio-indicator prio-${t.prio||'low'}"></div>
                <button style="border:none;background:none;color:#888;cursor:pointer;" onclick="del('${t.id}')">×</button>
            </div>
            <div class="card-text ${t.done?'done':''}">${t.text}</div>
            <div class="card-footer">
               ${deadlineHtml} ${folderBadge}
            </div>
        `;
        return card;
    };

    groups.todo.forEach(t => cols.todo.appendChild(createCard(t)));
    groups.doing.forEach(t => cols.doing.appendChild(createCard(t)));
    groups.done.forEach(t => cols.done.appendChild(createCard(t)));
}

document.getElementById('newTask').onkeydown = (e) => { if(e.key === 'Enter') addTask(); };
document.getElementById('newFolderInput').onkeydown = (e) => { if(e.key === 'Enter') addFolder(); };

load();
switchView('list'); 

// --- REALTIME TIMER STARTEN (Alle 10 Sekunden) ---
setInterval(updateRealtimeDeadlines, 10000);

</script>
</body>
</html>"""
        return template.replace("__BODY_CLASS__", body_class)

    # ---------------------------------------------------------
    # 2. POPUP MODE HTML (Auch angepasst für Live-Anzeige)
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
    --overdue: #ef4444;
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

  .content { flex: 1; font-size: 14px; display: flex; flex-direction: column;}
  .dl-mini { font-size: 10px; color: #888; margin-top: 2px; }
  .dl-overdue { color: var(--overdue); font-weight: bold; }

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
const KEY = 'todo_list_v2_kanban'; 
let data = { folders: [], todos: [] };

function load() {
    const raw = localStorage.getItem(KEY);
    if(raw) data = JSON.parse(raw);
    else {
        // Fallback für leere DB
        const old = localStorage.getItem('todo_list_v1');
        if(old && JSON.parse(old).length) data = {folders:[{id:'d',name:'All'}], todos:JSON.parse(old)};
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

    let dlHtml = '';
    if(todo.deadline) {
        // data-deadline auch hier für Konsistenz (auch wenn wir im Popup evtl nicht das volle Skript nutzen, schadet es nicht)
        dlHtml = `<span class="dl-mini" data-deadline="${todo.deadline}">...</span>`;
    }

    content.innerHTML = `<span>${todo.text}</span>${dlHtml}`;

    item.appendChild(chk);
    item.appendChild(dot);
    item.appendChild(content);
    listEl.appendChild(item);
  });
  updateRealtimeDeadlines(); // Einmal direkt beim Render aufrufen
}

// Gleiche Logic wie im Main Window, nur angepasst für Popup-Style
function updateRealtimeDeadlines() {
    const now = new Date();
    document.querySelectorAll('.dl-mini[data-deadline]').forEach(el => {
        const d = new Date(el.getAttribute('data-deadline'));
        const isOver = d < now;
        const txt = d.toLocaleDateString() + ' ' + d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
        el.innerText = '⏰ ' + txt;
        if(isOver) el.classList.add('dl-overdue');
        else el.classList.remove('dl-overdue');
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
    text: text, done: false, status: 'todo', prio: prio, folderId: fId, 
    created: new Date().toISOString(),
    deadline: null
  });
  save();
  document.getElementById('newInput').value = '';
}

function markDone(id) {
  const t = data.todos.find(x => x.id === id);
  if(t) { 
      t.done = true; 
      t.status = 'done'; 
      save(); 
  }
}

document.getElementById('newInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') addTodo();
});

load();
render();
// Auch im Popup einen Timer setzen
setInterval(updateRealtimeDeadlines, 10000);
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