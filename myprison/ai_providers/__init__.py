"""AI provider plugin registry for myprison."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any, Callable

from ..config import ToolConfig


class ProviderError(Exception):
    """Expected user-facing provider failure."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


ToolHandler = Callable[[ToolCall], dict[str, Any]]


class AIProvider:
    """Interface implemented by AI provider plugins."""

    name = ""
    display_name = ""
    default_model = ""

    def api_key(self, settings: dict) -> str:
        raise NotImplementedError

    def authenticate(self, settings: dict, cfg: ToolConfig, force: bool = False) -> str:
        raise NotImplementedError

    def run_turn(
        self,
        key: str,
        model: str,
        instructions: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        handle_tool: ToolHandler,
    ) -> str:
        raise NotImplementedError


def load_provider(name: str) -> AIProvider:
    """Load an installed AI provider plugin by name."""
    if name == "chatgpt":
        from .chatgpt import ChatGPTProvider

        return ChatGPTProvider()
    for entry_point in _entry_points():
        if entry_point.name == name:
            provider = entry_point.load()()
            if not isinstance(provider, AIProvider):
                raise ProviderError("AI provider does not implement AIProvider: %s" % name)
            return provider
    raise ProviderError("unknown AI provider: %s" % name)


def provider_names() -> list[str]:
    return sorted({"chatgpt", *[ep.name for ep in _entry_points()]})


def _entry_points():
    eps = metadata.entry_points()
    if hasattr(eps, "select"):
        return eps.select(group="myprison.ai_providers")
    return eps.get("myprison.ai_providers", [])
