from __future__ import annotations
from cortex_engine.core.text_sanitizer import sanitize


class TestSanitizer:
    def test_strips_control_chars(self):
        assert sanitize("hello\x01world\x03") == "helloworld"

    def test_preserves_whitespace(self):
        assert sanitize("tab\there\nnewline") == "tab\there\nnewline"

    def test_preserves_carriage_return(self):
        assert sanitize("line\r\nend") == "line\r\nend"

    def test_empty_string(self):
        assert sanitize("") == ""

    def test_none_returns_empty(self):
        assert sanitize(None) == ""

    def test_strips_null_byte(self):
        assert sanitize("before\x00after") == "beforeafter"

    def test_strips_vertical_tab_form_feed(self):
        assert sanitize("a\x0bb\x0cc") == "abc"
