"""Deterministic clause detection for contract policies."""

import re
from typing import List, Dict, Any, Optional

NUMBER_WORDS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23, 'twenty-four': 24,
    'twenty-five': 25, 'twenty-six': 26, 'twenty-seven': 27, 'twenty-eight': 28,
    'twenty-nine': 29, 'thirty': 30, 'thirty-one': 31, 'forty': 40, 'forty-five': 45,
    'fifty': 50, 'sixty': 60, 'seventy': 70, 'seventy-five': 75, 'eighty': 80, 'ninety': 90,
    'hundred': 100, 'one hundred': 100, 'ninety-one': 91, 'one hundred and twenty': 120,
    'one hundred twenty': 120, 'one hundred eighty': 180, 'three hundred sixty-five': 365,
    'three hundred sixty five': 365, 'three hundred and sixty-five': 365,
}


def parse_number(text):
    """Parse a number from text, handling both digits and word forms.
    Handles patterns like 'sixty (60)' or 'thirty(30)' or just '60' or 'sixty'.
    """
    if not text:
        return None
    text = text.strip()
    
    paren_match = re.search(r'\((\d+)\)', text)
    if paren_match:
        return int(paren_match.group(1))
    
    digit_match = re.search(r'\b(\d+)\b', text)
    if digit_match:
        return int(digit_match.group(1))
    
    text_clean = re.sub(r'[^a-zA-Z\s-]', '', text).lower().strip()
    if text_clean in NUMBER_WORDS:
        return NUMBER_WORDS[text_clean]
    
    for word, num in sorted(NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
        if word in text_clean:
            return num
    
    return None


def detect_all(extraction, policies):
    """Run all detectors and return raw findings."""
    sentences = extraction.get('sentences', [])
    if not sentences:
        return []
    
    all_findings = []
    finding_counter = 0
    
    for policy in policies:
        category = policy['category']
        if not policy.get('enabled', True):
            continue
        
        config = policy['config']
        
        if category == 'payment':
            results = detect_payment(sentences, config)
        elif category == 'renewal':
            results = detect_renewal(sentences, config)
        elif category == 'liability':
            results = detect_liability(sentences, config)
        elif category == 'termination':
            results = detect_termination(sentences, config)
        elif category == 'jurisdiction':
            results = detect_jurisdiction(sentences, config)
        elif category == 'custom':
            results = detect_custom(sentences, config, policy.get('name', 'Custom Policy'))
        else:
            continue
        
        if not results:
            finding_counter += 1
            all_findings.append({
                'risk_id': f'RISK-{finding_counter:03d}',
                'category': category,
                'result_type': 'not_found',
                'severity': None,
                'clause_title': None,
                'policy_expected': _describe_policy(category, config),
                'condition_detected': 'No matching clause found in the contract.',
                'evidence_quote': '',
                'page_number': None,
                'paragraph_reference': None,
                'line_reference': None,
                'explanation': f'No {category} clause was found in the contract.',
                'potential_impact': f'The contract does not appear to address {category} terms.',
                'suggested_action': f'Consider requesting that {category} terms be explicitly included in the contract.',
            })
        else:
            for r in results:
                finding_counter += 1
                r['risk_id'] = f'RISK-{finding_counter:03d}'
                all_findings.append(r)
    
    return all_findings


def _describe_policy(category, config):
    """Generate human-readable description of policy expectation."""
    if category == 'payment':
        return f"Payment within {config.get('max_payment_days', 30)} days"
    elif category == 'renewal':
        parts = []
        if not config.get('auto_renewal_allowed', False):
            parts.append('Auto-renewal not allowed')
        parts.append(f"Max renewal term: {config.get('max_renewal_term_months', 12)} months")
        parts.append(f"Min cancellation notice: {config.get('min_cancellation_notice_days', 30)} days")
        return '; '.join(parts)
    elif category == 'liability':
        parts = []
        if not config.get('unlimited_liability_allowed', False):
            parts.append('Unlimited liability not allowed')
        if config.get('require_liability_cap', True):
            parts.append('Liability cap required')
        return '; '.join(parts)
    elif category == 'termination':
        parts = [f"Min notice: {config.get('min_notice_days', 30)} days"]
        if config.get('flag_one_sided_termination', True):
            parts.append('Flag one-sided termination')
        return '; '.join(parts)
    elif category == 'jurisdiction':
        pref = config.get('preferred_jurisdiction', 'India')
        accepted = config.get('accepted_jurisdictions', [pref])
        return f"Preferred: {pref}; Accepted: {', '.join(accepted)}"
    return str(config)


def detect_payment(sentences, config):
    """Detect payment terms in contract sentences."""
    max_days = config.get('max_payment_days', 30)
    
    payment_keywords = [
        r'payment', r'pay\b', r'payable', r'invoice', r'invoicing', r'net\s+\d+',
        r'remittance', r'compensation', r'fee(?:s)?', r'billing',
        r'due\s+(?:within|after|upon|on)',
    ]
    payment_re = re.compile('|'.join(payment_keywords), re.IGNORECASE)
    
    findings = []
    
    for sent in sentences:
        text = sent['text']
        if not payment_re.search(text):
            continue
        
        # Check ambiguous first
        if re.search(r'within\s+a\s+reasonable\s+time', text, re.IGNORECASE):
            findings.append(_make_finding(
                category='payment',
                result_type='uncertain',
                policy_expected=f'Payment within {max_days} days',
                condition_detected='Ambiguous payment term: "within a reasonable time"',
                evidence=sent,
                explanation='The contract uses ambiguous language for payment timing. The exact number of days is not specified.',
                impact='Payment timing is unclear and may lead to delayed payments.',
                action='Request specific payment terms with a defined number of days.',
            ))
            continue
        
        # Check upon completion
        if re.search(r'upon\s+completion', text, re.IGNORECASE) and not re.search(r'\d+\s+days\s+upon\s+completion', text, re.IGNORECASE):
            findings.append(_make_finding(
                category='payment',
                result_type='uncertain',
                policy_expected=f'Payment within {max_days} days',
                condition_detected='Payment upon completion',
                evidence=sent,
                explanation='Payment is tied to project completion, which may not have a fixed timeline.',
                impact='Payment could be delayed if completion is disputed or delayed.',
                action='Consider adding a maximum payment period after completion.',
            ))
            continue
        
        # Check advance payment
        if re.search(r'(?:advance\s+payment|payment\s+in\s+advance|paid\s+in\s+advance)', text, re.IGNORECASE):
            findings.append(_make_finding(
                category='payment',
                result_type='match',
                policy_expected=f'Payment within {max_days} days',
                condition_detected='Advance payment required',
                evidence=sent,
                explanation='The contract requires advance payment, which is within the policy limit.',
                impact='Payment is received before work begins.',
                action='No action needed.',
            ))
            continue
            
        # Check Net XX
        net_match = re.search(r'net[\s-](\d+)', text, re.IGNORECASE)
        if net_match:
            days = int(net_match.group(1))
            start_point = _detect_start_point(text)
            if days > max_days:
                diff = days - max_days
                findings.append(_make_finding(
                    category='payment',
                    result_type='conflict',
                    policy_expected=f'Payment within {max_days} days',
                    condition_detected=f'Payment Net {days} days{start_point}',
                    evidence=sent,
                    explanation=f'The contract allows Net {days} days for payment, which exceeds the policy limit of {max_days} days by {diff} days.',
                    impact=f'You may wait up to {days} days for payment, {diff} days longer than your policy allows.',
                    action=f'Negotiate payment terms to within {max_days} days.',
                ))
            else:
                findings.append(_make_finding(
                    category='payment',
                    result_type='match',
                    policy_expected=f'Payment within {max_days} days',
                    condition_detected=f'Payment Net {days} days{start_point}',
                    evidence=sent,
                    explanation=f'The contract allows Net {days} days for payment, within the policy limit of {max_days} days.',
                    impact='Payment timeline is within acceptable limits.',
                    action='No action needed.',
                ))
            continue
        
        # Check within / after / from N days / months
        # Pattern: within/after/prior to (number words / digits) days
        day_pattern = r'(?:within|after|from|following|due\s+in)\s+([a-zA-Z\s-]+(?:\(\d+\))?|\d+)\s*(calendar\s+|business\s+)?days?'
        match = re.search(day_pattern, text, re.IGNORECASE)
        if match:
            num_str = match.group(1)
            num = parse_number(num_str)
            if num is not None:
                is_business = bool(match.group(2) and 'business' in match.group(2).lower()) or ('business day' in text.lower())
                count_basis = 'business days' if is_business else 'calendar days'
                start_point = _detect_start_point(text)
                
                if num > max_days:
                    diff = num - max_days
                    findings.append(_make_finding(
                        category='payment',
                        result_type='conflict',
                        policy_expected=f'Payment within {max_days} days',
                        condition_detected=f'Payment within {num} {count_basis}{start_point}',
                        evidence=sent,
                        explanation=f'The contract allows {num} {count_basis} for payment, which exceeds the policy limit of {max_days} days by {diff} days.',
                        impact=f'You may wait up to {num} {count_basis} for payment, {diff} days longer than your policy allows.',
                        action=f'Negotiate payment terms to within {max_days} days.',
                    ))
                else:
                    findings.append(_make_finding(
                        category='payment',
                        result_type='match',
                        policy_expected=f'Payment within {max_days} days',
                        condition_detected=f'Payment within {num} {count_basis}{start_point}',
                        evidence=sent,
                        explanation=f'The contract allows {num} {count_basis} for payment, within the policy limit of {max_days} days.',
                        impact='Payment timeline is within acceptable limits.',
                        action='No action needed.',
                    ))
                continue
        
        # Check months pattern: within N months
        month_pattern = r'(?:within|after|from)\s+([a-zA-Z\s-]+(?:\(\d+\))?|\d+)\s*months?'
        match = re.search(month_pattern, text, re.IGNORECASE)
        if match:
            num = parse_number(match.group(1))
            if num is not None:
                equiv_days = num * 30
                start_point = _detect_start_point(text)
                if equiv_days > max_days:
                    diff = equiv_days - max_days
                    findings.append(_make_finding(
                        category='payment',
                        result_type='conflict',
                        policy_expected=f'Payment within {max_days} days',
                        condition_detected=f'Payment within {num} months (~{equiv_days} days){start_point}',
                        evidence=sent,
                        explanation=f'The contract allows approximately {equiv_days} days for payment, which exceeds the policy limit of {max_days} days by {diff} days.',
                        impact=f'You may wait up to {equiv_days} days for payment.',
                        action=f'Negotiate payment terms to within {max_days} days.',
                    ))
                else:
                    findings.append(_make_finding(
                        category='payment',
                        result_type='match',
                        policy_expected=f'Payment within {max_days} days',
                        condition_detected=f'Payment within {num} months (~{equiv_days} days){start_point}',
                        evidence=sent,
                        explanation=f'The contract allows approximately {equiv_days} days for payment, within policy limit.',
                        impact='Payment timeline is acceptable.',
                        action='No action needed.',
                    ))
                continue
    
    return findings


def _detect_start_point(text):
    text_lower = text.lower()
    if 'invoice' in text_lower or 'invoicing' in text_lower:
        return ' of invoice'
    elif 'receipt' in text_lower:
        return ' of receipt'
    elif 'delivery' in text_lower or 'deliverable' in text_lower:
        return ' of delivery'
    elif 'acceptance' in text_lower:
        return ' of acceptance'
    elif 'completion' in text_lower:
        return ' of completion'
    return ''


def detect_renewal(sentences, config):
    """Detect auto-renewal and related terms."""
    auto_allowed = config.get('auto_renewal_allowed', False)
    max_term = config.get('max_renewal_term_months', 12)
    min_notice = config.get('min_cancellation_notice_days', 30)
    
    renewal_patterns = [
        r'auto(?:matic(?:ally)?)?[\s-]*renew',
        r'successive\s+term',
        r'evergreen',
        r'shall\s+(?:be\s+)?renew(?:ed)?',
        r'renewal\s+term',
        r'renew(?:s|ed|al)?\s+(?:for|automatically)',
        r'continue\s+(?:for|in\s+effect\s+for)\s+(?:additional|successive|further)',
    ]
    renewal_re = re.compile('|'.join(renewal_patterns), re.IGNORECASE)
    
    notice_patterns = [
        r"(\d+|[a-zA-Z\s-]+(?:\(\d+\))?)\s*(?:calendar\s+|business\s+)?days?(?:['\s]+)?(?:prior|advance|before|written)\s*(?:notice|notification)",
        r"(?:notice|notification)\s+(?:of\s+)?(?:at\s+least\s+|no\s+less\s+than\s+|not\s+less\s+than\s+|unless\s+)?(\d+|[a-zA-Z\s-]+(?:\(\d+\))?)\s*(?:calendar\s+|business\s+)?days?",
        r"unless\s+(\d+|[a-zA-Z\s-]+(?:\(\d+\))?)\s*days",
    ]
    
    term_patterns = [
        r'(?:for|of)\s+(?:an?\s+)?(?:additional\s+|successive\s+|further\s+)?(\d+|[a-zA-Z\s-]+(?:\(\d+\))?)\s*(?:[-\s])?(month|year)',
        r'(\d+|[a-zA-Z\s-]+(?:\(\d+\))?)\s*(?:[-\s])?(month|year)\s+(?:term|period|renewal)',
    ]
    
    findings = []
    
    for sent in sentences:
        text = sent['text']
        if not renewal_re.search(text):
            continue
        
        is_negated = bool(re.search(r'(?:no|not|without|shall\s+not)\s+(?:automatic(?:ally)?\s+)?renew', text, re.IGNORECASE))
        is_auto = bool(re.search(r'auto(?:matic(?:ally)?)?[\s-]*renew|evergreen|successive\s+term', text, re.IGNORECASE)) and not is_negated
        
        # Extract term
        term_months = None
        for pattern in term_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num = parse_number(match.group(1))
                unit = match.group(2).lower()
                if num is not None:
                    term_months = num * 12 if 'year' in unit else num
                    break
        
        # Extract notice
        notice_days = None
        for pattern in notice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num = parse_number(match.group(1))
                if num is not None:
                    notice_days = num
                    break
        
        conditions = []
        is_conflict = False
        
        if is_auto:
            conditions.append('Auto-renewal')
            if not auto_allowed:
                is_conflict = True
        elif is_negated:
            conditions.append('No automatic renewal')
        
        if is_auto and term_months is not None:
            conditions.append(f'{term_months}-month renewal term')
            if term_months > max_term:
                is_conflict = True
        
        if notice_days is not None:
            conditions.append(f'{notice_days}-day cancellation notice')
            # If notice period required to cancel is longer than policy minimum or if it's very onerous
            # In standard contract policy: notice required to cancel: if notice required is > 60 days, it's risky
        elif is_auto:
            conditions.append('Notice period not stated')
        
        result_type = 'conflict' if is_conflict else 'match'
        
        policy_desc = _describe_policy('renewal', config)
        condition_str = '; '.join(conditions) if conditions else 'Renewal terms present'
        
        explanations = []
        if is_auto and not auto_allowed:
            explanations.append('The contract includes auto-renewal, which is not permitted under your policy.')
        if term_months and term_months > max_term:
            explanations.append(f'The renewal term of {term_months} months exceeds the allowed maximum of {max_term} months.')
        if not explanations:
            explanations.append('The renewal terms satisfy your policy requirements.')
        
        impacts = []
        if is_auto and not auto_allowed:
            impacts.append('The contract will renew automatically unless affirmatively cancelled.')
        if term_months and term_months > max_term:
            impacts.append(f'You could be committed for an additional {term_months} months.')
        
        findings.append(_make_finding(
            category='renewal',
            result_type=result_type,
            policy_expected=policy_desc,
            condition_detected=condition_str,
            evidence=sent,
            explanation=' '.join(explanations),
            impact=' '.join(impacts) if impacts else 'Renewal terms appear acceptable.',
            action='Request removal of auto-renewal or adjustment of renewal terms.' if is_conflict else 'No action needed.',
        ))
    
    return findings


def detect_liability(sentences, config):
    """Detect liability terms."""
    unlimited_allowed = config.get('unlimited_liability_allowed', False)
    require_cap = config.get('require_liability_cap', True)
    
    unlimited_patterns = [
        r'unlimited\s+liability',
        r'liability\s+(?:shall\s+be\s+|is\s+)?unlimited',
        r'without\s+(?:any\s+)?limit(?:ation)?(?:\s+(?:of|on)\s+liability)?',
        r'uncapped\s+liability',
        r'liability\s+(?:shall\s+be\s+|is\s+)?uncapped',
        r'no\s+(?:cap|limit(?:ation)?)\s+(?:on|of)\s+liability',
    ]
    
    broad_indemnity_patterns = [
        r'indemnif(?:y|ies)\s+.*?(?:all|any\s+and\s+all|every)\s+(?:loss(?:es)?|damage|claim|liability|cost)',
        r'sole\s+liability',
        r'full(?:y)?\s+(?:liable|responsible|indemnif)',
        r'bear\s+all\s+(?:costs?|losses?|damages?|liabilit(?:y|ies))',
    ]
    
    cap_patterns = [
        r'(?:liability|damages?)\s+(?:shall|will)\s+not\s+exceed',
        r'(?:shall|will)\s+not\s+(?:be\s+)?(?:liable|responsible)\s+(?:for\s+)?(?:amounts?\s+)?(?:in\s+excess\s+of|exceeding|greater\s+than|more\s+than)',
        r'limit(?:ed|ation)?\s+(?:of\s+)?(?:liability|damages?)',
        r'(?:aggregate|total|maximum|max)\s+liability',
        r'(?:liability|damages?)\s+(?:(?:is|are|shall\s+be)\s+)?(?:limited|capped)\s+(?:to|at)',
        r'cap\s+(?:on|of)\s+(?:liability|damages?)',
    ]
    
    findings = []
    
    for sent in sentences:
        text = sent['text']
        
        # Check unlimited
        for pattern in unlimited_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result = 'match' if unlimited_allowed else 'conflict'
                findings.append(_make_finding(
                    category='liability',
                    result_type=result,
                    policy_expected=_describe_policy('liability', config),
                    condition_detected='Unlimited liability clause detected',
                    evidence=sent,
                    explanation='The contract states that liability is unlimited or uncapped.' + (' This conflicts with your policy.' if not unlimited_allowed else ''),
                    impact='You may be exposed to unbounded financial damages.' if not unlimited_allowed else 'Unlimited liability accepted per policy.',
                    action='Negotiate a reasonable liability cap (e.g., total fees paid under contract).' if not unlimited_allowed else 'Review clause carefully.',
                ))
                break
        
        # Check broad indemnity
        for pattern in broad_indemnity_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if not any(f['evidence_quote'] == sent['text'] for f in findings):
                    findings.append(_make_finding(
                        category='liability',
                        result_type='conflict' if not unlimited_allowed else 'match',
                        policy_expected=_describe_policy('liability', config),
                        condition_detected='Broad indemnification clause detected (requires review)',
                        evidence=sent,
                        explanation='The contract contains broad indemnification language covering all losses, which functions as uncapped liability.',
                        impact='You may be held liable for third-party claims or broad categories of loss.',
                        action='Request indemnification to be capped or limited to direct damages caused by gross negligence.',
                    ))
                break
        
        # Check liability cap (only if not already marked unlimited or broad indemnity in this sentence)
        if not any(f['evidence_quote'] == sent['text'] for f in findings):
            for pattern in cap_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    findings.append(_make_finding(
                        category='liability',
                        result_type='match',
                        policy_expected=_describe_policy('liability', config),
                        condition_detected='Liability cap clause detected',
                        evidence=sent,
                        explanation='The contract contains a liability limitation/cap clause, satisfying the liability cap requirement.',
                        impact='Damages are capped as specified in the clause.',
                        action='Verify the monetary amount of the cap is appropriate.',
                    ))
                    break
    
    return findings


def detect_termination(sentences, config):
    """Detect termination terms."""
    min_notice = config.get('min_notice_days', 30)
    flag_one_sided = config.get('flag_one_sided_termination', True)
    
    termination_patterns = [
        r'terminat(?:e|ion|ed|ing)',
        r'cancel(?:lation)?\s+of\s+(?:this\s+)?(?:agreement|contract)',
        r'cancel\s+this\s+(?:agreement|contract)',
    ]
    term_re = re.compile('|'.join(termination_patterns), re.IGNORECASE)
    
    convenience_patterns = [
        r'terminat(?:e|ion)\s+(?:for\s+)?convenience',
        r'terminat(?:e|ion)\s+(?:at\s+)?(?:any\s+time|will)',
        r'(?:without\s+)?(?:cause|reason)',
        r'(?:for\s+)?any\s+reason\s+or\s+no\s+reason',
    ]
    
    one_sided_patterns = [
        r'(?:the\s+)?(?:company|client|employer|buyer|purchaser)\s+(?:may|shall\s+have\s+the\s+right\s+to|reserves?\s+the\s+right\s+to)\s+terminat',
        r'(?:at\s+)?(?:the\s+)?(?:sole\s+)?discretion\s+of\s+(?:the\s+)?(?:company|client|employer|buyer)',
    ]
    
    notice_patterns = [
        r"(\d+|[a-zA-Z\s-]+(?:\(\d+\))?)\s*(?:calendar\s+|business\s+)?days?(?:['\s]+)?(?:prior\s+|advance\s+|written\s+)?notice",
        r"notice\s+(?:of\s+)?(?:at\s+least\s+|no\s+less\s+than\s+)?(\d+|[a-zA-Z\s-]+(?:\(\d+\))?)\s*(?:calendar\s+|business\s+)?days?",
    ]
    
    findings = []
    
    for sent in sentences:
        text = sent['text']
        if not term_re.search(text):
            continue
        
        is_convenience = bool(re.search('|'.join(convenience_patterns), text, re.IGNORECASE))
        is_one_sided = bool(re.search('|'.join(one_sided_patterns), text, re.IGNORECASE))
        
        notice_days = None
        for pattern in notice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num = parse_number(match.group(1))
                if num is not None:
                    notice_days = num
                    break
        
        conditions = []
        is_conflict = False
        
        if is_convenience:
            conditions.append('Termination for convenience')
        
        if is_one_sided and flag_one_sided:
            conditions.append('One-sided termination right')
            is_conflict = True
        
        if notice_days is not None:
            conditions.append(f'{notice_days}-day notice')
            if notice_days < min_notice:
                is_conflict = True
        
        if not conditions:
            conditions.append('Termination clause detected')
        
        result_type = 'conflict' if is_conflict else 'match'
        
        explanations = []
        if is_one_sided and flag_one_sided:
            explanations.append('The client/company has unilateral termination rights while reciprocal rights are not stated.')
        if notice_days is not None and notice_days < min_notice:
            explanations.append(f'The notice period of {notice_days} days is less than the minimum required ({min_notice} days).')
        if not explanations:
            explanations.append('Termination terms comply with policy.')
        
        findings.append(_make_finding(
            category='termination',
            result_type=result_type,
            policy_expected=_describe_policy('termination', config),
            condition_detected='; '.join(conditions),
            evidence=sent,
            explanation=' '.join(explanations),
            impact='Contract may be terminated prematurely or without sufficient notice.' if is_conflict else 'Termination terms appear balanced.',
            action='Negotiate mutual termination rights and adequate notice period.' if is_conflict else 'No action needed.',
        ))
    
    return findings


JURISDICTION_ALIASES = {
    'chennai': ('Tamil Nadu', 'India'),
    'madras': ('Tamil Nadu', 'India'),
    'madras high court': ('Tamil Nadu', 'India'),
    'mumbai': ('Maharashtra', 'India'),
    'bombay': ('Maharashtra', 'India'),
    'bombay high court': ('Maharashtra', 'India'),
    'delhi': ('Delhi', 'India'),
    'new delhi': ('Delhi', 'India'),
    'bangalore': ('Karnataka', 'India'),
    'bengaluru': ('Karnataka', 'India'),
    'kolkata': ('West Bengal', 'India'),
    'calcutta': ('West Bengal', 'India'),
    'hyderabad': ('Telangana', 'India'),
    'pune': ('Maharashtra', 'India'),
    'ahmedabad': ('Gujarat', 'India'),
    'india': (None, 'India'),
    'republic of india': (None, 'India'),
    'indian courts': (None, 'India'),
    'singapore': (None, 'Singapore'),
    'singapore courts': (None, 'Singapore'),
    'republic of singapore': (None, 'Singapore'),
    'england': (None, 'England'),
    'england and wales': (None, 'England'),
    'london': (None, 'England'),
    'united kingdom': (None, 'United Kingdom'),
    'uk': (None, 'United Kingdom'),
    'united states': (None, 'United States'),
    'us': (None, 'United States'),
    'usa': (None, 'United States'),
    'new york': ('New York', 'United States'),
    'california': ('California', 'United States'),
    'delaware': ('Delaware', 'United States'),
    'texas': ('Texas', 'United States'),
    'hong kong': (None, 'Hong Kong'),
    'dubai': (None, 'UAE'),
    'uae': (None, 'UAE'),
    'australia': (None, 'Australia'),
    'germany': (None, 'Germany'),
    'france': (None, 'France'),
    'japan': (None, 'Japan'),
    'china': (None, 'China'),
    'canada': (None, 'Canada'),
    'tamil nadu': ('Tamil Nadu', 'India'),
    'karnataka': ('Karnataka', 'India'),
    'maharashtra': ('Maharashtra', 'India'),
}


def detect_jurisdiction(sentences, config):
    """Detect governing law and jurisdiction clauses."""
    preferred = config.get('preferred_jurisdiction', 'India')
    accepted_list = config.get('accepted_jurisdictions', [preferred])
    accepted_lower = [a.lower() for a in accepted_list]
    
    jurisdiction_patterns = [
        r'(?:governed?\s+by|governing\s+law|subject\s+to)\s+(?:the\s+)?(?:laws?\s+of\s+)?(?:the\s+)?(.+?)(?:\.|,|;|$)',
        r'(?:jurisdiction|venue|courts?)\s+(?:of|in|at|located\s+in)\s+(?:the\s+)?(.+?)(?:\.|,|;|$)',
        r'(?:exclusive\s+)?(?:jurisdiction|venue)\s+(?:shall\s+be|is)\s+(?:in\s+)?(?:the\s+)?(.+?)(?:\.|,|;|$)',
        r'(?:courts?\s+of|tribunals?\s+of|arbitration\s+in)\s+(.+?)(?:\.|,|;|\s+shall|$)',
        r'(?:laws?\s+of\s+)(?:the\s+)?(.+?)(?:\s+shall|\s+will|\s+govern|\.|,|;|$)',
    ]
    
    findings = []
    
    for sent in sentences:
        text = sent['text']
        text_lower = text.lower()
        
        if not any(kw in text_lower for kw in ['govern', 'jurisdiction', 'venue', 'court', 'tribunal', 'arbitrat', 'law of', 'laws of', 'subject to the law']):
            continue
        
        detected_place = None
        detected_country = None
        detected_state = None
        
        # Check alias keys directly first
        for alias, (state, country) in sorted(JURISDICTION_ALIASES.items(), key=lambda x: -len(x[0])):
            if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                detected_place = alias
                detected_state = state
                detected_country = country
                break
        
        if not detected_place:
            for pattern in jurisdiction_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    detected_place = match.group(1).strip(' .,;')
                    break
        
        if not detected_place:
            continue
        
        if detected_country:
            country_lower = detected_country.lower()
            state_lower = detected_state.lower() if detected_state else ''
            
            is_match = country_lower in accepted_lower or (state_lower and state_lower in accepted_lower) or any(country_lower in a for a in accepted_lower)
            
            location_str = f"{detected_state}, {detected_country}" if detected_state else detected_country
            
            if is_match:
                findings.append(_make_finding(
                    category='jurisdiction',
                    result_type='match',
                    policy_expected=_describe_policy('jurisdiction', config),
                    condition_detected=f'Jurisdiction: {location_str}',
                    evidence=sent,
                    explanation=f'The contract designates {location_str} as governing jurisdiction, which matches your accepted jurisdictions.',
                    impact='Disputes will be resolved in your preferred or accepted jurisdiction.',
                    action='No action needed.',
                ))
            else:
                findings.append(_make_finding(
                    category='jurisdiction',
                    result_type='conflict',
                    policy_expected=_describe_policy('jurisdiction', config),
                    condition_detected=f'Jurisdiction: {location_str}',
                    evidence=sent,
                    explanation=f'The contract designates {location_str} as governing jurisdiction, which is not in your accepted list ({", ".join(accepted_list)}).',
                    impact=f'In case of disputes, legal proceedings would take place under {location_str} law.',
                    action=f'Negotiate to change jurisdiction to {preferred} or another accepted venue.',
                ))
        else:
            findings.append(_make_finding(
                category='jurisdiction',
                result_type='uncertain',
                policy_expected=_describe_policy('jurisdiction', config),
                condition_detected=f'Jurisdiction reference: "{detected_place}" (unrecognized location)',
                evidence=sent,
                explanation=f'A jurisdiction clause was detected referencing "{detected_place}", but the location could not be confirmed.',
                impact='The jurisdiction might be unfavorable or outside your accepted list.',
                action='Manually review the governing law clause.',
            ))
    
    return findings


def detect_custom(sentences, config, policy_name):
    """Detect custom policy matches."""
    match_type = config.get('match_type', 'must_contain')
    keywords = config.get('keywords', '')
    severity = config.get('severity', 'medium')
    description = config.get('description', '')
    expected = config.get('expected_condition', '')
    
    if not keywords:
        return []
    
    keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
    findings = []
    
    for sent in sentences:
        text = sent['text']
        text_lower = text.lower()
        
        if match_type == 'must_not_contain':
            for keyword in keyword_list:
                if keyword.lower() in text_lower:
                    findings.append(_make_finding(
                        category='custom',
                        result_type='conflict',
                        policy_expected=f'{policy_name}: Must not contain "{keyword}"',
                        condition_detected=f'Prohibited term found: "{keyword}"',
                        evidence=sent,
                        explanation=f'The contract contains the prohibited keyword "{keyword}". {description}'.strip(),
                        impact=expected or 'Contract contains restricted term.',
                        action='Negotiate removal or modification of this clause.',
                        severity_override=severity,
                    ))
        
        elif match_type == 'number_max':
            max_val = config.get('max_value')
            if max_val is not None:
                for keyword in keyword_list:
                    if keyword.lower() in text_lower:
                        numbers = re.findall(r'(\d+(?:\.\d+)?)', text)
                        for num_str in numbers:
                            num = float(num_str)
                            if num > max_val:
                                findings.append(_make_finding(
                                    category='custom',
                                    result_type='conflict',
                                    policy_expected=f'{policy_name}: {keyword} max {max_val}',
                                    condition_detected=f'Found value {num} exceeding limit {max_val}',
                                    evidence=sent,
                                    explanation=f'Value {num} associated with "{keyword}" exceeds maximum allowed threshold of {max_val}. {description}'.strip(),
                                    impact=expected or f'Numeric limit exceeded.',
                                    action=f'Negotiate to reduce this value to {max_val} or lower.',
                                    severity_override=severity,
                                ))
    
    if match_type == 'must_contain':
        full_text = ' '.join(s['text'].lower() for s in sentences)
        for keyword in keyword_list:
            if keyword.lower() not in full_text:
                findings.append({
                    'category': 'custom',
                    'result_type': 'conflict',
                    'policy_expected': f'{policy_name}: Must contain "{keyword}"',
                    'condition_detected': f'Required term "{keyword}" missing from contract',
                    'evidence_quote': '',
                    'page_number': None,
                    'paragraph_reference': None,
                    'line_reference': None,
                    'clause_title': None,
                    'explanation': f'The required term "{keyword}" was not found in the contract. {description}'.strip(),
                    'potential_impact': expected or f'Mandatory clause or keyword is absent.',
                    'suggested_action': f'Request inclusion of "{keyword}" in the agreement.',
                    'severity': severity,
                })
    
    return findings


def _make_finding(category, result_type, policy_expected, condition_detected, evidence, explanation, impact, action, severity_override=None):
    return {
        'category': category,
        'result_type': result_type,
        'severity': severity_override,
        'clause_title': evidence.get('clause_title'),
        'policy_expected': policy_expected,
        'condition_detected': condition_detected,
        'evidence_quote': evidence['text'],
        'page_number': evidence.get('page'),
        'paragraph_reference': evidence.get('paragraph_reference') or (f"Paragraph {evidence.get('paragraph')}" if evidence.get('paragraph') else None),
        'line_reference': f"line {evidence.get('line_ref')} on page {evidence.get('page')}" if evidence.get('line_ref') and evidence.get('page') else None,
        'explanation': explanation,
        'potential_impact': impact,
        'suggested_action': action,
    }
