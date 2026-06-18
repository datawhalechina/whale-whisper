from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProviderFieldOption(BaseModel):
    id: str
    label: str
    description: Optional[str] = None
    icon: Optional[str] = None

    @classmethod
    def from_spec(cls, spec) -> "ProviderFieldOption":
        return cls(
            id=spec.id,
            label=spec.label,
            description=spec.description,
            icon=spec.icon,
        )


class ProviderField(BaseModel):
    id: str
    label: str
    field_type: str = Field(..., alias="type")
    required: bool = False
    placeholder: Optional[str] = None
    default: Optional[Any] = None
    description: Optional[str] = None
    scope: str = "config"
    options: List[ProviderFieldOption] = Field(default_factory=list)
    options_source: Optional[str] = Field(default=None, alias="optionsSource")

    class Config:
        populate_by_name = True

    @classmethod
    def from_spec(cls, spec) -> "ProviderField":
        return cls(
            id=spec.id,
            label=spec.label,
            field_type=spec.field_type,
            required=spec.required,
            placeholder=spec.placeholder,
            default=spec.default,
            description=spec.description,
            scope=spec.scope,
            options=[ProviderFieldOption.from_spec(o) for o in spec.options],
            options_source=spec.options_source,
        )


class ProviderDefaults(BaseModel):
    base_url: Optional[str] = Field(default=None, alias="baseUrl")
    model: Optional[str] = None
    voice: Optional[str] = None

    class Config:
        populate_by_name = True

    @classmethod
    def from_spec(cls, spec) -> "ProviderDefaults":
        return cls(
            base_url=spec.base_url,
            model=spec.model,
            voice=spec.voice,
        )


class ProviderDesc(BaseModel):
    id: str
    label: str
    category: str
    icon: Optional[str] = None
    description: Optional[str] = None
    engine_id: Optional[str] = Field(default=None, alias="engineId")
    defaults: Optional[ProviderDefaults] = None
    fields: List[ProviderField] = Field(default_factory=list)

    class Config:
        populate_by_name = True

    @classmethod
    def from_spec(cls, spec, fields: Optional[List["ProviderField"]] = None) -> "ProviderDesc":
        return cls(
            id=spec.id,
            label=spec.label,
            category=spec.category,
            icon=spec.icon,
            description=spec.description,
            engine_id=spec.engine_id,
            defaults=ProviderDefaults.from_spec(spec.defaults) if spec.defaults else None,
            fields=fields if fields is not None else [ProviderField.from_spec(f) for f in spec.fields],
        )


class ProviderCatalogResponse(BaseModel):
    providers: List[ProviderDesc] = Field(default_factory=list)


class PluginDesc(BaseModel):
    id: str
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    providers: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PluginCatalogResponse(BaseModel):
    plugins: List[PluginDesc] = Field(default_factory=list)
