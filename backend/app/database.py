
"""
Database setup, models, and connection management for FraudLens.
Uses SQLite via SQLAlchemy with proper decimal handling for monetary values.
"""

import os
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///./fraudlens.db")

engine = create_engine(
    DB_PATH,
    connect_args={"check_same_thread": False},
    echo=False,
)


# Enable SQLite settings
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    pass


class Batch(Base):
    """Represents a single upload session."""
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    batch_uuid = Column(String(64), unique=True, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    original_filename = Column(String(512), nullable=True)
    status = Column(String(32), default="pending", nullable=False)
    total_invoices = Column(Integer, default=0)
    flagged_invoices = Column(Integer, default=0)
    invoice_period_start = Column(String(10), nullable=True)
    invoice_period_end = Column(String(10), nullable=True)
    error_message = Column(Text, nullable=True)
    is_latest = Column(Boolean, default=False, nullable=False)

    invoices = relationship(
        "Invoice",
        back_populates="batch",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_batches_status", "status"),
        Index("ix_batches_is_latest", "is_latest"),
    )


class Invoice(Base):
    """Normalized invoice record linked to a batch."""
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)

    invoice_number = Column(String(128), nullable=True)
    invoice_date = Column(String(10), nullable=True)
    invoice_month = Column(String(7), nullable=True)

    supplier_name = Column(String(256), nullable=True)
    supplier_gstin = Column(String(20), nullable=True)
    recipient_name = Column(String(256), nullable=True)
    recipient_gstin = Column(String(20), nullable=True)

    taxable_amount = Column(String(32), nullable=True)
    gst_rate = Column(String(16), nullable=True)
    cgst = Column(String(32), nullable=True)
    sgst = Column(String(32), nullable=True)
    igst = Column(String(32), nullable=True)
    total_gst = Column(String(32), nullable=True)
    total_amount = Column(String(32), nullable=True)

    total_amount_float = Column(Float, nullable=True)
    taxable_amount_float = Column(Float, nullable=True)
    gst_rate_float = Column(Float, nullable=True)

    place_of_supply = Column(String(128), nullable=True)
    source_filename = Column(String(512), nullable=True)
    raw_data = Column(Text, nullable=True)

    classification = Column(String(32), default="Not Suspicious")
    risk_level = Column(String(16), default="Low")
    flagged_techniques_count = Column(Integer, default=0)
    assessment_summary = Column(Text, nullable=True)

    batch = relationship("Batch", back_populates="invoices")
    findings = relationship(
        "TechniqueFinding",
        back_populates="invoice",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_invoices_batch_id", "batch_id"),
        Index("ix_invoices_supplier_gstin", "supplier_gstin"),
        Index("ix_invoices_invoice_month", "invoice_month"),
    )


class TechniqueFinding(Base):
    """Result of a fraud-detection technique applied to one invoice."""
    __tablename__ = "technique_findings"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    technique = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    severity = Column(String(16), nullable=True)
    reason = Column(Text, nullable=True)
    evidence = Column(Text, nullable=True)

    invoice = relationship("Invoice", back_populates="findings")

    __table_args__ = (
        Index("ix_findings_invoice_id", "invoice_id"),
        Index("ix_findings_technique", "technique"),
    )


class MonthlySummary(Base):
    """Pre-aggregated monthly stats across all batches."""
    __tablename__ = "monthly_summaries"

    id = Column(Integer, primary_key=True, index=True)
    month = Column(String(7), unique=True, nullable=False, index=True)
    total_invoices = Column(Integer, default=0)
    flagged_invoices = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)


# ── Security models ──────────────────────────────────────────────────────────

class User(Base):
    """Application login account. Passwords are stored as hashes."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(512), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)


class ActivityLog(Base):
    """Records important actions performed by authenticated users."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(100), nullable=False)
    action = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User")

    __table_args__ = (
        Index("ix_activity_logs_user_id", "user_id"),
        Index("ix_activity_logs_created_at", "created_at"),
        Index("ix_activity_logs_action", "action"),
    )


class UserSession(Base):
    """Tracks active login sessions and their inactivity expiry."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User")



# ── Database helpers ─────────────────────────────────────────────────────────

def get_db():
    """FastAPI dependency for a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create missing tables without deleting existing data."""
    Base.metadata.create_all(bind=engine)
