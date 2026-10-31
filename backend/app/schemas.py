"""
Pydantic schemas for API request/response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ── Batch ──────────────────────────────────────────────────────────────────────

class BatchBase(BaseModel):
    batch_uuid: str
    uploaded_at: datetime
    original_filename: Optional[str]
    status: str
    total_invoices: int
    flagged_invoices: int
    invoice_period_start: Optional[str]
    invoice_period_end: Optional[str]
    error_message: Optional[str]
    is_latest: bool

class BatchOut(BatchBase):
    id: int
    model_config = {"from_attributes": True}


# ── Technique finding ──────────────────────────────────────────────────────────

class TechniqueFindingOut(BaseModel):
    id: int
    technique: str
    status: str
    severity: Optional[str]
    reason: Optional[str]
    evidence: Optional[Dict[str, Any]]
    model_config = {"from_attributes": True}


# ── Invoice ────────────────────────────────────────────────────────────────────

class InvoiceListItem(BaseModel):
    id: int
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    supplier_name: Optional[str]
    supplier_gstin: Optional[str]
    total_amount: Optional[str]
    classification: str
    risk_level: str
    flagged_techniques_count: int
    model_config = {"from_attributes": True}


class InvoiceDetail(BaseModel):
    id: int
    batch_id: int
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    invoice_month: Optional[str]
    supplier_name: Optional[str]
    supplier_gstin: Optional[str]
    recipient_name: Optional[str]
    recipient_gstin: Optional[str]
    taxable_amount: Optional[str]
    gst_rate: Optional[str]
    cgst: Optional[str]
    sgst: Optional[str]
    igst: Optional[str]
    total_gst: Optional[str]
    total_amount: Optional[str]
    place_of_supply: Optional[str]
    source_filename: Optional[str]
    classification: str
    risk_level: str
    flagged_techniques_count: int
    assessment_summary: Optional[str]
    findings: List[TechniqueFindingOut]
    model_config = {"from_attributes": True}


# ── Dashboard ──────────────────────────────────────────────────────────────────

class DashboardSummary(BaseModel):
    invoices_scanned: int
    needs_review: int
    latest_batch: Optional[BatchOut]
    monthly_chart: List[Dict[str, Any]]


# ── Fraud Results list ─────────────────────────────────────────────────────────

class InvoiceListResponse(BaseModel):
    items: List[InvoiceListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Upload response ────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    batch_uuid: str
    status: str
    message: str
    total_invoices: int
    flagged_invoices: int
    errors: List[str]
