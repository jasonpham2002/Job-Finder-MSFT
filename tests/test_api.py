import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from urllib import request

# Point database at temp location BEFORE loading app.db.
_TEST_DIR = tempfile.TemporaryDirectory(prefix='jobfinder-tests-')
os.environ['JOBFINDER_DB'] = str(Path(_TEST_DIR.name) / 'db.sqlite3')
from app import db
from app.server import Handler
from http.server import ThreadingHTTPServer


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.url = f'http://127.0.0.1:{cls.httpd.server_port}'
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def api(self, path, payload=None):
        data = json.dumps(payload).encode('utf8') if payload is not None else None
        req = request.Request(self.url+path, data=data, headers={'Content-Type':'application/json'} if data else {})
        with request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())

    def test_starter_never_claims_real_submit(self):
        summary = self.api('/api/summary')
        self.assertGreaterEqual(summary['jobs'], 10)
        self.assertEqual(summary['real_submitted'], 0)
        self.assertEqual(summary['real_outreach_sent'], 0)
        job_id = self.api('/api/jobs')[0]['id']
        prepared = self.api('/api/prepare',{'job_id':job_id})
        self.assertEqual(prepared['status'],'draft')
        apps = self.api('/api/applications')
        target = next(app for app in apps if app['job_id']==job_id)
        self.api(f"/api/applications/{target['id']}/approve", {})
        outcome = self.api(f"/api/applications/{target['id']}/test-submit",{})
        self.assertFalse(outcome['real_application'])
        summary = self.api('/api/summary')
        self.assertEqual(summary['real_submitted'],0)
        self.assertEqual(summary['demo_submitted'],1)

    def test_outreach_is_never_sent(self):
        job_id = self.api('/api/jobs')[0]['id']
        msg = self.api('/api/outreach/prepare',{'job_id':job_id,'contact':{'name':'Taylor Morgan','role':'Recruiter'},'channel':'email'})
        self.assertEqual(msg['status'],'draft')
        self.assertEqual(self.api('/api/summary')['real_outreach_sent'],0)


if __name__=='__main__':
    unittest.main()
