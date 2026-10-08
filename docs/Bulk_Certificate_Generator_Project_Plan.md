# Bulk Certificate Generator: Production-Level Project Plan

> A complete checklist of what to build, in priority order: required features first, then production hardening, then "wow" features the reviewers won't expect, then AI/ML extras.

**Golden rule:** finish Tier 1 completely and cleanly before touching anything else. The assignment says optional features must not come at the cost of required ones. Every feature you add is something you may be asked to explain or modify live in the interview.

---

## 1. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Required |
| Framework | **FastAPI** | Async, auto OpenAPI docs, Pydantic validation |
| Database | **PostgreSQL** (SQLite for quick local dev/tests) | Relational DB required |
| ORM / Migrations | SQLAlchemy 2.0 + Alembic | Standard, explainable |
| Background jobs | **Celery + Redis** (fallback: ARQ or FastAPI BackgroundTasks) | True bulk processing, retries |
| PDF generation | **ReportLab** or **WeasyPrint** (HTML/CSS to PDF) | Pure Python, one fixed template |
| QR codes | `qrcode` + `Pillow` | Verification feature |
| File storage | Local disk behind a **storage interface** (S3/MinIO-ready) | Swap storage without changing logic |
| Testing | pytest, pytest-asyncio, httpx, factory-boy, coverage | Required test areas |
| Quality | ruff, black, mypy, pre-commit | Production hygiene |
| Packaging | Docker + Docker Compose | One-command run |
| CI | GitHub Actions | Lint + test on every push |

---

## 2. Tier 1: Required Features (Must Be Perfect)

### 2.1 Create a generation job (bulk)
- `POST /api/v1/jobs`: accepts a list of recipients plus certificate info (event/course name, date, issuer, etc.) in a single request.
- Returns `202 Accepted` with `job_id` and a status URL (no per-certificate requests).
- Enforce a max recipients per request (e.g. 5,000) and return a clear `413`/`422` beyond it.

### 2.2 Validation
- Pydantic schemas for every field: name (required, length limits), email (valid format), course/event, date (valid and not absurd), optional grade/score.
- **Per-recipient validation**: one bad row must not reject the whole job. Valid rows are accepted and invalid rows are recorded with a reason.
- Return a validation summary: `accepted: 480, rejected: 20` plus row-level errors (`row 17: invalid email`).
- Sanitize input (strip control characters, normalize whitespace, guard against PDF/HTML injection).

### 2.3 Certificate generation (single predefined template)
- One polished template with recipient name, course/event, date, issuer, unique certificate ID, and signature line.
- Generate one PDF per valid recipient.
- Handle long names (auto-shrink font to fit) and Unicode names.

### 2.4 Status & progress tracking
- Job states: `PENDING → PROCESSING → COMPLETED | COMPLETED_WITH_ERRORS | FAILED`
- Item states: `PENDING → PROCESSING → SUCCESS | FAILED | INVALID`
- `GET /api/v1/jobs/{job_id}`: returns total, succeeded, failed, invalid, percent complete, timestamps.

### 2.5 Failure isolation
- One failed certificate never stops the others (try/except per item, committed independently).
- Store the error message and error type per failed item.
- `GET /api/v1/jobs/{job_id}/failures`: lists only failed items with reasons.

### 2.6 Retrieve certificates
- `GET /api/v1/jobs/{job_id}/certificates`: paginated list with status and download links.
- `GET /api/v1/certificates/{certificate_id}/download`: single PDF.
- `GET /api/v1/jobs/{job_id}/download`: **all certificates as one ZIP** (streamed, not built in memory).

### 2.7 Tests (the 6 required areas, plus more)
1. Creating a job
2. Input validation
3. Certificate generation (PDF is created, non-empty, contains the recipient's data)
4. Job status/progress
5. Individual certificate failure handling (simulate a failure by mocking the generator)
6. Retrieving certificates (single and ZIP)

### 2.8 README (required content)
Setup, running, tests, example requests (curl), retrieving certificates, and design decisions (sync vs. background processing, with reasoning).

---

## 3. Tier 2: Production Hardening

These are what make it production-level instead of assignment-level.

### Reliability
- **Idempotency keys**: `Idempotency-Key` header so a retried request never creates duplicate jobs.
- **Retry with exponential backoff** for transient failures (storage, etc.). Don't retry permanent errors such as invalid data.
- **Retry failed only**: `POST /jobs/{id}/retry-failed` regenerates only the failed items.
- **Job cancellation**: `POST /jobs/{id}/cancel` stops pending items cleanly.
- **Chunked processing**: split large jobs into batches (e.g. 100 per Celery task) and process in parallel.
- **Atomic progress counters**: no race conditions when multiple workers update the same job.
- **Graceful worker shutdown** and stuck-job recovery (a job in `PROCESSING` for too long is requeued).

### Security
- **API key authentication** (hashed keys in the DB) and per-client job ownership. Clients only see their own jobs.
- **Rate limiting** per API key.
- Input size limits, file path traversal protection, safe filenames.
- Secrets via environment variables (`.env.example` committed, `.env` ignored).
- CORS config, security headers.

### Observability
- **Structured JSON logging** with a `request_id` and `job_id` on every log line.
- `/health` (liveness) and `/ready` (DB + Redis check).
- **Prometheus metrics** (`/metrics`): jobs created, certificates generated, failures, generation time.
- Audit log table: who created, retried, cancelled, or downloaded what.

### API quality
- API versioning (`/api/v1`), consistent error format (`{code, message, details}`), pagination and filtering (`?status=FAILED`), and OpenAPI docs with examples.

### Data & ops
- Alembic migrations, DB indexes on `job_id`, `status`, `certificate_code`.
- **Data retention**: auto-delete certificates after N days (config), plus a cleanup task.
- Dockerfile (multi-stage, non-root user), `docker-compose.yml` (api, worker, db, redis), and a `Makefile` (`make up`, `make test`, `make lint`).
- GitHub Actions CI: lint, type-check, tests, coverage threshold.

---

## 4. Tier 3: "Unexpected" Features (Reviewer Wow Factor)

Pick the ones you can explain confidently. The top five are marked ⭐.

### ⭐ 4.1 QR-code certificate verification
- Every certificate gets a unique ID (e.g. `CERT-2026-8F3K2A`) and a QR code that links to a public page.
- `GET /verify/{certificate_code}` shows: valid or invalid, recipient, course, issue date, issuer.
- Anyone can check authenticity, which solves the real-world problem of fake certificates.

### ⭐ 4.2 Tamper-proof digital signatures
- Sign each certificate's data with **HMAC-SHA256** (or Ed25519) and embed the signature in the QR/URL.
- The verify endpoint recomputes the signature and detects altered data.
- Embed metadata into the PDF (title, author, certificate ID).

### ⭐ 4.3 Certificate revocation
- `POST /certificates/{id}/revoke` with a reason. The verify page then shows "Revoked".
- Real-world need (issued by mistake, fraud) that most submissions skip.

### ⭐ 4.4 Dry-run / preview mode
- `POST /jobs?dry_run=true` validates everything and returns what *would* happen without generating anything.
- `GET /template/preview?name=...`: returns a sample PDF so the client can check the design first.

### ⭐ 4.5 Real-time progress streaming
- `GET /jobs/{id}/events` using **Server-Sent Events (SSE)** or WebSocket. The client sees live progress without polling.

### 4.6 Webhooks
- Client registers a `callback_url`. On job completion we `POST` a signed payload (HMAC header) with retries on failure.

### 4.7 Email delivery
- Option `send_email: true` emails each certificate to its recipient (SMTP / SendGrid / Mailpit for dev).
- Track per-recipient delivery status (`SENT`, `BOUNCED`).

### 4.8 CSV / Excel upload
- `POST /jobs/upload` accepts a `.csv`/`.xlsx` with recipients, with a downloadable sample file and row-level error report.

### 4.9 Multiple output formats
- PDF plus PNG preview (and a thumbnail) for each certificate.

### 4.10 Open Badges / LinkedIn integration
- Generate an "Add to LinkedIn profile" link per certificate.
- Optional **Open Badges 3.0 / Verifiable Credential JSON** export, a recognized standard that shows domain awareness.

### 4.11 Deduplication & job fingerprinting
- Detect duplicate recipients within a job (same email + course) and flag or skip them.
- Hash each job's input so identical re-submissions are detected.

### 4.12 Multi-language & font support
- Detect the script of each name (Latin, Devanagari, Arabic, CJK) and pick a matching font so names never render as empty boxes. Relevant for Indian-language names (Hindi, Gujarati, etc.).

### 4.13 Storage abstraction
- `StorageBackend` interface with `LocalStorage` and `S3Storage` implementations (MinIO in Docker). Download via **pre-signed expiring URLs**.

### 4.14 Admin analytics endpoint
- `GET /stats`: certificates per day, success rate, average generation time, top failure reasons.

### 4.15 Simple web dashboard (optional)
- Minimal static page or Swagger-only is fine. A tiny HTML page to upload a CSV and watch progress is a strong demo.

---

## 5. Tier 4: AI / ML Features

Design rule for all AI features: **they must be optional, fail safe, and never block the core flow.** If the AI service is down, the job still completes using rule-based fallbacks. Say this explicitly in the README, since it shows mature engineering.

### ⭐ 5.1 Smart name normalization & validation
- Fix casing (`jOHN DOE` → `John Doe`, `mcdonald` → `McDonald`), strip stray symbols/emojis, and fix common whitespace problems.
- Flag suspicious names (`asdf`, `test123`, `xxx`, all digits) using heuristics + a lightweight classifier or LLM check.
- Return suggestions as `"suggested_fix"` rather than silently changing data (keeps humans in control).

### ⭐ 5.2 Fuzzy duplicate detection
- Use `rapidfuzz` (or embeddings) to catch near-duplicates: `Rahul Sharma` vs `Rahul Sharmaa` with the same email domain.
- Output a "possible duplicates" report per job.

### ⭐ 5.3 Email typo detection & auto-correction suggestions
- `gmial.com → gmail.com`, `yahho.com → yahoo.com`. Use edit-distance against common domains plus MX record checks (optional).

### ⭐ 5.4 AI-personalized achievement text
- Given course name + optional grade/score, an LLM (Claude API) generates a short, professional line for the certificate, e.g. *"…for outstanding performance in Advanced Python Programming."*
- Strictly constrained prompt, length limit, content filter, and **cached per unique (course, grade band)** so 1,000 recipients ≠ 1,000 LLM calls.
- Fallback: a static template sentence when AI is unavailable.

### ⭐ 5.5 Natural-language job creation
- `POST /jobs/from-text`: *"Make certificates for everyone in this list who completed the Python workshop on 5 Oct"* with pasted raw text. An LLM extracts a structured job, which is **validated by the same Pydantic schemas** and shown for confirmation (dry-run) before generation.

### 5.6 Smart column mapping for CSV/Excel
- Uploaded sheets with messy headers (`Full Name`, `Participant`, `E-mail ID`, `Mail`) are mapped automatically to the required fields. Use fuzzy matching first and an LLM as a fallback. The user confirms the mapping.

### 5.7 Anomaly detection on jobs
- Flag unusual jobs: sudden huge volume, many invalid emails, many duplicates, repeated near-identical names (possible spam or abuse). Start with simple statistical rules (z-score) and describe how a model could replace them.

### 5.8 Certificate OCR verification (stretch)
- Upload a scanned/photographed certificate and extract the certificate ID/QR with `pyzbar` / OCR (Tesseract) to verify it automatically.

### 5.9 Failure root-cause summarizer
- After a job with failures, produce a plain-English summary: *"12 failures: 9 due to invalid email format, 3 due to unsupported characters in name."* Can be rule-based aggregation, with optional LLM wording.

**Responsible-AI notes to put in the README:** only send non-sensitive fields to external AI APIs, cache results, set timeouts, add a feature flag per AI feature (`AI_NAME_CLEANUP=true`), and log AI suggestions separately from user data.

---

## 6. Data Model

```
clients            id, name, api_key_hash, created_at
jobs               id, client_id, status, total, succeeded, failed, invalid,
                   idempotency_key, input_hash, callback_url, dry_run,
                   created_at, started_at, completed_at
certificates       id, job_id, certificate_code (unique), recipient_name,
                   recipient_email, course_name, issue_date, extra (JSON),
                   status, error_type, error_message, file_path,
                   signature, revoked_at, revoke_reason, attempts,
                   created_at, generated_at
validation_errors  id, job_id, row_index, field, message, raw_value
audit_logs         id, client_id, action, entity_type, entity_id, meta, created_at
webhook_deliveries id, job_id, url, status_code, attempts, last_error
```

**Indexes:** `certificates(job_id, status)`, `certificates(certificate_code)`, `jobs(client_id, created_at)`, `jobs(idempotency_key)`.

---

## 7. API Endpoint Summary

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/jobs` | Create bulk job (JSON) |
| POST | `/api/v1/jobs/upload` | Create job from CSV/Excel |
| POST | `/api/v1/jobs/from-text` | AI: job from natural language |
| GET | `/api/v1/jobs` | List jobs (filter/paginate) |
| GET | `/api/v1/jobs/{id}` | Status & progress |
| GET | `/api/v1/jobs/{id}/events` | Live progress (SSE) |
| GET | `/api/v1/jobs/{id}/certificates` | List certificates |
| GET | `/api/v1/jobs/{id}/failures` | Failures & validation errors |
| GET | `/api/v1/jobs/{id}/download` | ZIP of all certificates |
| POST | `/api/v1/jobs/{id}/retry-failed` | Retry failed items |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel job |
| GET | `/api/v1/certificates/{id}/download` | Single PDF |
| POST | `/api/v1/certificates/{id}/revoke` | Revoke |
| GET | `/verify/{code}` | Public verification page |
| GET | `/api/v1/template/preview` | Sample certificate |
| GET | `/api/v1/stats` | Analytics |
| GET | `/health`, `/ready`, `/metrics` | Ops |

---

## 8. Suggested Project Structure

```
bulk-certificate-generator/
├── app/
│   ├── main.py
│   ├── api/v1/            # routers: jobs, certificates, verify, stats
│   ├── core/              # config, security, logging, errors
│   ├── db/                # session, base, models
│   ├── schemas/           # Pydantic models
│   ├── services/          # job_service, validation_service, certificate_service
│   ├── generators/        # pdf_generator.py, template assets, fonts
│   ├── storage/           # base.py, local.py, s3.py
│   ├── workers/           # celery_app.py, tasks.py
│   ├── ai/                # name_cleaner, dedupe, email_fixer, text_writer, nl_job
│   └── utils/
├── migrations/            # Alembic
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── docs/                  # architecture diagram, ADRs
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── .env.example
├── pyproject.toml
└── README.md
```

**Layering rule:** routers handle HTTP only, services hold business logic, and generators/storage are swappable. This makes the code easy to explain and modify in the interview.

---

## 9. Testing Plan

| Area | Examples |
|---|---|
| Job creation | Valid job returns 202 and creates DB rows; max-size enforced; idempotency key returns the same job |
| Validation | Bad email, empty name, future/invalid date; mixed valid and invalid rows |
| Generation | PDF exists, is valid, contains name and certificate code; Unicode names work |
| Status/progress | Counters update correctly; final state is correct for all-success, partial, and all-fail |
| Failure isolation | Mock the generator to raise on item 3, so items 1, 2, 4, 5 still succeed |
| Retrieval | Single download, ZIP download, 404 for unknown IDs, access denied for another client's job |
| Verification | Valid code verifies; tampered signature fails; revoked cert shows revoked |
| AI features | Mock the LLM; confirm the fallback works when the AI call times out |
| Concurrency | Two workers updating counters don't corrupt totals |

Target: **85%+ coverage**, run in CI.

---

## 10. README Checklist

- [ ] Project overview and feature list
- [ ] Architecture diagram (API → Redis → Worker → DB/Storage)
- [ ] Setup (Docker and local), `.env` explanation
- [ ] Run the app, run the worker, run the tests
- [ ] Example `curl` for: create job, check status, list certificates, download one, download ZIP
- [ ] Design decisions: **why background processing** (sync would time out on large batches, and workers allow retries and scaling), why PostgreSQL, why Celery, why PDF library X
- [ ] Failure-handling strategy
- [ ] Security notes
- [ ] AI features: what they do, flags, fallbacks, privacy
- [ ] Known limitations and future scope

---

## 11. Build Roadmap

| Phase | Goal | Outcome |
|---|---|---|
| **1** | Project skeleton, config, DB models, migrations, Docker | App boots with `/health` |
| **2** | Validation + job creation + PDF generator (sync first) | Core flow works end-to-end |
| **3** | Move to Celery workers, status tracking, failure isolation | Real bulk processing |
| **4** | Retrieval: list, single download, ZIP | All required endpoints done |
| **5** | Tests for all 6 required areas + README | **Submittable assignment** |
| **6** | Hardening: auth, idempotency, retries, logging, CI | Production-level |
| **7** | QR verification, signatures, revocation, preview/dry-run | Wow features |
| **8** | CSV upload, SSE progress, webhooks, email | Real-world polish |
| **9** | AI features (5.1 to 5.4 first, with fallbacks) | Differentiator |
| **10** | Final cleanup, diagrams, demo video/GIF, future-scope section | Portfolio-ready |

---

## 12. Interview Preparation

Be ready to answer or live-code:

1. Why background jobs instead of synchronous generation? What changes if volume grows 100×?
2. How do you guarantee one failure doesn't affect others? Show the exact code.
3. How do you avoid duplicate jobs on a client retry? (Idempotency key)
4. How does the signature work, and what attack does it stop?
5. How would you switch from local storage to S3? (Show the interface)
6. "Add a second certificate template", so where does the change go?
7. "Add a `grade` field", so what needs to change (schema, model, migration, template, tests)?
8. How does the AI fallback work if the API is down?
9. How would you scale workers and what is the bottleneck? (PDF CPU time, DB writes)

---

## 13. Suggested "Must-Have + Wow" Shortlist

If time is limited, this combination gives maximum impact with manageable effort:

**Core (Tier 1)** → **Celery + retries + idempotency** → **QR verification with signatures** → **Revocation** → **Dry-run & preview** → **CSV upload** → **SSE progress** → **AI name cleanup + fuzzy duplicates + email-typo fix + AI-written achievement line (with fallbacks)** → **Docker + CI + 85% coverage**

Build it phase by phase, commit often with clear messages, and keep every feature small, tested, and documented.
