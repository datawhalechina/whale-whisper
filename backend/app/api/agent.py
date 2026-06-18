from dataclasses import replace
from typing import Any, Dict, Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.engine_schemas import (
    ConversationRequest,
    ConversationResponse,
    EngineDefaultResponse,
    EngineDesc,
    EngineListResponse,
    EngineParam,
    EngineParamsResponse,
    EngineRunRequest,
    HealthResponse,
)
from app.services.engines import registry
from app.services.engines import runtime_store
from app.services.engines.health import check_engine_health
from app.services.agents import (
    AgentContext,
    AgentEvent,
    build_agent_handler,
    coerce_text,
    sse_error,
    sse_event,
)
from app.services.memory import MemoryScope, MemoryService

router = APIRouter(prefix="/agent", tags=["agent"])
memory_service = MemoryService()


@router.get("/engines", response_model=EngineListResponse)
async def list_agent_engines() -> EngineListResponse:
    engines = [EngineDesc.from_spec(spec) for spec in registry.list("agent")]
    return EngineListResponse(engines=engines)


@router.get("/engines/default", response_model=EngineDefaultResponse)
async def get_default_agent_engine() -> EngineDefaultResponse:
    spec = registry.get_default("agent")
    engine = EngineDesc.from_spec(spec) if spec else None
    return EngineDefaultResponse(engine=engine)


@router.get("/engines/{engine}/params", response_model=EngineParamsResponse)
async def get_agent_engine_params(engine: str) -> EngineParamsResponse:
    params = [EngineParam.from_spec(p) for p in registry.get_params("agent", engine)]
    return EngineParamsResponse(params=params)


@router.get("/engines/{engine}/health", response_model=HealthResponse)
async def get_agent_engine_health(engine: str) -> HealthResponse:
    config = runtime_store.get("agent", engine)
    if not config:
        raise HTTPException(status_code=404, detail="Engine not found")
    base_url = _resolve_health_base_url(config, {})
    runtime = replace(config, base_url=base_url) if base_url else config
    return HealthResponse(
        **await check_engine_health(
            runtime,
            fallback_path="/health",
            base_url_override=base_url or None,
        )
    )


class AgentHealthRequest(BaseModel):
    config: Dict[str, Any] = Field(default_factory=dict)


@router.post("/engines/{engine}/health", response_model=HealthResponse)
async def post_agent_engine_health(engine: str, request: AgentHealthRequest) -> HealthResponse:
    config = runtime_store.get("agent", engine)
    if not config:
        raise HTTPException(status_code=404, detail="Engine not found")

    overrides = request.config if isinstance(request.config, dict) else {}
    base_url = _resolve_health_base_url(config, overrides)
    api_key = overrides.get("api_key") or overrides.get("apiKey")
    runtime = replace(config, base_url=base_url) if base_url else config

    return HealthResponse(
        **await check_engine_health(
            runtime,
            fallback_path="/health",
            base_url_override=base_url or None,
            api_key_override=str(api_key) if api_key else None,
        )
    )


@router.post("/engines/{engine}", response_model=ConversationResponse)
async def create_agent_conversation(engine: str, request: ConversationRequest) -> ConversationResponse:
    engine_id = _resolve_engine_id(engine)
    runtime = _get_engine_config(engine_id)
    handler = build_agent_handler(runtime)
    params = request.data or {}
    conversation_id = await handler.create_conversation(AgentContext(runtime=runtime, params=params))
    if not conversation_id:
        raise HTTPException(status_code=400, detail="Agent failed to create conversation")
    return ConversationResponse(conversationId=str(conversation_id))


@router.post("/engines")
async def run_agent_engine(request: EngineRunRequest) -> StreamingResponse:
    engine_id = _resolve_engine_id(request.engine)
    runtime = _get_engine_config(engine_id)
    text = coerce_text(request.data)
    if not text:
        return StreamingResponse(sse_error("Missing text input"), media_type="text/event-stream")

    spec = registry.get("agent", engine_id)
    handler = build_agent_handler(runtime)
    params = request.config if isinstance(request.config, dict) else {}
    memory_bridge = _coerce_bool(params.get("memory_bridge") or params.get("memoryBridge"))
    params = _strip_agent_config(params)
    if memory_bridge:
        scope = _extract_memory_scope(request.data)
        context_block = memory_service.build_context(scope, include_session_messages=False)
        text = memory_service.build_prompt(context=context_block, user_text=text)
    context = AgentContext(runtime=runtime, params=params)

    async def stream() -> Iterator[str]:
        try:
            capabilities = _resolve_capabilities(spec)
            if capabilities:
                yield sse_event(AgentEvent(event="agent.capabilities", data=capabilities))
            async for event in handler.stream(context, text):
                yield sse_event(event)
        except Exception as exc:
            for chunk in sse_error(str(exc)):
                yield chunk

    return StreamingResponse(stream(), media_type="text/event-stream")


def _resolve_engine_id(engine_id: str) -> str:
    if engine_id == "default":
        default_spec = registry.get_default("agent")
        return default_spec.id if default_spec else ""
    return engine_id


def _get_engine_config(engine_id: str):
    if not engine_id:
        raise HTTPException(status_code=400, detail="Missing engine id")
    config = runtime_store.get("agent", engine_id)
    if not config or not config.base_url:
        raise HTTPException(status_code=404, detail="Agent engine not configured")
    return config


def _resolve_health_base_url(config, overrides: Dict[str, Any]) -> str:
    base_url = (
        overrides.get("api_server")
        or overrides.get("base_url")
        or overrides.get("baseUrl")
        or config.base_url
    )
    if not base_url:
        return ""
    normalized = str(base_url).rstrip("/")
    health_path = config.paths.get("health") if config.paths else "/health"
    health_path = str(health_path)
    if not health_path.startswith("/"):
        health_path = f"/{health_path}"
    if normalized.endswith("/v1") and not health_path.startswith("/v1"):
        normalized = normalized[:-3]
        normalized = normalized.rstrip("/")
    return normalized


def _extract_memory_scope(data: Any) -> MemoryScope:
    if isinstance(data, dict):
        session_id = data.get("session_id") or data.get("sessionId") or "default"
        user_id = data.get("user_id") or "default"
        profile_id = data.get("profile_id") or "default"
        return MemoryScope(
            session_id=str(session_id or "default"),
            user_id=str(user_id or "default"),
            profile_id=str(profile_id or "default"),
        )
    return MemoryScope(session_id="default", user_id="default", profile_id="default")


def _strip_agent_config(config: Dict[str, Any]) -> Dict[str, Any]:
    blocked = {"memory_bridge", "memoryBridge"}
    return {key: value for key, value in config.items() if key not in blocked}


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _resolve_capabilities(spec) -> Dict[str, Any]:
    if not spec or not isinstance(spec.metadata, dict):
        return {}
    metadata = spec.metadata
    capabilities = {}
    raw_caps = metadata.get("capabilities")
    if isinstance(raw_caps, dict):
        capabilities.update(raw_caps)
    raw_action = metadata.get("action_tokens")
    if isinstance(raw_action, bool):
        capabilities.setdefault("action_tokens", raw_action)
    return capabilities
