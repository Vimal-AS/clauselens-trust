"""Policy management service."""

import json
from database import get_db


def get_enabled_policies():
    """Get all enabled policies."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM policies WHERE enabled=1 ORDER BY id").fetchall()
    conn.close()
    
    policies = []
    for row in rows:
        policies.append({
            'id': row['id'],
            'category': row['category'],
            'name': row['name'],
            'enabled': True,
            'config': json.loads(row['config']),
            'is_custom': bool(row['is_custom']),
        })
    
    return policies


def get_all_policies():
    """Get all policies including disabled ones."""
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
        })
    
    return policies
