"""ChatGPT provider plugin backed by the OpenAI Responses API."""

from __future__ import annotations

import getpass
import json
import os
import urllib.error
import urllib.request
from typing import Any

from ..config import ToolConfig
from . import AIProvider, ProviderError, ToolCall, ToolHandler

RESPONSES_URL = "https://api.openai.com/v1/responses"


class ChatGPTProvider(AIProvider):
    name = "chatgpt"
    display_name = "ChatGPT"
    default_model = "gpt-5.6-terra"
    responses_url = RESPONSES_URL
    api_label = "OpenAI"

    def api_key(self, settings: dict) -> str:
        return (
            os.environ.get("OPENAI_API_KEY", "").strip()
            or settings.get("api_key", "").strip()
        )

    def authenticate(self, settings: dict, cfg: ToolConfig, force: bool = False) -> str:
        if not force:
            print("First-time ChatGPT setup: set OPENAI_API_KEY or paste an API key now.")
        key = getpass.getpass("OpenAI API key (input hidden, blank cancels): ").strip()
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
        if settings.get("web_search", True):
            return [{"type": "web_search", "search_context_size": "medium"}]
        return []

    def run_turn(
        self,
        settings: dict,
        key: str,
        model: str,
        instructions: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        handle_tool: ToolHandler,
    ) -> str:
        input_items: list[dict[str, Any]] = list(messages)
        for _ in range(8):
            response = self._request(key, model, instructions, input_items, tools, settings)
            output = response.get("output") or []
            calls = [self._tool_call(item) for item in output if item.get("type") == "function_call"]
            if not calls:
                return self._response_text(response)
            tool_outputs = []
            for call in calls:
                result = handle_tool(call)
                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": call.id,
                    "output": json.dumps(result, ensure_ascii=False),
                })
            input_items = input_items + output + tool_outputs
        raise ProviderError("too many tool calls in one turn")

    def _request(
        self,
        key: str,
        model: str,
        instructions: str,
        input_items: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        settings: dict,
    ) -> dict:
        body = {
            "model": model,
            "instructions": instructions,
            "input": input_items,
            "tools": [self._responses_tool(tool) for tool in tools]
            + self.native_tools(settings),
            "tool_choice": "auto",
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.responses_url,
            data=data,
            method="POST",
            headers={
                "Authorization": "Bearer %s" % key,
                "Content-Type": "application/json",
                "User-Agent": "myprison",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                msg = payload.get("error", {}).get("message") or raw
            except ValueError:
                msg = raw[:500]
            raise ProviderError("%s API error HTTP %d: %s" % (self.api_label, exc.code, msg))
        except urllib.error.URLError as exc:
            raise ProviderError("%s API request failed: %s" % (self.api_label, exc))

    def _responses_tool(self, tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
            "strict": True,
        }

    def _tool_call(self, item: dict[str, Any]) -> ToolCall:
        try:
            args = json.loads(item.get("arguments") or "{}")
        except ValueError as exc:
            raise ProviderError("invalid tool arguments from model: %s" % exc)
        return ToolCall(
            id=item.get("call_id") or item.get("id") or "",
            name=item.get("name") or "",
            arguments=args,
        )

    def _response_text(self, response: dict[str, Any]) -> str:
        if isinstance(response.get("output_text"), str):
            return response["output_text"].strip()
        chunks: list[str] = []
        for item in response.get("output") or []:
            if item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
        return "\n".join(chunks).strip()
