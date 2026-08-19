# n8n Workflow Plan

This plan describes the n8n workflow around the extracted AI Release
Coordinator. The workflow still uses `ai-release-agent-demo-v2` as the target
repository for demonstration data, but the local Python API now belongs to this
`ai-release-coordinator` repository.

The recommended initial n8n version calls the local Python preview API through
an HTTP Request node. The Python API wraps the tested collector and analyzer.
n8n controls the release request, receives structured analysis JSON, and
presents a human review package.

## Scope

Included:

- Manual preview-only release analysis
- GitHub evidence collection through the local Python preview API
- Deterministic local analysis through the local Python preview API
- Reading structured JSON from an HTTP response
- Human review summary
- Explicit preview safety gate policy

Excluded:

- Publishing GitHub releases
- Creating or moving tags
- Merging pull requests
- Pushing commits
- Deployments
- Customer announcements
- AI-generated code execution

## Runtime Assumptions

The first workflow assumes self-hosted n8n runs on the same Windows machine as
the Release Coordinator repository.

Coordinator repository path:

```text
C:\Users\seime\PythonProject\ai-release-coordinator
```

Preview API command:

```text
.\.venv\Scripts\python.exe -m uvicorn release_agent.api:app --host 127.0.0.1 --port 8010 --reload
```

The preview API process needs a read-only GitHub token available as an
environment variable:

```text
GITHUB_TOKEN
```

The token must be restricted to the target repository and use read-only
permissions. For the current demo target, that repository is
`juesteeb-wbs/ai-release-agent-demo-v2`.

## Release Request

The workflow input should use this structure:

```json
{
  "repository_owner": "juesteeb-wbs",
  "repository_name": "ai-release-agent-demo-v2",
  "base_ref": "v1.0.0",
  "target_ref": "release/1.1.0",
  "release_version": "1.1.0",
  "release_mode": "preview",
  "publish_enabled": false
}
```

Validation rules:

- `release_mode` must be `preview`.
- `publish_enabled` must be `false`.
- `repository_owner`, `repository_name`, `base_ref`, `target_ref`, and
  `release_version` must be non-empty.
- The workflow must stop if validation fails.

## Workflow Nodes

### 1. Manual Trigger

Use a Manual Trigger node while building the demo.

Later, this can be replaced by a Webhook node or Form Trigger node.

### 2. Set Release Request

Use a Set node to define the release request fields.

Fields:

```text
repository_owner = juesteeb-wbs
repository_name = ai-release-agent-demo-v2
base_ref = v1.0.0
target_ref = release/1.1.0
release_version = 1.1.0
release_mode = preview
publish_enabled = false
```

### 3. Validate Request

Use a Code node to validate the release request.

Pseudo-code:

```javascript
const item = $input.first().json;

const required = [
  "repository_owner",
  "repository_name",
  "base_ref",
  "target_ref",
  "release_version"
];

for (const field of required) {
  if (!item[field] || String(item[field]).trim() === "") {
    throw new Error(`Missing required field: ${field}`);
  }
}

if (item.release_mode !== "preview") {
  throw new Error("release_mode must be preview");
}

if (item.publish_enabled !== false) {
  throw new Error("publish_enabled must be false");
}

return [{ json: item }];
```

### 4. Build Artifact Paths

Use a Set or Code node to derive local artifact paths.

Suggested values:

```text
repo_path = C:\Users\seime\PythonProject\ai-release-coordinator
evidence_file = artifacts\evidence\release-1.1.0-evidence.json
analysis_dir = artifacts\analysis\release-1.1.0
analysis_file = artifacts\analysis\release-1.1.0\analysis.json
```

### 5. Call Preview API

Use an HTTP Request node.

Method:

```text
POST
```

URL:

```text
http://127.0.0.1:8010/release-analysis/preview
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "repository_owner": "juesteeb-wbs",
  "repository_name": "ai-release-agent-demo-v2",
  "base_ref": "v1.0.0",
  "target_ref": "release/1.1.0",
  "release_version": "1.1.0",
  "release_mode": "preview",
  "publish_enabled": false
}
```

Expected result:

```text
HTTP 200 with analysis JSON
```

Failure handling:

- Stop if the HTTP status is not 2xx.
- `400` means the release request failed validation.
- `502` means GitHub evidence collection or analysis failed.
- Do not present an approval package if the preview API fails.

### 6. Build Human Review Summary

Use a Code node to extract the most important review fields from the HTTP
response. The preview API already returns `review_markdown`,
`executive_summary`, `blocker_summary`, `warning_summary`, and
`artifact_summary`, so n8n does not need to build all review text itself.

Suggested output fields:

```text
repository
release_range
base_sha
target_sha
change_count
claim_count
risk_level
risk_score
warnings
missing_documentation_warnings
customer_release_notes
technical_changelog
qa_checklist
deployment_and_rollback_guidance
review_markdown
executive_summary
blocker_summary
warning_summary
artifact_summary
```

Pseudo-code:

```javascript
const analysis = $input.first().json;

return [{
  json: {
    repository: analysis.repository,
    release_range: analysis.release_range,
    base_sha: analysis.base_sha,
    target_sha: analysis.target_sha,
    change_count: analysis.changes.length,
    claim_count: analysis.claims.length,
    risk_level: analysis.artifacts.risk_and_impact_assessment.level,
    risk_score: analysis.artifacts.risk_and_impact_assessment.score,
    warnings: analysis.warnings,
    missing_documentation_warnings: analysis.artifacts.missing_documentation_warnings,
    customer_release_notes: analysis.artifacts.customer_release_notes,
    technical_changelog: analysis.artifacts.technical_changelog,
    qa_checklist: analysis.artifacts.qa_checklist,
    deployment_and_rollback_guidance: analysis.artifacts.deployment_and_rollback_guidance,
    review_markdown: analysis.review_markdown,
    executive_summary: analysis.executive_summary,
    blocker_summary: analysis.blocker_summary,
    warning_summary: analysis.warning_summary,
    artifact_summary: analysis.artifact_summary
  }
}];
```

### Optional: AI-Assisted Review Draft

Use these optional nodes after `Build Human Review Summary` to test the
structured AI review contract. The current demo can still call
`/release-analysis/ai-review-draft` as a shortcut, but the model-ready path uses
separate input-package and validation calls.

#### Build AI Input Package

Use an HTTP Request node.

Method:

```text
POST
```

URL:

```text
http://host.docker.internal:8010/release-analysis/ai-input-package
```

Use `http://127.0.0.1:8010/release-analysis/ai-input-package` only when n8n is
not running in Docker.

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "analysis": "{{ $json.full_analysis || $json.full_review_data?.full_analysis || $json }}"
}
```

Expected result:

```text
ai_input_package
publication_performed = false
```

#### AI Model Node

Send `ai_input_package` to the model and require output that follows
[`docs/structured-ai-output-contract.md`](structured-ai-output-contract.md).

The model output should become an `ai_review_draft` object.

#### Validate AI Review Output

Use an HTTP Request node.

Method:

```text
POST
```

URL:

```text
http://host.docker.internal:8010/release-analysis/validate-ai-review
```

Use `http://127.0.0.1:8010/release-analysis/validate-ai-review` only when n8n is
not running in Docker.

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "ai_input_package": "{{ $json.ai_input_package }}",
  "ai_review_draft": "{{ $json.ai_review_draft }}"
}
```

Expected result:

```text
ai_review_validation
publication_performed = false
```

If `ai_review_validation.valid` is `false`, keep the deterministic review output
and show the validation errors to the reviewer.

### 7. Evaluate Safety Gates

Use a Code node to apply the preview safety policy. The purpose of this node is
to make the policy visible in workflow output, not to make final release
decisions automatically.

For the preview-only demo, use this policy:

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

Suggested Code node:

```javascript
const item = $input.first().json;
const reviewData = item.full_review_data || item;

const policy = {
  block_on_high_risk: true,
  block_on_missing_documentation: false,
  block_on_missing_check_runs: false,
  block_on_target_sha_changed: false,
  allow_warning_override: true,
  require_override_reason: true,
};

const hardBlockers = [];
const gateWarnings = [];

const riskLevel = String(reviewData.risk_level || item.risk_level || "").toLowerCase();

const releaseWarnings = Array.isArray(reviewData.warnings)
  ? reviewData.warnings
  : Array.isArray(item.warnings)
    ? item.warnings
    : [];

const missingDocs = Array.isArray(reviewData.missing_documentation_warnings)
  ? reviewData.missing_documentation_warnings
  : Array.isArray(item.missing_documentation_warnings)
    ? item.missing_documentation_warnings
    : [];

const hasMissingCheckRuns = releaseWarnings.some((warning) =>
  String(warning).includes("check_runs_unavailable")
);

if (riskLevel === "high") {
  const message = "Release risk level is high.";
  if (policy.block_on_high_risk) {
    hardBlockers.push(message);
  } else {
    gateWarnings.push(message);
  }
}

if (missingDocs.length > 0) {
  const message = `${missingDocs.length} change(s) have missing documentation warnings.`;
  if (policy.block_on_missing_documentation) {
    hardBlockers.push(message);
  } else {
    gateWarnings.push(message);
  }
}

if (hasMissingCheckRuns) {
  const message = "GitHub check-run evidence is unavailable.";
  if (policy.block_on_missing_check_runs) {
    hardBlockers.push(message);
  } else {
    gateWarnings.push(message);
  }
}

if (item.target_sha_changed === true) {
  const message = "Target branch moved after analysis.";
  if (policy.block_on_target_sha_changed) {
    hardBlockers.push(message);
  } else {
    gateWarnings.push(message);
  }
}

const gateStatus =
  hardBlockers.length > 0 ? "blocked" : gateWarnings.length > 0 ? "warning" : "pass";

return [{
  json: {
    ...item,
    gate_policy: policy,
    gate_status: gateStatus,
    can_approve_normally: gateStatus === "pass",
    requires_override_reason:
      gateStatus === "warning" &&
      policy.allow_warning_override &&
      policy.require_override_reason,
    hard_blockers: hardBlockers,
    gate_warnings: gateWarnings,
    safety_gate_summary: {
      status: gateStatus,
      hard_blocker_count: hardBlockers.length,
      warning_count: gateWarnings.length,
    },
  },
}];
```

Output fields:

```text
gate_policy
gate_status
can_approve_normally
requires_override_reason
hard_blockers
gate_warnings
safety_gate_summary
```

Expected statuses:

```text
pass
warning
blocked
```

### 8. Human Approval Preview

For the first version, use one of these:

- n8n Form node
- Manual review in the execution output
- Send the review summary to yourself through a non-publishing channel

The approval decision should be preview-only.

Allowed decisions:

```text
approve_draft
request_changes
reject_release
override_warning
```

For now, record the decision in workflow execution data only. Do not publish.

### 9. Record Preview Decision

Use a Code node to produce one compact final `decision_record`. Earlier nodes
can keep detailed review data for inspection, but the final workflow output
should be small enough to read at a glance.

Suggested Code node:

```javascript
const item = $input.first().json;
const reviewData = item.full_review_data || item;

const hardBlockers = Array.isArray(item.hard_blockers) ? item.hard_blockers : [];
const gateWarnings = Array.isArray(item.gate_warnings) ? item.gate_warnings : [];

const decisionRecord = {
  repository: item.repository || reviewData.repository,
  release_range: item.release_range || reviewData.release_range,
  base_sha: reviewData.base_sha || item.base_sha,
  target_sha: reviewData.target_sha || item.target_sha,

  risk_level: reviewData.risk_level || item.risk_level,
  risk_score: reviewData.risk_score || item.risk_score,

  gate_status: item.gate_status,
  can_approve_normally: item.can_approve_normally,
  hard_blockers: hardBlockers,
  gate_warnings: gateWarnings,

  review_decision: item.review_decision,
  reviewer_notes: item.reviewer_notes || "",
  reviewer: item.reviewer || "demo-reviewer",
  reviewed_at: item.reviewed_at || new Date().toISOString(),

  warning_count: gateWarnings.length,
  hard_blocker_count: hardBlockers.length,
  publication_performed: false,
};

return [{
  json: {
    decision_record: decisionRecord,
  },
}];
```

The final output should include only the compact decision record. Do not return
`...item` from this node unless debugging the workflow.

## Safety Gates

The workflow must stop or require review when:

- release request validation fails
- evidence collection fails
- analysis fails
- target SHA changes between collection and approval
- generated output contains unsupported claims
- missing-documentation warnings exist
- check-run evidence is unavailable
- risk level is high

In this demo, missing documentation and unavailable check-run evidence are
warnings for reviewer visibility, not automatic publication blockers, because no
publication action exists in this phase.

## Deferred Target SHA Movement Check

The local API includes `POST /release-analysis/resolve-ref` so the workflow can
compare the analyzed `target_sha` with the current target branch SHA before a
real publishing action. The active preview-only n8n workflow does not use this
node yet because it would require merging the preview response and the
`resolve-ref` response back into one item.

Enable this check before adding release publication, release drafts, tag
creation, deployment, or any other write action.

Suggested future node sequence:

```text
Evaluate Safety Gates
-> Resolve Current Target Ref
-> Merge Analysis And Current Ref
-> Compare Target SHA
-> Human Approval Preview
-> Record Preview Decision
```

The comparison should add a hard blocker when the current target SHA differs
from the analyzed `target_sha`.

## Expected First Demo Result

When run against:

```text
v1.0.0..release/1.1.0
```

the workflow should show:

- resolved base and target SHAs
- all merged pull requests in the range
- customer-facing release notes
- technical changelog
- risk assessment
- QA checklist
- deployment and rollback guidance
- missing-documentation warnings for intentionally under-documented changes
- warnings when check-run evidence is unavailable

## Later Native n8n Implementation

After the CLI-orchestrated workflow is working, the Python commands can be
replaced gradually:

| Current Step | Later n8n-native version |
| --- | --- |
| Python preview API | GitHub nodes, Code nodes, and AI model nodes |
| Local artifact files | n8n Data Tables or PostgreSQL |
| Manual execution output | Human approval form |

This staged approach keeps the first n8n workflow understandable while preserving
the tested Python implementation as a reliable reference.
