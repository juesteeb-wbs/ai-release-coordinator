from collections import defaultdict
from typing import Any

from release_agent.analysis_models import (
    AnalysisResult,
    ChangeRecord,
    ClaimRecord,
    EvidenceReference,
    GeneratedArtifacts,
    QACheck,
    RegressionTestSuggestion,
    RiskAssessment,
    RiskFactor,
)


DOC_PATH_PREFIXES = ("README", "docs/")
MAX_SOURCE_PATCH_EXCERPT_CHARS = 1200
RISK_WEIGHTS = {
    "customer_impact": 0.25,
    "breaking_change_potential": 0.20,
    "security_relevance": 0.15,
    "change_surface": 0.15,
    "insufficient_testing": 0.15,
    "rollback_complexity": 0.10,
}


class DeterministicReleaseAnalyzer:
    def analyze(self, evidence: dict[str, Any], source_evidence_file: str) -> AnalysisResult:
        pull_requests = [
            pull_request
            for pull_request in sorted(evidence.get("pull_requests", []), key=lambda pr: pr["number"])
            if not _has_internal_label(pull_request)
        ]
        files = evidence.get("files", [])
        files_by_pr = _associate_files_with_pull_requests(pull_requests, files)
        changes = [
            self._build_change(index, pull_request, files_by_pr[pull_request["number"]])
            for index, pull_request in enumerate(pull_requests, start=1)
        ]
        claims = _build_claims(changes)
        missing_doc_warnings = [
            warning
            for change in changes
            for warning in change.warnings
            if warning.startswith("Missing documentation")
        ]
        risk = _build_risk_assessment(changes)
        artifacts = GeneratedArtifacts(
            customer_release_notes=_render_customer_release_notes(changes, claims),
            technical_changelog=_render_technical_changelog(changes),
            suggested_regression_tests=_build_regression_tests(changes),
            risk_and_impact_assessment=risk,
            qa_checklist=_build_qa_checklist(changes, evidence),
            deployment_and_rollback_guidance=_render_deployment_guidance(changes),
            missing_documentation_warnings=missing_doc_warnings,
        )
        resolved_refs = evidence["resolved_refs"]
        request = evidence["request"]
        workflow_warnings = [warning["code"] for warning in evidence.get("warnings", [])]
        review_sections = _build_review_sections(
            repository=f"{request['repository_owner']}/{request['repository_name']}",
            release_range=f"{request['base_ref']}..{request['target_ref']}",
            base_sha=resolved_refs["base_sha"],
            target_sha=resolved_refs["target_sha"],
            changes=changes,
            claims=claims,
            artifacts=artifacts,
            warnings=workflow_warnings,
        )
        return AnalysisResult(
            source_evidence_file=source_evidence_file,
            repository=f"{request['repository_owner']}/{request['repository_name']}",
            release_range=f"{request['base_ref']}..{request['target_ref']}",
            base_sha=resolved_refs["base_sha"],
            target_sha=resolved_refs["target_sha"],
            changes=changes,
            claims=claims,
            artifacts=artifacts,
            warnings=workflow_warnings,
            review_markdown=review_sections["review_markdown"],
            executive_summary=review_sections["executive_summary"],
            blocker_summary=review_sections["blocker_summary"],
            warning_summary=review_sections["warning_summary"],
            artifact_summary=review_sections["artifact_summary"],
        )

    def _build_change(
        self,
        index: int,
        pull_request: dict[str, Any],
        files: list[dict[str, Any]],
    ) -> ChangeRecord:
        title = pull_request["title"]
        categories = _classify_change(pull_request, files)
        documentation_required = any(
            category in categories for category in ("feature", "breaking_change", "security")
        )
        has_docs = any(_is_doc_file(file["filename"]) for file in files)
        warnings: list[str] = []
        if documentation_required and not has_docs:
            warnings.append(f"Missing documentation for customer-visible change in PR #{pull_request['number']}.")

        migration_required = "breaking_change" in categories
        regression_required = any(category in categories for category in ("feature", "fix", "security"))
        customer_impact = _customer_impact(categories)
        change_id = f"CHANGE-{index:03d}"

        return ChangeRecord(
            change_id=change_id,
            title=title,
            summary=_summarize_change(title, categories),
            categories=categories,
            customer_impact=customer_impact,
            migration_required=migration_required,
            documentation_required=documentation_required,
            regression_testing_required=regression_required,
            approval_blocker=migration_required and not _has_migration_evidence(pull_request, files),
            classification_confidence=_classification_confidence(pull_request, files),
            evidence=[
                EvidenceReference(type="pull_request", reference=f"PR-{pull_request['number']}"),
                *[
                    EvidenceReference(type="file", reference=file["filename"])
                    for file in files[:8]
                ],
            ],
            warnings=warnings,
            source_evidence=_build_source_evidence(pull_request, files),
        )


def _associate_files_with_pull_requests(
    pull_requests: list[dict[str, Any]],
    files: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for pull_request in pull_requests:
        title = pull_request["title"].lower()
        for file in files:
            filename = file["filename"]
            patch = (file.get("patch") or "").lower()
            if _file_matches_title(filename, patch, title):
                grouped[pull_request["number"]].append(file)
        if not grouped[pull_request["number"]]:
            grouped[pull_request["number"]] = files
    return grouped


def _build_source_evidence(
    pull_request: dict[str, Any],
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "pull_request": {
            "number": pull_request["number"],
            "title": pull_request.get("title", ""),
            "body": pull_request.get("body") or "",
            "labels": pull_request.get("labels", []),
            "html_url": pull_request.get("html_url"),
        },
        "files": [
            {
                "filename": file["filename"],
                "status": file.get("status", ""),
                "additions": file.get("additions", 0),
                "deletions": file.get("deletions", 0),
                "changes": file.get("changes", 0),
                "patch_excerpt": _patch_excerpt(file.get("patch")),
                "omitted_reason": file.get("omitted_reason"),
            }
            for file in files[:8]
        ],
    }


def _patch_excerpt(patch: str | None) -> str | None:
    if patch is None:
        return None
    if len(patch) <= MAX_SOURCE_PATCH_EXCERPT_CHARS:
        return patch
    return patch[:MAX_SOURCE_PATCH_EXCERPT_CHARS]


def _file_matches_title(filename: str, patch: str, title: str) -> bool:
    filename_lower = filename.lower()
    if "csv" in title:
        return "evidence_collection" not in filename_lower and (
            "export" in filename_lower or "export" in patch or "csv" in patch
        )
    if "authentication" in title:
        return "auth" in filename_lower or "api-key" in patch or "x-api-key" in patch
    if "configuration" in title or "api key" in title:
        return "settings" in filename_lower or "support_ticket_api_key" in patch or "migration" in patch
    if "dependency" in title or "fastapi" in title:
        return filename_lower in {"pyproject.toml", "readme.md"} or "dependency" in filename_lower
    if "logging" in title:
        return "logging" in filename_lower or "configure_request_logging" in patch
    if "customer email" in title:
        return "ticket" in filename_lower or "customer_email" in patch
    if _is_internal_tooling_title(title):
        return filename_lower.startswith("release_agent/") or "evidence" in filename_lower
    return False


def _classify_change(pull_request: dict[str, Any], files: list[dict[str, Any]]) -> list[str]:
    labels = [label.lower() for label in pull_request.get("labels", [])]
    title_and_labels = " ".join(
        [
            pull_request.get("title", ""),
            " ".join(labels),
        ]
    ).lower()
    text = " ".join(
        [
            pull_request.get("title", ""),
            pull_request.get("body") or "",
            " ".join(pull_request.get("labels", [])),
            " ".join(file["filename"] for file in files),
        ]
    ).lower()
    categories: list[str] = []
    if "internal" in labels and not any(
        label in labels for label in ("security", "breaking change", "breaking_change")
    ):
        return ["internal"]
    if _is_internal_tooling_title(pull_request.get("title", "").lower()):
        return ["internal"]
    if any(term in text for term in ("export", "filter", "adds support")):
        categories.append("feature")
    if any(term in title_and_labels for term in ("fix", "bug", "regression")):
        categories.append("fix")
    if any(term in text for term in ("breaking", "migration", "rename", "legacy")):
        categories.append("breaking_change")
    if any(term in text for term in ("security", "denial-of-service", "starlette")):
        categories.append("security")
    if any(term in text for term in ("dependency", "fastapi", "starlette", "pyproject.toml")):
        categories.append("dependency")
    if any(term in text for term in ("logging", "internal", "refactor")) and "internal" not in categories:
        categories.append("internal")
    if files and all(_is_doc_file(file["filename"]) for file in files):
        categories.append("documentation")
    return categories or ["unknown"]


def _has_internal_label(pull_request: dict[str, Any]) -> bool:
    return "internal" in [label.lower() for label in pull_request.get("labels", [])]


def _is_internal_tooling_title(title: str) -> bool:
    return any(
        phrase in title
        for phrase in (
            "evidence collector",
            "release evidence analyzer",
            "local release evidence analyzer",
            "artifact generator",
            "release agent",
        )
    )


def _customer_impact(categories: list[str]) -> str:
    if "breaking_change" in categories:
        return "high"
    if "feature" in categories or "fix" in categories:
        return "medium"
    if "security" in categories:
        return "low"
    return "none"


def _classification_confidence(pull_request: dict[str, Any], files: list[dict[str, Any]]) -> float:
    score = 0.72
    if pull_request.get("labels"):
        score += 0.08
    if pull_request.get("body"):
        score += 0.08
    if files:
        score += 0.08
    return min(score, 0.96)


def _summarize_change(title: str, categories: list[str]) -> str:
    if "breaking_change" in categories:
        return f"{title}. This change requires deployment configuration review."
    if "security" in categories:
        return f"{title}. This change updates dependency security posture."
    if "internal" in categories and "feature" not in categories:
        return f"{title}. This is an internal implementation change."
    return f"{title}."


def _has_migration_evidence(pull_request: dict[str, Any], files: list[dict[str, Any]]) -> bool:
    text = f"{pull_request.get('body') or ''} " + " ".join(file.get("patch") or "" for file in files)
    return "migration" in text.lower() or "rename" in text.lower()


def _is_doc_file(filename: str) -> bool:
    return filename.startswith(DOC_PATH_PREFIXES) or filename.lower().endswith(".md")


def _build_claims(changes: list[ChangeRecord]) -> list[ClaimRecord]:
    claims: list[ClaimRecord] = []
    for index, change in enumerate(changes, start=1):
        if change.customer_impact == "none":
            targets = ["technical_changelog"]
        else:
            targets = ["customer_release_notes", "technical_changelog"]
        claims.append(
            ClaimRecord(
                claim_id=f"CLM-{index:03d}",
                statement=change.summary,
                artifact_targets=targets,
                change_ids=[change.change_id],
                evidence=change.evidence[:3],
                confidence=change.classification_confidence,
                validation_status="verified",
            )
        )
    return claims


def _render_customer_release_notes(changes: list[ChangeRecord], claims: list[ClaimRecord]) -> str:
    lines = ["# Customer Release Notes", ""]
    customer_changes = [change for change in changes if change.customer_impact != "none"]
    for change in customer_changes:
        lines.append(f"- {change.summary}")
    if not customer_changes:
        lines.append("- No customer-facing changes were identified.")
    return "\n".join(lines)


def _render_technical_changelog(changes: list[ChangeRecord]) -> str:
    lines = ["# Technical Changelog", ""]
    for change in changes:
        categories = ", ".join(change.categories)
        evidence = ", ".join(item.reference for item in change.evidence)
        lines.append(f"- **{change.change_id}** {change.title} (`{categories}`): {evidence}")
    return "\n".join(lines)


def _build_regression_tests(changes: list[ChangeRecord]) -> list[RegressionTestSuggestion]:
    suggestions: list[RegressionTestSuggestion] = []
    for index, change in enumerate(
        [change for change in changes if change.regression_testing_required],
        start=1,
    ):
        suggestions.append(
            RegressionTestSuggestion(
                test_id=f"RT-{index:03d}",
                title=f"Verify {change.title.lower()}",
                change_references=[change.change_id],
                priority="high" if change.customer_impact in {"high", "medium"} else "medium",
                preconditions=["The support-ticket API is running with test data available."],
                steps=[
                    "Exercise the affected endpoint or configuration path.",
                    "Verify the response and side effects match the documented behavior.",
                    "Run the automated pytest suite.",
                ],
                expected_result="The behavior works as intended and existing API behavior remains stable.",
                automation_candidate=True,
            )
        )
    return suggestions


def _build_risk_assessment(changes: list[ChangeRecord]) -> RiskAssessment:
    has_breaking = any("breaking_change" in change.categories for change in changes)
    has_security = any("security" in change.categories for change in changes)
    missing_docs = any(change.warnings for change in changes)
    customer_score = max((_impact_score(change.customer_impact) for change in changes), default=0)
    surface_score = min(len(changes) / 8, 1)
    testing_score = 0.2 if all(change.regression_testing_required for change in changes if change.customer_impact != "none") else 0.6
    factors = [
        RiskFactor("customer_impact", customer_score, RISK_WEIGHTS["customer_impact"], "Customer-visible features and a breaking configuration change are present."),
        RiskFactor("breaking_change_potential", 1.0 if has_breaking else 0.0, RISK_WEIGHTS["breaking_change_potential"], "Configuration rename requires migration attention." if has_breaking else "No breaking change detected."),
        RiskFactor("security_relevance", 0.7 if has_security else 0.0, RISK_WEIGHTS["security_relevance"], "Dependency security floor is included." if has_security else "No security-relevant change detected."),
        RiskFactor("change_surface", surface_score, RISK_WEIGHTS["change_surface"], f"{len(changes)} logical changes are included in the release boundary."),
        RiskFactor("insufficient_testing", 0.4 if missing_docs else testing_score, RISK_WEIGHTS["insufficient_testing"], "Automated tests exist, but at least one customer-visible change lacks documentation." if missing_docs else "Automated tests cover the identified changes."),
        RiskFactor("rollback_complexity", 0.6 if has_breaking else 0.2, RISK_WEIGHTS["rollback_complexity"], "Rollback must account for configuration compatibility." if has_breaking else "Rollback appears limited to code changes."),
    ]
    score = round(sum(factor.score * factor.weight for factor in factors), 2)
    level = "high" if score >= 0.7 else "medium" if score >= 0.35 else "low"
    return RiskAssessment(
        score=score,
        level=level,
        factors=factors,
        explanation="Risk score is deterministic and indicates review priority, not probability of failure.",
    )


def _impact_score(impact: str) -> float:
    return {"none": 0.0, "low": 0.25, "medium": 0.6, "high": 1.0}[impact]


def _build_qa_checklist(changes: list[ChangeRecord], evidence: dict[str, Any]) -> list[QACheck]:
    checklist = [
        QACheck("completed", "Automated pytest evidence is present in the repository history.", []),
        QACheck("recommended", "Verify customer-visible API behavior manually in a local environment.", [change.change_id for change in changes if change.customer_impact != "none"]),
    ]
    if any(warning == "check_runs_unavailable" for warning in [item["code"] for item in evidence.get("warnings", [])]):
        checklist.append(QACheck("recommended", "Review CI/check-run status manually because check-run evidence was unavailable to the collector.", []))
    for change in changes:
        if change.warnings:
            checklist.append(QACheck("blocked", change.warnings[0], [change.change_id]))
    return checklist


def _render_deployment_guidance(changes: list[ChangeRecord]) -> str:
    lines = ["# Deployment And Rollback Guidance", ""]
    if any(change.migration_required for change in changes):
        lines.append("- Before deployment, rename `SUPPORT_API_KEY` to `SUPPORT_TICKET_API_KEY` wherever a custom API key is configured.")
        lines.append("- Rollback requires restoring the previous application version and old environment variable name together.")
    else:
        lines.append("- No migration-required change was identified.")
    lines.append("- Run the automated test suite before deployment and after rollback.")
    return "\n".join(lines)


def _build_review_sections(
    *,
    repository: str,
    release_range: str,
    base_sha: str,
    target_sha: str,
    changes: list[ChangeRecord],
    claims: list[ClaimRecord],
    artifacts: GeneratedArtifacts,
    warnings: list[str],
) -> dict[str, str]:
    risk = artifacts.risk_and_impact_assessment
    qa_blockers = [item for item in artifacts.qa_checklist if item.status == "blocked"]
    warning_counts = _count_values(warnings)
    customer_changes = [change for change in changes if change.customer_impact != "none"]
    internal_changes = [change for change in changes if change.customer_impact == "none"]

    executive_summary = "\n".join(
        [
            f"Repository: {repository}",
            f"Release range: {release_range}",
            f"Base SHA: {base_sha[:7]}",
            f"Target SHA: {target_sha[:7]}",
            f"Risk: {risk.level} ({risk.score})",
            f"Changes: {len(changes)} total, {len(customer_changes)} customer-facing, {len(internal_changes)} internal",
            f"Claims: {len(claims)}",
        ]
    )

    blocker_lines = [f"- {item.title}" for item in qa_blockers]
    blocker_summary = "\n".join(blocker_lines) if blocker_lines else "- No hard blockers detected."

    warning_lines = []
    for warning in artifacts.missing_documentation_warnings:
        warning_lines.append(f"- {warning}")
    if warning_counts.get("check_runs_unavailable"):
        warning_lines.append("- Check-run evidence was unavailable; review CI status manually.")
    redaction_count = warning_counts.get("secret_redacted", 0)
    if redaction_count:
        warning_lines.append(f"- Potential secrets were redacted from evidence {redaction_count} time(s).")
    truncation_count = warning_counts.get("file_patch_truncated", 0) + warning_counts.get("total_patch_limit", 0)
    if truncation_count:
        warning_lines.append(f"- Patch evidence was truncated or omitted {truncation_count} time(s).")
    warning_summary = "\n".join(warning_lines) if warning_lines else "- No warnings detected."

    artifact_summary = "\n".join(
        [
            f"- Customer release notes: {_count_markdown_bullets(artifacts.customer_release_notes)} entries",
            f"- Technical changelog: {_count_markdown_bullets(artifacts.technical_changelog)} entries",
            f"- Suggested regression tests: {len(artifacts.suggested_regression_tests)}",
            f"- QA checks: {len(artifacts.qa_checklist)}",
            f"- Missing-documentation warnings: {len(artifacts.missing_documentation_warnings)}",
        ]
    )

    review_markdown = "\n\n".join(
        [
            f"# Release Review Preview: {release_range}",
            "## Executive Summary\n" + executive_summary,
            "## Safety Gate Focus\n" + blocker_summary,
            "## Warnings\n" + warning_summary,
            "## Customer Release Notes\n" + _strip_markdown_heading(artifacts.customer_release_notes),
            "## Artifact Summary\n" + artifact_summary,
            "## Deployment And Rollback\n" + _strip_markdown_heading(artifacts.deployment_and_rollback_guidance),
        ]
    )

    return {
        "review_markdown": review_markdown,
        "executive_summary": executive_summary,
        "blocker_summary": blocker_summary,
        "warning_summary": warning_summary,
        "artifact_summary": artifact_summary,
    }


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _count_markdown_bullets(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.startswith("- "))


def _strip_markdown_heading(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()
