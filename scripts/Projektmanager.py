from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
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
                prop_name = event.propertyName().data().decode("utf-8")
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
* { box-shadow: none; box-sizing: border-box; }

/* --- DARK THEME --- */
body.theme-dark {
  background: radial-gradient(circle at top, #23233a 0, #12121a 45%, #080810 100%) !important;
  color: #e0e6ed !important;
  --bg-color: #12121a;
  --sidebar-bg: #25262b;
  --card-bg: rgba(23, 24, 34, 0.92);
  --card-border: rgba(255,255,255,0.06);
  --card-header-bg: linear-gradient(135deg, rgba(79,172,254,0.25), rgba(0,242,254,0.08));
  --input-bg: rgba(5,7,14,0.9);
  --border-color: rgba(255,255,255,0.08);
  --text-muted: #9aa0a6;
  --text-main: #f4f7ff;
  --accent-color: #4facfe;
  --accent-grad: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  --accent-soft: rgba(79,172,254,0.12);
  --success-color: #00c851;
  --success-soft: rgba(0,200,81,0.12);
  --danger-color: #ff4444;
  --danger-soft: rgba(255,68,68,0.12);
  --warning-color: #ffc107;
  --warning-soft: rgba(255,193,7,0.16);
  --timeline-line: rgba(255,255,255,0.15);
  --row-alt: rgba(255,255,255,0.02);
  --chip-bg: rgba(255,255,255,0.06);
}

/* --- LIGHT THEME --- */
body.theme-light {
  background: radial-gradient(circle at top, #ffffff 0, #f3f4fb 40%, #e7e9f5 100%) !important;
  color: #2b2c31 !important;
  --bg-color: #f3f4f8;
  --sidebar-bg: #ffffff;
  --card-bg: #ffffff;
  --card-border: #dde1f0;
  --card-header-bg: linear-gradient(135deg, rgba(102,126,234,0.12), rgba(118,75,162,0.06));
  --input-bg: #f5f6fb;
  --border-color: #d3d8ea;
  --text-muted: #6c757d;
  --text-main: #212529;
  --accent-color: #4c6fff;
  --accent-grad: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --accent-soft: rgba(76,111,255,0.10);
  --success-color: #2ecc71;
  --success-soft: rgba(46,204,113,0.16);
  --danger-color: #e74c3c;
  --danger-soft: rgba(231,76,60,0.16);
  --warning-color: #f1c40f;
  --warning-soft: rgba(241,196,15,0.18);
  --timeline-line: #d6d9e0;
  --row-alt: #f8f9fc;
  --chip-bg: rgba(33,37,41,0.04);
}

body input, body textarea, body select {
    background: var(--input-bg) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-main) !important;
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
}

/* Zusatzstyles für nächste Meilenstein-Anzeige */
.next-ms {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
}
.next-ms-label { font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: .06em; }
.next-ms-name { color: var(--text-main); font-weight: 600; }
.next-ms-days { margin-left: 4px; font-weight: 600; }

/* Badge / Chip */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.badge-success { background: var(--success-soft); color: var(--success-color); }
.badge-danger { background: var(--danger-soft); color: var(--danger-color); }
.badge-warning { background: var(--warning-soft); color: var(--warning-color); }
.badge-neutral { background: var(--chip-bg); color: var(--text-muted); }

.chip-small {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 999px;
  background: var(--chip-bg);
}

/* Button-Styles */
.btn {
  border: none; border-radius: 999px; padding: 6px 14px;
  font-size: 12px; font-weight: 600; cursor: pointer;
  transition: transform 0.08s ease, box-shadow 0.12s ease, opacity 0.12s ease;
}
.btn-primary {
  background: var(--accent-grad);
  color: white;
  box-shadow: 0 6px 14px rgba(0,0,0,0.16);
}
.btn-primary:hover { transform: translateY(-1px); opacity: 0.96; }
.btn-primary:active { transform: translateY(0); box-shadow: 0 3px 8px rgba(0,0,0,0.18); }

.btn-ghost {
  background: transparent;
  color: var(--text-muted);
  padding-inline: 8px;
}
.btn-ghost:hover { opacity: 0.85; }

</style>
"""

THEME_SCRIPT = """
<script>
(function () {
  window.applyTheme = function(theme) {
    var normalized = (theme === 'light') ? 'theme-light' : 'theme-dark';
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(normalized);
  };
})();
</script>
"""


class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("Milestone Master Pro")
        self.resize(1100, 800)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        normalized_theme = theme.lower() if isinstance(theme, str) else None
        host_theme = _detect_host_theme(
            normalized_theme if normalized_theme in SUPPORTED_THEMES else THEME_DARK
        )
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
    # WINDOW MODE HTML – VOLLES DASHBOARD
    # ---------------------------------------------------------
    def _build_window_html(self, body_class: str):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Milestone Master</title>
<style>
  html, body { 
      height: 100%;
      margin: 0; font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif; 
  }

  body {
    display: flex; flex-direction: column;
    background: var(--bg-color); color: var(--text-main);
    transition: background 0.3s, color 0.3s;
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
    width: 100%;
    display: flex;
    flex-direction: column;
    height: 100vh;
    padding: 16px 20px;
    box-sizing: border-box;
    gap: 16px;
  }

  header {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    align-items: stretch;
  }

  .card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
  }

  .card-header-strip {
    height: 4px;
    background: var(--card-header-bg);
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }

  .card-body {
    padding: 12px 16px 14px 16px;
  }

  .project-info {
    flex: 2 1 260px;
  }

  .stat-card {
    flex: 1 1 150px;
  }

  .card-body-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 10px 14px 14px 14px;
  }

  .project-info h1 {
    margin: 0 0 4px 0;
    font-size: 22px;
    background: var(--accent-grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 800;
    letter-spacing: .01em;
  }

  .subtitle {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .08em;
    margin-bottom: 6px;
  }

  .date-range-inputs {
    display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    margin-bottom: 4px;
    font-size: 12px;
  }
  .date-range-inputs label {
    font-size: 11px; color: var(--text-muted);
    text-transform: uppercase; font-weight: 600;
    letter-spacing: .06em;
  }
  .date-range-inputs input {
    min-width: 135px; /* Etwas breiter für sichere Anzeige */
  }
  .date-help {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .big-number { font-size: 28px; font-weight: 700; }
  .sub-text { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .08em; }

  .bottom {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1 1 auto;
    min-height: 0;
  }

  /* --- TIMELINE STYLES --- */

  .timeline-card {
    background: var(--card-bg);
    border-radius: 14px;
    border: 1px solid var(--card-border);
    padding: 10px 16px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .timeline-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 11px;
    color: var(--text-muted);
  }

  .timeline-header-title {
    text-transform: uppercase;
    letter-spacing: .08em;
    font-weight: 600;
  }

  .timeline-container-inner {
    margin-top: 6px;
    border-radius: 14px;
    padding: 10px 4px;
    background: radial-gradient(circle at top, rgba(255,255,255,0.04), transparent 55%);
  }

  .timeline-container {
    position: relative;
    display: flex;
    align-items: center;
    overflow-x: visible; 
    overflow-y: visible;
    min-height: 150px; 
    padding-inline: 20px;
    margin-top: 10px;
    margin-bottom: 10px;
  }

  .timeline-track {
    position: relative;
    width: 100%;
    height: 6px;
    background: var(--timeline-line);
    border-radius: 999px;
    top: 0; 
  }

  .timeline-progress {
    position: absolute; left: 0; top: 0;
    height: 100%;
    background: var(--accent-grad);
    border-radius: 999px; transition: width 0.4s ease;
    opacity: 0.85;
  }

  .marker-now {
    position: absolute; top: -16px; bottom: -16px; width: 2px;
    background: var(--danger-color);
    box-shadow: 0 0 10px var(--danger-color);
    z-index: 5; pointer-events: none;
    transition: left 0.4s ease;
  }
  .marker-now::after {
    content: 'HEUTE'; position: absolute; top: -20px; left: -22px;
    background: var(--danger-color); color: white;
    font-size: 9px;
    padding: 2px 6px; border-radius: 999px; font-weight: 700;
    letter-spacing: .06em;
  }

  .milestone-node {
    position: absolute;
    top: 50%; transform: translate(-50%, -50%);
    width: 16px; height: 16px;
    background: var(--card-bg); border: 3px solid var(--text-muted);
    border-radius: 50%;
    cursor: pointer;
    z-index: 10;
    transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s, background 0.18s;
  }
  .milestone-node:hover {
    transform: translate(-50%, -50%) scale(1.2);
    box-shadow: 0 0 10px rgba(0,0,0,0.45);
    z-index: 20; 
  }
  .milestone-node.completed { border-color: var(--success-color); background: var(--success-color); }
  .milestone-node.future { border-color: var(--accent-color); background: var(--accent-soft); }
  .milestone-node.overdue { border-color: var(--danger-color); background: var(--danger-soft); }

  .node-wrapper {
    position: absolute;
    left: 50%; 
    transform: translateX(-50%);
    width: 100px; 
    text-align: center;
    pointer-events: none;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .node-wrapper::before {
    content: '';
    display: block;
    width: 1px;
    height: 15px; 
    background-color: var(--border-color);
    margin: 0 auto;
  }

  .node-label {
    white-space: normal; 
    font-size: 11px; font-weight: 600;
    color: var(--text-main);
    line-height: 1.2;
    background: var(--card-bg); 
    padding: 2px 4px;
    border-radius: 4px;
  }

  .node-date {
    white-space: nowrap; 
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .node-wrapper.pos-bottom {
    top: 20px;
  }

  .node-wrapper.pos-top {
    bottom: 20px;
    flex-direction: column-reverse; 
  }

  .node-wrapper.pos-top .node-date {
      margin-bottom: 2px;
      margin-top: 0;
  }

  /* ---------------------- */

  .editor-section {
    background: var(--card-bg); border: 1px solid var(--card-border);
    border-radius: 14px; overflow: hidden;
    display: flex; flex-direction: column;
    min-height: 0;
  }

  .editor-header {
    padding: 10px 16px; border-bottom: 1px solid var(--border-color);
    display: flex; justify-content: space-between; align-items: center;
  }
  .editor-header h3 { margin: 0; font-size: 14px; font-weight: 600; }

  .list-container {
    flex: 1 1 auto;
    overflow-y: auto;
    min-height: 0;
  }

  .ms-row {
    padding: 8px 16px;
    border-bottom: 1px solid var(--border-color);
    display: grid;
    /* --- HIER WURDE DIE SPALTENBREITE ANGEPASST (135px) --- */
    grid-template-columns: 24px 135px minmax(140px, 1.4fr) minmax(200px, 2fr) 26px;
    gap: 8px;
    align-items: flex-start;
    font-size: 13px;
  }
  .ms-row:nth-child(2n) {
    background: var(--row-alt);
  }

  .ms-check { cursor: pointer; margin-top: 2px; }

  .ms-date-wrapper {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .ms-date-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: .06em;
  }
  .ms-date { width: 100%; font-size: 12px; }

  .ms-main {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .ms-name {
    width: 100%; border: none; background: transparent;
    font-weight: 600; font-size: 13px;
  }
  .ms-name:focus { border-bottom: 1px solid var(--accent-color); outline: none; }

  .ms-meta {
    font-size: 11px;
    color: var(--text-muted);
    display: flex; gap: 6px; align-items: center;
  }

  .task-column {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .task-list {
    display: flex; flex-direction: column; gap: 3px;
  }
  .task-line {
    display: grid;
    grid-template-columns: 20px minmax(0, 1fr) 18px;
    align-items: center;
    gap: 4px;
  }
  .task-line input[type="text"] {
    border: none; background: transparent;
    font-size: 12px;
  }
  .task-line input[type="text"]:focus {
    outline: none;
    border-bottom: 1px solid var(--accent-color);
  }
  .task-remove {
    border: none; background: transparent; color: var(--text-muted);
    cursor: pointer; font-size: 13px;
  }
  .task-remove:hover { color: var(--danger-color); }

  .task-add {
    border: none; background: transparent; color: var(--accent-color);
    cursor: pointer; font-size: 11px; text-align: left; padding: 0;
  }

  .task-summary {
    font-size: 11px; color: var(--text-muted);
  }

  .btn-del {
    background: transparent; color: var(--text-muted); font-size: 18px;
    padding: 0; cursor: pointer;
  }
  .btn-del:hover { color: var(--danger-color); }

  @media (max-width: 900px) {
    header {
      flex-direction: column;
    }
    .project-info, .stat-card {
      flex: 1 1 auto;
    }
    .ms-row {
      grid-template-columns: 20px minmax(90px, 1fr);
      grid-template-rows: auto auto auto auto;
      grid-row-gap: 4px;
    }
  }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">

<div class="container">

  <header>
    <div class="card project-info">
      <div class="card-header-strip"></div>
      <div class="card-body">
        <div class="subtitle">Projektübersicht</div>
        <h1 contenteditable="true" id="projectTitle" onblur="saveData()">Mein Projekt</h1>
        <div class="date-range-inputs">
          <label for="startDate">Start</label>
          <input type="date" id="startDate" onchange="onDateChange()" inputmode="numeric" placeholder="YYYY-MM-DD">
          <label for="endDate">Ziel</label>
          <input type="date" id="endDate" onchange="onDateChange()" inputmode="numeric" placeholder="YYYY-MM-DD">
        </div>
        <div class="date-help">Format: JJJJ-MM-TT · Start wird automatisch vor Ziel korrigiert, falls vertauscht.</div>
        <div class="next-ms" id="nextMsBox">
          <span class="next-ms-label">Nächster Meilenstein:</span>
          <span class="next-ms-name" id="nextMsName">–</span>
          <span class="next-ms-date" id="nextMsDate"></span>
          <span class="next-ms-days" id="nextMsDays"></span>
        </div>
      </div>
    </div>

    <div class="card stat-card">
      <div class="card-header-strip"></div>
      <div class="card-body-stat">
        <div class="sub-text">Tage übrig</div>
        <div class="big-number" id="daysLeft">0</div>
      </div>
    </div>

    <div class="card stat-card">
      <div class="card-header-strip"></div>
      <div class="card-body-stat">
        <div class="sub-text">Fortschritt (Aufgaben)</div>
        <div class="big-number" id="progressPercent">0%</div>
      </div>
    </div>
  </header>

  <div class="bottom">
    <div class="timeline-card">
      <div class="timeline-header">
        <div class="timeline-header-title">Projektzeitachse</div>
        <div class="chip-small">Rot = Heute · Punkte = Meilensteine</div>
      </div>
      <div class="timeline-container-inner">
        <div class="timeline-container" id="timelineContainer">
          <div class="timeline-track" id="track">
            <div class="timeline-progress" id="timeProgress"></div>
            <div class="marker-now" id="markerNow"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="editor-section">
      <div class="editor-header">
        <h3>Meilensteine & Aufgaben</h3>
        <button class="btn btn-primary" onclick="addMilestone()">+ Meilenstein</button>
      </div>
      <div class="list-container" id="milestoneList"></div>
    </div>
  </div>

</div>

<script>
const KEY = 'milestone_master_v1';

let appData = {
  title: "Projekt Alpha",
  start: new Date().toISOString().split('T')[0],
  end: new Date(Date.now() + 90*24*60*60*1000).toISOString().split('T')[0],
  milestones: [
    {
      id: 'm1',
      name: "Kickoff",
      date: new Date().toISOString().split('T')[0],
      done: true,
      tasks: [
        { id: 't1', text: "Agenda vorbereiten", done: true },
        { id: 't2', text: "Teilnehmer einladen", done: false }
      ]
    },
    {
      id: 'm2',
      name: "Konzept",
      date: new Date(Date.now() + 20*24*60*60*1000).toISOString().split('T')[0],
      done: false,
      tasks: []
    }
  ]
};

function migrateTasks() {
  appData.milestones.forEach(m => {
    if (!m.tasks) m.tasks = [];
  });
}

function safeParseDate(str) {
  if (!str) return null;
  const d = new Date(str);
  if (isNaN(d.getTime())) return null;
  return d;
}

function normalizeDates() {
  let s = safeParseDate(appData.start) || new Date();
  let e = safeParseDate(appData.end) || new Date(Date.now() + 7*24*60*60*1000);
  if (s > e) {
    const tmp = s;
    s = e;
    e = tmp;
  }
  appData.start = s.toISOString().split('T')[0];
  appData.end = e.toISOString().split('T')[0];
}

function applyDateMinMax() {
  const startInput = document.getElementById('startDate');
  const endInput = document.getElementById('endDate');
  startInput.min = "1970-01-01";
  endInput.min = "1970-01-01";
  startInput.max = "2099-12-31";
  endInput.max = "2099-12-31";
}

function init() {
  const stored = localStorage.getItem(KEY);
  if (stored) {
    try {
      appData = JSON.parse(stored);
    } catch(e) {
      console.error("Daten korrupt, verwende Defaults");
    }
  }
  migrateTasks();
  normalizeDates();

  document.getElementById('projectTitle').innerText = appData.title;
  document.getElementById('startDate').value = appData.start;
  document.getElementById('endDate').value = appData.end;

  applyDateMinMax();

  const startInput = document.getElementById('startDate');
  const endInput = document.getElementById('endDate');
  if (!('valueAsDate' in startInput)) {
    startInput.setAttribute('type', 'text');
    endInput.setAttribute('type', 'text');
    startInput.setAttribute('pattern', '\\\\d{4}-\\\\d{2}-\\\\d{2}');
    endInput.setAttribute('pattern', '\\\\d{4}-\\\\d{2}-\\\\d{2}');
  }

  updateAll();
}

function saveData() {
  appData.title = document.getElementById('projectTitle').innerText.trim() || "Projekt";
  appData.start = document.getElementById('startDate').value;
  appData.end = document.getElementById('endDate').value;
  normalizeDates();
  document.getElementById('startDate').value = appData.start;
  document.getElementById('endDate').value = appData.end;
  localStorage.setItem(KEY, JSON.stringify(appData));
}

function onDateChange() {
  const s = safeParseDate(document.getElementById('startDate').value);
  const e = safeParseDate(document.getElementById('endDate').value);
  if (!s || !e) {
    document.getElementById('startDate').value = appData.start;
    document.getElementById('endDate').value = appData.end;
  }
  saveData();
  updateAll();
}

function getDaysDiff(d1, d2) {
  const date1 = new Date(d1);
  const date2 = new Date(d2);
  const diffTime = date2 - date1;
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

function calculateStats() {
  const now = new Date();
  const end = safeParseDate(appData.end) || now;

  const diffDays = getDaysDiff(now, end);
  const elDaysLeft = document.getElementById('daysLeft');
  elDaysLeft.innerText = diffDays > 0 ? diffDays : 0;
  elDaysLeft.style.color = diffDays < 0 ? 'var(--danger-color)' : 'var(--text-main)';

  const allTasks = appData.milestones.flatMap(m => m.tasks || []);
  const total = allTasks.length;
  const done = allTasks.filter(t => t.done).length;
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  document.getElementById('progressPercent').innerText = pct + "%";

  updateNextMilestoneBox();
}

function getMsStatus(ms) {
  const d = safeParseDate(ms.date);
  const now = new Date();
  if (ms.done) return { label: "Erledigt", cls: "badge-success" };
  if (!d) return { label: "Offen", cls: "badge-neutral" };
  if (d < now) return { label: "Überfällig", cls: "badge-danger" };
  return { label: "Offen", cls: "badge-warning" };
}

function updateNextMilestoneBox() {
  const now = new Date();
  const upcoming = appData.milestones
    .filter(m => !m.done)
    .map(m => ({...m, d: safeParseDate(m.date)}))
    .filter(m => m.d)
    .sort((a,b) => a.d - b.d)[0];

  const nameEl = document.getElementById('nextMsName');
  const dateEl = document.getElementById('nextMsDate');
  const daysEl = document.getElementById('nextMsDays');

  if (!upcoming) {
    nameEl.innerText = "Alle Meilensteine erledigt 🎉";
    dateEl.innerText = "";
    daysEl.innerText = "";
    return;
  }

  nameEl.innerText = upcoming.name;
  dateEl.innerText = "· " + upcoming.date;

  const days = getDaysDiff(now, upcoming.d);
  if (days < 0) {
    daysEl.innerText = `· ${Math.abs(days)} Tage überfällig`;
    daysEl.style.color = 'var(--danger-color)';
  } else if (days === 0) {
    daysEl.innerText = "· Heute fällig";
    daysEl.style.color = 'var(--danger-color)';
  } else {
    daysEl.innerText = `· in ${days} Tag${days === 1 ? '' : 'en'}`;
    daysEl.style.color = 'var(--text-main)';
  }
}

function renderTimeline() {
  const track = document.getElementById('track');
  track.innerHTML = `
      <div class="timeline-progress" id="timeProgress"></div>
      <div class="marker-now" id="markerNow"></div>
  `;
  const startDate = safeParseDate(appData.start);
  const endDate = safeParseDate(appData.end);
  if (!startDate || !endDate || endDate <= startDate) {
    return;
  }

  const startTs = startDate.getTime();
  const endTs = endDate.getTime();
  const totalDuration = endTs - startTs;

  const nowTs = new Date().getTime();
  let nowPct = ((nowTs - startTs) / totalDuration) * 100;
  nowPct = Math.max(0, Math.min(100, nowPct));

  const elMarker = document.getElementById('markerNow');
  elMarker.style.left = nowPct + "%";

  const elProg = document.getElementById('timeProgress');
  elProg.style.width = nowPct + "%";

  const sortedMilestones = [...appData.milestones].sort((a,b) => {
      const da = safeParseDate(a.date) || new Date(0);
      const db = safeParseDate(b.date) || new Date(0);
      return da - db;
  });

  sortedMilestones.forEach((ms, index) => {
    const msDate = safeParseDate(ms.date);
    if (!msDate) return;
    let pct = ((msDate.getTime() - startTs) / totalDuration) * 100;
    pct = Math.max(0, Math.min(100, pct));

    const node = document.createElement('div');
    const status = getMsStatus(ms);
    let extraClass = "";
    if (status.label === "Überfällig") extraClass = "overdue";
    node.className = `milestone-node ${ms.done ? 'completed' : 'future'} ${extraClass}`;
    node.style.left = pct + "%";
    node.title = `${ms.name} (${ms.date})`;

    const isTop = (index % 2 !== 0); 

    const wrapper = document.createElement('div');
    wrapper.className = isTop ? 'node-wrapper pos-top' : 'node-wrapper pos-bottom';

    const labelName = document.createElement('div');
    labelName.className = 'node-label';
    labelName.innerText = ms.name;

    const labelDate = document.createElement('div');
    labelDate.className = 'node-date';
    labelDate.innerText = msDate.getDate() + "." + (msDate.getMonth()+1) + ".";

    wrapper.appendChild(labelName);
    wrapper.appendChild(labelDate);

    node.appendChild(wrapper);

    node.onclick = () => {
      ms.done = !ms.done;
      updateAll();
    };

    track.appendChild(node);
  });
}

function renderList() {
  const list = document.getElementById('milestoneList');
  list.innerHTML = "";

  const sorted = [...appData.milestones].sort(
    (a,b) => (safeParseDate(a.date) || new Date(0)) - (safeParseDate(b.date) || new Date(0))
  );

  sorted.forEach(ms => {
    const row = document.createElement('div');
    row.className = 'ms-row';

    const tasks = ms.tasks || [];
    const doneTasks = tasks.filter(t => t.done).length;
    const totalTasks = tasks.length;
    const taskInfoText = totalTasks === 0 ? "Keine Aufgaben" : `${doneTasks}/${totalTasks} Aufgaben`;

    const taskContainer = document.createElement('div');
    taskContainer.className = 'task-column';

    const taskList = document.createElement('div');
    taskList.className = 'task-list';

    tasks.forEach(task => {
      const line = document.createElement('div');
      line.className = 'task-line';

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!task.done;
      cb.onchange = () => {
        task.done = cb.checked;
        saveData();
        calculateStats();
        // Hier kein renderList mehr, damit Eingabe nicht unterbrochen wird
      };

      const txt = document.createElement('input');
      txt.type = 'text';
      txt.value = task.text;
      txt.onchange = () => {
        task.text = txt.value;
        saveData();
      };

      const rm = document.createElement('button');
      rm.className = 'task-remove';
      rm.innerText = "×";
      rm.onclick = () => {
        const idx = ms.tasks.findIndex(t => t.id === task.id);
        if (idx >= 0) {
          ms.tasks.splice(idx, 1);
          saveData();
          calculateStats();
          renderList(); // Beim Löschen müssen wir neu rendern
        }
      };

      line.appendChild(cb);
      line.appendChild(txt);
      line.appendChild(rm);
      taskList.appendChild(line);
    });

    const summaryText = document.createElement('div');
    summaryText.className = 'task-summary';
    summaryText.innerText = taskInfoText;

    const addTaskBtn = document.createElement('button');
    addTaskBtn.className = 'task-add';
    addTaskBtn.innerText = "+ Aufgabe hinzufügen";
    addTaskBtn.onclick = () => {
      ms.tasks = ms.tasks || [];
      ms.tasks.push({
        id: 't_' + Date.now(),
        text: "Neue Aufgabe",
        done: false
      });
      saveData();
      calculateStats();
      renderList(); // Beim Hinzufügen auch neu rendern
    };

    taskContainer.appendChild(summaryText);
    taskContainer.appendChild(taskList);
    taskContainer.appendChild(addTaskBtn);

    row.innerHTML = `
      <input type="checkbox" class="ms-check" />
      <div class="ms-date-wrapper">
        <div class="ms-date-label">Fällig am</div>
        <input type="date" class="ms-date">
      </div>
      <div class="ms-main">
        <input type="text" class="ms-name">
        <div class="ms-meta"></div>
      </div>
      <div class="task-summary"></div>
      <button class="btn-del">×</button>
    `;

    const checkbox = row.querySelector('.ms-check');
    const dateInput = row.querySelector('.ms-date');
    const nameInput = row.querySelector('.ms-name');
    const metaDiv = row.querySelector('.ms-meta');
    const summaryDiv = row.querySelector('.task-summary');
    const delBtn = row.querySelector('.btn-del');

    checkbox.checked = ms.done;
    dateInput.value = ms.date;
    nameInput.value = ms.name;
    summaryDiv.replaceWith(taskContainer);

    const status = getMsStatus(ms);
    metaDiv.innerHTML = `
      <span class="badge ${status.cls}">${status.label}</span>
      <span>${taskInfoText}</span>
    `;

    if (!('valueAsDate' in dateInput)) {
      dateInput.setAttribute('type', 'text');
      dateInput.setAttribute('pattern', '\\\\d{4}-\\\\d{2}-\\\\d{2}');
      dateInput.setAttribute('placeholder', 'YYYY-MM-DD');
    }

    checkbox.onchange = () => {
      ms.done = checkbox.checked;
      saveData();
      calculateStats();
      renderTimeline(); // Update oben
      updateNextMilestoneBox();
      // KEIN renderList() hier!
    };
    dateInput.onchange = () => {
      const d = safeParseDate(dateInput.value);
      if (!d) {
        // Falls ungültig, nichts tun oder alten Wert lassen
        return;
      }
      ms.date = d.toISOString().split('T')[0];
      saveData();
      renderTimeline();
      updateNextMilestoneBox();
      // KEIN renderList() hier! Verhindert Fokus-Verlust beim Tippen.
    };
    nameInput.onchange = () => {
      ms.name = nameInput.value || "Meilenstein";
      saveData();
      renderTimeline();
      updateNextMilestoneBox();
      // KEIN renderList() hier!
    };
    delBtn.onclick = () => {
      if (confirm("Meilenstein wirklich löschen?")) {
        appData.milestones = appData.milestones.filter(m => m.id !== ms.id);
        updateAll(); // Beim Löschen muss alles neu
      }
    };

    list.appendChild(row);
  });
}

function addMilestone() {
  const newId = 'ms_' + Date.now();
  appData.milestones.push({
    id: newId,
    name: "Neuer Meilenstein",
    date: appData.end || new Date().toISOString().split('T')[0],
    done: false,
    tasks: []
  });
  updateAll();
  setTimeout(() => {
    const list = document.getElementById('milestoneList');
    list.scrollTop = list.scrollHeight;
  }, 50);
}

function updateAll() {
  saveData();
  calculateStats();
  renderTimeline();
  renderList();
}

init();
</script>
</body>
</html>"""
        return template.replace("__BODY_CLASS__", body_class)

    # ---------------------------------------------------------
    # POPUP MODE – mit Top‑Tasks
    # ---------------------------------------------------------
    def _build_popup_html(self, body_class: str):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Milestone Master – Dashboard</title>
<style>
  html, body {
    height: 100%;
    margin: 0;
    font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
    overflow: hidden;
  }
  body {
    background: var(--bg-color);
    color: var(--text-main);
    display: flex;
    align-items: stretch;
    justify-content: center;
  }
  .wrap {
    padding: 10px;
    box-sizing: border-box;
    width: 100%;
  }
  .card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 6px 10px 10px 10px;
    margin-bottom: 8px;
  }
  .title {
    font-size: 14px;
    font-weight: 600;
    margin: 0 0 2px 0;
  }
  .sub {
    font-size: 11px;
    color: var(--text-muted);
  }
  .stat-line {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    align-items: baseline;
  }
  .stat-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .big {
    font-size: 18px;
    font-weight: 700;
  }
  .label {
    font-size: 10px;
    text-transform: uppercase;
    color: var(--text-muted);
    letter-spacing: .08em;
  }
  .next-ms-name {
    font-weight: 600;
    font-size: 13px;
  }
  .next-ms-days.overdue { color: var(--danger-color); }

  .inline-badge {
    display: inline-flex;
    align-items: center;
    padding: 2px 6px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: .06em;
    text-transform: uppercase;
  }
  .inline-badge-success { background: var(--success-soft); color: var(--success-color); }
  .inline-badge-warning { background: var(--warning-soft); color: var(--warning-color); }
  .inline-badge-danger { background: var(--danger-soft); color: var(--danger-color); }
  .inline-badge-neutral { background: var(--chip-bg); color: var(--text-muted); }

  .task-list-popup {
    margin-top: 4px;
    padding-left: 10px;
  }
  .task-list-popup li {
    font-size: 11px;
    margin-bottom: 2px;
  }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">
<div class="wrap">
  <div class="card">
    <div class="label">Aktuelles Projekt</div>
    <div class="title" id="projectTitleSmall">Projekt</div>
    <div class="sub" id="dateRangeSmall"></div>
  </div>

  <div class="card">
    <div class="stat-line">
      <div class="stat-col">
        <div class="label">Tage übrig</div>
        <div class="big" id="daysLeftSmall">0</div>
      </div>
      <div class="stat-col">
        <div class="label">Aufgaben</div>
        <div class="sub">
          <span id="tasksDoneSmall">0</span>/<span id="tasksTotalSmall">0</span> erledigt
        </div>
        <div class="sub">
          <span class="label" style="font-size:9px;">Fortschritt</span>
          <span id="progressSmall">0%</span>
        </div>
      </div>
      <div class="stat-col">
        <div class="label">Meilensteine</div>
        <div class="sub">
          <span id="msDoneSmall">0</span>/<span id="msTotalSmall">0</span> erledigt
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="label">Nächster Meilenstein</div>
    <div class="next-ms-name" id="nextMsNameSmall">–</div>
    <div class="sub" id="nextMsDateSmall"></div>
    <div class="sub next-ms-days" id="nextMsDaysSmall"></div>
    <div class="sub" id="nextMsStatusSmall"></div>
    <div class="sub" id="nextMsTasksSmall"></div>
    <ul class="task-list-popup" id="nextMsTasksList"></ul>
  </div>
</div>

<script>
const KEY = 'milestone_master_v1';
let appData = null;

function safeParseDate(str) {
  if (!str) return null;
  const d = new Date(str);
  if (isNaN(d.getTime())) return null;
  return d;
}

function getMsStatus(ms) {
  const d = safeParseDate(ms.date);
  const now = new Date();
  if (ms.done) return { label: "Erledigt", cls: "inline-badge-success" };
  if (!d) return { label: "Offen", cls: "inline-badge-neutral" };
  if (d < now) return { label: "Überfällig", cls: "inline-badge-danger" };
  return { label: "Offen", cls: "inline-badge-warning" };
}

function loadData() {
  const stored = localStorage.getItem(KEY);
  if (stored) {
    try { appData = JSON.parse(stored);
    } catch(e) { appData = null; }
  }
}

function getDaysDiff(d1, d2) {
  const date1 = new Date(d1);
  const date2 = new Date(d2);
  const diffTime = date2 - date1;
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

function refresh() {
  if (!appData) return;
  document.getElementById('projectTitleSmall').innerText = appData.title || "Projekt";
  document.getElementById('dateRangeSmall').innerText =
    (appData.start || "?") + " – " + (appData.end || "?");

  const now = new Date();
  const end = safeParseDate(appData.end) || now;
  const diffDays = getDaysDiff(now, end);
  const elDays = document.getElementById('daysLeftSmall');
  elDays.innerText = diffDays > 0 ? diffDays : 0;

  const milestones = appData.milestones || [];
  const msTotal = milestones.length;
  const msDone = milestones.filter(m => m.done).length;
  document.getElementById('msTotalSmall').innerText = msTotal;
  document.getElementById('msDoneSmall').innerText = msDone;

  const allTasks = milestones.flatMap(m => m.tasks || []);
  const totalTasks = allTasks.length;
  const doneTasks = allTasks.filter(t => t.done).length;
  document.getElementById('tasksTotalSmall').innerText = totalTasks;
  document.getElementById('tasksDoneSmall').innerText = doneTasks;
  const pct = totalTasks === 0 ? 0 : Math.round((doneTasks / totalTasks) * 100);
  document.getElementById('progressSmall').innerText = pct + "%";

  const upcoming = milestones
    .filter(m => !m.done)
    .map(m => ({...m, d: safeParseDate(m.date)}))
    .filter(m => m.d)
    .sort((a,b) => a.d - b.d)[0];

  const nameEl = document.getElementById('nextMsNameSmall');
  const dateEl = document.getElementById('nextMsDateSmall');
  const daysEl = document.getElementById('nextMsDaysSmall');
  const tasksEl = document.getElementById('nextMsTasksSmall');
  const statusEl = document.getElementById('nextMsStatusSmall');
  const tasksListEl = document.getElementById('nextMsTasksList');

  tasksListEl.innerHTML = "";

  if (!upcoming) {
    nameEl.innerText = "Alle Meilensteine erledigt 🎉";
    dateEl.innerText = "";
    daysEl.innerText = "";
    tasksEl.innerText = "";
    statusEl.innerHTML = "";
    return;
  }

  nameEl.innerText = upcoming.name;
  dateEl.innerText = upcoming.date;

  const days = getDaysDiff(now, upcoming.d);
  daysEl.classList.remove('overdue');
  if (days < 0) {
    daysEl.innerText = `${Math.abs(days)} Tage überfällig`;
    daysEl.classList.add('overdue');
  } else if (days === 0) {
    daysEl.innerText = "Heute fällig";
    daysEl.classList.add('overdue');
  } else {
    daysEl.innerText = `in ${days} Tag${days === 1 ? '' : 'en'}`;
  }

  const tasks = upcoming.tasks || [];
  const doneTasksMs = tasks.filter(t => t.done).length;
  const totalTasksMs = tasks.length;
  tasksEl.innerText = totalTasksMs === 0
    ? "Keine Aufgaben hinterlegt"
    : `${doneTasksMs}/${totalTasksMs} Aufgaben erledigt`;

  const status = getMsStatus(upcoming);
  statusEl.innerHTML = `<span class="inline-badge ${status.cls}">${status.label}</span>`;

  const openTasks = tasks.filter(t => !t.done).slice(0, 3);
  openTasks.forEach(t => {
    const li = document.createElement('li');
    li.textContent = t.text;
    tasksListEl.appendChild(li);
  });
}

function init() {
  loadData();
  refresh();
}

init();
</script>
</body>
</html>"""
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