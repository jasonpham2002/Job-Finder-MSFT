# Judge Acceptance Tests (mandatory)

1. **Fresh setup:** New machine or clean environment; follow README without developer help. Import no private developer account data.
2. **New resume:** Use judge-provided fictional resume with PDF or DOCX input. Extract accurately. Verify no unsupported qualifications are introduced.
3. **LinkedIn URL:** Paste an accessible LinkedIn posting URL. If access is blocked or disallowed, demonstrate a clear paste-description fallback without bypassing controls.
4. **Indeed URL:** Repeat with Indeed job URL and normalize into same schema.
5. **Company ATS URL:** Use Workday, Greenhouse or Lever URL and show normalized details; use fallback when required.
6. **Unseen domain URL:** Judge chooses previously untested legitimate company careers page. Tool should attempt compliant extraction or explain a supported fallback; must not silently hallucinate data.
7. **Ten-job pipeline:** Display 10 distinct, relevant roles, tailored drafts, and their true states. Real submitted states must include evidence.
8. **Verified contact:** Show a publicly available professional profile, name, current title, source and reason to contact. Do not infer emails as verified.
9. **Outreach authorization:** Draft email and LinkedIn message; review/approve; use permitted sending integration or stage for manual send. Prevent duplicate outreach and respect opt-outs.
10. **Response classification:** Inject `sample_data/fictional_inbox.json`: classify positive human reply, automated receipt and rejection without confusing them.
11. **Portability:** Export ZIP, move to Computer B (or clean user account), configure new credentials, use a different resume and job URL, run smoke tests.
12. **Security:** Inspect exported ZIP for keys/cookies/private resumes; demonstrate safe logging and explicit consent. Ensure the UI never says demo submission is real.

## Pass criteria

Students should supply test results and report unsupported features. Core acceptance does not automatically mean the 10-real-applications target was reached; those submissions are independently verified under the rubric. Judges may substitute synthetic scenarios for non-compliant real-site actions, but those synthetic actions never count toward real-submission points.
