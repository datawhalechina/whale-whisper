import base64
import asyncio
import hashlib
import hmac
import io
import json
import uuid
import wave
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
import websockets
from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

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
    if engine_type in {"aliyun_nls_asr", "aliyun_nls"}:
        return await _forward_aliyun_nls_transcription(config, audio_bytes, overrides, filename, content_type)
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
    if engine_type in {"aliyun_nls_asr", "aliyun_nls"}:
        return await _forward_aliyun_nls_transcription(config, audio_bytes, {}, filename, content_type)
    response = await _forward_transcription(config, audio_bytes, {}, filename, content_type)
    return response


@router.websocket("/engines/stream")
async def run_asr_engine_stream(websocket: WebSocket) -> None:
    await websocket.accept()

    engine_id = "default"
    engine_config = None
    overrides: Dict[str, Any] = {}
    sample_rate = 16000
    channels = 1
    buffer = bytearray()

    try:
        while True:
            message = await websocket.receive()

            if message.get("text") is not None:
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "Invalid JSON payload."})
                    continue

                message_type = payload.get("type")
                if message_type == "start":
                    engine_id = payload.get("engine", "default")
                    engine_id = _resolve_engine_id(engine_id)
                    engine_config = _get_engine_config(engine_id)
                    overrides = payload.get("config") if isinstance(payload.get("config"), dict) else {}
                    sample_rate = int(payload.get("sample_rate") or payload.get("sampleRate") or 16000)
                    channels = int(payload.get("channels") or 1)
                    buffer = bytearray()
                    await websocket.send_json({"type": "ready"})
                elif message_type == "stop":
                    if engine_config is None:
                        await websocket.send_json({"type": "error", "error": "Engine not initialized."})
                        continue
                    if not buffer:
                        await websocket.send_json({"type": "error", "error": "Missing audio data."})
                        continue

                    wav_bytes = _encode_wav_pcm16(bytes(buffer), sample_rate, channels)
                    filename = overrides.get("filename") or "audio.wav"
                    content_type = overrides.get("content_type") or "audio/wav"

                    engine_type = (engine_config.engine_type or "openai_compat").lower()
                    if engine_type in {"dify_asr", "dify"}:
                        response = await _forward_dify_transcription(
                            engine_config, wav_bytes, overrides, filename, content_type
                        )
                    elif engine_type in {"coze_asr", "coze"}:
                        response = await _forward_coze_transcription(
                            engine_config, wav_bytes, overrides, filename, content_type
                        )
                    elif engine_type in {"aliyun_nls_asr", "aliyun_nls"}:
                        response = await _forward_aliyun_nls_transcription(
                            engine_config, wav_bytes, overrides, filename, content_type
                        )
                    else:
                        response = await _forward_transcription(
                            engine_config, wav_bytes, overrides, filename, content_type
                        )

                    await websocket.send_json({"type": "result", "data": response})
                    buffer = bytearray()
                elif message_type == "reset":
                    buffer = bytearray()
                else:
                    await websocket.send_json({"type": "error", "error": "Unknown message type."})

            elif message.get("bytes") is not None:
                buffer.extend(message["bytes"])

    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"type": "error", "error": str(exc)})
        await websocket.close(code=1011)


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
    if engine_type not in {"dify_asr", "coze_asr", "aliyun_nls_asr", "dify", "coze", "aliyun_nls"} and not config.model:
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


def _resolve_audio_format(filename: str, content_type: str) -> str:
    normalized_type = (content_type or "").strip().lower()
    if "/" in normalized_type:
        fmt = normalized_type.split("/", 1)[1].split(";", 1)[0].strip()
        if fmt:
            return fmt
    if "." in (filename or ""):
        return filename.rsplit(".", 1)[-1].strip().lower()
    return "wav"


def _aliyun_quote(value: str) -> str:
    return quote(value, safe="~")


def _build_aliyun_create_token_url(
    access_key_id: str,
    access_key_secret: str,
    region: str,
    endpoint: str,
    timestamp: str,
    signature_nonce: str,
) -> str:
    params = {
        "AccessKeyId": access_key_id,
        "Action": "CreateToken",
        "Format": "JSON",
        "RegionId": region,
        "SignatureMethod": "HMAC-SHA1",
        "SignatureNonce": signature_nonce,
        "SignatureVersion": "1.0",
        "Timestamp": timestamp,
        "Version": "2019-02-28",
    }
    canonical_query = "&".join(
        f"{_aliyun_quote(k)}={_aliyun_quote(str(v))}" for k, v in sorted(params.items(), key=lambda item: item[0])
    )
    string_to_sign = f"POST&{_aliyun_quote('/')}&{_aliyun_quote(canonical_query)}"
    signature = base64.b64encode(
        hmac.new(
            f"{access_key_secret}&".encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")
    signed_query = f"Signature={_aliyun_quote(signature)}&{canonical_query}"
    return f"{endpoint.rstrip('/')}/?{signed_query}"


def _aliyun_nls_websocket_endpoint(region: str) -> str:
    internal_regions = {
        "cn-shanghai-internal",
        "cn-beijing-internal",
        "cn-shenzhen-internal",
    }
    public_regions = {
        "cn-shanghai",
        "cn-beijing",
        "cn-shenzhen",
    }
    normalized = (region or "").strip().lower()
    if normalized in internal_regions:
        return f"wss://nls-gateway-{normalized}.aliyuncs.com:80/ws/v1"
    if normalized in public_regions:
        return f"wss://nls-gateway-{normalized}.aliyuncs.com/ws/v1"
    return "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"


def _resolve_aliyun_nls_credentials(config, overrides: Dict[str, Any]) -> Dict[str, Any]:
    params = _merge_params(config, overrides)
    access_key_id = str(
        params.get("accessKeyId")
        or params.get("access_key_id")
        or params.get("akId")
        or ""
    ).strip()
    access_key_secret = str(
        params.get("accessKeySecret")
        or params.get("access_key_secret")
        or params.get("akSecret")
        or ""
    ).strip()
    app_key = str(
        params.get("appKey")
        or params.get("app_key")
        or ""
    ).strip()
    region = str(params.get("region") or "cn-shanghai").strip().lower()
    if not access_key_id:
        raise HTTPException(status_code=400, detail="Aliyun NLS ASR missing accessKeyId")
    if not access_key_secret:
        raise HTTPException(status_code=400, detail="Aliyun NLS ASR missing accessKeySecret")
    if not app_key:
        raise HTTPException(status_code=400, detail="Aliyun NLS ASR missing appKey")
    return {
        "params": params,
        "access_key_id": access_key_id,
        "access_key_secret": access_key_secret,
        "app_key": app_key,
        "region": region,
    }


async def _create_aliyun_nls_token(
    access_key_id: str,
    access_key_secret: str,
    region: str,
    endpoint: str,
    timeout: float,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signature_nonce = str(uuid.uuid4())
    token_url = _build_aliyun_create_token_url(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region=region,
        endpoint=endpoint,
        timestamp=timestamp,
        signature_nonce=signature_nonce,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(token_url)
        response.raise_for_status()
        payload = response.json()
    token_info = payload.get("Token") if isinstance(payload, dict) else None
    token = token_info.get("Id") if isinstance(token_info, dict) else ""
    if not isinstance(token, str) or not token.strip():
        message = payload.get("Message") if isinstance(payload, dict) else "Unknown error"
        raise HTTPException(status_code=400, detail=f"Aliyun NLS token creation failed: {message}")
    return token.strip()


async def _forward_aliyun_nls_transcription(
    config,
    audio_bytes: bytes,
    overrides: Dict[str, Any],
    filename: str,
    content_type: str,
) -> dict:
    resolved = _resolve_aliyun_nls_credentials(config, overrides)
    params = resolved["params"]
    access_key_id = resolved["access_key_id"]
    access_key_secret = resolved["access_key_secret"]
    app_key = resolved["app_key"]
    region = resolved["region"]

    endpoint = (
        str(params.get("endpoint") or params.get("meta_endpoint") or config.base_url or "").strip()
        or f"http://nls-meta.{region}.aliyuncs.com"
    )
    token = await _create_aliyun_nls_token(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region=region,
        endpoint=endpoint,
        timeout=config.timeout,
    )

    ws_url = f"{_aliyun_nls_websocket_endpoint(region)}?token={_aliyun_quote(token)}"
    task_id = uuid.uuid4().hex
    audio_format = str(params.get("format") or _resolve_audio_format(filename, content_type) or "wav").lower()
    sample_rate = _to_int(params.get("sample_rate") or params.get("sampleRate"), 16000)

    start_payload = {
        "header": {
            "appkey": app_key,
            "message_id": uuid.uuid4().hex,
            "task_id": task_id,
            "namespace": "SpeechTranscriber",
            "name": "StartTranscription",
        },
        "payload": {
            "format": audio_format,
            "sample_rate": sample_rate,
            "enable_intermediate_result": True,
            "enable_punctuation_prediction": True,
        },
    }
    stop_payload = {
        "header": {
            "appkey": app_key,
            "message_id": uuid.uuid4().hex,
            "task_id": task_id,
            "namespace": "SpeechTranscriber",
            "name": "StopTranscription",
        },
        "payload": {},
    }

    sentence_results = []
    last_partial = ""
    timeout_seconds = max(float(config.timeout or 60.0), 10.0)

    try:
        async with websockets.connect(ws_url, max_size=None, open_timeout=timeout_seconds) as ws:
            await ws.send(json.dumps(start_payload))
            started = False

            while True:
                raw_message = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
                if isinstance(raw_message, bytes):
                    continue

                event = json.loads(raw_message)
                header = event.get("header") if isinstance(event, dict) else {}
                payload = event.get("payload") if isinstance(event, dict) else {}
                event_name = header.get("name")
                status = header.get("status")
                if status not in (None, 20000000, "20000000"):
                    status_message = header.get("status_message") or payload.get("message") or "Unknown status"
                    raise HTTPException(status_code=400, detail=f"Aliyun NLS ASR failed: {status_message}")

                if event_name == "TranscriptionStarted" and not started:
                    started = True
                    await ws.send(audio_bytes)
                    await ws.send(json.dumps(stop_payload))
                    continue

                if event_name == "SentenceEnd":
                    result_text = str(payload.get("result") or "").strip()
                    if result_text:
                        sentence_results.append(result_text)
                    continue

                if event_name == "TranscriptionResultChanged":
                    last_partial = str(payload.get("result") or "").strip()
                    continue

                if event_name == "TranscriptionCompleted":
                    break
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Aliyun NLS ASR timed out") from exc

    final_text = "\n".join(sentence_results).strip() or last_partial
    return {"text": final_text} if final_text else {"text": ""}


def _extract_text(payload: Dict[str, Any]) -> str:
    if isinstance(payload.get("text"), str):
        return payload["text"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("text"), str):
        return data["text"]
    return ""
