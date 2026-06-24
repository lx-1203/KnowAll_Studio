"""Anthropic Messages API adapter"""
import json
import asyncio
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .base import BaseModelAdapter, AdapterConfig, AdapterResponse


def _sync_post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    """Synchronous HTTP POST using urllib."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:500]}")
    except URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}")


class AnthropicAdapter(BaseModelAdapter):
    """Adapter for Anthropic Messages API (and compatible endpoints like DeepSeek)."""

    provider = "anthropic"

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1", model_name: str = "claude-sonnet-4-6"):
        super().__init__(api_key, base_url)
        self.model_name = model_name
        self._api_version = "2023-06-01"

    async def chat_completion(
        self, messages: list[dict[str, str]], config: AdapterConfig
    ) -> AdapterResponse:
        url = f"{self.base_url.rstrip('/')}/messages"
        headers = self._build_headers()
        headers.update({
            "anthropic-version": self._api_version,
            "Content-Type": "application/json",
        })

        # Convert OpenAI-format messages to Anthropic format
        system_prompt = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        payload = {
            "model": self.model_name,
            "messages": anthropic_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        if system_prompt:
            payload["system"] = system_prompt
        payload.update(config.extra)

        data = await asyncio.to_thread(_sync_post, url, headers, payload, config.timeout)
        return self._parse_response(data)

    def count_tokens(self, text: str) -> int:
        return len(text) // 2

    def _parse_response(self, data: dict) -> AdapterResponse:
        content_blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        usage = data.get("usage", {})
        return AdapterResponse(
            content=text,
            raw_content=json.dumps(data, ensure_ascii=False),
            model=data.get("model", self.model_name),
            tokens_input=usage.get("input_tokens", 0),
            tokens_output=usage.get("output_tokens", 0),
            finish_reason=data.get("stop_reason", "stop"),
        )
