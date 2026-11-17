"""
URL parsing service.

Thin wrapper over the shared feature-extractor parser. The core scanner
NEVER contacts the submitted destination: there is no HTTP client, browser,
redirect resolver, or screenshot capability anywhere in the scan path.
"""

from __future__ import annotations

from app.services.feature_extractor import ParsedURL, parse_url


def parse(url: str) -> ParsedURL:
    """Parse a validated URL string. No network I/O occurs."""
    return parse_url(url)
