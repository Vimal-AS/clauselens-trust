import json
import os
from flask import Blueprint, jsonify, request, current_app, send_file
from database import get_db

analyses_bp = Blueprint('analyses', __name__)


@analyses_bp.route('/api/analyses', methods=['GET'])
def list_analyses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM analyses ORDER BY created_at DESC").fetchall()
    conn.close()
    analyses = []
    for row in rows:
        analyses.append({
            'id': row['id'],
            'original_filename': row['original_filename'],
            'file_type': row['file_type'],
            'file_size': row['file_size'],
            'status': row['status'],
            'total_pages': row['total_pages'],
            'is_sample': bool(row['is_sample']),
            'error_message': row['error_message'],
            'created_at': row['created_at'],
            'completed_at': row['completed_at']
        })
    return jsonify({'analyses': analyses})


@analyses_bp.route('/api/analyses/<analysis_id>', methods=['GET'])
def get_analysis(analysis_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Analysis not found.'}), 404
    
    findings = conn.execute("SELECT * FROM findings WHERE analysis_id=? ORDER BY id", (analysis_id,)).fetchall()
    conn.close()
    
    findings_list = []
    for f in findings:
        findings_list.append({
            'id': f['id'],
            'risk_id': f['risk_id'],
            'category': f['category'],
            'severity': f['severity'],
            'result_type': f['result_type'],
            'clause_title': f['clause_title'],
            'policy_expected': f['policy_expected'],
            'condition_detected': f['condition_detected'],
            'evidence_quote': f['evidence_quote'],
            'page_number': f['page_number'],
            'paragraph_reference': f['paragraph_reference'],
            'line_reference': f['line_reference'],
            'explanation': f['explanation'],
            'potential_impact': f['potential_impact'],
            'suggested_action': f['suggested_action'],
            'verification_status': f['verification_status'],
            'review_status': f['review_status'],
            'review_note': f['review_note'],
            'reviewed_at': f['reviewed_at'],
        })
    
    summary = {
        'total_findings': len(findings_list),
        'high': sum(1 for f in findings_list if f['severity'] == 'high'),
        'medium': sum(1 for f in findings_list if f['severity'] == 'medium'),
        'low': sum(1 for f in findings_list if f['severity'] == 'low'),
        'conflicts': sum(1 for f in findings_list if f['result_type'] == 'conflict'),
        'matches': sum(1 for f in findings_list if f['result_type'] == 'match'),
        'uncertain': sum(1 for f in findings_list if f['result_type'] == 'uncertain'),
        'not_found': sum(1 for f in findings_list if f['result_type'] == 'not_found'),
        'verified': sum(1 for f in findings_list if f['verification_status'] == 'verified'),
        'needs_review': sum(1 for f in findings_list if f['verification_status'] == 'needs_manual_review'),
        'unable_to_verify': sum(1 for f in findings_list if f['verification_status'] == 'unable_to_verify'),
    }
    
    warnings = []
    if row['error_message']:
        try:
            parsed = json.loads(row['error_message'])
            if isinstance(parsed, dict) and 'warnings' in parsed:
                warnings = parsed['warnings']
        except Exception:
            pass

    return jsonify({
        'analysis': {
            'id': row['id'],
            'original_filename': row['original_filename'],
            'file_type': row['file_type'],
            'file_size': row['file_size'],
            'status': row['status'],
            'total_pages': row['total_pages'],
            'total_paragraphs': row['total_paragraphs'],
            'is_sample': bool(row['is_sample']),
            'warnings': warnings,
            'created_at': row['created_at'],
            'completed_at': row['completed_at'],
        },
        'summary': summary,
        'findings': findings_list,
        'warnings': warnings
    })


@analyses_bp.route('/api/analyses/<analysis_id>/findings', methods=['GET'])
def get_analysis_findings(analysis_id):
    conn = get_db()
    row = conn.execute("SELECT id FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Analysis not found.'}), 404
    
    # Apply filters
    query = "SELECT * FROM findings WHERE analysis_id=?"
    params = [analysis_id]
    
    severity = request.args.get('severity')
    if severity and severity != 'all':
        query += " AND severity=?"
        params.append(severity)
    
    category = request.args.get('category')
    if category and category != 'all':
        query += " AND category=?"
        params.append(category)
    
    result_type = request.args.get('result_type')
    if result_type and result_type != 'all':
        query += " AND result_type=?"
        params.append(result_type)
    
    verification = request.args.get('verification')
    if verification and verification != 'all':
        query += " AND verification_status=?"
        params.append(verification)
    
    review = request.args.get('review')
    if review and review != 'all':
        query += " AND review_status=?"
        params.append(review)
    
    search = request.args.get('search')
    if search:
        query += " AND (evidence_quote LIKE ? OR clause_title LIKE ? OR explanation LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY id"
    findings = conn.execute(query, params).fetchall()
    conn.close()
    
    findings_list = []
    for f in findings:
        findings_list.append({
            'id': f['id'],
            'risk_id': f['risk_id'],
            'category': f['category'],
            'severity': f['severity'],
            'result_type': f['result_type'],
            'clause_title': f['clause_title'],
            'policy_expected': f['policy_expected'],
            'condition_detected': f['condition_detected'],
            'evidence_quote': f['evidence_quote'],
            'page_number': f['page_number'],
            'paragraph_reference': f['paragraph_reference'],
            'line_reference': f['line_reference'],
            'explanation': f['explanation'],
            'potential_impact': f['potential_impact'],
            'suggested_action': f['suggested_action'],
            'verification_status': f['verification_status'],
            'review_status': f['review_status'],
            'review_note': f['review_note'],
        })
    
    return jsonify({'findings': findings_list, 'count': len(findings_list)})


@analyses_bp.route('/api/analyses/<analysis_id>', methods=['DELETE'])
def delete_analysis(analysis_id):
    conn = get_db()
    row = conn.execute("SELECT filename FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Analysis not found.'}), 404
    
    # Delete uploaded file if it exists
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], row['filename'])
    if os.path.exists(file_path):
        os.remove(file_path)
    
    conn.execute("DELETE FROM findings WHERE analysis_id=?", (analysis_id,))
    conn.execute("DELETE FROM analyses WHERE id=?", (analysis_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Analysis deleted.'})


@analyses_bp.route('/api/analyses/<analysis_id>/export.json', methods=['GET'])
def export_json(analysis_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Analysis not found.'}), 404
    
    # Apply same filters
    query = "SELECT * FROM findings WHERE analysis_id=?"
    params = [analysis_id]
    
    severity = request.args.get('severity')
    if severity and severity != 'all':
        query += " AND severity=?"
        params.append(severity)
    
    category = request.args.get('category')
    if category and category != 'all':
        query += " AND category=?"
        params.append(category)
    
    result_type = request.args.get('result_type')
    if result_type and result_type != 'all':
        query += " AND result_type=?"
        params.append(result_type)
    
    verification = request.args.get('verification')
    if verification and verification != 'all':
        query += " AND verification_status=?"
        params.append(verification)
    
    review = request.args.get('review')
    if review and review != 'all':
        query += " AND review_status=?"
        params.append(review)
    
    search = request.args.get('search')
    if search:
        query += " AND (evidence_quote LIKE ? OR clause_title LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY id"
    findings = conn.execute(query, params).fetchall()
    
    # Get policies used
    policies = conn.execute("SELECT * FROM policies WHERE enabled=1").fetchall()
    conn.close()
    
    findings_list = []
    for f in findings:
        findings_list.append({
            'risk_id': f['risk_id'],
            'category': f['category'],
            'severity': f['severity'],
            'result_type': f['result_type'],
            'clause_title': f['clause_title'],
            'policy_expected': f['policy_expected'],
            'condition_detected': f['condition_detected'],
            'evidence_quote': f['evidence_quote'],
            'page_number': f['page_number'],
            'paragraph_reference': f['paragraph_reference'],
            'line_reference': f['line_reference'],
            'explanation': f['explanation'],
            'potential_impact': f['potential_impact'],
            'suggested_action': f['suggested_action'],
            'verification_status': f['verification_status'],
            'review_status': f['review_status'],
        })
    
    policies_list = []
    for p in policies:
        policies_list.append({
            'category': p['category'],
            'name': p['name'],
            'config': json.loads(p['config']),
        })
    
    warnings = []
    if row['error_message']:
        try:
            parsed = json.loads(row['error_message'])
            if isinstance(parsed, dict) and 'warnings' in parsed:
                warnings = parsed['warnings']
        except Exception:
            pass

    export = {
        'contract_name': row['original_filename'],
        'analysis_id': row['id'],
        'timestamp': row['completed_at'] or row['created_at'],
        'file_type': row['file_type'],
        'policies_used': policies_list,
        'warnings': warnings,
        'summary': {
            'total_findings': len(findings_list),
            'high': sum(1 for f in findings_list if f['severity'] == 'high'),
            'medium': sum(1 for f in findings_list if f['severity'] == 'medium'),
            'low': sum(1 for f in findings_list if f['severity'] == 'low'),
            'conflicts': sum(1 for f in findings_list if f['result_type'] == 'conflict'),
            'matches': sum(1 for f in findings_list if f['result_type'] == 'match'),
            'uncertain': sum(1 for f in findings_list if f['result_type'] == 'uncertain'),
            'not_found': sum(1 for f in findings_list if f['result_type'] == 'not_found'),
        },
        'findings': findings_list,
        'disclaimer': 'This report is generated by ClauseLens Trust, an informational tool for contract review. It does not constitute legal advice. Please consult a qualified legal professional for legal guidance.'
    }
    
    from flask import Response
    return Response(
        json.dumps(export, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=clauselens-{analysis_id}.json'}
    )


@analyses_bp.route('/api/analyses/<analysis_id>/export.pdf', methods=['GET'])
def export_pdf(analysis_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Analysis not found.'}), 404
    
    # Apply filters
    query = "SELECT * FROM findings WHERE analysis_id=?"
    params = [analysis_id]
    
    severity = request.args.get('severity')
    if severity and severity != 'all':
        query += " AND severity=?"
        params.append(severity)
    
    category = request.args.get('category')
    if category and category != 'all':
        query += " AND category=?"
        params.append(category)
    
    result_type = request.args.get('result_type')
    if result_type and result_type != 'all':
        query += " AND result_type=?"
        params.append(result_type)
    
    verification = request.args.get('verification')
    if verification and verification != 'all':
        query += " AND verification_status=?"
        params.append(verification)
    
    review = request.args.get('review')
    if review and review != 'all':
        query += " AND review_status=?"
        params.append(review)
    
    search = request.args.get('search')
    if search:
        query += " AND (evidence_quote LIKE ? OR clause_title LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    
    query += " ORDER BY id"
    findings = conn.execute(query, params).fetchall()
    
    policies = conn.execute("SELECT * FROM policies WHERE enabled=1").fetchall()
    conn.close()
    
    findings_list = [dict(f) for f in findings]
    for fl in findings_list:
        fl['config'] = None  # remove any extra fields
    
    policies_list = []
    for p in policies:
        policies_list.append({'category': p['category'], 'name': p['name'], 'config': json.loads(p['config'])})
    
    warnings = []
    if row['error_message']:
        try:
            parsed = json.loads(row['error_message'])
            if isinstance(parsed, dict) and 'warnings' in parsed:
                warnings = parsed['warnings']
        except Exception:
            pass

    from services.report_generator import generate_pdf_report
    pdf_path = generate_pdf_report(
        analysis_id=row['id'],
        contract_name=row['original_filename'],
        timestamp=row['completed_at'] or row['created_at'],
        findings=findings_list,
        policies=policies_list,
        reports_folder=current_app.config['REPORTS_FOLDER'],
        warnings=warnings
    )
    
    return send_file(pdf_path, mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f'clauselens-{analysis_id}.pdf')


@analyses_bp.route('/api/analyses/<analysis_id>/page/<int:page_num>.png', methods=['GET'])
def get_page_png(analysis_id, page_num):
    conn = get_db()
    row = conn.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Analysis not found.'}), 404

    # Support multiple images preview
    if row['file_type'] == 'images':
        folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], row['filename'])
        if not os.path.exists(folder_path):
            conn.close()
            return jsonify({'error': 'Source images are no longer stored on the server.'}), 404

        target_img_path = None
        orig_name = f'image-{page_num}.png'
        manifest_path = os.path.join(folder_path, 'manifest.json')
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, 'r', encoding='utf-8') as mf:
                    manifest = json.load(mf)
                for item in manifest.get('images', []):
                    if item.get('index') == page_num:
                        saved_fn = item.get('saved_filename') or item.get('original_filename')
                        cand = os.path.join(folder_path, saved_fn)
                        if os.path.isfile(cand):
                            target_img_path = cand
                            orig_name = item.get('original_filename', orig_name)
                            break
            except Exception:
                pass

        if not target_img_path:
            exts = ('.jpg', '.jpeg', '.png')
            img_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(exts)])
            if 1 <= page_num <= len(img_files):
                target_img_path = os.path.join(folder_path, img_files[page_num - 1])
                orig_name = img_files[page_num - 1]

        if not target_img_path or not os.path.exists(target_img_path):
            conn.close()
            return jsonify({'error': f'Image {page_num} not found.'}), 404

        conn.close()
        ext = target_img_path.rsplit('.', 1)[-1].lower()
        mimetype = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png'
        return send_file(target_img_path, mimetype=mimetype, as_attachment=False, download_name=orig_name)
        
    if row['file_type'] != 'pdf':
        conn.close()
        return jsonify({'error': 'Page preview is only supported for PDF and Image contracts.'}), 400
        
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], row['filename'])
    if not os.path.exists(file_path):
        conn.close()
        return jsonify({'error': 'Source PDF is no longer stored on the server.'}), 404
        
    finding_id = request.args.get('finding_id')
    highlight_text = None
    if finding_id:
        f_row = conn.execute("SELECT evidence_quote FROM findings WHERE id=? AND analysis_id=?", (finding_id, analysis_id)).fetchone()
        if f_row and f_row['evidence_quote']:
            highlight_text = f_row['evidence_quote']
            
    conn.close()
    
    try:
        import fitz
        import io
        doc = fitz.open(file_path)
        if page_num < 1 or page_num > len(doc):
            doc.close()
            return jsonify({'error': f'Page {page_num} out of range (1-{len(doc)}).'}), 404
            
        page = doc[page_num - 1]
        
        # Add highlight annotation if highlight_text is requested
        if highlight_text:
            search_str = highlight_text[:60].strip()
            rects = page.search_for(search_str)
            if not rects and len(highlight_text) > 30:
                rects = page.search_for(highlight_text[:30].strip())
            for r in rects:
                annot = page.add_highlight_annot(r)
                annot.update()
                
        # Render page to pixmap
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        doc.close()
        
        return send_file(
            io.BytesIO(img_bytes),
            mimetype='image/png',
            download_name=f'page-{page_num}.png'
        )
    except Exception as e:
        return jsonify({'error': f'Failed to render page image: {str(e)}'}), 500


@analyses_bp.route('/api/analyses/<analysis_id>/text', methods=['GET'])
def get_analysis_text(analysis_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Analysis not found.'}), 404
        
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], row['filename'])
    if not os.path.exists(file_path) and row['is_sample']:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate_dirs = [
            os.path.join(base_dir, 'demo_contracts'),
            os.path.join(base_dir, 'tests', 'fixtures')
        ]
        for cdir in candidate_dirs:
            if os.path.isdir(cdir):
                for f in os.listdir(cdir):
                    if f.lower() in row['original_filename'].lower() or row['original_filename'].lower() in f.lower():
                        file_path = os.path.join(cdir, f)
                        break
                if os.path.exists(file_path):
                    break
        if not os.path.exists(file_path):
            p_fallback = os.path.join(base_dir, 'demo_contracts', 'sample_freelance_contract.pdf')
            if os.path.exists(p_fallback):
                file_path = p_fallback
            
    if not os.path.exists(file_path):
        conn.close()
        return jsonify({'error': 'Source document text is not available on disk (upload file was deleted following extraction per data retention settings).'}), 404
        
    from services.document_extractor import extract_document
    extraction = extract_document(file_path, row['file_type'])
    conn.close()
    
    if extraction.get('error'):
        return jsonify({'error': extraction['error']}), 400
        
    full_text = extraction.get('full_text', '')
    sentences = extraction.get('sentences', [])
    
    return jsonify({
        'analysis_id': analysis_id,
        'filename': row['original_filename'],
        'file_type': row['file_type'],
        'character_count': len(full_text),
        'word_count': len(full_text.split()),
        'total_pages': row['total_pages'],
        'total_paragraphs': row['total_paragraphs'],
        'full_text': full_text,
        'sentences': [{'text': s['text'], 'page': s.get('page'), 'paragraph': s.get('paragraph'), 'line': s.get('line_ref')} for s in sentences]
    })


@analyses_bp.route('/api/analyses/<analysis_id>/source-file', methods=['GET'])
def get_analysis_source_file(analysis_id):
    """Directly view or download the source contract document for an analysis."""
    conn = get_db()
    row = conn.execute("SELECT filename, original_filename, file_type FROM analyses WHERE id=?", (analysis_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Analysis not found.'}), 404
        
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], row['filename'])
    if not os.path.exists(file_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate_dirs = [
            os.path.join(base_dir, 'demo_contracts'),
            os.path.join(base_dir, 'tests', 'fixtures')
        ]
        for cdir in candidate_dirs:
            if os.path.isdir(cdir):
                for f in os.listdir(cdir):
                    if f.lower() in row['original_filename'].lower() or row['original_filename'].lower() in f.lower():
                        file_path = os.path.join(cdir, f)
                        break
                if os.path.exists(file_path):
                    break
    if not os.path.exists(file_path):
        return jsonify({'error': 'Source file not found on server.'}), 404
        
    if row['file_type'] == 'images':
        import io
        import zipfile
        if os.path.isdir(file_path):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                exts = ('.jpg', '.jpeg', '.png')
                for f in sorted(os.listdir(file_path)):
                    if f.lower().endswith(exts):
                        zf.write(os.path.join(file_path, f), arcname=f)
            buf.seek(0)
            return send_file(buf, mimetype='application/zip', as_attachment=True, download_name=f'contract-images-{analysis_id}.zip')
        else:
            return send_file(file_path, as_attachment=True)

    mimetype = 'application/pdf' if row['file_type'] == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return send_file(file_path, mimetype=mimetype, as_attachment=False, download_name=row['original_filename'])


