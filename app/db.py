"""SQLite storage with idempotent schema migrations for demo and extensions."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get('JOBFINDER_DB', str(ROOT / 'local_demo.sqlite3')))


@contextmanager
def connection():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def _ensure_columns(db: sqlite3.Connection, table: str, columns: dict[str, str]):
    existing = {r['name'] for r in db.execute(f'PRAGMA table_info({table})').fetchall()}
    for col_name, col_def in columns.items():
        if col_name not in existing:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_def}')


def init_db():
    with connection() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, company TEXT NOT NULL, description TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL DEFAULT 'demo'
        );
        CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK (id = 1), resume TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL,
            tailored_resume TEXT NOT NULL, fit_score INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft', confirmation TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(job_id)
        );
        CREATE TABLE IF NOT EXISTS outreach (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL,
            contact_name TEXT NOT NULL, contact_role TEXT NOT NULL,
            contact_profile TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL, body TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            company TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            source_url TEXT NOT NULL,
            linkedin_url TEXT NOT NULL DEFAULT '',
            public_email TEXT NOT NULL DEFAULT '',
            verification_status TEXT NOT NULL DEFAULT 'unverified',
            artifact_type TEXT NOT NULL DEFAULT '',
            artifact_title TEXT NOT NULL DEFAULT '',
            artifact_url TEXT NOT NULL DEFAULT '',
            artifact_snippet TEXT NOT NULL DEFAULT '',
            opted_out INTEGER NOT NULL DEFAULT 0,
            last_contacted_at TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            outreach_id INTEGER,
            provider_message_id TEXT NOT NULL UNIQUE,
            thread_id TEXT NOT NULL DEFAULT '',
            sender TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            snippet TEXT NOT NULL DEFAULT '',
            classification TEXT NOT NULL DEFAULT 'unknown',
            human_verified INTEGER NOT NULL DEFAULT 0,
            received_at TEXT NOT NULL DEFAULT '',
            follow_up_draft TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS gap_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            gap_type TEXT NOT NULL DEFAULT 'true_skill_gap',
            micro_project_brief TEXT NOT NULL DEFAULT '',
            proof_url TEXT NOT NULL DEFAULT '',
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        _ensure_columns(db, 'jobs', {
            'location': "TEXT NOT NULL DEFAULT ''",
            'salary_text': "TEXT NOT NULL DEFAULT ''",
            'posted_at': "TEXT NOT NULL DEFAULT ''",
            'ats_family': "TEXT NOT NULL DEFAULT 'unknown'",
            'preflight_json': "TEXT NOT NULL DEFAULT '{}'",
        })
        _ensure_columns(db, 'applications', {
            'claim_map_json': "TEXT NOT NULL DEFAULT '[]'",
            'slop_warnings_json': "TEXT NOT NULL DEFAULT '[]'",
            'ats_preview_text': "TEXT NOT NULL DEFAULT ''",
            'answers_json': "TEXT NOT NULL DEFAULT '{}'",
            'callback_packet_json': "TEXT NOT NULL DEFAULT '{}'",
            'resume_sha256': "TEXT NOT NULL DEFAULT ''",
            'answers_sha256': "TEXT NOT NULL DEFAULT ''",
            'evidence_note': "TEXT NOT NULL DEFAULT ''",
            'submitted_at': "TEXT NOT NULL DEFAULT ''",
        })
        _ensure_columns(db, 'outreach', {
            'contact_id': 'INTEGER',
            'channel': "TEXT NOT NULL DEFAULT 'email'",
            'provider_message_id': "TEXT NOT NULL DEFAULT ''",
            'sent_at': "TEXT NOT NULL DEFAULT ''",
            'opted_out': 'INTEGER NOT NULL DEFAULT 0',
        })
        count = db.execute('SELECT COUNT(*) AS n FROM jobs').fetchone()['n']
        if count == 0:
            jobs = json.loads((ROOT / 'sample_data' / 'fictional_jobs.json').read_text(encoding='utf8'))
            db.executemany('INSERT INTO jobs (title,company,description,url,origin) VALUES (?,?,?,?,?)',
                           [(j['title'], j['company'], j['description'], j['url'], 'fictional-sample') for j in jobs])
        if not db.execute('SELECT 1 FROM profile WHERE id=1').fetchone():
            resume = (ROOT / 'sample_data' / 'sample_resume.txt').read_text(encoding='utf8')
            db.execute('INSERT INTO profile(id,resume) VALUES (1,?)', (resume,))


def log_audit(actor: str, action: str, entity_type: str, entity_id: str = '', details=None):
    payload = json.dumps(details or {}, ensure_ascii=False)
    with connection() as db:
        db.execute(
            'INSERT INTO audit_events (actor, action, entity_type, entity_id, details_json) VALUES (?,?,?,?,?)',
            (actor, action, entity_type, str(entity_id), payload),
        )


def rows(query, params=()):
    with connection() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]


def row(query, params=()):
    with connection() as db:
        result = db.execute(query, params).fetchone()
        return dict(result) if result else None
