"""Owner B modular routes: artifact contacts, authorized outreach, inbox sync & callbacks.

Teammate B implements concrete logic here and in app/adapters_outreach.py without
touching app/server.py or Owner A files.
"""


def handle_get(path: str):
    """Return (status_code, payload) if path belongs to Owner B, else None."""
    if path in ('/api/networking/status', '/api/inbox/status'):
        return 200, {
            'owner': 'Owner B',
            'scope': ['contacts_d4', 'outreach_oauth', 'cooldown_optout', 'inbox_sync', 'callback_ui'],
            'implemented': False,
            'note': 'Foundation seam ready; implement tasks B-01..B-04 in plans/OWNER_B_WORKBOOK.md.',
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
    if path.startswith('/api/networking/') or path.startswith('/api/inbox/'):
        return 501, {
            'error': 'Owner B endpoint not implemented yet.',
            'endpoint': path,
            'guide': 'plans/OWNER_B_WORKBOOK.md',
        }
    return None
