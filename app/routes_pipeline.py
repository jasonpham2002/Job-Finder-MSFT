"""Owner A modular routes: job discovery, preflight, PDF/DOCX, AI tailor, gaps, Co-Pilot apply.

Teammate A implements concrete logic here and in app/adapters_pipeline.py without
touching app/server.py or Owner B files.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
from pathlib import Path
from typing import Any

from . import db
from .adapters_pipeline import (
    LocalResumeFileAdapter,
    ResumeFileError,
    UnifiedModelAdapter,
)

MIN_RESUME_CHARS = 50


def handle_get(path: str):
    """Return (status_code, payload) if path belongs to Owner A, else None."""
    if path == '/api/pipeline/status':
        return 200, {
            'owner': 'Owner A',
            'scope': ['discovery', 'preflight_d1', 'resume_pdf_docx', 'tailor_d2', 'gaps_d5', 'copilot_d3'],
            'implemented': True,
            'tasks_completed': ['A-01'],
            'model_adapter': UnifiedModelAdapter.inspect_capabilities(),
            'resume_adapter': {
                **LocalResumeFileAdapter.inspect_capabilities(),
                'max_upload_json_bytes': 200_000,
            },
            'note': 'Task A-01 active (ModelAdapter + ResumeFileAdapter); A-02..A-05 pending.',
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


def handle_post(path: str, payload: dict):
    """Return (status_code, payload) if path belongs to Owner A, else None."""
    if path == '/api/pipeline/resume/upload':
        return _handle_resume_upload(payload)
    if path.startswith('/api/pipeline/'):
        return 501, {
            'error': 'Owner A endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_A_WORKBOOK.md',
        }
    return None
