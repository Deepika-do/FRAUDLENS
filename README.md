# FraudLens — GST Invoice Fraud Detection System

## Quick Start

### Prerequisites
- Python 3.10+ 
- Node.js 18+

### 1. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Start the backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API runs at http://localhost:8000  
Interactive API docs: http://localhost:8000/api/docs

### 3. Install frontend dependencies

```bash
cd frontend
npm install
```

### 4. Start the frontend

```bash
cd frontend
npm run dev
```

The app runs at http://localhost:5173

---

## Architecture

```
Fraudlens/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application & routes
│   │   ├── database.py          # SQLAlchemy models (SQLite)
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── processor.py         # Batch processing engine
│   │   ├── detection/
│   │   │   ├── gst_validation.py        # Technique 1
│   │   │   ├── duplicate_detection.py   # Technique 2
│   │   │   ├── zscore_analysis.py       # Technique 3
│   │   │   ├── supplier_behavior.py     # Technique 4
│   │   │   ├── transaction_frequency.py # Technique 5
│   │   │   ├── isolation_forest.py      # Technique 6
│   │   │   └── risk_classifier.py       # Classification engine
│   │   └── parsers/
│   │       └── invoice_parser.py        # PDF/CSV/JSON/XLSX/TXT parser
│   ├── tests/
│   │   └── test_detection.py            # Pytest test suite
│   ├── data/
│   │   └── synthetic_invoices.csv       # Labelled synthetic test data
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.tsx
        ├── api.ts               # Typed API client
        ├── components/
        │   ├── Sidebar.tsx
        │   ├── InvoiceDetailPanel.tsx
        │   └── ui.tsx
        └── pages/
            ├── Dashboard.tsx
            ├── UploadInvoices.tsx
            └── FraudResults.tsx
```

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## Supported Upload Formats
| Format | Notes |
|--------|-------|
| CSV | Headers should match field names (invoice_number, supplier_gstin, etc.) |
| XLSX / XLS | Same header convention as CSV |
| JSON | List of invoice objects, or `{"invoices": [...]}` envelope |
| PDF | Text-extractable PDFs only; scanned images not supported |
| TXT | CSV-style or labeled fields |

Image files (JPG, PNG, etc.) are **not** supported.

## Six Detection Techniques
1. **GST Validation** — GSTIN format, checksum, and tax calculation consistency
2. **Duplicate Detection** — Within-batch and cross-batch duplicate matching
3. **Z-Score Analysis** — Statistical outlier detection on invoice amounts
4. **Supplier Behaviour Analysis** — Deviation from established supplier patterns
5. **Transaction Frequency** — Spike detection in submission volume
6. **Isolation Forest (ML)** — scikit-learn anomaly detection on numerical features

## Important Notes
- The database persists in `backend/fraudlens.db` (SQLite).
- Results reflect the **latest successfully processed batch** on the dashboard and fraud results pages.
- Historical invoices are retained and used as comparison baselines for detection techniques.
- This system identifies *potentially suspicious* invoices for human review. It does not determine fraud definitively.
- Synthetic test data in `data/synthetic_invoices.csv` is clearly labeled and must not be treated as real invoices.
