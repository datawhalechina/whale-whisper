from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.provider_catalog_schemas import (
    ProviderCatalogResponse,
    ProviderDesc,
    ProviderField,
)
from app.services.providers.registry import registry
from app.services.providers.types import ProviderConfig
from app.services.catalogs.provider_catalog import get_provider_catalog

router = APIRouter(prefix="/providers", tags=["providers"])

ALIYUN_NLS_PROVIDER_ID = "aliyun-nls-transcription"


class ProviderRequest(BaseModel):
    provider_id: str = Field(..., alias="providerId")
    api_key: Optional[str] = Field(default=None, alias="apiKey")
    base_url: Optional[str] = Field(default=None, alias="baseUrl")
    model: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        populate_by_name = True


class ProviderValidationResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None


class ProviderModelsResponse(BaseModel):
    models: List[Dict[str, Any]] = Field(default_factory=list)


class ProviderVoicesResponse(BaseModel):
    voices: List[Dict[str, Any]] = Field(default_factory=list)


def _aliyun_nls_default_fields() -> List[ProviderField]:
    return [
        ProviderField(
            id="apiKey",
            label="API Key",
            field_type="secret",
            required=True,
        ),
    ]


def _resolve_provider_fields(spec) -> List[ProviderField]:
    fields = [ProviderField.from_spec(field) for field in spec.fields]
    if spec.id != ALIYUN_NLS_PROVIDER_ID:
        return fields

    # Keep UI minimal for this provider: only API key is exposed.
    return _aliyun_nls_default_fields()


def _to_config(request: ProviderRequest) -> ProviderConfig:
    return ProviderConfig(
        provider_id=request.provider_id,
        api_key=request.api_key,
        base_url=request.base_url,
        model=request.model,
        extra=request.extra or {},
    )


@router.post("/validate", response_model=ProviderValidationResponse)
async def validate_provider(request: ProviderRequest) -> ProviderValidationResponse:
    config = _to_config(request)
    result = await registry.validate(config)
    return ProviderValidationResponse(valid=result.valid, reason=result.reason)


@router.post("/models", response_model=ProviderModelsResponse)
async def list_models(request: ProviderRequest) -> ProviderModelsResponse:
    config = _to_config(request)
    models = await registry.list_models(config)
    return ProviderModelsResponse(models=models)


@router.post("/voices", response_model=ProviderVoicesResponse)
async def list_voices(request: ProviderRequest) -> ProviderVoicesResponse:
    config = _to_config(request)
    voices = await registry.list_voices(config)
    return ProviderVoicesResponse(voices=voices)


@router.get("/catalog", response_model=ProviderCatalogResponse)
async def list_provider_catalog() -> ProviderCatalogResponse:
    catalog = get_provider_catalog()
    providers = [
        ProviderDesc.from_spec(spec, fields=_resolve_provider_fields(spec))
        for spec in catalog.list()
    ]
    return ProviderCatalogResponse(providers=providers)
