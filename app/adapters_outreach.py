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


_ROLE_KEYWORDS_RE = re.compile(
    r'\b(?:Recruiter|Recruiting|Talent\s+Acquisition|People\s+Partner|Hiring\s+Manager|'
    r'Engineering\s+Manager|Software\s+Engineer|Staff\s+Engineer|Principal\s+Engineer|'
    r'Senior\s+Engineer|Solutions\s+Engineer|Developer|Director\s+of\s+Engineering|'
    r'VP\s+of\s+Engineering|Head\s+of\s+Engineering|Tech\s+Lead|Team\s+Lead|'
    r'Research\s+Scientist|Data\s+Scientist|Product\s+Manager|CTO|Co-Founder|Founder)\b',
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r'[A-Za-z0-9.!#$%&\x27*+/=?^_\x60{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')


def _validate_non_prohibited_public_url(url: str) -> str:
    from .engine import valid_public_url

    parsed = parse.urlsplit(url)
    host = (parsed.hostname or '').rstrip('.').casefold()
    if any(host == site or host.endswith('.' + site) for site in ('linkedin.com', 'indeed.com')):
        raise ValueError('Use a public employer page or paste professional evidence.')
    valid_public_url(url)
    return url


class PublicArtifactContactAdapter(ProfessionalContactAdapter):
    """Extract explicitly attributed people from public employer pages."""

    def research(self, job):
        from .engine import JobParser

        current = _validate_non_prohibited_public_url(job['source_url'])
        opener = request.build_opener(NoProviderRedirects())
        raw_html = ''
        for _ in range(4):
            req = request.Request(
                current,
                headers={'Accept': 'text/html,application/xhtml+xml', 'User-Agent': 'JobFinder/1.0'},
            )
            try:
                with opener.open(req, timeout=8) as response:
                    ctype = (response.headers.get_content_type() or '').lower()
                    if ctype not in ('text/html', 'application/xhtml+xml'):
                        raise ValueError('The source must be a public employer HTML page.')
                    raw_html = response.read(500_000).decode('utf8', errors='replace')
                    break
            except error.HTTPError as exc:
                if exc.code in (301, 302, 303, 307, 308):
                    location = exc.headers.get('Location') if exc.headers else None
                    if not location:
                        raise ValueError('Redirect missing Location header.') from exc
                    current = _validate_non_prohibited_public_url(parse.urljoin(current, location))
                    continue
                raise
        else:
            raise ValueError('Too many redirects while fetching public employer source.')

        parser = JobParser()
        parser.feed(raw_html)
        effective_job = {**job, 'source_url': current}
        extracted = self.extract(effective_job, parser.job_ld)
        if extracted:
            return extracted
        return self.extract_html_contacts(effective_job, raw_html, parser)

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
            if not _EMAIL_RE.fullmatch(email):
                email = None
            contacts.setdefault(name.strip().casefold(), VerifiedContact(
                name=name.strip()[:160], title=title.strip()[:160], company=company,
                source_url=source, verification_status='verified_public', professional_email=email,
                relevance_reason=f'The employer source lists this person as {title.strip()[:160]}. Review team fit.',
                artifact_hook={'type': 'team_bio', 'title': f'{name.strip()[:160]} — {title.strip()[:160]}',
                               'url': source, 'snippet': description},
            ))
        return list(contacts.values())

    def extract_html_contacts(self, job, raw_html: str, parser=None):
        """Extract attributed contacts from public HTML team cards or engineering blog author metadata."""
        company = str(job.get('company') or '').strip()
        source = str(job.get('source_url') or '').strip()
        if not company or not source or not raw_html:
            return []
        plain_all = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', unescape(raw_html))).strip()
        if company.casefold() not in plain_all.casefold():
            return []

        contacts = {}
        card_pattern = re.compile(
            r'<(?:article|section|li|div)\b[^>]*>(.*?)</(?:article|section|li|div)>',
            re.IGNORECASE | re.DOTALL,
        )
        name_role_pattern = re.compile(
            r'([A-Z][a-zA-Z.\'-]+(?:\s+[A-Z][a-zA-Z.\'-]+){1,2})\s*(?:[—–·|,-]|\n)\s*'
            r'([A-Za-z0-9 &/,\'-]{3,80})',
        )
        for match in card_pattern.finditer(raw_html):
            if len(contacts) >= 3:
                break
            block_html = match.group(1)
            block_text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' | ', unescape(block_html))).strip(' |')
            if len(block_text) < 35 or len(block_text) > 900:
                continue
            if not _ROLE_KEYWORDS_RE.search(block_text):
                continue
            segments = [seg.strip() for seg in block_text.split('|') if seg.strip()]
            person_name = ''
            person_role = ''
            snippet_parts = []
            for idx, seg in enumerate(segments):
                inline = name_role_pattern.fullmatch(seg)
                if inline and _ROLE_KEYWORDS_RE.search(inline.group(2)) and not person_name:
                    person_name = inline.group(1).strip()
                    person_role = inline.group(2).strip()
                    continue
                if (
                    not person_name
                    and re.fullmatch(r'[A-Z][a-zA-Z.\'-]+(?:\s+[A-Z][a-zA-Z.\'-]+){1,2}', seg)
                    and idx + 1 < len(segments)
                    and _ROLE_KEYWORDS_RE.search(segments[idx + 1])
                    and len(segments[idx + 1]) <= 90
                ):
                    person_name = seg
                    person_role = segments[idx + 1]
                    continue
                if seg not in (person_name, person_role) and len(seg) >= 20:
                    snippet_parts.append(seg)
            if not person_name or not person_role or not snippet_parts:
                continue
            snippet = ' '.join(snippet_parts)[:300]
            mailto_match = re.search(
                r'mailto:([A-Za-z0-9.!#$%&\x27*+/=?^_\x60{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})',
                block_html,
            )
            email = mailto_match.group(1) if mailto_match else None
            contacts.setdefault(person_name.casefold(), VerifiedContact(
                name=person_name[:160],
                title=person_role[:160],
                company=company,
                source_url=source,
                verification_status='verified_public',
                professional_email=email,
                relevance_reason=f'The public employer page lists {person_name[:160]} as {person_role[:160]}.',
                artifact_hook={
                    'type': 'team_bio',
                    'title': f'{person_name[:160]} — {person_role[:160]}',
                    'url': source,
                    'snippet': snippet,
                },
            ))

        if not contacts:
            author_match = re.search(
                r'<meta\b[^>]+(?:name|property)=["\'](?:author|article:author)["\'][^>]+content=["\']([^"\']+)["\']',
                raw_html,
                re.IGNORECASE,
            )
            if author_match:
                author_name = unescape(author_match.group(1)).strip()
                role_match = _ROLE_KEYWORDS_RE.search(plain_all)
                page_title = (getattr(parser, 'metatitle', '') or getattr(parser, 'title', '') or 'Employer Article').strip()
                page_desc = (getattr(parser, 'description', '') or plain_all[:260]).strip()
                if (
                    re.fullmatch(r'[A-Z][a-zA-Z.\'-]+(?:\s+[A-Z][a-zA-Z.\'-]+){1,2}', author_name)
                    and len(page_desc) >= 20
                ):
                    role_label = role_match.group(0) if role_match else 'Team Author'
                    contacts[author_name.casefold()] = VerifiedContact(
                        name=author_name[:160],
                        title=role_label[:160],
                        company=company,
                        source_url=source,
                        verification_status='verified_public',
                        professional_email=None,
                        relevance_reason=f'Published author of "{page_title[:120]}" on {company} public page.',
                        artifact_hook={
                            'type': 'blog_post',
                            'title': page_title[:160],
                            'url': source,
                            'snippet': page_desc[:300],
                        },
                    )
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
    if any(marker in text for marker in ('not moving forward', 'not be moving forward', 'other candidates', 'unfortunately we')):
        return 'rejection'
    if any(marker in text for marker in ('automated confirmation', 'application has been received', 'application received', 'auto-reply', 'automatic reply')) or any(
        marker in sender for marker in ('no-reply', 'noreply', 'do-not-reply')
    ):
        return 'automated_receipt'
    if 'interview' in text and any(marker in text for marker in ('schedule', 'invite', 'invitation', 'availability', 'calendar', 'book a time')):
        return 'interview_invitation'
    if re.search(r"\b(i can refer you|i'd be happy to refer you|happy to refer you|i can put you in touch|submit a referral)\b", text):
        return 'referral_opportunity'
    if re.search(r'\b(please send|could you share|send over) (your|a copy of your) (resume|cv|portfolio|github)\b', text):
        return 'request_for_info'
    if ('availability' in text and 'conversation' in text) or any(
        marker in text
        for marker in (
            'happy to chat',
            'love to chat',
            'open to a quick call',
            'free for a quick call',
            'free for a call',
            "let's connect",
            'would love to connect',
            'schedule a quick call',
            'share your availability',
            'chat next week',
        )
    ):
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
