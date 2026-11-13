"""Owner A modular routes: job discovery, preflight, PDF/DOCX, AI tailor, gaps, Co-Pilot apply.

Teammate A implements concrete logic here and in app/adapters_pipeline.py without
touching app/server.py or Owner B files.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db, engine
from .adapters_pipeline import (
    SENSITIVE_FIELDS,
    ApplicationError,
    CallbackCheatSheetBuilder,
    DuplicateApplicationError,
    GapBridgeAdapter,
    GapBridgeError,
    JobDiscoveryError,
    LiveJobDiscoveryAdapter,
    LocalResumeFileAdapter,
    ModelAdapterError,
    ModelNotConfiguredError,
    CoPilotApplicationAdapter,
    ResumeFileError,
    TailorError,
    UnifiedModelAdapter,
    VoicePreservingTailorAdapter,
    _build_schema_gap_artifact,
    analyze_ats_preview,
    build_minimal_docx_bytes,
    compute_job_fit_snapshot,
    compute_sha256_text,
    normalize_job_url,
)

MIN_RESUME_CHARS = 50
_JOB_PREFLIGHT_RE = re.compile(r'^/api/pipeline/jobs/(\d+)/preflight$')
_JOB_GAPS_RE = re.compile(r'^/api/pipeline/jobs/(\d+)/gaps$')
_GAP_VERIFY_RE = re.compile(r'^/api/pipeline/gaps/(\d+)/verify$')
_APP_COPILOT_RE = re.compile(r'^/api/pipeline/applications/(\d+)/copilot$')
_JOB_COPILOT_RE = re.compile(r'^/api/pipeline/jobs/(\d+)/copilot$')
_APP_CONFIRM_RE = re.compile(r'^/api/pipeline/applications/(\d+)/confirm$')
_APP_EXPORT_DOCX_RE = re.compile(r'^/api/pipeline/applications/(\d+)/export-docx$')
_APP_CALLBACK_RE = re.compile(r'^/api/pipeline/applications/(\d+)/callback-packet$')


def handle_get(path: str):
    """Return (status_code, payload) if path belongs to Owner A, else None."""
    if path == '/api/pipeline/status':
        return 200, {
            'owner': 'Owner A',
            'scope': ['discovery', 'preflight_d1', 'resume_pdf_docx', 'tailor_d2', 'gaps_d5', 'copilot_d3'],
            'implemented': True,
            'tasks_completed': ['A-01', 'A-02', 'A-03', 'A-04', 'A-05'],
            'model_adapter': UnifiedModelAdapter.inspect_capabilities(),
            'resume_adapter': {
                **LocalResumeFileAdapter.inspect_capabilities(),
                'max_upload_json_bytes': 200_000,
            },
            'discovery_adapter': LiveJobDiscoveryAdapter.inspect_capabilities(),
            'application_adapter': CoPilotApplicationAdapter.inspect_capabilities(),
            'tailor_adapter': VoicePreservingTailorAdapter.inspect_capabilities(),
            'gap_bridge_adapter': GapBridgeAdapter.inspect_capabilities(),
            'note': (
                'Tasks A-01..A-05 complete (ModelAdapter, ResumeFileAdapter, JobDiscoveryAdapter + D1, '
                'CoPilotApplicationAdapter + D3, VoicePreservingTailorAdapter + D2, GapBridgeAdapter + D5).'
            ),
        }
    if path == '/api/pipeline/gaps':
        return _handle_list_all_gaps()
    job_gaps_match = _JOB_GAPS_RE.match(path)
    if job_gaps_match:
        return _handle_get_job_gaps(int(job_gaps_match.group(1)))
    app_cb_match = _APP_CALLBACK_RE.match(path)
    if app_cb_match:
        return _handle_get_callback_packet(int(app_cb_match.group(1)))
    if path.startswith('/api/pipeline/'):
        return 501, {
            'error': 'Owner A endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_A_WORKBOOK.md',
        }
    return None


def _decode_upload_bytes(payload: dict[str, Any], filename: str) -> bytes:
    content_b64 = payload.get('content_base64')
    if isinstance(content_b64, str) and content_b64.strip():
        try:
            return base64.b64decode(content_b64.strip(), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ResumeFileError('Invalid base64 content in content_base64.') from exc

    raw_text = payload.get('text')
    if isinstance(raw_text, str) and raw_text.strip():
        ext = Path(filename).suffix.lower()
        if ext not in ('.txt', '.md'):
            raise ResumeFileError('Plain text uploads require a .txt or .md filename, or provide content_base64.')
        return raw_text.encode('utf-8')

    raise ResumeFileError('Provide content_base64 (or text for .txt/.md files).')


def _handle_resume_upload(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}

    filename = str(payload.get('filename', '')).strip()
    if not filename:
        return 400, {'error': 'filename is required.'}

    save_to_profile = bool(payload.get('save_to_profile', True))
    try:
        file_bytes = _decode_upload_bytes(payload, filename)
        bundle = LocalResumeFileAdapter().extract_bundle(file_bytes, filename)
    except ResumeFileError as exc:
        return 400, {'error': str(exc)}

    extracted_text = bundle['extracted_text']
    if len(extracted_text) < MIN_RESUME_CHARS:
        return 400, {'error': f'Extracted resume must contain at least {MIN_RESUME_CHARS} characters.'}

    resume_sha256 = hashlib.sha256(extracted_text.encode('utf-8')).hexdigest()

    if save_to_profile:
        with db.connection() as con:
            cur = con.execute('UPDATE profile SET resume=? WHERE id=1', (extracted_text,))
            if cur.rowcount == 0:
                con.execute('INSERT INTO profile(id, resume) VALUES(1, ?)', (extracted_text,))
        db.log_audit(
            'candidate',
            'resume_uploaded',
            'profile',
            '1',
            {
                'filename': bundle['filename'],
                'file_type': bundle['file_type'],
                'char_count': len(extracted_text),
                'resume_sha256': resume_sha256,
            },
        )

    return 200, {
        'ok': True,
        'filename': bundle['filename'],
        'file_type': bundle['file_type'],
        'saved_to_profile': save_to_profile,
        'char_count': len(extracted_text),
        'resume_sha256': resume_sha256,
        'extracted_text': extracted_text,
        'ats_preview_text': bundle['ats_preview_text'],
        'ats_diagnostics': bundle['ats_diagnostics'],
    }


def _deserialize_job_row(job_row: Any) -> dict[str, Any]:
    out = dict(job_row)
    raw_pf = out.get('preflight_json') or ''
    if isinstance(raw_pf, str) and raw_pf.strip():
        try:
            out['preflight'] = json.loads(raw_pf)
        except ValueError:
            out['preflight'] = None
    else:
        out['preflight'] = None
    return out


def _upsert_job_record(job: dict[str, Any], default_origin: str) -> tuple[dict[str, Any], bool]:
    """Insert or return existing deduplicated job row with strict D1 preflight storage."""
    title = str(job.get('title') or '').strip()[:200]
    company = str(job.get('company') or '').strip()[:120]
    description = str(job.get('description') or '').strip()[:12000]
    url = str(job.get('url') or '').strip()
    origin = str(job.get('origin') or default_origin or 'discovered').strip()
    location = str(job.get('location') or '').strip()[:120]
    salary_text = str(job.get('salary_text') or '').strip()[:80]
    posted_at = str(job.get('posted_at') or '').strip()[:40]

    evaluated = engine.evaluate_preflight({**job, 'title': title, 'description': description, 'url': url})
    ats_family = str(job.get('ats_family') or evaluated['ats_family'])
    if ats_family not in engine.VALID_ATS_FAMILIES:
        ats_family = evaluated['ats_family']
    preflight_dict = engine.preflight_storage_dict(
        job.get('preflight') if isinstance(job.get('preflight'), dict) else evaluated
    )
    preflight_json = json.dumps(preflight_dict, ensure_ascii=False)

    norm_url = normalize_job_url(url)
    norm_title = title.lower()
    norm_company = company.lower()

    existing_rows = db.rows('SELECT * FROM jobs ORDER BY id DESC')
    for existing in existing_rows:
        ex_url = normalize_job_url(existing['url'] or '')
        if norm_url and ex_url and norm_url == ex_url:
            return _deserialize_job_row(existing), False
        if (
            norm_company
            and norm_title
            and (existing['company'] or '').strip().lower() == norm_company
            and (existing['title'] or '').strip().lower() == norm_title
        ):
            return _deserialize_job_row(existing), False

    with db.connection() as con:
        cur = con.execute(
            'INSERT INTO jobs(title, company, description, url, origin, location, salary_text, posted_at, ats_family, preflight_json) '
            'VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (title, company, description, url, origin, location, salary_text, posted_at, ats_family, preflight_json),
        )
        new_id = cur.lastrowid
    inserted_row = db.row('SELECT * FROM jobs WHERE id=?', (new_id,))
    return _deserialize_job_row(inserted_row), True


def _get_discovery_adapter() -> LiveJobDiscoveryAdapter:
    return LiveJobDiscoveryAdapter()


def _handle_jobs_discover(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}

    query = str(payload.get('query') or '').strip()
    location = str(payload.get('location') or '').strip()
    boards = payload.get('boards')
    has_boards = bool(boards) if isinstance(boards, (list, tuple)) else bool(str(boards or '').strip())
    if not query and not has_boards:
        return 400, {'error': 'Provide a query or at least one public ATS board (e.g. greenhouse:stripe).'}

    save = bool(payload.get('save', True))
    adapter = _get_discovery_adapter()
    filters = {
        'query': query,
        'location': location,
        'boards': boards,
        'limit': payload.get('limit', 15),
        'include_serper': payload.get('include_serper', True),
        'hydrate_urls': payload.get('hydrate_urls', True),
    }
    try:
        discovered = adapter.search(filters)
    except JobDiscoveryError as exc:
        return 400, {'error': str(exc)}

    results: list[dict[str, Any]] = []
    inserted_count = 0
    duplicate_count = 0
    for item in discovered:
        if save and item.get('title') and (item.get('description') or item.get('url')):
            stored, was_inserted = _upsert_job_record(item, default_origin='discovered')
            stored['inserted'] = was_inserted
            stored['extraction_status'] = item.get('extraction_status', '')
            stored['source_provider'] = item.get('source_provider', '')
            results.append(stored)
            if was_inserted:
                inserted_count += 1
            else:
                duplicate_count += 1
        else:
            results.append(item)

    db.log_audit(
        'pipeline',
        'jobs_discovered',
        'job',
        '',
        {
            'sources': adapter.last_metadata.get('sources_queried', []),
            'discovered_count': len(discovered),
            'inserted_count': inserted_count,
            'duplicate_count': duplicate_count,
            'saved': save,
        },
    )
    return 200, {
        'ok': True,
        'saved': save,
        'discovered_count': len(discovered),
        'inserted_count': inserted_count,
        'duplicate_count': duplicate_count,
        'jobs': results,
        'metadata': adapter.last_metadata,
    }


def _handle_job_import_url(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}

    url = str(payload.get('url') or '').strip()
    if not url:
        return 400, {'error': 'url is required.'}
    try:
        engine.valid_public_url(url)
    except ValueError as exc:
        return 400, {'error': str(exc)}

    save = bool(payload.get('save', True))
    if payload.get('manual_paste'):
        title = str(payload.get('title') or '').strip()
        company = str(payload.get('company') or '').strip()
        description = str(payload.get('description') or '').strip()
        if not title or len(description) < 40:
            return 400, {'error': 'Manual paste fallback requires a title and at least 40 characters of description.'}
        manual_job = {
            'title': title,
            'company': company,
            'description': description,
            'location': str(payload.get('location') or '').strip(),
            'salary_text': str(payload.get('salary_text') or '').strip(),
            'posted_at': str(payload.get('posted_at') or '').strip(),
            'url': url,
            'ats_family': engine.detect_ats_family(url),
            'origin': 'manual_fallback_paste',
        }
        stored, was_inserted = _upsert_job_record(manual_job, default_origin='manual_fallback_paste')
        db.log_audit(
            'candidate',
            'job_imported_manual_paste',
            'job',
            str(stored.get('id') or ''),
            {'ats_family': stored.get('ats_family', 'unknown'), 'inserted': was_inserted},
        )
        return 200, {
            'ok': True,
            'saved': True,
            'inserted': was_inserted,
            'manual_fallback': False,
            'extraction': 'manual-paste',
            'extraction_status': 'verified_manual_paste',
            'job': stored,
        }

    inspected = engine.inspect_public_job_url(url)
    if inspected.get('extraction_status') == 'manual_fallback':
        db.log_audit(
            'candidate',
            'job_url_manual_fallback',
            'job',
            '',
            {'ats_family': inspected.get('ats_family', 'unknown'), 'url': url},
        )
        return 200, {
            'ok': False,
            'saved': False,
            'manual_fallback': True,
            'ats_family': inspected.get('ats_family', 'unknown'),
            'url': url,
            'reason': inspected.get('reason') or 'Paste the job description manually.',
        }

    preflight = engine.evaluate_preflight(inspected)
    job_payload = {
        **inspected,
        'origin': 'imported_url',
        'preflight': engine.preflight_storage_dict(preflight),
    }

    if save:
        stored, was_inserted = _upsert_job_record(job_payload, default_origin='imported_url')
        db.log_audit(
            'candidate',
            'job_imported_url',
            'job',
            str(stored.get('id') or ''),
            {
                'ats_family': stored.get('ats_family', 'unknown'),
                'extraction': inspected.get('extraction', ''),
                'inserted': was_inserted,
            },
        )
        return 200, {
            'ok': True,
            'saved': True,
            'inserted': was_inserted,
            'manual_fallback': False,
            'extraction': inspected.get('extraction', ''),
            'extraction_status': inspected.get('extraction_status', 'verified'),
            'job': stored,
        }

    return 200, {
        'ok': True,
        'saved': False,
        'manual_fallback': False,
        'extraction': inspected.get('extraction', ''),
        'extraction_status': inspected.get('extraction_status', 'verified'),
        'job': job_payload,
    }


def _evaluate_and_persist_job_preflight(job_row: Any) -> dict[str, Any]:
    job_dict = dict(job_row)
    evaluated = engine.evaluate_preflight(job_dict)
    ats_family = evaluated['ats_family']
    preflight_dict = engine.preflight_storage_dict(evaluated)
    preflight_json = json.dumps(preflight_dict, ensure_ascii=False)
    with db.connection() as con:
        con.execute(
            'UPDATE jobs SET ats_family=?, preflight_json=? WHERE id=?',
            (ats_family, preflight_json, job_row['id']),
        )
    updated = db.row('SELECT * FROM jobs WHERE id=?', (job_row['id'],))
    return _deserialize_job_row(updated)


def _handle_job_preflight(job_id: int) -> tuple[int, dict[str, Any]]:
    job_row = db.row('SELECT * FROM jobs WHERE id=?', (job_id,))
    if not job_row:
        return 404, {'error': f'Job {job_id} not found.'}
    updated = _evaluate_and_persist_job_preflight(job_row)
    db.log_audit(
        'pipeline',
        'job_preflight_evaluated',
        'job',
        str(job_id),
        {'ats_family': updated.get('ats_family', 'unknown'), 'liveness': (updated.get('preflight') or {}).get('liveness_status')},
    )
    return 200, {
        'ok': True,
        'job_id': job_id,
        'ats_family': updated['ats_family'],
        'preflight': updated['preflight'],
        'job': updated,
    }


def _handle_preflight_all() -> tuple[int, dict[str, Any]]:
    all_rows = db.rows('SELECT * FROM jobs ORDER BY id DESC')
    updated = [_evaluate_and_persist_job_preflight(r) for r in all_rows]
    db.log_audit('pipeline', 'jobs_preflight_all', 'job', '', {'evaluated_count': len(updated)})
    return 200, {
        'ok': True,
        'evaluated_count': len(updated),
        'jobs': updated,
    }


def _safe_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
    return {}


def _safe_json_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except ValueError:
            pass
    return []


def _deserialize_application_row(app_row: Any) -> dict[str, Any]:
    out = dict(app_row)
    answers_store = _safe_json_dict(out.get('answers_json'))
    callback_store = _safe_json_dict(out.get('callback_packet_json'))
    out['answers_data'] = answers_store
    out['copilot_packet'] = answers_store.get('copilot_packet')
    out['callback_packet'] = callback_store
    out['claim_evidence_map'] = _safe_json_list(out.get('claim_map_json'))
    out['slop_warnings'] = _safe_json_list(out.get('slop_warnings_json'))
    return out


def _get_application_adapter() -> CoPilotApplicationAdapter:
    return CoPilotApplicationAdapter()


def _get_gap_bridge_adapter() -> GapBridgeAdapter:
    return GapBridgeAdapter()


def _get_callback_builder() -> CallbackCheatSheetBuilder:
    return CallbackCheatSheetBuilder()


def _strip_sensitive_answers(answers: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in answers.items() if k not in SENSITIVE_FIELDS}


def _load_verified_gap_proofs(job_id: int) -> list[dict[str, Any]]:
    rows = db.rows(
        "SELECT id, job_id, skill_name, gap_type, micro_project_brief, proof_url, verified, created_at "
        "FROM gap_artifacts WHERE job_id=? AND verified=1 AND (gap_type IS NULL OR gap_type != 'wording_gap') "
        "ORDER BY id ASC",
        (job_id,),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        skill = str(item.get('skill_name') or '').strip()
        if not skill:
            continue
        out.append({
            'id': item.get('id'),
            'skill_name': skill,
            'gap_type': item.get('gap_type') or 'true_skill_gap',
            'micro_project_brief': str(item.get('micro_project_brief') or '').strip(),
            'proof_url': str(item.get('proof_url') or '').strip() or None,
            'verified': True,
        })
    return out


def _build_and_save_copilot_packet(app_row: Any, job_row: Any, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    existing_store = _safe_json_dict(app_row['answers_json'])
    if app_row['status'] == 'confirmed' and existing_store.get('copilot_packet'):
        # Confirmed application packets stay immutable to preserve tamper-evident receipt integrity.
        return 200, {
            'ok': True,
            'immutable': True,
            'application': _deserialize_application_row(app_row),
            'copilot_packet': existing_store['copilot_packet'],
        }

    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    profile_resume = (profile_row or {}).get('resume') or ''
    approved_resume = str(
        payload.get('approved_resume')
        or app_row['tailored_resume']
        or profile_resume
    ).strip()

    existing_candidate = _safe_json_dict(existing_store.get('candidate_answers'))
    new_candidate = _safe_json_dict(payload.get('candidate_answers'))
    merged_candidate = {**existing_candidate, **{k: str(v) for k, v in new_candidate.items()}}

    existing_sensitive = _safe_json_dict(existing_store.get('sensitive_answers'))
    new_sensitive = _safe_json_dict(payload.get('sensitive_answers'))
    merged_sensitive = {**existing_sensitive}
    for key in SENSITIVE_FIELDS:
        if key in new_sensitive:
            merged_sensitive[key] = str(new_sensitive[key])

    try:
        packet = _get_application_adapter().prepare(
            dict(job_row),
            {
                'resume': profile_resume,
                'candidate_answers': merged_candidate,
                'sensitive_answers': merged_sensitive,
            },
            approved_resume,
        )
    except ApplicationError as exc:
        return 400, {'error': str(exc)}

    packet_dict = {
        'job_id': packet.job_id,
        'ats_family': packet.ats_family,
        'ordered_sections': packet.ordered_sections,
        'sensitive_fields_locked': packet.sensitive_fields_locked,
        'callback_packet': packet.callback_packet,
    }
    resume_sha256 = compute_sha256_text(approved_resume)
    updated_store = {
        **existing_store,
        'copilot_packet': packet_dict,
        'candidate_answers': merged_candidate,
        'sensitive_answers': merged_sensitive,
        'sensitive_fields_confirmed': bool(existing_store.get('sensitive_fields_confirmed', False)),
        'approved': bool(existing_store.get('approved', False)),
    }

    verified_proofs = _load_verified_gap_proofs(int(job_row['id']))
    existing_cb = _safe_json_dict(app_row['callback_packet_json'])
    merged_cb = _get_callback_builder().build(
        dict(job_row),
        profile_resume,
        approved_resume,
        existing_cb={**packet.callback_packet, **existing_cb},
        candidate_answers=_strip_sensitive_answers(merged_candidate),
        verified_gap_proofs=verified_proofs,
        resume_sha256=resume_sha256,
        mode='heuristic',
    )

    new_tailored = approved_resume if payload.get('approved_resume') else app_row['tailored_resume']
    with db.connection() as con:
        con.execute(
            'UPDATE applications SET tailored_resume=?, answers_json=?, callback_packet_json=?, resume_sha256=? WHERE id=?',
            (
                new_tailored,
                json.dumps(updated_store, ensure_ascii=False),
                json.dumps(merged_cb, ensure_ascii=False),
                resume_sha256,
                app_row['id'],
            ),
        )

    refreshed = db.row(
        'SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
        (app_row['id'],),
    )
    db.log_audit(
        'candidate',
        'copilot_packet_prepared',
        'application',
        str(app_row['id']),
        {'job_id': job_row['id'], 'ats_family': packet.ats_family, 'resume_sha256': resume_sha256},
    )
    return 200, {
        'ok': True,
        'immutable': False,
        'application': _deserialize_application_row(refreshed),
        'copilot_packet': packet_dict,
    }


def _handle_application_copilot(app_id: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    app_row = db.row('SELECT * FROM applications WHERE id=?', (app_id,))
    if not app_row:
        return 404, {'error': f'Application {app_id} not found.'}
    job_row = db.row('SELECT * FROM jobs WHERE id=?', (app_row['job_id'],))
    if not job_row:
        return 404, {'error': f'Job {app_row["job_id"]} not found.'}
    return _build_and_save_copilot_packet(app_row, job_row, payload)


def _handle_job_copilot(job_id: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    job_row = db.row('SELECT * FROM jobs WHERE id=?', (job_id,))
    if not job_row:
        return 404, {'error': f'Job {job_id} not found.'}

    app_row = db.row('SELECT * FROM applications WHERE job_id=?', (job_id,))
    if not app_row:
        profile_row = db.row('SELECT resume FROM profile WHERE id=1')
        profile_resume = (profile_row or {}).get('resume') or ''
        if len(profile_resume.strip()) < MIN_RESUME_CHARS:
            return 400, {'error': f'Save or upload a resume ({MIN_RESUME_CHARS}+ chars) before building a Co-Pilot packet.'}
        fit = engine.match_resume(profile_resume, job_row['description'])
        tailored = engine.draft_resume(profile_resume, job_row)
        with db.connection() as con:
            con.execute(
                "INSERT INTO applications(job_id, tailored_resume, fit_score, status) VALUES(?,?,?,'draft') "
                "ON CONFLICT(job_id) DO NOTHING",
                (job_id, tailored, fit['score']),
            )
        app_row = db.row('SELECT * FROM applications WHERE job_id=?', (job_id,))
    return _build_and_save_copilot_packet(app_row, job_row, payload)


def _find_duplicate_confirmed_application(app_id: int, job_row: Any) -> Any:
    norm_url = normalize_job_url(job_row['url'] or '')
    confirmed_rows = db.rows(
        "SELECT a.id, a.job_id, a.confirmation, j.url FROM applications a JOIN jobs j ON j.id=a.job_id "
        "WHERE a.status='confirmed' AND a.confirmation!=''"
    )
    for row_item in confirmed_rows:
        if row_item['id'] == app_id or row_item['job_id'] == job_row['id']:
            return row_item
        if norm_url and normalize_job_url(row_item['url'] or '') == norm_url:
            return row_item
    return None


def _handle_application_confirm(app_id: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    app_row = db.row('SELECT * FROM applications WHERE id=?', (app_id,))
    if not app_row:
        return 404, {'error': f'Application {app_id} not found.'}
    job_row = db.row('SELECT * FROM jobs WHERE id=?', (app_row['job_id'],))
    if not job_row:
        return 404, {'error': f'Job {app_row["job_id"]} not found.'}

    if app_row['status'] == 'test_submitted':
        return 400, {
            'error': 'Test-submitted demo applications stay separate from real applications and cannot be converted to confirmed.'
        }

    existing_store = _safe_json_dict(app_row['answers_json'])
    merged_candidate = {
        **_safe_json_dict(existing_store.get('candidate_answers')),
        **{k: str(v) for k, v in _safe_json_dict(payload.get('candidate_answers')).items()},
    }
    merged_sensitive = dict(_safe_json_dict(existing_store.get('sensitive_answers')))
    incoming_sensitive = _safe_json_dict(payload.get('sensitive_answers'))
    for key in SENSITIVE_FIELDS:
        if key in incoming_sensitive:
            merged_sensitive[key] = str(incoming_sensitive[key])

    approved_resume = str(payload.get('approved_resume') or app_row['tailored_resume'] or '').strip()
    explicit_approval = bool(payload.get('explicit_user_approval', False))
    sensitive_confirmed = bool(payload.get('sensitive_fields_confirmed', False))
    outcome = str(payload.get('outcome') or 'confirmed').strip().lower()
    confirmation_reference = str(payload.get('confirmation_reference') or '').strip()
    evidence_note = str(payload.get('evidence_note') or '').strip()
    evidence_path = str(payload.get('evidence_path') or '').strip()

    if outcome == 'confirmed':
        duplicate = _find_duplicate_confirmed_application(app_id, job_row)
        if duplicate is not None:
            return 409, {
                'error': f'Duplicate submission blocked: application #{duplicate["id"]} is already confirmed ({duplicate["confirmation"]}).'
            }

    prepared_payload = {
        'job': dict(job_row),
        'approved_resume': approved_resume,
        'candidate_answers': merged_candidate,
        'sensitive_answers': merged_sensitive,
        'sensitive_fields_confirmed': sensitive_confirmed,
        'outcome': outcome,
        'confirmation_reference': confirmation_reference,
        'evidence_note': evidence_note,
        'evidence_path': evidence_path,
    }
    try:
        result = _get_application_adapter().submit(prepared_payload, explicit_user_approval=explicit_approval)
    except PermissionError as exc:
        return 403, {'error': str(exc)}
    except DuplicateApplicationError as exc:
        return 409, {'error': str(exc)}
    except ApplicationError as exc:
        return 400, {'error': str(exc)}

    now_iso = datetime.now(timezone.utc).isoformat()
    stored_confirmation = result.confirmation_id or ''
    updated_store = {
        **existing_store,
        'candidate_answers': merged_candidate,
        'sensitive_answers': merged_sensitive,
        'sensitive_fields_confirmed': True,
        'approved': True,
        'approved_at': existing_store.get('approved_at') or now_iso,
        'confirmation_reference': stored_confirmation or None,
        'evidence_path': result.evidence_path,
        'outcome': result.status,
    }
    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    profile_resume = (profile_row or {}).get('resume') or ''
    verified_proofs = _load_verified_gap_proofs(int(job_row['id']))
    callback_store = _get_callback_builder().build(
        dict(job_row),
        profile_resume,
        approved_resume,
        existing_cb=_safe_json_dict(app_row['callback_packet_json']),
        candidate_answers={**_strip_sensitive_answers(merged_candidate), 'sensitive_fields_confirmed': True},
        verified_gap_proofs=verified_proofs,
        resume_sha256=result.resume_sha256 or '',
        answers_sha256=result.answers_sha256 or '',
        confirmation_reference=stored_confirmation,
        submitted_at=now_iso,
        mode='heuristic',
    )

    with db.connection() as con:
        con.execute(
            'UPDATE applications SET tailored_resume=?, status=?, confirmation=?, answers_json=?, '
            'callback_packet_json=?, resume_sha256=?, answers_sha256=?, evidence_note=?, submitted_at=? WHERE id=?',
            (
                approved_resume,
                result.status,
                stored_confirmation,
                json.dumps(updated_store, ensure_ascii=False),
                json.dumps(callback_store, ensure_ascii=False),
                result.resume_sha256 or '',
                result.answers_sha256 or '',
                evidence_note or result.details,
                now_iso,
                app_id,
            ),
        )

    db.log_audit(
        'candidate',
        f'application_{result.status}',
        'application',
        str(app_id),
        {
            'job_id': job_row['id'],
            'ats_family': job_row['ats_family'] or engine.detect_ats_family(job_row['url'] or ''),
            'status': result.status,
            'confirmation_reference': stored_confirmation,
            'resume_sha256': result.resume_sha256,
            'answers_sha256': result.answers_sha256,
            'sensitive_fields_confirmed': True,
        },
    )

    refreshed = db.row(
        'SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
        (app_id,),
    )
    return 200, {
        'ok': True,
        'real_submitted_counted': bool(result.status == 'confirmed' and stored_confirmation),
        'receipt': {
            'status': result.status,
            'confirmation_reference': stored_confirmation or None,
            'resume_sha256': result.resume_sha256,
            'answers_sha256': result.answers_sha256,
            'evidence_path': result.evidence_path,
            'submitted_at': now_iso,
            'details': result.details,
        },
        'application': _deserialize_application_row(refreshed),
    }


def handle_post(path: str, payload: dict):
    """Return (status_code, payload) if path belongs to Owner A, else None."""
    if path == '/api/pipeline/resume/upload':
        return _handle_resume_upload(payload)
    if path == '/api/pipeline/jobs/discover':
        return _handle_jobs_discover(payload)
    if path == '/api/pipeline/jobs/import-url':
        return _handle_job_import_url(payload)
    if path == '/api/pipeline/jobs/preflight-all':
        return _handle_preflight_all()
    preflight_match = _JOB_PREFLIGHT_RE.match(path)
    if preflight_match:
        return _handle_job_preflight(int(preflight_match.group(1)))
    if path == '/api/pipeline/prepare-ai':
        return _handle_prepare_ai(payload)
    if path == '/api/pipeline/tailor/lint':
        return _handle_tailor_lint(payload)
    if path == '/api/pipeline/gaps/analyze':
        return _handle_gap_analyze(payload)
    gap_verify_match = _GAP_VERIFY_RE.match(path)
    if gap_verify_match:
        return _handle_gap_verify(int(gap_verify_match.group(1)), payload)
    app_cb_match = _APP_CALLBACK_RE.match(path)
    if app_cb_match:
        return _handle_post_callback_packet(int(app_cb_match.group(1)), payload)
    export_docx_match = _APP_EXPORT_DOCX_RE.match(path)
    if export_docx_match:
        return _handle_export_docx(int(export_docx_match.group(1)), payload)
    app_copilot_match = _APP_COPILOT_RE.match(path)
    if app_copilot_match:
        return _handle_application_copilot(int(app_copilot_match.group(1)), payload)
    job_copilot_match = _JOB_COPILOT_RE.match(path)
    if job_copilot_match:
        return _handle_job_copilot(int(job_copilot_match.group(1)), payload)
    confirm_match = _APP_CONFIRM_RE.match(path)
    if confirm_match:
        return _handle_application_confirm(int(confirm_match.group(1)), payload)
    if path.startswith('/api/pipeline/'):
        return 501, {
            'error': 'Owner A endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_A_WORKBOOK.md',
        }
    return None


def _resolve_tailor_target_application(job_id: int, application_id: Any) -> tuple[Optional[dict[str, Any]], Optional[tuple[int, dict[str, Any]]]]:
    if application_id is not None:
        try:
            parsed_app_id = int(application_id)
        except (TypeError, ValueError):
            return None, (400, {'error': 'application_id must be an integer.'})
        row = db.row('SELECT * FROM applications WHERE id=?', (parsed_app_id,))
        if not row:
            return None, (404, {'error': f'Application {parsed_app_id} not found.'})
        if int(row['job_id']) != job_id:
            return None, (400, {'error': 'application_id does not belong to job_id.'})
        if row['status'] == 'confirmed':
            return None, (409, {'error': 'Confirmed application is immutable and cannot be re-tailored.'})
        if row['status'] == 'test_submitted':
            return None, (409, {'error': 'Demo test_submitted application is isolated; prepare a new draft instead.'})
        return dict(row), None

    non_demo_rows = db.rows(
        "SELECT * FROM applications WHERE job_id=? AND status != 'test_submitted' ORDER BY id DESC",
        (job_id,),
    )
    if not non_demo_rows:
        return None, None
    latest = dict(non_demo_rows[0])
    if latest['status'] == 'confirmed':
        return None, (409, {'error': 'Latest application for this job is confirmed and immutable.'})
    return latest, None


def _handle_prepare_ai(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    raw_job_id = payload.get('job_id')
    if raw_job_id is None:
        return 400, {'error': 'job_id is required.'}
    try:
        job_id = int(raw_job_id)
    except (TypeError, ValueError):
        return 400, {'error': 'job_id must be an integer.'}

    job_row = db.row('SELECT * FROM jobs WHERE id=?', (job_id,))
    if not job_row:
        return 404, {'error': f'Job {job_id} not found.'}

    existing_app, conflict_err = _resolve_tailor_target_application(job_id, payload.get('application_id'))
    if conflict_err is not None:
        return conflict_err

    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    profile_resume = (profile_row or {}).get('resume') or ''
    base_resume = str(payload.get('base_resume') or profile_resume).strip()
    if len(base_resume) < MIN_RESUME_CHARS:
        return 400, {'error': f'Candidate resume must contain at least {MIN_RESUME_CHARS} characters before tailoring.'}

    verified_proofs = _load_verified_gap_proofs(job_id)
    verified_gap_skills = [p['skill_name'] for p in verified_proofs]
    candidate_confirmations = _safe_json_dict(payload.get('candidate_confirmations'))
    mode = str(payload.get('mode') or 'auto').strip().lower()

    ats_before = compute_job_fit_snapshot(base_resume, dict(job_row))
    try:
        tailored = VoicePreservingTailorAdapter().tailor(
            base_resume,
            dict(job_row),
            verified_gap_skills=verified_gap_skills,
            candidate_confirmations=candidate_confirmations or None,
            mode=mode,
            ats_match=ats_before,
        )
    except (TailorError, ModelNotConfiguredError) as exc:
        return 400, {'error': str(exc)}
    except ModelAdapterError as exc:
        return 502, {'error': str(exc)}

    tailored_text = tailored['tailored_text']
    ats_after = compute_job_fit_snapshot(tailored_text, dict(job_row))
    claim_map_json = json.dumps(tailored['claim_evidence_map'], ensure_ascii=False)
    slop_json = json.dumps(tailored['slop_warnings'], ensure_ascii=False)

    existing_cb = _safe_json_dict((existing_app or {}).get('callback_packet_json'))
    existing_answers_store = _safe_json_dict((existing_app or {}).get('answers_json'))
    existing_candidate_answers = _strip_sensitive_answers(_safe_json_dict(existing_answers_store.get('candidate_answers')))
    seed_cb = {
        **existing_cb,
        'why_this_role': tailored['why_this_role'] or existing_cb.get('why_this_role', ''),
        'probe_questions': [],
        'tailor_changes': tailored['changes'][:12],
        'tailor_summary': {
            'generation_mode': tailored['generation_mode'],
            'provider': tailored['provider'],
            'model': tailored['model'],
            'fit_score_before': ats_before['fit_score'],
            'fit_score_after': ats_after['fit_score'],
            'matched_keywords': ats_after['matched'],
            'missing_keywords': ats_after['missing'],
            'changes_count': len(tailored['changes']),
            'slop_score': tailored['slop_score'],
            'unverified_count': len(tailored['unverified_claims']),
            'verified_gap_skills': verified_gap_skills,
        },
    }
    updated_cb = _get_callback_builder().build(
        dict(job_row),
        base_resume,
        tailored_text,
        existing_cb=seed_cb,
        candidate_answers=existing_candidate_answers,
        verified_gap_proofs=verified_proofs,
        changes=tailored['changes'][:12],
        resume_sha256=tailored['resume_sha256'],
        generation_mode=tailored['generation_mode'],
        mode='heuristic',
    )
    cb_json = json.dumps(updated_cb, ensure_ascii=False)

    with db.connection() as con:
        if existing_app:
            app_id = int(existing_app['id'])
            con.execute(
                '''UPDATE applications
                   SET tailored_resume=?, fit_score=?, claim_map_json=?, slop_warnings_json=?,
                       ats_preview_text=?, callback_packet_json=?, resume_sha256=?
                   WHERE id=?''',
                (
                    tailored_text,
                    ats_after['fit_score'],
                    claim_map_json,
                    slop_json,
                    tailored['ats_preview_text'],
                    cb_json,
                    tailored['resume_sha256'],
                    app_id,
                ),
            )
        else:
            app_id = con.execute(
                '''INSERT INTO applications(
                       job_id, tailored_resume, fit_score, status, confirmation,
                       claim_map_json, slop_warnings_json, ats_preview_text, callback_packet_json, resume_sha256
                   ) VALUES(?,?,?,'draft','',?,?,?,?,?)''',
                (
                    job_id,
                    tailored_text,
                    ats_after['fit_score'],
                    claim_map_json,
                    slop_json,
                    tailored['ats_preview_text'],
                    cb_json,
                    tailored['resume_sha256'],
                ),
            ).lastrowid

    refreshed = db.row(
        'SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
        (app_id,),
    )
    db.log_audit(
        'candidate',
        'resume_tailored',
        'application',
        str(app_id),
        {
            'job_id': job_id,
            'generation_mode': tailored['generation_mode'],
            'provider': tailored['provider'],
            'model': tailored['model'],
            'fit_score_before': ats_before['fit_score'],
            'fit_score_after': ats_after['fit_score'],
            'claim_count': len(tailored['claim_evidence_map']),
            'slop_warning_count': len(tailored['slop_warnings']),
            'unverified_count': len(tailored['unverified_claims']),
            'resume_sha256': tailored['resume_sha256'],
        },
    )
    return 200, {
        'ok': True,
        'application': _deserialize_application_row(refreshed),
        'tailored_text': tailored_text,
        'claim_evidence_map': tailored['claim_evidence_map'],
        'slop_warnings': tailored['slop_warnings'],
        'flagged_terms': tailored['flagged_terms'],
        'slop_score': tailored['slop_score'],
        'unverified_claims': tailored['unverified_claims'],
        'questions_for_candidate': tailored['questions_for_candidate'],
        'ats_preview_text': tailored['ats_preview_text'],
        'ats_diagnostics': tailored['ats_diagnostics'],
        'changes': tailored['changes'],
        'why_this_role': tailored['why_this_role'],
        'generation_mode': tailored['generation_mode'],
        'provider': tailored['provider'],
        'model': tailored['model'],
        'resume_sha256': tailored['resume_sha256'],
        'fit_before': ats_before,
        'fit_after': ats_after,
        'verified_gap_skills': verified_gap_skills,
    }


def _handle_tailor_lint(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    text = str(payload.get('text') or payload.get('tailored_text') or '').strip()
    if not text:
        return 400, {'error': 'text is required.'}

    try:
        docx_bytes = build_minimal_docx_bytes(text)
        ats_preview_text = LocalResumeFileAdapter().extract_plain_preview(docx_bytes, 'draft_resume.docx')
    except (TailorError, ResumeFileError) as exc:
        return 400, {'error': str(exc)}

    lint = engine.lint_ai_slop(text)
    ats_diagnostics = analyze_ats_preview(ats_preview_text)
    resume_sha256 = compute_sha256_text(text)

    fit_match = None
    job_id = payload.get('job_id')
    if job_id is not None:
        try:
            parsed_job_id = int(job_id)
        except (TypeError, ValueError):
            return 400, {'error': 'job_id must be an integer.'}
        job_row = db.row('SELECT * FROM jobs WHERE id=?', (parsed_job_id,))
        if not job_row:
            return 404, {'error': f'Job {parsed_job_id} not found.'}
        fit_match = compute_job_fit_snapshot(text, dict(job_row))

    grounding = None
    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    base_resume = str(payload.get('base_resume') or ((profile_row or {}).get('resume')) or '').strip()
    if base_resume:
        raw_claims = payload.get('claim_evidence_map')
        if raw_claims is not None:
            grounding = engine.verify_tailor_grounding(base_resume, text, raw_claims)

    saved_app = None
    raw_app_id = payload.get('application_id')
    if raw_app_id is not None and bool(payload.get('save', False)):
        try:
            app_id = int(raw_app_id)
        except (TypeError, ValueError):
            return 400, {'error': 'application_id must be an integer.'}
        app_row = db.row('SELECT * FROM applications WHERE id=?', (app_id,))
        if not app_row:
            return 404, {'error': f'Application {app_id} not found.'}
        if app_row['status'] == 'confirmed':
            return 409, {'error': 'Confirmed application is immutable and cannot be modified.'}
        if app_row['status'] == 'test_submitted':
            return 409, {'error': 'Demo test_submitted application is isolated and cannot be modified.'}
        new_fit = fit_match['fit_score'] if fit_match else app_row['fit_score']
        with db.connection() as con:
            con.execute(
                '''UPDATE applications
                   SET tailored_resume=?, fit_score=?, slop_warnings_json=?, ats_preview_text=?, resume_sha256=?
                   WHERE id=?''',
                (
                    text,
                    new_fit,
                    json.dumps(lint['slop_warnings'], ensure_ascii=False),
                    ats_preview_text,
                    resume_sha256,
                    app_id,
                ),
            )
        refreshed = db.row(
            'SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
            (app_id,),
        )
        saved_app = _deserialize_application_row(refreshed)

    return 200, {
        'ok': True,
        'slop_warnings': lint['slop_warnings'],
        'flagged_terms': lint['flagged_terms'],
        'slop_score': lint['slop_score'],
        'clean': lint['clean'],
        'ats_preview_text': ats_preview_text,
        'ats_diagnostics': ats_diagnostics,
        'resume_sha256': resume_sha256,
        'fit_match': fit_match,
        'grounding': grounding,
        'application': saved_app,
    }


def _handle_export_docx(app_id: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    app_row = db.row(
        'SELECT a.*, j.title, j.company FROM applications a LEFT JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
        (app_id,),
    )
    if not app_row:
        return 404, {'error': f'Application {app_id} not found.'}

    custom_text = str(payload.get('text') or '').strip()
    stored_text = str(app_row['tailored_resume'] or '').strip()
    if custom_text and app_row['status'] == 'confirmed' and custom_text != stored_text:
        return 409, {'error': 'Confirmed application is immutable; cannot export altered text under this receipt.'}

    resume_text = custom_text or stored_text
    if not resume_text:
        return 400, {'error': 'Application has no tailored resume text to export.'}

    try:
        docx_bytes = build_minimal_docx_bytes(resume_text)
        ats_preview_text = LocalResumeFileAdapter().extract_plain_preview(docx_bytes, 'export.docx')
    except (TailorError, ResumeFileError) as exc:
        return 400, {'error': str(exc)}

    company = str(app_row['company'] or 'company').strip()
    title = str(app_row['title'] or 'resume').strip()
    slug = re.sub(r'[^a-z0-9]+', '_', f'{company}_{title}_tailored'.lower()).strip('_') or f'application_{app_id}'
    filename = f'{slug}.docx'
    docx_sha256 = hashlib.sha256(docx_bytes).hexdigest()
    resume_sha256 = compute_sha256_text(resume_text)

    db.log_audit(
        'candidate',
        'docx_exported',
        'application',
        str(app_id),
        {
            'filename': filename,
            'byte_length': len(docx_bytes),
            'docx_sha256': docx_sha256,
            'resume_sha256': resume_sha256,
        },
    )
    return 200, {
        'ok': True,
        'application_id': app_id,
        'filename': filename,
        'mime_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'content_base64': base64.b64encode(docx_bytes).decode('ascii'),
        'byte_length': len(docx_bytes),
        'docx_sha256': docx_sha256,
        'resume_sha256': resume_sha256,
        'ats_preview_text': ats_preview_text,
        'ats_diagnostics': analyze_ats_preview(ats_preview_text),
    }


def _serialize_job_gaps_from_rows(job_id: int, rows: list[Any]) -> dict[str, Any]:
    wording_gaps: list[dict[str, Any]] = []
    skill_gaps: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        gap_type = str(item.get('gap_type') or 'true_skill_gap').strip()
        skill_name = str(item.get('skill_name') or '').strip()
        brief = str(item.get('micro_project_brief') or '').strip()
        proof_url = str(item.get('proof_url') or '').strip() or None
        is_verified = bool(int(item.get('verified') or 0))
        serialized = {
            'id': item.get('id'),
            'job_id': int(item.get('job_id') or job_id),
            'skill_name': skill_name,
            'gap_type': gap_type,
            'micro_project_brief': brief,
            'proof_url': proof_url,
            'verified': is_verified,
            'created_at': item.get('created_at') or '',
        }
        artifacts.append(serialized)
        if gap_type == 'wording_gap':
            wording_gaps.append({
                'id': item.get('id'),
                'job_term': skill_name,
                'candidate_evidence': brief,
            })
        else:
            skill_gaps.append({
                'id': item.get('id'),
                'skill_name': skill_name,
                'gap_type': gap_type,
                'micro_project_brief': brief,
                'proof_url': proof_url,
                'verified': is_verified,
                'created_at': item.get('created_at') or '',
            })

    schema_artifact = _build_schema_gap_artifact(job_id, wording_gaps, skill_gaps)
    verified_skills = [s['skill_name'] for s in skill_gaps if s['verified']]
    return {
        'wording_gaps': wording_gaps,
        'skill_gaps': skill_gaps,
        'artifacts': artifacts,
        'schema_artifact': schema_artifact,
        'verified_gap_skills': verified_skills,
        'verified_count': len(verified_skills),
        'unverified_skill_gap_count': sum(1 for s in skill_gaps if not s['verified']),
    }


def _handle_get_job_gaps(job_id: int) -> tuple[int, dict[str, Any]]:
    job_row = db.row('SELECT id, title, company FROM jobs WHERE id=?', (job_id,))
    if not job_row:
        return 404, {'error': f'Job {job_id} not found.'}
    rows = db.rows('SELECT * FROM gap_artifacts WHERE job_id=? ORDER BY id ASC', (job_id,))
    serialized = _serialize_job_gaps_from_rows(job_id, rows)
    return 200, {
        'ok': True,
        'job_id': job_id,
        'job_title': job_row['title'] or '',
        'company': job_row['company'] or '',
        **serialized,
    }


def _handle_list_all_gaps() -> tuple[int, dict[str, Any]]:
    rows = db.rows(
        'SELECT g.*, j.title AS job_title, j.company AS company '
        'FROM gap_artifacts g LEFT JOIN jobs j ON j.id=g.job_id '
        'ORDER BY g.job_id DESC, g.id ASC'
    )
    grouped: dict[int, list[Any]] = {}
    meta: dict[int, tuple[str, str]] = {}
    for row in rows:
        jid = int(row['job_id'])
        grouped.setdefault(jid, []).append(row)
        meta[jid] = (str(row['job_title'] or ''), str(row['company'] or ''))

    by_job: list[dict[str, Any]] = []
    all_artifacts: list[dict[str, Any]] = []
    for jid, group_rows in grouped.items():
        serialized = _serialize_job_gaps_from_rows(jid, group_rows)
        title, company = meta[jid]
        all_artifacts.extend(serialized['artifacts'])
        by_job.append({
            'job_id': jid,
            'job_title': title,
            'company': company,
            **serialized,
        })

    return 200, {
        'ok': True,
        'count': len(all_artifacts),
        'artifacts': all_artifacts,
        'by_job': by_job,
    }


def _refresh_unconfirmed_callbacks_for_job(job_id: int) -> None:
    job_row = db.row('SELECT * FROM jobs WHERE id=?', (job_id,))
    if not job_row:
        return
    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    profile_resume = (profile_row or {}).get('resume') or ''
    verified_proofs = _load_verified_gap_proofs(job_id)
    app_rows = db.rows(
        "SELECT * FROM applications WHERE job_id=? AND status NOT IN ('confirmed', 'test_submitted') ORDER BY id DESC",
        (job_id,),
    )
    if not app_rows:
        return
    builder = _get_callback_builder()
    with db.connection() as con:
        for app_row in app_rows:
            prev_cb = _safe_json_dict(app_row['callback_packet_json'])
            answers_store = _safe_json_dict(app_row['answers_json'])
            candidate_answers = _strip_sensitive_answers(_safe_json_dict(answers_store.get('candidate_answers')))
            tailored_resume = str(app_row['tailored_resume'] or profile_resume or '').strip()
            refreshed_cb = builder.build(
                dict(job_row),
                profile_resume,
                tailored_resume,
                existing_cb={**prev_cb, 'probe_questions': []},
                candidate_answers=candidate_answers,
                verified_gap_proofs=verified_proofs,
                resume_sha256=app_row['resume_sha256'] or None,
                answers_sha256=app_row['answers_sha256'] or None,
                mode='heuristic',
            )
            con.execute(
                'UPDATE applications SET callback_packet_json=? WHERE id=?',
                (json.dumps(refreshed_cb, ensure_ascii=False), app_row['id']),
            )


def _handle_gap_analyze(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    raw_job_id = payload.get('job_id')
    if raw_job_id is None:
        return 400, {'error': 'job_id is required.'}
    try:
        job_id = int(raw_job_id)
    except (TypeError, ValueError):
        return 400, {'error': 'job_id must be an integer.'}

    job_row = db.row('SELECT * FROM jobs WHERE id=?', (job_id,))
    if not job_row:
        return 404, {'error': f'Job {job_id} not found.'}

    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    profile_resume = (profile_row or {}).get('resume') or ''
    base_resume = str(payload.get('base_resume') or profile_resume).strip()
    if len(base_resume) < MIN_RESUME_CHARS:
        return 400, {'error': f'Candidate resume must contain at least {MIN_RESUME_CHARS} characters before gap analysis.'}

    mode = str(payload.get('mode') or 'auto').strip().lower()
    existing_rows = db.rows('SELECT * FROM gap_artifacts WHERE job_id=? ORDER BY id ASC', (job_id,))
    try:
        analysis = _get_gap_bridge_adapter().analyze(
            base_resume,
            dict(job_row),
            existing_artifacts=[dict(r) for r in existing_rows],
            mode=mode,
        )
    except (GapBridgeError, ModelNotConfiguredError) as exc:
        return 400, {'error': str(exc)}
    except ModelAdapterError as exc:
        return 502, {'error': str(exc)}

    existing_verified = {
        str(r['skill_name']).strip().lower(): dict(r)
        for r in existing_rows
        if int(r['verified'] or 0) == 1 and str(r['gap_type'] or '') != 'wording_gap'
    }

    with db.connection() as con:
        con.execute("DELETE FROM gap_artifacts WHERE job_id=? AND (verified=0 OR gap_type='wording_gap')", (job_id,))
        for wg in analysis['wording_gaps']:
            con.execute(
                'INSERT INTO gap_artifacts(job_id, skill_name, gap_type, micro_project_brief, proof_url, verified) '
                "VALUES(?, ?, 'wording_gap', ?, '', 0)",
                (job_id, wg['job_term'], wg['candidate_evidence']),
            )
        for sg in analysis['skill_gaps']:
            low = sg['skill_name'].lower()
            if low in existing_verified:
                if not str(existing_verified[low].get('micro_project_brief') or '').strip() and sg['micro_project_brief']:
                    con.execute(
                        'UPDATE gap_artifacts SET micro_project_brief=? WHERE id=?',
                        (sg['micro_project_brief'], existing_verified[low]['id']),
                    )
                continue
            con.execute(
                'INSERT INTO gap_artifacts(job_id, skill_name, gap_type, micro_project_brief, proof_url, verified) '
                "VALUES(?, ?, 'true_skill_gap', ?, '', 0)",
                (job_id, sg['skill_name'], sg['micro_project_brief']),
            )

    persisted_rows = db.rows('SELECT * FROM gap_artifacts WHERE job_id=? ORDER BY id ASC', (job_id,))
    serialized = _serialize_job_gaps_from_rows(job_id, persisted_rows)
    _refresh_unconfirmed_callbacks_for_job(job_id)

    db.log_audit(
        'pipeline',
        'gaps_analyzed',
        'job',
        str(job_id),
        {
            'wording_gap_count': len(serialized['wording_gaps']),
            'skill_gap_count': len(serialized['skill_gaps']),
            'verified_count': serialized['verified_count'],
            'generation_mode': analysis['generation_mode'],
            'provider': analysis['provider'],
            'model': analysis['model'],
        },
    )
    return 200, {
        'ok': True,
        'job_id': job_id,
        'job_title': job_row['title'] or '',
        'company': job_row['company'] or '',
        **serialized,
        'matched_keywords': analysis['matched_keywords'],
        'fit_score': analysis['fit_score'],
        'generation_mode': analysis['generation_mode'],
        'provider': analysis['provider'],
        'model': analysis['model'],
    }


def _handle_gap_verify(gap_id: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    gap_row = db.row('SELECT * FROM gap_artifacts WHERE id=?', (gap_id,))
    if not gap_row:
        return 404, {'error': f'Gap artifact {gap_id} not found.'}
    if str(gap_row['gap_type'] or '') == 'wording_gap':
        return 400, {
            'error': 'Wording gaps already map to existing resume evidence and do not require external proof verification.'
        }

    try:
        clean_url = _get_gap_bridge_adapter().validate_proof_url(str(payload.get('proof_url') or ''))
    except GapBridgeError as exc:
        return 400, {'error': str(exc)}

    brief_override = str(payload.get('micro_project_brief') or '').strip()
    new_brief = brief_override or str(gap_row['micro_project_brief'] or '').strip()
    with db.connection() as con:
        con.execute(
            'UPDATE gap_artifacts SET proof_url=?, micro_project_brief=?, verified=1 WHERE id=?',
            (clean_url, new_brief, gap_id),
        )

    job_id = int(gap_row['job_id'])
    updated_row = db.row('SELECT * FROM gap_artifacts WHERE id=?', (gap_id,))
    persisted_rows = db.rows('SELECT * FROM gap_artifacts WHERE job_id=? ORDER BY id ASC', (job_id,))
    serialized = _serialize_job_gaps_from_rows(job_id, persisted_rows)
    _refresh_unconfirmed_callbacks_for_job(job_id)

    db.log_audit(
        'candidate',
        'gap_proof_verified',
        'gap_artifact',
        str(gap_id),
        {
            'job_id': job_id,
            'skill_name': updated_row['skill_name'],
            'proof_url': clean_url,
        },
    )
    return 200, {
        'ok': True,
        'job_id': job_id,
        'unlocked_skill': updated_row['skill_name'],
        'artifact': {
            'id': updated_row['id'],
            'job_id': job_id,
            'skill_name': updated_row['skill_name'],
            'gap_type': updated_row['gap_type'],
            'micro_project_brief': updated_row['micro_project_brief'],
            'proof_url': updated_row['proof_url'],
            'verified': True,
            'created_at': updated_row['created_at'],
        },
        **serialized,
    }


def _synthesize_callback_for_app(app_row: Any, job_row: Any, mode: str = 'heuristic') -> dict[str, Any]:
    existing_cb = _safe_json_dict(app_row['callback_packet_json'])
    answers_store = _safe_json_dict(app_row['answers_json'])
    candidate_answers = _strip_sensitive_answers(_safe_json_dict(answers_store.get('candidate_answers')))
    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    profile_resume = (profile_row or {}).get('resume') or ''
    tailored_resume = str(app_row['tailored_resume'] or profile_resume or '').strip()
    verified_proofs = _load_verified_gap_proofs(int(job_row['id']))
    return _get_callback_builder().build(
        dict(job_row),
        profile_resume,
        tailored_resume,
        existing_cb=existing_cb,
        candidate_answers=candidate_answers,
        verified_gap_proofs=verified_proofs,
        resume_sha256=app_row['resume_sha256'] or None,
        answers_sha256=app_row['answers_sha256'] or None,
        confirmation_reference=app_row['confirmation'] or None,
        submitted_at=app_row['submitted_at'] or None,
        mode=mode,
    )


def _handle_get_callback_packet(app_id: int) -> tuple[int, dict[str, Any]]:
    app_row = db.row(
        'SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
        (app_id,),
    )
    if not app_row:
        return 404, {'error': f'Application {app_id} not found.'}
    job_row = db.row('SELECT * FROM jobs WHERE id=?', (app_row['job_id'],))
    if not job_row:
        return 404, {'error': f'Job {app_row["job_id"]} not found.'}

    existing_cb = _safe_json_dict(app_row['callback_packet_json'])
    has_full = (
        isinstance(existing_cb.get('probe_questions'), list)
        and isinstance(existing_cb.get('diff_summary'), list)
        and 'why_this_role' in existing_cb
    )
    cb_packet = existing_cb if has_full else _synthesize_callback_for_app(app_row, job_row, mode='heuristic')
    return 200, {
        'ok': True,
        'application_id': app_id,
        'immutable': bool(app_row['status'] == 'confirmed'),
        'callback_packet': cb_packet,
        'application': _deserialize_application_row(app_row),
    }


def _handle_post_callback_packet(app_id: int, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {'error': 'Request body must be a JSON object.'}
    app_row = db.row(
        'SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
        (app_id,),
    )
    if not app_row:
        return 404, {'error': f'Application {app_id} not found.'}
    job_row = db.row('SELECT * FROM jobs WHERE id=?', (app_row['job_id'],))
    if not job_row:
        return 404, {'error': f'Job {app_row["job_id"]} not found.'}

    if app_row['status'] == 'test_submitted':
        return 409, {'error': 'Demo test_submitted application is isolated and cannot be modified.'}
    if app_row['status'] == 'confirmed':
        mutating_keys = {'why_this_role', 'probe_questions', 'candidate_answers', 'approved_resume', 'tailored_resume', 'force', 'regenerate'}
        if any(k in payload for k in mutating_keys) or str(payload.get('mode') or '').strip().lower() == 'llm':
            return 409, {'error': 'Confirmed application callback packet is immutable and cannot be modified.'}
        existing_cb = _safe_json_dict(app_row['callback_packet_json'])
        cb_packet = (
            existing_cb
            if ('probe_questions' in existing_cb and 'diff_summary' in existing_cb)
            else _synthesize_callback_for_app(app_row, job_row, mode='heuristic')
        )
        return 200, {
            'ok': True,
            'immutable': True,
            'application_id': app_id,
            'callback_packet': cb_packet,
            'application': _deserialize_application_row(app_row),
        }

    mode = str(payload.get('mode') or 'heuristic').strip().lower()
    if mode not in ('auto', 'llm', 'heuristic'):
        return 400, {'error': 'mode must be one of: auto, llm, heuristic.'}

    existing_cb = _safe_json_dict(app_row['callback_packet_json'])
    seed_cb = {**existing_cb, 'probe_questions': []} if bool(payload.get('refresh_probes', True)) else existing_cb
    answers_store = _safe_json_dict(app_row['answers_json'])
    candidate_answers = _strip_sensitive_answers(_safe_json_dict(answers_store.get('candidate_answers')))
    profile_row = db.row('SELECT resume FROM profile WHERE id=1')
    profile_resume = (profile_row or {}).get('resume') or ''
    tailored_resume = str(app_row['tailored_resume'] or profile_resume or '').strip()
    verified_proofs = _load_verified_gap_proofs(int(job_row['id']))

    try:
        cb_packet = _get_callback_builder().build(
            dict(job_row),
            profile_resume,
            tailored_resume,
            existing_cb=seed_cb,
            candidate_answers=candidate_answers,
            verified_gap_proofs=verified_proofs,
            resume_sha256=app_row['resume_sha256'] or None,
            answers_sha256=app_row['answers_sha256'] or None,
            confirmation_reference=app_row['confirmation'] or None,
            submitted_at=app_row['submitted_at'] or None,
            mode=mode,
        )
    except (GapBridgeError, ModelNotConfiguredError, TailorError) as exc:
        return 400, {'error': str(exc)}
    except ModelAdapterError as exc:
        return 502, {'error': str(exc)}

    with db.connection() as con:
        con.execute(
            'UPDATE applications SET callback_packet_json=? WHERE id=?',
            (json.dumps(cb_packet, ensure_ascii=False), app_id),
        )
    refreshed = db.row(
        'SELECT a.*, j.title, j.company, j.url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?',
        (app_id,),
    )
    db.log_audit(
        'candidate',
        'callback_packet_generated',
        'application',
        str(app_id),
        {
            'job_id': job_row['id'],
            'mode': cb_packet.get('callback_generation_mode'),
            'verified_proof_count': len(verified_proofs),
        },
    )
    return 200, {
        'ok': True,
        'immutable': False,
        'application_id': app_id,
        'callback_packet': cb_packet,
        'application': _deserialize_application_row(refreshed),
    }
