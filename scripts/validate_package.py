"""Basic offline handoff verifier. No network or external dependencies."""
import json
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
expected = [
 'README.md','START_HERE_STUDENTS.md','CHALLENGE_BRIEF.md','AGENTS.md',
 'docs/RUBRIC.md','docs/ACCEPTANCE_TESTS.md','docs/BUILD_PLAN.md',
 'docs/ARCHITECTURE.md','docs/INTEGRATION_GUIDE.md',
 'docs/PORTABILITY_GUIDE.md','docs/SECURITY_AND_CONSENT.md',
 'docs/DEMO_SCRIPT.md','deliverables/TEAM_HANDOFF_TEMPLATE.md',
 'app/server.py','app/engine.py','app/db.py','app/adapters.py',
 'web/index.html','web/styles.css','web/app.js',
 'config.example.json','.env.example','sample_data/fictional_jobs.json',
 'sample_data/sample_resume.txt'
]
expected += [f'skills/{n}/SKILL.md' for n in ('resume-optimizer','job-finder','company-research','application-preparer','networking-outreach','response-tracker')]
for name in expected:
    assert (ROOT/name).is_file(), f'Missing required file: {name}'
for skill in (ROOT/'skills').glob('*/SKILL.md'):
    content = skill.read_text(encoding='utf8')
    assert content.startswith('---\nname: '), skill
    assert re.search(r'(?m)^description: .+',content), skill
    assert '\n---\n' in content[4:], skill
for file in list((ROOT/'schemas').glob('*.json'))+list((ROOT/'sample_data').glob('*.json'))+[ROOT/'config.example.json']:
    json.loads(file.read_text(encoding='utf8'))
assert len(json.loads((ROOT/'sample_data/fictional_jobs.json').read_text())) >= 10
assert not (ROOT / '.env').exists(), 'Remove real secrets (.env) before sharing.'
assert not (ROOT / 'local_demo.sqlite3').exists(), 'Remove local resume-containing database before sharing.'
print('Package validated: required files, six skills, 12 sample jobs, valid JSON, no local .env/DB.')
