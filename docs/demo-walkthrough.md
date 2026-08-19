# Demo Walkthrough

This walkthrough shows the current AI Release Agent demo at a high level. It is
intended for explaining the project, not for replacing the detailed
implementation docs.

## Demo Message

The demo shows how AI can support release management without taking over release
control.

The core idea is:

```text
GitHub evidence
-> deterministic analysis
-> reviewer-friendly artifacts
-> safety gates
-> human decision
-> AI assistance planned around validated evidence
```

AI is positioned as a drafting and review assistant. Deterministic code keeps
ownership of evidence collection, validation, safety gates, and publishing
controls. Humans remain responsible for approval.

## What To Show

### 1. Baseline Application

Show the FastAPI support-ticket app as the demo product being released.

Useful points:

- It has real API behavior, not placeholder code.
- It uses SQLite for local persistence.
- It has automated tests.
- `v1.0.0` is the baseline release.

### 2. Release Branch

Show that `release/1.1.0` contains a realistic mix of changes:

- customer-facing features
- a bug fix
- a breaking configuration change
- a dependency/security update
- internal tooling
- documentation and workflow work

This gives the Release Agent enough evidence to classify and explain a release.

### 3. Evidence Collection And Analysis

Show that the Python release agent can collect GitHub evidence and generate a
structured analysis.

Important points:

- Evidence collection is read-only.
- The analyzer produces structured changes, claims, risk, QA suggestions, and
  draft release artifacts.
- Generated artifacts are local previews, not published releases.

### 4. Local Preview API

Show the FastAPI preview endpoint:

```text
POST /release-analysis/preview
```

This endpoint lets n8n call the tested Python implementation through an HTTP
Request node.

Important points:

- n8n does not need to run shell commands.
- The endpoint is preview-only.
- It does not create releases, tags, pull requests, deployments, or GitHub
  write actions.

### 5. n8n Workflow

Show the current n8n workflow:

```text
Manual Trigger
-> Set Release Request
-> Validate Request
-> Build Artifact Paths
-> HTTP Request to preview API
-> Build Review Summary
-> Build Compact Front Page
-> Evaluate Safety Gates
-> Simulate human decision
-> Record Preview Decision
```

The workflow demonstrates the release-review loop from request to decision.

### 6. Safety Gates

Show the explicit safety policy in the `Evaluate Safety Gates` node.

Current demo policy:

```text
High risk: blocker
Missing documentation: warning
Missing check-runs: warning
Target SHA movement: prepared in API, deferred in n8n until publishing exists
```

Important point:

The workflow separates blockers from warnings. It can explain why normal
approval is not allowed.

### 7. Decision Record

Show the final compact `decision_record`.

It should include:

- repository and release range
- analyzed base and target SHAs
- risk level and score
- gate status
- hard blockers
- warnings
- reviewer decision and notes
- `publication_performed: false`

This is the audit-style output for the preview workflow.

## AI Phase

The next phase introduces AI carefully.

AI may help with:

- clearer release summaries
- improved release note wording
- risk explanations
- reviewer questions
- QA focus suggestions

AI must not:

- approve releases
- override blockers
- publish releases
- create or move tags
- merge pull requests
- deploy anything
- invent unsupported customer-facing claims

The planned AI design is documented in
[`docs/ai-assisted-analysis-design.md`](ai-assisted-analysis-design.md).

## Demo Closing

The current project demonstrates a safe release-agent pattern:

```text
AI assists.
Deterministic controls validate.
Humans approve.
Publishing stays disabled until explicit safety controls exist.
```

That is the main story to emphasize.
