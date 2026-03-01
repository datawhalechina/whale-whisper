import os
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx

from app.services.engines import runtime_store
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

LOCAL_TTS_PROVIDER_IDS = {
    "volcengine-speech",
    "alibaba-cloud-model-studio-speech",
}
LOCAL_TTS_VOICES_DIR = Path(__file__).resolve().parent / "voices"
LOCAL_TTS_VOICE_FILES = {
    "volcengine-speech": LOCAL_TTS_VOICES_DIR / "volcengine.json",
    "alibaba-cloud-model-studio-speech": LOCAL_TTS_VOICES_DIR / "alibaba.json",
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
        if config.provider_id not in LOCAL_TTS_PROVIDER_IDS:
            return []

        voices = await _load_local_tts_voices(config.provider_id)
        tts_runtime = runtime_store.get("tts", config.provider_id)

        if config.provider_id == "alibaba-cloud-model-studio-speech":
            runtime_model = str(tts_runtime.model or "").strip() if tts_runtime else ""
            filter_model = config.model or runtime_model
            model_candidates = _resolve_model_candidates(filter_model)
            if model_candidates:
                voices = [
                    voice
                    for voice in voices
                    if _voice_matches_model_candidates(voice, model_candidates)
                ]

        options: List[dict] = []
        for voice in voices:
            if not isinstance(voice, dict):
                continue

            voice_id = voice.get("id")
            voice_name = voice.get("name")
            if not isinstance(voice_id, str) or not voice_id.strip():
                continue
            if not isinstance(voice_name, str) or not voice_name.strip():
                continue

            options.append(
                {
                    "id": voice_id.strip(),
                    "label": voice_name.strip(),
                    "description": _build_voice_description(voice),
                }
            )

        return options

    @staticmethod
    def _validate_basic(
        config: ProviderConfig, require_base_url: bool, require_api_key: bool
    ) -> ProviderValidation:
        if require_api_key and not str(config.api_key or "").strip():
            return ProviderValidation(valid=False, reason="Missing API key")
        if require_base_url and not str(config.base_url or "").strip():
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


async def _load_local_tts_voices(provider_id: str) -> List[dict]:
    path = LOCAL_TTS_VOICE_FILES.get(provider_id)
    if not path:
        return []
    return _load_local_tts_voices_cached(provider_id, str(path))


@lru_cache(maxsize=8)
def _load_local_tts_voices_cached(provider_id: str, path: str) -> List[dict]:
    source = Path(path)
    if not source.exists():
        return []

    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return []

    if provider_id == "alibaba-cloud-model-studio-speech":
        return _parse_alibaba_voices(raw)
    if provider_id == "volcengine-speech":
        return _parse_volcengine_voices(raw)
    return []


def _parse_alibaba_voices(raw: Any) -> List[dict]:
    if not isinstance(raw, list):
        return []

    voices: List[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        voice_id = str(item.get("voice") or "").strip()
        name = str(item.get("name") or "").strip()
        model = str(item.get("model") or "").strip()
        language = str(item.get("language") or "").strip()

        if not voice_id:
            continue

        voice: Dict[str, Any] = {
            "id": voice_id,
            "name": name or voice_id,
            "compatible_models": [model] if model else [],
        }
        if language:
            voice["languages"] = [{"title": language, "code": language}]
        voices.append(voice)

    return voices


def _parse_volcengine_voices(raw: Any) -> List[dict]:
    if not isinstance(raw, dict):
        return []

    data = raw.get("data")
    if not isinstance(data, dict):
        return []

    resource_packs = data.get("resource_packs")
    if not isinstance(resource_packs, list):
        return []

    voices: List[dict] = []
    for item in resource_packs:
        if not isinstance(item, dict):
            continue

        details = item.get("details")
        details = details if isinstance(details, dict) else {}
        voice_id = str(item.get("code") or "").strip()
        name = str(item.get("resource_display") or "").strip()
        language = str(details.get("language") or "").strip()

        if not voice_id:
            continue

        voice: Dict[str, Any] = {
            "id": voice_id,
            "name": name or voice_id,
            "compatible_models": ["v1"],
        }
        if language:
            voice["languages"] = [{"title": language, "code": language}]
        voices.append(voice)

    return voices


def _resolve_model_candidates(model: Optional[str]) -> Set[str]:
    if not model:
        return set()

    candidate = model.strip()
    if not candidate:
        return set()

    result: Set[str] = {candidate}
    if "/" in candidate:
        short_model = candidate.split("/")[-1].strip()
        if short_model:
            result.add(short_model)
    else:
        result.add(f"alibaba/{candidate}")
    return result


def _voice_matches_model_candidates(voice: dict, model_candidates: Set[str]) -> bool:
    compatible_models = voice.get("compatible_models")
    if not isinstance(compatible_models, list) or len(compatible_models) == 0:
        return True

    normalized = {
        str(model).strip()
        for model in compatible_models
        if isinstance(model, str) and str(model).strip()
    }
    return len(normalized.intersection(model_candidates)) > 0


def _build_voice_description(voice: dict) -> str:
    descriptions: List[str] = []

    languages = voice.get("languages")
    if isinstance(languages, list) and len(languages) > 0:
        titles: List[str] = []
        for language in languages:
            if not isinstance(language, dict):
                continue
            title = language.get("title")
            code = language.get("code")
            if isinstance(title, str) and title.strip():
                titles.append(title.strip())
            elif isinstance(code, str) and code.strip():
                titles.append(code.strip())
        if titles:
            descriptions.append(", ".join(titles))

    return " | ".join(descriptions)


registry = ProviderRegistry()
