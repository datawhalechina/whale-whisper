import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.api.providers import list_provider_catalog  # noqa: E402
from app.services.catalogs.provider_catalog import (  # noqa: E402
    ProviderFieldOptionSpec,
    ProviderFieldSpec,
    ProviderSpec,
)
from app.services.catalogs.provider_catalog import ProviderDefaults  # noqa: E402


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def _spec_with_full_fields() -> ProviderSpec:
    return ProviderSpec(
        id="test-provider",
        label="Test Provider",
        category="llm",
        icon="icon-x",
        description="desc",
        engine_id="engine-1",
        defaults=ProviderDefaults(
            base_url="https://example.com",
            model="m1",
            voice="v1",
        ),
        fields=[
            ProviderFieldSpec(
                id="model",
                label="Model",
                field_type="select",
                required=True,
                placeholder="pick",
                default="m1",
                description="model desc",
                scope="config",
                options=[
                    ProviderFieldOptionSpec(
                        id="m1", label="M1", description="opt", icon="i"
                    )
                ],
                options_source="catalog",
            )
        ],
    )


def test_catalog_response_serializes_with_alias_contract():
    """Freeze the API JSON contract: alias fields (engineId, baseUrl,
    optionsSource, type) must appear in serialized output."""
    import asyncio

    import app.api.providers as providers_mod

    original = providers_mod.get_provider_catalog
    fake_spec = _spec_with_full_fields()

    class _FakeCatalog:
        def list(self):
            return [fake_spec]

    providers_mod.get_provider_catalog = lambda: _FakeCatalog()
    try:
        response = asyncio.run(list_provider_catalog())
    finally:
        providers_mod.get_provider_catalog = original

    providers_list = response.providers
    assert len(providers_list) == 1
    desc = providers_list[0]

    # top-level alias contract
    dumped = desc.model_dump(by_alias=True, exclude_none=False)
    assert dumped["engineId"] == "engine-1"
    assert dumped["id"] == "test-provider"
    assert dumped["category"] == "llm"

    # defaults alias contract
    assert dumped["defaults"]["baseUrl"] == "https://example.com"
    assert dumped["defaults"]["model"] == "m1"
    assert dumped["defaults"]["voice"] == "v1"

    # field alias contract
    field = dumped["fields"][0]
    assert field["type"] == "select"
    assert field["optionsSource"] == "catalog"
    assert field["scope"] == "config"

    # option contract
    option = field["options"][0]
    assert option["id"] == "m1"
    assert option["label"] == "M1"
    assert option["icon"] == "i"


if __name__ == "__main__":
    run(
        "catalog response serializes with alias contract",
        test_catalog_response_serializes_with_alias_contract,
    )
