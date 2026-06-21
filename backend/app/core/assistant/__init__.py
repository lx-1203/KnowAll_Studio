"""AI Multi-role Assistant (M6) - supports real SSE streaming"""
import json
import httpx
from typing import AsyncGenerator
from app.core.api_scheduler import api_client, TaskType, GenerationConfig
from app.core.api_scheduler.adapters.base import AdapterConfig

ROLE_PRESETS = {
    "lecturer": {
        "name": "授课讲师",
        "system": "你是一位经验丰富的授课讲师。请系统性地讲解知识点，用清晰的逻辑、生动的例子帮助学习者理解。在讲解结束后可以提一个思考题。",
    },
    "tutor": {
        "name": "答疑助教",
        "system": "你是一位耐心细致的答疑助教。针对学习者的问题给出准确、易懂的解答。如果不确定，请诚实说明。用分点方式组织回答。",
    },
    "mentor": {
        "name": "研讨主持人",
        "system": "你是一位苏格拉底式研讨主持人。不要直接给出答案，而是通过层层递进的提问引导学习者自己发现答案。每次回复最多提一个问题。",
    },
    "expand": {
        "name": "举一反三",
        "system": "你是一位知识拓展专家。根据学习者提供的内容，给出3-5个相关的拓展知识点、实际应用场景或跨学科联系。",
    },
}


class Assistant:
    """AI assistant with role presets. Handles conversation context management."""

    def get_role_presets(self) -> dict:
        return {
            key: {"name": v["name"], "description": v["system"][:50] + "..."}
            for key, v in ROLE_PRESETS.items()
        }

    async def chat_stream(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
    ) -> AsyncGenerator[str, None]:
        """Stream chat response using SSE via httpx streaming.

        Yields content chunks as they arrive from the model API.
        """
        preset = ROLE_PRESETS.get(role_preset, ROLE_PRESETS["tutor"])
        messages = [{"role": "system", "content": preset["system"]}]
        if history:
            messages.extend(history[-20:])
        messages.append({"role": "user", "content": user_message})

        adapter = api_client.get_adapter(model)
        url = f"{adapter.base_url.rstrip('/')}/chat/completions"
        headers = adapter._build_headers()
        payload = {
            "model": adapter.model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def chat(
        self,
        user_message: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
    ) -> str:
        """Non-streaming chat. Returns full response."""
        preset = ROLE_PRESETS.get(role_preset, ROLE_PRESETS["tutor"])
        messages = [{"role": "system", "content": preset["system"]}]
        if history:
            messages.extend(history[-20:])
        messages.append({"role": "user", "content": user_message})

        adapter = api_client.get_adapter(model)
        response = await adapter.chat_completion(
            messages,
            AdapterConfig(temperature=0.7, max_tokens=2048, timeout=120),
        )
        return response.content

    async def chat_with_context(
        self,
        user_message: str,
        knowledge_context: str,
        role_preset: str = "tutor",
        history: list[dict] | None = None,
        model: str = "deepseek-chat",
    ) -> str:
        """Chat with additional knowledge context."""
        preset = ROLE_PRESETS.get(role_preset, ROLE_PRESETS["tutor"])
        messages = [
            {"role": "system", "content": preset["system"] + f"\n\n参考知识上下文：\n{knowledge_context[:3000]}"},
        ]
        if history:
            messages.extend(history[-20:])
        messages.append({"role": "user", "content": user_message})

        result = await api_client.generate(
            task_type=TaskType.CHAT,
            messages=messages,
            prompt_template_id=f"assistant.{role_preset}",
            generation_content=user_message,
            config=GenerationConfig(max_tokens=2048),
        )
        return result.content


assistant = Assistant()
