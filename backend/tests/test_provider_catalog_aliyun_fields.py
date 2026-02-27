import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.api.providers import _resolve_provider_field_dicts
from app.services.catalogs.provider_catalog import ProviderFieldSpec, ProviderSpec


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def _field(field_id: str, label: str = "", field_type: str = "text", required: bool = False, scope: str = "config"):
    return ProviderFieldSpec(
        id=field_id,
        label=label or field_id,
        field_type=field_type,
        required=required,
        scope=scope,
    )


def test_aliyun_catalog_fields_are_normalized_when_openai_style_fields_present():
    spec = ProviderSpec(
        id="aliyun-nls-transcription",
        label="Alibaba Bailian",
        category="transcription",
        fields=[
            _field("apiKey", "API Key", "secret", True),
            _field("baseUrl", "Base URL", "text", True),
        ],
    )

    fields = _resolve_provider_field_dicts(spec)
    field_ids = [item["id"] for item in fields]

    assert field_ids == ["apiKey", "model"]
    assert "baseUrl" not in field_ids


def test_aliyun_catalog_fields_are_forced_to_minimal_shape():
    spec = ProviderSpec(
        id="aliyun-nls-transcription",
        label="Alibaba Bailian",
        category="transcription",
        fields=[
            _field("apiKey", "API Key", "secret", True, "config"),
            _field("model", "Model", "select", False, "config"),
            _field("region", "Region", "select", False, "extra"),
        ],
    )

    fields = _resolve_provider_field_dicts(spec)
    field_ids = [item["id"] for item in fields]

    assert field_ids == ["apiKey", "model"]


if __name__ == "__main__":
    run(
        "aliyun catalog fields are normalized when openai-style fields present",
        test_aliyun_catalog_fields_are_normalized_when_openai_style_fields_present,
    )
    run(
        "aliyun catalog fields are forced to minimal shape",
        test_aliyun_catalog_fields_are_forced_to_minimal_shape,
    )
