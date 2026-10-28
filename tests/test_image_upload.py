"""Tests for Multiple Image Upload and Analysis in ClauseLens Trust."""

import io
import os
import json
import pytest
from PIL import Image, ImageDraw, ImageFilter
from app import app
from database import init_db, seed_default_policies, seed_default_settings


@pytest.fixture
def client():
    app.config['TESTING'] = True
    init_db()
    seed_default_policies()
    seed_default_settings()
    with app.test_client() as client:
        yield client


def _create_image_bytes(text="Contract clause text.", fmt="JPEG", size=(900, 300), blur=False):
    """Helper to generate in-memory image bytes with given text."""
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 40), text, fill="black")
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=10))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def test_upload_images_success(client):
    """Test uploading multiple valid contract images (JPG, PNG)."""
    img1 = _create_image_bytes("1. Payment shall be made Net 60 days.", fmt="JPEG")
    img2 = _create_image_bytes("2. Auto-renewal shall occur for 24 months.", fmt="PNG")

    data = {
        'images': [
            (img1, 'contract_page_1.jpg'),
            (img2, 'contract_page_2.png'),
        ]
    }
    res = client.post('/api/contracts/upload-images', data=data, content_type='multipart/form-data')
    assert res.status_code == 200
    res_data = res.json
    assert 'uploaded successfully' in res_data['message']
    file_info = res_data['file']
    assert file_info['file_type'] == 'images'
    assert file_info['total_images'] == 2
    assert 'contract_page_1.jpg' in file_info['original_filename']

    # Verify manifest on disk
    upload_folder = app.config['UPLOAD_FOLDER']
    batch_dir = os.path.join(upload_folder, file_info['uuid_name'])
    assert os.path.isdir(batch_dir)
    manifest_path = os.path.join(batch_dir, 'manifest.json')
    assert os.path.isfile(manifest_path)
    with open(manifest_path, 'r', encoding='utf-8') as mf:
        manifest = json.load(mf)
    assert manifest['total_images'] == 2
    assert manifest['images'][0]['original_filename'] == 'contract_page_1.jpg'
    assert manifest['images'][1]['original_filename'] == 'contract_page_2.png'


def test_upload_images_order_preserved(client):
    """Test that image order and original filenames are strictly preserved."""
    names = ['alpha_terms.png', 'beta_payment.jpg', 'gamma_renewal.png']
    img_list = [(_create_image_bytes(f"Clause in {name}", fmt='PNG' if name.endswith('.png') else 'JPEG'), name) for name in names]

    res = client.post('/api/contracts/upload-images', data={'images': img_list}, content_type='multipart/form-data')
    assert res.status_code == 200
    file_info = res.json['file']

    manifest_path = os.path.join(app.config['UPLOAD_FOLDER'], file_info['uuid_name'], 'manifest.json')
    with open(manifest_path, 'r', encoding='utf-8') as mf:
        manifest = json.load(mf)

    saved_names = [img['original_filename'] for img in manifest['images']]
    assert saved_names == names
    assert manifest['images'][0]['index'] == 1
    assert manifest['images'][1]['index'] == 2
    assert manifest['images'][2]['index'] == 3


def test_upload_images_unsupported_type(client):
    """Test rejecting unsupported file extensions."""
    fake_txt = io.BytesIO(b"Hello world text file")
    data = {'images': [(fake_txt, 'document.txt')]}
    res = client.post('/api/contracts/upload-images', data=data, content_type='multipart/form-data')
    assert res.status_code == 400
    assert 'unsupported' in res.json['error'].lower()


def test_upload_images_corrupt_file(client):
    """Test rejecting corrupted image files."""
    corrupt_jpg = io.BytesIO(b"\xff\xd8\xff\xe0" + b"garbage_corrupted_data_not_an_image")
    data = {'images': [(corrupt_jpg, 'broken.jpg')]}
    res = client.post('/api/contracts/upload-images', data=data, content_type='multipart/form-data')
    assert res.status_code == 400
    assert 'corrupt' in res.json['error'].lower() or 'unreadable' in res.json['error'].lower()


def test_upload_images_count_limit(client):
    """Test enforcing image count limit (max 20)."""
    # 21 images exceeds the limit
    imgs = [(_create_image_bytes(f"Page {i}", fmt="JPEG"), f"page_{i:02d}.jpg") for i in range(21)]
    res = client.post('/api/contracts/upload-images', data={'images': imgs}, content_type='multipart/form-data')
    assert res.status_code == 400
    assert 'Maximum of 20 images' in res.json['error']


def test_image_analysis_pipeline_and_findings(client):
    """Test passing extracted image text through the ClauseLens Trust analysis pipeline."""
    # Create two clear contract page images with standard policy triggers
    text_p1 = "1. Payment Terms. Invoices shall be payable within 60 days of receipt."
    text_p2 = "2. Auto-Renewal. This Agreement shall automatically renew for successive terms of 24 months."

    img1 = _create_image_bytes(text_p1, fmt="JPEG", size=(1000, 300))
    img2 = _create_image_bytes(text_p2, fmt="PNG", size=(1000, 300))

    up_res = client.post('/api/contracts/upload-images', data={
        'images': [(img1, 'contract_payment_p1.jpg'), (img2, 'contract_renewal_p2.png')]
    }, content_type='multipart/form-data')
    assert up_res.status_code == 200
    file_info = up_res.json['file']

    # Run analysis
    analyse_res = client.post('/api/contracts/analyse', json=file_info)
    assert analyse_res.status_code == 200
    ana_data = analyse_res.json
    analysis_id = ana_data['analysis_id']
    assert 'summary' in ana_data

    # Check analysis details & findings
    detail_res = client.get(f'/api/analyses/{analysis_id}')
    assert detail_res.status_code == 200
    detail = detail_res.json
    assert detail['analysis']['file_type'] == 'images'
    assert detail['analysis']['total_pages'] == 2

    findings = detail['findings']
    assert len(findings) >= 2

    # Verify findings contain source image filename and image number
    payment_finding = next((f for f in findings if f['category'] == 'payment' and f['result_type'] == 'conflict'), None)
    assert payment_finding is not None
    assert payment_finding['page_number'] == 1
    assert 'contract_payment_p1.jpg' in payment_finding['paragraph_reference']
    assert 'Image 1' in payment_finding['paragraph_reference']

    renewal_finding = next((f for f in findings if f['category'] == 'renewal' and f['result_type'] == 'conflict'), None)
    assert renewal_finding is not None
    assert renewal_finding['page_number'] == 2
    assert 'contract_renewal_p2.png' in renewal_finding['paragraph_reference']
    assert 'Image 2' in renewal_finding['paragraph_reference']


def test_image_blur_and_insufficient_text_warnings(client):
    """Test generating warnings when an image is blurry or contains insufficient text."""
    # Very blurry image
    blurry_img = _create_image_bytes("Payment shall be made within 60 days.", fmt="JPEG", blur=True)
    # Image with almost no text
    empty_img = _create_image_bytes("Hi", fmt="PNG")

    up_res = client.post('/api/contracts/upload-images', data={
        'images': [(blurry_img, 'blurry_page.jpg'), (empty_img, 'sparse_page.png')]
    }, content_type='multipart/form-data')
    assert up_res.status_code == 200
    file_info = up_res.json['file']

    analyse_res = client.post('/api/contracts/analyse', json=file_info)
    # Even with low text, if there are warnings they should be returned
    if analyse_res.status_code == 200:
        ana_data = analyse_res.json
        assert len(ana_data.get('warnings', [])) > 0
        w_text = ' '.join(ana_data['warnings']).lower()
        assert 'blurry' in w_text or 'insufficient' in w_text
    else:
        # Or if insufficient total text, clear error message returned
        assert 'insufficient' in analyse_res.json['error'].lower() or 'unreadable' in analyse_res.json['error'].lower()


def test_image_export_and_previews(client):
    """Test JSON export, PDF export, page preview, and source download for image analysis."""
    text_p1 = "1. Payment Terms. The Client shall pay all invoices within Net 60 days."
    img1 = _create_image_bytes(text_p1, fmt="JPEG")

    up_res = client.post('/api/contracts/upload-images', data={'images': [(img1, 'invoice_page.jpg')]}, content_type='multipart/form-data')
    file_info = up_res.json['file']
    file_info['is_sample'] = True

    ana_res = client.post('/api/contracts/analyse', json=file_info)
    assert ana_res.status_code == 200
    analysis_id = ana_res.json['analysis_id']

    # 1. JSON Export
    json_res = client.get(f'/api/analyses/{analysis_id}/export.json')
    assert json_res.status_code == 200
    export_data = json_res.json
    assert export_data['file_type'] == 'images'
    assert len(export_data['findings']) > 0

    # 2. PDF Export
    pdf_res = client.get(f'/api/analyses/{analysis_id}/export.pdf')
    assert pdf_res.status_code == 200
    assert pdf_res.headers['Content-Type'] == 'application/pdf'
    assert len(pdf_res.data) > 500

    # 3. Image page preview
    page_res = client.get(f'/api/analyses/{analysis_id}/page/1.png')
    assert page_res.status_code == 200
    assert 'image' in page_res.headers['Content-Type']

    # 4. Source images zip download
    src_res = client.get(f'/api/analyses/{analysis_id}/source-file')
    assert src_res.status_code == 200
    assert 'zip' in src_res.headers['Content-Type']

    # 5. Plain text view
    txt_res = client.get(f'/api/analyses/{analysis_id}/text')
    assert txt_res.status_code == 200
    assert txt_res.json['file_type'] == 'images'
    assert 'Payment' in txt_res.json['full_text']
