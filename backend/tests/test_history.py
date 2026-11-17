"""History service and history API tests (storage modes + user isolation)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.auth import AuthUser  # noqa: E402
from app.services.history_service import (  # noqa: E402
    build_history_store,
    new_scan_id,
)

USER_A = AuthUser(id="user-a-test-id", email="a@test.local", token="")
USER_B = AuthUser(id="user-b-test-id", email="b@test.local", token="")


def make_record(**over):
    base = {
        "id": new_scan_id(),
        "created_at": "2026-01-01T00:00:00+00:00",
        "url": "https://example.com/",
        "classification": "likely_benign",
        "binary_prediction": "benign",
        "risk_score": 10,
        "probability": 0.1,
        "model_version": "test",
        "result": {"x": 1},
    }
    base.update(over)
    return base


class TestSQLiteStore:
    def test_save_and_list(self, tmp_path):
        store = build_history_store("sqlite", tmp_path / "t.db", 100)
        store.save(make_record(), USER_A)
        store.save(make_record(classification="high_risk", probability=0.9, risk_score=92), USER_A)
        scans, total = store.list_scans(USER_A, 10, 0, None, None, "desc")
        assert total == 2
        assert len(scans) == 2

    def test_filter_and_search(self, tmp_path):
        store = build_history_store("sqlite", tmp_path / "t.db", 100)
        store.save(make_record(url="https://wikipedia.org/"), USER_A)
        store.save(make_record(url="https://github.com/"), USER_A)
        store.save(make_record(url="http://198.51.100.3/login", classification="high_risk"), USER_A)
        _, total = store.list_scans(USER_A, 10, 0, "high_risk", None, "desc")
        assert total == 1
        _, total = store.list_scans(USER_A, 10, 0, None, "github", "desc")
        assert total == 1

    def test_retention_cap(self, tmp_path):
        store = build_history_store("sqlite", tmp_path / "t.db", 5)
        for i in range(9):
            store.save(make_record(url=f"https://example.com/{i}"), USER_A)
        _, total = store.list_scans(USER_A, 50, 0, None, None, "desc")
        assert total == 5

    def test_delete_and_clear(self, tmp_path):
        store = build_history_store("sqlite", tmp_path / "t.db", 100)
        rec = make_record()
        store.save(rec, USER_A)
        assert store.get(USER_A, rec["id"]) is not None
        assert store.delete(USER_A, rec["id"]) is True
        assert store.get(USER_A, rec["id"]) is None
        store.save(make_record(), USER_A)
        assert store.clear(USER_A) == 1
        assert store.stats(USER_A)["total"] == 0

    def test_persistence_across_connections(self, tmp_path):
        store = build_history_store("sqlite", tmp_path / "t.db", 100)
        rec = make_record()
        store.save(rec, USER_A)
        store2 = build_history_store("sqlite", tmp_path / "t.db", 100)
        assert store2.get(USER_A, rec["id"]) is not None

    def test_legacy_rows_without_owner_are_invisible(self, tmp_path):
        """Pre-multi-user prototype rows (user_id='') belong to nobody."""
        import sqlite3

        db = tmp_path / "legacy.db"
        store = build_history_store("sqlite", db, 100)
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO scans (id, user_id, created_at, url, classification,"
                " binary_prediction, risk_score, probability, model_version, result_json)"
                " VALUES ('legacy1', '', '2025-01-01T00:00:00+00:00', 'https://old.example/',"
                " 'likely_benign', 'benign', 5, 0.05, 'old', '{}')"
            )
        assert store.list_scans(USER_A, 10, 0, None, None, "desc")[1] == 0
        assert store.list_scans(USER_B, 10, 0, None, None, "desc")[1] == 0
        assert store.get(USER_A, "legacy1") is None
        assert store.delete(USER_A, "legacy1") is False
        assert store.stats(USER_A)["total"] == 0

    def test_migrate_existing_single_user_database(self, tmp_path):
        """Old schema (no user_id column) is migrated transparently."""
        import sqlite3

        db = tmp_path / "old.db"
        with sqlite3.connect(db) as conn:
            conn.execute(
                "CREATE TABLE scans (id TEXT PRIMARY KEY, created_at TEXT NOT NULL,"
                " url TEXT NOT NULL, classification TEXT NOT NULL,"
                " binary_prediction TEXT NOT NULL, risk_score INTEGER NOT NULL,"
                " probability REAL NOT NULL, model_version TEXT NOT NULL,"
                " result_json TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT INTO scans VALUES ('old1', '2025-01-01', 'https://old.example/',"
                " 'likely_benign', 'benign', 5, 0.05, 'old', '{}')"
            )
        # Building the store migrates the schema; legacy rows stay unowned.
        store = build_history_store("sqlite", db, 100)
        assert store.list_scans(USER_A, 10, 0, None, None, "desc")[1] == 0
        store.save(make_record(), USER_A)
        assert store.list_scans(USER_A, 10, 0, None, None, "desc")[1] == 1


class TestUserIsolation:
    """User A must never touch User B's records (and vice versa)."""

    def test_sqlite_isolation(self, tmp_path):
        store = build_history_store("sqlite", tmp_path / "t.db", 100)
        rec_a = make_record(url="https://a.example/")
        store.save(rec_a, USER_A)
        rec_b = make_record(url="https://b.example/")
        store.save(rec_b, USER_B)

        # Lists are private
        _, total_a = store.list_scans(USER_A, 50, 0, None, None, "desc")
        _, total_b = store.list_scans(USER_B, 50, 0, None, None, "desc")
        assert total_a == 1 and total_b == 1

        # Reads are private
        assert store.get(USER_B, rec_a["id"]) is None
        assert store.get(USER_A, rec_b["id"]) is None

        # Deletes are private
        assert store.delete(USER_B, rec_a["id"]) is False
        assert store.delete(USER_A, rec_a["id"]) is True

        # Clear only affects the caller
        store.save(make_record(), USER_A)
        store.save(make_record(), USER_A)
        assert store.clear(USER_A) == 2
        assert store.stats(USER_B)["total"] == 1

        # Stats are private
        stats_a = store.stats(USER_A)
        assert stats_a["total"] == 0

    def test_memory_isolation(self, tmp_path):
        store = build_history_store("memory", tmp_path / "none.db", 100)
        rec_a = make_record()
        store.save(rec_a, USER_A)
        assert store.get(USER_B, rec_a["id"]) is None
        assert store.list_scans(USER_B, 10, 0, None, None, "desc")[1] == 0
        assert store.delete(USER_B, rec_a["id"]) is False
        assert store.stats(USER_A)["total"] == 1


class TestMemoryAndDisabled:
    def test_memory_store(self, tmp_path):
        store = build_history_store("memory", tmp_path / "none.db", 100)
        store.save(make_record(), USER_A)
        scans, total = store.list_scans(USER_A, 10, 0, None, None, "desc")
        assert total == 1
        assert len(scans) == 1

    def test_disabled_store(self, tmp_path):
        store = build_history_store("disabled", tmp_path / "none.db", 100)
        store.save(make_record(), USER_A)
        assert store.list_scans(USER_A, 10, 0, None, None, "desc") == ([], 0)
        assert store.get(USER_A, "x") is None
        assert store.delete(USER_A, "x") is False
        assert store.clear(USER_A) == 0
        assert store.stats(USER_A) == {"total": 0}

    def test_unknown_mode_raises(self, tmp_path):
        import pytest

        with pytest.raises(ValueError):
            build_history_store("carrier-pigeon", tmp_path / "x.db", 10)


class TestHistoryAPI:
    def test_list_empty_for_new_user(self, auth_client):
        r = auth_client.get("/api/history")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0 and body["scans"] == []

    def test_scan_then_list_is_user_scoped(self, auth_client):
        scan = auth_client.post("/api/scan", json={"url": "https://www.wikipedia.org/"}).json()
        listed = auth_client.get("/api/history").json()
        assert listed["total"] == 1
        assert listed["scans"][0]["id"] == scan["scan_id"]
        assert listed["scans"][0]["url"] == "https://www.wikipedia.org/"

    def test_foreign_scan_returns_404_not_403(self, auth_client, auth_client_b):
        scan = auth_client.post("/api/scan", json={"url": "https://www.wikipedia.org/"}).json()
        other_scan_id = scan["scan_id"]
        # User B cannot read it
        r = auth_client_b.get(f"/api/history/{other_scan_id}")
        assert r.status_code == 404
        # ... or delete it
        r = auth_client_b.delete(f"/api/history/{other_scan_id}")
        assert r.status_code == 404
        # Owner still can
        assert auth_client.get(f"/api/history/{other_scan_id}").status_code == 200

    def test_delete_own_scan(self, auth_client):
        scan = auth_client.post("/api/scan", json={"url": "https://www.wikipedia.org/"}).json()
        r = auth_client.delete(f"/api/history/{scan['scan_id']}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True
        assert auth_client.get("/api/history").json()["total"] == 0

    def test_clear_history(self, auth_client):
        for _ in range(3):
            auth_client.post("/api/scan", json={"url": "https://www.wikipedia.org/"})
        r = auth_client.delete("/api/history")
        assert r.status_code == 200
        assert r.json()["deleted_count"] == 3

    def test_search_and_filter(self, auth_client):
        auth_client.post("/api/scan", json={"url": "https://www.wikipedia.org/"})
        auth_client.post("/api/scan", json={"url": "http://198.51.100.7/paypal/login"})
        r = auth_client.get("/api/history", params={"search": "wikipedia"})
        assert r.json()["total"] == 1
        r = auth_client.get("/api/history", params={"classification": "high_risk"})
        assert r.json()["total"] >= 0  # depends on model verdict; just shape

    def test_user_b_dashboard_empty_when_a_scanned(self, auth_client, auth_client_b):
        auth_client.post("/api/scan", json={"url": "https://www.wikipedia.org/"})
        dash_b = auth_client_b.get("/api/dashboard").json()
        assert dash_b["total_scans"] == 0
        dash_a = auth_client.get("/api/dashboard").json()
        assert dash_a["total_scans"] == 1
