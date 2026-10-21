"""Bereitet Antworten des Assistenten für den Viewer auf:
{"text": str, "view": {"template", "data", "html"} | {"html"} | None, "attachments": [{"name", "uri"}]}
"html" ist die fertig gerenderte Ansicht (backend/rendering.py, Jinja2-Vorlagen in templates/) -
der Viewer zeigt sie im Board-iframe.
"page": {"url", "title"} - die beste Webseite der Runde, die sich einbetten lässt (gelesene vor
gefundenen; mcp_servers/web.py: embeddable) - der Viewer zeigt sie im Board (board/web.html, Sandbox)
und ersetzt damit, was dort lag.

Dasselbe Format für beide Wege (wie presenter.py im PDA):
  - Antwort auf eine Chat-Nachricht   (assistant_server.py, POST /chat)
  - Nachricht, die der Dienst von sich aus schickt  (push - z. B. Morning-Briefing)

push öffnet das Popup der Toolbar mit der 3D-Figur, die den Text sagt und die
[aktionen] darin ausführt. Der Dienst kennt die Toolbar nicht direkt: Das Plugin
startet ihn mit A3D_PUSH_URL (POST /push an seinen Asset-Server), von dort geht
es über services.push an PluginWidget.on_push.

    from backend.assistant import AssistantReply
    from backend.presenter import push
    push(AssistantReply("[geste.winken] Guten Morgen! Heute hast du drei Termine."))
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any

from backend import config
from backend.assistant import AssistantReply
from backend.rendering import ViewRenderer
from backend.views import HtmlView, TemplateView

log = logging.getLogger(__name__)

PUSH_TIMEOUT_S = 10
PAGE_CHECK_BUDGET_S = 6          # so lange insgesamt auf die Einbett-Prüfung der Seiten warten
_renderer = ViewRenderer(config.TEMPLATE_DIR)


def present(reply: AssistantReply) -> dict[str, Any]:
    return {"text": reply.text, "view": _view_to_json(reply.view),
            "attachments": [{"name": a.name, "uri": a.uri} for a in reply.attachments],
            "page": _page_to_json(reply.pages)}


def _page_to_json(urls: tuple[str, ...]) -> dict | None:
    """Erste Seite (in Reihenfolge), die sich einbetten lässt - alle parallel geprüft, höchstens
    PAGE_CHECK_BUDGET_S lang (eine langsame Seite hält die Antwort nicht auf)."""
    if not urls:
        return None
    from mcp_servers import web            # liegt im Ordner des Dienstes (Arbeitsverzeichnis)
    pool = ThreadPoolExecutor(max_workers=len(urls), thread_name_prefix="embed-check")
    futures = [pool.submit(web.embeddable, url) for url in urls]
    deadline = time.monotonic() + PAGE_CHECK_BUDGET_S
    try:
        for future in futures:
            try:
                checked = future.result(timeout=max(0.0, deadline - time.monotonic()))
            except FutureTimeout:
                continue
            except Exception:  # noqa: BLE001  # Prüfung ist ein Extra - nie die Antwort scheitern lassen
                continue
            if checked is not None:
                return {"url": checked[0], "title": checked[1]}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    log.info("Keine der %d Seiten lässt sich einbetten (oder antwortet) - Board bleibt", len(urls))
    return None


def push(reply: AssistantReply) -> bool:
    """Nachricht des Assistenten ohne vorherige Nutzereingabe: Popup öffnen, die Figur spricht.
    False, wenn der Dienst nicht vom Plugin gestartet wurde oder die Toolbar nicht erreichbar ist."""
    url = os.environ.get("A3D_PUSH_URL")
    if not url:
        log.warning("push ohne A3D_PUSH_URL (Dienst nicht vom Plugin gestartet): %s", reply.text)
        return False
    request = urllib.request.Request(url, json.dumps(present(reply)).encode("utf-8"),
                                     {"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # localhost ohne Proxy
    try:
        with opener.open(request, timeout=PUSH_TIMEOUT_S) as response:
            return bool(json.loads(response.read().decode("utf-8")).get("ok"))
    except Exception as error:  # noqa: BLE001  # Toolbar weg o. Ä. - nur protokollieren
        log.warning("push fehlgeschlagen (%s): %s", error, reply.text)
        return False


def _view_to_json(view) -> dict | None:
    if isinstance(view, TemplateView):
        result = {"template": view.template, "data": dict(view.data)}
        try:
            result["html"] = _renderer.render(view)
        except Exception as error:  # noqa: BLE001  # Ansicht fehlt dann - die Antwort selbst nicht
            log.warning("Ansicht %r nicht gerendert: %s", view.template, error)
        return result
    if isinstance(view, HtmlView):
        return {"html": view.html}
    return None
