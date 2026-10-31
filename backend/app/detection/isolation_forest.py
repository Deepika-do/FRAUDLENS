"""
Technique 6: Isolation Forest (Machine Learning)
Detects anomalous invoices based on a set of numerical features using scikit-learn.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

MIN_TRAINING_SAMPLES = 10     # minimum samples required to fit the model
CONTAMINATION = 0.05          # configurable: expected fraction of outliers in training set
RANDOM_STATE = 42


def _build_feature_vector(inv: Dict[str, Any], supplier_avg: Optional[float] = None) -> Optional[List[float]]:
    """
    Returns [total_amount, taxable_amount, gst_rate, total_gst, deviation_from_supplier_avg]
    or None if too many features are missing.
    """
    def safe_float(key):
        try:
            return float(str(inv.get(key) or "").replace(",", "") or 0)
        except (ValueError, TypeError):
            return 0.0

    total_amount = safe_float("total_amount")
    taxable_amount = safe_float("taxable_amount")
    gst_rate = safe_float("gst_rate")
    total_gst = safe_float("total_gst")

    # Deviation from supplier average (0 if unknown)
    dev = (total_amount - supplier_avg) if supplier_avg else 0.0

    if total_amount <= 0 and taxable_amount <= 0:
        return None

    return [total_amount, taxable_amount, gst_rate, total_gst, dev]


def _build_training_matrix(
    historical: List[Dict[str, Any]],
    supplier_avg: Optional[float],
) -> Optional[np.ndarray]:
    rows = []
    for h in historical:
        fv = _build_feature_vector(h, supplier_avg)
        if fv:
            rows.append(fv)
    if len(rows) < MIN_TRAINING_SAMPLES:
        return None
    return np.array(rows, dtype=float)


def run(
    invoice: Dict[str, Any],
    historical_invoices: List[Dict[str, Any]],   # all historical invoices (not current batch)
    supplier_avg: Optional[float] = None,
) -> Dict[str, Any]:
    """
    CONTAMINATION controls the fraction of training data treated as outliers.
    Anomaly scores < 0 indicate more unusual instances.
    This score does NOT represent a fraud probability.
    """
    evidence: Dict[str, Any] = {
        "contamination": CONTAMINATION,
        "min_training_samples": MIN_TRAINING_SAMPLES,
    }

    target_fv = _build_feature_vector(invoice, supplier_avg)
    if target_fv is None:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "Invoice lacks sufficient numerical features for Isolation Forest.",
            "evidence": evidence,
        }

    X_train = _build_training_matrix(historical_invoices, supplier_avg)
    if X_train is None:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": (
                f"Only {len(historical_invoices)} historical invoices with usable features available "
                f"(minimum {MIN_TRAINING_SAMPLES} required to fit Isolation Forest reliably)."
            ),
            "evidence": evidence,
        }

    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_train)
        target_scaled = scaler.transform([target_fv])

        model = IsolationForest(
            contamination=CONTAMINATION,
            random_state=RANDOM_STATE,
            n_estimators=100,
        )
        model.fit(X_scaled)

        prediction = model.predict(target_scaled)[0]   # 1=normal, -1=anomaly
        score = float(model.score_samples(target_scaled)[0])

        evidence["training_samples"] = len(X_train)
        evidence["anomaly_prediction"] = int(prediction)
        evidence["anomaly_score"] = round(score, 6)
        evidence["features_used"] = ["total_amount", "taxable_amount", "gst_rate", "total_gst", "supplier_deviation"]
        evidence["note"] = (
            "Anomaly score indicates statistical unusualness relative to historical data. "
            "A negative score or prediction of -1 does not confirm fraud."
        )

        if prediction == -1:
            return {
                "status": "Flagged",
                "severity": "Low",
                "reason": (
                    f"Isolation Forest classifies this invoice as anomalous "
                    f"(score: {score:.4f}). The model was trained on {len(X_train)} historical invoices. "
                    f"This indicates the invoice is statistically unusual, not that fraud is confirmed."
                ),
                "evidence": evidence,
            }
        return {
            "status": "Pass",
            "severity": "None",
            "reason": (
                f"Isolation Forest classifies this invoice as normal "
                f"(score: {score:.4f}, trained on {len(X_train)} samples)."
            ),
            "evidence": evidence,
        }

    except Exception as e:
        return {
            "status": "Error",
            "severity": "None",
            "reason": f"Isolation Forest model failed: {str(e)}",
            "evidence": evidence,
        }
