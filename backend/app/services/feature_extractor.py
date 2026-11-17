"""
ThreatLens AI - Shared URL Feature Extractor
=============================================

This module is the SINGLE source of truth for URL feature extraction.
Both the training notebook (ml/notebooks/) and the live inference
endpoint (backend/app/services/inference_service.py) MUST use this module
so that the feature schema is identical between training and serving.

FEATURE_SCHEMA_VERSION: bump whenever the feature list changes. A trained
model records the schema version it was trained with; the API refuses to
serve if the versions mismatch.

Design principles
-----------------
* Lexical only: features are computed from the URL string alone.
* No network requests are ever made. The submitted destination is NOT
  contacted (SSRF-safe by construction).
* All features are signals, never verdicts on their own. A URL containing
  digits, an unusual path, or even a suspicious token can be perfectly
  legitimate. Interpretation belongs to the trained model + explanation
  service, not to any single feature.
* Generic token lists (suspicious words, shorteners, TLDs, brands) are
  transparent, documented, and intentionally conservative. They are
  heuristics feeding a statistical model - not rules that decide outcomes.
* Malformed input raises URLValidationError; extraction never silently
  invents structure.
"""

from __future__ import annotations

import ipaddress
import math
import re
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlsplit

FEATURE_SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Documented reference lists (transparent, generic, manually curated)
# ---------------------------------------------------------------------------

# Well-known URL shortener domains (documented heuristic list).
SHORTENER_DOMAINS: frozenset[str] = frozenset(
    {
        "bit.ly", "bitly.com", "tinyurl.com", "goo.gl", "t.co", "is.gd",
        "ow.ly", "buff.ly", "adf.ly", "bit.do", "cutt.ly", "rb.gy",
        "rebrand.ly", "s.id", "lnkd.in", "shorturl.at", "tiny.cc",
        "v.gd", "x.gd", "shorte.st", "shrtco.de", "gg.gg", "urlz.fr",
    }
)

# TLDs that statistically over-index in abuse reports. Presence is a weak
# signal only - legitimate sites also use these TLDs.
SUSPICIOUS_TLDS: frozenset[str] = frozenset(
    {
        "tk", "ml", "ga", "cf", "gq", "xyz", "top", "buzz", "click", "work",
        "link", "zip", "mov", "rest", "fit", "cam", "cfd", "sbs", "quest",
        "surf", "monster", "lol", "bar", "rest", "icu", "cyou", "live",
    }
)

# Generic security/urgency vocabulary commonly abused in phishing URLs.
# Meaning always depends on the full URL and the trained model.
SUSPICIOUS_TOKENS: frozenset[str] = frozenset(
    {
        "login", "log-in", "signin", "sign-in", "verify", "verification",
        "account", "update", "secure", "security", "webscr", "banking",
        "confirm", "password", "credential", "credentials", "wallet",
        "invoice", "payment", "bonus", "giveaway", "unlock", "urgent",
        "alert", "suspended", "locked", "recovery", "authenticate",
    }
)

# Popular brand names frequently impersonated. The feature fires only when
# a brand token appears somewhere in the URL while the registrable domain
# does not contain that token (e.g. "paypal.verify-account.example.com").
BRAND_TOKENS: frozenset[str] = frozenset(
    {
        "paypal", "apple", "icloud", "microsoft", "office365", "outlook",
        "gmail", "google", "facebook", "instagram", "whatsapp", "netflix",
        "amazon", "ebay", "dhl", "fedex", "linkedin", "twitter", "binance",
        "coinbase", "maybank", "cimb", "grab", "spotify", "steam",
    }
)

# Executable / archive file extensions that should rarely appear in a
# navigational link.
EXECUTABLE_EXTENSIONS: frozenset[str] = frozenset(
    {".exe", ".scr", ".msi", ".bat", ".cmd", ".apk", ".jar", ".vbs", ".ps1"}
)

# Standard ports for HTTP/HTTPS.
STANDARD_PORTS: frozenset[int] = frozenset({80, 443})

_HEX_LABEL_RE = re.compile(r"^[0-9a-f]+$")
_PCT_ENCODED_RE = re.compile(r"%[0-9a-fA-F]{2}")


class URLValidationError(ValueError):
    """Raised when a URL cannot be parsed safely for feature extraction."""


@dataclass(frozen=True)
class ParsedURL:
    """Structural parse of a URL, kept separate from numeric features."""

    raw: str
    scheme: str
    hostname: str
    port: int | None
    path: str
    query: str
    fragment: str
    registrable_domain: str
    scheme_was_inferred: bool


def _strip_input(url: str) -> str:
    if not isinstance(url, str):
        raise URLValidationError("URL must be a string")
    stripped = url.strip()
    if not stripped:
        raise URLValidationError("URL is empty")
    if len(stripped) > 4096:
        raise URLValidationError("URL exceeds the maximum supported length")
    # Control characters cannot appear in real navigable URLs.
    if any(ord(ch) < 32 for ch in stripped):
        raise URLValidationError("URL contains control characters")
    return stripped


def _registrable_domain_of(hostname: str) -> str:
    """
    Approximate the registrable domain with a small multi-label suffix list
    (e.g. co.uk, com.my). A full Public Suffix List is intentionally not
    used to keep the prototype dependency-free; the approximation is only
    used for the brand-impersonation heuristic and grouping heuristics.
    """
    parts = hostname.rsplit(".", 2)
    two_part_suffixes = {
        "co.uk", "org.uk", "ac.uk", "gov.uk", "com.my", "edu.my", "gov.my",
        "com.au", "co.nz", "co.jp", "co.kr", "com.sg", "com.br", "co.in",
        "com.tr", "com.mx", "co.za", "com.hk", "com.tw",
    }
    if len(parts) == 3 and f"{parts[1]}.{parts[2]}" in two_part_suffixes:
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return hostname


def parse_url(url: str) -> ParsedURL:
    """
    Parse a URL string into structural components.

    A bare domain (e.g. "example.com") is accepted for convenience: the
    scheme is inferred ONLY for parsing purposes and `scheme_was_inferred`
    records this. Features never pretend the original input had a scheme.
    """
    cleaned = _strip_input(url)
    if "://" not in cleaned:
        parsed_for_structure = urlsplit(f"http://{cleaned}")
        scheme_was_inferred = True
    else:
        parsed_for_structure = urlsplit(cleaned)
        scheme_was_inferred = False

    scheme = (parsed_for_structure.scheme or "").lower()
    hostname = (parsed_for_structure.hostname or "").rstrip(".")
    if not hostname:
        raise URLValidationError("URL has no parseable hostname")

    try:
        hostname.encode("ascii")
    except UnicodeEncodeError:
        # IDN hostnames are accepted; the punycode feature will not fire,
        # but the non-ascii indicator is handled by the caller if needed.
        pass

    try:
        port = parsed_for_structure.port  # May raise ValueError for bad ports
    except ValueError as exc:
        raise URLValidationError("URL has an invalid port") from exc

    raw_scheme = cleaned.split("://", 1)[0].lower() if "://" in cleaned else ""
    return ParsedURL(
        raw=cleaned,
        scheme=scheme,
        hostname=hostname.lower(),
        port=port,
        path=parsed_for_structure.path or "",
        query=parsed_for_structure.query or "",
        fragment=parsed_for_structure.fragment or "",
        registrable_domain=_registrable_domain_of(hostname.lower()),
        scheme_was_inferred=scheme_was_inferred,
    )


def _shannon_entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def _is_ip_address(hostname: str) -> bool:
    candidate = hostname
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    try:
        ipaddress.ip_address(candidate)
        return True
    except ValueError:
        return False


def _token_hits(text_lower: str, tokens: frozenset[str]) -> int:
    hits = 0
    for token in tokens:
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text_lower):
            hits += 1
    return hits


# ---------------------------------------------------------------------------
# Feature computation
# ---------------------------------------------------------------------------

# NOTE: the ORDER of FEATURE_NAMES is part of the schema contract. It must
# never change without bumping FEATURE_SCHEMA_VERSION and retraining.
FEATURE_NAMES: tuple[str, ...] = (
    "url_length",
    "hostname_length",
    "path_length",
    "query_length",
    "nb_dots_url",
    "nb_dots_hostname",
    "nb_subdomain_labels",
    "nb_hyphens_url",
    "nb_hyphens_hostname",
    "nb_underscores_url",
    "nb_digits_url",
    "nb_digits_hostname",
    "ratio_digits_url",
    "ratio_digits_hostname",
    "nb_pct_encoded",
    "nb_query_params",
    "nb_ampersand",
    "nb_at_symbol",
    "nb_double_slash_path",
    "path_depth",
    "has_ip",
    "has_non_standard_port",
    "is_https",
    "has_credentials_pattern",
    "is_shortener_domain",
    "has_punycode",
    "has_suspicious_tld",
    "has_executable_extension",
    "has_long_hostname",
    "nb_suspicious_tokens",
    "has_brand_token_outside_domain",
    "nb_hex_labels_hostname",
    "hostname_entropy",
)


def extract_features(url: str) -> dict[str, float]:
    """
    Extract the full lexical feature vector for a URL.

    Returns an ordered dict keyed by FEATURE_NAMES. Values are ints/floats
    (booleans encoded as 0/1). Raises URLValidationError for unparseable
    input. No network access is performed.
    """
    p = parse_url(url)

    full = p.raw
    host = p.hostname
    path = p.path
    query = p.query

    path_no_scheme = full.split("://", 1)[-1] if "://" in full else full

    url_length = len(full)
    hostname_length = len(host)
    path_length = len(path)
    query_length = len(query)

    nb_dots_url = full.count(".")
    nb_dots_hostname = host.count(".")
    host_labels = [label for label in host.split(".") if label]
    nb_subdomain_labels = max(0, len(host_labels) - 2)

    nb_hyphens_url = full.count("-")
    nb_hyphens_hostname = host.count("-")
    nb_underscores_url = full.count("_")
    nb_digits_url = sum(ch.isdigit() for ch in full)
    nb_digits_hostname = sum(ch.isdigit() for ch in host)
    ratio_digits_url = nb_digits_url / url_length if url_length else 0.0
    ratio_digits_hostname = (
        nb_digits_hostname / hostname_length if hostname_length else 0.0
    )

    nb_pct_encoded = len(_PCT_ENCODED_RE.findall(full))

    query_params: list[str] = []
    if query:
        query_params = [part for part in query.split("&") if part]
    nb_query_params = len(query_params)
    nb_ampersand = full.count("&")

    nb_at_symbol = full.count("@")

    # A "//" appearing inside the path indicates a possible open-redirect or
    # defacement-style URL; the scheme's "://" is excluded.
    nb_double_slash_path = path_no_scheme.split("/", 1)[-1].count("//")

    path_segments = [seg for seg in path.split("/") if seg]
    path_depth = len(path_segments)

    has_ip = 1 if _is_ip_address(host) else 0
    has_non_standard_port = (
        1 if (p.port is not None and p.port not in STANDARD_PORTS) else 0
    )
    is_https = 1 if (not p.scheme_was_inferred and p.scheme == "https") else 0

    userinfo = ""
    if "@" in path_no_scheme.split("/", 1)[0]:
        userinfo = path_no_scheme.split("/", 1)[0].split("@", 1)[0]
    has_credentials_pattern = 1 if ":" in userinfo else 0

    is_shortener_domain = 1 if host in SHORTENER_DOMAINS else 0
    has_punycode = 1 if any(label.startswith("xn--") for label in host_labels) else 0

    tld = host_labels[-1] if host_labels else ""
    has_suspicious_tld = 1 if tld in SUSPICIOUS_TLDS else 0

    last_segment = path_segments[-1].lower() if path_segments else ""
    has_executable_extension = 1 if any(
        last_segment.endswith(ext) for ext in EXECUTABLE_EXTENSIONS
    ) else 0

    has_long_hostname = 1 if hostname_length >= 30 else 0

    searchable = f"{host}{path}?{query}".lower()
    nb_suspicious_tokens = _token_hits(searchable, SUSPICIOUS_TOKENS)

    brand_hits = _token_hits(searchable, BRAND_TOKENS)
    registrable = p.registrable_domain.lower()
    brand_outside = 1 if brand_hits > 0 and not any(
        b in registrable for b in BRAND_TOKENS
    ) else 0

    nb_hex_labels = sum(
        1
        for label in host_labels
        if len(label) >= 8 and _HEX_LABEL_RE.match(label)
    )

    features: dict[str, float] = {
        "url_length": url_length,
        "hostname_length": hostname_length,
        "path_length": path_length,
        "query_length": query_length,
        "nb_dots_url": nb_dots_url,
        "nb_dots_hostname": nb_dots_hostname,
        "nb_subdomain_labels": nb_subdomain_labels,
        "nb_hyphens_url": nb_hyphens_url,
        "nb_hyphens_hostname": nb_hyphens_hostname,
        "nb_underscores_url": nb_underscores_url,
        "nb_digits_url": nb_digits_url,
        "nb_digits_hostname": nb_digits_hostname,
        "ratio_digits_url": ratio_digits_url,
        "ratio_digits_hostname": ratio_digits_hostname,
        "nb_pct_encoded": nb_pct_encoded,
        "nb_query_params": nb_query_params,
        "nb_ampersand": nb_ampersand,
        "nb_at_symbol": nb_at_symbol,
        "nb_double_slash_path": nb_double_slash_path,
        "path_depth": path_depth,
        "has_ip": has_ip,
        "has_non_standard_port": has_non_standard_port,
        "is_https": is_https,
        "has_credentials_pattern": has_credentials_pattern,
        "is_shortener_domain": is_shortener_domain,
        "has_punycode": has_punycode,
        "has_suspicious_tld": has_suspicious_tld,
        "has_executable_extension": has_executable_extension,
        "has_long_hostname": has_long_hostname,
        "nb_suspicious_tokens": nb_suspicious_tokens,
        "has_brand_token_outside_domain": brand_outside,
        "nb_hex_labels_hostname": nb_hex_labels,
        "hostname_entropy": round(_shannon_entropy(host), 6),
    }

    assert tuple(features.keys()) == FEATURE_NAMES, "Feature order drifted"
    return features


def feature_vector(url: str) -> list[float]:
    """Feature values as a plain list in FEATURE_NAMES order."""
    feats = extract_features(url)
    return [float(feats[name]) for name in FEATURE_NAMES]


def normalise_url_for_dedup(url: str) -> str:
    """
    Canonical form used for de-duplication and leakage checks:
    lowercase scheme/host, drop fragment and surrounding whitespace,
    strip a single trailing slash. Path/query case is preserved.
    """
    p = parse_url(url)
    base = f"{p.scheme}://{p.hostname}" if p.scheme else f"//{p.hostname}"
    if p.port is not None:
        base += f":{p.port}"
    target = p.path.rstrip("/")
    if p.query:
        target += f"?{p.query}"
    return f"{base}{target}"


# ---------------------------------------------------------------------------
# Feature documentation (surfaced by the API and the UI)
# ---------------------------------------------------------------------------

FEATURE_DESCRIPTIONS: dict[str, str] = {
    "url_length": "Total character length of the submitted URL.",
    "hostname_length": "Character length of the hostname.",
    "path_length": "Character length of the path component.",
    "query_length": "Character length of the query string.",
    "nb_dots_url": "Number of '.' characters in the full URL.",
    "nb_dots_hostname": "Number of '.' characters in the hostname.",
    "nb_subdomain_labels": "Estimated number of subdomain labels beyond registrable domain.",
    "nb_hyphens_url": "Number of '-' characters in the full URL.",
    "nb_hyphens_hostname": "Number of '-' characters in the hostname.",
    "nb_underscores_url": "Number of '_' characters in the full URL.",
    "nb_digits_url": "Number of digit characters in the full URL.",
    "nb_digits_hostname": "Number of digit characters in the hostname.",
    "ratio_digits_url": "Share of digit characters in the full URL.",
    "ratio_digits_hostname": "Share of digit characters in the hostname.",
    "nb_pct_encoded": "Number of percent-encoded sequences (e.g. %20).",
    "nb_query_params": "Number of query-string parameters.",
    "nb_ampersand": "Number of '&' characters in the full URL.",
    "nb_at_symbol": "Number of '@' characters (can hide the real host).",
    "nb_double_slash_path": "Occurrences of '//' inside path/query (open-redirect style).",
    "path_depth": "Number of path segments.",
    "has_ip": "Hostname is an IPv4/IPv6 address instead of a domain name.",
    "has_non_standard_port": "Explicit port that is not 80/443.",
    "is_https": "Original submission used the https:// scheme.",
    "has_credentials_pattern": "Userinfo section contains 'user:password@'.",
    "is_shortener_domain": "Domain appears on the documented URL-shortener list.",
    "has_punycode": "Hostname contains punycode ('xn--') labels.",
    "has_suspicious_tld": "TLD appears on the documented high-abuse TLD list.",
    "has_executable_extension": "Path ends with an executable/archive extension.",
    "has_long_hostname": "Hostname is 30 characters or longer.",
    "nb_suspicious_tokens": "Count of generic security/urgency terms from the documented list.",
    "has_brand_token_outside_domain": "A known brand token appears in the URL but not in the registrable domain.",
    "nb_hex_labels_hostname": "Hostname labels that are long hexadecimal strings.",
    "hostname_entropy": "Shannon entropy of hostname characters (randomness indicator).",
}
