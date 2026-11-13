import base64
import json
import tempfile
import unittest
from email import message_from_bytes
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

from app import db
from app.adapters_outreach import (
    GmailOutreachAdapter, ManualOutreachAdapter, OutlookOutreachAdapter,
    PublicArtifactContactAdapter, classify_reply,
)
from app.routes_outreach import handle_get, handle_post


MESSAGE = {'channel': 'email', 'recipient': 'recruiter@company.invalid',
           'subject': 'A question about the role', 'body': 'Could we discuss the team’s work?'}


class OutreachAdapterTests(unittest.TestCase):
    def test_all_adapters_require_boolean_approval(self):
        for adapter in (GmailOutreachAdapter(), ManualOutreachAdapter(), OutlookOutreachAdapter()):
            with self.subTest(adapter=type(adapter).__name__), self.assertRaises(PermissionError):
                adapter.send(MESSAGE, 'true')

    @patch('app.adapters_outreach.provider_json', side_effect=[{'access_token': 'access'}, {'id': 'gmail-id'}])
    @patch('app.adapters_outreach.gmail_client', return_value={'client_id': 'client', 'client_secret': 'secret'})
    @patch('app.adapters_outreach.gmail_token_path')
    def test_gmail_refreshes_token_and_sends_mime(self, token_path, client, provider):
        with tempfile.TemporaryDirectory() as directory:
            token_path.return_value = Path(directory) / 'token.json'
            token_path.return_value.write_text(json.dumps({'client_id': 'client', 'refresh_token': 'refresh'}))
            result = GmailOutreachAdapter().send(MESSAGE, True)
        refresh, send = (call.args[0] for call in provider.call_args_list)
        self.assertEqual(parse_qs(refresh.data.decode())['refresh_token'], ['refresh'])
        self.assertEqual(send.headers['Authorization'], 'Bearer access')
        decoded = message_from_bytes(base64.urlsafe_b64decode(json.loads(send.data)['raw']))
        self.assertEqual(decoded['To'], MESSAGE['recipient'])
        self.assertEqual(decoded['Subject'], MESSAGE['subject'])
        self.assertEqual(decoded.get_payload(decode=True).decode().strip(), MESSAGE['body'])
        self.assertEqual((result.status, result.confirmation_id), ('sent', 'gmail-id'))

    @patch('app.adapters_outreach.GmailOutreachAdapter._access_token', return_value='access')
    @patch('app.adapters_outreach.provider_json', return_value={})
    def test_missing_provider_id_is_unknown(self, provider, token):
        self.assertEqual(GmailOutreachAdapter().send(MESSAGE, True).status, 'unknown')

    @patch('app.adapters_outreach.GmailOutreachAdapter._access_token', side_effect=FileNotFoundError)
    @patch('app.adapters_outreach.provider_json')
    def test_missing_token_falls_back_without_sending(self, provider, token):
        self.assertEqual(GmailOutreachAdapter().send(MESSAGE, True).status, 'manual_required')
        provider.assert_not_called()


class OutreachRouteTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_path = patch.object(db, 'DB_PATH', Path(directory.name) / 'db.sqlite3')
        db_path.start()
        self.addCleanup(db_path.stop)
        db.init_db()
        with db.connection() as con:
            self.job_id = con.execute(
                "INSERT INTO jobs(title,company,description,url,origin) VALUES(?,?,?,?,'user-supplied')",
                ('Engineer', 'Test Company', 'Description', 'https://careers.company.com/123'),
            ).lastrowid

    def stage(self, **overrides):
        return handle_post('/api/networking/outreach/drafts', {
            **MESSAGE, 'recipient': 'recruiter@company.com', 'job_id': self.job_id,
            'name': 'Recruiter', 'role': 'Recruiter', 'source_url': 'https://company.com/team',
            'user_authorized_recipient': True, **overrides,
        })

    @patch('app.adapters_outreach.refresh_gmail_token', return_value='inbox-token')
    @patch('app.adapters_outreach.provider_json')
    def test_inbox_sync_requires_consent_and_deduplicates(self, provider, token):
        page = {'messages': [{'id': 'reply-id'}]}
        message = {
            'threadId': 'thread-id', 'internalDate': '1700000000000',
            'snippet': 'We would like to schedule an interview.',
            'payload': {'headers': [{'name': 'From', 'value': 'recruiter@example.org'},
                                    {'name': 'Auto-Submitted', 'value': 'auto-replied'}]},
        }
        provider.side_effect = [page, message, page, message]
        sync_path = '/api/inbox/sync'
        self.assertEqual(handle_post(sync_path, {})[0], 403)
        self.assertEqual(handle_post(sync_path, {'explicit_inbox_consent': True})[0], 403)
        provider.assert_not_called()
        _, status = handle_get('/api/inbox/status')
        consent = {'explicit_inbox_consent': True, 'sync_token': status['sync_token']}
        self.assertEqual(handle_post(sync_path, consent)[1]['inserted'], 1)
        self.assertEqual(handle_post(sync_path, consent)[1]['inserted'], 0)
        query = parse_qs(provider.call_args_list[0].args[0].full_url.split('?', 1)[1])
        self.assertIn('label:JobFinder', query['q'][0])
        self.assertEqual(token.call_args.args[0].name, 'gmail-inbox.json')
        _, stored = handle_get('/api/inbox/replies')
        self.assertEqual(len(stored['replies']), 1)
        self.assertEqual(stored['replies'][0]['classification'], 'automated_receipt')
        self.assertFalse(stored['replies'][0]['human_verified'])

    def test_simulation_classifies_fixture_without_saving_replies(self):
        _, simulation = handle_post('/api/inbox/simulate', {})
        self.assertEqual(simulation['mode'], 'TEST ONLY')
        self.assertEqual([r['classification'] for r in simulation['replies']],
                         ['human_positive_reply', 'automated_receipt', 'rejection'])
        self.assertEqual(handle_get('/api/inbox/replies')[1]['replies'], [])

    def test_referral_info_and_quoted_interview(self):
        sender = 'recruiter@example.org'
        self.assertEqual(classify_reply(sender, 'Re: Application', 'I can refer you.'), 'referral_opportunity')
        self.assertEqual(classify_reply(sender, 'Re: Application', 'Please send your portfolio.'), 'request_for_info')
        self.assertEqual(classify_reply(sender, 'Re: Application', 'Thanks.\n> Please schedule an interview.'), 'unknown')

    def action(self, draft, action, **overrides):
        return handle_post(f"/api/networking/outreach/{draft['id']}/{action}", {
            'explicit_user_approval': True, 'review_token': draft['review_token'], **overrides,
        })

    def approve(self, draft):
        return self.action(draft, 'approve', reviewed_message={
            key: draft[key] for key in ('job_url', 'channel', 'recipient', 'subject', 'body')
        })

    @patch('app.adapters_outreach.GmailOutreachAdapter._access_token', return_value='access')
    @patch('app.adapters_outreach.provider_json', return_value={'id': 'gmail-id'})
    def test_approved_send_records_evidence_and_blocks_retries(self, provider, token):
        code, draft = self.stage()
        self.assertEqual(code, 201)
        self.assertEqual(self.action(draft, 'send')[0], 403)
        self.assertEqual(self.action(draft, 'approve', explicit_user_approval=1)[0], 403)
        self.assertEqual(self.approve(draft)[0], 200)
        self.assertEqual(self.action(draft, 'send', explicit_user_approval=False)[0], 403)
        self.assertEqual(self.action(draft, 'send', review_token='incorrect')[0], 403)
        self.assertEqual(self.action(draft, 'send')[1]['provider_message_id'], 'gmail-id')
        self.assertEqual(self.action(draft, 'send')[0], 409)
        self.assertEqual(self.stage()[0], 409)
        provider.assert_called_once()
        row = db.row('SELECT * FROM outreach WHERE id=?', (draft['id'],))
        self.assertTrue(row['sent_at'])
        event = db.row("SELECT details_json FROM audit_events WHERE action='outreach_sent'")
        details = json.loads(event['details_json'])
        self.assertTrue(details['explicit_user_approval'])
        self.assertEqual(details['job_url'], draft['job_url'])
        self.assertEqual(details['provider_message_id'], 'gmail-id')

    def test_changed_draft_and_opted_out_recipient_are_blocked(self):
        _, draft = self.stage()
        self.assertEqual(self.approve(draft)[0], 200)
        with db.connection() as con:
            con.execute("UPDATE outreach SET body='Changed' WHERE id=?", (draft['id'],))
        self.assertEqual(self.action(draft, 'send')[0], 403)
        with db.connection() as con:
            con.execute('UPDATE contacts SET opted_out=1')
        self.assertEqual(self.stage()[0], 409)

    def test_artifact_requires_employer_evidence_and_preserves_opt_out(self):
        source = 'https://company.com/team'
        job = {'source_url': source, 'company': 'Test Company'}
        person = {'@type': 'Person', 'name': 'Taylor Recruiter', 'jobTitle': 'Recruiter',
                  'worksFor': {'name': job['company']}, 'description': 'Leads technical recruiting.'}
        adapter = PublicArtifactContactAdapter()
        self.assertEqual(adapter.extract(job, [{**person, 'description': ''}]), [])
        self.assertEqual(adapter.extract(job, [{**person, 'worksFor': 'Other Company'}]), [])
        contacts = adapter.extract(job, [person])
        self.assertIsNone(contacts[0].professional_email)
        with patch.object(PublicArtifactContactAdapter, 'research', return_value=contacts):
            _, status = handle_get('/api/inbox/status')
            args = {'job_id': self.job_id, 'source_url': source, 'employer_source_confirmed': True,
                    'sync_token': status['sync_token']}
            _, result = handle_post('/api/networking/contacts/research', args)
            contact = result['contacts'][0]
            draft_args = {'contact_id': contact['id']}
            draft = handle_post('/api/networking/contacts/draft', draft_args)[1]
            self.assertIn(source, draft['body'])
            self.assertEqual(handle_post(f'/api/networking/contacts/{contact["id"]}/opt-out', status)[0], 200)
            handle_post('/api/networking/contacts/research', args)
            self.assertEqual(handle_post('/api/networking/contacts/draft', draft_args)[0], 409)

    def test_callback_uses_exact_confirmed_application_snapshot(self):
        packet = {'diff_summary': ['Moved an existing project'], 'submitted_answers': {'availability': 'May'},
                  'probe_questions': ['What did you build?']}
        with db.connection() as con:
            app_id = con.execute(
                """INSERT INTO applications(job_id,tailored_resume,fit_score,status,confirmation,callback_packet_json)
                   VALUES(?,'resume',80,'confirmed','ats-receipt',?)""", (self.job_id, json.dumps(packet)),
            ).lastrowid
            reply_id = con.execute(
                "INSERT INTO replies(provider_message_id,classification) VALUES('reply-123','interview_invitation')",
            ).lastrowid
        self.assertIsNone(handle_get('/api/inbox/replies')[1]['replies'][0]['callback_packet'])
        token = handle_get('/api/inbox/status')[1]['sync_token']
        self.assertEqual(handle_post('/api/inbox/link-application', {
            'sync_token': token, 'reply_id': reply_id, 'application_id': app_id,
        })[0], 200)
        self.assertEqual(handle_get('/api/inbox/replies')[1]['replies'][0]['callback_packet'], packet)

    def test_rejects_demo_jobs_unauthorized_addresses_and_multiple_recipients(self):
        self.assertEqual(self.stage(job_id=1)[0], 403)
        self.assertEqual(self.stage(user_authorized_recipient=False)[0], 403)
        self.assertEqual(self.stage(recipient='a@company.com, b@company.com')[0], 400)

    @patch('app.adapters_outreach.provider_json')
    def test_linkedin_manual_delivery_is_user_reported(self, provider):
        _, draft = self.stage(channel='linkedin', recipient='https://www.linkedin.com/in/recruiter/')
        self.assertEqual(self.approve(draft)[0], 200)
        self.assertEqual(self.action(draft, 'manual-sent', confirmed_manually_sent=True)[0], 409)
        self.assertEqual(self.action(draft, 'send')[1]['status'], 'manual_required')
        self.assertEqual(self.action(draft, 'manual-sent')[0], 409)
        result = self.action(draft, 'manual-sent', confirmed_manually_sent=True)[1]
        self.assertEqual(result['status'], 'manual_sent')
        self.assertTrue(result['sent_at'])
        self.assertEqual(db.row('SELECT provider_message_id FROM outreach')['provider_message_id'], '')
        provider.assert_not_called()

    def test_html_and_blog_contact_extraction_and_redirect_guard(self):
        adapter = PublicArtifactContactAdapter()
        job = {'source_url': 'https://company.com/team', 'company': 'Test Company'}
        team_html = '''
        <html><head><title>Test Company Team</title></head><body>
          <article>
            <h3>Jordan Lee</h3>
            <p>Senior Technical Recruiter</p>
            <p>Leads university and distributed systems recruiting across Test Company.</p>
            <a href="mailto:jordan@company.com">Email</a>
          </article>
        </body></html>
        '''
        extracted = adapter.extract_html_contacts(job, team_html)
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0].name, 'Jordan Lee')
        self.assertEqual(extracted[0].professional_email, 'jordan@company.com')
        self.assertEqual(extracted[0].artifact_hook['type'], 'team_bio')

        blog_html = '''
        <html><head>
          <title>Scaling Python Services at Test Company</title>
          <meta name="author" content="Morgan Chen">
          <meta name="description" content="How our Staff Engineer team improved reliability across Test Company.">
        </head><body><p>Test Company engineering blog post by Staff Engineer Morgan Chen.</p></body></html>
        '''
        blog_contacts = adapter.extract_html_contacts(job, blog_html)
        self.assertEqual(len(blog_contacts), 1)
        self.assertEqual(blog_contacts[0].name, 'Morgan Chen')
        self.assertEqual(blog_contacts[0].artifact_hook['type'], 'blog_post')

    def test_manual_contact_excerpt_and_overlap_grounded_artifact_draft(self):
        with db.connection() as con:
            con.execute(
                'UPDATE jobs SET description=? WHERE id=?',
                ('Build Python and SQL data services and REST APIs for enterprise customers.', self.job_id),
            )
        _, status = handle_get('/api/networking/status')
        self.assertTrue(status['implemented'])
        with patch.object(PublicArtifactContactAdapter, 'research', return_value=[]):
            code, res = handle_post('/api/networking/contacts/research', {
                'job_id': self.job_id,
                'source_url': 'https://company.com/about',
                'employer_source_confirmed': True,
                'sync_token': status['sync_token'],
                'manual_contact': {
                    'name': 'Alex Rivera',
                    'role': 'Engineering Manager',
                    'artifact_type': 'team_bio',
                    'artifact_snippet': 'Alex Rivera leads the Python & SQL platform team at Test Company.',
                    'public_email': 'alex@company.com',
                },
            })
        self.assertEqual(code, 200)
        self.assertEqual(len(res['contacts']), 1)
        contact_id = res['contacts'][0]['id']
        code, draft = handle_post('/api/networking/contacts/draft', {'contact_id': contact_id, 'channel': 'email'})
        self.assertEqual(code, 200)
        self.assertIn('https://company.com/about', draft['body'])
        self.assertEqual(draft['recipient'], 'alex@company.com')
        self.assertEqual(draft['contact_name'], 'Alex Rivera')
        self.assertEqual(handle_get('/api/networking/contacts')[1]['contacts'][0]['name'], 'Alex Rivera')

    def test_expanded_reply_classifier_and_simulated_callback_preview(self):
        self.assertEqual(
            classify_reply('recruiter@company.com', 'Re: Engineer role', 'Thanks for reaching out — happy to chat next week!'),
            'human_positive_reply',
        )
        self.assertEqual(
            classify_reply('recruiter@company.com', 'Re: Engineer role', 'Are you free for a quick call on Tuesday?'),
            'human_positive_reply',
        )
        _, sim = handle_post('/api/inbox/simulate', {})
        self.assertEqual(sim['mode'], 'TEST ONLY')
        pos = sim['replies'][0]
        self.assertEqual(pos['classification'], 'human_positive_reply')
        self.assertIn('callback_packet', pos)
        self.assertEqual(pos['callback_packet']['mode'], 'TEST ONLY')
        self.assertTrue(pos['callback_packet']['probe_questions'])
