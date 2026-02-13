import base64
from typing import Any, AsyncIterator, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.api.engine_schemas import (
    EngineDefaultResponse,
    EngineDesc,
    EngineListResponse,
    EngineParam,
    EngineParamsResponse,
    EngineRunRequest,
    HealthResponse,
    VoiceDesc,
    VoiceListResponse,
)
from app.services.engines import registry, runtime_store
from app.services.engines.health import check_engine_health
from app.core.http_utils import normalize_path, resolve_api_key, sanitize_config

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


@router.post("/engines")
async def run_tts_engine(request: EngineRunRequest) -> StreamingResponse:
    engine_id = _resolve_engine_id(request.engine)
    config = _get_engine_config(engine_id)
    text = _coerce_text(request.data)
    if not text:
        raise HTTPException(status_code=400, detail="Missing text input")

    engine_type = (config.engine_type or "openai_compat").lower()
    overrides = request.config if isinstance(request.config, dict) else {}

    if engine_type in {"dify_tts", "dify"}:
        stream = await _stream_dify_tts(config, text, overrides)
        return StreamingResponse(stream, media_type="audio/mpeg")

    if engine_type in {"coze_tts", "coze"}:
        stream = await _stream_coze_tts(config, text, overrides)
        return StreamingResponse(stream, media_type="audio/mpeg")

    base_url_override, api_key_override = _resolve_connection_overrides(overrides)
    payload: Dict[str, Any] = {"model": config.model, "input": text}
    payload.update(config.default_params)
    payload.update(sanitize_config(overrides))

    if "voice" not in payload:
        raise HTTPException(status_code=400, detail="Missing voice for TTS")

    resolved_base_url = (base_url_override or config.base_url).rstrip("/")
    if _is_dashscope_compatible_base(resolved_base_url) and _is_realtime_tts_model(
        payload.get("model")
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "DashScope realtime TTS models are not supported by this endpoint. "
                "Please switch to a non-realtime qwen3-tts model, or use DashScope realtime API."
            ),
        )

    speech_path = config.paths.get("speech") if config.paths else None
    path = normalize_path(speech_path or "/audio/speech")
    url = resolved_base_url + path

    headers = {"Content-Type": "application/json"}
    headers.update(config.headers)
    api_key = api_key_override or resolve_api_key(config.api_key_env)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    media_type = _audio_media_type(payload.get("response_format") or payload.get("format"))
    try:
        content = await _request_tts_bytes(url, headers, payload, timeout=config.timeout)
        return Response(content=content, media_type=media_type)
    except HTTPException as exc:
        if (
            exc.status_code == 404
            and _is_dashscope_compatible_base(resolved_base_url)
            and engine_type not in {"dify_tts", "coze_tts", "dify", "coze"}
        ):
            fallback_url = _dashscope_multimodal_tts_url(resolved_base_url)
            content, media_type_override = await _request_dashscope_tts_bytes(
                fallback_url,
                headers,
                payload,
                timeout=config.timeout,
            )
            return Response(content=content, media_type=media_type_override or media_type)
        raise


def _resolve_engine_id(engine_id: str) -> str:
    if engine_id == "default":
        default_spec = registry.get_default("tts")
        return default_spec.id if default_spec else ""
    return engine_id


def _get_engine_config(engine_id: str):
    if not engine_id:
        raise HTTPException(status_code=400, detail="Missing engine id")
    config = runtime_store.get("tts", engine_id)
    if not config or not config.base_url:
        raise HTTPException(status_code=404, detail="TTS engine not configured")
    engine_type = (config.engine_type or "openai_compat").lower()
    if engine_type not in {"dify_tts", "coze_tts", "dify", "coze"} and not config.model:
        raise HTTPException(status_code=400, detail="TTS engine missing model")
    return config


def _coerce_text(data: Any) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        text = data.get("text") or data.get("input") or data.get("prompt")
        if isinstance(text, str):
            return text
    return ""


def _resolve_connection_overrides(config: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    base_url = config.get("base_url") or config.get("baseUrl")
    api_key = config.get("api_key") or config.get("apiKey")
    return (
        str(base_url).strip() if isinstance(base_url, str) and base_url.strip() else None,
        str(api_key).strip() if isinstance(api_key, str) and api_key.strip() else None,
    )


def _audio_media_type(format_name: Optional[str]) -> str:
    if not format_name:
        return "audio/mpeg"
    value = str(format_name).lower()
    if value == "wav":
        return "audio/wav"
    if value == "opus":
        return "audio/opus"
    if value == "aac":
        return "audio/aac"
    if value == "flac":
        return "audio/flac"
    return "audio/mpeg"


def _is_dashscope_compatible_base(base_url: str) -> bool:
    value = (base_url or "").lower()
    return "dashscope" in value and "/compatible-mode/" in value


def _is_realtime_tts_model(model_name: Any) -> bool:
    if not isinstance(model_name, str):
        return False
    return "realtime" in model_name.lower()


def _dashscope_multimodal_tts_url(base_url: str) -> str:
    cleaned = (base_url or "").rstrip("/")
    if "/compatible-mode/" in cleaned:
        cleaned = cleaned.split("/compatible-mode/")[0]
    return f"{cleaned}/api/v1/services/aigc/multimodal-generation/generation"


async def _create_tts_stream(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    *,
    timeout: float,
) -> AsyncIterator[bytes]:
    client = httpx.AsyncClient(timeout=timeout)
    try:
        response = await client.stream("POST", url, headers=headers, json=payload).__aenter__()
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if response.status_code >= 400:
        detail = await response.aread()
        await response.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=response.status_code,
            detail=detail.decode("utf-8", errors="ignore") or response.reason_phrase,
        )

    async def iterator() -> AsyncIterator[bytes]:
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return iterator()


async def _request_tts_bytes(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    *,
    timeout: float,
) -> bytes:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text or response.reason_phrase,
        )

    return response.content


def _extract_dashscope_audio_data(body: Dict[str, Any]) -> Optional[str]:
    output = body.get("output")
    if isinstance(output, dict):
        audio = output.get("audio")
        if isinstance(audio, dict):
            data = audio.get("data")
            if isinstance(data, str) and data.strip():
                return data
    return None


def _extract_dashscope_audio_url(body: Dict[str, Any]) -> Optional[str]:
    output = body.get("output")
    if isinstance(output, dict):
        audio = output.get("audio")
        if isinstance(audio, dict):
            url = audio.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
    return None


def _build_dashscope_tts_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    input_payload: Dict[str, Any] = {
        "text": str(payload.get("input") or ""),
    }
    voice = payload.get("voice")
    if isinstance(voice, str) and voice.strip():
        input_payload["voice"] = voice.strip()

    for key in ("language_type", "instructions", "optimize_instructions"):
        if key in payload and payload[key] is not None:
            input_payload[key] = payload[key]

    return {
        "model": payload.get("model"),
        "input": input_payload,
    }


async def _request_dashscope_tts_bytes(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    *,
    timeout: float,
) -> tuple[bytes, Optional[str]]:
    request_payload = _build_dashscope_tts_payload(payload)
    request_headers = dict(headers)
    request_headers["Content-Type"] = "application/json"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=request_headers, json=request_payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text or response.reason_phrase,
        )

    data = response.json() if response.content else {}
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Invalid DashScope TTS response")

    audio_b64 = _extract_dashscope_audio_data(data)
    if audio_b64:
        try:
            return base64.b64decode(audio_b64), None
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Invalid base64 audio data: {exc}") from exc

    audio_url = _extract_dashscope_audio_url(data)
    if not audio_url:
        raise HTTPException(
            status_code=502,
            detail="DashScope TTS response missing audio output",
        )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            audio_response = await client.get(audio_url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if audio_response.status_code >= 400:
        raise HTTPException(
            status_code=audio_response.status_code,
            detail=audio_response.text or audio_response.reason_phrase,
        )

    media_type = (audio_response.headers.get("content-type") or "").split(";")[0].strip() or None
    return audio_response.content, media_type


def _merge_params(config, overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(config.default_params or {})
    merged.update(sanitize_config(overrides))
    return merged


async def _stream_dify_tts(
    config,
    text: str,
    overrides: Dict[str, Any],
) -> AsyncIterator[bytes]:
    params = _merge_params(config, overrides)
    api_server = params.get("api_server") or config.base_url
    api_key = params.get("api_key") or resolve_api_key(config.api_key_env)
    username = params.get("username") or params.get("user")

    if not api_server:
        return
    if not api_key:
        return
    if not username:
        return

    payload = {"text": text, "user": username}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    headers.update(config.headers)

    speech_path = config.paths.get("speech") if config.paths else None
    path = normalize_path(speech_path or "/text-to-audio")
    url = api_server.rstrip("/") + path

    return await _create_tts_stream(url, headers, payload, timeout=config.timeout)


async def _stream_coze_tts(
    config,
    text: str,
    overrides: Dict[str, Any],
) -> AsyncIterator[bytes]:
    params = _merge_params(config, overrides)
    api_base = params.get("api_base") or config.base_url
    token = params.get("token") or resolve_api_key(config.api_key_env)
    bot_id = params.get("bot_id")
    response_format = params.get("response_format") or "mp3"
    sample_rate = params.get("sample_rate") or 16000

    if not api_base or not token or not bot_id:
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    headers.update(config.headers)

    voice_id = await _fetch_coze_voice_id(
        api_base,
        headers,
        bot_id,
        config.paths.get("bot") if config.paths else None,
        timeout=config.timeout,
    )
    if not voice_id:
        return

    payload = {
        "input": text,
        "voice_id": voice_id,
        "speed": params.get("speed") or 1.0,
        "response_format": response_format,
        "sample_rate": sample_rate,
    }

    speech_path = config.paths.get("speech") if config.paths else None
    path = normalize_path(speech_path or "/v1/audio/speech")
    url = api_base.rstrip("/") + path

    return await _create_tts_stream(url, headers, payload, timeout=config.timeout)


async def _fetch_coze_voice_id(
    api_base: str,
    headers: Dict[str, str],
    bot_id: str,
    path_template: Optional[str],
    *,
    timeout: float,
) -> Optional[str]:
    path = path_template or "/v1/bots/{bot_id}"
    if "{bot_id}" in path:
        path = path.replace("{bot_id}", bot_id)
    path = normalize_path(path)
    url = api_base.rstrip("/") + path
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    voice_info = (data.get("data") or {}).get("voice_info_list") or []
    if not voice_info:
        return None
    voice_id = voice_info[0].get("voice_id")
    if isinstance(voice_id, str) and voice_id:
        return voice_id
    return None
