"""Owner A modular routes: job discovery, preflight, PDF/DOCX, AI tailor, gaps, Co-Pilot apply.

Teammate A implements concrete logic here and in app/adapters_pipeline.py without
touching app/server.py or Owner B files.
"""


def handle_get(path: str):
    """Return (status_code, payload) if path belongs to Owner A, else None."""
    if path == '/api/pipeline/status':
        return 200, {
            'owner': 'Owner A',
            'scope': ['discovery', 'preflight_d1', 'resume_pdf_docx', 'tailor_d2', 'gaps_d5', 'copilot_d3'],
            'implemented': False,
            'note': 'Foundation seam ready; implement tasks A-01..A-05 in plans/OWNER_A_WORKBOOK.md.',
        }
    if path.startswith('/api/pipeline/'):
        return 501, {
            'error': 'Owner A endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_A_WORKBOOK.md',
        }
    return None


def handle_post(path: str, payload: dict):
    """Return (status_code, payload) if path belongs to Owner A, else None."""
    if path.startswith('/api/pipeline/'):
        return 501, {
            'error': 'Owner A endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_A_WORKBOOK.md',
        }
    return None
