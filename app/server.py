"""Python standard-library local web server (thin frozen router).

Run: python -m app.server
Delegates Owner A routes (/api/pipeline/*) to app/routes_pipeline.py and
Owner B routes (/api/networking/*, /api/inbox/*) to app/routes_outreach.py.
"""
import json
import os
import re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib import parse
from . import db, engine, routes_pipeline, routes_outreach

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
MIME = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8'}


class Handler(BaseHTTPRequestHandler):
    def json_response(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 200_000:
            raise ValueError('Request too large (200 KB maximum).')
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode('utf8'))

    def do_GET(self):
        path = parse.urlsplit(self.path).path
        for module in (routes_pipeline, routes_outreach):
            delegated = module.handle_get(path)
            if delegated is not None:
                status, payload = delegated
                return self.json_response(payload, status)
        if path == '/api/jobs':
            return self.json_response(db.rows('SELECT * FROM jobs ORDER BY id DESC'))
        if path == '/api/profile':
            return self.json_response(db.row('SELECT resume FROM profile WHERE id=1'))
        if path == '/api/applications':
            return self.json_response(db.rows('''SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id ORDER BY a.id DESC'''))
        if path == '/api/outreach':
            return self.json_response(db.rows('''SELECT o.*, j.title, j.company FROM outreach o JOIN jobs j ON j.id=o.job_id ORDER BY o.id DESC'''))
        if path == '/api/summary':
            return self.json_response({
                'jobs': db.row('SELECT COUNT(*) AS n FROM jobs')['n'],
                'prepared': db.row('SELECT COUNT(*) AS n FROM applications')['n'],
                'demo_submitted': db.row("SELECT COUNT(*) AS n FROM applications WHERE status='test_submitted'")['n'],
                'real_submitted': db.row("SELECT COUNT(*) AS n FROM applications WHERE status='confirmed' AND confirmation!=''")['n'],
                'outreach_drafts': db.row('SELECT COUNT(*) AS n FROM outreach')['n'],
                'real_outreach_sent': db.row("SELECT COUNT(*) AS n FROM outreach WHERE status='sent' AND provider_message_id!=''")['n'],
            })
        if path == '/':
            path = '/index.html'
        filepath = (WEB / path.lstrip('/')).resolve()
        if WEB.resolve() not in filepath.parents or filepath.suffix not in MIME or not filepath.is_file():
            return self.json_response({'error': 'Not found'}, 404)
        data = filepath.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', MIME[filepath.suffix])
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = parse.urlsplit(self.path).path
        try:
            payload = self.read_json()
            for module in (routes_pipeline, routes_outreach):
                delegated = module.handle_post(path, payload)
                if delegated is not None:
                    status, body = delegated
                    return self.json_response(body, status)
            if path == '/api/profile':
                resume = str(payload.get('resume', '')).strip()
                if len(resume) < 50:
                    raise ValueError('Resume must contain at least 50 characters.')
                with db.connection() as con:
                    con.execute('UPDATE profile SET resume=? WHERE id=1', (resume,))
                return self.json_response({'ok': True})
            if path == '/api/jobs/import':
                joburl = str(payload.get('url', '')).strip()
                title = str(payload.get('title', '')).strip()
                company = str(payload.get('company', '')).strip()
                description = str(payload.get('description', '')).strip()
                extraction = 'user-supplied'
                if not joburl:
                    raise ValueError('Paste a job URL.')
                # Even if description was pasted, check URL structure. Do not fetch then.
                parsed = parse.urlsplit(joburl)
                if parsed.scheme not in ('http', 'https') or not parsed.hostname:
                    raise ValueError('Provide an http(s) job URL.')
                if not description:
                    extracted = engine.extract_public_job(joburl)
                    title = title or extracted['title']
                    company = company or extracted['company']
                    description = extracted['description']
                    extraction = extracted['extraction']
                if len(description) < 70:
                    raise ValueError('Provide the complete job description (at least 70 characters).')
                with db.connection() as con:
                    cursor = con.execute('INSERT INTO jobs(title,company,description,url,origin) VALUES(?,?,?,?,?)',
                                         (title or 'Job posting (confirm title)', company or 'Unknown employer', description[:20000], joburl, extraction))
                    job_id = cursor.lastrowid
                return self.json_response({'ok': True, 'job_id': job_id, 'extraction': extraction})
            if path == '/api/prepare':
                job_id = int(payload.get('job_id', 0))
                job = db.row('SELECT * FROM jobs WHERE id=?', (job_id,))
                if not job:
                    return self.json_response({'error': 'Unknown job ID'}, 404)
                resume = db.row('SELECT resume FROM profile WHERE id=1')['resume']
                fit = engine.match_resume(resume, job['description'])
                tailored = engine.draft_resume(resume, job)
                with db.connection() as con:
                    con.execute('''INSERT INTO applications(job_id, tailored_resume, fit_score,status)
                        VALUES(?,?,?,'draft') ON CONFLICT(job_id) DO UPDATE SET
                        tailored_resume=excluded.tailored_resume, fit_score=excluded.fit_score,
                        status='draft',confirmation='' ''', (job_id, tailored, fit['score']))
                return self.json_response({'job': job, 'fit': fit, 'tailored_resume': tailored, 'status': 'draft'})
            if path == '/api/outreach/prepare':
                job_id = int(payload.get('job_id', 0))
                job = db.row('SELECT * FROM jobs WHERE id=?', (job_id,))
                if not job:
                    return self.json_response({'error': 'Unknown job ID'}, 404)
                contact = payload.get('contact') or {}
                name = str(contact.get('name', '')).strip()
                role = str(contact.get('role', '')).strip()
                if not name or not role:
                    raise ValueError('Enter a verified contact name and role.')
                resume = db.row('SELECT resume FROM profile WHERE id=1')['resume']
                draft = engine.draft_message(contact, job, resume, str(payload.get('channel', 'email')))
                with db.connection() as con:
                    con.execute('''INSERT INTO outreach(job_id,contact_name,contact_role,contact_profile,subject,body)
                        VALUES(?,?,?,?,?,?)''', (job_id, name, role, str(contact.get('profile', '')), draft['subject'], draft['body']))
                return self.json_response(draft)
            m = re.fullmatch(r'/api/applications/(\d+)/approve', path)
            if m:
                with db.connection() as con:
                    updated = con.execute("UPDATE applications SET status='approved_for_test' WHERE id=? AND status='draft'", (int(m[1]),))
                if updated.rowcount == 0:
                    raise ValueError('Application must be a draft before approving.')
                return self.json_response({'ok': True, 'status': 'approved_for_test'})
            m = re.fullmatch(r'/api/applications/(\d+)/test-submit', path)
            if m:
                with db.connection() as con:
                    updated = con.execute("UPDATE applications SET status='test_submitted', confirmation='DEMO ONLY - no job site contacted' WHERE id=? AND status='approved_for_test'", (int(m[1]),))
                if updated.rowcount == 0:
                    raise ValueError('Approve the draft before test submitting.')
                return self.json_response({'ok': True, 'status': 'test_submitted', 'real_application': False})
            return self.json_response({'error': 'Unknown endpoint'}, 404)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self.json_response({'error': str(exc)}, 400)
        except Exception as exc:
            self.log_error('Server error: %s', str(exc))
            return self.json_response({'error': 'Internal server error; see terminal.'}, 500)


def run():
    db.init_db()
    host = '127.0.0.1'  # bind only to local machine
    port = int(os.environ.get('JOBFINDER_PORT', '8765'))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'Job Finder student starter running at http://{host}:{port}')
    print('DEMO MODE: No real applications submitted; no outbound messages sent.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    run()
