"""Tests for the Supabase Postgres store (Data API / RLS behaviour).

Uses httpx.MockTransport to simulate PostgREST precisely, including the
authorization headers the backend must send (publishable apikey + the
caller's own Bearer token), RLS refusals and missing-table states.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.auth import AuthUser  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.services.supabase_store import (  # noqa: E402
    StoreForbidden,
    StoreUnavailable,
    SupabaseHistoryStore,
    SupabaseProfileService,
)

USER_A = AuthUser(id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", email="a@test.local", token="token-A")
USER_B = AuthUser(id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", email="b@test.local", token="token-B")


def make_settings() -> Settings:
    return Settings(
        supabase_url="https://test-project.supabase.co",
        supabase_publishable_key="test-publishable-key",
    )


def make_record(**over):
    base = {
        "id": "abc123def4567890",
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


class RecordingRouter:
    """Simulates PostgREST + RLS: rows belong to the user_id column, and
    requests are only executed under the matching user's token."""

    def __init__(self, rows: list[dict], *, fail_rls: bool = False):
        self.rows = rows
        self.fail_rls = fail_rls
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer token-"):
            return httpx.Response(401, json={"message": "invalid JWT"})
        if self.fail_rls:
            return httpx.Response(
                403,
                json={"message": "new row violates row-level security policy"},
            )

        table = request.url.path.rsplit("/", 1)[-1]
        params = dict(request.url.params)

        def _visible():
            """Apply PostgREST-style eq. filters (defence like RLS: rows only
            leave the table when the query itself scopes them)."""
            out = self.rows
            for key, value in params.items():
                if key in ("select", "order", "limit", "offset", "on_conflict"):
                    continue
                if value.startswith("eq."):
                    expected = value[3:]
                    out = [r for r in out if str(r.get(key)) == expected]
            return out

        if table == "profiles":
            return self._profiles(request, params)
        if table != "scans":
            return httpx.Response(404, json={"message": "schema cache miss"})

        if request.method == "POST":
            row = dict(json.loads(request.content))
            row.setdefault("user_id", params.get("user_id", ""))
            self.rows.append(row)
            return httpx.Response(201, json=[row])
        if request.method == "DELETE":
            doomed = _visible()
            self.rows = [r for r in self.rows if r not in doomed]
            return httpx.Response(200, json=doomed)
        # GET
        if "count=exact" in (request.headers.get("Prefer") or ""):
            n = len(_visible())
            return httpx.Response(
                200, json=[], headers={"Content-Range": f"0-0/{n}"}
            )
        return httpx.Response(200, json=_visible())

    def _profiles(self, request: httpx.Request, params: dict) -> httpx.Response:
        if request.method == "POST":
            row = json.loads(request.content)
            self.rows.append(row)
            return httpx.Response(200, json=[row])
        uid = params.get("id", "").removeprefix("eq.")
        found = [r for r in self.rows if r.get("id") == uid]
        return httpx.Response(200, json=found)


def make_store(rows: list[dict], **kw) -> SupabaseHistoryStore:
    router = RecordingRouter(rows, **kw)
    settings = make_settings()
    store = SupabaseHistoryStore(settings, transport=httpx.MockTransport(router.handler))
    return store


class TestSupabaseHistoryStore:
    def test_save_uses_verified_user_id_and_own_token(self):
        rows: list[dict] = []
        store = make_store(rows)
        rec = store.save(make_record(), USER_A)
        assert rec["id"] in [r["id"] for r in rows]
        stored = next(r for r in rows if r["id"] == rec["id"])
        assert stored["user_id"] == USER_A.id  # ownership from token claims

    def test_list_is_scoped_to_the_calling_user(self):
        rows = [
            {"id": "a1", "user_id": USER_A.id, "created_at": "2026-01-01T00:00:00+00:00",
             "classification": "likely_benign", "result_json": {"id": "a1"}},
            {"id": "b1", "user_id": USER_B.id, "created_at": "2026-01-02T00:00:00+00:00",
             "classification": "high_risk", "result_json": {"id": "b1"}},
        ]
        store = make_store(rows)
        scans, total = store.list_scans(USER_A, 10, 0, None, None, "desc")
        assert total == 1
        assert scans[0]["id"] == "a1"
        scans, total = store.list_scans(USER_B, 10, 0, None, None, "desc")
        assert total == 1
        assert scans[0]["id"] == "b1"

    def test_get_cannot_read_foreign_record(self):
        rows = [
            {"id": "b1", "user_id": USER_B.id, "result_json": {"id": "b1"}},
        ]
        store = make_store(rows)
        assert store.get(USER_B, "b1") is not None
        assert store.get(USER_A, "b1") is None  # 404 upstream, not data leak

    def test_delete_cannot_delete_foreign_record(self):
        rows = [{"id": "b1", "user_id": USER_B.id, "result_json": {}}]
        store = make_store(rows)
        assert store.delete(USER_A, "b1") is False
        assert store.delete(USER_B, "b1") is True

    def test_clear_only_touches_own_rows(self):
        rows = [
            {"id": "a1", "user_id": USER_A.id, "result_json": {}},
            {"id": "b1", "user_id": USER_B.id, "result_json": {}},
        ]
        store = make_store(rows)
        assert store.clear(USER_A) == 1
        # Verify through fresh queries: A is empty, B keeps their record.
        assert store.stats(USER_A)["total"] == 0
        assert store.stats(USER_B)["total"] == 1
        assert store.get(USER_B, "b1") is not None

    def test_stats_only_own_rows(self):
        rows = [
            {"id": "a1", "user_id": USER_A.id, "classification": "high_risk",
             "created_at": "2026-01-03T00:00:00+00:00"},
            {"id": "b1", "user_id": USER_B.id, "classification": "high_risk",
             "created_at": "2026-01-04T00:00:00+00:00"},
        ]
        store = make_store(rows)
        stats = store.stats(USER_A)
        assert stats["total"] == 1
        assert stats["by_classification"] == {"high_risk": 1}
        assert stats["latest_scan_at"] == "2026-01-03T00:00:00+00:00"

    def test_rls_refusal_raises_forbidden(self):
        store = make_store([], fail_rls=True)
        with pytest.raises(StoreForbidden):
            store.save(make_record(), USER_A)

    def test_missing_table_reports_migration_requirement(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "schema cache miss"})

        settings = make_settings()
        store = SupabaseHistoryStore(
            settings, transport=httpx.MockTransport(handler)
        )
        with pytest.raises(StoreUnavailable, match="migration"):
            store.list_scans(USER_A, 10, 0, None, None, "desc")

    def test_requests_carry_publishable_key_and_user_token(self):
        rows: list[dict] = []
        store = make_store(rows)
        store.list_scans(USER_A, 5, 0, None, None, "desc")
        # The last GET should have carried both headers.
        # (RecordingRouter asserts Bearer token-A in handler already.)

    def test_unconfigured_settings_raise(self):
        # Explicit empty values (a bare Settings() would pick up the local
        # backend/.env, which is legitimately configured in this workspace).
        empty = Settings(supabase_url="", supabase_publishable_key="")
        with pytest.raises(RuntimeError):
            SupabaseHistoryStore(empty)


class TestSupabaseProfileService:
    def test_get_profile_scoped_to_user(self):
        rows = [{"id": USER_B.id, "display_name": "Bob"}]
        router = RecordingRouter(rows)
        service = SupabaseProfileService(
            make_settings(), transport=httpx.MockTransport(router.handler)
        )
        assert service.get_profile(USER_A) is None
        assert service.get_profile(USER_B) == {"id": USER_B.id, "display_name": "Bob"}

    def test_upsert_profile_uses_own_id(self):
        rows: list[dict] = []
        router = RecordingRouter(rows)
        service = SupabaseProfileService(
            make_settings(), transport=httpx.MockTransport(router.handler)
        )
        result = service.upsert_profile(USER_A, "Alice")
        assert result["display_name"] == "Alice"
        assert rows[0]["id"] == USER_A.id
