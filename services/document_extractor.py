"""Document text extraction with location tracking for PDF and DOCX files."""

import re
import os


def extract_document(file_path, file_type):
    """Extract text from a document with location information.
    
    Returns dict with:
        - full_text: complete extracted text
        - sentences: list of {text, start, end, page, paragraph, line, clause_title}
        - pages: list of {page_num, text, lines: [{text, bbox, line_idx}]}  (PDF only)
        - paragraphs: list of {para_num, text, source}  (DOCX)
        - total_pages: int or None
        - total_paragraphs: int or None
        - error: str or None
    """
    if file_type == 'pdf':
        return _extract_pdf(file_path)
    elif file_type == 'docx':
        return _extract_docx(file_path)
    else:
        return {'error': f'Unsupported file type: {file_type}'}


def _extract_pdf(file_path):
    """Extract text from PDF using PyMuPDF with page and line tracking."""
    try:
        import fitz
    except ImportError:
        return {'error': 'PyMuPDF is not installed. Please install it with: pip install PyMuPDF'}
    
    try:
        doc = fitz.open(file_path)
    except Exception:
        return {'error': 'Could not open the PDF file. It may be corrupted.'}
    
    if doc.is_encrypted:
        doc.close()
        return {'error': 'This PDF is encrypted. Please provide an unencrypted version.'}
    
    pages = []
    all_text_parts = []
    all_lines = []
    global_char_offset = 0
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        page_text_parts = []
        page_lines = []
        line_idx = 0
        
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # text block only
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                line_text = "".join(span.get("text", "") for span in spans).strip()
                if not line_text:
                    continue
                
                bbox = line.get("bbox", None)
                
                page_lines.append({
                    'text': line_text,
                    'bbox': list(bbox) if bbox else None,
                    'line_idx': line_idx,
                    'page_num': page_num + 1,
                    'char_offset': global_char_offset + sum(len(t) + 1 for t in page_text_parts),
                })
                page_text_parts.append(line_text)
                line_idx += 1
        
        page_text = "\n".join(page_text_parts)
        
        pages.append({
            'page_num': page_num + 1,
            'text': page_text,
            'lines': page_lines,
        })
        
        if page_text:
            all_text_parts.append(page_text)
            all_lines.extend(page_lines)
        
        global_char_offset += len(page_text) + 1
    
    doc.close()
    
    full_text = "\n".join(all_text_parts)
    
    # Check for scanned/empty PDF
    if len(full_text.strip()) < 50:
        return {
            'error': 'This PDF appears to be scanned or contains no extractable text. OCR is required to analyse this document, which is not available in the current configuration.'
        }
    
    sentences = _split_sentences(full_text, pages, 'pdf')
    
    return {
        'full_text': full_text,
        'sentences': sentences,
        'pages': pages,
        'paragraphs': None,
        'total_pages': len(pages),
        'total_paragraphs': None,
        'all_lines': all_lines,
        'error': None,
    }


def _extract_docx(file_path):
    """Extract text from DOCX with paragraph tracking."""
    try:
        from docx import Document
    except ImportError:
        return {'error': 'python-docx is not installed. Please install it with: pip install python-docx'}
    
    try:
        doc = Document(file_path)
    except Exception:
        return {'error': 'Could not open the DOCX file. It may be corrupted.'}
    
    paragraphs = []
    all_text_parts = []
    para_num = 0
    
    # Body paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        para_num += 1
        paragraphs.append({
            'para_num': para_num,
            'text': text,
            'source': f'Paragraph {para_num}',
            'style': para.style.name if para.style else None,
        })
        all_text_parts.append(text)
    
    # Table cells
    table_num = 0
    for table in doc.tables:
        table_num += 1
        for row_idx, row in enumerate(table.rows):
            for cell_idx, cell in enumerate(row.cells):
                text = cell.text.strip()
                if not text:
                    continue
                para_num += 1
                source = f'Table {table_num}, row {row_idx + 1}, cell {cell_idx + 1}'
                paragraphs.append({
                    'para_num': para_num,
                    'text': text,
                    'source': source,
                })
                all_text_parts.append(text)
    
    # Headers and footers
    for section in doc.sections:
        for header_footer, label in [(section.header, 'Header'), (section.footer, 'Footer')]:
            if header_footer and header_footer.paragraphs:
                for para in header_footer.paragraphs:
                    text = para.text.strip()
                    if text:
                        para_num += 1
                        paragraphs.append({
                            'para_num': para_num,
                            'text': text,
                            'source': label,
                        })
                        all_text_parts.append(text)
    
    full_text = "\n".join(all_text_parts)
    
    if len(full_text.strip()) < 10:
        return {'error': 'The DOCX file appears to be empty or contains no extractable text.'}
    
    sentences = _split_sentences(full_text, None, 'docx', paragraphs=paragraphs)
    
    return {
        'full_text': full_text,
        'sentences': sentences,
        'pages': None,
        'paragraphs': paragraphs,
        'total_pages': None,
        'total_paragraphs': para_num,
        'all_lines': None,
        'error': None,
    }


LEGAL_ABBREVIATIONS = (
    'e.g.', 'i.e.', 'etc.', 'vs.', 'al.', 'ltd.', 'inc.', 'corp.', 'co.',
    'no.', 'sec.', 'art.', 'para.', 'cl.', 'pvt.', 'u.s.', 'u.k.', 'dept.',
    'approx.', 'govt.', 'reg.', 'ref.', 'v.', 'jan.', 'feb.', 'mar.', 'apr.',
    'jun.', 'jul.', 'aug.', 'sep.', 'sept.', 'oct.', 'nov.', 'dec.'
)


def _split_into_sentences_raw(text):
    """Split text into sentences, protecting legal abbreviations and numbers."""
    if not text:
        return []
    
    # Protect legal abbreviations by replacing their period with a placeholder
    protected_text = text
    placeholder_map = {}
    for i, abbr in enumerate(LEGAL_ABBREVIATIONS):
        pattern = re.compile(re.escape(abbr), re.IGNORECASE)
        for m in pattern.finditer(protected_text):
            matched_str = m.group(0)
            token = f"__ABBR_{i}_{len(placeholder_map)}__"
            placeholder_map[token] = matched_str
            protected_text = protected_text.replace(matched_str, token)
    
    # Protect decimal numbers (e.g., 1.5, 30.00)
    for m in re.finditer(r'\b\d+\.\d+\b', protected_text):
        num_str = m.group(0)
        token = f"__DEC_{len(placeholder_map)}__"
        placeholder_map[token] = num_str
        protected_text = protected_text.replace(num_str, token)

    # Standard sentence split on punctuation followed by whitespace and uppercase/quote/bracket
    pattern = r'(?<=[.!?;])\s+(?=[A-Z"\(\[])'
    parts = re.split(pattern, protected_text)
    
    # Restore placeholders in each sentence
    restored_sentences = []
    for part in parts:
        restored = part
        for token, original in placeholder_map.items():
            if token in restored:
                restored = restored.replace(token, original)
        restored = restored.strip()
        if restored:
            restored_sentences.append(restored)
            
    return restored_sentences


def _split_sentences(full_text, pages, file_type, paragraphs=None):
    """Split text into sentences while preserving location information and section headers."""
    sentences = []
    current_clause_title = None
    
    if file_type == 'pdf' and pages:
        for page_info in pages:
            page_text = page_info['text']
            page_num = page_info['page_num']
            if not page_text.strip():
                continue
            
            raw_sentences = _split_into_sentences_raw(page_text)
            char_pos = 0
            for raw in raw_sentences:
                raw = raw.strip()
                if not raw:
                    continue
                
                idx = page_text.find(raw, char_pos)
                if idx == -1:
                    idx = char_pos
                
                line_ref = _find_line_for_text(raw, page_info.get('lines', []))
                clause_title = _extract_clause_title(raw, page_text, idx)
                if clause_title:
                    current_clause_title = clause_title
                
                sentences.append({
                    'text': raw,
                    'page': page_num,
                    'paragraph': None,
                    'paragraph_reference': None,
                    'line_ref': line_ref,
                    'clause_title': clause_title or current_clause_title,
                    'source': f'Page {page_num}',
                })
                
                char_pos = idx + len(raw)
    
    elif file_type == 'docx' and paragraphs:
        for para_info in paragraphs:
            para_text = para_info['text']
            para_num = para_info['para_num']
            source = para_info['source']
            
            raw_sentences = _split_into_sentences_raw(para_text)
            
            for raw in raw_sentences:
                raw = raw.strip()
                if not raw:
                    continue
                
                clause_title = _extract_clause_title(raw, para_text, 0)
                if clause_title:
                    current_clause_title = clause_title
                
                sentences.append({
                    'text': raw,
                    'page': None,
                    'paragraph': para_num,
                    'paragraph_reference': source,
                    'line_ref': None,
                    'clause_title': clause_title or current_clause_title,
                    'source': source,
                })
    
    return sentences


def _find_line_for_text(text, lines):
    """Find the line index for a piece of text within page lines."""
    if not lines:
        return None
    
    text_lower = text.lower()[:60]
    for line in lines:
        if line['text'].lower().startswith(text_lower[:30]) or text_lower.startswith(line['text'].lower()[:30]):
            return line['line_idx'] + 1
    
    for line in lines:
        if text[:20].lower() in line['text'].lower():
            return line['line_idx'] + 1
    
    return None


def _extract_clause_title(sentence_text, full_context, position):
    """Extract a clause number/title if present at or before the sentence."""
    clause_pattern = r'^(\d+(?:\.\d+)*\.?\s*)'
    match = re.match(clause_pattern, sentence_text)
    if match:
        return match.group(1).strip()
    
    section_pattern = r'^((?:Section|Clause|Article|Schedule)\s+\d+(?:\.\d+)*)'
    match = re.match(section_pattern, sentence_text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    if position > 0:
        before = full_context[max(0, position - 200):position].strip()
        lines = before.split('\n')
        if lines:
            last_line = lines[-1].strip()
            heading_match = re.match(r'^(\d+(?:\.\d+)*\.?\s+.{3,60})$', last_line)
            if heading_match and len(last_line) < 80:
                return heading_match.group(1).strip()
    
    return None
