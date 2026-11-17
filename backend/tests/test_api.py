"""API integration tests: scan flow, validation, errors, rate limiting."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestHealthAndReadiness:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

    def test_ready_with_model(self, client):
        r = client.get("/api/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["ready"] is True
        assert body["model_available"] is True

    def test_ready_without_model(self, no_model_client):
        r = no_model_client.get("/api/ready")
        assert r.status_code == 200
        body = r.json()
        assert body["ready"] is False
        assert body["model_available"] is False
        assert "MODEL_DROPIN" in body["model_message"]


class TestScanFlow:
    def test_successful_scan_shape(self, client):
        r = client.post("/api/scan", json={"url": "https://www.wikipedia.org/"})
        assert r.status_code == 200
        body = r.json()
        for field in (
            "scan_id", "url", "classification", "binary_prediction", "risk_score",
            "model_probability", "is_uncertain", "observed_features", "explanation",
            "threat_intelligence", "model_version", "scan_timestamp", "limitations",
        ):
            assert field in body
        assert body["classification"] in {"likely_benign", "suspicious", "high_risk"}
        assert body["binary_prediction"] in {"benign", "phishing"}
        assert 0 <= body["risk_score"] <= 100
        assert 0.0 <= body["model_probability"] <= 1.0
        assert len(body["explanation"]["observed_characteristics"]) >= 1
        assert len(body["explanation"]["recommended_actions"]) >= 1
        assert len(body["explanation"]["cannot_determine"]) >= 3

    def test_scan_risk_score_matches_probability(self, client):
        r = client.post("/api/scan", json={"url": "https://www.wikipedia.org/"}).json()
        assert r["risk_score"] == round(r["model_probability"] * 100)

    def test_scan_is_deterministic(self, client):
        url = "http://198.51.100.10/login/verify/account.php?u=1"
        a = client.post("/api/scan", json={"url": url}).json()
        b = client.post("/api/scan", json={"url": url}).json()
        assert a["model_probability"] == b["model_probability"]
        assert a["classification"] == b["classification"]

    def test_whitespace_and_bare_domain(self, client):
        r = client.post("/api/scan", json={"url": "   example.com/path   "})
        assert r.status_code == 200
        body = r.json()
        assert body["url"] == "example.com/path"
        assert body["scheme_was_inferred"] is True

    def test_evidence_exactness_flag(self, client):
        body = client.post(
            "/api/scan", json={"url": "http://198.51.100.10/login/verify"}
        ).json()
        evidence = body["explanation"]["model_evidence"]
        assert evidence["method"] in {"tree_path", "coefficient_log_odds", "rule_based_fallback"}
        if evidence["method"] != "rule_based_fallback":
            assert evidence["probability_check"]["exact"] is True


class TestScanValidation:
    def test_invalid_scheme_rejected(self, client):
        r = client.post("/api/scan", json={"url": "javascript:alert(1)"})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "unsupported_scheme"

    def test_ftp_rejected(self, client):
        r = client.post("/api/scan", json={"url": "ftp://example.com/x"})
        assert r.status_code == 400

    def test_empty_rejected(self, client):
        r = client.post("/api/scan", json={"url": "   "})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "empty_input"

    def test_missing_field_error_format(self, client):
        r = client.post("/api/scan", json={})
        assert r.status_code == 422
        body = r.json()
        assert body["error"]["code"] == "validation_error"

    def test_non_string_rejected(self, client):
        r = client.post("/api/scan", json={"url": 123})
        assert r.status_code == 422

    def test_oversized_url_rejected(self, client):
        r = client.post("/api/scan", json={"url": "http://example.com/" + "a" * 3000})
        assert r.status_code == 400
        assert r.json()["error"]["code"] == "url_too_long"

    def test_localhost_rejected(self, client):
        r = client.post("/api/scan", json={"url": "http://localhost:8000/"})
        assert r.status_code == 400


class TestModelUnavailable:
    def test_scan_returns_503_no_fallback(self, no_model_client):
        r = no_model_client.post("/api/scan", json={"url": "https://example.com/"})
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "model_unavailable"

    def test_model_info_503(self, no_model_client):
        r = no_model_client.get("/api/model-info")
        assert r.status_code == 503

    def test_ready_reports_false(self, no_model_client):
        assert no_model_client.get("/api/ready").json()["ready"] is False


class TestModelInfo:
    def test_model_info_fields(self, client):
        r = client.get("/api/model-info")
        assert r.status_code == 200
        body = r.json()
        assert body["model_id"] == "threatlens-test-model"
        assert body["feature_schema_version"]
        assert "probability_meaning" in body

    def test_metrics_endpoint(self, client):
        r = client.get("/api/model-info/metrics")
        assert r.status_code == 200


class TestRateLimiting:
    def test_rate_limit_429(self, tmp_path, trained_pipeline):
        from fastapi.testclient import TestClient

        artifacts, *_ = trained_pipeline

        from app.core.auth import get_current_user
        from app.core.config import Settings
        from app.main import create_app
        from tests.conftest import USER_A

        settings = Settings(
            artifacts_dir=artifacts,
            database_path=tmp_path / "rl.db",
            history_mode="memory",
            rate_limit_scan_per_minute=3,
            supabase_url="https://test-project.supabase.co",
            supabase_publishable_key="test-publishable-key",
        )
        app = create_app(settings)
        app.dependency_overrides[get_current_user] = lambda: USER_A
        with TestClient(app) as c:
            codes = [
                c.post("/api/scan", json={"url": "https://example.com/"}).status_code
                for _ in range(6)
            ]
            assert codes[:3] == [200, 200, 200]
            assert 429 in codes


class TestErrorConsistency:
    def test_errors_use_error_envelope(self, client):
        r = client.post("/api/scan", json={"url": "not a url at all"})
        body = r.json()
        assert "error" in body and "code" in body["error"] and "message" in body["error"]

    def test_404_envelope(self, client):
        r = client.get("/api/definitely-not-an-endpoint")
        assert r.status_code == 404
        assert "error" in r.json()
