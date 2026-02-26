from fastapi import APIRouter, HTTPException

from app.api.engine_schemas import (
    EngineDefaultResponse,
    EngineDesc,
    EngineListResponse,
    EngineParam,
    EngineParamsResponse,
    HealthResponse,
    VoiceDesc,
    VoiceListResponse,
)
from app.services.engines import registry, runtime_store
from app.services.engines.health import check_engine_health

router = APIRouter(prefix="/tts", tags=["tts"])


@router.get("/engines", response_model=EngineListResponse)
async def list_tts_engines() -> EngineListResponse:
    engines = [EngineDesc.from_spec(spec) for spec in registry.list("tts")]
    return EngineListResponse(engines=engines)


@router.get("/engines/default", response_model=EngineDefaultResponse)
async def get_default_tts_engine() -> EngineDefaultResponse:
    spec = registry.get_default("tts")
    engine = EngineDesc.from_spec(spec) if spec else None
    return EngineDefaultResponse(engine=engine)


@router.get("/engines/{engine}/params", response_model=EngineParamsResponse)
async def get_tts_engine_params(engine: str) -> EngineParamsResponse:
    params = [EngineParam.from_spec(p) for p in registry.get_params("tts", engine)]
    return EngineParamsResponse(params=params)


@router.get("/engines/{engine}/voices", response_model=VoiceListResponse)
async def get_tts_engine_voices(engine: str) -> VoiceListResponse:
    voices = []
    for voice in registry.get_voices("tts", engine):
        if isinstance(voice, dict):
            if "id" in voice and "label" in voice:
                voices.append(VoiceDesc(**voice))
    return VoiceListResponse(voices=voices)


@router.get("/engines/{engine}/health", response_model=HealthResponse)
async def get_tts_engine_health(engine: str) -> HealthResponse:
    config = runtime_store.get("tts", engine)
    if not config:
        raise HTTPException(status_code=404, detail="Engine not found")
    return HealthResponse(**await check_engine_health(config))
