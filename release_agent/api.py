from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from release_agent.ai_review import (
    build_ai_input_package,
    build_review_artifacts,
    generate_demo_ai_review_draft,
    validate_ai_review_draft,
    validate_ai_review_or_raise,
)
from release_agent.analyzer import DeterministicReleaseAnalyzer
from release_agent.dashboard import (
    DashboardStore,
    DashboardWebhookError,
    build_preview_request,
    build_review_decision,
    build_review_decision_update,
    dashboard_decision_result,
    dashboard_error,
    dashboard_home,
    dashboard_not_found,
    dashboard_review_detail,
    dashboard_result,
    dashboard_store_from_environment,
    maybe_forward_to_webhook,
    parse_urlencoded_form,
)
from release_agent.evidence import ReleaseEvidenceCollector
from release_agent.errors import ReleaseAgentError, ReleaseRequestError
from release_agent.github_client import GitHubClient
from release_agent.models import ReleaseRequest


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_owner: str = Field(min_length=1)
    repository_name: str = Field(min_length=1)
    base_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    release_version: str = Field(min_length=1)
    release_mode: str = "preview"
    publish_enabled: bool = False


class ResolveRefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_owner: str = Field(min_length=1)
    repository_name: str = Field(min_length=1)
    ref: str = Field(min_length=1)


class AIReviewDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: dict[str, Any]
    draft_mode: str = "demo"


class AIInputPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis: dict[str, Any]


class AIReviewValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_input_package: dict[str, Any]
    ai_review_draft: dict[str, Any]


def create_app(
    collector: ReleaseEvidenceCollector | None = None,
    analyzer: DeterministicReleaseAnalyzer | None = None,
    github_client: GitHubClient | None = None,
    dashboard_store: DashboardStore | None = None,
) -> FastAPI:
    app = FastAPI(
        title="AI Release Agent Preview API",
        version="0.1.0",
    )
    client = github_client or GitHubClient()
    evidence_collector = collector or ReleaseEvidenceCollector(client)
    release_analyzer = analyzer or DeterministicReleaseAnalyzer()
    review_store = dashboard_store or dashboard_store_from_environment()

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "release-agent-preview-api"}

    @app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
    def dashboard() -> HTMLResponse:
        return dashboard_home(review_store)

    @app.get("/dashboard/reviews/{review_id}", response_class=HTMLResponse, tags=["dashboard"])
    def dashboard_review(review_id: int) -> HTMLResponse:
        if review_store is None:
            return dashboard_error(
                "Review data unavailable",
                "Set RELEASE_AGENT_DATABASE_URL to enable Postgres-backed review pages.",
            )
        review = review_store.get_review(review_id)
        if review is None:
            return dashboard_not_found(review_id)
        return dashboard_review_detail(review)

    @app.post("/dashboard/start-preview", response_class=HTMLResponse, tags=["dashboard"])
    async def start_preview_from_dashboard(request: Request) -> HTMLResponse:
        payload = build_preview_request(await parse_urlencoded_form(request))
        try:
            forwarding_result = maybe_forward_to_webhook(
                "RELEASE_AGENT_PREVIEW_WEBHOOK_URL",
                payload,
            )
        except DashboardWebhookError as exc:
            return dashboard_error("Release briefing failed", str(exc))
        return dashboard_result("Release briefing request", payload, forwarding_result)

    @app.post("/dashboard/submit-review", response_class=HTMLResponse, tags=["dashboard"])
    async def submit_review_from_dashboard(request: Request) -> HTMLResponse:
        payload = build_review_decision(await parse_urlencoded_form(request))
        try:
            forwarding_result = maybe_forward_to_webhook(
                "RELEASE_AGENT_REVIEW_WEBHOOK_URL",
                payload,
            )
        except DashboardWebhookError as exc:
            return dashboard_error("Human review submission failed", str(exc))
        return dashboard_result("Human review decision", payload, forwarding_result)

    @app.post(
        "/dashboard/reviews/{review_id}/decision",
        response_class=HTMLResponse,
        tags=["dashboard"],
    )
    async def submit_review_decision(review_id: int, request: Request) -> HTMLResponse:
        if review_store is None:
            return dashboard_error(
                "Review data unavailable",
                "Set RELEASE_AGENT_DATABASE_URL to enable Postgres-backed review decisions.",
            )

        existing_review = review_store.get_review(review_id)
        if existing_review is None:
            return dashboard_not_found(review_id)
        if existing_review.review_status == "completed":
            return dashboard_error(
                "Review already completed",
                "This review is read-only because a human decision has already been submitted.",
            )

        decision = build_review_decision_update(await parse_urlencoded_form(request))
        try:
            review = review_store.update_review_decision(review_id, decision)
            forwarding_result = maybe_forward_to_webhook(
                "RELEASE_AGENT_REVIEW_WEBHOOK_URL",
                {
                    "review_id": review.id,
                    "decision_recorded_at": review.decision_recorded_at,
                    "review_decision": review.review_decision,
                    "reviewer": review.reviewer,
                    "reviewer_notes": review.reviewer_notes,
                    "override_reason": review.override_reason,
                    "review_status": review.review_status,
                },
            )
        except KeyError:
            return dashboard_not_found(review_id)
        except DashboardWebhookError as exc:
            return dashboard_error("Human review submission failed", str(exc))

        return dashboard_decision_result(review, forwarding_result)

    @app.post("/release-analysis/preview", tags=["release-analysis"])
    def preview_release_analysis(payload: PreviewRequest) -> dict[str, Any]:
        try:
            request = ReleaseRequest.from_mapping(payload.model_dump())
            evidence = evidence_collector.collect(request)
            result = release_analyzer.analyze(
                evidence.to_dict(),
                source_evidence_file="http-request",
            )
            analysis = result.to_dict()
            return {
                **analysis,
                "ai_input_package": build_ai_input_package(analysis),
                "publication_performed": False,
            }
        except ReleaseRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except ReleaseAgentError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    @app.post("/release-analysis/resolve-ref", tags=["release-analysis"])
    def resolve_ref(payload: ResolveRefRequest) -> dict[str, str]:
        try:
            sha = client.resolve_commit_sha(
                payload.repository_owner,
                payload.repository_name,
                payload.ref,
            )
            return {
                "repository": f"{payload.repository_owner}/{payload.repository_name}",
                "ref": payload.ref,
                "sha": sha,
            }
        except ReleaseAgentError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    @app.post("/release-analysis/ai-review-draft", tags=["release-analysis"])
    def ai_review_draft(payload: AIReviewDraftRequest) -> dict[str, Any]:
        if payload.draft_mode != "demo":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="draft_mode must be 'demo' for this preview phase.",
            )

        try:
            ai_input = build_ai_input_package(payload.analysis)
            draft = generate_demo_ai_review_draft(ai_input)
            validation = validate_ai_review_or_raise(ai_input, draft)
            return {
                "ai_input_package": ai_input,
                "ai_review_draft": draft,
                "ai_review_validation": validation,
                "publication_performed": False,
            }
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"analysis is missing required field: {exc.args[0]}",
            ) from exc
        except ReleaseAgentError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    @app.post("/release-analysis/ai-input-package", tags=["release-analysis"])
    def ai_input_package(payload: AIInputPackageRequest) -> dict[str, Any]:
        try:
            return {
                "ai_input_package": build_ai_input_package(payload.analysis),
                "publication_performed": False,
            }
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"analysis is missing required field: {exc.args[0]}",
            ) from exc

    @app.post("/release-analysis/validate-ai-review", tags=["release-analysis"])
    def validate_ai_review(payload: AIReviewValidationRequest) -> dict[str, Any]:
        validation = validate_ai_review_draft(
            payload.ai_input_package,
            payload.ai_review_draft,
        )
        return {
            "ai_review_validation": validation,
            "review_artifacts": (
                build_review_artifacts(
                    payload.ai_input_package,
                    payload.ai_review_draft,
                )
                if validation["valid"]
                else {}
            ),
            "publication_performed": False,
        }

    return app


app = create_app()
