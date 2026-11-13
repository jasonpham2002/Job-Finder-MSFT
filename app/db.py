"""SQLite demo storage; no credentials, sent messages, or real applications."""
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
        ''')
        count = db.execute('SELECT COUNT(*) AS n FROM jobs').fetchone()['n']
        if count == 0:
            jobs = json.loads((ROOT / 'sample_data' / 'fictional_jobs.json').read_text(encoding='utf8'))
            db.executemany('INSERT INTO jobs (title,company,description,url,origin) VALUES (?,?,?,?,?)',
                           [(j['title'], j['company'], j['description'], j['url'], 'fictional-sample') for j in jobs])
        if not db.execute('SELECT 1 FROM profile WHERE id=1').fetchone():
            resume = (ROOT / 'sample_data' / 'sample_resume.txt').read_text(encoding='utf8')
            db.execute('INSERT INTO profile(id,resume) VALUES (1,?)', (resume,))


def rows(query, params=()):
    with connection() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]


def row(query, params=()):
    with connection() as db:
        result = db.execute(query, params).fetchone()
        return dict(result) if result else None
