from fastapi.testclient import TestClient

from release_agent.api import create_app, main
from release_agent.errors import GitHubClientError
from release_agent.models import ReleaseRequest


class FakeCollector:
    def collect(self, request: ReleaseRequest):
        return FakeEvidence(
            {
                "request": {
                    "repository_owner": request.repository_owner,
                    "repository_name": request.repository_name,
                    "base_ref": request.base_ref,
                    "target_ref": request.target_ref,
                },
                "resolved_refs": {
                    "base_sha": "base-sha",
                    "target_sha": "target-sha",
                },
                "warnings": [],
                "pull_requests": [
                    {
                        "number": 1,
                        "title": "Add CSV ticket export",
                        "body": "Adds export endpoint.",
                        "labels": ["enhancement"],
                        "author": "juesteeb-wbs",
                        "state": "closed",
                        "merged_at": "2026-07-22T10:00:00Z",
                        "merge_commit_sha": "merge-1",
                        "html_url": "https://example.test/pull/1",
                    }
                ],
                "files": [
                    {
                        "filename": "app/main.py",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 0,
                        "changes": 1,
                        "patch": "+export.csv",
                    }
                ],
            }
        )


class FakeEvidence:
    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        return self.payload


class FakeGitHubClient:
    def resolve_commit_sha(self, owner: str, repo: str, ref: str) -> str:
        assert owner == "juesteeb-wbs"
        assert repo == "ai-release-agent-demo-v2"
        assert ref == "release/1.1.0"
        return "current-target-sha"


class FailingGitHubClient:
    def resolve_commit_sha(self, owner: str, repo: str, ref: str) -> str:
        raise GitHubClientError("GitHub API request failed: 404 not found")


def test_api_console_entrypoint_uses_environment(monkeypatch):
    calls = []

    def fake_run(app_path, **kwargs):
        calls.append((app_path, kwargs))

    monkeypatch.setattr("uvicorn.run", fake_run)
    monkeypatch.setenv("RELEASE_COORDINATOR_HOST", "127.0.0.1")
    monkeypatch.setenv("RELEASE_COORDINATOR_PORT", "8999")
    monkeypatch.setenv("RELEASE_COORDINATOR_RELOAD", "true")

    main()

    assert calls == [
        (
            "release_agent.api:app",
            {"host": "127.0.0.1", "port": 8999, "reload": True},
        )
    ]


def test_preview_api_returns_analysis_result():
    client = TestClient(create_app(collector=FakeCollector()))

    response = client.post(
        "/release-analysis/preview",
        json={
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "base_ref": "v1.0.0",
            "target_ref": "release/1.1.0",
            "release_version": "1.1.0",
            "release_mode": "preview",
            "publish_enabled": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["repository"] == "juesteeb-wbs/ai-release-agent-demo-v2"
    assert body["release_range"] == "v1.0.0..release/1.1.0"
    assert body["base_sha"] == "base-sha"
    assert body["target_sha"] == "target-sha"
    assert body["changes"][0]["title"] == "Add CSV ticket export"
    assert body["artifacts"]["customer_release_notes"]
    assert body["ai_input_package"]["repository"] == "juesteeb-wbs/ai-release-agent-demo-v2"
    assert body["ai_input_package"]["neutral_change_evidence"][0]["change_id"] == "CHANGE-001"
    assert body["ai_input_package"]["neutral_change_evidence"][0]["pull_request"]["body"] == (
        "Adds export endpoint."
    )
    assert body["publication_performed"] is False


def test_preview_api_rejects_publish_enabled():
    client = TestClient(create_app(collector=FakeCollector()))

    response = client.post(
        "/release-analysis/preview",
        json={
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "base_ref": "v1.0.0",
            "target_ref": "release/1.1.0",
            "release_version": "1.1.0",
            "release_mode": "preview",
            "publish_enabled": True,
        },
    )

    assert response.status_code == 400
    assert "publish_enabled" in response.json()["detail"]


def test_preview_api_rejects_unknown_fields():
    client = TestClient(create_app(collector=FakeCollector()))

    response = client.post(
        "/release-analysis/preview",
        json={
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "base_ref": "v1.0.0",
            "target_ref": "release/1.1.0",
            "release_version": "1.1.0",
            "unexpected": "nope",
        },
    )

    assert response.status_code == 422


def test_resolve_ref_returns_current_sha():
    client = TestClient(create_app(github_client=FakeGitHubClient()))

    response = client.post(
        "/release-analysis/resolve-ref",
        json={
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "ref": "release/1.1.0",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "repository": "juesteeb-wbs/ai-release-agent-demo-v2",
        "ref": "release/1.1.0",
        "sha": "current-target-sha",
    }


def test_resolve_ref_rejects_unknown_fields():
    client = TestClient(create_app(github_client=FakeGitHubClient()))

    response = client.post(
        "/release-analysis/resolve-ref",
        json={
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "ref": "release/1.1.0",
            "unexpected": "nope",
        },
    )

    assert response.status_code == 422


def test_resolve_ref_translates_github_errors():
    client = TestClient(create_app(github_client=FailingGitHubClient()))

    response = client.post(
        "/release-analysis/resolve-ref",
        json={
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "ref": "missing-branch",
        },
    )

    assert response.status_code == 502
    assert "GitHub API request failed" in response.json()["detail"]


def test_ai_review_draft_endpoint_returns_valid_demo_draft():
    client = TestClient(create_app())

    response = client.post(
        "/release-analysis/ai-review-draft",
        json={"analysis": _analysis(), "draft_mode": "demo"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_review_validation"]["valid"] is True
    assert body["ai_review_draft"]["draft_source"] == "deterministic_demo_generator"
    assert body["publication_performed"] is False


def test_ai_review_draft_endpoint_rejects_non_demo_mode():
    client = TestClient(create_app())

    response = client.post(
        "/release-analysis/ai-review-draft",
        json={"analysis": _analysis(), "draft_mode": "model"},
    )

    assert response.status_code == 400
    assert "draft_mode" in response.json()["detail"]


def test_ai_review_draft_endpoint_translates_validation_errors():
    client = TestClient(create_app())
    analysis = _analysis()
    analysis["changes"][0]["change_id"] = ""

    response = client.post(
        "/release-analysis/ai-review-draft",
        json={"analysis": analysis, "draft_mode": "demo"},
    )

    assert response.status_code == 502
    assert "unknown evidence" in response.json()["detail"]


def test_ai_input_package_endpoint_returns_package_for_model_prompting():
    client = TestClient(create_app())

    response = client.post(
        "/release-analysis/ai-input-package",
        json={"analysis": _analysis()},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_input_package"]["repository"] == "juesteeb-wbs/ai-release-agent-demo-v2"
    assert body["ai_input_package"]["changes"][0]["change_id"] == "CHANGE-001"
    assert body["ai_input_package"]["neutral_change_evidence"][0] == {
        "change_id": "CHANGE-001",
        "title": "Add CSV ticket export",
        "summary": "Add CSV ticket export.",
        "source_pull_requests": ["PR-1"],
        "pull_request": {
            "number": None,
            "title": None,
            "body": "",
            "labels": [],
            "html_url": None,
        },
        "changed_files": [],
        "file_evidence": [],
        "warnings": ["Missing documentation for customer-visible change in PR #1."],
        "evidence_references": ["CHANGE-001"],
    }
    assert body["publication_performed"] is False


def test_ai_input_package_endpoint_rejects_missing_required_analysis_fields():
    client = TestClient(create_app())

    response = client.post(
        "/release-analysis/ai-input-package",
        json={"analysis": {"repository": "juesteeb-wbs/ai-release-agent-demo-v2"}},
    )

    assert response.status_code == 400
    assert "missing required field" in response.json()["detail"]


def test_validate_ai_review_endpoint_returns_valid_result():
    client = TestClient(create_app())
    input_response = client.post(
        "/release-analysis/ai-input-package",
        json={"analysis": _analysis()},
    )
    ai_input_package = input_response.json()["ai_input_package"]

    response = client.post(
        "/release-analysis/validate-ai-review",
        json={
            "ai_input_package": ai_input_package,
            "ai_review_draft": {
                "summary_suggestions": [],
                "release_note_suggestions": [
                    {
                        "audience": "customer",
                        "text": "Add CSV ticket export.",
                        "evidence_references": ["CHANGE-001"],
                        "is_inference": False,
                    }
                ],
                "risk_explanations": [
                    {
                        "factor": "overall_release_risk",
                        "text": "The release has high risk due to a customer-visible change.",
                        "evidence_references": ["CHANGE-001"],
                        "is_inference": True,
                    }
                ],
                "reviewer_questions": [],
                "process_improvement_suggestions": [],
                "missing_information": [],
                "unsupported_claims": [],
                "validation_notes": ["Customer-facing suggestions reference evidence."],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_review_validation"]["valid"] is True
    artifacts = body["review_artifacts"]
    assert "Add CSV ticket export." in artifacts["customer_release_notes"]
    assert "Technical Changelog" in artifacts["technical_changelog"]
    assert "CHANGE-001" in artifacts["suggested_regression_tests"]
    assert "high" in artifacts["risk_and_impact_assessment"]
    assert "check_runs_unavailable" in artifacts["qa_checklist"]
    assert "Run tests" in artifacts["deployment_and_rollback_guidance"]
    assert "Missing documentation" in artifacts["missing_documentation_warnings"]
    assert "Customer-Facing Release Notes" in artifacts["review_artifact_markdown"]
    assert body["publication_performed"] is False


def test_validate_ai_review_endpoint_returns_structured_validation_errors():
    client = TestClient(create_app())
    input_response = client.post(
        "/release-analysis/ai-input-package",
        json={"analysis": _analysis()},
    )
    ai_input_package = input_response.json()["ai_input_package"]

    response = client.post(
        "/release-analysis/validate-ai-review",
        json={
            "ai_input_package": ai_input_package,
            "ai_review_draft": {
                "summary_suggestions": [],
                "release_note_suggestions": [
                    {
                        "audience": "customer",
                        "text": "Unsupported claim.",
                        "evidence_references": ["CHANGE-999"],
                        "is_inference": False,
                    }
                ],
                "risk_explanations": [],
                "reviewer_questions": [],
                "process_improvement_suggestions": [],
                "missing_information": [],
                "unsupported_claims": [],
                "validation_notes": [],
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ai_review_validation"]["valid"] is False
    assert "CHANGE-999" in body["ai_review_validation"]["errors"][0]
    assert body["review_artifacts"] == {}


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
                "warnings": ["Missing documentation for customer-visible change in PR #1."],
                "evidence": [{"type": "pull_request", "reference": "PR-1"}],
            }
        ],
        "artifacts": {
            "customer_release_notes": "# Customer Release Notes\n\n- Add CSV ticket export.",
            "technical_changelog": "# Technical Changelog\n\n- CHANGE-001",
            "qa_checklist": [],
            "deployment_and_rollback_guidance": "# Deployment And Rollback\n\n- Run tests.",
            "missing_documentation_warnings": [
                "Missing documentation for customer-visible change in PR #1."
            ],
            "risk_and_impact_assessment": {
                "level": "high",
                "score": 0.82,
                "factors": [],
            },
        },
        "warnings": ["check_runs_unavailable"],
    }
