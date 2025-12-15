# scripts/readme_manager.py
import os
import sys
import shutil
from PyQt5.QtCore import (
    QObject, pyqtSlot, pyqtSignal, QUrl, QEvent, QTimer, QSize
)
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QApplication, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtGui import QPalette

# --- KONFIGURATION ---
# Hier werden die READMEs gespeichert:
DATA_DIR = os.path.expanduser('~/.tray_launcher_readmes')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

THEME_LIGHT = "light"
THEME_DARK = "dark"
SUPPORTED_THEMES = {THEME_LIGHT, THEME_DARK}


# --- 1. Backend Logik (API) ---

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


class ReadmeAPI(QObject):
    """
    Schnittstelle zwischen Python (Dateisystem) und JavaScript (Editor).
    """
    # Signale an JS
    fileListChanged = pyqtSignal()
    contentLoaded = pyqtSignal(str, str)  # title, content
    themeChanged = pyqtSignal(str)

    def __init__(self, initial_theme=THEME_LIGHT):
        super().__init__()
        self._theme = initial_theme

    @pyqtSlot(result=list)
    def list_files(self):
        """Gibt eine Liste aller .md Dateien zurück."""
        try:
            files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith('.md')]
            files.sort(key=str.lower)
            return files
        except Exception as e:
            print(f"Fehler beim Listen: {e}")
            return []

    @pyqtSlot(str, result=str)
    def load_file(self, filename):
        """Lädt den Inhalt einer Datei."""
        if not filename: return ""
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path): return ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Fehler beim Laden von {filename}: {e}")
            return ""

    @pyqtSlot(str, str)
    def save_file(self, filename, content):
        """Speichert Inhalt in Datei. Erstellt sie, falls nicht existent."""
        if not filename: return
        # Sicherstellen, dass Endung stimmt
        if not filename.lower().endswith('.md'):
            filename += ".md"

        path = os.path.join(DATA_DIR, filename)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.fileListChanged.emit()  # Liste aktualisieren (falls neue Datei)
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")

    @pyqtSlot(str)
    def delete_file(self, filename):
        """Löscht eine Datei."""
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            try:
                os.remove(path)
                self.fileListChanged.emit()
            except Exception as e:
                print(f"Fehler beim Löschen: {e}")

    @pyqtSlot(result=str)
    def get_theme(self):
        return self._theme

    @pyqtSlot(str)
    def set_theme(self, theme):
        """Kann vom JS aufgerufen werden, oder intern."""
        t = theme.lower()
        if t in SUPPORTED_THEMES and t != self._theme:
            self._theme = t
            self.themeChanged.emit(t)


# --- 2. Frontend (HTML/JS/CSS) ---

STYLE_CSS = r"""
/* --- Grundlayout --- */
* { box-sizing: border-box; }
body {
    margin: 0; padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    height: 100vh; overflow: hidden;
    display: flex;
    background-color: #ffffff; color: #333;
    transition: background 0.3s, color 0.3s;
}

/* --- Sidebar (Links) --- */
#sidebar {
    width: 250px;
    background: #f4f6f8;
    border-right: 1px solid #e1e4e8;
    display: flex; flex-direction: column;
    flex-shrink: 0;
}
#sidebar-header {
    padding: 10px; border-bottom: 1px solid #e1e4e8;
    display: flex; gap: 5px;
}
#file-list {
    flex: 1; overflow-y: auto; list-style: none; padding: 0; margin: 0;
}
#file-list li {
    padding: 8px 15px; cursor: pointer; border-bottom: 1px solid transparent;
    font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
#file-list li:hover { background-color: #e8eaed; }
#file-list li.active { background-color: #0366d6; color: white; }

/* --- Editor & Preview Container --- */
#main-area {
    flex: 1; display: flex; flex-direction: row;
    height: 100%;
}
#editor-pane {
    flex: 1; display: flex; flex-direction: column;
    border-right: 1px solid #e1e4e8;
}
#preview-pane {
    flex: 1; padding: 20px 40px; overflow-y: auto;
    background: #fff;
}

/* --- Editor Inputs --- */
#meta-bar {
    padding: 10px; border-bottom: 1px solid #e1e4e8;
    display: flex; align-items: center; justify-content: space-between;
    background: #fafbfc;
}
#current-filename {
    font-weight: bold; border: none; background: transparent;
    font-size: 14px; flex: 1; color: inherit;
}
textarea#editor {
    flex: 1; width: 100%; resize: none; border: none; outline: none; padding: 15px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 14px; line-height: 1.5; background: transparent; color: inherit;
}

/* --- Inputs & Buttons --- */
input[type="text"] {
    border: 1px solid #ccc; border-radius: 4px; padding: 4px 8px;
}
button {
    cursor: pointer; padding: 5px 10px; border-radius: 4px; border: 1px solid #ccc; background: #fff;
}
button:hover { background: #f0f0f0; }
button.primary { background: #2ea44f; color: white; border-color: rgba(27,31,35,0.15); }
button.primary:hover { background: #2c974b; }
button.danger { color: #cb2431; }
button.danger:hover { background: #cb2431; color: white; }

/* --- Dark Mode --- */
body.theme-dark { background-color: #0d1117; color: #c9d1d9; }
body.theme-dark #sidebar { background: #161b22; border-right-color: #30363d; }
body.theme-dark #sidebar-header { border-bottom-color: #30363d; }
body.theme-dark #file-list li:hover { background-color: #21262d; }
body.theme-dark #file-list li.active { background-color: #1f6feb; }
body.theme-dark #editor-pane { border-right-color: #30363d; background: #0d1117; }
body.theme-dark #preview-pane { background: #0d1117; }
body.theme-dark #meta-bar { background: #161b22; border-bottom-color: #30363d; }
body.theme-dark input[type="text"], body.theme-dark button {
    background: #21262d; border-color: #363b42; color: #c9d1d9;
}
body.theme-dark button:hover { background: #30363d; }
body.theme-dark button.primary { background: #238636; border-color: #2ea043; color: white; }

/* --- Markdown Styles (Github like) --- */
.markdown-body { font-size: 16px; line-height: 1.5; }
.markdown-body h1, .markdown-body h2 { border-bottom: 1px solid #eaecef; padding-bottom: .3em; }
.theme-dark .markdown-body h1, .theme-dark .markdown-body h2 { border-bottom-color: #21262d; }
.markdown-body pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; }
.theme-dark .markdown-body pre { background: #161b22; }
.markdown-body code { font-family: monospace; background: rgba(175, 184, 193, 0.2); padding: 0.2em 0.4em; border-radius: 6px; font-size: 85%; }
.markdown-body blockquote { border-left: 0.25em solid #dfe2e5; color: #6a737d; padding: 0 1em; }
.theme-dark .markdown-body blockquote { border-left-color: #30363d; color: #8b949e; }
.markdown-body img { max-width: 100%; }

/* --- Helper --- */
.hidden { display: none !important; }
"""

MAIN_JS = r"""
let currentFile = null;
let isScrolling = false;

window.addEventListener('load', () => {
    // QWebChannel initialisieren
    new QWebChannel(qt.webChannelTransport, (channel) => {
        window.backend = channel.objects.backend;

        // Signale verbinden
        window.backend.fileListChanged.connect(refreshFileList);
        window.backend.themeChanged.connect(applyTheme);

        // Initialisierung
        refreshFileList();
        window.backend.get_theme().then(applyTheme);

        // UI Events
        setupUI();
    });
});

function setupUI() {
    const editor = document.getElementById('editor');
    const preview = document.getElementById('preview-pane');

    // Live Rendering
    editor.addEventListener('input', () => {
        renderMarkdown(editor.value);
        saveDebounced();
    });

    // Scroll Sync
    editor.addEventListener('scroll', () => {
        if (!isScrolling) {
            isScrolling = true;
            syncScroll(editor, preview);
            setTimeout(() => isScrolling = false, 50);
        }
    });
    preview.addEventListener('scroll', () => {
        if (!isScrolling) {
            isScrolling = true;
            syncScroll(preview, editor);
            setTimeout(() => isScrolling = false, 50);
        }
    });

    // Buttons
    document.getElementById('btn-new').onclick = createNewFile;
    document.getElementById('btn-delete').onclick = deleteCurrentFile;
}

function syncScroll(source, target) {
    const p = source.scrollTop / (source.scrollHeight - source.clientHeight);
    target.scrollTop = p * (target.scrollHeight - target.clientHeight);
}

// --- Datei Logik ---

function refreshFileList() {
    window.backend.list_files().then(files => {
        const list = document.getElementById('file-list');
        list.innerHTML = "";

        if (files.length === 0) {
            list.innerHTML = "<li style='color:#888; font-style:italic; padding:10px;'>Keine READMEs</li>";
        }

        files.forEach(f => {
            const li = document.createElement('li');
            li.textContent = f.replace('.md', ''); // Endung verstecken
            li.onclick = () => loadFile(f);
            if (currentFile === f) li.classList.add('active');
            list.appendChild(li);
        });
    });
}

function loadFile(filename) {
    currentFile = filename;
    // UI Update List selection
    const list = document.getElementById('file-list');
    Array.from(list.children).forEach(li => {
        li.classList.toggle('active', li.textContent === filename.replace('.md', ''));
    });

    document.getElementById('current-filename').textContent = filename;
    document.getElementById('editor').disabled = false;
    document.getElementById('btn-delete').disabled = false;

    window.backend.load_file(filename).then(content => {
        document.getElementById('editor').value = content;
        renderMarkdown(content);
    });
}

function createNewFile() {
    const name = prompt("Name für das neue README:");
    if (!name) return;

    let filename = name.endsWith('.md') ? name : name + ".md";
    currentFile = filename;

    // Speichert eine leere Datei, backend triggert fileListChanged
    window.backend.save_file(filename, "# " + name + "\n\nStart typing...");

    // Wir laden die Datei direkt
    setTimeout(() => loadFile(filename), 100);
}

let saveTimeout;
function saveDebounced() {
    if (!currentFile) return;
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
        const content = document.getElementById('editor').value;
        const status = document.getElementById('status-msg');

        window.backend.save_file(currentFile, content);

        status.textContent = "Gespeichert";
        status.style.opacity = 1;
        setTimeout(() => status.style.opacity = 0, 1500);
    }, 500); // Autosave nach 500ms Inaktivität
}

function deleteCurrentFile() {
    if (!currentFile) return;
    if (confirm("Möchtest du '" + currentFile + "' wirklich löschen?")) {
        window.backend.delete_file(currentFile);
        document.getElementById('editor').value = "";
        document.getElementById('preview-pane').innerHTML = "";
        document.getElementById('current-filename').textContent = "";
        document.getElementById('editor').disabled = true;
        document.getElementById('btn-delete').disabled = true;
        currentFile = null;
    }
}

// --- Markdown Renderer ---
function renderMarkdown(text) {
    const prev = document.getElementById('preview-pane');
    if (typeof marked !== 'undefined') {
        prev.innerHTML = marked.parse(text);
        // Highlight JS neu triggern wenn vorhanden
        if (typeof hljs !== 'undefined') {
            prev.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }
    } else {
        prev.innerText = text; 
    }
}

function applyTheme(theme) {
    document.body.className = "theme-" + theme;
}
"""

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="utf-8">
    <title>README Manager</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/4.3.0/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/styles/github.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/styles/github-dark.min.css" media="(prefers-color-scheme: dark)">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.7.0/highlight.min.js"></script>

    <style>{style}</style>
</head>
<body class="theme-light">

    <div id="sidebar">
        <div id="sidebar-header">
            <button id="btn-new" class="primary" style="width:100%">+ Neu</button>
        </div>
        <ul id="file-list">
            </ul>
    </div>

    <div id="main-area">
        <div id="editor-pane">
            <div id="meta-bar">
                <span id="current-filename">Keine Datei ausgewählt</span>
                <span id="status-msg" style="color:green; font-size:12px; margin-right:10px; opacity:0; transition:opacity 0.5s;"></span>
                <button id="btn-delete" class="danger" disabled title="Löschen">🗑️</button>
            </div>
            <textarea id="editor" disabled placeholder="Wähle eine Datei links aus oder erstelle eine neue..."></textarea>
        </div>
        <div id="preview-pane" class="markdown-body">
            </div>
    </div>

    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>{main_js}</script>
</body>
</html>
"""


# --- 3. Theme Watcher (für Tray Launcher Sync) ---

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
        if self._app:
            try:
                self._app.removeEventFilter(self)
            except:
                pass
            self._app = None


# --- 4. Main Widget ---

class PluginWidget(QMainWindow):
    """
    Diese Klasse wird vom Tray Launcher geladen.
    Der Konstruktor akzeptiert `mode` (Window/Popup).
    """

    def __init__(self, mode="Window"):
        super().__init__()
        self.setWindowTitle("README Manager")
        self.resize(1000, 700)  # Standardgröße

        # Theme erkennen
        self._current_theme = _detect_host_theme()

        # Backend Setup
        self.backend = ReadmeAPI(initial_theme=self._current_theme)

        # UI Setup
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QWebEngineView()
        # Kontextmenü im Browser ausschalten (optional)
        self.browser.setContextMenuPolicy(3)  # Qt.CustomContextMenu (effektiv aus)

        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        # WebChannel Setup
        self.channel = QWebChannel(self.browser.page())
        self.channel.registerObject('backend', self.backend)
        self.browser.page().setWebChannel(self.channel)

        # HTML rendern
        html = HTML_TEMPLATE.format(
            style=STYLE_CSS,
            main_js=MAIN_JS
        )

        # WICHTIG: BaseUrl setzen, damit qrc Imports funktionieren
        # Wir nehmen den Pfad dieser Datei als Basis
        try:
            base_path = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            base_path = os.getcwd()

        base_url = QUrl.fromLocalFile(base_path + os.sep)
        self.browser.setHtml(html, base_url)

        # Theme Sync Hook
        self._theme_watcher = None
        app = QApplication.instance()
        if app:
            self._theme_watcher = HostThemeWatcher(app)
            self._theme_watcher.themeChanged.connect(self.backend.set_theme)

    def closeEvent(self, event):
        if self._theme_watcher:
            self._theme_watcher.cleanup()
        super().closeEvent(event)


# --- 5. Standalone Test ---
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    # Simulator für Tray Theme Property
    app.setProperty("toolbar_theme", "dark")

    win = PluginWidget(mode="Window")
    win.show()
    sys.exit(app.exec_())