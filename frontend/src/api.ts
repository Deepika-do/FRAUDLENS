 
/**
 * Centralized API client.
 */
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  withCredentials: true,
});

export interface BatchSummary {
  id: number;
  batch_uuid: string;
  uploaded_at: string;
  original_filename: string | null;
  status: string;
  total_invoices: number;
  flagged_invoices: number;
  invoice_period_start: string | null;
  invoice_period_end: string | null;
  error_message: string | null;
  is_latest: boolean;
}

export interface DashboardData {
  invoices_scanned: number;
  needs_review: number;
  latest_batch: BatchSummary | null;
  monthly_chart: Array<{ month: string; total: number; flagged: number }>;
}

export interface InvoiceListItem {
  id: number;
  invoice_number: string | null;
  invoice_date: string | null;
  supplier_name: string | null;
  supplier_gstin: string | null;
  total_amount: string | null;
  classification: string;
  risk_level: string;
  flagged_techniques_count: number;
}

export interface TechniqueFinding {
  id: number;
  technique: string;
  status: string;
  severity: string | null;
  reason: string | null;
  evidence: Record<string, unknown>;
}

export interface InvoiceDetail {
  id: number;
  batch_id: number;
  invoice_number: string | null;
  invoice_date: string | null;
  invoice_month: string | null;
  supplier_name: string | null;
  supplier_gstin: string | null;
  recipient_name: string | null;
  recipient_gstin: string | null;
  taxable_amount: string | null;
  gst_rate: string | null;
  cgst: string | null;
  sgst: string | null;
  igst: string | null;
  total_gst: string | null;
  total_amount: string | null;
  place_of_supply: string | null;
  source_filename: string | null;
  classification: string;
  risk_level: string;
  flagged_techniques_count: number;
  assessment_summary: string | null;
  findings: TechniqueFinding[];
}

export interface InvoiceListResponse {
  items: InvoiceListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface UploadResponse {
  batch_uuid: string;
  status: string;
  message: string;
  total_invoices: number;
  flagged_invoices: number;
  errors: string[];
}

export const getDashboard = () =>
  api.get<DashboardData>('/dashboard').then(r => r.data);

export const uploadFile = (file: File) => {
  const form = new FormData();
  form.append('file', file);

  return api.post<UploadResponse>('/upload', form).then(r => r.data);
};

export const getResults = (params: {
  page?: number;
  page_size?: number;
  search?: string;
  classification?: string;
  risk_level?: string;
  sort_by?: string;
  sort_dir?: string;
}) =>
  api.get<InvoiceListResponse>('/results', { params }).then(r => r.data);

export const getInvoiceDetail = (id: number) =>
  api.get<InvoiceDetail>(`/results/${id}`).then(r => r.data);

export const getBatches = () =>
  api.get<BatchSummary[]>('/batches').then(r => r.data);

export const deleteBatch = (batchUuid: string) =>
  api.delete(`/batches/${batchUuid}`).then(r => r.data);

export default api;
