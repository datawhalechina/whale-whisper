import asyncio
import base64
import json
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Response
from websockets import connect as ws_connect
from websockets.exceptions import ConnectionClosed

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
from app.core.http_utils import normalize_path, resolve_api_key
from app.services.engines import registry, runtime_store
from app.services.engines.health import check_engine_health

router = APIRouter(prefix="/tts", tags=["tts"])

VOLCENGINE_ENGINE_IDS = {"volcengine-speech", "volcengine"}
ALIBABA_ENGINE_IDS = {
    "alibaba-cloud-model-studio-speech",
    "alibaba-cloud-model-studio",
}
VOLCENGINE_TTS_URL = "https://openspeech.bytedance.com/api/v1/tts"
ALIBABA_TTS_WS_CN = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
ALIBABA_TTS_WS_INTL = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference"


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
async def run_tts_engine(request: EngineRunRequest) -> Response:
    engine_id = _resolve_tts_engine_id(request.engine)
    runtime_config = _get_tts_engine_config(engine_id)

    text = _extract_tts_input(request.data)
    if not text:
        raise HTTPException(status_code=400, detail="Missing text input")

    overrides = request.config if isinstance(request.config, dict) else {}
    api_key = _resolve_tts_api_key(runtime_config, overrides)
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing apiKey for TTS provider")

    if engine_id in VOLCENGINE_ENGINE_IDS:
        return await _forward_volcengine_tts(
            runtime_config=runtime_config,
            text=text,
            overrides=overrides,
            api_key=api_key,
        )

    if engine_id in ALIBABA_ENGINE_IDS:
        return await _forward_alibaba_tts(
            engine_id=engine_id,
            runtime_config=runtime_config,
            text=text,
            overrides=overrides,
            api_key=api_key,
        )

    payload = _build_unspeech_payload(
        engine_id=engine_id,
        runtime_config=runtime_config,
        text=text,
        overrides=overrides,
    )

    speech_path = runtime_config.paths.get("speech") if runtime_config.paths else None
    url = runtime_config.base_url.rstrip("/") + normalize_path(speech_path or "/audio/speech")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    headers.update(runtime_config.headers)

    try:
        async with httpx.AsyncClient(timeout=runtime_config.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream TTS connection failed: {exc}",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=_extract_tts_error(response, engine_id),
        )

    media_type = response.headers.get("Content-Type") or "audio/mpeg"
    return Response(content=response.content, media_type=media_type, status_code=response.status_code)


def _resolve_tts_engine_id(engine_id: str) -> str:
    if engine_id == "default":
        default_spec = registry.get_default("tts")
        return default_spec.id if default_spec else ""
    return engine_id


def _get_tts_engine_config(engine_id: str):
    if not engine_id:
        raise HTTPException(status_code=400, detail="Missing engine id")

    config = runtime_store.get("tts", engine_id)
    if not config or not config.base_url:
        raise HTTPException(status_code=404, detail="TTS engine not configured")

    return config


def _extract_tts_input(data: Any) -> str:
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        for key in ("text", "input", "prompt"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _extract_json_error_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()

    detail = payload.get("detail")
    if isinstance(detail, str) and detail.strip():
        return detail.strip()

    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    if isinstance(error, dict):
        nested = error.get("message")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()

    errors = payload.get("errors")
    if isinstance(errors, list) and len(errors) > 0:
        first = errors[0]
        if isinstance(first, dict):
            first_detail = first.get("detail")
            if isinstance(first_detail, str) and first_detail.strip():
                return first_detail.strip()
            first_title = first.get("title")
            if isinstance(first_title, str) and first_title.strip():
                return first_title.strip()

    return ""


def _decorate_tts_error(detail: str, engine_id: Optional[str]) -> str:
    normalized = detail.strip()
    if not normalized:
        return normalized

    lower = normalized.lower()
    if (
        engine_id in VOLCENGINE_ENGINE_IDS
        and "requested grant not found in saas storage" in lower
    ):
        return (
            f"{normalized} (Volcengine credentials mismatch: "
            "check that apiKey is a valid Volcengine Speech token and appId belongs to the same app.)"
        )
    return normalized


def _extract_tts_error(response: httpx.Response, engine_id: Optional[str] = None) -> str:
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            payload = response.json()
            message = _extract_json_error_message(payload)
            if message:
                return _decorate_tts_error(message, engine_id)
            return _decorate_tts_error(json.dumps(payload, ensure_ascii=False), engine_id)
        except Exception:
            pass

    text = response.text.strip()
    if text:
        if text.startswith("{") and text.endswith("}"):
            try:
                nested_payload = json.loads(text)
                nested_message = _extract_json_error_message(nested_payload)
                if nested_message:
                    return _decorate_tts_error(nested_message, engine_id)
            except Exception:
                pass
        return _decorate_tts_error(text, engine_id)
    return f"Upstream TTS request failed: {response.status_code}"


def _read_string(config: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_number(config: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = config.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return float(value.strip())
            except ValueError:
                continue
    return None


def _read_map(config: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    for key in keys:
        value = config.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


def _resolve_tts_api_key(runtime_config, overrides: Dict[str, Any]) -> str:
    override_key = _read_string(overrides, "apiKey", "api_key")
    if override_key:
        return override_key
    return resolve_api_key(runtime_config.api_key_env)


def _resolve_tts_model(engine_id: str, runtime_config, overrides: Dict[str, Any]) -> str:
    model = _read_string(overrides, "model") or str(runtime_config.model or "").strip()
    if not model:
        return ""

    if engine_id in VOLCENGINE_ENGINE_IDS and "/" not in model:
        return f"volcengine/{model}"

    if engine_id in ALIBABA_ENGINE_IDS and "/" not in model:
        return f"alibaba/{model}"

    return model


def _resolve_tts_voice(runtime_config, overrides: Dict[str, Any]) -> str:
    override_voice = _read_string(overrides, "voice")
    if override_voice:
        return override_voice

    default_voice = runtime_config.default_params.get("voice") if runtime_config.default_params else None
    if isinstance(default_voice, str):
        return default_voice.strip()

    return ""


def _build_volcengine_extra_body(overrides: Dict[str, Any]) -> Dict[str, Any]:
    extra_body = {
        **_read_map(overrides, "extraBody"),
        **_read_map(overrides, "extra_body"),
    }

    app = {
        **_read_map(extra_body, "app"),
        **_read_map(overrides, "app"),
    }
    app_id = (
        _read_string(overrides, "appId", "appid", "app_id")
        or _read_string(app, "appId", "appid", "app_id")
    )
    if not app_id:
        raise HTTPException(status_code=400, detail="Missing appId for Volcengine speech")

    app["appid"] = app_id
    extra_body["app"] = app

    audio = {
        **_read_map(extra_body, "audio"),
        **_read_map(overrides, "audio"),
    }
    speed = _read_number(overrides, "speed")
    if speed is not None:
        audio["speed_ratio"] = speed
    if audio:
        extra_body["audio"] = audio

    request = _read_map(overrides, "request")
    if request:
        extra_body["request"] = request

    user = _read_map(overrides, "user")
    if user:
        extra_body["user"] = user

    return extra_body


def _build_unspeech_payload(
    engine_id: str,
    runtime_config,
    text: str,
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    model = _resolve_tts_model(engine_id, runtime_config, overrides)
    if not model:
        raise HTTPException(status_code=400, detail="Missing model")

    voice = _resolve_tts_voice(runtime_config, overrides)
    if not voice:
        raise HTTPException(status_code=400, detail="Missing voice")

    payload: Dict[str, Any] = {
        "model": model,
        "input": text,
        "voice": voice,
    }

    response_format = _read_string(overrides, "response_format", "responseFormat", "format")
    if not response_format and runtime_config.default_params:
        default_format = runtime_config.default_params.get("response_format")
        if isinstance(default_format, str):
            response_format = default_format.strip()
    if response_format:
        payload["response_format"] = response_format

    speed = _read_number(overrides, "speed")
    if speed is not None:
        payload["speed"] = speed

    return payload


def _to_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _resolve_tts_response_format(runtime_config, overrides: Dict[str, Any]) -> str:
    response_format = _read_string(overrides, "response_format", "responseFormat", "format")
    if response_format:
        return response_format
    if runtime_config.default_params:
        default_format = runtime_config.default_params.get("response_format")
        if isinstance(default_format, str) and default_format.strip():
            return default_format.strip()
    return "mp3"


def _resolve_tts_media_type(format_name: str) -> str:
    value = str(format_name or "").strip().lower()
    if value in {"", "mp3"}:
        return "audio/mpeg"
    if value == "wav":
        return "audio/wav"
    if value in {"ogg", "opus", "ogg_opus"}:
        return "audio/ogg"
    if value == "pcm":
        return "audio/pcm"
    return "audio/mpeg"


def _resolve_volcengine_tts_url(runtime_config, overrides: Dict[str, Any]) -> str:
    base_url = str(runtime_config.base_url or "").strip().lower()
    if "openspeech.bytedance.com" in base_url:
        return runtime_config.base_url.rstrip("/")
    return VOLCENGINE_TTS_URL


def _resolve_alibaba_tts_ws_url(runtime_config, overrides: Dict[str, Any]) -> str:
    runtime_base = str(runtime_config.base_url or "").strip()
    normalized_base = runtime_base.lower()

    region = _read_string(overrides, "region").lower()
    if region in {"intl", "sg", "singapore", "intl-singapore", "ap-southeast-1"}:
        return ALIBABA_TTS_WS_INTL

    if "dashscope-intl.aliyuncs.com" in normalized_base:
        return ALIBABA_TTS_WS_INTL
    if "dashscope.aliyuncs.com" in normalized_base:
        return ALIBABA_TTS_WS_CN
    return ALIBABA_TTS_WS_CN


def _normalize_alibaba_provider_model(model: str) -> str:
    normalized = str(model or "").strip()
    if normalized.lower().startswith("alibaba/"):
        return normalized.split("/", 1)[1].strip()
    return normalized


def _build_volcengine_provider_payload(
    runtime_config,
    text: str,
    overrides: Dict[str, Any],
    api_key: str,
) -> Dict[str, Any]:
    voice = _resolve_tts_voice(runtime_config, overrides)
    if not voice:
        raise HTTPException(status_code=400, detail="Missing voice")

    extra_body = _build_volcengine_extra_body(overrides)
    app = _read_map(extra_body, "app")
    audio = _read_map(extra_body, "audio")
    request = _read_map(extra_body, "request")
    user = _read_map(extra_body, "user")

    app_id = _read_string(app, "appid", "app_id", "appId")
    if not app_id:
        raise HTTPException(status_code=400, detail="Missing appId for Volcengine speech")

    cluster = _read_string(app, "cluster") or "volcano_tts"
    request_id = _read_string(request, "reqid", "request_id", "requestId") or str(uuid.uuid4())
    user_id = _read_string(user, "uid", "user_id", "userId") or str(uuid.uuid4())
    operation = _read_string(request, "operation") or "query"
    encoding = _resolve_tts_response_format(runtime_config, overrides)
    speed_ratio = _read_number(audio, "speed_ratio")
    if speed_ratio is None:
        speed_ratio = _read_number(overrides, "speed")
    if speed_ratio is None:
        speed_ratio = 1.0

    payload: Dict[str, Any] = {
        "app": {
            "appid": app_id,
            "token": api_key,
            "cluster": cluster,
        },
        "user": {
            "uid": user_id,
        },
        "audio": {
            "voice_type": voice,
            "encoding": encoding,
            "speed_ratio": speed_ratio,
        },
        "request": {
            "reqid": request_id,
            "text": text,
            "operation": operation,
        },
    }

    for key in (
        "emotion",
        "enable_emotion",
        "emotion_scale",
        "rate",
        "bit_rate",
        "explicit_language",
        "context_language",
        "loudness_ratio",
    ):
        if key in audio and audio[key] is not None:
            payload["audio"][key] = audio[key]

    for key in (
        "text_type",
        "silence_duration",
        "with_timestamp",
        "extra_param",
        "disable_markdown_filter",
        "enable_latex_tn",
        "cache_config",
        "use_cache",
    ):
        if key in request and request[key] is not None:
            payload["request"][key] = request[key]

    return payload


async def _forward_volcengine_tts(
    runtime_config,
    text: str,
    overrides: Dict[str, Any],
    api_key: str,
) -> Response:
    url = _resolve_volcengine_tts_url(runtime_config, overrides)
    payload = _build_volcengine_provider_payload(runtime_config, text, overrides, api_key)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer;{api_key}",
    }
    headers.update(runtime_config.headers)

    try:
        async with httpx.AsyncClient(timeout=runtime_config.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Volcengine TTS connection failed: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=_extract_tts_error(response, "volcengine-speech"),
        )

    try:
        data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid Volcengine TTS response: {exc}") from exc

    audio_base64 = data.get("data") if isinstance(data, dict) else None
    if not isinstance(audio_base64, str) or not audio_base64.strip():
        raise HTTPException(status_code=502, detail="Volcengine TTS returned empty audio payload")

    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Invalid Volcengine audio base64: {exc}") from exc

    media_type = _resolve_tts_media_type(_resolve_tts_response_format(runtime_config, overrides))
    return Response(content=audio_bytes, media_type=media_type, status_code=200)


def _build_alibaba_run_task_event(
    task_id: str,
    model: str,
    text: str,
    voice: str,
    response_format: str,
    sample_rate: int,
    volume: int,
    rate: float,
    pitch: float,
) -> Dict[str, Any]:
    return {
        "header": {
            "task_id": task_id,
            "action": "run-task",
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "tts",
            "function": "SpeechSynthesizer",
            "model": model,
            "input": {},
            "parameters": {
                "text_type": "PlainText",
                "voice": voice,
                "format": response_format,
                "sample_rate": sample_rate,
                "volume": volume,
                "rate": rate,
                "pitch": pitch,
            },
        },
    }


def _build_alibaba_continue_task_event(task_id: str, text: str) -> Dict[str, Any]:
    return {
        "header": {
            "task_id": task_id,
            "action": "continue-task",
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "tts",
            "function": "SpeechSynthesizer",
            "input": {
                "text": text,
            },
        },
    }


def _build_alibaba_finish_task_event(task_id: str) -> Dict[str, Any]:
    return {
        "header": {
            "task_id": task_id,
            "action": "finish-task",
            "streaming": "duplex",
        },
        "payload": {
            "input": {},
        },
    }


async def _forward_alibaba_tts(
    engine_id: str,
    runtime_config,
    text: str,
    overrides: Dict[str, Any],
    api_key: str,
) -> Response:
    model = _normalize_alibaba_provider_model(
        _resolve_tts_model(engine_id, runtime_config, overrides)
    )
    if not model:
        raise HTTPException(status_code=400, detail="Missing model")

    voice = _resolve_tts_voice(runtime_config, overrides)
    if not voice:
        raise HTTPException(status_code=400, detail="Missing voice")

    response_format = _resolve_tts_response_format(runtime_config, overrides)
    sample_rate = _to_int(_read_number(overrides, "sample_rate", "sampleRate"), 22050)
    volume = _to_int(_read_number(overrides, "volume"), 50)
    rate = _to_float(_read_number(overrides, "rate"), 1.0)
    pitch = _to_float(_read_number(overrides, "pitch"), 1.0)
    ws_url = _resolve_alibaba_tts_ws_url(runtime_config, overrides)
    task_id = str(uuid.uuid4())
    audio_binary = bytearray()
    timeout_seconds = max(float(runtime_config.timeout or 60.0), 10.0)

    try:
        async with ws_connect(
            ws_url,
            additional_headers={
                "Authorization": api_key,
                "X-DashScope-DataInspection": "enable",
            },
            open_timeout=min(timeout_seconds, 30.0),
            ping_interval=20,
            ping_timeout=20,
            max_size=2**23,
        ) as ws:
            await ws.send(
                json.dumps(
                    _build_alibaba_run_task_event(
                        task_id=task_id,
                        model=model,
                        text=text,
                        voice=voice,
                        response_format=response_format,
                        sample_rate=sample_rate,
                        volume=volume,
                        rate=rate,
                        pitch=pitch,
                    ),
                    ensure_ascii=False,
                )
            )

            while True:
                raw_message = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)

                if isinstance(raw_message, (bytes, bytearray)):
                    audio_binary.extend(raw_message)
                    continue
                if not isinstance(raw_message, str):
                    continue

                try:
                    event = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue

                header = event.get("header")
                header = header if isinstance(header, dict) else {}
                event_type = str(header.get("event") or "").strip().lower()

                if event_type == "task-started":
                    await ws.send(
                        json.dumps(
                            _build_alibaba_continue_task_event(task_id=task_id, text=text),
                            ensure_ascii=False,
                        )
                    )
                    await ws.send(
                        json.dumps(
                            _build_alibaba_finish_task_event(task_id=task_id),
                            ensure_ascii=False,
                        )
                    )
                    continue

                if event_type == "task-failed":
                    code = str(header.get("error_code") or "").strip()
                    message = str(header.get("error_message") or "Alibaba TTS task failed.").strip()
                    detail = f"{message} ({code})" if code else message
                    raise HTTPException(status_code=400, detail=detail)

                if event_type == "task-finished":
                    break

    except HTTPException:
        raise
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Alibaba TTS timed out") from exc
    except ConnectionClosed as exc:
        raise HTTPException(status_code=502, detail=f"Alibaba TTS websocket closed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Alibaba TTS connection failed: {exc}") from exc

    if len(audio_binary) == 0:
        raise HTTPException(status_code=502, detail="Alibaba TTS returned empty audio payload")

    media_type = _resolve_tts_media_type(response_format)
    return Response(content=bytes(audio_binary), media_type=media_type, status_code=200)
