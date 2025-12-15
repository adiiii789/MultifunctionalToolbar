# scripts/pro_canvas_html_v1_singlefile.py
import os
import sys
from PyQt5.QtCore import (
    QObject, pyqtSlot, pyqtSignal, QUrl, QEvent
)
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QApplication
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QPalette

# --- 1. Python-Backend-Logik (Unsere API für JS) ---

# Speicherort geändert, damit wir nicht die Text-Notizen überschreiben
NOTES_DIR = os.path.expanduser('~/.simple_canvas_plugin_v1')
os.makedirs(NOTES_DIR, exist_ok=True)

THEME_LIGHT = "light"
THEME_DARK = "dark"
SUPPORTED_THEMES = {THEME_LIGHT, THEME_DARK}


def _detect_host_theme(default=THEME_LIGHT):
    app = QApplication.instance()
    if app is not None:
        prop = app.property("toolbar_theme")
        if isinstance(prop, str) and prop.lower() in SUPPORTED_THEMES:
            return prop.lower()
        try:
            palette = app.palette()
            if palette and palette.color(QPalette.Window).value() < 128:
                return THEME_DARK
        except Exception:
            pass
    return default


class CanvasAPI(QObject):
    """
    API zum Speichern und Laden von Zeichnungen (als Base64 Strings).
    """

    notesChanged = pyqtSignal()
    themeChanged = pyqtSignal(str)

    def __init__(self, initial_theme=THEME_LIGHT):
        super().__init__()
        self._theme = initial_theme if initial_theme in SUPPORTED_THEMES else THEME_LIGHT

    @pyqtSlot(result='QVariantList')
    def list_notes(self):
        """Liefert eine Liste aller Zeichnungs-Titel."""
        try:
            # Wir nutzen weiterhin .txt, speichern darin aber den Base64 Image String
            return sorted(
                [f[:-4] for f in os.listdir(NOTES_DIR) if f.endswith('.txt')],
                key=lambda s: s.lower()
            )
        except Exception as e:
            print(f"Fehler beim Auflisten der Zeichnungen: {e}")
            return []

    @pyqtSlot(str, result=str)
    def load_note(self, title):
        """Lädt den Base64-String einer Zeichnung."""
        path = os.path.join(NOTES_DIR, title + '.txt')
        if not title or not os.path.exists(path):
            return ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Fehler beim Laden der Zeichnung {title}: {e}")
            return ""

    @pyqtSlot(str, str)
    def save_note(self, title, content):
        """Speichert den Base64-String der Zeichnung."""
        if not title: return
        path = os.path.join(NOTES_DIR, title + '.txt')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.notesChanged.emit()
        except Exception as e:
            print(f"Fehler beim Speichern der Zeichnung {title}: {e}")

    @pyqtSlot(str)
    def delete_note(self, title):
        """Löscht eine Zeichnung."""
        if not title: return
        path = os.path.join(NOTES_DIR, title + '.txt')
        if os.path.exists(path):
            try:
                os.remove(path)
                self.notesChanged.emit()
            except Exception as e:
                print(f"Fehler beim Löschen der Zeichnung {title}: {e}")

    def _set_theme_internal(self, theme: str):
        theme_lower = (theme or "").lower()
        if theme_lower not in SUPPORTED_THEMES or theme_lower == self._theme:
            return False
        self._theme = theme_lower
        self.themeChanged.emit(self._theme)
        return True

    @pyqtSlot(result=str)
    def get_theme(self):
        return self._theme

    @pyqtSlot(str)
    def set_theme(self, theme):
        self._set_theme_internal(theme)

    def current_theme(self):
        return self._theme


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


# --- 2. Frontend-Code (CSS & JS für Canvas) ---

STYLE_CSS = r"""
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f7fa;
    color: #222;
    margin: 0;
    overflow: hidden;
    font-size: 14px;
    transition: background 0.25s ease, color 0.25s ease;
}
.view-container {
    height: 100vh;
    display: none; /* Standard aus */
}
body.window-mode #window-view { display: flex; }
body.popup-mode #popup-view { display: flex; }

/* --- Sidebar (Liste) --- */
#sidebar {
    background: #eaeaea;
    width: 250px;
    padding: 1em;
    box-sizing: border-box;
    overflow-y: auto;
    border-right: 1px solid #d7d7d7;
    display: flex;
    flex-direction: column;
}
#main {
    flex: 1;
    padding: 1em;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    background: #ffffff;
    overflow: hidden;
}

/* --- Canvas Container --- */
.canvas-wrapper {
    flex: 1;
    border: 1px solid #ccc;
    background: #fff; /* Leinwand ist immer weiß */
    position: relative;
    margin-bottom: 1em;
    overflow: hidden;
    cursor: crosshair;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
canvas {
    display: block;
    touch-action: none;
}

/* --- Toolbar --- */
.toolbar {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 10px;
    padding: 5px;
    background: #f0f0f0;
    border-radius: 5px;
}
.toolbar label { font-size: 0.9em; margin-right: 5px; }
input[type="color"] { border: none; width: 30px; height: 30px; padding: 0; cursor: pointer; }
input[type="range"] { cursor: pointer; }

/* --- Controls --- */
input[type="text"] {
    width: 100%;
    margin: .5em 0 1em 0;
    padding: 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    box-sizing: border-box;
}
button {
    padding: .6em 1em;
    border: none;
    border-radius: 4px;
    background: #007aff;
    color: white;
    font-size: 0.9em;
    cursor: pointer;
    transition: background 0.2s;
}
button:hover { background: #0056b3; }
button.danger { background: #dc3545; }
button.danger:hover { background: #a71d2a; }
button.secondary { background: #6c757d; }
button.secondary:hover { background: #5a6268; }

#notelist { padding: 0; list-style: none; margin-bottom: auto; }
#notelist li {
    padding: .5em .3em;
    cursor: pointer;
    border-radius: 3px;
    word-break: break-all;
    margin-bottom: 2px;
}
#notelist li:hover { background: #dcdcdc; }
#notelist li.selected { background: #007aff; color: white; font-weight: bold; }

#status-bar, #popup-status-bar {
    margin-top: 5px;
    height: 1.2em;
    font-weight: bold;
    font-size: 0.9em;
}

/* --- Popup Mode Adjustments --- */
#popup-view {
    flex-direction: column;
    padding: 1em;
    box-sizing: border-box;
}
#popup-view .canvas-wrapper { height: 300px; flex: none; }

/* --- Dark Theme --- */
body.theme-dark { background: #2E2E2E; color: #f5f5f5; }
body.theme-dark #sidebar { background: #1f232b; border-right-color: #373b44; color: #f5f5f5; }
body.theme-dark #main { background: #2b2f38; }
body.theme-dark .toolbar { background: #3A3A3A; color: #f5f5f5; }
body.theme-dark input[type="text"] { background: #3A3A3A; border-color: #4d4d4d; color: #f5f5f5; }
body.theme-dark #notelist li:hover { background: #333948; }
body.theme-dark #notelist li.selected { background: #3A4A6A; }
/* Canvas bleibt weiß, damit man Farben sieht, aber Rahmen passt sich an */
body.theme-dark .canvas-wrapper { border-color: #444; }
"""

MAIN_JS = r"""
let currentTheme = 'light';
let canvas, ctx;
let isDrawing = false;
let lastX = 0;
let lastY = 0;

// Canvas Settings
let brushColor = "#000000";
let brushSize = 3;

window.addEventListener('load', () => {
    if (typeof qt === 'undefined' || typeof qt.webChannelTransport === 'undefined') {
        document.body.innerHTML = "<h3>Fehler: QWebChannel nicht gefunden.</h3>";
        return;
    }
    new QWebChannel(qt.webChannelTransport, (channel) => {
        window.backend = channel.objects.backend;
        initApp();
        initThemeSync();
    });
});

function initApp() {
    const params = new URLSearchParams(window.location.search);
    const mode = params.get('mode') || 'Window';
    document.body.classList.add(mode.toLowerCase() + '-mode');

    if (mode === 'Window') initWindowView();
    else initPopupView(); // Minimal implementiert für dieses Beispiel

    // Global Listener für Änderungen durch andere Fenster
    if (window.backend.notesChanged) {
        window.backend.notesChanged.connect(refreshNoteList);
    }
}

async function initThemeSync() {
    applyTheme('light');
    if (window.backend.themeChanged) window.backend.themeChanged.connect(applyTheme);
    try {
        const theme = await window.backend.get_theme();
        applyTheme(theme || 'light');
    } catch(e) {}
}

// --- Canvas Logic ---

function setupCanvas(canvasId) {
    canvas = document.getElementById(canvasId);
    ctx = canvas.getContext('2d');

    // Größe der Leinwand an den Container anpassen
    const wrapper = canvas.parentElement;
    canvas.width = wrapper.clientWidth;
    canvas.height = wrapper.clientHeight;

    // Standardhintergrund Weiß
    clearCanvas();

    // Event Listeners
    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseout', stopDrawing);

    // Touch Support (optional)
    canvas.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent("mousedown", {
            clientX: touch.clientX, clientY: touch.clientY
        });
        canvas.dispatchEvent(mouseEvent);
    }, false);

    // Tools initialisieren
    document.getElementById('color-picker').addEventListener('change', (e) => brushColor = e.target.value);
    document.getElementById('size-slider').addEventListener('input', (e) => brushSize = e.target.value);
    document.getElementById('btn-clear').addEventListener('click', clearCanvas);
    document.getElementById('btn-eraser').addEventListener('click', () => brushColor = "#FFFFFF");
    document.getElementById('btn-pen').addEventListener('click', () => {
        brushColor = document.getElementById('color-picker').value;
    });
}

function startDrawing(e) {
    isDrawing = true;
    [lastX, lastY] = getPos(e);
}

function draw(e) {
    if (!isDrawing) return;
    const [x, y] = getPos(e);

    ctx.beginPath();
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = brushColor;
    ctx.lineWidth = brushSize;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    [lastX, lastY] = [x, y];
}

function stopDrawing() {
    isDrawing = false;
}

function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    return [
        e.clientX - rect.left,
        e.clientY - rect.top
    ];
}

function clearCanvas() {
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

// --- Window Mode Logic ---

const el = {
    noteList: document.getElementById('notelist'),
    newTitle: document.getElementById('new-title'),
    addNoteBtn: document.getElementById('add-note-btn'),
    currentTitle: document.getElementById('current-title'),
    saveBtn: document.getElementById('save-btn'),
    deleteBtn: document.getElementById('delete-btn'),
    statusBar: document.getElementById('status-bar'),
};
let currentSelectedTitle = "";

function initWindowView() {
    setupCanvas('main-canvas');

    el.addNoteBtn.addEventListener('click', addNewDrawing);
    el.saveBtn.addEventListener('click', saveCurrentDrawing);
    el.deleteBtn.addEventListener('click', deleteCurrentDrawing);

    refreshNoteList();
}

async function refreshNoteList() {
    const notes = await window.backend.list_notes();
    el.noteList.innerHTML = "";
    notes.forEach(title => {
        const li = document.createElement('li');
        li.innerText = title;
        li.dataset.title = title;
        li.addEventListener('click', () => openDrawing(title));
        if (title === currentSelectedTitle) li.classList.add('selected');
        el.noteList.appendChild(li);
    });
}

async function openDrawing(title) {
    const content = await window.backend.load_note(title);
    currentSelectedTitle = title;
    el.currentTitle.value = title;

    // Update Selection UI
    document.querySelectorAll('#notelist li').forEach(li => {
        li.classList.toggle('selected', li.dataset.title === title);
    });

    // Bild laden
    if (content) {
        const img = new Image();
        img.onload = function() {
            clearCanvas(); // Erst weiß machen
            ctx.drawImage(img, 0, 0); // Dann Bild drauf malen
        };
        img.src = content;
    } else {
        clearCanvas(); // Leeres Blatt
    }
}

async function saveCurrentDrawing() {
    const title = el.currentTitle.value;
    if (!title) {
        showStatus("Bitte erstelle eine 'Neue Zeichnung'.", "error");
        return;
    }
    // Canvas als Base64 Bild speichern (PNG)
    const dataURL = canvas.toDataURL("image/png");

    await window.backend.save_note(title, dataURL);
    showStatus(`Zeichnung '${title}' gespeichert!`, "success");
}

async function addNewDrawing() {
    const newTitle = el.newTitle.value.trim();
    if (!newTitle) {
        showStatus("Bitte Titel eingeben.", "error");
        return;
    }
    // Leeres weißes Bild speichern
    clearCanvas();
    const dataURL = canvas.toDataURL("image/png");

    await window.backend.save_note(newTitle, dataURL);

    currentSelectedTitle = newTitle;
    await refreshNoteList();
    el.currentTitle.value = newTitle;
    el.newTitle.value = "";
}

async function deleteCurrentDrawing() {
    const title = el.currentTitle.value;
    if (!title) return;

    await window.backend.delete_note(title);

    el.currentTitle.value = "";
    clearCanvas();
    currentSelectedTitle = "";
    showStatus(`Gelöscht: ${title}`, "success");
}

// --- Popup Mode Logic (Vereinfacht) ---
function initPopupView() {
    // Hier könnte man eine separate Logik implementieren
    // Für dieses Beispiel nutzen wir nur die Info, dass es existiert.
    document.body.innerHTML = "<h3 style='padding:20px'>Popup-Modus für Canvas ist in dieser Version nur Platzhalter. Bitte Window-Modus nutzen.</h3>";
}

// --- Helpers ---

function showStatus(msg, type) {
    if (!el.statusBar) return;
    el.statusBar.innerText = msg;
    el.statusBar.style.color = (type === "error") ? "red" : "green";
    setTimeout(() => { el.statusBar.innerText = ""; }, 3000);
}

function applyTheme(theme) {
    currentTheme = (theme === 'dark') ? 'dark' : 'light';
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(`theme-${currentTheme}`);
}
"""

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Canvas Notes</title>
    <style>
        {style}
    </style>
</head>
<body class="theme-light">

    <div id="window-view" class="view-container">
        <div id="sidebar">
            <h3>Galerie</h3>
            <ul id="notelist"></ul>
            <div style="margin-top:auto">
                <input id="new-title" type="text" placeholder="Titel für Neues Bild..." />
                <button id="add-note-btn" style="width:100%">+ Neues Bild</button>
            </div>
        </div>

        <div id="main">
            <input id="current-title" type="text" placeholder="Bildtitel" readonly />

            <div class="toolbar">
                <button id="btn-pen">✏️ Stift</button>
                <button id="btn-eraser" class="secondary">🧽 Radierer</button>
                <div style="width:10px"></div>
                <label>Farbe:</label>
                <input type="color" id="color-picker" value="#000000">
                <div style="width:10px"></div>
                <label>Größe:</label>
                <input type="range" id="size-slider" min="1" max="20" value="3">
                <div style="flex:1"></div>
                <button id="btn-clear" class="danger">🗑️ Leeren</button>
            </div>

            <div class="canvas-wrapper">
                <canvas id="main-canvas"></canvas>
            </div>

            <div class="button-bar">
                <button id="save-btn">💾 Speichern</button>
                <button id="delete-btn" class="danger">Löschen</button>
            </div>
            <div id="status-bar"></div>
        </div>
    </div>

    <div id="popup-view" class="view-container">
        </div>

    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        {main_js}
    </script>
</body>
</html>
"""


# --- 4. Die Plugin-Hauptklasse ---

class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("Pro Canvas V1")

        if mode == "Window":
            self.resize(900, 700)  # Etwas breiter für Canvas
        else:
            self.resize(400, 500)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        self._current_theme = _detect_host_theme(default=theme if theme in SUPPORTED_THEMES else THEME_LIGHT)

        # 1. Backend-Instanz (umbenannt zu CanvasAPI)
        self.backend = CanvasAPI(initial_theme=self._current_theme)
        self.backend.themeChanged.connect(self._on_backend_theme_changed)

        # 2. WebChannel einrichten
        self.channel = QWebChannel(self.browser.page())
        self.channel.registerObject('backend', self.backend)
        self.browser.page().setWebChannel(self.channel)

        # 3. HTML zusammenbauen
        self.html_content = HTML_TEMPLATE.format(
            style=STYLE_CSS,
            main_js=MAIN_JS
        )

        # 4. Base URL setzen (wichtig für interne Ressourcen)
        try:
            current_dir_path = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            current_dir_path = os.path.abspath(os.getcwd())

        base_url = QUrl.fromLocalFile(current_dir_path + os.path.sep)
        base_url.setQuery(f"mode={mode}&theme={self._current_theme}")

        self.browser.setHtml(self.html_content, base_url)
        self._view_ready = False
        self.browser.loadFinished.connect(self._on_view_ready)

        self._theme_watcher = None
        app_instance = QApplication.instance()
        if app_instance is not None:
            self._theme_watcher = HostThemeWatcher(app_instance)
            self._theme_watcher.themeChanged.connect(self.backend.set_theme)
            self.destroyed.connect(self._cleanup_theme_watcher)

    def _on_view_ready(self, ok: bool):
        self._view_ready = bool(ok)
        if ok:
            self._push_theme_to_web(self.backend.current_theme())

    def _push_theme_to_web(self, theme: str):
        if not self._view_ready: return
        script = f'window.applyTheme && window.applyTheme("{theme}")'
        try:
            self.browser.page().runJavaScript(script)
        except Exception:
            pass

    def _on_backend_theme_changed(self, theme: str):
        self._current_theme = theme
        self._push_theme_to_web(theme)

    def _cleanup_theme_watcher(self):
        if self._theme_watcher:
            self._theme_watcher.cleanup()
            self._theme_watcher.deleteLater()
            self._theme_watcher = None

    def closeEvent(self, event):
        self._cleanup_theme_watcher()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Window Modus starten
    main_window = PluginWidget(mode="Window")
    main_window.show()

    sys.exit(app.exec_())