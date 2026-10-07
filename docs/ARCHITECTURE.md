# TailorDocs System Architecture & Technical Specifications

This document outlines the detailed system architecture, project folder structure, data models, compilation pipeline, and deployment strategies for **TailorDocs**.

---

## 1. System Topology Overview

TailorDocs is a modular service with a containerized Python backend and Rust-based Tectonic LaTeX engine. The backend uses raw SQL to persist resume JSON and metadata in PostgreSQL on AWS RDS, while generated PDFs are stored in Amazon S3.

```
   +---------------------------------------------------------------------------------+
   |                                 DOCKER CONTAINER                                |
   |                                                                                 |
   |   +-------------------------------------------------------------------------+   |
   |   |                           FastAPI Web Server                            |   |
   |   |                                                                         |   |
   |   |   [API Layer]                                                           |   |
    |   |     - /api/baseline-resumes (Save / list)                               |   |
     |   |     - /api/sessions (Explicit session save / retrieval)                |   |
     |   |     - /api/tailor/resume (Stateless tailoring)                         |   |
   |   |     - /api/compile (LaTeX compiler invoker)                             |   |
   |   |                                                                         |   |
   |   |   [Services Layer]                                                      |   |
    |   |     - analyzer.py  (Sentence embeddings mapping & TF-IDF scores)        |   |
   |   |     - tailorer.py  (LiteLLM client + Pydantic guardrails)               |   |
   |   |     - compiler.py  (Recursive sanitization & JSON-to-LaTeX runner)       |   |
   |   +--------------------------|-------------------|--------------------------+   |
   |                              |                   |                              |
   |                              v                   v                              |
   |                     +-----------------+ +-------------------+                   |
    |                     | AWS RDS         | |  Tectonic Engine  |                   |
    |                     | PostgreSQL      | | (Local executable |                   |
    |                     | (raw SQL)       | |  running inside)  |                   |
   |                     +-----------------+ +--------|----------+                   |
   |                                                  |                              |
   |                                                  v                              |
    |                                         [Amazon S3 PDF Storage]                 |
   +---------------------------------------------------------------------------------+
```

---

## 2. Project Folder Structure

The workspace directory is organized as a modular, cleanly-separated Python project:

```
tailordocs_server/
├── app/
│   ├── __init__.py
│   ├── main.py              # Application entrypoint & CORS setup
│   ├── api/                 # API Routes & Schema definitions
│   │   ├── __init__.py
│   │   ├── resumes.py       # Resume Upload, Retrieval, and Editing (CRUD)
│   │   └── tailor.py        # ATS alignment evaluation & tailoring pipeline
│   ├── core/                # Global configuration and PostgreSQL access
│   │   ├── __init__.py
│   │   ├── config.py        # Settings (API keys, directory paths, DB URLs)
│   │   ├── database.py      # Raw SQL PostgreSQL connection management
│   │   └── security.py      # LaTeX sanitization and string escaping utilities
│   ├── models/              # Pydantic request and response schemas
│   │   ├── __init__.py
│   │   ├── resume.py        # Resume validation schema
│   ├── services/            # Business Logic / Isolated Engine Pipelines
│   │   ├── __init__.py
│   │   ├── analyzer.py      # Keyword extraction & SentenceTransformer embeddings
│   │   ├── tailorer.py      # LLM structured prompt construction & execution
│   │   └── compiler.py      # Orchestrator for JSON-to-LaTeX translating and compiling
│   └── templates/           # Static LaTeX assets
│       └── resume.tex       # Blank Jake's Resume LaTeX layout source
├── docs/
│   ├── PRD.md               # Product Requirements Document
│   └── ARCHITECTURE.md      # This file
├── Dockerfile               # Production multi-stage Docker configuration (Python + Tectonic)
├── docker-compose.yml       # Local development composition orchestrator
├── README.md                # Quick-start instructions
└── requirements.txt         # Explicit system dependencies
```

---

## 3. Data Schema & Core Models

To prevent parsing or validation failures, we enforce a strict schema corresponding directly to Jake's Resume layout structure.

### 3.1 Resume JSON Schema (The Structured Data model)

```json
{
    "personal_info": {
        "name": "",
        "phone": "",
        "email": {
            "url": "",
            "display": ""
        },
        "linkedin": {
            "url": "",
            "display": ""
        },
        "github": {
            "url": "",
            "display": ""
        }
    },
    "objective": "",
    "education": [
        {
            "institution": "",
            "location": "",
            "degree": "",
            "duration": ""
        }
    ],
    "skills": [
        {
            "title": "",
            "items": []
        }
    ],
    "projects": [
        {
            "title": "",
            "tech_stack": "",
            "duration": "",
            "points": []
        }
    ]
}
```

### 3.2 PostgreSQL Persistence Schema (Raw SQL)

```sql
CREATE TABLE baseline_resumes (
    baseline_resume_id UUID PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    resume JSONB NOT NULL
);

CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    session_name VARCHAR(255) NOT NULL,
    job_description VARCHAR(15000) NOT NULL,
    baseline_resume_id UUID NOT NULL REFERENCES baseline_resumes(baseline_resume_id),
    baseline_jd_score SMALLINT,
    current_jd_score SMALLINT,
    current_resume JSONB NOT NULL
);
```

The application issues parameterized raw SQL queries through `psycopg`. ORM and SQLAlchemy abstractions are intentionally not used. Apply `db/schema.sql` explicitly to the local PostgreSQL database; migrations are not yet required.

Generated PDFs are stored in Amazon S3. A PDF object is available only for preview/download or permanent deletion; it is not edited or exposed for unrelated object operations.

---

## 4. Primary Architecture Pipelines

### 4.1 Ingestion & Parsing Pipeline (Backend Core)
1. **User Uploads / Imports**: A standard raw JSON file matching the schema is validated using Pydantic. Simple contact strings (e.g. `"user@example.com"`) are automatically normalized into `{ "url": "...", "display": "..." }` structures.
2. **Manual Job-Description Input (Current Milestone)**: The client sends non-empty pasted text as `job_description` with one Tailoring Input to `POST /api/tailor/resume`.
    - Text is capped at **15,000 characters** before it is sent to the LLM, preventing context-window overflow.
    - The endpoint invokes the tailoring pipeline immediately and returns a Current Resume without persisting it.

### 4.2 ATS Scoring & Semantic Mapping Pipeline
1. **Semantic Embedding Matrix**:
   - The system maps all responsibilities found in the job post against user project bullets and skills.
   - Computes cosine similarity scores locally via `Sentence-Transformers` (`all-MiniLM-L6-v2`).
2. **Keyword Matcher**:
   - Compares the set of technical, framework, and language keywords extracted from the job posting against the fields in the user's resume JSON (including project points and technical skills sections).
3. **Alignment Matrix Generation**:
   - Creates a mapping layout of which existing resume bullets are top-ranked matches for target job duties.
   - Calculates a combined benchmark percentage score reflecting actual alignment.

### 4.3 LLM Bullet Point & Resume Optimizer (Single-Call Flow)
1. **Context-Bounded Prompting**:
    - Instruct the LLM to tailor the Tailoring Input JSON to match the cleaned Job Description text.
   - Single LLM call executed via LiteLLM: primary model `gpt-4o-mini`, with automatic fallback to `gemini/gemini-1.5-flash`.
   - Returns structured output strictly validated against the `Resume` Pydantic model.
2. **Intelligent Reordering & Bullet Optimization**:
   - Reorders `skills` categories and `projects` so that skills and projects most relevant to the target job description appear first.
   - Places non-matching skills and projects at the bottom of their respective lists without deleting them.
   - Rewrites project bullet points using the **STAR method** to naturally integrate key target keywords.
3. **Guardrails**: No new degrees, institutions, project titles, or fabricated achievements are introduced.
4. **Explicit Persistence**: A user action saves a named Baseline Resume or a Tailoring Session with parameterized raw SQL. Tailoring responses are never persisted automatically.

### 4.4 LaTeX-Safe Compilation Pipeline
1. **Sanitization**: Before generating a LaTeX document, the tailored JSON is processed by a recursive sanitizer function to escape LaTeX reserved tokens:
   - `&` -> `\&`
   - `%` -> `\%`
   - `$` -> `\$`
   - `#` -> `\#`
   - `_` -> `\_`
   - `{` -> `\{`
   - `}` -> `\}`
   - `~` -> `\textasciitilde{}`
   - `^` -> `\textasciicircum{}`
   - `\` -> `\textbackslash{}`
2. **Translation**: A custom Python function reads the sanitized JSON structures and writes them directly into the Jake's Resume standard raw LaTeX document format.
3. **Tectonic Invocation**:
   - The compiled source `.tex` is written to a temporary location.
   - We trigger the local `tectonic` executable using a Python subprocess command.
    - The generated PDF is stored in Amazon S3. It can subsequently be retrieved for preview/download or deleted permanently.

---

## 5. Dockerization & Warmup Strategy

Tectonic is a modern, self-bootstrapping TeX engine that dynamically fetches packages on-demand from online repositories. To prevent runtime HTTP overhead or network blockages when compiling PDFs, the Docker image runs a **Warmup Stage**:

### Dockerfile Design Workflow
1. **Install Base Components**: Setup Debian/Alpine base, install Python 3.11, Rust/Tectonic, and compilation dependencies.
2. **Copy Empty Templates**: Inject standard Jake's Resume `resume.tex` containing mock data into the image.
3. **Warmup Compile**: Run `tectonic resume.tex` during the image building process (`docker build`).
4. **Caching Package Cache**: This mock compilation pulls all required packages (`geometry`, `hyperref`, `titlesec`, `enumitem`, `fancyhdr`, etc.) into Tectonic's local installation cache inside the image.
5. **Runtime Phase**: At runtime, Tectonic uses the cached assets locally. This yields ultra-fast, 100% offline document generation in sub-second times.

---

## 6. Endpoints API Design (FastAPI)

All `/api/...` endpoints require a Cognito User Pool access token. The API validates the token's signature against Cognito JWKS and verifies its issuer, expiration, token use, and app-client ID before deriving the User ID from its `sub` claim. FastAPI documentation and OpenAPI endpoints are disabled.

| Method | Endpoint | Description | Request Payload | Response Payload |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/baseline-resumes` | Save a named Baseline Resume | `{ "name": "...", "resume": { ... } }` | Baseline ID and name |
| **GET** | `/api/baseline-resumes` | List Baseline Resume IDs and names | *None* | List of IDs and names |
| **POST** | `/api/tailor/resume` | Tailor a pasted Job Description | `{ "job_description": "...", "baseline_resume_id": "..." }` or `{ "job_description": "...", "resume": { ... } }` | Current Resume JSON |
| **POST** | `/api/sessions` | Explicitly save a new Tailoring Session | Session name, Job Description, baseline ID, Current Resume | Session ID and name |
| **GET** | `/api/sessions` | List saved Tailoring Sessions | *None* | Session IDs and names |
| **GET** | `/api/sessions/{id}` | Load one saved Tailoring Session | *None* | Job Description, baseline ID, Current Resume |
| **PUT** | `/api/sessions/{id}` | Explicitly replace a saved Tailoring Session | Session name, Job Description, baseline ID, Current Resume | Session ID and name |
