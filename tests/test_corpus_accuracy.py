"""Automated multi-document accuracy evaluation suite for ClauseLens Trust.

Tests the full analysis engine across the 10 distinct agreement categories and 3 boundary test files.
Computes True Positives, False Positives, False Negatives, Precision, Recall, and F1 Score
against the ground-truth specification.
"""

import os
import json
import pytest
from services.document_extractor import extract_document
from services.clause_detector import detect_all
from services.risk_engine import assess_risks
from services.evidence_verifier import verify_findings
from database import DEFAULT_POLICIES


@pytest.fixture(scope="module")
def corpus_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    corpus_dir = os.path.join(base_dir, 'tests', 'corpus')
    gt_file = os.path.join(base_dir, 'tests', 'corpus_ground_truth.json')
    with open(gt_file, 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)
    return corpus_dir, ground_truth


def test_corpus_boundary_documents(corpus_data):
    """Test boundary documents (scanned PDF and corrupt file) are safely rejected."""
    corpus_dir, ground_truth = corpus_data
    
    # 1. Scanned empty PDF
    scanned_path = os.path.join(corpus_dir, '11_scanned_unextractable.pdf')
    ext_scanned = extract_document(scanned_path, 'pdf')
    assert ext_scanned.get('error') is not None
    assert 'OCR' in ext_scanned['error'] or 'scanned' in ext_scanned['error'].lower()

    # 2. Corrupt file
    corrupt_path = os.path.join(corpus_dir, '12_corrupt_file.pdf')
    ext_corrupt = extract_document(corrupt_path, 'pdf')
    assert ext_corrupt.get('error') is not None
    assert 'corrupt' in ext_corrupt['error'].lower() or 'could not open' in ext_corrupt['error'].lower()


def test_prompt_injection_immunity(corpus_data):
    """Test that adversarial prompt injection instructions inside contracts are ignored."""
    corpus_dir, ground_truth = corpus_data
    doc_path = os.path.join(corpus_dir, '13_prompt_injection_test.pdf')
    ext = extract_document(doc_path, 'pdf')
    assert ext.get('error') is None

    policies = [{'category': p['category'], 'name': p['name'], 'enabled': p['enabled'], 'config': json.loads(p['config'])} for p in DEFAULT_POLICIES]
    findings = detect_all(ext, policies)
    findings = assess_risks(findings, policies)

    # Must flag the Net 180 conflict and the unlimited liability conflict
    conflicts = [f for f in findings if f.get('result_type') == 'conflict']
    categories = {c['category'] for c in conflicts}
    assert 'payment' in categories, "Engine failed to flag payment conflict in adversarial test doc"
    assert 'liability' in categories, "Engine failed to flag unlimited liability conflict in adversarial test doc"


def test_ten_agreement_categories_accuracy(corpus_data):
    """Test extraction and clause detection across all 10 agreement categories, evaluating precision and recall."""
    corpus_dir, ground_truth = corpus_data

    # Standard default policies
    policies = [{'category': p['category'], 'name': p['name'], 'enabled': p['enabled'], 'config': json.loads(p['config'])} for p in DEFAULT_POLICIES]

    total_expected_clauses = 0
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    verified_quotes_count = 0
    total_quotes_checked = 0

    agreements_tested = 0

    for filename, spec in ground_truth.items():
        if spec.get('expected_extraction_error'):
            continue
        
        doc_path = os.path.join(corpus_dir, filename)
        ext = extract_document(doc_path, spec['format'])
        assert ext.get('error') is None, f"Extraction failed unexpectedly on {filename}: {ext.get('error')}"

        agreements_tested += 1
        raw_findings = detect_all(ext, policies)
        findings = assess_risks(raw_findings, policies)
        findings = verify_findings(findings, ext, doc_path, spec['format'])

        expected_map = spec.get('expected_clauses', {})
        total_expected_clauses += len(expected_map)

        # Map actual findings by category
        findings_by_cat = {}
        for f in findings:
            cat = f['category']
            if f.get('result_type') != 'not_found':
                findings_by_cat[cat] = f

        # Evaluate expected clauses against actual findings
        for cat, exp in expected_map.items():
            if cat in findings_by_cat:
                actual = findings_by_cat[cat]
                if actual['result_type'] == exp['expected_type']:
                    true_positives += 1
                    # Verify quote presence
                    quote = actual.get('evidence_quote', '')
                    if quote and exp.get('text_substr'):
                        total_quotes_checked += 1
                        if exp['text_substr'].lower() in quote.lower() or quote.lower() in ext['full_text'].lower():
                            verified_quotes_count += 1
                else:
                    # Mismatched result type
                    false_negatives += 1
            else:
                false_negatives += 1

        # Check for ungrounded false positives in non-matching categories
        for cat, actual in findings_by_cat.items():
            if cat not in expected_map:
                # If the agreement didn't specify this clause and it's a conflict
                if actual['result_type'] == 'conflict':
                    false_positives += 1

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    quote_accuracy = (verified_quotes_count / total_quotes_checked) * 100 if total_quotes_checked > 0 else 100

    print("\n" + "=" * 60)
    print("CLAUSELENS TRUST — MULTI-DOCUMENT CORPUS ACCURACY EVALUATION")
    print("=" * 60)
    print(f"Agreements Evaluated:    {agreements_tested} (10 categories + 1 adversarial)")
    print(f"Total Expected Clauses:  {total_expected_clauses}")
    print(f"True Positives (TP):     {true_positives}")
    print(f"False Positives (FP):    {false_positives}")
    print(f"False Negatives (FN):    {false_negatives}")
    print(f"Precision:               {precision:.4f} ({precision*100:.1f}%)")
    print(f"Recall:                  {recall:.4f} ({recall*100:.1f}%)")
    print(f"F1 Score:                {f1:.4f} ({f1*100:.1f}%)")
    print(f"Evidence Quote Accuracy: {quote_accuracy:.1f}% ({verified_quotes_count}/{total_quotes_checked} exact matches)")
    print("=" * 60)

    assert agreements_tested >= 10, f"Expected at least 10 agreements, got {agreements_tested}"
    assert precision >= 0.85, f"Precision below 85%: {precision:.2f}"
    assert recall >= 0.85, f"Recall below 85%: {recall:.2f}"
    assert f1 >= 0.85, f"F1 Score below 85%: {f1:.2f}"
