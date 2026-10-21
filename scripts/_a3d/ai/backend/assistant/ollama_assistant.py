"""OllamaAssistant: Assistent mit lokalem Sprachmodell und Werkzeugen (Tool-Calling).

Ablauf von reply(message):
  1. Feste Befehle (commands.COMMANDS, z. B. "hilfe") direkt beantworten.
  2. Nachricht an den Gesprächsverlauf anhängen.
  3. model.chat(Systemanweisung + Verlauf, alle Werkzeuge)
  4. Will das Modell Werkzeuge nutzen, ruft der Assistent sie über den ToolProvider
     auf (eigene Integrationen oder MCP-Server) und hängt jedes Ergebnis als
     "tool"-Nachricht an. Weiter bei 3 - höchstens max_tool_rounds-mal.
  5. Sonst ist der Text des Modells die Antwort. Wurden Werkzeuge genutzt,
     zeigt die Ansicht oben eine Tabelle mit Aufrufen und Ergebnissen. Dateien,
     die Werkzeuge mitliefern (z. B. Mail-Anhänge), hängen an der Antwort.
"""
from __future__ import annotations

import datetime
import json
import logging
import re
from collections.abc import Callable
from dataclasses import replace

from backend.assistant.base import AssistantReply
from backend.assistant.commands import COMMANDS
from backend.assistant.llm import ChatMessage, ToolCall
from backend.assistant.ollama import OllamaError, OllamaModel
from backend.assistant.tools import Attachment, ToolProvider, ToolResult, ToolSpec
from backend.preferences import PreferenceStore
from backend.views import TemplateView

log = logging.getLogger(__name__)

MODEL_PREFERENCE = "ollama_model"
MAX_TOOL_RESULT_CHARS = 8000   # schützt das Kontextfenster kleiner Modelle

# Texte der Systemanweisung je Sprache (config.LANGUAGE)
BASE_INSTRUCTIONS = {
    "de": ("Du bist Miku, eine persönliche Assistentin auf dem Windows-PC des Nutzers. Du erscheinst als "
           "animierte 3D-Figur, und alles, was du schreibst, wird laut vorgelesen. "
           "Antworte immer auf Deutsch, kurz und freundlich, in ganzen Sätzen ohne Markdown, Listenzeichen "
           "oder Emojis. "
           "Nutze Werkzeuge nur, wenn du sie für die Antwort brauchst, und erfinde keine Ergebnisse. "
           "Brauchst du ein Werkzeug, ruf es sofort auf, statt es nur anzukündigen. "
           "Sollst du etwas recherchieren, suchen oder nachsehen, rufe dafür wirklich ein Werkzeug auf "
           "(z. B. web_search). Behaupte nie, du hättest gesucht oder ein Werkzeug benutzt, wenn du es "
           "nicht aufgerufen hast. "
           "Etwas am PC tun (z. B. einen Timer stellen oder einen Termin eintragen) kannst du nur mit einem "
           "Werkzeugaufruf. Sag nie, dass du es tust oder getan hast, ohne das Werkzeug aufgerufen zu haben. "
           "Fehlt dir eine Angabe, frag kurz nach."),
    "en": ("You are Miku, a personal assistant on the user's Windows PC. You appear as an animated 3D "
           "character, and everything you write is read aloud. "
           "Always answer in English, briefly and kindly, in full sentences without Markdown, bullet "
           "points or emojis. Even if tool results are in another language, answer in English. "
           "Only use tools when you need them for the answer, and never make up results. "
           "When you need a tool, call it right away instead of announcing that you will. "
           "If you are asked to research, search or look something up, actually call a tool for it "
           "(e.g. web_search). Never claim that you searched or used a tool if you did not call it. "
           "You can only do things on the PC (e.g. set a timer or add an appointment) by calling a tool. "
           "Never say that you are doing or have done it without having called the tool. "
           "If information is missing, ask a short question."),
}
_NOW = {
    "de": lambda now: f"Jetzt ist {_WEEKDAYS_DE[now.weekday()]}, der {now:%d.%m.%Y}, {now:%H:%M} Uhr.",
    "en": lambda now: f"It is now {now:%A, %B} {now.day}, {now:%Y}, {now:%H:%M}.",
}
# Absicherung, wenn eine Runde ohne Werkzeug endet (kleine Modelle sagen oft "Ich stelle den Timer",
# ohne ihn aufzurufen): erst unabhängig einschätzen lassen, ob die Bitte ein Werkzeug braucht - ohne den
# Entwurf, sonst hält das Modell die Sache für erledigt -, dann den Aufruf ohne Entwurf neu anfordern.
# Beides intern, deshalb nur Englisch. Gemessen: Einschätzung 55/56 richtig, Neuversuch 8/8.
_NEEDS_TOOL = ("Tools:\n{tools}\n\nUser message: {message!r}\n\nTo fulfil this message, must one of these "
               "tools be called now (to do something on the PC or to get current information)? "
               "Answer only YES or NO.")
_CALL_NOW_ATTEMPTS = 2   # Neuversuch einzeln gemessen 8/8, im Ablauf 3/5 - deshalb zweimal
_CALL_FAILED = {         # auch der Neuversuch ohne Aufruf: lieber ehrlich als ein erfundener Timer
    "de": "Das hat gerade nicht geklappt. Sag es bitte noch einmal.",
    "en": "Sorry, that didn't work just now. Please say it again.",
}
_CALL_NOW = ("(System) The user's last message needs one of your tools. Call the matching tool now with the "
             "right arguments. Do not answer in text first.")
_KNOWN_ABOUT_USER = {"de": "Bekanntes über den Nutzer: ", "en": "Known about the user: "}

_WEEKDAYS_DE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


class OllamaAssistant:
    """Erfüllt Assistant und ModelSelection (base.py)."""

    def __init__(self, model: OllamaModel, tools: ToolProvider, preferences: PreferenceStore,
                 instructions: str = "", max_tool_rounds: int = 5, max_history: int = 30,
                 language: str = "de", check_missed_calls: bool = True,
                 clock: Callable[[], datetime.datetime] = datetime.datetime.now):
        self.model = model
        self.tools = tools
        self.preferences = preferences
        self.instructions = instructions
        self.max_tool_rounds = max_tool_rounds
        self.max_history = max_history
        self.clock = clock
        self.language = language if language in BASE_INSTRUCTIONS else "en"
        self.check_missed_calls = check_missed_calls
        self.history: list[ChatMessage] = []

    # --- Assistant -------------------------------------------------------------------
    def reply(self, message: str) -> AssistantReply:
        command = message.strip().lower()
        if command == "neu":
            self.history.clear()
        if command in COMMANDS:
            return COMMANDS[command][1]()

        try:
            if not self._ensure_model():
                return AssistantReply("In Ollama ist noch kein Modell installiert. "
                                      "Lade eins herunter, z. B. mit: ollama pull llama3.2")
        except OllamaError as error:
            return AssistantReply(str(error))

        start = len(self.history)
        self.history.append(ChatMessage("user", message))
        tool_log: list[tuple[ToolCall, ToolResult]] = []
        try:
            text = self._run(tool_log)
        except OllamaError as error:
            del self.history[start:]   # misslungene Runde nicht im Verlauf behalten
            return AssistantReply(f"Fehler von Ollama ({self.model.name}): {error}")
        # Überlegungen braucht das Modell nur innerhalb der Runde (bei Werkzeugen) - danach weg, spart Kontext
        self.history[start:] = [replace(m, thinking="") if m.thinking else m for m in self.history[start:]]
        self._trim_history()
        return AssistantReply(text, _tool_view(tool_log) if tool_log else None, _attachments(tool_log),
                              _page_candidates(tool_log))

    def _run(self, tool_log: list[tuple[ToolCall, ToolResult]]) -> str:
        tools = self.tools.list_tools()
        checked = False
        for round_ in range(self.max_tool_rounds + 1):
            # In der letzten Runde keine Werkzeuge mehr anbieten: Das Modell muss antworten.
            offered = tools if round_ < self.max_tool_rounds else []
            response = self.model.chat([self._system_message(), *self.history], offered)
            message = response.message
            calls = message.tool_calls or calls_written_as_text(message.content, offered)
            if calls and not message.tool_calls:
                # Kleine Modelle schreiben den Aufruf manchmal als Text ("[web_search query=...]")
                # statt ihn auszulösen - dann als echten Aufruf behandeln.
                log.info("Werkzeugaufruf als Text erkannt: %s", calls)
                names = {call.name for call in calls}
                content = _TEXT_CALL.sub(lambda m: "" if m.group(1) in names else m.group(0), message.content)
                message = replace(message, content=content.strip(), tool_calls=calls)
            self.history.append(message)
            if not calls and offered and not tool_log and not checked and self.check_missed_calls:
                # Ohne Werkzeug geantwortet: Braucht die Bitte eins, den Aufruf nachholen
                # (der Entwurf fällt weg, die Antwort entsteht danach mit dem Ergebnis neu).
                checked = True
                missed = self._missed_calls(offered)
                if missed is not None:
                    self.history[-1] = message = missed
                    calls = missed.tool_calls
            if not calls:
                text = message.content.strip() or self._answer_without_thinking()
                return text or "(Das Modell hat keine Antwort geliefert.)"
            for call in calls:
                result = self._call_tool(call)
                tool_log.append((call, result))
                content = ("Fehler: " if result.is_error else "") + result.content[:MAX_TOOL_RESULT_CHARS]
                self.history.append(ChatMessage("tool", content, tool_name=call.name))
        return "Ich habe zu viele Werkzeuge nacheinander aufgerufen und breche ab. Versuch es bitte genauer."

    def _missed_calls(self, offered: list[ToolSpec]) -> ChatMessage | None:
        """Antwort ohne Werkzeug: Braucht die letzte Bitte eins? Dann den Aufruf ohne den Entwurf
        neu anfordern. Ergebnis (ersetzt den Entwurf): Nachricht mit den Aufrufen, ohne Aufruf eine
        ehrliche Fehlermeldung - oder None, wenn kein Werkzeug nötig ist."""
        message = next((m.content for m in reversed(self.history) if m.role == "user"), "")
        tool_list = "\n".join(f"- {spec.name}: {spec.description}" for spec in offered)
        try:
            verdict = self._chat_without_thinking(
                [ChatMessage("user", _NEEDS_TOOL.format(tools=tool_list, message=message))], [])
            if not verdict.content.strip().upper().startswith("YES"):
                return None
            for attempt in range(1, _CALL_NOW_ATTEMPTS + 1):
                retry = self._chat_without_thinking(
                    [self._system_message(), *self.history[:-1], ChatMessage("user", _CALL_NOW)], offered)
                calls = retry.tool_calls or calls_written_as_text(retry.content, offered)
                if calls:
                    log.info("Werkzeugaufruf fehlte - nachgeholt (Versuch %d): %s", attempt,
                             [call.name for call in calls])
                    return ChatMessage("assistant", "", tool_calls=tuple(calls))
        except OllamaError as error:
            log.warning("Prüfung auf vergessenen Werkzeugaufruf fehlgeschlagen: %s", error)
            return None
        log.info("Bitte braucht laut Prüfung ein Werkzeug, aber kein Aufruf kam - Antwort ersetzt")
        return ChatMessage("assistant", _CALL_FAILED[self.language])

    def _chat_without_thinking(self, messages: list[ChatMessage], tools: list[ToolSpec]) -> ChatMessage:
        thinking = getattr(self.model, "think", None)
        if thinking:
            self.model.think = False
        try:
            return self.model.chat(messages, tools).message
        finally:
            if thinking:
                self.model.think = thinking

    def _answer_without_thinking(self) -> str:
        """Denkmodus: Manchmal steht die Antwort nur in den Überlegungen und der Text bleibt leer.
        Dann einmal ohne Denken und ohne Werkzeuge nachfragen (ersetzt die leere Antwort)."""
        if not getattr(self.model, "think", None):
            return ""
        log.info("Leere Antwort im Denkmodus - frage ohne Denken nach")
        self.history.pop()
        self.model.think = False
        try:
            response = self.model.chat([self._system_message(), *self.history], [])
        finally:
            self.model.think = True
        self.history.append(response.message)
        return response.message.content.strip()

    def _call_tool(self, call: ToolCall) -> ToolResult:
        log.info("Werkzeug %s(%s)", call.name, call.arguments)
        try:
            return self.tools.call_tool(call.name, call.arguments)
        except Exception as error:   # z. B. erfundener Werkzeugname - das Modell soll es korrigieren
            log.warning("Werkzeug %s fehlgeschlagen: %s", call.name, error)
            return ToolResult(str(error), is_error=True)

    def _system_message(self) -> ChatMessage:
        now = self.clock()
        parts = [BASE_INSTRUCTIONS[self.language], _NOW[self.language](now)]
        context = {k: v for k, v in self.preferences.all().items() if k != MODEL_PREFERENCE}
        if context:
            parts.append(_KNOWN_ABOUT_USER[self.language] + json.dumps(context, ensure_ascii=False))
        if self.instructions:
            parts.append(self.instructions)
        return ChatMessage("system", "\n\n".join(parts))

    def _trim_history(self) -> None:
        # Vorne kürzen, aber immer an einer Nutzernachricht beginnen
        # (keine "tool"-Nachricht ohne den zugehörigen Aufruf).
        while len(self.history) > self.max_history:
            del self.history[0]
            while self.history and self.history[0].role != "user":
                del self.history[0]

    # --- ModelSelection ---------------------------------------------------------------
    def available_models(self) -> list[dict]:
        return [{"name": info.name, "tools": info.supports_tools} for info in self.model.available_models()]

    def current_model(self) -> str:
        self._ensure_model()
        return self.model.name

    def select_model(self, name: str) -> None:
        if name not in self.model.installed():
            raise ValueError(f"Modell {name!r} ist in Ollama nicht installiert")
        self.model.name = name
        self.preferences.set(MODEL_PREFERENCE, name)

    def _ensure_model(self) -> bool:
        """Modell festlegen, falls noch keins gewählt ist: zuletzt gewähltes, sonst erstes installiertes."""
        if self.model.name:
            return True
        installed = self.model.installed()
        saved = self.preferences.get(MODEL_PREFERENCE)
        self.model.name = saved if saved in installed else (installed[0] if installed else "")
        return bool(self.model.name)


# --- Werkzeugaufrufe, die das Modell als Text geschrieben hat ---------------------------
# [name ...] oder [name(...)] - nur Namen von angebotenen Werkzeugen zählen, sonst bleibt es
# Text (z. B. die Aktionen der Figur wie [gesture.wave]).
_TEXT_CALL = re.compile(r"\[\s*([A-Za-z_][\w-]*)\s*(?:\((.*?)\)\s*|([^\[\]]*))\]", re.S)
_KEY_VALUE = re.compile(r"""(\w+)\s*[=:]\s*(?:"([^"]*)"|'([^']*)'|([^\s,]+))""")


def calls_written_as_text(text: str, tools: list[ToolSpec]) -> tuple[ToolCall, ...]:
    specs = {spec.name: spec for spec in tools}
    calls = []
    for match in _TEXT_CALL.finditer(text or ""):
        spec = specs.get(match.group(1))
        if spec is None:
            continue
        arguments = _text_arguments(match.group(2) if match.group(2) is not None else match.group(3), spec)
        if arguments is not None:
            calls.append(ToolCall(spec.name, arguments))
    return tuple(calls)


def _text_arguments(raw: str, spec: ToolSpec) -> dict | None:
    """Argumente aus 'query="x" max_results=3', '{"query": "x"}' oder nur '"x"' (-> erster Pflichtparameter)."""
    raw = (raw or "").strip()
    properties = spec.input_schema.get("properties", {})
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except ValueError:
            pass
    arguments = {}
    for match in _KEY_VALUE.finditer(raw):
        if match.group(1) in properties:
            value = next(group for group in match.groups()[1:] if group is not None)
            arguments[match.group(1)] = _coerce(value, properties[match.group(1)])
    if arguments:
        return arguments
    required = spec.input_schema.get("required") or list(properties)
    value = raw.lstrip(":= ").strip().strip("\"'")
    if not required:
        return {}
    return {required[0]: _coerce(value, properties.get(required[0], {}))} if value else None


def _coerce(value: str, schema: dict):
    kind = schema.get("type")
    try:
        if kind == "integer":
            return int(value)
        if kind == "number":
            return float(value)
    except ValueError:
        return value
    if kind == "boolean":
        return value.lower() in ("true", "1", "yes", "ja")
    return value


def _tool_view(tool_log: list[tuple[ToolCall, ToolResult]]) -> TemplateView:
    """Bestätigung fürs Board (templates/tool_calls.html.j2): was wurde mit welchen Angaben aufgerufen."""
    calls = [{"name": call.name, "arguments": dict(call.arguments), "result": _shorten(result.content),
              "error": result.is_error} for call, result in tool_log]
    rows = [[c["name"], json.dumps(c["arguments"], ensure_ascii=False),
             ("Fehler: " if c["error"] else "") + c["result"]] for c in calls]
    return TemplateView("tool_calls", {"title": "Ausgeführt", "calls": calls,
                                       "columns": ["Werkzeug", "Argumente", "Ergebnis"], "rows": rows})


_URL = re.compile(r"https?://[^\s<>\"']+")
MAX_PAGE_CANDIDATES = 6


def _page_candidates(tool_log: list[tuple[ToolCall, ToolResult]]) -> tuple[str, ...]:
    """Seiten fürs Board, beste zuerst: gelesene (web_fetch, neueste zuerst), dann die Treffer der
    Suchen (neueste Suche zuerst, in Trefferreihenfolge). Das Board zeigt die erste, die sich
    einbetten lässt (presenter.py) - viele Seiten verbieten es."""
    urls: list[str] = []
    for call, result in reversed(tool_log):
        if call.name == "web_fetch" and not result.is_error and isinstance(call.arguments.get("url"), str):
            urls.append(call.arguments["url"])
    for call, result in reversed(tool_log):
        if call.name == "web_search" and not result.is_error:
            urls.extend(match.group(0).rstrip(".,);") for match in _URL.finditer(result.content))
    return tuple(dict.fromkeys(urls))[:MAX_PAGE_CANDIDATES]


def _attachments(tool_log: list[tuple[ToolCall, ToolResult]]) -> tuple[Attachment, ...]:
    """Alle mitgelieferten Dateien der Runde, jede nur einmal (z. B. read_email + read_attachment)."""
    unique = {attachment.uri: attachment for _, result in tool_log for attachment in result.attachments}
    return tuple(unique.values())


def _shorten(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[:limit] + " …"
