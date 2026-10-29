import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'clauselens.db')


def get_db():
    """Get a database connection with row factory and generous busy timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            config TEXT NOT NULL DEFAULT '{}',
            is_custom INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            total_pages INTEGER,
            total_paragraphs INTEGER,
            extracted_text_length INTEGER,
            is_sample INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id TEXT NOT NULL,
            risk_id TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT,
            result_type TEXT NOT NULL,
            clause_title TEXT,
            policy_expected TEXT,
            condition_detected TEXT,
            evidence_quote TEXT,
            page_number INTEGER,
            paragraph_reference TEXT,
            line_reference TEXT,
            explanation TEXT,
            potential_impact TEXT,
            suggested_action TEXT,
            verification_status TEXT NOT NULL DEFAULT 'needs_manual_review',
            review_status TEXT NOT NULL DEFAULT 'not_reviewed',
            review_note TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_findings_analysis ON findings(analysis_id);
        CREATE INDEX IF NOT EXISTS idx_findings_category ON findings(category);
        CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
        CREATE INDEX IF NOT EXISTS idx_findings_result_type ON findings(result_type);
    ''')
    
    conn.commit()
    conn.close()


DEFAULT_POLICIES = [
    {
        'category': 'payment',
        'name': 'Payment Terms',
        'enabled': 1,
        'config': json.dumps({
            'max_payment_days': 30
        }),
        'is_custom': 0
    },
    {
        'category': 'renewal',
        'name': 'Auto-Renewal Terms',
        'enabled': 1,
        'config': json.dumps({
            'auto_renewal_allowed': False,
            'max_renewal_term_months': 12,
            'min_cancellation_notice_days': 30
        }),
        'is_custom': 0
    },
    {
        'category': 'liability',
        'name': 'Liability Terms',
        'enabled': 1,
        'config': json.dumps({
            'unlimited_liability_allowed': False,
            'require_liability_cap': True
        }),
        'is_custom': 0
    },
    {
        'category': 'termination',
        'name': 'Termination Terms',
        'enabled': 1,
        'config': json.dumps({
            'min_notice_days': 30,
            'flag_one_sided_termination': True
        }),
        'is_custom': 0
    },
    {
        'category': 'jurisdiction',
        'name': 'Jurisdiction',
        'enabled': 1,
        'config': json.dumps({
            'preferred_jurisdiction': 'India',
            'accepted_jurisdictions': ['India']
        }),
        'is_custom': 0
    }
]


def seed_default_policies():
    """Insert default policies if none exist."""
    conn = get_db()
    cursor = conn.cursor()
    count = cursor.execute("SELECT COUNT(*) FROM policies WHERE is_custom = 0").fetchone()[0]
    if count == 0:
        for p in DEFAULT_POLICIES:
            cursor.execute(
                "INSERT INTO policies (category, name, enabled, config, is_custom) VALUES (?, ?, ?, ?, ?)",
                (p['category'], p['name'], p['enabled'], p['config'], p['is_custom'])
            )
        conn.commit()
    conn.close()


def seed_default_settings():
    """Insert default settings if none exist."""
    conn = get_db()
    cursor = conn.cursor()
    defaults = {
        'theme': 'light',
        'language': 'en',
        'default_severity_filter': 'all',
        'default_category_filter': 'all',
        'keep_uploaded_files': 'false',
        'show_plain_english_explanations': 'false',
    }
    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    conn.close()
