"""
Technique 1: GST Validation
- GSTIN format + checksum validation
- Tax calculation consistency check
- CGST/SGST vs IGST consistency
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)

CHECKSUM_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

VALID_GST_RATES = {0.0, 0.1, 0.25, 1.0, 1.5, 3.0, 5.0, 6.0, 7.5, 9.0, 12.0, 14.0, 18.0, 28.0}
RATE_TOLERANCE = 0.5  # allow half-percent rounding


def _validate_gstin_checksum(gstin: str) -> bool:
    """Luhn-like GSTIN checksum for 15-character GSTIN."""
    if len(gstin) != 15:
        return False
    total = 0
    for i, ch in enumerate(gstin[:-1]):
        if ch not in CHECKSUM_CHARS:
            return False
        val = CHECKSUM_CHARS.index(ch)
        if i % 2 == 1:
            val *= 2
        total += val // len(CHECKSUM_CHARS) + val % len(CHECKSUM_CHARS)
    expected = (len(CHECKSUM_CHARS) - total % len(CHECKSUM_CHARS)) % len(CHECKSUM_CHARS)
    return CHECKSUM_CHARS[expected] == gstin[-1]


def _to_dec(val: Optional[str]) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val).replace(",", "").strip())
    except InvalidOperation:
        return None


def run(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      status: Pass | Flagged | Insufficient Data | Error
      severity: High | Medium | Low | None
      reason: str
      evidence: dict
    """
    issues = []
    evidence: Dict[str, Any] = {}
    severity = "None"

    # ── 1. GSTIN format validation ──────────────────────────────────────────
    supplier_gstin = invoice.get("supplier_gstin")
    if supplier_gstin:
        if not GSTIN_PATTERN.match(supplier_gstin):
            issues.append(f"Supplier GSTIN '{supplier_gstin}' does not match the required 15-character format.")
            evidence["supplier_gstin_format"] = "invalid"
            severity = "Medium"
        else:
            if not _validate_gstin_checksum(supplier_gstin):
                issues.append(f"Supplier GSTIN '{supplier_gstin}' fails checksum validation.")
                evidence["supplier_gstin_checksum"] = "fail"
                severity = "Medium"
            else:
                evidence["supplier_gstin_format"] = "valid"
                evidence["supplier_gstin_checksum"] = "pass"
    else:
        issues.append("Supplier GSTIN is missing.")
        evidence["supplier_gstin_format"] = "missing"
        severity = "High"

    recipient_gstin = invoice.get("recipient_gstin")
    if recipient_gstin and not GSTIN_PATTERN.match(recipient_gstin):
        issues.append(f"Recipient GSTIN '{recipient_gstin}' does not match required format.")
        evidence["recipient_gstin_format"] = "invalid"
        if severity == "None":
            severity = "Low"

    # ── 2. Tax calculation consistency ─────────────────────────────────────
    taxable = _to_dec(invoice.get("taxable_amount"))
    rate = _to_dec(invoice.get("gst_rate"))
    cgst = _to_dec(invoice.get("cgst"))
    sgst = _to_dec(invoice.get("sgst"))
    igst = _to_dec(invoice.get("igst"))
    total_gst = _to_dec(invoice.get("total_gst"))
    total_amount = _to_dec(invoice.get("total_amount"))

    if taxable is not None and rate is not None:
        calculated_gst = (taxable * rate / Decimal("100")).quantize(Decimal("0.01"))
        evidence["taxable_amount"] = str(taxable)
        evidence["gst_rate"] = str(rate)
        evidence["calculated_gst"] = str(calculated_gst)

        # Validate rate is a known GST slab
        rate_float = float(rate)
        nearest_valid = min(VALID_GST_RATES, key=lambda r: abs(r - rate_float))
        if abs(nearest_valid - rate_float) > RATE_TOLERANCE:
            issues.append(
                f"GST rate {rate_float}% is not a recognized GST slab "
                f"(nearest valid: {nearest_valid}%)."
            )
            if severity in ("None", "Low"):
                severity = "Medium"

        # Check recorded GST vs calculated
        recorded_gst = total_gst or (
            (cgst + sgst) if (cgst is not None and sgst is not None) else
            igst
        )
        if recorded_gst is not None:
            diff = abs(recorded_gst - calculated_gst)
            evidence["recorded_gst"] = str(recorded_gst)
            evidence["gst_difference"] = str(diff)
            if diff > Decimal("1.00"):  # > ₹1 tolerance for rounding
                issues.append(
                    f"Recorded GST (₹{recorded_gst}) differs from calculated GST "
                    f"(₹{calculated_gst}) by ₹{diff}."
                )
                severity = "High" if diff > Decimal("100") else "Medium"

        # Total amount check
        if total_amount is not None and recorded_gst is not None:
            expected_total = taxable + recorded_gst
            total_diff = abs(total_amount - expected_total)
            evidence["expected_total"] = str(expected_total)
            evidence["actual_total"] = str(total_amount)
            evidence["total_difference"] = str(total_diff)
            if total_diff > Decimal("2.00"):
                issues.append(
                    f"Total invoice amount (₹{total_amount}) does not match "
                    f"taxable + GST (₹{expected_total}), difference ₹{total_diff}."
                )
                if severity not in ("High",):
                    severity = "Medium"

    elif taxable is None and total_amount is None:
        return {
            "status": "Insufficient Data",
            "severity": "None",
            "reason": "Neither taxable amount nor total amount is available for GST validation.",
            "evidence": evidence,
        }

    # ── 3. CGST+SGST vs IGST logic ─────────────────────────────────────────
    if cgst is not None and igst is not None and igst > Decimal("0"):
        issues.append(
            "Invoice contains both CGST/SGST and IGST. "
            "IGST applies to inter-state transactions; CGST+SGST applies to intra-state."
        )
        if severity == "None":
            severity = "Medium"
        evidence["cgst_igst_conflict"] = True

    if not issues:
        return {
            "status": "Pass",
            "severity": "None",
            "reason": "GSTIN format, checksum, and tax calculations are consistent.",
            "evidence": evidence,
        }
    return {
        "status": "Flagged",
        "severity": severity,
        "reason": " | ".join(issues),
        "evidence": evidence,
    }
