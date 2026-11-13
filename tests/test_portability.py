import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PortabilityTests(unittest.TestCase):
    def test_six_skills_valid_frontmatter(self):
        files = sorted((ROOT/'skills').glob('*/SKILL.md'))
        self.assertEqual(len(files),6)
        for file in files:
            text = file.read_text(encoding='utf8')
            self.assertTrue(text.startswith('---\nname: '))
            self.assertIn('\ndescription: ',text)

    def test_offline_jobs_are_fictional(self):
        jobs=json.loads((ROOT/'sample_data/fictional_jobs.json').read_text())
        self.assertEqual(len(jobs),12)
        self.assertTrue(all('(Fictional)' in job['company'] for job in jobs))
        self.assertTrue(all(job['url'].startswith('https://example.com/') for job in jobs))

if __name__=='__main__':
    unittest.main()
