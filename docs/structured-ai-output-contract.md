# Structured AI Output Contract

This document defines the JSON contract for AI-assisted release review output.
It is the target shape for a future model-backed n8n node and the current
preview-only demo draft endpoint.

AI output is advisory. It must pass deterministic validation before it can be
shown as a trusted review aid.

## Top-Level Object

The AI response must be a JSON object with these fields:

```json
{
  "summary_suggestions": [],
  "release_note_suggestions": [],
  "risk_explanations": [],
  "reviewer_questions": [],
  "process_improvement_suggestions": [],
  "missing_information": [],
  "unsupported_claims": [],
  "validation_notes": []
}
```

All top-level fields are required. Each field must be an array. Extra fields are
allowed during experimentation, but deterministic validation must ignore them
unless explicitly documented later.

## Evidence References

AI output must use stable evidence references from the AI input package.

Allowed reference examples:

```text
CHANGE-001
CHANGE-006
```

Rules:

- Customer-facing release note suggestions must include at least one evidence
  reference.
- Every evidence reference must exist in the deterministic AI input package.
- Pull request numbers, file paths, and free-text citations are not enough by
  themselves for this contract.
- If the model is unsure, it should create a reviewer question or unsupported
  claim instead of inventing evidence.

## Inference Rules

Each suggestion that contains interpretation must set:

```json
"is_inference": true
```

Use `is_inference: false` only when the text is directly supported by the
referenced change record.

Examples:

```text
"Support tickets can now be exported as CSV."
```

This can be non-inference when it references the CSV export change.

```text
"This release may reduce manual reporting effort."
```

This is an inference unless the evidence explicitly proves that outcome.

## summary_suggestions

Purpose: improve reviewer-facing summaries.

Item shape:

```json
{
  "target": "executive_summary",
  "text": "This release adds CSV export and customer email filtering.",
  "evidence_references": ["CHANGE-001", "CHANGE-006"],
  "is_inference": false
}
```

Required fields:

```text
target
text
evidence_references
is_inference
```

Allowed `target` values:

```text
executive_summary
review_markdown
blocker_summary
warning_summary
artifact_summary
```

## release_note_suggestions

Purpose: suggest customer-facing or internal release-note wording.

Item shape:

```json
{
  "audience": "customer",
  "text": "Support tickets can now be exported as CSV.",
  "evidence_references": ["CHANGE-001"],
  "is_inference": false
}
```

Required fields:

```text
audience
text
evidence_references
is_inference
```

Allowed `audience` values:

```text
customer
technical
internal
```

Customer-facing suggestions must be evidence-backed. Unsupported or inferred
customer-facing claims must not be inserted into final customer release notes
without human review.

## risk_explanations

Purpose: explain risk factors in reviewer-friendly language.

Item shape:

```json
{
  "factor": "breaking_change_potential",
  "text": "The API key environment variable was renamed and requires deployment configuration review.",
  "evidence_references": ["CHANGE-003"],
  "is_inference": false
}
```

Required fields:

```text
factor
text
evidence_references
is_inference
```

Allowed `factor` values:

```text
customer_impact
breaking_change_potential
security_relevance
change_surface
insufficient_testing
rollback_complexity
overall_release_risk
other
```

Risk explanations do not control `risk_score`, `risk_level`, or safety gates.
Those remain deterministic.

## reviewer_questions

Purpose: ask focused questions for the human reviewer.

Item shape:

```json
{
  "question": "Has the API key environment variable rename been applied in deployment configuration?",
  "reason": "A breaking configuration change is present.",
  "evidence_references": ["CHANGE-003"]
}
```

Required fields:

```text
question
reason
evidence_references
```

Reviewer questions may point to ambiguity, missing evidence, or required manual
checks. They must not instruct the workflow to publish, deploy, merge, or tag.

## process_improvement_suggestions

Purpose: suggest practical improvements to the release process before approval
or before future releases.

Item shape:

```json
{
  "suggestion": "Add customer-facing documentation for the customer email ticket filter.",
  "reason": "CHANGE-006 is customer-visible and currently has a missing-documentation warning.",
  "evidence_references": ["CHANGE-006"],
  "priority": "high"
}
```

Required fields:

```text
suggestion
reason
evidence_references
priority
```

Allowed `priority` values:

```text
low
medium
high
```

Suggestions should focus on release readiness, review quality, documentation,
test evidence, migration clarity, rollback clarity, or labeling quality. They
must not instruct the workflow to publish, deploy, merge, or tag.

## missing_information

Purpose: identify information that is missing or unavailable and would improve
release confidence.

Item shape:

```json
{
  "item": "CI/check-run status",
  "reason": "The collector could not access check-run evidence.",
  "evidence_references": ["CHANGE-001", "CHANGE-006"],
  "blocks_release_confidence": true
}
```

Required fields:

```text
item
reason
evidence_references
blocks_release_confidence
```

`blocks_release_confidence` must be a boolean. Use `true` when the missing
information materially affects release confidence. Use `false` for lower-risk
gaps that are useful but not central to the release decision.

## unsupported_claims

Purpose: make unsupported model output visible instead of silently trusting it.

Item shape:

```json
{
  "text": "The release improves performance.",
  "reason": "No performance evidence exists in the input package."
}
```

Required fields:

```text
text
reason
```

Unsupported claims must not be copied into customer release notes. They can be
shown to the reviewer as warnings or prompts for follow-up evidence.

## validation_notes

Purpose: explain validation-relevant observations.

Item shape:

```json
"Customer-facing suggestions reference collected evidence."
```

Each item must be a string. Validation notes are informational and must not
change safety gate results by themselves.

## Forbidden Output

The AI response must not recommend or instruct:

```text
publish release
publish the release
create tag
create a tag
move tag
move a tag
merge pull request
merge the pull request
deploy now
deploy this release
start deployment
trigger deployment
run deployment
perform deployment
```

Review questions about deployment configuration are allowed. For example:

```text
Has deployment configuration been updated?
```

That is a review question, not a publishing instruction.

## Valid Output Example

```json
{
  "summary_suggestions": [
    {
      "target": "executive_summary",
      "text": "This release contains customer-visible API improvements and one breaking configuration change.",
      "evidence_references": ["CHANGE-001", "CHANGE-003", "CHANGE-006"],
      "is_inference": true
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
      "text": "The API key environment variable rename requires deployment configuration review.",
      "evidence_references": ["CHANGE-003"],
      "is_inference": false
    }
  ],
  "reviewer_questions": [
    {
      "question": "Has deployment configuration been updated for the API key rename?",
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
      "reason": "Check-run evidence was unavailable to the collector.",
      "evidence_references": ["CHANGE-001", "CHANGE-006"],
      "blocks_release_confidence": true
    }
  ],
  "unsupported_claims": [],
  "validation_notes": [
    "Customer-facing suggestions include evidence references."
  ]
}
```

## Invalid Output Example

```json
{
  "summary_suggestions": [],
  "release_note_suggestions": [
    {
      "audience": "customer",
      "text": "The release improves performance.",
      "evidence_references": [],
      "is_inference": false
    }
  ],
  "risk_explanations": [],
  "reviewer_questions": [
    {
      "question": "Should we publish the release now?",
      "reason": "The release notes are ready.",
      "evidence_references": ["CHANGE-001"]
    }
  ],
  "process_improvement_suggestions": [
    {
      "suggestion": "Deploy immediately.",
      "reason": "The generated release notes look complete.",
      "evidence_references": ["CHANGE-001"],
      "priority": "urgent"
    }
  ],
  "missing_information": [],
  "unsupported_claims": [],
  "validation_notes": []
}
```

Reasons this is invalid:

- The customer-facing performance claim has no evidence reference.
- The AI recommends a publishing action.
- The process-improvement priority uses an unsupported enum value.
- The performance claim should be listed in `unsupported_claims` unless evidence
  exists.

## n8n Failure Behavior

If `ai_review_validation.valid` is `false`, n8n should:

- stop using AI suggestions for reviewer-facing artifacts
- keep the deterministic analysis output
- show validation errors to the reviewer
- add a warning or blocker before approval, depending on the safety policy
- avoid publishing or GitHub write actions

The workflow may allow one retry with validation feedback in a later phase. For
the current preview demo, validation failure should require human review.
