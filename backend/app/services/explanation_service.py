"""
Explanation service
===================

Separates explanation into four layers (per the project design):

  1. Observed characteristics - directly measured properties of the URL.
  2. Model evidence - EXACT per-instance feature contributions derived from
     the selected model:
       * Logistic Regression: contribution_j = coef_j * z_j  (log-odds space,
         where z_j is the standardised feature value). Bias = intercept.
       * Tree ensembles (Random Forest, Extra Trees): exact decision-path decomposition per tree
         (treeinterpreter method). For each tree, predict_proba telescopes:
         P(leaf) = P(root) + sum over path of (P(child) - P(node)), and each
         delta is attributed to the split feature. Averaging over trees
         reproduces the forest's predict_proba EXACTLY.
       * Gradient boosting (HistGradientBoosting): the same path decomposition
         in log-odds space, summed over trees; sigmoid(bias + sum) is exact.
     If no method applies, the service says so and offers rule-based
     contextual guidance, clearly labelled as such (never presented as
     model-derived contributions).
  3. Risk interpretation - careful plain-language meaning of the signals.
  4. Recommended action - proportionate safety advice.

No contribution value is ever invented; global importances are never
presented as per-URL explanations.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np

from app.services.feature_extractor import FEATURE_NAMES

Method = str  # "coefficient_log_odds" | "tree_path" | "tree_path_log_odds" | "rule_based_fallback"


# ---------------------------------------------------------------------------
# Exact per-instance contribution methods
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def contributions_for_linear(
    pipeline: Any, x: np.ndarray
) -> tuple[float, dict[str, float]] | None:
    """Exact log-odds decomposition for StandardScaler+LogisticRegression."""
    try:
        steps = dict(pipeline.named_steps)
    except AttributeError:
        return None
    if "clf" not in steps or not hasattr(steps["clf"], "coef_"):
        return None
    clf = steps["clf"]
    if list(clf.classes_) != [0, 1]:
        return None
    if "scaler" in steps and hasattr(steps["scaler"], "mean_"):
        z = (x - steps["scaler"].mean_) / steps["scaler"].scale_
    else:
        z = x
    contrib = clf.coef_[0] * z
    intercept = float(clf.intercept_[0])
    per_feature = {name: float(c) for name, c in zip(FEATURE_NAMES, contrib)}
    return intercept, per_feature


def contributions_for_forest(
    pipeline: Any, x: np.ndarray
) -> tuple[float, dict[str, float]] | None:
    """
    Exact probability-space decomposition for a bagged tree ensemble
    (RandomForestClassifier or ExtraTreesClassifier: both average per-tree leaf
    class proportions, so the per-tree path decomposition is exact for both).

    Handles the bare-estimator case and Pipeline-wrapped forests. When a
    pipeline is supplied, all preceding preprocessing steps are applied to
    the feature vector first, because tree thresholds operate in the
    transformed space; contributions are then reported against the ORIGINAL
    feature names (the mapping is 1:1 by position).
    """
    x_model = np.asarray(x, dtype=float)
    forest = pipeline
    if hasattr(pipeline, "named_steps"):
        steps = list(pipeline.named_steps.items())
        if not steps:
            return None
        forest = steps[-1][1]
        for _name, step in steps[:-1]:
            if hasattr(step, "transform"):
                x_model = np.asarray(
                    step.transform(x_model.reshape(1, -1)), dtype=float
                ).ravel()
    if not hasattr(forest, "estimators_") or not hasattr(forest, "classes_"):
        return None
    if list(forest.classes_) != [0, 1]:
        return None
    if not forest.estimators_:
        return None

    idx1 = list(forest.classes_).index(1)
    bias = 0.0
    contrib: dict[str, float] = defaultdict(float)
    n_trees = len(forest.estimators_)

    for est in forest.estimators_:
        tree = est.tree_
        values = tree.value[:, 0, :]  # weighted class counts per node
        prop = values / values.sum(axis=1, keepdims=True)  # class proportion per node
        node = 0
        bias += float(prop[0][idx1])
        while tree.children_left[node] != -1:
            feat_idx = int(tree.feature[node])
            go_left = x_model[feat_idx] <= tree.threshold[node]
            child = tree.children_left[node] if go_left else tree.children_right[node]
            contrib[FEATURE_NAMES[feat_idx]] += float(prop[child][idx1] - prop[node][idx1])
            node = int(child)

    return bias / n_trees, {k: v / n_trees for k, v in contrib.items()}


def contributions_for_boosting(
    pipeline: Any, x: np.ndarray
) -> tuple[float, dict[str, float]] | None:
    """
    Exact log-odds decomposition for a binary HistGradientBoostingClassifier.

    The raw score is baseline + sum over trees of the leaf value reached.
    Within each tree the leaf value telescopes along the decision path:
    value(leaf) = value(root) + sum of (value(child) - value(node)), and each
    delta is attributed to the split feature. Internal node values are the
    sample-weighted means of their children, so the attribution is meaningful
    as well as exact. sigmoid(bias + sum(contributions)) == predict_proba.

    Uses scikit-learn's fitted predictor arrays (version pinned in
    requirements); the caller verifies exactness on every request.
    """
    x_model = np.asarray(x, dtype=float)
    model = pipeline
    if hasattr(pipeline, "named_steps"):
        steps = list(pipeline.named_steps.items())
        if not steps:
            return None
        model = steps[-1][1]
        for _name, step in steps[:-1]:
            if hasattr(step, "transform"):
                x_model = np.asarray(
                    step.transform(x_model.reshape(1, -1)), dtype=float
                ).ravel()
    predictors = getattr(model, "_predictors", None)
    baseline = getattr(model, "_baseline_prediction", None)
    if predictors is None or baseline is None or not hasattr(model, "classes_"):
        return None
    if list(model.classes_) != [0, 1]:
        return None
    is_categorical = getattr(model, "is_categorical_", None)
    if is_categorical is not None and np.any(is_categorical):
        return None

    bias = float(np.ravel(baseline)[0])
    contrib: dict[str, float] = defaultdict(float)
    for per_iteration in predictors:
        nodes = per_iteration[0].nodes  # binary task: one tree per iteration
        node = 0
        bias += float(nodes["value"][0])
        while nodes["is_leaf"][node] == 0:
            feat_idx = int(nodes["feature_idx"][node])
            value = x_model[feat_idx]
            if np.isnan(value):
                go_left = bool(nodes["missing_go_to_left"][node])
            else:
                go_left = value <= nodes["num_threshold"][node]
            child = int(nodes["left"][node] if go_left else nodes["right"][node])
            contrib[FEATURE_NAMES[feat_idx]] += float(
                nodes["value"][child] - nodes["value"][node]
            )
            node = child
    return bias, dict(contrib)


def compute_model_evidence(pipeline: Any, features: dict[str, float]) -> dict:
    """
    Returns {method, method_description, bias, contributions[], exact_sum,
    probability_check}. Falls back to method='rule_based_fallback' when the
    selected model type is not supported - never fabricates numbers.
    """
    x = np.array([float(features[name]) for name in FEATURE_NAMES])

    # Try each exact method; both helpers internally verify applicability.
    linear = contributions_for_linear(pipeline, x)
    if linear:
        bias, per_feature = linear
        proba = float(pipeline.predict_proba(x.reshape(1, -1))[0][1])
        total = _sigmoid(bias + sum(per_feature.values()))
        return {
            "method": "coefficient_log_odds",
            "method_description": (
                "Exact coefficient decomposition of the Logistic "
                "Regression: contribution = coefficient x standardised "
                "feature value, in log-odds space; bias = intercept."
            ),
            "bias": round(bias, 6),
            "probability_check": {
                "decomposition_sum": round(total, 6),
                "predict_proba": round(proba, 6),
                "exact": abs(total - proba) < 1e-6,
            },
            "contributions": per_feature,
        }

    forest = contributions_for_forest(pipeline, x)
    if forest:
        bias, per_feature = forest
        proba = float(pipeline.predict_proba(x.reshape(1, -1))[0][1])
        total = bias + sum(per_feature.values())
        return {
            "method": "tree_path",
            "method_description": (
                "Exact decision-path decomposition of the tree ensemble "
                "(treeinterpreter method): each tree's probability change "
                "along the path taken by this URL is attributed to the "
                "feature that caused the split, averaged over all trees."
            ),
            "bias": round(bias, 6),
            "probability_check": {
                "decomposition_sum": round(total, 6),
                "predict_proba": round(proba, 6),
                "exact": abs(total - proba) < 1e-6,
            },
            "contributions": per_feature,
        }

    boosting = contributions_for_boosting(pipeline, x)
    if boosting:
        bias, per_feature = boosting
        proba = float(pipeline.predict_proba(x.reshape(1, -1))[0][1])
        total = _sigmoid(bias + sum(per_feature.values()))
        # The decomposition reads fitted predictor arrays, so it is shown only
        # when it reproduces predict_proba; otherwise fall through honestly.
        if abs(total - proba) < 1e-6:
            return {
                "method": "tree_path_log_odds",
                "method_description": (
                    "Exact decision-path decomposition of the gradient-boosted "
                    "trees: each tree's change in log-odds along the path taken "
                    "by this URL is attributed to the feature that caused the "
                    "split, summed over all trees; bias = baseline log-odds."
                ),
                "bias": round(bias, 6),
                "probability_check": {
                    "decomposition_sum": round(total, 6),
                    "predict_proba": round(proba, 6),
                    "exact": True,
                },
                "contributions": per_feature,
            }

    return {
        "method": "rule_based_fallback",
        "method_description": (
            "The selected model type does not expose a per-instance "
            "contribution method in this prototype. Only measured URL "
            "characteristics are shown below; no model-derived contributions "
            "are available."
        ),
        "bias": None,
        "probability_check": None,
        "contributions": {},
    }


# ---------------------------------------------------------------------------
# Observed characteristics (only what is actually present)
# ---------------------------------------------------------------------------

def observed_characteristics(features: dict[str, float]) -> list[dict[str, str]]:
    obs: list[dict[str, str]] = []

    def add(label: str, detail: str, severity: str) -> None:
        obs.append({"label": label, "detail": detail, "severity": severity})

    if features.get("has_ip"):
        add("IP address host", "The hostname is a raw IP address instead of a domain name.", "high")
    if features.get("has_credentials_pattern"):
        add("Credentials in URL", "The URL contains a 'user:password@' style section, a classic technique to hide the real destination.", "high")
    if features.get("nb_at_symbol", 0) > 0:
        add("'@' symbol present", "An '@' appears in the URL. Everything before it is ignored by browsers, which can disguise the real host.", "high")
    if features.get("is_https") == 0:
        add("No HTTPS", "The submitted link does not use the https:// scheme (or no scheme was provided).", "medium")
    if features.get("has_brand_token_outside_domain"):
        add("Brand name outside the domain", "A well-known brand token appears in the URL but not in the actual registrable domain - a common impersonation pattern.", "high")
    if features.get("nb_suspicious_tokens", 0) > 0:
        add("Security-themed wording", f"The URL contains {int(features['nb_suspicious_tokens'])} term(s) from the generic security/urgency vocabulary (e.g. 'login', 'verify', 'account').", "medium")
    if features.get("nb_subdomain_labels", 0) >= 3:
        add("Deep subdomain nesting", f"The hostname has {int(features['nb_subdomain_labels'])} subdomain levels, which can push the real destination out of sight.", "medium")
    if features.get("has_punycode"):
        add("Punycode / internationalised domain", "The hostname contains punycode ('xn--') labels, sometimes used to imitate familiar characters.", "medium")
    if features.get("nb_pct_encoded", 0) >= 3:
        add("Heavy encoding", f"The URL contains {int(features['nb_pct_encoded'])} percent-encoded sequences, which can obscure its content.", "medium")
    if features.get("nb_double_slash_path", 0) > 0:
        add("Embedded redirect pattern", "A '//' appears inside the path or query, a pattern seen in open redirects.", "medium")
    if features.get("is_shortener_domain"):
        add("URL shortener", "The domain appears on the documented URL-shortener list, hiding the final destination.", "medium")
    if features.get("has_suspicious_tld"):
        add("High-abuse TLD", "The domain extension appears on the documented high-abuse TLD list (weak signal - legitimate sites also use these).", "low")
    if features.get("has_non_standard_port"):
        add("Non-standard port", "An explicit non-standard port (not 80/443) is part of the URL.", "medium")
    if features.get("has_executable_extension"):
        add("Executable file path", "The path points to an executable or archive file type.", "high")
    if features.get("has_long_hostname"):
        add("Unusually long hostname", f"The hostname is {int(features['hostname_length'])} characters long.", "low")
    if features.get("nb_hex_labels_hostname", 0) > 0:
        add("Random-looking hostname label", "Part of the hostname is a long hexadecimal string, typical of generated domains.", "medium")
    if features.get("hostname_entropy", 0) >= 3.8:
        add("High hostname randomness", f"Hostname character entropy is {features['hostname_entropy']:.2f} (randomness indicator).", "low")
    if features.get("url_length", 0) > 150:
        add("Very long URL", f"The URL is {int(features['url_length'])} characters long.", "low")
    if features.get("nb_query_params", 0) >= 6:
        add("Many query parameters", f"The query string carries {int(features['nb_query_params'])} parameters.", "low")
    if features.get("is_https") == 1 and not any(o["severity"] in {"high", "medium"} for o in obs):
        add("Standard HTTPS form", "The URL uses https:// with no strongly unusual structural signals observed.", "info")
    if not obs:
        add("No notable signals", "None of the documented lexical indicators were observed in this URL.", "info")
    return obs


# ---------------------------------------------------------------------------
# Risk interpretation + recommendations
# ---------------------------------------------------------------------------

def risk_interpretation(
    classification: str,
    is_uncertain: bool,
    probability: float,
    contributions: list[dict[str, Any]],
    method: str,
) -> str:
    top = ", ".join(c["feature_label"] for c in contributions[:3]) or "the measured characteristics"
    if method == "rule_based_fallback":
        base = (
            "This assessment is based on measured URL characteristics only; "
            "the selected model does not expose per-instance feature "
            "contributions in this prototype. "
        )
    else:
        base = (
            f"The model's decision was driven mainly by {top}. "
        )
    if classification == "high_risk":
        text = (
            base +
            f"The model estimates a {probability*100:.0f}% probability that this URL matches "
            "phishing patterns seen in its training data, which is a strong signal, "
            "but it is an estimate - not proof of criminal intent."
        )
    elif classification == "suspicious":
        text = (
            base +
            f"The model estimates a {probability*100:.0f}% phishing-class probability, "
            "meaning meaningful but not conclusive phishing indicators are present."
        )
    else:
        text = (
            base +
            f"The model estimates a {probability*100:.0f}% phishing-class probability, "
            "below its decision threshold, meaning no dominant phishing signals were found "
            "in the URL structure itself."
        )
    if is_uncertain:
        text += (
            " The score falls inside the model's documented uncertainty band, so treat "
            "this result as inconclusive and rely on the observed characteristics."
        )
    return text


RECOMMENDATIONS_BY_BAND: dict[str, list[str]] = {
    "high_risk": [
        "Do not open this link, and never enter passwords, payment details, or personal information on it.",
        "Report the link through your institution's official phishing-reporting channel (for AIU: the campus IT service desk).",
        "If you already interacted with the destination, change affected credentials immediately from a trusted bookmark - not from this link.",
        "Delete the message that delivered this link after reporting it.",
    ],
    "suspicious": [
        "Do not enter passwords, payment details, or personal information until the destination is verified through an independent source.",
        "Compare the domain against the official address obtained from the organisation's website or official app - not from the message.",
        "Check the brand name, subdomains and spelling carefully; impersonation often hides after '/' or in long subdomains.",
        "Ask your campus IT team or use your institution's official reporting process if unsure.",
    ],
    "likely_benign": [
        "This classification is not a guarantee of safety - the URL structure alone cannot prove a site is legitimate.",
        "Stay alert for urgency, unexpected attachments, or requests for credentials after opening any link.",
        "Verify the domain against an independently obtained official source when money or credentials are involved.",
    ],
}

CONTEXTUAL_RECOMMENDATIONS: list[tuple[str, str]] = [
    ("has_brand_token_outside_domain", "The brand token appears outside the registrable domain: verify the organisation's real web address from an official source."),
    ("is_shortener_domain", "Because this is a shortened link, the final destination is hidden; use a link-expander preview or request the full URL from the sender."),
    ("has_credentials_pattern", "The URL embeds credential-style text: browsers will send you to the host after the '@' - inspect the full address carefully."),
    ("nb_suspicious_tokens>=2", "Multiple urgency/security terms appear in the URL: be extra cautious about any page asking for sign-in details."),
]

CANNOT_DETERMINE = [
    "Whether the destination website itself is malicious - this scanner never visits the site.",
    "Whether the page content, downloads, or server behaviour are safe.",
    "Whether the domain has a known bad or good reputation (no threat-intelligence provider is integrated).",
    "Whether the model probability reflects real-world risk - probabilities are uncalibrated estimates.",
    "Whether novel phishing techniques that differ from the training data will be caught.",
]


def build_explanation(
    url: str,
    parsed: Any,
    features: dict[str, float],
    probability: float,
    classification: str,
    binary_prediction: str,
    is_uncertain: bool,
    pipeline: Any,
) -> dict:
    evidence = compute_model_evidence(pipeline, features)
    method = evidence["method"]

    contributions: list[dict[str, Any]] = []
    if evidence["contributions"]:
        from app.services.feature_extractor import FEATURE_DESCRIPTIONS

        items = sorted(evidence["contributions"].items(), key=lambda kv: abs(kv[1]), reverse=True)
        for name, value in items[:8]:
            if abs(value) < 1e-9:
                continue
            contributions.append(
                {
                    "feature": name,
                    "feature_label": FEATURE_DESCRIPTIONS.get(name, name),
                    "feature_value": features.get(name),
                    "contribution": round(value, 6),
                    "direction": "toward_phishing" if value > 0 else "toward_benign",
                }
            )
    evidence["top_contributions"] = contributions
    evidence["disclaimer"] = (
        "Contributions show which features moved THIS prediction, per the "
        "documented exact decomposition. They do not prove causation in the "
        "real world, and they do not measure feature importance across the "
        "dataset."
    )

    interpretation = risk_interpretation(
        classification, is_uncertain, probability, contributions, method
    )

    actions = list(RECOMMENDATIONS_BY_BAND[classification])
    for key, advice in CONTEXTUAL_RECOMMENDATIONS:
        if key.endswith(">=2"):
            feat = key.split(">=")[0]
            if features.get(feat, 0) >= 2 and advice not in actions:
                actions.append(advice)
        elif features.get(key) and advice not in actions:
            actions.append(advice)
    if binary_prediction == "benign":
        actions.append(
            "A benign prediction is not a safety certificate: if the message around this "
            "link creates urgency or asks for credentials, treat it with suspicion."
        )

    return {
        "summary": interpretation,
        "observed_characteristics": observed_characteristics(features),
        "model_evidence": evidence,
        "risk_interpretation": interpretation,
        "recommended_actions": actions,
        "cannot_determine": list(CANNOT_DETERMINE),
    }
