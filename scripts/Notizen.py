# scripts/pro_flappy_html_v3_singlefile.py
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

NOTES_DIR = os.path.expanduser('~/.simple_notes_plugin_v2')
os.makedirs(NOTES_DIR, exist_ok=True)

THEME_LIGHT = "light"
THEME_DARK = "dark"
SUPPORTED_THEMES = {THEME_LIGHT, THEME_DARK}


def _detect_host_theme(default=THEME_LIGHT):
    """
    Versucht das aktuelle Theme der Hauptanwendung zu ermitteln.
    Fallback ist 'light', falls keine Information verfügbar ist.
    """
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


class NotesAPI(QObject):
    """
    Diese API wird per QWebChannel 1:1 in JavaScript bereitgestellt.
    JS kann diese Methoden direkt aufrufen (z.B. window.backend.list_notes())
    """

    # Signal, das an JS gesendet wird, wenn sich die Notizliste ändert
    notesChanged = pyqtSignal()
    themeChanged = pyqtSignal(str)

    def __init__(self, initial_theme=THEME_LIGHT):
        super().__init__()
        self._theme = initial_theme if initial_theme in SUPPORTED_THEMES else THEME_LIGHT

    @pyqtSlot(result='QVariantList')
    def list_notes(self):
        """Liefert eine Liste aller Notiztitel."""
        try:
            return sorted(
                [f[:-4] for f in os.listdir(NOTES_DIR) if f.endswith('.txt')],
                key=lambda s: s.lower()
            )
        except Exception as e:
            print(f"Fehler beim Auflisten der Notizen: {e}")
            return []

    @pyqtSlot(str, result=str)
    def load_note(self, title):
        """Lädt den Inhalt einer Notiz anhand des Titels."""
        path = os.path.join(NOTES_DIR, title + '.txt')
        if not title or not os.path.exists(path):
            return ""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Fehler beim Laden der Notiz {title}: {e}")
            return ""

    @pyqtSlot(str, str)
    def save_note(self, title, content):
        """Speichert oder erstellt eine Notiz."""
        if not title: return
        path = os.path.join(NOTES_DIR, title + '.txt')
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.notesChanged.emit()  # Signal senden!
        except Exception as e:
            print(f"Fehler beim Speichern der Notiz {title}: {e}")

    @pyqtSlot(str)
    def delete_note(self, title):
        """Löscht eine Notiz."""
        if not title: return
        path = os.path.join(NOTES_DIR, title + '.txt')
        if os.path.exists(path):
            try:
                os.remove(path)
                self.notesChanged.emit()
            except Exception as e:
                print(f"Fehler beim Löschen der Notiz {title}: {e}")

    def _set_theme_internal(self, theme: str):
        theme_lower = (theme or "").lower()
        if theme_lower not in SUPPORTED_THEMES or theme_lower == self._theme:
            return False
        self._theme = theme_lower
        self.themeChanged.emit(self._theme)
        return True

    @pyqtSlot(result=str)
    def get_theme(self):
        """Gibt das derzeit verwendete Theme zurück."""
        return self._theme

    @pyqtSlot(str)
    def set_theme(self, theme):
        """
        Wird vom Frontend aufgerufen, um das Theme (light/dark) zu setzen.
        """
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


# --- 2. Frontend-Code (als Python-Strings) ---

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
    display: flex;
}
/* --- Modus-Umschaltung --- */
.view-container {
    display: none; /* Standardmäßig alles ausblenden */
}
body.window-mode #window-view {
    display: flex; /* Nur den View für den aktiven Modus anzeigen */
}
body.popup-mode #popup-view {
    display: flex;
}
/* --- Allgemeines Styling --- */
input[type="text"], textarea {
    width: 95%;
    margin: .5em 0 1em 0;
    padding: 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-family: inherit;
    font-size: 1em;
    background: #fff;
    color: inherit;
}
textarea {
    resize: none;
}
button {
    padding: .8em 1.5em;
    margin-top: 1em;
    border: none;
    border-radius: 4px;
    background: #007aff;
    color: white;
    font-size: 1em;
    cursor: pointer;
    transition: background 0.2s;
}
button:hover { background: #0056b3; }
button.danger { background: #dc3545; }
button.danger:hover { background: #a71d2a; }
#status-bar, #popup-status-bar {
    margin-top: 1em;
    color: green;
    font-weight: bold;
    height: 1.2em;
}
/* --- Window-Modus --- */
#sidebar {
    background: #eaeaea;
    width: 30%;
    min-width: 150px;
    padding: 1em;
    box-sizing: border-box;
    overflow-y: auto;
    height: 100vh;
    border-right: 1px solid #d7d7d7;
}
#main {
    flex: 1;
    padding: 2em;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: #ffffff;
}
#main #content {
    flex: 1; /* Nimmt allen verfügbaren Platz ein */
}
#notelist {
    padding: 0; list-style: none; margin-bottom: 2em;
}
#notelist li {
    padding: .5em .3em;
    cursor: pointer;
    border-radius: 3px;
    word-break: break-all;
    transition: background .2s ease;
}
#notelist li:hover { background: #dcdcdc; }
#notelist li.selected {
    background: #007aff;
    color: white;
    font-weight: bold;
}
#new-title { width: 90%; }
#add-note-btn { width: 100%; }
/* --- Popup-Modus --- */
#popup-view {
    flex-direction: column;
    padding: 1.5em;
    box-sizing: border-box;
    background: inherit;
    align-items: stretch;
    justify-content: flex-start;
}
#popup-view h3 { margin-top: 0; }
#popup-view input, #popup-view textarea {
    width: 100%;
    margin: 0 auto 1em auto;
    display: block;
}
#popup-view textarea { height: 60vh; }

/* --- Dark Theme Overrides --- */
body.theme-dark {
    background: #111418;
    color: #f1f1f1;
}
body.theme-dark #sidebar {
    background: #1d2128;
    border-right-color: #292d36;
    color: #eaeaea;
}
body.theme-dark #main {
    background: #16191f;
}
body.theme-dark input[type="text"],
body.theme-dark textarea {
    background: #242933;
    border-color: #3a4151;
    color: #f5f5f5;
}
body.theme-dark #notelist li:hover {
    background: #2c3242;
}
body.theme-dark #notelist li.selected {
    background: #4d6bff;
}
body.theme-dark button {
    background: #2d7dff;
    color: #fefefe;
}
body.theme-dark button:hover {
    background: #245fcc;
}
body.theme-dark button.danger {
    background: #b93737;
}
body.theme-dark button.danger:hover {
    background: #962a2a;
}
body.theme-dark #popup-view {
    background: transparent;
}
body.theme-dark #sidebar h3,
body.theme-dark #popup-view h3 {
    color: inherit;
}
body.theme-dark #status-bar,
body.theme-dark #popup-status-bar {
    color: #70ff95;
}
body.theme-dark #popup-view input,
body.theme-dark #popup-view textarea {
    background: #2f323b;
    border-color: #414753;
    color: #f5f5f5;
}
body.theme-light #popup-view input,
body.theme-light #popup-view textarea {
    background: #ffffff;
    border-color: #cfd7e6;
    color: #1f1f1f;
}
body.theme-light {
    background: #FFFFFF;
    color: #1f1f1f;
}
body.theme-light #sidebar {
    background: #f4f6fb;
    border-right-color: #dfe3ef;
    color: #1f1f1f;
}
body.theme-light #main {
    background: #ffffff;
    color: #1f1f1f;
}
body.theme-light input[type="text"],
body.theme-light textarea {
    background: #ffffff;
    border-color: #cfd7e6;
    color: #1f1f1f;
}
body.theme-light #notelist li {
    color: #1f1f1f;
}
body.theme-light #notelist li:hover {
    background: #e2e9fb;
}
body.theme-light #notelist li.selected {
    background: #3A4A6A;
    color: #ffffff;
}
body.theme-light button {
    background: #3A4A6A;
    color: #ffffff;
}
body.theme-light button:hover {
    background: #4c5f85;
}
body.theme-light button.danger {
    background: #d9534f;
}
body.theme-light button.danger:hover {
    background: #c14440;
}
body.theme-light #status-bar,
body.theme-light #popup-status-bar {
    color: #2a8f60;
}
body.theme-dark {
    background: #2E2E2E;
    color: #f5f5f5;
}
body.theme-dark #sidebar {
    background: #1f232b;
    border-right-color: #373b44;
    color: #f5f5f5;
}
body.theme-dark #main {
    background: #2b2f38;
    color: #f5f5f5;
}
body.theme-dark input[type="text"],
body.theme-dark textarea {
    background: #3A3A3A;
    border-color: #4d4d4d;
    color: #f5f5f5;
}
body.theme-dark #notelist li {
    color: #f0f0f0;
}
body.theme-dark #notelist li:hover {
    background: #333948;
}
body.theme-dark #notelist li.selected {
    background: #3A4A6A;
    color: #ffffff;
}
body.theme-dark button {
    background: #3A4A6A;
    color: #ffffff;
}
body.theme-dark button:hover {
    background: #4c5f84;
}
body.theme-dark button.danger {
    background: #b74c4c;
}
body.theme-dark button.danger:hover {
    background: #a04545;
}
body.theme-dark #status-bar,
body.theme-dark #popup-status-bar {
    color: #6fe3a3;
}
"""

MAIN_JS = r"""
let currentTheme = 'light';

// Warten, bis das Fenster geladen ist, um die Bridge einzurichten
window.addEventListener('load', () => {
    // Prüfen, ob der qt.webChannelTransport existiert
    // Dieses Objekt wird von qwebchannel.js bereitgestellt
    if (typeof qt === 'undefined' || typeof qt.webChannelTransport === 'undefined') {
        console.error("QWebChannel nicht gefunden! Läuft die App außerhalb von PyQt?");
        document.body.innerHTML = "<h1>Fehler: QWebChannel konnte nicht geladen werden.</h1><p>Bitte stellen Sie sicher, dass die Qt-Ressourcen korrekt installiert sind.</p>";
        return;
    }

    // Die "Bridge" initialisieren
    new QWebChannel(qt.webChannelTransport, (channel) => {
        // Das in Python registrierte 'backend'-Objekt in 'window.backend' spiegeln
        window.backend = channel.objects.backend;

        // Globale UI-Elemente initialisieren
        initApp();
        initThemeSync();
    });
});

/**
 * Initialisiert die Anwendung basierend auf dem Modus.
 */
function initApp() {
    // 1. Modus aus der URL auslesen (z.B. ?mode=Popup)
    const params = new URLSearchParams(window.location.search);
    const mode = params.get('mode') || 'Window'; // Standard ist Window

    // 2. Body-Klasse setzen, um das CSS-Styling zu aktivieren
    document.body.classList.add(mode.toLowerCase() + '-mode');

    // 3. Je nach Modus die passenden Event-Listener registrieren
    if (mode === 'Window') {
        initWindowView();
    } else {
        initPopupView();
    }

    // 4. Global auf Änderungen vom Python-Backend lauschen!
    // Wenn eine andere App (oder das Popup) speichert, aktualisiert sich die Liste.
    if (window.backend && window.backend.notesChanged) {
        window.backend.notesChanged.connect(refreshNoteList);
    }
}

async function initThemeSync() {
    applyTheme('light');
    if (!window.backend) return;
    if (window.backend.themeChanged && typeof window.backend.themeChanged.connect === 'function') {
        window.backend.themeChanged.connect(applyTheme);
    }
    try {
        const theme = await window.backend.get_theme();
        applyTheme(theme || 'light');
    } catch (e) {
        applyTheme('light');
    }
}

// --- Logik für den Window-Modus ---

// UI-Elemente für Window-Modus
const el = {
    noteList: document.getElementById('notelist'),
    newTitle: document.getElementById('new-title'),
    addNoteBtn: document.getElementById('add-note-btn'),
    currentTitle: document.getElementById('current-title'),
    content: document.getElementById('content'),
    saveBtn: document.getElementById('save-btn'),
    deleteBtn: document.getElementById('delete-btn'),
    statusBar: document.getElementById('status-bar'),
};

let currentSelectedTitle = "";

function initWindowView() {
    // Event Listeners
    el.addNoteBtn.addEventListener('click', addNewNote);
    el.saveBtn.addEventListener('click', saveCurrentNote);
    el.deleteBtn.addEventListener('click', deleteCurrentNote);

    // Beim Start die Liste laden
    refreshNoteList();
}

/**
 * Holt die Notizliste vom Python-Backend und zeigt sie an.
 */
async function refreshNoteList() {
    if (!window.backend || !el.noteList) return;

    try {
        const notes = await window.backend.list_notes();
        el.noteList.innerHTML = ""; // Liste leeren

        notes.forEach(title => {
            const li = document.createElement('li');
            li.innerText = title;
            li.dataset.title = title; // Titel im DOM speichern
            li.addEventListener('click', () => openNote(title));

            if (title === currentSelectedTitle) {
                li.classList.add('selected');
            }
            el.noteList.appendChild(li);
        });
    } catch (e) {
        console.error("Fehler beim Laden der Notizliste:", e);
    }
}

/**
 * Öffnet eine Notiz und lädt den Inhalt vom Python-Backend.
 */
async function openNote(title) {
    try {
        const content = await window.backend.load_note(title);

        currentSelectedTitle = title;
        el.currentTitle.value = title;
        el.content.value = content;

        // "selected"-Klasse in der Liste aktualisieren
        document.querySelectorAll('#notelist li').forEach(li => {
            li.classList.toggle('selected', li.dataset.title === title);
        });
    } catch (e) {
        console.error("Fehler beim Öffnen der Notiz:", e);
        showStatus("Fehler beim Laden der Notiz.", "error");
    }
}

/**
 * Speichert die aktuell geöffnete Notiz im Backend.
 */
async function saveCurrentNote() {
    const title = el.currentTitle.value;
    const content = el.content.value;

    if (!title) {
        showStatus("Bitte erstelle eine 'Neue Notiz' mit Titel.", "error");
        return;
    }

    await window.backend.save_note(title, content);
    showStatus(`Notiz '${title}' gespeichert!`, "success");
}

/**
 * Erstellt eine neue, leere Notiz.
 */
async function addNewNote() {
    const newTitle = el.newTitle.value.trim();
    if (!newTitle) {
        showStatus("Bitte einen Titel für die neue Notiz eingeben.", "error");
        return;
    }

    // Eine leere Notiz im Backend speichern
    await window.backend.save_note(newTitle, "");

    // Das 'notesChanged'-Signal vom Backend wird automatisch 'refreshNoteList' triggern.

    // Die neue Notiz direkt öffnen
    currentSelectedTitle = newTitle; // Wichtig, damit sie selektiert wird
    await refreshNoteList(); // Liste neu laden
    openNote(newTitle); // Inhalt laden (wird leer sein)

    el.newTitle.value = ""; // Input-Feld leeren
}

/**
 * Löscht die aktuell geöffnete Notiz.
 */
async function deleteCurrentNote() {
    const title = el.currentTitle.value;
    if (!title) return;

    // Hier wäre Platz für eine "Sicher?"-Abfrage

    await window.backend.delete_note(title);

    // Das 'notesChanged'-Signal vom Backend wird 'refreshNoteList' triggern.

    // Editor leeren
    el.currentTitle.value = "";
    el.content.value = "";
    currentSelectedTitle = "";
    showStatus(`Notiz '${title}' gelöscht.`, "success");
}


// --- Logik für den Popup-Modus ---
function initPopupView() {
    const titleEl = document.getElementById('popup-title');
    const contentEl = document.getElementById('popup-content');
    const saveBtn = document.getElementById('popup-save-btn');
    const statusBar = document.getElementById('popup-status-bar');

    saveBtn.addEventListener('click', async () => {
        const title = titleEl.value.trim();
        const content = contentEl.value.trim();

        if (!title) {
            statusBar.innerText = "Bitte einen Titel eingeben.";
            statusBar.style.color = "red";
            return;
        }

        await window.backend.save_note(title, content);

        statusBar.innerText = `Notiz '${title}' gespeichert!`;
        statusBar.style.color = "green";

        // Felder leeren und nach 2 Sek. Status zurücksetzen
        titleEl.value = "";
        contentEl.value = "";
        setTimeout(() => { statusBar.innerText = ""; }, 2000);
    });
}


// --- Hilfsfunktionen ---
function showStatus(message, type) {
    if (!el.statusBar) return;
    el.statusBar.innerText = message;
    el.statusBar.style.color = (type === "error") ? "red" : "green";

    setTimeout(() => { el.statusBar.innerText = ""; }, 3000);
}

function applyTheme(theme) {
    currentTheme = (theme === 'dark') ? 'dark' : 'light';
    document.body.classList.remove('theme-light', 'theme-dark');
    document.body.classList.add(`theme-${currentTheme}`);
}
"""

# --- 3. Das HTML-Template, das alles zusammenfügt ---

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>Notizen</title>
    <style>
        {style}
    </style>
</head>
<body class="theme-light">

    <div id="window-view" class="view-container">
        <div id="sidebar">
            <h3>Notizen</h3>
            <ul id="notelist"></ul>
            <input id="new-title" type="text" placeholder="Neuer Titel..." />
            <button id="add-note-btn">Neue Notiz</button>
        </div>
        <div id="main">
            <input id="current-title" type="text" placeholder="Titel" readonly />
            <textarea id="content" placeholder="Text hier eingeben ..."></textarea>
            <div class="button-bar">
                <button id="save-btn">Speichern</button>
                <button id="delete-btn" class="danger">Löschen</button>
            </div>
            <div id="status-bar"></div>
        </div>
    </div>

    <div id="popup-view" class="view-container">
        <h3>Schnelle Notiz</h3>
        <input id="popup-title" placeholder="Titel..." />
        <textarea id="popup-content" placeholder="Notiztext hier..."></textarea>
        <button id="popup-save-btn">Speichern</button>
        <div id="popup-status-bar"></div>
    </div>

    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <script>
        {main_js}
    </script>

</body>
</html>
"""


# --- 4. Die Plugin-Hauptklasse (JETZT MIT KORREKTEM SETUP) ---

class PluginWidget(QMainWindow):
    def __init__(self, theme="light", mode="Window"):
        super().__init__()
        self.setWindowTitle("Pro Notizen V3 (Robust)")

        if mode == "Window":
            self.resize(700, 800)
        else:
            self.resize(400, 500)  # Kleineres Fenster für Popup

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.browser = QWebEngineView()
        layout.addWidget(self.browser)
        self.setCentralWidget(central)

        # Theme-State aus der Host-Anwendung ermitteln und setzen
        self._current_theme = _detect_host_theme(default=theme if theme in SUPPORTED_THEMES else THEME_LIGHT)

        # 1. Python-Backend-Instanz erstellen
        self.backend = NotesAPI(initial_theme=self._current_theme)
        self.backend.themeChanged.connect(self._on_backend_theme_changed)

        # 2. WebChannel einrichten
        self.channel = QWebChannel(self.browser.page())

        # 3. Das Backend-Objekt im Channel unter dem Namen 'backend' registrieren
        self.channel.registerObject('backend', self.backend)

        # 4. Den Channel der Browser-Seite zuweisen
        self.browser.page().setWebChannel(self.channel)

        # 5. Das finale HTML aus den Teilen zusammenbauen
        #    (Beachte: {qwebchannel} ist weg, da es jetzt im Template-HTML ist)
        self.html_content = HTML_TEMPLATE.format(
            style=STYLE_CSS,
            main_js=MAIN_JS
        )

        # 6. **** DER ENTSCHEIDENDE FIX ****
        #    Wir müssen setHtml() eine 'baseUrl' geben, damit
        #    der <script src="qrc:...">-Tag laden darf.
        #    Wir nutzen den Pfad dieser Python-Datei als Basis.

        # Finde den Pfad zur aktuellen Datei
        try:
            # __file__ ist der zuverlässigste Weg
            current_dir_path = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            # Fallback, falls __file__ nicht definiert ist (z.B. in einer REPL)
            current_dir_path = os.path.abspath(os.getcwd())

        # Erstelle eine file:// QUrl. Der OS-spezifische Separator ist wichtig.
        base_url = QUrl.fromLocalFile(current_dir_path + os.path.sep)

        # Hänge die Modus/Theme-Parameter an die URL an, damit JS sie lesen kann
        base_url.setQuery(f"mode={mode}&theme={self._current_theme}")

        # Lade das HTML mit der korrekten Basis-URL
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
        if not self._view_ready:
            return
        script = f'window.applyTheme && window.applyTheme("{theme}")'
        try:
            self.browser.page().runJavaScript(script)
        except Exception as exc:
            print(f"Theme-Sync JS fehlgeschlagen: {exc}")

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


# --- Zum Testen der Anwendung ---
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Teste den "Window"-Modus
    main_window = PluginWidget(mode="Window")
    main_window.show()

    # Teste den "Popup"-Modus in einem separaten Fenster
    popup_window = PluginWidget(mode="Popup")
    popup_window.setWindowTitle("Popup Modus")
    popup_window.show()

    sys.exit(app.exec_())