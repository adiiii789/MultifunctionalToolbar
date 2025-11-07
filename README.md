# Multifunctional Toolbar (Tray Launcher)

Ein leichter **PyQt5**-Launcher mit Systemtray-Icon, Popup-Panel und Hauptfenster. Er listet ausführbare **Plugins** (Python & HTML) aus einem frei wählbaren Ordner, bietet **Inline-HTML-Previews**, eine **Suchleiste**, sowie eine WebEngine-**Toolbar** mit **HTML-Theme-Schalter** (🌙/☀️) und sicherem **Zurück**-Handling.

---

## Highlights

- **Systemtray-App** (Windows-optimiert)  
  - Linksklick: Hauptfenster öffnen/aktivieren  
  - Rechtsklick: kompaktes **Popup** neben dem Cursor
- **Plugins aus Ordner** `./scripts`  
  - `.py` → als Qt-Widget (klassische Plugins)  
  - `.html` → im Container oder inline (siehe `[html]`-Prefix)
- **Inline-HTML-Preview** via `QWebEngineView`  
  - Dateien mit Prefix **`[html]`** erscheinen als kompakte Cards in der Liste  
  - Optionaler **WebChannel** (z. B. Mediensteuerung)
- **Toolbar (HTML, WebEngine)**  
  - **← Explorer** (Zurück ins Listing)  
  - **🌙/☀️ Theme-Toggle** (echtes HTML-Element mit CSS)
- **Suche** (rechts oben im Hauptfenster)  
  - Filtert Einträge im aktuellen Ordner (case-insensitive)
- **Stabil & Crash-resistent**  
  - **Sicheres Zurück** (räumt WebEngine-Seiten vor dem Wechsel auf)  
  - Entkoppelter Listen-Zurück-Button (`QTimer.singleShot`)

---

## Anforderungen

- **Python 3.8+**
- **PyQt5** & **PyQtWebEngine**
  
```bash
pip install PyQt5 PyQtWebEngine
```

> Tipp: Unter Windows empfiehlt sich eine venv, um Konflikte zu vermeiden.

---

## Schnellstart

1. Repository/Projekt lokal haben.
2. Ordner `scripts/` existiert (wird beim ersten Start befüllt).
3. Starten:

```bash
python tray_launcher.py
```

Nach dem Start liegt ein Tray-Icon im Infobereich.  
- **Linksklick:** Hauptfenster  
- **Rechtsklick:** Popup mit Explorer

---

## Ordnerstruktur & Plugins

```
project/
├── tray_launcher.py
└── scripts/
    ├── timer_plugin.py       # Beispiel: Python-Plugin (Qt-Widget)
    └── html_timer/
        └── index.html        # Beispiel: HTML-Demo
```

- **Python-Plugins**: Datei exportiert **`PluginWidget`** (Qt-Widget).  
  Optionaler Konstruktor-Parameter `mode`: `"Window"` oder `"Popup"`.

```python
class PluginWidget(QWidget):
    def __init__(self, mode="Window"):
        super().__init__()
        # ... UI ...
```

- **HTML-Plugins**: 
  - Normale `.html`-Dateien werden in einem Container angezeigt.  
  - Dateien mit Prefix **`[html]`** (z. B. `[html]status.html`) erscheinen **inline**, kompakt und ohne Scrollen.
  - Für fortgeschrittene Szenarien kann eine `.py`-Datei HTML liefern, wenn sie eine Funktion  
    **`get_inline_html(mode: str) -> str`** bereitstellt.

---

## Bedienung

### Explorer
- Navigiert den **`scripts/`**-Baum.
- **Zurück**: 
  - **Toolbar-Button „← Explorer“** (wenn ein Plugin/Link offen ist)
  - **Listen-Button „← Zurück“** (im Ordnerlisting)

### Suche
- Eingabe oben rechts im Hauptfenster → *Enter* → Filtert Einträge im aktuellen Ordner.

### Theme
- **HTML-Button** in der Toolbar (🌙/☀️).  
  - Wechselt zwischen **Dark** und **Light** Theme.  
  - Einstellungen werden sofort auf UI und Toolbar gespiegelt.

### Links in Inline-HTML
- Klicks werden abgefangen:
  - **Lokale Dateien** → als Plugin geöffnet  
  - **Web-URLs** → im eingebetteten Viewer (eigene Seite in der App)

---

## Stabilität & Sicherheit

- **Safe Back**: Beim Zurückwechsel werden aktive `QWebEngineView` zuerst auf `about:blank` umgeladen und die Seite **asynchron entfernt** → verhindert **Access Violations** (0xC0000005).
- **Entkoppelter Listen-Zurück**: `QTimer.singleShot(0, ...)` vermeidet Rennen zwischen Render & Rebuild.
- **Teardown**: WebEngine-Toolbars werden beim Beenden versteckt und `deleteLater()` aufgerufen.

---

## Erweiterungstipps

- **Eigene Python-Plugins**:  
  - Lege `.py` in `scripts/` ab, exportiere `PluginWidget`.  
  - Nutze den `mode`-Parameter für unterschiedliche Layouts im Popup vs. Hauptfenster.

- **Eigene Inline-HTML-Cards**:  
  - Benenne Datei mit Prefix `[html]`.  
  - Vermeide Scrollbars; nutze responsive, kompakte Layouts.

- **WebChannel**:  
  - In Inline-HTML ist `window.media` (Beispiel: Medien-Keys) verfügbar.  
  - Eigene Bridges lassen sich analog registrieren.

---

## Troubleshooting

- **„PyQtWebEngine nicht verfügbar“**  
  → `pip install PyQtWebEngine`  
  → Falls Headless/Server: WebEngine benötigt GUI-Stack.

- **Crash beim Zurück (ältere Builds)**  
  → Stelle sicher, dass die „Safe Back“-Änderungen enthalten sind (WebViews → `about:blank`, `deleteLater()`).

- **Plugin lädt nicht**  
  - Python: Prüfe, ob `PluginWidget` existiert und instanziierbar ist.  
  - HTML: Dateipfade & Berechtigungen prüfen.

---

## Lizenz

Wähle eine Lizenz deiner Wahl und ergänze sie hier (z. B. MIT).

---

## Credits

- PyQt5, PyQtWebEngine  
- Design: kompakte Launcher-Erfahrung mit HTML-Toolbar und systemfreundlichem Verhalten.
