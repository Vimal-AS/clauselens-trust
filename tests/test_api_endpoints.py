"""Test Flask REST API endpoints, validation, and exports."""

import os
import json
import pytest
from app import app
from database import init_db, seed_default_policies, seed_default_settings

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


@pytest.fixture
def client():
    app.config['TESTING'] = True
    init_db()
    seed_default_policies()
    seed_default_settings()
    with app.test_client() as client:
        yield client


def test_health_check(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    assert res.json['status'] == 'ok'


def test_policies_crud(client):
    # GET policies
    res = client.get('/api/policies')
    assert res.status_code == 200
    policies = res.json['policies']
    assert len(policies) >= 5
    
    # PUT update payment policy
    payment_policy = next(p for p in policies if p['category'] == 'payment')
    payment_policy['config']['max_payment_days'] = 45
    
    put_res = client.put('/api/policies', json={'policies': [payment_policy]})
    assert put_res.status_code == 200
    
    # Verify update persisted
    verify_res = client.get('/api/policies')
    updated = next(p for p in verify_res.json['policies'] if p['category'] == 'payment')
    assert updated['config']['max_payment_days'] == 45
    
    # Restore defaults
    restore_res = client.post('/api/policies/restore-defaults')
    assert restore_res.status_code == 200
    
    # Verify restored
    final_res = client.get('/api/policies')
    restored = next(p for p in final_res.json['policies'] if p['category'] == 'payment')
    assert restored['config']['max_payment_days'] == 30


def test_upload_invalid_file_type(client):
    jpg_path = os.path.join(FIXTURES_DIR, 'invalid_contract.jpg')
    with open(jpg_path, 'rb') as f:
        res = client.post('/api/contracts/upload', data={'file': (f, 'invalid_contract.jpg')})
    assert res.status_code == 400
    assert 'not supported' in res.json['error']


def test_upload_encrypted_file(client):
    enc_path = os.path.join(FIXTURES_DIR, 'encrypted.pdf')
    with open(enc_path, 'rb') as f:
        res = client.post('/api/contracts/upload', data={'file': (f, 'encrypted.pdf')})
    assert res.status_code == 400
    assert 'encrypted' in res.json['error'].lower()


def test_upload_corrupt_file(client):
    corrupt_path = os.path.join(FIXTURES_DIR, 'corrupt.pdf')
    with open(corrupt_path, 'rb') as f:
        res = client.post('/api/contracts/upload', data={'file': (f, 'corrupt.pdf')})
    assert res.status_code == 400


def test_demo_and_analysis_workflow(client):
    # 1. Load demo contract
    demo_res = client.post('/api/contracts/demo')
    assert demo_res.status_code == 200
    demo_file = demo_res.json['file']
    assert demo_file['is_sample'] is True

    # 2. Run analysis
    analyse_res = client.post('/api/contracts/analyse', json=demo_file)
    assert analyse_res.status_code == 200
    data = analyse_res.json
    analysis_id = data['analysis_id']
    assert data['summary']['conflicts'] == 4

    # 3. Get analysis detail
    detail_res = client.get(f'/api/analyses/{analysis_id}')
    assert detail_res.status_code == 200
    assert detail_res.json['analysis']['is_sample'] is True
    findings = detail_res.json['findings']
    assert len(findings) > 0

    # 4. Filter findings by severity=high
    filter_res = client.get(f'/api/analyses/{analysis_id}/findings?severity=high')
    assert filter_res.status_code == 200
    for f in filter_res.json['findings']:
        assert f['severity'] == 'high'

    # 5. Patch review status
    first_id = findings[0]['id']
    patch_res = client.patch(f'/api/findings/{first_id}/review', json={
        'review_status': 'reviewed',
        'review_note': 'Discussed with client.'
    })
    assert patch_res.status_code == 200

    # 6. JSON Export
    json_export = client.get(f'/api/analyses/{analysis_id}/export.json')
    assert json_export.status_code == 200
    assert json_export.content_type == 'application/json'
    export_data = json.loads(json_export.data)
    assert export_data['analysis_id'] == analysis_id
    assert 'disclaimer' in export_data

    # 7. PDF Export
    pdf_export = client.get(f'/api/analyses/{analysis_id}/export.pdf')
    assert pdf_export.status_code == 200
    assert pdf_export.content_type == 'application/pdf'
    assert len(pdf_export.data) > 1000

    # 7b. Filtered Exports (JSON & PDF)
    filtered_json = client.get(f'/api/analyses/{analysis_id}/export.json?severity=high')
    assert filtered_json.status_code == 200
    fj_data = json.loads(filtered_json.data)
    assert all(f['severity'] == 'high' for f in fj_data['findings'])

    filtered_pdf = client.get(f'/api/analyses/{analysis_id}/export.pdf?severity=high')
    assert filtered_pdf.status_code == 200
    assert len(filtered_pdf.data) > 1000

    # 8. Page Image Preview
    page_img = client.get(f'/api/analyses/{analysis_id}/page/1.png?finding_id={first_id}')
    assert page_img.status_code == 200
    assert page_img.content_type == 'image/png'
    assert len(page_img.data) > 5000

    # 9. Plain Text View
    text_res = client.get(f'/api/analyses/{analysis_id}/text')
    assert text_res.status_code == 200
    text_data = text_res.json
    assert len(text_data['full_text']) > 50
    assert text_data['word_count'] > 10
    assert 'Payment' in text_data['full_text']


def test_demo_list_and_docx_demo(client):
    # Check demo list returns all registered demo documents
    list_res = client.get('/api/contracts/demo-list')
    assert list_res.status_code == 200
    demos = list_res.json['demos']
    assert len(demos) >= 5
    
    # Load a DOCX demo (Vendor supply agreement)
    docx_demo = client.post('/api/contracts/demo', json={'demo_id': 'vendor_supply'})
    assert docx_demo.status_code == 200
    f = docx_demo.json['file']
    assert f['file_type'] == 'docx'
    assert f['is_sample'] is True

    # Analyse the DOCX demo
    analyse_docx = client.post('/api/contracts/analyse', json=f)
    assert analyse_docx.status_code == 200
    docx_analysis_id = analyse_docx.json['analysis_id']

    # Get plain text of the DOCX demo
    docx_text_res = client.get(f'/api/analyses/{docx_analysis_id}/text')
    assert docx_text_res.status_code == 200
    assert 'Vendor Supply Agreement' in docx_text_res.json['full_text']



def test_settings_and_data_deletion(client):
    # Update settings
    put_res = client.put('/api/settings', json={
        'settings': {'theme': 'dark', 'language': 'ta'}
    })
    assert put_res.status_code == 200
    
    get_res = client.get('/api/settings')
    assert get_res.json['settings']['theme'] == 'dark'
    assert get_res.json['settings']['language'] == 'ta'
    
    # Delete all data
    del_res = client.post('/api/settings/delete-data')
    assert del_res.status_code == 200
    
    # Check analyses are empty
    list_res = client.get('/api/analyses')
    assert len(list_res.json['analyses']) == 0
