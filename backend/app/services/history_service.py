"""User-scoped persistence layer (policy-controlled, swappable).

A thin service layer wraps the storage engine so it can be swapped
(sqlite | supabase | memory | disabled) without touching route code.

AUTHENTICATION-AWARE (v2): every method takes the authenticated
:class:`AuthUser` (derived from a verified Supabase access token) and every
query is scoped to that user's id. A user can never read, modify or delete
another user's records - not by changing an id, query parameter or request
body. Legacy rows without an owner (user_id empty) belong to nobody and are
never exposed to any account.

The database stores ONLY: scan id, owner id, timestamp, submitted URL,
classification, risk score, model probability, model version and the full
result JSON (for reopening a scan). No cookies, credentials, page content,
or unrelated personal data.

Records are capped (FIFO trim) at HISTORY_RETENTION_LIMIT and deletable
via the API. When HISTORY_MODE=disabled or memory, nothing touches disk.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from app.core.auth import AuthUser

_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scans (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    url TEXT NOT NULL,
    classification TEXT NOT NULL,
    binary_prediction TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    probability REAL NOT NULL,
    model_version TEXT NOT NULL,
    result_json TEXT NOT NULL
);
"""

_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_scans_user_created ON scans (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_classification ON scans (classification);
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoryStore(ABC):
    mode = "abstract"

    @abstractmethod
    def save(self, record: dict, user: AuthUser) -> dict: ...
    @abstractmethod
    def list_scans(
        self, user: AuthUser, limit: int, offset: int, classification: str | None,
        search: str | None, order: str,
    ) -> tuple[list[dict], int]: ...
    @abstractmethod
    def get(self, user: AuthUser, scan_id: str) -> dict | None: ...
    @abstractmethod
    def delete(self, user: AuthUser, scan_id: str) -> bool: ...
    @abstractmethod
    def clear(self, user: AuthUser) -> int: ...
    @abstractmethod
    def stats(self, user: AuthUser) -> dict: ...


class NullHistoryStore(HistoryStore):
    """HISTORY_MODE=disabled - nothing is stored anywhere."""

    mode = "disabled"

    def save(self, record: dict, user: AuthUser) -> dict:  # noqa: ARG002
        return record

    def list_scans(self, user, limit, offset, classification, search, order):  # noqa: ARG002
        return [], 0

    def get(self, user, scan_id):  # noqa: ARG002
        return None

    def delete(self, user, scan_id):  # noqa: ARG002
        return False

    def clear(self, user: AuthUser) -> int:  # noqa: ARG002
        return 0

    def stats(self, user: AuthUser) -> dict:  # noqa: ARG002
        return {"total": 0}


class MemoryHistoryStore(HistoryStore):
    """HISTORY_MODE=memory - in-process only, cleared on restart."""

    mode = "memory"

    def __init__(self, retention_limit: int) -> None:
        self._records: dict[str, dict] = {}
        self._order: list[str] = []
        self._limit = retention_limit
        self._lock = threading.Lock()

    def save(self, record: dict, user: AuthUser) -> dict:
        with self._lock:
            record = {**record, "user_id": user.id}
            self._records[record["id"]] = record
            self._order.append(record["id"])
            while len(self._order) > self._limit:
                old = self._order.pop(0)
                self._records.pop(old, None)
        return record

    def list_scans(self, user, limit, offset, classification, search, order):
        rows = [r for r in self._records.values() if r.get("user_id") == user.id]
        if classification:
            rows = [r for r in rows if r["classification"] == classification]
        if search:
            q = search.lower()
            rows = [r for r in rows if q in r["url"].lower()]
        rows.sort(key=lambda r: r["created_at"], reverse=(order == "desc"))
        total = len(rows)
        return rows[offset: offset + limit], total

    def get(self, user, scan_id):
        rec = self._records.get(scan_id)
        if rec is not None and rec.get("user_id") == user.id:
            return rec
        return None

    def delete(self, user, scan_id):
        with self._lock:
            rec = self._records.get(scan_id)
            if rec is not None and rec.get("user_id") == user.id:
                del self._records[scan_id]
                self._order = [i for i in self._order if i != scan_id]
                return True
        return False

    def clear(self, user: AuthUser) -> int:
        with self._lock:
            owned = [i for i, r in self._records.items() if r.get("user_id") == user.id]
            for i in owned:
                self._records.pop(i, None)
            self._order = [i for i in self._order if i not in set(owned)]
            return len(owned)

    def stats(self, user: AuthUser) -> dict:
        rows = [r for r in self._records.values() if r.get("user_id") == user.id]
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["classification"]] = counts.get(r["classification"], 0) + 1
        return {
            "total": len(rows),
            "by_classification": counts,
            "latest_scan_at": max((r["created_at"] for r in rows), default=None),
        }


class SQLiteHistoryStore(HistoryStore):
    """HISTORY_MODE=sqlite - capped local persistence (development prototype).

    Every query is filtered by the verified owner id. Pre-existing databases
    from the single-user prototype are migrated transparently: old rows get
    an empty user_id, which means they are owned by nobody and never exposed
    to any account (no silent reassignment).
    """

    mode = "sqlite"

    def __init__(self, db_path: Path, retention_limit: int) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._retention = retention_limit
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            # Order matters: create the table, migrate legacy columns, THEN
            # create indexes (which reference the migrated user_id column).
            self._conn.executescript(_TABLE_SQL)
            self._migrate_add_user_id()
            self._conn.executescript(_INDEX_SQL)

    def _migrate_add_user_id(self) -> None:
        """Add user_id to pre-multi-user databases (safe, repeatable)."""
        cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(scans)")}
        if "user_id" not in cols:
            self._conn.execute(
                "ALTER TABLE scans ADD COLUMN user_id TEXT NOT NULL DEFAULT ''"
            )

    def save(self, record: dict, user: AuthUser) -> dict:
        with self._lock, self._conn:
            # Explicit column names: legacy databases may have user_id appended
            # last by ALTER TABLE, so positional inserts would be wrong.
            self._conn.execute(
                """
                INSERT INTO scans (
                    id, user_id, created_at, url, classification,
                    binary_prediction, risk_score, probability,
                    model_version, result_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record["id"], user.id, record["created_at"], record["url"],
                    record["classification"], record["binary_prediction"],
                    record["risk_score"], record["probability"],
                    record["model_version"], json.dumps(record),
                ),
            )
            # FIFO trim beyond the retention cap (this user's rows only)
            self._conn.execute(
                """
                DELETE FROM scans WHERE user_id = ? AND id IN (
                    SELECT id FROM scans WHERE user_id = ? ORDER BY created_at ASC
                    LIMIT MAX(0, (
                        SELECT COUNT(*) FROM scans WHERE user_id = ?
                    ) - ?)
                )
                """,
                (user.id, user.id, user.id, self._retention),
            )
        return record

    def list_scans(self, user, limit, offset, classification, search, order):
        clauses, params = ["user_id = ?"], [user.id]
        if classification:
            clauses.append("classification = ?")
            params.append(classification)
        if search:
            clauses.append("LOWER(url) LIKE ?")
            params.append(f"%{search.lower()}%")
        where = f"WHERE {' AND '.join(clauses)}"
        direction = "DESC" if order == "desc" else "ASC"
        with self._lock, self._conn:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM scans {where}", params
            ).fetchone()[0]
            rows = self._conn.execute(
                f"SELECT result_json FROM scans {where} "
                f"ORDER BY created_at {direction} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [json.loads(r[0]) for r in rows], int(total)

    def get(self, user, scan_id):
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT result_json FROM scans WHERE id = ? AND user_id = ?",
                (scan_id, user.id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, user, scan_id):
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM scans WHERE id = ? AND user_id = ?",
                (scan_id, user.id),
            )
            return cur.rowcount > 0

    def clear(self, user: AuthUser) -> int:
        with self._lock, self._conn:
            n = self._conn.execute(
                "SELECT COUNT(*) FROM scans WHERE user_id = ?", (user.id,)
            ).fetchone()[0]
            self._conn.execute("DELETE FROM scans WHERE user_id = ?", (user.id,))
            return int(n)

    def stats(self, user: AuthUser) -> dict:
        with self._lock, self._conn:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM scans WHERE user_id = ?", (user.id,)
            ).fetchone()[0]
            counts = self._conn.execute(
                "SELECT classification, COUNT(*) FROM scans WHERE user_id = ? "
                "GROUP BY classification",
                (user.id,),
            ).fetchall()
            latest = self._conn.execute(
                "SELECT MAX(created_at) FROM scans WHERE user_id = ?", (user.id,)
            ).fetchone()[0]
        return {
            "total": int(total),
            "by_classification": {r[0]: int(r[1]) for r in counts},
            "latest_scan_at": latest,
        }


def build_history_store(mode: str, db_path: Path, retention: int) -> HistoryStore:
    """Build the configured store. Supabase mode is wired in main.py because
    it needs the full settings object (URL + publishable key)."""
    mode = mode.lower().strip()
    if mode == "disabled":
        return NullHistoryStore()
    if mode == "memory":
        return MemoryHistoryStore(retention)
    if mode == "sqlite":
        return SQLiteHistoryStore(db_path, retention)
    if mode == "supabase":
        from app.services.supabase_store import SupabaseHistoryStore  # late import

        raise ValueError(
            "HISTORY_MODE=supabase requires build_supabase_store(settings); "
            "SUPABASE_URL/SUPABASE_PUBLISHABLE_KEY must be configured."
        )
    raise ValueError(f"Unknown HISTORY_MODE: {mode}")


def new_scan_id() -> str:
    return uuid.uuid4().hex[:16]
