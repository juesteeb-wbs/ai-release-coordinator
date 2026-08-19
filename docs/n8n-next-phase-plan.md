# n8n Next Phase Plan

This document defines the next implementation phase after the initial
preview-only n8n workflow.

The current workflow can submit a release request, call the local FastAPI preview
API, receive analysis JSON, build a compact review summary, evaluate safety
gates with an explicit preview policy, and record a preview decision. The next
phase should make that workflow more usable, reviewable, and auditable while
remaining read-only.

## Current Workflow

Current node sequence:

```text
Manual Trigger
-> Set Release Request
-> Validate Request
-> Build Artifact Paths
-> HTTP Request to preview API
-> Build Review Summary
-> Build Compact Front Page
-> Evaluate Safety Gates
-> Add Review Decision fields
-> Record Preview Decision
```

## Goals

- Improve the human review experience.
- Persist a useful preview decision record.
- Detect if the target branch moved after analysis.
- Make safety gates clearer and more configurable.
- Prepare for AI-assisted analysis without trusting AI output blindly.
- Improve diagnostics and workflow observability.

## Non-Goals

This phase must not:

- Publish GitHub releases
- Create release drafts
- Push commits
- Create or move tags
- Merge pull requests
- Deploy anything
- Send customer announcements
- Automatically approve a release
- Require GitHub write permissions

## Workstream 1: Review UX

Improve the review output so a human reviewer can quickly understand the release
state.

Recommended improvements:

- Separate executive summary from detailed artifacts.
- Show risk level, risk score, blockers, and warnings near the top.
- Show base and target SHA prefixes with full SHAs available in details.
- Show customer release notes separately from technical changelog.
- Show missing-documentation warnings as a dedicated section.
- Show QA checklist grouped by status:
  - completed
  - recommended
  - blocked
- Keep the full analysis JSON available for expansion/debugging.

Suggested next node:

```text
Build Review Markdown
```

Output fields:

```text
review_markdown
executive_summary
blocker_summary
warning_summary
artifact_summary
```

Acceptance criteria:

- A reviewer can understand the release status without reading raw JSON.
- Internal tooling changes do not appear in customer-facing notes.
- Blockers and warnings are visually obvious.

## Workstream 2: Persist Preview Decision

The workflow currently records a decision in the execution output. The next step
is to persist that record in a predictable place.

Initial storage options:

1. n8n execution data
2. local JSON file written by a controlled local API endpoint
3. n8n Data Tables
4. PostgreSQL later, if needed

Recommended first implementation:

- Keep using n8n execution data.
- Add a final compact `decision_record` object.
- Do not write to GitHub.

Decision record fields:

```text
repository
release_range
base_sha
target_sha
risk_level
risk_score
gate_status
can_approve_normally
hard_blockers
gate_warnings
review_decision
reviewer_notes
reviewer
reviewed_at
warning_count
hard_blocker_count
publication_performed
```

Acceptance criteria:

- The final workflow output contains one decision record.
- The record includes the target SHA used for analysis.
- `publication_performed` is always `false`.

## Workstream 3: Target SHA Movement Check

The specification requires approval to be tied to the analyzed target SHA. If the
target branch moves after evidence collection, approval should require a fresh
analysis.

Recommended first implementation:

- Use the lightweight preview API endpoint that resolves a ref to a SHA.
- In n8n, store the analyzed `target_sha`.
- Before recording approval, re-check the current target SHA.
- Block normal approval if the current target SHA differs.

API endpoint:

```text
POST /release-analysis/resolve-ref
```

Request:

```json
{
  "repository_owner": "juesteeb-wbs",
  "repository_name": "ai-release-agent-demo-v2",
  "ref": "release/1.1.0"
}
```

Response:

```json
{
  "ref": "release/1.1.0",
  "sha": "..."
}
```

Acceptance criteria:

- The workflow can detect when `release/1.1.0` moved after analysis.
- The gate result includes a hard blocker when target SHA changed.
- The reviewer sees both the analyzed SHA and current SHA.

## Workstream 4: Safety Gate Policy

The gate logic should stay deterministic and easy to inspect. In this phase, the
policy is embedded in the `Evaluate Safety Gates` Code node and emitted in the
workflow output.

Recommended policy fields:

```text
block_on_high_risk
block_on_missing_documentation
block_on_missing_check_runs
block_on_target_sha_changed
allow_warning_override
require_override_reason
```

Preview-only policy:

```json
{
  "block_on_high_risk": true,
  "block_on_missing_documentation": false,
  "block_on_missing_check_runs": false,
  "block_on_target_sha_changed": false,
  "allow_warning_override": true,
  "require_override_reason": true
}
```

Policy meaning:

- High risk blocks normal approval.
- Missing documentation is visible as a warning.
- Missing check-run evidence is visible as a warning.
- Target SHA movement is disabled until the workflow performs a publishing or
  release-draft action.
- Warning overrides are allowed but require reviewer notes.

Suggested gate statuses:

```text
pass
warning
blocked
```

Suggested decision rules:

- `approve_draft` is allowed only when gate status is `pass`.
- `override_warning` requires reviewer notes.
- `request_changes` is valid for `warning` or `blocked`.
- `reject_release` is always valid.

Acceptance criteria:

- Gate output distinguishes hard blockers from warnings.
- Override decisions require a reason.
- The workflow still performs no publishing action.

## Workstream 5: Prepare AI-Assisted Analysis

The current analyzer is deterministic. A later phase can add AI-assisted
classification and artifact generation, but deterministic validation must remain
around it.

The design for this phase is documented in
[`docs/ai-assisted-analysis-design.md`](ai-assisted-analysis-design.md).
The structured model output contract is documented in
[`docs/structured-ai-output-contract.md`](structured-ai-output-contract.md).

The first implementation provides a preview-only convenience endpoint,
`POST /release-analysis/ai-review-draft`, that builds the AI input package,
generates a deterministic demo draft, and validates the structured output.

The model-ready path is split into `POST /release-analysis/ai-input-package` and
`POST /release-analysis/validate-ai-review`, so n8n can insert a real model node
between input preparation and deterministic validation.

Preparation tasks:

- Define the AI input package.
- Define structured AI output schema.
- Mark AI-only interpretations as inference.
- Require evidence references for customer-facing claims.
- Capture release-process improvement suggestions.
- Capture missing information that affects release confidence.
- Validate AI output before showing it as confirmed.
- Keep deterministic gates independent of model recommendations.

AI output should not be trusted when:

- claims lack evidence
- classifications conflict with changed files
- breaking changes lack migration guidance
- generated text contains unresolved templates
- generated text contains suspected secrets

Acceptance criteria:

- AI output schema is documented before model integration.
- Unsupported claims are blocked from customer release notes.
- A human reviewer can distinguish evidence-backed facts from inference.
- AI suggestions identify useful release-process improvements and missing
  release evidence.
- Deterministic safety gates remain independent of AI recommendations.

## Workstream 6: Observability And Diagnostics

Add enough diagnostics to understand workflow failures and review quality.

Recommended metrics:

```text
analysis_started_at
analysis_finished_at
duration_ms
change_count
claim_count
warning_count
hard_blocker_count
redaction_count
truncation_count
check_run_warning_present
target_sha
```

Failure diagnostics:

- validation failure reason
- HTTP request status
- preview API error detail
- GitHub access or permission issue
- evidence truncation warnings

Acceptance criteria:

- Failed executions show an actionable error message.
- Successful executions show duration and warning counts.
- Reviewer can identify whether evidence was incomplete.

## Recommended Implementation Order

1. Add review Markdown to the preview API response.
2. Use the review Markdown in the n8n review summary.
3. Improve Safety Gates node with explicit policy fields.
4. Improve Record Preview Decision node.
5. Add target SHA movement check.
6. Add observability fields.
7. Document AI output schema for the later AI-assisted phase.

## Definition Of Done

This phase is complete when:

- The n8n workflow produces a readable review package.
- The workflow records a structured preview decision.
- Safety gates clearly identify blockers and warnings.
- Target SHA movement can be detected before approval.
- The workflow remains read-only.
- No publishing or GitHub write action exists.
