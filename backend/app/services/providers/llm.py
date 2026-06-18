import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx

from app.core.settings import AppSettings, get_settings
from app.services.providers.types import ProviderConfig


class LLMConfigError(ValueError):
    pass


@dataclass
class LLMResponse:
    text: str
    conversation_id: Optional[str] = None


class LLMProvider:
    def supports_messages(self) -> bool:
        return False

    async def generate(
        self,
        text: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        raise NotImplementedError

    async def stream(
        self,
        text: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        response = await self.generate(
            text=text,
            user_id=user_id,
            conversation_id=conversation_id,
            messages=messages,
        )
        return [response.text]


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        model: str,
        timeout: float,
        temperature: float,
        system_prompt: Optional[str],
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.system_prompt = system_prompt

    async def generate(
        self,
        text: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resolved_messages = self._resolve_messages(text, messages)
        payload = {
            "model": self.model,
            "messages": resolved_messages,
            "temperature": self.temperature,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMConfigError("OpenAI-compatible response missing content")
        return LLMResponse(text=content)

    def supports_messages(self) -> bool:
        return True

    async def stream(
        self,
        text: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resolved_messages = self._resolve_messages(text, messages)
        payload = {
            "model": self.model,
            "messages": resolved_messages,
            "temperature": self.temperature,
            "stream": True,
        }

        deltas: List[str] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    chunk = line.strip()
                    if not chunk:
                        continue
                    if not chunk.startswith("data:"):
                        continue
                    data = chunk.split("data:", 1)[1].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        deltas.append(content)

        if not deltas:
            response = await self.generate(
                text=text, user_id=user_id, conversation_id=conversation_id, messages=messages
            )
            return [response.text]

        return deltas

    def _resolve_messages(
        self, text: str, messages: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        if messages:
            return messages
        resolved: List[Dict[str, Any]] = []
        if self.system_prompt:
            resolved.append({"role": "system", "content": self.system_prompt})
        resolved.append({"role": "user", "content": text})
        return resolved


class DifyProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, user: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.user = user
        self.timeout = timeout

    async def generate(
        self,
        text: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        text = _coerce_text_from_messages(text, messages)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": {},
            "query": text,
            "response_mode": "blocking",
            "user": user_id or self.user,
            "conversation_id": conversation_id or "",
            "files": [],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/chat-messages", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        answer = data.get("answer")
        if not answer:
            raise LLMConfigError("Dify response missing 'answer'")
        return LLMResponse(text=answer, conversation_id=_extract_conversation_id(data))


class FastGPTProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, uid: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.uid = uid
        self.timeout = timeout

    async def generate(
        self,
        text: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        text = _coerce_text_from_messages(text, messages)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "chatId": conversation_id or "",
            "stream": False,
            "detail": False,
            "messages": [
                {"role": "user", "content": text},
            ],
            "customUid": user_id or self.uid,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            message = data["choices"][0].get("message") or {}
            content = message.get("content") or ""
        except (KeyError, IndexError, TypeError):
            content = ""

        if not content:
            raise LLMConfigError("FastGPT response missing content")
        return LLMResponse(text=content, conversation_id=_extract_conversation_id(data))


class CozeProvider(LLMProvider):
    def __init__(self, api_base: str, token: str, bot_id: str, user: str, timeout: float) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.bot_id = bot_id
        self.user = user
        self.timeout = timeout

    async def _create_conversation(self) -> str:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.api_base}/v1/conversation/create", headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            return data["data"]["id"]
        except (KeyError, TypeError):
            raise LLMConfigError("Coze response missing conversation id")

    async def generate(
        self,
        text: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        text = _coerce_text_from_messages(text, messages)
        if not conversation_id:
            conversation_id = await self._create_conversation()
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "bot_id": self.bot_id,
            "user_id": user_id or self.user,
            "stream": True,
            "auto_save_history": True,
            "additional_messages": [
                {"role": "user", "content": text, "content_type": "text"}
            ],
        }
        api_url = f"{self.api_base}/v3/chat?conversation_id={conversation_id}"

        text_chunks = []
        event_name = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", api_url, headers=headers, json=payload) as response:
                response.raise_for_status()
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
                    content = message_json.get("content")
                    if content:
                        text_chunks.append(content)

        if not text_chunks:
            raise LLMConfigError("Coze response missing content")
        return LLMResponse(text="".join(text_chunks), conversation_id=conversation_id)


def _extract_conversation_id(data: Dict[str, Any]) -> Optional[str]:
    for key in ("conversation_id", "conversationId", "chatId", "chat_id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    nested = data.get("data")
    if isinstance(nested, dict):
        for key in ("conversation_id", "conversationId", "chatId", "chat_id", "id"):
            value = nested.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _coerce_text_from_messages(
    text: str, messages: Optional[List[Dict[str, Any]]]
) -> str:
    if isinstance(text, str) and text:
        return text
    if not messages:
        return text
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])
    last = messages[-1] if messages else None
    if isinstance(last, dict) and last.get("content"):
        return str(last["content"])
    return text


def build_llm_provider(settings: AppSettings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider in {"openai", "openai_compat", "openai-compatible"}:
        if not settings.openai_api_key:
            raise LLMConfigError("OPENAI_API_KEY is required")
        return OpenAICompatProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout=settings.llm_timeout,
            temperature=settings.llm_temperature,
            system_prompt=settings.llm_system_prompt,
        )
    if provider == "dify":
        if not settings.dify_base_url:
            raise LLMConfigError("DIFY_BASE_URL is required")
        if not settings.dify_api_key:
            raise LLMConfigError("DIFY_API_KEY is required")
        return DifyProvider(
            base_url=settings.dify_base_url,
            api_key=settings.dify_api_key,
            user=settings.dify_user,
            timeout=settings.llm_timeout,
        )
    if provider == "fastgpt":
        if not settings.fastgpt_base_url:
            raise LLMConfigError("FASTGPT_BASE_URL is required")
        if not settings.fastgpt_api_key:
            raise LLMConfigError("FASTGPT_API_KEY is required")
        return FastGPTProvider(
            base_url=settings.fastgpt_base_url,
            api_key=settings.fastgpt_api_key,
            uid=settings.fastgpt_uid,
            timeout=settings.llm_timeout,
        )
    if provider == "coze":
        if not settings.coze_token:
            raise LLMConfigError("COZE_TOKEN is required")
        if not settings.coze_bot_id:
            raise LLMConfigError("COZE_BOT_ID is required")
        return CozeProvider(
            api_base=settings.coze_api_base,
            token=settings.coze_token,
            bot_id=settings.coze_bot_id,
            user=settings.coze_user,
            timeout=settings.llm_timeout,
        )
    raise LLMConfigError(f"Unsupported LLM provider: {settings.llm_provider}")


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    return build_llm_provider(settings)


def build_llm_provider_from_config(
    config: ProviderConfig, settings: Optional[AppSettings] = None
) -> LLMProvider:
    settings = settings or get_settings()
    provider_id = config.provider_id.lower()

    if provider_id in {"dify"}:
        if not config.base_url:
            raise LLMConfigError("DIFY base URL is required")
        if not config.api_key:
            raise LLMConfigError("DIFY API key is required")
        user = config.extra.get("user") if isinstance(config.extra, dict) else None
        return DifyProvider(
            base_url=config.base_url,
            api_key=config.api_key,
            user=user or settings.dify_user,
            timeout=settings.llm_timeout,
        )

    if provider_id in {"fastgpt"}:
        if not config.base_url:
            raise LLMConfigError("FastGPT base URL is required")
        if not config.api_key:
            raise LLMConfigError("FastGPT API key is required")
        uid = config.extra.get("uid") if isinstance(config.extra, dict) else None
        return FastGPTProvider(
            base_url=config.base_url,
            api_key=config.api_key,
            uid=uid or settings.fastgpt_uid,
            timeout=settings.llm_timeout,
        )

    if provider_id in {"coze"}:
        if not config.base_url:
            raise LLMConfigError("Coze API base is required")
        if not config.api_key:
            raise LLMConfigError("Coze token is required")
        bot_id = config.extra.get("bot_id") if isinstance(config.extra, dict) else None
        if not bot_id:
            raise LLMConfigError("Coze bot_id is required")
        user = config.extra.get("user") if isinstance(config.extra, dict) else None
        return CozeProvider(
            api_base=config.base_url,
            token=config.api_key,
            bot_id=bot_id,
            user=user or settings.coze_user,
            timeout=settings.llm_timeout,
        )

    base_url = config.base_url or settings.openai_base_url
    model = config.model or settings.openai_model
    if not base_url:
        raise LLMConfigError("OpenAI-compatible base URL is required")
    if not model:
        raise LLMConfigError("OpenAI-compatible model is required")
    return OpenAICompatProvider(
        base_url=base_url,
        api_key=config.api_key or settings.openai_api_key,
        model=model,
        timeout=settings.llm_timeout,
        temperature=settings.llm_temperature,
        system_prompt=settings.llm_system_prompt,
    )
