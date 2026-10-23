"""ClaudeModel: LanguageModel (llm.py) über die Claude API von Anthropic (SDK "anthropic").

Werkzeuge (MCP-Server, Plugins der Toolbar) laufen wie bei Ollama lokal: Claude antwortet mit
tool_use-Blöcken, der Assistent (ollama_assistant.py) ruft die Werkzeuge auf und schickt die
Ergebnisse als tool_result zurück. Anthropics MCP-Connector ginge nur für MCP-Server mit URL -
unsere laufen lokal über stdio.

Denken: Die Modelle denken immer (adaptiv); think steuert nur den Aufwand (effort).
Denkblöcke sind signiert und an alles gebunden, was in der Anfrage davor steht (Systemanweisung,
Werkzeuge, Verlauf). Sie gehen innerhalb einer Antwort unverändert zurück (provider_content),
der Assistent entfernt sie danach. Ändert sich doch etwas davor, verwirft die API sie
(prefix_mismatch_behavior "drop_block") statt mit 400 abzulehnen.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import anthropic

from backend.assistant.llm import ChatMessage, ModelError, ModelInfo, ModelResponse, ToolCall
from backend.assistant.tools import ToolSpec

log = logging.getLogger(__name__)

_BINDING_BETA = "thinking-binding-controls-2026-08-01"
# Lehnt das Modell aus Sicherheitsgründen ab, antwortet serverseitig ein anderes ("default" wählt es).
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5")
_EFFORT = {False: "low", True: "high"}   # think -> effort; None = Standard des Modells
_CACHE = {"type": "ephemeral"}


class ClaudeModel:
    """Erfüllt LanguageModel; Anbieter für ModelRouter (Modellnamen = Claude-Modell-IDs)."""

    reliable_tool_calls = True   # die Nachprüfung auf vergessene Werkzeugaufrufe ist für kleine Modelle

    def __init__(self, client: anthropic.Anthropic, models: Sequence[str], max_tokens: int = 16000):
        self.client = client
        self.models = list(models)
        self.max_tokens = max_tokens
        self.name = ""
        self.think: bool | None = None
        self._tools: list[dict[str, Any]] = []   # zuletzt angebotene Werkzeuge, siehe chat()

    def handles(self, name: str) -> bool:
        return name in self.models

    def installed(self) -> list[str]:
        return list(self.models)

    def available_models(self) -> list[ModelInfo]:
        return [ModelInfo(name, True) for name in self.models]

    def chat(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec] = ()) -> ModelResponse:
        if tools:
            self._tools = [_tool_to_claude(spec) for spec in tools]
        params: dict[str, Any] = {}
        if self._tools:
            # Ohne Werkzeuge (letzte Runde) dieselben schicken, nur keins erlauben: Ein anderes tools-Feld
            # machte die Denkblöcke ungültig, und ein Verlauf mit tool_use braucht die Definitionen.
            params["tools"] = [*self._tools[:-1], {**self._tools[-1], "cache_control": _CACHE}]
            params["tool_choice"] = {"type": "auto" if tools else "none"}
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        if system:
            params["system"] = system
        if self.think is not None:
            params["output_config"] = {"effort": _EFFORT[bool(self.think)]}
        betas = [_BINDING_BETA]
        if self.name in _FALLBACK_MODELS:
            betas.append(_FALLBACK_BETA)
            params["fallbacks"] = "default"
        try:
            response = self.client.beta.messages.create(
                model=self.name, max_tokens=self.max_tokens, messages=_messages_to_claude(messages),
                thinking={"type": "adaptive", "block_binding": {"prefix_mismatch_behavior": "drop_block"}},
                cache_control=_CACHE,   # Verlauf zwischen den Werkzeug-Runden aus dem Cache
                betas=betas, **params)
        except anthropic.AuthenticationError:
            raise ModelError("API-Schlüssel ungültig (data/anthropic_api_key.txt bzw. ANTHROPIC_API_KEY)") from None
        except anthropic.PermissionDeniedError as error:
            raise ModelError(f"Kein Zugriff: {error.message}") from None
        except anthropic.RateLimitError:
            raise ModelError("Zu viele Anfragen - kurz warten und noch einmal versuchen") from None
        except anthropic.APIStatusError as error:
            raise ModelError(error.message) from None
        except anthropic.APIConnectionError:
            raise ModelError("Claude ist nicht erreichbar. Internetverbindung da?") from None

        usage = response.usage
        log.info("Claude %s: %s Tokens Eingabe (+%s aus dem Cache), %s Ausgabe", response.model,
                 usage.input_tokens, usage.cache_read_input_tokens or 0, usage.output_tokens)
        if response.stop_reason == "refusal":
            raise ModelError("Claude hat die Anfrage abgelehnt")
        calls = tuple(ToolCall(block.name, block.input if isinstance(block.input, dict) else {}, block.id)
                      for block in response.content if block.type == "tool_use")
        if calls and response.stop_reason == "max_tokens":
            raise ModelError("Antwort abgeschnitten (CLAUDE_MAX_TOKENS), der Werkzeugaufruf ist unvollständig")
        text = "\n".join(block.text for block in response.content if block.type == "text").strip()
        return ModelResponse(ChatMessage("assistant", text, calls, provider_content=tuple(response.content)))


def _tool_to_claude(spec: ToolSpec) -> dict[str, Any]:
    schema = spec.input_schema or {"type": "object", "properties": {}}
    return {"name": spec.name, "description": spec.description, "input_schema": {"type": "object", **schema}}


def _messages_to_claude(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    """Verlauf ins Format der Claude API. Die Systemanweisung geht extra (chat()).

    Ergebnisse einer Runde stehen zusammen in einer Nutzernachricht. Aufrufe ohne ID (aus Ollama-Zeiten
    des Gesprächs oder als Text erkannt) bekommen eine aus ihrer Position; ihre Ergebnisse der Reihe nach.
    """
    result: list[dict[str, Any]] = []
    pending: list[str] = []   # IDs der letzten Aufrufe, deren Ergebnis noch fehlt
    for index, message in enumerate(messages):
        if message.role == "system":
            continue
        if message.role == "assistant":
            ids = [call.id or f"call_{index}_{n}" for n, call in enumerate(message.tool_calls)]
            if message.provider_content:
                content: list[Any] = list(message.provider_content)
            else:
                content = [{"type": "text", "text": message.content}] if message.content.strip() else []
                content += [{"type": "tool_use", "id": call_id, "name": call.name, "input": call.arguments}
                            for call_id, call in zip(ids, message.tool_calls)]
            pending = ids
            if content:
                result.append({"role": "assistant", "content": content})
        elif message.role == "tool":
            call_id = message.tool_call_id if message.tool_call_id in pending else (pending[0] if pending else "")
            if not call_id:
                result.append({"role": "user", "content": message.content or "(leer)"})
                continue
            pending.remove(call_id)
            block = {"type": "tool_result", "tool_use_id": call_id, "content": message.content or "(leer)"}
            previous = result[-1] if result else None
            if previous and previous["role"] == "user" and isinstance(previous["content"], list):
                previous["content"].append(block)
            else:
                result.append({"role": "user", "content": [block]})
        else:
            result.append({"role": "user", "content": message.content or "…"})
    return result
