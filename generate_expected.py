"""Generate expected JSON results for fixtures using ClauseLens engines."""

import os
import json
from services.document_extractor import extract_document
from services.clause_detector import detect_all
from services.risk_engine import assess_risks
from services.evidence_verifier import verify_findings
from database import DEFAULT_POLICIES

fixtures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests', 'fixtures')
expected_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests', 'expected')

# Default policy objects
policies = []
for p in DEFAULT_POLICIES:
    policies.append({
        'category': p['category'],
        'name': p['name'],
        'enabled': True,
        'config': json.loads(p['config']),
        'is_custom': False
    })

contracts = [
    ('sample_freelance_contract.pdf', 'pdf'),
    ('ambiguous_payment_contract.pdf', 'pdf'),
    ('clean_compliant_contract.pdf', 'pdf'),
    ('vendor_agreement.docx', 'docx'),
    ('consulting_contract.docx', 'docx'),
]

for filename, file_type in contracts:
    file_path = os.path.join(fixtures_dir, filename)
    base_name = os.path.splitext(filename)[0]
    out_json = os.path.join(expected_dir, f"{base_name}.json")
    
    extraction = extract_document(file_path, file_type)
    if extraction.get('error'):
        print(f"Skipping {filename}: {extraction['error']}")
        continue
        
    raw_findings = detect_all(extraction, policies)
    findings = assess_risks(raw_findings, policies)
    findings = verify_findings(findings, extraction, file_path, file_type)
    
    expected_data = {
        'fixture_name': filename,
        'file_type': file_type,
        'total_findings': len(findings),
        'summary': {
            'conflicts': sum(1 for f in findings if f.get('result_type') == 'conflict'),
            'matches': sum(1 for f in findings if f.get('result_type') == 'match'),
            'uncertain': sum(1 for f in findings if f.get('result_type') == 'uncertain'),
            'not_found': sum(1 for f in findings if f.get('result_type') == 'not_found'),
            'high': sum(1 for f in findings if f.get('severity') == 'high'),
            'medium': sum(1 for f in findings if f.get('severity') == 'medium'),
            'low': sum(1 for f in findings if f.get('severity') == 'low'),
        },
        'findings': [
            {
                'category': f['category'],
                'result_type': f['result_type'],
                'severity': f['severity'],
                'policy_expected': f['policy_expected'],
                'condition_detected': f['condition_detected'],
                'evidence_quote': f['evidence_quote'],
                'verification_status': f['verification_status']
            }
            for f in findings
        ]
    }
    
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(expected_data, f, indent=2, ensure_ascii=False)
        
    print(f"Generated expected for {filename}: {expected_data['summary']}")

print("All expected JSONs generated!")
