from release_agent.ai_review import (
    build_ai_input_package,
    generate_demo_ai_review_draft,
    validate_ai_review_draft,
)


def test_build_ai_input_package_compacts_analysis():
    package = build_ai_input_package(_analysis())

    assert package["repository"] == "juesteeb-wbs/ai-release-agent-demo-v2"
    assert package["release_range"] == "v1.0.0..release/1.1.0"
    assert package["changes"] == [
        {
            "change_id": "CHANGE-001",
            "title": "Add CSV ticket export",
            "summary": "Add CSV ticket export.",
            "categories": ["feature"],
            "customer_impact": "medium",
            "migration_required": False,
            "documentation_required": True,
            "regression_testing_required": True,
            "warnings": ["Missing documentation for customer-visible change in PR #1."],
            "evidence": [
                {"type": "pull_request", "reference": "PR-1"},
                {"type": "file", "reference": "app/main.py"},
            ],
        }
    ]
    assert package["neutral_change_evidence"] == [
        {
            "change_id": "CHANGE-001",
            "title": "Add CSV ticket export",
            "summary": "Add CSV ticket export.",
            "source_pull_requests": ["PR-1"],
            "pull_request": {
                "number": 1,
                "title": "Add CSV ticket export",
                "body": "Adds export endpoint.",
                "labels": ["enhancement"],
                "html_url": "https://example.test/pull/1",
            },
            "changed_files": ["app/main.py"],
            "file_evidence": [
                {
                    "filename": "app/main.py",
                    "status": "modified",
                    "additions": 1,
                    "deletions": 0,
                    "changes": 1,
                    "patch_excerpt": "+export.csv",
                    "omitted_reason": None,
                }
            ],
            "warnings": ["Missing documentation for customer-visible change in PR #1."],
            "evidence_references": ["CHANGE-001"],
        }
    ]
    assert "categories" not in package["neutral_change_evidence"][0]
    assert "customer_impact" not in package["neutral_change_evidence"][0]
    assert package["risk_assessment"]["level"] == "high"
    assert "customer_release_notes" in package["existing_artifacts"]


def test_demo_ai_review_draft_is_validated_against_evidence():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is True
    assert validation["errors"] == []
    assert draft["draft_source"] == "deterministic_demo_generator"
    assert draft["release_note_suggestions"][0]["evidence_references"] == ["CHANGE-001"]
    assert draft["process_improvement_suggestions"]
    assert draft["missing_information"]


def test_ai_review_validation_rejects_unknown_evidence_references():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)
    draft["release_note_suggestions"][0]["evidence_references"] = ["CHANGE-999"]

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is False
    assert "CHANGE-999" in validation["errors"][0]


def test_ai_review_validation_rejects_forbidden_release_actions():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)
    draft["reviewer_questions"].append(
        {
            "question": "Should we publish release now?",
            "reason": "This should not be recommended by AI output.",
            "evidence_references": ["CHANGE-001"],
        }
    )

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is False
    assert "must not recommend publishing" in validation["errors"][0]


def test_ai_review_validation_allows_deployment_configuration_review_question():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)
    draft["reviewer_questions"].append(
        {
            "question": "Has deployment configuration been updated?",
            "reason": "A migration or breaking-change signal is present.",
            "evidence_references": ["CHANGE-001"],
        }
    )

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is True
    assert validation["errors"] == []


def test_ai_review_validation_rejects_missing_extended_sections():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)
    del draft["process_improvement_suggestions"]

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is False
    assert "process_improvement_suggestions must be a list" in validation["errors"][0]


def test_ai_review_validation_rejects_invalid_process_improvement_priority():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)
    draft["process_improvement_suggestions"][0]["priority"] = "urgent"

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is False
    assert "priority" in validation["errors"][0]


def test_ai_review_validation_rejects_invalid_missing_information_boolean():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)
    draft["missing_information"][0]["blocks_release_confidence"] = "yes"

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is False
    assert "blocks_release_confidence" in validation["errors"][0]


def test_ai_review_validation_rejects_unknown_extended_section_reference():
    package = build_ai_input_package(_analysis())
    draft = generate_demo_ai_review_draft(package)
    draft["process_improvement_suggestions"][0]["evidence_references"] = ["CHANGE-999"]

    validation = validate_ai_review_draft(package, draft)

    assert validation["valid"] is False
    assert "CHANGE-999" in validation["errors"][0]


def _analysis():
    return {
        "repository": "juesteeb-wbs/ai-release-agent-demo-v2",
        "release_range": "v1.0.0..release/1.1.0",
        "base_sha": "base-sha",
        "target_sha": "target-sha",
        "changes": [
            {
                "change_id": "CHANGE-001",
                "title": "Add CSV ticket export",
                "summary": "Add CSV ticket export.",
                "categories": ["feature"],
                "customer_impact": "medium",
                "migration_required": False,
                "documentation_required": True,
                "regression_testing_required": True,
                "approval_blocker": False,
                "classification_confidence": 0.96,
                "warnings": ["Missing documentation for customer-visible change in PR #1."],
                "evidence": [
                    {"type": "pull_request", "reference": "PR-1"},
                    {"type": "file", "reference": "app/main.py"},
                ],
                "source_evidence": {
                    "pull_request": {
                        "number": 1,
                        "title": "Add CSV ticket export",
                        "body": "Adds export endpoint.",
                        "labels": ["enhancement"],
                        "html_url": "https://example.test/pull/1",
                    },
                    "files": [
                        {
                            "filename": "app/main.py",
                            "status": "modified",
                            "additions": 1,
                            "deletions": 0,
                            "changes": 1,
                            "patch_excerpt": "+export.csv",
                            "omitted_reason": None,
                        }
                    ],
                },
            }
        ],
        "claims": [],
        "artifacts": {
            "customer_release_notes": "# Customer Release Notes\n\n- Add CSV ticket export.",
            "technical_changelog": "# Technical Changelog\n\n- CHANGE-001",
            "suggested_regression_tests": [],
            "risk_and_impact_assessment": {
                "level": "high",
                "score": 0.82,
                "factors": [],
                "explanation": "Risk score is deterministic.",
            },
            "qa_checklist": [],
            "deployment_and_rollback_guidance": "# Deployment And Rollback\n\n- Run tests.",
            "missing_documentation_warnings": [
                "Missing documentation for customer-visible change in PR #1."
            ],
        },
        "warnings": ["check_runs_unavailable"],
        "review_markdown": "# Release Review Preview",
        "executive_summary": "Risk: high",
        "blocker_summary": "- Missing documentation",
        "warning_summary": "- Check-run evidence was unavailable",
        "artifact_summary": "- Customer release notes: 1 entries",
    }
