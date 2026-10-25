"""Comprehensive test suite for different agreement types.

Tests accuracy and reliability across:
1. Non-Disclosure Agreements (NDA)
2. Software License Agreements (SLA)
3. Master Services Agreements (MSA) / Consulting Contracts
4. Vendor Procurement Agreements
5. Edge cases in number parsing, abbreviation protection, and jurisdiction aliases
"""

import pytest
from services.clause_detector import (
    parse_number,
    detect_payment,
    detect_renewal,
    detect_liability,
    detect_termination,
    detect_jurisdiction,
    detect_custom,
    detect_all,
)
from services.document_extractor import _split_into_sentences_raw
from services.risk_engine import assess_risks
from services.evidence_verifier import _normalized_match, _normalize_whitespace


def test_abbreviation_protected_splitting():
    """Verify that sentence splitting does not fragment legal citations or corporate abbreviations."""
    sample_text = (
        "Client shall pay ABC Co., Ltd. within thirty (30) days of invoice date. "
        "Vendor Inc. shall deliver deliverables pursuant to Sec. 4.2 of Schedule A. "
        "Any dispute shall be referred to arbitration in Chennai, India vs. foreign litigation."
    )
    sentences = _split_into_sentences_raw(sample_text)
    assert len(sentences) == 3
    assert "ABC Co., Ltd." in sentences[0]
    assert "Sec. 4.2" in sentences[1]
    assert "vs. foreign litigation" in sentences[2]


def test_extended_number_parsing():
    """Verify parsing of hyphenated numbers, compounds, and ordinals."""
    assert parse_number("thirty-five") == 35
    assert parse_number("forty-five (45) days") == 45
    assert parse_number("within seventy-five days") == 75
    assert parse_number("payable on the thirtieth day") == 30
    assert parse_number("sixtieth (60th) calendar day") == 60


def test_nda_agreement_clauses():
    """Test clause detection in a Non-Disclosure Agreement (NDA)."""
    sentences = [
        {
            'text': 'This Non-Disclosure Agreement shall govern confidential disclosures between the parties.',
            'page': 1,
            'clause_title': '1. Purpose'
        },
        {
            'text': 'Recipient shall maintain confidentiality of Confidential Information for a period of five (5) years from disclosure.',
            'page': 1,
            'clause_title': '3. Non-Disclosure'
        },
        {
            'text': 'This Agreement shall be governed by the laws of Singapore and subject to arbitration administered by the Singapore International Arbitration Centre (SIAC).',
            'page': 2,
            'clause_title': '7. Governing Law'
        }
    ]
    
    # Test jurisdiction detection in NDA
    config_jurisdiction = {
        'preferred_jurisdiction': 'Singapore',
        'accepted_jurisdictions': ['Singapore', 'India']
    }
    findings = detect_jurisdiction(sentences, config_jurisdiction)
    assert len(findings) >= 1
    assert findings[0]['result_type'] == 'match'
    assert 'Singapore' in findings[0]['condition_detected']

    # Test custom NDA policy (e.g. non-compete prohibited in mutual NDA)
    config_custom = {
        'match_type': 'must_not_contain',
        'keywords': 'non-compete, covenant not to compete',
        'severity': 'high',
        'description': 'NDAs must not sneak in non-compete covenants'
    }
    custom_findings = detect_custom(sentences, config_custom, 'NDA Purity')
    # No non-compete in clean NDA -> 0 conflicts
    assert len(custom_findings) == 0


def test_software_license_agreement_sla():
    """Test clause detection in a Software License Agreement / SaaS SLA."""
    sentences = [
        {
            'text': 'The subscription term shall automatically renew for successive terms of 12 months unless either party provides written notice at least sixty (60) days prior.',
            'page': 1,
            'clause_title': 'Term & Renewal'
        },
        {
            'text': 'Vendor total aggregate liability under this Agreement shall not exceed the total fees paid by Customer during the preceding twelve (12) months.',
            'page': 2,
            'clause_title': 'Limitation of Liability'
        },
        {
            'text': 'Customer may terminate this Agreement for convenience upon ninety (90) days advance written notice to Vendor.',
            'page': 2,
            'clause_title': 'Termination'
        }
    ]

    # Renewal test: auto renewal allowed vs not allowed
    renewal_policy_disallowed = {
        'auto_renewal_allowed': False,
        'max_renewal_term_months': 12,
        'min_cancellation_notice_days': 30
    }
    renewal_findings = detect_renewal(sentences, renewal_policy_disallowed)
    assert len(renewal_findings) == 1
    assert renewal_findings[0]['result_type'] == 'conflict'
    assert 'Auto-renewal' in renewal_findings[0]['condition_detected']

    # Liability test: capped liability
    liability_policy = {
        'unlimited_liability_allowed': False,
        'require_liability_cap': True
    }
    liability_findings = detect_liability(sentences, liability_policy)
    assert len(liability_findings) == 1
    assert liability_findings[0]['result_type'] == 'match'

    # Termination test: 90 days notice with 30-day min policy
    termination_policy = {
        'min_notice_days': 30,
        'flag_one_sided_termination': True
    }
    termination_findings = detect_termination(sentences, termination_policy)
    assert len(termination_findings) == 1
    assert '90-day notice' in termination_findings[0]['condition_detected']


def test_vendor_procurement_payment_terms():
    """Test payment term variations in vendor and freelance agreements."""
    # Net-45 term (hyphenated)
    s1 = [{'text': 'Invoices shall be payable on a Net-45 basis upon receipt of undisputed invoice.', 'page': 1}]
    f1 = detect_payment(s1, {'max_payment_days': 30})
    assert len(f1) == 1
    assert f1[0]['result_type'] == 'conflict'
    assert '45' in f1[0]['condition_detected']

    # Immediate payment upon receipt
    s2 = [{'text': 'All invoiced fees are due immediately upon receipt of invoice.', 'page': 1}]
    f2 = detect_payment(s2, {'max_payment_days': 30})
    assert len(f2) == 1
    assert f2[0]['result_type'] == 'match'

    # Ambiguous discretionary cycle
    s3 = [{'text': 'Remittance will occur in accordance with Client internal billing cycle.', 'page': 1}]
    f3 = detect_payment(s3, {'max_payment_days': 30})
    assert len(f3) == 1
    assert f3[0]['result_type'] == 'uncertain'


def test_evidence_quote_smart_punctuation_normalization():
    """Verify that typographical quotes and dashes match correctly against source text."""
    doc_text = 'The total liability of ABC Co. “shall not exceed” the fees paid — under any circumstances.'
    quote_clean = 'The total liability of ABC Co. "shall not exceed" the fees paid - under any circumstances.'
    assert _normalized_match(quote_clean, doc_text)


def test_master_services_agreement_msa():
    """Test clause detection in a Master Services Agreement (MSA)."""
    sentences = [
        {
            'text': 'Either party may terminate this Agreement immediately upon written notice in the event of insolvency or material breach.',
            'page': 1,
            'clause_title': 'Section 8: Termination'
        },
        {
            'text': 'The parties submit to the exclusive jurisdiction of the High Court of Judicature at Madras, Chennai.',
            'page': 2,
            'clause_title': 'Section 12: Jurisdiction'
        }
    ]

    # Termination: immediate termination for breach
    term_policy = {'min_notice_days': 30, 'flag_one_sided_termination': True}
    findings = detect_termination(sentences, term_policy)
    assert len(findings) == 1
    assert '0-day notice' in findings[0]['condition_detected']
    assert findings[0]['result_type'] == 'conflict'

    # Jurisdiction: Chennai / Madras alias
    jurisdiction_policy = {
        'preferred_jurisdiction': 'India',
        'accepted_jurisdictions': ['India', 'Tamil Nadu']
    }
    j_findings = detect_jurisdiction(sentences, jurisdiction_policy)
    assert len(j_findings) >= 1
    assert j_findings[0]['result_type'] == 'match'
    assert 'Tamil Nadu, India' in j_findings[0]['condition_detected']


def test_consulting_agreement_custom_rules():
    """Test policy verification for consulting agreements with custom IP and non-solicitation rules."""
    sentences = [
        {
            'text': 'Consultant agrees to assign all intellectual property and inventions to Client as work-for-hire.',
            'page': 1,
            'clause_title': 'Intellectual Property'
        },
        {
            'text': 'Consultant shall not solicit any employee of Client for a period of twelve (12) months following termination.',
            'page': 2,
            'clause_title': 'Non-Solicitation'
        }
    ]

    # Custom rule: Must not contain non-solicitation
    rule_no_solicit = {
        'match_type': 'must_not_contain',
        'keywords': 'solicit, non-solicitation',
        'severity': 'medium',
        'description': 'Protect freelancer freedom to recruit'
    }
    f_solicit = detect_custom(sentences, rule_no_solicit, 'No Solicitation Rule')
    assert len(f_solicit) == 1
    assert f_solicit[0]['result_type'] == 'conflict'
    assert 'Prohibited term found' in f_solicit[0]['condition_detected']

    # Custom rule: Must contain work-for-hire
    rule_work_for_hire = {
        'match_type': 'must_contain',
        'keywords': 'work-for-hire',
        'severity': 'high',
        'description': 'Ensure IP assignment is explicit'
    }
    f_ip = detect_custom(sentences, rule_work_for_hire, 'IP Assignment Rule')
    # Since 'work-for-hire' is present in sentences, 0 missing conflicts should be raised
    assert len(f_ip) == 0
