# Resume Tailoring

This context manages a user's tailored resumes for specific job descriptions. A tailoring session keeps the source resume and its current tailored result together for comparison.

## Language

**Tailoring Session**:
A user-owned workspace for one job description, its baseline resume, and its current tailored resume. It is identified by a session ID; a user may create sessions with duplicate names or job descriptions.
_Avoid_: Resume record, generation

**Baseline Resume**:
A named, validated resume JSON saved by a user. It is never overwritten; editing creates another Baseline Resume. A Tailoring Session references one Baseline Resume, which remains unchanged within that session.
_Avoid_: Original resume, source document

**Current Resume**:
The latest validated resume JSON in a tailoring session. It may be changed after the session is created.
_Avoid_: Tailored resume, generated resume

**Tailoring Input**:
The validated resume JSON used for one tailoring request. A request may begin from a saved Baseline Resume or use a client-provided Current Resume from a prior request. It is not persisted unless the user explicitly saves a Tailoring Session.
_Avoid_: New baseline, generated resume

**Job Description**:
The nonblank text for the role targeted by a tailoring session, limited to 15,000 characters.
_Avoid_: JD, job post

**Baseline JD Score**:
The floored whole-number percentage measuring the baseline resume's similarity to the session's job description.
It is absent until score calculation is implemented.
_Avoid_: Baseline score

**Current JD Score**:
The floored whole-number percentage measuring the current resume's similarity to the session's job description. It is recalculated whenever the current resume changes.
It is absent until score calculation is implemented.
_Avoid_: Current score, improvement score

**User ID**:
The verified Cognito User Pool `sub` claim that identifies the owner of a tailoring session. It is not a JWT or a value supplied by the client.
_Avoid_: JWT, username, email
