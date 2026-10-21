"""ToolbarPluginTools: Werkzeuge der Toolbar-Plugins (Timer, Kalender ...) als ToolProvider.

Plugins legen ASSISTANT_TOOLS an (Konvention: plugin_tools.py im Toolbar-Ordner). Die
Toolbar stellt sie über eine kleine HTTP-Schnittstelle bereit; Adresse und Token stehen in
den Umgebungsvariablen TOOLBAR_TOOLS_URL / TOOLBAR_TOOLS_TOKEN, die dieser Dienst erbt,
weil das 3D-Assistent-Plugin ihn aus der Toolbar heraus startet. Ohne sie (Dienst von Hand
gestartet) gibt es einfach keine Plugin-Werkzeuge.

Die Liste wird kurz zwischengespeichert und dann neu geholt - ein neues Plugin mit
ASSISTANT_TOOLS steht dem Assistenten also ohne Neustart zur Verfügung.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from backend.assistant.tools import ToolResult, ToolSpec

log = logging.getLogger(__name__)

CACHE_S = 10
TIMEOUT_S = 90


class ToolbarPluginTools:
    """Erfüllt ToolProvider (backend/assistant/tools.py)."""

    def __init__(self, url: str | None = None, token: str | None = None):
        self.url = (url or os.environ.get("TOOLBAR_TOOLS_URL") or "").rstrip("/")
        self.token = token or os.environ.get("TOOLBAR_TOOLS_TOKEN") or ""
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # localhost ohne Proxy
        self._tools: list[ToolSpec] = []
        self._fetched = 0.0

    def list_tools(self) -> list[ToolSpec]:
        if not self.url:
            return []
        if time.monotonic() - self._fetched > CACHE_S:
            try:
                data = self._request("GET", "/tools")
                self._tools = [ToolSpec(t["name"], t.get("description", ""), t.get("input_schema") or {})
                               for t in data]
            except Exception as error:  # noqa: BLE001  # Toolbar weg - keine Plugin-Werkzeuge, kein Absturz
                log.warning("Plugin-Werkzeuge der Toolbar nicht abrufbar: %s", error)
                self._tools = []
            self._fetched = time.monotonic()
        return list(self._tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        try:
            data = self._request("POST", "/call", {"name": name, "arguments": arguments})
        except Exception as error:  # noqa: BLE001
            return ToolResult(f"Toolbar nicht erreichbar: {error}", is_error=True)
        if not data.get("ok"):
            return ToolResult(str(data.get("error") or "Fehler im Plugin"), is_error=True)
        result = data.get("result")
        return ToolResult(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        request = urllib.request.Request(
            self.url + path, method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"})
        with self._opener.open(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
