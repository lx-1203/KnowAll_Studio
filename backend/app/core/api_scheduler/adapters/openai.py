"""OpenAI-compatible adapter (works for OpenAI, DeepSeek, Ollama, vLLM, etc.)"""
import json
import asyncio
import tiktoken
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .base import BaseModelAdapter, AdapterConfig, AdapterResponse


def _sync_post(url: str, headers: dict, payload: dict, timeout: int) -> dict:
    """Synchronous HTTP POST using urllib (most reliable cross-platform)."""
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


class OpenAICompatAdapter(BaseModelAdapter):
    """Adapter for any OpenAI-compatible API (OpenAI, DeepSeek, Ollama, vLLM, etc.)"""

    provider = "openai_compat"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model_name: str = "gpt-4o"):
        super().__init__(api_key, base_url)
        self.model_name = model_name
        try:
            self._encoder = tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            self._encoder = tiktoken.get_encoding("cl100k_base")

    async def chat_completion(
        self, messages: list[dict[str, str]], config: AdapterConfig
    ) -> AdapterResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = self._build_headers()
        headers["User-Agent"] = "KnowAll-Studio/1.0"
        headers["Accept"] = "application/json"
        payload = {
            "model": self.model_name,
            "messages": self._normalize_messages(messages),
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }
        payload.update(config.extra)

        data = await asyncio.to_thread(_sync_post, url, headers, payload, config.timeout)
        return self._parse_response(data)

    def count_tokens(self, text: str) -> int:
        return len(self._encoder.encode(text))

    def _parse_response(self, data: dict) -> AdapterResponse:
        choice = data["choices"][0]
        usage = data.get("usage", {})
        return AdapterResponse(
            content=choice["message"]["content"],
            raw_content=json.dumps(data, ensure_ascii=False),
            model=data.get("model", self.model_name),
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )


class DeepSeekAdapter(OpenAICompatAdapter):
    provider = "deepseek"
    model_name = "deepseek-chat"

    def __init__(self, api_key: str):
        super().__init__(api_key, base_url="https://api.deepseek.com/v1", model_name="deepseek-chat")


class OllamaAdapter(OpenAICompatAdapter):
    provider = "ollama"

    def __init__(self, model_name: str = "qwen2.5:7b", base_url: str = "http://localhost:11434/v1"):
        super().__init__(api_key="ollama", base_url=base_url, model_name=model_name)

    def _build_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}  # Ollama needs no auth header
