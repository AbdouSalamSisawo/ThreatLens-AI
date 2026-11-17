"""Structured logging setup. Avoids logging full submitted URLs (privacy)."""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S"
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Quiet noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def redact_url(url: str, keep_host: bool = True) -> str:
    """Return a log-safe representation of a URL (host only, path dropped)."""
    if not keep_host:
        return "[redacted]"
    try:
        from urllib.parse import urlsplit

        parts = urlsplit(url.strip())
        host = parts.hostname or "[unparsed]"
        return f"{parts.scheme or 'no-scheme'}://{host}/[redacted]"
    except Exception:  # noqa: BLE001
        return "[redacted]"
