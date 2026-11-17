"""Supabase Postgres stores via the Data API (least-privilege architecture).

The backend holds NO privileged key. Every request to Supabase's Data API
(PostgREST) carries:

* ``apikey``: the project's publishable (anon) key - public by design
* ``Authorization: Bearer <the caller's own verified access token>``

Row Level Security policies (see ``supabase/migrations/0001_init.sql``)
therefore apply to every single query: users can only select, insert or
delete rows where ``user_id = auth.uid()``. Even though the backend also
filters by the verified user id (defence in depth), the database is the
final authority - the server cannot accidentally leak another user's data
because it has no way to bypass RLS.

Tables are created by the versioned SQL migration in
``supabase/migrations/``. If the migration has not been applied yet, this
store reports a clear, actionable "migration required" state instead of
faking empty data.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.auth import AuthUser
from app.core.config import Settings
from app.services.history_service import HistoryStore

logger = logging.getLogger("threatlens.supabase")

_SCAN_COLUMNS = (
    "id,user_id,created_at,url,classification,binary_prediction,"
    "risk_score,probability,model_version,result_json"
)


class StoreUnavailable(Exception):
    """Supabase unreachable / migration not applied - surfaced as HTTP 503."""


class StoreForbidden(Exception):
    """Row Level Security refused the operation - surfaced as HTTP 403."""


class _Postgrest:
    """Minimal PostgREST client that always acts as the authenticated user."""

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base = f"{settings.supabase_url_clean}/rest/v1"
        self._apikey = settings.supabase_publishable_key
        self._client = httpx.Client(
            base_url=self._base,
            transport=transport,  # injectable for isolated tests
            timeout=httpx.Timeout(15.0, connect=8.0),
        )

    def request(
        self,
        method: str,
        table: str,
        user: AuthUser,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        prefer: str | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {
            "apikey": self._apikey,
            "Authorization": f"Bearer {user.token}",
            "Accept": "application/json",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        try:
            resp = self._client.request(
                method,
                f"/{table}",
                params=params,
                json=json_body,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise StoreUnavailable(
                f"Supabase Data API unreachable ({type(exc).__name__})"
            ) from exc

        if resp.status_code == 404:
            # Table missing -> the SQL migration has not been applied yet.
            raise StoreUnavailable(
                "Supabase table not found - apply the SQL migration in "
                "supabase/migrations/ via the Supabase SQL Editor first."
            )
        if resp.status_code in (401, 403):
            detail = ""
            try:
                detail = resp.json().get("message", "")
            except Exception:  # noqa: BLE001
                pass
            raise StoreForbidden(
                f"Supabase refused the operation ({resp.status_code}) {detail}".strip()
            )
        if resp.status_code >= 400:
            raise StoreUnavailable(f"Supabase Data API error {resp.status_code}")
        return resp


class SupabaseHistoryStore(HistoryStore):
    """HISTORY_MODE=supabase - multi-user persistence with RLS enforcement."""

    mode = "supabase"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.supabase_configured:
            raise RuntimeError(
                "HISTORY_MODE=supabase requires SUPABASE_URL and "
                "SUPABASE_PUBLISHABLE_KEY to be configured."
            )
        self._rest = _Postgrest(settings, transport=transport)

    # ------------------------------------------------------------------ save
    def save(self, record: dict, user: AuthUser) -> dict:
        payload = {
            "id": record["id"],
            "user_id": user.id,
            "created_at": record["created_at"],
            "url": record["url"],
            "classification": record["classification"],
            "binary_prediction": record["binary_prediction"],
            "risk_score": record["risk_score"],
            "probability": record["probability"],
            "model_version": record["model_version"],
            "result_json": record,
        }
        resp = self._rest.request(
            "POST", "scans", user, json_body=payload, prefer="return=minimal"
        )
        if resp.status_code not in (200, 201):
            raise StoreUnavailable(f"Insert failed ({resp.status_code})")
        return record

    # ------------------------------------------------------------------ list
    def list_scans(self, user, limit, offset, classification, search, order):
        params: dict[str, Any] = {
            "select": _SCAN_COLUMNS,
            "user_id": f"eq.{user.id}",
            "order": f"created_at.{'desc' if order == 'desc' else 'asc'}",
            "limit": limit,
            "offset": offset,
        }
        if classification:
            params["classification"] = f"eq.{classification}"
        if search:
            params["url"] = f"ilike.*{search}*"

        rows = self._rest.request("GET", "scans", user, params=params).json()
        total = self._count(user, params)
        return [self._row_to_record(r) for r in rows], total

    def _count(self, user: AuthUser, base_params: dict[str, Any]) -> int:
        count_params = dict(base_params)
        count_params.update({"select": "id", "limit": 1})
        count_params.pop("offset", None)
        resp = self._rest.request(
            "GET", "scans", user, params=count_params, prefer="count=exact"
        )
        content_range = resp.headers.get("Content-Range", "")
        # e.g. "0-0/123"
        if "/" in content_range:
            raw = content_range.rsplit("/", 1)[-1]
            if raw.isdigit():
                return int(raw)
        return 0

    @staticmethod
    def _row_to_record(row: dict[str, Any]) -> dict:
        record = row.get("result_json")
        if isinstance(record, dict) and record.get("id") == row.get("id"):
            return record
        # Fallback: rebuild from columns (should not normally happen).
        return {
            "id": row.get("id"),
            "user_id": row.get("user_id"),
            "created_at": row.get("created_at"),
            "url": row.get("url"),
            "classification": row.get("classification"),
            "binary_prediction": row.get("binary_prediction"),
            "risk_score": row.get("risk_score"),
            "probability": row.get("probability"),
            "model_version": row.get("model_version"),
            "result": None,
        }

    # ------------------------------------------------------------------- get
    def get(self, user: AuthUser, scan_id: str) -> dict | None:
        params = {
            "select": _SCAN_COLUMNS,
            "id": f"eq.{scan_id}",
            "user_id": f"eq.{user.id}",
            "limit": 1,
        }
        rows = self._rest.request("GET", "scans", user, params=params).json()
        return self._row_to_record(rows[0]) if rows else None

    # ---------------------------------------------------------------- delete
    def delete(self, user: AuthUser, scan_id: str) -> bool:
        params = {"id": f"eq.{scan_id}", "user_id": f"eq.{user.id}"}
        resp = self._rest.request(
            "DELETE", "scans", user, params=params, prefer="return=representation"
        )
        return bool(resp.json())

    def clear(self, user: AuthUser) -> int:
        count = self._count(
            user, {"select": "id", "user_id": f"eq.{user.id}"}
        )
        if count == 0:
            return 0
        self._rest.request(
            "DELETE", "scans", user, params={"user_id": f"eq.{user.id}"}
        )
        return count

    # ----------------------------------------------------------------- stats
    def stats(self, user: AuthUser) -> dict:
        total = self._count(user, {"select": "id", "user_id": f"eq.{user.id}"})
        rows: list[dict] = []
        if total:
            params = {
                "select": "classification,created_at",
                "user_id": f"eq.{user.id}",
                "order": "created_at.desc",
                "limit": 2000,
            }
            rows = self._rest.request("GET", "scans", user, params=params).json()
        counts: dict[str, int] = {}
        for r in rows:
            c = r.get("classification")
            counts[c] = counts.get(c, 0) + 1
        return {
            "total": total,
            "by_classification": counts,
            "latest_scan_at": rows[0].get("created_at") if rows else None,
        }


class SupabaseProfileService:
    """Read/update the caller's profile row (profiles table, RLS-protected)."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._rest = _Postgrest(settings, transport=transport)

    def get_profile(self, user: AuthUser) -> dict | None:
        params = {
            "select": "id,display_name,created_at,updated_at",
            "id": f"eq.{user.id}",
            "limit": 1,
        }
        rows = self._rest.request("GET", "profiles", user, params=params).json()
        return rows[0] if rows else None

    def upsert_profile(self, user: AuthUser, display_name: str) -> dict:
        payload = {"id": user.id, "display_name": display_name}
        resp = self._rest.request(
            "POST",
            "profiles",
            user,
            params={"on_conflict": "id"},
            json_body=payload,
            prefer="resolution=merge-duplicates,return=representation",
        )
        rows = resp.json()
        return rows[0] if rows else payload
