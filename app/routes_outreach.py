"""Owner B modular routes: artifact contacts, authorized outreach, inbox sync & callbacks.

Teammate B implements concrete logic here and in app/adapters_outreach.py without
touching app/server.py or Owner A files.
"""



import json
import os
import re
from datetime import datetime, timezone
from email.errors import HeaderParseError
from email.headerregistry import Address
from hashlib import sha256
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from urllib.parse import urlsplit

from . import db
from .adapters_outreach import (
    GmailOutreachAdapter, ManualOutreachAdapter, OutlookOutreachAdapter,
    classify_reply, generate_outreach_draft,
)

OUTREACH_PATH = re.compile(r'/api/networking/outreach/([0-9]+)/(approve|send|manual-sent)')
EMAIL_PROVIDERS = {'gmail': GmailOutreachAdapter, 'outlook': OutlookOutreachAdapter, 'manual': ManualOutreachAdapter}


def audit(con, outreach_id, action, details):
    con.execute(
        'INSERT INTO audit_events(actor,action,entity_type,entity_id,details_json) VALUES(?,?,?,?,?)',
        ('local-user', action, 'outreach', str(outreach_id), json.dumps(details)),
    )


def public_link(value):
    parsed = urlsplit(value)
    hostname = (parsed.hostname or '').lower().rstrip('.')
    return (
        parsed.scheme in ('https', 'http') and '.' in hostname
        and not parsed.username and not parsed.password
        and hostname not in {'example.com', 'example.net', 'example.org'}
        and not hostname.endswith(('.example', '.invalid', '.test', '.localhost', '.local',
                                   '.example.com', '.example.net', '.example.org'))
    )


def create_delivery_draft(payload):
    """Stage user-supplied content and an authorized destination for review."""
    if payload.get('user_authorized_recipient') is not True:
        return 403, {'error': 'Confirm that the recipient address or profile is authorized.'}
    name = str(payload.get('name') or '').strip()
    role = str(payload.get('role') or '').strip()
    recipient = str(payload.get('recipient') or '').strip()
    subject = str(payload.get('subject') or '').strip()
    body = str(payload.get('body') or '').strip()
    channel = payload.get('channel')
    if not name or not role or not body or '[YOUR NAME]' in body or channel not in ('email', 'linkedin'):
        raise ValueError('Provide a contact name, role, channel and final message.')
    if channel == 'email':
        try:
            address = Address(addr_spec=recipient)
        except HeaderParseError as exc:
            raise ValueError('Provide one valid recipient email address.') from exc
        if (address.addr_spec != recipient or not address.username or not public_link('https://' + address.domain)
                or not subject or len(subject) > 200 or '\r' in subject or '\n' in subject):
            raise ValueError('Provide one real email address and a single-line subject.')
    else:
        profile = urlsplit(recipient)
        if (not public_link(recipient) or profile.hostname not in ('www.linkedin.com', 'linkedin.com')
                or not profile.path.startswith('/in/') or not profile.path[4:].strip('/')):
            raise ValueError('Provide the recipient’s LinkedIn profile URL.')
        recipient = f'https://www.linkedin.com{profile.path.rstrip("/")}'
        subject = ''
    source_url = str(payload.get('source_url') or '').strip()
    if not public_link(source_url):
        raise ValueError('Provide the public source or professional profile for the recipient.')
    with db.connection() as con:
        job = con.execute('SELECT * FROM jobs WHERE id=?', (int(payload.get('job_id', 0)),)).fetchone()
        if job is None:
            return 404, {'error': 'Unknown job ID.'}
        if job['origin'] in ('fictional-sample', 'demo') or not public_link(job['url']):
            return 403, {'error': 'Delivery requires a real job and its source URL.'}
        contact_id = con.execute(
            '''INSERT INTO contacts(job_id,company,name,role,source_url,public_email,linkedin_url,verification_status)
               VALUES(?,?,?,?,?,?,?,'user_provided')''',
            (job['id'], job['company'], name, role, source_url,
             recipient if channel == 'email' else '', recipient if channel == 'linkedin' else ''),
        ).lastrowid
        outreach_id = con.execute(
            '''INSERT INTO outreach(job_id,contact_id,contact_name,contact_role,contact_profile,channel,subject,body)
               VALUES(?,?,?,?,?,?,?,?)''',
            (job['id'], contact_id, name, role, recipient if channel == 'linkedin' else '', channel, subject, body),
        ).lastrowid
        review_token = token_urlsafe(32)
        audit(con, outreach_id, 'outreach_staged', {
            'review_token_sha256': sha256(review_token.encode('ascii')).hexdigest(),
        })
    return 201, {'id': outreach_id, 'review_token': review_token, 'status': 'draft',
                 'job_url': job['url'], 'channel': channel,
                 'recipient': recipient, 'subject': subject, 'body': body}


def delivery_block(con, row):
    # Compare all matching contacts so a new draft cannot bypass a previous opt-out.
    destination = row['public_email'] or row['linkedin_url']
    opted_out = con.execute(
        '''SELECT 1 FROM contacts WHERE opted_out=1 AND (
           lower(public_email)=lower(?) OR lower(rtrim(linkedin_url,'/'))=lower(?) OR
           (lower(trim(company))=lower(trim(?)) AND lower(trim(name))=lower(trim(?))))''',
        (destination, destination, row['company'], row['contact_name']),
    ).fetchone()
    if row['opted_out'] or opted_out:
        return 'This contact has opted out.'
    recent = con.execute(
        '''SELECT 1 FROM outreach o JOIN jobs j ON j.id=o.job_id
           LEFT JOIN contacts c ON c.id=o.contact_id
           WHERE o.id!=? AND (
             lower(trim(j.company))=lower(trim(?)) OR lower(c.public_email)=lower(?)
             OR lower(rtrim(c.linkedin_url,'/'))=lower(?))
           AND (o.status IN ('sending','unknown')
                OR (o.status IN ('sent','manual_sent') AND datetime(o.sent_at)>datetime('now','-14 days')))''',
        (row['id'], row['company'], destination, destination),
    ).fetchone()
    if recent:
        return 'Recent or unresolved outreach blocks delivery. Check the previous message first.'
    return None


def handle_delivery(outreach_id, action, payload):
    if payload.get('explicit_user_approval') is not True:
        return 403, {'error': 'Explicit user approval is required.'}
    with db.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute(
            '''SELECT o.*, j.url AS job_url, j.company, j.origin, c.source_url,
                      c.public_email, c.linkedin_url, c.verification_status
               FROM outreach o JOIN jobs j ON j.id=o.job_id
               LEFT JOIN contacts c ON c.id=o.contact_id AND c.job_id=o.job_id
               WHERE o.id=?''',
            (outreach_id,),
        ).fetchone()
        if row is None:
            return 404, {'error': 'Unknown outreach draft.'}
        # The shared HTTP handler accepts JSON even for cross-origin text/plain POSTs.
        # Require a token from the staging response before mutating delivery state.
        staged = con.execute(
            '''SELECT details_json FROM audit_events WHERE entity_type='outreach'
               AND entity_id=? AND action='outreach_staged' ORDER BY id DESC LIMIT 1''',
            (str(outreach_id),),
        ).fetchone()
        review_token = payload.get('review_token')
        if not (staged and isinstance(review_token, str) and compare_digest(
            json.loads(staged['details_json'])['review_token_sha256'],
            sha256(review_token.encode('utf8')).hexdigest(),
        )):
            return 403, {'error': 'Provide the review token from the staged delivery draft.'}
        if (row['verification_status'] not in ('verified_public', 'user_provided')
                or row['origin'] in ('fictional-sample', 'demo') or not public_link(row['job_url'])):
            return 403, {'error': 'Stage a delivery draft with an authorized recipient and real job first.'}
        message = {
            'channel': row['channel'],
            'recipient': row['public_email'] if row['channel'] == 'email' else row['linkedin_url'],
            'subject': row['subject'], 'body': row['body'],
        }
        if (not message['recipient'] or row['channel'] not in ('email', 'linkedin')
                or not public_link(row['source_url'])):
            return 403, {'error': 'The draft has no authorized destination and source.'}
        approval = {
            'job_url': row['job_url'], 'contact_id': row['contact_id'], 'source_url': row['source_url'],
            'message_sha256': sha256(json.dumps(message, sort_keys=True).encode('utf8')).hexdigest(),
            'explicit_user_approval': True,
        }
        if action == 'approve':
            provider = payload.get('provider', 'gmail' if row['channel'] == 'email' else 'manual')
            if provider not in EMAIL_PROVIDERS or (row['channel'] == 'linkedin' and provider != 'manual'):
                raise ValueError('Select gmail, outlook or manual for email, and manual for LinkedIn.')
            if row['status'] not in ('draft', 'approved', 'failed', 'manual_required'):
                return 409, {'error': 'This outreach is already sent or has an unresolved delivery attempt.'}
            if payload.get('reviewed_message') != {'job_url': row['job_url'], **message}:
                return 409, {'error': 'Approval must match the current job, recipient, channel, subject and body.'}
            if blocked := delivery_block(con, row):
                return 409, {'error': blocked}
            con.execute("UPDATE outreach SET status='approved' WHERE id=?", (outreach_id,))
            audit(con, outreach_id, 'outreach_approved', {**approval, 'provider': provider})
            return 200, {'status': 'approved', 'provider': provider}

        saved = con.execute(
            '''SELECT details_json FROM audit_events WHERE entity_type='outreach'
               AND entity_id=? AND action='outreach_approved' ORDER BY id DESC LIMIT 1''',
            (str(outreach_id),),
        ).fetchone()
        approved = json.loads(saved['details_json']) if saved else {}
        if any(approved.get(key) != value for key, value in approval.items()):
            return 403, {'error': 'Approve the current outreach draft first.'}
        provider = approved['provider']
        if action == 'manual-sent':
            if row['status'] != 'manual_required' or payload.get('confirmed_manually_sent') is not True:
                return 409, {'error': 'Confirm manual delivery after receiving the copyable message.'}
            sent_at = datetime.now(timezone.utc).isoformat()
            con.execute("UPDATE outreach SET status='manual_sent', sent_at=? WHERE id=?", (sent_at, outreach_id))
            con.execute('UPDATE contacts SET last_contacted_at=? WHERE id=?', (sent_at, row['contact_id']))
            audit(con, outreach_id, 'outreach_manual_sent', {**approved, 'sent_at': sent_at, 'user_reported': True})
            return 200, {'status': 'manual_sent', 'sent_at': sent_at, 'user_reported': True}

        if row['status'] != 'approved':
            return 409, {'error': 'This outreach is already in progress or has a recorded outcome.'}
        if blocked := delivery_block(con, row):
            return 409, {'error': blocked}
        con.execute("UPDATE outreach SET status='sending' WHERE id=?", (outreach_id,))
        audit(con, outreach_id, 'outreach_attempted', approved)

    result = EMAIL_PROVIDERS[provider]().send(message, explicit_user_approval=True)
    status = result.status
    message_id = result.confirmation_id or ''
    if status == 'sent' and not message_id:
        status = 'unknown'
    sent_at = datetime.now(timezone.utc).isoformat() if status == 'sent' else ''
    with db.connection() as con:
        con.execute('UPDATE outreach SET status=?, provider_message_id=?, sent_at=? WHERE id=?',
                    (status, message_id, sent_at, outreach_id))
        if sent_at:
            con.execute('UPDATE contacts SET last_contacted_at=? WHERE id=?', (sent_at, row['contact_id']))
        audit(con, outreach_id, 'outreach_' + status, {
            **approved, 'provider_message_id': message_id, 'sent_at': sent_at,
        })
    response = {'status': status, 'details': result.details}
    if status == 'manual_required':
        response['message'] = message
    if status == 'sent':
        response.update(provider_message_id=message_id, sent_at=sent_at)
    return 200, response

def handle_get(path: str):
    """Return (status_code, payload) if path belongs to Owner B, else None."""
    if path in ('/api/networking/status', '/api/inbox/status'):
        return 200, {
            'owner': 'Owner B',
            'scope': ['contacts_d4', 'outreach_oauth', 'cooldown_optout', 'inbox_sync', 'callback_ui'],
            'implemented': False,
            'available': ['outreach_delivery'] if path == '/api/networking/status' else ['fictional_inbox'],
            'note': 'See plans/OWNER_B_WORKBOOK.md for the remaining work.',
        }
    if path.startswith('/api/networking/') or path.startswith('/api/inbox/'):
        return 501, {
            'error': 'Owner B endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_B_WORKBOOK.md',
        }
    return None


def handle_post(path: str, payload: dict):
    """Return (status_code, payload) if path belongs to Owner B, else None."""
    if path == '/api/networking/outreach/drafts' or (match := OUTREACH_PATH.fullmatch(path)):
        if not isinstance(payload, dict):
            return 400, {'error': 'Expected a JSON object.'}
        try:
            if path == '/api/networking/outreach/drafts':
                return create_delivery_draft(payload)
            return handle_delivery(int(match[1]), match[2], payload)
        except (ValueError, TypeError) as exc:
            return 400, {'error': str(exc)}
    if path == '/api/inbox/simulate':
        fixture = Path(__file__).resolve().parents[1] / 'sample_data' / 'fictional_inbox.json'
        messages = json.loads(fixture.read_text(encoding='utf-8'))
        return 200, {'mode': 'TEST ONLY', 'replies': [
            {'subject': message['subject'], 'classification': classify_reply(
                message['from'], message['subject'], message['body']
            )}
            for message in messages
        ]}
    if path == '/api/outreach/prepare' and os.getenv('JOBFINDER_LLM_OUTREACH') == '1':
        return prepare_llm_draft(payload)
    if path.startswith('/api/networking/') or path.startswith('/api/inbox/'):
        return 501, {
            'error': 'Owner B endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_B_WORKBOOK.md',
        }
    return None


def prepare_llm_draft(payload):
    job = db.row('SELECT * FROM jobs WHERE id=?', (int(payload.get('job_id', 0)),))
    if not job:
        return 404, {'error': 'Unknown job ID'}
    contact = payload.get('contact') or {}
    if not isinstance(contact, dict):
        return 400, {'error': 'Enter a verified contact name and role.'}
    name = str(contact.get('name', '')).strip()
    role = str(contact.get('role', '')).strip()
    channel = payload.get('channel', 'email')
    if not name or not role or channel not in ('email', 'linkedin'):
        return 400, {'error': 'Enter a verified contact name and role and select a valid channel.'}

    try:
        from .adapters_pipeline import UnifiedModelAdapter
    except ModuleNotFoundError as exc:
        if exc.name != 'app.adapters_pipeline':
            raise
        return 503, {'error': 'The shared LLM adapter is not available yet.'}

    resume = db.row('SELECT resume FROM profile WHERE id=1')['resume']
    try:
        draft = generate_outreach_draft(UnifiedModelAdapter(), resume, job, {'name': name, 'role': role}, channel)
    except Exception:
        return 502, {'error': 'Could not generate a draft. Check the LLM configuration or retry.'}

    with db.connection() as con:
        con.execute(
            'INSERT INTO outreach(job_id,contact_name,contact_role,contact_profile,subject,body) VALUES(?,?,?,?,?,?)',
            (job['id'], name, role, str(contact.get('profile', '')), draft['subject'], draft['body']),
        )
    return 200, draft
