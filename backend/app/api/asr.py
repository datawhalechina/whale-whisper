import base64
import asyncio
import io
import json
import time
import wave
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
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
)
from app.services.engines import registry, runtime_store
from app.services.engines.health import check_engine_health
from app.core.http_utils import normalize_path, resolve_api_key, sanitize_config

router = APIRouter(prefix="/asr", tags=["asr"])
ASR_BLOCKED_CONFIG_KEYS = frozenset(
    {
        "api_key",
        "apiKey",
        "base_url",
        "baseUrl",
        "engine",
        "filename",
        "file_name",
        "file",
        "content_type",
        "mime_type",
    }
)


ALIYUN_ASR_ENGINE_TYPES = frozenset(
    {"aliyun_nls_asr", "aliyun_nls", "aliyun_dashscope_asr", "aliyun_dashscope"}
)


@router.get("/engines", response_model=EngineListResponse)
async def list_asr_engines() -> EngineListResponse:
    engines = [EngineDesc.from_spec(spec) for spec in registry.list("asr")]
    return EngineListResponse(engines=engines)


@router.get("/engines/default", response_model=EngineDefaultResponse)
async def get_default_asr_engine() -> EngineDefaultResponse:
    spec = registry.get_default("asr")
    engine = EngineDesc.from_spec(spec) if spec else None
    return EngineDefaultResponse(engine=engine)


@router.get("/engines/{engine}/params", response_model=EngineParamsResponse)
async def get_asr_engine_params(engine: str) -> EngineParamsResponse:
    params = [EngineParam.from_spec(p) for p in registry.get_params("asr", engine)]
    return EngineParamsResponse(params=params)


@router.get("/engines/{engine}/health", response_model=HealthResponse)
async def get_asr_engine_health(engine: str) -> HealthResponse:
    config = runtime_store.get("asr", engine)
    if not config:
        raise HTTPException(status_code=404, detail="Engine not found")
    return HealthResponse(**await check_engine_health(config))


@router.post("/engines")
async def run_asr_engine(request: EngineRunRequest) -> dict:
    engine_id = _resolve_engine_id(request.engine)
    config = _get_engine_config(engine_id)
    audio_bytes = _extract_audio_bytes(request.data)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Missing audio data")
    overrides = request.config if isinstance(request.config, dict) else {}
    filename, content_type = _resolve_file_meta(overrides)
    engine_type = (config.engine_type or "openai_compat").lower()
    if engine_type in {"dify_asr", "dify"}:
        return await _forward_dify_transcription(config, audio_bytes, overrides, filename, content_type)
    if engine_type in {"coze_asr", "coze"}:
        return await _forward_coze_transcription(config, audio_bytes, overrides, filename, content_type)
    if engine_type in ALIYUN_ASR_ENGINE_TYPES:
        return await _forward_aliyun_dashscope_transcription(config, audio_bytes, overrides, filename, content_type)
    response = await _forward_transcription(config, audio_bytes, overrides, filename, content_type)
    return response


@router.post("/engines/file")
async def run_asr_engine_file(
    file: UploadFile = File(...),
    engine: str = "default",
) -> dict:
    engine_id = _resolve_engine_id(engine)
    config = _get_engine_config(engine_id)
    audio_bytes = await file.read()
    filename = file.filename or "audio.wav"
    content_type = file.content_type or "application/octet-stream"
    engine_type = (config.engine_type or "openai_compat").lower()
    if engine_type in {"dify_asr", "dify"}:
        return await _forward_dify_transcription(config, audio_bytes, {}, filename, content_type)
    if engine_type in {"coze_asr", "coze"}:
        return await _forward_coze_transcription(config, audio_bytes, {}, filename, content_type)
    if engine_type in ALIYUN_ASR_ENGINE_TYPES:
        return await _forward_aliyun_dashscope_transcription(config, audio_bytes, {}, filename, content_type)
    response = await _forward_transcription(config, audio_bytes, {}, filename, content_type)
    return response


@router.websocket("/engines/stream")
async def run_asr_engine_stream(websocket: WebSocket) -> None:
    await websocket.accept()

    engine_id = "default"
    engine_config = None
    engine_type = ""
    overrides: Dict[str, Any] = {}
    sample_rate = 16000
    channels = 1
    buffer = bytearray()
    aliyun_realtime_session: Optional["AliyunRealtimeSession"] = None
    has_audio = False

    try:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                break
            except RuntimeError as exc:
                if _is_disconnect_receive_runtime_error(exc):
                    break
                raise

            if _is_websocket_disconnect_message(message):
                break

            if message.get("text") is not None:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "Invalid JSON payload."})
                    continue

                message_type = payload.get("type")
                if message_type == "start":
                    if aliyun_realtime_session is not None:
                        await _close_aliyun_realtime_session(aliyun_realtime_session)
                        aliyun_realtime_session = None
                    engine_id = payload.get("engine", "default")
                    engine_id = _resolve_engine_id(engine_id)
                    engine_config = _get_engine_config(engine_id)
                    engine_type = (engine_config.engine_type or "openai_compat").lower()
                    overrides = payload.get("config") if isinstance(payload.get("config"), dict) else {}
                    sample_rate = int(payload.get("sample_rate") or payload.get("sampleRate") or 16000)
                    channels = int(payload.get("channels") or 1)
                    buffer = bytearray()
                    has_audio = False
                    if engine_type in ALIYUN_ASR_ENGINE_TYPES:
                        aliyun_realtime_session = await _open_aliyun_realtime_session(
                            config=engine_config,
                            overrides=overrides,
                            sample_rate=sample_rate,
                        )
                    await websocket.send_json({"type": "ready"})
                elif message_type == "stop":
                    if engine_config is None:
                        await websocket.send_json({"type": "error", "error": "Engine not initialized."})
                        continue
                    if not has_audio:
                        await websocket.send_json({"type": "error", "error": "Missing audio data."})
                        continue

                    if engine_type in ALIYUN_ASR_ENGINE_TYPES:
                        if aliyun_realtime_session is None:
                            await websocket.send_json(
                                {"type": "error", "error": "Alibaba Bailian realtime session is not initialized."}
                            )
                            continue
                        response = await _finish_aliyun_realtime_session(
                            aliyun_realtime_session,
                            overrides,
                        )
                        await _close_aliyun_realtime_session(aliyun_realtime_session)
                        aliyun_realtime_session = None
                        has_audio = False
                        await websocket.send_json({"type": "result", "data": response})
                    else:
                        pcm_bytes = bytes(buffer)
                        wav_bytes = _encode_wav_pcm16(pcm_bytes, sample_rate, channels)
                        filename = overrides.get("filename") or "audio.wav"
                        content_type = overrides.get("content_type") or "audio/wav"

                        if engine_type in {"dify_asr", "dify"}:
                            response = await _forward_dify_transcription(
                                engine_config, wav_bytes, overrides, filename, content_type
                            )
                        elif engine_type in {"coze_asr", "coze"}:
                            response = await _forward_coze_transcription(
                                engine_config, wav_bytes, overrides, filename, content_type
                            )
                        else:
                            response = await _forward_transcription(
                                engine_config, wav_bytes, overrides, filename, content_type
                            )

                        await websocket.send_json({"type": "result", "data": response})
                        buffer = bytearray()
                        has_audio = False
                elif message_type == "reset":
                    buffer = bytearray()
                    has_audio = False
                else:
                    await websocket.send_json({"type": "error", "error": "Unknown message type."})

            elif message.get("bytes") is not None:
                chunk = message["bytes"]
                if not isinstance(chunk, (bytes, bytearray)) or not chunk:
                    continue
                has_audio = True
                if engine_type in ALIYUN_ASR_ENGINE_TYPES and aliyun_realtime_session is not None:
                    await _append_aliyun_realtime_audio(aliyun_realtime_session, bytes(chunk))
                else:
                    buffer.extend(chunk)

    except WebSocketDisconnect:
        if aliyun_realtime_session is not None:
            await _close_aliyun_realtime_session(aliyun_realtime_session)
        return
    except Exception as exc:
        if aliyun_realtime_session is not None:
            await _close_aliyun_realtime_session(aliyun_realtime_session)
        sent = await _safe_send_ws_error(websocket, str(exc))
        if not sent:
            return
        try:
            await websocket.close(code=1011)
        except (RuntimeError, WebSocketDisconnect):
            return


def _is_websocket_disconnect_message(message: Dict[str, Any]) -> bool:
    return isinstance(message, dict) and message.get("type") == "websocket.disconnect"


def _is_disconnect_receive_runtime_error(exc: BaseException) -> bool:
    if not isinstance(exc, RuntimeError):
        return False
    return "disconnect message has been received" in str(exc).lower()


async def _safe_send_ws_error(websocket: WebSocket, error_message: str) -> bool:
    try:
        await websocket.send_json({"type": "error", "error": error_message})
    except (RuntimeError, WebSocketDisconnect):
        return False
    return True


def _resolve_engine_id(engine_id: str) -> str:
    if engine_id == "default":
        default_spec = registry.get_default("asr")
        return default_spec.id if default_spec else ""
    return engine_id


def _get_engine_config(engine_id: str):
    if not engine_id:
        raise HTTPException(status_code=400, detail="Missing engine id")
    config = runtime_store.get("asr", engine_id)
    if not config or not config.base_url:
        raise HTTPException(status_code=404, detail="ASR engine not configured")
    engine_type = (config.engine_type or "openai_compat").lower()
    if engine_type not in {"dify_asr", "coze_asr", "dify", "coze"} | ALIYUN_ASR_ENGINE_TYPES and not config.model:
        raise HTTPException(status_code=400, detail="ASR engine missing model")
    return config


def _extract_audio_bytes(data: Any) -> bytes:
    if data is None:
        return b""
    if isinstance(data, str):
        return _decode_base64(data)
    if isinstance(data, dict):
        base64_payload = data.get("audio_base64") or data.get("base64")
        if isinstance(base64_payload, str):
            return _decode_base64(base64_payload)
    return b""


def _decode_base64(payload: str) -> bytes:
    try:
        return base64.b64decode(payload, validate=True)
    except Exception:
        return b""


def _resolve_file_meta(overrides: Optional[Dict[str, Any]]) -> tuple[str, str]:
    if not overrides:
        return "audio.wav", "application/octet-stream"
    filename = (
        overrides.get("filename")
        or overrides.get("file_name")
        or overrides.get("file")
        or "audio.wav"
    )
    content_type = overrides.get("content_type") or overrides.get("mime_type") or "application/octet-stream"
    return str(filename), str(content_type)


def _encode_wav_pcm16(pcm_bytes: bytes, sample_rate: int, channels: int) -> bytes:
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(max(1, channels))
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()


async def _forward_transcription(
    config,
    audio_bytes: bytes,
    overrides: Optional[Dict[str, Any]],
    filename: str,
    content_type: str,
) -> dict:
    headers = {}
    headers.update(config.headers)
    api_key = resolve_api_key(config.api_key_env)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data: Dict[str, Any] = {"model": config.model}
    data.update(config.default_params)
    if isinstance(overrides, dict):
        data.update(sanitize_config(overrides, blocked=ASR_BLOCKED_CONFIG_KEYS))

    transcription_path = config.paths.get("transcription") if config.paths else None
    path = normalize_path(transcription_path or "/audio/transcriptions")
    url = config.base_url.rstrip("/") + path

    files = {"file": (filename, audio_bytes, content_type)}

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        response = await client.post(url, headers=headers, data=data, files=files)
        response.raise_for_status()
        return response.json()


def _merge_params(config, overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(config.default_params or {})
    merged.update(sanitize_config(overrides, blocked=ASR_BLOCKED_CONFIG_KEYS))
    return merged


async def _forward_dify_transcription(
    config,
    audio_bytes: bytes,
    overrides: Dict[str, Any],
    filename: str,
    content_type: str,
) -> dict:
    params = _merge_params(config, overrides)
    api_server = params.get("api_server") or config.base_url
    api_key = params.get("api_key") or resolve_api_key(config.api_key_env)
    username = params.get("username") or params.get("user")

    if not api_server or not api_key:
        raise HTTPException(status_code=400, detail="Dify ASR missing API server or key")

    headers = {"Authorization": f"Bearer {api_key}"}
    headers.update(config.headers)
    data: Dict[str, Any] = {}
    if username:
        data["user"] = username

    transcription_path = config.paths.get("transcription") if config.paths else None
    path = normalize_path(transcription_path or "/audio-to-text")
    url = api_server.rstrip("/") + path

    files = {"file": (filename, audio_bytes, content_type)}
    async with httpx.AsyncClient(timeout=config.timeout) as client:
        response = await client.post(url, headers=headers, data=data, files=files)
        response.raise_for_status()
        payload = response.json()
    text = _extract_text(payload)
    return {"text": text} if text else payload


async def _forward_coze_transcription(
    config,
    audio_bytes: bytes,
    overrides: Dict[str, Any],
    filename: str,
    content_type: str,
) -> dict:
    params = _merge_params(config, overrides)
    api_base = params.get("api_base") or config.base_url
    token = params.get("token") or resolve_api_key(config.api_key_env)

    if not api_base or not token:
        raise HTTPException(status_code=400, detail="Coze ASR missing API base or token")

    headers = {"Authorization": f"Bearer {token}"}
    headers.update(config.headers)

    transcription_path = config.paths.get("transcription") if config.paths else None
    path = normalize_path(transcription_path or "/v1/audio/transcriptions")
    url = api_base.rstrip("/") + path

    files = {"file": (filename, audio_bytes, content_type)}
    async with httpx.AsyncClient(timeout=config.timeout) as client:
        response = await client.post(url, headers=headers, files=files)
        response.raise_for_status()
        payload = response.json()
    text = _extract_text(payload)
    return {"text": text} if text else payload


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


def _to_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return fallback


def _first_present(params: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in params and params.get(key) is not None:
            return params.get(key)
    return None


def _resolve_audio_format(filename: str, content_type: str) -> str:
    normalized_type = (content_type or "").strip().lower()
    if "/" in normalized_type:
        fmt = normalized_type.split("/", 1)[1].split(";", 1)[0].strip()
        if fmt:
            return fmt
    if "." in (filename or ""):
        return filename.rsplit(".", 1)[-1].strip().lower()
    return "wav"


DASHSCOPE_CN_BASE = "https://dashscope.aliyuncs.com"
DASHSCOPE_INTL_BASE = "https://dashscope-intl.aliyuncs.com"
ALIYUN_ASR_REALTIME_MODEL = "qwen3-asr-flash-realtime"


@dataclass
class AliyunRealtimeSession:
    ws: Any
    reader_task: Optional[asyncio.Task] = None
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    transcripts: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


def _resolve_aliyun_dashscope_base_url(params: Dict[str, Any], config) -> str:
    explicit_base = str(
        _first_present(params, "base_url", "baseUrl", "dashscope_base_url", "dashscopeBaseUrl")
        or config.base_url
        or ""
    ).strip()
    if explicit_base:
        return explicit_base.rstrip("/")

    region = str(_first_present(params, "region") or "cn-beijing").strip().lower()
    if region in {"intl", "sg", "singapore", "intl-singapore", "ap-southeast-1"}:
        return DASHSCOPE_INTL_BASE
    return DASHSCOPE_CN_BASE


def _resolve_aliyun_dashscope_credentials(config, overrides: Dict[str, Any]) -> Dict[str, Any]:
    params = _merge_params(config, overrides)
    api_key = str(
        _first_present(params, "api_key", "apiKey", "dashscope_api_key", "dashscopeApiKey")
        or resolve_api_key(config.api_key_env)
        or ""
    ).strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="Alibaba Bailian ASR missing apiKey")

    model = ALIYUN_ASR_REALTIME_MODEL

    return {
        "params": params,
        "api_key": api_key,
        "model": model,
        "base_url": _resolve_aliyun_dashscope_base_url(params, config),
    }


def _build_aliyun_dashscope_urls(base_url: str) -> Dict[str, str]:
    root = base_url.rstrip("/")
    return {
        "chat": f"{root}/compatible-mode/v1/chat/completions",
    }


def _resolve_aliyun_realtime_model(model: str) -> str:
    normalized = (model or "").strip()
    if not normalized:
        return ALIYUN_ASR_REALTIME_MODEL
    if "realtime" in normalized.lower():
        return normalized
    return ALIYUN_ASR_REALTIME_MODEL


def _resolve_aliyun_non_realtime_model(model: str) -> str:
    normalized = (model or "").strip()
    if not normalized:
        return "qwen3-asr-flash"
    if "realtime" in normalized.lower():
        return "qwen3-asr-flash"
    return normalized


def _build_aliyun_realtime_ws_url(base_url: str, model: str) -> str:
    raw = (base_url or "").strip().rstrip("/")
    if not raw:
        raw = DASHSCOPE_CN_BASE

    parsed = urlsplit(raw)
    if not parsed.scheme:
        parsed = urlsplit(f"https://{raw}")

    scheme = parsed.scheme.lower()
    if scheme == "https":
        ws_scheme = "wss"
    elif scheme == "http":
        ws_scheme = "ws"
    elif scheme in {"ws", "wss"}:
        ws_scheme = scheme
    else:
        ws_scheme = "wss"

    path = parsed.path.rstrip("/")
    realtime_path = "/api-ws/v1/realtime"
    if path.endswith(realtime_path):
        final_path = path
    elif not path:
        final_path = realtime_path
    else:
        final_path = f"{path}{realtime_path}"

    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_items["model"] = _resolve_aliyun_realtime_model(model)
    return urlunsplit((ws_scheme, parsed.netloc, final_path, urlencode(query_items), ""))


def _resolve_audio_mime_type(filename: str, content_type: str) -> str:
    normalized_type = (content_type or "").strip().lower()
    if normalized_type.startswith("audio/"):
        return normalized_type.split(";", 1)[0]

    audio_format = _resolve_audio_format(filename, content_type)
    if audio_format:
        return f"audio/{audio_format}"
    return "audio/wav"


def _build_audio_data_url(audio_bytes: bytes, filename: str, content_type: str) -> str:
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    return f"data:{_resolve_audio_mime_type(filename, content_type)};base64,{encoded}"


def _collect_aliyun_asr_options(params: Dict[str, Any]) -> Dict[str, Any]:
    options: Dict[str, Any] = {}
    language = _first_present(params, "language")
    if language is not None:
        options["language"] = str(language).strip()

    enable_itn = _first_present(params, "enable_itn", "enableItn")
    if enable_itn is not None:
        options["enable_itn"] = _to_bool(enable_itn, False)

    enable_words = _first_present(params, "enable_words", "enableWords")
    if enable_words is not None:
        options["enable_words"] = _to_bool(enable_words, False)

    channel_id = _first_present(params, "channel_id", "channelId")
    if channel_id is not None:
        if isinstance(channel_id, list):
            options["channel_id"] = [_to_int(item, 0) for item in channel_id]
        else:
            options["channel_id"] = [_to_int(channel_id, 0)]

    return options


def _normalize_realtime_language(language: Any) -> Optional[str]:
    if language is None:
        return None
    value = str(language).strip()
    if not value:
        return None
    if "-" in value:
        return value.split("-", 1)[0].lower()
    return value.lower()


def _build_aliyun_realtime_session_event(params: Dict[str, Any], sample_rate: int) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "event_id": f"event_{int(time.time() * 1000)}",
        "type": "session.update",
        "session": {
            "modalities": ["text"],
            "input_audio_format": "pcm",
            "sample_rate": max(8000, _to_int(sample_rate, 16000)),
        },
    }

    language = _normalize_realtime_language(_first_present(params, "language"))
    if language:
        event["session"]["input_audio_transcription"] = {"language": language}

    enable_server_vad = _to_bool(_first_present(params, "enable_server_vad", "enableServerVad"), False)
    if enable_server_vad:
        event["session"]["turn_detection"] = {
            "type": "server_vad",
            "threshold": _to_float(_first_present(params, "vad_threshold", "vadThreshold"), 0.0),
            "silence_duration_ms": _to_int(
                _first_present(params, "vad_silence_ms", "vadSilenceMs", "silence_duration_ms"),
                400,
            ),
        }
    else:
        event["session"]["turn_detection"] = None

    return event


def _extract_aliyun_realtime_event_text(event: Dict[str, Any]) -> str:
    for key in ("transcript", "text", "delta"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    data = event.get("data")
    if isinstance(data, dict):
        for key in ("transcript", "text", "delta"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    output = event.get("output")
    if isinstance(output, dict):
        value = output.get("text")
        if isinstance(value, str) and value.strip():
            return value.strip()

    item = event.get("item")
    if isinstance(item, dict):
        for key in ("transcript", "text", "delta"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _extract_aliyun_realtime_error(event: Dict[str, Any]) -> str:
    error = event.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    if isinstance(error, str) and error.strip():
        return error.strip()
    message = event.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return "Alibaba Bailian realtime ASR failed."


async def _read_aliyun_realtime_events(session: AliyunRealtimeSession) -> None:
    ws = session.ws
    try:
        async for raw_message in ws:
            if not isinstance(raw_message, str):
                continue
            try:
                event = json.loads(raw_message)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue

            text = _extract_aliyun_realtime_event_text(event)
            if text and (not session.transcripts or session.transcripts[-1] != text):
                session.transcripts.append(text)

            event_type = str(event.get("type") or "").lower()
            if event_type == "error":
                session.error_message = _extract_aliyun_realtime_error(event)
                session.finished.set()
                return
            if event_type == "session.finished":
                session.finished.set()
                return
    except ConnectionClosed:
        if not session.finished.is_set():
            session.finished.set()
    except Exception as exc:
        if not session.finished.is_set():
            session.error_message = str(exc)
            session.finished.set()


async def _open_aliyun_realtime_session(config, overrides: Dict[str, Any], sample_rate: int) -> AliyunRealtimeSession:
    resolved = _resolve_aliyun_dashscope_credentials(config, overrides)
    ws_url = _build_aliyun_realtime_ws_url(
        base_url=resolved["base_url"],
        model=resolved["model"],
    )
    timeout_seconds = max(float(config.timeout or 60.0), 10.0)
    ws = await ws_connect(
        ws_url,
        additional_headers={
            "Authorization": f"Bearer {resolved['api_key']}",
            "OpenAI-Beta": "realtime=v1",
        },
        open_timeout=min(timeout_seconds, 30.0),
        ping_interval=20,
        ping_timeout=20,
        max_size=2**22,
    )
    session = AliyunRealtimeSession(ws=ws)
    session.reader_task = asyncio.create_task(_read_aliyun_realtime_events(session))
    await ws.send(
        json.dumps(
            _build_aliyun_realtime_session_event(
                params=resolved["params"],
                sample_rate=sample_rate,
            ),
            ensure_ascii=False,
        )
    )
    return session


async def _append_aliyun_realtime_audio(session: AliyunRealtimeSession, pcm_bytes: bytes) -> None:
    if not pcm_bytes:
        return
    await session.ws.send(
        json.dumps(
            {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm_bytes).decode("ascii"),
            }
        )
    )


async def _finish_aliyun_realtime_session(session: AliyunRealtimeSession, overrides: Dict[str, Any]) -> Dict[str, Any]:
    enable_server_vad = _to_bool(
        _first_present(overrides, "enable_server_vad", "enableServerVad"),
        False,
    )
    if not enable_server_vad:
        await session.ws.send(
            json.dumps(
                {
                    "event_id": f"event_{int(time.time() * 1000)}",
                    "type": "input_audio_buffer.commit",
                }
            )
        )
    await session.ws.send(
        json.dumps(
            {
                "event_id": f"event_{int(time.time() * 1000)}",
                "type": "session.finish",
            }
        )
    )
    try:
        await asyncio.wait_for(session.finished.wait(), timeout=15)
    except asyncio.TimeoutError:
        if session.transcripts:
            return {"text": "\n".join(session.transcripts).strip()}
        raise HTTPException(status_code=504, detail="Alibaba Bailian realtime ASR timed out")

    if session.error_message:
        raise HTTPException(status_code=400, detail=session.error_message)

    text = "\n".join(part for part in session.transcripts if part).strip()
    return {"text": text} if text else {"text": ""}


async def _close_aliyun_realtime_session(session: AliyunRealtimeSession) -> None:
    if session.reader_task is not None:
        session.reader_task.cancel()
        try:
            await session.reader_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    try:
        await session.ws.close()
    except Exception:
        pass


def _extract_dashscope_asr_text(payload: Dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, dict):
        if isinstance(output.get("text"), str):
            return output["text"].strip()
        results = output.get("results")
        if isinstance(results, list):
            chunks = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                for key in ("text", "transcript", "result", "sentence"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        chunks.append(value.strip())
                        break
            if chunks:
                return "\n".join(chunks).strip()

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts).strip()

    return _extract_text(payload)


async def _forward_aliyun_dashscope_transcription(
    config,
    audio_bytes: bytes,
    overrides: Dict[str, Any],
    filename: str,
    content_type: str,
) -> dict:
    resolved = _resolve_aliyun_dashscope_credentials(config, overrides)
    params = resolved["params"]
    api_key = resolved["api_key"]
    model = resolved["model"]
    urls = _build_aliyun_dashscope_urls(resolved["base_url"])
    timeout_seconds = max(float(config.timeout or 60.0), 10.0)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        audio_data_url = _build_audio_data_url(audio_bytes, filename, content_type)
        chat_model = _resolve_aliyun_non_realtime_model(model)
        chat_payload: Dict[str, Any] = {
            "model": chat_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_data_url},
                        }
                    ],
                }
            ],
            "stream": False,
        }
        asr_options = _collect_aliyun_asr_options(params)
        if asr_options:
            chat_payload["asr_options"] = asr_options

        chat_response = await client.post(urls["chat"], headers=headers, json=chat_payload)
        chat_response.raise_for_status()
        chat_data = chat_response.json()
        text = _extract_dashscope_asr_text(chat_data)
        return {"text": text} if text else chat_data


def _extract_text(payload: Dict[str, Any]) -> str:
    if isinstance(payload.get("text"), str):
        return payload["text"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("text"), str):
        return data["text"]
    return ""
