"""POST /api/scan - the core URL analysis endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.core.auth import AuthUser, get_current_user
from app.core.logging_config import redact_url
from app.services.feature_extractor import (
    FEATURE_DESCRIPTIONS,
    URLValidationError,
    parse_url,
)
from app.services.inference_service import InferenceError
from app.services.reputation_service import NoProviderConfigured
from app.utils.validation import validate_url_input
from app.schemas.scan import ScanRequest, ScanResult

logger = logging.getLogger("threatlens.api.scan")
router = APIRouter(prefix="/api", tags=["scan"])


@router.post(
    "/scan",
    response_model=ScanResult,
    responses={400: {"description": "Invalid input"}, 401: {"description": "Not authenticated"},
               429: {"description": "Rate limited"},
               503: {"description": "Model unavailable"}},
)
def scan_url(
    payload: ScanRequest,
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
) -> ScanResult:
    state = request.app.state

    # -- Rate limiting (per authenticated user, not per IP) -------------------
    allowed, retry_after = state.rate_limiter.check(f"scan:{user.id}")
    if not allowed:
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many scan requests. Please wait before trying again.",
                "retry_after_seconds": retry_after,
            },
        )

    # -- Server-side validation (client validation is never trusted) ----------
    settings = state.settings
    verdict = validate_url_input(payload.url, settings.max_url_length)
    if not verdict.ok:
        raise HTTPException(
            status_code=400,
            detail={"code": verdict.error_code, "message": verdict.message},
        )
    url = verdict.cleaned_url  # type: ignore[assignment]

    # -- Model availability: explicit error, never a fallback prediction ------
    if state.inference_service is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "model_unavailable",
                "message": state.model_error or (
                    "The trained model is not available. Train it with the "
                    "documented pipeline before scanning."
                ),
            },
        )

    # -- Parse (NO network request - the destination is never contacted) ------
    try:
        parsed = parse_url(url)
    except URLValidationError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_url", "message": str(exc)}
        ) from exc

    # -- Genuine inference ------------------------------------------------------
    try:
        prediction = state.inference_service.predict(url)
    except InferenceError as exc:
        logger.error("Inference failed for %s: %s", redact_url(url), exc)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "inference_failed",
                "message": "The model failed to produce a prediction. No result is returned.",
            },
        ) from exc

    # -- Explanation -------------------------------------------------------------
    try:
        explanation = state.explanation_builder(
            url=url,
            parsed=parsed,
            features=prediction["features"],
            probability=prediction["probability_phishing"],
            classification=prediction["classification"],
            binary_prediction=prediction["binary_prediction"],
            is_uncertain=prediction["is_uncertain"],
            pipeline=state.inference_service._pipeline,
        )
    except Exception:  # noqa: BLE001 - explanation failure must not fake results
        logger.exception("Explanation generation failed")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "explanation_failed",
                "message": "The classification succeeded but explanation generation failed.",
            },
        )

    # -- Optional persistence per configured policy -------------------------------
    # Ownership comes from the verified token, never from the browser.
    scan_id = state.new_scan_id()
    scan_timestamp = state.utc_now_iso()
    history_saved = False
    record = {
        "id": scan_id,
        "user_id": user.id,
        "created_at": scan_timestamp,
        "url": url,
        "classification": prediction["classification"],
        "binary_prediction": prediction["binary_prediction"],
        "risk_score": prediction["risk_score"],
        "probability": prediction["probability_phishing"],
        "model_version": state.inference_service.model_version,
        "result": None,
    }
    try:
        record["result"] = True  # full JSON persisted by store if supported
        if state.history_store.mode != "disabled":
            from app.schemas.scan import ScanResult as SR

            full_result = _build_result(
                state, record, url, parsed, prediction, explanation, scan_timestamp
            )
            record["result"] = full_result.model_dump()
            state.history_store.save(record, user)
            history_saved = True
    except Exception:  # noqa: BLE001 - history failure must not break scanning
        logger.exception("History persistence failed (scan result still returned)")
        history_saved = False

    result = _build_result(state, record, url, parsed, prediction, explanation, scan_timestamp)
    result.history_saved = history_saved
    logger.info(
        "scan %s %s -> %s (%.3f)", scan_id, redact_url(url),
        prediction["classification"], prediction["probability_phishing"],
    )
    return result


def _build_result(state, record, url, parsed, prediction, explanation, scan_timestamp) -> ScanResult:
    features = prediction["features"]
    return ScanResult(
        scan_id=record["id"],
        url=url,
        scheme_was_inferred=parsed.scheme_was_inferred,
        classification=prediction["classification"],
        binary_prediction=prediction["binary_prediction"],
        risk_score=prediction["risk_score"],
        model_probability=round(prediction["probability_phishing"], 6),
        is_uncertain=prediction["is_uncertain"],
        observed_features=[
            {"name": k, "value": v, "description": FEATURE_DESCRIPTIONS.get(k, k)}
            for k, v in features.items()
        ],
        explanation=explanation,
        threat_intelligence=state.reputation_service.check(url),
        model_version=state.inference_service.model_version,
        model_id=state.inference_service.model_id,
        selected_model=state.inference_service.selected_model,
        feature_schema_version=state.inference_service.feature_schema_version,
        scan_timestamp=scan_timestamp,
        scan_duration_ms=prediction["duration_ms"],
        limitations=[
            "A benign prediction does not guarantee the URL is safe.",
            "A phishing prediction is an estimate, not a confirmed threat.",
            "URL-only analysis cannot see page content or server behaviour.",
            "No threat-intelligence provider is integrated; the prediction is from the local model only.",
        ],
    )
