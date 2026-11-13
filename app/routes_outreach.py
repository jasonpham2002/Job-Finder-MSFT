"""Owner B modular routes: artifact contacts, authorized outreach, inbox sync & callbacks.

Teammate B implements concrete logic here and in app/adapters_outreach.py without
touching app/server.py or Owner A files.
"""



import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from email.errors import HeaderParseError
from email.headerregistry import Address
from hashlib import sha256
from http.client import HTTPException
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from urllib.error import HTTPError
from urllib.parse import urlsplit

from . import db
from .adapters_outreach import (
    GmailInboxAdapter, GmailOutreachAdapter, ManualOutreachAdapter, OutlookOutreachAdapter,
    PublicArtifactContactAdapter, classify_reply, generate_outreach_draft,
)

OUTREACH_PATH = re.compile(r'/api/networking/outreach/([0-9]+)/(approve|send|manual-sent)')
EMAIL_PROVIDERS = {'gmail': GmailOutreachAdapter, 'outlook': OutlookOutreachAdapter, 'manual': ManualOutreachAdapter}
INBOX_SYNC_TOKEN = token_urlsafe(32)
CONTACT_OPTOUT_PATH = re.compile(r'/api/networking/contacts/([0-9]+)/opt-out')


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
        con.execute('BEGIN IMMEDIATE')
        job = con.execute('SELECT * FROM jobs WHERE id=?', (int(payload.get('job_id', 0)),)).fetchone()
        if job is None:
            return 404, {'error': 'Unknown job ID.'}
        if job['origin'] in ('fictional-sample', 'demo') or not public_link(job['url']):
            return 403, {'error': 'Delivery requires a real job and its source URL.'}
        blocked = delivery_block(con, {
            'id': 0, 'company': job['company'], 'contact_name': name, 'opted_out': False,
            'public_email': recipient if channel == 'email' else '',
            'linkedin_url': recipient if channel == 'linkedin' else '',
        })
        if blocked:
            return 409, {'error': blocked}
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


def cooldown_days():
    config_path = Path(__file__).resolve().parents[1] / 'config.json'
    if not config_path.is_file():
        return 14
    days = json.loads(config_path.read_text(encoding='utf8')).get('company_outreach_cooldown_days', 14)
    if type(days) is not int or days < 1:
        raise ValueError('company_outreach_cooldown_days must be a positive integer.')
    return days


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
                OR (o.status IN ('sent','manual_sent') AND datetime(o.sent_at)>datetime('now',?)))''',
        (row['id'], row['company'], destination, destination, f'-{cooldown_days()} days'),
    ).fetchone()
    if recent:
        return 'Recent or unresolved outreach blocks delivery. Check the previous message first.'
    return None


def research_contacts(payload):
    job = db.row('SELECT * FROM jobs WHERE id=?', (int(payload.get('job_id', 0)),))
    if not job:
        return 404, {'error': 'Unknown job ID.'}
    source = str(payload.get('source_url', '')).strip()
    if job['origin'] in ('fictional-sample', 'demo'):
        return 400, {'error': 'Import a real job before researching contacts.'}
    if not public_link(source) or payload.get('employer_source_confirmed') is not True:
        return 400, {'error': 'Confirm a public source published by this employer.'}
    try:
        contacts = PublicArtifactContactAdapter().research({**job, 'source_url': source})
    except (OSError, HTTPException, ValueError, TypeError):
        contacts = []
    results = []
    with db.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        for contact in contacts:
            artifact = contact.artifact_hook
            existing = con.execute(
                'SELECT id FROM contacts WHERE job_id=? AND name=? AND source_url=?',
                (job['id'], contact.name, source),
            ).fetchone()
            values = (contact.title, contact.professional_email or '', artifact['type'], artifact['title'],
                      artifact['url'], artifact['snippet'])
            if existing:
                contact_id = existing['id']
                con.execute(
                    '''UPDATE contacts SET role=?,public_email=?,artifact_type=?,artifact_title=?,
                       artifact_url=?,artifact_snippet=?,verification_status='verified_public' WHERE id=?''',
                    (*values, contact_id),
                )
            else:
                contact_id = con.execute(
                    '''INSERT INTO contacts(job_id,company,name,source_url,role,public_email,artifact_type,
                       artifact_title,artifact_url,artifact_snippet,verification_status)
                       VALUES(?,?,?,?,?,?,?,?,?,?,'verified_public')''',
                    (job['id'], job['company'], contact.name, source, *values),
                ).lastrowid
            results.append({**asdict(contact), 'id': contact_id})
    return 200, {'contacts': results, 'manual_queries': [] if results else [
        f'"{job["company"]}" "{job["title"]}" team bio',
        f'"{job["company"]}" recruiting team careers',
    ]}


def opt_out_contact(contact_id, payload):
    if payload.get('sync_token') != INBOX_SYNC_TOKEN:
        return 403, {'error': 'Open JobFinder to update the contact.'}
    with db.connection() as con:
        updated = con.execute('UPDATE contacts SET opted_out=1 WHERE id=?', (contact_id,))
        if not updated.rowcount:
            return 404, {'error': 'Unknown contact.'}
    return 200, {'opted_out': True}


def llm_outreach_enabled():
    value = os.getenv('JOBFINDER_LLM_OUTREACH')
    if value is not None:
        return value == '1'
    try:
        from .adapters_pipeline import load_local_env
    except ModuleNotFoundError as exc:
        if exc.name != 'app.adapters_pipeline':
            raise
        return False

    return load_local_env().get('JOBFINDER_LLM_OUTREACH') == '1'


def artifact_draft(payload):
    contact = db.row('SELECT * FROM contacts WHERE id=?', (int(payload.get('contact_id', 0)),))
    if not contact or contact['verification_status'] != 'verified_public' or not contact['artifact_snippet']:
        return 400, {'error': 'Select a verified contact with a public artifact first.'}
    job = db.row('SELECT * FROM jobs WHERE id=?', (contact['job_id'],))
    channel = payload.get('channel', 'email')
    if not job or channel not in ('email', 'linkedin'):
        return 400, {'error': 'Select a valid job and outreach channel.'}
    with db.connection() as con:
        blocked = delivery_block(con, {**contact, 'id': 0, 'contact_name': contact['name']})
    if blocked:
        return 409, {'error': blocked}
    artifact = {key: contact['artifact_' + key] for key in ('type', 'title', 'url', 'snippet')}
    subject = f'Question about the {job["title"]} role'[:200] if channel == 'email' else ''
    body = (f'Hi {contact["name"]}, I found your bio on the {job["company"]} website ({artifact["url"]}). '
            f'I’m interested in the {job["title"]} role. '
            'Would you be open to sharing what the team looks for in candidates?')
    if llm_outreach_enabled():
        try:
            from .adapters_pipeline import UnifiedModelAdapter
        except ModuleNotFoundError as exc:
            if exc.name != 'app.adapters_pipeline':
                raise
        else:
            resume = db.row('SELECT resume FROM profile WHERE id=1')['resume']
            try:
                generated = generate_outreach_draft(UnifiedModelAdapter(), resume, job, {
                    'name': contact['name'], 'role': contact['role'], 'artifact_hook': artifact,
                }, channel)
                subject, body = generated['subject'], generated['body']
            except (ValueError, RuntimeError, OSError):
                pass
    return 200, {'subject': subject, 'body': body, 'status': 'draft', 'artifact_hook': artifact}


def callback_packet(reply_id):
    linked = db.row(
        """SELECT a.callback_packet_json FROM replies r JOIN applications a ON a.id=r.application_id
           WHERE r.id=? AND r.classification IN ('human_positive_reply','interview_invitation',
           'referral_opportunity','request_for_info') AND a.status='confirmed' AND a.confirmation!=''""",
        (reply_id,),
    )
    try:
        packet = json.loads(linked['callback_packet_json']) if linked else None
    except (TypeError, ValueError):
        packet = None
    return packet if isinstance(packet, dict) and packet else None


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

def sync_inbox(payload):
    if (not isinstance(payload, dict) or payload.get('explicit_inbox_consent') is not True
            or payload.get('sync_token') != INBOX_SYNC_TOKEN):
        return 403, {'error': 'Confirm read-only sync of Gmail messages labeled JobFinder.'}
    try:
        replies = GmailInboxAdapter().sync(connection=None)
    except FileNotFoundError:
        return 409, {'error': 'Run python -m app.adapters_outreach authorize-gmail-inbox first.'}
    except HTTPError as exc:
        return 502, {'error': f'Gmail inbox sync failed (HTTP {exc.code}). Check read-only authorization.'}
    except (OSError, HTTPException, ValueError, KeyError, TypeError):
        return 502, {'error': 'Gmail inbox sync failed. Check the OAuth configuration and connection.'}
    with db.connection() as con:
        before = con.total_changes
        con.executemany(
            '''INSERT INTO replies(provider_message_id,thread_id,sender,subject,snippet,classification,received_at)
               VALUES(?,?,?,?,?,?,?) ON CONFLICT(provider_message_id) DO NOTHING''',
            [(r.provider_message_id, r.thread_id, r.sender, r.subject, r.snippet, r.classification, r.received_at)
             for r in replies],
        )
        inserted = con.total_changes - before
    return 200, {'mode': 'gmail', 'scanned': len(replies), 'inserted': inserted}


def handle_get(path: str):
    """Return (status_code, payload) if path belongs to Owner B, else None."""
    if path == '/api/inbox/replies':
        replies = db.rows(
            '''SELECT id,provider_message_id,thread_id,sender,subject,snippet,classification,human_verified,received_at
               FROM replies ORDER BY received_at DESC,id DESC LIMIT 100'''
        )
        for reply in replies:
            reply['callback_packet'] = callback_packet(reply['id'])
        return 200, {'mode': 'gmail', 'replies': replies}
    if path in ('/api/networking/status', '/api/inbox/status'):
        return 200, {
            'owner': 'Owner B',
            'scope': ['contacts_d4', 'outreach_oauth', 'cooldown_optout', 'inbox_sync', 'callback_ui'],
            'implemented': False,
            'available': ['outreach_delivery'] if path == '/api/networking/status' else ['fictional_inbox', 'gmail_sync'],
            **({'sync_token': INBOX_SYNC_TOKEN} if path == '/api/inbox/status' else {}),
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
    if path == '/api/inbox/link-application':
        if not isinstance(payload, dict) or payload.get('sync_token') != INBOX_SYNC_TOKEN:
            return 403, {'error': 'Open Inbox Tracker to link a reply.'}
        with db.connection() as con:
            updated = con.execute(
                """UPDATE replies SET application_id=? WHERE id=? AND EXISTS (
                   SELECT 1 FROM applications WHERE id=? AND status='confirmed' AND confirmation!='')""",
                (payload.get('application_id'), payload.get('reply_id'), payload.get('application_id')),
            )
        return (200, {'linked': True}) if updated.rowcount else (404, {'error': 'Reply or confirmed application not found.'})
    if path == '/api/networking/outreach/drafts' or (match := OUTREACH_PATH.fullmatch(path)):
        if not isinstance(payload, dict):
            return 400, {'error': 'Expected a JSON object.'}
        try:
            if path == '/api/networking/outreach/drafts':
                return create_delivery_draft(payload)
            return handle_delivery(int(match[1]), match[2], payload)
        except (ValueError, TypeError) as exc:
            return 400, {'error': str(exc)}
    if path in ('/api/networking/contacts/research', '/api/networking/contacts/draft') or (
        opt_out := CONTACT_OPTOUT_PATH.fullmatch(path)
    ):
        if not isinstance(payload, dict):
            return 400, {'error': 'Expected a JSON object.'}
        try:
            if path == '/api/networking/contacts/research':
                if payload.get('sync_token') != INBOX_SYNC_TOKEN:
                    return 403, {'error': 'Open JobFinder to research an employer source.'}
                return research_contacts(payload)
            if path == '/api/networking/contacts/draft':
                return artifact_draft(payload)
            return opt_out_contact(int(opt_out[1]), payload)
        except (ValueError, TypeError) as exc:
            return 400, {'error': str(exc)}
    if path == '/api/inbox/sync':
        return sync_inbox(payload)
    if path == '/api/inbox/simulate':
        fixture = Path(__file__).resolve().parents[1] / 'sample_data' / 'fictional_inbox.json'
        messages = json.loads(fixture.read_text(encoding='utf-8'))
        return 200, {'mode': 'TEST ONLY', 'replies': [
            {'subject': message['subject'], 'classification': classify_reply(
                message['from'], message['subject'], message['body']
            )}
            for message in messages
        ]}
    if path == '/api/outreach/prepare' and isinstance(payload, dict):
        contact = payload.get('contact') or {}
        if not isinstance(contact, dict):
            return 400, {'error': 'Provide a contact record.'}
        job = db.row('SELECT company FROM jobs WHERE id=?', (int(payload.get('job_id', 0)),))
        if job:
            with db.connection() as con:
                blocked = delivery_block(con, {
                    'id': 0, 'company': job['company'], 'contact_name': str(contact.get('name', '')).strip(),
                    'opted_out': False, 'public_email': str(contact.get('email', '')).strip(),
                    'linkedin_url': str(contact.get('profile', '')).strip().rstrip('/'),
                })
            if blocked:
                return 409, {'error': blocked}
        if llm_outreach_enabled():
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
