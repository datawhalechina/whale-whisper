import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.services.engines import registry, runtime_store  # noqa: E402
from app.services.engines.loader import _load_engines  # noqa: E402


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def _reset_registry():
    for kind in ("llm", "tts", "asr", "agent"):
        registry._engines[kind] = {}
        registry._defaults[kind] = None


def _sample_config(engine_id: str = "test-engine"):
    return {
        "default": engine_id,
        "engines": [
            {
                "id": engine_id,
                "label": "Test Engine",
                "description": "desc",
                "type": "openai_compat",
                "base_url": "https://example.com",
                "model": "gpt-test",
                "api_key_env": "TEST_KEY",
                "headers": {"X-Custom": "1"},
                "timeout": 30,
                "params": [{"name": "temperature", "type": "number", "default": 0.7}],
                "defaults": {"user": "whale"},
                "paths": {"chat": "/v1/chat"},
            }
        ],
    }


def test_load_llm_engine_registers_spec_and_runtime():
    _reset_registry()
    _load_engines("llm", _sample_config("llm-1"))

    default_spec = registry.get_default("llm")
    assert default_spec is not None
    assert default_spec.id == "llm-1"
    assert default_spec.label == "Test Engine"
    assert default_spec.description == "desc"

    runtime = runtime_store.get("llm", "llm-1")
    assert runtime is not None
    assert runtime.base_url == "https://example.com"
    assert runtime.model == "gpt-test"
    assert runtime.api_key_env == "TEST_KEY"
    assert runtime.timeout == 30.0
    assert runtime.headers == {"X-Custom": "1"}
    assert runtime.default_params == {"user": "whale", "temperature": 0.7}
    assert runtime.paths == {"chat": "/v1/chat"}


def test_load_agent_engine_defaults_to_agent_type():
    _reset_registry()
    # agent config without explicit "type" should fall back to "agent"
    config = {
        "engines": [{"id": "agent-1", "base_url": "https://agent.example.com"}],
    }
    _load_engines("agent", config, default_type="agent")

    runtime = runtime_store.get("agent", "agent-1")
    assert runtime is not None
    assert runtime.engine_type == "agent"
    spec = registry.get("agent", "agent-1")
    assert spec is not None
    assert spec.metadata["type"] == "agent"


def test_load_engine_first_becomes_default_without_explicit_default():
    _reset_registry()
    config = {
        "engines": [
            {"id": "first", "type": "openai_compat"},
            {"id": "second", "type": "openai_compat"},
        ],
    }
    _load_engines("tts", config)

    assert registry.get_default("tts").id == "first"


def test_load_engines_skips_invalid_entries():
    _reset_registry()
    config = {
        "engines": [
            "not-a-dict",
            {"id": "", "type": "openai_compat"},  # missing id, skipped
            {"id": "valid", "type": "openai_compat"},
        ],
    }
    _load_engines("asr", config)

    assert registry.get("asr", "valid") is not None
    assert registry.get("asr", "") is None


def test_load_engines_noop_when_engines_not_list():
    _reset_registry()
    _load_engines("llm", {"default": "x", "engines": "not-a-list"})
    assert registry.get_default("llm") is None


if __name__ == "__main__":
    run("load llm engine registers spec and runtime", test_load_llm_engine_registers_spec_and_runtime)
    run("load agent engine defaults to agent type", test_load_agent_engine_defaults_to_agent_type)
    run("load engine first becomes default without explicit default", test_load_engine_first_becomes_default_without_explicit_default)
    run("load engines skips invalid entries", test_load_engines_skips_invalid_entries)
    run("load engines noop when engines not list", test_load_engines_noop_when_engines_not_list)
