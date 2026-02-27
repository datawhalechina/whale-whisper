import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.api.asr import (  # noqa: E402
    _build_aliyun_dashscope_urls,
    _build_aliyun_realtime_ws_url,
    _extract_aliyun_realtime_event_text,
    _extract_dashscope_asr_text,
    _resolve_aliyun_non_realtime_model,
    _resolve_aliyun_realtime_model,
)


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def test_build_aliyun_dashscope_urls():
    urls = _build_aliyun_dashscope_urls("https://dashscope.aliyuncs.com")
    assert urls["chat"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def test_extract_dashscope_asr_text_from_chat_response():
    payload = {
        "choices": [
            {
                "message": {
                    "content": "hello world",
                }
            }
        ]
    }
    assert _extract_dashscope_asr_text(payload) == "hello world"


def test_extract_dashscope_asr_text_from_output_results():
    payload = {
        "output": {
            "task_status": "SUCCEEDED",
            "results": [
                {"text": "first line"},
                {"transcript": "second line"},
            ],
        }
    }
    assert _extract_dashscope_asr_text(payload) == "first line\nsecond line"


def test_resolve_realtime_models():
    assert _resolve_aliyun_realtime_model("") == "qwen3-asr-flash-realtime"
    assert _resolve_aliyun_realtime_model("qwen3-asr-flash") == "qwen3-asr-flash-realtime"
    assert _resolve_aliyun_realtime_model("qwen3-asr-flash-realtime") == "qwen3-asr-flash-realtime"
    assert _resolve_aliyun_non_realtime_model("qwen3-asr-flash-realtime") == "qwen3-asr-flash"


def test_build_realtime_ws_url():
    assert (
        _build_aliyun_realtime_ws_url("https://dashscope.aliyuncs.com", "qwen3-asr-flash-realtime")
        == "wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=qwen3-asr-flash-realtime"
    )
    assert (
        _build_aliyun_realtime_ws_url("https://dashscope-intl.aliyuncs.com", "qwen3-asr-flash-realtime")
        == "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime?model=qwen3-asr-flash-realtime"
    )


def test_extract_realtime_event_text():
    assert _extract_aliyun_realtime_event_text({"type": "response.text.delta", "delta": "你"}) == "你"
    assert _extract_aliyun_realtime_event_text({"type": "session.finished", "transcript": "你好"}) == "你好"
    assert _extract_aliyun_realtime_event_text({"type": "noop"}) == ""


if __name__ == "__main__":
    run("build aliyun dashscope urls", test_build_aliyun_dashscope_urls)
    run("extract dashscope asr text from chat response", test_extract_dashscope_asr_text_from_chat_response)
    run("extract dashscope asr text from output results", test_extract_dashscope_asr_text_from_output_results)
    run("resolve realtime models", test_resolve_realtime_models)
    run("build realtime ws url", test_build_realtime_ws_url)
    run("extract realtime event text", test_extract_realtime_event_text)
