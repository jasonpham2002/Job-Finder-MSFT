# Resume Tailoring Prompt

Inputs: original resume, verified fact inventory, target job description, desired format.

Instructions:
- Map every recommended accomplishment/skill bullet to a supported source fact. Leave metrics blank or request confirmation when missing.
- Use crisp action verbs, relevant terminology, and simple ATS-friendly headings.
- Do not create employment dates, metrics, certifications, degrees, technologies or achievements not present in verified input.
- Prioritize honest role-relevant points; present 1–2 page professional resume where practical.
- Output: tailored resume text; `changes` (original passage -> edited passage -> rationale); `evidence_map` (claim -> exact source); `unverified_claims` and `questions_for_candidate`.
- An employee in a similar role can suggest terminology or learning gaps but is never proof the candidate owns a skill.

For D2, map each changed claim to an exact candidate source and preserve candidate voice. For D5, separate wording gaps from skills that require proof. Keep unsupported claims outside the tailored resume.
