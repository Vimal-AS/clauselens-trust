from flask import Blueprint, jsonify, request
from database import get_db
from datetime import datetime, timezone

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/api/settings', methods=['GET'])
def get_settings():
    conn = get_db()
    rows = conn.execute("SELECT * FROM settings").fetchall()
    conn.close()
    settings = {row['key']: row['value'] for row in rows}
    settings.setdefault('show_plain_english_explanations', 'false')
    return jsonify({'settings': settings})


@settings_bp.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.get_json()
    if not data or 'settings' not in data:
        return jsonify({'error': 'Missing settings data.'}), 400
    
    conn = get_db()
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        for key, value in data['settings'].items():
            conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?",
                (key, str(value), now_str, str(value), now_str)
            )
        conn.commit()
        return jsonify({'message': 'Settings updated.'})
    except Exception:
        conn.rollback()
        return jsonify({'error': 'Failed to update settings.'}), 500
    finally:
        conn.close()


@settings_bp.route('/api/settings/restore-defaults', methods=['POST'])
def restore_default_settings():
    conn = get_db()
    defaults = {
        'theme': 'light',
        'language': 'en',
        'default_severity_filter': 'all',
        'default_category_filter': 'all',
        'keep_uploaded_files': 'false',
        'show_plain_english_explanations': 'false',
    }
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        for key, value in defaults.items():
            conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?",
                (key, value, now_str, value, now_str)
            )
        conn.commit()
        return jsonify({'message': 'Default settings restored.'})
    except Exception:
        conn.rollback()
        return jsonify({'error': 'Failed to restore defaults.'}), 500
    finally:
        conn.close()


@settings_bp.route('/api/settings/delete-data', methods=['POST'])
def delete_all_data():
    import os
    from flask import current_app
    conn = get_db()
    try:
        conn.execute("DELETE FROM findings")
        conn.execute("DELETE FROM analyses")
        conn.commit()
        
        # Delete all uploaded files
        upload_dir = current_app.config['UPLOAD_FOLDER']
        for f in os.listdir(upload_dir):
            try:
                os.remove(os.path.join(upload_dir, f))
            except OSError:
                pass
        
        # Delete all reports
        reports_dir = current_app.config['REPORTS_FOLDER']
        for f in os.listdir(reports_dir):
            try:
                os.remove(os.path.join(reports_dir, f))
            except OSError:
                pass
        
        return jsonify({'message': 'All analysis data deleted.'})
    except Exception:
        conn.rollback()
        return jsonify({'error': 'Failed to delete data.'}), 500
    finally:
        conn.close()
