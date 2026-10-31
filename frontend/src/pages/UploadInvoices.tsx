
import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload,
  FileText,
  X,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Trash2,
  RefreshCw
} from 'lucide-react';

import { uploadFile, getBatches, deleteBatch } from '../api';
import type { UploadResponse, BatchSummary } from '../api';
import { Spinner } from '../components/ui';

const SUPPORTED_EXTS = ['.pdf', '.json', '.csv', '.xlsx', '.xls', '.txt'];
const MAX_MB = 20;

const UploadInvoices: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Upload history states
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [deletingBatch, setDeletingBatch] = useState<string | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  // Load upload history
  const loadBatches = useCallback(async () => {
    try {
      setLoadingBatches(true);
      setBatchError(null);
      const data = await getBatches();
      setBatches(data);
    } catch {
      setBatchError('Unable to load upload history.');
    } finally {
      setLoadingBatches(false);
    }
  }, []);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  // Delete selected batch
  const handleDeleteBatch = async (batch: BatchSummary) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${batch.original_filename}" and all its invoices?`
    );

    if (!confirmed) return;

    try {
      setDeletingBatch(batch.batch_uuid);
      setBatchError(null);

      await deleteBatch(batch.batch_uuid);
      await loadBatches();
    } catch {
      setBatchError('Unable to delete this batch. Please try again.');
    } finally {
      setDeletingBatch(null);
    }
  };

  const validateFile = (file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!SUPPORTED_EXTS.includes(ext)) {
      return `Unsupported file type "${ext}". Accepted: ${SUPPORTED_EXTS.join(', ')}`;
    }

    if (file.size > MAX_MB * 1024 * 1024) {
      return `File size (${(file.size / 1024 / 1024).toFixed(1)} MB) exceeds the ${MAX_MB} MB limit.`;
    }

    if (file.size === 0) {
      return 'The selected file is empty.';
    }

    return null;
  };

  const handleFileDrop = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;

    const file = files[0];
    const err = validateFile(file);

    if (err) {
      setUploadError(err);
      setSelectedFile(null);
    } else {
      setSelectedFile(file);
      setUploadError(null);
      setResult(null);
    }
  }, []);

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const onDragLeave = () => setDragOver(false);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFileDrop(e.dataTransfer.files);
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFileDrop(e.target.files);
    e.target.value = '';
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setUploadError(null);
    setResult(null);

    try {
      const resp = await uploadFile(selectedFile);
      setResult(resp);
      setSelectedFile(null);

      // Refresh history after successful upload
      await loadBatches();
    } catch (e: any) {
      const msg =
        e?.response?.data?.detail ||
        e?.message ||
        'Upload failed. Please try again.';

      setUploadError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setUploading(false);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    setUploadError(null);
    setResult(null);
  };

  return (
    <>
      <div className="page-header">
        <div className="page-title">Upload Invoices</div>
        <div className="page-subtitle">
          Upload a GST invoice file to run fraud detection analysis.
        </div>
      </div>

      <div className="page-body" style={{ maxWidth: 850 }}>

        {/* Upload zone */}
        <div
          className={`upload-zone${dragOver ? ' drag-over' : ''}`}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => !selectedFile && fileInputRef.current?.click()}
          style={{ cursor: selectedFile ? 'default' : 'pointer' }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={SUPPORTED_EXTS.join(',')}
            style={{ display: 'none' }}
            onChange={onFileChange}
            id="file-upload-input"
          />

          {!selectedFile ? (
            <>
              <Upload
                size={32}
                color="var(--color-text-muted)"
                style={{ margin: '0 auto 12px' }}
              />

              <div style={{
                fontSize: 15,
                fontWeight: 500,
                color: 'var(--color-text-primary)',
                marginBottom: 4
              }}>
                Drop a file here, or{' '}
                <span style={{ color: 'var(--color-blue)', cursor: 'pointer' }}>
                  browse
                </span>
              </div>

              <div style={{
                fontSize: 12.5,
                color: 'var(--color-text-muted)',
                marginBottom: 12
              }}>
                One file per upload · up to {MAX_MB} MB
              </div>

              <div style={{
                display: 'flex',
                gap: 6,
                flexWrap: 'wrap',
                justifyContent: 'center',
              }}>
                {SUPPORTED_EXTS.map(ext => (
                  <span
                    key={ext}
                    style={{
                      fontSize: 11,
                      padding: '2px 8px',
                      background: 'white',
                      border: '1px solid var(--color-border)',
                      borderRadius: 4,
                      color: 'var(--color-text-secondary)',
                      fontWeight: 500,
                    }}
                  >
                    {ext.toUpperCase()}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              justifyContent: 'center'
            }}>
              <FileText size={28} color="var(--color-blue)" />

              <div style={{ textAlign: 'left' }}>
                <div style={{ fontWeight: 500, fontSize: 14 }}>
                  {selectedFile.name}
                </div>
                <div style={{
                  fontSize: 12,
                  color: 'var(--color-text-muted)',
                  marginTop: 2
                }}>
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </div>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  clearFile();
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--color-text-muted)',
                  padding: 4,
                  borderRadius: 4,
                  display: 'flex',
                }}
                aria-label="Remove file"
              >
                <X size={16} />
              </button>
            </div>
          )}
        </div>

        {/* Upload notes */}
        <div style={{
          marginTop: 12,
          padding: '10px 14px',
          background: '#f9fafb',
          border: '1px solid var(--color-border)',
          borderRadius: 6,
          fontSize: 12.5,
          color: 'var(--color-text-secondary)',
          lineHeight: 1.6,
        }}>
          <strong style={{ color: 'var(--color-text-primary)' }}>
            Supported formats:
          </strong>{' '}
          CSV and Excel files should have headers matching field names such as
          invoice_number, invoice_date, supplier_gstin, total_amount.
          JSON files can be a list of invoices or an object with an "invoices" key.
          PDFs are processed by text extraction — scanned image PDFs are not supported.
          TXT files with CSV-style or labeled fields are accepted.
          Image files (JPG, PNG, etc.) are not supported.
        </div>

        {/* Upload error */}
        {uploadError && (
          <div className="alert alert-error" style={{ marginTop: 16 }}>
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <div>{uploadError}</div>
          </div>
        )}

        {/* Upload button */}
        {selectedFile && !result && (
          <div style={{ marginTop: 16 }}>
            <button
              className="btn btn-primary"
              onClick={handleUpload}
              disabled={uploading}
              id="upload-submit-btn"
            >
              {uploading ? <Spinner size={15} /> : <Upload size={15} />}
              {uploading ? 'Processing…' : 'Upload & Analyse'}
            </button>
          </div>
        )}

        {/* Progress indicator */}
        {uploading && (
          <div className="alert alert-info" style={{ marginTop: 16 }}>
            <Spinner size={15} />
            <div>
              Parsing file, running fraud detection techniques, and saving results.
              This may take a moment for large files.
            </div>
          </div>
        )}

        {/* Success result */}
        {result && (
          <div style={{
            marginTop: 16,
            display: 'flex',
            flexDirection: 'column',
            gap: 12
          }}>
            <div className={`alert ${
              result.status === 'completed' ? 'alert-success' : 'alert-error'
            }`}>
              {result.status === 'completed'
                ? <CheckCircle size={16} style={{ flexShrink: 0 }} />
                : <AlertCircle size={16} style={{ flexShrink: 0 }} />}

              <div>
                <strong>
                  {result.status === 'completed'
                    ? 'Processing complete.'
                    : 'Processing issue.'}
                </strong>{' '}
                {result.message}
              </div>
            </div>

            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 12,
            }}>
              <div className="metric-panel">
                <div className="metric-label">Invoices Processed</div>
                <div className="metric-value" style={{ fontSize: 22 }}>
                  {result.total_invoices}
                </div>
              </div>

              <div className="metric-panel">
                <div className="metric-label">Needs Review</div>
                <div
                  className="metric-value"
                  style={{
                    fontSize: 22,
                    color: result.flagged_invoices > 0 ? '#dc2626' : undefined
                  }}
                >
                  {result.flagged_invoices}
                </div>
              </div>
            </div>

            {result.errors.length > 0 && (
              <div style={{
                background: '#fff7ed',
                border: '1px solid rgba(194,65,12,0.2)',
                borderRadius: 6,
                padding: '10px 14px',
              }}>
                <div style={{
                  fontSize: 12.5,
                  fontWeight: 600,
                  color: '#9a3412',
                  marginBottom: 6,
                  display: 'flex',
                  gap: 6,
                  alignItems: 'center'
                }}>
                  <AlertTriangle size={14} />
                  {result.errors.length} parsing warning(s)
                </div>

                <ul style={{
                  fontSize: 12,
                  color: '#92400e',
                  paddingLeft: 16,
                  margin: 0
                }}>
                  {result.errors.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-primary"
                onClick={() => navigate('/results')}
              >
                View Results →
              </button>

              <button
                className="btn btn-secondary"
                onClick={() => setResult(null)}
              >
                Upload Another
              </button>
            </div>
          </div>
        )}

        {/* Upload History */}
        <div style={{ marginTop: 36 }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 16
          }}>
            <div>
              <h2 style={{
                fontSize: 18,
                fontWeight: 600,
                margin: 0,
                color: 'var(--color-text-primary)'
              }}>
                Upload History
              </h2>
              <p style={{
                fontSize: 12.5,
                color: 'var(--color-text-muted)',
                marginTop: 4
              }}>
                View and manage your uploaded invoice batches.
              </p>
            </div>

            <button
              className="btn btn-secondary"
              onClick={loadBatches}
              disabled={loadingBatches}
            >
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>

          {batchError && (
            <div className="alert alert-error" style={{ marginBottom: 12 }}>
              <AlertCircle size={16} />
              {batchError}
            </div>
          )}

          {loadingBatches ? (
            <p style={{ color: 'var(--color-text-muted)' }}>
              Loading upload history...
            </p>
          ) : batches.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)' }}>
              No uploaded batches found.
            </p>
          ) : (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 10
            }}>
              {batches.map(batch => (
                <div
                  key={batch.batch_uuid}
                  className="metric-panel"
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                    padding: 16
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{
                      fontWeight: 600,
                      fontSize: 13.5,
                      color: 'var(--color-text-primary)',
                      overflowWrap: 'anywhere'
                    }}>
                      <FileText
                        size={14}
                        style={{
                          display: 'inline',
                          verticalAlign: 'middle',
                          marginRight: 6
                        }}
                      />
                      {batch.original_filename}
                    </div>

                    <div style={{
                      fontSize: 12,
                      color: 'var(--color-text-secondary)',
                      marginTop: 6
                    }}>
                      {batch.total_invoices} invoices · {batch.flagged_invoices} need review
                    </div>

                    <div style={{
                      fontSize: 11.5,
                      color: 'var(--color-text-muted)',
                      marginTop: 4
                    }}>
                      {new Date(batch.uploaded_at).toLocaleString()}
                      {batch.is_latest && (
                        <strong style={{
                          color: 'var(--color-blue)',
                          marginLeft: 8
                        }}>
                          Latest batch
                        </strong>
                      )}
                    </div>
                  </div>

                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDeleteBatch(batch)}
                    disabled={deletingBatch === batch.batch_uuid}
                    style={{
                      color: '#dc2626',
                      flexShrink: 0
                    }}
                  >
                    {deletingBatch === batch.batch_uuid
                      ? <Spinner size={14} />
                      : <Trash2 size={14} />}
                    {deletingBatch === batch.batch_uuid
                      ? 'Deleting...'
                      : 'Delete'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </>
  );
};

export default UploadInvoices;
