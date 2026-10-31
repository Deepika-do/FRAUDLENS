"""
Technique 2: Duplicate Invoice Detection
- Within-batch duplicates
- Cross-batch (historical) duplicates
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _normalize_invoice_number(inv_no: Optional[str]) -> Optional[str]:
    if not inv_no:
        return None
    # Remove spaces, hyphens, slashes; uppercase
    return re.sub(r"[\s\-/\\]", "", str(inv_no)).upper()


def _normalize_gstin(gstin: Optional[str]) -> Optional[str]:
    if not gstin:
        return None
    return re.sub(r"\s+", "", str(gstin)).upper()


def _make_key(inv: Dict[str, Any]) -> Optional[tuple]:
    """Composite duplicate key: (normalized_gstin, normalized_inv_no, date, amount_rounded)."""
    gstin = _normalize_gstin(inv.get("supplier_gstin"))
    inv_no = _normalize_invoice_number(inv.get("invoice_number"))
    date = str(inv.get("invoice_date") or "").strip()
    try:
        amount = round(float(str(inv.get("total_amount") or 0).replace(",", "")), 0)
    except (ValueError, TypeError):
        amount = None

    if not inv_no or not gstin:
        return None
    return (gstin, inv_no, date)


def run_batch(
    invoice: Dict[str, Any],
    batch_invoices: List[Dict[str, Any]],  # all other invoices in current batch
    historical_invoices: List[Dict[str, Any]],  # invoices from previous batches
) -> Dict[str, Any]:
    """
    Check for duplicates within the batch and against historical records.
    `invoice` is the invoice being evaluated; it should NOT appear in batch_invoices.
    """
    evidence: Dict[str, Any] = {}
    issues = []
    severity = "None"

    key = _make_key(invoice)
    if key is None:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "Cannot check for duplicates: invoice number or supplier GSTIN is missing.",
            "evidence": evidence,
        }

    evidence["evaluated_key"] = {
        "supplier_gstin": key[0],
        "invoice_number": key[1],
        "invoice_date": key[2],
    }

    # Within-batch check
    for other in batch_invoices:
        other_key = _make_key(other)
        if other_key and other_key == key:
            issues.append(
                f"Duplicate found within the current batch: "
                f"invoice '{other.get('invoice_number')}' from supplier {other.get('supplier_gstin')}."
            )
            evidence["within_batch_duplicate"] = {
                "invoice_number": other.get("invoice_number"),
                "supplier_gstin": other.get("supplier_gstin"),
                "invoice_date": other.get("invoice_date"),
                "total_amount": other.get("total_amount"),
            }
            severity = "High"
            break

    # Historical check
    if not issues:
        for hist in historical_invoices:
            hist_key = _make_key(hist)
            if hist_key and hist_key == key:
                issues.append(
                    f"Duplicate found against historical invoice "
                    f"(batch_id={hist.get('batch_id')}, id={hist.get('id')}): "
                    f"invoice '{hist.get('invoice_number')}' from {hist.get('supplier_gstin')}."
                )
                evidence["historical_duplicate"] = {
                    "invoice_id": hist.get("id"),
                    "batch_id": hist.get("batch_id"),
                    "invoice_number": hist.get("invoice_number"),
                    "supplier_gstin": hist.get("supplier_gstin"),
                    "invoice_date": hist.get("invoice_date"),
                    "total_amount": hist.get("total_amount"),
                }
                severity = "High"
                break

    if not issues:
        return {
            "status": "Pass",
            "severity": "None",
            "reason": "No duplicate invoices found within this batch or in historical records.",
            "evidence": evidence,
        }
    return {
        "status": "Flagged",
        "severity": severity,
        "reason": " | ".join(issues),
        "evidence": evidence,
    }
