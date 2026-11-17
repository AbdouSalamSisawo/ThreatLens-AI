"""Authentication & authorization tests (security-critical).

Covers the REAL get_current_user dependency end-to-end:
  * valid ES256 token via (mocked) JWKS -> accepted
  * missing / malformed / expired / wrong-issuer / wrong-audience /
    tampered tokens -> HTTP 401
  * service_role-style tokens rejected
  * secure fallback to the Supabase Auth /user endpoint when JWKS is
    unavailable (auto mode) - and 401 when that endpoint rejects the token
  * unauthenticated access to protected endpoints -> 401
  * public endpoints stay public
  * a browser-supplied user id can never override the verified identity
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import create_app  # noqa: E402
from tests.conftest import ISSUER, USER_A, make_test_settings, mint_token  # noqa: E402


@pytest.fixture()
def real_client(test_settings, fake_jwks):
    """Client WITHOUT dependency overrides: the real auth dependency runs."""
    app = create_app(test_settings)
    with TestClient(app) as c:
        yield c


def _auth(token: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


class TestTokenVerification:
    def test_valid_token_accepted(self, real_client, es256_keypair):
        token = mint_token(es256_keypair, USER_A.id)
        r = real_client.get("/api/history", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 0  # new user -> empty history

    def test_missing_authorization_header(self, real_client):
        r = real_client.get("/api/history")
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "missing_token"
        assert r.headers.get("www-authenticate") == "Bearer"

    def test_malformed_authorization_header(self, real_client):
        r = real_client.get("/api/history", headers={"Authorization": "Basic abc"})
        assert r.status_code == 401
        r = real_client.get("/api/history", headers={"Authorization": "Bearer "})
        assert r.status_code == 401

    def test_garbage_token(self, real_client):
        r = real_client.get("/api/history", headers=_auth("not-a-jwt"))
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "invalid_token"

    def test_expired_token(self, real_client, es256_keypair):
        token = mint_token(es256_keypair, USER_A.id, exp=int(time.time()) - 7200)
        r = real_client.get("/api/history", headers=_auth(token))
        assert r.status_code == 401

    def test_wrong_issuer(self, real_client, es256_keypair):
        token = mint_token(
            es256_keypair, USER_A.id, iss="https://evil.example.com/auth/v1"
        )
        r = real_client.get("/api/history", headers=_auth(token))
        assert r.status_code == 401

    def test_wrong_audience(self, real_client, es256_keypair):
        token = mint_token(es256_keypair, USER_A.id, aud="some-other-aud")
        r = real_client.get("/api/history", headers=_auth(token))
        assert r.status_code == 401

    def test_missing_sub_claim(self, real_client, es256_keypair):
        token = mint_token(es256_keypair, USER_A.id, sub=None)
        # jwt.encode drops None values; build a token without sub instead.
        import jwt as pyjwt

        now = int(time.time())
        payload = {
            "aud": "authenticated", "exp": now + 600, "iat": now,
            "iss": ISSUER, "role": "authenticated",
        }
        token = pyjwt.encode(
            payload, es256_keypair, algorithm="ES256", headers={"kid": "test-kid"}
        )
        r = real_client.get("/api/history", headers=_auth(token))
        assert r.status_code == 401

    def test_service_role_rejected(self, real_client, es256_keypair):
        token = mint_token(es256_keypair, USER_A.id, role="service_role")
        r = real_client.get("/api/history", headers=_auth(token))
        assert r.status_code == 401

    def test_tampered_signature(self, real_client, es256_keypair):
        token = mint_token(es256_keypair, USER_A.id)
        header, payload, sig = token.split(".")
        tampered = f"{header}.{payload}.{sig[:-4]}aaaa"
        r = real_client.get("/api/history", headers=_auth(tampered))
        assert r.status_code == 401

    def test_wrong_key_signature(self, real_client):
        from cryptography.hazmat.primitives.asymmetric import ec

        other_key = ec.generate_private_key(ec.SECP256R1())
        token = mint_token(other_key, USER_A.id)
        r = real_client.get("/api/history", headers=_auth(token))
        assert r.status_code == 401


class TestUserinfoFallback:
    """auto mode: when JWKS cannot verify, the /user endpoint must confirm."""

    @pytest.fixture()
    def no_jwks_client(self, test_settings, es256_keypair, monkeypatch):
        """Force JWKS to fail (simulating an HS256-only project) and stub the
        Supabase Auth /user endpoint with a controllable fake that - like the
        real GoTrue - only accepts tokens signed by its own key."""
        import jwt as pyjwt
        import app.core.auth as auth_module

        class FailingClient:
            def get_signing_key_from_jwt(self, token):
                raise auth_module.PyJWKClientError("no asymmetric keys published")

        monkeypatch.setattr(
            auth_module, "_jwks_client", lambda settings: FailingClient()
        )

        calls: list[str] = []

        def _fake_user_endpoint(url, headers=None, **kwargs):  # noqa: ANN001
            auth_header = (headers or {}).get("Authorization", "")
            token = auth_header.removeprefix("Bearer ")
            calls.append(token)
            try:
                # Simulate the provider checking the signature with its key.
                pyjwt.decode(
                    token,
                    es256_keypair.public_key(),
                    algorithms=["ES256"],
                    audience=["authenticated"],
                    leeway=10,
                )
                status, payload_user = 200, {"id": USER_A.id, "email": USER_A.email}
            except Exception:  # noqa: BLE001
                status, payload_user = 401, {"error": "invalid_grant"}

            class Resp:
                def __init__(self, code: int, body: dict):
                    self.status_code = code
                    self._body = body

                def json(self):  # noqa: ANN202
                    return self._body

            return Resp(status, payload_user)

        monkeypatch.setattr(auth_module.httpx, "get", _fake_user_endpoint)
        app = create_app(test_settings)
        with TestClient(app) as c:
            yield c, calls

    def test_userinfo_fallback_accepts_live_session(
        self, no_jwks_client, es256_keypair
    ):
        client, calls = no_jwks_client
        token = mint_token(es256_keypair, USER_A.id)
        r = client.get("/api/history", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert len(calls) == 1  # exactly one /user validation call

    def test_userinfo_fallback_rejects_unknown_token(self, no_jwks_client):
        client, _ = no_jwks_client
        # Signed by a different (unknown) key AND not a live session.
        from cryptography.hazmat.primitives.asymmetric import ec

        other = ec.generate_private_key(ec.SECP256R1())
        token = mint_token(other, USER_A.id)
        r = client.get("/api/history", headers=_auth(token))
        assert r.status_code == 401


class TestProtectedEndpoints:
    def test_scan_requires_auth(self, anon_client):
        r = anon_client.post("/api/scan", json={"url": "https://www.wikipedia.org/"})
        assert r.status_code == 401
        assert "error" in r.json()

    def test_history_requires_auth(self, anon_client):
        assert anon_client.get("/api/history").status_code == 401

    def test_dashboard_requires_auth(self, anon_client):
        assert anon_client.get("/api/dashboard").status_code == 401

    def test_profile_requires_auth(self, anon_client):
        assert anon_client.get("/api/profile").status_code == 401

    def test_delete_requires_auth(self, anon_client):
        assert anon_client.delete("/api/history/abc123").status_code == 401
        assert anon_client.delete("/api/history").status_code == 401


class TestPublicEndpointsStayPublic:
    def test_health(self, anon_client):
        assert anon_client.get("/api/health").status_code == 200

    def test_ready(self, anon_client):
        assert anon_client.get("/api/ready").status_code == 200

    def test_model_info(self, anon_client):
        assert anon_client.get("/api/model-info").status_code == 200

    def test_model_metrics(self, anon_client):
        assert anon_client.get("/api/model-info/metrics").status_code == 200


class TestIdentitySource:
    def test_browser_user_id_cannot_override(self, auth_client):
        """Scans are saved under the SERVER-verified identity; a spoofed
        owner id in the request body or params is ignored (it isn't even
        read). After a scan, the record belongs to the verified user only."""
        r = auth_client.post(
            "/api/scan",
            json={"url": "https://www.wikipedia.org/", "user_id": USER_B_ID},
        )
        assert r.status_code == 200
        hist = auth_client.get("/api/history").json()
        assert hist["total"] == 1
        assert hist["scans"][0]["user_id"] == USER_A_ID


USER_A_ID = USER_A.id
USER_B_ID = "22222222-2222-4222-8222-222222222222"
