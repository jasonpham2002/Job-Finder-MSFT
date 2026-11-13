"""Deterministic, offline reference engine. Replace with verified AI and integrations.

IMPORTANT: This engine does not submit applications, scrape LinkedIn, or send emails.
It never invents resume details and treats external job text as untrusted data.
"""
import html
import json
import re
import socket
import ipaddress
from html.parser import HTMLParser
from urllib import request, parse, error

STOP = set('a an the and or to for of in at on by with from as is are be this that their our your you we i it have has will can must should ability experience work working team role position job jobs company candidate including strong excellent opportunity relevant required preferred responsible responsibilities years year degree skills knowledge hands hands-on using use an into plus through'.split())


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


def extract_public_job(url):
    """Best-effort public HTML + JobPosting JSON-LD; no login, no bypass, no LinkedIn scraping."""
    opener = request.build_opener(NoRedirect())
    current = url
    for _ in range(3):
        valid_public_url(current)
        req = request.Request(current, headers={'User-Agent': 'JobFinderHackathonStudentStarter/1.0 (educational; public pages only)', 'Accept': 'text/html'})
        try:
            with opener.open(req, timeout=6) as response:
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type.lower():
                    raise ValueError('This address did not return HTML. Paste the job description manually.')
                raw = response.read(600_000)
                decoded = raw.decode('utf-8', errors='replace')
                parser = JobParser()
                parser.feed(decoded)
                structured = _find_jobposting(parser.job_ld)
                if structured:
                    org = structured.get('hiringOrganization') or {}
                    orgname = org.get('name', '') if isinstance(org, dict) else ''
                    result = {'title': _text_from_html(structured.get('title', parser.metatitle or parser.title))[:200],
                              'company': _text_from_html(orgname)[:120],
                              'description': _text_from_html(structured.get('description', ''))[:12000],
                              'url': current, 'extraction': 'schema-org-jobposting'}
                else:
                    result = {'title': (parser.metatitle or parser.title)[:200], 'company': '',
                              'description': (' '.join(parser.text) or parser.description)[:12000],
                              'url': current, 'extraction': 'generic-html-needs-review'}
                if len(result['description']) < 70:
                    raise ValueError('Job content was not accessible. Paste the description manually.')
                return result
        except error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get('Location')
                if not location:
                    break
                current = parse.urljoin(current, location)
                continue
            raise ValueError(f'Website returned HTTP {exc.code}. Paste the description manually.') from exc
        except error.URLError as exc:
            raise ValueError('Could not reach the job page. Paste the description manually.') from exc
    raise ValueError('Redirect limit reached. Paste the job description manually.')
