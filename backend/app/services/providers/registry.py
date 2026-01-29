from typing import List, Optional

import httpx

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
    "groq",
    "glm",
}


class ProviderRegistry:
    async def validate(self, config: ProviderConfig) -> ProviderValidation:
        provider_id = config.provider_id
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
        
        result = [
            {
                "id": item.get("id", "unknown"),
                "label": item.get("id", "unknown"),
            }
            for item in models
            if isinstance(item, dict)
        ]
        
        # GLM 的 /models API 不返回免费模型，手动添加免费文本模型
        if "bigmodel.cn" in config.base_url:
            extra_models = [
                {"id": "glm-4.7-flash", "label": "glm-4.7-flash (免费)"},
                {"id": "glm-4-flash-250414", "label": "glm-4-flash-250414 (免费)"},
            ]
            # 合并并去重
            existing_ids = {m["id"] for m in result}
            for model in extra_models:
                if model["id"] not in existing_ids:
                    result.append(model)
        
        return result


registry = ProviderRegistry()
