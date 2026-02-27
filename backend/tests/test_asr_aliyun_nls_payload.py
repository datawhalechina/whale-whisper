import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.api.asr import _aliyun_nls_websocket_endpoint, _build_aliyun_create_token_url


def run(name: str, fn):
    try:
        fn()
        print(f"PASS {name}")
    except Exception:
        print(f"FAIL {name}")
        raise


def test_aliyun_nls_websocket_endpoint_matches_airi_regions():
    assert (
        _aliyun_nls_websocket_endpoint("cn-shanghai")
        == "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
    )
    assert (
        _aliyun_nls_websocket_endpoint("cn-beijing")
        == "wss://nls-gateway-cn-beijing.aliyuncs.com/ws/v1"
    )
    assert (
        _aliyun_nls_websocket_endpoint("cn-shenzhen")
        == "wss://nls-gateway-cn-shenzhen.aliyuncs.com/ws/v1"
    )
    assert (
        _aliyun_nls_websocket_endpoint("cn-shanghai-internal")
        == "wss://nls-gateway-cn-shanghai-internal.aliyuncs.com:80/ws/v1"
    )


def test_build_aliyun_create_token_url_contains_required_signed_fields():
    url = _build_aliyun_create_token_url(
        access_key_id="test-ak-id",
        access_key_secret="test-ak-secret",
        region="cn-shanghai",
        endpoint="http://nls-meta.cn-shanghai.aliyuncs.com",
        timestamp="2025-01-02T03:04:05Z",
        signature_nonce="nonce-123",
    )

    assert url.startswith("http://nls-meta.cn-shanghai.aliyuncs.com/?Signature=")
    assert "AccessKeyId=test-ak-id" in url
    assert "Action=CreateToken" in url
    assert "Format=JSON" in url
    assert "RegionId=cn-shanghai" in url
    assert "SignatureMethod=HMAC-SHA1" in url
    assert "SignatureNonce=nonce-123" in url
    assert "SignatureVersion=1.0" in url
    assert "Timestamp=2025-01-02T03%3A04%3A05Z" in url
    assert "Version=2019-02-28" in url


if __name__ == "__main__":
    run(
        "aliyun websocket endpoint matches airi regions",
        test_aliyun_nls_websocket_endpoint_matches_airi_regions,
    )
    run(
        "build aliyun create token url contains required signed fields",
        test_build_aliyun_create_token_url_contains_required_signed_fields,
    )
