"""ModelRouter: eine Modellauswahl über mehrere Anbieter (Ollama lokal, Ollama-Cloud, Claude API, Claude-Abo).

Erfüllt LanguageModel und bietet, was der Assistent sonst von OllamaModel nutzt (name, think,
installed, available_models). Wer antwortet, entscheidet der Modellname: der erste weitere Anbieter,
dessen handles(name) zutrifft (Ollama-Cloud: "cloud/…", Claude: seine Modell-IDs, Abo: "abo/…"),
sonst der erste. Anbieter mit runs_tools (Claude-Abo) führen die Werkzeug-Schleife selbst: respond().
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from backend.assistant.llm import ChatMessage, ModelError, ModelResponse
from backend.assistant.tools import ToolSpec

log = logging.getLogger(__name__)


class ModelRouter:
    def __init__(self, providers: Sequence[Any], name: str = "", think: bool | None = None):
        self.providers = list(providers)   # erster = Standard (Ollama lokal)
        self.name = name
        self.think = think

    def _provider(self) -> Any:
        return next((p for p in self.providers[1:] if p.handles(self.name)), self.providers[0])

    @property
    def reliable_tool_calls(self) -> bool:
        return getattr(self._provider(), "reliable_tool_calls", False)

    @property
    def runs_tools(self) -> bool:
        return getattr(self._provider(), "runs_tools", False)

    def chat(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec] = ()) -> ModelResponse:
        return self._selected().chat(messages, tools)

    def respond(self, *args: Any) -> ChatMessage:
        return self._selected().respond(*args)

    def _selected(self) -> Any:
        provider = self._provider()
        provider.name, provider.think = self.name, self.think
        return provider

    def installed(self) -> list[str]:
        return self._collect(lambda provider: provider.installed())

    def available_models(self) -> list:
        return self._collect(lambda provider: provider.available_models())

    def _collect(self, get: Callable[[Any], list]) -> list:
        """Ergebnisse aller Anbieter. Ein nicht erreichbarer fällt weg; erst wenn keiner antwortet, gibt es den Fehler."""
        results, errors = [], []
        for provider in self.providers:
            try:
                results.extend(get(provider))
            except ModelError as error:
                errors.append(error)
        if errors and not results:
            raise errors[0]
        for error in errors:
            log.info("Anbieter nicht erreichbar, seine Modelle fehlen in der Auswahl: %s", error)
        return results
