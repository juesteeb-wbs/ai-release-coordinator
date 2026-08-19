from release_agent.analyzer import DeterministicReleaseAnalyzer


def test_analyzer_classifies_changes_and_generates_artifacts():
    evidence = _sample_evidence()

    result = DeterministicReleaseAnalyzer().analyze(evidence, "evidence.json")

    categories_by_title = {
        change.title: set(change.categories)
        for change in result.changes
    }
    assert categories_by_title["Add CSV ticket export"] == {"feature"}
    assert categories_by_title["Fix authentication header handling"] == {"fix"}
    assert categories_by_title["Rename API key configuration variable"] == {
        "breaking_change"
    }
    assert categories_by_title["Update FastAPI stack dependency floor"] == {
        "security",
        "dependency",
    }
    assert categories_by_title["Add customer email ticket filter"] == {"feature"}
    assert categories_by_title["Add read-only GitHub evidence collector"] == {"internal"}
    assert categories_by_title["Add local release evidence analyzer"] == {"internal"}
    assert "Refactor request logging" not in categories_by_title
    assert "Exclude internal tooling from customer-facing analysis" not in categories_by_title

    assert result.base_sha == "base-sha"
    assert result.target_sha == "target-sha"
    assert len(result.claims) == 7
    assert result.artifacts.risk_and_impact_assessment.level == "high"
    assert "Customer Release Notes" in result.artifacts.customer_release_notes
    assert "Technical Changelog" in result.artifacts.technical_changelog
    assert "Add read-only GitHub evidence collector" not in result.artifacts.customer_release_notes
    assert "Add local release evidence analyzer" not in result.artifacts.customer_release_notes
    assert "Exclude internal tooling from customer-facing analysis" not in result.artifacts.customer_release_notes
    assert result.review_markdown.startswith("# Release Review Preview")
    assert "## Executive Summary" in result.review_markdown
    assert "## Safety Gate Focus" in result.review_markdown
    assert "## Warnings" in result.review_markdown
    assert "Risk: high" in result.executive_summary
    assert "Missing documentation" in result.blocker_summary
    assert "Check-run evidence was unavailable" in result.warning_summary
    assert "Customer release notes:" in result.artifact_summary
    csv_change = next(change for change in result.changes if change.title == "Add CSV ticket export")
    assert csv_change.source_evidence["pull_request"]["body"] == "Adds export endpoint."
    assert csv_change.source_evidence["pull_request"]["labels"] == ["enhancement"]
    assert csv_change.source_evidence["files"][0]["patch_excerpt"] == "+export.csv"


def test_analyzer_flags_customer_email_filter_missing_documentation():
    evidence = _sample_evidence()

    result = DeterministicReleaseAnalyzer().analyze(evidence, "evidence.json")

    warnings = result.artifacts.missing_documentation_warnings
    assert any("PR #6" in warning for warning in warnings)
    customer_email_change = next(
        change for change in result.changes if change.title == "Add customer email ticket filter"
    )
    assert customer_email_change.documentation_required is True
    assert customer_email_change.warnings


def test_analyzer_includes_check_run_warning_in_qa_checklist():
    evidence = _sample_evidence()

    result = DeterministicReleaseAnalyzer().analyze(evidence, "evidence.json")

    assert "check_runs_unavailable" in result.warnings
    assert any("check-run" in item.title for item in result.artifacts.qa_checklist)


def _sample_evidence():
    return {
        "request": {
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "base_ref": "v1.0.0",
            "target_ref": "release/1.1.0",
        },
        "resolved_refs": {
            "base_sha": "base-sha",
            "target_sha": "target-sha",
        },
        "warnings": [{"code": "check_runs_unavailable"}],
        "pull_requests": [
            _pr(1, "Add CSV ticket export", ["enhancement"], "Adds export endpoint."),
            _pr(2, "Fix authentication header handling", ["bug"], "Fixes malformed API key handling."),
            _pr(
                3,
                "Rename API key configuration variable",
                ["enhancement", "breaking change"],
                "Breaking change. Migration from SUPPORT_API_KEY to SUPPORT_TICKET_API_KEY.",
            ),
            _pr(
                4,
                "Update FastAPI stack dependency floor",
                ["enhancement", "security"],
                "Security dependency update for Starlette denial-of-service fix.",
            ),
            _pr(5, "Refactor request logging", ["internal"], "Internal logging refactor."),
            _pr(6, "Add customer email ticket filter", ["enhancement"], "Adds customer_email filter."),
            _pr(7, "Add read-only GitHub evidence collector", ["enhancement"], "Adds evidence collector."),
            _pr(8, "Add local release evidence analyzer", ["enhancement"], "Adds deterministic analyzer and artifact generator."),
            _pr(9, "Exclude internal tooling from customer-facing analysis", ["internal"], "Tune analyzer rules for internal tooling."),
        ],
        "files": [
            _file("tests/test_export.py", "+export.csv"),
            _file("app/main.py", "+export.csv\n+customer_email"),
            _file("app/auth.py", "+X-API-Key"),
            _file("tests/test_auth.py", "+padded api key"),
            _file("app/settings.py", "+SUPPORT_TICKET_API_KEY\n-SUPPORT_API_KEY"),
            _file("README.md", "+Migration note\n+SUPPORT_TICKET_API_KEY"),
            _file("pyproject.toml", "+fastapi>=0.115.3\n+starlette>=0.40.0"),
            _file("tests/test_dependency_policy.py", "+dependency floor"),
            _file("app/logging.py", "+configure_request_logging"),
            _file("tests/test_logging.py", "+support_api.requests"),
            _file("app/repository.py", "+customer_email"),
            _file("tests/test_tickets.py", "+customer_email"),
            _file("release_agent/evidence.py", "+ReleaseEvidenceCollector"),
            _file("release_agent/analyzer.py", "+evidence collector"),
            _file("release_agent/analysis_models.py", "+ChangeRecord"),
            _file("tests/test_analyzer.py", "+local release evidence analyzer"),
            _file("release_agent/analyzer.py", "+internal label"),
        ],
    }


def _pr(number, title, labels, body):
    return {
        "number": number,
        "title": title,
        "body": body,
        "labels": labels,
        "author": "juesteeb-wbs",
        "state": "closed",
        "merged_at": "2026-07-22T10:00:00Z",
        "merge_commit_sha": f"merge-{number}",
        "html_url": f"https://example.test/pull/{number}",
    }


def _file(filename, patch):
    return {
        "filename": filename,
        "status": "modified",
        "additions": 1,
        "deletions": 0,
        "changes": 1,
        "patch": patch,
    }
