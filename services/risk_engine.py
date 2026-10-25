"""Risk assessment engine - assigns severity to findings based on deterministic rules."""

import re

# Severity thresholds (configurable constants)
PAYMENT_MEDIUM_THRESHOLD = 15  # days over limit for Medium vs High (>15 days over is High)
RENEWAL_HIGH_NOTICE_THRESHOLD = 60  # notice days for High
JURISDICTION_SEVERITY = 'medium'


def assess_risks(findings, policies):
    """Assess and assign severity to each finding."""
    policy_map = {p['category']: p['config'] for p in policies}
    
    for finding in findings:
        if finding.get('severity'):
            continue
        
        result_type = finding.get('result_type')
        category = finding.get('category')
        
        if result_type == 'match':
            finding['severity'] = 'low'
            continue
        
        if result_type == 'not_found':
            finding['severity'] = None
            continue
        
        if result_type == 'uncertain':
            finding['severity'] = 'medium'
            continue
        
        if result_type == 'conflict':
            finding['severity'] = _assess_conflict_severity(finding, category, policy_map.get(category, {}))
    
    return findings


def _assess_conflict_severity(finding, category, config):
    condition = finding.get('condition_detected', '').lower()
    
    if category == 'payment':
        return _assess_payment_severity(finding, config)
    elif category == 'renewal':
        return _assess_renewal_severity(finding, config)
    elif category == 'liability':
        return _assess_liability_severity(finding, config)
    elif category == 'jurisdiction':
        return JURISDICTION_SEVERITY
    elif category == 'termination':
        return _assess_termination_severity(finding, config)
    elif category == 'custom':
        return finding.get('severity', 'medium')
    
    return 'medium'


def _assess_payment_severity(finding, config):
    max_days = config.get('max_payment_days', 30)
    condition = finding.get('condition_detected', '')
    
    match = re.search(r'(\d+)\s*(?:calendar\s+|business\s+)?days', condition)
    if match:
        detected_days = int(match.group(1))
        over = detected_days - max_days
        if over > PAYMENT_MEDIUM_THRESHOLD:
            return 'high'
        elif over > 0:
            return 'medium'
    
    match = re.search(r'~(\d+)\s*days', condition)
    if match:
        detected_days = int(match.group(1))
        over = detected_days - max_days
        if over > PAYMENT_MEDIUM_THRESHOLD:
            return 'high'
        elif over > 0:
            return 'medium'
    
    return 'medium'


def _assess_renewal_severity(finding, config):
    condition = finding.get('condition_detected', '').lower()
    max_term = config.get('max_renewal_term_months', 12)
    
    term_match = re.search(r'(\d+)-month\s+renewal\s+term', condition)
    if term_match:
        term = int(term_match.group(1))
        if term > max_term:
            return 'high'
    
    notice_match = re.search(r'(\d+)-day\s+(?:cancellation\s+)?notice', condition)
    if notice_match:
        notice = int(notice_match.group(1))
        if notice > RENEWAL_HIGH_NOTICE_THRESHOLD:
            return 'high'
            
    return 'medium'


def _assess_liability_severity(finding, config):
    condition = finding.get('condition_detected', '').lower()
    if 'unlimited' in condition or 'uncapped' in condition:
        return 'high'
    elif 'broad' in condition or 'indemnif' in condition or 'sole' in condition:
        return 'medium'
    return 'medium'


def _assess_termination_severity(finding, config):
    return 'medium'
