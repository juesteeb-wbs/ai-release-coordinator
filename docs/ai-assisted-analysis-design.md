# AI-Assisted Analysis Design

This document defines how AI should be used by the extracted AI Release
Coordinator. The goal is to show useful AI assistance without making the model
responsible for safety, approval, or publishing decisions.

## Positioning

The Release Coordinator uses AI as a reviewer and drafting assistant.

Deterministic code remains responsible for:

- GitHub evidence collection
- secret redaction
- release-boundary resolution
- schema validation
- evidence-reference validation
- safety gate evaluation
- publication controls

Humans remain responsible for final approval.

AI output is advisory. It must be structured, validated, and reviewable before it
is shown as release evidence or used in customer-facing artifacts.

## AI Responsibilities

The AI-assisted phase may use a model to:

- improve release summaries
- explain risk factors in clearer language
- identify reviewer questions
- suggest customer-facing release note wording
- suggest technical changelog wording
- detect ambiguity or missing context
- propose QA focus areas
- suggest release-process improvements
- identify missing information that affects release confidence

The model must not:

- approve a release
- override a blocker
- publish a release
- create or move tags
- merge pull requests
- deploy anything
- invent customer-facing claims
- use unsupported facts as evidence
- execute generated code

## AI Input Package

The model should receive a compact package derived from the deterministic
analysis result, not raw repository history.

Suggested input fields:

```json
{
  "repository": "owner/target-repository",
  "release_range": "v1.0.0..release/1.1.0",
  "base_sha": "...",
  "target_sha": "...",
  "changes": [
    {
      "change_id": "CHANGE-001",
      "title": "Add CSV ticket export",
      "summary": "Add CSV ticket export.",
      "categories": ["feature"],
      "customer_impact": "medium",
      "migration_required": false,
      "documentation_required": true,
      "regression_testing_required": true,
      "warnings": [
        "Missing documentation for customer-visible change in PR #1."
      ],
      "evidence": [
        {"type": "pull_request", "reference": "PR-1"},
        {"type": "file", "reference": "app/main.py"}
      ]
    }
  ],
  "risk_assessment": {
    "level": "high",
    "score": 0.82,
    "factors": []
  },
  "warnings": [
    "check_runs_unavailable"
  ],
  "missing_documentation_warnings": [],
  "existing_artifacts": {
    "customer_release_notes": "...",
    "technical_changelog": "...",
    "qa_checklist": [],
    "deployment_and_rollback_guidance": "..."
  }
}
```

Input rules:

- Include only redacted evidence.
- Exclude secrets, credentials, private keys, and tokens.
- Exclude raw patches unless they are necessary and already redacted.
- Prefer summarized evidence over large raw diffs.
- Preserve stable evidence references such as `CHANGE-001`, `PR-3`, and file
  paths.

## Structured AI Output

The model should return structured JSON. Free-form Markdown can be included
inside fields, but the outer response must be machine-validated.

The detailed output contract is documented in
[`docs/structured-ai-output-contract.md`](structured-ai-output-contract.md).

Suggested output schema:

```json
{
  "summary_suggestions": [
    {
      "target": "executive_summary",
      "text": "This release adds CSV export and customer email filtering...",
      "evidence_references": ["CHANGE-001", "CHANGE-006"],
      "is_inference": false
    }
  ],
  "release_note_suggestions": [
    {
      "audience": "customer",
      "text": "Support tickets can now be exported as CSV.",
      "evidence_references": ["CHANGE-001"],
      "is_inference": false
    }
  ],
  "risk_explanations": [
    {
      "factor": "breaking_change_potential",
      "text": "The API key environment variable was renamed and requires deployment configuration review.",
      "evidence_references": ["CHANGE-003"],
      "is_inference": false
    }
  ],
  "reviewer_questions": [
    {
      "question": "Has the API key environment variable rename been applied in deployment configuration?",
      "reason": "A breaking configuration change is present.",
      "evidence_references": ["CHANGE-003"]
    }
  ],
  "process_improvement_suggestions": [
    {
      "suggestion": "Add a migration checklist for the API key configuration rename.",
      "reason": "CHANGE-003 requires deployment configuration changes and rollback coordination.",
      "evidence_references": ["CHANGE-003"],
      "priority": "high"
    }
  ],
  "missing_information": [
    {
      "item": "CI/check-run status",
      "reason": "The collector could not access check-run evidence.",
      "evidence_references": ["CHANGE-001", "CHANGE-006"],
      "blocks_release_confidence": true
    }
  ],
  "unsupported_claims": [
    {
      "text": "The release improves performance.",
      "reason": "No performance evidence exists in the input package."
    }
  ],
  "validation_notes": [
    "Customer-facing suggestions reference collected evidence."
  ]
}
```

## Validation Rules

Deterministic validation must run after the model response.

Required checks:

- The response is valid JSON.
- Required fields are present.
- Enums use accepted values.
- Every customer-facing suggestion has at least one evidence reference.
- Every evidence reference exists in the deterministic analysis input.
- `is_inference` is `true` for interpretation that is not directly proven by
  evidence.
- Unsupported claims are excluded from customer release notes.
- Output contains no suspected secrets.
- Output contains no unresolved templates.
- The model does not recommend publishing, merging, tagging, or deploying.

If validation fails, one retry may be allowed with validation feedback. If the
second response fails, the workflow must stop and require human review.

## Safety Gates

AI output must not directly control release gates.

The deterministic workflow remains responsible for:

- `gate_status`
- `can_approve_normally`
- `hard_blockers`
- `gate_warnings`
- `publication_performed`

The model may suggest review questions or explain risk, but it cannot downgrade
a blocker or approve an override.

## n8n Placement

Recommended future node sequence:

```text
HTTP Request to preview API
-> Build Review Summary
-> Build AI Input Package
-> AI-Assisted Review Draft
-> Validate AI Output
-> Build Compact Front Page
-> Evaluate Safety Gates
-> Simulate human decision
-> Record Preview Decision
```

The AI nodes should remain before the deterministic safety gates. The gates can
then consider validation failures, unsupported claims, or model-output warnings
without trusting the model's recommendation.

## Current Preview Endpoints

The first implementation exposes a convenience preview-only endpoint:

```text
POST /release-analysis/ai-review-draft
```

Request:

```json
{
  "analysis": {
    "...": "analysis JSON returned by /release-analysis/preview"
  },
  "draft_mode": "demo"
}
```

Response:

```json
{
  "ai_input_package": {},
  "ai_review_draft": {},
  "ai_review_validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  },
  "publication_performed": false
}
```

`draft_mode: "demo"` uses a deterministic demo generator. It does not call an AI
model. The endpoint exists so the n8n workflow can test the input package,
structured draft shape, and validation layer before model credentials are added.

In the later model-backed phase, only the draft-generation step should be
replaced by a model call. The deterministic validation step should remain.

The reusable model-backed path is split into two endpoints:

```text
POST /release-analysis/ai-input-package
POST /release-analysis/validate-ai-review
```

`/release-analysis/ai-input-package` converts deterministic analysis JSON into
the compact package that n8n can send to a model.

`/release-analysis/validate-ai-review` validates structured model output against
the AI input package. It returns structured validation results instead of
publishing anything or changing GitHub state.

Model-backed n8n sequence:

```text
HTTP Request to preview API
-> Build Review Summary
-> HTTP Request to AI input package endpoint
-> AI model node
-> HTTP Request to validate AI review endpoint
-> Build AI Review Display
-> Build Compact Front Page
-> Evaluate Safety Gates
-> Record Preview Decision
```

## Acceptance Criteria

- The AI input package is derived only from collected, redacted evidence.
- The AI response uses a documented structured schema.
- Customer-facing AI suggestions include valid evidence references.
- Unsupported or inferred claims are visible to the reviewer.
- Deterministic safety gates remain independent of AI recommendations.
- No publishing, GitHub write action, deployment, tag creation, or release
  creation is added in this phase.
