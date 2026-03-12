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
  --modal-overlay: rgba(0,0,0,0.7);
  --modal-bg: #333;
  --tag-bg: rgba(255,255,255,0.1);
  --progress-bg: rgba(255,255,255,0.1);
  --stats-bg: #252525;
  --search-bg: rgba(0,0,0,0.2);
  --timer-active: rgba(16,185,129,0.15);
  --bulk-bar-bg: #1a1a1a;
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
  --modal-overlay: rgba(0,0,0,0.4);
  --modal-bg: #fff;
  --tag-bg: rgba(0,0,0,0.07);
  --progress-bg: rgba(0,0,0,0.08);
  --stats-bg: #f4f5f7;
  --search-bg: rgba(0,0,0,0.04);
  --timer-active: rgba(16,185,129,0.08);
  --bulk-bar-bg: #e7ecf9;
}

body input, body textarea, body select {
    background: var(--item-bg) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-main) !important;
}
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
        self.setWindowTitle("To-Do Plugin Ultra (Next Level)")
        self.resize(1200, 850)

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
    # 1. WINDOW MODE HTML - ULTRA EDITION
    # ---------------------------------------------------------
    def _build_window_html(self, body_class: str):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>To-Do Ultra</title>
<style>
  :root{
    --prio-high: #ef4444;
    --prio-med: #f59e0b;
    --prio-low: #10b981;
    --success: #10b981;
    --urgent: #f59e0b;
    --overdue: #ef4444;
    --blue: #3b82f6;
    --purple: #8b5cf6;
  }
  *{box-sizing: border-box; box-shadow: none !important; outline: none;}
  html, body{ height:100%; margin:0; font-family: Inter, sans-serif; overflow: hidden; }
  body { display: flex; background: var(--bg-color); color: var(--text-main); }
  .app-layout { display: flex; width: 100%; height: 100%; overflow: hidden; }

  /* ===== SIDEBAR ===== */
  .sidebar {
    width: 240px; background: var(--sidebar-bg);
    border-right: 1px solid var(--border-color);
    display: flex; flex-direction: column;
    padding: 16px 10px; flex-shrink: 0; overflow-y: auto;
  }
  .sidebar h2 { margin: 0 0 10px 10px; font-size: 11px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 1px; }
  .sidebar-section { margin-bottom: 20px; }

  /* Stats Mini Widget in Sidebar */
  .stats-mini {
    background: var(--stats-bg); border-radius: 8px; padding: 10px 12px;
    margin-bottom: 14px; border: 1px solid var(--border-color);
  }
  .stats-mini-title { font-size: 10px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 1px; margin-bottom: 8px; }
  .stats-row { display: flex; justify-content: space-between; align-items: center; }
  .stats-val { font-size: 20px; font-weight: 700; color: var(--success); }
  .stats-sub { font-size: 10px; color: var(--text-muted); }
  .streak-badge { background: linear-gradient(135deg, #f59e0b, #ef4444); color: white; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold; }

  /* Progress Bar */
  .progress-bar-wrap { height: 4px; background: var(--progress-bg); border-radius: 2px; margin-top: 8px; }
  .progress-bar-fill { height: 100%; background: linear-gradient(90deg, var(--success), #34d399); border-radius: 2px; transition: width 0.5s ease; }

  /* Tags Filter */
  .tags-filter { display: flex; flex-wrap: wrap; gap: 5px; }
  .tag-chip {
    padding: 3px 8px; border-radius: 10px; font-size: 11px; cursor: pointer;
    border: 1px solid var(--border-color); background: var(--tag-bg);
    color: var(--text-muted); transition: all 0.15s;
    display: flex; align-items: center; gap: 4px;
  }
  .tag-chip:hover { border-color: var(--text-muted); color: var(--text-main); }
  .tag-chip.active { border-color: var(--blue); color: var(--blue); background: rgba(59,130,246,0.1); }
  .tag-chip .tag-dot { width: 6px; height: 6px; border-radius: 50%; }

  /* Folder List */
  .folder-list { flex: 0; overflow-y: auto; overflow-x: hidden; }
  .folder-row {
    display: flex;
    justify-content: space-between; align-items: center;
    width: 100%; padding: 7px 10px;
    margin-bottom: 3px; border-radius: 6px;
    cursor: pointer; color: var(--text-main);
    transition: background 0.1s;
  }
  .folder-row:hover { background: var(--hover-bg); }
  .folder-row.active { background: var(--hover-bg); font-weight: bold; border-left: 3px solid var(--success); }
  .folder-info { flex: 1; display: flex; align-items: center; justify-content: space-between; padding-right: 5px; min-width: 0; }
  .folder-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 13px; }
  .folder-count { font-size: 11px; color: var(--text-muted); background: var(--border-color); padding: 2px 6px; border-radius: 10px; margin-left: 8px;}
  .btn-folder-del {
    background: transparent; border: none; color: var(--text-muted);
    cursor: pointer; width: 22px; height: 22px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    opacity: 0; transition: all 0.2s; font-size: 16px; font-weight: bold;
  }
  .folder-row:hover .btn-folder-del { opacity: 1; }
  .btn-folder-del:hover { color: #ef4444; background: var(--trash-hover); }
  .add-folder-row { margin-top: 8px; display: flex; gap: 5px; }
  .add-folder-row input { flex: 1; padding: 5px; border-radius: 4px; font-size: 12px; }
  .icon-btn-sm { background: var(--hover-bg); border: 1px solid var(--border-color); color: var(--text-main); border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0 8px; font-size: 14px;}

  /* ===== MAIN CONTENT ===== */
  .main { flex: 1; display: flex; flex-direction: column; padding: 16px 20px; min-width: 0; height: 100%; }

  /* HEADER */
  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-shrink: 0;}
  header h1 { margin: 0; font-size: 20px; }
  .header-controls { display: flex; gap: 8px; align-items: center; }

  .view-toggle {
    display: flex; background: var(--item-bg); border: 1px solid var(--border-color);
    border-radius: 6px; overflow: hidden;
  }
  .view-btn {
    padding: 5px 11px; cursor: pointer; border: none; background: transparent; color: var(--text-muted); font-size: 12px; font-weight: 600;
  }
  .view-btn.active { background: var(--hover-bg); color: var(--text-main); }
  .icon-btn { background: var(--hover-bg); border: 1px solid var(--border-color); color: var(--text-main); border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0 10px; height: 30px; font-size: 12px;}

  /* SEARCH BAR */
  .search-bar {
    display: flex; align-items: center; gap: 8px;
    background: var(--search-bg); border: 1px solid var(--border-color);
    border-radius: 6px; padding: 6px 12px; margin-bottom: 10px; flex-shrink: 0;
  }
  .search-bar input { flex: 1; border: none !important; background: transparent !important; font-size: 13px; }
  .search-icon { color: var(--text-muted); font-size: 14px; }
  .search-clear { cursor: pointer; color: var(--text-muted); font-size: 16px; display: none; }
  .search-clear.visible { display: block; }
  .filter-pills { display: flex; gap: 5px; flex-shrink: 0; }
  .filter-pill {
    padding: 2px 8px; border-radius: 10px; font-size: 11px; cursor: pointer;
    border: 1px solid var(--border-color); color: var(--text-muted); background: transparent; white-space: nowrap;
  }
  .filter-pill.active { border-color: var(--blue); color: var(--blue); background: rgba(59,130,246,0.1); }

  /* INPUT AREA */
  .input-area {
    display: flex; gap: 8px;
    margin-bottom: 12px; background: var(--item-bg); padding: 8px 12px; border-radius: 8px; border: 1px solid var(--border-color); flex-shrink: 0; flex-wrap: wrap; align-items: center;
  }
  .input-main-row { display: flex; flex: 1; gap: 8px; width: 100%; align-items: center; }
  .input-area input[type="text"] { flex: 1; border: none !important; background: transparent !important; font-size: 14px; }
  .prio-select { background: transparent; color: var(--text-muted); border: 1px solid var(--border-color); border-radius: 6px; padding: 3px 6px; cursor: pointer; height: 28px; font-size: 12px; }
  .prio-select option { background: var(--bg-color); color: var(--text-main); }
  .btn-add { background: var(--text-main); color: var(--bg-color); border: none; border-radius: 6px; padding: 0 16px; font-weight: bold; cursor: pointer; height: 28px; font-size: 12px; }
  .deadline-wrapper { display: flex; align-items: center; gap: 6px; padding-left: 8px; border-left: 1px solid var(--border-color); height: 28px;}
  .dl-checkbox-label { font-size: 11px; color: var(--text-muted); cursor: pointer; user-select: none; display: flex; align-items: center; gap: 3px;}
  .dl-input { background: var(--bg-color); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 4px; padding: 2px 4px; font-size: 11px; display: none; }
  .dl-input.visible { display: block; }

  /* Tag input in add row */
  .tag-input-wrap { display: flex; align-items: center; gap: 4px; padding-left: 8px; border-left: 1px solid var(--border-color); }
  .tag-input-wrap input { width: 80px; font-size: 11px !important; padding: 2px 4px; border-radius: 4px; height: 24px; }

  /* Recurring option */
  .recur-select { background: transparent; color: var(--text-muted); border: 1px solid var(--border-color); border-radius: 6px; padding: 3px 4px; cursor: pointer; height: 28px; font-size: 11px; }

  /* --- DEADLINE BADGES --- */
  .dl-badge {
      display: inline-flex; align-items: center; gap: 4px;
      font-size: 11px; padding: 2px 6px; border-radius: 4px;
      margin-right: 6px; transition: background 0.3s, color 0.3s;
  }
  .dl-normal { color: var(--text-muted); background: var(--border-color); }
  .dl-urgent { color: #fff; background: var(--urgent); font-weight: bold; }
  .dl-overdue { color: #fff; background: var(--overdue); font-weight: bold; animation: pulse 2s infinite; }
  @keyframes pulse { 0% {opacity:1;} 50% {opacity:0.8;} 100% {opacity:1;} }

  /* --- BULK ACTION BAR --- */
  .bulk-bar {
    display: none; position: sticky; top: 0; z-index: 100;
    background: var(--bulk-bar-bg); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 8px 14px;
    margin-bottom: 8px; align-items: center; justify-content: space-between;
    animation: slideDown 0.2s;
  }
  .bulk-bar.visible { display: flex; }
  .bulk-bar-left { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--text-muted); }
  .bulk-bar-actions { display: flex; gap: 6px; }
  .bulk-btn { padding: 4px 10px; border-radius: 5px; border: 1px solid var(--border-color); background: transparent; color: var(--text-main); cursor: pointer; font-size: 12px; }
  .bulk-btn:hover { background: var(--hover-bg); }
  .bulk-btn.danger { border-color: #ef4444; color: #ef4444; }
  .bulk-btn.danger:hover { background: var(--trash-hover); }
  @keyframes slideDown { from { transform: translateY(-8px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

  /* --- LIST VIEW STYLES --- */
  .list-view { flex: 1; overflow-y: auto; overflow-x: hidden; display: block; }
  .item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 9px 12px; margin-bottom: 5px;
    background: var(--item-bg);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    transition: transform 0.1s, border-color 0.15s;
    position: relative;
  }
  .item:hover { transform: translateX(2px); border-color: var(--text-muted); }
  .item.selected { border-color: var(--blue); background: rgba(59,130,246,0.06); }
  .item.timer-running { background: var(--timer-active); border-color: var(--success); }

  /* Checkbox for selection */
  .sel-check {
    width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid var(--border-color);
    cursor: pointer; flex-shrink: 0; margin-top: 2px; opacity: 0; transition: opacity 0.15s;
    background: transparent; accent-color: var(--blue);
  }
  .item:hover .sel-check, .item.selected .sel-check { opacity: 1; }

  .check {
    width: 18px; height: 18px; border-radius: 5px; border: 2px solid var(--text-muted);
    display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; margin-top: 1px;
  }
  .check.checked { background: var(--success); border-color: var(--success); color: white; font-size: 11px; }
  .prio-indicator { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
  .prio-high { background: var(--prio-high); box-shadow: 0 0 5px var(--prio-high); }
  .prio-med { background: var(--prio-med); }
  .prio-low { background: var(--prio-low); opacity: 0.5; }

  .text-content { flex: 1; min-width: 0; cursor: pointer; }
  .task-text { font-size: 13px; word-break: break-word; }
  .task-text.done { text-decoration: line-through; opacity: 0.5; }
  .task-meta { font-size: 10px; color: var(--text-muted); margin-top: 3px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;}
  .badge { padding: 1px 5px; border-radius: 3px; background: var(--border-color); font-size: 10px; }

  /* Subtask Progress Bar in List */
  .subtask-progress { margin-top: 5px; }
  .subtask-bar-wrap { height: 3px; background: var(--progress-bg); border-radius: 2px; width: 100px; display: inline-block; vertical-align: middle; margin-right: 4px; }
  .subtask-bar-fill { height: 100%; background: var(--success); border-radius: 2px; transition: width 0.3s ease; }
  .subtask-text { font-size: 10px; color: var(--text-muted); vertical-align: middle; }

  /* Tag badges inline */
  .tag-badge { padding: 1px 6px; border-radius: 8px; font-size: 10px; }

  /* Timer display */
  .timer-display { font-size: 10px; font-weight: bold; color: var(--success); letter-spacing: 1px; }

  /* Recurring icon */
  .recur-icon { font-size: 10px; color: var(--purple); }

  .btn-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.2s; align-items: flex-start; padding-top: 1px; }
  .item:hover .btn-actions { opacity: 1; }
  .btn-icon-small { background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 15px; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border-radius: 4px;}
  .btn-icon-small:hover { background: var(--hover-bg); color: var(--text-main); }
  .btn-del:hover { color: #ef4444; background: var(--trash-hover); }
  .btn-timer { font-size: 11px; }
  .btn-timer.running { color: var(--success); }

  /* --- KANBAN BOARD STYLES --- */
  .board-view { flex: 1; display: none; overflow-x: auto; overflow-y: hidden; gap: 15px; padding-bottom: 10px; height: 100%; }
  .kanban-col {
      flex: 1; min-width: 260px; max-width: 350px;
      background: var(--col-bg); border-radius: 8px;
      display: flex; flex-direction: column; border: 1px solid var(--border-color); height: 100%;
  }
  .col-header {
      padding: 10px 12px; font-weight: bold; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px;
      border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; background: rgba(0,0,0,0.02);
  }
  .col-count { background: var(--border-color); border-radius: 10px; padding: 2px 8px; font-size: 11px; color: var(--text-main); }
  .col-body { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
  .board-card {
      background: var(--item-bg); border: 1px solid var(--border-color);
      border-radius: 6px; padding: 10px; cursor: grab;
      transition: transform 0.2s;
  }
  .board-card:active { cursor: grabbing; }
  .board-card:hover { border-color: var(--text-muted); }
  .card-top { display: flex; justify-content: space-between; margin-bottom: 6px; }
  .card-text { font-size: 13px; line-height: 1.4; margin-bottom: 6px; color: var(--text-main); }
  .card-text.done { text-decoration: line-through; opacity: 0.6; }
  .card-footer { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; align-items: center; }
  .drag-over { background: var(--hover-bg); border: 2px dashed var(--text-muted); }

  /* ===== STATS VIEW ===== */
  .stats-view { flex: 1; display: none; overflow-y: auto; padding: 10px 0; }
  .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
  .stat-card { background: var(--stats-bg); border-radius: 8px; padding: 14px 16px; border: 1px solid var(--border-color); }
  .stat-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-bottom: 6px; }
  .stat-value { font-size: 28px; font-weight: 700; color: var(--text-main); }
  .stat-sub { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
  .stat-bar { height: 4px; background: var(--progress-bg); border-radius: 2px; margin-top: 10px; }
  .stat-bar-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--success), #34d399); }
  .chart-section { background: var(--stats-bg); border-radius: 8px; padding: 14px 16px; border: 1px solid var(--border-color); margin-bottom: 12px; }
  .chart-title { font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 12px; }
  .activity-chart { display: flex; align-items: flex-end; gap: 3px; height: 60px; }
  .activity-bar { flex: 1; background: var(--success); border-radius: 2px 2px 0 0; opacity: 0.8; min-height: 2px; transition: height 0.5s; cursor: default; }
  .activity-bar:hover { opacity: 1; }
  .prio-dist { display: flex; gap: 8px; align-items: center; }
  .prio-seg { height: 12px; border-radius: 3px; }

  /* --- MODAL (DETAIL VIEW) STYLES --- */
  .modal-overlay {
      position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: var(--modal-overlay); z-index: 1000;
      display: none; justify-content: center; align-items: center;
      backdrop-filter: blur(2px);
      animation: fadeIn 0.2s;
  }
  .modal-content {
      background: var(--modal-bg); width: 640px; max-width: 90%; max-height: 90vh;
      border-radius: 8px; border: 1px solid var(--border-color);
      display: flex; flex-direction: column; overflow: hidden;
      animation: slideUp 0.2s;
  }
  .modal-header {
      padding: 14px 20px; border-bottom: 1px solid var(--border-color);
      display: flex; justify-content: space-between; align-items: center;
      background: var(--sidebar-bg);
  }
  .modal-body { padding: 18px 20px; overflow-y: auto; flex: 1; }
  .modal-footer { padding: 12px 20px; border-top: 1px solid var(--border-color); text-align: right; background: var(--sidebar-bg); display: flex; justify-content: space-between; align-items: center; }

  .detail-row { margin-bottom: 14px; }
  .detail-label { font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--text-muted); margin-bottom: 4px; display: block; font-weight: bold; }
  .detail-input { width: 100%; padding: 7px 8px; background: var(--item-bg); border: 1px solid var(--border-color); color: var(--text-main); border-radius: 4px; font-size: 13px; }
  .detail-desc { width: 100%; min-height: 90px; resize: vertical; font-family: inherit; line-height: 1.5; }
  .meta-grid { display: flex; gap: 12px; }
  .meta-col { flex: 1; }

  /* Subtask section in modal */
  .subtask-list { margin-bottom: 8px; display: flex; flex-direction: column; gap: 5px; }
  .subtask-item { display: flex; align-items: center; gap: 8px; padding: 5px 8px; background: var(--item-bg); border: 1px solid var(--border-color); border-radius: 5px; }
  .subtask-item .sub-check { width: 14px; height: 14px; cursor: pointer; accent-color: var(--success); flex-shrink: 0; }
  .subtask-item .sub-text { flex: 1; font-size: 12px; }
  .subtask-item .sub-text.done { text-decoration: line-through; opacity: 0.5; }
  .subtask-item .sub-del { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 14px; opacity: 0; }
  .subtask-item:hover .sub-del { opacity: 1; }
  .add-subtask-row { display: flex; gap: 6px; }
  .add-subtask-row input { flex: 1; font-size: 12px; padding: 5px; border-radius: 4px; }
  .add-subtask-row button { padding: 0 10px; border: 1px solid var(--border-color); background: transparent; color: var(--text-main); border-radius: 4px; cursor: pointer; font-size: 12px; }

  /* Tags in modal */
  .tags-editor { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
  .tag-badge-editable { padding: 2px 8px; border-radius: 10px; font-size: 11px; display: flex; align-items: center; gap: 4px; cursor: default; }
  .tag-badge-editable .tag-x { cursor: pointer; opacity: 0.6; font-size: 12px; }
  .tag-badge-editable .tag-x:hover { opacity: 1; }
  .tag-add-btn { padding: 2px 8px; border-radius: 10px; font-size: 11px; border: 1px dashed var(--border-color); background: transparent; color: var(--text-muted); cursor: pointer; }

  /* Timer Section in Modal */
  .timer-section { display: flex; align-items: center; gap: 12px; }
  .timer-big { font-size: 28px; font-weight: 700; font-family: monospace; color: var(--text-main); min-width: 90px; }
  .timer-btn { padding: 5px 14px; border-radius: 6px; border: 1px solid var(--border-color); background: transparent; color: var(--text-main); cursor: pointer; font-size: 12px; }
  .timer-btn.start { border-color: var(--success); color: var(--success); }
  .timer-btn.stop { border-color: #ef4444; color: #ef4444; }
  .timer-log { font-size: 10px; color: var(--text-muted); margin-top: 6px; }

  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
  @keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

  /* Keyboard Shortcut Hint */
  .kbd { display: inline-block; padding: 1px 5px; border-radius: 3px; font-size: 10px; border: 1px solid var(--border-color); color: var(--text-muted); font-family: monospace; }

  /* Export button group */
  .export-group { display: flex; gap: 4px; }
  .export-btn { padding: 3px 8px; border-radius: 4px; border: 1px solid var(--border-color); background: transparent; color: var(--text-muted); cursor: pointer; font-size: 11px; }
  .export-btn:hover { background: var(--hover-bg); color: var(--text-main); }

  /* Scrollbars */
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 3px; }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">

<div class="app-layout">
  <!-- ===== SIDEBAR ===== -->
  <div class="sidebar">

    <!-- Stats Mini -->
    <div class="stats-mini">
      <div class="stats-mini-title">Heute</div>
      <div class="stats-row">
        <div>
          <div class="stats-val" id="sideStatDone">0</div>
          <div class="stats-sub">Erledigt</div>
        </div>
        <div>
          <span class="streak-badge" id="sideStreak">🔥 0d</span>
        </div>
      </div>
      <div class="progress-bar-wrap">
        <div class="progress-bar-fill" id="sideProgress" style="width:0%"></div>
      </div>
    </div>

    <!-- Tags Filter -->
    <div class="sidebar-section">
      <h2>Tags</h2>
      <div class="tags-filter" id="tagsFilter">
        <span class="tag-chip active" data-tag="all" onclick="filterByTag('all')">Alle</span>
      </div>
    </div>

    <!-- Folder List -->
    <div class="sidebar-section" style="flex:1; display:flex; flex-direction:column; min-height:0;">
      <h2>Ordner</h2>
      <div class="folder-list" id="folderList" style="flex:1; overflow-y:auto;"></div>
      <div class="add-folder-row">
        <input id="newFolderInput" placeholder="Neuer Ordner..." />
        <button class="icon-btn-sm" onclick="addFolder()">+</button>
      </div>
    </div>

  </div>

  <!-- ===== MAIN ===== -->
  <div class="main">
    <header>
      <h1 id="headerTitle">Alle Aufgaben</h1>
      <div class="header-controls">
        <div class="export-group">
          <button class="export-btn" onclick="exportJSON()" title="Als JSON exportieren">JSON</button>
          <button class="export-btn" onclick="exportCSV()" title="Als CSV exportieren">CSV</button>
        </div>
        <div class="view-toggle">
          <button class="view-btn active" id="btnViewList" onclick="switchView('list')">Liste</button>
          <button class="view-btn" id="btnViewBoard" onclick="switchView('board')">Trello</button>
          <button class="view-btn" id="btnViewStats" onclick="switchView('stats')">Stats</button>
        </div>
        <button class="icon-btn" title="Erledigte löschen" onclick="clearDone()">Clear Done</button>
        <span class="kbd" title="N=Neu, ESC=Schließen, 1-3=Prio, Del=Löschen">⌨</span>
      </div>
    </header>

    <!-- SEARCH + FILTER -->
    <div class="search-bar">
      <span class="search-icon">🔍</span>
      <input type="text" id="searchInput" placeholder="Suchen... (Strg+F)" oninput="onSearch()" />
      <span class="search-clear" id="searchClear" onclick="clearSearch()">×</span>
    </div>
    <div class="filter-pills" style="margin-bottom:10px; flex-shrink:0;">
      <button class="filter-pill active" id="fpAll" onclick="setStatusFilter('all')">Alle</button>
      <button class="filter-pill" id="fpTodo" onclick="setStatusFilter('todo')">Offen</button>
      <button class="filter-pill" id="fpUrgent" onclick="setStatusFilter('urgent')">Urgent ⚠</button>
      <button class="filter-pill" id="fpOverdue" onclick="setStatusFilter('overdue')">Überfällig 🔴</button>
      <button class="filter-pill" id="fpRecur" onclick="setStatusFilter('recurring')">🔄 Wiederhol.</button>
      <button class="filter-pill" id="fpDone" onclick="setStatusFilter('done')">Erledigt</button>
    </div>

    <!-- INPUT AREA -->
    <div class="input-area">
      <div class="input-main-row">
        <input type="text" id="newTask" placeholder="Neue Aufgabe eingeben... (N)" />
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
        <select id="newRecur" class="recur-select" title="Wiederholung">
          <option value="">Einmalig</option>
          <option value="daily">Täglich 🔄</option>
          <option value="weekly">Wöchentl. 🔄</option>
          <option value="monthly">Monatlich 🔄</option>
        </select>
        <div class="tag-input-wrap">
          <input type="text" id="newTagInput" placeholder="#tag" style="font-size:11px !important; height:24px; border:1px solid var(--border-color) !important; border-radius:4px; padding: 2px 6px; background:transparent !important;" />
        </div>
        <button class="btn-add" onclick="addTask()">Add</button>
      </div>
    </div>

    <!-- BULK ACTION BAR -->
    <div class="bulk-bar" id="bulkBar">
      <div class="bulk-bar-left">
        <span id="bulkCount">0</span> ausgewählt
        <button class="bulk-btn" onclick="bulkSelectAll()">Alle</button>
        <button class="bulk-btn" onclick="bulkDeselectAll()">Keine</button>
      </div>
      <div class="bulk-bar-actions">
        <select id="bulkFolderSel" class="prio-select" style="font-size:11px; height:26px;">
          <option value="">→ Ordner verschieben</option>
        </select>
        <button class="bulk-btn" onclick="bulkMove()">Verschieben</button>
        <button class="bulk-btn" onclick="bulkDone()">✓ Erledigt</button>
        <button class="bulk-btn" onclick="bulkUndone()">↩ Rückgängig</button>
        <button class="bulk-btn danger" onclick="bulkDelete()">× Löschen</button>
      </div>
    </div>

    <!-- LIST VIEW -->
    <div class="list-view" id="listView"></div>

    <!-- BOARD VIEW -->
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

    <!-- STATS VIEW -->
    <div class="stats-view" id="statsView"></div>

  </div>
</div>

<!-- ===== DETAIL MODAL ===== -->
<div id="detailModal" class="modal-overlay" onclick="closeDetail(event)">
  <div class="modal-content" onclick="event.stopPropagation()">
    <div class="modal-header">
      <h3 style="margin:0; font-size:15px;">Task Details</h3>
      <button class="btn-icon-small" onclick="closeDetail()" style="font-size:18px;">×</button>
    </div>
    <div class="modal-body">
      <input type="hidden" id="modalId">

      <div class="detail-row">
        <label class="detail-label">Aufgabe</label>
        <input type="text" id="modalTitle" class="detail-input" placeholder="Titel" />
      </div>

      <div class="meta-grid detail-row">
        <div class="meta-col">
          <label class="detail-label">Priorität</label>
          <select id="modalPrio" class="detail-input">
            <option value="low">Niedrig</option>
            <option value="med">Mittel</option>
            <option value="high">Hoch</option>
          </select>
        </div>
        <div class="meta-col">
          <label class="detail-label">Ordner</label>
          <select id="modalFolder" class="detail-input"></select>
        </div>
        <div class="meta-col">
          <label class="detail-label">Wiederholung</label>
          <select id="modalRecur" class="detail-input">
            <option value="">Einmalig</option>
            <option value="daily">Täglich</option>
            <option value="weekly">Wöchentlich</option>
            <option value="monthly">Monatlich</option>
          </select>
        </div>
      </div>

      <div class="detail-row">
        <label class="detail-label">Deadline</label>
        <input type="datetime-local" id="modalDeadline" class="detail-input" />
      </div>

      <div class="detail-row">
        <label class="detail-label">Tags</label>
        <div class="tags-editor" id="modalTagsEditor"></div>
      </div>

      <div class="detail-row">
        <label class="detail-label">Beschreibung / Notizen</label>
        <textarea id="modalDesc" class="detail-input detail-desc" placeholder="Details..."></textarea>
      </div>

      <!-- SUBTASKS -->
      <div class="detail-row">
        <label class="detail-label">Unteraufgaben <span id="subtaskProgress" style="color:var(--success);"></span></label>
        <div class="subtask-list" id="subtaskList"></div>
        <div class="add-subtask-row">
          <input type="text" id="newSubtaskInput" placeholder="Neue Unteraufgabe..." />
          <button onclick="addSubtask()">+</button>
        </div>
      </div>

      <!-- TIMER -->
      <div class="detail-row">
        <label class="detail-label">Zeit-Tracker</label>
        <div class="timer-section">
          <div class="timer-big" id="modalTimerDisplay">00:00:00</div>
          <button class="timer-btn start" id="modalTimerBtn" onclick="toggleTimer()">▶ Start</button>
          <button class="timer-btn" onclick="resetTimer()" style="border-color:var(--text-muted);">↺ Reset</button>
        </div>
        <div class="timer-log" id="timerLog"></div>
      </div>

    </div>
    <div class="modal-footer">
      <span id="modalCreated" style="font-size:10px; color:var(--text-muted);"></span>
      <button class="btn-add" onclick="saveDetail()">Speichern</button>
    </div>
  </div>
</div>

<script>
// =====================================================
// DATA & STATE
// =====================================================
const KEY = 'todo_ultra_v1';
let data = { folders: [], todos: [], activityLog: [] };
let activeFolderId = 'all';
let currentView = 'list';
let currentDetailId = null;
let searchQuery = '';
let statusFilter = 'all';
let activeTagFilter = 'all';
let selectedIds = new Set();

// Timer state
let timerInterval = null;
let timerStartTime = null;
let timerElapsed = 0; // ms accumulated before current start
let timerTaskId = null;

// =====================================================
// PERSISTENCE
// =====================================================
function load() {
  let raw = localStorage.getItem(KEY);
  if (!raw) {
    // Migrate from old key
    const oldRaw = localStorage.getItem('todo_list_v2_kanban');
    if (oldRaw) {
      const oldData = JSON.parse(oldRaw);
      data = {
        folders: oldData.folders || [],
        todos: (oldData.todos || []).map(t => migrateTask(t)),
        activityLog: []
      };
    } else {
      data = { folders: [{id: 'f_default', name: 'Allgemein'}], todos: [], activityLog: [] };
      activeFolderId = 'f_default';
    }
  } else {
    data = JSON.parse(raw);
    if (!data.activityLog) data.activityLog = [];
  }
  // Migration & field init for all tasks
  data.todos.forEach(t => migrateTask(t));
  if (activeFolderId !== 'all' && !data.folders.find(f => f.id === activeFolderId)) {
    activeFolderId = 'all';
  }
}

function migrateTask(t) {
  if (!t.status) t.status = t.done ? 'done' : 'todo';
  if (!t.deadline) t.deadline = null;
  if (!t.description) t.description = '';
  if (!t.tags) t.tags = [];
  if (!t.subtasks) t.subtasks = [];
  if (!t.recurType) t.recurType = '';
  if (!t.timerTotal) t.timerTotal = 0; // ms total tracked
  return t;
}

function save() {
  localStorage.setItem(KEY, JSON.stringify(data));
  render();
}

// =====================================================
// RECURRING TASKS: spawn next occurrence on complete
// =====================================================
function spawnRecurring(t) {
  if (!t.recurType) return;
  const now = new Date();
  let nextDeadline = null;
  if (t.deadline) {
    const d = new Date(t.deadline);
    if (t.recurType === 'daily') d.setDate(d.getDate() + 1);
    else if (t.recurType === 'weekly') d.setDate(d.getDate() + 7);
    else if (t.recurType === 'monthly') d.setMonth(d.getMonth() + 1);
    nextDeadline = d.toISOString();
  }
  const newId = Date.now().toString(36) + Math.random().toString(36).substr(2);
  data.todos.push({
    id: newId, text: t.text, done: false, status: 'todo',
    prio: t.prio, folderId: t.folderId,
    created: now.toISOString(), deadline: nextDeadline,
    description: t.description, tags: [...t.tags],
    subtasks: t.subtasks.map(s => ({...s, done: false})),
    recurType: t.recurType, timerTotal: 0
  });
}

// =====================================================
// ACTIVITY LOG
// =====================================================
function logActivity(type) {
  const today = new Date().toISOString().slice(0,10);
  const entry = data.activityLog.find(e => e.date === today);
  if (entry) { entry[type] = (entry[type] || 0) + 1; }
  else { const e = {date: today}; e[type] = 1; data.activityLog.push(e); }
  // Keep last 30 days
  if (data.activityLog.length > 30) data.activityLog = data.activityLog.slice(-30);
}

// =====================================================
// SEARCH & FILTER
// =====================================================
function onSearch() {
  const val = document.getElementById('searchInput').value;
  searchQuery = val.toLowerCase();
  document.getElementById('searchClear').classList.toggle('visible', val.length > 0);
  render();
}
function clearSearch() {
  document.getElementById('searchInput').value = '';
  searchQuery = '';
  document.getElementById('searchClear').classList.remove('visible');
  render();
}
function setStatusFilter(f) {
  statusFilter = f;
  ['All','Todo','Urgent','Overdue','Recur','Done'].forEach(x => {
    const el = document.getElementById('fp' + x);
    if(el) el.classList.remove('active');
  });
  const map = {all:'fpAll',todo:'fpTodo',urgent:'fpUrgent',overdue:'fpOverdue',recurring:'fpRecur',done:'fpDone'};
  const el = document.getElementById(map[f]);
  if(el) el.classList.add('active');
  render();
}
function filterByTag(tag) {
  activeTagFilter = tag;
  document.querySelectorAll('.tag-chip').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-tag') === tag);
  });
  render();
}

function applyFilters(todos) {
  let list = [...todos];
  if (activeFolderId !== 'all') list = list.filter(t => t.folderId === activeFolderId);
  if (searchQuery) list = list.filter(t => t.text.toLowerCase().includes(searchQuery) || t.description.toLowerCase().includes(searchQuery) || t.tags.some(tag => tag.toLowerCase().includes(searchQuery)));
  if (activeTagFilter !== 'all') list = list.filter(t => t.tags.includes(activeTagFilter));
  const now = new Date();
  if (statusFilter === 'todo') list = list.filter(t => !t.done);
  else if (statusFilter === 'done') list = list.filter(t => t.done);
  else if (statusFilter === 'urgent') list = list.filter(t => !t.done && t.deadline && (new Date(t.deadline) - now) < 86400000 && (new Date(t.deadline) - now) > 0);
  else if (statusFilter === 'overdue') list = list.filter(t => !t.done && t.deadline && new Date(t.deadline) < now);
  else if (statusFilter === 'recurring') list = list.filter(t => t.recurType);
  return list;
}

// =====================================================
// UI HELPERS
// =====================================================
function toggleDateInput() {
  const chk = document.getElementById('hasDeadlineToggle');
  const inp = document.getElementById('deadlineInput');
  inp.classList.toggle('visible', chk.checked);
  if (!chk.checked) inp.value = '';
  else inp.focus();
}

function getDeadlineInfo(isoString) {
  if (!isoString) return null;
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = date - now;
  const diffHrs = diffMs / (1000 * 60 * 60);
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  const formatted = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  let status = 'normal', relativeText = '';
  if (diffMs < 0) {
    status = 'overdue';
    relativeText = Math.abs(Math.floor(diffDays)) < 1 ? 'Seit heute überfällig' : `Seit ${Math.floor(Math.abs(diffDays))}d überfällig`;
  } else if (diffHrs < 24) {
    status = 'urgent';
    const h = Math.floor(diffHrs);
    relativeText = h === 0 ? `In ${Math.floor(diffMs / 60000)} Min.` : `In ca. ${h} Std.`;
  } else {
    relativeText = formatted;
  }
  return { formatted, status, relativeText };
}

function getDeadlineHtml(isoString) {
  const info = getDeadlineInfo(isoString);
  if (!info) return '';
  return `<span class="dl-badge dl-${info.status}" data-deadline="${isoString}" title="${info.formatted}">⏰ ${info.relativeText}</span>`;
}

function updateRealtimeDeadlines() {
  document.querySelectorAll('.dl-badge[data-deadline]').forEach(badge => {
    const iso = badge.getAttribute('data-deadline');
    const info = getDeadlineInfo(iso);
    if (info) { badge.className = `dl-badge dl-${info.status}`; badge.innerHTML = `⏰ ${info.relativeText}`; }
  });
}

function formatTime(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}

function getTagColor(tag) {
  // Deterministic color from tag string
  const colors = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#06b6d4','#ec4899','#84cc16'];
  let hash = 0;
  for(let i = 0; i < tag.length; i++) hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function tagBadgeHtml(tag, small=true) {
  const color = getTagColor(tag);
  const size = small ? 'font-size:10px;padding:1px 6px;' : 'font-size:11px;padding:2px 8px;';
  return `<span class="tag-badge" style="${size}background:${color}22;color:${color};border:1px solid ${color}44;">${tag}</span>`;
}

// =====================================================
// DRAG AND DROP
// =====================================================
function drag(ev, id) { ev.dataTransfer.setData("text/plain", id); ev.dataTransfer.effectAllowed = "move"; }
function allowDrop(ev) { ev.preventDefault(); ev.currentTarget.classList.add('drag-over'); }
function removeDragStyle(ev) { ev.currentTarget.classList.remove('drag-over'); }
function drop(ev, newStatus) {
  ev.preventDefault(); ev.currentTarget.classList.remove('drag-over');
  const id = ev.dataTransfer.getData("text/plain");
  const t = data.todos.find(x => x.id === id);
  if (t) { t.status = newStatus; t.done = (newStatus === 'done'); save(); }
}

// =====================================================
// VIEW SWITCHING
// =====================================================
function switchView(mode) {
  currentView = mode;
  ['list','board','stats'].forEach(v => {
    document.getElementById('btnView' + v.charAt(0).toUpperCase() + v.slice(1)).className = v === mode ? 'view-btn active' : 'view-btn';
    const el = document.getElementById(v + 'View');
    if (v === 'board') el.style.display = mode === 'board' ? 'flex' : 'none';
    else el.style.display = mode === v ? (v === 'list' ? 'block' : 'block') : 'none';
  });
  document.getElementById('listView').style.display = mode === 'list' ? 'block' : 'none';
  document.getElementById('boardView').style.display = mode === 'board' ? 'flex' : 'none';
  document.getElementById('statsView').style.display = mode === 'stats' ? 'block' : 'none';
  render();
}

// =====================================================
// BULK ACTIONS
// =====================================================
function updateBulkBar() {
  const bar = document.getElementById('bulkBar');
  bar.classList.toggle('visible', selectedIds.size > 0);
  document.getElementById('bulkCount').innerText = selectedIds.size;
  // Fill bulk folder select
  const sel = document.getElementById('bulkFolderSel');
  sel.innerHTML = '<option value="">→ Ordner verschieben</option>';
  data.folders.forEach(f => { const o = document.createElement('option'); o.value = f.id; o.innerText = f.name; sel.appendChild(o); });
}
function toggleSelect(id) {
  if (selectedIds.has(id)) selectedIds.delete(id);
  else selectedIds.add(id);
  updateBulkBar();
  // Update item class without full re-render
  document.querySelectorAll('.item').forEach(el => {
    if(el.getAttribute('data-id') === id) el.classList.toggle('selected', selectedIds.has(id));
  });
  document.querySelectorAll('.sel-check').forEach(el => {
    if(el.getAttribute('data-id') === id) el.checked = selectedIds.has(id);
  });
}
function bulkSelectAll() {
  applyFilters(data.todos).forEach(t => selectedIds.add(t.id));
  updateBulkBar(); render();
}
function bulkDeselectAll() { selectedIds.clear(); updateBulkBar(); render(); }
function bulkDone() { selectedIds.forEach(id => { const t = data.todos.find(x=>x.id===id); if(t){t.done=true;t.status='done'; logActivity('done');} }); selectedIds.clear(); save(); }
function bulkUndone() { selectedIds.forEach(id => { const t = data.todos.find(x=>x.id===id); if(t){t.done=false;t.status='todo';} }); selectedIds.clear(); save(); }
function bulkDelete() {
  if(!confirm(`${selectedIds.size} Aufgaben löschen?`)) return;
  data.todos = data.todos.filter(t => !selectedIds.has(t.id));
  selectedIds.clear(); save();
}
function bulkMove() {
  const fId = document.getElementById('bulkFolderSel').value;
  if(!fId) return;
  selectedIds.forEach(id => { const t = data.todos.find(x=>x.id===id); if(t) t.folderId = fId; });
  selectedIds.clear(); save();
}

// =====================================================
// ACTIONS
// =====================================================
function addFolder() {
  const inp = document.getElementById('newFolderInput');
  const name = inp.value.trim(); if (!name) return;
  const id = 'f_' + Date.now();
  data.folders.push({id, name}); inp.value = '';
  activeFolderId = id; save();
}

function deleteFolder(id, event) {
  if(event) event.stopPropagation();
  if(!confirm('Ordner wirklich löschen?')) return;
  data.folders = data.folders.filter(f => f.id !== id);
  data.todos = data.todos.filter(t => t.folderId !== id);
  if(activeFolderId === id) activeFolderId = 'all';
  save();
}

function selectFolder(id) { activeFolderId = id; selectedIds.clear(); updateBulkBar(); render(); }

function addTask() {
  const inp = document.getElementById('newTask');
  const text = inp.value.trim(); if (!text) return;

  let targetFolder = activeFolderId;
  if (targetFolder === 'all') {
    targetFolder = data.folders.length > 0 ? data.folders[0].id : null;
    if(!targetFolder) { alert("Bitte erst einen Ordner erstellen!"); return; }
  }

  const hasDeadline = document.getElementById('hasDeadlineToggle').checked;
  const deadlineVal = document.getElementById('deadlineInput').value;
  let finalDeadline = (hasDeadline && deadlineVal) ? new Date(deadlineVal).toISOString() : null;

  // Tags aus dem Input
  const rawTag = document.getElementById('newTagInput').value.trim().replace(/^#/, '').toLowerCase();
  const tags = rawTag ? [rawTag] : [];

  const recurType = document.getElementById('newRecur').value;

  const newId = Date.now().toString(36) + Math.random().toString(36).substr(2);
  data.todos.push({
    id: newId, text, done: false, status: 'todo',
    prio: document.getElementById('newPrio').value, folderId: targetFolder,
    created: new Date().toISOString(), deadline: finalDeadline,
    description: '', tags, subtasks: [], recurType, timerTotal: 0
  });
  inp.value = ''; document.getElementById('newTagInput').value = '';
  document.getElementById('hasDeadlineToggle').checked = false;
  document.getElementById('newRecur').value = '';
  toggleDateInput();
  logActivity('added');
  save();
}

function toggle(id) {
  const t = data.todos.find(x => x.id === id);
  if (t) {
    t.done = !t.done;
    if (t.done) {
      t.status = 'done';
      logActivity('done');
      if (t.recurType) spawnRecurring(t);
    } else {
      t.status = 'todo';
    }
    save();
  }
}

function del(id) {
  if(confirm('Aufgabe löschen?')) { data.todos = data.todos.filter(x => x.id !== id); save(); }
}

function clearDone() {
  if(confirm('Erledigte löschen?')) {
    data.todos = data.todos.filter(t => {
      const folderMatch = activeFolderId === 'all' || t.folderId === activeFolderId;
      return !(t.done && folderMatch);
    });
    save();
  }
}

// =====================================================
// TIMER
// =====================================================
function getTimerElapsed() {
  if (timerStartTime) return timerElapsed + (Date.now() - timerStartTime);
  return timerElapsed;
}

function toggleTimer() {
  if (timerInterval) {
    // Stop
    clearInterval(timerInterval); timerInterval = null;
    timerElapsed = getTimerElapsed();
    timerStartTime = null;
    // Save to task
    const t = data.todos.find(x => x.id === timerTaskId);
    if(t) { t.timerTotal = (t.timerTotal || 0) + timerElapsed; timerElapsed = 0; save(); }
    document.getElementById('modalTimerBtn').className = 'timer-btn start';
    document.getElementById('modalTimerBtn').innerHTML = '▶ Start';
    updateTimerLog();
  } else {
    // Start
    timerStartTime = Date.now();
    timerInterval = setInterval(() => {
      document.getElementById('modalTimerDisplay').innerText = formatTime(getTimerElapsed());
    }, 1000);
    document.getElementById('modalTimerBtn').className = 'timer-btn stop';
    document.getElementById('modalTimerBtn').innerHTML = '■ Stop';
  }
}

function resetTimer() {
  if(timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  timerElapsed = 0; timerStartTime = null;
  document.getElementById('modalTimerDisplay').innerText = '00:00:00';
  document.getElementById('modalTimerBtn').className = 'timer-btn start';
  document.getElementById('modalTimerBtn').innerHTML = '▶ Start';
}

function updateTimerLog() {
  const t = data.todos.find(x => x.id === timerTaskId);
  if(t && t.timerTotal > 0) {
    document.getElementById('timerLog').innerText = `Gesamt: ${formatTime(t.timerTotal)}`;
  } else {
    document.getElementById('timerLog').innerText = '';
  }
}

// =====================================================
// SUBTASK LOGIC
// =====================================================
function renderSubtasks() {
  if(!currentDetailId) return;
  const t = data.todos.find(x => x.id === currentDetailId);
  if(!t) return;
  const listEl = document.getElementById('subtaskList');
  listEl.innerHTML = '';
  (t.subtasks || []).forEach((sub, idx) => {
    const div = document.createElement('div');
    div.className = 'subtask-item';
    div.innerHTML = `
      <input type="checkbox" class="sub-check" ${sub.done?'checked':''} onchange="toggleSubtask(${idx})">
      <span class="sub-text ${sub.done?'done':''}">${sub.text}</span>
      <button class="sub-del" onclick="deleteSubtask(${idx})">×</button>
    `;
    listEl.appendChild(div);
  });
  const done = (t.subtasks||[]).filter(s=>s.done).length;
  const total = (t.subtasks||[]).length;
  document.getElementById('subtaskProgress').innerText = total > 0 ? `${done}/${total}` : '';
}

function addSubtask() {
  const inp = document.getElementById('newSubtaskInput');
  const text = inp.value.trim(); if(!text || !currentDetailId) return;
  const t = data.todos.find(x => x.id === currentDetailId);
  if(t) { t.subtasks.push({text, done: false}); inp.value = ''; renderSubtasks(); }
}

function toggleSubtask(idx) {
  const t = data.todos.find(x => x.id === currentDetailId);
  if(t && t.subtasks[idx]) { t.subtasks[idx].done = !t.subtasks[idx].done; renderSubtasks(); }
}

function deleteSubtask(idx) {
  const t = data.todos.find(x => x.id === currentDetailId);
  if(t) { t.subtasks.splice(idx, 1); renderSubtasks(); }
}

// =====================================================
// TAGS EDITOR
// =====================================================
function renderTagsEditor(taskTags) {
  const editor = document.getElementById('modalTagsEditor');
  editor.innerHTML = '';
  (taskTags||[]).forEach(tag => {
    const color = getTagColor(tag);
    const span = document.createElement('span');
    span.className = 'tag-badge-editable';
    span.style = `background:${color}22;color:${color};border:1px solid ${color}44;`;
    span.innerHTML = `${tag} <span class="tag-x" onclick="removeModalTag('${tag}')">×</span>`;
    editor.appendChild(span);
  });
  const addBtn = document.createElement('button');
  addBtn.className = 'tag-add-btn';
  addBtn.innerText = '+ Tag';
  addBtn.onclick = () => {
    const tag = prompt('Tag eingeben:');
    if(tag && tag.trim()) addModalTag(tag.trim().toLowerCase().replace(/^#/,''));
  };
  editor.appendChild(addBtn);
}

function addModalTag(tag) {
  const t = data.todos.find(x => x.id === currentDetailId);
  if(t && !t.tags.includes(tag)) { t.tags.push(tag); renderTagsEditor(t.tags); }
}

function removeModalTag(tag) {
  const t = data.todos.find(x => x.id === currentDetailId);
  if(t) { t.tags = t.tags.filter(x => x !== tag); renderTagsEditor(t.tags); }
}

// =====================================================
// DETAIL MODAL
// =====================================================
function openDetail(id) {
  const t = data.todos.find(x => x.id === id);
  if (!t) return;
  currentDetailId = id;

  document.getElementById('modalId').value = t.id;
  document.getElementById('modalTitle').value = t.text;
  document.getElementById('modalPrio').value = t.prio;
  document.getElementById('modalDesc').value = t.description || '';
  document.getElementById('modalRecur').value = t.recurType || '';

  const folderSel = document.getElementById('modalFolder');
  folderSel.innerHTML = '';
  data.folders.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f.id; opt.innerText = f.name;
    if (f.id === t.folderId) opt.selected = true;
    folderSel.appendChild(opt);
  });

  const dlInput = document.getElementById('modalDeadline');
  if(t.deadline) {
    const d = new Date(t.deadline);
    const dLocal = new Date(d.getTime() - (d.getTimezoneOffset() * 60000));
    dlInput.value = dLocal.toISOString().slice(0,16);
  } else dlInput.value = '';

  document.getElementById('modalCreated').innerText = 'Erstellt: ' + new Date(t.created).toLocaleString();

  // Timer state
  if(timerTaskId !== id) {
    // If switching tasks, stop existing timer
    if(timerInterval) { clearInterval(timerInterval); timerInterval = null; }
    timerElapsed = 0; timerStartTime = null;
    timerTaskId = id;
  }
  document.getElementById('modalTimerDisplay').innerText = formatTime(timerElapsed);
  document.getElementById('modalTimerBtn').className = timerInterval ? 'timer-btn stop' : 'timer-btn start';
  document.getElementById('modalTimerBtn').innerHTML = timerInterval ? '■ Stop' : '▶ Start';
  updateTimerLog();

  renderSubtasks();
  renderTagsEditor(t.tags);

  document.getElementById('detailModal').style.display = 'flex';
}

function closeDetail(e) {
  if (e && e.target !== e.currentTarget) return;
  document.getElementById('detailModal').style.display = 'none';
  currentDetailId = null;
}

function saveDetail() {
  if (!currentDetailId) return;
  const t = data.todos.find(x => x.id === currentDetailId);
  if (!t) return;

  t.text = document.getElementById('modalTitle').value;
  t.prio = document.getElementById('modalPrio').value;
  t.folderId = document.getElementById('modalFolder').value;
  t.description = document.getElementById('modalDesc').value;
  t.recurType = document.getElementById('modalRecur').value;

  const dlVal = document.getElementById('modalDeadline').value;
  t.deadline = dlVal ? new Date(dlVal).toISOString() : null;

  save();
  document.getElementById('detailModal').style.display = 'none';
  currentDetailId = null;
}

// =====================================================
// EXPORT
// =====================================================
function exportJSON() {
  const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'todos_export.json'; a.click();
}
function exportCSV() {
  const rows = [['ID','Text','Prio','Status','Folder','Deadline','Tags','Timer(min)','Created']];
  data.todos.forEach(t => {
    const folder = data.folders.find(f => f.id === t.folderId);
    rows.push([t.id, `"${t.text.replace(/"/g,'""')}"`, t.prio, t.status,
      folder ? folder.name : '', t.deadline || '',
      t.tags.join(';'), Math.round((t.timerTotal||0)/60000), t.created]);
  });
  const csv = rows.map(r => r.join(',')).join('\\n');
  const blob = new Blob([csv], {type: 'text/csv'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'todos_export.csv'; a.click();
}

// =====================================================
// RENDER
// =====================================================
function render() {
  renderFolders();
  renderTagsFilterSidebar();
  renderSideStats();
  updateBulkBar();

  const headerTitle = document.getElementById('headerTitle');
  if (activeFolderId === 'all') headerTitle.innerText = 'Alle Aufgaben';
  else {
    const curr = data.folders.find(f => f.id === activeFolderId);
    headerTitle.innerText = curr ? curr.name : 'Unbekannt';
  }

  const visible = applyFilters(data.todos);
  if (currentView === 'list') renderList(visible);
  else if (currentView === 'board') renderBoard(applyFilters(data.todos));
  else renderStats();
}

function renderFolders() {
  const fList = document.getElementById('folderList');
  fList.innerHTML = '';
  const allDiv = document.createElement('div');
  const allCount = data.todos.filter(t => !t.done && (activeFolderId === 'all' || true)).length;
  const openCount = data.todos.filter(t => !t.done).length;
  allDiv.className = `folder-row ${activeFolderId === 'all' ? 'active' : ''}`;
  allDiv.innerHTML = `<div class="folder-info"><span class="folder-name">Alle Aufgaben</span><span class="folder-count">${openCount}</span></div><div style="width:22px;"></div>`;
  allDiv.onclick = () => selectFolder('all');
  fList.appendChild(allDiv);

  data.folders.forEach(f => {
    const div = document.createElement('div');
    const count = data.todos.filter(t => t.folderId === f.id && !t.done).length;
    div.className = `folder-row ${activeFolderId === f.id ? 'active' : ''}`;
    div.innerHTML = `<div class="folder-info"><span class="folder-name">${f.name}</span><span class="folder-count">${count}</span></div><button class="btn-folder-del" onclick="deleteFolder('${f.id}', event)">×</button>`;
    div.onclick = () => selectFolder(f.id);
    fList.appendChild(div);
  });
}

function renderTagsFilterSidebar() {
  const container = document.getElementById('tagsFilter');
  // Collect all unique tags
  const allTags = new Set();
  data.todos.forEach(t => t.tags.forEach(tag => allTags.add(tag)));
  container.innerHTML = '';
  const allChip = document.createElement('span');
  allChip.className = 'tag-chip' + (activeTagFilter === 'all' ? ' active' : '');
  allChip.setAttribute('data-tag','all');
  allChip.innerText = 'Alle';
  allChip.onclick = () => filterByTag('all');
  container.appendChild(allChip);
  allTags.forEach(tag => {
    const color = getTagColor(tag);
    const chip = document.createElement('span');
    chip.className = 'tag-chip' + (activeTagFilter === tag ? ' active' : '');
    chip.setAttribute('data-tag', tag);
    chip.innerHTML = `<span class="tag-dot" style="background:${color};"></span>${tag}`;
    chip.onclick = () => filterByTag(tag);
    container.appendChild(chip);
  });
}

function renderSideStats() {
  const today = new Date().toISOString().slice(0,10);
  const todayLog = data.activityLog.find(e => e.date === today);
  const doneToday = todayLog ? (todayLog.done || 0) : 0;
  document.getElementById('sideStatDone').innerText = doneToday;

  // Streak: consecutive days with at least 1 done
  let streak = 0;
  const d = new Date(); d.setHours(0,0,0,0);
  for(let i = 0; i < 30; i++) {
    const key = d.toISOString().slice(0,10);
    const entry = data.activityLog.find(e => e.date === key);
    if(entry && (entry.done || 0) > 0) { streak++; d.setDate(d.getDate()-1); }
    else { if(i === 0) { d.setDate(d.getDate()-1); continue; } break; }
  }
  document.getElementById('sideStreak').innerText = `🔥 ${streak}d`;

  const total = data.todos.length;
  const done = data.todos.filter(t => t.done).length;
  const pct = total > 0 ? Math.round(done/total*100) : 0;
  document.getElementById('sideProgress').style.width = pct + '%';
}

function renderList(todos) {
  const tList = document.getElementById('listView');
  tList.innerHTML = '';
  if(!todos.length) {
    tList.innerHTML = '<div style="text-align:center;color:var(--text-muted);margin-top:40px;font-size:13px;">Keine Aufgaben</div>';
    return;
  }
  const prioScore = { high: 3, med: 2, low: 1 };
  const sorted = [...todos].sort((a, b) => {
    if (a.done !== b.done) return a.done - b.done;
    if (!a.done) {
      const now = new Date().getTime();
      const aDl = a.deadline ? new Date(a.deadline).getTime() : Infinity;
      const bDl = b.deadline ? new Date(b.deadline).getTime() : Infinity;
      if ((aDl < now) !== (bDl < now)) return (aDl < now) ? -1 : 1;
    }
    return (prioScore[b.prio]||1) - (prioScore[a.prio]||1);
  });

  sorted.forEach(t => {
    const item = document.createElement('div');
    item.className = `item ${selectedIds.has(t.id) ? 'selected' : ''} ${(timerTaskId === t.id && timerInterval) ? 'timer-running' : ''}`;
    item.setAttribute('data-id', t.id);

    let folderName = '';
    if (activeFolderId === 'all') {
      const f = data.folders.find(x => x.id === t.folderId);
      if (f) folderName = `<span class="badge">${f.name}</span>`;
    }

    const deadlineHtml = t.done ? '' : getDeadlineHtml(t.deadline);
    const descIcon = (t.description && t.description.trim()) ? '<span title="Notizen">📄</span>' : '';
    const recurIcon = t.recurType ? `<span class="recur-icon">🔄</span>` : '';

    // Subtask progress
    let subtaskHtml = '';
    if(t.subtasks && t.subtasks.length > 0) {
      const done = t.subtasks.filter(s=>s.done).length;
      const pct = Math.round(done/t.subtasks.length*100);
      subtaskHtml = `<div class="subtask-progress"><span class="subtask-bar-wrap"><span class="subtask-bar-fill" style="width:${pct}%"></span></span><span class="subtask-text">${done}/${t.subtasks.length}</span></div>`;
    }

    // Tag badges
    const tagsHtml = t.tags.map(tag => tagBadgeHtml(tag)).join('');

    // Timer display
    const timerHtml = t.timerTotal > 0 ? `<span class="timer-display">⏱ ${formatTime(t.timerTotal)}</span>` : '';

    item.innerHTML = `
      <input type="checkbox" class="sel-check" data-id="${t.id}" ${selectedIds.has(t.id)?'checked':''} onchange="toggleSelect('${t.id}')">
      <div class="check ${t.done?'checked':''}" onclick="toggle('${t.id}')">${t.done?'✓':''}</div>
      <div class="prio-indicator prio-${t.prio||'low'}"></div>
      <div class="text-content" onclick="openDetail('${t.id}')">
        <div class="task-text ${t.done?'done':''}">${t.text}</div>
        <div class="task-meta">
          ${deadlineHtml} ${folderName} ${tagsHtml} ${recurIcon} ${descIcon} ${timerHtml}
        </div>
        ${subtaskHtml}
      </div>
      <div class="btn-actions">
        <button class="btn-icon-small btn-timer ${(timerTaskId===t.id&&timerInterval)?'running':''}" onclick="quickTimer('${t.id}')" title="Timer">⏱</button>
        <button class="btn-icon-small" onclick="openDetail('${t.id}')" title="Details">✎</button>
        <button class="btn-icon-small btn-del" onclick="del('${t.id}')" title="Löschen">×</button>
      </div>
    `;
    tList.appendChild(item);
  });
}

function quickTimer(id) {
  // Quick toggle timer from list without opening detail
  if (timerTaskId === id && timerInterval) {
    clearInterval(timerInterval); timerInterval = null;
    const elapsed = getTimerElapsed();
    timerElapsed = 0; timerStartTime = null;
    const t = data.todos.find(x => x.id === id);
    if(t) { t.timerTotal = (t.timerTotal||0) + elapsed; save(); }
  } else {
    if(timerInterval) {
      clearInterval(timerInterval); timerInterval = null;
      const elapsed = getTimerElapsed(); timerElapsed = 0; timerStartTime = null;
      const prev = data.todos.find(x => x.id === timerTaskId);
      if(prev) { prev.timerTotal = (prev.timerTotal||0) + elapsed; }
    }
    timerTaskId = id; timerElapsed = 0; timerStartTime = Date.now();
    timerInterval = setInterval(() => {}, 1000);
    save();
  }
}

function renderBoard(todos) {
  const cols = { todo: document.getElementById('col-todo'), doing: document.getElementById('col-doing'), done: document.getElementById('col-done') };
  Object.values(cols).forEach(c => c.innerHTML = '');
  const groups = { todo: [], doing: [], done: [] };
  const prioScore = { high: 3, med: 2, low: 1 };
  todos.sort((a, b) => (prioScore[b.prio]||1) - (prioScore[a.prio]||1));
  todos.forEach(t => { let s = t.status || (t.done ? 'done' : 'todo'); if(!groups[s]) s = 'todo'; groups[s].push(t); });

  document.getElementById('cnt-todo').innerText = groups.todo.length;
  document.getElementById('cnt-doing').innerText = groups.doing.length;
  document.getElementById('cnt-done').innerText = groups.done.length;

  const createCard = (t) => {
    const card = document.createElement('div');
    card.className = 'board-card'; card.draggable = true;
    card.ondragstart = (e) => drag(e, t.id);
    let folderBadge = '';
    if (activeFolderId === 'all') {
      const f = data.folders.find(x => x.id === t.folderId);
      if (f) folderBadge = `<span class="badge" style="font-size:10px;">${f.name}</span>`;
    }
    const deadlineHtml = t.done ? '' : getDeadlineHtml(t.deadline);
    const tagsHtml = t.tags.map(tag => tagBadgeHtml(tag)).join('');
    let subtaskHtml = '';
    if(t.subtasks && t.subtasks.length > 0) {
      const done = t.subtasks.filter(s=>s.done).length;
      const pct = Math.round(done/t.subtasks.length*100);
      subtaskHtml = `<div style="margin-top:5px;"><span class="subtask-bar-wrap" style="width:100%;display:block;"><span class="subtask-bar-fill" style="width:${pct}%"></span></span><span style="font-size:10px;color:var(--text-muted);">${done}/${t.subtasks.length} Subtasks</span></div>`;
    }
    card.innerHTML = `
      <div class="card-top">
        <div class="prio-indicator prio-${t.prio||'low'}"></div>
        <div style="display:flex;gap:2px;">
          <button style="border:none;background:none;color:var(--text-muted);cursor:pointer;font-size:13px;" onclick="openDetail('${t.id}')">✎</button>
          <button style="border:none;background:none;color:var(--text-muted);cursor:pointer;font-size:13px;" onclick="del('${t.id}')">×</button>
        </div>
      </div>
      <div class="card-text ${t.done?'done':''}" onclick="openDetail('${t.id}')">${t.text}</div>
      ${subtaskHtml}
      <div class="card-footer">${deadlineHtml} ${tagsHtml} ${folderBadge}</div>
    `;
    return card;
  };
  groups.todo.forEach(t => cols.todo.appendChild(createCard(t)));
  groups.doing.forEach(t => cols.doing.appendChild(createCard(t)));
  groups.done.forEach(t => cols.done.appendChild(createCard(t)));
}

// =====================================================
// STATS VIEW
// =====================================================
function renderStats() {
  const statsEl = document.getElementById('statsView');
  const total = data.todos.length;
  const done = data.todos.filter(t => t.done).length;
  const open = total - done;
  const overdue = data.todos.filter(t => !t.done && t.deadline && new Date(t.deadline) < new Date()).length;
  const highPrio = data.todos.filter(t => !t.done && t.prio === 'high').length;
  const totalTime = data.todos.reduce((sum, t) => sum + (t.timerTotal||0), 0);
  const pct = total > 0 ? Math.round(done/total*100) : 0;

  // Activity chart data (last 14 days)
  const days = [];
  const d = new Date(); d.setHours(0,0,0,0);
  for(let i = 13; i >= 0; i--) {
    const dd = new Date(d); dd.setDate(dd.getDate()-i);
    const key = dd.toISOString().slice(0,10);
    const entry = data.activityLog.find(e => e.date === key);
    days.push({ key, done: entry ? (entry.done||0) : 0, label: dd.toLocaleDateString(undefined,{day:'2-digit',month:'2-digit'}) });
  }
  const maxDone = Math.max(...days.map(d=>d.done), 1);

  // Prio distribution
  const hCount = data.todos.filter(t=>!t.done&&t.prio==='high').length;
  const mCount = data.todos.filter(t=>!t.done&&t.prio==='med').length;
  const lCount = data.todos.filter(t=>!t.done&&t.prio==='low').length;
  const prioTotal = hCount+mCount+lCount || 1;

  // Top tags
  const tagCounts = {};
  data.todos.forEach(t => t.tags.forEach(tag => { tagCounts[tag] = (tagCounts[tag]||0) + 1; }));
  const topTags = Object.entries(tagCounts).sort((a,b)=>b[1]-a[1]).slice(0,5);

  statsEl.innerHTML = `
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Gesamt</div>
        <div class="stat-value">${total}</div>
        <div class="stat-sub">${open} offen · ${done} erledigt</div>
        <div class="stat-bar"><div class="stat-bar-fill" style="width:${pct}%"></div></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Überfällig</div>
        <div class="stat-value" style="color:${overdue>0?'var(--overdue)':'var(--success)'}">${overdue}</div>
        <div class="stat-sub">${highPrio} hoch priorisiert</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Tracked Zeit</div>
        <div class="stat-value" style="font-size:20px;">${formatTime(totalTime)}</div>
        <div class="stat-sub">Über alle Aufgaben</div>
      </div>
    </div>

    <div class="chart-section">
      <div class="chart-title">Erledigte Aufgaben – Letzte 14 Tage</div>
      <div class="activity-chart">
        ${days.map(d => `<div class="activity-bar" style="height:${Math.round(d.done/maxDone*100)}%" title="${d.label}: ${d.done} erledigt"></div>`).join('')}
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:4px;">
        <span style="font-size:9px;color:var(--text-muted);">${days[0].label}</span>
        <span style="font-size:9px;color:var(--text-muted);">${days[days.length-1].label}</span>
      </div>
    </div>

    <div class="chart-section">
      <div class="chart-title">Prioritäten (offene Tasks)</div>
      <div class="prio-dist">
        <div class="prio-seg" style="width:${Math.round(hCount/prioTotal*100)}%;background:var(--prio-high);" title="Hoch: ${hCount}"></div>
        <div class="prio-seg" style="width:${Math.round(mCount/prioTotal*100)}%;background:var(--prio-med);" title="Mittel: ${mCount}"></div>
        <div class="prio-seg" style="width:${Math.round(lCount/prioTotal*100)}%;background:var(--prio-low);opacity:0.5;" title="Niedrig: ${lCount}"></div>
      </div>
      <div style="display:flex;gap:12px;margin-top:6px;font-size:11px;color:var(--text-muted);">
        <span>🔴 Hoch: ${hCount}</span>
        <span>🟡 Mittel: ${mCount}</span>
        <span>🟢 Niedrig: ${lCount}</span>
      </div>
    </div>

    ${topTags.length > 0 ? `
    <div class="chart-section">
      <div class="chart-title">Top Tags</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:4px;">
        ${topTags.map(([tag,count]) => `${tagBadgeHtml(tag, false)} <span style="font-size:11px;color:var(--text-muted);vertical-align:middle;">${count}×</span>`).join('')}
      </div>
    </div>` : ''}
  `;
}

// =====================================================
// KEYBOARD SHORTCUTS
// =====================================================
document.addEventListener('keydown', (e) => {
  const tag = document.activeElement.tagName;
  const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

  if (e.key === 'Escape') {
    closeDetail(); clearSearch();
  }
  if (!inInput) {
    if (e.key === 'n' || e.key === 'N') { document.getElementById('newTask').focus(); e.preventDefault(); }
    if (e.key === 'f' && e.ctrlKey) { document.getElementById('searchInput').focus(); e.preventDefault(); }
    if (e.key === '1') { document.getElementById('newPrio').value = 'low'; }
    if (e.key === '2') { document.getElementById('newPrio').value = 'med'; }
    if (e.key === '3') { document.getElementById('newPrio').value = 'high'; }
    if (e.key === 'l') switchView('list');
    if (e.key === 'b') switchView('board');
    if (e.key === 's') switchView('stats');
  }
  if (inInput && e.key === 'Enter' && document.activeElement.id === 'newTask') addTask();
  if (inInput && e.key === 'Enter' && document.activeElement.id === 'newFolderInput') addFolder();
  if (inInput && e.key === 'Enter' && document.activeElement.id === 'newSubtaskInput') addSubtask();
  if (inInput && e.key === 'Enter' && document.activeElement.id === 'modalTitle') saveDetail();
});

// =====================================================
// INIT & REALTIME
// =====================================================
load();
switchView('list');
setInterval(updateRealtimeDeadlines, 10000);
</script>
</body>
</html>"""
        return template.replace("__BODY_CLASS__", body_class)

    # ---------------------------------------------------------
    # 2. POPUP MODE HTML (Kompakt mit Search & Tag Filter)
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
    --bg-color: #2e2e2e; --success: #10b981; --text-main: #e6eef8;
    --border-color: rgba(255,255,255,0.1); --prio-high: #ef4444;
    --prio-med: #f59e0b; --prio-low: #888; --overdue: #ef4444;
  }
  *{ box-sizing: border-box; outline: none; box-shadow: none !important; }
  html, body { height: 100%; margin: 0; padding: 0; overflow: hidden; }
  body { background: var(--bg-color); color: var(--text-main); font-family: sans-serif; display: flex; flex-direction: column; }
  .app-container { display: flex; flex-direction: column; height: 100vh; padding: 10px; }
  .filter-row { margin-bottom: 6px; display: flex; gap: 5px; align-items: center; }
  .folder-select { flex:1; background: rgba(0,0,0,0.2); border: 1px solid var(--border-color); color: var(--text-main); border-radius: 4px; padding: 4px; font-size: 11px; }
  .folder-select option { background: #333; }
  .search-row { display: flex; align-items: center; gap: 5px; background: rgba(0,0,0,0.15); border: 1px solid var(--border-color); border-radius: 4px; padding: 4px 8px; margin-bottom: 6px; }
  .search-row input { flex:1; background: transparent; border: none !important; color: var(--text-main) !important; font-size: 12px; }
  .input-row { display: flex; gap: 6px; margin-bottom: 8px; border-bottom: 1px solid var(--border-color); padding-bottom: 6px; }
  input { flex: 1; background: transparent; border: none; color: inherit; font-size: 13px; }
  select { background: #333; color: #fff; border: 1px solid #555; border-radius: 4px; font-size: 11px; }
  .list { flex: 1; overflow-y: auto; }
  .item { display: flex; align-items: center; padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
  .checkbox { width: 14px; height: 14px; border: 1px solid rgba(255,255,255,0.3); border-radius: 3px; margin-right: 7px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .dot { width: 6px; height: 6px; border-radius: 50%; margin-right: 7px; flex-shrink: 0; }
  .dot-high { background: var(--prio-high); } .dot-med { background: var(--prio-med); } .dot-low { background: var(--prio-low); }
  .content { flex: 1; font-size: 13px; display: flex; flex-direction: column; min-width: 0; }
  .content-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dl-mini { font-size: 10px; color: #888; margin-top: 2px; }
  .dl-overdue { color: var(--overdue); font-weight: bold; }
  .empty-msg { text-align: center; color: rgba(255,255,255,0.3); margin-top: 20px; font-size: 12px; }
  .subtask-mini { font-size: 9px; color: #888; }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">
  <div class="app-container">
    <div class="filter-row">
      <select id="folderFilter" class="folder-select" onchange="switchFolder(this.value)">
        <option value="all">Alle Ordner</option>
      </select>
    </div>
    <div class="search-row">
      <span style="color:#888;font-size:12px;">🔍</span>
      <input type="text" id="popupSearch" placeholder="Suchen..." oninput="render()">
    </div>
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
const KEY = 'todo_ultra_v1';
let data = { folders: [], todos: [], activityLog: [] };
let activePopupFolder = 'all';

function load() {
  const raw = localStorage.getItem(KEY);
  if(raw) data = JSON.parse(raw);
  else {
    const old = localStorage.getItem('todo_list_v2_kanban');
    if(old) { const od = JSON.parse(old); data = {folders: od.folders||[], todos: od.todos||[], activityLog:[]}; }
    else { data = {folders:[{id:'d',name:'All'}], todos:[], activityLog:[]}; }
  }
  data.todos.forEach(t => { if(!t.tags)t.tags=[]; if(!t.subtasks)t.subtasks=[]; if(!t.timerTotal)t.timerTotal=0; if(!t.recurType)t.recurType=''; });
}

function save() { localStorage.setItem(KEY, JSON.stringify(data)); render(); }

function render() {
  const folderSel = document.getElementById('folderFilter');
  folderSel.innerHTML = '<option value="all">Alle Ordner</option>';
  data.folders.forEach(f => {
    const opt = document.createElement('option');
    opt.value = f.id; opt.innerText = f.name;
    if(f.id === activePopupFolder) opt.selected = true;
    folderSel.appendChild(opt);
  });
  folderSel.value = activePopupFolder;

  const query = document.getElementById('popupSearch').value.toLowerCase();
  let activeTodos = data.todos.filter(t => !t.done);
  if(activePopupFolder !== 'all') activeTodos = activeTodos.filter(t => t.folderId === activePopupFolder);
  if(query) activeTodos = activeTodos.filter(t => t.text.toLowerCase().includes(query) || (t.tags||[]).some(tag=>tag.includes(query)));

  const score = { high: 3, med: 2, low: 1 };
  activeTodos.sort((a,b) => (score[b.prio||'low']||1) - (score[a.prio||'low']||1));

  const listEl = document.getElementById('todoList');
  listEl.innerHTML = '';
  if (!activeTodos.length) { listEl.innerHTML = '<div class="empty-msg">Nichts zu tun!</div>'; return; }

  activeTodos.forEach(todo => {
    const item = document.createElement('div');
    item.className = 'item';
    const dot = document.createElement('div'); dot.className = 'dot dot-' + (todo.prio || 'low');
    const chk = document.createElement('div'); chk.className = 'checkbox'; chk.onclick = () => markDone(todo.id);
    const content = document.createElement('div'); content.className = 'content';

    let dlHtml = '';
    if(todo.deadline) dlHtml = `<span class="dl-mini" data-deadline="${todo.deadline}">⏰ ...</span>`;

    // Subtask progress
    let subHtml = '';
    if(todo.subtasks && todo.subtasks.length > 0) {
      const d = todo.subtasks.filter(s=>s.done).length;
      subHtml = `<span class="subtask-mini">${d}/${todo.subtasks.length} Subtasks</span>`;
    }

    content.innerHTML = `<span class="content-text">${todo.text}</span>${dlHtml}${subHtml}`;
    item.appendChild(chk); item.appendChild(dot); item.appendChild(content);
    listEl.appendChild(item);
  });
  updateDeadlines();
}

function updateDeadlines() {
  const now = new Date();
  document.querySelectorAll('.dl-mini[data-deadline]').forEach(el => {
    const d = new Date(el.getAttribute('data-deadline'));
    const diff = d - now;
    let txt;
    if(diff < 0) { txt = '⏰ Überfällig!'; el.classList.add('dl-overdue'); }
    else if(diff < 3600000) { txt = `⏰ In ${Math.floor(diff/60000)} Min.`; el.classList.remove('dl-overdue'); }
    else { txt = '⏰ ' + d.toLocaleDateString() + ' ' + d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}); el.classList.remove('dl-overdue'); }
    el.innerText = txt;
  });
}

function switchFolder(newId) { activePopupFolder = newId; render(); }

function addTodo() {
  const text = document.getElementById('newInput').value.trim();
  const prio = document.getElementById('prioInput').value;
  if (!text) return;
  let fId = activePopupFolder;
  if (fId === 'all') fId = data.folders.length > 0 ? data.folders[0].id : 'default';
  if(data.folders.length === 0) data.folders.push({id: 'default', name: 'Allgemein'});
  data.todos.push({
    id: Date.now().toString(36) + Math.random().toString(36).substr(2),
    text, done: false, status: 'todo', prio, folderId: fId,
    created: new Date().toISOString(), deadline: null,
    tags:[], subtasks:[], recurType:'', timerTotal: 0
  });
  save();
  document.getElementById('newInput').value = '';
}

function markDone(id) {
  const t = data.todos.find(x => x.id === id);
  if(t) { t.done = true; t.status = 'done'; save(); }
}

document.getElementById('newInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') addTodo(); });
load(); render();
setInterval(updateDeadlines, 10000);
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