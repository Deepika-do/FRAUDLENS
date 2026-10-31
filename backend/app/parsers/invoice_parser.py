"""
Invoice file parsers — PDF, JSON, CSV, XLSX, TXT.
Each parser returns a list of raw invoice dicts using normalized field names.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

NORMALIZED_COLUMNS = {
    # invoice_number
    "invoice no": "invoice_number",
    "invoice number": "invoice_number",
    "inv no": "invoice_number",
    "inv_no": "invoice_number",
    "invoice_no": "invoice_number",
    "bill no": "invoice_number",
    "bill_no": "invoice_number",

    # invoice_date
    "invoice date": "invoice_date",
    "invoice_date": "invoice_date",
    "bill date": "invoice_date",
    "date": "invoice_date",

    # supplier
    "supplier name": "supplier_name",
    "supplier_name": "supplier_name",
    "seller name": "supplier_name",
    "vendor name": "supplier_name",

    "supplier gstin": "supplier_gstin",
    "supplier_gstin": "supplier_gstin",
    "seller gstin": "supplier_gstin",
    "gstin of supplier": "supplier_gstin",
    "gstin": "supplier_gstin",

    # recipient
    "recipient name": "recipient_name",
    "recipient_name": "recipient_name",
    "buyer name": "recipient_name",
    "customer name": "recipient_name",

    "recipient gstin": "recipient_gstin",
    "recipient_gstin": "recipient_gstin",
    "buyer gstin": "recipient_gstin",
    "gstin of recipient": "recipient_gstin",

    # amounts
    "taxable amount": "taxable_amount",
    "taxable_amount": "taxable_amount",
    "taxable value": "taxable_amount",
    "taxable_value": "taxable_amount",
    "assessable value": "taxable_amount",

    "gst rate": "gst_rate",
    "gst_rate": "gst_rate",
    "tax rate": "gst_rate",
    "rate": "gst_rate",

    "cgst": "cgst",
    "cgst amount": "cgst",
    "sgst": "sgst",
    "sgst amount": "sgst",
    "igst": "igst",
    "igst amount": "igst",

    "total gst": "total_gst",
    "total_gst": "total_gst",
    "total tax": "total_gst",
    "tax amount": "total_gst",

    "total amount": "total_amount",
    "total_amount": "total_amount",
    "invoice amount": "total_amount",
    "invoice_amount": "total_amount",
    "amount": "total_amount",
    "grand total": "total_amount",

    "place of supply": "place_of_supply",
    "place_of_supply": "place_of_supply",
}


def _normalize_headers(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map raw column names to normalized field names."""
    result: Dict[str, Any] = {}
    for k, v in raw.items():
        normalized = NORMALIZED_COLUMNS.get(str(k).strip().lower(), str(k).strip().lower())
        result[normalized] = v
    return result


def _safe_numeric(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("₹", "").replace("Rs", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ─── CSV parser ──────────────────────────────────────────────────────────────

def parse_csv(content: bytes, filename: str) -> List[Dict[str, Any]]:
    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = [_normalize_headers(row) for row in reader]
        for r in rows:
            r["source_filename"] = filename
        return rows
    except Exception as e:
        raise ValueError(f"CSV parse error: {e}")


# ─── Excel parser ─────────────────────────────────────────────────────────────

def parse_excel(content: bytes, filename: str) -> List[Dict[str, Any]]:
    try:
        df = pd.read_excel(io.BytesIO(content), dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(how="all")
        rows = []
        for _, row in df.iterrows():
            raw = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            normalized = _normalize_headers(raw)
            normalized["source_filename"] = filename
            rows.append(normalized)
        return rows
    except Exception as e:
        raise ValueError(f"Excel parse error: {e}")


# ─── JSON parser ─────────────────────────────────────────────────────────────

def parse_json(content: bytes, filename: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"JSON parse error: {e}")

    # Unwrap common envelope patterns
    if isinstance(data, dict):
        for key in ("invoices", "data", "records", "items", "invoice"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # Treat single dict as one invoice
            data = [data]

    if not isinstance(data, list):
        raise ValueError("JSON must contain a list of invoice objects or a recognized envelope.")

    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_headers(item)
        normalized["source_filename"] = filename
        rows.append(normalized)
    return rows


# ─── PDF parser ──────────────────────────────────────────────────────────────

_FIELD_PATTERNS = {
    "invoice_number": [
        r"invoice\s*(?:no\.?|number)[:\s#]*([A-Za-z0-9/\-_]+)",
        r"bill\s*(?:no\.?|number)[:\s#]*([A-Za-z0-9/\-_]+)",
        r"inv\.?\s*no[:\s]*([A-Za-z0-9/\-_]+)",
    ],
    "invoice_date": [
        r"(?:invoice|bill)\s*date[:\s]*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
        r"date[:\s]*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
        r"dated[:\s]*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})",
    ],
    "supplier_gstin": [
        r"(?:supplier|seller|from)\s*gstin[:\s]*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
        r"gstin[:\s]*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
    ],
    "recipient_gstin": [
        r"(?:recipient|buyer|to)\s*gstin[:\s]*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
    ],
    "supplier_name": [
        r"(?:from|supplier|sold by)[:\s]+([A-Za-z0-9\s&.,()'-]{3,60}?)(?:\n|gstin|gst)",
    ],
    "recipient_name": [
        r"(?:to|buyer|recipient|bill to|ship to)[:\s]+([A-Za-z0-9\s&.,()'-]{3,60}?)(?:\n|gstin|gst)",
    ],
    "taxable_amount": [
        r"taxable\s*(?:amount|value)[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
        r"assessable\s*value[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
    ],
    "gst_rate": [
        r"gst\s*(?:rate|@)[:\s]*([0-9]+(?:\.\d{1,2})?)\s*%?",
        r"tax\s*rate[:\s]*([0-9]+(?:\.\d{1,2})?)\s*%?",
        r"@\s*([0-9]+(?:\.\d{1,2})?)\s*%",
    ],
    "cgst": [
        r"cgst[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
    ],
    "sgst": [
        r"sgst[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
    ],
    "igst": [
        r"igst[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
    ],
    "total_gst": [
        r"total\s*(?:gst|tax)[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
    ],
    "total_amount": [
        r"(?:grand\s*total|total\s*amount|invoice\s*amount|total\s*value)[:\s₹]*([0-9,]+(?:\.\d{1,2})?)",
        r"total[:\s₹]+([0-9,]+(?:\.\d{1,2})?)",
    ],
    "place_of_supply": [
        r"place\s*of\s*supply[:\s]*([A-Za-z\s]+?)(?:\n|\d)",
    ],
}


def _extract_pdf_fields(text: str) -> Dict[str, Any]:
    text_lower = text.lower()
    result: Dict[str, Any] = {}
    for field, patterns in _FIELD_PATTERNS.items():
        for pattern in patterns:
            m = re.search(pattern, text_lower, re.IGNORECASE)
            if m:
                result[field] = m.group(1).strip()
                break
    return result


def parse_pdf(content: bytes, filename: str) -> List[Dict[str, Any]]:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    except Exception as e:
        raise ValueError(f"PDF extraction error: {e}")

    if not text.strip():
        raise ValueError("PDF contains no extractable text. OCR is not supported in this version.")

    fields = _extract_pdf_fields(text)
    fields["source_filename"] = filename
    return [fields]


# ─── TXT parser ──────────────────────────────────────────────────────────────

def parse_txt(content: bytes, filename: str) -> List[Dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    # Try CSV-style first
    if "," in text and "\n" in text:
        try:
            return parse_csv(content, filename)
        except Exception:
            pass
    # Fall back to regex field extraction
    fields = _extract_pdf_fields(text)
    if not fields:
        raise ValueError("TXT file does not contain recognizable invoice fields.")
    fields["source_filename"] = filename
    return [fields]


# ─── Dispatcher ──────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".pdf", ".json", ".csv", ".xlsx", ".xls", ".txt"}


def parse_file(content: bytes, filename: str) -> List[Dict[str, Any]]:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if ext == ".csv":
        return parse_csv(content, filename)
    if ext in (".xlsx", ".xls"):
        return parse_excel(content, filename)
    if ext == ".json":
        return parse_json(content, filename)
    if ext == ".pdf":
        return parse_pdf(content, filename)
    if ext == ".txt":
        return parse_txt(content, filename)
    raise ValueError(f"Handler missing for '{ext}'")


def normalize_invoice_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw parsed row to a clean invoice dict suitable for the DB."""
    return {
        "invoice_number": raw.get("invoice_number") or raw.get("Invoice Number") or raw.get("inv_no"),
        "invoice_date": _parse_date(raw.get("invoice_date")),
        "supplier_name": raw.get("supplier_name"),
        "supplier_gstin": _clean_gstin(raw.get("supplier_gstin")),
        "recipient_name": raw.get("recipient_name"),
        "recipient_gstin": _clean_gstin(raw.get("recipient_gstin")),
        "taxable_amount": _safe_numeric_str(raw.get("taxable_amount")),
        "gst_rate": _safe_numeric_str(raw.get("gst_rate")),
        "cgst": _safe_numeric_str(raw.get("cgst")),
        "sgst": _safe_numeric_str(raw.get("sgst")),
        "igst": _safe_numeric_str(raw.get("igst")),
        "total_gst": _safe_numeric_str(raw.get("total_gst")),
        "total_amount": _safe_numeric_str(raw.get("total_amount")),
        "place_of_supply": raw.get("place_of_supply"),
        "source_filename": raw.get("source_filename"),
    }


def _clean_gstin(val: Any) -> Optional[str]:
    if not val:
        return None
    return re.sub(r"\s+", "", str(val)).upper()


def _safe_numeric_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).replace(",", "").replace("₹", "").replace("Rs", "").strip()
    try:
        f = float(s)
        return f"{f:.2f}"
    except (ValueError, TypeError):
        return None


def _parse_date(val: Any) -> Optional[str]:
    if not val:
        return None
    s = str(val).strip()
    # Try various formats
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d",
                "%d-%m-%y", "%d/%m/%y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Return as-is if unrecognized but not empty
    return s if s else None
