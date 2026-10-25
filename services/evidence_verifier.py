"""Evidence verification - verifies that findings' evidence quotes exist verbatim in source document."""

import re


def verify_findings(findings, extraction, file_path, file_type):
    """Verify each finding's evidence quote against the extracted text."""
    full_text = extraction.get('full_text', '')
    
    for finding in findings:
        quote = finding.get('evidence_quote', '')
        if not quote:
            if finding.get('result_type') == 'not_found':
                finding['verification_status'] = 'verified'
            else:
                finding['verification_status'] = 'unable_to_verify'
            continue
        
        # 1. Exact match
        if quote in full_text:
            finding['verification_status'] = 'verified'
            if file_type == 'pdf':
                _verify_pdf_highlight(finding, file_path)
            continue
        
        # 2. Normalized match (whitespace, ligatures, hyphenation)
        if _normalized_match(quote, full_text):
            finding['verification_status'] = 'verified'
            if file_type == 'pdf':
                _verify_pdf_highlight(finding, file_path)
            continue
            
        norm_quote = _normalize_whitespace(quote)
        norm_text = _normalize_whitespace(full_text)
        if norm_quote in norm_text:
            finding['verification_status'] = 'verified'
            if file_type == 'pdf':
                _verify_pdf_highlight(finding, file_path)
            continue
            
        # 3. Check cross-page spans (PDF)
        if file_type == 'pdf' and extraction.get('pages'):
            pages = extraction['pages']
            page_num = finding.get('page_number')
            if page_num and page_num < len(pages):
                combined = pages[page_num - 1]['text'] + '\n' + pages[page_num]['text']
                if _normalized_match(quote, combined):
                    finding['verification_status'] = 'needs_manual_review'
                    continue
                    
        # 4. Partial/fuzzy match
        if _partial_match(quote, full_text, threshold=0.75):
            finding['verification_status'] = 'needs_manual_review'
            continue
            
        finding['verification_status'] = 'unable_to_verify'
        
    return findings


def _normalize_whitespace(text):
    if not text:
        return ''
    text = text.replace('\ufb01', 'fi').replace('\ufb02', 'fl')
    text = text.replace('\ufb00', 'ff').replace('\ufb03', 'ffi').replace('\ufb04', 'ffl')
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('—', '-').replace('–', '-')
    text = text.replace('\u00a0', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\u00ad', '')
    text = re.sub(r'-\s*\n\s*', '', text)
    return text.strip()


def _normalized_match(quote, text):
    norm_quote = _normalize_whitespace(quote).lower()
    norm_text = _normalize_whitespace(text).lower()
    return norm_quote in norm_text


def _partial_match(quote, text, threshold=0.75):
    if not quote or not text:
        return False
    norm_quote = _normalize_whitespace(quote).lower()
    norm_text = _normalize_whitespace(text).lower()
    quote_words = norm_quote.split()
    if not quote_words:
        return False
    matched = sum(1 for w in quote_words if w in norm_text)
    return (matched / len(quote_words)) >= threshold


def _verify_pdf_highlight(finding, file_path):
    page_num = finding.get('page_number')
    quote = finding.get('evidence_quote', '')
    if not page_num or not quote:
        return
        
    try:
        import fitz
        doc = fitz.open(file_path)
        if page_num <= len(doc):
            page = doc[page_num - 1]
            search_text = quote[:40]
            rects = page.search_for(search_text)
            if not rects and len(quote) > 20:
                rects = page.search_for(quote[:20])
            if not rects:
                if finding.get('verification_status') == 'verified':
                    finding['verification_status'] = 'needs_manual_review'
        doc.close()
    except Exception:
        pass
