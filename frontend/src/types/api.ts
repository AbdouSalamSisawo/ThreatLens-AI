/* Typed mirrors of the FastAPI response schemas (see backend/app/schemas). */

export type Classification = "likely_benign" | "suspicious" | "high_risk";
export type BinaryPrediction = "phishing" | "benign";

export interface ObservedCharacteristic {
  label: string;
  detail: string;
  severity: "high" | "medium" | "low" | "info";
}

export interface ModelContribution {
  feature: string;
  feature_label: string;
  feature_value: number | string | null;
  contribution: number;
  direction: "toward_phishing" | "toward_benign";
}

export interface ModelEvidence {
  method: "tree_path" | "coefficient_log_odds" | "rule_based_fallback";
  method_description: string;
  bias: number | null;
  probability_check: {
    decomposition_sum: number;
    predict_proba: number;
    exact: boolean;
  } | null;
  contributions: Record<string, number>;
  top_contributions: ModelContribution[];
  disclaimer: string;
}

export interface Explanation {
  summary: string;
  observed_characteristics: ObservedCharacteristic[];
  model_evidence: ModelEvidence;
  risk_interpretation: string;
  recommended_actions: string[];
  cannot_determine: string[];
}

export interface ThreatIntelligenceStatus {
  provider: string;
  status: "confirmed_match" | "no_match" | "unknown" | "unavailable";
  message: string;
}

export interface FeatureValue {
  name: string;
  value: number;
  description: string;
}

export interface ScanResult {
  scan_id: string;
  url: string;
  scheme_was_inferred: boolean;
  classification: Classification;
  binary_prediction: BinaryPrediction;
  risk_score: number;
  model_probability: number;
  is_uncertain: boolean;
  observed_features: FeatureValue[];
  explanation: Explanation;
  threat_intelligence: ThreatIntelligenceStatus;
  model_version: string;
  model_id: string;
  selected_model: string;
  feature_schema_version: string;
  scan_timestamp: string;
  scan_duration_ms: number;
  history_saved: boolean;
  limitations: string[];
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface ModelInfo {
  model_id: string;
  model_version: string;
  trained_at: string;
  selected_model: string;
  selection_reason: string;
  feature_schema_version: string;
  n_features: number;
  probability_meaning: string;
  classification_bands: Record<
    string,
    { min_probability: number; description?: string }
  >;
  uncertain_band: { lower: number; upper: number };
  dataset: {
    source: string;
    retrieved: string;
    prepared_records: number;
    class_distribution: { phishing: number; legitimate: number };
  };
  training_config: Record<string, unknown>;
  test_metrics: TestMetrics | Record<string, never>;
  evaluation_available: boolean;
  evaluation_notes: string[];
}

export interface TestMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc: number | null;
  pr_auc: number | null;
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
}

export interface FullMetrics extends ModelInfo {
  split_sizes: { train: number; validation: number; test: number; cv_folds?: number; scheme?: string };
  validation_comparison: Record<
    string,
    {
      accuracy: number;
      precision: number;
      recall: number;
      f1: number;
      roc_auc: number | null;
      pr_auc: number | null;
    }
  >;
  majority_baseline_validation_accuracy: number;
  domain_grouped_evaluation: {
    description: string;
    n_train: number;
    n_holdout: number;
    n_unique_domains_holdout: number;
    metrics: TestMetrics;
  };
  out_of_source_checks: Record<string, unknown>;
  evaluation_notes: string[];
}

export interface HistoryItem {
  id: string;
  created_at: string;
  url: string;
  classification: Classification;
  binary_prediction: BinaryPrediction;
  risk_score: number;
  probability: number;
  model_version: string;
}

export interface HistoryResponse {
  scans: HistoryItem[];
  total: number;
  limit: number;
  offset: number;
  history_mode: string;
}

export interface DashboardData {
  history_mode: string;
  total_scans: number;
  by_classification: Record<Classification, number>;
  latest_scan_at: string | null;
  recent_scans: HistoryItem[];
  classification_distribution: { classification: string; count: number }[];
  model: {
    available: boolean;
    model_id?: string;
    model_version?: string;
    selected_model?: string;
    trained_at?: string;
    test_metrics?: TestMetrics;
    evaluation_available?: boolean;
  };
  generated_at: string;
}

export interface ReadyData {
  ready: boolean;
  model_available: boolean;
  model_message: string | null;
  history_mode: string;
  checks: Record<string, boolean>;
}

export interface ProfileResponse {
  display_name: string | null;
  created_at: string | null;
  updated_at: string | null;
  profile_source?: string;
}
