from html import unescape

from fastapi.testclient import TestClient

from release_agent.api import create_app
from release_agent.dashboard import DashboardStore, ReleaseReview, ReleaseWorkflowRun


class FakeDashboardStore(DashboardStore):
    def __init__(self):
        self.review = ReleaseReview(
            id=7,
            decision_recorded_at="2026-08-12T10:00:00+00:00",
            repository="juesteeb-wbs/ai-release-agent-demo-v2",
            release_range="v1.0.0..release/1.1.0",
            risk_level="high",
            risk_score=0.82,
            gate_status="blocked",
            recommended_next_step="Confirm migration guidance before approval.",
            publication_status_message="Publication was not performed because safety gates blocked the release.",
            human_review_card_link="https://drive.example/review-card",
            review_decision="pending_review",
            reviewer="",
            reviewer_notes="",
            override_reason="",
            review_status="pending_review",
            processed_at=None,
            processing_result=None,
            processing_notes=None,
            workflow_status="failed",
            workflow_started_at="2026-08-12T10:00:01+00:00",
            workflow_completed_at="2026-08-12T10:02:01+00:00",
            workflow_error="Preview API failed.",
            artifact_links={
                "compact_release_view": "https://drive.example/compact-release-view",
                "customer_release_notes": "https://drive.example/customer-release-notes",
                "technical_changelog": "https://drive.example/technical-changelog",
                "testing_qa": "https://drive.example/testing-qa",
                "pull_request_preparation": "https://drive.example/pull-request-preparation",
            },
        )
        self.workflow_runs = [
            ReleaseWorkflowRun(
                workflow_run_id="1066",
                workflow_status="failed",
                workflow_started_at="2026-08-12T10:00:01+00:00",
                workflow_completed_at="2026-08-12T10:02:01+00:00",
                workflow_error="Preview API failed before review creation.",
                release_review_id=None,
            ),
            ReleaseWorkflowRun(
                workflow_run_id="1067",
                workflow_status="running",
                workflow_started_at="2026-08-12T10:05:01+00:00",
                workflow_completed_at=None,
                workflow_error=None,
                release_review_id=7,
            ),
        ]
        self.updated_decision = None

    def list_reviews(self, limit: int = 20):
        return [self.review]

    def list_workflow_runs(self, limit: int = 20):
        return self.workflow_runs

    def get_review(self, review_id: int):
        return self.review if review_id == self.review.id else None

    def update_review_decision(self, review_id: int, decision):
        if review_id != self.review.id:
            raise KeyError(review_id)
        self.updated_decision = decision
        self.review = ReleaseReview(
            **{
                **self.review.__dict__,
                "review_decision": decision["review_decision"],
                "reviewer": decision["reviewer"],
                "reviewer_notes": decision["reviewer_notes"],
                "override_reason": decision["override_reason"],
                "review_status": "completed",
            }
        )
        return self.review


def test_dashboard_home_renders_review_console():
    client = TestClient(create_app())

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Release review console" in response.text
    assert "Start briefing" in response.text
    assert "Release review queue" in response.text
    assert "Create Release Briefing" in response.text
    assert "Review Console" in response.text
    assert "Select a release from the review queue" in response.text
    assert "Submit human decision" not in response.text


def test_dashboard_home_renders_postgres_review_queue():
    client = TestClient(create_app(dashboard_store=FakeDashboardStore()))

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Release review queue" in response.text
    assert "v1.0.0..release/1.1.0" in response.text
    assert "blocked" in response.text
    assert "Active reviews" in response.text
    assert "Running workflows" in response.text
    assert "Failed workflows" in response.text
    assert "Workflow activity" in response.text
    assert "No review created yet" in response.text
    assert "Preview API failed before review creation." in response.text
    assert "<button type=\"submit\" disabled>Start briefing</button>" in response.text
    assert "A briefing workflow is already running." in response.text
    assert "failed" in response.text
    assert "Confirm migration guidance before approval." in response.text
    assert "Open card" in response.text


def test_dashboard_review_detail_renders_decision_form():
    client = TestClient(create_app(dashboard_store=FakeDashboardStore()))

    response = client.get("/dashboard/reviews/7")

    assert response.status_code == 200
    assert "Confirm migration guidance before approval." in response.text
    assert "Open Human Review Card" in response.text
    assert "Submit review decision" in response.text
    assert "This release cannot be approved normally" in response.text
    assert "Decision guide" in response.text
    assert "Review Console" in response.text
    assert "Workflow status" in response.text
    assert "Preview API failed." in response.text
    assert "Human decision" in response.text
    assert "data-override-reason-field hidden" in response.text
    assert "[hidden]" in response.text
    assert "data-review-decision" in response.text
    assert "Artifacts" in response.text
    assert "Human review" in response.text
    assert "Release communication" in response.text
    assert "Validation and planning" in response.text
    assert "Compact Release View" in response.text
    assert "Customer Release Notes" in response.text
    assert "Pull Request Preparation" in response.text
    assert "Release Actions Preview" in response.text
    assert "Preview only. No publishing action is implemented or executed." in response.text
    assert "Release actions are unavailable because this review is not approved." in response.text


def test_dashboard_review_detail_returns_404_for_missing_review():
    client = TestClient(create_app(dashboard_store=FakeDashboardStore()))

    response = client.get("/dashboard/reviews/999")

    assert response.status_code == 404
    assert "Review #999 does not exist" in response.text


def test_dashboard_review_decision_updates_store_without_webhook(monkeypatch):
    monkeypatch.delenv("RELEASE_AGENT_REVIEW_WEBHOOK_URL", raising=False)
    store = FakeDashboardStore()
    client = TestClient(create_app(dashboard_store=store))

    response = client.post(
        "/dashboard/reviews/7/decision",
        data={
            "review_decision": "request_changes",
            "reviewer": "Release Manager",
            "reviewer_notes": "Migration guidance needs confirmation.",
            "override_reason": "undefined",
        },
    )

    assert response.status_code == 200
    assert "Decision recorded" in response.text
    assert store.updated_decision == {
        "review_decision": "request_changes",
        "reviewer": "Release Manager",
        "reviewer_notes": "Migration guidance needs confirmation.",
        "override_reason": "",
        "review_status": "completed",
    }
    detail_response = client.get("/dashboard/reviews/7")
    assert detail_response.status_code == 200
    assert "Changes requested" in detail_response.text
    assert "This release needs changes and should be re-evaluated before approval." in detail_response.text
    assert "Notes: Migration guidance needs confirmation." in detail_response.text
    assert "Decision recorded" in detail_response.text
    assert "This review is read-only because a human decision has already been submitted." in detail_response.text
    assert "Submit review decision" not in detail_response.text


def test_dashboard_completed_review_rejects_duplicate_decision(monkeypatch):
    monkeypatch.delenv("RELEASE_AGENT_REVIEW_WEBHOOK_URL", raising=False)
    store = FakeDashboardStore()
    client = TestClient(create_app(dashboard_store=store))

    first_response = client.post(
        "/dashboard/reviews/7/decision",
        data={
            "review_decision": "request_changes",
            "reviewer": "Release Manager",
            "reviewer_notes": "Migration guidance needs confirmation.",
            "override_reason": "",
        },
    )
    second_response = client.post(
        "/dashboard/reviews/7/decision",
        data={
            "review_decision": "approve",
            "reviewer": "Release Manager",
            "reviewer_notes": "Changed my mind.",
            "override_reason": "",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 502
    assert "Review already completed" in second_response.text
    assert "This review is read-only because a human decision has already been submitted." in second_response.text
    assert store.review.review_decision == "request_changes"


def test_dashboard_approved_review_shows_release_actions_preview(monkeypatch):
    monkeypatch.delenv("RELEASE_AGENT_REVIEW_WEBHOOK_URL", raising=False)
    store = FakeDashboardStore()
    client = TestClient(create_app(dashboard_store=store))

    response = client.post(
        "/dashboard/reviews/7/decision",
        data={
            "review_decision": "approve",
            "reviewer": "Release Manager",
            "reviewer_notes": "Ready for next release steps.",
            "override_reason": "",
        },
    )
    detail_response = client.get("/dashboard/reviews/7")

    assert response.status_code == 200
    assert detail_response.status_code == 200
    assert "Release Actions Preview" in detail_response.text
    assert "This release is approved for the next controlled release steps." in detail_response.text
    assert "Create GitHub release draft" in detail_response.text
    assert "Publish customer-facing release notes" in detail_response.text
    assert "Preview only" in detail_response.text


def test_dashboard_preview_form_prepares_payload_without_webhook(monkeypatch):
    monkeypatch.delenv("RELEASE_AGENT_PREVIEW_WEBHOOK_URL", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/dashboard/start-preview",
        data={
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "base_ref": "v1.0.0",
            "target_ref": "release/1.1.0",
            "release_version": "1.1.0",
        },
    )

    assert response.status_code == 200
    assert "Payload prepared" in response.text
    rendered = unescape(response.text)
    assert '"release_mode": "preview"' in rendered
    assert '"publish_enabled": false' in rendered


def test_dashboard_review_form_prepares_completed_review_without_webhook(monkeypatch):
    monkeypatch.delenv("RELEASE_AGENT_REVIEW_WEBHOOK_URL", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/dashboard/submit-review",
        data={
            "decision_recorded_at": "2026-08-12T10:00:00.000Z",
            "review_decision": "request_changes",
            "reviewer": "Release Manager",
            "reviewer_notes": "Add migration confirmation before approval.",
            "override_reason": "",
        },
    )

    assert response.status_code == 200
    assert "Payload prepared" in response.text
    rendered = unescape(response.text)
    assert '"review_decision": "request_changes"' in rendered
    assert '"review_status": "completed"' in rendered
