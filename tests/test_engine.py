import unittest
from app.engine import match_resume, draft_resume, draft_message, JobParser, _find_jobposting, valid_public_url


class EngineTests(unittest.TestCase):
    def test_overlap_transparent(self):
        output = match_resume('Excel reporting SQL dashboards', 'SQL reporting dashboards and Excel knowledge')
        self.assertIn('sql', output['shared_keywords'])
        self.assertTrue(0 <= output['score'] <= 100)

    def test_resume_keeps_original(self):
        original = 'Jordan has verified SQL and Excel reporting experience.'
        job = {'title':'Analyst','company':'Test','description':'Excel dashboards and SQL'}
        draft = draft_resume(original,job)
        self.assertIn(original,draft)
        self.assertNotIn('10 years experience',draft)

    def test_message_is_draft(self):
        out = draft_message({'name':'Taylor Morgan','role':'Recruiter'},
             {'title':'Analyst','company':'Test','description':'SQL'}, 'SQL experience')
        self.assertEqual(out['status'],'draft')
        self.assertIn('Taylor',out['body'])
        self.assertEqual(out['channel'],'email')

    def test_public_parser_schema_org(self):
        parser=JobParser()
        parser.feed('''<html><title>Careers</title><script type="application/ld+json">{"@type":"JobPosting","title":"Analyst","description":"Build analytics dashboards"}</script><p>Hello</p></html>''')
        self.assertEqual(_find_jobposting(parser.job_ld)['title'],'Analyst')

    def test_public_host_validation_blocks_local(self):
        for addr in ['file:///etc/passwd','http://127.0.0.1/secret','http://localhost:8080/', 'ftp://example.com']:
            with self.subTest(addr=addr), self.assertRaises(ValueError):
                valid_public_url(addr)


if __name__=='__main__':
    unittest.main()
