import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.services.catalogs.provider_catalog import get_provider_catalog


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def test_tts_provider_defaults_use_official_direct_endpoints():
    catalog = get_provider_catalog()

    volc = catalog.get("volcengine-speech")
    assert volc is not None
    assert volc.defaults.base_url == "https://openspeech.bytedance.com/api/v1/tts"
    assert volc.defaults.model == "v1"

    alibaba = catalog.get("alibaba-cloud-model-studio-speech")
    assert alibaba is not None
    assert alibaba.defaults.base_url == "https://dashscope.aliyuncs.com"
    assert alibaba.defaults.model == "cosyvoice-v1"

    model_field = next((f for f in alibaba.fields if f.id == "model"), None)
    assert model_field is not None
    option_ids = [option.id for option in model_field.options]
    assert option_ids == ["cosyvoice-v1", "cosyvoice-v2"]


if __name__ == "__main__":
    run(
        "tts provider defaults use official direct endpoints",
        test_tts_provider_defaults_use_official_direct_endpoints,
    )
