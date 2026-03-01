import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import app.services.providers.registry as provider_registry_module  # noqa: E402
from app.services.engines.runtime_store import EngineRuntimeConfig, store as runtime_store  # noqa: E402
from app.services.providers.types import ProviderConfig  # noqa: E402


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def test_list_voices_volcengine_from_local_catalog():
    async def fake_load(provider_id: str):
        assert provider_id == "volcengine-speech"
        return [
            {
                "id": "voice-a",
                "name": "Voice A",
                "languages": [{"title": "Chinese"}],
                "compatible_models": ["v1"],
            }
        ]

    original = provider_registry_module._load_local_tts_voices
    provider_registry_module._load_local_tts_voices = fake_load
    try:
        result = asyncio.run(
            provider_registry_module.registry.list_voices(
                ProviderConfig(
                    provider_id="volcengine-speech",
                    api_key="",
                )
            )
        )
    finally:
        provider_registry_module._load_local_tts_voices = original

    assert result == [
        {
            "id": "voice-a",
            "label": "Voice A",
            "description": "Chinese",
        }
    ]


def test_list_voices_alibaba_filters_by_model():
    async def fake_load(provider_id: str):
        assert provider_id == "alibaba-cloud-model-studio-speech"
        return [
            {
                "id": "voice-1",
                "name": "Voice One",
                "languages": [{"title": "Chinese"}],
                "compatible_models": ["cosyvoice-v1"],
            },
            {
                "id": "voice-2",
                "name": "Voice Two",
                "languages": [{"title": "Chinese"}],
                "compatible_models": ["cosyvoice-v2"],
            },
        ]

    original = provider_registry_module._load_local_tts_voices
    provider_registry_module._load_local_tts_voices = fake_load
    try:
        result = asyncio.run(
            provider_registry_module.registry.list_voices(
                ProviderConfig(
                    provider_id="alibaba-cloud-model-studio-speech",
                    api_key="",
                    model="cosyvoice-v1",
                )
            )
        )
    finally:
        provider_registry_module._load_local_tts_voices = original

    assert len(result) == 1
    assert result[0]["id"] == "voice-1"


def test_list_voices_unsupported_provider_returns_empty():
    result = asyncio.run(
        provider_registry_module.registry.list_voices(
            ProviderConfig(
                provider_id="unknown-provider",
                api_key="",
            )
        )
    )
    assert result == []


if __name__ == "__main__":
    run("list voices volcengine from local catalog", test_list_voices_volcengine_from_local_catalog)
    run("list voices alibaba filters by model", test_list_voices_alibaba_filters_by_model)
    run("list voices unsupported provider returns empty", test_list_voices_unsupported_provider_returns_empty)
