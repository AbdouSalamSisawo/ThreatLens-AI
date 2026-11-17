"""Supabase access-token verification (security-critical).

Every protected endpoint depends on :func:`get_current_user`, which:

1. Extracts ``Authorization: Bearer <access_token>``.
2. Verifies the token cryptographically when the project publishes asymmetric
   signing keys (JWKS, ES256/RS256) - signature, expiry, issuer, audience and
   ``sub`` are all checked with PyJWT. Keys are fetched from the project's
   JWKS endpoint and cached (``PyJWKClient`` handles rotation via ``kid``).
3. Falls back to validating the token against the Supabase Auth ``/user``
   endpoint when only symmetric (HS256) signing is configured. That endpoint
   returns a user record only for a live, valid session, so claims are taken
   from the verified response - never from an unverified JWT decode.
4. Derives the authenticated user id exclusively from the verified claims
   (``sub``). A user id supplied by the browser is never trusted.

Verification strategy is controlled by ``SUPABASE_AUTH_MODE``:
``auto`` (default: JWKS when asymmetric keys are published, otherwise the
/user endpoint), ``jwks`` (force signature verification) or ``userinfo``
(force the /user endpoint check).

Tokens are never logged. Verification failures return HTTP 401 in the
application's standard ``{"error": {...}}`` envelope.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient, PyJWKClientError
from jwt.exceptions import InvalidTokenError

from app.core.config import Settings

logger = logging.getLogger("threatlens.auth")

# Only asymmetric algorithms published via JWKS are accepted for local
# signature verification. HS256 secrets are never published in a JWKS, so a
# symmetric project automatically falls back to the /user endpoint check.
_ALLOWED_ASYMMETRIC_ALGS = {
    "ES256", "ES384", "ES512",
    "RS256", "RS384", "RS512",
    "PS256", "PS384", "PS512",
}

_JWKS_CLIENTS: dict[str, PyJWKClient] = {}
_JWKS_LOCK = threading.Lock()


class TokenRejected(Exception):
    """Raised internally when a token cannot be accepted."""


class _JwksUnavailable(Exception):
    """JWKS verification is not possible for this token/project."""


@dataclass(frozen=True)
class AuthUser:
    """Authenticated identity derived ONLY from verified token claims."""

    id: str
    email: str | None
    token: str  # the caller's own access token (never logged)
    claims: dict[str, Any] = field(default_factory=dict, repr=False)

    def __repr__(self) -> str:  # pragma: no cover - keep tokens out of logs
        return f"AuthUser(id={self.id!r}, email={self.email!r})"


def _jwks_client(settings: Settings) -> PyJWKClient:
    """Per-project JWKS client with local key caching (rotation-safe)."""
    url = f"{settings.supabase_url_clean}/auth/v1/.well-known/jwks.json"
    with _JWKS_LOCK:
        client = _JWKS_CLIENTS.get(url)
        if client is None:
            client = PyJWKClient(
                url, cache_keys=True, lifespan=600, max_cached_keys=16
            )
            _JWKS_CLIENTS[url] = client
        return client


def _verify_via_jwks(token: str, settings: Settings) -> dict[str, Any]:
    """Full cryptographic verification against the project's trusted JWKS."""
    # Shape check first: an unparsable token can never be saved by a
    # fallback, so reject it outright instead of bouncing it to /user.
    try:
        jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise TokenRejected("unparsable token") from exc

    try:
        signing_key = _jwks_client(settings).get_signing_key_from_jwt(token)
    except PyJWKClientError as exc:
        # No published keys / no matching kid for this token / JWKS
        # unreachable - a live HS256 session token may still be verified by
        # the /user endpoint, hence _JwksUnavailable (not TokenRejected).
        raise _JwksUnavailable(str(exc)) from exc

    alg = getattr(signing_key, "algorithm_name", None)
    if alg not in _ALLOWED_ASYMMETRIC_ALGS:
        raise _JwksUnavailable(f"unsupported signing algorithm {alg!r}")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience=settings.supabase_jwt_audience_list,
            issuer=settings.supabase_jwt_issuer,
            leeway=settings.supabase_jwt_leeway_seconds,
            options={"require": ["exp", "iat", "sub"]},
        )
    except InvalidTokenError as exc:
        raise TokenRejected(f"token rejected: {type(exc).__name__}") from exc

    if claims.get("role") not in (None, "authenticated"):
        # e.g. service_role tokens must never be accepted on user endpoints.
        raise TokenRejected("unsupported token role")
    return claims


def _verify_via_userinfo(token: str, settings: Settings) -> dict[str, Any]:
    """Secure fallback: validate the token against Supabase Auth /user.

    The endpoint answers 200 only for a live, valid session token, so the
    returned identity is authoritative. Claims are built from that verified
    response - the JWT itself is never decoded-and-trusted here.
    """
    url = f"{settings.supabase_url_clean}/auth/v1/user"
    try:
        resp = httpx.get(
            url,
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise TokenRejected(
            "auth provider unreachable while validating token"
        ) from exc

    if resp.status_code != 200:
        raise TokenRejected("token not accepted by Supabase Auth")
    user = resp.json()
    user_id = user.get("id")
    if not user_id:
        raise TokenRejected("token not associated with a user")
    return {
        "sub": str(user_id),
        "email": user.get("email"),
        "role": "authenticated",
        "verified_by": "userinfo_endpoint",
    }


def verify_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Verify an access token and return its verified claims.

    Raises :class:`TokenRejected` for any unacceptable token.
    """
    if not settings.supabase_configured:
        raise TokenRejected("auth_not_configured")

    mode = settings.supabase_auth_mode.lower().strip()
    if mode in ("auto", "jwks"):
        try:
            return _verify_via_jwks(token, settings)
        except _JwksUnavailable as exc:
            logger.info("JWKS verification unavailable (%s)", exc)
            if mode == "jwks":
                raise TokenRejected("token could not be verified via JWKS")
            # auto: fall through to the /user endpoint check
    elif mode != "userinfo":
        logger.warning("Unknown SUPABASE_AUTH_MODE %r - using auto", mode)

    return _verify_via_userinfo(token, settings)


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request) -> AuthUser:
    """FastAPI dependency: authenticate the caller from their access token."""
    settings: Settings = request.app.state.settings

    if not settings.supabase_configured:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "auth_not_configured",
                "message": (
                    "Authentication is not configured on the server. Set "
                    "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the backend "
                    "environment and restart the API."
                ),
            },
        )

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise _unauthorized(
            "missing_token",
            "Authentication required. Send 'Authorization: Bearer <access_token>'.",
        )
    token = header[len("Bearer "):].strip()
    if not token:
        raise _unauthorized("missing_token", "Access token is empty.")

    try:
        claims = verify_access_token(token, settings)
    except TokenRejected:
        # Deliberately vague: never disclose why a token failed.
        raise _unauthorized(
            "invalid_token", "The session token is missing, invalid or expired."
        ) from None

    user_id = claims.get("sub")
    if not user_id:
        raise _unauthorized("invalid_token", "The session token has no subject.")

    return AuthUser(
        id=str(user_id),
        email=claims.get("email") if isinstance(claims.get("email"), str) else None,
        token=token,
        claims=claims,
    )
