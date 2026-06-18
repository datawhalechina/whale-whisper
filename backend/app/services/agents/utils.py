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
