import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Iterable, Optional, Type

import httpx

from app.core.http_utils import normalize_path
from app.services.engines.runtime_store import EngineRuntimeConfig
from .types import AgentEvent
from .utils import merge_params


@dataclass
class AgentContext:
    runtime: EngineRuntimeConfig
    params: Dict[str, Any]


class AgentHandler:
    async def create_conversation(self, context: AgentContext) -> str:
        return ""

    async def stream(self, context: AgentContext, text: str) -> AsyncIterator[AgentEvent]:
        if not text:
            return
        yield AgentEvent(event="message.delta", data={"text": text})
        yield AgentEvent(event="message.done", data={})


class DifyAgentHandler(AgentHandler):
    async def create_conversation(self, context: AgentContext) -> str:
        params = _apply_dify_defaults(context)
        api_server = params.get("api_server")
        api_key = params.get("api_key")
        username = params.get("username") or params.get("user")
        inputs = _coerce_dify_inputs(params)

        if not api_server or not api_key or not username:
            return ""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        headers.update(context.runtime.headers)
        payload = {
            "inputs": inputs,
            "query": "hello",
            "response_mode": "blocking",
            "user": username,
            "conversation_id": "",
            "files": [],
        }
        chat_path = _resolve_path(
            context.runtime,
            "conversation",
            _resolve_path(context.runtime, "chat", "/chat-messages"),
        )
        async with httpx.AsyncClient(timeout=context.runtime.timeout) as client:
            response = await client.post(
                _build_dify_url(api_server, chat_path),
                headers=headers,
                json=payload,
            )
            if response.status_code >= 400:
                return ""
            data = response.json()
        return str(data.get("conversation_id") or "")

    async def stream(self, context: AgentContext, text: str) -> AsyncIterator[AgentEvent]:
        params = _apply_dify_defaults(context)
        api_server = params.get("api_server")
        api_key = params.get("api_key")
        username = params.get("username") or params.get("user")
        conversation_id = _coerce_dify_conversation_id(params.get("conversation_id"))
        inputs = _coerce_dify_inputs(params)

        if not api_server:
            yield AgentEvent(event="error", data={"message": "Missing Dify API server."})
            return
        if not api_key:
            yield AgentEvent(event="error", data={"message": "Missing Dify API key."})
            return
        if not username:
            yield AgentEvent(event="error", data={"message": "Missing Dify username."})
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        headers.update(context.runtime.headers)
        payload = {
            "inputs": inputs,
            "query": text,
            "response_mode": "streaming",
            "user": username,
            "conversation_id": conversation_id,
            "files": [],
        }

        chat_path = _resolve_path(context.runtime, "chat", "/chat-messages")
        async with httpx.AsyncClient(timeout=context.runtime.timeout) as client:
            async with client.stream(
                "POST",
                _build_dify_url(api_server, chat_path),
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    detail = await _read_error_detail(response)
                    yield AgentEvent(event="error", data={"message": detail})
                    return
                current_conversation_id = conversation_id
                async for line in response.aiter_lines():
                    chunk = line.strip()
                    if not chunk or not chunk.startswith("data:"):
                        continue
                    data_payload = chunk.split("data:", 1)[1].strip()
                    if not data_payload:
                        continue
                    try:
                        data = json.loads(data_payload)
                    except json.JSONDecodeError:
                        continue
                    if not current_conversation_id and data.get("conversation_id"):
                        current_conversation_id = str(data["conversation_id"])
                        yield AgentEvent(
                            event="conversation.id",
                            data={"conversation_id": current_conversation_id},
                        )
                    answer = data.get("answer")
                    event_name = data.get("event", "")
                    if answer and "message" in str(event_name):
                        yield AgentEvent(event="message.delta", data={"text": str(answer)})

        yield AgentEvent(event="message.done", data={})


class CozeAgentHandler(AgentHandler):
    async def create_conversation(self, context: AgentContext) -> str:
        params = _apply_coze_defaults(context)
        api_base = params.get("api_base")
        token = params.get("token")
        if not api_base or not token:
            return ""

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        headers.update(context.runtime.headers)
        conversation_path = _resolve_path(context.runtime, "conversation", "/v1/conversation/create")
        async with httpx.AsyncClient(timeout=context.runtime.timeout) as client:
            response = await client.post(
                _build_url(api_base, conversation_path),
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        return str(data.get("data", {}).get("id") or "")

    async def stream(self, context: AgentContext, text: str) -> AsyncIterator[AgentEvent]:
        params = _apply_coze_defaults(context)
        api_base = params.get("api_base")
        token = params.get("token")
        bot_id = params.get("bot_id")
        user_id = params.get("user") or "whale"
        conversation_id = params.get("conversation_id") or ""

        if not api_base:
            yield AgentEvent(event="error", data={"message": "Missing Coze API base."})
            return
        if not token:
            yield AgentEvent(event="error", data={"message": "Missing Coze token."})
            return
        if not bot_id:
            yield AgentEvent(event="error", data={"message": "Missing Coze bot_id."})
            return

        if not conversation_id:
            conversation_id = await self.create_conversation(context)
            if conversation_id:
                yield AgentEvent(event="conversation.id", data={"conversation_id": conversation_id})

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        headers.update(context.runtime.headers)
        payload = {
            "bot_id": bot_id,
            "user_id": user_id,
            "stream": True,
            "auto_save_history": True,
            "additional_messages": [
                {
                    "role": "user",
                    "content": text,
                    "content_type": "text",
                }
            ],
        }
        chat_path = _resolve_path(context.runtime, "chat", "/v3/chat")
        api_url = _build_url(api_base, chat_path)
        if conversation_id:
            separator = "&" if "?" in api_url else "?"
            api_url = f"{api_url}{separator}conversation_id={conversation_id}"

        async with httpx.AsyncClient(timeout=context.runtime.timeout) as client:
            async with client.stream("POST", api_url, headers=headers, json=payload) as response:
                response.raise_for_status()
                event_name: Optional[str] = None
                async for line in response.aiter_lines():
                    chunk = line.strip()
                    if not chunk:
                        continue
                    if chunk.startswith("event:"):
                        event_name = chunk.split(":", 1)[1].strip()
                        continue
                    if event_name != "conversation.message.delta":
                        continue
                    if "data:" not in chunk:
                        continue
                    message_data = chunk.split("data:", 1)[1].strip()
                    if not message_data:
                        continue
                    try:
                        message_json = json.loads(message_data)
                    except json.JSONDecodeError:
                        continue
                    reasoning_content = message_json.get("reasoning_content")
                    if reasoning_content:
                        yield AgentEvent(event="message.think", data={"text": str(reasoning_content)})
                    content = message_json.get("content")
                    if content:
                        yield AgentEvent(event="message.delta", data={"text": str(content)})

        yield AgentEvent(event="message.done", data={})


class FastGPTAgentHandler(AgentHandler):
    async def create_conversation(self, context: AgentContext) -> str:
        params = _apply_fastgpt_defaults(context)
        conversation_id = params.get("conversation_id")
        if conversation_id:
            return str(conversation_id)
        return os.urandom(8).hex()

    async def stream(self, context: AgentContext, text: str) -> AsyncIterator[AgentEvent]:
        params = _apply_fastgpt_defaults(context)
        base_url = params.get("base_url")
        api_key = params.get("api_key")
        uid = params.get("uid")
        conversation_id = params.get("conversation_id") or ""

        if not base_url:
            yield AgentEvent(event="error", data={"message": "Missing FastGPT base URL."})
            return
        if not api_key:
            yield AgentEvent(event="error", data={"message": "Missing FastGPT API key."})
            return

        if not conversation_id:
            conversation_id = await self.create_conversation(context)
            if conversation_id:
                yield AgentEvent(event="conversation.id", data={"conversation_id": conversation_id})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        headers.update(context.runtime.headers)
        payload = {
            "chatId": conversation_id,
            "stream": True,
            "detail": False,
            "messages": [
                {"role": "user", "content": text},
            ],
            "customUid": uid,
        }

        chat_path = _resolve_path(context.runtime, "chat", "/v1/chat/completions")
        async with httpx.AsyncClient(timeout=context.runtime.timeout) as client:
            async with client.stream(
                "POST",
                _build_url(base_url, chat_path),
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    chunk = line.strip()
                    if not chunk or not chunk.startswith("data:"):
                        continue
                    data_payload = chunk.split("data:", 1)[1].strip()
                    if not data_payload or data_payload == "[DONE]":
                        continue
                    try:
                        data = json.loads(data_payload)
                    except json.JSONDecodeError:
                        continue
                    try:
                        delta = data["choices"][0].get("delta") or {}
                        content = delta.get("content")
                    except (KeyError, IndexError, TypeError):
                        content = None
                    if content:
                        yield AgentEvent(event="message.delta", data={"text": str(content)})

        yield AgentEvent(event="message.done", data={})


class CustomAgentHandler(AgentHandler):
    async def create_conversation(self, context: AgentContext) -> str:
        params = _apply_custom_defaults(context)
        conversation_id = params.get("conversation_id")
        if conversation_id:
            return str(conversation_id)

        base_url = params.get("base_url")
        if not base_url:
            return ""

        conversation_path = context.runtime.paths.get("conversation") if context.runtime.paths else None
        if not conversation_path:
            return ""

        payload = {"config": _sanitize_custom_params(params)}
        headers = _build_headers(context.runtime, params.get("api_key"))
        url = _build_url(base_url, normalize_path(str(conversation_path)))

        async with httpx.AsyncClient(timeout=context.runtime.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return _extract_conversation_id(data)

    async def stream(self, context: AgentContext, text: str) -> AsyncIterator[AgentEvent]:
        params = _apply_custom_defaults(context)
        base_url = params.get("base_url")
        if not base_url:
            yield AgentEvent(event="error", data={"message": "Missing custom agent base URL."})
            return

        chat_path = _resolve_path(context.runtime, "chat", "/chat")
        url = _build_url(base_url, chat_path)
        headers = _build_headers(context.runtime, params.get("api_key"))
        payload = {
            "text": text,
            "conversation_id": params.get("conversation_id") or "",
            "config": _sanitize_custom_params(params),
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=context.runtime.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for event in _stream_sse_events(response):
                    yield event

        yield AgentEvent(event="message.done", data={})


_HANDLER_REGISTRY: Dict[str, Type[AgentHandler]] = {}


def register_agent_handler(engine_types: Iterable[str], handler: Type[AgentHandler]) -> None:
    for engine_type in engine_types:
        if not engine_type:
            continue
        _HANDLER_REGISTRY[str(engine_type).lower()] = handler


def build_agent_handler(runtime: EngineRuntimeConfig) -> AgentHandler:
    engine_type = (runtime.engine_type or "").lower()
    handler = _HANDLER_REGISTRY.get(engine_type, AgentHandler)
    return handler()


def _apply_dify_defaults(context: AgentContext) -> Dict[str, Any]:
    params = merge_params(context.runtime.default_params, context.params)
    if context.runtime.api_key_env and not params.get("api_key"):
        params["api_key"] = os.getenv(context.runtime.api_key_env, "")
    if not params.get("api_server"):
        params["api_server"] = context.runtime.base_url
    return params


def _apply_coze_defaults(context: AgentContext) -> Dict[str, Any]:
    params = merge_params(context.runtime.default_params, context.params)
    if context.runtime.api_key_env and not params.get("token"):
        params["token"] = os.getenv(context.runtime.api_key_env, "")
    if not params.get("api_base"):
        params["api_base"] = context.runtime.base_url
    return params


def _apply_fastgpt_defaults(context: AgentContext) -> Dict[str, Any]:
    params = merge_params(context.runtime.default_params, context.params)
    if context.runtime.api_key_env and not params.get("api_key"):
        params["api_key"] = os.getenv(context.runtime.api_key_env, "")
    if not params.get("base_url"):
        params["base_url"] = context.runtime.base_url
    return params


def _apply_custom_defaults(context: AgentContext) -> Dict[str, Any]:
    params = merge_params(context.runtime.default_params, context.params)
    if context.runtime.api_key_env and not params.get("api_key"):
        params["api_key"] = os.getenv(context.runtime.api_key_env, "")
    if not params.get("base_url"):
        params["base_url"] = context.runtime.base_url
    return params


def _sanitize_custom_params(params: Dict[str, Any]) -> Dict[str, Any]:
    blocked = {"api_key", "base_url", "stream"}
    sanitized = {}
    for key, value in params.items():
        if key in blocked:
            continue
        if value is None:
            continue
        sanitized[key] = value
    return sanitized


def _resolve_path(runtime: EngineRuntimeConfig, key: str, fallback: str) -> str:
    path = runtime.paths.get(key) if runtime.paths else None
    return normalize_path(path or fallback)


def _build_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _build_dify_url(base_url: str, path: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path
    if normalized_base.endswith("/v1") and normalized_path.startswith("/v1"):
        normalized_path = normalized_path[3:] or "/"
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    return normalized_base + normalized_path


def _build_headers(runtime: EngineRuntimeConfig, api_key: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    headers.update(runtime.headers)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _coerce_dify_conversation_id(value: Any) -> str:
    if not value:
        return ""
    if not isinstance(value, str):
        value = str(value)
    candidate = value.strip()
    if not candidate:
        return ""
    try:
        uuid.UUID(candidate)
    except (ValueError, AttributeError):
        return ""
    return candidate


def _coerce_dify_inputs(params: Dict[str, Any]) -> Dict[str, Any]:
    inputs = params.get("inputs")
    if inputs is None or inputs == "":
        return {}
    if isinstance(inputs, dict):
        return inputs
    if isinstance(inputs, str):
        try:
            parsed = json.loads(inputs)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


async def _read_error_detail(response: httpx.Response) -> str:
    try:
        raw = await response.aread()
    except httpx.HTTPError:
        raw = b""
    text = raw.decode("utf-8", errors="ignore").strip() if raw else ""
    if text:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(payload, dict):
            message = payload.get("message") or payload.get("detail") or payload.get("error")
            code = payload.get("code")
            if message and code:
                return f"{message} ({code})"
            if message:
                return str(message)
    return f"Request failed with status {response.status_code}."


async def _stream_sse_events(response: httpx.Response) -> AsyncIterator[AgentEvent]:
    event_name: Optional[str] = None
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if line == "":
            if data_lines:
                payload_text = "\n".join(data_lines).strip()
                event = _normalize_custom_event(event_name, payload_text)
                if event:
                    yield event
            event_name = None
            data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line.split("data:", 1)[1].lstrip())
            continue

    if data_lines:
        payload_text = "\n".join(data_lines).strip()
        event = _normalize_custom_event(event_name, payload_text)
        if event:
            yield event


def _normalize_custom_event(event_name: Optional[str], payload_text: str) -> Optional[AgentEvent]:
    name = (event_name or "").strip()
    data: Any = payload_text
    if payload_text:
        try:
            data = json.loads(payload_text)
        except json.JSONDecodeError:
            data = payload_text

    if name in {"message.delta", "message.think", "message.done", "conversation.id", "error"}:
        return _coerce_agent_event(name, data)
    if name in {"done", "message.done", "final"}:
        return AgentEvent(event="message.done", data={})
    if name in {"delta", "message"} or not name:
        return _coerce_agent_event("message.delta", data)

    return _coerce_agent_event("message.delta", data)


def _coerce_agent_event(event: str, data: Any) -> AgentEvent:
    if event in {"message.delta", "message.think"}:
        if isinstance(data, dict):
            text = data.get("text")
            if isinstance(text, str):
                return AgentEvent(event=event, data={"text": text})
        if isinstance(data, str):
            return AgentEvent(event=event, data={"text": data})
        return AgentEvent(event=event, data={"text": ""})
    if event == "conversation.id":
        if isinstance(data, dict):
            conversation_id = data.get("conversation_id") or data.get("conversationId") or data.get("id")
            return AgentEvent(event=event, data={"conversation_id": conversation_id})
        if isinstance(data, str):
            return AgentEvent(event=event, data={"conversation_id": data})
        return AgentEvent(event=event, data={"conversation_id": ""})
    if event == "error":
        if isinstance(data, dict) and isinstance(data.get("message"), str):
            return AgentEvent(event=event, data={"message": data["message"]})
        if isinstance(data, str):
            return AgentEvent(event=event, data={"message": data})
        return AgentEvent(event=event, data={"message": "Agent error."})
    return AgentEvent(event="message.done", data={})


def _extract_conversation_id(payload: Any) -> str:
    if isinstance(payload, dict):
        value = payload.get("conversation_id") or payload.get("conversationId")
        if value:
            return str(value)
        data = payload.get("data")
        if isinstance(data, dict) and data.get("id"):
            return str(data["id"])
        if payload.get("id"):
            return str(payload["id"])
    if isinstance(payload, str):
        return payload
    return ""


register_agent_handler({"dify", "dify_agent"}, DifyAgentHandler)
register_agent_handler({"coze", "coze_agent"}, CozeAgentHandler)
register_agent_handler({"fastgpt", "fastgpt_agent"}, FastGPTAgentHandler)
register_agent_handler({"custom", "custom_agent"}, CustomAgentHandler)
