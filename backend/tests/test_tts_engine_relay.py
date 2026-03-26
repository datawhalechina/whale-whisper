import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.api.tts import (  # noqa: E402
    _build_volcengine_provider_payload,
    _build_unspeech_payload,
    _decorate_tts_error,
    _extract_json_error_message,
    _extract_tts_input,
    _normalize_alibaba_provider_model,
    _resolve_volcengine_tts_url,
    _resolve_alibaba_tts_ws_url,
    _resolve_tts_api_key,
)
from app.services.engines.runtime_store import EngineRuntimeConfig  # noqa: E402


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def test_extract_tts_input_supports_string_and_object_forms():
    assert _extract_tts_input("hello") == "hello"
    assert _extract_tts_input({"text": "hello"}) == "hello"
    assert _extract_tts_input({"input": "hello"}) == "hello"
    assert _extract_tts_input({"prompt": "hello"}) == "hello"
    assert _extract_tts_input(None) == ""


def test_resolve_tts_api_key_prefers_request_override():
    import os

    previous = os.environ.get("TEST_TTS_KEY")
    os.environ["TEST_TTS_KEY"] = "env-key"
    runtime = EngineRuntimeConfig(
        id="volcengine-speech",
        base_url="https://unspeech.example/v1",
        model="v1",
        api_key_env="TEST_TTS_KEY",
    )
    try:
        assert _resolve_tts_api_key(runtime, {"apiKey": "request-key"}) == "request-key"
        assert _resolve_tts_api_key(runtime, {"api_key": "request-key-2"}) == "request-key-2"
        assert _resolve_tts_api_key(runtime, {}) == "env-key"
    finally:
        if previous is None:
            os.environ.pop("TEST_TTS_KEY", None)
        else:
            os.environ["TEST_TTS_KEY"] = previous


def test_build_unspeech_payload_for_volcengine():
    runtime = EngineRuntimeConfig(
        id="volcengine-speech",
        base_url="https://unspeech.example/v1",
        model="v1",
    )

    payload = _build_unspeech_payload(
        engine_id="volcengine-speech",
        runtime_config=runtime,
        text="hello volcengine",
        overrides={
            "model": "v1",
            "voice": "zh_female_sample",
            "appId": "appid-123",
            "response_format": "mp3",
        },
    )

    assert payload["model"] == "volcengine/v1"
    assert payload["voice"] == "zh_female_sample"
    assert payload["input"] == "hello volcengine"
    assert payload["response_format"] == "mp3"
    assert payload["extra_body"]["app"]["appid"] == "appid-123"


def test_build_unspeech_payload_for_alibaba():
    runtime = EngineRuntimeConfig(
        id="alibaba-cloud-model-studio-speech",
        base_url="https://unspeech.example/v1",
        model="alibaba/cosyvoice-v1",
    )

    payload = _build_unspeech_payload(
        engine_id="alibaba-cloud-model-studio-speech",
        runtime_config=runtime,
        text="hello alibaba",
        overrides={
            "model": "cosyvoice-v1",
            "voice": "longxiaochun_v2",
            "rate": 1.2,
            "pitch": 0.9,
            "volume": 80,
        },
    )

    assert payload["model"] == "alibaba/cosyvoice-v1"
    assert payload["voice"] == "longxiaochun_v2"
    assert payload["input"] == "hello alibaba"
    assert payload["extra_body"]["rate"] == 1.2
    assert payload["extra_body"]["pitch"] == 0.9
    assert payload["extra_body"]["volume"] == 80


def test_build_volcengine_provider_payload_direct():
    runtime = EngineRuntimeConfig(
        id="volcengine-speech",
        base_url="https://unspeech.example/v1",
        model="v1",
    )

    payload = _build_volcengine_provider_payload(
        runtime_config=runtime,
        text="hello volcengine direct",
        overrides={
            "voice": "zh_female_sample",
            "appId": "appid-123",
            "response_format": "mp3",
            "speed": 1.2,
            "request": {"operation": "query"},
        },
        api_key="token-abc",
    )

    assert payload["app"]["appid"] == "appid-123"
    assert payload["app"]["token"] == "token-abc"
    assert payload["audio"]["voice_type"] == "zh_female_sample"
    assert payload["audio"]["encoding"] == "mp3"
    assert payload["audio"]["speed_ratio"] == 1.2
    assert payload["request"]["text"] == "hello volcengine direct"


def test_resolve_volcengine_tts_url_ignores_client_url_override():
    runtime = EngineRuntimeConfig(
        id="volcengine-speech",
        base_url="https://openspeech.bytedance.com/api/v1/tts",
        model="v1",
    )
    url = _resolve_volcengine_tts_url(
        runtime,
        {
            "volcengine_url": "https://attacker.example/tts",
            "provider_url": "https://attacker-2.example/tts",
        },
    )
    assert url == "https://openspeech.bytedance.com/api/v1/tts"


def test_resolve_alibaba_tts_ws_url_prefers_intl_region():
    runtime = EngineRuntimeConfig(
        id="alibaba-cloud-model-studio-speech",
        base_url="https://unspeech.example/v1",
        model="alibaba/cosyvoice-v1",
    )
    ws_url = _resolve_alibaba_tts_ws_url(runtime, {"region": "intl"})
    assert ws_url == "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"


def test_resolve_alibaba_tts_ws_url_ignores_client_url_override():
    runtime = EngineRuntimeConfig(
        id="alibaba-cloud-model-studio-speech",
        base_url="https://dashscope.aliyuncs.com",
        model="cosyvoice-v1",
    )
    ws_url = _resolve_alibaba_tts_ws_url(
        runtime,
        {
            "ws_url": "wss://attacker.example/ws",
            "dashscope_ws_url": "wss://attacker-2.example/ws",
            "baseUrl": "https://dashscope-intl.aliyuncs.com",
        },
    )
    assert ws_url == "wss://dashscope.aliyuncs.com/api-ws/v1/inference"


def test_normalize_alibaba_provider_model_strips_provider_prefix():
    assert _normalize_alibaba_provider_model("alibaba/cosyvoice-v1") == "cosyvoice-v1"
    assert _normalize_alibaba_provider_model("cosyvoice-v1") == "cosyvoice-v1"


def test_extract_json_error_message_from_errors_array():
    payload = {
        "errors": [
            {
                "status": 401,
                "detail": "load grant: requested grant not found in SaaS storage",
            }
        ]
    }
    assert (
        _extract_json_error_message(payload)
        == "load grant: requested grant not found in SaaS storage"
    )


def test_decorate_tts_error_for_volcengine_grant_issue():
    message = "load grant: requested grant not found in SaaS storage"
    decorated = _decorate_tts_error(message, "volcengine-speech")
    assert "Volcengine credentials mismatch" in decorated
    assert "appId" in decorated


if __name__ == "__main__":
    run("extract tts input supports string and object forms", test_extract_tts_input_supports_string_and_object_forms)
    run("resolve tts api key prefers request override", test_resolve_tts_api_key_prefers_request_override)
    run("build unspeech payload for volcengine", test_build_unspeech_payload_for_volcengine)
    run("build unspeech payload for alibaba", test_build_unspeech_payload_for_alibaba)
    run("build volcengine provider payload direct", test_build_volcengine_provider_payload_direct)
    run(
        "resolve volcengine tts url ignores client url override",
        test_resolve_volcengine_tts_url_ignores_client_url_override,
    )
    run("resolve alibaba tts ws url prefers intl region", test_resolve_alibaba_tts_ws_url_prefers_intl_region)
    run(
        "resolve alibaba tts ws url ignores client url override",
        test_resolve_alibaba_tts_ws_url_ignores_client_url_override,
    )
    run("normalize alibaba provider model strips provider prefix", test_normalize_alibaba_provider_model_strips_provider_prefix)
    run("extract json error message from errors array", test_extract_json_error_message_from_errors_array)
    run("decorate tts error for volcengine grant issue", test_decorate_tts_error_for_volcengine_grant_issue)
