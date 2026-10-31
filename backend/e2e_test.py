"""
End-to-end integration test: uploads synthetic CSV and verifies the full pipeline.
Run with: python e2e_test.py
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000/api"

def test_health():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    print("✓ Health check passed")

def test_dashboard_empty():
    r = requests.get(f"{BASE_URL}/dashboard")
    assert r.status_code == 200
    data = r.json()
    print(f"✓ Dashboard API works (invoices_scanned={data['invoices_scanned']})")
    return data

def test_upload_csv():
    with open("data/synthetic_invoices.csv", "rb") as f:
        r = requests.post(
            f"{BASE_URL}/upload",
            files={"file": ("synthetic_invoices.csv", f, "text/csv")}
        )
    assert r.status_code in (200, 202), f"Upload failed: {r.status_code} {r.text}"
    data = r.json()
    print(f"✓ Upload succeeded: {data['total_invoices']} invoices, {data['flagged_invoices']} flagged")
    print(f"  Status: {data['status']}")
    if data.get('errors'):
        print(f"  Warnings: {data['errors'][:3]}")
    return data

def test_dashboard_after_upload():
    r = requests.get(f"{BASE_URL}/dashboard")
    assert r.status_code == 200
    data = r.json()
    assert data['invoices_scanned'] > 0, "Dashboard shows 0 invoices after upload"
    assert data['latest_batch'] is not None
    assert len(data['monthly_chart']) > 0, "Monthly chart is empty"
    print(f"✓ Dashboard updated: {data['invoices_scanned']} scanned, {data['needs_review']} need review")
    print(f"  Monthly chart months: {[m['month'] for m in data['monthly_chart']]}")
    return data

def test_results():
    r = requests.get(f"{BASE_URL}/results")
    assert r.status_code == 200
    data = r.json()
    assert data['total'] > 0, "Fraud results page is empty after upload"
    print(f"✓ Results: {data['total']} invoices, page {data['page']}/{data['total_pages']}")
    
    # Verify all fields are present
    first = data['items'][0]
    assert 'invoice_number' in first
    assert 'classification' in first
    assert 'risk_level' in first
    print(f"  First: {first['invoice_number']} | {first['classification']} | {first['risk_level']} Risk")
    return data

def test_invoice_detail(invoice_id: int):
    r = requests.get(f"{BASE_URL}/results/{invoice_id}")
    assert r.status_code == 200
    data = r.json()
    assert len(data['findings']) == 6, f"Expected 6 technique findings, got {len(data['findings'])}"
    techniques = {f['technique'] for f in data['findings']}
    expected = {'gst_validation','duplicate_detection','zscore_analysis',
                'supplier_behavior','transaction_frequency','isolation_forest'}
    assert techniques == expected, f"Missing techniques: {expected - techniques}"
    print(f"✓ Invoice detail: all 6 techniques present")
    for f in data['findings']:
        print(f"  {f['technique']:30s} → {f['status']:20s} (severity: {f['severity']})")

def test_search_filter():
    r = requests.get(f"{BASE_URL}/results", params={"search": "Acme"})
    assert r.status_code == 200
    data = r.json()
    print(f"✓ Search 'Acme': {data['total']} results")
    
    r = requests.get(f"{BASE_URL}/results", params={"classification": "Suspicious"})
    data = r.json()
    print(f"✓ Filter Suspicious: {data['total']} results")

def test_unsupported_format():
    r = requests.post(
        f"{BASE_URL}/upload",
        files={"file": ("image.png", b"fake image data", "image/png")}
    )
    assert r.status_code == 400, f"Expected 400 for .png, got {r.status_code}"
    print(f"✓ Unsupported format correctly rejected")

def test_second_upload_history():
    """Upload a second batch and verify historical data is preserved."""
    import io
    csv2 = (
        "invoice_number,invoice_date,supplier_name,supplier_gstin,total_amount,gst_rate,taxable_amount\n"
        "INV-H001,2024-07-15,Acme Supplies Pvt Ltd,27AABCU9603R1ZP,15000,18,12711.86\n"
        "INV-H002,2024-07-20,Delta Wholesalers,07AAACW4404D1ZB,8500,12,7589.29\n"
    )
    r = requests.post(
        f"{BASE_URL}/upload",
        files={"file": ("batch2.csv", csv2.encode(), "text/csv")}
    )
    assert r.status_code in (200, 202)
    data = r.json()
    print(f"✓ Second batch uploaded: {data['total_invoices']} invoices")
    
    # Dashboard should show latest batch (2 invoices) not all 14
    dash = requests.get(f"{BASE_URL}/dashboard").json()
    assert dash['invoices_scanned'] == 2, \
        f"Dashboard should show 2 (latest batch), got {dash['invoices_scanned']}"
    
    # Monthly chart should show BOTH months
    months = [m['month'] for m in dash['monthly_chart']]
    assert len(months) >= 2, f"Historical chart should have ≥2 months, has {months}"
    print(f"✓ Historical preservation: chart has {len(months)} months: {months}")

if __name__ == "__main__":
    print("=" * 60)
    print("FraudLens End-to-End Integration Test")
    print("=" * 60)
    
    failures = []
    tests = [
        ("Health check", test_health),
        ("Dashboard (empty)", test_dashboard_empty),
        ("Upload CSV", test_upload_csv),
        ("Dashboard (post-upload)", test_dashboard_after_upload),
        ("Results list", test_results),
        ("Unsupported format", test_unsupported_format),
        ("Second batch + history", test_second_upload_history),
    ]
    
    results_data = None
    for name, fn in tests:
        try:
            result = fn()
            if name == "Results list" and result:
                results_data = result
        except Exception as e:
            print(f"✗ {name}: {e}")
            failures.append(name)
    
    # Test invoice detail with first result
    if results_data and results_data.get('items'):
        try:
            test_invoice_detail(results_data['items'][0]['id'])
            test_search_filter()
        except Exception as e:
            print(f"✗ Invoice detail: {e}")
            failures.append("Invoice detail")
    
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED ✓")
