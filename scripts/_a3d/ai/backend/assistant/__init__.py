"""Assistent hinter dem Chat.

Aufbau:
  base.py              Assistant-Protokoll + AssistantReply (Ansichten: backend/views.py)
  commands.py          CommandAssistant - feste Befehle, ohne Sprachmodell
  llm.py               LanguageModel-Protokoll
  ollama.py            OllamaModel - LanguageModel über Ollama (lokal oder Ollama-Cloud)
  claude.py            ClaudeModel - LanguageModel über die Claude API (Anthropic)
  claude_code.py       ClaudeCodeAgent - Claude über das eigene Abo (Claude Agent SDK, eigene Werkzeug-Schleife)
  router.py            ModelRouter - eine Modellauswahl über alle Anbieter
  ollama_assistant.py  OllamaAssistant - Sprachmodell + Werkzeuge (Tool-Calling)
  tools.py             ToolProvider-Protokoll (Integrationen, MCP) + CompositeToolProvider
  skills/              Fähigkeiten des Assistenten (morning, travel, organization)

Es gibt einen durchgehenden Assistenten. Welcher läuft, legt
config.ASSISTANT_BACKEND fest ("ollama" oder "commands", siehe _BACKENDS).
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from backend import config
from backend.assistant.base import Assistant, AssistantReply, ModelSelection
from backend.assistant.commands import CommandAssistant

log = logging.getLogger(__name__)


def _ollama_assistant() -> Assistant:
    # Erst hier importieren: Der CommandAssistant braucht nichts davon.
    from backend.assistant.ollama import CLOUD_PREFIX, OllamaClient, OllamaModel
    from backend.assistant.ollama_assistant import OllamaAssistant
    from backend.assistant.router import ModelRouter
    from backend.assistant.skills import SKILLS
    from backend.assistant.tools import CompositeToolProvider
    from backend.integrations.mcp_client import load_mcp_servers
    from backend.integrations.toolbar import ToolbarPluginTools
    from backend.preferences import JsonPreferenceStore

    # Erster Anbieter = Ollama lokal (alles, was kein anderer übernimmt), dann die mit API-Schlüssel
    providers = [OllamaModel(OllamaClient(config.OLLAMA_URL, config.OLLAMA_TIMEOUT_S), options=config.OLLAMA_OPTIONS)]
    if config.OLLAMA_API_KEY:
        cloud = OllamaClient(config.OLLAMA_CLOUD_URL, config.OLLAMA_TIMEOUT_S, config.OLLAMA_API_KEY)
        providers.append(OllamaModel(cloud, options=config.OLLAMA_OPTIONS, prefix=CLOUD_PREFIX))
    if config.ANTHROPIC_API_KEY:
        import anthropic
        from backend.assistant.claude import ClaudeModel
        providers.append(ClaudeModel(anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY),
                                     config.CLAUDE_MODELS, config.CLAUDE_MAX_TOKENS))
    if config.CLAUDE_CODE_MODELS:
        try:
            from backend.assistant.claude_code import ClaudeCodeAgent
        except ImportError as error:   # claude-agent-sdk fehlt (setup_ai.bat noch nicht neu ausgeführt)
            log.warning("Claude-Abo nicht verfügbar: %s", error)
        else:
            providers.append(ClaudeCodeAgent(config.CLAUDE_CODE_MODELS, config.ASSISTANT_MAX_TOOL_ROUNDS + 1,
                                             config.OLLAMA_TIMEOUT_S, config.CLAUDE_CODE_DIR))
    model = ModelRouter(providers, config.OLLAMA_MODEL, config.OLLAMA_THINK)
    mcp_servers = load_mcp_servers(config.MCP_SERVERS_FILE, config.ROOT_DIR)
    # Werkzeuge: MCP-Server, Plugins der Toolbar (Timer, Kalender ...), Fähigkeiten
    tools = CompositeToolProvider([*mcp_servers, ToolbarPluginTools(), *(skill.tools for skill in SKILLS)])
    instructions = "\n\n".join(skill.instructions for skill in SKILLS)
    return OllamaAssistant(model, tools, JsonPreferenceStore(config.PREFERENCES_FILE), instructions,
                           config.ASSISTANT_MAX_TOOL_ROUNDS, config.ASSISTANT_MAX_HISTORY,
                           language=config.LANGUAGE, check_missed_calls=config.ASSISTANT_CHECK_MISSED_CALLS)


_BACKENDS: dict[str, Callable[[], Assistant]] = {
    "commands": CommandAssistant,
    "ollama": _ollama_assistant,
}


def create_assistant(backend: str = config.ASSISTANT_BACKEND) -> Assistant:
    try:
        factory = _BACKENDS[backend]
    except KeyError:
        raise ValueError(f"Unbekanntes Assistant-Backend: {backend!r} (verfügbar: {sorted(_BACKENDS)})") from None
    return factory()


__all__ = ["Assistant", "AssistantReply", "ModelSelection", "create_assistant"]
