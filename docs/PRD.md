# TailorDocs Product Requirements Document (PRD)

## 1. Executive Summary
TailorDocs is a high-performance, automated resume and cover letter tailoring tool designed for modern job seekers. It optimizes the job application process by extracting key requirements from target job descriptions, running semantic and keyword alignment analysis against an existing JSON-formatted resume, and dynamically rewriting and formatting optimized resumes and cover letters. By using a pre-configured LaTeX compiler (Tectonic) inside Docker, TailorDocs achieves clean typography and 100% readable Applicant Tracking System (ATS) outputs.

---

## 2. Goals & Objectives
* **Automation**: Reduce manual resume-matching and editing time by 70%.
* **ATS Compatibility**: Produce industry-standard resumes formatted in LaTeX (using Jake's Resume template) that parse flawlessly in standard ATS platforms (Lever, Workday, Greenhouse).
* **Control**: Store intermediate and final resume data in structured JSON, allowing users/frontend to edit, review, and adjust contents before compiling (Stateful Editing Flow).
* **Zero Hallucination**: Restrict the LLM to rewriting existing bullet points to target job requirements using the STAR method (Situation, Task, Action, Result) without generating fictitious credentials or experience.

---

## 3. Scope & Target Audience
- **Target Audience**: Software engineers, technical managers, and corporate professionals applying to competitive roles.
- **In-Scope**:
  - Structured JSON resume ingestion and validation against Jake's Resume JSON Schema (Personal Info, Objective, Education, Skills, and Projects).
  - Normalization of contact details (strings to `{ "url": "...", "display": "..." }` objects).
  - Current milestone: direct manual job-description input with a 15,000-character budget before LLM tailoring.
   - Cognito User Pool access-token authentication for all API endpoints; the verified `sub` identifies the user.
  - LLM-based targeted resume tailoring (via LiteLLM with `gpt-4o-mini` primary and `gemini/gemini-1.5-flash` fallback) using zero-hallucination guardrails and priority reordering.
   - Explicit tailoring persistence: raw SQL access to PostgreSQL stores named Baseline Resumes and Tailoring Sessions. A session references its selected Baseline Resume and stores its Current Resume. No ORM or SQLAlchemy is used.
  - Recursive LaTeX-safe sanitization of all string outputs to prevent compilation failure.
  - Execution of a Python JSON-to-LaTeX translation script.
  - Compilation of LaTeX source into polished PDF via Tectonic in Docker and storage of the generated PDF in Amazon S3 for preview, download, or permanent deletion.
- **Out-of-Scope**:
  - Work experience ("experience") section (intentionally omitted in current version; project-focused layout).
  - Multi-user team collaboration tools and full-scale OAuth provider setup.
  - DOCX or HTML editing inside the app (the definitive source of truth is JSON, and final output is PDF).

---

## 4. Key Functional Requirements

### FR-1: JSON Resume Ingestion & Validation
* The system must accept an uploaded JSON file and validate it against the rigid schema corresponding to Jake's Resume layout.
* Supported sections: `personal_info`, `objective`, `education`, `skills`, and `projects`.
* Ingestion must automatically normalize string contact identifiers (email, LinkedIn, GitHub) into `{ "url": "...", "display": "..." }` object structures.

### FR-2: Manual Job-Description Input
* The tailoring endpoint accepts a manually pasted `job_description` plus either a saved Baseline Resume ID or a client-provided Tailoring Input.
* Job-description text must be non-empty and is capped at 15,000 characters before LLM tailoring. Tailoring does not persist its input or Current Resume automatically.

### FR-3: Local Semantic Alignment & Scoring
* Map individual job requirements to relevant resume sections and skills.
* Generate a comprehensive "ATS Alignment Score" reflecting keyword density, semantic coverage, and formatting structure.

### FR-4: Bullet Point & Section Tailoring (LLM-based)
* A single LLM call is executed with LiteLLM (primary: `gpt-4o-mini`, fallback: `gemini/gemini-1.5-flash`), taking both the cleaned Job Description text and validated Tailoring Input JSON.
* **Zero-Hallucination Constraint**: The LLM must not invent new degrees, institutions, project titles, or fake metrics.
* **Intelligent Reordering**: Reorders skills and projects such that items and bullet points matching the target job description appear at the top, while non-matching items are preserved but moved to the bottom of their respective lists.
* Rewrites project bullet points using the STAR method (Situation, Task, Action, Result) integrating relevant keywords from the job description.

### FR-5: Stateful Resume and PDF Lifecycle
* Save Baseline Resume JSON in `baseline_resumes` and Tailoring Session data in `sessions` using raw SQL. Do not use an ORM or SQLAlchemy.
* A session stores its user owner, name, Job Description, selected baseline foreign key, Current Resume JSON, and nullable JD scores.
* The user explicitly saves Baseline Resumes and Tailoring Sessions; no tailoring response is stored automatically.

### FR-6: LaTeX-Safe Compilation Pipeline
* Traversed recursively, all string properties of the JSON must be sanitized to escape LaTeX control characters (`&`, `%`, `$`, `_`, `{`, `}`, `~`, `^`, `\`).
* A Python script must translate the sanitized JSON fields directly into a populated LaTeX source file.
* Invoke `tectonic` inside the Docker runtime to compile the LaTeX source to a production-quality PDF.

---

## 5. Non-Functional Requirements
* **Determinism & Stability**: The system must enforce that the generated JSON always parses cleanly, sanitizes correctly, and compiles without throwing LaTeX environment errors.
* **Performance**: PDF compilation must happen in sub-second latency at runtime. This is achieved by pre-installing and caching LaTeX packages (via a mock compilation) during the Docker image build phase.
* **Portability**: Code and system dependencies must be fully encapsulated within a single Dockerfile containing Python 3.11 and the Tectonic compiler CLI.

---
## 6. Strict Constraints & Out of Scope
> AI Instruction: DO NOT build the following features under any circumstances.
- **No social features:** Users cannot share resume or see other users.
- **No payment structures:** do not implement any billing logic
- **No complex media:** only support for text, no photos, videos, or emojis

## 7. Success Criteria
1. Successfully parse, analyze, rewrite, and compile a resume PDF in under 10 seconds total pipeline execution.
2. Ensure 0% LaTeX compiler crash rates due to unescaped special characters.
3. Validate that output PDFs have a 100% success rate under automated parser scans.
