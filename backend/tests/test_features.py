"""Unit tests: URL parsing and feature extraction (shared module)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.feature_extractor import (  # noqa: E402
    FEATURE_DESCRIPTIONS,
    FEATURE_NAMES,
    URLValidationError,
    canonical_feature_url,
    extract_features,
    normalise_url_for_dedup,
    parse_url,
)


class TestParsing:
    def test_basic_http(self):
        p = parse_url("http://example.com/path?q=1")
        assert p.scheme == "http"
        assert p.hostname == "example.com"
        assert p.path == "/path"
        assert p.query == "q=1"
        assert p.scheme_was_inferred is False

    def test_https_and_port(self):
        p = parse_url("https://example.com:8443/x")
        assert p.scheme == "https"
        assert p.port == 8443

    def test_bare_domain_marks_inferred_scheme(self):
        p = parse_url("example.com/path")
        assert p.scheme_was_inferred is True
        assert p.hostname == "example.com"

    def test_case_and_whitespace_normalisation(self):
        p = parse_url("  HTTPS://EXAMPLE.COM/Path  ")
        assert p.hostname == "example.com"
        assert p.path == "/Path"  # path case preserved

    def test_invalid_port_rejected(self):
        with pytest.raises(URLValidationError):
            parse_url("http://example.com:notaport/")

    def test_no_hostname_rejected(self):
        with pytest.raises(URLValidationError):
            parse_url("http://")

    def test_empty_rejected(self):
        with pytest.raises(URLValidationError):
            parse_url("   ")

    def test_control_characters_rejected(self):
        with pytest.raises(URLValidationError):
            parse_url("http://exa\nmple.com")

    def test_oversized_rejected(self):
        with pytest.raises(URLValidationError):
            parse_url("http://example.com/" + "a" * 5000)


class TestFeatures:
    def test_feature_vector_shape_and_order(self):
        f = extract_features("https://example.com/a?b=1")
        assert list(f.keys()) == list(FEATURE_NAMES)
        assert all(isinstance(v, (int, float)) for v in f.values())

    def test_ip_hostname_flagged(self):
        assert extract_features("http://192.168.1.1/login")["has_ip"] == 1
        assert extract_features("http://example.com/login")["has_ip"] == 0

    def test_ipv6_hostname_flagged(self):
        assert extract_features("http://[2001:db8::1]/x")["has_ip"] == 1

    def test_https_flag_only_for_real_scheme(self):
        assert extract_features("https://example.com/")["is_https"] == 1
        # bare domain: scheme inferred for parsing, feature must stay 0
        assert extract_features("example.com/")["is_https"] == 0

    def test_at_symbol_and_credentials(self):
        f = extract_features("http://user:pass@example.com/x")
        assert f["nb_at_symbol"] == 1
        assert f["has_credentials_pattern"] == 1

    def test_percent_encoding_counted(self):
        assert extract_features("http://example.com/a%20b%20c%20d")["nb_pct_encoded"] == 3

    def test_query_params_counted(self):
        f = extract_features("http://example.com/?a=1&b=2&c=3")
        assert f["nb_query_params"] == 3
        assert f["nb_ampersand"] == 2

    def test_shortener_detected(self):
        assert extract_features("https://bit.ly/abc")["is_shortener_domain"] == 1
        assert extract_features("https://example.com/bit.ly/abc")["is_shortener_domain"] == 0

    def test_punycode_detected(self):
        assert extract_features("https://xn--80ak6aa92e.com/")["has_punycode"] == 1

    def test_suspicious_tokens_counted(self):
        f = extract_features("http://example.com/login/verify/account")
        assert f["nb_suspicious_tokens"] == 3

    def test_brand_outside_domain(self):
        assert (
            extract_features("http://paypal.verify-login.example.com/")[
                "has_brand_token_outside_domain"
            ]
            == 1
        )
        # brand in registrable domain itself -> not flagged
        assert (
            extract_features("https://www.paypal.com/signin")[
                "has_brand_token_outside_domain"
            ]
            == 0
        )

    def test_registrable_domain_ignores_deep_subdomains(self):
        # Regression (schema 1.1.0): deep subdomains under a two-part suffix
        # must not leak into the registrable domain.
        assert parse_url("https://a.b.example.co.uk/x").registrable_domain == "example.co.uk"
        assert parse_url("https://example.co.uk/").registrable_domain == "example.co.uk"
        assert parse_url("https://a.b.example.com/").registrable_domain == "example.com"
        # ...otherwise a brand in a subdomain would hide the impersonation.
        assert (
            extract_features("http://login.paypal-verify.secure.co.uk/")[
                "has_brand_token_outside_domain"
            ]
            == 1
        )

    def test_non_standard_port(self):
        assert extract_features("http://example.com:8080/")["has_non_standard_port"] == 1
        assert extract_features("https://example.com:443/")["has_non_standard_port"] == 0

    def test_long_url_handled(self):
        url = "http://example.com/" + "x" * 1900
        f = extract_features(url)
        assert f["url_length"] == len(url)

    def test_double_slash_in_path(self):
        assert extract_features("http://example.com/redirect?to=http://evil.com")[
            "nb_double_slash_path"
        ] >= 1

    def test_no_network_calls(self, monkeypatch):
        """Feature extraction must never open sockets."""
        import socket

        def forbidden(*a, **k):  # pragma: no cover
            raise AssertionError("Network access attempted during feature extraction")

        monkeypatch.setattr(socket, "create_connection", forbidden)
        extract_features("http://example.com/login/verify/account")

    def test_feature_values_finite(self):
        import math

        f = extract_features("http://198.51.100.9/a/login?x=1&y=%20")
        assert all(math.isfinite(v) for v in f.values())


class TestCanonicalisation:
    """Schema 2.0.0: edits that do not change the destination must not change features."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("https://WWW.Example.com", "https://example.com/"),
            ("www.example.com/a?b=1", "example.com/a?b=1"),
            ("http://user:pw@www.example.com:8080?q#f", "http://user:pw@example.com:8080/?q#f"),
            ("https://www.com/", "https://www.com/"),  # never strip down to a bare TLD
            ("http://[2001:db8::1]/x", "http://[2001:db8::1]/x"),
            ("HTTP://Example.COM/Path/A", "http://example.com/Path/A"),  # path case kept
        ],
    )
    def test_canonical_form(self, raw, expected):
        assert canonical_feature_url(raw) == expected

    @pytest.mark.parametrize(
        "a, b",
        [
            ("http://www.paypal-secure.com.example.net/login.php", "http://paypal-secure.com.example.net/login.php"),
            ("https://Example.org", "https://example.org/"),
            ("example.org", "www.example.org/"),
        ],
    )
    def test_meaning_preserving_edits_do_not_change_features(self, a, b):
        assert extract_features(a) == extract_features(b)

    def test_raw_mode_is_available_for_research(self):
        raw = extract_features("http://www.example.com", canonicalize=False)
        canonical = extract_features("http://www.example.com")
        assert raw["nb_dots_hostname"] == 2 and canonical["nb_dots_hostname"] == 1


class TestSchema2Features:
    def test_every_feature_documented(self):
        assert set(FEATURE_NAMES) == set(FEATURE_DESCRIPTIONS)
        assert len(FEATURE_NAMES) == 57

    def test_deception_patterns(self):
        f = extract_features("http://login.paypal.com.secure-check.xyz/www.bank.com/verify/index.php?u=http://a.b")
        assert f["tld_token_in_subdomain"] == 1
        assert f["tld_token_in_path"] == 1
        assert f["http_in_path"] == 1
        assert f["has_page_extension"] == 1
        assert f["domain_label_has_hyphen"] == 1
        assert f["is_root_path"] == 0

    def test_home_page_and_domain_label(self):
        f = extract_features("https://example.org")
        assert f["is_root_path"] == 1
        assert f["has_common_tld"] == 1 and f["tld_length"] == 3
        assert f["domain_label_length"] == 7  # "example"
        assert f["domain_label_has_digit"] == 0

    def test_random_looking_domain(self):
        f = extract_features("http://xkqzrtw9.top/")
        assert f["domain_label_has_digit"] == 1
        assert f["domain_label_max_consonant_run"] == 7
        assert f["domain_label_vowel_ratio"] == 0.0

    def test_ip_host_has_no_domain_label(self):
        f = extract_features("http://198.51.100.7/a")
        assert f["domain_label_length"] == 0 and f["tld_length"] == 0 and f["has_common_tld"] == 0

    def test_word_statistics(self):
        f = extract_features("https://example.com/account-recovery/step_two?id=42")
        assert f["nb_path_words"] == 6  # account, recovery, step, two, id, 42
        assert f["longest_path_word"] == len("recovery")
        assert f["first_dir_length"] == len("account-recovery")


class TestDedup:
    def test_normalisation(self):
        assert normalise_url_for_dedup("HTTPS://Example.com/a/#frag") == normalise_url_for_dedup(
            "https://example.com/a"
        )
        assert normalise_url_for_dedup("https://example.com/a?B=1") != normalise_url_for_dedup(
            "https://example.com/a?b=1"
        )  # query case preserved
