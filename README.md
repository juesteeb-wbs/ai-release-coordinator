# AI Release Agent Demo

This repository demonstrates a GitHub-based AI Release Agent concept.

The first baseline release is a compact Python FastAPI support-ticket API. It is
intended to become the `v1.0.0` starting point for later release-agent evidence
collection and release-note generation demos.

## Phase 1 scope

Implemented in the baseline application:

- Create support tickets
- Retrieve a ticket by ID
- List support tickets
- Filter tickets by category, priority, and status
- Assign ticket category and priority
- Basic API-key authentication
- SQLite persistence
- Typed request and response validation
- Unit and API-level tests with `pytest`

Not included in Phase 1:

- n8n workflow implementation
- GitHub API integration
- release analysis
- publishing releases or modifying remote GitHub resources

## Requirements

- Python 3.11 or newer

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

If the virtual environment is created without pip, install through the global
pip launcher instead:

```powershell
python -m pip --python .\.venv\Scripts\python.exe install -e ".[dev]"
```

## Run the API

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload
```

The API uses these defaults for local development:

```text
SUPPORT_TICKET_API_KEY=dev-support-api-key
SUPPORT_DATABASE_PATH=support_tickets.sqlite3
```

Both values can be overridden with environment variables.

### Migration note

Starting with the `release/1.1.0` branch, API-key configuration uses
`SUPPORT_TICKET_API_KEY`. Deployments that previously set `SUPPORT_API_KEY` must
rename that environment variable before upgrading.

## Test

```powershell
.\.venv\Scripts\python -m pytest
```

## Dependency security note

The application declares a direct Starlette dependency floor of `>=0.40.0`.
Starlette `0.40.0` includes a fix for a denial-of-service issue in
`multipart/form-data` request parsing. FastAPI is constrained to `>=0.115.3`
because that release supports the Starlette `>=0.40.0` range.

## Collect release evidence

Phase 3 adds a read-only evidence collector for comparing the baseline tag with
the release branch. The collector reads GitHub evidence and writes local JSON; it
does not create releases, merge pull requests, push commits, or publish
anything.

For public repositories, unauthenticated requests may work. To avoid rate limits,
set a read-only GitHub token in the environment:

```powershell
$env:GITHUB_TOKEN="your-read-only-token"
```

The collector uses the operating system certificate store when available. If
your environment requires a custom certificate authority bundle, set:

```powershell
$env:GITHUB_CA_BUNDLE="C:\path\to\ca-bundle.pem"
```

Collect evidence for the demo release boundary:

```powershell
.\.venv\Scripts\python -m release_agent.cli collect-evidence `
  --owner juesteeb-wbs `
  --repo ai-release-agent-demo-v2 `
  --base-ref v1.0.0 `
  --target-ref release/1.1.0 `
  --release-version 1.1.0 `
  --output artifacts/evidence/release-1.1.0-evidence.json
```

The `artifacts/` directory is ignored because generated evidence may include
repository text, pull request text, and other untrusted data.

Analyze collected evidence and generate local draft artifacts:

```powershell
.\.venv\Scripts\python -m release_agent.cli analyze-evidence `
  --evidence-file artifacts\evidence\release-1.1.0-evidence.json `
  --output-dir artifacts\analysis\release-1.1.0
```

The analyzer is deterministic and rule-based in this phase. It produces
structured change records, claim records, release-note drafts, a technical
changelog, suggested regression tests, risk assessment, QA checklist, deployment
guidance, and missing-documentation warnings. AI-assisted analysis is planned
for a later phase.

The analysis output also includes review-focused fields for n8n:

```text
review_markdown
executive_summary
blocker_summary
warning_summary
artifact_summary
```

The CLI writes `review-preview.md` beside the other generated Markdown files.

## Run the release preview API

The preview API exposes the collector and analyzer through HTTP so local n8n
workflows can use an HTTP Request node instead of running shell commands.

Start the API:

```powershell
$env:GITHUB_TOKEN="your-read-only-token"
.\.venv\Scripts\python -m uvicorn release_agent.api:app --host 127.0.0.1 --port 8010 --reload
```

Preview a release analysis:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/release-analysis/preview `
  -ContentType "application/json" `
  -Body '{
    "repository_owner": "juesteeb-wbs",
    "repository_name": "ai-release-agent-demo-v2",
    "base_ref": "v1.0.0",
    "target_ref": "release/1.1.0",
    "release_version": "1.1.0",
    "release_mode": "preview",
    "publish_enabled": false
  }'
```

The endpoint is read-only. It does not publish releases, push commits, create
tags, merge pull requests, or modify GitHub resources.

### Release Coordinator dashboard

The same FastAPI service also includes a lightweight dashboard UI for local
human-review demos:

```text
http://127.0.0.1:8010/dashboard
```

The dashboard can prepare payloads locally without calling n8n. To let it trigger
the two local n8n workflows, configure webhook URLs before starting the API:

```powershell
$env:RELEASE_AGENT_PREVIEW_WEBHOOK_URL="http://localhost:5678/webhook/..."
$env:RELEASE_AGENT_REVIEW_WEBHOOK_URL="http://localhost:5678/webhook/..."
```

`RELEASE_AGENT_PREVIEW_WEBHOOK_URL` is used by the Create release briefing form.
`RELEASE_AGENT_REVIEW_WEBHOOK_URL` is used by the Submit human decision form.
Both actions remain preview-only and do not publish or modify GitHub resources.

To enable the Postgres-backed review queue and detail pages, configure:

```powershell
$env:RELEASE_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/database"
```

Then reinstall dependencies if needed:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

With the database URL configured, `/dashboard` lists active records from
`release_reviews`: pending reviews and completed reviews that have not been
processed yet. `/dashboard/reviews/{id}` shows the review details, Human Review
Card link, and reviewer decision form. Submitting the form updates the Postgres
row and can optionally call `RELEASE_AGENT_REVIEW_WEBHOOK_URL` for Workflow 2
processing.

Resolve the current SHA for a Git ref:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/release-analysis/resolve-ref `
  -ContentType "application/json" `
  -Body '{
    "repository_owner": "juesteeb-wbs",
    "repository_name": "ai-release-agent-demo-v2",
    "ref": "release/1.1.0"
  }'
```

n8n can call this endpoint before recording approval and compare the returned
`sha` with the analyzed `target_sha`. If the values differ, the target branch
moved and the workflow should require a fresh preview analysis.

Generate a demo AI-assisted review draft from an existing analysis response:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/release-analysis/ai-review-draft `
  -ContentType "application/json" `
  -Body '{
    "analysis": {
      "...": "analysis JSON returned by /release-analysis/preview"
    },
    "draft_mode": "demo"
  }'
```

This endpoint builds the AI input package, generates a structured demo draft,
and validates the draft against deterministic evidence rules. It does not call a
model yet. The demo generator is a safe stand-in for the later model call so the
workflow can be tested without adding AI credentials.

Build only the AI input package for a future model call:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/release-analysis/ai-input-package `
  -ContentType "application/json" `
  -Body '{
    "analysis": {
      "...": "analysis JSON returned by /release-analysis/preview"
    }
  }'
```

Validate structured AI review output:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/release-analysis/validate-ai-review `
  -ContentType "application/json" `
  -Body '{
    "ai_input_package": {
      "...": "AI input package returned by /release-analysis/ai-input-package"
    },
    "ai_review_draft": {
      "...": "structured AI output following docs/structured-ai-output-contract.md"
    }
  }'
```

These split endpoints are intended for the later model-backed n8n workflow:
n8n builds the input package, sends it to a model, then asks Python to validate
the model output before showing it to a reviewer.

## Endpoints

`GET /health` is public.

Ticket endpoints require an `X-API-Key` header:

```text
X-API-Key: dev-support-api-key
```

Available ticket endpoints:

```text
POST   /tickets
GET    /tickets
GET    /tickets/{ticket_id}
PATCH  /tickets/{ticket_id}
```

Supported ticket values:

```text
category: billing | technical | account | product | other
priority: low | medium | high | urgent
status: open | in_progress | resolved | closed
```

Example create request:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/tickets `
  -Headers @{ "X-API-Key" = "dev-support-api-key" } `
  -ContentType "application/json" `
  -Body '{
    "title": "Cannot access billing portal",
    "description": "The customer receives a permission error when opening invoices.",
    "customer_email": "alex@example.com",
    "category": "billing",
    "priority": "high"
  }'
```
