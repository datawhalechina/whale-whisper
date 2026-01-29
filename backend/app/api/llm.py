import json
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.engine_schemas import (
    EngineDefaultResponse,
    EngineDesc,
    EngineListResponse,
    EngineParam,
    EngineParamsResponse,
    EngineRunRequest,
    HealthResponse,
)
from app.services.engines import registry, runtime_store
from app.services.engines.health import check_engine_health
from app.core.http_utils import resolve_api_key, sanitize_config

router = APIRouter(prefix="/llm", tags=["llm"])


class LLMHealthRequest(BaseModel):
    config: Dict[str, Any] = Field(default_factory=dict)


def _sse_error(message: str) -> Iterator[str]:
    payload = json.dumps({"message": message})
    yield f"event: error\ndata: {payload}\n\n"


@router.get("/engines", response_model=EngineListResponse)
async def list_llm_engines() -> EngineListResponse:
    engines = [EngineDesc.from_spec(spec) for spec in registry.list("llm")]
    return EngineListResponse(engines=engines)


@router.get("/engines/default", response_model=EngineDefaultResponse)
async def get_default_llm_engine() -> EngineDefaultResponse:
    spec = registry.get_default("llm")
    engine = EngineDesc.from_spec(spec) if spec else None
    return EngineDefaultResponse(engine=engine)


@router.get("/engines/{engine}/params", response_model=EngineParamsResponse)
async def get_llm_engine_params(engine: str) -> EngineParamsResponse:
    params = [EngineParam.from_spec(p) for p in registry.get_params("llm", engine)]
    return EngineParamsResponse(params=params)


@router.get("/engines/{engine}/health", response_model=HealthResponse)
async def get_llm_engine_health(engine: str) -> HealthResponse:
    config = runtime_store.get("llm", engine)
    if not config:
        raise HTTPException(status_code=404, detail="Engine not found")
    return HealthResponse(**await check_engine_health(config))


@router.post("/engines/{engine}/health", response_model=HealthResponse)
async def post_llm_engine_health(engine: str, request: LLMHealthRequest) -> HealthResponse:
    config = runtime_store.get("llm", engine)
    if not config:
        raise HTTPException(status_code=404, detail="Engine not found")
    
    overrides = request.config if isinstance(request.config, dict) else {}
    base_url = overrides.get("base_url") or overrides.get("baseUrl")
    api_key = overrides.get("api_key") or overrides.get("apiKey")
    
    return HealthResponse(
        **await check_engine_health(
            config,
            base_url_override=str(base_url) if base_url else None,
            api_key_override=str(api_key) if api_key else None,
        )
    )


@router.post("/engines")
async def run_llm_engine(request: EngineRunRequest) -> StreamingResponse:
    engine_id = request.engine
    if engine_id == "default":
        default_spec = registry.get_default("llm")
        engine_id = default_spec.id if default_spec else ""
    if not engine_id:
        return StreamingResponse(_sse_error("Missing engine id"), media_type="text/event-stream")

    config = runtime_store.get("llm", engine_id)
    if not config or not config.base_url:
        return StreamingResponse(
            _sse_error(f"LLM engine '{engine_id}' not configured"),
            media_type="text/event-stream",
        )
    if not config.model:
        return StreamingResponse(
            _sse_error(f"LLM engine '{engine_id}' missing model"),
            media_type="text/event-stream",
        )

    messages = _coerce_messages(request.data)
    if not messages:
        return StreamingResponse(
            _sse_error("Missing chat messages"),
            media_type="text/event-stream",
        )

    payload: Dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "stream": True,
    }
    payload.update(config.default_params)
    payload.update(sanitize_config(request.config))

    headers = {"Content-Type": "application/json"}
    headers.update(config.headers)
    api_key = resolve_api_key(config.api_key_env)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    chat_path = config.paths.get("chat") if config.paths else None
    stream = _stream_openai_compat(
        config.base_url,
        headers,
        payload,
        timeout=config.timeout,
        path=chat_path,
    )
    return StreamingResponse(stream, media_type="text/event-stream")


def _coerce_messages(data: Any) -> List[Dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, str):
        return [{"role": "user", "content": data}]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        messages = data.get("messages")
        if isinstance(messages, list):
            return [item for item in messages if isinstance(item, dict)]
        text = data.get("text") or data.get("prompt")
        if isinstance(text, str):
            return [{"role": "user", "content": text}]
    return []


async def _stream_openai_compat(
    base_url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    *,
    timeout: float,
    path: Optional[str] = None,
) -> AsyncIterator[str]:
    path = path or "/chat/completions"
    if not path.startswith("/"):
        path = f"/{path}"
    url = base_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line == "":
                        yield "\n"
                    else:
                        yield f"{line}\n"
    except httpx.HTTPError as exc:
        message = str(exc)
        for chunk in _sse_error(message):
            yield chunk
