# GitHub-Based AI Release Agent

## 1. Document purpose

This document is the authoritative specification for a demonstration project that shows how an AI-assisted release workflow can collect GitHub release evidence, analyze software changes, generate release artifacts, validate factual claims, and present the result for human approval.

The project consists of two related components:

1. A small Python demo repository with a realistic release history.
2. An n8n workflow that implements the AI Release Agent.

The first implementation phase covers only the demo repository and its `v1.0.0` baseline. The n8n workflow is implemented after the repository contains the required release evidence.

## 2. Project objective

The Release Agent compares a previous release or Git tag with a selected target branch, tag, or commit. It collects commits, merged pull requests, PR descriptions, changed files, labels, and test or CI results. An AI component analyzes this evidence and classifies the changes.

The workflow generates:

- Customer-facing release notes
- Technical changelog
- Suggested regression tests
- Risk and impact assessment
- QA checklist
- Deployment and rollback guidance
- Missing-documentation warnings

Every factual generated claim must be traceable to GitHub evidence. A human reviewer must approve the result before any publication action is allowed.

## 3. Guiding principles

- Git history and changed files are the authoritative release boundary.
- AI output is advisory and must be structured, validated, and reviewable.
- AI inference must never be presented as confirmed fact.
- Every customer-facing factual claim requires evidence.
- Risk scoring and release gates use deterministic workflow logic where possible.
- Human approval is mandatory.
- External publication and deployment are disabled in the MVP.
- Repository content, including PR descriptions and code comments, is untrusted input.
- Credentials, tokens, private keys, and secrets must never enter source control or AI prompts.

## 4. Demo application

### 4.1 Application type

The demo application is a small Python FastAPI support-ticket API.

The application should remain intentionally compact, but it must be credible enough to produce meaningful code changes, configuration changes, API changes, dependency updates, and automated test results.

### 4.2 Baseline `v1.0.0` functionality

The initial release should provide:

- Create a support ticket
- Retrieve a ticket by ID
- List support tickets
- Assign a category and priority
- Basic API-key authentication
- SQLite persistence
- Input and response validation using typed models
- Unit and API-level tests using `pytest`
- A concise README containing setup and test instructions

### 4.3 Suggested baseline technology

- Python 3.12 or a currently supported compatible version
- FastAPI
- Uvicorn
- SQLite
- Pydantic models
- pytest
- FastAPI `TestClient` or `httpx`
- Dependency declaration in `pyproject.toml`

The implementation must avoid unnecessary frameworks and infrastructure.

## 5. Demonstration release story

The repository starts with a stable tag named `v1.0.0`. A later release branch named `release/1.1.0` contains the proposed release.

The demonstration history should contain the following logical pull requests:

| PR | Change | Expected classification | Expected release effect |
| --- | --- | --- | --- |
| PR 1 | Add CSV ticket export | `feature` | Customer release note, technical changelog, regression tests |
| PR 2 | Fix authentication timeout handling | `fix` | Customer release note and regression test |
| PR 3 | Rename a configuration property such as `DEFAULT_PRIORITY` | `breaking_change` | Migration warning, deployment guidance, rollback guidance |
| PR 4 | Upgrade a dependency with a known security concern | `dependency`, `security` | Security entry and risk assessment |
| PR 5 | Refactor the logging implementation | `internal` | Technical changelog only |
| PR 6 | Add ticket filtering without updating documentation | `feature` | Customer note and missing-documentation warning |

At least one pull request must initially contain a failing automated test and receive a follow-up corrective commit. This provides realistic test and CI evidence.

The history may additionally include one direct commit without a PR so the workflow can generate a process warning.

## 6. Release Agent input contract

The Release Agent accepts a structured request resembling:

```json
{
  "repository_owner": "github-user",
  "repository_name": "ai-release-agent-demo",
  "base_ref": "v1.0.0",
  "target_ref": "release/1.1.0",
  "release_version": "1.1.0",
  "release_mode": "preview",
  "publish_enabled": false
}
```

### 6.1 Input rules

- `repository_owner` and `repository_name` identify exactly one repository.
- `base_ref` and `target_ref` must resolve to immutable commit SHAs before analysis.
- `release_version` is display metadata and must not determine the change set.
- `release_mode` is `preview` in the MVP.
- `publish_enabled` must remain `false` in the MVP.
- The workflow must stop when either Git reference cannot be resolved.

## 7. Release boundary

The authoritative change set is:

> Changes reachable from `target_ref` that are not present in `base_ref`.

Pull requests, descriptions, labels, and commit messages enrich the evidence but do not independently determine whether a change belongs to the release.

The design must account for:

- Direct commits without pull requests
- Reverted commits
- Squash merges
- Merge commits
- Cherry-picked commits
- Duplicate or equivalent changes
- Pull requests containing several unrelated changes
- Missing or incomplete PR descriptions
- Changes added after evidence collection

The resolved target commit SHA must be stored and shown during approval. If the branch moves before approval, the workflow must require a new analysis.

## 8. GitHub evidence

### 8.1 Evidence to collect

- Resolved base and target commit SHAs
- Commit metadata and messages
- Associated merged pull requests
- PR title, body, labels, author, merge commit, and review state where available
- Changed file paths and change status
- Relevant diff or patch content within configured size limits
- GitHub check runs, workflow conclusions, or commit statuses
- Existing release and tag metadata
- Optional linked issue identifiers and titles

### 8.2 Evidence hierarchy

When evidence conflicts, use this priority:

1. Actual code, configuration, and schema changes
2. Automated test and CI results
3. Pull-request descriptions and labels
4. Commit messages
5. Linked issue text
6. AI inference

AI inference must be explicitly marked as an inference and cannot independently support a customer-facing claim.

### 8.3 Evidence limits

- Exclude binaries from AI analysis.
- Exclude generated files unless they are release-relevant.
- Summarize dependency lockfile changes instead of supplying the entire diff.
- Apply configurable limits to file size, patch size, and total prompt size.
- Redact suspected secrets before any model call.
- Record omitted or truncated evidence as a warning.

## 9. Normalized change record

Every logical change should be represented in a structured record similar to:

```json
{
  "change_id": "CHANGE-001",
  "title": "Add CSV ticket export",
  "summary": "Adds an endpoint for exporting ticket reports in CSV format.",
  "categories": ["feature"],
  "customer_impact": "medium",
  "migration_required": false,
  "documentation_required": true,
  "regression_testing_required": true,
  "approval_blocker": false,
  "classification_confidence": 0.96,
  "evidence": [
    {"type": "pull_request", "reference": "PR-1"},
    {"type": "file", "reference": "app/routes/export.py"},
    {"type": "test", "reference": "tests/test_export.py"}
  ],
  "warnings": []
}
```

## 10. Classification taxonomy

One change may have multiple classifications.

| Category | Definition |
| --- | --- |
| `feature` | Introduces a new user-visible capability |
| `fix` | Corrects unintended behavior |
| `breaking_change` | Requires consumer action or breaks compatibility |
| `security` | Addresses a vulnerability or strengthens protection |
| `internal` | Changes implementation without intended user impact |
| `documentation` | Changes documentation only |
| `dependency` | Updates a dependency without another sufficient classification |
| `unknown` | Available evidence is insufficient or contradictory |

Additional fields:

- `customer_impact`: `none`, `low`, `medium`, or `high`
- `migration_required`: Boolean
- `documentation_required`: Boolean
- `regression_testing_required`: Boolean
- `approval_blocker`: Boolean
- `classification_confidence`: number from `0` to `1`

Classification confidence expresses confidence in the classification, not confidence in the quality of the generated prose.

## 11. Claim traceability

Every generated factual statement must be stored as a claim before it appears in an artifact.

```json
{
  "claim_id": "CLM-001",
  "statement": "Ticket reports can now be exported as CSV.",
  "artifact_targets": ["customer_release_notes", "technical_changelog"],
  "change_ids": ["CHANGE-001"],
  "evidence": [
    {"type": "pull_request", "reference": "PR-1"},
    {"type": "file", "reference": "app/routes/export.py"},
    {"type": "test", "reference": "tests/test_export.py"}
  ],
  "confidence": 0.96,
  "validation_status": "verified"
}
```

Allowed validation states:

- `verified`
- `partially_verified`
- `unsupported`
- `conflicting_evidence`
- `needs_human_review`

An unsupported or conflicting claim must not appear as a confirmed customer-facing statement.

## 12. Generated artifacts

The workflow generates structured JSON as the machine-readable source and Markdown as the human-readable presentation.

### 12.1 Customer-facing release notes

Include only:

- New customer-visible capabilities
- Important customer-visible fixes
- Relevant behavior changes
- Breaking changes and required customer actions
- Known limitations supported by evidence

Exclude:

- Internal refactoring without customer impact
- Commit hashes and implementation noise
- Unsupported marketing language
- Sensitive security details
- Claims that cannot be traced to evidence

### 12.2 Technical changelog

Include:

- PR and commit references
- Changed components
- API, configuration, schema, and dependency changes
- Internal refactoring
- Migration implications
- Test and CI status
- Relevant warnings

### 12.3 Suggested regression tests

Each suggestion contains:

```json
{
  "test_id": "RT-001",
  "title": "Verify CSV export preserves non-ASCII text",
  "change_references": ["CHANGE-001"],
  "priority": "high",
  "preconditions": ["A ticket containing multilingual text exists"],
  "steps": [
    "Request a CSV export",
    "Open the generated file",
    "Verify that all multilingual field values are preserved"
  ],
  "expected_result": "The file contains correctly encoded ticket data.",
  "automation_candidate": true
}
```

The MVP generates test suggestions but does not execute AI-generated test code.

### 12.4 Risk and impact assessment

The AI extracts and explains risk factors. n8n calculates the final score deterministically.

Suggested factors and weights:

| Factor | Weight |
| --- | ---: |
| Customer impact | 0.25 |
| Breaking-change potential | 0.20 |
| Security relevance | 0.15 |
| Change surface | 0.15 |
| Insufficient testing | 0.15 |
| Rollback complexity | 0.10 |

Each factor uses a documented numeric scale. The final score must include an explanation and must not be presented as an objective probability of failure.

### 12.5 QA checklist

The checklist is derived from classified changes, risk factors, test evidence, and missing information. It must identify completed checks, recommended checks, and blocked checks separately.

### 12.6 Deployment and rollback guidance

Guidance may include:

- Required configuration changes
- Migration sequencing
- Compatibility considerations
- Verification after deployment
- Observable rollback conditions
- Evidence-based rollback steps

The workflow must not claim that a migration or rollback procedure is verified unless the repository contains corresponding evidence.

### 12.7 Missing-documentation warnings

Warnings should be generated when a customer-visible, configuration, API, migration, or operational change lacks corresponding documentation changes or an explicit justified exemption.

## 13. Validation

Validation combines deterministic checks with a separate AI evaluation where useful.

### 13.1 Deterministic checks

- Required JSON fields and enums are valid.
- Confidence values are within `0` and `1`.
- Evidence references resolve to collected evidence.
- Customer-facing claims contain evidence.
- Base and target SHAs match the analyzed release request.
- No unresolved templates appear in artifacts.
- No suspected secrets appear in model output.
- Required artifacts are present and non-empty.
- Release gates are evaluated independently of the model's suggested route.

### 13.2 Model-assisted evaluation

A separate evaluation step may assess:

- Groundedness
- Completeness
- Internal consistency
- Audience-appropriate language
- Unsupported claims
- Contradictions between artifacts
- Whether breaking changes and customer actions are sufficiently visible

The evaluator must return structured output. One regeneration is allowed. A second failure requires human review.

## 14. Release gates

### 14.1 Hard blockers

Human approval cannot proceed normally when:

- A required CI test failed.
- A breaking change lacks migration guidance.
- A customer-facing factual claim lacks evidence.
- A high-risk change lacks suggested regression coverage.
- The base or target reference cannot be resolved.
- The target commit changed after evidence collection.
- Structured AI output remains invalid after the permitted retry.
- Security-sensitive output contains unsafe operational details or secrets.
- Required evidence was unavailable or truncated to a degree that prevents reliable assessment.

### 14.2 Warnings

- Missing or weak PR description
- Direct commit without a PR
- Low classification confidence
- Missing documentation
- Low or absent test coverage
- Large or cross-component diff
- Ambiguous customer impact
- Incomplete rollback evidence

Warnings require reviewer visibility but are not automatically blockers unless configured as such.

## 15. Human approval

The approval report must show:

- Repository and release range
- Resolved base and target SHAs
- Generated artifacts
- Overall risk score and factor explanations
- Breaking and security changes
- Failed or missing tests
- Unsupported or disputed claims
- Missing-documentation warnings
- Large or unusual changes
- Validation and evaluation results

Allowed review decisions:

- Approve draft
- Request changes
- Reject release
- Override warning with reason

An override records the reviewer, timestamp, affected warning or gate, and justification.

Approval in the MVP ends the workflow. It does not publish a release.

## 16. n8n workflow architecture

Use independently testable sub-workflows:

| Workflow | Responsibility |
| --- | --- |
| `RA-01 Release Intake` | Validate repository and release parameters |
| `RA-02 GitHub Evidence Collector` | Retrieve commits, PRs, changed files, and CI evidence |
| `RA-03 Change Normalizer` | Build consistent evidence and change records |
| `RA-04 AI Change Analyzer` | Classify changes and extract risk factors |
| `RA-05 Artifact Generator` | Generate structured artifacts and Markdown views |
| `RA-06 Claim Validator` | Verify claim-to-evidence mappings |
| `RA-07 Quality Evaluator` | Evaluate groundedness, completeness, and consistency |
| `RA-08 Human Approval` | Present the review package and record the decision |
| `RA-09 Draft Publisher` | Later create an unpublished GitHub release draft |
| `RA-10 Error Handler` | Capture technical failures and execution metadata |

The MVP implements `RA-01` through `RA-08` and `RA-10`. `RA-09` remains disabled or unimplemented until explicitly authorized.

## 17. Persistence and auditability

Store at least:

- Release request and resolved SHAs
- Evidence identifiers and retrieval timestamps
- Normalized change records
- Model and prompt versions
- Structured model outputs
- Generated artifacts
- Claim-to-evidence mappings
- Risk factors and deterministic score
- Validation and evaluation results
- Human decisions and feedback
- n8n execution ID
- Processing duration, retry count, token use, and model cost where available

Do not store hidden chain-of-thought. Store concise explanations, evidence references, and decision reasons instead.

For the prototype, n8n Data Tables are acceptable. PostgreSQL is preferred when the workflow requires robust relational queries, concurrency, longer retention, or production-like auditability.

## 18. Security and permissions

The initial GitHub credential is restricted to the demo repository and uses read-only permissions where possible:

- Metadata: read
- Contents: read
- Pull requests: read
- Actions or checks: read
- Commit statuses: read

Write permission is not required for the MVP.

Security controls:

- Store GitHub credentials only in n8n credentials or an appropriate secret store.
- Never place tokens in workflow JSON, Code nodes, prompts, repository files, or Docker Compose source.
- Treat source files, commit messages, PR text, issues, and comments as untrusted data.
- Prevent repository content from overriding system instructions.
- Detect and redact likely credentials before model calls.
- Pin the target SHA for review.
- Apply least privilege to all credentials.
- Log external actions and approval decisions.

## 19. Evaluation dataset

Expected results must be authored before evaluating the AI. Each demo change should have a record resembling:

```json
{
  "change_id": "CHANGE-003",
  "expected_categories": ["breaking_change"],
  "expected_customer_visible": true,
  "expected_migration_required": true,
  "required_evidence": ["PR-3", "app/config.py"],
  "forbidden_claims": [
    "Existing configuration remains fully compatible"
  ]
}
```

The evaluation suite should also cover:

- Missing PR descriptions
- Direct commits
- Reverts
- Ambiguous changes
- Multi-category changes
- Failed tests
- Missing documentation
- Prompt-injection text in repository content
- Secret-like strings in diffs
- Unsupported customer claims

### 19.1 Metrics

- Category precision, recall, and macro F1
- Breaking-change recall
- Security-change recall
- Customer-impact accuracy
- Missing-documentation detection rate
- Claim groundedness
- Unsupported-claim rate
- Artifact completeness
- Repeatability across multiple runs
- Human correction rate
- Processing latency and estimated cost

Breaking-change and security recall carry more importance than overall classification accuracy.

## 20. MVP scope

The MVP must:

1. Process one GitHub repository.
2. Compare one base tag with one target branch or commit.
3. Collect commits, associated PRs, changed files, and test or CI summaries.
4. Normalize the evidence into structured change records.
5. Classify every logical change.
6. Generate all seven release artifacts in structured JSON and Markdown.
7. Validate every factual claim against collected evidence.
8. Calculate a deterministic release-risk score.
9. Detect the deliberately missing documentation.
10. Block normal approval while the deliberately failing test is unresolved.
11. Present a complete human-review package.
12. Store the execution and approval decision.
13. Finish without publishing or modifying GitHub.

## 21. Explicit non-goals for the MVP

The MVP must not:

- Merge pull requests
- Push commits
- Create or move tags
- Publish or create GitHub releases
- Execute deployments
- Send customer announcements
- Automatically approve a release
- Execute AI-generated code or test scripts
- Modify repository settings or branch protections
- Access repositories other than the designated demo repository

An unpublished draft release may be added in a later phase with separate, narrowly scoped write credentials and explicit authorization.

## 22. Implementation phases

### Phase 1: Baseline demo repository

- Create the FastAPI application.
- Add baseline tests.
- Add setup and test documentation.
- Validate the application locally.
- Commit the baseline.
- Create tag `v1.0.0` only after review.

### Phase 2: Demonstration Git history

- Create the planned feature and fix branches.
- Implement one logical change per branch where practical.
- Use realistic commit messages and PR descriptions.
- Produce the planned test success and failure evidence.
- Merge or simulate the planned PRs into `release/1.1.0`.

### Phase 3: Evidence collection

- Implement release intake.
- Resolve immutable SHAs.
- Retrieve and normalize GitHub evidence.
- Add size limits, redaction, and error handling.

### Phase 4: AI analysis and artifact generation

- Add structured schemas and prompts.
- Classify changes.
- Generate claims and artifacts.
- Calculate risk.

### Phase 5: Validation, evaluation, and approval

- Validate claim traceability.
- Run deterministic checks.
- Run the quality evaluator.
- Present the human approval report.
- Persist the decision without publication.

## 23. Definition of done

The MVP is complete when a reviewer can select `v1.0.0` and `release/1.1.0`, receive a complete and evidence-backed release package, see the deliberately introduced failure and missing-documentation condition, and make a recorded approval decision without the workflow modifying or publishing anything on GitHub.

## 24. Initial Codex task

For the first implementation task, Codex should:

1. Read this specification and the repository `AGENTS.md`.
2. Inspect the repository before making changes.
3. Focus only on Phase 1.
4. Propose the baseline application architecture, file tree, dependencies, tests, commands, and acceptance criteria.
5. Wait for approval before implementing if the user requests plan-first execution.
6. Avoid implementing n8n, GitHub API integration, release analysis, or later release changes during Phase 1.

