"""
Technique 3: Z-Score Analysis
Detects invoice amounts that are statistically unusual relative to a reference distribution.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

Z_SCORE_THRESHOLD = 3.0          # configurable
MIN_SAMPLE_SIZE = 5               # minimum historical records for reliable Z-score


def _mean(values: List[float]) -> float:
    return sum(values) / len(values)


def _stdev(values: List[float], mu: float) -> float:
    variance = sum((v - mu) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def run(
    invoice: Dict[str, Any],
    reference_amounts: List[float],   # historical amounts for comparison
    scope: str = "global",            # "supplier" or "global"
) -> Dict[str, Any]:
    """
    Args:
        invoice: the invoice being evaluated
        reference_amounts: list of historical total amounts (from same supplier or broader)
        scope: description of reference pool used
    """
    evidence: Dict[str, Any] = {"reference_scope": scope}

    try:
        amount = float(str(invoice.get("total_amount") or "").replace(",", "") or 0)
    except (ValueError, TypeError):
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "Invoice total amount is not a valid number; Z-score cannot be calculated.",
            "evidence": evidence,
        }

    if amount <= 0:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "Invoice amount is zero or negative; Z-score is not meaningful.",
            "evidence": evidence,
        }

    evidence["observed_amount"] = amount

    if len(reference_amounts) < MIN_SAMPLE_SIZE:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": (
                f"Only {len(reference_amounts)} historical reference record(s) available "
                f"(minimum {MIN_SAMPLE_SIZE} required for a reliable Z-score)."
            ),
            "evidence": evidence,
        }

    mu = _mean(reference_amounts)
    sigma = _stdev(reference_amounts, mu)
    evidence["reference_mean"] = round(mu, 2)
    evidence["reference_std"] = round(sigma, 2)
    evidence["sample_size"] = len(reference_amounts)
    evidence["z_score_threshold"] = Z_SCORE_THRESHOLD

    if sigma < 1e-6:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "All historical reference amounts are identical; Z-score is undefined.",
            "evidence": evidence,
        }

    z = (amount - mu) / sigma
    evidence["z_score"] = round(z, 4)

    if abs(z) >= Z_SCORE_THRESHOLD:
        direction = "higher" if z > 0 else "lower"
        return {
            "status": "Flagged",
            "severity": "Medium",
            "reason": (
                f"Invoice amount ₹{amount:,.2f} is {abs(z):.2f} standard deviations {direction} "
                f"than the {scope}-level mean of ₹{mu:,.2f} (σ={sigma:,.2f}). "
                f"This is an unusual amount, not necessarily evidence of fraud."
            ),
            "evidence": evidence,
        }

    return {
        "status": "Pass",
        "severity": "None",
        "reason": (
            f"Invoice amount ₹{amount:,.2f} is within normal range "
            f"(Z-score: {z:.2f}, threshold: ±{Z_SCORE_THRESHOLD})."
        ),
        "evidence": evidence,
    }
