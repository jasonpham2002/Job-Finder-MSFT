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
from pathlib import Path
from typing import Any

from . import db, engine
from .adapters_pipeline import (
    JobDiscoveryError,
    LiveJobDiscoveryAdapter,
    LocalResumeFileAdapter,
    ResumeFileError,
    UnifiedModelAdapter,
    normalize_job_url,
)

MIN_RESUME_CHARS = 50
_JOB_PREFLIGHT_RE = re.compile(r'^/api/pipeline/jobs/(\d+)/preflight$')


def handle_get(path: str):
    """Return (status_code, payload) if path belongs to Owner A, else None."""
    if path == '/api/pipeline/status':
        return 200, {
            'owner': 'Owner A',
            'scope': ['discovery', 'preflight_d1', 'resume_pdf_docx', 'tailor_d2', 'gaps_d5', 'copilot_d3'],
            'implemented': True,
            'tasks_completed': ['A-01', 'A-02'],
            'model_adapter': UnifiedModelAdapter.inspect_capabilities(),
            'resume_adapter': {
                **LocalResumeFileAdapter.inspect_capabilities(),
                'max_upload_json_bytes': 200_000,
            },
            'discovery_adapter': LiveJobDiscoveryAdapter.inspect_capabilities(),
            'note': 'Tasks A-01 + A-02 active (ModelAdapter, ResumeFileAdapter, JobDiscoveryAdapter + D1 Pre-Flight); A-03..A-05 pending.',
        }
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
    if path.startswith('/api/pipeline/'):
        return 501, {
            'error': 'Owner A endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_A_WORKBOOK.md',
        }
    return None
