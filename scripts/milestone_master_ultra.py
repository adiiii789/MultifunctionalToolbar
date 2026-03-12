from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
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


THEME_OVERRIDE_CSS = """
<style>
* { box-shadow: none !important; box-sizing: border-box; }

body.theme-dark {
  background: #202020 !important; /* Etwas weicheres Dunkelgrau statt fast Schwarz */
  color: #c4c4c4 !important; /* Entspanntes Hellgrau statt grellem Weiß */
  --bg: #202020;
  --sidebar-bg: #1a1a1a;
  --card-bg: #2a2a2a;
  --card-border: rgba(255,255,255,0.06);
  --input-bg: #252525;
  --border: rgba(255,255,255,0.08);
  --text: #c4c4c4;
  --muted: #808080;
  --accent: #9e9e9e; /* Sanftes Mittel-/Hellgrau für die Balken statt #ffffff */
  --accent2: #7a7a7a; 
  --success: #a6e3a1;
  --danger: #f38ba8;
  --warning: #fab387;
  --chip: rgba(255,255,255,0.05);
  --row-alt: rgba(255,255,255,0.02);
  --hover: rgba(255,255,255,0.04);
  --success-soft: rgba(166,227,161,0.15);
  --danger-soft: rgba(243,139,168,0.15);
  --warning-soft: rgba(250,179,135,0.15);
  --accent-soft: rgba(158,158,158,0.15);
}

body.theme-light {
  background: #f4f4f4 !important; /* Ein weicheres, wärmeres Hellgrau */
  color: #555555 !important; /* Dunkelgrau statt hartem Schwarz für den Text */
  --bg: #f4f4f4;
  --sidebar-bg: #eaeaea;
  --card-bg: #ffffff;
  --card-border: #e0e0e0;
  --input-bg: #f9f9f9;
  --border: #d8d8d8;
  --text: #555555;
  --muted: #999999;
  --accent: #7a7a7a; /* Sanftes Mittelgrau für die Balken statt tiefem Schwarz */
  --accent2: #9e9e9e;
  --success: #40a02b;
  --danger: #d20f39;
  --warning: #fe640b;
  --chip: rgba(0,0,0,0.04);
  --row-alt: rgba(0,0,0,0.02);
  --hover: rgba(0,0,0,0.03);
  --success-soft: rgba(64,160,43,0.12);
  --danger-soft: rgba(210,15,57,0.12);
  --warning-soft: rgba(254,100,11,0.12);
  --accent-soft: rgba(122,122,122,0.12);
}

body input, body textarea, body select {
  background: var(--input-bg) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 12px;
  font-family: inherit;
}
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
</style>
"""

THEME_SCRIPT = """
<script>
(function () {
  window.applyTheme = function(theme) {
    var cls = theme === 'light' ? 'theme-light' : 'theme-dark';
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(cls);
  };
})();
</script>
"""


class PluginWidget(QMainWindow):
    def __init__(self, theme="dark", mode="Window"):
        super().__init__()
        self.setWindowTitle("Milestone Master Ultra")
        self.resize(1200, 860)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        normalized = theme.lower() if isinstance(theme, str) else None
        host_theme = _detect_host_theme(normalized if normalized in SUPPORTED_THEMES else THEME_DARK)
        self._current_theme = host_theme if host_theme in SUPPORTED_THEMES else THEME_DARK
        self._current_mode = mode if mode in ("Window", "Popup") else "Window"
        self._view_ready = False
        self._theme_watcher = None

        body_class = "theme-" + self._current_theme
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
            self.destroyed.connect(self._cleanup_watcher)

    def _build_window_html(self, body_class):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Milestone Master Ultra</title>
<style>
html, body {
  height: 100%; margin: 0;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  overflow: hidden;
}
body { display: flex; background: var(--bg); color: var(--text); }

/* ===== LAYOUT ===== */
.app { display: flex; width: 100%; height: 100vh; overflow: hidden; }

/* ===== SIDEBAR ===== */
.sidebar {
  width: 200px; flex-shrink: 0;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--card-border);
  display: flex; flex-direction: column;
  padding: 12px 8px; gap: 2px; overflow-y: auto;
}
.logo {
  font-size: 13px; font-weight: 800; padding: 0 6px 12px;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  letter-spacing: .01em;
}
.sb-sec {
  font-size: 10px; text-transform: uppercase; letter-spacing: .1em;
  color: var(--muted); font-weight: 600; padding: 8px 6px 3px;
}
.sb-btn {
  width: 100%; padding: 7px 10px; border-radius: 8px; border: none;
  background: transparent; color: var(--muted); font-size: 12px;
  font-weight: 500; text-align: left; cursor: pointer;
  display: flex; align-items: center; gap: 7px; transition: background .1s;
  font-family: inherit;
}
.sb-btn:hover { background: var(--hover); color: var(--text); }
.sb-btn.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.proj-btn {
  width: 100%; padding: 6px 10px; border-radius: 8px; border: none;
  background: transparent; color: var(--muted); font-size: 12px;
  text-align: left; cursor: pointer; display: flex; align-items: center;
  gap: 4px; transition: background .1s; font-family: inherit;
}
.proj-btn:hover { background: var(--hover); color: var(--text); }
.proj-btn.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.proj-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.proj-badge {
  font-size: 10px; background: var(--chip); border-radius: 999px;
  padding: 1px 5px; color: var(--muted); flex-shrink: 0;
}
.proj-del {
  background: transparent; border: none; color: transparent;
  cursor: pointer; font-size: 14px; padding: 0 2px; line-height: 1;
}
.proj-btn:hover .proj-del { color: var(--muted); }
.proj-del:hover { color: var(--danger) !important; }
.add-proj-btn {
  margin-top: 4px; width: 100%; padding: 7px 10px;
  border: 1px dashed var(--border); border-radius: 8px;
  background: transparent; color: var(--muted); cursor: pointer;
  font-size: 12px; text-align: left; transition: all .1s; font-family: inherit;
}
.add-proj-btn:hover { border-color: var(--accent); color: var(--accent); }
.sb-spacer { flex: 1; }

/* ===== MAIN ===== */
.main { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }

/* TOP BAR */
.topbar {
  display: flex; align-items: center; gap: 10px; padding: 9px 18px;
  border-bottom: 1px solid var(--card-border); background: var(--card-bg); flex-shrink: 0;
}
.topbar-title {
  font-size: 15px; font-weight: 800; flex-shrink: 0;
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.topbar-info { flex: 1; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; font-size: 11px; color: var(--muted); }
.topbar-info strong { color: var(--text); }
.health-pill {
  display: flex; align-items: center; gap: 5px; padding: 3px 10px;
  border-radius: 999px; font-size: 11px; font-weight: 700;
  border: 1px solid var(--border); background: var(--chip); flex-shrink: 0;
}
.h-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.view-tabs { display: flex; background: var(--chip); border-radius: 8px; padding: 2px; gap: 1px; flex-shrink: 0; }
.vtab {
  padding: 4px 11px; border: none; background: transparent; color: var(--muted);
  font-size: 11px; font-weight: 600; cursor: pointer; border-radius: 6px;
  transition: all .1s; font-family: inherit;
}
.vtab.active { background: var(--card-bg); color: var(--text); }
.vtab:hover:not(.active) { color: var(--text); }

/* CONTENT AREA */
.content { flex: 1; overflow: hidden; display: flex; flex-direction: column; min-height: 0; }

/* ===== SHARED CARDS ===== */
.card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; }
.badge {
  display: inline-flex; align-items: center; padding: 2px 7px;
  border-radius: 999px; font-size: 10px; font-weight: 600;
  letter-spacing: .04em; text-transform: uppercase;
}
.bs { background: var(--success-soft); color: var(--success); }
.bd { background: var(--danger-soft); color: var(--danger); }
.bw { background: var(--warning-soft); color: var(--warning); }
.bn { background: var(--chip); color: var(--muted); }
.ba { background: var(--accent-soft); color: var(--accent); }

/* ===== DASHBOARD ===== */
#vDash {
  display: flex; flex-direction: column;
  padding: 14px 18px; gap: 10px; overflow-y: auto; height: 100%;
}
.proj-meta {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 10px 14px;
}
#projTitleInp {
  flex: 1; min-width: 150px; border: none !important; background: transparent !important;
  font-size: 15px !important; font-weight: 700 !important; color: var(--text) !important;
  padding: 0 !important; outline: none;
}
#projTitleInp:focus { border-bottom: 1px solid var(--accent) !important; border-radius: 0; }
.meta-lbl { font-size: 10px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.meta-date { max-width: 140px; font-size: 11px !important; padding: 3px 6px !important; }
.next-ms-box { margin-left: auto; font-size: 12px; color: var(--muted); display: flex; align-items: center; gap: 5px; }

.stat-row { display: flex; gap: 8px; flex-shrink: 0; }
.stat-card { flex: 1; padding: 12px 14px; }
.stat-lbl { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
.stat-val { font-size: 22px; font-weight: 700; margin-top: 2px; }
.stat-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.mini-bar { height: 3px; border-radius: 2px; background: var(--chip); margin-top: 8px; }
.mini-fill { height: 100%; border-radius: 2px; transition: width .5s; background: linear-gradient(90deg, var(--accent), var(--accent2)); }

.crit-card { padding: 10px 14px; border-left: 3px solid var(--danger); display: none; flex-shrink: 0; }
.crit-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--danger); margin-bottom: 5px; }

/* MS EDITOR (shared) */
.ms-editor { border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; flex: 1; min-height: 0; border: 1px solid var(--card-border); }
.ms-hdr {
  padding: 9px 16px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;
  background: var(--card-bg);
}
.ms-hdr h3 { margin: 0; font-size: 13px; font-weight: 700; }
.add-ms-btn {
  background: linear-gradient(135deg, var(--accent), var(--accent2));
  color: #fff; border: none; border-radius: 999px; padding: 5px 14px;
  font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit;
}
.add-ms-btn:hover { opacity: .9; }
.ms-list { flex: 1; overflow-y: auto; background: var(--card-bg); }

.ms-row {
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  display: grid;
  grid-template-columns: 20px 130px minmax(110px,1.2fr) 95px minmax(160px,2fr) 22px;
  gap: 7px; align-items: start;
}
.ms-row:nth-child(even) { background: var(--row-alt); }
.ms-row.hi-risk { border-left: 3px solid var(--danger); }

.ms-chk { cursor: pointer; margin-top: 3px; accent-color: var(--success); }
.ms-date-wrap { display: flex; flex-direction: column; gap: 2px; }
.ms-date-lbl { font-size: 9px; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }
.ms-date-inp { width: 100%; font-size: 11px !important; padding: 3px 4px !important; }

.ms-main { display: flex; flex-direction: column; gap: 2px; }
.ms-name-inp {
  width: 100%; border: none !important; background: transparent !important;
  font-weight: 600; font-size: 13px; color: var(--text) !important; padding: 0 !important;
}
.ms-name-inp:focus { border-bottom: 1px solid var(--accent) !important; border-radius: 0; outline: none; }
.ms-meta { font-size: 11px; color: var(--muted); display: flex; gap: 5px; align-items: center; flex-wrap: wrap; margin-top: 2px; }
.ms-prog { height: 3px; border-radius: 2px; background: var(--chip); margin-top: 4px; }
.ms-prog-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--success), var(--accent)); transition: width .4s; }

.risk-sel {
  font-size: 10px !important; padding: 2px 5px !important; border-radius: 999px !important;
  font-weight: 600; cursor: pointer; margin-bottom: 3px;
}
.risk-low { background: var(--success-soft) !important; color: var(--success) !important; border-color: var(--success) !important; }
.risk-medium { background: var(--warning-soft) !important; color: var(--warning) !important; border-color: var(--warning) !important; }
.risk-high { background: var(--danger-soft) !important; color: var(--danger) !important; border-color: var(--danger) !important; }
.dep-sel { font-size: 10px !important; padding: 2px 4px !important; max-width: 100%; }

.task-col { display: flex; flex-direction: column; gap: 2px; }
.task-sum { font-size: 11px; color: var(--muted); }
.task-line { display: grid; grid-template-columns: 15px 1fr 15px; align-items: center; gap: 3px; }
.task-cb { accent-color: var(--success); width: 13px; height: 13px; }
.task-txt { border: none !important; background: transparent !important; font-size: 12px; color: var(--text) !important; padding: 0 !important; }
.task-txt:focus { border-bottom: 1px solid var(--accent) !important; border-radius: 0; outline: none; }
.task-rm { border: none; background: transparent; color: var(--muted); cursor: pointer; font-size: 13px; line-height: 1; }
.task-rm:hover { color: var(--danger); }
.task-add { border: none; background: transparent; color: var(--accent); cursor: pointer; font-size: 11px; padding: 2px 0 0; font-family: inherit; }
.note-btn { border: none; background: transparent; color: var(--muted); cursor: pointer; font-size: 11px; padding: 2px 0 0; font-family: inherit; }
.note-btn:hover { color: var(--accent); }
.note-area {
  display: none; grid-column: 1/-1; width: 100%; min-height: 46px; resize: vertical;
  font-family: inherit; font-size: 12px !important; margin-top: 4px;
}
.note-area.vis { display: block; }
.ms-del { background: transparent; border: none; color: var(--muted); cursor: pointer; font-size: 18px; padding: 0; line-height: 1; }
.ms-del:hover { color: var(--danger); }

/* ===== TIMELINE ===== */
#vTimeline { display: none; flex-direction: column; padding: 14px 18px; gap: 10px; overflow: hidden; height: 100%; }
.tl-card { padding: 10px 14px 16px; flex-shrink: 0; }
.tl-hdr { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.tl-hdr-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }
.tl-container { position: relative; display: flex; align-items: center; min-height: 160px; padding-inline: 20px; margin: 10px 0; }
.tl-track { position: relative; width: 100%; height: 6px; background: var(--border); border-radius: 999px; }
.tl-prog { position: absolute; left: 0; top: 0; height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 999px; opacity: .85; transition: width .4s; }
.tl-now { position: absolute; top: -18px; bottom: -18px; width: 2px; background: var(--danger); z-index: 5; pointer-events: none; }
.tl-now::after {
  content: 'HEUTE'; position: absolute; top: -20px; left: -22px;
  background: var(--danger); color: #fff; font-size: 9px; padding: 2px 6px;
  border-radius: 999px; font-weight: 700; letter-spacing: .06em;
}
.ms-node {
  position: absolute; top: 50%; transform: translate(-50%, -50%);
  width: 16px; height: 16px; border-radius: 50%;
  border: 3px solid var(--muted); background: var(--card-bg);
  cursor: pointer; z-index: 10; transition: transform .15s;
}
.ms-node:hover { transform: translate(-50%,-50%) scale(1.3); z-index: 20; }
.ms-node.done { border-color: var(--success); background: var(--success); }
.ms-node.future { border-color: var(--accent); background: var(--accent-soft); }
.ms-node.overdue { border-color: var(--danger); background: var(--danger-soft); }
.ms-node.blocked { border-color: var(--warning); background: var(--warning-soft); }
.dep-line { position: absolute; top: 50%; height: 2px; background: var(--muted); z-index: 4; pointer-events: none; opacity: .35; }
.node-wrap {
  position: absolute; left: 50%; transform: translateX(-50%);
  width: 110px; text-align: center; pointer-events: none;
  display: flex; flex-direction: column; align-items: center;
}
.node-wrap::before { content: ''; display: block; width: 1px; height: 14px; background: var(--border); margin: 0 auto; }
.node-lbl { font-size: 11px; font-weight: 600; color: var(--text); line-height: 1.2; background: var(--card-bg); padding: 2px 4px; border-radius: 4px; }
.node-date { white-space: nowrap; font-size: 10px; color: var(--muted); margin-top: 2px; }
.node-wrap.bottom { top: 22px; }
.node-wrap.top { bottom: 22px; flex-direction: column-reverse; }
.node-wrap.top .node-date { margin-bottom: 2px; margin-top: 0; }

/* ===== GANTT ===== */
#vGantt { display: none; flex-direction: column; padding: 14px 18px; gap: 10px; overflow: hidden; height: 100%; }
.gantt-wrap { border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; flex: 1; min-height: 0; border: 1px solid var(--card-border); }
.gantt-hdr { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; height: 36px; background: var(--card-bg); }
.gantt-lbl { width: 200px; flex-shrink: 0; padding: 8px 12px; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 600; border-right: 1px solid var(--border); display: flex; align-items: center; }
.gantt-chart-hdr { flex: 1; position: relative; overflow: hidden; }
.gantt-body { flex: 1; overflow-y: auto; min-height: 0; background: var(--card-bg); }
.gantt-row { display: flex; border-bottom: 1px solid var(--border); min-height: 38px; align-items: center; }
.gantt-row:hover { background: var(--row-alt); }
.gantt-row-lbl { width: 200px; flex-shrink: 0; padding: 6px 12px; font-size: 12px; font-weight: 600; border-right: 1px solid var(--border); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 5px; }
.gantt-row-chart { flex: 1; position: relative; height: 38px; }
.gantt-bar {
  position: absolute; height: 22px; top: 50%; transform: translateY(-50%);
  border-radius: 5px; display: flex; align-items: center; padding: 0 7px;
  font-size: 10px; font-weight: 600; color: #fff; white-space: nowrap; overflow: hidden; min-width: 4px;
}
.gantt-bar.done { background: var(--success); }
.gantt-bar.overdue { background: var(--danger); }
.gantt-bar.normal { background: var(--accent); }
.gantt-today { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--danger); opacity: .7; z-index: 5; }
.gantt-grid { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border); opacity: .5; }
.gantt-mlbl { position: absolute; font-size: 9px; color: var(--muted); top: 10px; }

/* ===== BURNDOWN ===== */
#vBurn { display: none; flex-direction: column; padding: 14px 18px; gap: 10px; overflow-y: auto; height: 100%; }
.vel-row { display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }
.vel-card { flex: 1; min-width: 100px; padding: 10px 14px; }
.vel-val { font-size: 20px; font-weight: 700; }
.vel-lbl { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-top: 2px; }
.bn-card { padding: 14px; }
.bn-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); margin-bottom: 10px; }
.heat-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.heat-item { flex: 1; min-width: 120px; border-radius: 10px; padding: 10px 12px; border: 2px solid transparent; }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">

<div class="app">

  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="logo">🏔 Milestone Master</div>

    <div class="sb-sec">Views</div>
    <button class="sb-btn active" id="sb-dash" onclick="switchTab('dash')">📊 Dashboard</button>
    <button class="sb-btn" id="sb-tl" onclick="switchTab('tl')">📅 Timeline</button>
    <button class="sb-btn" id="sb-gantt" onclick="switchTab('gantt')">📉 Gantt</button>
    <button class="sb-btn" id="sb-burn" onclick="switchTab('burn')">🔥 Burndown</button>

    <div class="sb-sec">Projekte</div>
    <div id="projList"></div>
    <button class="add-proj-btn" onclick="addProject()">+ Neues Projekt</button>

    <div class="sb-spacer"></div>
    <div class="sb-sec">Export</div>
    <button class="sb-btn" onclick="doExportJSON()">⬇ JSON</button>
    <button class="sb-btn" onclick="doExportCSV()">⬇ CSV</button>
    <div style="font-size:10px;color:var(--muted);padding:6px 6px 0;line-height:1.7;">
      N = Meilenstein &nbsp; 1-4 = View<br>P = Projekt
    </div>
  </div>

  <!-- MAIN -->
  <div class="main">

    <!-- TOPBAR -->
    <div class="topbar">
      <div class="topbar-title" id="topTitle">Projekt</div>
      <div class="topbar-info">
        <span id="topRange"></span>
        <span id="topDays"></span>
        <span id="topProg"></span>
      </div>
      <div class="health-pill">
        <span class="h-dot" id="hDot"></span>
        <span id="hLbl">–</span>
      </div>
      <div class="view-tabs">
        <button class="vtab active" id="vt-dash" onclick="switchTab('dash')">Dashboard</button>
        <button class="vtab" id="vt-tl" onclick="switchTab('tl')">Timeline</button>
        <button class="vtab" id="vt-gantt" onclick="switchTab('gantt')">Gantt</button>
        <button class="vtab" id="vt-burn" onclick="switchTab('burn')">Burndown</button>
      </div>
    </div>

    <!-- CONTENT -->
    <div class="content">

      <!-- DASHBOARD -->
      <div id="vDash">
        <div class="card proj-meta">
          <input type="text" id="projTitleInp" placeholder="Projektname..." onblur="onTitleBlur()" />
          <span class="meta-lbl">Start</span>
          <input type="date" class="meta-date" id="startDateInp" onchange="onDateCh()" />
          <span class="meta-lbl">Ziel</span>
          <input type="date" class="meta-date" id="endDateInp" onchange="onDateCh()" />
          <div class="next-ms-box" id="nextMsBox"></div>
        </div>
        <div class="stat-row">
          <div class="card stat-card">
            <div class="stat-lbl">Tage übrig</div>
            <div class="stat-val" id="sDays" style="color:var(--accent)">0</div>
            <div class="stat-sub" id="sDaysSub"></div>
          </div>
          <div class="card stat-card">
            <div class="stat-lbl">Tasks</div>
            <div class="stat-val" id="sPct">0%</div>
            <div class="stat-sub" id="sTaskSub"></div>
            <div class="mini-bar"><div class="mini-fill" id="sTaskBar" style="width:0%"></div></div>
          </div>
          <div class="card stat-card">
            <div class="stat-lbl">Meilensteine</div>
            <div class="stat-val" id="sMs">0/0</div>
            <div class="stat-sub" id="sMsSub"></div>
            <div class="mini-bar"><div class="mini-fill" id="sMsBar" style="width:0%;background:var(--success)"></div></div>
          </div>
          <div class="card stat-card">
            <div class="stat-lbl">Velocity</div>
            <div class="stat-val" id="sVel" style="color:var(--success)">0</div>
            <div class="stat-sub">Tasks / Woche</div>
          </div>
          <div class="card stat-card">
            <div class="stat-lbl">Überfällig</div>
            <div class="stat-val" id="sOver" style="color:var(--danger)">0</div>
            <div class="stat-sub">Meilensteine</div>
          </div>
          <div class="card stat-card">
            <div class="stat-lbl">Blockiert</div>
            <div class="stat-val" id="sBlocked" style="color:var(--warning)">0</div>
            <div class="stat-sub">durch Abhängigkeit</div>
          </div>
        </div>
        <div class="card crit-card" id="critCard">
          <div class="crit-title">⚠ Kritischer Pfad</div>
          <div id="critContent"></div>
        </div>
        <div class="ms-editor" id="msEditorDash">
          <div class="ms-hdr">
            <h3>Meilensteine &amp; Aufgaben</h3>
            <button class="add-ms-btn" onclick="addMs()">+ Meilenstein</button>
          </div>
          <div class="ms-list" id="msListDash"></div>
        </div>
      </div>

      <!-- TIMELINE -->
      <div id="vTimeline">
        <div class="card tl-card">
          <div class="tl-hdr">
            <span class="tl-hdr-title">Projektzeitachse</span>
            <span style="font-size:10px;color:var(--muted);">🔴 Heute &nbsp;·&nbsp; Punkte = Meilensteine &nbsp;·&nbsp; Pfeil = Abhängigkeit</span>
          </div>
          <div style="padding:8px 4px;border-radius:10px;">
            <div class="tl-container" id="tlContainer">
              <div class="tl-track" id="tlTrack">
                <div class="tl-prog" id="tlProg"></div>
                <div class="tl-now" id="tlNow"></div>
              </div>
            </div>
          </div>
        </div>
        <div class="ms-editor" style="flex:1;min-height:0;">
          <div class="ms-hdr">
            <h3>Meilensteine &amp; Aufgaben</h3>
            <button class="add-ms-btn" onclick="addMs()">+ Meilenstein</button>
          </div>
          <div class="ms-list" id="msListTL"></div>
        </div>
      </div>

      <!-- GANTT -->
      <div id="vGantt">
        <div class="gantt-wrap">
          <div class="gantt-hdr">
            <div class="gantt-lbl">Meilenstein</div>
            <div class="gantt-chart-hdr" id="ganttHdr"></div>
          </div>
          <div class="gantt-body" id="ganttBody"></div>
        </div>
      </div>

      <!-- BURNDOWN -->
      <div id="vBurn">
        <div class="vel-row" id="velCards"></div>
        <div class="card bn-card">
          <div class="bn-title">Burndown Chart</div>
          <svg id="bnSvg" viewBox="0 0 800 260" style="width:100%;" xmlns="http://www.w3.org/2000/svg"></svg>
        </div>
        <div class="card bn-card">
          <div class="bn-title">Risiko Heatmap</div>
          <div class="heat-grid" id="heatGrid"></div>
        </div>
      </div>

    </div><!-- /content -->
  </div><!-- /main -->
</div><!-- /app -->

<script>
// ============================================================
// STATE
// ============================================================
var SKEY = 'milestone_ultra_v2';
var projects = [];
var aIdx = 0;   // active project index
var curTab = 'dash';

// ============================================================
// HELPERS
// ============================================================
function spd(s) {
  if (!s) return null;
  var d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}
function dd(a, b) {
  return Math.ceil((new Date(b) - new Date(a)) / 86400000);
}
function iso(d) { return d.toISOString().slice(0, 10); }
function uid() { return '_' + Math.random().toString(36).slice(2) + Date.now().toString(36); }

function msStat(ms) {
  var d = spd(ms.date), now = new Date();
  if (ms.done) return { l: 'Erledigt', c: 'bs' };
  if (!d) return { l: 'Offen', c: 'bn' };
  if (d < now) return { l: 'Überfällig', c: 'bd' };
  return { l: 'Offen', c: 'bw' };
}
function blocked(ms, all) {
  if (!ms.blockedBy) return false;
  var dep = null;
  for (var i = 0; i < all.length; i++) { if (all[i].id === ms.blockedBy) { dep = all[i]; break; } }
  return dep && !dep.done;
}
function health(p) {
  var now = new Date(), ms = p.milestones || [], tasks = [];
  ms.forEach(function(m) { (m.tasks || []).forEach(function(t) { tasks.push(t); }); });
  var tot = tasks.length, done = tasks.filter(function(t) { return t.done; }).length;
  var over = ms.filter(function(m) { return !m.done && spd(m.date) && spd(m.date) < now; }).length;
  var hi = ms.filter(function(m) { return !m.done && m.risk === 'high'; }).length;
  var s = 100 - over * 15 - hi * 8;
  if (tot > 0) s = Math.round(s * (0.4 + 0.6 * done / tot));
  s = Math.max(0, Math.min(100, s));
  var col = s >= 75 ? 'var(--success)' : s >= 45 ? 'var(--warning)' : 'var(--danger)';
  return { s: s, col: col, lbl: (s >= 75 ? 'Gut' : s >= 45 ? 'Mittel' : 'Kritisch') + ' (' + s + ')' };
}
function velocity(p) {
  var now = new Date(), start = spd(p.start) || now;
  var weeks = Math.max(1, dd(start, now) / 7), tasks = [];
  (p.milestones || []).forEach(function(m) { (m.tasks || []).forEach(function(t) { tasks.push(t); }); });
  return Math.round(tasks.filter(function(t) { return t.done; }).length / weeks * 10) / 10;
}

// ============================================================
// DATA
// ============================================================
function defProject() {
  var now = new Date();
  return {
    id: uid(), title: 'Mein Projekt',
    start: iso(now), end: iso(new Date(now.getTime() + 90 * 86400000)),
    milestones: [
      { id: uid(), name: 'Kickoff', date: iso(now), done: true, risk: 'low', notes: '', blockedBy: '',
        tasks: [{ id: uid(), text: 'Agenda vorbereiten', done: true },
                { id: uid(), text: 'Teilnehmer einladen', done: false }] },
      { id: uid(), name: 'Konzept', date: iso(new Date(now.getTime() + 20 * 86400000)),
        done: false, risk: 'medium', notes: '', blockedBy: '', tasks: [] }
    ]
  };
}
function fixMs(ms) {
  if (!ms.tasks) ms.tasks = [];
  if (!ms.risk) ms.risk = 'low';
  if (!ms.notes) ms.notes = '';
  if (ms.blockedBy === undefined || ms.blockedBy === null) ms.blockedBy = '';
}
function loadData() {
  var raw = localStorage.getItem(SKEY);
  if (raw) {
    try {
      var p = JSON.parse(raw);
      if (p && p.projects) { projects = p.projects; aIdx = p.aIdx || 0; }
      else if (p && p.milestones) { projects = [p]; aIdx = 0; }
      else { projects = [defProject()]; }
    } catch(e) { projects = [defProject()]; }
  } else {
    var old = localStorage.getItem('milestone_master_v1');
    if (old) { try { var od = JSON.parse(old); projects = [Object.assign(defProject(), od)]; } catch(e) { projects = [defProject()]; } }
    else { projects = [defProject()]; }
  }
  if (!projects || !projects.length) projects = [defProject()];
  projects.forEach(function(p) { (p.milestones || []).forEach(fixMs); });
  if (aIdx >= projects.length) aIdx = 0;
}
function saveData() {
  localStorage.setItem(SKEY, JSON.stringify({ projects: projects, aIdx: aIdx }));
}
function getP() { return projects[aIdx] || projects[0]; }
function normDates(p) {
  var s = spd(p.start) || new Date(), e = spd(p.end) || new Date();
  if (s > e) { var tmp = s; s = e; e = tmp; }
  p.start = iso(s); p.end = iso(e);
}

// ============================================================
// PROJECT ACTIONS
// ============================================================
function addProject() {
  var p = defProject(); p.title = 'Projekt ' + (projects.length + 1);
  projects.push(p); aIdx = projects.length - 1;
  saveData(); loadUI(); updateAll();
}
function switchProject(i) { aIdx = i; saveData(); loadUI(); updateAll(); }
function deleteProject(i) {
  if (projects.length <= 1) { alert('Mindestens ein Projekt muss bleiben.'); return; }
  if (!confirm('Projekt löschen?')) return;
  projects.splice(i, 1); if (aIdx >= projects.length) aIdx = projects.length - 1;
  saveData(); loadUI(); updateAll();
}
function loadUI() {
  var p = getP();
  document.getElementById('projTitleInp').value = p.title || '';
  document.getElementById('startDateInp').value = p.start || '';
  document.getElementById('endDateInp').value = p.end || '';
}
function onTitleBlur() {
  var p = getP(); p.title = document.getElementById('projTitleInp').value.trim() || 'Projekt';
  saveData(); renderProjList(); updateTopBar();
}
function onDateCh() {
  var p = getP();
  p.start = document.getElementById('startDateInp').value;
  p.end = document.getElementById('endDateInp').value;
  normDates(p);
  document.getElementById('startDateInp').value = p.start;
  document.getElementById('endDateInp').value = p.end;
  saveData(); updateAll();
}

// ============================================================
// MILESTONE ACTIONS
// ============================================================
function addMs() {
  var p = getP();
  p.milestones.push({ id: uid(), name: 'Neuer Meilenstein', date: p.end || iso(new Date()), done: false, risk: 'low', notes: '', blockedBy: '', tasks: [] });
  saveData(); updateAll();
  setTimeout(function() { document.querySelectorAll('.ms-list').forEach(function(el) { el.scrollTop = el.scrollHeight; }); }, 60);
}

// ============================================================
// TAB SWITCHING
// ============================================================
function switchTab(tab) {
  curTab = tab;
  var tabs = ['dash', 'tl', 'gantt', 'burn'];
  var ids = { dash: 'vDash', tl: 'vTimeline', gantt: 'vGantt', burn: 'vBurn' };
  tabs.forEach(function(t) {
    var v = document.getElementById(ids[t]);
    var vt = document.getElementById('vt-' + t);
    var sb = document.getElementById('sb-' + t);
    if (v) v.style.display = (t === tab) ? 'flex' : 'none';
    if (vt) { vt.className = 'vtab' + (t === tab ? ' active' : ''); }
    if (sb) { sb.className = 'sb-btn' + (t === tab ? ' active' : ''); }
  });
  renderTab();
}
function renderTab() {
  if (curTab === 'dash') renderMsList('msListDash');
  else if (curTab === 'tl') { renderTimeline(); renderMsList('msListTL'); }
  else if (curTab === 'gantt') renderGantt();
  else if (curTab === 'burn') renderBurndown();
}

// ============================================================
// STATS
// ============================================================
function calcStats() {
  var p = getP(), now = new Date(), ms = p.milestones || [], tasks = [];
  ms.forEach(function(m) { (m.tasks || []).forEach(function(t) { tasks.push(t); }); });
  var tot = tasks.length, done = tasks.filter(function(t) { return t.done; }).length;
  var pct = tot === 0 ? 0 : Math.round(done / tot * 100);
  var msTot = ms.length, msDone = ms.filter(function(m) { return m.done; }).length;
  var msPct = msTot === 0 ? 0 : Math.round(msDone / msTot * 100);
  var over = ms.filter(function(m) { return !m.done && spd(m.date) && spd(m.date) < now; }).length;
  var blk = ms.filter(function(m) { return blocked(m, ms); }).length;
  var end = spd(p.end) || now, dLeft = dd(now, end);
  var vel = velocity(p), h = health(p);

  el('sDays', function(e) { e.textContent = Math.max(0, dLeft); e.style.color = dLeft < 0 ? 'var(--danger)' : 'var(--accent)'; });
  el('sDaysSub', function(e) { e.textContent = dLeft < 0 ? Math.abs(dLeft) + 'd überzogen' : 'bis ' + (p.end || '?'); });
  el('sPct', function(e) { e.textContent = pct + '%'; });
  el('sTaskSub', function(e) { e.textContent = done + '/' + tot + ' Tasks'; });
  el('sTaskBar', function(e) { e.style.width = pct + '%'; });
  el('sMs', function(e) { e.textContent = msDone + '/' + msTot; });
  el('sMsSub', function(e) { e.textContent = msPct + '% erledigt'; });
  el('sMsBar', function(e) { e.style.width = msPct + '%'; });
  el('sVel', function(e) { e.textContent = vel; });
  el('sOver', function(e) { e.textContent = over; });
  el('sBlocked', function(e) { e.textContent = blk; });
  el('hDot', function(e) { e.style.background = h.col; });
  el('hLbl', function(e) { e.textContent = h.lbl; e.style.color = h.col; });

  // Critical path
  var cp = ms.filter(function(m) { return !m.done && (m.risk === 'high' || m.blockedBy); });
  el('critCard', function(e) { e.style.display = cp.length ? 'block' : 'none'; });
  el('critContent', function(e) {
    e.innerHTML = cp.map(function(m) {
      var dep = '';
      if (m.blockedBy) { for (var i = 0; i < ms.length; i++) { if (ms[i].id === m.blockedBy) { dep = ' (blockiert von: ' + ms[i].name + ')'; break; } } }
      return '<span style="margin-right:8px;">⛔ <strong>' + m.name + '</strong>' + dep + ' <span class="badge bd">' + m.risk + '</span></span>';
    }).join('<br>');
  });

  // Next milestone
  var upcoming = null, upcoming_d = null;
  ms.filter(function(m) { return !m.done; }).forEach(function(m) {
    var d = spd(m.date); if (!d) return;
    if (!upcoming || d < upcoming_d) { upcoming = m; upcoming_d = d; }
  });
  el('nextMsBox', function(e) {
    if (!upcoming) { e.innerHTML = '<span style="color:var(--success)">🎉 Alle erledigt!</span>'; return; }
    var days = dd(now, upcoming_d);
    var col = days <= 0 ? 'var(--danger)' : 'var(--text)';
    e.innerHTML = '<span style="color:var(--muted)">Nächster:</span> <strong>' + upcoming.name + '</strong> <span style="color:' + col + '">(' + (days < 0 ? Math.abs(days) + 'd überfällig' : days === 0 ? 'Heute' : 'in ' + days + 'd') + ')</span>';
  });
}
function updateTopBar() {
  var p = getP(), now = new Date(), end = spd(p.end) || now;
  var dLeft = dd(now, end), tasks = [];
  (p.milestones || []).forEach(function(m) { (m.tasks || []).forEach(function(t) { tasks.push(t); }); });
  var tot = tasks.length, done = tasks.filter(function(t) { return t.done; }).length;
  var pct = tot === 0 ? 0 : Math.round(done / tot * 100);
  el('topTitle', function(e) { e.textContent = p.title || 'Projekt'; });
  el('topRange', function(e) { e.innerHTML = '<strong>' + (p.start || '?') + '</strong> → <strong>' + (p.end || '?') + '</strong>'; });
  el('topDays', function(e) { e.innerHTML = '<strong style="color:' + (dLeft < 0 ? 'var(--danger)' : 'var(--accent)') + '">' + Math.max(0, dLeft) + 'd</strong> übrig'; });
  el('topProg', function(e) { e.innerHTML = '<strong>' + pct + '%</strong> Tasks'; });
}
function el(id, fn) { var e = document.getElementById(id); if (e) fn(e); }

// ============================================================
// PROJECT LIST
// ============================================================
function renderProjList() {
  var container = document.getElementById('projList'); if (!container) return;
  container.innerHTML = '';
  projects.forEach(function(p, i) {
    var btn = document.createElement('button');
    btn.className = 'proj-btn' + (i === aIdx ? ' active' : '');
    var open = (p.milestones || []).filter(function(m) { return !m.done; }).length;
    btn.innerHTML = '<span class="proj-name">' + (p.title || 'Projekt') + '</span>' +
      '<span class="proj-badge">' + open + '</span>' +
      '<span class="proj-del" title="Löschen">×</span>';
    (function(idx) {
      btn.onclick = function(ev) {
        if (ev.target.className === 'proj-del') { ev.stopPropagation(); deleteProject(idx); return; }
        switchProject(idx);
      };
    })(i);
    container.appendChild(btn);
  });
}

// ============================================================
// MILESTONE LIST
// ============================================================
function renderMsList(containerId) {
  var p = getP(), container = document.getElementById(containerId); if (!container) return;
  container.innerHTML = '';
  var sorted = (p.milestones || []).slice().sort(function(a, b) {
    return (spd(a.date) || new Date(0)) - (spd(b.date) || new Date(0));
  });
  sorted.forEach(function(ms) { appendMsRow(ms, p, container, containerId); });
}

function appendMsRow(ms, p, container, containerId) {
  var tasks = ms.tasks || [];
  var doneT = tasks.filter(function(t) { return t.done; }).length;
  var totT = tasks.length;
  var taskPct = totT === 0 ? 0 : Math.round(doneT / totT * 100);
  var isBlocked = blocked(ms, p.milestones || []);
  var stat = msStat(ms);

  var row = document.createElement('div');
  row.className = 'ms-row' + (ms.risk === 'high' && !ms.done ? ' hi-risk' : '');

  // Col 1: checkbox
  var chk = document.createElement('input'); chk.type = 'checkbox'; chk.className = 'ms-chk'; chk.checked = !!ms.done;
  chk.onchange = function() { ms.done = chk.checked; saveData(); updateAll(); };

  // Col 2: date
  var dWrap = document.createElement('div'); dWrap.className = 'ms-date-wrap';
  var dLbl = document.createElement('div'); dLbl.className = 'ms-date-lbl'; dLbl.textContent = 'Fällig am';
  var dInp = document.createElement('input'); dInp.type = 'date'; dInp.className = 'ms-date-inp'; dInp.value = ms.date || '';
  dInp.onchange = function() { var d = spd(dInp.value); if (d) { ms.date = iso(d); saveData(); renderTimeline(); calcStats(); } };
  dWrap.appendChild(dLbl); dWrap.appendChild(dInp);

  // Col 3: name + meta + progress
  var mDiv = document.createElement('div'); mDiv.className = 'ms-main';
  var nInp = document.createElement('input'); nInp.type = 'text'; nInp.className = 'ms-name-inp'; nInp.value = ms.name || '';
  nInp.onchange = function() { ms.name = nInp.value || 'Meilenstein'; saveData(); renderTimeline(); calcStats(); };
  var meta = document.createElement('div'); meta.className = 'ms-meta';
  meta.innerHTML = '<span class="badge ' + stat.c + '">' + stat.l + '</span>' + (isBlocked ? '<span style="color:var(--warning);font-size:10px;">⛔ Blockiert</span>' : '');
  var prog = document.createElement('div'); prog.className = 'ms-prog';
  var progFill = document.createElement('div'); progFill.className = 'ms-prog-fill'; progFill.style.width = taskPct + '%';
  prog.appendChild(progFill);
  mDiv.appendChild(nInp); mDiv.appendChild(meta); mDiv.appendChild(prog);

  // Col 4: risk + dep
  var rDiv = document.createElement('div');
  var rSel = document.createElement('select'); rSel.className = 'risk-sel risk-' + (ms.risk || 'low');
  [['low','🟢 Low'],['medium','🟡 Medium'],['high','🔴 High']].forEach(function(rv) {
    var o = document.createElement('option'); o.value = rv[0]; o.textContent = rv[1]; o.selected = ms.risk === rv[0]; rSel.appendChild(o);
  });
  rSel.onchange = function() { ms.risk = rSel.value; rSel.className = 'risk-sel risk-' + ms.risk; saveData(); calcStats(); };
  var dSel = document.createElement('select'); dSel.className = 'dep-sel';
  var noneOpt = document.createElement('option'); noneOpt.value = ''; noneOpt.textContent = 'Keine Abh.'; dSel.appendChild(noneOpt);
  (p.milestones || []).filter(function(m) { return m.id !== ms.id; }).forEach(function(m) {
    var o = document.createElement('option'); o.value = m.id; o.textContent = m.name; o.selected = ms.blockedBy === m.id; dSel.appendChild(o);
  });
  dSel.onchange = function() { ms.blockedBy = dSel.value; saveData(); calcStats(); renderMsList(containerId); };
  rDiv.appendChild(rSel); rDiv.appendChild(dSel);

  // Col 5: tasks
  var tCol = document.createElement('div'); tCol.className = 'task-col';
  var tSum = document.createElement('div'); tSum.className = 'task-sum';
  tSum.textContent = totT === 0 ? 'Keine Aufgaben' : doneT + '/' + totT + ' Aufgaben';
  tCol.appendChild(tSum);
  var tList = document.createElement('div');
  tasks.forEach(function(task) {
    var line = document.createElement('div'); line.className = 'task-line';
    var cb = document.createElement('input'); cb.type = 'checkbox'; cb.className = 'task-cb'; cb.checked = !!task.done;
    cb.onchange = function() {
      task.done = cb.checked; saveData(); calcStats();
      var d2 = tasks.filter(function(t) { return t.done; }).length;
      tSum.textContent = d2 + '/' + tasks.length + ' Aufgaben';
      progFill.style.width = (tasks.length === 0 ? 0 : Math.round(d2 / tasks.length * 100)) + '%';
    };
    var txt = document.createElement('input'); txt.type = 'text'; txt.className = 'task-txt'; txt.value = task.text;
    txt.onchange = function() { task.text = txt.value; saveData(); };
    var rm = document.createElement('button'); rm.className = 'task-rm'; rm.textContent = '×';
    rm.onclick = function() { var i = tasks.indexOf(task); if (i >= 0) tasks.splice(i, 1); saveData(); calcStats(); renderMsList(containerId); };
    line.appendChild(cb); line.appendChild(txt); line.appendChild(rm);
    tList.appendChild(line);
  });
  tCol.appendChild(tList);
  var addT = document.createElement('button'); addT.className = 'task-add'; addT.textContent = '+ Aufgabe';
  addT.onclick = function() { tasks.push({ id: uid(), text: 'Neue Aufgabe', done: false }); saveData(); calcStats(); renderMsList(containerId); };
  tCol.appendChild(addT);
  var noteBtn = document.createElement('button'); noteBtn.className = 'note-btn'; noteBtn.textContent = ms.notes ? '📝 Notiz' : '+ Notiz';
  noteBtn.onclick = function() { noteArea.classList.toggle('vis'); noteBtn.textContent = noteArea.classList.contains('vis') ? '📝 Notiz' : '+ Notiz'; };
  tCol.appendChild(noteBtn);

  // Col 6: delete
  var del = document.createElement('button'); del.className = 'ms-del'; del.textContent = '×';
  del.onclick = function() { if (confirm('Meilenstein löschen?')) { p.milestones = p.milestones.filter(function(m) { return m.id !== ms.id; }); saveData(); updateAll(); } };

  row.appendChild(chk); row.appendChild(dWrap); row.appendChild(mDiv);
  row.appendChild(rDiv); row.appendChild(tCol); row.appendChild(del);
  container.appendChild(row);

  // Note area (full-width extra row)
  var noteArea = document.createElement('textarea'); noteArea.className = 'note-area' + (ms.notes ? ' vis' : '');
  noteArea.placeholder = 'Notizen, Risiken, Details...'; noteArea.value = ms.notes || '';
  noteArea.onchange = function() { ms.notes = noteArea.value; saveData(); };
  var noteRow = document.createElement('div'); noteRow.style.cssText = 'grid-column:1/-1;padding:0 4px 6px;';
  noteRow.appendChild(noteArea);
  container.appendChild(noteRow);
}

// ============================================================
// TIMELINE
// ============================================================
function renderTimeline() {
  var p = getP(), track = document.getElementById('tlTrack'); if (!track) return;
  track.innerHTML = '<div class="tl-prog" id="tlProg"></div><div class="tl-now" id="tlNow"></div>';
  var s = spd(p.start), e = spd(p.end); if (!s || !e || e <= s) return;
  var sTs = s.getTime(), eTs = e.getTime(), tot = eTs - sTs, nowTs = Date.now();
  var nowPct = Math.max(0, Math.min(100, (nowTs - sTs) / tot * 100));
  document.getElementById('tlProg').style.width = nowPct + '%';
  document.getElementById('tlNow').style.left = nowPct + '%';

  var ms = (p.milestones || []).slice().sort(function(a, b) { return (spd(a.date) || new Date(0)) - (spd(b.date) || new Date(0)); });

  // Dependency lines
  ms.forEach(function(m) {
    if (!m.blockedBy) return;
    var dep = null; for (var i = 0; i < ms.length; i++) { if (ms[i].id === m.blockedBy) { dep = ms[i]; break; } }
    if (!dep) return;
    var fd = spd(dep.date), td = spd(m.date); if (!fd || !td) return;
    var fp = Math.max(0, Math.min(100, (fd.getTime() - sTs) / tot * 100));
    var tp = Math.max(0, Math.min(100, (td.getTime() - sTs) / tot * 100));
    var line = document.createElement('div'); line.className = 'dep-line';
    line.style.left = fp + '%'; line.style.width = Math.max(0, tp - fp) + '%';
    track.appendChild(line);
  });

  // Nodes
  ms.forEach(function(m, idx) {
    var md = spd(m.date); if (!md) return;
    var pct = Math.max(0, Math.min(100, (md.getTime() - sTs) / tot * 100));
    var isBlk = blocked(m, p.milestones || []);
    var st = msStat(m);
    var cls = m.done ? 'done' : (st.l === 'Überfällig' ? 'overdue' : 'future');
    if (isBlk && !m.done) cls = 'blocked';

    var node = document.createElement('div'); node.className = 'ms-node ' + cls; node.style.left = pct + '%';
    node.title = m.name + ' (' + (m.date || '') + ')';

    var wrap = document.createElement('div'); wrap.className = 'node-wrap ' + (idx % 2 !== 0 ? 'top' : 'bottom');
    var risk = { low: '🟢', medium: '🟡', high: '🔴' }[m.risk] || '';
    wrap.innerHTML = '<div class="node-lbl">' + m.name + '</div><div class="node-date">' + md.getDate() + '.' + (md.getMonth() + 1) + '. ' + risk + '</div>';
    node.appendChild(wrap);
    node.onclick = function() { m.done = !m.done; saveData(); updateAll(); };
    track.appendChild(node);
  });
}

// ============================================================
// GANTT
// ============================================================
function renderGantt() {
  var p = getP(), s = spd(p.start), e = spd(p.end);
  var hdr = document.getElementById('ganttHdr'), body = document.getElementById('ganttBody');
  if (!hdr || !body || !s || !e || e <= s) return;
  hdr.innerHTML = ''; body.innerHTML = '';
  var totDays = dd(s, e), now = new Date();
  var nowPct = Math.max(0, Math.min(100, dd(s, now) / totDays * 100));

  // Month labels
  var cur = new Date(s.getFullYear(), s.getMonth(), 1);
  while (cur <= e) {
    var pct = Math.max(0, Math.min(100, dd(s, cur) / totDays * 100));
    var ml = document.createElement('div'); ml.className = 'gantt-mlbl'; ml.style.left = pct + '%';
    ml.textContent = cur.toLocaleDateString('de-DE', { month: 'short', year: '2-digit' });
    hdr.appendChild(ml);
    var gl = document.createElement('div'); gl.className = 'gantt-grid'; gl.style.left = pct + '%'; hdr.appendChild(gl);
    cur.setMonth(cur.getMonth() + 1);
  }
  var todayHdr = document.createElement('div'); todayHdr.className = 'gantt-today'; todayHdr.style.left = nowPct + '%'; hdr.appendChild(todayHdr);

  var ms = (p.milestones || []).slice().sort(function(a, b) { return (spd(a.date) || new Date(0)) - (spd(b.date) || new Date(0)); });
  ms.forEach(function(m) {
    var md = spd(m.date); if (!md) return;
    var endPct = Math.max(2, Math.min(100, dd(s, md) / totDays * 100));
    var st = msStat(m);
    var row = document.createElement('div'); row.className = 'gantt-row';
    var lbl = document.createElement('div'); lbl.className = 'gantt-row-lbl';
    lbl.innerHTML = '<span class="badge ' + st.c + '" style="font-size:8px;padding:1px 4px;">' + (m.done ? '✓' : '○') + '</span> ' + m.name;
    var chart = document.createElement('div'); chart.className = 'gantt-row-chart';
    var tl = document.createElement('div'); tl.className = 'gantt-today'; tl.style.left = nowPct + '%';
    var bar = document.createElement('div');
    bar.className = 'gantt-bar ' + (m.done ? 'done' : (md < now ? 'overdue' : 'normal'));
    bar.style.cssText = 'left:0;width:' + endPct + '%';
    bar.textContent = m.name; bar.title = m.name + ' bis ' + (m.date || '');
    chart.appendChild(tl); chart.appendChild(bar);
    row.appendChild(lbl); row.appendChild(chart); body.appendChild(row);
  });
}

// ============================================================
// BURNDOWN
// ============================================================
function renderBurndown() {
  var p = getP(), now = new Date(), ms = p.milestones || [], tasks = [];
  ms.forEach(function(m) { (m.tasks || []).forEach(function(t) { tasks.push(t); }); });
  var tot = tasks.length, done = tasks.filter(function(t) { return t.done; }).length;
  var remaining = tot - done, vel = velocity(p);
  var s = spd(p.start) || now, e = spd(p.end) || now;
  var daysLeft = dd(now, e), daysTotal = Math.max(1, dd(s, e)), elapsed = Math.max(1, dd(s, now));
  var eta = vel > 0 ? Math.ceil(remaining / (vel / 7)) : null;

  var vc = document.getElementById('velCards');
  if (vc) vc.innerHTML =
    vCard(vel, 'Tasks/Woche', 'var(--accent)') + vCard(done, 'Erledigt', 'var(--success)') +
    vCard(remaining, 'Verbleibend', 'var(--warning)') + vCard(Math.max(0, daysLeft), 'Tage bis Deadline', 'var(--danger)') +
    vCard(eta !== null ? eta + 'd' : '∞', 'Gesch. Fertigstellung', 'var(--text)');

  // SVG
  var svg = document.getElementById('bnSvg'); if (!svg) return;
  var W = 800, H = 260, pl = 50, pr = 20, pt = 20, pb = 40, cW = W - pl - pr, cH = H - pt - pb;
  var elPct = Math.min(1, elapsed / daysTotal);
  var actualX = pl + cW * elPct;
  var actualY = pt + cH * (remaining / Math.max(1, tot));
  var out = "<line x1='" + pl + "' y1='" + pt + "' x2='" + pl + "' y2='" + (pt+cH) + "' stroke='var(--border)' stroke-width='1'/>";
  out += "<line x1='" + pl + "' y1='" + (pt+cH) + "' x2='" + (pl+cW) + "' y2='" + (pt+cH) + "' stroke='var(--border)' stroke-width='1'/>";
  out += "<text x='" + (pl-5) + "' y='" + (pt+8) + "' text-anchor='end' font-size='10' fill='var(--muted)'>" + tot + "</text>";
  out += "<text x='" + (pl-5) + "' y='" + (pt+cH) + "' text-anchor='end' font-size='10' fill='var(--muted)'>0</text>";
  out += "<text x='" + pl + "' y='" + (H-6) + "' font-size='10' fill='var(--muted)'>Start</text>";
  out += "<text x='" + (pl+cW-20) + "' y='" + (H-6) + "' font-size='10' fill='var(--muted)'>Ende</text>";
  out += "<line x1='" + pl + "' y1='" + pt + "' x2='" + (pl+cW) + "' y2='" + (pt+cH) + "' stroke='var(--success)' stroke-width='1.5' stroke-dasharray='6,4' opacity='0.5'/>";
  out += "<text x='" + (pl+cW+3) + "' y='" + (pt+cH) + "' font-size='9' fill='var(--success)'>Ideal</text>";
  out += "<line x1='" + pl + "' y1='" + pt + "' x2='" + actualX + "' y2='" + actualY + "' stroke='var(--accent)' stroke-width='2.5'/>";
  out += "<circle cx='" + actualX + "' cy='" + actualY + "' r='4' fill='var(--accent)'/>";
  out += "<line x1='" + actualX + "' y1='" + pt + "' x2='" + actualX + "' y2='" + (pt+cH) + "' stroke='var(--danger)' stroke-width='1' stroke-dasharray='4,3' opacity='0.7'/>";
  out += "<text x='" + (actualX+3) + "' y='" + (pt+14) + "' font-size='9' fill='var(--danger)'>Heute</text>";
  if (vel > 0) {
    var dToFin = remaining / (vel / 7);
    var finX = pl + cW * Math.min(1, elPct + dToFin / daysTotal);
    out += "<line x1='" + actualX + "' y1='" + actualY + "' x2='" + finX + "' y2='" + (pt+cH) + "' stroke='var(--warning)' stroke-width='1.5' stroke-dasharray='5,4' opacity='0.7'/>";
    out += "<text x='" + (finX+3) + "' y='" + (pt+cH-4) + "' font-size='9' fill='var(--warning)'>ETA</text>";
  }
  svg.innerHTML = out;

  // Heatmap
  var hg = document.getElementById('heatGrid');
  if (hg) {
    hg.innerHTML = '';
    (p.milestones || []).forEach(function(m) {
      var d = spd(m.date), days = d ? dd(now, d) : 0, st = msStat(m);
      var rCol = { low: 'var(--success)', medium: 'var(--warning)', high: 'var(--danger)' }[m.risk] || 'var(--muted)';
      var t = m.tasks || [], td2 = t.filter(function(x) { return x.done; }).length;
      var div = document.createElement('div'); div.className = 'heat-item'; div.style.borderColor = rCol;
      div.innerHTML = '<div style="font-size:12px;font-weight:700;">' + m.name + '</div>' +
        '<div style="font-size:10px;color:' + rCol + ';font-weight:600;margin-top:2px;">⬤ ' + m.risk + ' risk</div>' +
        '<span class="badge ' + st.c + '" style="margin-top:4px;display:inline-flex;">' + st.l + '</span>' +
        '<div style="font-size:10px;color:var(--muted);margin-top:4px;">' + (t.length > 0 ? td2 + '/' + t.length + ' Tasks' : 'Keine Tasks') + '</div>' +
        '<div style="font-size:10px;color:var(--muted);">' + (d ? (days < 0 ? Math.abs(days) + 'd überfällig' : 'in ' + days + 'd') : '–') + '</div>';
      hg.appendChild(div);
    });
  }
}
function vCard(v, lbl, col) {
  return '<div class="card vel-card"><div class="vel-val" style="color:' + col + '">' + v + '</div><div class="vel-lbl">' + lbl + '</div></div>';
}

// ============================================================
// EXPORT
// ============================================================
function doExportJSON() {
  var blob = new Blob([JSON.stringify({ projects: projects, aIdx: aIdx }, null, 2)], { type: 'application/json' });
  var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'milestones.json'; a.click();
}
function doExportCSV() {
  var p = getP(), rows = [['Meilenstein','Datum','Status','Risiko','Blockiert von','Tasks gesamt','Tasks erledigt','Notizen']];
  (p.milestones || []).forEach(function(m) {
    var dep = ''; if (m.blockedBy) { for (var i = 0; i < p.milestones.length; i++) { if (p.milestones[i].id === m.blockedBy) { dep = p.milestones[i].name; break; } } }
    var t = m.tasks || [], td = t.filter(function(x) { return x.done; }).length;
    rows.push(['"' + m.name + '"', m.date || '', msStat(m).l, m.risk, dep, t.length, td, '"' + (m.notes || '').replace(/"/g, '""') + '"']);
  });
  var csv = rows.map(function(r) { return r.join(','); }).join('\\n');
  var blob = new Blob([csv], { type: 'text/csv' });
  var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'milestones.csv'; a.click();
}

// ============================================================
// KEYBOARD
// ============================================================
document.addEventListener('keydown', function(ev) {
  var tag = document.activeElement.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
  if (ev.key === 'n' || ev.key === 'N') addMs();
  else if (ev.key === '1') switchTab('dash');
  else if (ev.key === '2') switchTab('tl');
  else if (ev.key === '3') switchTab('gantt');
  else if (ev.key === '4') switchTab('burn');
  else if (ev.key === 'p' || ev.key === 'P') addProject();
});

// ============================================================
// MAIN UPDATE
// ============================================================
function updateAll() { calcStats(); updateTopBar(); renderProjList(); renderTab(); }

// ============================================================
// INIT
// ============================================================
loadData();
loadUI();
switchTab('dash');
</script>
</body>
</html>"""
        return template.replace("__BODY_CLASS__", body_class)

    def _build_popup_html(self, body_class):
        template = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Milestone Ultra Popup</title>
<style>
html, body { height: 100%; margin: 0; font-family: 'Segoe UI', system-ui, sans-serif; overflow: hidden; }
body { background: var(--bg); color: var(--text); display: flex; flex-direction: column; }
.wrap { padding: 10px; overflow-y: auto; flex: 1; }
.card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px; padding: 9px 13px; margin-bottom: 8px; }
.lbl { font-size: 10px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); font-weight: 600; margin-bottom: 3px; }
.ttl { font-size: 14px; font-weight: 700; }
.sub { font-size: 11px; color: var(--muted); }
.big { font-size: 20px; font-weight: 700; }
.row { display: flex; gap: 10px; }
.col { flex: 1; }
.badge { display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 999px; font-size: 10px; font-weight: 600; }
.bs { background: var(--success-soft); color: var(--success); }
.bd { background: var(--danger-soft); color: var(--danger); }
.bw { background: var(--warning-soft); color: var(--warning); }
.bn { background: var(--chip); color: var(--muted); }
.hbar { height: 4px; border-radius: 2px; background: var(--chip); margin-top: 6px; }
.hfill { height: 100%; border-radius: 2px; transition: width .5s; }
.psel { width: 100%; margin-bottom: 8px; padding: 5px 8px; border-radius: 6px; background: var(--input-bg); border: 1px solid var(--border); color: var(--text); font-size: 12px; font-family: inherit; }
ul.tl { margin: 4px 0 0 12px; padding: 0; }
ul.tl li { font-size: 11px; color: var(--muted); margin-bottom: 2px; }
::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
</style>
""" + THEME_OVERRIDE_CSS + THEME_SCRIPT + """
</head>
<body class="__BODY_CLASS__">
<div class="wrap">
  <select class="psel" id="ppSel" onchange="switchP(this.value)"></select>
  <div class="card">
    <div class="lbl">Projekt</div>
    <div class="ttl" id="ppTitle">–</div>
    <div class="sub" id="ppRange"></div>
    <div class="hbar"><div class="hfill" id="ppHF"></div></div>
    <div class="sub" id="ppHL" style="margin-top:3px;"></div>
  </div>
  <div class="card">
    <div class="row">
      <div class="col"><div class="lbl">Tage übrig</div><div class="big" id="ppDays" style="color:var(--accent)">0</div></div>
      <div class="col"><div class="lbl">Tasks</div><div class="sub"><span id="ppTD">0</span>/<span id="ppTT">0</span> (<span id="ppPct">0</span>%)</div></div>
      <div class="col"><div class="lbl">Meilensteine</div><div class="sub"><span id="ppMD">0</span>/<span id="ppMT">0</span></div></div>
    </div>
  </div>
  <div class="card">
    <div class="lbl">Nächster Meilenstein</div>
    <div class="ttl" id="ppNName">–</div>
    <div class="sub" id="ppNDate"></div>
    <div class="sub" id="ppNDays" style="margin-top:2px;"></div>
    <div id="ppNSt" style="margin-top:4px;"></div>
    <div class="sub" id="ppNT" style="margin-top:4px;"></div>
    <ul class="tl" id="ppNL"></ul>
  </div>
</div>
<script>
var SKEY = 'milestone_ultra_v2';
var projects = [], aIdx = 0;
function spd(s) { if (!s) return null; var d = new Date(s); return isNaN(d.getTime()) ? null : d; }
function dd(a, b) { return Math.ceil((new Date(b) - new Date(a)) / 86400000); }
function msStat(ms) {
  var d = spd(ms.date), now = new Date();
  if (ms.done) return { l: 'Erledigt', c: 'bs' };
  if (!d) return { l: 'Offen', c: 'bn' };
  if (d < now) return { l: 'Überfällig', c: 'bd' };
  return { l: 'Offen', c: 'bw' };
}
function hlth(p) {
  var now = new Date(), ms = p.milestones || [], tasks = [];
  ms.forEach(function(m) { (m.tasks || []).forEach(function(t) { tasks.push(t); }); });
  var tot = tasks.length, done = tasks.filter(function(t) { return t.done; }).length;
  var over = ms.filter(function(m) { return !m.done && spd(m.date) && spd(m.date) < now; }).length;
  var hi = ms.filter(function(m) { return !m.done && m.risk === 'high'; }).length;
  var s = Math.max(0, Math.min(100, 100 - over * 15 - hi * 8));
  if (tot > 0) s = Math.round(s * (0.4 + 0.6 * done / tot));
  var col = s >= 75 ? 'var(--success)' : s >= 45 ? 'var(--warning)' : 'var(--danger)';
  return { s: s, col: col, lbl: (s >= 75 ? 'Gut' : s >= 45 ? 'Mittel' : 'Kritisch') + ' (' + s + ')' };
}
function loadData() {
  var raw = localStorage.getItem(SKEY);
  if (raw) { try { var p = JSON.parse(raw); if (p && p.projects) { projects = p.projects; aIdx = p.aIdx || 0; } else if (p && p.milestones) { projects = [p]; } } catch(e) {} }
  if (!projects || !projects.length) projects = [{ id: '_', title: 'Projekt', start: '', end: '', milestones: [] }];
  projects.forEach(function(p) { (p.milestones || []).forEach(function(m) { if (!m.tasks) m.tasks = []; if (!m.risk) m.risk = 'low'; }); });
}
function switchP(id) { for (var i = 0; i < projects.length; i++) { if (projects[i].id === id) { aIdx = i; break; } } refresh(); }
function refresh() {
  var p = projects[aIdx] || projects[0]; if (!p) return;
  var now = new Date(), end = spd(p.end) || now;
  var ms = p.milestones || [], tasks = [];
  ms.forEach(function(m) { (m.tasks || []).forEach(function(t) { tasks.push(t); }); });
  var tot = tasks.length, done = tasks.filter(function(t) { return t.done; }).length;
  var pct = tot === 0 ? 0 : Math.round(done / tot * 100);
  var mt = ms.length, md2 = ms.filter(function(m) { return m.done; }).length;
  var dl = dd(now, end), h = hlth(p);
  var sel = document.getElementById('ppSel');
  if (sel) sel.innerHTML = projects.map(function(pp) { return '<option value="' + pp.id + '"' + (pp.id === p.id ? ' selected' : '') + '>' + (pp.title || 'Projekt') + '</option>'; }).join('');
  function s(id, fn) { var e = document.getElementById(id); if (e) fn(e); }
  s('ppTitle', function(e) { e.textContent = p.title || 'Projekt'; });
  s('ppRange', function(e) { e.textContent = (p.start || '?') + ' – ' + (p.end || '?'); });
  s('ppHF', function(e) { e.style.cssText = 'width:' + h.s + '%;background:' + h.col; });
  s('ppHL', function(e) { e.textContent = h.lbl; e.style.color = h.col; });
  s('ppDays', function(e) { e.textContent = Math.max(0, dl); e.style.color = dl < 0 ? 'var(--danger)' : 'var(--accent)'; });
  s('ppTD', function(e) { e.textContent = done; });
  s('ppTT', function(e) { e.textContent = tot; });
  s('ppPct', function(e) { e.textContent = pct; });
  s('ppMD', function(e) { e.textContent = md2; });
  s('ppMT', function(e) { e.textContent = mt; });
  var up = null, up_d = null;
  ms.filter(function(m) { return !m.done; }).forEach(function(m) { var d = spd(m.date); if (!d) return; if (!up || d < up_d) { up = m; up_d = d; } });
  if (!up) {
    s('ppNName', function(e) { e.textContent = '🎉 Alle erledigt!'; });
    ['ppNDate','ppNDays','ppNT'].forEach(function(id) { s(id, function(e) { e.textContent = ''; }); });
    s('ppNSt', function(e) { e.innerHTML = ''; }); s('ppNL', function(e) { e.innerHTML = ''; });
    return;
  }
  s('ppNName', function(e) { e.textContent = up.name; });
  s('ppNDate', function(e) { e.textContent = up.date; });
  var days = dd(now, up_d);
  s('ppNDays', function(e) { e.textContent = days < 0 ? Math.abs(days) + 'd überfällig' : days === 0 ? 'Heute fällig' : 'in ' + days + 'd'; e.style.color = days <= 0 ? 'var(--danger)' : 'var(--muted)'; });
  var st = msStat(up);
  s('ppNSt', function(e) { e.innerHTML = '<span class="badge ' + st.c + '">' + st.l + '</span>'; });
  var ut = up.tasks || [], utd = ut.filter(function(t) { return t.done; }).length;
  s('ppNT', function(e) { e.textContent = ut.length === 0 ? 'Keine Tasks' : utd + '/' + ut.length + ' Tasks'; });
  s('ppNL', function(e) { e.innerHTML = ''; ut.filter(function(t) { return !t.done; }).slice(0, 3).forEach(function(t) { var li = document.createElement('li'); li.textContent = t.text; e.appendChild(li); }); });
}
loadData(); refresh();
</script>
</body>
</html>"""
        return template.replace("__BODY_CLASS__", body_class)

    def _on_view_ready(self, ok):
        self._view_ready = bool(ok)
        if ok:
            self._apply_theme(self._current_theme)

    def _apply_theme(self, theme):
        if not self._view_ready:
            return
        t = theme if theme in SUPPORTED_THEMES else THEME_DARK
        script = f'window.applyTheme && window.applyTheme("{t}")'
        try:
            self.browser.page().runJavaScript(script)
        except Exception:
            pass

    def _on_host_theme_changed(self, theme):
        t = theme if theme in SUPPORTED_THEMES else THEME_DARK
        self._current_theme = t
        self._apply_theme(t)

    def _cleanup_watcher(self):
        if self._theme_watcher:
            self._theme_watcher.cleanup()
            self._theme_watcher.deleteLater()
            self._theme_watcher = None

    def closeEvent(self, event):
        self._cleanup_watcher()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PluginWidget(theme="dark", mode="Window")
    window.show()
    sys.exit(app.exec_())
