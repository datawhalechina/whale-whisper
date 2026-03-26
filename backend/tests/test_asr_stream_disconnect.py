import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.api.asr import (  # noqa: E402
    _is_disconnect_receive_runtime_error,
    _is_websocket_disconnect_message,
)


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def test_detects_disconnect_message_frame():
    assert _is_websocket_disconnect_message({"type": "websocket.disconnect"}) is True
    assert _is_websocket_disconnect_message({"type": "websocket.receive"}) is False
    assert _is_websocket_disconnect_message({}) is False


def test_detects_disconnect_runtime_error_message():
    exc = RuntimeError('Cannot call "receive" once a disconnect message has been received.')
    assert _is_disconnect_receive_runtime_error(exc) is True


def test_ignores_unrelated_runtime_errors():
    exc = RuntimeError("boom")
    assert _is_disconnect_receive_runtime_error(exc) is False


if __name__ == "__main__":
    run("detect disconnect message frame", test_detects_disconnect_message_frame)
    run(
        "detect disconnect runtime error message",
        test_detects_disconnect_runtime_error_message,
    )
    run("ignore unrelated runtime errors", test_ignores_unrelated_runtime_errors)
