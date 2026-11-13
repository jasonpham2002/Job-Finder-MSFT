"""Outreach providers and draft helpers."""
import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from email.message import EmailMessage
from http.client import HTTPException
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib import error, parse, request

from .adapters import ActionResult, InboxAdapter, InboxReply, OutreachAdapter, ProfessionalContactAdapter, VerifiedContact

GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
GMAIL_READ_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
GMAIL_API = 'https://gmail.googleapis.com/gmail/v1/users/me'
GMAIL_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GMAIL_SEND_URL = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'


def gmail_client():
    client_id = os.environ.get('GMAIL_OAUTH_CLIENT_ID')
    client_secret = os.environ.get('GMAIL_OAUTH_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise ValueError('Set GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET.')
    return {'client_id': client_id, 'client_secret': client_secret}


def gmail_token_path():
    return Path.home() / '.jobfinder' / 'gmail-outreach.json'


def gmail_inbox_token_path():
    return gmail_token_path().with_name('gmail-inbox.json')


def authorize_gmail(inbox=False):
    """Run desktop consent separately from any request to send a message."""
    client = gmail_client()
    destination = gmail_inbox_token_path() if inbox else gmail_token_path()
    if destination.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Gmail credentials must be stored outside the project.')
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config({'installed': {
        **client,
        'auth_uri': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_uri': GMAIL_TOKEN_URL,
        'redirect_uris': ['http://127.0.0.1'],
    }}, scopes=[GMAIL_READ_SCOPE if inbox else GMAIL_SCOPE], autogenerate_code_verifier=True)
    credentials = flow.run_local_server(
        host='127.0.0.1', port=0, timeout_seconds=180, prompt='consent',
    )
    if not credentials.refresh_token:
        raise ValueError('Google did not issue an offline Gmail credential.')
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf8', dir=destination.parent, delete=False) as token:
        temporary_path = Path(token.name)
        try:
            json.dump({'client_id': client['client_id'], 'refresh_token': credentials.refresh_token}, token)
            token.close()
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)


class NoProviderRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def provider_json(req):
    with request.build_opener(NoProviderRedirects()).open(req, timeout=15) as response:
        return json.load(response)


def refresh_gmail_token(token_path):
    client = gmail_client()
    saved = json.loads(token_path.read_text(encoding='utf8'))
    if saved['client_id'] != client['client_id']:
        raise ValueError('The saved Gmail credential belongs to another OAuth client.')
    form = parse.urlencode({
        **client, 'grant_type': 'refresh_token', 'refresh_token': saved['refresh_token'],
    }).encode('ascii')
    access_token = provider_json(request.Request(GMAIL_TOKEN_URL, data=form))['access_token']
    if not isinstance(access_token, str) or not access_token.strip() or any(c.isspace() for c in access_token):
        raise ValueError('Google returned an invalid access token.')
    return access_token

class GmailOutreachAdapter(OutreachAdapter):
    def _access_token(self):
        return refresh_gmail_token(gmail_token_path())

    def send(self, message, explicit_user_approval):
        if explicit_user_approval is not True:
            raise PermissionError('Cannot send without user approval.')
        if message.get('channel') != 'email':
            return ActionResult('manual_required', details='Copy the approved message and send it manually.')

        email = EmailMessage()
        email['To'] = message['recipient']
        email['Subject'] = message['subject']
        email.set_content(message['body'])
        raw = base64.urlsafe_b64encode(email.as_bytes()).decode('ascii')
        try:
            token = self._access_token()
        except (OSError, HTTPException, ValueError, KeyError, TypeError):
            return ActionResult('manual_required', details='Authorize Gmail locally or use manual sending.')

        req = request.Request(GMAIL_SEND_URL, data=json.dumps({'raw': raw}).encode('utf8'), headers={
            'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
        })
        try:
            response = provider_json(req)
        except error.HTTPError as exc:
            if exc.code in {400, 401, 403, 404, 429}:
                return ActionResult('failed', details=f'Gmail rejected the request (HTTP {exc.code}).')
        except (OSError, HTTPException, ValueError):
            pass
        else:
            message_id = response.get('id') if isinstance(response, dict) else None
            if isinstance(message_id, str) and message_id.strip():
                return ActionResult('sent', confirmation_id=message_id)
        return ActionResult('unknown', details='Check Gmail Sent before attempting any follow-up.')


class ManualOutreachAdapter(OutreachAdapter):
    def send(self, message, explicit_user_approval):
        if explicit_user_approval is not True:
            raise PermissionError('Cannot send without user approval.')
        return ActionResult('manual_required', details='Copy the approved message and send it manually.')


class OutlookOutreachAdapter(ManualOutreachAdapter):
    """Outlook provider contract. Use manual delivery until Graph is integrated."""

    def __init__(self):
        self.client_id = os.environ.get('OUTLOOK_CLIENT_ID')

PROMPT = Path(__file__).resolve().parents[1] / 'prompts' / 'outreach_prompt.md'


class PublicArtifactContactAdapter(ProfessionalContactAdapter):
    """Extract explicitly attributed people from public employer pages."""

    def research(self, job):
        from .engine import JobParser, valid_public_url

        source = job['source_url']
        parsed = parse.urlsplit(source)
        host = (parsed.hostname or '').rstrip('.').casefold()
        if any(host == site or host.endswith('.' + site) for site in ('linkedin.com', 'indeed.com')):
            raise ValueError('Use a public employer page or paste professional evidence.')
        valid_public_url(source)
        req = request.Request(source, headers={'Accept': 'text/html', 'User-Agent': 'JobFinder/1.0'})
        with request.build_opener(NoProviderRedirects()).open(req, timeout=8) as response:
            if response.headers.get_content_type() != 'text/html':
                raise ValueError('The source must be a public employer HTML page.')
            parser = JobParser()
            parser.feed(response.read(500_000).decode('utf8', errors='replace'))
        return self.extract(job, parser.job_ld)

    def extract(self, job, nodes):
        contacts = {}
        company = job['company']
        source = job['source_url']
        pending = list(nodes)
        while pending and len(contacts) < 3:
            node = pending.pop()
            if isinstance(node, list):
                pending.extend(reversed(node))
            if not isinstance(node, dict):
                continue
            pending.extend(node[key] for key in ('@graph', 'mainEntity', 'author', 'employee', 'itemListElement', 'item')
                           if key in node)
            kinds = node.get('@type', [])
            if kinds != 'Person' and not (isinstance(kinds, list) and 'Person' in kinds):
                continue
            employer = node.get('worksFor')
            employer = employer.get('name') if isinstance(employer, dict) else employer
            name, title = node.get('name'), node.get('jobTitle')
            if not all(isinstance(value, str) and value.strip() for value in (name, title, employer)):
                continue
            if employer.strip().casefold() != company.strip().casefold():
                continue
            description = node.get('description')
            description = ' '.join(description.split())[:300] if isinstance(description, str) else ''
            if not description:
                continue
            email = node.get('email')
            email = email.removeprefix('mailto:').strip() if isinstance(email, str) else ''
            if not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_\x60{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', email):
                email = None
            contacts.setdefault(name.strip().casefold(), VerifiedContact(
                name=name.strip()[:160], title=title.strip()[:160], company=company,
                source_url=source, verification_status='verified_public', professional_email=email,
                relevance_reason=f'The employer source lists this person as {title.strip()[:160]}. Review team fit.',
                artifact_hook={'type': 'team_bio', 'title': f'{name.strip()[:160]} — {title.strip()[:160]}',
                               'url': source, 'snippet': description},
            ))
        return list(contacts.values())
DRAFT_SCHEMA = {
    'type': 'object',
    'properties': {'subject': {'type': 'string'}, 'body': {'type': 'string'}},
    'required': ['subject', 'body'],
    'additionalProperties': False,
}


def generate_outreach_draft(model, resume, job, contact, channel):
    inputs = {
        'resume': resume,
        'job': {key: job[key] for key in ('title', 'company', 'description')},
        'contact': {key: contact[key] for key in ('name', 'role')},
        'channel': channel,
    }
    if contact.get('artifact_hook'):
        inputs['contact']['artifact_hook'] = contact['artifact_hook']
    result = model.generate(PROMPT.read_text(encoding='utf-8'), json.dumps(inputs), DRAFT_SCHEMA)
    if not isinstance(result, dict) or set(result) != {'subject', 'body'}:
        raise ValueError('The model returned an invalid draft.')
    subject, body = result['subject'], result['body']
    if not isinstance(subject, str) or not isinstance(body, str) or not body.strip():
        raise ValueError('The model returned an invalid draft.')
    subject = subject.strip()
    if channel == 'email' and (not subject or len(subject) > 200 or '\n' in subject or '\r' in subject):
        raise ValueError('The model returned an invalid email subject.')
    return {'subject': subject if channel == 'email' else '', 'body': body.strip()}


class GmailInboxAdapter(InboxAdapter):
    """Read recent incoming messages the user labeled JobFinder in Gmail."""

    def sync(self, connection, since=None):
        cutoff = int(datetime.fromisoformat(since).timestamp()) if since else int(
            (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
        )
        token = refresh_gmail_token(gmail_inbox_token_path())
        headers = {'Authorization': f'Bearer {token}'}
        params = parse.urlencode({'q': f'label:JobFinder after:{cutoff} -in:sent', 'maxResults': 100})
        page = provider_json(request.Request(f'{GMAIL_API}/messages?{params}', headers=headers))
        replies = []
        for item in page.get('messages', []):
            message_id = parse.quote(item['id'], safe='')
            fields = {'format': 'full', 'fields': 'threadId,internalDate,snippet,payload(headers)'}
            try:
                message = provider_json(request.Request(
                    f'{GMAIL_API}/messages/{message_id}?{parse.urlencode(fields)}', headers=headers,
                ))
            except error.HTTPError as exc:
                if exc.code == 404:
                    continue  # The message was removed after Gmail listed it.
                raise
            metadata = {h['name'].casefold(): h['value'] for h in message['payload']['headers']}
            sender = metadata.get('from', '')
            subject = metadata.get('subject', '')
            snippet = unescape(message.get('snippet', ''))
            automated = (
                metadata.get('auto-submitted', 'no').strip().casefold() != 'no'
                or metadata.get('precedence', '').strip().casefold() in ('bulk', 'list', 'junk')
            )
            replies.append(InboxReply(
                provider_message_id=item['id'], thread_id=message['threadId'],
                sender=sender[:320], subject=subject[:500], snippet=snippet[:240],
                classification=classify_reply(sender, subject, snippet, automated=automated),
                human_verified=False,
                received_at=datetime.fromtimestamp(int(message['internalDate']) / 1000, timezone.utc).isoformat(),
            ))
        return replies


def classify_reply(sender, subject, body, *, automated=False):
    """Classify recruiting messages using conservative text rules."""
    sender = sender.casefold()
    fresh_body = re.split(r'(?m)^\s*>|^On .+ wrote:', body, maxsplit=1)[0]
    text = f'{subject}\n{fresh_body}'.casefold().replace('’', "'")
    if automated:
        return 'automated_receipt'
    if re.search(r'\b(unsubscribe me|remove me from|do not contact me|stop emailing me)\b', text):
        return 'unsubscribe'
    if any(marker in text for marker in ('not moving forward', 'not be moving forward', 'other candidates')):
        return 'rejection'
    if any(marker in text for marker in ('automated confirmation', 'application has been received', 'application received')) or any(
        marker in sender for marker in ('no-reply', 'noreply', 'do-not-reply')
    ):
        return 'automated_receipt'
    if 'interview' in text and any(marker in text for marker in ('schedule', 'invite', 'availability')):
        return 'interview_invitation'
    if re.search(r"\b(i can refer you|i'd be happy to refer you|i can put you in touch)\b", text):
        return 'referral_opportunity'
    if re.search(r'\b(please send|could you share) (your|a copy of your) (resume|cv|portfolio)\b', text):
        return 'request_for_info'
    if 'availability' in text and 'conversation' in text:
        return 'human_positive_reply'
    return 'unknown'


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['authorize-gmail', 'authorize-gmail-inbox'])
    args = parser.parse_args()
    try:
        authorize_gmail(inbox=args.command == 'authorize-gmail-inbox')
    except ImportError:
        parser.exit(1, 'Install google-auth-oauthlib to authorize Gmail.\n')
    except Exception:
        parser.exit(1, 'Gmail authorization failed. Check the desktop OAuth configuration and retry.\n')
    print('Gmail authorization saved locally.')
