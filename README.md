# Multifunctional Toolbar v2 (Traylauncher)

Sauberer Nachbau des Tray-Launchers. `Traylauncher.py` liegt im Root und ist die Mainklasse. Optik, Größen und Verhalten des Originals sind vollständig erhalten (Popup 15 % × 50 % des Bildschirms, Hauptfenster 40 % × 40 %, Theme-Toggle mit Sonne/Mond-Switch, Tabs, Suche, identische Farben und Stylesheets).

## Start

```bash
pip install PyQt5 PyQtWebEngine
pip install winsdk   # optional: Album-Cover der laufenden Medien (Win 10/11)
python Traylauncher.py
```

Inline-HTML-Cards können über die Media-Bridge zusätzlich `media.requestMediaInfo()` aufrufen und erhalten über das Signal `media.mediaInfoChanged` ein JSON mit Titel, Interpret, Wiedergabestatus und Album-Cover (Base64) der gerade laufenden Medien — genutzt z. B. von `Dual UI.py`, das das Cover rechts im Button anzeigt. Ohne `winsdk` oder ohne laufende Medien bleibt das Cover einfach ausgeblendet.

Linksklick auf das Tray-Icon: Hauptfenster. Rechtsklick: Popup.

## Neu: Plugin-Parameter in der Plugin-Datei

Was ein Plugin "kann", wird jetzt per Konstanten oben in der Datei gesteuert. Die Werte werden per AST gelesen — die Datei wird dafür nicht ausgeführt.

| Parameter | Typ | Wirkung |
|---|---|---|
| `HTML_BUTTON = True` | bool | Der Listen-Button wird als HTML-Card gerendert |
| `BUTTON_HTML = "<div>…</div>"` | str | Das HTML für den Button (nur mit `HTML_BUTTON = True`) |
| `BUTTON_HTML_FILE = "card.html"` | str | HTML-Datei (relativ zur Plugin-Datei) für den Button |
| `BUTTON_HEIGHT = 80` | int | Höhe des Buttons/der Card in px (Standard 60 bzw. Original-Formel) |
| `NAME = "Musik"` | str | Anzeigename statt Dateiname |
| `ICON = "🎵"` | str | Emoji/Text vor dem Namen — oder eine **Bilddatei** (`ICON = "icon.png"`, relativ zur Plugin-Datei oder absolut; .png/.jpg/.svg/.ico/.gif/.webp/.bmp). Wird links im Listen-Button und als Tab-Icon angezeigt |
| `OPACITY = 0.85` | float | Transparenz des Buttons, 0–1 (Zusatzfeature) |
| `RUN_AS = "widget"` | str | `"widget"` (Standard, öffnet im Tab), `"process"` (eigener Python-Prozess), `"browser"` (HTML im Standardbrowser) |
| `ALLOW_POPUP = False` | bool | Eintrag im Rechtsklick-Popup ausblenden |
| `ALLOW_WINDOW = False` | bool | Eintrag im Hauptfenster ausblenden |
| `MEDIA_BRIDGE = False` | bool | WebChannel-Mediensteuerung (`media.playPause()` usw.) deaktivieren |
| `PINNED = True` | bool/int | Plugin oben in der Liste anpinnen (vor allen anderen Einträgen). Zahl statt `True` legt die Reihenfolge mehrerer angepinnter Plugins fest (kleiner = weiter oben) |

Für `.html`-Dateien gelten dieselben Parameter als führende HTML-Kommentare:

```html
<!-- html_button: true -->
<!-- button_height: 80 -->
```

## Transparenz (Zusatzfeature)

Global oben in `Traylauncher.py`: `POPUP_OPACITY` (Standard 0.97) und `MAIN_WINDOW_OPACITY` (Standard 1.0). Pro Plugin über `OPACITY`.

## HTML-Explorer (anpassbare Oberfläche)

Die Plugin-Liste (Ordner, Buttons, Inline-Cards) wird als HTML gerendert — Python ist nur noch Backend und liefert den Zustand als JSON über eine QWebChannel-Bridge (`explorer`-Objekt: `getState`, `open`, `enterDir`, `goBack`, `openLink`; dazu `media` für die Cards). Das komplette Aussehen liegt in **`ui/explorer.html`** (wird beim ersten Start angelegt) und kann dort frei angepasst werden — Farben, Abstände, Animationen, Layout. Die mitgelieferte Standard-UI repliziert den bisherigen Qt-Explorer exakt (gleiche Farben, Höhen, Hover-Effekte, Scrollbar).

Inline-Cards laufen als iframes innerhalb des Explorers; `window.media`, `window.toolbarMode` und **`openPlugin(pfad)`** stehen dort zur Verfügung — damit kann ein Button in der Card jedes Plugin öffnen (`openPlugin('Timer.py')`, relativ zum Ordner der Card, oder absolut; `openPlugin()` ohne Argument öffnet die eigene Datei). Linkklicks (`<a href>`) öffnen wie bisher als Tab, `get_inline_html(mode)` und alle Plugin-Parameter funktionieren unverändert. Über `HTML_EXPLORER = False` oben in `Traylauncher.py` (oder ohne PyQtWebEngine) wird automatisch der klassische Qt-Explorer verwendet.

## Kanonische Plugin-Struktur

Plugins sollten möglichst diesem Aufbau folgen — der Plugin-Editor erzeugt ihn, erkennt ihn beim Laden und trägt die Teile automatisch in Formular und Vorschau (Button/Window/Popup) ein:

```python
# --- Plugin-Parameter ---
NAME = "Mein Plugin"
HTML_BUTTON = True
# ------------------------

BUTTON_HTML = """…Card-HTML…"""          # optional: Button in der Liste

class PluginWidget(QMainWindow):
    def __init__(self, mode="Window"):
        ...
        if mode == "Window":
            self.html = r"""…Fenster-HTML…"""
        else:  # Popup
            self.html = r"""…Popup-HTML…"""
```

Abwandlungen (unbedingtes `self._base_html = …`, Modul-Variablen wie `POPUP_HTML_CONTENT`, `WINDOW_HTML`-Konstanten, `get_inline_html`) werden vom Editor ebenfalls erkannt; die Theme-Wrapper-Plugins (Kalender, To-Do, …) behalten bewusst ihre eigene Struktur, weil sie ihr HTML zur Laufzeit dynamisch aufbauen.

## Plugins als geschlossene Systeme

Ein Plugin lebt vollständig in seiner Datei — der Launcher lädt es nur und routet:

- **UI**: `BUTTON_HTML` / `get_inline_html(mode)` (Card) bzw. `PluginWidget` (Fenster) — in der Plugin-Datei.
- **Backend-Logik**: `handle_call(method, args)` in der Plugin-Datei. Die Card ruft es per `pluginCall('methode', {…}, callback)` auf; der Launcher transportiert nur JSON, führt aber keine Plugin-Logik aus. Das Modul wird gecacht, Zustand (z. B. Zählerstände) bleibt zwischen Aufrufen erhalten. Beispiel: `scripts/Zähler.py`.
- **Systemweite Dienste** liegen getrennt in **`services.py`** (Root): die Media-Bridge (`media.*` — Windows-Medientasten + Album-Cover, per `MEDIA_BRIDGE = False` abwählbar) und die native Titelleisten-Färbung. Der Launcher importiert sie nur und registriert sie über `create_services()` auf dem WebChannel — neue Dienste dort ergänzen, sie stehen dann automatisch allen Cards zur Verfügung. Fehlt `services.py`, läuft die Toolbar mit No-op-Stubs weiter.
- **Launcher selbst**: nur Management — Listing, Tabs, Watcher, Parameter-Lesen (AST), Routing (`openPlugin`, `pluginCall`), Theme-Verteilung (`toolbar_theme`).

## Native Windows-Titelleiste (Zusatzfeature)

Die Titelleiste des Hauptfensters folgt dem Light/Dark-Toggle — über die Windows-DWM-API, ohne die Leiste zu ersetzen. Alle Fenster-Features (Snap-Layouts, an die Seite andocken, Doppelklick-Maximieren) bleiben erhalten. Dark-Mode funktioniert ab Windows 10 1809; die konkreten Farben (`TITLEBAR_COLOR_DARK/LIGHT`, `TITLEBAR_TEXT_DARK/LIGHT` oben in `Traylauncher.py`) greifen unter Windows 11 und werden unter Windows 10 still ignoriert.

## Abwärtskompatibilität

Der Dateiname-Prefix `[html]` und die Funktion `get_inline_html(mode)` funktionieren unverändert; ebenso `class PluginWidget(mode=...)` für klassische Widget-Plugins. Bestehende Plugins laufen ohne Änderung.

## Beispiele in `scripts/`

`Plugin Editor.py` (🛠️ Editor zum Erstellen neuer Plugins — Formular, Code-Generator und Live-Vorschau für Button/Window/Popup inkl. Dark/Light; speichert direkt in `scripts/`), `Musik Steuerung.py` (HTML-Button per `BUTTON_HTML` + Media-Bridge), `Timer.py` (klassisches Widget-Plugin), `Notizen Transparent.py` (transparenter Button, nur im Hauptfenster), `[HTML] Uhr Kompat.py` (altes `[html]`-Prefix-Verhalten).
