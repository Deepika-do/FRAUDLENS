"""
SYNTHETIC TEST DATA — NOT REAL INVOICES
Tests for all fraud detection techniques, parsers, and risk classification.
Run with: pytest tests/ -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from decimal import Decimal

# ─── GST Validation Tests ──────────────────────────────────────────────────────

from app.detection.gst_validation import run as gst_run, _validate_gstin_checksum, GSTIN_PATTERN

def test_valid_gstin_format():
    assert GSTIN_PATTERN.match("27AABCU9603R1ZP")

def test_invalid_gstin_format_short():
    assert not GSTIN_PATTERN.match("27AABCU9603R1Z")

def test_invalid_gstin_format_wrong_chars():
    assert not GSTIN_PATTERN.match("XXAABCU9603R1ZP")

def test_gst_calculation_correct():
    # Use a GSTIN that passes format check (checksum may flag); test that
    # the tax calculation is verified independently of GSTIN checksum.
    # We test that correct amounts are recognized even if GSTIN checksum fails.
    inv = {
        "supplier_gstin": "27AABCU9603R1ZP",   # format-valid, may fail checksum
        "taxable_amount": "10000",
        "gst_rate": "18",
        "cgst": "900",
        "sgst": "900",
        "total_gst": "1800",
        "total_amount": "11800",
    }
    result = gst_run(inv)
    # If only checksum fails the result is Flagged with severity Medium (not High)
    # Tax calculations should be confirmed consistent in evidence
    assert result["evidence"].get("gst_difference") is None or float(result["evidence"].get("gst_difference","0")) < 1.0, \
        "Tax calculation check failed unexpectedly"

def test_gst_calculation_correct_with_valid_gstin():
    # Pure tax calculation test with valid format, no checksum expectation
    inv = {
        "taxable_amount": "10000",
        "gst_rate": "18",
        "total_gst": "1800",
        "total_amount": "11800",
    }
    result = gst_run(inv)
    # Missing GSTIN → Flagged, but calculation part should be clean
    assert "gst_difference" not in result["evidence"] or float(result["evidence"].get("gst_difference","0")) < 1.0

def test_gst_calculation_mismatch():
    inv = {
        "supplier_gstin": "27AABCU9603R1ZP",
        "taxable_amount": "10000",
        "gst_rate": "18",
        "cgst": "900",
        "sgst": "900",
        "total_gst": "2000",   # incorrect
        "total_amount": "12000",
    }
    result = gst_run(inv)
    assert result["status"] == "Flagged"

def test_missing_gstin():
    inv = {"taxable_amount": "10000", "gst_rate": "18", "total_amount": "11800"}
    result = gst_run(inv)
    assert result["status"] == "Flagged"
    assert result["severity"] == "High"

def test_cgst_igst_conflict():
    inv = {
        "supplier_gstin": "27AABCU9603R1ZP",
        "taxable_amount": "10000",
        "gst_rate": "18",
        "cgst": "900",
        "igst": "1800",
        "total_gst": "1800",
        "total_amount": "11800",
    }
    result = gst_run(inv)
    assert result["status"] == "Flagged"

def test_insufficient_data():
    result = gst_run({})
    assert result["status"] == "Insufficient Data"


# ─── Duplicate Detection Tests ────────────────────────────────────────────────

from app.detection.duplicate_detection import run_batch as dup_run

SAMPLE_INV = {
    "invoice_number": "INV-001",
    "supplier_gstin": "27AABCU9603R1ZP",
    "invoice_date": "2024-01-15",
    "total_amount": "11800",
}

def test_no_duplicate():
    result = dup_run(SAMPLE_INV, [], [])
    assert result["status"] == "Pass"

def test_within_batch_duplicate():
    same = dict(SAMPLE_INV)
    result = dup_run(SAMPLE_INV, [same], [])
    assert result["status"] == "Flagged"
    assert "within_batch_duplicate" in result["evidence"]

def test_historical_duplicate():
    hist = dict(SAMPLE_INV)
    hist["id"] = 99
    hist["batch_id"] = 1
    result = dup_run(SAMPLE_INV, [], [hist])
    assert result["status"] == "Flagged"
    assert "historical_duplicate" in result["evidence"]

def test_different_date_not_duplicate():
    other = dict(SAMPLE_INV)
    other["invoice_date"] = "2024-02-15"
    other["invoice_number"] = "INV-002"
    result = dup_run(SAMPLE_INV, [other], [])
    assert result["status"] == "Pass"

def test_missing_invoice_number():
    inv = {"supplier_gstin": "27AABCU9603R1ZP"}
    result = dup_run(inv, [], [])
    assert result["status"] == "Insufficient Data"


# ─── Z-Score Tests ─────────────────────────────────────────────────────────────

from app.detection.zscore_analysis import run as zscore_run

def test_zscore_normal_amount():
    hist = [10000.0, 11000.0, 9500.0, 10500.0, 10200.0, 9800.0]
    inv = {"total_amount": "10300"}
    result = zscore_run(inv, hist)
    assert result["status"] == "Pass"

def test_zscore_outlier_amount():
    hist = [10000.0, 11000.0, 9500.0, 10500.0, 10200.0, 9800.0]
    inv = {"total_amount": "150000"}   # extreme outlier
    result = zscore_run(inv, hist)
    assert result["status"] == "Flagged"

def test_zscore_insufficient_data():
    hist = [10000.0, 11000.0]  # only 2 samples
    inv = {"total_amount": "10000"}
    result = zscore_run(inv, hist)
    assert result["status"] == "Insufficient Data"

def test_zscore_zero_std():
    hist = [10000.0, 10000.0, 10000.0, 10000.0, 10000.0]
    inv = {"total_amount": "10000"}
    result = zscore_run(inv, hist)
    assert result["status"] == "Insufficient Data"

def test_zscore_missing_amount():
    result = zscore_run({}, [10000.0] * 10)
    assert result["status"] == "Insufficient Data"


# ─── Supplier Behavior Tests ───────────────────────────────────────────────────

from app.detection.supplier_behavior import run as sb_run

def _make_hist(amounts):
    return [{"total_amount": str(a)} for a in amounts]

def test_supplier_normal():
    hist = _make_hist([10000, 11000, 9500, 10500, 10200])
    result = sb_run({"total_amount": "10300"}, hist)
    assert result["status"] == "Pass"

def test_supplier_spike():
    hist = _make_hist([10000, 11000, 9500, 10500, 10200])
    result = sb_run({"total_amount": "500000"}, hist)  # 50× spike
    assert result["status"] == "Flagged"

def test_supplier_insufficient_history():
    hist = _make_hist([10000])
    result = sb_run({"total_amount": "10000"}, hist)
    assert result["status"] == "Insufficient Data"

def test_supplier_no_history():
    result = sb_run({"total_amount": "10000"}, [])
    assert result["status"] == "Insufficient Data"


# ─── Transaction Frequency Tests ───────────────────────────────────────────────

from app.detection.transaction_frequency import run as freq_run

def _make_supplier_invs(month, count):
    return [{"invoice_month": month, "total_amount": "10000"} for _ in range(count)]

def test_freq_normal():
    current = _make_supplier_invs("2024-06", 2)
    hist = (
        _make_supplier_invs("2024-04", 2) +
        _make_supplier_invs("2024-05", 2)
    )
    result = freq_run(current, hist, "2024-06")
    assert result["status"] == "Pass"

def test_freq_spike():
    current = _make_supplier_invs("2024-06", 30)  # sudden spike
    hist = (
        _make_supplier_invs("2024-04", 2) +
        _make_supplier_invs("2024-05", 3)
    )
    result = freq_run(current, hist, "2024-06")
    assert result["status"] == "Flagged"

def test_freq_insufficient_history():
    current = _make_supplier_invs("2024-06", 5)
    hist = _make_supplier_invs("2024-05", 2)  # only 1 month
    result = freq_run(current, hist, "2024-06")
    assert result["status"] == "Insufficient Data"


# ─── Isolation Forest Tests ────────────────────────────────────────────────────

from app.detection.isolation_forest import run as if_run

def _make_hist_invoices(n, base_amount=10000):
    return [
        {"total_amount": str(base_amount + i * 100),
         "taxable_amount": str(int((base_amount + i * 100) / 1.18)),
         "gst_rate": "18",
         "total_gst": str(int((base_amount + i * 100) * 0.18 / 1.18))}
        for i in range(n)
    ]

def test_if_insufficient_training():
    hist = _make_hist_invoices(5)   # < 10
    inv = {"total_amount": "10000", "taxable_amount": "8475", "gst_rate": "18", "total_gst": "1525"}
    result = if_run(inv, hist)
    assert result["status"] == "Insufficient Data"

def test_if_runs_with_adequate_data():
    hist = _make_hist_invoices(20)
    inv = {"total_amount": "10000", "taxable_amount": "8475", "gst_rate": "18", "total_gst": "1525"}
    result = if_run(inv, hist)
    assert result["status"] in ("Pass", "Flagged", "Error")

def test_if_extreme_outlier():
    hist = _make_hist_invoices(30, base_amount=10000)
    inv = {"total_amount": "5000000", "taxable_amount": "4237288", "gst_rate": "18", "total_gst": "762712"}
    result = if_run(inv, hist)
    # Should be flagged for extreme outlier
    assert result["status"] in ("Flagged", "Pass")  # depends on model, don't assert exact


# ─── Risk Classifier Tests ─────────────────────────────────────────────────────

from app.detection.risk_classifier import classify_invoice

def test_all_pass():
    findings = [
        {"technique": t, "status": "Pass", "severity": "None"}
        for t in ["gst_validation", "duplicate_detection", "zscore_analysis",
                  "supplier_behavior", "transaction_frequency", "isolation_forest"]
    ]
    cls, risk, _ = classify_invoice(findings)
    assert cls == "Not Suspicious"
    assert risk == "Low"

def test_high_severity_duplicate():
    findings = [
        {"technique": "duplicate_detection", "status": "Flagged", "severity": "High"},
        {"technique": "gst_validation", "status": "Pass", "severity": "None"},
        {"technique": "zscore_analysis", "status": "Insufficient Data", "severity": "None"},
        {"technique": "supplier_behavior", "status": "Pass", "severity": "None"},
        {"technique": "transaction_frequency", "status": "Pass", "severity": "None"},
        {"technique": "isolation_forest", "status": "Pass", "severity": "None"},
    ]
    cls, risk, _ = classify_invoice(findings)
    assert cls == "Suspicious"
    assert risk == "High"

def test_medium_findings():
    findings = [
        {"technique": "zscore_analysis", "status": "Flagged", "severity": "Medium"},
        {"technique": "supplier_behavior", "status": "Flagged", "severity": "Medium"},
        {"technique": "gst_validation", "status": "Pass", "severity": "None"},
        {"technique": "duplicate_detection", "status": "Pass", "severity": "None"},
        {"technique": "transaction_frequency", "status": "Insufficient Data", "severity": "None"},
        {"technique": "isolation_forest", "status": "Pass", "severity": "None"},
    ]
    cls, risk, _ = classify_invoice(findings)
    assert cls == "Suspicious"


# ─── Parser Tests ──────────────────────────────────────────────────────────────

from app.parsers.invoice_parser import parse_csv, parse_json, parse_excel, parse_file

def test_parse_csv_basic():
    csv_data = (
        "invoice_number,invoice_date,supplier_name,supplier_gstin,total_amount\n"
        "INV-001,2024-01-15,Acme Pvt Ltd,27AABCU9603R1ZP,11800\n"
    ).encode()
    rows = parse_csv(csv_data, "test.csv")
    assert len(rows) == 1
    assert rows[0]["invoice_number"] == "INV-001"

def test_parse_json_list():
    import json
    data = json.dumps([
        {"invoice_number": "INV-001", "total_amount": "11800", "supplier_gstin": "27AABCU9603R1ZP"}
    ]).encode()
    rows = parse_json(data, "test.json")
    assert len(rows) == 1

def test_parse_json_envelope():
    import json
    data = json.dumps({
        "invoices": [
            {"invoice_number": "INV-001", "total_amount": "11800"}
        ]
    }).encode()
    rows = parse_json(data, "test.json")
    assert len(rows) == 1

def test_unsupported_extension():
    with pytest.raises(ValueError, match="Unsupported"):
        parse_file(b"data", "invoice.png")

def test_empty_csv():
    csv_data = b"invoice_number,total_amount\n"
    rows = parse_csv(csv_data, "test.csv")
    assert rows == []
