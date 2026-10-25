"""End-to-end live server validation script."""

import time
import threading
import requests
from app import app
from database import init_db, seed_default_policies, seed_default_settings

def run_server():
    app.run(host='127.0.0.1', port=5005, debug=False, use_reloader=False)

def main():
    init_db()
    seed_default_policies()
    seed_default_settings()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    base_url = 'http://127.0.0.1:5005'
    print(f"Connecting to live server at {base_url}...")

    # 1. UI Pages
    for path in ['/', '/policies', '/results', '/settings']:
        r = requests.get(f"{base_url}{path}")
        assert r.status_code == 200, f"Failed GET {path}: {r.status_code}"
        assert 'ClauseLens' in r.text
        print(f"PASS: Page {path} rendered HTTP 200")

    # 2. Health
    r = requests.get(f"{base_url}/api/health")
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'
    print("PASS: /api/health returned OK")

    # 3. Demo contract workflow
    demo_r = requests.post(f"{base_url}/api/contracts/demo")
    assert demo_r.status_code == 200
    demo_file = demo_r.json()['file']
    assert demo_file['is_sample'] is True
    print("PASS: /api/contracts/demo loaded sample contract")

    analyse_r = requests.post(f"{base_url}/api/contracts/analyse", json=demo_file)
    assert analyse_r.status_code == 200
    res_data = analyse_r.json()
    analysis_id = res_data['analysis_id']
    assert res_data['summary']['conflicts'] == 4
    print(f"PASS: /api/contracts/analyse produced 4 conflicts for demo (ID: {analysis_id})")

    # 4. Results & Findings
    det_r = requests.get(f"{base_url}/api/analyses/{analysis_id}")
    assert det_r.status_code == 200
    findings = det_r.json()['findings']
    assert len(findings) > 0
    first_id = findings[0]['id']
    print(f"PASS: /api/analyses/{analysis_id} retrieved {len(findings)} findings")

    # 5. Patch review
    rev_r = requests.patch(f"{base_url}/api/findings/{first_id}/review", json={
        'review_status': 'reviewed',
        'review_note': 'Live test note verified.'
    })
    assert rev_r.status_code == 200
    print("PASS: /api/findings/{id}/review updated status persistently")

    # 6. JSON Export
    json_r = requests.get(f"{base_url}/api/analyses/{analysis_id}/export.json")
    assert json_r.status_code == 200
    assert json_r.headers['Content-Type'] == 'application/json'
    print("PASS: /api/analyses/{id}/export.json succeeded")

    # 7. PDF Export
    pdf_r = requests.get(f"{base_url}/api/analyses/{analysis_id}/export.pdf")
    assert pdf_r.status_code == 200
    assert pdf_r.headers['Content-Type'] == 'application/pdf'
    assert len(pdf_r.content) > 1000
    print("PASS: /api/analyses/{id}/export.pdf generated valid PDF report")

    # 8. Page preview PNG with highlight
    png_r = requests.get(f"{base_url}/api/analyses/{analysis_id}/page/1.png?finding_id={first_id}")
    assert png_r.status_code == 200
    assert png_r.headers['Content-Type'] == 'image/png'
    assert len(png_r.content) > 5000
    print("PASS: /api/analyses/{id}/page/1.png rendered highlighted page image")

    print("\nALL LIVE SERVER TESTS PASSED SUCCESSFULLY!")
    import os
    os._exit(0)

if __name__ == '__main__':
    main()
