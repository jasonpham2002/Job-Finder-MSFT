"""Extension contracts. None of these functions actually contact outside services.

Students must implement them with appropriate APIs, credentials, permission,
confirmation evidence, and tests. Do not silently simulate success.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionResult:
    status: str  # confirmed | sent | unknown | failed | manual_required
    confirmation_id: Optional[str] = None
    details: str = ''


class JobDiscoveryAdapter:
    def search(self, filters):
        raise NotImplementedError('Build permitted live job discovery; use normalized Job schema.')


class ResumeFileAdapter:
    def extract(self, file_bytes, filename):
        raise NotImplementedError('Implement PDF/DOCX/TXT extraction with privacy safeguards.')


class ModelAdapter:
    def generate(self, system_prompt, user_prompt, output_schema):
        raise NotImplementedError('Implement OpenAI, Anthropic, or another supported API; no hardcoded keys.')


class ApplicationAdapter:
    def prepare(self, job, profile, approved_resume):
        raise NotImplementedError('Build supported ATS workflow; capture exact form answers.')

    def submit(self, prepared_application, explicit_user_approval) -> ActionResult:
        if not explicit_user_approval:
            raise PermissionError('Cannot submit without candidate approval.')
        raise NotImplementedError('Add a permitted application adapter with confirmation evidence.')


class ProfessionalContactAdapter:
    def research(self, job):
        raise NotImplementedError('Use legitimate sources; no prohibited LinkedIn scraping or guessed emails.')


class OutreachAdapter:
    def send(self, message, explicit_user_approval) -> ActionResult:
        if not explicit_user_approval:
            raise PermissionError('Cannot send without user approval.')
        raise NotImplementedError('Connect authorized Gmail/Outlook provider; capture message ID.')


class InboxAdapter:
    def sync(self, connection, since):
        raise NotImplementedError('Read authorized inbox threads and classify replies.')
