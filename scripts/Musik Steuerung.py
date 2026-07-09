# =============================================================================
# Demo: Neues Parametersystem — der Listen-Button ist selbst eine HTML-Card.
# HTML_BUTTON = True aktiviert das HTML-Rendering, BUTTON_HTML liefert das HTML.
# Der ⏱-Button zeigt: Cards können per openPlugin('Name.py') andere Plugins
# öffnen (relativ zum eigenen Ordner; openPlugin() ohne Argument = eigene Datei).
# =============================================================================
HTML_BUTTON = True
BUTTON_HEIGHT = 72
OPACITY = 0.9
NAME = "Musik"
ICON = "🎵"
MEDIA_BRIDGE = True
PINNED = 1  # ganz oben in der Liste (True = anpinnen, Zahl = Reihenfolge)

BUTTON_HTML = """
<div style="display:flex;align-items:center;justify-content:center;height:100%;gap:10px;
            font-family:system-ui;color:inherit;">
  <button onclick="media.prev()"      style="font-size:16px;padding:4px 10px;border-radius:8px;border:none;cursor:pointer;">⏮</button>
  <button onclick="media.playPause()" style="font-size:16px;padding:4px 14px;border-radius:8px;border:none;cursor:pointer;">⏯</button>
  <button onclick="media.next()"      style="font-size:16px;padding:4px 10px;border-radius:8px;border:none;cursor:pointer;">⏭</button>
  <button onclick="media.mute()"      style="font-size:16px;padding:4px 10px;border-radius:8px;border:none;cursor:pointer;">🔇</button>
  <button onclick="openPlugin('Timer.py')" title="Timer-Plugin öffnen"
          style="font-size:16px;padding:4px 10px;border-radius:8px;border:none;cursor:pointer;">⏱</button>
</div>
"""
