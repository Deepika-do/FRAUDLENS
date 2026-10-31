"""
Technique 4: Supplier Behavior Analysis
Detects deviations from an established supplier's historical transaction patterns.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

MIN_HISTORY = 3    # minimum transactions for a meaningful supplier baseline
DEVIATION_THRESHOLD = 2.5   # sigma multiplier for flagging


def _stats(values: List[float]):
    n = len(values)
    mu = sum(values) / n
    sigma = math.sqrt(sum((v - mu) ** 2 for v in values) / n) if n > 1 else 0.0
    return mu, sigma


def run(
    invoice: Dict[str, Any],
    supplier_history: List[Dict[str, Any]],   # historical invoices from same supplier
) -> Dict[str, Any]:
    """
    Analyzes whether the current invoice deviates significantly from the supplier's
    established historical behaviour.
    """
    evidence: Dict[str, Any] = {}

    try:
        current_amount = float(str(invoice.get("total_amount") or "").replace(",", "") or 0)
    except (ValueError, TypeError):
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "Invoice amount is missing or invalid; supplier behaviour analysis skipped.",
            "evidence": evidence,
        }

    evidence["current_amount"] = current_amount
    evidence["history_count"] = len(supplier_history)

    if len(supplier_history) < MIN_HISTORY:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": (
                f"Only {len(supplier_history)} historical transaction(s) for this supplier "
                f"(minimum {MIN_HISTORY} required). Cannot establish a reliable baseline."
            ),
            "evidence": evidence,
        }

    hist_amounts = []
    for h in supplier_history:
        try:
            a = float(str(h.get("total_amount") or "").replace(",", "") or 0)
            if a > 0:
                hist_amounts.append(a)
        except (ValueError, TypeError):
            pass

    if len(hist_amounts) < MIN_HISTORY:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "Insufficient numeric amount data in supplier history.",
            "evidence": evidence,
        }

    mu, sigma = _stats(hist_amounts)
    evidence["historical_mean"] = round(mu, 2)
    evidence["historical_std"] = round(sigma, 2)
    evidence["sample_size"] = len(hist_amounts)

    issues = []
    severity = "None"

    if sigma > 1e-6:
        deviation = (current_amount - mu) / sigma
        evidence["deviation_sigma"] = round(deviation, 4)
        if abs(deviation) >= DEVIATION_THRESHOLD:
            direction = "above" if deviation > 0 else "below"
            issues.append(
                f"Invoice amount ₹{current_amount:,.2f} is {abs(deviation):.2f}σ "
                f"{direction} this supplier's historical average ₹{mu:,.2f}."
            )
            severity = "Medium"

    # Check for sudden amount spike (current vs max historical)
    max_hist = max(hist_amounts)
    min_hist = min(hist_amounts)
    evidence["historical_max"] = round(max_hist, 2)
    evidence["historical_min"] = round(min_hist, 2)

    if current_amount > max_hist * 3 and current_amount > mu * 3:
        issues.append(
            f"Invoice amount ₹{current_amount:,.2f} is more than 3× the supplier's historical maximum "
            f"(₹{max_hist:,.2f})."
        )
        severity = "High"

    if not issues:
        return {
            "status": "Pass",
            "severity": "None",
            "reason": (
                f"Invoice amount ₹{current_amount:,.2f} is consistent with this supplier's "
                f"historical pattern (mean ₹{mu:,.2f}, σ={sigma:,.2f})."
            ),
            "evidence": evidence,
        }
    return {
        "status": "Flagged",
        "severity": severity,
        "reason": " | ".join(issues),
        "evidence": evidence,
    }
