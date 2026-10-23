"""Backend des KI-Dienstes für den 3D-Assistenten - übernommen aus dem PDA (SWE_II_PDA).

  config.py        Einstellungen (Ollama, Sprache, Pfade)
  preferences.py   Kontextwissen und Präferenzen des Nutzers (z. B. gewähltes Modell)
  speech.py        Spracheingabe (faster-whisper) und -ausgabe (Piper, Windows-Stimme)
  views.py         Ansicht-Anfragen (Tabellen, die der Viewer aufs Board legt)
  rendering.py     Ansicht -> HTML (Jinja2-Vorlagen in templates/)
  presenter.py     Antwort -> JSON für den Viewer; push: Nachricht ohne Nutzereingabe
  assistant/       der Assistent: Sprachmodelle (Ollama, Claude), Tool-Calling, feste Befehle, Fähigkeiten
  integrations/    MCP-Client, Werkzeuge der Toolbar-Plugins und spätere Integrationen als ToolProvider

Nicht übernommen: Qt-Popup und Bridge - die Oberfläche ist der 3D-Viewer, er spricht über
assistant_server.py (HTTP, nur localhost) mit diesem Backend.
"""
