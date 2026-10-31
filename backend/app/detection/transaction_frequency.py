"""
Technique 5: Transaction Frequency Analysis
Detects unusual increases in transaction volume for a supplier in a given time window.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

MIN_HISTORY_MONTHS = 2          # need at least 2 comparison months
FREQUENCY_SPIKE_MULTIPLIER = 3  # current count > 3× historical average → flag


def _group_by_month(invoices: List[Dict[str, Any]]) -> Dict[str, int]:
    monthly: Dict[str, int] = defaultdict(int)
    for inv in invoices:
        month = (inv.get("invoice_month") or str(inv.get("invoice_date") or "")[:7])
        if month and len(month) == 7:
            monthly[month] += 1
    return dict(monthly)


def run(
    current_batch_supplier_invoices: List[Dict[str, Any]],  # current batch invoices for this supplier
    historical_supplier_invoices: List[Dict[str, Any]],     # previous batches' invoices for this supplier
    current_month: str,  # YYYY-MM
) -> Dict[str, Any]:
    """
    Compares transaction count in current_month against historical monthly averages.
    """
    evidence: Dict[str, Any] = {"current_month": current_month}

    current_count = len(current_batch_supplier_invoices)
    evidence["current_month_count"] = current_count

    hist_monthly = _group_by_month(historical_supplier_invoices)
    # Exclude current month from history
    hist_monthly.pop(current_month, None)
    evidence["history_months"] = len(hist_monthly)

    if len(hist_monthly) < MIN_HISTORY_MONTHS:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": (
                f"Only {len(hist_monthly)} historical month(s) of data available for this supplier "
                f"(minimum {MIN_HISTORY_MONTHS} required to assess frequency changes)."
            ),
            "evidence": evidence,
        }

    counts = list(hist_monthly.values())
    hist_avg = sum(counts) / len(counts)
    hist_max = max(counts)
    evidence["historical_monthly_avg"] = round(hist_avg, 2)
    evidence["historical_monthly_max"] = hist_max
    evidence["historical_monthly_counts"] = hist_monthly

    if hist_avg < 1:
        hist_avg = 1.0  # avoid division by zero for very sparse history

    ratio = current_count / hist_avg
    evidence["frequency_ratio"] = round(ratio, 2)
    evidence["threshold_multiplier"] = FREQUENCY_SPIKE_MULTIPLIER

    if ratio >= FREQUENCY_SPIKE_MULTIPLIER:
        return {
            "status": "Flagged",
            "severity": "Medium",
            "reason": (
                f"Supplier submitted {current_count} invoice(s) this month ({current_month}), "
                f"which is {ratio:.1f}× the historical monthly average of {hist_avg:.1f}. "
                f"This unusual spike warrants review."
            ),
            "evidence": evidence,
        }

    return {
        "status": "Pass",
        "severity": "None",
        "reason": (
            f"Transaction frequency ({current_count} this month) is within normal range "
            f"(historical average: {hist_avg:.1f}/month)."
        ),
        "evidence": evidence,
    }
