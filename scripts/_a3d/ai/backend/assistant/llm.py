"""Schnittstelle zu einem Sprachmodell.

Nur Datentypen und Protokoll. Die Typen folgen dem Chat-Format, das Ollama
(/api/chat) und andere Anbieter gemeinsam haben. Implementierungen: ollama.py
(Ollama lokal und Ollama-Cloud), claude.py (Claude API); router.py wählt je Modellname.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from backend.assistant.tools import ToolSpec

Role = Literal["system", "user", "assistant", "tool"]


class ModelError(RuntimeError):
    """Das Sprachmodell ist nicht erreichbar oder hat mit einem Fehler geantwortet."""


@dataclass(frozen=True)
class ModelInfo:
    name: str
    supports_tools: bool


@dataclass(frozen=True)
class ToolCall:
    """Das Modell möchte ein Werkzeug mit diesen Argumenten aufrufen."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str = ""          # vom Modell vergeben (Claude); das Ergebnis verweist darauf, Ollama hat keine


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str = ""   # nur bei role="tool": zu welchem Werkzeug das Ergebnis gehört
    tool_call_id: str = ""   # nur bei role="tool": ToolCall.id des Aufrufs, falls vergeben
    thinking: str = ""    # Denkmodus: Überlegungen des Modells (gehen mit den Werkzeugaufrufen zurück)
    # Antwort im Format des Anbieters, die unverändert zurückgehen muss (Claude: Inhaltsblöcke samt
    # signierter Denkblöcke). Nur innerhalb einer Antwort; der Assistent entfernt sie danach wie thinking.
    provider_content: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ModelResponse:
    message: ChatMessage


@runtime_checkable
class LanguageModel(Protocol):
    def chat(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec] = ()) -> ModelResponse:
        """Nächste Antwort des Modells auf den bisherigen Verlauf."""
        ...
