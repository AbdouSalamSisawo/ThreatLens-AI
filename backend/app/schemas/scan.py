"""Pydantic request/response schemas for the scan API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ScanRequest(BaseModel):
    url: str = Field(..., description="The URL to analyse (http/https, or a bare domain).")

    @field_validator("url")
    @classmethod
    def url_must_be_string_like(cls, v: str) -> str:
        if v is None:
            raise ValueError("url is required")
        return v


class ObservedCharacteristic(BaseModel):
    label: str
    detail: str
    severity: str  # high | medium | low | info


class ModelContribution(BaseModel):
    feature: str
    feature_label: str
    feature_value: float | int | str | None
    contribution: float
    direction: str  # toward_phishing | toward_benign


class ModelEvidence(BaseModel):
    method: str
    method_description: str
    bias: float | None = None
    probability_check: dict[str, Any] | None = None
    contributions: dict[str, float] = Field(default_factory=dict)
    top_contributions: list[ModelContribution] = Field(default_factory=list)
    disclaimer: str


class FeatureValue(BaseModel):
    name: str
    value: float | int
    description: str


class Explanation(BaseModel):
    summary: str
    observed_characteristics: list[ObservedCharacteristic]
    model_evidence: ModelEvidence
    risk_interpretation: str
    recommended_actions: list[str]
    cannot_determine: list[str]


class ThreatIntelligenceStatus(BaseModel):
    provider: str
    status: str  # confirmed_match | no_match | unknown | unavailable
    message: str


class ScanResult(BaseModel):
    scan_id: str
    url: str
    scheme_was_inferred: bool = False
    classification: str  # likely_benign | suspicious | high_risk
    binary_prediction: str  # phishing | benign
    risk_score: int = Field(..., ge=0, le=100)
    model_probability: float = Field(..., ge=0.0, le=1.0)
    is_uncertain: bool
    observed_features: list[FeatureValue]
    explanation: Explanation
    threat_intelligence: ThreatIntelligenceStatus
    model_version: str
    model_id: str
    selected_model: str
    feature_schema_version: str
    scan_timestamp: str
    scan_duration_ms: float
    history_saved: bool = False
    limitations: list[str]


class ScanError(BaseModel):
    error: dict[str, Any]


class HistoryListResponse(BaseModel):
    scans: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    history_mode: str


class HistoryDeleteResponse(BaseModel):
    deleted: bool
    scan_id: str | None = None
    deleted_count: int | None = None


class DashboardResponse(BaseModel):
    history_mode: str
    total_scans: int
    by_classification: dict[str, int]
    latest_scan_at: str | None
    recent_scans: list[dict[str, Any]]
    classification_distribution: list[dict[str, Any]]
    model: dict[str, Any]
    generated_at: str


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str


class ReadyResponse(BaseModel):
    ready: bool
    model_available: bool
    model_message: str | None = None
    history_mode: str
    checks: dict[str, bool]
