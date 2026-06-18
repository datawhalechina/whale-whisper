import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import app.services.providers.registry as provider_registry_module  # noqa: E402
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


def _volcengine_voices_payload() -> str:
    return """
{
  "status": "success",
  "error": null,
  "data": {
    "resource_packs": [
      {
        "code": "zh_female_test",
        "resource_display": "Test Voice",
        "details": {
          "language": "Chinese",
          "voice_type": "zh_female_test",
          "tone_number": "zh_female_test",
          "recommended_scenario": "General"
        }
      }
    ]
  }
}
""".strip()


def _make_local_temp_file() -> Path:
    root = ROOT / "tests_tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"tmp-{uuid.uuid4().hex}.json"
    return path


def test_load_local_tts_voices_recovers_after_transient_parse_error():
    temp_path = _make_local_temp_file()
    try:
        temp_path.write_text("{ invalid json", encoding="utf-8")

        original_map = provider_registry_module.LOCAL_TTS_VOICE_FILES
        provider_registry_module.LOCAL_TTS_VOICE_FILES = {
            **original_map,
            "volcengine-speech": temp_path,
        }
        provider_registry_module._load_local_tts_voices_cached.cache_clear()
        provider_registry_module._LAST_GOOD_LOCAL_TTS_VOICES.pop("volcengine-speech", None)
        try:
            broken = asyncio.run(
                provider_registry_module._load_local_tts_voices("volcengine-speech")
            )
            assert broken == []

            temp_path.write_text(_volcengine_voices_payload(), encoding="utf-8")
            recovered = asyncio.run(
                provider_registry_module._load_local_tts_voices("volcengine-speech")
            )
            assert len(recovered) == 1
            assert recovered[0]["id"] == "zh_female_test"
        finally:
            provider_registry_module.LOCAL_TTS_VOICE_FILES = original_map
            provider_registry_module._load_local_tts_voices_cached.cache_clear()
            provider_registry_module._LAST_GOOD_LOCAL_TTS_VOICES.pop("volcengine-speech", None)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_load_local_tts_voices_uses_last_good_on_parse_error():
    temp_path = _make_local_temp_file()
    try:
        temp_path.write_text(_volcengine_voices_payload(), encoding="utf-8")

        original_map = provider_registry_module.LOCAL_TTS_VOICE_FILES
        provider_registry_module.LOCAL_TTS_VOICE_FILES = {
            **original_map,
            "volcengine-speech": temp_path,
        }
        provider_registry_module._load_local_tts_voices_cached.cache_clear()
        provider_registry_module._LAST_GOOD_LOCAL_TTS_VOICES.pop("volcengine-speech", None)
        try:
            first = asyncio.run(
                provider_registry_module._load_local_tts_voices("volcengine-speech")
            )
            assert len(first) == 1

            temp_path.write_text("{ invalid json", encoding="utf-8")
            provider_registry_module._load_local_tts_voices_cached.cache_clear()
            fallback = asyncio.run(
                provider_registry_module._load_local_tts_voices("volcengine-speech")
            )
            assert len(fallback) == 1
            assert fallback[0]["id"] == "zh_female_test"
        finally:
            provider_registry_module.LOCAL_TTS_VOICE_FILES = original_map
            provider_registry_module._load_local_tts_voices_cached.cache_clear()
            provider_registry_module._LAST_GOOD_LOCAL_TTS_VOICES.pop("volcengine-speech", None)
    finally:
        if temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    run("list voices volcengine from local catalog", test_list_voices_volcengine_from_local_catalog)
    run("list voices alibaba filters by model", test_list_voices_alibaba_filters_by_model)
    run("list voices unsupported provider returns empty", test_list_voices_unsupported_provider_returns_empty)
    run(
        "load local tts voices recovers after transient parse error",
        test_load_local_tts_voices_recovers_after_transient_parse_error,
    )
    run(
        "load local tts voices uses last good on parse error",
        test_load_local_tts_voices_uses_last_good_on_parse_error,
    )
