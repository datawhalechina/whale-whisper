import json
from typing import Any, Dict, Iterable

from .types import AgentEvent


def sse_event(event: AgentEvent) -> str:
    payload = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.event}\ndata: {payload}\n\n"


def sse_error(message: str) -> Iterable[str]:
    return [sse_event(AgentEvent(event="error", data={"message": message}))]


def merge_params(defaults: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(defaults or {})
    if overrides:
        merged.update(overrides)
    return merged


def coerce_text(data: Any) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        text = data.get("text") or data.get("input") or data.get("prompt")
        if isinstance(text, str):
            return text
    return ""


def coerce_bool(value: Any, default: bool = False) -> bool:
    """Safely coerce a value to boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in {"1", "true", "yes", "on"}:
            return True
        if lower in {"0", "false", "no", "off", ""}:
            return False
        return bool(value)
    return default


def coerce_json_dict(value: Any) -> Dict[str, Any]:
    """Convert string/dict to dict, handling JSON strings."""
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}
