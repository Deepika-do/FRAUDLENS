"""
Batch processing engine.
Orchestrates parsing → normalization → detection → classification → persistence.
"""
from __future__ import annotations

import json
import traceback
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.database import Batch, Invoice, MonthlySummary, TechniqueFinding
from app.parsers.invoice_parser import normalize_invoice_row
from app.detection import (
    gst_validation,
    duplicate_detection,
    zscore_analysis,
    supplier_behavior,
    transaction_frequency,
    isolation_forest,
    risk_classifier,
)

TECHNIQUE_ORDER = [
    ("gst_validation", gst_validation),
    ("duplicate_detection", None),      # handled separately
    ("zscore_analysis", zscore_analysis),
    ("supplier_behavior", supplier_behavior),
    ("transaction_frequency", None),    # handled separately
    ("isolation_forest", isolation_forest),
]


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "") or 0) or None
    except (ValueError, TypeError):
        return None



def _invoice_month(inv_dict: Dict[str, Any]) -> Optional[str]:
    date = inv_dict.get("invoice_date")

    if not date:
        return None

    date_str = str(date).strip()

    if len(date_str) >= 7:
        month = date_str[:7]

        if (
            len(month) == 7
            and month[:4].isdigit()
            and month[4] == "-"
            and month[5:7].isdigit()
            and 1 <= int(month[5:7]) <= 12
        ):
            return month

    return None



def _build_inv_dict_from_orm(inv: Invoice) -> Dict[str, Any]:
    return {
        "id": inv.id,
        "batch_id": inv.batch_id,
        "invoice_number": inv.invoice_number,
        "invoice_date": inv.invoice_date,
        "invoice_month": inv.invoice_month,
        "supplier_name": inv.supplier_name,
        "supplier_gstin": inv.supplier_gstin,
        "recipient_name": inv.recipient_name,
        "recipient_gstin": inv.recipient_gstin,
        "taxable_amount": inv.taxable_amount,
        "gst_rate": inv.gst_rate,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "igst": inv.igst,
        "total_gst": inv.total_gst,
        "total_amount": inv.total_amount,
        "place_of_supply": inv.place_of_supply,
        "source_filename": inv.source_filename,
    }


def process_batch(
    db: Session,
    batch: Batch,
    raw_invoice_rows: List[Dict[str, Any]],
    errors: List[str],
) -> None:
    """
    Main processing function:
    1. Normalizes raw rows
    2. Fetches historical records
    3. Runs all six detection techniques
    4. Classifies each invoice
    5. Persists results
    6. Updates monthly summaries
    """

    # ── Normalize rows ───────────────────────────────────────────────────────
    normalized: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_invoice_rows):
        try:
            norm = normalize_invoice_row(raw)
            norm["_source_raw"] = raw
            normalized.append(norm)
        except Exception as e:
            errors.append(f"Row {idx + 1}: normalization error — {e}")

    if not normalized:
        batch.status = "failed"
        batch.error_message = "No invoices could be parsed from the uploaded file(s)."
        db.commit()
        return

    # ── Fetch historical data (from previous batches only) ───────────────────
    historical_orm = (
        db.query(Invoice)
        .filter(Invoice.batch_id != batch.id)
        .all()
    )
    historical: List[Dict[str, Any]] = [_build_inv_dict_from_orm(h) for h in historical_orm]

    # Index historical by supplier GSTIN
    hist_by_supplier: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for h in historical:
        gs = h.get("supplier_gstin")
        if gs:
            hist_by_supplier[gs].append(h)

    # Global historical amounts for Z-score fallback
    global_hist_amounts = [
        _safe_float(h.get("total_amount"))
        for h in historical
        if _safe_float(h.get("total_amount"))
    ]

    # ── Save invoice stubs (for within-batch reference) ──────────────────────
    saved_invoices: List[Invoice] = []
    for norm in normalized:
        month = _invoice_month(norm)
        inv_orm = Invoice(
            batch_id=batch.id,
            invoice_number=norm.get("invoice_number"),
            invoice_date=norm.get("invoice_date"),
            invoice_month=month,
            supplier_name=norm.get("supplier_name"),
            supplier_gstin=norm.get("supplier_gstin"),
            recipient_name=norm.get("recipient_name"),
            recipient_gstin=norm.get("recipient_gstin"),
            taxable_amount=norm.get("taxable_amount"),
            gst_rate=norm.get("gst_rate"),
            cgst=norm.get("cgst"),
            sgst=norm.get("sgst"),
            igst=norm.get("igst"),
            total_gst=norm.get("total_gst"),
            total_amount=norm.get("total_amount"),
            total_amount_float=_safe_float(norm.get("total_amount")),
            taxable_amount_float=_safe_float(norm.get("taxable_amount")),
            gst_rate_float=_safe_float(norm.get("gst_rate")),
            place_of_supply=norm.get("place_of_supply"),
            source_filename=norm.get("source_filename"),
            raw_data=json.dumps(norm.get("_source_raw", {})),
        )
        db.add(inv_orm)
        saved_invoices.append(inv_orm)

    db.flush()  # get IDs without full commit

    # ── Build within-batch list for duplicate detection ──────────────────────
    batch_inv_dicts = [_build_inv_dict_from_orm(i) for i in saved_invoices]

    # ── Group current batch by supplier/month for frequency analysis ─────────
    batch_by_supplier: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for inv_d in batch_inv_dicts:
        gs = inv_d.get("supplier_gstin")
        if gs:
            batch_by_supplier[gs].append(inv_d)

    # Determine current month from batch data
    months_in_batch = [d.get("invoice_month") for d in batch_inv_dicts if d.get("invoice_month")]
    current_month = max(months_in_batch) if months_in_batch else datetime.utcnow().strftime("%Y-%m")

    # Update batch period info
    if months_in_batch:
        batch.invoice_period_start = min(months_in_batch) + "-01"
        batch.invoice_period_end = max(months_in_batch) + "-28"

    # ── Supplier average (for Isolation Forest deviation feature) ────────────
    supplier_avg_map: Dict[str, Optional[float]] = {}
    for gs, hist_list in hist_by_supplier.items():
        amounts = [_safe_float(h.get("total_amount")) for h in hist_list]
        amounts = [a for a in amounts if a]
        supplier_avg_map[gs] = (sum(amounts) / len(amounts)) if amounts else None

    # ── Run detection per invoice ─────────────────────────────────────────────
    flagged_count = 0

    for idx, (inv_orm, inv_dict) in enumerate(zip(saved_invoices, batch_inv_dicts)):
        technique_results: List[Dict[str, Any]] = []

        # Other invoices in batch (exclude self)
        other_batch = [d for i, d in enumerate(batch_inv_dicts) if i != idx]

        gs = inv_dict.get("supplier_gstin")
        supplier_hist = hist_by_supplier.get(gs, []) if gs else []
        supplier_avg = supplier_avg_map.get(gs) if gs else None
        supplier_hist_amounts = [
            _safe_float(h.get("total_amount")) for h in supplier_hist
            if _safe_float(h.get("total_amount"))
        ]

        # 1. GST Validation
        try:
            r = gst_validation.run(inv_dict)
        except Exception as e:
            r = {"status": "Error", "severity": "None", "reason": str(e), "evidence": {}}
        technique_results.append({"technique": "gst_validation", **r})

        # 2. Duplicate Detection
        try:
            r = duplicate_detection.run_batch(inv_dict, other_batch, historical)
        except Exception as e:
            r = {"status": "Error", "severity": "None", "reason": str(e), "evidence": {}}
        technique_results.append({"technique": "duplicate_detection", **r})

        # 3. Z-Score Analysis
        try:
            if supplier_hist_amounts and len(supplier_hist_amounts) >= 5:
                r = zscore_analysis.run(inv_dict, supplier_hist_amounts, scope="supplier")
            else:
                r = zscore_analysis.run(inv_dict, global_hist_amounts, scope="global")
        except Exception as e:
            r = {"status": "Error", "severity": "None", "reason": str(e), "evidence": {}}
        technique_results.append({"technique": "zscore_analysis", **r})

        # 4. Supplier Behavior
        try:
            r = supplier_behavior.run(inv_dict, supplier_hist)
        except Exception as e:
            r = {"status": "Error", "severity": "None", "reason": str(e), "evidence": {}}
        technique_results.append({"technique": "supplier_behavior", **r})

        # 5. Transaction Frequency
        try:
            supplier_batch_invoices = batch_by_supplier.get(gs, []) if gs else []
            r = transaction_frequency.run(
                supplier_batch_invoices, supplier_hist, current_month
            )
        except Exception as e:
            r = {"status": "Error", "severity": "None", "reason": str(e), "evidence": {}}
        technique_results.append({"technique": "transaction_frequency", **r})

        # 6. Isolation Forest
        try:
            r = isolation_forest.run(inv_dict, historical, supplier_avg)
        except Exception as e:
            r = {"status": "Error", "severity": "None", "reason": str(e), "evidence": {}}
        technique_results.append({"technique": "isolation_forest", **r})

        # ── Classify ──────────────────────────────────────────────────────────
        classification, risk_level, summary = risk_classifier.classify_invoice(technique_results)
        flagged_count_this = sum(
            1 for t in technique_results if t.get("status") == "Flagged"
        )

        inv_orm.classification = classification
        inv_orm.risk_level = risk_level
        inv_orm.assessment_summary = summary
        inv_orm.flagged_techniques_count = flagged_count_this

        if classification == "Suspicious":
            flagged_count += 1

        # ── Persist findings ──────────────────────────────────────────────────
        for tr in technique_results:
            finding = TechniqueFinding(
                invoice_id=inv_orm.id,
                technique=tr["technique"],
                status=tr["status"],
                severity=tr.get("severity"),
                reason=tr.get("reason"),
                evidence=json.dumps(tr.get("evidence", {})),
            )
            db.add(finding)

    # ── Update batch summary ──────────────────────────────────────────────────
    batch.total_invoices = len(saved_invoices)
    batch.flagged_invoices = flagged_count
    batch.status = "completed"

    # Mark this batch as latest (clear previous latest flag)
    db.query(Batch).filter(Batch.is_latest == True, Batch.id != batch.id).update(
        {"is_latest": False}
    )
    batch.is_latest = True

    # ── Update monthly summaries ──────────────────────────────────────────────
    _update_monthly_summaries(db, saved_invoices)

    db.commit()


def _update_monthly_summaries(db: Session, invoices: List[Invoice]) -> None:
    """Recompute monthly summaries from scratch for affected months."""
    affected_months = {inv.invoice_month for inv in invoices if inv.invoice_month}

    for month in affected_months:
        # Count all (historical + current batch) for that month
        month_invoices = (
            db.query(Invoice)
            .filter(Invoice.invoice_month == month)
            .all()
        )
        total = len(month_invoices)
        flagged = sum(1 for i in month_invoices if i.classification == "Suspicious")

        existing = db.query(MonthlySummary).filter(MonthlySummary.month == month).first()
        if existing:
            existing.total_invoices = total
            existing.flagged_invoices = flagged
            existing.last_updated = datetime.utcnow()
        else:
            db.add(MonthlySummary(
                month=month,
                total_invoices=total,
                flagged_invoices=flagged,
            ))
