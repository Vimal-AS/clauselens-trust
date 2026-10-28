import os
import uuid
import zipfile
from flask import Blueprint, jsonify, request, current_app, send_file
from werkzeug.utils import secure_filename

contracts_bp = Blueprint('contracts', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png'}
PDF_MAGIC = b'%PDF'
DOCX_MAGIC = b'PK\x03\x04'
MAX_ZIP_RATIO = 100  # zip bomb guard
MAX_IMAGE_COUNT = 20
MAX_IMAGE_SIZE_BYTES = int(os.environ.get('UPLOAD_MAX_SIZE_MB', 50)) * 1024 * 1024  # Up to 50 MB per image
MAX_BATCH_SIZE_BYTES = MAX_IMAGE_SIZE_BYTES * 2  # Batch image limit


def _validate_image_file(file_storage):
    """Validate uploaded image file. Returns (ok, error_message, ext, size)."""
    if not file_storage or file_storage.filename == '':
        return False, 'No file selected.', None, 0

    filename = file_storage.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in IMAGE_EXTENSIONS:
        return False, f"File '{filename}' has an unsupported extension .{ext}. Please upload JPG, JPEG, or PNG images.", None, 0

    header = file_storage.read(8)
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)

    if size > MAX_IMAGE_SIZE_BYTES:
        max_mb = MAX_IMAGE_SIZE_BYTES // (1024 * 1024)
        return False, f"Image '{filename}' exceeds the {max_mb} MB size limit ({size / (1024*1024):.1f} MB).", None, size

    if ext in ('jpg', 'jpeg'):
        if header[:3] != b'\xff\xd8\xff':
            return False, f"File '{filename}' does not appear to be a valid JPEG image.", None, size
    elif ext == 'png':
        if header[:8] != b'\x89PNG\r\n\x1a\n':
            return False, f"File '{filename}' does not appear to be a valid PNG image.", None, size

    try:
        from PIL import Image
        img = Image.open(file_storage)
        img.verify()
        file_storage.seek(0)
    except Exception:
        file_storage.seek(0)
        return False, f"Image '{filename}' appears corrupted or unreadable.", None, size

    return True, None, ext, size


def _validate_file(file_storage):
    """Validate uploaded file. Returns (ok, error_message, file_type)."""
    if not file_storage or file_storage.filename == '':
        return False, 'No file selected.', None
    
    filename = file_storage.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    if ext not in ALLOWED_EXTENSIONS:
        return False, f'File type .{ext} is not supported. Please upload a PDF or DOCX file.', None
    
    # Read first bytes for magic number check
    header = file_storage.read(4)
    file_storage.seek(0)
    
    if ext == 'pdf':
        if header[:4] != PDF_MAGIC:
            return False, 'The file does not appear to be a valid PDF.', None
        file_type = 'pdf'
    elif ext == 'docx':
        if header[:4] != DOCX_MAGIC:
            return False, 'The file does not appear to be a valid DOCX file.', None
        file_type = 'docx'
        # Check for zip bomb
        try:
            file_storage.seek(0)
            content = file_storage.read()
            file_storage.seek(0)
            import io
            zf = zipfile.ZipFile(io.BytesIO(content))
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            compressed_size = len(content)
            if compressed_size > 0 and total_uncompressed / compressed_size > MAX_ZIP_RATIO:
                return False, 'File rejected: suspicious compression ratio.', None
            zf.close()
        except zipfile.BadZipFile:
            return False, 'The DOCX file appears to be corrupted.', None
    else:
        return False, 'Unsupported file type.', None
    
    return True, None, file_type


@contracts_bp.route('/api/contracts/upload-images', methods=['POST'])
def upload_contract_images():
    """Upload multiple contract page images (JPG, JPEG, PNG)."""
    files = request.files.getlist('images') or request.files.getlist('files')
    if not files and 'file' in request.files:
        files = request.files.getlist('file')

    if not files or all(not f or f.filename == '' for f in files):
        return jsonify({'error': 'No images provided for upload.'}), 400

    # Filter out empty entries
    files = [f for f in files if f and f.filename]

    if len(files) > MAX_IMAGE_COUNT:
        return jsonify({
            'error': f'Maximum of {MAX_IMAGE_COUNT} images allowed per upload. You selected {len(files)} images.'
        }), 400

    total_size = 0
    validated_files = []

    for f in files:
        ok, err, ext, size = _validate_image_file(f)
        if not ok:
            return jsonify({'error': err}), 400
        total_size += size
        validated_files.append((f, ext, size))

    if total_size > MAX_BATCH_SIZE_BYTES:
        return jsonify({
            'error': f'Total upload size exceeds 50 MB limit ({total_size / (1024*1024):.1f} MB).'
        }), 400

    import json
    batch_uuid = uuid.uuid4().hex
    folder_name = f"{batch_uuid}.images"
    folder_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(folder_path, exist_ok=True)

    manifest_images = []
    for idx, (f, ext, size) in enumerate(validated_files, 1):
        clean_name = secure_filename(f.filename) or f"image_{idx}.{ext}"
        saved_name = f"{idx:03d}_{clean_name}"
        save_path = os.path.join(folder_path, saved_name)
        f.save(save_path)
        manifest_images.append({
            'index': idx,
            'original_filename': f.filename,
            'saved_filename': saved_name,
            'file_size': size,
            'ext': ext,
        })

    manifest = {
        'batch_id': batch_uuid,
        'file_type': 'images',
        'total_images': len(manifest_images),
        'total_size': total_size,
        'images': manifest_images,
    }

    with open(os.path.join(folder_path, 'manifest.json'), 'w', encoding='utf-8') as mf:
        json.dump(manifest, mf, indent=2)

    first_names = [item['original_filename'] for item in manifest_images[:2]]
    more_count = len(manifest_images) - len(first_names)
    display_title = f"{len(manifest_images)} Images: {', '.join(first_names)}{' (+' + str(more_count) + ' more)' if more_count > 0 else ''}"

    return jsonify({
        'message': f'{len(manifest_images)} images uploaded successfully.',
        'file': {
            'uuid_name': folder_name,
            'original_filename': display_title,
            'file_type': 'images',
            'file_size': total_size,
            'total_images': len(manifest_images),
            'is_sample': False
        }
    })


@contracts_bp.route('/api/contracts/upload', methods=['POST'])
def upload_contract():
    if 'images' in request.files:
        return upload_contract_images()

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided.'}), 400
    
    file = request.files['file']
    ok, error, file_type = _validate_file(file)
    if not ok:
        return jsonify({'error': error}), 400
    
    # Check file size (already handled by Flask MAX_CONTENT_LENGTH, but double-check)
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024)
    if file_size > max_size:
        return jsonify({'error': f'File too large. Maximum size is {max_size // (1024*1024)} MB.'}), 400
    
    # Save with UUID filename
    original_filename = secure_filename(file.filename)
    uuid_name = f"{uuid.uuid4().hex}.{file_type}"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], uuid_name)
    file.save(save_path)
    
    # Check for encrypted PDF
    if file_type == 'pdf':
        try:
            import fitz
            doc = fitz.open(save_path)
            if doc.is_encrypted:
                doc.close()
                os.remove(save_path)
                return jsonify({'error': 'This PDF is encrypted. Please provide an unencrypted version.'}), 400
            doc.close()
        except Exception:
            os.remove(save_path)
            return jsonify({'error': 'Could not open the PDF file. It may be corrupted.'}), 400
    
    is_sample = request.form.get('is_sample', '0') == '1'
    
    return jsonify({
        'message': 'File uploaded successfully.',
        'file': {
            'uuid_name': uuid_name,
            'original_filename': original_filename,
            'file_type': file_type,
            'file_size': file_size,
            'is_sample': is_sample
        }
    })


DEMO_CONTRACTS = [
    {
        'id': 'sample_freelance',
        'filename': 'sample_freelance_contract.pdf',
        'display_name': 'Sample_Freelance_Agreement.pdf',
        'title': 'Freelance Service Agreement',
        'file_type': 'pdf',
        'risk_badge': 'High Risk',
        'conflicts_summary': '4 Conflicts (Payment, Renewal, Liability, Jurisdiction)',
        'description': 'Net 60 days, auto-renewal with 90-day cancellation notice, unlimited liability, Singapore courts.'
    },
    {
        'id': 'vendor_supply',
        'filename': 'vendor_agreement.docx',
        'display_name': 'Vendor_Supply_Agreement.docx',
        'title': 'Vendor Supply Agreement',
        'file_type': 'docx',
        'risk_badge': 'High Risk',
        'conflicts_summary': '3 Conflicts (Net 45, 24-Mo Renewal, Uncapped Liability)',
        'description': 'Net 45 payment, 24-month renewal term, uncapped liability & broad indemnity, London courts.'
    },
    {
        'id': 'nda_strict',
        'filename': 'nda_strict_confidentiality.pdf',
        'display_name': 'Strict_Mutual_NDA.pdf',
        'title': 'Strict Mutual NDA',
        'file_type': 'pdf',
        'risk_badge': 'High Risk',
        'conflicts_summary': '3 Conflicts (Net 60, Unlimited Indemnity, California Law)',
        'description': '60-day invoice disbursement, unlimited broad indemnity, California USA governing jurisdiction.'
    },
    {
        'id': 'software_saas',
        'filename': 'software_license_agreement.docx',
        'display_name': 'Software_Subscription_Agreement.docx',
        'title': 'SaaS Subscription Contract',
        'file_type': 'docx',
        'risk_badge': 'Medium Risk',
        'conflicts_summary': '3 Conflicts (Net 60, 15-Day Unilateral Termination, Singapore Law)',
        'description': '60-day invoicing, 15-day unilateral termination right, Singapore governing law.'
    },
    {
        'id': 'ambiguous_payment',
        'filename': 'ambiguous_payment_contract.pdf',
        'display_name': 'Standard_Consulting_Agreement.pdf',
        'title': 'Technical Advisory Agreement',
        'file_type': 'pdf',
        'risk_badge': 'Ambiguous Terms',
        'conflicts_summary': '1 Uncertain (Within a reasonable time), 0 Conflicts',
        'description': 'Payment timing "within a reasonable time", capped liability, Indian jurisdiction (Chennai).'
    },
    {
        'id': 'clean_compliant',
        'filename': 'clean_compliant_contract.pdf',
        'display_name': 'Master_Services_Agreement_Compliant.pdf',
        'title': 'Clean Master Services Agreement',
        'file_type': 'pdf',
        'risk_badge': 'Compliant',
        'conflicts_summary': '0 Conflicts (5 Matches, Net 15, Liability Cap)',
        'description': 'Net 15 days, no auto-renewal, clear liability cap, Indian jurisdiction (Mumbai).'
    },
    {
        'id': 'consulting_milestones',
        'filename': 'consulting_contract.docx',
        'display_name': 'Professional_Services_Contract.docx',
        'title': 'Consulting Milestone Agreement',
        'file_type': 'docx',
        'risk_badge': 'Compliant',
        'conflicts_summary': '0 Conflicts (Milestone advance payment, table format)',
        'description': 'Advance payment schedule, milestone tables, 60-day mutual termination, Chennai courts.'
    }
]


@contracts_bp.route('/api/contracts/demo-list', methods=['GET'])
def get_demo_list():
    return jsonify({'demos': DEMO_CONTRACTS})


def _get_demo_fixture_path(filename):
    """Find demo file path in demo_contracts/ or tests/fixtures/."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Check dedicated demo_contracts directory first
    p1 = os.path.join(base_dir, 'demo_contracts', filename)
    if os.path.exists(p1):
        return p1
    # Fallback to tests/fixtures
    p2 = os.path.join(base_dir, 'tests', 'fixtures', filename)
    if os.path.exists(p2):
        return p2
    return None


@contracts_bp.route('/api/contracts/demo', methods=['POST'])
def load_demo_contract():
    import shutil
    data = request.get_json(silent=True) or {}
    demo_id = data.get('demo_id') or request.args.get('demo_id') or 'sample_freelance'
    
    selected_demo = next((d for d in DEMO_CONTRACTS if d['id'] == demo_id), DEMO_CONTRACTS[0])
    
    fixture_path = _get_demo_fixture_path(selected_demo['filename'])
    if not fixture_path or not os.path.exists(fixture_path):
        return jsonify({'error': f"Demo contract '{selected_demo['filename']}' not found on server."}), 404
        
    ext = selected_demo['file_type']
    uuid_name = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], uuid_name)
    shutil.copyfile(fixture_path, save_path)
    file_size = os.path.getsize(save_path)
    
    return jsonify({
        'message': f"Demo contract '{selected_demo['title']}' loaded.",
        'file': {
            'uuid_name': uuid_name,
            'original_filename': selected_demo['display_name'],
            'file_type': ext,
            'file_size': file_size,
            'is_sample': True,
            'demo_id': selected_demo['id'],
            'title': selected_demo['title']
        }
    })


@contracts_bp.route('/api/contracts/demo/<demo_id>/file', methods=['GET'])
def get_demo_file(demo_id):
    """Directly view or download a demo PDF or DOCX file."""
    selected_demo = next((d for d in DEMO_CONTRACTS if d['id'] == demo_id), None)
    if not selected_demo:
        return jsonify({'error': 'Demo contract not found.'}), 404
        
    fixture_path = _get_demo_fixture_path(selected_demo['filename'])
    if not fixture_path or not os.path.exists(fixture_path):
        return jsonify({'error': 'File not found on server.'}), 404
        
    mimetype = 'application/pdf' if selected_demo['file_type'] == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    as_attachment = request.args.get('download', 'false').lower() == 'true' or selected_demo['file_type'] == 'docx'
    return send_file(fixture_path, mimetype=mimetype, as_attachment=as_attachment, download_name=selected_demo['display_name'])


@contracts_bp.route('/api/contracts/file/<uuid_name>', methods=['GET'])
def get_uploaded_file(uuid_name):
    """Directly view or download an uploaded contract file."""
    safe_name = os.path.basename(uuid_name)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_name)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found.'}), 404
        
    ext = safe_name.split('.')[-1].lower()
    mimetype = 'application/pdf' if ext == 'pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    return send_file(file_path, mimetype=mimetype, as_attachment=False)


@contracts_bp.route('/api/contracts/analyse', methods=['POST'])
def analyse_contract():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing request data.'}), 400
    
    uuid_name = data.get('uuid_name')
    original_filename = data.get('original_filename', 'unknown')
    file_type = data.get('file_type')
    file_size = data.get('file_size', 0)
    is_sample = data.get('is_sample', False)
    
    if not uuid_name or not file_type:
        return jsonify({'error': 'Missing file information.'}), 400
    
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], uuid_name)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Uploaded file not found. Please re-upload.'}), 404
    
    # Generate analysis ID
    analysis_id = uuid.uuid4().hex[:12]
    
    try:
        # Step 1: Extract text
        from services.document_extractor import extract_document
        extraction = extract_document(file_path, file_type)
        
        if extraction.get('error'):
            from database import get_db
            from datetime import datetime, timezone
            conn = get_db()
            conn.execute(
                "INSERT INTO analyses (id, filename, original_filename, file_type, file_size, status, is_sample, error_message, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (analysis_id, uuid_name, original_filename, file_type, file_size, 'error', 1 if is_sample else 0, extraction['error'], datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            conn.close()
            return jsonify({'error': extraction['error']}), 400
        
        # Step 2: Get policies
        from services.policy_manager import get_enabled_policies
        policies = get_enabled_policies()
        
        # Step 3: Run detection
        from services.clause_detector import detect_all
        raw_findings = detect_all(extraction, policies)
        
        # Step 4: Apply risk engine
        from services.risk_engine import assess_risks
        findings = assess_risks(raw_findings, policies)
        
        # Step 4b: Apply language template if configured
        from database import get_db as gdb_lang
        c_lang = gdb_lang()
        lang_row = c_lang.execute("SELECT value FROM settings WHERE key='language'").fetchone()
        c_lang.close()
        current_lang = lang_row['value'] if lang_row else 'en'
        if current_lang == 'ta':
            from services.translations import get_tamil_explanation
            for f in findings:
                cat = f.get('category', '')
                rt = f.get('result_type', '')
                ta_exp = get_tamil_explanation(cat, rt)
                if ta_exp:
                    f['explanation'] = f"{f.get('explanation', '')} ({ta_exp})"
        
        # Step 5: Verify evidence
        from services.evidence_verifier import verify_findings
        findings = verify_findings(findings, extraction, file_path, file_type)
        
        # Step 6: Store results
        from database import get_db
        from datetime import datetime, timezone
        import json
        conn = get_db()
        
        warnings = extraction.get('warnings', [])
        warn_data = json.dumps({'warnings': warnings}) if warnings else None

        conn.execute(
            "INSERT INTO analyses (id, filename, original_filename, file_type, file_size, status, total_pages, total_paragraphs, extracted_text_length, is_sample, error_message, created_at, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (analysis_id, uuid_name, original_filename, file_type, file_size, 'completed',
             extraction.get('total_pages'), extraction.get('total_paragraphs'),
             len(extraction.get('full_text', '')), 1 if is_sample else 0,
             warn_data,
             datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
        )
        
        for f in findings:
            conn.execute(
                """INSERT INTO findings (analysis_id, risk_id, category, severity, result_type, clause_title,
                policy_expected, condition_detected, evidence_quote, page_number, paragraph_reference,
                line_reference, explanation, potential_impact, suggested_action, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (analysis_id, f.get('risk_id', ''), f.get('category', ''), f.get('severity'),
                 f.get('result_type', 'not_found'), f.get('clause_title'),
                 f.get('policy_expected', ''), f.get('condition_detected', ''),
                 f.get('evidence_quote', ''), f.get('page_number'),
                 f.get('paragraph_reference'), f.get('line_reference'),
                 f.get('explanation', ''), f.get('potential_impact', ''),
                 f.get('suggested_action', ''), f.get('verification_status', 'needs_manual_review'))
            )
        
        conn.commit()
        conn.close()
        
        # Optionally delete uploaded file (preserve samples and if keep_uploaded_files is true)
        from database import get_db as gdb
        c2 = gdb()
        keep = c2.execute("SELECT value FROM settings WHERE key='keep_uploaded_files'").fetchone()
        c2.close()
        if not is_sample and keep and keep['value'] == 'false':
            try:
                if os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path, ignore_errors=True)
                else:
                    os.remove(file_path)
            except OSError:
                pass
        
        return jsonify({
            'message': 'Analysis complete.',
            'analysis_id': analysis_id,
            'warnings': warnings,
            'summary': {
                'total_findings': len(findings),
                'conflicts': sum(1 for f in findings if f.get('result_type') == 'conflict'),
                'matches': sum(1 for f in findings if f.get('result_type') == 'match'),
                'uncertain': sum(1 for f in findings if f.get('result_type') == 'uncertain'),
                'not_found': sum(1 for f in findings if f.get('result_type') == 'not_found'),
                'high': sum(1 for f in findings if f.get('severity') == 'high'),
                'medium': sum(1 for f in findings if f.get('severity') == 'medium'),
                'low': sum(1 for f in findings if f.get('severity') == 'low'),
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Analysis failed. Please try again.'}), 500
