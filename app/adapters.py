"""Extension contracts and typed payloads for Owner A and Owner B adapters.

None of these base classes contact outside services. Teammates implement concrete
subclasses in app/adapters_pipeline.py (Owner A) and app/adapters_outreach.py (Owner B).
Do not silently simulate success or omit external confirmation evidence.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ActionResult:
    status: str  # confirmed | sent | unknown | failed | manual_required
    confirmation_id: Optional[str] = None
    details: str = ''
    resume_sha256: Optional[str] = None
    answers_sha256: Optional[str] = None
    evidence_path: Optional[str] = None


@dataclass
class JobPreflight:
    ats_family: str  # greenhouse | lever | ashby | workday | linkedin | indeed | company_site | unknown
    liveness_status: str  # active | stale_risk | closed | unknown
    scam_risk: str  # low | medium | high
    scam_flags: list[str] = field(default_factory=list)
    friction_roi: str = 'standard'  # high_roi_low_bot_noise | standard | saturated_easy_apply | high_risk
    notes: str = ''


@dataclass
class TailoredResumeResult:
    tailored_text: str
    claim_evidence_map: list[dict[str, str]] = field(default_factory=list)
    slop_warnings: list[str] = field(default_factory=list)
    unverified_claims: list[str] = field(default_factory=list)
    questions_for_candidate: list[str] = field(default_factory=list)
    ats_preview_text: str = ''


@dataclass
class GapAnalysisResult:
    wording_gaps: list[dict[str, str]] = field(default_factory=list)
    skill_gaps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CoPilotPacket:
    job_id: int
    ats_family: str
    ordered_sections: list[dict[str, Any]] = field(default_factory=list)
    sensitive_fields_locked: list[str] = field(default_factory=lambda: [
        'work_authorization', 'visa_sponsorship', 'salary_expectation',
        'veteran_status', 'disability_status', 'references',
    ])
    callback_packet: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifiedContact:
    name: str
    title: str
    company: str
    source_url: str
    verification_status: str  # verified_public | user_provided | unverified | fictional_test
    linkedin_url: Optional[str] = None
    professional_email: Optional[str] = None
    relevance_reason: str = ''
    artifact_hook: Optional[dict[str, str]] = None
    opted_out: bool = False


@dataclass
class InboxReply:
    provider_message_id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    classification: str  # human_positive_reply | automated_receipt | interview_invitation | referral_opportunity | rejection | request_for_info | unsubscribe | unknown
    human_verified: bool
    received_at: str = ''
    follow_up_draft: str = ''


class JobDiscoveryAdapter:
    def search(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError('Owner A: build permitted live job discovery (Greenhouse/Lever/Ashby feeds).')

    def preflight_job(self, job: dict[str, Any]) -> JobPreflight:
        raise NotImplementedError('Owner A: implement D1 ghost-job, scam, and friction-ROI pre-flight check.')


class ResumeFileAdapter:
    def extract(self, file_bytes: bytes, filename: str) -> str:
        raise NotImplementedError('Owner A: implement PDF/DOCX/TXT extraction with privacy safeguards.')

    def extract_plain_preview(self, file_bytes: bytes, filename: str) -> str:
        raise NotImplementedError('Owner A: implement D2 ATS plain-text linearization preview.')


class ModelAdapter:
    def generate(self, system_prompt: str, user_prompt: str, output_schema: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        raise NotImplementedError('Owner A: implement OpenAI, Gemini, or Anthropic behind unified config.')


class ApplicationAdapter:
    def prepare(self, job: dict[str, Any], profile: dict[str, Any], approved_resume: str) -> CoPilotPacket:
        raise NotImplementedError('Owner A: implement D3 Co-Pilot Packet with locked sensitive fields.')

    def submit(self, prepared_application: dict[str, Any], explicit_user_approval: bool) -> ActionResult:
        if not explicit_user_approval:
            raise PermissionError('Cannot submit without candidate approval.')
        raise NotImplementedError('Owner A: add permitted ATS/HITL or confirmed manual receipt capture.')


class ProfessionalContactAdapter:
    def research(self, job: dict[str, Any]) -> list[VerifiedContact]:
        raise NotImplementedError('Owner B: implement D4 artifact-first public contact discovery; never guess emails.')


class OutreachAdapter:
    def send(self, message: dict[str, Any], explicit_user_approval: bool) -> ActionResult:
        if not explicit_user_approval:
            raise PermissionError('Cannot send without user approval.')
        raise NotImplementedError('Owner B: connect authorized Gmail/Outlook provider with cooldown & opt-out guard.')


class InboxAdapter:
    def sync(self, connection: Any, since: Optional[str] = None) -> list[InboxReply]:
        raise NotImplementedError('Owner B: read authorized inbox threads and classify replies safely.')
