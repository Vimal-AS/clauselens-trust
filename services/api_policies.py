import json
from flask import Blueprint, jsonify, request
from database import get_db, DEFAULT_POLICIES
from datetime import datetime, timezone

policies_bp = Blueprint('policies', __name__)


@policies_bp.route('/api/policies', methods=['GET'])
def get_policies():
    conn = get_db()
    rows = conn.execute("SELECT * FROM policies ORDER BY is_custom, id").fetchall()
    conn.close()
    policies = []
    for row in rows:
        policies.append({
            'id': row['id'],
            'category': row['category'],
            'name': row['name'],
            'enabled': bool(row['enabled']),
            'config': json.loads(row['config']),
            'is_custom': bool(row['is_custom']),
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        })
    return jsonify({'policies': policies})


@policies_bp.route('/api/policies', methods=['PUT'])
def update_policies():
    data = request.get_json()
    if not data or 'policies' not in data:
        return jsonify({'error': 'Missing policies data.'}), 400
    
    conn = get_db()
    try:
        for p in data['policies']:
            pid = p.get('id')
            if not pid:
                continue
            
            config = p.get('config', {})
            # Validate config values
            if p.get('category') == 'payment':
                max_days = config.get('max_payment_days')
                if max_days is not None and (not isinstance(max_days, (int, float)) or max_days <= 0):
                    return jsonify({'error': 'Maximum payment days must be a positive number.'}), 400
            
            if p.get('category') == 'renewal':
                max_term = config.get('max_renewal_term_months')
                if max_term is not None and (not isinstance(max_term, (int, float)) or max_term <= 0):
                    return jsonify({'error': 'Maximum renewal term must be a positive number.'}), 400
                min_notice = config.get('min_cancellation_notice_days')
                if min_notice is not None and (not isinstance(min_notice, (int, float)) or min_notice <= 0):
                    return jsonify({'error': 'Minimum cancellation notice must be a positive number.'}), 400
            
            if p.get('category') == 'termination':
                min_notice = config.get('min_notice_days')
                if min_notice is not None and (not isinstance(min_notice, (int, float)) or min_notice <= 0):
                    return jsonify({'error': 'Minimum notice days must be a positive number.'}), 400
            
            if p.get('category') == 'jurisdiction':
                pref = config.get('preferred_jurisdiction', '')
                if isinstance(pref, str) and pref.strip() == '':
                    return jsonify({'error': 'Preferred jurisdiction cannot be empty.'}), 400

            conn.execute(
                "UPDATE policies SET name=?, enabled=?, config=?, updated_at=? WHERE id=?",
                (p.get('name', ''), 1 if p.get('enabled', True) else 0, json.dumps(config), datetime.now(timezone.utc).isoformat(), pid)
            )
        conn.commit()
        return jsonify({'message': 'Policies updated successfully.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': 'Failed to update policies.'}), 500
    finally:
        conn.close()


@policies_bp.route('/api/policies/custom', methods=['POST'])
def create_custom_policy():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing policy data.'}), 400
    
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Policy name is required.'}), 400
    
    config = data.get('config', {})
    match_type = config.get('match_type', 'must_contain')
    if match_type not in ('must_contain', 'must_not_contain', 'number_max'):
        return jsonify({'error': 'Invalid match type. Must be must_contain, must_not_contain, or number_max.'}), 400
    
    keywords = config.get('keywords', '')
    if not keywords:
        return jsonify({'error': 'Keywords are required.'}), 400
    
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO policies (category, name, enabled, config, is_custom) VALUES (?, ?, ?, ?, ?)",
            ('custom', name, 1 if data.get('enabled', True) else 0, json.dumps(config), 1)
        )
        conn.commit()
        policy_id = cursor.lastrowid
        return jsonify({'message': 'Custom policy created.', 'id': policy_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': 'Failed to create custom policy.'}), 500
    finally:
        conn.close()


@policies_bp.route('/api/policies/custom/<int:policy_id>', methods=['DELETE'])
def delete_custom_policy(policy_id):
    conn = get_db()
    row = conn.execute("SELECT is_custom FROM policies WHERE id=?", (policy_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Policy not found.'}), 404
    if not row['is_custom']:
        conn.close()
        return jsonify({'error': 'Cannot delete built-in policies.'}), 400
    conn.execute("DELETE FROM policies WHERE id=?", (policy_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Custom policy deleted.'})


@policies_bp.route('/api/policies/restore-defaults', methods=['POST'])
def restore_defaults():
    conn = get_db()
    try:
        conn.execute("DELETE FROM policies WHERE is_custom = 0")
        for p in DEFAULT_POLICIES:
            conn.execute(
                "INSERT INTO policies (category, name, enabled, config, is_custom) VALUES (?, ?, ?, ?, ?)",
                (p['category'], p['name'], p['enabled'], p['config'], p['is_custom'])
            )
        conn.commit()
        return jsonify({'message': 'Default policies restored.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': 'Failed to restore defaults.'}), 500
    finally:
        conn.close()
