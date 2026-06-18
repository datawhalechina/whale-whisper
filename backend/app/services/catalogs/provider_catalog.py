from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

import yaml

from app.core.settings import get_settings


@dataclass
class ProviderFieldOptionSpec:
    id: str
    label: str
    description: Optional[str] = None
    icon: Optional[str] = None


@dataclass
class ProviderFieldSpec:
    id: str
    label: str
    field_type: str
    required: bool = False
    placeholder: Optional[str] = None
    default: Optional[Any] = None
    description: Optional[str] = None
    scope: str = "config"
    options: List[ProviderFieldOptionSpec] = field(default_factory=list)
    options_source: Optional[str] = None


@dataclass
class ProviderDefaults:
    base_url: Optional[str] = None
    model: Optional[str] = None
    voice: Optional[str] = None


@dataclass
class ProviderSpec:
    id: str
    label: str
    category: str
    icon: Optional[str] = None
    description: Optional[str] = None
    engine_id: Optional[str] = None
    defaults: ProviderDefaults = field(default_factory=ProviderDefaults)
    fields: List[ProviderFieldSpec] = field(default_factory=list)


class ProviderCatalog:
    def __init__(self, providers: List[ProviderSpec]):
        self._providers = providers
        self._index = {provider.id: provider for provider in providers}

    def list(self) -> List[ProviderSpec]:
        return list(self._providers)

    def get(self, provider_id: str) -> Optional[ProviderSpec]:
        return self._index.get(provider_id)


def _parse_field_options(raw: Any) -> List[ProviderFieldOptionSpec]:
    if not isinstance(raw, list):
        return []
    options: List[ProviderFieldOptionSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        option_id = str(item.get("id") or item.get("value") or "")
        label = str(item.get("label") or option_id)
        if not option_id:
            continue
        options.append(
            ProviderFieldOptionSpec(
                id=option_id,
                label=label,
                description=item.get("description"),
                icon=item.get("icon"),
            )
        )
    return options


def _parse_fields(raw: Any) -> List[ProviderFieldSpec]:
    if not isinstance(raw, list):
        return []
    fields: List[ProviderFieldSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        field_id = str(item.get("id") or "")
        label = str(item.get("label") or field_id)
        field_type = str(item.get("type") or "text")
        if not field_id:
            continue
        fields.append(
            ProviderFieldSpec(
                id=field_id,
                label=label,
                field_type=field_type,
                required=bool(item.get("required", False)),
                placeholder=item.get("placeholder"),
                default=item.get("default"),
                description=item.get("description"),
                scope=str(item.get("scope") or "config"),
                options=_parse_field_options(item.get("options")),
                options_source=item.get("options_source"),
            )
        )
    return fields


def _parse_defaults(raw: Any) -> ProviderDefaults:
    if not isinstance(raw, dict):
        return ProviderDefaults()
    return ProviderDefaults(
        base_url=raw.get("base_url") or raw.get("baseUrl"),
        model=raw.get("model"),
        voice=raw.get("voice"),
    )


def _load_catalog_file(path: Path) -> List[ProviderSpec]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return []
    entries = data.get("providers")
    if not isinstance(entries, list):
        return []
    providers: List[ProviderSpec] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        provider_id = str(item.get("id") or "")
        label = str(item.get("label") or provider_id)
        category = str(item.get("category") or "")
        if not provider_id or not category:
            continue
        engine_id_raw = item.get("engine_id") or item.get("engineId")
        engine_id = None
        if engine_id_raw is not None and str(engine_id_raw).strip():
            engine_id = str(engine_id_raw)
        providers.append(
            ProviderSpec(
                id=provider_id,
                label=label,
                category=category,
                icon=item.get("icon"),
                description=item.get("description"),
                engine_id=engine_id,
                defaults=_parse_defaults(item.get("defaults")),
                fields=_parse_fields(item.get("fields")),
            )
        )
    return providers


@lru_cache
def get_provider_catalog() -> ProviderCatalog:
    settings = get_settings()
    base_dir = Path(__file__).resolve().parents[3]
    path = Path(settings.provider_catalog_path)
    if not path.is_absolute():
        path = base_dir / path
    providers = _load_catalog_file(path)
    return ProviderCatalog(providers)
