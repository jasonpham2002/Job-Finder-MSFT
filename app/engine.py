"""Deterministic, offline reference engine + A-02 URL/ATS extractors & D1 Pre-Flight Shield.

IMPORTANT: This engine does not submit applications, scrape LinkedIn, or send emails.
It never bypasses logins/CAPTCHAs, never invents resume details, and treats external job
text as untrusted data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import html
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
from typing import Any, Callable, Mapping, Optional
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
