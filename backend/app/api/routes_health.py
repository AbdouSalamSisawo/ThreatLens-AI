"""Health and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.scan import HealthResponse, ReadyResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/ready", response_model=ReadyResponse)
def ready(request: Request) -> ReadyResponse:
    state = request.app.state
    settings = state.settings
    model_available = state.inference_service is not None
    checks = {
        "model_loaded": model_available,
        "history_store_ready": state.history_store is not None,
        "feature_extractor_ready": state.feature_extractor_ready,
        # Auth readiness reports only booleans - never internal configuration.
        "auth_configured": settings.supabase_configured,
        "profile_store_ready": state.profile_service is not None
        or settings.history_mode == "disabled",
    }
    return ReadyResponse(
        ready=all(checks.values()),
        model_available=model_available,
        model_message=None if model_available else state.model_error,
        history_mode=state.history_store.mode,
        checks=checks,
    )
