import React, { useEffect, useState } from 'react';
import { X, CheckCircle2, AlertCircle, MinusCircle, ShieldCheck, ShieldAlert, FileText, Users, Calculator } from 'lucide-react';
import { getInvoiceDetail } from '../api';
import type { InvoiceDetail, TechniqueFinding } from '../api';
import { Spinner, formatCurrency, formatDate } from './ui';

interface Props {
  invoiceId: number;
  onClose: () => void;
}

/* ─── Technique metadata ──────────────────────────────────────────────── */
const TECHNIQUE_META: Record<string, { label: string; description: string }> = {
  gst_validation: {
    label: 'GST Validation',
    description: 'Checks whether GST details and tax information appear valid.',
  },
  duplicate_detection: {
    label: 'Duplicate Detection',
    description: 'Checks whether an invoice has been submitted more than once.',
  },
  zscore_analysis: {
    label: 'Z-Score Analysis',
    description: 'Identifies invoice amounts that are unusually different from normal amounts.',
  },
  supplier_behavior: {
    label: 'Supplier Behaviour',
    description: "Identifies unusual patterns in a supplier's transactions.",
  },
  transaction_frequency: {
    label: 'Transaction Frequency',
    description: 'Checks whether a supplier is generating an unusually high number of invoices.',
  },
  isolation_forest: {
    label: 'Isolation Forest',
    description: 'Identifies unusual invoice patterns by comparing them with other invoices.',
  },
};

/* Canonical order so display is always consistent */
const TECHNIQUE_ORDER = [
  'gst_validation',
  'duplicate_detection',
  'zscore_analysis',
  'supplier_behavior',
  'transaction_frequency',
  'isolation_forest',
];

/* ─── Status pill ─────────────────────────────────────────────────────── */
const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  if (status === 'Pass') {
    return (
      <span className="idp-status-pill idp-status-pass">
        <CheckCircle2 size={12} />
        PASS
      </span>
    );
  }
  if (status === 'Flagged') {
    return (
      <span className="idp-status-pill idp-status-flagged">
        <AlertCircle size={12} />
        FLAGGED
      </span>
    );
  }
  return (
    <span className="idp-status-pill idp-status-insufficient">
      <MinusCircle size={12} />
      INSUFFICIENT DATA
    </span>
  );
};

/* ─── Overall assessment banner ───────────────────────────────────────── */
const AssessmentBanner: React.FC<{ inv: InvoiceDetail }> = ({ inv }) => {
  const isSuspicious = inv.classification === 'Suspicious';
  const riskLevel = inv.risk_level;

  const riskColor =
    riskLevel === 'High' ? 'var(--color-red)' :
    riskLevel === 'Medium' ? 'var(--color-amber)' :
    'var(--color-green)';

  const riskBg =
    riskLevel === 'High' ? 'var(--color-red-light)' :
    riskLevel === 'Medium' ? 'var(--color-amber-light)' :
    'var(--color-green-light)';

  const riskBorder =
    riskLevel === 'High' ? 'rgba(220,38,38,0.2)' :
    riskLevel === 'Medium' ? 'rgba(217,119,6,0.2)' :
    'rgba(22,163,74,0.2)';

  return (
    <div
      className="idp-assessment-banner"
      style={{ background: riskBg, borderColor: riskBorder }}
    >
      <div className="idp-assessment-icon" style={{ color: riskColor }}>
        {isSuspicious ? <ShieldAlert size={28} /> : <ShieldCheck size={28} />}
      </div>
      <div className="idp-assessment-content">
        <div className="idp-assessment-verdict" style={{ color: riskColor }}>
          {isSuspicious ? 'Suspicious Invoice' : 'No Significant Issues Found'}
        </div>
        <div className="idp-assessment-meta">
          <span className="idp-risk-chip" style={{ color: riskColor, borderColor: riskBorder, background: 'rgba(255,255,255,0.7)' }}>
            {riskLevel} Risk
          </span>
          {inv.flagged_techniques_count > 0 && (
            <span className="idp-flagged-chip">
              {inv.flagged_techniques_count} check{inv.flagged_techniques_count !== 1 ? 's' : ''} flagged
            </span>
          )}
        </div>
        {inv.assessment_summary && (
          <p className="idp-assessment-summary">{inv.assessment_summary}</p>
        )}
      </div>
    </div>
  );
};

/* ─── Section wrapper ─────────────────────────────────────────────────── */
const Section: React.FC<{ icon: React.ReactNode; title: string; children: React.ReactNode }> = ({
  icon,
  title,
  children,
}) => (
  <div className="idp-section">
    <div className="idp-section-header">
      <span className="idp-section-icon">{icon}</span>
      <span className="idp-section-title">{title}</span>
    </div>
    <div className="idp-section-body">{children}</div>
  </div>
);

/* ─── Key-value row ───────────────────────────────────────────────────── */
const Field: React.FC<{
  label: string;
  value: string | null | undefined;
  mono?: boolean;
  bold?: boolean;
}> = ({ label, value, mono, bold }) => {
  if (!value || value === '—') return null;
  return (
    <div className="idp-field">
      <span className="idp-field-label">{label}</span>
      <span
        className="idp-field-value"
        style={{
          fontFamily: mono ? 'monospace' : undefined,
          fontWeight: bold ? 600 : undefined,
          fontSize: mono ? 12 : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
};

/* ─── Divider ─────────────────────────────────────────────────────────── */
const Divider: React.FC = () => <div className="idp-divider" />;

/* ─── Technique card ──────────────────────────────────────────────────── */
const TechniqueCard: React.FC<{ finding: TechniqueFinding }> = ({ finding }) => {
  const meta = TECHNIQUE_META[finding.technique] || {
    label: finding.technique.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    description: '',
  };
  const isFlagged = finding.status === 'Flagged';

  return (
    <div className={`idp-technique-card${isFlagged ? ' idp-technique-flagged' : ''}`}>
      <div className="idp-technique-top">
        <div className="idp-technique-info">
          <div className="idp-technique-name">{meta.label}</div>
          <div className="idp-technique-desc">{meta.description}</div>
        </div>
        <StatusPill status={finding.status} />
      </div>
      {isFlagged && finding.reason && (
        <div className="idp-technique-reason">
          <AlertCircle size={13} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>{finding.reason}</span>
        </div>
      )}
    </div>
  );
};

/* ─── Main component ──────────────────────────────────────────────────── */
const InvoiceDetailPanel: React.FC<Props> = ({ invoiceId, onClose }) => {
  const [inv, setInv] = useState<InvoiceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getInvoiceDetail(invoiceId)
      .then(setInv)
      .catch((e) => setError(e?.response?.data?.detail || 'Failed to load invoice details.'))
      .finally(() => setLoading(false));
  }, [invoiceId]);

  /* Build ordered findings — fill gaps with synthetic "Insufficient Data" */
  const orderedFindings: TechniqueFinding[] = (() => {
    if (!inv) return [];
    const map = new Map(inv.findings.map((f) => [f.technique, f]));
    return TECHNIQUE_ORDER.map(
      (key) =>
        map.get(key) ?? {
          id: -1,
          technique: key,
          status: 'Insufficient Data',
          severity: null,
          reason: null,
          evidence: {},
        },
    );
  })();

  return (
    <>
      <div className="detail-overlay" onClick={onClose} />
      <aside className="detail-panel idp-panel" role="dialog" aria-label="Invoice Detail">
        {/* Header */}
        <div className="idp-header">
          <div className="idp-header-meta">
            <div className="idp-header-number">
              {inv?.invoice_number ? `Invoice ${inv.invoice_number}` : `Invoice #${invoiceId}`}
            </div>
            {inv && (
              <div className="idp-header-date">
                {formatDate(inv.invoice_date)}
                {inv.source_filename ? ` · ${inv.source_filename}` : ''}
              </div>
            )}
          </div>
          <button onClick={onClose} className="detail-close-button" aria-label="Close panel">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="idp-body">
          {loading && (
            <div className="idp-loading">
              <Spinner size={28} />
            </div>
          )}
          {error && <div className="alert alert-error">{error}</div>}

          {inv && !loading && (
            <>
              {/* ── 1. Overall Assessment ── */}
              <AssessmentBanner inv={inv} />

              {/* ── 2. Invoice Information ── */}
              <Section icon={<FileText size={15} />} title="Invoice Information">
                <Field label="Invoice Number" value={inv.invoice_number} />
                <Field label="Invoice Date" value={formatDate(inv.invoice_date)} />
                <Field label="Invoice Month" value={inv.invoice_month} />
                <Field label="Place of Supply" value={inv.place_of_supply} />
              </Section>

              {/* ── 3. Supplier & Recipient ── */}
              <Section icon={<Users size={15} />} title="Supplier & Recipient">
                <div className="idp-party-group">
                  <div className="idp-party-label">Supplier</div>
                  <Field label="Name" value={inv.supplier_name} />
                  <Field label="GSTIN" value={inv.supplier_gstin} mono />
                </div>
                <Divider />
                <div className="idp-party-group">
                  <div className="idp-party-label">Recipient</div>
                  <Field label="Name" value={inv.recipient_name} />
                  <Field label="GSTIN" value={inv.recipient_gstin} mono />
                </div>
              </Section>

              {/* ── 4. GST & Tax Breakdown ── */}
              <Section icon={<Calculator size={15} />} title="GST & Tax Breakdown">
                <Field label="Taxable Amount" value={formatCurrency(inv.taxable_amount)} />
                <Field label="GST Rate" value={inv.gst_rate ? `${inv.gst_rate}%` : null} />
                <Divider />
                <Field label="CGST" value={formatCurrency(inv.cgst)} />
                <Field label="SGST" value={formatCurrency(inv.sgst)} />
                <Field label="IGST" value={formatCurrency(inv.igst)} />
                <Field label="Total GST" value={formatCurrency(inv.total_gst)} />
                <Divider />
                <Field label="Total Invoice Amount" value={formatCurrency(inv.total_amount)} bold />
              </Section>

              {/* ── 5. Fraud Detection Results ── */}
              <Section
                icon={
                  inv.flagged_techniques_count > 0
                    ? <ShieldAlert size={15} color="var(--color-red)" />
                    : <ShieldCheck size={15} color="var(--color-green)" />
                }
                title="Fraud Detection Results"
              >
                <div className="idp-legend">
                  <span className="idp-legend-item idp-legend-pass">
                    <CheckCircle2 size={11} /> Pass
                  </span>
                  <span className="idp-legend-item idp-legend-flagged">
                    <AlertCircle size={11} /> Flagged
                  </span>
                  <span className="idp-legend-item idp-legend-insufficient">
                    <MinusCircle size={11} /> Insufficient Data
                  </span>
                </div>
                <div className="idp-techniques-list">
                  {orderedFindings.map((f) => (
                    <TechniqueCard key={f.technique} finding={f} />
                  ))}
                </div>
              </Section>
            </>
          )}
        </div>
      </aside>
    </>
  );
};

export default InvoiceDetailPanel;
