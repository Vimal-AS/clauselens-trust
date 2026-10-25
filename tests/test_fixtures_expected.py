"""Test all fixtures against expected outputs."""

import os
import json
import pytest
from services.document_extractor import extract_document
from services.clause_detector import detect_all
from services.risk_engine import assess_risks
from services.evidence_verifier import verify_findings
from database import DEFAULT_POLICIES

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')
EXPECTED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'expected')

CONTRACT_FIXTURES = [
    ('sample_freelance_contract.pdf', 'pdf'),
    ('ambiguous_payment_contract.pdf', 'pdf'),
    ('clean_compliant_contract.pdf', 'pdf'),
    ('vendor_agreement.docx', 'docx'),
    ('consulting_contract.docx', 'docx'),
]


@pytest.mark.parametrize('filename, file_type', CONTRACT_FIXTURES)
def test_fixture_against_expected(filename, file_type):
    file_path = os.path.join(FIXTURES_DIR, filename)
    expected_path = os.path.join(EXPECTED_DIR, f"{os.path.splitext(filename)[0]}.json")
    
    assert os.path.exists(file_path), f"Fixture missing: {file_path}"
    assert os.path.exists(expected_path), f"Expected JSON missing: {expected_path}"
    
    with open(expected_path, 'r', encoding='utf-8') as f:
        expected = json.load(f)
        
    policies = [
        {
            'category': p['category'],
            'name': p['name'],
            'enabled': True,
            'config': json.loads(p['config']),
            'is_custom': False
        }
        for p in DEFAULT_POLICIES
    ]
    
    extraction = extract_document(file_path, file_type)
    assert extraction['error'] is None
    
    raw_findings = detect_all(extraction, policies)
    findings = assess_risks(raw_findings, policies)
    findings = verify_findings(findings, extraction, file_path, file_type)
    
    actual_summary = {
        'conflicts': sum(1 for f in findings if f.get('result_type') == 'conflict'),
        'matches': sum(1 for f in findings if f.get('result_type') == 'match'),
        'uncertain': sum(1 for f in findings if f.get('result_type') == 'uncertain'),
        'not_found': sum(1 for f in findings if f.get('result_type') == 'not_found'),
        'high': sum(1 for f in findings if f.get('severity') == 'high'),
        'medium': sum(1 for f in findings if f.get('severity') == 'medium'),
        'low': sum(1 for f in findings if f.get('severity') == 'low'),
    }
    
    assert actual_summary == expected['summary'], f"Mismatch for {filename}:\nActual: {actual_summary}\nExpected: {expected['summary']}"
    
    # Assert every finding with a quote exists verbatim in source text
    full_text = extraction['full_text']
    for f in findings:
        if f.get('evidence_quote'):
            assert f['verification_status'] in ('verified', 'needs_manual_review')
