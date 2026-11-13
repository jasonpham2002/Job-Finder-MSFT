"""Outreach providers and draft helpers."""
import base64
import json
import os
from email.message import EmailMessage
from http.client import HTTPException
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib import error, parse, request

from .adapters import ActionResult, OutreachAdapter

GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
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


def authorize_gmail():
    """Run desktop consent separately from any request to send a message."""
    client = gmail_client()
    destination = gmail_token_path()
    if destination.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Gmail credentials must be stored outside the project.')
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config({'installed': {
        **client,
        'auth_uri': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_uri': GMAIL_TOKEN_URL,
        'redirect_uris': ['http://127.0.0.1'],
    }}, scopes=[GMAIL_SCOPE], autogenerate_code_verifier=True)
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


class GmailOutreachAdapter(OutreachAdapter):
    def _access_token(self):
        client = gmail_client()
        saved = json.loads(gmail_token_path().read_text(encoding='utf8'))
        if saved['client_id'] != client['client_id']:
            raise ValueError('The saved Gmail credential belongs to another OAuth client.')
        form = parse.urlencode({
            **client, 'grant_type': 'refresh_token', 'refresh_token': saved['refresh_token'],
        }).encode('ascii')
        access_token = provider_json(request.Request(GMAIL_TOKEN_URL, data=form))['access_token']
        if not isinstance(access_token, str) or not access_token.strip() or any(c.isspace() for c in access_token):
            raise ValueError('Google returned an invalid access token.')
        return access_token

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


def classify_reply(sender, subject, body):
    """Classify recruiting messages using conservative text rules."""
    sender = sender.casefold()
    text = f'{subject}\n{body}'.casefold().replace('’', "'")
    if any(marker in text for marker in ('not moving forward', 'not be moving forward', 'other candidates')):
        return 'rejection'
    if any(marker in text for marker in ('automated confirmation', 'application has been received', 'application received')) or any(
        marker in sender for marker in ('no-reply', 'noreply', 'do-not-reply')
    ):
        return 'automated_receipt'
    if 'interview' in text and any(marker in text for marker in ('schedule', 'invite', 'availability')):
        return 'interview_invitation'
    if 'availability' in text and 'conversation' in text:
        return 'human_positive_reply'
    return 'unknown'


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['authorize-gmail'])
    parser.parse_args()
    try:
        authorize_gmail()
    except ImportError:
        parser.exit(1, 'Install google-auth-oauthlib to authorize Gmail.\n')
    except Exception:
        parser.exit(1, 'Gmail authorization failed. Check the desktop OAuth configuration and retry.\n')
    print('Gmail authorization saved locally.')
