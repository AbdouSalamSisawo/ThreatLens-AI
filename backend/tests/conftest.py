"""Shared pytest fixtures for ThreatLens AI backend tests."""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import jwt
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.auth import AuthUser, get_current_user  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.feature_extractor import FEATURE_NAMES, feature_vector  # noqa: E402


# ---------------------------------------------------------------------------
# Clearly-labelled synthetic FIXTURE data for tests only. These URLs are
# constructed for structural testing and are never used to claim realistic
# production performance.
# ---------------------------------------------------------------------------

BENIGN_FIXTURE_URLS = [
    "https://www.google.com/search?q=test",
    "https://en.wikipedia.org/wiki/Phishing",
    "https://www.bbc.co.uk/news",
    "https://github.com/scikit-learn/scikit-learn",
    "https://www.nytimes.com/section/technology",
    "https://docs.python.org/3/library/urllib.parse.html",
    "https://stackoverflow.com/questions/tagged/python",
    "https://www.amazon.com/dp/B08N5WRWNW",
    "https://www.mozilla.org/en-US/firefox/",
    "https://archive.org/details/texts",
    "https://www.imdb.com/title/tt0111161/",
    "https://www.economist.com/science-and-technology",
    "https://nodejs.org/en/docs",
    "https://www.reddit.com/r/netsec/",
    "https://www.theguardian.com/world",
    "https://ftp.gnu.org/gnu/wget/",
    "https://openai.com/research",
    "https://www.debian.org/releases/stable/",
    "https://www.rust-lang.org/learn",
    "https://kernel.org/pub/linux/kernel/",
]

PHISHING_FIXTURE_URLS = [
    "http://198.51.100.7/paypal/login/verify/account.php?user=a",
    "http://secure-update.apple-id.verify-account.info/signin/webscr",
    "http://198.51.100.23/banking/confirm/credentials/update/login",
    "http://198.51.100.99/amzn/billing/update/payment-verify/webscr",
    "http://secure-login.bankofverify.com/auth/verify/account/update",
    "http://198.51.100.12/confirm/password/reset/login/verify/account",
    "http://appleid.apple.verifybilling.info/secure/signin/webscr/login",
    "http://198.51.100.55/ebay-signin/secure-account/verify/update.php",
    "http://account-verify.netflix-billing.info/login/secure/webscr",
    "http://198.51.100.77/wellsfargo/login/update/verify/webscr/confirm",
    "http://paypal-resolve.secure-account.login-verify.top/webscr/signin",
    "http://198.51.100.31/facebook-security/verify-account/login/confirm",
    "http://secure-credentials-update.signin-verify-account.xyz/login",
    "http://198.51.100.41/microsoft-outlook/verify/signin/webscr/login",
    "http://update-payment-info.secure-banking-login.cyou/confirm/webscr",
    "http://198.51.100.61/instagram-verify/login/secure/account/update",
    "http://signin-apple-id.verify-account-locked.icloud-secure.top/login",
    "http://198.51.100.85/chase-online/login/verify/confirm/webscr/update",
    "http://secure-verify-login.account-update-credentials.click/signin",
    "http://198.51.100.102/dhl-package/confirm/payment/verify/login/webscr",
]


@pytest.fixture(scope="session")
def trained_pipeline(tmp_path_factory):
    """
    Train a small RandomForest on the clearly-labelled fixture URLs with the
    SHARED feature extractor - proving the train->save->reload->infer path.
    This model is for tests only and must never be used for production metrics.
    """
    urls = BENIGN_FIXTURE_URLS + PHISHING_FIXTURE_URLS
    labels = [0] * len(BENIGN_FIXTURE_URLS) + [1] * len(PHISHING_FIXTURE_URLS)
    X = pd.DataFrame([dict(zip(FEATURE_NAMES, feature_vector(u))) for u in urls])
    y = labels

    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=60, random_state=7)),
        ]
    )
    pipe.fit(X, y)

    artifacts = tmp_path_factory.mktemp("artifacts")
    joblib.dump(pipe, artifacts / "phishing_model.joblib")
    return artifacts, pipe, urls, labels


def write_metadata(artifacts: Path) -> None:
    import json

    from app.services.feature_extractor import FEATURE_SCHEMA_VERSION

    (artifacts / "model_metadata.json").write_text(
        json.dumps(
            {
                "model_id": "threatlens-test-model",
                "model_version": "0.0.0-test",
                "trained_at": "2026-01-01T00:00:00Z",
                "selected_model": "random_forest",
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "classification_bands": {
                    "high_risk": {"min_probability": 0.80},
                    "suspicious": {"min_probability": 0.50},
                    "likely_benign": {"min_probability": 0.00},
                },
                "uncertain_band": {"lower": 0.35, "upper": 0.65},
                "probability_meaning": "test fixture",
                "dataset": {"source": "test fixture"},
                "training_config": {},
            }
        )
    )
    (artifacts / "metrics.json").write_text(json.dumps({"test_metrics": {}}))
    (artifacts / "feature_schema.json").write_text(
        json.dumps(
            {
                "schema_version": FEATURE_SCHEMA_VERSION,
                "feature_names": list(FEATURE_NAMES),
            }
        )
    )


@pytest.fixture(scope="session")
def es256_keypair():
    """Session-scoped ES256 keypair used to sign/mint test access tokens.

    The private key stays in-process; only the JWKS verification path in
    app.core.auth is exercised against the matching public key.
    """
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key


@pytest.fixture()
def fake_jwks(es256_keypair, monkeypatch):
    """Replace the real JWKS client with one that always 'knows' our test key.

    This lets auth tests exercise the FULL verification path in
    app.core.auth (signature, exp, iss, aud, role checks) without network.
    """
    from cryptography.hazmat.primitives import serialization

    public_pem = (
        es256_keypair.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    public_key_obj = serialization.load_pem_public_key(public_pem)

    class FakeSigningKey:
        algorithm_name = "ES256"
        key = public_key_obj

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, token):  # noqa: ARG002
            return FakeSigningKey()

    import app.core.auth as auth_module

    monkeypatch.setattr(auth_module, "_jwks_client", lambda settings: FakeJWKClient())
    return True


ISSUER = "https://test-project.supabase.co/auth/v1"

# Stable test identities (never real users).
USER_A = AuthUser(id="11111111-1111-4111-8111-111111111111", email="user-a@test.local", token="")
USER_B = AuthUser(id="22222222-2222-4222-8222-222222222222", email="user-b@test.local", token="")


def mint_token(private_key, user_id: str, **claim_over) -> str:
    import time

    now = int(time.time())
    claims = {
        "aud": "authenticated",
        "exp": now + 600,
        "iat": now,
        "iss": ISSUER,
        "sub": user_id,
        "email": f"{user_id[:8]}@test.local",
        "role": "authenticated",
    }
    claims.update(claim_over)
    return jwt.encode(claims, private_key, algorithm="ES256", headers={"kid": "test-kid"})


def user_token(private_key, user: AuthUser, **claim_over) -> str:
    return mint_token(private_key, user.id, **claim_over)


def make_test_settings(**over) -> Settings:
    base = dict(
        artifacts_dir=None,  # always overridden by callers
        database_path=None,
        history_mode="sqlite",
        rate_limit_scan_per_minute=1000,  # not a limiter test by default
        cors_origins="http://localhost:5173",
        supabase_url="https://test-project.supabase.co",
        supabase_publishable_key="test-publishable-key",
        supabase_auth_mode="auto",
    )
    base.update(over)
    return Settings(**base)


@pytest.fixture()
def test_settings(trained_pipeline, tmp_path):
    artifacts, _pipe, _urls, _labels = trained_pipeline
    write_metadata(artifacts)
    return make_test_settings(
        artifacts_dir=artifacts, database_path=tmp_path / "test_history.db"
    )


def _override_auth(app, user: AuthUser) -> None:
    """Pin the identity for endpoint tests (real verification is covered by
    test_auth.py against the actual dependency + fake JWKS)."""

    def _current_user() -> AuthUser:
        return AuthUser(id=user.id, email=user.email, token="test-token", claims={"sub": user.id})

    app.dependency_overrides[get_current_user] = _current_user


def _make_client(test_settings, user: AuthUser | None):
    from fastapi.testclient import TestClient

    app = create_app(test_settings)
    if user is not None:
        _override_auth(app, user)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(test_settings):
    """Authenticated as USER_A (identity override)."""
    yield from _make_client(test_settings, USER_A)


@pytest.fixture()
def auth_client_b(test_settings):
    """A second independent authenticated identity (USER_B)."""
    yield from _make_client(test_settings, USER_B)


@pytest.fixture()
def client(test_settings):
    """Back-compat alias: authenticated client as USER_A."""
    yield from _make_client(test_settings, USER_A)


@pytest.fixture()
def anon_client(test_settings):
    """Unauthenticated client - the real auth dependency runs."""
    yield from _make_client(test_settings, None)


@pytest.fixture()
def no_model_client(tmp_path):
    """App pointed at an empty artifacts dir: model must be unavailable.

    Authenticated as USER_A - these tests target model behaviour, not auth."""
    empty = tmp_path / "no-artifacts"
    empty.mkdir()

    settings = make_test_settings(
        artifacts_dir=empty,
        database_path=tmp_path / "h.db",
        history_mode="memory",
    )
    yield from _make_client(settings, USER_A)
