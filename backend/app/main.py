"""
ThreatLens AI - FastAPI application entry point.

Startup sequence:
  1. Load configuration from environment (.env supported).
  2. Configure logging.
  3. Load the TRAINED model artefact (never trains at startup; never
     fabricates a replacement). A missing artefact degrades the API to an
     explicit "model unavailable" state - health/ready/report it honestly.
  4. Build the configured history store (disabled | memory | sqlite).
  5. Wire the reputation service (none integrated -> honest status).

Security posture:
  * No endpoint fetches arbitrary URLs. The scan path contains zero HTTP
    clients.
  * Request-size and URL-length limits enforced.
  * In-process sliding-window rate limiting on the scan endpoint.
  * Consistent JSON error format; no stack traces leak to clients in
    production.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    routes_dashboard,
    routes_health,
    routes_history,
    routes_model,
    routes_profile,
    routes_scan,
)
from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging
from app.core.rate_limit import SlidingWindowRateLimiter
from app.ml.model_loader import ModelNotAvailableError, load_model
from app.services.explanation_service import build_explanation
from app.services.history_service import (
    build_history_store,
    new_scan_id,
    utc_now_iso,
)
from app.services.reputation_service import build_reputation_service

logger = logging.getLogger("threatlens.main")

DESCRIPTION = """
Explainable phishing-URL detection API (student prototype).

* `POST /api/scan` analyses a URL **without ever contacting the destination**.
* Predictions come from a locally trained scikit-learn model; explanations
  are exact per-instance feature decompositions.
* No threat-intelligence provider is integrated; none is simulated.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging("DEBUG" if not settings.is_production else "INFO")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = app.state
        state.settings = settings
        state.feature_extractor_ready = True
        state.new_scan_id = new_scan_id
        state.utc_now_iso = utc_now_iso
        state.explanation_builder = build_explanation
        state.rate_limiter = SlidingWindowRateLimiter(
            max_requests=settings.rate_limit_scan_per_minute, window_seconds=60
        )
        state.profile_service = None
        if settings.history_mode == "supabase":
            if not settings.supabase_configured:
                raise RuntimeError(
                    "HISTORY_MODE=supabase requires SUPABASE_URL and "
                    "SUPABASE_PUBLISHABLE_KEY in the backend environment."
                )
            from app.services.supabase_store import (
                SupabaseHistoryStore,
                SupabaseProfileService,
            )

            state.history_store = SupabaseHistoryStore(settings)
            state.profile_service = SupabaseProfileService(settings)
        else:
            state.history_store = build_history_store(
                settings.history_mode,
                settings.database_path,
                settings.history_retention_limit,
            )
            if settings.supabase_configured:
                # Auth works with any history mode; profile storage uses
                # Supabase when configured (still no privileged key).
                from app.services.supabase_store import SupabaseProfileService

                state.profile_service = SupabaseProfileService(settings)
        state.reputation_service = build_reputation_service(settings)
        state.loaded_model = None
        state.inference_service = None
        state.model_error = None
        try:
            state.loaded_model = load_model(settings)
            from app.services.inference_service import InferenceService

            state.inference_service = InferenceService(state.loaded_model)
            logger.info(
                "Ready: model %s v%s | history mode=%s",
                state.inference_service.model_id,
                state.inference_service.model_version,
                state.history_store.mode,
            )
        except ModelNotAvailableError as exc:
            state.model_error = str(exc)
            logger.error("Model not available: %s", exc)
        except Exception as exc:  # noqa: BLE001
            state.model_error = f"Unexpected model load failure: {exc}"
            logger.exception("Unexpected model load failure")
        yield
        # No background resources to release (sqlite store is request-scoped)

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=DESCRIPTION,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=600,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if request.method == "POST":
            content_length = request.headers.get("content-length")
            if content_length and content_length.isdigit():
                if int(content_length) > settings.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "payload_too_large",
                                "message": "Request body exceeds the allowed size.",
                            }
                        },
                    )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if not settings.is_production:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        message = (
            "An unexpected internal error occurred."
            if settings.is_production
            else f"An unexpected internal error occurred: {exc}"
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": message}},
        )

    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": f"Invalid request: {first.get('msg', 'malformed body')} ({loc or 'body'}).",
                    "details": exc.errors(),
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # Normalise every HTTP error into the {"error": {...}} envelope.
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            payload = exc.detail
        else:
            payload = {"code": "http_error", "message": str(exc.detail)}
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": payload},
            headers=getattr(exc, "headers", None),
        )

    app.include_router(routes_health.router)
    app.include_router(routes_scan.router)
    app.include_router(routes_model.router)
    app.include_router(routes_history.router)
    app.include_router(routes_dashboard.router)
    app.include_router(routes_profile.router)

    # Optional single-origin hosting of the built frontend (vite build output
    # copied to backend/static). Registered after the API routes so /api
    # always wins. The SPA uses hash routing, so server-side deep links are
    # limited to "/" and "/index.html".
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.is_dir() and (static_dir / "index.html").exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="spa")
        logger.info("Serving built frontend from %s", static_dir)

    return app


app = create_app()
