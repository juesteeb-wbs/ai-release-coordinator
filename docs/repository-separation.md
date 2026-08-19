# Repository Separation

This repository is the extracted Release Coordinator implementation. The demo
application remains in a separate target repository.

## Current Demo Split

```text
ai-release-agent-demo-v2
- FastAPI support-ticket demo application
- application tests
- release branches, tags, and pull requests
- GitHub evidence used by the coordinator

ai-release-coordinator
- release_agent Python package
- local FastAPI coordinator API
- dashboard UI
- evidence collection and analysis helpers
- AI input/output validation
- n8n workflow documentation
```

The coordinator should analyze the target repository through GitHub APIs and
request data. It should not require its Python package to live inside the target
repository.

## Near-Term Rule

Copying was intentional for the first extraction step. Do not delete or alter
the original demo repository while stabilizing this new package.

## Desired Production Shape

In a production setup, the Release Coordinator would be an installable Python
package:

```powershell
pip install ai-release-coordinator
```

or, during development:

```powershell
pip install -e .
```

The package would run locally, in CI, or beside n8n, and receive the target
repository through request data:

```json
{
  "repository_owner": "github-user-or-org",
  "repository_name": "target-repository",
  "base_ref": "v1.0.0",
  "target_ref": "release/1.1.0",
  "release_version": "1.1.0",
  "release_mode": "preview",
  "publish_enabled": false
}
```

## Refactoring Goals

- Keep target repository details configurable.
- Keep demo-specific examples in docs and tests, not in runtime assumptions.
- Preserve read-only GitHub behavior.
- Keep AI output validation inside deterministic Python code.
- Keep dashboard and n8n integration independent from any one application repo.
