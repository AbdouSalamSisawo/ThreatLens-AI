"""Scan history endpoints (list/get/delete/clear) - user-scoped.

Every endpoint requires a verified Supabase access token and passes the
authenticated user to the store, which filters every query by the verified
owner id (and, for Supabase mode, executes the query under the caller's own
JWT so RLS re-checks ownership at the database). A foreign or missing scan
returns 404 - never a 403 - so record existence is not disclosed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.auth import AuthUser, get_current_user
from app.schemas.scan import HistoryDeleteResponse, HistoryListResponse

router = APIRouter(prefix="/api", tags=["history"])

CLASSIFICATIONS = {"likely_benign", "suspicious", "high_risk"}


@router.get("/history", response_model=HistoryListResponse)
def list_history(
    request: Request,
    user: AuthUser = Depends(get_current_user),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    classification: str | None = Query(None),
    search: str | None = Query(None, max_length=200),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> HistoryListResponse:
    store = request.app.state.history_store
    if classification is not None and classification not in CLASSIFICATIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_classification",
                "message": "classification must be one of: " + ", ".join(sorted(CLASSIFICATIONS)),
            },
        )
    scans, total = store.list_scans(user, limit, offset, classification, search, order)
    # Strip heavy nested result payloads for the list view
    slim = [
        {k: v for k, v in s.items() if k != "result"} if isinstance(s, dict) else s
        for s in scans
    ]
    return HistoryListResponse(
        scans=slim, total=total, limit=limit, offset=offset, history_mode=store.mode
    )


@router.get("/history/{scan_id}")
def get_scan(
    scan_id: str,
    request: Request,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    store = request.app.state.history_store
    record = store.get(user, scan_id)
    if record is None:
        # Also covers another user's record: existence is not disclosed.
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Scan record not found."},
        )
    return record


@router.delete("/history/{scan_id}", response_model=HistoryDeleteResponse)
def delete_scan(
    scan_id: str,
    request: Request,
    user: AuthUser = Depends(get_current_user),
) -> HistoryDeleteResponse:
    store = request.app.state.history_store
    if store.mode == "disabled":
        raise HTTPException(
            status_code=404,
            detail={"code": "history_disabled", "message": "History storage is disabled."},
        )
    deleted = store.delete(user, scan_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Scan record not found."},
        )
    return HistoryDeleteResponse(deleted=True, scan_id=scan_id)


@router.delete("/history", response_model=HistoryDeleteResponse)
def clear_history(
    request: Request,
    user: AuthUser = Depends(get_current_user),
) -> HistoryDeleteResponse:
    store = request.app.state.history_store
    count = store.clear(user)
    return HistoryDeleteResponse(deleted=count > 0, deleted_count=count)
