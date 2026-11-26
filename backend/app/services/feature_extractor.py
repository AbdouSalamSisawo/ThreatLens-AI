"""
ThreatLens AI - Shared URL Feature Extractor
=============================================

This module is the SINGLE source of truth for URL feature extraction.
Both the training notebook (Phishing-url-detection-ML project, which keeps
a verbatim copy of this file in threatlens_features/) and the live inference
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

# 1.1.0: registrable-domain fix for deep subdomains under two-part suffixes.
# 2.0.0: features are computed on a canonical form of the URL (leading "www."
#        removed, host lower-cased, empty path written as "/") so that edits
#        which do not change the destination cannot change the prediction;
#        24 additional lexical features (word statistics, registrable-label
#        randomness, TLD tokens out of place, page extensions, ...).
FEATURE_SCHEMA_VERSION = "2.0.0"

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

# Generic TLD strings whose appearance OUTSIDE the real TLD position (in a
# subdomain or the path) is a classic deception pattern, e.g.
# "paypal.com.account-check.example.net" or "example.net/www.bank.com/login".
TLD_TOKENS: frozenset[str] = frozenset(
    {"com", "net", "org", "info", "biz", "ru", "de", "uk", "br", "io"}
)

# The most common generic TLDs (used as a weak "ordinary TLD" indicator).
COMMON_TLDS: frozenset[str] = frozenset({"com", "org", "net", "edu", "gov"})

# Server-side page extensions typical of hosted pages and phishing kits.
PAGE_EXTENSIONS: tuple[str, ...] = (
    ".php", ".html", ".htm", ".asp", ".aspx", ".jsp", ".cgi",
)

_HEX_LABEL_RE = re.compile(r"^[0-9a-f]+$")
_PCT_ENCODED_RE = re.compile(r"%[0-9a-fA-F]{2}")
_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_SPECIAL_CHARS = "!*'();:+$,[]|"
_VOWELS = frozenset("aeiou")


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
    parts = [p for p in hostname.split(".") if p]
    two_part_suffixes = {
        "co.uk", "org.uk", "ac.uk", "gov.uk", "com.my", "edu.my", "gov.my",
        "com.au", "co.nz", "co.jp", "co.kr", "com.sg", "com.br", "co.in",
        "com.tr", "com.mx", "co.za", "com.hk", "com.tw",
    }
    # Keep exactly one label in front of the (possibly two-label) suffix, so
    # deeper subdomains never leak into the registrable domain.
    if len(parts) >= 3 and f"{parts[-2]}.{parts[-1]}" in two_part_suffixes:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
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


def canonical_feature_url(url: str) -> str:
    """
    Canonical form of a URL for feature extraction (schema >= 2.0.0).

    Applies only edits that never change where a URL leads:
      * lower-case the scheme and the host (both are case-insensitive);
      * remove ONE leading "www." label when a real domain remains;
      * write an empty path as "/" ("example.com" == "example.com/").
    Userinfo, port, path, query and fragment are otherwise kept verbatim.

    Without this step a model can learn that "www." means legitimate (a
    collection artefact of crawled corpora) and an attacker could flip a
    verdict simply by adding "www." to a phishing link.
    """
    cleaned = _strip_input(url)
    has_scheme = "://" in cleaned
    scheme, rest = cleaned.split("://", 1) if has_scheme else ("", cleaned)
    split_at = len(rest)
    for sep in "/?#":
        idx = rest.find(sep)
        if idx != -1:
            split_at = min(split_at, idx)
    authority, tail = rest[:split_at], rest[split_at:]
    userinfo, at, hostport = authority.rpartition("@")
    hostport = hostport.lower()
    if hostport.startswith("www.") and "." in hostport[4:].split(":", 1)[0]:
        hostport = hostport[4:]
    if not tail or tail[0] in "?#":
        tail = "/" + tail
    prefix = f"{scheme.lower()}://" if has_scheme else ""
    return f"{prefix}{userinfo}{at}{hostport}{tail}"


def _words(text_lower: str) -> list[str]:
    return [w for w in _WORD_SPLIT_RE.split(text_lower) if w]


def _longest_run(text: str, predicate) -> int:
    best = current = 0
    for ch in text:
        current = current + 1 if predicate(ch) else 0
        best = max(best, current)
    return best


def _max_char_repeat(text: str) -> int:
    best = current = 1 if text else 0
    for prev, ch in zip(text, text[1:]):
        current = current + 1 if ch == prev else 1
        best = max(best, current)
    return best


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
    # --- added in schema 2.0.0 ---
    "nb_slash_url",
    "nb_equal_url",
    "nb_tilde_url",
    "nb_special_chars_url",
    "max_char_repeat",
    "ratio_upper_path",
    "tld_token_in_subdomain",
    "has_common_tld",
    "tld_length",
    "domain_label_length",
    "domain_label_has_digit",
    "domain_label_has_hyphen",
    "domain_label_vowel_ratio",
    "domain_label_max_consonant_run",
    "http_in_path",
    "tld_token_in_path",
    "has_page_extension",
    "is_root_path",
    "first_dir_length",
    "nb_host_words",
    "longest_host_word",
    "nb_path_words",
    "longest_path_word",
    "avg_path_word_length",
)


def extract_features(url: str, canonicalize: bool = True) -> dict[str, float]:
    """
    Extract the full lexical feature vector for a URL.

    Returns an ordered dict keyed by FEATURE_NAMES. Values are ints/floats
    (booleans encoded as 0/1). Raises URLValidationError for unparseable
    input. No network access is performed.

    `canonicalize=False` skips canonical_feature_url(); it exists only so the
    research notebook can measure what canonicalisation buys. Serving and
    training always use the default.
    """
    if canonicalize:
        url = canonical_feature_url(url)
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

    # --- schema 2.0.0 additions --------------------------------------------
    path_query_lower = f"{path}?{query}".lower()
    subdomain = (
        host[: -len(registrable)].rstrip(".")
        if registrable and host.endswith(registrable) and host != registrable
        else ""
    )
    domain_label = "" if has_ip else (registrable.split(".")[0] if registrable else "")
    domain_letters = [ch for ch in domain_label if ch.isalpha()]
    host_words = _words(host)
    path_words = _words(path_query_lower)
    stripped_path = path.strip("/")

    nb_slash_url = full.count("/")
    nb_equal_url = full.count("=")
    nb_tilde_url = full.count("~")
    nb_special_chars_url = sum(full.count(ch) for ch in _SPECIAL_CHARS)
    max_char_repeat = _max_char_repeat(full)
    ratio_upper_path = (sum(ch.isupper() for ch in path) / len(path)) if path else 0.0
    tld_token_in_subdomain = 1 if any(
        label in TLD_TOKENS for label in subdomain.split(".") if label
    ) else 0
    has_common_tld = 1 if (tld in COMMON_TLDS and not has_ip) else 0
    tld_length = 0 if has_ip else len(tld)
    domain_label_length = len(domain_label)
    domain_label_has_digit = 1 if any(ch.isdigit() for ch in domain_label) else 0
    domain_label_has_hyphen = 1 if "-" in domain_label else 0
    domain_label_vowel_ratio = (
        sum(ch in _VOWELS for ch in domain_letters) / len(domain_letters)
        if domain_letters else 0.0
    )
    domain_label_max_consonant_run = _longest_run(
        domain_label, lambda ch: ch.isalpha() and ch not in _VOWELS
    )
    http_in_path = path_query_lower.count("http")
    tld_token_in_path = 1 if any(
        f".{t}/" in path_query_lower or f".{t}?" in path_query_lower
        or path_query_lower.endswith(f".{t}")
        for t in TLD_TOKENS
    ) else 0
    has_page_extension = 1 if path.lower().endswith(PAGE_EXTENSIONS) else 0
    is_root_path = 1 if (path in ("", "/") and not query) else 0
    first_dir_length = len(stripped_path.split("/")[0]) if stripped_path else 0

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
        "nb_slash_url": nb_slash_url,
        "nb_equal_url": nb_equal_url,
        "nb_tilde_url": nb_tilde_url,
        "nb_special_chars_url": nb_special_chars_url,
        "max_char_repeat": max_char_repeat,
        "ratio_upper_path": round(ratio_upper_path, 6),
        "tld_token_in_subdomain": tld_token_in_subdomain,
        "has_common_tld": has_common_tld,
        "tld_length": tld_length,
        "domain_label_length": domain_label_length,
        "domain_label_has_digit": domain_label_has_digit,
        "domain_label_has_hyphen": domain_label_has_hyphen,
        "domain_label_vowel_ratio": round(domain_label_vowel_ratio, 6),
        "domain_label_max_consonant_run": domain_label_max_consonant_run,
        "http_in_path": http_in_path,
        "tld_token_in_path": tld_token_in_path,
        "has_page_extension": has_page_extension,
        "is_root_path": is_root_path,
        "first_dir_length": first_dir_length,
        "nb_host_words": len(host_words),
        "longest_host_word": max((len(w) for w in host_words), default=0),
        "nb_path_words": len(path_words),
        "longest_path_word": max((len(w) for w in path_words), default=0),
        "avg_path_word_length": round(
            sum(len(w) for w in path_words) / len(path_words), 6
        ) if path_words else 0.0,
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
    "nb_slash_url": "Number of '/' characters in the full URL.",
    "nb_equal_url": "Number of '=' characters (query assignments) in the URL.",
    "nb_tilde_url": "Number of '~' characters (often user home directories on shared hosting).",
    "nb_special_chars_url": "Number of unusual punctuation characters such as ! * ' ( ) ; : + $ , [ ] |.",
    "max_char_repeat": "Longest run of the same character repeated in a row.",
    "ratio_upper_path": "Share of upper-case letters in the path (random-looking paths mix case).",
    "tld_token_in_subdomain": "A domain ending such as 'com' or 'net' appears as a subdomain label (e.g. paypal.com.example.net).",
    "has_common_tld": "The domain ends in a very common ending (.com, .org, .net, .edu, .gov).",
    "tld_length": "Length of the domain ending (top-level domain).",
    "domain_label_length": "Length of the main domain name, without subdomains or ending.",
    "domain_label_has_digit": "The main domain name contains a digit.",
    "domain_label_has_hyphen": "The main domain name contains a hyphen.",
    "domain_label_vowel_ratio": "Share of vowels among letters in the main domain name (random names have few).",
    "domain_label_max_consonant_run": "Longest run of consecutive consonants in the main domain name.",
    "http_in_path": "Times 'http' appears inside the path or query (an embedded second link).",
    "tld_token_in_path": "A domain-like string such as '.com/' appears inside the path or query.",
    "has_page_extension": "Path ends with a server page extension such as .php or .html.",
    "is_root_path": "The URL points at a site's home page (no path or query).",
    "first_dir_length": "Length of the first folder name in the path.",
    "nb_host_words": "Number of words in the hostname.",
    "longest_host_word": "Length of the longest word in the hostname.",
    "nb_path_words": "Number of words in the path and query.",
    "longest_path_word": "Length of the longest word in the path and query.",
    "avg_path_word_length": "Average word length in the path and query.",
}
