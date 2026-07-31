"""OpenCode provider plugin backed by the OpenCode Zen gateway.

OpenCode Zen (https://opencode.ai/zen) exposes an OpenAI Responses-compatible
endpoint, so this provider reuses the ChatGPT wire protocol with a different
URL, API key, and model catalog.
"""

from __future__ import annotations

import getpass
import os
from typing import Any

from ..config import ToolConfig
from .chatgpt import ChatGPTProvider

ZEN_RESPONSES_URL = "https://opencode.ai/zen/v1/responses"


class OpenCodeProvider(ChatGPTProvider):
    name = "opencode"
    display_name = "OpenCode Zen"
    default_model = "gpt-5.6-terra"
    responses_url = ZEN_RESPONSES_URL
    api_label = "OpenCode Zen"

    def api_key(self, settings: dict) -> str:
        return (
            os.environ.get("OPENCODE_API_KEY", "").strip()
            or settings.get("api_key", "").strip()
        )

    def authenticate(self, settings: dict, cfg: ToolConfig, force: bool = False) -> str:
        if not force:
            print("First-time OpenCode setup: set OPENCODE_API_KEY or paste an API key now.")
            print("Create a key at https://opencode.ai/zen")
        key = getpass.getpass("OpenCode API key (input hidden, blank cancels): ").strip()
        if not key:
            return ""
        save = input("Save this key in .myprison.json mode 0600? [y/N] ").strip().lower()
        if save == "y":
            settings["api_key"] = key
            cfg.save()
            print("Saved AI settings to %s" % cfg.path)
        else:
            print("Using key for this session only.")
        return key

    def native_tools(self, settings: dict) -> list[dict[str, Any]]:
        # The Zen gateway does not forward OpenAI hosted tools, so provider
        # web search is opt-in here instead of on by default.
        if settings.get("web_search", False):
            return [{"type": "web_search", "search_context_size": "medium"}]
        return []
