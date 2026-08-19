# AI Release Coordinator

This repository contains the Python side of an AI-assisted Release Coordinator.
It is separated from the demo application repository so the coordinator can
eventually be installed and used against any GitHub repository.

The coordinator is preview-only. It collects release evidence, prepares review
artifacts, validates structured AI output, serves a local dashboard, and keeps
the final decision human-owned and auditable. It does not publish releases,
create tags, merge pull requests, deploy code, or modify GitHub resources.

## Repository Split

The project is intentionally split into two roles:

```text
Target repository
- application code
- release branches and tags
- pull requests and CI evidence

Release Coordinator repository
- GitHub evidence collection
- deterministic analysis helpers
- AI input/output validation
- local FastAPI API
- dashboard for human review
- n8n workflow documentation
```

For the current demo, the target repository is:

```text
juesteeb-wbs/ai-release-agent-demo-v2
```

See [docs/repository-separation.md](docs/repository-separation.md) for the
separation plan.

## Requirements

- Python 3.11 or newer
- A read-only GitHub token for evidence collection
- Optional: PostgreSQL for the dashboard review queue
- Optional: n8n for the workflow orchestration demo

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

If the virtual environment is created without pip, install through the global
pip launcher instead:

```powershell
python -m pip --python .\.venv\Scripts\python.exe install -e ".[dev]"
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Run the Local API

Set a read-only GitHub token before starting the API:

```powershell
$env:GITHUB_TOKEN="your-read-only-token"
.\.venv\Scripts\python.exe -m uvicorn release_agent.api:app --host 0.0.0.0 --port 8010 --reload
```

When n8n runs in Docker, call the API from n8n through:

```text
http://host.docker.internal:8010
```

When calling from the Windows host directly, use:

```text
http://127.0.0.1:8010
```

## Preview a Release

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

The endpoint returns the release analysis and an AI input package derived from
GitHub evidence. The request is read-only and requires `publish_enabled` to be
`false`.

## AI Workflow Endpoints

Build an AI input package from an analysis response:

```text
POST /release-analysis/ai-input-package
```

Validate structured AI review output:

```text
POST /release-analysis/validate-ai-review
```

Generate a deterministic demo AI review draft without calling a model:

```text
POST /release-analysis/ai-review-draft
```

The structured AI output contract is documented in
[docs/structured-ai-output-contract.md](docs/structured-ai-output-contract.md).

## Dashboard

Open the local dashboard at:

```text
http://127.0.0.1:8010/dashboard
```

The dashboard can trigger n8n workflows when webhook URLs are configured:

```powershell
$env:RELEASE_AGENT_PREVIEW_WEBHOOK_URL="http://localhost:5678/webhook/release-agent-preview"
$env:RELEASE_AGENT_REVIEW_WEBHOOK_URL="http://localhost:5678/webhook/release-agent-review-decision"
```

To enable the Postgres-backed review queue and workflow status cards:

```powershell
$env:RELEASE_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/database"
```

The dashboard is designed for human-in-the-loop review. It shows release risk,
safety-gate status, generated artifacts, workflow status, and reviewer decision
state.

## CLI

Collect evidence:

```powershell
.\.venv\Scripts\python.exe -m release_agent.cli collect-evidence `
  --owner juesteeb-wbs `
  --repo ai-release-agent-demo-v2 `
  --base-ref v1.0.0 `
  --target-ref release/1.1.0 `
  --release-version 1.1.0 `
  --output artifacts/evidence/release-1.1.0-evidence.json
```

Analyze evidence:

```powershell
.\.venv\Scripts\python.exe -m release_agent.cli analyze-evidence `
  --evidence-file artifacts\evidence\release-1.1.0-evidence.json `
  --output-dir artifacts\analysis\release-1.1.0
```

Generated artifacts are written under `artifacts/`, which is ignored by Git.

## Safety Model

- GitHub evidence and repository text are treated as untrusted input.
- Secrets and tokens must never enter source control or AI prompts.
- AI output is advisory and must pass deterministic validation.
- Safety gates are deterministic and visible to the reviewer.
- Human approval is required.
- Publication remains disabled in this demo.
