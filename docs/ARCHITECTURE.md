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
   |   |     - /api/resumes (CRUD / Import)                                      |   |
    |   |     - /api/tailor/resume (Direct JD tailoring)                         |   |
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

### 3.2 PostgreSQL Resume Schema (Raw SQL)

```sql
CREATE TABLE resumes (
    id UUID PRIMARY KEY,
    parent_resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    is_baseline BOOLEAN NOT NULL DEFAULT FALSE,
    company_name TEXT,
    position TEXT,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

The application issues parameterized raw SQL queries to AWS RDS. ORM and SQLAlchemy abstractions are intentionally not used.

Generated PDFs are stored in Amazon S3. A PDF object is available only for preview/download or permanent deletion; it is not edited or exposed for unrelated object operations.

---

## 4. Primary Architecture Pipelines

### 4.1 Ingestion & Parsing Pipeline (Backend Core)
1. **User Uploads / Imports**: A standard raw JSON file matching the schema is validated using Pydantic. Simple contact strings (e.g. `"user@example.com"`) are automatically normalized into `{ "url": "...", "display": "..." }` structures.
2. **Manual Job-Description Input (Current Milestone)**: The client sends non-empty pasted text as `job_description` with the baseline resume to `POST /api/tailor/resume`.
    - Text is capped at **15,000 characters** before it is sent to the LLM, preventing context-window overflow.
    - The endpoint invokes the tailoring pipeline immediately; there is no URL ingestion, preview, approval, or persistence stage.

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
   - Instruct the LLM to tailor the baseline resume JSON to match the cleaned job description text.
   - Single LLM call executed via LiteLLM: primary model `gpt-4o-mini`, with automatic fallback to `gemini/gemini-1.5-flash`.
   - Returns structured output strictly validated against the `Resume` Pydantic model.
2. **Intelligent Reordering & Bullet Optimization**:
   - Reorders `skills` categories and `projects` so that skills and projects most relevant to the target job description appear first.
   - Places non-matching skills and projects at the bottom of their respective lists without deleting them.
   - Rewrites project bullet points using the **STAR method** to naturally integrate key target keywords.
3. **Guardrails**: No new degrees, institutions, project titles, or fabricated achievements are introduced.
4. **Stateful Persistence**: The resulting tailored JSON and its metadata are stored with parameterized raw SQL in the AWS RDS PostgreSQL `resumes` table and returned to the client.

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
| **POST** | `/api/resumes/` | Upload / Import new baseline structured resume | JSON Resume | Saved JSON Resume + `id` + metadata |
| **GET** | `/api/resumes/{id}` | Fetch specific stored resume | *None* | Stored JSON Resume + metadata |
| **PUT** | `/api/resumes/{id}` | Update stored resume JSON (Manual edit support) | JSON Resume | Updated JSON Resume |
| **GET** | `/api/resumes/` | List all stored resumes (baseline & tailored) | *None* | List of resume metadata summaries |
| **POST** | `/api/tailor/resume` | Tailor a resume using a pasted job description | `{ "job_description": "...", "baseline_resume": { ... } }` | Tailored resume JSON |
| **POST** | `/api/resumes/{id}/compile` | Escape JSON, compile it, and store the PDF in S3 | *None* | PDF metadata |
| **GET** | `/api/resumes/{id}/pdf` | Retrieve the generated PDF for preview or download | *None* | PDF stream |
| **DELETE** | `/api/resumes/{id}/pdf` | Permanently delete the generated PDF from S3 | *None* | Deletion confirmation |
