import unittest

from app.api.tts import _extract_upstream_error_detail, _format_httpx_error_detail


class TtsErrorHelpersTest(unittest.TestCase):
    def test_extract_upstream_error_detail_prefers_detail_field(self) -> None:
        detail = _extract_upstream_error_detail(b'{"detail":"upstream bad gateway"}', "Bad Gateway")
        self.assertEqual(detail, "upstream bad gateway")

    def test_extract_upstream_error_detail_handles_nested_error_message(self) -> None:
        detail = _extract_upstream_error_detail(
            b'{"error":{"message":"model overloaded"}}',
            "Bad Gateway",
        )
        self.assertEqual(detail, "model overloaded")

    def test_extract_upstream_error_detail_falls_back_to_reason_phrase(self) -> None:
        detail = _extract_upstream_error_detail(b"", "Bad Gateway")
        self.assertEqual(detail, "Bad Gateway")

    def test_format_httpx_error_detail_never_returns_empty(self) -> None:
        class DummyError(Exception):
            pass

        detail = _format_httpx_error_detail(DummyError())
        self.assertTrue(detail)
        self.assertIn("DummyError", detail)


if __name__ == "__main__":
    unittest.main()
