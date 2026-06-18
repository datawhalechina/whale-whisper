from pathlib import Path
from typing import Any, Dict, List

import yaml

from app.core.settings import get_settings
from app.services.engines import EngineParamSpec, EngineRuntimeConfig, EngineSpec, registry, runtime_store


def bootstrap_engines() -> None:
    config = _load_engine_config()
    if not config:
        return
    _load_engines("llm", config.get("llm") or {})
    _load_engines("tts", config.get("tts") or {})
    _load_engines("asr", config.get("asr") or {})
    _load_engines("agent", config.get("agent") or {}, default_type="agent")


def _load_engine_config() -> Dict[str, Any]:
    base_dir = Path(__file__).resolve().parents[3]
    settings = get_settings()
    path = Path(settings.engine_config_path)
    if not path.is_absolute():
        path = base_dir / path

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _load_engines(
    kind: str,
    config: Dict[str, Any],
    default_type: str = "openai_compat",
) -> None:
    default_id = _as_str(config.get("default"))
    engines = config.get("engines")
    if not isinstance(engines, list):
        return

    for index, engine in enumerate(engines):
        if not isinstance(engine, dict):
            continue

        engine_id = _as_str(engine.get("id"))
        if not engine_id:
            continue

        label = _as_str(engine.get("label")) or engine_id
        description = _as_str(engine.get("description"))
        engine_type = _as_str(engine.get("type")) or default_type
        metadata = _parse_metadata(engine, engine_type)

        params = _parse_params(engine.get("params"))
        spec = EngineSpec(
            id=engine_id,
            label=label,
            description=description,
            params=params,
            metadata=metadata,
        )
        registry.register(kind, spec, default=engine_id == default_id or index == 0)

        base_url = _as_str(engine.get("base_url") or engine.get("baseUrl") or "")
        model = _as_str(engine.get("model") or "")
        api_key_env = _as_str(engine.get("api_key_env") or engine.get("apiKeyEnv"))
        headers = engine.get("headers") if isinstance(engine.get("headers"), dict) else {}
        timeout = _as_float(engine.get("timeout"), 60.0)
        default_params = _parse_defaults(engine, params)

        runtime_store.register(
            kind,
            EngineRuntimeConfig(
                id=engine_id,
                base_url=base_url,
                model=model,
                api_key_env=api_key_env or None,
                headers={str(k): str(v) for k, v in headers.items()},
                timeout=timeout,
                default_params=default_params,
                engine_type=engine_type,
                paths=_parse_paths(engine.get("paths")),
            ),
        )


def _parse_params(value: Any) -> List[EngineParamSpec]:
    if not isinstance(value, list):
        return []
    params: List[EngineParamSpec] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _as_str(item.get("name"))
        param_type = _as_str(item.get("type")) or "string"
        if not name:
            continue
        params.append(
            EngineParamSpec(
                name=name,
                param_type=param_type,
                required=bool(item.get("required", False)),
                default=item.get("default"),
                options=item.get("options") if isinstance(item.get("options"), list) else [],
                description=_as_str(item.get("description")),
            )
        )
    return params


def _parse_defaults(engine: Dict[str, Any], params: List[EngineParamSpec]) -> Dict[str, Any]:
    defaults = engine.get("defaults")
    if not isinstance(defaults, dict):
        defaults = {}
    merged = dict(defaults)
    for param in params:
        if param.default is not None and param.name not in merged:
            merged[param.name] = param.default
    return merged


def _parse_paths(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(k): str(v) for k, v in value.items() if v is not None}


def _parse_metadata(engine: Dict[str, Any], engine_type: str) -> Dict[str, Any]:
    metadata = engine.get("metadata") if isinstance(engine.get("metadata"), dict) else {}
    capabilities = engine.get("capabilities")
    if isinstance(capabilities, dict):
        metadata = {**metadata, "capabilities": capabilities}
    normalized = {str(k): v for k, v in metadata.items()}
    normalized["type"] = engine_type
    return normalized


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _as_float(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback
