import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ContractAndFoundationTests(unittest.TestCase):
    def test_db_migration_is_idempotent_on_legacy_schema(self):
        with tempfile.TemporaryDirectory(prefix='jobfinder-migrate-') as tmp:
            db_file = Path(tmp) / 'legacy.sqlite3'
            con = sqlite3.connect(str(db_file))
            con.executescript('''
                CREATE TABLE jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL, company TEXT NOT NULL, description TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL DEFAULT 'demo'
                );
                CREATE TABLE profile (id INTEGER PRIMARY KEY CHECK (id = 1), resume TEXT NOT NULL);
                CREATE TABLE applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL,
                    tailored_resume TEXT NOT NULL, fit_score INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft', confirmation TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(job_id)
                );
                CREATE TABLE outreach (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL,
                    contact_name TEXT NOT NULL, contact_role TEXT NOT NULL,
                    contact_profile TEXT NOT NULL DEFAULT '',
                    subject TEXT NOT NULL, body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            con.close()

            orig = os.environ.get('JOBFINDER_DB')
            os.environ['JOBFINDER_DB'] = str(db_file)
            try:
                from importlib import reload
                from app import db
                reload(db)
                db.init_db()
                db.init_db()
                tables = {r['name'] for r in db.rows("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({'jobs', 'profile', 'applications', 'outreach', 'contacts', 'replies', 'gap_artifacts', 'audit_events'}.issubset(tables))
                app_cols = {r['name'] for r in db.rows('PRAGMA table_info(applications)')}
                self.assertTrue({'claim_map_json', 'slop_warnings_json', 'ats_preview_text', 'callback_packet_json', 'resume_sha256', 'answers_sha256'}.issubset(app_cols))
            finally:
                if orig is None:
                    os.environ.pop('JOBFINDER_DB', None)
                else:
                    os.environ['JOBFINDER_DB'] = orig

    def test_extended_schemas_exist_and_parse(self):
        job_schema = json.loads((ROOT / 'schemas/job.schema.json').read_text(encoding='utf8'))
        self.assertIn('preflight', job_schema['properties'])
        self.assertIn('ats_family', job_schema['properties'])

        app_schema = json.loads((ROOT / 'schemas/application.schema.json').read_text(encoding='utf8'))
        for key in ('claim_evidence_map', 'slop_warnings', 'ats_preview_text', 'copilot_packet', 'callback_packet', 'resume_sha256'):
            self.assertIn(key, app_schema['properties'])

        contact_schema = json.loads((ROOT / 'schemas/contact.schema.json').read_text(encoding='utf8'))
        self.assertIn('artifact_hook', contact_schema['properties'])

        gap_schema = json.loads((ROOT / 'schemas/gap_artifact.schema.json').read_text(encoding='utf8'))
        self.assertIn('skill_gaps', gap_schema['properties'])

    def test_adapter_consent_guards_raise_without_approval(self):
        from app.adapters import ApplicationAdapter, OutreachAdapter
        with self.assertRaises(PermissionError):
            ApplicationAdapter().submit({}, explicit_user_approval=False)
        with self.assertRaises(PermissionError):
            OutreachAdapter().send({}, explicit_user_approval=False)

    def test_modular_route_seams_stay_isolated(self):
        from app import routes_pipeline, routes_outreach
        status_a, body_a = routes_pipeline.handle_get('/api/pipeline/status')
        self.assertEqual(status_a, 200)
        self.assertEqual(body_a['owner'], 'Owner A')

        status_b, body_b = routes_outreach.handle_get('/api/networking/status')
        self.assertEqual(status_b, 200)
        self.assertEqual(body_b['owner'], 'Owner B')

        self.assertIsNone(routes_pipeline.handle_get('/api/networking/status'))
        self.assertIsNone(routes_outreach.handle_get('/api/pipeline/status'))
        self.assertEqual(routes_pipeline.handle_post('/api/pipeline/gaps', {})[0], 501)
        self.assertIsNone(routes_pipeline.handle_post('/api/inbox/sync', {}))
        self.assertEqual(routes_outreach.handle_post('/api/inbox/sync', {})[0], 403)


if __name__ == '__main__':
    unittest.main()
