"""ClaudeCodeAgent: Claude über das eigene Abo (Pro/Max), mit dem Claude Agent SDK.

Das SDK startet Claude Code (claude.exe, im Paket enthalten) im Hintergrund. Angemeldet ist es wie
Claude Code selbst (einmal "claude" im Terminal starten und einloggen), ohne API-Schlüssel. Die
Nutzung zählt gegen die Limits des Abos, geteilt mit Claude Code - und ist nur für die eigene
Nutzung erlaubt, nicht in Programmen, die andere mit ihrem Abo nutzen.

Anders als OllamaModel und ClaudeModel führt Claude Code die Werkzeug-Schleife selbst. Unsere
Werkzeuge (MCP-Server, Toolbar-Plugins, Fähigkeiten) bekommt es als MCP-Server im selben Prozess,
jeder Aufruf geht an call_tool des Assistenten. Deshalb respond() statt chat() (runs_tools,
siehe ollama_assistant.py). Die eingebauten Werkzeuge von Claude Code (Dateien, Bash ...) sind aus.

Die Sitzung bleibt offen (ClaudeSDKClient): schneller, und Claude Code kennt das Gespräch selbst.
Neu begonnen wird, wenn sich Modell, Aufwand, Systemanweisung oder Werkzeuge ändern oder der
Verlauf nicht mehr zur Sitzung passt ("neu", zwischendurch ein anderes Modell, ein Fehler) -
dann geht der bisherige Verlauf als Text mit der ersten Nachricht.
"""
from __future__ import annotations

import asyncio
import atexit
import concurrent.futures
import logging
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ClaudeSDKError,
                              ResultMessage, TextBlock, create_sdk_mcp_server, tool)

from backend.assistant.llm import ChatMessage, ModelError, ModelInfo, ModelResponse, ToolCall
from backend.assistant.tools import ToolResult, ToolSpec

log = logging.getLogger(__name__)

PREFIX = "abo/"        # Modellnamen in der Auswahl, z. B. "abo/haiku"
SERVER = "miku"        # unsere Werkzeuge heißen in Claude Code mcp__miku__<name>
_EFFORT = {False: "low", True: "high"}   # think -> effort; None = Standard des Modells
_ERRORS = {
    "authentication_failed": "Claude Code ist nicht angemeldet. Einmal 'claude' im Terminal starten und einloggen.",
    "rate_limit": "Das Limit des Claude-Abos ist gerade erreicht. Später noch einmal versuchen.",
    "billing_error": "Problem mit dem Claude-Abo (Abrechnung).",
}


class ClaudeCodeAgent:
    """Anbieter für ModelRouter mit eigener Werkzeug-Schleife."""

    runs_tools = True
    reliable_tool_calls = True

    def __init__(self, models: Sequence[str], max_turns: int, timeout: float, cwd: Path):
        self.models = list(models)   # Aliasse von Claude Code, z. B. "haiku"
        self.max_turns = max_turns
        self.timeout = timeout
        self.cwd = cwd
        self.name = ""
        self.think: bool | None = None
        self._client: ClaudeSDKClient | None = None
        self._session_key: tuple | None = None
        self._last: ChatMessage | None = None   # letzte Antwort der Sitzung - steht sie im Verlauf, geht es weiter
        self._call_tool: Callable[[ToolCall], ToolResult] | None = None
        # Das SDK ist asynchron, der Assistent nicht: eigene Ereignisschleife in einem Hintergrund-Thread
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, name="claude-code", daemon=True).start()
        atexit.register(self.close)

    def handles(self, name: str) -> bool:
        return name.startswith(PREFIX)

    def installed(self) -> list[str]:
        return [PREFIX + model for model in self.models]

    def available_models(self) -> list[ModelInfo]:
        return [ModelInfo(name, True) for name in self.installed()]

    def chat(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec] = ()) -> ModelResponse:
        raise ModelError("Das Claude-Abo beantwortet nur ganze Nachrichten (respond)")

    def respond(self, system: str, history: Sequence[ChatMessage], note: str, tools: Sequence[ToolSpec],
                call_tool: Callable[[ToolCall], ToolResult]) -> ChatMessage:
        """Antwort auf history[-1] (Nutzernachricht). note steht vor der Nachricht (z. B. die Uhrzeit)."""
        future = asyncio.run_coroutine_threadsafe(self._respond(system, history, note, tools, call_tool), self._loop)
        try:
            return future.result(self.timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            self._reset()
            raise ModelError("Claude Code hat zu lange gebraucht") from None
        except ModelError:
            self._reset()
            raise
        except ClaudeSDKError as error:
            self._reset()
            raise ModelError(f"Claude Code: {error}") from None

    async def _respond(self, system: str, history: Sequence[ChatMessage], note: str, tools: Sequence[ToolSpec],
                       call_tool: Callable[[ToolCall], ToolResult]) -> ChatMessage:
        model = self.name.removeprefix(PREFIX)
        effort = None if self.think is None else _EFFORT[bool(self.think)]
        key = (model, effort, system, tuple(spec.name for spec in tools))
        prompt = f"{note}\n\n{history[-1].content}" if note else history[-1].content
        if not (self._client and key == self._session_key and len(history) >= 2 and history[-2] is self._last):
            await self._disconnect()
            client = ClaudeSDKClient(self._options(model, effort, system, tools))
            await client.connect()
            self._client, self._session_key = client, key
            earlier = _transcript(history[:-1])
            if earlier:
                prompt = f"{earlier}\n\n{prompt}"
            log.info("Neue Claude-Code-Sitzung (%s, Aufwand %s)", model, effort or "Standard")
        self._call_tool = call_tool
        await self._client.query(prompt)
        text, error = "", ""
        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                if message.error:
                    error = _ERRORS.get(message.error, message.error)
                parts = [block.text for block in message.content if isinstance(block, TextBlock)]
                if parts:
                    text = "\n".join(parts)
            elif isinstance(message, ResultMessage):
                log.info("Claude Code %s: %d Runden, %d ms", model, message.num_turns, message.duration_ms)
                if message.is_error:
                    error = error or message.result or "; ".join(message.errors or ()) or message.subtype
                elif message.result:
                    text = message.result
        if error:
            raise ModelError(error)
        self._last = ChatMessage("assistant", text.strip())
        return self._last

    def _options(self, model: str, effort: str | None, system: str, tools: Sequence[ToolSpec]) -> ClaudeAgentOptions:
        self.cwd.mkdir(parents=True, exist_ok=True)
        return ClaudeAgentOptions(
            model=model, effort=effort, system_prompt=system,
            tools=[],                      # keine eingebauten Werkzeuge von Claude Code
            mcp_servers={SERVER: create_sdk_mcp_server(SERVER, tools=[self._sdk_tool(spec) for spec in tools])},
            allowed_tools=[f"mcp__{SERVER}__{spec.name}" for spec in tools],
            permission_mode="dontAsk",     # alles andere ablehnen statt nachzufragen (niemand sieht die Frage)
            setting_sources=[],            # keine CLAUDE.md, Einstellungen oder Skills des Nutzers
            max_turns=self.max_turns, cwd=self.cwd)

    def _sdk_tool(self, spec: ToolSpec) -> Any:
        async def handler(arguments: dict[str, Any]) -> dict[str, Any]:
            result = await asyncio.to_thread(self._call_tool, ToolCall(spec.name, dict(arguments)))
            return {"content": [{"type": "text", "text": result.content or "(leer)"}], "is_error": result.is_error}
        schema = spec.input_schema or {"type": "object", "properties": {}}
        return tool(spec.name, spec.description, {"type": "object", **schema})(handler)

    def _reset(self) -> None:
        """Sitzung verwerfen (nach Fehlern): die nächste Nachricht beginnt neu, mit dem Verlauf als Text."""
        self._last = None
        asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)

    async def _disconnect(self) -> None:
        client, self._client, self._session_key = self._client, None, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception as error:
                log.debug("Claude Code beenden: %s", error)

    def close(self) -> None:
        try:
            asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop).result(5)
        except Exception:
            pass


def _transcript(history: Sequence[ChatMessage]) -> str:
    lines = [f"{'User' if m.role == 'user' else 'You'}: {m.content}" for m in history
             if m.role in ("user", "assistant") and m.content.strip()]
    return "(Earlier in this conversation)\n" + "\n".join(lines) if lines else ""
