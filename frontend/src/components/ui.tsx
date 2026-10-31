import React from 'react';

interface RiskBadgeProps {
  level: string;
  className?: string;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, className = '' }) => {
  const cls =
    level === 'High' ? 'badge badge-high' :
    level === 'Medium' ? 'badge badge-medium' :
    'badge badge-low';
  return <span className={`${cls} ${className}`}>{level} Risk</span>;
};

interface ClassificationBadgeProps {
  classification: string;
  className?: string;
}

export const ClassificationBadge: React.FC<ClassificationBadgeProps> = ({ classification, className = '' }) => {
  const cls = classification === 'Suspicious' ? 'badge badge-suspicious' : 'badge badge-not-suspicious';
  const label = classification === 'Suspicious' ? 'Suspicious' : 'Not Suspicious';
  return <span className={`${cls} ${className}`}>{label}</span>;
};

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const cls =
    status === 'Pass' ? 'badge badge-pass' :
    status === 'Flagged' ? 'badge badge-flagged' :
    status === 'Insufficient Data' ? 'badge badge-insufficient' :
    'badge badge-error';
  return <span className={`${cls} ${className}`}>{status}</span>;
};

interface SpinnerProps {
  size?: number;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 18 }) => (
  <div className="spinner" style={{ width: size, height: size }} />
);

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, subtitle, action }) => (
  <div className="empty-state">
    {icon && <div className="empty-state-icon">{icon}</div>}
    <div className="empty-state-title">{title}</div>
    {subtitle && <div className="empty-state-sub">{subtitle}</div>}
    {action}
  </div>
);

export const formatCurrency = (val: string | null | undefined): string => {
  if (!val) return '—';
  const num = parseFloat(val.replace(',', ''));
  if (isNaN(num)) return val;
  return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const formatDate = (val: string | null | undefined): string => {
  if (!val) return '—';
  try {
    const d = new Date(val);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch {
    return val;
  }
};

export const TECHNIQUE_LABELS: Record<string, string> = {
  gst_validation: 'GST Validation',
  duplicate_detection: 'Duplicate Detection',
  zscore_analysis: 'Z-Score Analysis',
  supplier_behavior: 'Supplier Behaviour',
  transaction_frequency: 'Transaction Frequency',
  isolation_forest: 'Isolation Forest (ML)',
};
