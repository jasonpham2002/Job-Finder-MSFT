"""Deterministic, offline reference engine + A-02 URL/ATS extractors & D1 Pre-Flight Shield.

IMPORTANT: This engine does not submit applications, scrape LinkedIn, or send emails.
It never bypasses logins/CAPTCHAs, never invents resume details, and treats external job
text as untrusted data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import html
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib import error, parse, request

STOP = set('a an the and or to for of in at on by with from as is are be this that their our your you we i it have has will can must should ability experience work working team role position job jobs company candidate including strong excellent opportunity relevant required preferred responsible responsibilities years year degree skills knowledge hands hands-on using use an into plus through'.split())

VALID_ATS_FAMILIES = frozenset({
    'greenhouse', 'lever', 'ashby', 'workday', 'linkedin', 'indeed', 'company_site', 'unknown',
})

_AUTH_BLOCK_HTTP_CODES = {401, 403, 407, 429, 451, 999}
_AUTH_REDIRECT_MARKERS = (
    '/login', '/signin', '/authwall', '/uas/login', '/checkpoint/', '/challenge',
)
_BLOCKED_BODY_MARKERS = (
    'sign in to view',
    'join linkedin',
    'authwall',
    'enable javascript to run',
    'please enable javascript',
    'checking your browser before accessing',
    'attention required! | cloudflare',
    'verify you are human',
)
_CLOSED_JOB_PHRASES = (
    'no longer accepting applications',
    'no longer accepting candidates',
    'this job is no longer available',
    'this position has been filled',
    'position has been filled',
    'position filled',
    'role has been filled',
    'job is closed',
    'posting has expired',
    'applications are closed',
    'requisition is closed',
)
_HIGH_RISK_SCAM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        'upfront_reference_harvesting',
        re.compile(
            r'(?:provide|submit|include|attach|send|share).{0,45}'
            r'(?:manager|supervisor|professional|previous\s+boss)\s+references'
            r'(?:.{0,30}(?:upfront|with\s+(?:your\s+)?application|before\s+(?:an?\s+)?interview|prior\s+to\s+interview))?'
            r'|(?:manager|supervisor|professional)?\s*references.{0,25}'
            r'(?:upfront|prior\s+to\s+(?:an?\s+)?interview|before\s+(?:an?\s+)?interview)',
            re.IGNORECASE,
        ),
    ),
    (
        'off_platform_messaging_pivot',
        re.compile(
            r'(?:contact|message|text|reach\s+out|interview|apply|chat).{0,45}'
            r'(?:\btelegram\b|\bwhatsapp\b|\bsignal\b|\bwickr\b)'
            r'|https?://(?:t\.me|wa\.me)/',
            re.IGNORECASE,
        ),
    ),
    (
        'pre_offer_sensitive_pii_or_payment',
        re.compile(
            r'(?:\bssn\b|social\s+security\s+number|bank\s+routing|routing\s+number|'
            r'bank\s+account\s+number|driver\'?s\s+license|passport\s+(?:copy|scan)|'
            r'wire\s+transfer|purchase\s+(?:your\s+own\s+)?equipment|check\s+deposit)',
            re.IGNORECASE,
        ),
    ),
    (
        'untrusted_takehome_or_malware_download',
        re.compile(
            r'npm\s+install\s+(?:https?://|git\+|github\.com/)'
            r'|(?:take-home|coding\s+test|assessment|interview).{0,60}(?:npm\s+install|clone.{0,25}github\.com/)'
            r'|(?:clone|run|execute|install).{0,45}(?:obscure|personal)\s+(?:github|repo|package)'
            r'|(?:download|install|run).{0,45}(?:custom\s+video|assessment|interview)[^\n]{0,30}\.(?:exe|dmg|pkg|msi|bat|cmd|sh)\b',
            re.IGNORECASE,
        ),
    ),
)
_MEDIUM_RISK_SCAM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        'unrealistic_guaranteed_pay',
        re.compile(r'guaranteed\s+\$?\d[\d,]*(?:\s*/\s*|\s+per\s+)(?:day|daily|week|weekly)|earn\s+\$\d{3,4}\s+daily', re.IGNORECASE),
    ),
    (
        'low_bar_urgent_hiring_pitch',
        re.compile(r'(?:urgent\s+hiring|immediate\s+start).{0,40}no\s+experience\s+(?:needed|required)', re.IGNORECASE),
    ),
)


def keywords(value):
    return {w for w in re.findall(r"[a-z][a-z0-9+#.-]{2,}", value.lower()) if w not in STOP}


def match_resume(resume, job_description):
    """Heuristic overlap only; its 0-100 score is NOT an ML fit or hiring probability."""
    a, b = keywords(resume), keywords(job_description)
    matches = sorted(a & b)
    missing = sorted(b - a)
    score = min(100, round(100 * len(matches) / max(1, len(b))))
    return {"score": score, "shared_keywords": matches[:25], "unmatched_job_keywords": missing[:20], "method": "Keyword-overlap demonstration; not an ATS or hiring prediction"}


def draft_resume(resume, job):
    """Reorder/annotate but preserve verified resume content verbatim."""
    fit = match_resume(resume, job.get('description', ''))
    name = job.get('title') or 'this role'
    matched = ', '.join(fit['shared_keywords'][:10]) or 'No confirmed shared keywords yet'
    return (f"TARGET ROLE: {name} at {job.get('company') or 'the employer'}\n\n"
            f"EDITOR'S NOTE (not part of final resume):\n"
            f"Verified overlap: {matched}.\n"
            "Review the job description and move only genuine, relevant experience higher. "
            "Confirm every claim. Do not add skills that are not supported by the resume.\n\n"
            "ORIGINAL VERIFIED RESUME (preserved for editing):\n"
            f"{resume.strip()}\n")


def draft_message(person, job, resume, channel='email'):
    name = person.get('name', 'there').split()[0]
    role = job.get('title', 'a role')
    company = job.get('company', 'your company')
    shared = match_resume(resume, job.get('description', ''))['shared_keywords'][:3]
    basis = ', '.join(shared) if shared else 'my relevant experience'
    message = (f"Hi {name},\n\nI am interested in the {role} opportunity at {company}. "
               f"My resume highlights {basis}, and I would appreciate any perspective "
               "you may be willing to share about the team or hiring process. "
               "If it is appropriate, I would also be grateful for advice on the application.\n\n"
               "Thank you for considering my message.\n\nBest regards,\n[YOUR NAME]")
    return {'subject': f'Question about {role} at {company}' if channel == 'email' else '',
            'body': message, 'channel': channel, 'status': 'draft', 'note': 'Sample draft: verify all claims and approve before sending.'}


def valid_public_url(url):
    """Fail closed on non-public hosts; resolve DNS before fetching any remote data."""
    parsed = parse.urlsplit(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Provide a public http(s) job URL without embedded credentials.')
    if parsed.port and parsed.port not in (80, 443):
        raise ValueError('Only standard web ports 80 and 443 are supported in this starter.')
    host = parsed.hostname.lower().rstrip('.')
    if host in ('localhost',) or host.endswith(('.local', '.internal')):
        raise ValueError('Local or internal addresses cannot be imported.')
    try:
        records = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        if not records:
            raise ValueError('Host has no public DNS address.')
        for item in records:
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                raise ValueError('Private, loopback, or reserved addresses are not allowed.')
    except socket.gaierror as ex:
        raise ValueError('Could not resolve public job website: ' + str(ex)) from ex
    return url


def detect_ats_family(url: str) -> str:
    """Classify a job URL into a canonical ATS family or site category."""
    raw = str(url or '').strip()
    if not raw:
        return 'unknown'
    parsed = parse.urlsplit(raw)
    host = (parsed.hostname or '').lower().rstrip('.')
    if parsed.scheme not in ('http', 'https') or not host:
        return 'unknown'
    if host in ('example.com', 'example.org', 'example.net') or host.endswith(('.example.com', '.example.org', '.example.net')):
        return 'unknown'

    query = parse.parse_qs(parsed.query)
    if host in ('boards.greenhouse.io', 'job-boards.greenhouse.io', 'boards-api.greenhouse.io') or host.endswith('.greenhouse.io') or 'gh_jid' in query:
        return 'greenhouse'
    if host in ('jobs.lever.co', 'jobs.eu.lever.co', 'api.lever.co', 'api.eu.lever.co') or host.endswith('.lever.co'):
        return 'lever'
    if host in ('jobs.ashbyhq.com', 'api.ashbyhq.com') or host.endswith('.ashbyhq.com'):
        return 'ashby'
    if host.endswith('.myworkdayjobs.com') or host.endswith('.myworkdaysite.com') or host.endswith('.workday.com'):
        return 'workday'
    if host == 'linkedin.com' or host.endswith('.linkedin.com'):
        return 'linkedin'
    if host == 'indeed.com' or host.endswith('.indeed.com'):
        return 'indeed'
    return 'company_site'


def parse_ats_url(url: str) -> Optional[dict[str, str]]:
    """Parse canonical Greenhouse, Lever, or Ashby job URLs into public JSON API details."""
    raw = str(url or '').strip()
    if not raw:
        return None
    parsed = parse.urlsplit(raw)
    host = (parsed.hostname or '').lower().rstrip('.')
    parts = [p for p in parsed.path.split('/') if p]
    query = parse.parse_qs(parsed.query)

    if host in ('boards.greenhouse.io', 'job-boards.greenhouse.io'):
        if len(parts) >= 3 and parts[1] == 'jobs':
            board, job_id = parts[0], parts[2]
            return {
                'ats_family': 'greenhouse',
                'board': board,
                'job_id': job_id,
                'api_url': f'https://boards-api.greenhouse.io/v1/boards/{parse.quote(board)}/jobs/{parse.quote(job_id)}?content=true',
            }
        if 'for' in query and 'token' in query:
            board, job_id = query['for'][0], query['token'][0]
            return {
                'ats_family': 'greenhouse',
                'board': board,
                'job_id': job_id,
                'api_url': f'https://boards-api.greenhouse.io/v1/boards/{parse.quote(board)}/jobs/{parse.quote(job_id)}?content=true',
            }

    if host in ('jobs.lever.co', 'jobs.eu.lever.co') and len(parts) >= 2:
        board, job_id = parts[0], parts[1]
        api_host = 'api.eu.lever.co' if host == 'jobs.eu.lever.co' else 'api.lever.co'
        return {
            'ats_family': 'lever',
            'board': board,
            'job_id': job_id,
            'api_url': f'https://{api_host}/v0/postings/{parse.quote(board)}/{parse.quote(job_id)}',
        }

    if host == 'jobs.ashbyhq.com' and len(parts) >= 2:
        board, job_id = parts[0], parts[1]
        return {
            'ats_family': 'ashby',
            'board': board,
            'job_id': job_id,
            'api_url': f'https://api.ashbyhq.com/posting-api/job-board/{parse.quote(board)}?includeCompensation=true',
        }

    return None


class JobParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self.text = []
        self.metatitle = ''
        self.description = ''
        self.job_ld = []
        self._skip = 0
        self._title = False
        self._ld = False
        self._ld_buf = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag in ('style', 'noscript'):
            self._skip += 1
        elif tag == 'script':
            if data.get('type', '').lower() == 'application/ld+json':
                self._ld = True
                self._ld_buf = []
            else:
                self._skip += 1
        elif tag == 'title':
            self._title = True
        elif tag == 'meta':
            key = data.get('property', data.get('name', '')).lower()
            if key == 'og:title':
                self.metatitle = data.get('content', '')
            if key in ('description', 'og:description'):
                self.description = data.get('content', '')

    def handle_endtag(self, tag):
        if tag in ('style', 'noscript') and self._skip:
            self._skip -= 1
        elif tag == 'script':
            if self._ld:
                try:
                    self.job_ld.append(json.loads(''.join(self._ld_buf)))
                except (ValueError, TypeError):
                    pass
                self._ld = False
            elif self._skip:
                self._skip -= 1
        elif tag == 'title':
            self._title = False

    def handle_data(self, data):
        if self._ld:
            self._ld_buf.append(data)
        elif not self._skip:
            if self._title:
                self.title += data
            cleaned = data.strip()
            if cleaned:
                self.text.append(cleaned)


def _find_jobposting(value):
    if isinstance(value, list):
        for item in value:
            found = _find_jobposting(item)
            if found:
                return found
    if isinstance(value, dict):
        kind = value.get('@type', '')
        if kind == 'JobPosting' or isinstance(kind, list) and 'JobPosting' in kind:
            return value
        for key in ('@graph', 'mainEntity'):
            if key in value:
                found = _find_jobposting(value[key])
                if found:
                    return found
    return None


def _text_from_html(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(str(value)))).strip()


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _default_http_get(url: str, accept: str = 'text/html,application/json', timeout: float = 6.0) -> tuple[int, dict[str, str], bytes]:
    """Perform a single SSRF-validated HTTP GET without following redirects automatically."""
    opener = request.build_opener(NoRedirect())
    current = url
    for _ in range(3):
        valid_public_url(current)
        req = request.Request(
            current,
            headers={
                'User-Agent': 'JobFinderHackathonStudentStarter/1.0 (educational; public pages only)',
                'Accept': accept,
            },
        )
        try:
            with opener.open(req, timeout=timeout) as response:
                hdrs = {k.lower(): v for k, v in response.headers.items()}
                hdrs['__final_url__'] = current
                return getattr(response, 'status', 200), hdrs, response.read(600_000)
        except error.HTTPError as exc:
            hdrs = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
            hdrs['__final_url__'] = current
            body = b''
            try:
                body = exc.read(100_000)
            except Exception:
                pass
            finally:
                exc.close()
            if exc.code in (301, 302, 303, 307, 308):
                location = hdrs.get('location')
                if not location:
                    return exc.code, hdrs, body
                next_url = parse.urljoin(current, location)
                if any(marker in next_url.lower() for marker in _AUTH_REDIRECT_MARKERS):
                    hdrs['__final_url__'] = next_url
                    return 401, hdrs, body
                current = next_url
                continue
            return exc.code, hdrs, body
    raise ValueError('Redirect limit reached. Paste the job description manually.')


def _format_board_name(slug: str) -> str:
    return ' '.join(part.capitalize() for part in re.split(r'[-_]+', str(slug or '').strip()) if part)


def _format_jobposting_location(structured: Mapping[str, Any]) -> str:
    locations: list[str] = []
    job_loc = structured.get('jobLocation')
    items = job_loc if isinstance(job_loc, list) else ([job_loc] if isinstance(job_loc, dict) else [])
    for item in items:
        if not isinstance(item, dict):
            continue
        addr = item.get('address')
        if isinstance(addr, dict):
            parts = [
                str(addr.get('addressLocality') or '').strip(),
                str(addr.get('addressRegion') or '').strip(),
                str(addr.get('addressCountry') or '').strip(),
            ]
            joined = ', '.join(p for p in parts if p)
            if joined and joined not in locations:
                locations.append(joined)
        elif isinstance(addr, str) and addr.strip():
            locations.append(addr.strip())
    if str(structured.get('jobLocationType') or '').upper() == 'TELECOMMUTE' and 'Remote' not in locations:
        locations.append('Remote')
    return ' / '.join(locations)[:120]


def _format_jobposting_salary(structured: Mapping[str, Any]) -> str:
    base = structured.get('baseSalary')
    if not isinstance(base, dict):
        return ''
    currency = str(base.get('currency') or '').strip()
    unit = ''
    val = base.get('value')
    if isinstance(val, dict):
        unit = str(val.get('unitText') or '').strip()
        min_v = val.get('minValue')
        max_v = val.get('maxValue')
        exact = val.get('value')
        if min_v is not None and max_v is not None:
            amount = f'{min_v}-{max_v}'
        elif exact is not None:
            amount = str(exact)
        else:
            amount = ''
    elif val is not None:
        amount = str(val)
    else:
        amount = ''
    if not amount:
        return ''
    return ' '.join(part for part in (currency, amount, unit) if part)[:80]


def _format_lever_salary(data: Mapping[str, Any]) -> str:
    sal = data.get('salaryRange')
    if not isinstance(sal, dict):
        return ''
    low = sal.get('min')
    high = sal.get('max')
    currency = str(sal.get('currency') or '').strip()
    interval = str(sal.get('interval') or '').strip()
    if low is None and high is None:
        return ''
    span = f'{low}-{high}' if (low is not None and high is not None) else str(low if low is not None else high)
    return ' '.join(part for part in (currency, span, interval) if part)[:80]


def _epoch_ms_to_iso(value: Any) -> str:
    if isinstance(value, (int, float)) and value > 0:
        dt = datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    return ''


def _fetch_ats_single_job(
    ats_info: dict[str, str],
    original_url: str,
    http_get: Callable[[str, str, float], tuple[int, dict[str, str], bytes]],
) -> Optional[dict[str, Any]]:
    api_url = ats_info['api_url']
    status, _, raw = http_get(api_url, 'application/json', 6.0)
    if status != 200:
        return None
    try:
        data = json.loads(raw.decode('utf-8', errors='replace'))
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    ats_family = ats_info['ats_family']
    board = ats_info['board']

    if ats_family == 'greenhouse':
        loc = data.get('location')
        loc_name = str(loc.get('name') or '').strip() if isinstance(loc, dict) else ''
        desc = _text_from_html(data.get('content', ''))
        if len(desc) < 40:
            return None
        return {
            'title': _text_from_html(data.get('title', ''))[:200],
            'company': str(data.get('company_name') or _format_board_name(board))[:120],
            'description': desc[:12000],
            'location': loc_name[:120],
            'salary_text': '',
            'posted_at': str(data.get('first_published') or data.get('updated_at') or '')[:40],
            'valid_through': '',
            'url': str(data.get('absolute_url') or original_url),
            'ats_family': 'greenhouse',
            'extraction': 'greenhouse-public-api',
            'extraction_status': 'verified',
        }

    if ats_family == 'lever':
        cats = data.get('categories') or {}
        sections = [str(data.get('descriptionPlain') or _text_from_html(data.get('description', ''))).strip()]
        for lst in data.get('lists') or []:
            if isinstance(lst, dict):
                heading = str(lst.get('text') or '').strip()
                items_txt = _text_from_html(lst.get('content', ''))
                if heading or items_txt:
                    sections.append(f'{heading}: {items_txt}'.strip(': '))
        if data.get('additionalPlain'):
            sections.append(str(data['additionalPlain']).strip())
        desc = ' '.join(s for s in sections if s)
        if len(desc) < 40:
            return None
        return {
            'title': str(data.get('text') or '')[:200],
            'company': _format_board_name(board)[:120],
            'description': desc[:12000],
            'location': str(cats.get('location') or '')[:120],
            'salary_text': _format_lever_salary(data),
            'posted_at': _epoch_ms_to_iso(data.get('createdAt')),
            'valid_through': '',
            'url': str(data.get('hostedUrl') or original_url),
            'ats_family': 'lever',
            'extraction': 'lever-public-api',
            'extraction_status': 'verified',
        }

    if ats_family == 'ashby':
        job_id = ats_info['job_id']
        jobs_list = data.get('jobs') or []
        match = next(
            (
                item for item in jobs_list
                if isinstance(item, dict)
                and (str(item.get('id') or '') == job_id or job_id in str(item.get('jobUrl') or ''))
            ),
            None,
        )
        if not match:
            return None
        desc = str(match.get('descriptionPlain') or _text_from_html(match.get('descriptionHtml', ''))).strip()
        if len(desc) < 40:
            return None
        comp = match.get('compensation')
        comp_summary = str(comp.get('compensationTierSummary') or '').strip() if isinstance(comp, dict) else ''
        return {
            'title': str(match.get('title') or '')[:200],
            'company': _format_board_name(board)[:120],
            'description': desc[:12000],
            'location': str(match.get('location') or '')[:120],
            'salary_text': comp_summary[:80],
            'posted_at': str(match.get('publishedAt') or '')[:40],
            'valid_through': '',
            'url': str(match.get('jobUrl') or original_url),
            'ats_family': 'ashby',
            'extraction': 'ashby-public-api',
            'extraction_status': 'verified',
        }

    return None


def _manual_fallback_payload(url: str, ats_family: str, reason: str) -> dict[str, Any]:
    return {
        'title': '',
        'company': '',
        'description': '',
        'location': '',
        'salary_text': '',
        'posted_at': '',
        'valid_through': '',
        'url': url,
        'ats_family': ats_family,
        'extraction': 'manual-fallback',
        'extraction_status': 'manual_fallback',
        'fallback_required': True,
        'reason': reason,
    }


def inspect_public_job_url(
    url: str,
    http_get: Optional[Callable[[str, str, float], tuple[int, dict[str, str], bytes]]] = None,
) -> dict[str, Any]:
    """Extract normalized job metadata via public ATS APIs, JSON-LD, or HTML with honest fallback."""
    valid_public_url(url)
    fetcher = http_get or _default_http_get
    ats_family = detect_ats_family(url)

    ats_info = parse_ats_url(url)
    if ats_info is not None:
        try:
            ats_result = _fetch_ats_single_job(ats_info, url, fetcher)
            if ats_result is not None:
                return ats_result
        except (error.URLError, TimeoutError, ValueError):
            pass

    try:
        status, headers, raw = fetcher(url, 'text/html', 6.0)
    except (error.URLError, TimeoutError) as exc:
        return _manual_fallback_payload(
            url,
            ats_family,
            f'Could not reach {ats_family} URL ({exc}). Paste the job description manually without bypassing site controls.',
        )

    final_url = headers.get('__final_url__', url)
    final_ats = detect_ats_family(final_url) if final_url else ats_family
    if final_ats != 'unknown':
        ats_family = final_ats

    if status in _AUTH_BLOCK_HTTP_CODES or any(m in final_url.lower() for m in _AUTH_REDIRECT_MARKERS):
        return _manual_fallback_payload(
            url,
            ats_family,
            f'Site blocked automated access or requires sign-in (HTTP {status} on {ats_family}). '
            'Paste the job description manually; never bypass logins or CAPTCHAs.',
        )
    if status >= 400:
        return _manual_fallback_payload(
            url,
            ats_family,
            f'Website returned HTTP {status}. Paste the job description manually.',
        )

    content_type = headers.get('content-type', '')
    if content_type and 'text/html' not in content_type.lower() and 'application/xhtml' not in content_type.lower():
        return _manual_fallback_payload(
            url,
            ats_family,
            'This address did not return HTML. Paste the job description manually.',
        )

    decoded = raw.decode('utf-8', errors='replace')
    parser = JobParser()
    parser.feed(decoded)
    structured = _find_jobposting(parser.job_ld)

    if structured:
        org = structured.get('hiringOrganization') or {}
        orgname = org.get('name', '') if isinstance(org, dict) else ''
        desc = _text_from_html(structured.get('description', ''))[:12000]
        result = {
            'title': _text_from_html(structured.get('title', parser.metatitle or parser.title))[:200],
            'company': _text_from_html(orgname)[:120],
            'description': desc,
            'location': _format_jobposting_location(structured),
            'salary_text': _format_jobposting_salary(structured),
            'posted_at': str(structured.get('datePosted') or '').strip()[:40],
            'valid_through': str(structured.get('validThrough') or '').strip()[:40],
            'url': final_url,
            'ats_family': ats_family,
            'extraction': 'schema-org-jobposting',
            'extraction_status': 'verified',
        }
    else:
        visible_text = (' '.join(parser.text) or parser.description)[:12000]
        lower_sample = (decoded[:4000] + ' ' + visible_text[:1000]).lower()
        if len(visible_text.strip()) < 70 or (
            len(visible_text.strip()) < 400 and any(marker in lower_sample for marker in _BLOCKED_BODY_MARKERS)
        ):
            return _manual_fallback_payload(
                url,
                ats_family,
                f'Job page on {ats_family} requires JavaScript rendering, cookies, or login. '
                'Paste the job description manually.',
            )
        result = {
            'title': (parser.metatitle or parser.title).strip()[:200],
            'company': '',
            'description': visible_text,
            'location': '',
            'salary_text': '',
            'posted_at': '',
            'valid_through': '',
            'url': final_url,
            'ats_family': ats_family,
            'extraction': 'generic-html-needs-review',
            'extraction_status': 'needs_review',
        }

    if len(result['description']) < 70:
        return _manual_fallback_payload(
            url,
            ats_family,
            'Job content was not accessible (<70 chars). Paste the description manually.',
        )
    return result


def extract_public_job(url):
    """Best-effort public ATS / HTML + JobPosting JSON-LD; no login, no bypass, no LinkedIn scraping."""
    result = inspect_public_job_url(url)
    if result.get('extraction_status') == 'manual_fallback':
        raise ValueError(result.get('reason') or 'Job content was not accessible. Paste the description manually.')
    return result


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or '').strip()
    if not raw:
        return None
    normalized = raw.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', raw)
    if m:
        try:
            return datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def evaluate_preflight(job: Mapping[str, Any], now: Optional[datetime] = None) -> dict[str, Any]:
    """Evaluate D1 Pre-Flight Shield: ATS family, liveness, scam flags, and friction-ROI."""
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    url = str(job.get('url') or '').strip()
    title = str(job.get('title') or '').strip()
    description = str(job.get('description') or '').strip()
    combined_text = f'{title}\n{description}'
    lower_text = combined_text.lower()

    raw_ats = str(job.get('ats_family') or '').strip().lower()
    ats_family = raw_ats if raw_ats in VALID_ATS_FAMILIES and raw_ats != 'unknown' else detect_ats_family(url)

    posted_dt = _parse_iso_datetime(job.get('posted_at') or job.get('datePosted'))
    valid_through_dt = _parse_iso_datetime(job.get('valid_through') or job.get('validThrough'))

    notes_parts: list[str] = [f'ATS={ats_family}']

    if any(phrase in lower_text for phrase in _CLOSED_JOB_PHRASES):
        liveness_status = 'closed'
        notes_parts.append('Closed-posting wording detected.')
    elif valid_through_dt is not None and valid_through_dt < current_time:
        liveness_status = 'closed'
        notes_parts.append(f'validThrough expired ({valid_through_dt.date().isoformat()}).')
    elif posted_dt is not None:
        age_days = max(0, (current_time - posted_dt).days)
        if age_days > 30:
            liveness_status = 'stale_risk'
            notes_parts.append(f'Posted {age_days}d ago (>30d stale risk; needs_review).')
        else:
            liveness_status = 'active'
            notes_parts.append(f'Fresh posting ({age_days}d old).')
    else:
        liveness_status = 'unknown'
        notes_parts.append('Missing posting date (needs_review).')

    scam_flags: list[str] = []
    high_hits = 0
    medium_hits = 0
    for flag_name, pattern in _HIGH_RISK_SCAM_PATTERNS:
        if pattern.search(combined_text):
            scam_flags.append(flag_name)
            high_hits += 1
    for flag_name, pattern in _MEDIUM_RISK_SCAM_PATTERNS:
        if pattern.search(combined_text):
            scam_flags.append(flag_name)
            medium_hits += 1

    if high_hits >= 1 or medium_hits >= 2:
        scam_risk = 'high'
    elif medium_hits == 1:
        scam_risk = 'medium'
    else:
        scam_risk = 'low'

    if scam_flags:
        notes_parts.append(f'Red flags: {", ".join(scam_flags)}.')

    if scam_risk == 'high' or liveness_status == 'closed':
        friction_roi = 'high_risk'
    elif ats_family in ('linkedin', 'indeed') or 'easy apply' in lower_text or '1-click apply' in lower_text:
        friction_roi = 'saturated_easy_apply'
    elif ats_family in ('workday', 'ashby', 'greenhouse', 'lever', 'company_site') and liveness_status == 'active' and scam_risk == 'low':
        friction_roi = 'high_roi_low_bot_noise'
    else:
        friction_roi = 'standard'

    return {
        'ats_family': ats_family,
        'liveness_status': liveness_status,
        'scam_risk': scam_risk,
        'scam_flags': scam_flags,
        'friction_roi': friction_roi,
        'notes': ' '.join(notes_parts),
    }


def preflight_storage_dict(preflight: Mapping[str, Any]) -> dict[str, Any]:
    """Return the strict schemas/job.schema.json#properties.preflight subset (no extra keys)."""
    return {
        'liveness_status': str(preflight.get('liveness_status', 'unknown')),
        'scam_risk': str(preflight.get('scam_risk', 'low')),
        'scam_flags': list(preflight.get('scam_flags') or []),
        'friction_roi': str(preflight.get('friction_roi', 'standard')),
        'notes': str(preflight.get('notes', '')),
    }


# ---------------------------------------------------------------------------
# Task A-04: Deterministic D2 Anti-Slop Linter & Claim Grounding Verifier
# ---------------------------------------------------------------------------

_AI_SLOP_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ('spearheaded', re.compile(r'\bspearhead(?:ed|ing|s)?\b', re.IGNORECASE), 'led / built / launched'),
    ('synergistic', re.compile(r'\bsynerg(?:istic|istically|ies|y|ize|ized)?\b', re.IGNORECASE), 'collaborative / combined'),
    ('delved', re.compile(r'\bdelv(?:e|ed|ing|s)\b', re.IGNORECASE), 'analyzed / investigated'),
    ('orchestrated', re.compile(r'\borchestrat(?:e|ed|ing|s)\b', re.IGNORECASE), 'coordinated / ran'),
    ('testament', re.compile(r'\btestament\b', re.IGNORECASE), 'evidence / result'),
    ('cutting-edge', re.compile(r'\bcutting[- ]edge\b', re.IGNORECASE), 'modern (or name the exact tool)'),
    ('dynamic professional', re.compile(r'\bdynamic\s+professional\b', re.IGNORECASE), 'actual role title + domain'),
    ('results-driven', re.compile(r'\bresults[- ]driven\b', re.IGNORECASE), 'state measurable outcome instead'),
    ('detail-oriented', re.compile(r'\bdetail[- ]oriented\b', re.IGNORECASE), 'show concrete accuracy/QA work instead'),
    ('self-starter', re.compile(r'\bself[- ]starter\b', re.IGNORECASE), 'describe project initiated independently'),
    ('best-in-class', re.compile(r'\bbest[- ]in[- ]class\b', re.IGNORECASE), 'replace hype with concrete benchmark'),
    ('world-class', re.compile(r'\bworld[- ]class\b', re.IGNORECASE), 'replace hype with concrete scope'),
    ('thought leader', re.compile(r'\bthought\s+leader(?:ship)?\b', re.IGNORECASE), 'cite specific talk, doc, or mentoring'),
    ('game-changer', re.compile(r'\bgame[- ]chang(?:er|ing)\b', re.IGNORECASE), 'state specific impact instead'),
    ('revolutionized', re.compile(r'\brevolutioniz(?:e|ed|ing|es)\b', re.IGNORECASE), 'redesigned / improved'),
    ('leveraged', re.compile(r'\bleverag(?:e|ed|ing|es)\b', re.IGNORECASE), 'used / applied'),
)

_METRIC_TOKEN_RE = re.compile(
    r'\$\s*\d[\d,]*(?:\.\d+)?[kKmMbB]?\b'
    r'|\b\d+(?:\.\d+)?%'
    r'|\b\d+(?:\.\d+)?[xX+]\b'
    r'|\b\d[\d,]*(?:\.\d+)?\b'
)
_TECH_TERM_RE = re.compile(
    r'\b(?:'
    r'python|javascript|typescript|react|next\.js|node\.js|angular|vue|django|flask|fastapi|'
    r'java|kotlin|swift|golang|rust|ruby|php|scala|sql|postgres(?:ql)?|mysql|sqlite|mongodb|'
    r'redis|kafka|airflow|spark|snowflake|databricks|bigquery|dbt|tableau|power\s*bi|'
    r'aws|gcp|azure|kubernetes|docker|terraform|ansible|jenkins|github\s*actions|'
    r'pytorch|tensorflow|scikit-learn|langchain|graphql|grpc|salesforce|workday|sap'
    r')\b',
    re.IGNORECASE,
)


def lint_ai_slop(text: str) -> dict[str, Any]:
    """Detect recognizable LLM/corporate clichés and suggest voice-preserving replacements."""
    raw = str(text or '')
    lines = raw.splitlines() or [raw]
    flagged_terms: list[dict[str, Any]] = []
    slop_warnings: list[str] = []
    total_hits = 0

    for label, pattern, suggestion in _AI_SLOP_RULES:
        matches = list(pattern.finditer(raw))
        if not matches:
            continue
        line_nums = [
            idx + 1 for idx, line in enumerate(lines)
            if pattern.search(line)
        ]
        count = len(matches)
        total_hits += count
        flagged_terms.append({
            'term': label,
            'count': count,
            'suggestion': suggestion,
            'line_numbers': line_nums,
        })
        line_str = ', '.join(str(n) for n in line_nums[:4])
        slop_warnings.append(
            f'Avoid AI/corporate cliché "{label}" ({count}x, line {line_str}) — consider "{suggestion}".'
        )

    return {
        'slop_warnings': slop_warnings,
        'flagged_terms': flagged_terms,
        'slop_score': total_hits,
        'clean': total_hits == 0,
    }


def _normalize_ws(text: str) -> str:
    return re.sub(r'\s+', ' ', str(text or '').lower()).strip()


def _extract_meaningful_metrics(text: str) -> set[str]:
    found: set[str] = set()
    for match in _METRIC_TOKEN_RE.findall(str(text or '')):
        clean = re.sub(r'\s+', '', match).lower().strip(',.')
        if not clean:
            continue
        # Exclude plain 4-digit calendar years (1900-2099) from synthetic metric warnings.
        if re.fullmatch(r'(?:19|20)\d{2}', clean):
            continue
        # Ignore trivial single digits 1-9 unless qualified by %, $, x, or +.
        if clean.isdigit() and int(clean) < 10:
            continue
        found.add(clean)
    return found


def verify_tailor_grounding(
    original_resume: str,
    tailored_text: str,
    claim_evidence_map: Sequence[Mapping[str, str]],
    candidate_confirmations: Optional[Mapping[str, Any]] = None,
    verified_gap_skills: Sequence[str] = (),
) -> dict[str, Any]:
    """Deterministically verify that tailored claims, metrics, and skills trace back to source facts."""
    evidence_parts = [str(original_resume or '')]
    if isinstance(candidate_confirmations, Mapping):
        for k, v in candidate_confirmations.items():
            if str(v or '').strip():
                evidence_parts.append(f'{k}: {v}')
    for skill in verified_gap_skills:
        clean_skill = str(skill or '').strip()
        if clean_skill:
            evidence_parts.append(f'Verified Gap Project: {clean_skill}')

    evidence_corpus = '\n'.join(evidence_parts)
    norm_corpus = _normalize_ws(evidence_corpus)
    corpus_tokens = set(re.findall(r'[a-z0-9+#.-]{3,}', norm_corpus))

    verified_map: list[dict[str, str]] = []
    unverified_claims: list[str] = []
    questions: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()

    for entry in claim_evidence_map or []:
        if not isinstance(entry, Mapping):
            continue
        claim = str(entry.get('claim') or '').strip()
        snippet = str(entry.get('source_snippet') or '').strip()
        if not claim:
            continue
        norm_snippet = _normalize_ws(snippet)
        snippet_tokens = [tok for tok in re.findall(r'[a-z0-9+#.-]{3,}', norm_snippet)]

        is_grounded = False
        if len(norm_snippet) >= 4 and norm_snippet in norm_corpus:
            is_grounded = True
        elif snippet_tokens:
            overlap_ratio = sum(1 for tok in snippet_tokens if tok in corpus_tokens) / len(snippet_tokens)
            if overlap_ratio >= 0.75:
                is_grounded = True

        if is_grounded:
            pair = (claim, snippet)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                verified_map.append({'claim': claim, 'source_snippet': snippet})
        else:
            unverified_claims.append(f'{claim} (unverified source snippet: {snippet or "missing"})')
            questions.append(f'Can you verify "{claim}"? No matching snippet was found in your source resume.')

    # Catch unverified quantitative metrics or dollar/percentage figures introduced in tailored_text.
    source_metrics = _extract_meaningful_metrics(evidence_corpus)
    tailored_metrics = _extract_meaningful_metrics(tailored_text)
    for new_metric in sorted(tailored_metrics - source_metrics):
        unverified_claims.append(f'New metric "{new_metric}" in tailored resume lacks source verification.')
        questions.append(f'Please confirm metric "{new_metric}" before keeping it on your resume.')

    # Catch well-known technical tools introduced in tailored_text without evidence in source corpus.
    source_tech = {m.lower() for m in _TECH_TERM_RE.findall(evidence_corpus)}
    tailored_tech = {m.lower() for m in _TECH_TERM_RE.findall(tailored_text)}
    for new_tech in sorted(tailored_tech - source_tech):
        unverified_claims.append(f'Unsupported technology "{new_tech}" detected outside verified source evidence.')
        questions.append(f'Do you have verified hands-on experience with "{new_tech}"? Provide evidence before adding it.')

    return {
        'claim_evidence_map': verified_map,
        'unverified_claims': list(dict.fromkeys(unverified_claims)),
        'questions_for_candidate': list(dict.fromkeys(questions)),
    }


# ---------------------------------------------------------------------------
# Task A-05: D5 Gap-to-Proof Bridge & D2 Callback Cheat Sheet Engine Helpers
# ---------------------------------------------------------------------------

_GENERIC_FILLER_GAP_WORDS = frozenset({
    'analyze', 'analysis', 'backend', 'build', 'building', 'clean', 'collaborate', 'create', 'creating',
    'data', 'deliver', 'deployment', 'deployments', 'design', 'develop', 'developing', 'drive', 'end', 'engineer',
    'engineering', 'ensure', 'environment', 'fast', 'focus', 'frontend', 'fullstack', 'good', 'great', 'harnesses', 'help', 'high',
    'implement', 'improve', 'including', 'key', 'large', 'maintain', 'manage', 'modern', 'module', 'modules', 'new',
    'open', 'own', 'platform', 'problems', 'product', 'production', 'proven', 'real', 'related', 'reliable',
    'remote', 'requirements', 'role', 'scalable', 'scale', 'services', 'software', 'solutions',
    'stakeholder', 'stakeholders', 'support', 'supporting', 'system', 'systems', 'technical',
    'tools', 'understand', 'writing', 'written',
})

_SKILL_SYNONYM_CLUSTERS: tuple[tuple[str, ...], ...] = (
    ('kubernetes', 'k8s', 'eks', 'aks', 'gke', 'container orchestration'),
    ('docker', 'container', 'containers', 'containerized', 'containerization', 'podman'),
    ('postgresql', 'postgres', 'psql', 'sql', 'mysql', 'sqlite', 'relational database'),
    ('typescript', 'ts', 'javascript', 'js', 'ecmascript'),
    ('react', 'reactjs', 'next.js', 'nextjs', 'frontend spa'),
    ('ci/cd', 'cicd', 'ci', 'github actions', 'gitlab ci', 'jenkins', 'continuous integration'),
    ('etl', 'elt', 'data pipeline', 'data pipelines', 'airflow', 'ingestion'),
    ('pytest', 'unit test', 'unit tests', 'unit testing', 'automated testing', 'integration tests', 'tdd'),
    ('rest', 'restful', 'rest apis', 'rest api', 'http api', 'apis', 'api'),
    ('terraform', 'iac', 'infrastructure as code', 'cloudformation', 'pulumi'),
    ('dashboard', 'dashboards', 'kpi reporting', 'bi', 'tableau', 'power bi', 'analytics'),
    ('aws', 'gcp', 'azure', 'cloud infrastructure', 'cloud'),
    ('graphql', 'apollo', 'schema api'),
    ('redis', 'memcached', 'caching', 'in-memory cache'),
)

_MICRO_PROJECT_TEMPLATES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ('kubernetes', 'k8s', 'eks', 'aks', 'gke'),
        '48h Lab: Package a sample FastAPI/Python worker into a Deployment + Service + readiness/liveness probe '
        'YAML tested on kind/minikube; push manifests, smoke test script, and failure-recovery README to a public repo.',
    ),
    (
        ('terraform', 'iac', 'pulumi'),
        '48h Lab: Author modular Terraform config provisioning a local/cloud sandbox resource with variables, outputs, '
        'tflint/validate CI check, and plan output screenshot documented in a public README.',
    ),
    (
        ('docker', 'container', 'containerization'),
        '48h Lab: Create a multi-stage minimal Dockerfile + docker-compose healthcheck harness running automated integration '
        'checks against a tiny seed dataset; publish repo with build size before/after metrics.',
    ),
    (
        ('graphql', 'apollo'),
        '48h Lab: Build a typed GraphQL schema over an existing SQLite dataset with query/mutation resolvers, N+1 batching '
        'notes, and 5 automated query tests.',
    ),
    (
        ('airflow', 'etl', 'dbt', 'spark', 'kafka'),
        '48h Lab: Build an idempotent ingestion + transform pipeline on public sample CSV data with schema validation, '
        'retry behavior, row-count assertions, and reproducible CLI run instructions.',
    ),
    (
        ('react', 'typescript', 'next.js', 'nextjs'),
        '48h Lab: Ship a single-screen interactive React + TypeScript component backed by typed mock JSON, keyboard navigation, '
        'and unit tests covering empty/error/loading states.',
    ),
)


def _find_candidate_evidence(term: str, resume_text: str) -> str:
    """Return verbatim resume line supporting term directly or via adjacent synonym cluster, else ''."""
    clean_term = str(term or '').strip().lower()
    if not clean_term or not resume_text:
        return ''
    lines = [ln.strip() for ln in str(resume_text).splitlines() if ln.strip()]

    # Build equivalent search terms from synonym clusters containing clean_term.
    related_terms: list[str] = [clean_term]
    for cluster in _SKILL_SYNONYM_CLUSTERS:
        if clean_term in cluster or any(clean_term in alias or alias in clean_term for alias in cluster if len(alias) >= 4):
            for alias in cluster:
                if alias != clean_term:
                    related_terms.append(alias)

    for candidate in related_terms:
        pattern = re.compile(r'(?<![a-z0-9])' + re.escape(candidate) + r'(?![a-z0-9])', re.IGNORECASE)
        for line in lines:
            if pattern.search(line):
                return line[:220]
    return ''


def _default_micro_project_brief(skill_name: str, job: Mapping[str, Any]) -> str:
    low = skill_name.lower()
    for aliases, template in _MICRO_PROJECT_TEMPLATES:
        if any(alias == low or alias in low for alias in aliases):
            return template
    role = str(job.get('title') or 'this role').strip()
    return (
        f'48h Lab: Build a focused, reproducible mini-artifact demonstrating {skill_name} for {role} '
        '(working code or config, 3+ automated verification checks, and a concise README explaining design trade-offs), '
        'and publish it at a public URL before adding the skill to your resume.'
    )


def classify_skill_gaps(
    resume_text: str,
    job: Mapping[str, Any],
    verified_gap_skills: Sequence[str] = (),
) -> dict[str, Any]:
    """Deterministically split missing job terms into wording_gaps vs. blocked true_skill_gaps (D5)."""
    base_resume = str(resume_text or '')
    job_text = '\n'.join(
        str(job.get(field) or '').strip()
        for field in ('title', 'requirements', 'description')
        if str(job.get(field) or '').strip()
    )
    verified_set = {str(s or '').strip().lower() for s in verified_gap_skills if str(s or '').strip()}

    # Collect structured tech terms first (preserving natural casing like Kubernetes, CI/CD, GraphQL)
    ordered_terms: list[str] = []
    seen_lower: set[str] = set()
    for m in _TECH_TERM_RE.finditer(job_text):
        tok = m.group(0).strip()
        low = tok.lower()
        if low not in seen_lower:
            seen_lower.add(low)
            ordered_terms.append(tok)

    # Supplement with unmatched high-signal keywords from match_resume
    match_out = match_resume(base_resume, job_text)
    for kw in match_out.get('unmatched_job_keywords') or []:
        clean_kw = str(kw).strip('.,;:()[]')
        low = clean_kw.lower()
        if (
            not low
            or low in seen_lower
            or low in STOP
            or low in _GENERIC_FILLER_GAP_WORDS
            or len(low) < 3
        ):
            continue
        seen_lower.add(low)
        ordered_terms.append(clean_kw)

    resume_tech_lower = {m.group(0).strip().lower() for m in _TECH_TERM_RE.finditer(base_resume)}
    resume_kw_lower = keywords(base_resume)

    wording_gaps: list[dict[str, str]] = []
    skill_gaps: list[dict[str, Any]] = []

    for term in ordered_terms:
        low = term.lower()
        # Already literally present in base resume
        if low in resume_tech_lower or low in resume_kw_lower:
            continue
        # Adjacent or synonym evidence exists verbatim in candidate resume -> wording_gap
        evidence = _find_candidate_evidence(low, base_resume)
        if evidence:
            wording_gaps.append({
                'job_term': term,
                'candidate_evidence': evidence,
            })
            continue
        # Otherwise missing from base resume -> true_skill_gap (verified only if proof artifact exists)
        is_verified = low in verified_set
        skill_gaps.append({
            'skill_name': term,
            'gap_type': 'true_skill_gap',
            'micro_project_brief': _default_micro_project_brief(term, job),
            'verified': is_verified,
        })
        if len(skill_gaps) >= 8 and len(wording_gaps) >= 6:
            break

    return {
        'wording_gaps': wording_gaps[:8],
        'skill_gaps': skill_gaps[:8],
        'matched_keywords': list(match_out.get('shared_keywords') or []),
        'fit_score': int(match_out.get('score') or 0),
    }


def summarize_resume_diff(master_resume: str, tailored_resume: str, limit: int = 5) -> list[dict[str, str]]:
    """Produce concise diffs comparing master_resume lines against tailored_resume lines."""
    master_lines = [ln.strip() for ln in str(master_resume or '').splitlines() if ln.strip()]
    tailored_lines = [ln.strip() for ln in str(tailored_resume or '').splitlines() if ln.strip()]
    if not tailored_lines:
        return []
    if master_lines == tailored_lines:
        return []

    matcher = difflib.SequenceMatcher(None, master_lines, tailored_lines)
    diffs: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        orig_chunk = ' | '.join(master_lines[i1:i2])
        edit_chunk = ' | '.join(tailored_lines[j1:j2])
        if tag == 'insert':
            summary = f'Added tailored section/line: {edit_chunk[:120]}'
        elif tag == 'delete':
            summary = f'Trimmed line: {orig_chunk[:120]}'
        else:
            summary = f'Updated "{orig_chunk[:70]}" -> "{edit_chunk[:70]}"'
        diffs.append({
            'change_type': tag,
            'original': orig_chunk,
            'edited': edit_chunk,
            'summary': summary,
        })
        if len(diffs) >= limit:
            break
    return diffs


def generate_probe_questions(
    resume_text: str,
    tailored_text: str,
    job: Mapping[str, Any],
    verified_gap_proofs: Sequence[Mapping[str, Any]] = (),
) -> list[str]:
    """Generate 3 likely interviewer deep-dive questions tied to highlighted bullets and gap proofs."""
    combined_resume = str(tailored_text or resume_text or '').strip()
    lines = [ln.strip(' -*\t') for ln in combined_resume.splitlines() if len(ln.strip()) >= 18]
    job_title = str(job.get('title') or 'this role').strip()
    company = str(job.get('company') or 'the team').strip()
    job_desc = '\n'.join(
        str(job.get(f) or '') for f in ('title', 'requirements', 'description') if job.get(f)
    )
    shared = list((match_resume(combined_resume, job_desc).get('shared_keywords') or []))
    missing = list((match_resume(combined_resume, job_desc).get('unmatched_job_keywords') or []))

    questions: list[str] = []

    # Question 1: Metric-bearing or experience bullet probe
    metric_line = next(
        (ln for ln in lines if _extract_meaningful_metrics(ln)),
        lines[1] if len(lines) > 1 else (lines[0] if lines else ''),
    )
    if metric_line:
        snippet = metric_line[:110].rstrip('.')
        questions.append(
            f'Deep-dive on "{snippet}": What architectural trade-offs did you evaluate and how did you validate the outcome?'
        )

    # Question 2: Top role-overlap technical depth probe
    if shared:
        focus = ', '.join(shared[:3])
        questions.append(
            f'For {job_title} at {company}, describe a production bug, scaling limit, or edge case you solved involving {focus}.'
        )

    # Question 3: Verified proof-of-skill project OR priority gap readiness probe
    verified_list = [p for p in (verified_gap_proofs or ()) if str(p.get('skill_name') or '').strip()]
    if verified_list:
        proof = verified_list[0]
        skill = str(proof.get('skill_name')).strip()
        proof_url = str(proof.get('proof_url') or '').strip()
        ref = f' ({proof_url})' if proof_url else ''
        questions.append(
            f'You showcased verified proof-of-work in {skill}{ref}: what did you test to prove correctness and how would you extend it at scale?'
        )
    elif missing:
        gap_focus = ', '.join(missing[:2])
        questions.append(
            f'How would you ramp up on {gap_focus} during your first 30 days using the systems fundamentals already on your resume?'
        )

    defaults = [
        f'Which project on your tailored resume best demonstrates readiness for {job_title} at {company}, and why?',
        'Walk through how you debugged a failure from logs or metrics to root-cause fix and regression test.',
        'If given ambiguous requirements on week one, what clarifying questions and milestones would you propose?',
    ]
    for q in defaults:
        if len(questions) >= 3:
            break
        if q not in questions:
            questions.append(q)

    return questions[:3]

