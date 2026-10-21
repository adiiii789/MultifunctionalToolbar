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
- **Launcher selbst**: nur Management — Listing, Tabs, Watcher, Parameter-Lesen (AST), Routing (`openPlugin`, `pluginCall`, `push`), Theme-Verteilung (`toolbar_theme`).

## Push: ein Plugin öffnet das Popup selbst

Eine Komponente kann das Popup von sich aus öffnen, z. B. für eine Erinnerung oder ein Briefing:

```python
import services
services.push("3D Assistent.py", "Dein Termin beginnt in 10 Minuten.")
```

Der Launcher öffnet das Popup am Tray-Icon, lädt das Plugin (ein schon offenes bleibt samt Zustand)
und übergibt die Daten an **`PluginWidget.on_push(data)`**. Ist das Plugin im sichtbaren
Hauptfenster schon als Tab offen, kommt stattdessen dieser Tab nach vorne. Der Pfad ist absolut
oder relativ zu `scripts/`, `data` ein beliebiges Python-Objekt. `push` darf aus jedem Thread
aufgerufen werden (Timer, HTTP-Server im Plugin …) und läuft dann im Qt-Hauptthread. Ohne
laufende Toolbar gibt es `False` zurück.

## KI-Assistent steuert Plugins (`ASSISTANT_TOOLS`)

Der 3D-Assistent kann Plugins bedienen („Stell einen Timer auf 10 Minuten“, „Trag morgen um 9
Zahnarzt ein“). Ein Plugin bietet dafür Werkzeuge an – wie die übrigen Parameter oben in der Datei,
per AST gelesen, ein neues Plugin ist ohne Neustart dabei:

```python
ASSISTANT_TOOLS = {
    "timer_start": {
        "description": "Starts a countdown timer.",           # fürs Sprachmodell, am besten Englisch
        "parameters": {"minutes": {"type": "number", "description": "Duration in minutes"}},
        "required": ["minutes"],
        "window": True,                                       # optional, siehe unten
        "show": True,                                         # optional: ohne Board als Tab zeigen
        "board": False,                                       # optional: nicht aufs Board
    },
}

def assistant_call(tool, args): ...                 # ohne "window": Modul-Ebene, Fenster nicht nötig

class PluginWidget(QMainWindow):
    def assistant_call(self, tool, args): ...       # mit "window": True - der Launcher öffnet das Fenster
    def on_assistant_change(self, tool, args, result): ...   # optional: offenes Fenster aktualisieren
```

- **Ohne `window`** (z. B. Kalender: Termine in .ics-Dateien) läuft `assistant_call` auf Modul-Ebene;
  ist das Plugin offen, ruft der Launcher danach `on_assistant_change` auf, damit es neu zeichnet.
- **Mit `"window": True`** (z. B. Timer: Zustand lebt im JavaScript des Fensters) nimmt der Launcher
  das offene Fenster oder öffnet es als Tab im Hauptfenster. Gibt `assistant_call` ein
  `concurrent.futures.Future` zurück, wartet er darauf (z. B. Antwort von `runJavaScript`).
- **Board:** Bedient der Assistent ein Plugin, erscheint es im Board des 3D-Assistenten (steht Miku
  im schmalen Popup, schaltet es dafür auf „⇔ Breit“). Das echte Plugin-Fenster liegt dabei verdeckt
  unter der 3D-Ansicht; `board/plugin.html` im Board-iframe zeigt laufend Bilder davon und schickt
  Klicks und Mausrad zurück (nach einem Klick tippt man direkt ins Plugin) - Menü und Figur bleiben
  so über dem Plugin. Dort geöffnete Plugins laufen weiter, auch wenn ✕ sie vom Board nimmt.
  `"board": False` schaltet das für ein Werkzeug ab. Die Werkzeugaufrufe stehen in der Konsole
  (`[3D Assistent JS] [Werkzeug] …`), aufs Board nur mit dem Schalter im Panel.
- **Mit `"show": True`** holt der Launcher das Plugin nach dem Aufruf als Tab im Hauptfenster nach
  vorne, damit man die Änderung sieht; `on_assistant_change` erreicht auch das frisch geöffnete
  Fenster (der Kalender springt so zur Woche des neuen Termins und hebt ihn hervor). Nur für
  Änderungen, nicht für Abfragen.
- Rückgabe: Text oder JSON-taugliches Objekt; Fehler als Exception mit verständlicher Meldung.
- Alles läuft im Qt-Hauptthread. Die Schnittstelle (`plugin_tools.py`) hört nur auf 127.0.0.1 und
  braucht ein zufälliges Token, das nur Prozesse kennen, die die Toolbar startet (der KI-Dienst).
- `services.say(text)` lässt den Assistenten etwas ansagen, ohne dass das Plugin ihn kennt – der
  Timer nutzt das, wenn ein vom Assistenten gestellter Countdown abläuft.
- **Plugin-Liste:** Das eingebaute Werkzeug `toolbar_list_plugins` listet alle Plugins (wie der
  Explorer, bei jedem Aufruf neu) mit Beschreibung und ihren Werkzeugen. Die Beschreibung steht als
  `DESCRIPTION = "Ein Satz, was das Plugin macht."` oben in der Plugin-Datei (auch im Plugin-Editor);
  fehlt sie, nimmt es den Docstring oder die Beschreibungen der `ASSISTANT_TOOLS`.
- Eingebaut: **Timer** (`timer_start`, `timer_status`, `timer_cancel`), **Kalender**
  (`calendar_list_events`, `calendar_add_event` – Löschen bewusst nicht), **Dateisuche** (`file_search`),
  **Bildersuche** (`image_search`), **GIF-Suche** (`gif_search`).
  Vorlage: `scripts/Vorlage.py`.
- **Dateisuche** (`scripts/work tools/Dateisuche.py`): sucht nur im Dateinamen, nur in den Benutzerordnern
  (Desktop, Dokumente, Downloads, Bilder, Musik, Videos, OneDrive), ohne versteckte Ordner, AppData und
  Dateien mit Zugangsdaten (`EXCLUDED_DIRS`/`EXCLUDED_FILES`). Das Modell bekommt nur Anzahl und
  Dateinamen - keine Pfade, keine Inhalte (Schutz vor Prompt Injection über Webseiten). Ein Klick öffnet
  nur `explorer /select,<Pfad>` (Ordner auf, Datei markiert, nichts wird gestartet), und nur für Pfade aus
  der aktuellen Trefferliste.
- **Bildersuche** (`scripts/work tools/Bildersuche.py`, braucht `pip install ddgs` in der Toolbar-venv):
  Bilder aus dem Internet (DuckDuckGo, SafeSearch moderat), ein Klick kopiert das Bild in Originalgröße
  in die Zwischenablage (nur Pixel). Vorschaubilder über den Bild-Proxy der Suchmaschine; den Server des
  Originals kontaktiert die Toolbar erst beim Kopieren. Geladen wird nur von öffentlichen Adressen (auch
  nach Weiterleitungen), nur JPEG/PNG/GIF/WebP mit Größenlimit, kein SVG. Das Modell bekommt nur die
  Anzahl (Titel fremder Seiten könnten Anweisungen enthalten).
- **GIF-Suche** (`scripts/work tools/Gifsuche.py`): animierte GIFs über KLIPY. Braucht einen eigenen,
  kostenlosen API-Schlüssel (partner.klipy.com → API Keys; Testmodus: 100 Anfragen/Stunde), der im
  Fenster eingegeben und lokal in `gifsuche_config.json` gespeichert wird (in `.gitignore`). Ein Klick
  kopiert die GIF-Datei (bleibt beim Einfügen animiert) plus das erste Bild; die Datei liegt in
  `%TEMP%\Toolbar-GIFs` und wird nach einem Tag gelöscht. Laden/Prüfen wie die Bildersuche über
  `scripts/work tools/_web_images.py`; das Modell bekommt nur die Anzahl.
- **Webseiten im Board:** Liest Miku eine Seite (`web_fetch`, sonst erster Treffer von `web_search`),
  zeigt das Board sie (`viewer/board/web.html`) - nur wenn sie öffentlich ist und Einbetten erlaubt
  (`X-Frame-Options`/`frame-ancestors`, geprüft im KI-Dienst: `mcp_servers/web.py` `embeddable`).
  Der Viewer ist Chromium 83 mit bekannten Lücken: Die Seite läuft in einer Sandbox (eigener leerer
  Ursprung, keine Pop-ups/Downloads/Umleitung) und standardmäßig ohne Skripte. Panel-Schalter:
  „Webseiten aufs Board“ (an), „Webseiten: Skripte erlauben ⚠“ (aus).
- **Zugang:** Der Asset-Server des 3D-Assistenten und sein KI-Dienst nehmen Anfragen nur mit einem
  zufälligen Token an (neu bei jedem Start; Viewer: `viewer.html?k=…`, `js/token.js`). Sonst könnte jedes
  Programm auf dem PC - oder eine Webseite, die den Port errät - Miku Aufträge geben.

## Native Windows-Titelleiste (Zusatzfeature)

Die Titelleiste des Hauptfensters folgt dem Light/Dark-Toggle — über die Windows-DWM-API, ohne die Leiste zu ersetzen. Alle Fenster-Features (Snap-Layouts, an die Seite andocken, Doppelklick-Maximieren) bleiben erhalten. Dark-Mode funktioniert ab Windows 10 1809; die konkreten Farben (`TITLEBAR_COLOR_DARK/LIGHT`, `TITLEBAR_TEXT_DARK/LIGHT` oben in `Traylauncher.py`) greifen unter Windows 11 und werden unter Windows 10 still ignoriert.

## Abwärtskompatibilität

Der Dateiname-Prefix `[html]` und die Funktion `get_inline_html(mode)` funktionieren unverändert; ebenso `class PluginWidget(mode=...)` für klassische Widget-Plugins. Bestehende Plugins laufen ohne Änderung.

## Beispiele in `scripts/`

`Plugin Editor.py` (🛠️ Editor zum Erstellen neuer Plugins — Formular, Code-Generator und Live-Vorschau für Button/Window/Popup inkl. Dark/Light; speichert direkt in `scripts/`), `Musik Steuerung.py` (HTML-Button per `BUTTON_HTML` + Media-Bridge), `Timer.py` (klassisches Widget-Plugin), `Notizen Transparent.py` (transparenter Button, nur im Hauptfenster), `[HTML] Uhr Kompat.py` (altes `[html]`-Prefix-Verhalten).
