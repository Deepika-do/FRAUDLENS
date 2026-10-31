
"""
FraudLens FastAPI application — entry point.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import traceback
import uuid

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import (
    Batch,
    Invoice,
    MonthlySummary,
    TechniqueFinding,
    User,
    UserSession,
    ActivityLog,
    SessionLocal,
    get_db,
    init_db,
)

from app.parsers.invoice_parser import SUPPORTED_EXTENSIONS, parse_file
from app.processor import process_batch
from app import schemas


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FraudLens — GST Invoice Fraud Detection",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", 20))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ── Authentication helpers ────────────────────────────────────────────────────

SESSION_TIMEOUT_MINUTES = 15
SESSION_MAX_HOURS = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000,
    )
    return salt.hex() + ":" + password_hash.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, expected_hash = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            600_000,
        ).hex()

        return hmac.compare_digest(actual_hash, expected_hash)

    except (ValueError, TypeError):
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def record_activity(
    db: Session,
    username: str,
    action: str,
    description: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
):
    log = ActivityLog(
        user_id=user_id,
        username=username,
        action=action,
        description=description,
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get("fraudlens_session")

    if not token:
        raise HTTPException(status_code=401, detail="Please log in.")

    token_hash = hash_session_token(token)

    session_record = (
        db.query(UserSession)
        .filter(UserSession.token_hash == token_hash)
        .first()
    )

    now = datetime.utcnow()

    if not session_record:
        raise HTTPException(status_code=401, detail="Invalid session.")

    if (
        now - session_record.last_activity
    ).total_seconds() > SESSION_TIMEOUT_MINUTES * 60:
        db.delete(session_record)
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in again.",
        )

    if session_record.expires_at <= now:
        db.delete(session_record)
        db.commit()
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please log in again.",
        )

    user = (
        db.query(User)
        .filter(
            User.id == session_record.user_id,
            User.is_active == True,
        )
        .first()
    )

    if not user:
        db.delete(session_record)
        db.commit()
        raise HTTPException(status_code=401, detail="Account is inactive.")

    session_record.last_activity = now
    db.commit()

    return user


# ── General helpers ───────────────────────────────────────────────────────────

def _safe_filename(filename: str) -> str:
    return Path(filename).name


def _get_latest_batch(db: Session) -> Optional[Batch]:
    return db.query(Batch).filter(Batch.is_latest == True).first()


def _finding_to_schema(f: TechniqueFinding) -> schemas.TechniqueFindingOut:
    try:
        evidence = json.loads(f.evidence) if f.evidence else {}
    except Exception:
        evidence = {}

    return schemas.TechniqueFindingOut(
        id=f.id,
        technique=f.technique,
        status=f.status,
        severity=f.severity,
        reason=f.reason,
        evidence=evidence,
    )


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    init_db()

    username = os.environ.get("FRAUDLENS_ADMIN_USERNAME")
    password = os.environ.get("FRAUDLENS_ADMIN_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "Set FRAUDLENS_ADMIN_USERNAME and FRAUDLENS_ADMIN_PASSWORD before starting."
        )

    db = SessionLocal()

    try:
        admin = db.query(User).filter(User.username == username).first()

        if not admin:
            admin = User(
                username=username,
                password_hash=hash_password(password),
                is_active=True,
            )
            db.add(admin)
            db.commit()

    finally:
        db.close()


# ── Authentication API ────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(
    credentials: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.username == credentials.username)
        .first()
    )

    if (
        not user
        or not user.is_active
        or not verify_password(credentials.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password.",
        )

    token = secrets.token_urlsafe(48)
    now = datetime.utcnow()

    session_record = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        created_at=now,
        last_activity=now,
        expires_at=now + timedelta(hours=SESSION_MAX_HOURS),
    )

    user.last_login = now
    db.add(session_record)
    db.commit()

    record_activity(
        db,
        username=user.username,
        action="LOGIN",
        description="User logged in successfully.",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    response.set_cookie(
        key="fraudlens_session",
        value=token,
        httponly=True,
        secure=os.environ.get(
            "FRAUDLENS_COOKIE_SECURE", "false"
        ).lower() == "true",
        samesite="strict",
        max_age=SESSION_MAX_HOURS * 60 * 60,
        path="/",
    )

    return {
        "message": "Login successful.",
        "username": user.username,
    }


@app.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = request.cookies.get("fraudlens_session")

    if token:
        token_hash = hash_session_token(token)

        db.query(UserSession).filter(
            UserSession.token_hash == token_hash
        ).delete(synchronize_session=False)

        db.commit()

    record_activity(
        db,
        username=current_user.username,
        action="LOGOUT",
        description="User logged out.",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )

    response.delete_cookie(
        key="fraudlens_session",
        path="/",
        httponly=True,
        samesite="strict",
    )

    return {"message": "Logged out successfully."}


@app.get("/api/auth/me")
def get_logged_in_user(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "username": current_user.username,
    }


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/api/dashboard", response_model=schemas.DashboardSummary)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    latest = _get_latest_batch(db)

    if not latest:
        return schemas.DashboardSummary(
            invoices_scanned=0,
            needs_review=0,
            latest_batch=None,
            monthly_chart=[],
        )

    monthly = db.query(MonthlySummary).order_by(
        MonthlySummary.month
    ).all()

    chart = [
        {
            "month": m.month,
            "total": m.total_invoices,
            "flagged": m.flagged_invoices,
        }
        for m in monthly
    ]

    batch_out = schemas.BatchOut.model_validate(latest)

    return schemas.DashboardSummary(
        invoices_scanned=latest.total_invoices,
        needs_review=latest.flagged_invoices,
        latest_batch=batch_out,
        monthly_chart=chart,
    )


# ── Upload ────────────────────────────────────────────────────────────────────

@app.post(
    "/api/upload",
    response_model=schemas.UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = _safe_filename(file.filename or "unknown")
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds maximum allowed {MAX_FILE_SIZE_MB} MB.",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    errors: List[str] = []

    try:
        raw_rows = parse_file(content, filename)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File parsing failed: {e}",
        )

    if not raw_rows:
        raise HTTPException(
            status_code=422,
            detail="No invoice records could be extracted from this file.",
        )

    batch_uuid = str(uuid.uuid4())

    batch = Batch(
        batch_uuid=batch_uuid,
        original_filename=filename,
        status="processing",
        uploaded_at=datetime.utcnow(),
        is_latest=False,
    )

    db.add(batch)
    db.commit()
    db.refresh(batch)

    try:
        process_batch(db, batch, raw_rows, errors)
        db.refresh(batch)

    except Exception as e:
        batch.status = "failed"
        batch.error_message = str(e)
        db.commit()

        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {e}",
        )

    return schemas.UploadResponse(
        batch_uuid=batch_uuid,
        status=batch.status,
        message=(
            f"Batch processed successfully. "
            f"{batch.total_invoices} invoice(s) processed, "
            f"{batch.flagged_invoices} require review."
        ),
        total_invoices=batch.total_invoices,
        flagged_invoices=batch.flagged_invoices,
        errors=errors,
    )


# ── Batches ───────────────────────────────────────────────────────────────────

@app.get("/api/batches", response_model=List[schemas.BatchOut])
def list_batches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Batch).order_by(
        Batch.uploaded_at.desc()
    ).all()


@app.get("/api/batches/{batch_uuid}", response_model=schemas.BatchOut)
def get_batch(
    batch_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batch = db.query(Batch).filter(
        Batch.batch_uuid == batch_uuid
    ).first()

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    return batch


@app.delete("/api/batches/{batch_uuid}")
def delete_batch(
    batch_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batch = db.query(Batch).filter(
        Batch.batch_uuid == batch_uuid
    ).first()

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Batch not found.",
        )

    try:
        affected_months = {
            invoice.invoice_month
            for invoice in batch.invoices
            if invoice.invoice_month
        }

        db.delete(batch)
        db.flush()

        for month in affected_months:
            remaining_invoices = (
                db.query(Invoice)
                .filter(Invoice.invoice_month == month)
                .all()
            )

            if not remaining_invoices:
                db.query(MonthlySummary).filter(
                    MonthlySummary.month == month
                ).delete(synchronize_session=False)

            else:
                total = len(remaining_invoices)

                flagged = sum(
                    1
                    for invoice in remaining_invoices
                    if invoice.flagged_techniques_count > 0
                )

                summary = (
                    db.query(MonthlySummary)
                    .filter(MonthlySummary.month == month)
                    .first()
                )

                if summary:
                    summary.total_invoices = total
                    summary.flagged_invoices = flagged

        db.query(Batch).update({Batch.is_latest: False})

        latest_batch = (
            db.query(Batch)
            .filter(Batch.status == "completed")
            .order_by(Batch.uploaded_at.desc())
            .first()
        )

        if latest_batch:
            latest_batch.is_latest = True

        db.commit()

        return {
            "message": "Batch deleted successfully.",
            "deleted_batch": batch_uuid,
        }

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete batch: {str(e)}",
        )


# ── Fraud Results ─────────────────────────────────────────────────────────────

@app.get("/api/results", response_model=schemas.InvoiceListResponse)
def get_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("id"),
    sort_dir: Optional[str] = Query("asc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    latest = _get_latest_batch(db)

    if not latest:
        return schemas.InvoiceListResponse(
            items=[],
            total=0,
            page=1,
            page_size=page_size,
            total_pages=0,
        )

    q = db.query(Invoice).filter(
        Invoice.batch_id == latest.id
    )

    if search:
        like = f"%{search}%"

        q = q.filter(
            Invoice.invoice_number.ilike(like)
            | Invoice.supplier_name.ilike(like)
            | Invoice.supplier_gstin.ilike(like)
        )

    if classification:
        q = q.filter(
            Invoice.classification == classification
        )

    if risk_level:
        q = q.filter(
            Invoice.risk_level == risk_level
        )

    valid_sort_cols = {
        "id": Invoice.id,
        "invoice_number": Invoice.invoice_number,
        "invoice_date": Invoice.invoice_date,
        "supplier_name": Invoice.supplier_name,
        "total_amount": Invoice.total_amount_float,
        "risk_level": Invoice.risk_level,
        "classification": Invoice.classification,
        "flagged_techniques_count": Invoice.flagged_techniques_count,
    }

    sort_col = valid_sort_cols.get(
        sort_by or "id",
        Invoice.id,
    )

    if sort_dir == "desc":
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col.asc())

    total = q.count()
    total_pages = max(
        1,
        (total + page_size - 1) // page_size,
    )

    items = q.offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return schemas.InvoiceListResponse(
        items=[
            schemas.InvoiceListItem.model_validate(i)
            for i in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@app.get(
    "/api/results/{invoice_id}",
    response_model=schemas.InvoiceDetail,
)
def get_invoice_detail(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inv = db.query(Invoice).filter(
        Invoice.id == invoice_id
    ).first()

    if not inv:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found.",
        )

    findings = [
        _finding_to_schema(f)
        for f in inv.findings
    ]

    return schemas.InvoiceDetail(
        id=inv.id,
        batch_id=inv.batch_id,
        invoice_number=inv.invoice_number,
        invoice_date=inv.invoice_date,
        invoice_month=inv.invoice_month,
        supplier_name=inv.supplier_name,
        supplier_gstin=inv.supplier_gstin,
        recipient_name=inv.recipient_name,
        recipient_gstin=inv.recipient_gstin,
        taxable_amount=inv.taxable_amount,
        gst_rate=inv.gst_rate,
        cgst=inv.cgst,
        sgst=inv.sgst,
        igst=inv.igst,
        total_gst=inv.total_gst,
        total_amount=inv.total_amount,
        place_of_supply=inv.place_of_supply,
        source_filename=inv.source_filename,
        classification=inv.classification,
        risk_level=inv.risk_level,
        flagged_techniques_count=inv.flagged_techniques_count,
        assessment_summary=inv.assessment_summary,
        findings=findings,
    )


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
    }
