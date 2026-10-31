import React, { useEffect, useState, useCallback } from 'react';
import { Search, ChevronUp, ChevronDown, ChevronsUpDown, FileText, AlertTriangle } from 'lucide-react';
import { getResults } from '../api';
import type { InvoiceListResponse } from '../api';
import {
  RiskBadge, ClassificationBadge, Spinner, EmptyState,
  formatCurrency, formatDate,
} from '../components/ui';
import InvoiceDetailPanel from '../components/InvoiceDetailPanel';

type SortDir = 'asc' | 'desc';

const SortIcon: React.FC<{ col: string; active: string; dir: SortDir }> = ({ col, active, dir }) => {
  if (col !== active) return <ChevronsUpDown size={12} style={{ color: 'var(--color-text-muted)' }} />;
  return dir === 'asc' ? <ChevronUp size={12} /> : <ChevronDown size={12} />;
};

const FraudResults: React.FC = () => {
  const [data, setData] = useState<InvoiceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [classification, setClassification] = useState('');
  const [riskLevel, setRiskLevel] = useState('');
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState('id');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const pageSize = 20;

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await getResults({
        page,
        page_size: pageSize,
        search: search || undefined,
        classification: classification || undefined,
        risk_level: riskLevel || undefined,
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      setData(resp);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load results.');
    } finally {
      setLoading(false);
    }
  }, [page, search, classification, riskLevel, sortBy, sortDir]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [search, classification, riskLevel]);

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('asc');
    }
  };

  const columns = [
    { key: 'invoice_number', label: 'Invoice No.' },
    { key: 'invoice_date', label: 'Date' },
    { key: 'supplier_name', label: 'Supplier' },
    { key: 'supplier_gstin', label: 'GSTIN' },
    { key: 'total_amount', label: 'Amount' },
    { key: 'classification', label: 'Classification' },
    { key: 'risk_level', label: 'Risk' },
    { key: 'flagged_techniques_count', label: 'Flags' },
  ];

  return (
    <>
      <div className="page-header">
        <div className="page-title">Fraud Results</div>
        <div className="page-subtitle">
          Showing invoices from the latest processed batch.
          {data && ` ${data.total} invoice(s) found.`}
        </div>
      </div>

      <div className="page-body" style={{ padding: '16px 28px' }}>
        {/* Filter bar */}
        <div style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          marginBottom: 16,
          flexWrap: 'wrap',
        }}>
          <div style={{ position: 'relative', flex: '1 1 220px' }}>
            <Search
              size={14}
              style={{
                position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                color: 'var(--color-text-muted)',
              }}
            />
            <input
              className="input"
              style={{ width: '100%', paddingLeft: 30 }}
              placeholder="Search invoice no., supplier, GSTIN…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              id="results-search"
            />
          </div>

          <select
            className="select"
            value={classification}
            onChange={e => setClassification(e.target.value)}
            id="results-filter-classification"
          >
            <option value="">All Classifications</option>
            <option value="Suspicious">Suspicious</option>
            <option value="Not Suspicious">Not Suspicious</option>
          </select>

          <select
            className="select"
            value={riskLevel}
            onChange={e => setRiskLevel(e.target.value)}
            id="results-filter-risk"
          >
            <option value="">All Risk Levels</option>
            <option value="High">High Risk</option>
            <option value="Medium">Medium Risk</option>
            <option value="Low">Low Risk</option>
          </select>

          {(search || classification || riskLevel) && (
            <button
              className="btn btn-secondary"
              style={{ fontSize: 12.5 }}
              onClick={() => { setSearch(''); setClassification(''); setRiskLevel(''); }}
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Table */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
              <Spinner size={28} />
            </div>
          ) : error ? (
            <div style={{ padding: 24 }}>
              <div className="alert alert-error">{error}</div>
            </div>
          ) : !data || data.total === 0 ? (
            <EmptyState
              icon={<FileText size={40} />}
              title={
                data && (search || classification || riskLevel)
                  ? 'No invoices match your filters'
                  : 'No invoices in the latest batch'
              }
              subtitle={
                data && (search || classification || riskLevel)
                  ? 'Try adjusting your search or filter criteria.'
                  : 'Upload an invoice file to see results here.'
              }
            />
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      {columns.map(col => (
                        <th
                          key={col.key}
                          onClick={() => handleSort(col.key)}
                          style={{ userSelect: 'none' }}
                        >
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                            {col.label}
                            <SortIcon col={col.key} active={sortBy} dir={sortDir} />
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map(inv => (
                      <tr
                        key={inv.id}
                        onClick={() => setSelectedId(inv.id)}
                        style={{ cursor: 'pointer' }}
                      >
                        <td style={{ fontWeight: 500 }}>
                          {inv.invoice_number || <span style={{ color: 'var(--color-text-muted)' }}>—</span>}
                        </td>
                        <td style={{ color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>
                          {formatDate(inv.invoice_date)}
                        </td>
                        <td>
                          {inv.supplier_name || <span style={{ color: 'var(--color-text-muted)' }}>—</span>}
                        </td>
                        <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-secondary)' }}>
                          {inv.supplier_gstin || '—'}
                        </td>
                        <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                          {formatCurrency(inv.total_amount)}
                        </td>
                        <td>
                          <ClassificationBadge classification={inv.classification} />
                        </td>
                        <td>
                          <RiskBadge level={inv.risk_level} />
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          {inv.flagged_techniques_count > 0 ? (
                            <span style={{
                              display: 'inline-flex', alignItems: 'center', gap: 3,
                              fontSize: 12, color: 'var(--color-red)', fontWeight: 600,
                            }}>
                              <AlertTriangle size={12} />
                              {inv.flagged_techniques_count}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--color-text-muted)', fontSize: 12 }}>0</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {data.total_pages > 1 && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 16px',
                  borderTop: '1px solid var(--color-border)',
                }}>
                  <span style={{ fontSize: 12.5, color: 'var(--color-text-muted)' }}>
                    Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, data.total)} of {data.total}
                  </span>
                  <div className="pagination">
                    <button
                      className="pagination-btn"
                      onClick={() => setPage(p => p - 1)}
                      disabled={page === 1}
                    >
                      ‹ Prev
                    </button>
                    {Array.from({ length: Math.min(data.total_pages, 7) }, (_, i) => {
                      const p = i + 1;
                      return (
                        <button
                          key={p}
                          className={`pagination-btn${p === page ? ' active' : ''}`}
                          onClick={() => setPage(p)}
                        >
                          {p}
                        </button>
                      );
                    })}
                    <button
                      className="pagination-btn"
                      onClick={() => setPage(p => p + 1)}
                      disabled={page === data.total_pages}
                    >
                      Next ›
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selectedId !== null && (
        <InvoiceDetailPanel
          invoiceId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </>
  );
};

export default FraudResults;
