from flask import Blueprint, jsonify, request
from database import get_db
from datetime import datetime, timezone

findings_bp = Blueprint('findings', __name__)


@findings_bp.route('/api/findings/<int:finding_id>/review', methods=['PATCH'])
def update_review(finding_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Missing data.'}), 400
    
    review_status = data.get('review_status')
    if review_status not in ('not_reviewed', 'reviewed', 'needs_attention'):
        return jsonify({'error': 'Invalid review status. Must be not_reviewed, reviewed, or needs_attention.'}), 400
    
    review_note = data.get('review_note', '')
    
    conn = get_db()
    row = conn.execute("SELECT id FROM findings WHERE id=?", (finding_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Finding not found.'}), 404
    
    conn.execute(
        "UPDATE findings SET review_status=?, review_note=?, reviewed_at=? WHERE id=?",
        (review_status, review_note, datetime.now(timezone.utc).isoformat(), finding_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'message': 'Review updated.'})
