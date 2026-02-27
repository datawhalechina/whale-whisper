from typing import List, Optional

import httpx
import os

from app.services.providers.types import ProviderConfig, ProviderValidation


OPENAI_COMPAT_IDS = {
    "openai",
    "openai_compat",
    "openai-compatible",
    "openai-compatible-audio-speech",
    "openai-compatible-audio-transcription",
    "openai-audio-speech",
    "openai-audio-transcription",
    "openrouter-ai",
    "ollama",
    "lm-studio",
    "vllm",
    "deepseek",
    "302-ai",
    "alibaba-cloud-model-studio",
    "volcengine",
    "comet-api",
    "cerebras-ai",
    "together-ai",
    "azure-ai-foundry",
    "xai",
    "novita-ai",
    "fireworks-ai",
    "featherless-ai",
    "cloudflare-workers-ai",
    "perplexity-ai",
    "mistral-ai",
    "moonshot-ai",
    "modelscope",
    "player2",
}

ALIYUN_NLS_ASR_IDS = {
    "aliyun-nls-transcription",
    "aliyun-nls-asr",
}

class ProviderRegistry:
    async def validate(self, config: ProviderConfig) -> ProviderValidation:
        provider_id = config.provider_id
        if provider_id in ALIYUN_NLS_ASR_IDS:
            api_key = (
                config.api_key
                or config.extra.get("apiKey")
                or config.extra.get("api_key")
                or os.getenv("DASHSCOPE_API_KEY")
            )
            if not str(api_key or "").strip():
                return ProviderValidation(valid=False, reason="Missing apiKey for Alibaba Bailian ASR")
            return ProviderValidation(valid=True)
        if provider_id in {"dify", "fastgpt"}:
            return self._validate_basic(config, require_base_url=True, require_api_key=True)
        if provider_id == "coze":
            result = self._validate_basic(config, require_base_url=True, require_api_key=True)
            if not result.valid:
                return result
            if not config.extra.get("bot_id"):
                return ProviderValidation(valid=False, reason="Missing bot_id for Coze")
            return ProviderValidation(valid=True)

        if provider_id in OPENAI_COMPAT_IDS or "openai" in provider_id:
            result = self._validate_basic(config, require_base_url=True, require_api_key=True)
            if not result.valid:
                return result
            try:
                await self._fetch_openai_models(config)
            except Exception as exc:
                return ProviderValidation(valid=False, reason=str(exc))
            return ProviderValidation(valid=True)

        return self._validate_basic(config, require_base_url=False, require_api_key=False)

    async def list_models(self, config: ProviderConfig) -> List[dict]:
        provider_id = config.provider_id
        if provider_id in ALIYUN_NLS_ASR_IDS:
            return [
                {"id": "qwen3-asr-flash-realtime", "label": "qwen3-asr-flash-realtime"},
                {"id": "qwen3-asr-flash", "label": "qwen3-asr-flash"},
            ]
        if provider_id in OPENAI_COMPAT_IDS or "openai" in provider_id:
            return await self._fetch_openai_models(config)
        return []

    async def list_voices(self, config: ProviderConfig) -> List[dict]:
        return []

    @staticmethod
    def _validate_basic(
        config: ProviderConfig, require_base_url: bool, require_api_key: bool
    ) -> ProviderValidation:
        if require_api_key and not config.api_key:
            return ProviderValidation(valid=False, reason="Missing API key")
        if require_base_url and not config.base_url:
            return ProviderValidation(valid=False, reason="Missing base URL")
        return ProviderValidation(valid=True)

    @staticmethod
    async def _fetch_openai_models(config: ProviderConfig) -> List[dict]:
        if not config.base_url:
            raise ValueError("Base URL is required")
        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        url = config.base_url.rstrip("/") + "/models"

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        models = data.get("data") if isinstance(data, dict) else None
        if not isinstance(models, list):
            return []
        return [
            {
                "id": item.get("id", "unknown"),
                "label": item.get("id", "unknown"),
            }
            for item in models
            if isinstance(item, dict)
        ]


registry = ProviderRegistry()
