"""LLM 客户端抽象层 — 统一接口 + DeepSeek-V4-Pro 默认实现"""

import os
import asyncio
from typing import AsyncIterator, Literal
from openai import AsyncOpenAI

# 默认使用 DeepSeek（OpenAI 兼容接口）
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-v4-pro"
FAST_MODEL = os.environ.get("LLM_FAST_MODEL", "deepseek-chat")  # 非面试问题的轻量模型

# 全局并发限制：最多同时 3 个 LLM 调用，防止 API 额度被快速耗尽
_LLM_SEMAPHORE = asyncio.Semaphore(3)

# 流式 chunk 类型：thinking = 思考链，token = 回答正文
StreamChunk = dict[Literal["type", "content"], str]


class LLMClient:
    """统一的 LLM 调用抽象。通过 OpenAI 兼容 SDK 接入，模型可配置替换。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or os.environ.get("LLM_MODEL", DEFAULT_MODEL)
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def configure(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        """运行时重新配置客户端。传空 key 可重置以防止使用旧配置。"""
        if api_key is not None:
            self.api_key = api_key
        if base_url is not None:
            self.base_url = base_url or self.base_url
        if model is not None:
            self.model = model or DEFAULT_MODEL
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url or DEFAULT_BASE_URL)

    def _ensure_key(self):
        """首次调用时校验 API Key 已配置（延迟校验，避免 import 时崩溃）。"""
        if not self.api_key or self.api_key.startswith("your_"):
            raise RuntimeError(
                "DEEPSEEK_API_KEY 未配置。请复制 .env.example 为 .env 并填入你的 DeepSeek API 密钥。\n"
                "获取地址：https://platform.deepseek.com"
            )

    def fast_model(self) -> str:
        """返回与当前 Provider 兼容的轻量模型。

        `deepseek-chat` 只在 DeepSeek 兼容端点使用；其他 Provider 回退到
        用户当前选择的模型，避免把 DeepSeek 模型名发送到 OpenAI/Anthropic。
        """
        if "deepseek.com" in (self.base_url or "").lower():
            return FAST_MODEL
        return self.model

    async def chat(
        self, messages: list[dict], temperature: float = 0.4, model: str | None = None
    ) -> str:
        """非流式对话，返回完整文本。"""
        self._ensure_key()
        async with _LLM_SEMAPHORE:
            resp = await self._client.chat.completions.create(
            model=model or self.model,
            messages=messages,
            temperature=temperature,
            stream=False,
        )
        return resp.choices[0].message.content or ""

    async def stream(
        self, messages: list[dict], temperature: float = 0.4, model: str | None = None
    ) -> AsyncIterator[StreamChunk]:
        """流式对话，逐 chunk yield。

        model 参数可选：传入则覆盖默认模型（用于模型切换）。
        """
        self._ensure_key()
        async with _LLM_SEMAPHORE:
            resp = await self._client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            # Keep the permit until the entire response stream has been consumed.
            async for chunk in resp:
                delta = chunk.choices[0].delta
                if delta:
                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        yield {"type": "thinking", "content": reasoning}
                    if delta.content:
                        yield {"type": "token", "content": delta.content}


# 全局默认实例
llm_client = LLMClient()
