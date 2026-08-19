
from typing import Any

from release_agent.errors import ReleaseAgentError


class AIReviewValidationError(ReleaseAgentError):
    """Raised when AI-assisted review output fails deterministic validation."""


def build_ai_input_package(analysis: dict[str, Any]) -> dict[str, Any]:
    artifacts = analysis.get("artifacts", {})
    risk = artifacts.get("risk_and_impact_assessment", {})

    return {
        "repository": analysis["repository"],
        "release_range": analysis["release_range"],
        "base_sha": analysis["base_sha"],
        "target_sha": analysis["target_sha"],
        "changes": [_compact_change(change) for change in analysis.get("changes", [])],
        "neutral_change_evidence": [
            _neutral_change_evidence(change) for change in analysis.get("changes", [])
        ],
        "risk_assessment": {
            "level": risk.get("level"),
            "score": risk.get("score"),
            "factors": risk.get("factors", []),
        },
        "warnings": analysis.get("warnings", []),
        "missing_documentation_warnings": artifacts.get(
            "missing_documentation_warnings",
            [],
        ),
        "existing_artifacts": {
            "customer_release_notes": artifacts.get("customer_release_notes", ""),
            "technical_changelog": artifacts.get("technical_changelog", ""),
            "qa_checklist": artifacts.get("qa_checklist", []),
            "deployment_and_rollback_guidance": artifacts.get(
                "deployment_and_rollback_guidance",
                "",
            ),
        },
    }


def _neutral_change_evidence(change: dict[str, Any]) -> dict[str, Any]:
    evidence = change.get("evidence", [])
    source = change.get("source_evidence", {})
    pull_request = source.get("pull_request", {})
    source_files = source.get("files", [])
    return {
        "change_id": change["change_id"],
        "title": change["title"],
        "summary": change.get("summary", ""),
        "source_pull_requests": [
            item["reference"]
            for item in evidence
            if item.get("type") == "pull_request"
        ],
        "pull_request": {
            "number": pull_request.get("number"),
            "title": pull_request.get("title"),
            "body": pull_request.get("body", ""),
            "labels": pull_request.get("labels", []),
            "html_url": pull_request.get("html_url"),
        },
        "changed_files": [
            item["reference"]
            for item in evidence
            if item.get("type") == "file"
        ],
        "file_evidence": [
            {
                "filename": file.get("filename"),
                "status": file.get("status"),
                "additions": file.get("additions"),
                "deletions": file.get("deletions"),
                "changes": file.get("changes"),
                "patch_excerpt": file.get("patch_excerpt"),
                "omitted_reason": file.get("omitted_reason"),
            }
            for file in source_files
        ],
        "warnings": change.get("warnings", []),
        "evidence_references": [change["change_id"]],
    }


def generate_demo_ai_review_draft(ai_input: dict[str, Any]) -> dict[str, Any]:
    customer_changes = [
        change
        for change in ai_input.get("changes", [])
        if change.get("customer_impact") != "none"
    ]
    breaking_changes = [
        change
        for change in ai_input.get("changes", [])
        if change.get("migration_required")
        or "breaking_change" in change.get("categories", [])
    ]
    regression_changes = [
        change
        for change in customer_changes
        if change.get("regression_testing_required")
    ]
    documentation_gaps = [
        change
        for change in customer_changes
        if change.get("documentation_required") and change.get("warnings")
    ]

    release_note_suggestions = [
        {
            "audience": "customer",
            "text": change["summary"],
            "evidence_references": [change["change_id"]],
            "is_inference": False,
        }
        for change in customer_changes[:5]
    ]

    reviewer_questions = [
        {
            "question": (
                "Has deployment configuration been updated for "
                f"{change['title']}?"
            ),
            "reason": "A migration or breaking-change signal is present.",
            "evidence_references": [change["change_id"]],
        }
        for change in breaking_changes
    ]
    if regression_changes:
        reviewer_questions.append(
            {
                "question": "Have the customer-visible API paths been tested manually?",
                "reason": "Customer-visible changes require regression attention.",
                "evidence_references": [
                    change["change_id"] for change in regression_changes[:5]
                ],
            }
        )

    risk = ai_input.get("risk_assessment", {})
    risk_level = risk.get("level", "unknown")
    risk_score = risk.get("score", "unknown")
    customer_change_ids = [change["change_id"] for change in customer_changes]

    return {
        "summary_suggestions": [
            {
                "target": "executive_summary",
                "text": (
                    f"This release contains {len(customer_changes)} customer-visible "
                    f"change(s) and has {risk_level} review risk ({risk_score})."
                ),
                "evidence_references": customer_change_ids,
                "is_inference": True,
            }
        ],
        "release_note_suggestions": release_note_suggestions,
        "risk_explanations": [
            {
                "factor": "overall_release_risk",
                "text": (
                    "Risk should be reviewed carefully because the deterministic "
                    f"assessment classified this release as {risk_level}."
                ),
                "evidence_references": customer_change_ids,
                "is_inference": True,
            }
        ],
        "reviewer_questions": reviewer_questions,
        "process_improvement_suggestions": _build_process_improvement_suggestions(
            breaking_changes,
            documentation_gaps,
            ai_input.get("warnings", []),
            customer_change_ids,
        ),
        "missing_information": _build_missing_information(
            documentation_gaps,
            ai_input.get("warnings", []),
            customer_change_ids,
        ),
        "unsupported_claims": [],
        "validation_notes": [
            "Demo draft generated from deterministic analysis output.",
            "Replace this draft generator with a model call in the AI-assisted n8n phase.",
        ],
        "draft_source": "deterministic_demo_generator",
    }


def validate_ai_review_draft(
    ai_input: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    available_references = {
        change["change_id"]
        for change in ai_input.get("changes", [])
        if change.get("change_id")
    }
    errors: list[str] = []
    warnings: list[str] = []

    _require_list(draft, "summary_suggestions", errors)
    _require_list(draft, "release_note_suggestions", errors)
    _require_list(draft, "risk_explanations", errors)
    _require_list(draft, "reviewer_questions", errors)
    _require_list(draft, "process_improvement_suggestions", errors)
    _require_list(draft, "missing_information", errors)
    _require_list(draft, "unsupported_claims", errors)
    _require_list(draft, "validation_notes", errors)

    for section in (
        "summary_suggestions",
        "release_note_suggestions",
        "risk_explanations",
    ):
        for index, item in enumerate(draft.get(section, [])):
            _validate_text_item(
                item,
                f"{section}[{index}]",
                available_references,
                errors,
                warnings,
                require_evidence=section == "release_note_suggestions",
            )

    for index, item in enumerate(draft.get("reviewer_questions", [])):
        _validate_question_item(
            item,
            f"reviewer_questions[{index}]",
            available_references,
            errors,
            warnings,
        )

    for index, item in enumerate(draft.get("process_improvement_suggestions", [])):
        _validate_process_improvement_item(
            item,
            f"process_improvement_suggestions[{index}]",
            available_references,
            errors,
        )

    for index, item in enumerate(draft.get("missing_information", [])):
        _validate_missing_information_item(
            item,
            f"missing_information[{index}]",
            available_references,
            errors,
        )

    if _contains_forbidden_action(draft):
        errors.append("AI review draft must not recommend publishing or GitHub write actions.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "available_evidence_references": sorted(available_references),
    }


def validate_ai_review_or_raise(
    ai_input: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    result = validate_ai_review_draft(ai_input, draft)
    if not result["valid"]:
        raise AIReviewValidationError("; ".join(result["errors"]))
    return result


def build_review_artifacts(
    ai_input: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, str]:
    existing = ai_input.get("existing_artifacts", {})
    risk = ai_input.get("risk_assessment", {})
    changes = ai_input.get("changes", [])
    missing_docs = ai_input.get("missing_documentation_warnings", [])

    artifacts = {
        "customer_release_notes": _build_customer_release_notes(existing, draft),
        "technical_changelog": existing.get("technical_changelog", ""),
        "suggested_regression_tests": _build_suggested_regression_tests(changes),
        "risk_and_impact_assessment": _build_risk_and_impact_assessment(risk, draft),
        "qa_checklist": _build_qa_checklist(existing, ai_input),
        "deployment_and_rollback_guidance": existing.get(
            "deployment_and_rollback_guidance",
            "",
        ),
        "missing_documentation_warnings": _build_missing_documentation_warnings(
            missing_docs,
        ),
    }
    artifacts["review_artifact_markdown"] = _build_review_artifact_markdown(artifacts)
    return artifacts


def _compact_change(change: dict[str, Any]) -> dict[str, Any]:
    return {
        "change_id": change["change_id"],
        "title": change["title"],
        "summary": change["summary"],
        "categories": change.get("categories", []),
        "customer_impact": change.get("customer_impact"),
        "migration_required": change.get("migration_required", False),
        "documentation_required": change.get("documentation_required", False),
        "regression_testing_required": change.get("regression_testing_required", False),
        "warnings": change.get("warnings", []),
        "evidence": change.get("evidence", []),
    }


def _build_customer_release_notes(
    existing: dict[str, Any],
    draft: dict[str, Any],
) -> str:
    notes = [existing.get("customer_release_notes", "").strip()]
    suggestions = [
        item
        for item in draft.get("release_note_suggestions", [])
        if item.get("audience") == "customer" and str(item.get("text", "")).strip()
    ]
    if suggestions:
        notes.extend(
            [
                "## AI-Suggested Customer Wording",
                *[
                    f"- {item['text']} ({', '.join(item.get('evidence_references', []))})"
                    for item in suggestions
                ],
            ]
        )
    return "\n\n".join(note for note in notes if note)


def _build_suggested_regression_tests(changes: list[dict[str, Any]]) -> str:
    candidates = [
        change
        for change in changes
        if change.get("regression_testing_required")
        or change.get("customer_impact") in {"medium", "high"}
    ]
    if not candidates:
        return "No targeted regression tests suggested from the current evidence."

    lines = ["# Suggested Regression Tests", ""]
    for change in candidates:
        lines.extend(
            [
                f"- **{change['change_id']}** {change['title']}",
                f"  - Verify: {change['summary']}",
                "  - Expected: customer-visible behavior matches the release note and existing API behavior is unchanged.",
            ]
        )
    return "\n".join(lines)


def _build_risk_and_impact_assessment(
    risk: dict[str, Any],
    draft: dict[str, Any],
) -> str:
    lines = [
        "# Risk And Impact Assessment",
        "",
        f"- Level: {risk.get('level', 'unknown')}",
        f"- Score: {risk.get('score', 'unknown')}",
    ]
    factors = risk.get("factors", [])
    if factors:
        lines.append("- Deterministic factors:")
        for factor in factors:
            name = factor.get("name", "unknown")
            explanation = factor.get("explanation", "")
            lines.append(f"  - {name}: {explanation}")

    explanations = draft.get("risk_explanations", [])
    if explanations:
        lines.extend(["", "## AI-Assisted Risk Context"])
        for item in explanations:
            refs = ", ".join(item.get("evidence_references", []))
            lines.append(f"- {item.get('factor', 'other')}: {item.get('text', '')} ({refs})")
    return "\n".join(lines)


def _build_qa_checklist(
    existing: dict[str, Any],
    ai_input: dict[str, Any],
) -> str:
    checks = existing.get("qa_checklist", [])
    lines = ["# QA Checklist", ""]
    if checks:
        for check in checks:
            refs = ", ".join(check.get("change_references", []))
            lines.append(f"- [{check.get('status', 'todo')}] {check.get('title', '')} ({refs})")
    else:
        lines.append("- No deterministic QA checklist items were generated.")

    warnings = ai_input.get("warnings", [])
    if warnings:
        lines.extend(["", "## Evidence Warnings"])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def _build_missing_documentation_warnings(warnings: list[str]) -> str:
    if not warnings:
        return "No missing-documentation warnings were found."
    return "\n".join(["# Missing Documentation Warnings", "", *[f"- {warning}" for warning in warnings]])


def _build_review_artifact_markdown(artifacts: dict[str, str]) -> str:
    sections = [
        ("Customer-Facing Release Notes", artifacts["customer_release_notes"]),
        ("Technical Changelog", artifacts["technical_changelog"]),
        ("Suggested Regression Tests", artifacts["suggested_regression_tests"]),
        ("Risk And Impact Assessment", artifacts["risk_and_impact_assessment"]),
        ("QA Checklist", artifacts["qa_checklist"]),
        ("Deployment And Rollback Guidance", artifacts["deployment_and_rollback_guidance"]),
        ("Missing Documentation Warnings", artifacts["missing_documentation_warnings"]),
    ]
    return "\n\n".join(
        f"## {title}\n\n{content.strip()}" for title, content in sections if content.strip()
    )


def _build_process_improvement_suggestions(
    breaking_changes: list[dict[str, Any]],
    documentation_gaps: list[dict[str, Any]],
    warnings: list[str],
    customer_change_ids: list[str],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []

    for change in breaking_changes[:3]:
        suggestions.append(
            {
                "suggestion": "Add a migration checklist for the breaking configuration change.",
                "reason": f"{change['change_id']} requires deployment configuration review.",
                "evidence_references": [change["change_id"]],
                "priority": "high",
            }
        )

    for change in documentation_gaps[:3]:
        suggestions.append(
            {
                "suggestion": "Add customer-facing documentation before release.",
                "reason": f"{change['change_id']} is customer-visible and has documentation warnings.",
                "evidence_references": [change["change_id"]],
                "priority": "high",
            }
        )

    if "check_runs_unavailable" in warnings and customer_change_ids:
        suggestions.append(
            {
                "suggestion": "Record manual CI/check-run verification in the release review.",
                "reason": "Check-run evidence was unavailable to the collector.",
                "evidence_references": customer_change_ids[:5],
                "priority": "medium",
            }
        )

    return suggestions


def _build_missing_information(
    documentation_gaps: list[dict[str, Any]],
    warnings: list[str],
    customer_change_ids: list[str],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []

    if "check_runs_unavailable" in warnings and customer_change_ids:
        missing.append(
            {
                "item": "CI/check-run status",
                "reason": "The collector could not access check-run evidence.",
                "evidence_references": customer_change_ids[:5],
                "blocks_release_confidence": True,
            }
        )

    for change in documentation_gaps[:3]:
        missing.append(
            {
                "item": f"Customer documentation for {change['title']}",
                "reason": f"{change['change_id']} has a missing-documentation warning.",
                "evidence_references": [change["change_id"]],
                "blocks_release_confidence": True,
            }
        )

    return missing


def _require_list(payload: dict[str, Any], field: str, errors: list[str]) -> None:
    if not isinstance(payload.get(field), list):
        errors.append(f"{field} must be a list.")


def _validate_text_item(
    item: dict[str, Any],
    path: str,
    available_references: set[str],
    errors: list[str],
    warnings: list[str],
    require_evidence: bool,
) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object.")
        return
    if not str(item.get("text", "")).strip():
        errors.append(f"{path}.text is required.")
    references = item.get("evidence_references", [])
    if require_evidence and not references:
        errors.append(f"{path}.evidence_references is required.")
    _validate_references(path, references, available_references, errors)
    if item.get("is_inference") is True:
        warnings.append(f"{path} is marked as inference.")


def _validate_question_item(
    item: dict[str, Any],
    path: str,
    available_references: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object.")
        return
    if not str(item.get("question", "")).strip():
        errors.append(f"{path}.question is required.")
    if not str(item.get("reason", "")).strip():
        errors.append(f"{path}.reason is required.")
    _validate_references(path, item.get("evidence_references", []), available_references, errors)
    if not item.get("evidence_references"):
        warnings.append(f"{path} has no evidence references.")


def _validate_process_improvement_item(
    item: dict[str, Any],
    path: str,
    available_references: set[str],
    errors: list[str],
) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object.")
        return
    if not str(item.get("suggestion", "")).strip():
        errors.append(f"{path}.suggestion is required.")
    if not str(item.get("reason", "")).strip():
        errors.append(f"{path}.reason is required.")
    if item.get("priority") not in {"low", "medium", "high"}:
        errors.append(f"{path}.priority must be one of: low, medium, high.")
    references = item.get("evidence_references", [])
    if not references:
        errors.append(f"{path}.evidence_references is required.")
    _validate_references(path, references, available_references, errors)


def _validate_missing_information_item(
    item: dict[str, Any],
    path: str,
    available_references: set[str],
    errors: list[str],
) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object.")
        return
    if not str(item.get("item", "")).strip():
        errors.append(f"{path}.item is required.")
    if not str(item.get("reason", "")).strip():
        errors.append(f"{path}.reason is required.")
    if not isinstance(item.get("blocks_release_confidence"), bool):
        errors.append(f"{path}.blocks_release_confidence must be a boolean.")
    references = item.get("evidence_references", [])
    if not references:
        errors.append(f"{path}.evidence_references is required.")
    _validate_references(path, references, available_references, errors)


def _validate_references(
    path: str,
    references: Any,
    available_references: set[str],
    errors: list[str],
) -> None:
    if not isinstance(references, list):
        errors.append(f"{path}.evidence_references must be a list.")
        return
    for reference in references:
        if reference not in available_references:
            errors.append(f"{path} references unknown evidence: {reference}.")


def _contains_forbidden_action(payload: Any) -> bool:
    forbidden_phrases = (
        "publish release",
        "publish the release",
        "create tag",
        "create a tag",
        "move tag",
        "move a tag",
        "merge pull request",
        "merge the pull request",
        "deploy now",
        "deploy this release",
        "start deployment",
        "trigger deployment",
        "run deployment",
        "perform deployment",
    )
    if isinstance(payload, dict):
        return any(_contains_forbidden_action(value) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_forbidden_action(value) for value in payload)
    if isinstance(payload, str):
        lowered = payload.lower()
        return any(phrase in lowered for phrase in forbidden_phrases)
    return False
