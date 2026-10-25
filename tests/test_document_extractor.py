"""Test extraction for PDF and DOCX, scanned document detection, and quote verification."""

import os
import pytest
from services.document_extractor import extract_document
from services.evidence_verifier import verify_findings

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def test_pdf_extraction_with_locations():
    pdf_path = os.path.join(FIXTURES_DIR, 'sample_freelance_contract.pdf')
    res = extract_document(pdf_path, 'pdf')
    assert res['error'] is None
    assert res['total_pages'] == 1
    assert len(res['sentences']) > 0
    
    # Check that sentences have page numbers (1-based) and line references
    for s in res['sentences']:
        assert s['page'] == 1
        assert s['text'] is not None


def test_docx_extraction_with_paragraphs_and_tables():
    docx_path = os.path.join(FIXTURES_DIR, 'consulting_contract.docx')
    res = extract_document(docx_path, 'docx')
    assert res['error'] is None
    assert res['total_paragraphs'] > 0
    # DOCX must not have page numbers
    for s in res['sentences']:
        assert s['page'] is None
        assert s['paragraph'] is not None or 'Table' in str(s.get('paragraph_reference', ''))


def test_scanned_pdf_rejection():
    scanned_path = os.path.join(FIXTURES_DIR, 'scanned_empty.pdf')
    res = extract_document(scanned_path, 'pdf')
    assert res.get('error') is not None
    assert 'OCR is required' in res['error']


def test_encrypted_pdf_rejection():
    enc_path = os.path.join(FIXTURES_DIR, 'encrypted.pdf')
    res = extract_document(enc_path, 'pdf')
    assert res.get('error') is not None
    assert 'encrypted' in res['error'].lower()


def test_corrupt_pdf_rejection():
    corrupt_path = os.path.join(FIXTURES_DIR, 'corrupt.pdf')
    res = extract_document(corrupt_path, 'pdf')
    assert res.get('error') is not None
    assert 'corrupt' in res['error'].lower() or 'could not open' in res['error'].lower()


def test_evidence_quote_verification():
    pdf_path = os.path.join(FIXTURES_DIR, 'sample_freelance_contract.pdf')
    extraction = extract_document(pdf_path, 'pdf')
    
    # Verbatim quote present
    findings = [
        {
            'evidence_quote': 'payment within sixty (60) days of invoice',
            'page_number': 1,
            'result_type': 'conflict'
        },
        {
            'evidence_quote': 'THIS SENTENCE DOES NOT EXIST ANYWHERE IN THE CONTRACT',
            'page_number': 1,
            'result_type': 'conflict'
        }
    ]
    
    verified = verify_findings(findings, extraction, pdf_path, 'pdf')
    assert verified[0]['verification_status'] == 'verified'
    assert verified[1]['verification_status'] == 'unable_to_verify'
