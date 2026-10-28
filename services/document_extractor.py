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
    elif file_type in ('images', 'image', 'jpg', 'jpeg', 'png'):
        return _extract_images(file_path)
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
        
        block_idx = 0
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # text block only
                continue
            block_idx += 1
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
                    'para_num': block_idx,
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
    cum_chars = 0
    
    # Body paragraphs
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        para_num += 1
        page_num = max(1, (cum_chars // 2200) + 1)
        paragraphs.append({
            'para_num': para_num,
            'page_num': page_num,
            'text': text,
            'source': f'Paragraph {para_num}',
            'style': para.style.name if para.style else None,
        })
        all_text_parts.append(text)
        cum_chars += len(text) + 1
    
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
                page_num = max(1, (cum_chars // 2200) + 1)
                source = f'Table {table_num}, row {row_idx + 1}, cell {cell_idx + 1}'
                paragraphs.append({
                    'para_num': para_num,
                    'page_num': page_num,
                    'text': text,
                    'source': source,
                })
                all_text_parts.append(text)
                cum_chars += len(text) + 1
    
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
                
                line_ref, para_num = _find_line_and_para_for_text(raw, page_info.get('lines', []))
                clause_title = _extract_clause_title(raw, page_text, idx)
                if clause_title:
                    current_clause_title = clause_title
                
                para_label = f"Paragraph {para_num}" if para_num else None
                sentences.append({
                    'text': raw,
                    'page': page_num,
                    'paragraph': para_num,
                    'paragraph_reference': para_label,
                    'line_ref': line_ref,
                    'clause_title': clause_title or current_clause_title,
                    'source': f'Page {page_num}' + (f', {para_label}' if para_label else ''),
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
    line_idx, _ = _find_line_and_para_for_text(text, lines)
    return line_idx


def _find_line_and_para_for_text(text, lines):
    """Find the line index and paragraph number for a piece of text within page lines."""
    if not lines:
        return None, 1
    
    text_clean = text.strip().lower()
    text_prefix = text_clean[:50]
    
    # 1. Prefix match
    for line in lines:
        lt = line['text'].strip().lower()
        if lt.startswith(text_prefix[:25]) or text_prefix.startswith(lt[:25]):
            return line['line_idx'] + 1, line.get('para_num', 1)
    
    # 2. Substring match
    for line in lines:
        lt = line['text'].strip().lower()
        if len(lt) >= 8 and (lt in text_clean or text_clean in lt):
            return line['line_idx'] + 1, line.get('para_num', 1)
        if len(text_prefix) >= 10 and text_prefix[:20] in lt:
            return line['line_idx'] + 1, line.get('para_num', 1)
    
    # 3. Word match fallback
    words = [w for w in text_clean.split() if len(w) > 4][:5]
    if words:
        for line in lines:
            lt = line['text'].strip().lower()
            if any(w in lt for w in words):
                return line['line_idx'] + 1, line.get('para_num', 1)

    # 4. Default to first line's paragraph
    return lines[0]['line_idx'] + 1, lines[0].get('para_num', 1)


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


def _configure_tesseract():
    """Ensure pytesseract has a valid tesseract_cmd on Windows/Linux."""
    try:
        import pytesseract
    except ImportError:
        return None, "pytesseract is not installed. Please install it with: pip install pytesseract"

    import shutil

    # 1. Configured via environment variable
    env_cmd = os.environ.get('TESSERACT_CMD')
    if env_cmd and os.path.isfile(env_cmd):
        pytesseract.pytesseract.tesseract_cmd = env_cmd
        return pytesseract, None

    # 2. Check if tesseract binary is already discoverable in PATH
    which_cmd = shutil.which('tesseract')
    if which_cmd:
        return pytesseract, None

    # 3. Known standard Windows installation locations
    candidates = [
        r'C:\Program Files\tesseract.exe',
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        os.path.expanduser(r'~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'),
    ]
    for p in candidates:
        if os.path.isfile(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return pytesseract, None

    return pytesseract, "Tesseract OCR binary not found. Please install Tesseract OCR on your system or set TESSERACT_CMD."


def _resolve_image_list(file_path):
    """Resolve ordered list of image dicts {index, original_filename, path} from file_path."""
    import json

    if os.path.isdir(file_path):
        manifest_path = os.path.join(file_path, 'manifest.json')
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                items = []
                for item in manifest.get('images', []):
                    img_name = item.get('saved_filename') or item.get('original_filename')
                    img_abs = os.path.join(file_path, img_name)
                    if os.path.isfile(img_abs):
                        items.append({
                            'index': item.get('index', len(items) + 1),
                            'original_filename': item.get('original_filename', img_name),
                            'path': img_abs,
                        })
                if items:
                    return items, None
            except Exception:
                pass

        exts = ('.jpg', '.jpeg', '.png')
        files = sorted([f for f in os.listdir(file_path) if f.lower().endswith(exts)])
        if not files:
            return None, "No image files found in upload directory."
        items = []
        for idx, fname in enumerate(files, 1):
            items.append({
                'index': idx,
                'original_filename': fname,
                'path': os.path.join(file_path, fname),
            })
        return items, None

    elif os.path.isfile(file_path):
        if file_path.lower().endswith('.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                return manifest.get('images', []), None
            except Exception as e:
                return None, f"Could not read image manifest: {e}"
        else:
            fname = os.path.basename(file_path)
            return [{
                'index': 1,
                'original_filename': fname,
                'path': file_path,
            }], None

    return None, f"Image path '{file_path}' not found."


def _check_image_quality(img, filename, img_num):
    """Inspect image for blurriness, corruption, or low readability."""
    warnings = []
    try:
        from PIL import ImageFilter, ImageStat
        gray = img.convert('L')
        w, h = img.size
        if w < 120 or h < 120:
            warnings.append(f"Image {img_num} ({filename}) has very low resolution ({w}x{h} px). Text may be unreadable.")
            return warnings, 0.0

        lap_kernel = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
        edges = gray.filter(lap_kernel)
        stat = ImageStat.Stat(edges)
        sharpness = stat.var[0]

        edge_find = gray.filter(ImageFilter.FIND_EDGES)
        edge_var = ImageStat.Stat(edge_find).var[0]

        # Blur threshold: severely blurred images have very low edge variance
        if sharpness < 40.0 and edge_var < 150.0:
            warnings.append(f"Image {img_num} ({filename}) appears blurry or low contrast (sharpness score: {sharpness:.1f}). OCR recognition accuracy may be reduced.")

        return warnings, sharpness
    except Exception:
        return warnings, 50.0


def _split_image_sentences(page_text, img_num, orig_name, img_lines):
    """Split extracted image text into sentences while tracking image location metadata."""
    sentences = []
    blocks = [b.strip() for b in page_text.split('\n\n') if b.strip()]
    if not blocks:
        blocks = [page_text]

    current_clause_title = None
    char_pos = 0

    for block_idx, block in enumerate(blocks):
        para_num = block_idx + 1
        raw_sentences = _split_into_sentences_raw(block)
        for raw in raw_sentences:
            raw = raw.strip()
            if not raw:
                continue

            idx = page_text.find(raw, char_pos)
            if idx == -1:
                idx = char_pos

            line_ref = _find_line_for_text(raw, img_lines)
            clause_title = _extract_clause_title(raw, page_text, idx)
            if clause_title:
                current_clause_title = clause_title

            para_label = f"Paragraph {para_num}"
            source_label = f"Image {img_num} ({orig_name}), {para_label}"
            sentences.append({
                'text': raw,
                'page': img_num,
                'paragraph': para_num,
                'paragraph_reference': source_label,
                'line_ref': line_ref,
                'clause_title': clause_title or current_clause_title,
                'source': source_label,
                'image_filename': orig_name,
                'image_number': img_num,
            })
            char_pos = idx + len(raw)

    return sentences


def _extract_images(file_path):
    """Extract text from one or more images using Tesseract OCR with location & quality tracking."""
    items, err = _resolve_image_list(file_path)
    if err:
        return {'error': err}

    try:
        from PIL import Image
    except ImportError:
        return {'error': 'Pillow is not installed. Please install it with: pip install Pillow'}

    pytesseract, tess_err = _configure_tesseract()
    if tess_err:
        return {'error': tess_err}

    pages = []
    all_text_parts = []
    all_lines = []
    all_sentences = []
    all_warnings = []

    for item in items:
        img_num = item.get('index', 1)
        orig_name = item.get('original_filename', f'Image_{img_num}')
        img_path = item.get('path')

        if not img_path or not os.path.exists(img_path):
            all_warnings.append(f"Image {img_num} ({orig_name}): File not found on disk.")
            continue

        try:
            with Image.open(img_path) as img:
                img_rgb = img.convert('RGB')
        except Exception as e:
            all_warnings.append(f"Image {img_num} ({orig_name}): Unable to read image file ({str(e)}). Image may be corrupted or unreadable.")
            continue

        # Check blurriness & resolution
        q_warnings, sharpness = _check_image_quality(img_rgb, orig_name, img_num)
        all_warnings.extend(q_warnings)

        # Run OCR
        try:
            ocr_text = pytesseract.image_to_string(img_rgb)
        except Exception as e:
            all_warnings.append(f"Image {img_num} ({orig_name}): OCR extraction failed ({str(e)}).")
            continue

        clean_text = ocr_text.strip()
        words = re.findall(r'\b[a-zA-Z0-9]{2,}\b', clean_text)
        if len(clean_text) < 25 or len(words) < 4:
            all_warnings.append(
                f"Image {img_num} ({orig_name}) contains insufficient readable text ({len(words)} words extracted). "
                f"Please verify this image contains readable contract terms."
            )

        img_lines = []
        page_text_parts = []
        line_idx = 0

        for raw_line in ocr_text.splitlines():
            line_str = raw_line.strip()
            if not line_str:
                continue
            line_idx += 1
            page_text_parts.append(line_str)
            line_info = {
                'text': line_str,
                'line_idx': line_idx,
                'page_num': img_num,
                'bbox': None,
            }
            img_lines.append(line_info)
            all_lines.append(line_info)

        img_page_text = "\n".join(page_text_parts)
        pages.append({
            'page_num': img_num,
            'filename': orig_name,
            'text': img_page_text,
            'lines': img_lines,
            'sharpness': sharpness,
        })

        if img_page_text:
            all_text_parts.append(img_page_text)
            img_sentences = _split_image_sentences(img_page_text, img_num, orig_name, img_lines)
            all_sentences.extend(img_sentences)

    full_text = "\n\n".join(all_text_parts)
    if len(full_text.strip()) < 20:
        return {
            'error': 'The uploaded images contain insufficient or unreadable text. OCR could not extract readable contract terms. Please ensure the images are clear, legible contract documents.',
            'warnings': all_warnings
        }

    return {
        'full_text': full_text,
        'sentences': all_sentences,
        'pages': pages,
        'paragraphs': None,
        'total_pages': len(items),
        'total_paragraphs': None,
        'all_lines': all_lines,
        'warnings': all_warnings,
        'error': None,
    }
