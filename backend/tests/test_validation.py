"""Validation utility tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.validation import validate_url_input  # noqa: E402


class TestValidation:
    def test_valid_https(self):
        v = validate_url_input("https://example.com/page", 2048)
        assert v.ok and v.cleaned_url == "https://example.com/page"

    def test_bare_domain_accepted(self):
        v = validate_url_input("example.com", 2048)
        assert v.ok

    def test_non_string(self):
        assert not validate_url_input(None, 2048).ok
        assert not validate_url_input(123, 2048).ok

    def test_empty(self):
        assert not validate_url_input("  ", 2048).ok

    def test_too_long(self):
        assert not validate_url_input("http://e.com/" + "x" * 3000, 2048).ok

    def test_scheme_whitelist(self):
        for bad in ("javascript:alert(1)", "data:text/html,x", "file:///etc/passwd", "ftp://x.com"):
            assert not validate_url_input(bad, 2048).ok

    def test_control_chars(self):
        assert not validate_url_input("http://ex\x01ample.com/", 2048).ok

    def test_localhost(self):
        assert not validate_url_input("http://localhost:3000/", 2048).ok

    def test_garbage_path_only(self):
        assert not validate_url_input("/just/a/path", 2048).ok
