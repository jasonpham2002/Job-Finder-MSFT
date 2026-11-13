import base64
import json
import tempfile
import unittest
from email import message_from_bytes
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

from app import db
from app.adapters_outreach import GmailOutreachAdapter, ManualOutreachAdapter, OutlookOutreachAdapter
from app.routes_outreach import handle_post


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
        self.assertEqual(self.approve(self.stage()[1])[0], 409)
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
        self.assertEqual(self.approve(self.stage()[1])[0], 409)

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
