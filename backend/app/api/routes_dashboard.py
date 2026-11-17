"""GET /api/dashboard - real aggregates from the authenticated user's records.

Every number here comes from an actual database query scoped to the
verified caller (plus the public model-evaluation artefacts). Nothing is
simulated, and no other user's activity is ever included.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.auth import AuthUser, get_current_user
from app.ml.model_metadata import public_model_info
from app.schemas.scan import DashboardResponse
from app.services.supabase_store import StoreForbidden, StoreUnavailable

router = APIRouter(prefix="/api", tags=["dashboard"])


def _store_error_response(exc: Exception) -> HTTPException:
    if isinstance(exc, StoreForbidden):
        return HTTPException(
            status_code=403,
            detail={
                "code": "history_forbidden",
                "message": "The database refused access to your scan records.",
            },
        )
    return HTTPException(
        status_code=503,
        detail={
            "code": "history_store_unavailable",
            "message": str(exc) or "The scan-history store is currently unavailable.",
        },
    )


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    request: Request,
    user: AuthUser = Depends(get_current_user),
    recent_limit: int = Query(10, ge=1, le=50),
) -> DashboardResponse:
    state = request.app.state
    store = state.history_store
    try:
        stats = store.stats(user)
        recent, _total = store.list_scans(
            user, limit=recent_limit, offset=0, classification=None, search=None,
            order="desc",
        )
    except (StoreUnavailable, StoreForbidden) as exc:
        raise _store_error_response(exc) from exc
    slim = [
        {k: v for k, v in s.items() if k != "result"} if isinstance(s, dict) else s
        for s in recent
    ]

    by_class = stats.get("by_classification", {})
    distribution = [
        {"classification": key, "count": int(by_class.get(key, 0))}
        for key in ("likely_benign", "suspicious", "high_risk")
    ]

    model_block: dict = {"available": False}
    if state.loaded_model is not None:
        info = public_model_info(state.loaded_model)
        test = info.get("test_metrics", {})
        model_block = {
            "available": True,
            "model_id": info.get("model_id"),
            "model_version": info.get("model_version"),
            "selected_model": info.get("selected_model"),
            "trained_at": info.get("trained_at"),
            "test_metrics": test,
            "evaluation_available": info.get("evaluation_available", False),
        }

    from app.services.history_service import utc_now_iso  # single source

    return DashboardResponse(
        history_mode=store.mode,
        total_scans=int(stats.get("total", 0)),
        by_classification={k: int(by_class.get(k, 0)) for k in
                           ("likely_benign", "suspicious", "high_risk")},
        latest_scan_at=stats.get("latest_scan_at"),
        recent_scans=slim,
        classification_distribution=distribution,
        model=model_block,
        generated_at=utc_now_iso(),
    )
