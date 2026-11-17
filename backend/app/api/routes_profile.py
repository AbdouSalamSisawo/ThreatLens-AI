"""Authenticated profile endpoints (account settings).

GET  /api/profile  - the caller's profile row (display name, timestamps).
PUT  /api/profile  - update supported profile fields (display name only).

The profile row lives in the Supabase ``profiles`` table and is protected
by RLS: the query runs under the caller's own access token, so users can
only ever read or update their own row. If the SQL migration has not been
applied yet, the endpoints report a clear 503 instead of pretending.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app.core.auth import AuthUser, get_current_user
from app.services.supabase_store import StoreForbidden, StoreUnavailable

router = APIRouter(prefix="/api", tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=60)

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("display_name cannot be empty")
        return v


class ProfileResponse(BaseModel):
    display_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    profile_source: str = "supabase"


def _profile_service(request: Request):
    return request.app.state.profile_service


def _map_store_error(exc: Exception) -> HTTPException:
    if isinstance(exc, StoreForbidden):
        return HTTPException(
            status_code=403,
            detail={
                "code": "profile_forbidden",
                "message": "The database refused access to your profile.",
            },
        )
    return HTTPException(
        status_code=503,
        detail={
            "code": "profile_store_unavailable",
            "message": str(exc) or "The profile store is currently unavailable.",
        },
    )


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    request: Request,
    user: AuthUser = Depends(get_current_user),
) -> ProfileResponse:
    service = _profile_service(request)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "profile_store_unavailable",
                "message": "Profile storage requires Supabase configuration.",
            },
        )
    try:
        row = service.get_profile(user)
    except (StoreUnavailable, StoreForbidden) as exc:
        raise _map_store_error(exc) from exc
    if row is None:
        # No row yet (e.g. the signup trigger could not run). Not an error:
        # the UI falls back to the verified email from the session.
        return ProfileResponse(display_name=None)
    return ProfileResponse(
        display_name=row.get("display_name"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
) -> ProfileResponse:
    service = _profile_service(request)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "profile_store_unavailable",
                "message": "Profile storage requires Supabase configuration.",
            },
        )
    try:
        row = service.upsert_profile(user, payload.display_name)
    except (StoreUnavailable, StoreForbidden) as exc:
        raise _map_store_error(exc) from exc
    return ProfileResponse(
        display_name=row.get("display_name"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )
