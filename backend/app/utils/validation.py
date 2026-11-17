"""Server-side input validation for URL submissions (never trust the client)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.feature_extractor import URLValidationError, parse_url

ALLOWED_SCHEMES = {"http", "https", ""}  # "" = bare domain (documented rule)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    cleaned_url: str | None = None


def validate_url_input(raw: object, max_url_length: int) -> ValidationResult:
    """
    Validate a submitted URL string.

    Rules (documented in the API docs and Security & Privacy page):
    * Must be a string, non-empty, within the configured length limit.
    * http:// and https:// are accepted. A bare domain (e.g. example.com)
      is accepted as a documented convenience; the response records that
      no scheme was present in the original submission.
    * Other schemes (ftp:, javascript:, data:, file:, ...) are rejected.
    * Control characters and non-URL junk are rejected.
    * The URL is never fetched, normalised silently, or re-written to a
      different destination.
    """
    if not isinstance(raw, str):
        return ValidationResult(False, "invalid_type", "The URL must be a string.")
    cleaned = raw.strip()
    if not cleaned:
        return ValidationResult(False, "empty_input", "No URL was submitted.")
    if len(cleaned) > max_url_length:
        return ValidationResult(
            False,
            "url_too_long",
            f"The URL exceeds the maximum supported length of {max_url_length} characters.",
        )
    if any(ord(ch) < 32 or ch == "\x7f" for ch in cleaned):
        return ValidationResult(
            False, "invalid_characters", "The URL contains control characters."
        )

    lowered = cleaned.lower()
    if "://" in lowered:
        scheme = lowered.split("://", 1)[0]
        if scheme not in {"http", "https"}:
            return ValidationResult(
                False,
                "unsupported_scheme",
                "Only http:// and https:// URLs are supported.",
            )
    elif " " in cleaned or cleaned.startswith(("/", "#", "?")):
        return ValidationResult(
            False,
            "invalid_url",
            "This does not look like a URL. Include a domain such as example.com.",
        )
    elif ":" in cleaned.split("/")[0]:
        return ValidationResult(
            False,
            "unsupported_scheme",
            "Only http:// and https:// URLs are supported.",
        )

    try:
        parsed = parse_url(cleaned)
    except URLValidationError as exc:
        return ValidationResult(False, "invalid_url", str(exc))

    if parsed.hostname in {"localhost"} or parsed.hostname.endswith(".local"):
        return ValidationResult(
            False,
            "hostname_not_analysable",
            "Local hostnames cannot be analysed meaningfully by a URL scanner.",
        )

    return ValidationResult(True, cleaned_url=cleaned)
