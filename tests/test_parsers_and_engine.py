"""Test number parsing, detectors, and risk engine severity scoring."""

import pytest
from services.clause_detector import parse_number, detect_payment, detect_renewal, detect_liability, detect_jurisdiction, detect_termination, detect_custom
from services.risk_engine import assess_risks


def test_parse_number():
    assert parse_number("30") == 30
    assert parse_number("sixty (60)") == 60
    assert parse_number("forty-five") == 45
    assert parse_number("thirty(30)") == 30
    assert parse_number("one hundred twenty") == 120
    assert parse_number("90 days") == 90
    assert parse_number(None) is None
    assert parse_number("") is None


def test_detect_payment_conflict_and_severity():
    config = {'max_payment_days': 30}
    sentences = [
        {'text': 'Client shall make payment within sixty (60) days of invoice.', 'page': 1, 'line_ref': 2, 'clause_title': '2. Fees'}
    ]
    findings = detect_payment(sentences, config)
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'conflict'
    assert '60' in findings[0]['condition_detected']

    # Assess severity: >15 days over 30 is High
    policies = [{'category': 'payment', 'config': config}]
    assessed = assess_risks(findings, policies)
    assert assessed[0]['severity'] == 'high'


def test_detect_payment_medium_severity():
    config = {'max_payment_days': 30}
    sentences = [
        {'text': 'Payment is due within 40 calendar days following receipt.', 'page': 1, 'line_ref': 4}
    ]
    findings = detect_payment(sentences, config)
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'conflict'
    policies = [{'category': 'payment', 'config': config}]
    assessed = assess_risks(findings, policies)
    # 40 - 30 = 10 days over <= 15 days -> Medium
    assert assessed[0]['severity'] == 'medium'


def test_detect_payment_ambiguous():
    config = {'max_payment_days': 30}
    sentences = [
        {'text': 'The fee will be payable within a reasonable time upon invoicing.', 'page': 1}
    ]
    findings = detect_payment(sentences, config)
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'uncertain'
    policies = [{'category': 'payment', 'config': config}]
    assessed = assess_risks(findings, policies)
    assert assessed[0]['severity'] == 'medium'


def test_detect_renewal_auto_conflict():
    config = {
        'auto_renewal_allowed': False,
        'max_renewal_term_months': 12,
        'min_cancellation_notice_days': 30
    }
    sentences = [
        {'text': 'This contract will automatically renew for successive terms of 24 months unless notice is given 90 days prior.', 'page': 1}
    ]
    findings = detect_renewal(sentences, config)
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'conflict'
    policies = [{'category': 'renewal', 'config': config}]
    assessed = assess_risks(findings, policies)
    # Notice >60 days or term >12 -> High
    assert assessed[0]['severity'] == 'high'


def test_detect_liability_unlimited():
    config = {'unlimited_liability_allowed': False, 'require_liability_cap': True}
    sentences = [
        {'text': "Notwithstanding anything to the contrary, Vendor's liability shall be unlimited.", 'page': 1}
    ]
    findings = detect_liability(sentences, config)
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'conflict'
    policies = [{'category': 'liability', 'config': config}]
    assessed = assess_risks(findings, policies)
    assert assessed[0]['severity'] == 'high'


def test_detect_liability_cap_match():
    config = {'unlimited_liability_allowed': False, 'require_liability_cap': True}
    sentences = [
        {'text': 'The total liability of Vendor shall not exceed the amounts paid under this Agreement.', 'page': 1}
    ]
    findings = detect_liability(sentences, config)
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'match'
    policies = [{'category': 'liability', 'config': config}]
    assessed = assess_risks(findings, policies)
    assert assessed[0]['severity'] == 'low'


def test_detect_jurisdiction_accepted_and_conflict():
    config = {'preferred_jurisdiction': 'India', 'accepted_jurisdictions': ['India', 'Tamil Nadu']}
    
    # Conflict: Singapore
    s1 = [{'text': 'This agreement is governed by the laws of Singapore.', 'page': 1}]
    f1 = detect_jurisdiction(s1, config)
    assert len(f1) == 1
    assert f1[0]['result_type'] == 'conflict'
    assert f1[0]['severity'] is None
    assessed = assess_risks(f1, [{'category': 'jurisdiction', 'config': config}])
    assert assessed[0]['severity'] == 'medium'

    # Match: Chennai
    s2 = [{'text': 'The courts of Chennai, India shall have exclusive jurisdiction.', 'page': 1}]
    f2 = detect_jurisdiction(s2, config)
    assert len(f2) == 1
    assert f2[0]['result_type'] == 'match'


def test_detect_termination_one_sided():
    config = {'min_notice_days': 30, 'flag_one_sided_termination': True}
    sentences = [
        {'text': 'The Company may terminate this Agreement at any time in its sole discretion upon 10 days notice.', 'page': 1}
    ]
    findings = detect_termination(sentences, config)
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'conflict'
    assert 'One-sided' in findings[0]['condition_detected']
    policies = [{'category': 'termination', 'config': config}]
    assessed = assess_risks(findings, policies)
    assert assessed[0]['severity'] == 'medium'


def test_custom_policy_must_not_contain():
    config = {
        'match_type': 'must_not_contain',
        'keywords': 'non-compete, covenant not to compete',
        'severity': 'high',
        'description': 'Protect freelancer client freedom',
        'expected_condition': 'No non-compete'
    }
    sentences = [
        {'text': 'Contractor agrees to a strict non-compete clause for 2 years following termination.', 'page': 2}
    ]
    findings = detect_custom(sentences, config, 'Non-Compete Policy')
    assert len(findings) == 1
    assert findings[0]['result_type'] == 'conflict'
    assert findings[0]['severity'] == 'high'
