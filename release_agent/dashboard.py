import html
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs
from urllib.request import Request, urlopen

from fastapi import Request as FastAPIRequest
from fastapi.responses import HTMLResponse


class DashboardWebhookError(Exception):
    pass


@dataclass(frozen=True)
class ReleaseReview:
    id: int
    decision_recorded_at: str
    repository: str
    release_range: str
    risk_level: str | None
    risk_score: float | None
    gate_status: str | None
    recommended_next_step: str | None
    publication_status_message: str | None
    human_review_card_link: str | None
    review_decision: str | None
    reviewer: str | None
    reviewer_notes: str | None
    override_reason: str | None
    review_status: str
    processed_at: str | None
    processing_result: str | None
    processing_notes: str | None
    workflow_status: str | None = None
    workflow_started_at: str | None = None
    workflow_completed_at: str | None = None
    workflow_error: str | None = None
    artifact_links: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReleaseWorkflowRun:
    workflow_run_id: str
    workflow_status: str
    workflow_started_at: str | None
    workflow_completed_at: str | None
    workflow_error: str | None
    release_review_id: int | None


class DashboardStore:
    def list_reviews(self, limit: int = 20) -> list[ReleaseReview]:
        raise NotImplementedError

    def list_workflow_runs(self, limit: int = 20) -> list[ReleaseWorkflowRun]:
        raise NotImplementedError

    def get_review(self, review_id: int) -> ReleaseReview | None:
        raise NotImplementedError

    def update_review_decision(
        self,
        review_id: int,
        decision: dict[str, str],
    ) -> ReleaseReview:
        raise NotImplementedError


class PostgresDashboardStore(DashboardStore):
    def __init__(self, database_url: str):
        self.database_url = database_url

    def list_reviews(self, limit: int = 20) -> list[ReleaseReview]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                      r.id,
                      r.decision_recorded_at,
                      r.repository,
                      r.release_range,
                      r.risk_level,
                      r.risk_score,
                      r.gate_status,
                      r.recommended_next_step,
                      r.publication_status_message,
                      r.human_review_card_link,
                      r.review_decision,
                      r.reviewer,
                      r.reviewer_notes,
                      r.override_reason,
                      r.review_status,
                      r.processed_at,
                      r.processing_result,
                      r.processing_notes,
                      r.artifact_links,
                      w.workflow_status,
                      w.workflow_started_at,
                      w.workflow_completed_at,
                      w.workflow_error
                    FROM release_reviews r
                    LEFT JOIN LATERAL (
                      SELECT
                        workflow_status,
                        workflow_started_at,
                        workflow_completed_at,
                        workflow_error
                      FROM release_workflow_runs
                      WHERE release_review_id = r.id
                      ORDER BY created_at DESC
                      LIMIT 1
                    ) w ON TRUE
                    WHERE r.review_status = 'pending_review'
                       OR (r.review_status = 'completed' AND r.processed_at IS NULL)
                    ORDER BY r.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [_review_from_row(row) for row in cursor.fetchall()]

    def list_workflow_runs(self, limit: int = 20) -> list[ReleaseWorkflowRun]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                      workflow_run_id,
                      workflow_status,
                      workflow_started_at,
                      workflow_completed_at,
                      workflow_error,
                      release_review_id
                    FROM release_workflow_runs
                    WHERE workflow_status IN ('running', 'failed')
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [_workflow_run_from_row(row) for row in cursor.fetchall()]

    def get_review(self, review_id: int) -> ReleaseReview | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                      r.id,
                      r.decision_recorded_at,
                      r.repository,
                      r.release_range,
                      r.risk_level,
                      r.risk_score,
                      r.gate_status,
                      r.recommended_next_step,
                      r.publication_status_message,
                      r.human_review_card_link,
                      r.review_decision,
                      r.reviewer,
                      r.reviewer_notes,
                      r.override_reason,
                      r.review_status,
                      r.processed_at,
                      r.processing_result,
                      r.processing_notes,
                      r.artifact_links,
                      w.workflow_status,
                      w.workflow_started_at,
                      w.workflow_completed_at,
                      w.workflow_error
                    FROM release_reviews r
                    LEFT JOIN LATERAL (
                      SELECT
                        workflow_status,
                        workflow_started_at,
                        workflow_completed_at,
                        workflow_error
                      FROM release_workflow_runs
                      WHERE release_review_id = r.id
                      ORDER BY created_at DESC
                      LIMIT 1
                    ) w ON TRUE
                    WHERE r.id = %s
                    """,
                    (review_id,),
                )
                row = cursor.fetchone()
                return _review_from_row(row) if row else None

    def update_review_decision(
        self,
        review_id: int,
        decision: dict[str, str],
    ) -> ReleaseReview:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE release_reviews
                    SET
                      review_decision = %s,
                      reviewer = %s,
                      reviewer_notes = %s,
                      override_reason = %s,
                      review_status = 'completed'
                    WHERE id = %s
                    RETURNING
                      id,
                      decision_recorded_at,
                      repository,
                      release_range,
                      risk_level,
                      risk_score,
                      gate_status,
                      recommended_next_step,
                      publication_status_message,
                      human_review_card_link,
                      review_decision,
                      reviewer,
                      reviewer_notes,
                      override_reason,
                      review_status,
                      processed_at,
                      processing_result,
                      processing_notes,
                      artifact_links
                    """,
                    (
                        decision["review_decision"],
                        decision["reviewer"],
                        decision.get("reviewer_notes", ""),
                        decision.get("override_reason", ""),
                        review_id,
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    raise KeyError(review_id)
                connection.commit()
                return _review_from_row(row)

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "Install the PostgreSQL dashboard dependency with "
                '`python -m pip install -e ".[dev]"`.'
            ) from exc
        return psycopg.connect(self.database_url)


def dashboard_store_from_environment() -> DashboardStore | None:
    database_url = os.environ.get("RELEASE_AGENT_DATABASE_URL", "").strip()
    return PostgresDashboardStore(database_url) if database_url else None


def dashboard_home(store: DashboardStore | None = None) -> HTMLResponse:
    reviews: list[ReleaseReview] = []
    workflow_runs: list[ReleaseWorkflowRun] = []
    store_message = "Set RELEASE_AGENT_DATABASE_URL to show review records."
    workflow_message = "Set RELEASE_AGENT_DATABASE_URL to show workflow activity."
    if store:
        try:
            reviews = store.list_reviews()
            store_message = "Showing review briefing records from Postgres."
        except Exception as exc:
            store_message = f"Review data is unavailable: {exc}"
        try:
            workflow_runs = store.list_workflow_runs()
            workflow_message = "Showing running and failed n8n workflow runs from Postgres."
        except Exception as exc:
            workflow_message = f"Workflow activity is unavailable: {exc}"
    return HTMLResponse(
        _page(
            "Release Coordinator Dashboard",
            _home_content(reviews, workflow_runs, store_message, workflow_message),
        )
    )


def dashboard_review_detail(review: ReleaseReview) -> HTMLResponse:
    return HTMLResponse(_page(f"Review {review.id}", _review_detail_content(review)))


def dashboard_not_found(review_id: int) -> HTMLResponse:
    content = f"""
    <section class="hero compact danger">
      <div>
        <p class="eyebrow">Review not found</p>
        <h1>Review #{review_id} does not exist</h1>
        <p>The dashboard could not find this review record in Postgres.</p>
      </div>
      <a class="button secondary" href="/dashboard">Back to dashboard</a>
    </section>
    """
    return HTMLResponse(_page("Review not found", content), status_code=404)


async def parse_urlencoded_form(request: FastAPIRequest) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1].strip() for key, values in parsed.items()}


def _clean_optional_text(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in {"undefined", "null"} else text


def build_preview_request(form: dict[str, str]) -> dict[str, Any]:
    return {
        "repository_owner": form.get("repository_owner", ""),
        "repository_name": form.get("repository_name", ""),
        "base_ref": form.get("base_ref", ""),
        "target_ref": form.get("target_ref", ""),
        "release_version": form.get("release_version", ""),
        "release_mode": "preview",
        "publish_enabled": False,
    }


def build_review_decision(form: dict[str, str]) -> dict[str, Any]:
    return {
        "decision_recorded_at": form.get("decision_recorded_at", ""),
        "review_decision": form.get("review_decision", ""),
        "reviewer": _clean_optional_text(form.get("reviewer", "")),
        "reviewer_notes": _clean_optional_text(form.get("reviewer_notes", "")),
        "override_reason": _clean_optional_text(form.get("override_reason", "")),
        "review_status": "completed",
    }


def build_review_decision_update(form: dict[str, str]) -> dict[str, str]:
    return {
        "review_decision": form.get("review_decision", ""),
        "reviewer": _clean_optional_text(form.get("reviewer", "")),
        "reviewer_notes": _clean_optional_text(form.get("reviewer_notes", "")),
        "override_reason": _clean_optional_text(form.get("override_reason", "")),
        "review_status": "completed",
    }


def maybe_forward_to_webhook(env_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    webhook_url = os.environ.get(env_name, "").strip()
    if not webhook_url:
        return {
            "forwarded": False,
            "message": f"{env_name} is not configured; payload was prepared only.",
        }

    request = Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read(4000).decode("utf-8", errors="replace")
            return {
                "forwarded": True,
                "status_code": response.status,
                "message": "Payload was forwarded to n8n.",
                "response": response_body,
            }
    except HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", errors="replace")
        raise DashboardWebhookError(
            f"n8n webhook returned HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise DashboardWebhookError(f"n8n webhook could not be reached: {exc}") from exc


def dashboard_result(
    title: str,
    payload: dict[str, Any],
    forwarding_result: dict[str, Any],
) -> HTMLResponse:
    status_label = "Forwarded to n8n" if forwarding_result["forwarded"] else "Payload prepared"
    content = f"""
    <section class="hero compact">
      <div>
        <p class="eyebrow">Dashboard action</p>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(forwarding_result["message"])}</p>
      </div>
      <a class="button secondary" href="/dashboard">Back to dashboard</a>
    </section>

    <section class="result">
      <h2>{html.escape(status_label)}</h2>
      <pre>{html.escape(json.dumps(payload, indent=2))}</pre>
    </section>
    """
    return HTMLResponse(_page(title, content))


def dashboard_decision_result(
    review: ReleaseReview,
    forwarding_result: dict[str, Any],
) -> HTMLResponse:
    status_label = "Forwarded to n8n" if forwarding_result["forwarded"] else "Decision recorded"
    content = f"""
    <section class="hero compact">
      <div>
        <p class="eyebrow">Human decision</p>
        <h1>{html.escape(status_label)}</h1>
        <p>{html.escape(forwarding_result["message"])}</p>
      </div>
      <a class="button secondary" href="/dashboard/reviews/{review.id}">Back to review</a>
    </section>
    <section class="result">
      <h2>Recorded decision</h2>
      <dl class="facts">
        <div><dt>Decision</dt><dd>{html.escape(review.review_decision or "")}</dd></div>
        <div><dt>Reviewer</dt><dd>{html.escape(review.reviewer or "")}</dd></div>
        <div><dt>Status</dt><dd>{html.escape(review.review_status)}</dd></div>
      </dl>
    </section>
    """
    return HTMLResponse(_page("Human decision recorded", content))


def dashboard_error(title: str, message: str) -> HTMLResponse:
    content = f"""
    <section class="hero compact danger">
      <div>
        <p class="eyebrow">Dashboard action failed</p>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(message)}</p>
      </div>
      <a class="button secondary" href="/dashboard">Back to dashboard</a>
    </section>
    """
    return HTMLResponse(_page(title, content), status_code=502)


def _home_content(
    reviews: list[ReleaseReview],
    workflow_runs: list[ReleaseWorkflowRun],
    store_message: str,
    workflow_message: str,
) -> str:
    review_rows = "\n".join(_review_row(review) for review in reviews)
    workflow_rows = "\n".join(_workflow_run_row(run) for run in workflow_runs)
    summary = _queue_summary(reviews, workflow_runs)
    review_table = (
        f"""
        <table>
          <thead>
            <tr>
              <th>Release</th>
              <th>Risk</th>
              <th>Gate</th>
              <th>Workflow</th>
              <th>Next step</th>
              <th>Card</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>{review_rows}</tbody>
        </table>
        """
        if reviews
        else '<p class="empty">No review records found yet.</p>'
    )
    workflow_table = (
        f"""
        <table>
          <thead>
            <tr>
              <th>Run</th>
              <th>Status</th>
              <th>Started</th>
              <th>Completed</th>
              <th>Review</th>
              <th>Error</th>
            </tr>
          </thead>
          <tbody>{workflow_rows}</tbody>
        </table>
        """
        if workflow_runs
        else '<p class="empty">No running or failed workflow runs found.</p>'
    )
    preview_disabled = " disabled" if summary["running"] else ""
    preview_status = (
        "A briefing workflow is already running. Watch the Release Review Queue until it completes."
        if summary["running"]
        else "Ready to start a new release briefing."
    )
    return f"""
    <section class="hero">
      <div>
        <p class="eyebrow">Release Coordinator</p>
        <h1>Release review console</h1>
        <p>
          Create a release briefing, then use the active review queue to open a
          release-specific decision page.
        </p>
      </div>
      <div class="status">
        <span>Briefing only</span>
        <strong>No publish actions</strong>
      </div>
    </section>

    <section class="metrics">
      <div class="metric"><span>Active reviews</span><strong>{summary["active"]}</strong></div>
      <div class="metric blocked"><span>Blocked</span><strong>{summary["blocked"]}</strong></div>
      <div class="metric running"><span>Running workflows</span><strong>{summary["running"]}</strong></div>
      <div class="metric failed"><span>Failed workflows</span><strong>{summary["failed"]}</strong></div>
    </section>

    <main class="tabs">
      <div class="tab-list" role="tablist" aria-label="Release dashboard sections">
        <button class="tab-button active" type="button" data-tab="preview">Create Release Briefing</button>
        <button class="tab-button" type="button" data-tab="queue">Release Review Queue</button>
        <button class="tab-button" type="button" data-tab="console">Review Console</button>
      </div>

      <section class="tab-panel active" id="tab-preview">
        <div class="panel narrow-panel">
        <div class="panel-header">
          <span class="step">1</span>
          <div>
            <h2>Create release briefing</h2>
            <p>Calls n8n Workflow 1 when RELEASE_AGENT_PREVIEW_WEBHOOK_URL is configured.</p>
          </div>
        </div>
        <form method="post" action="/dashboard/start-preview">
          <label>Repository owner<input name="repository_owner" value="juesteeb-wbs" required></label>
          <label>Repository name<input name="repository_name" value="ai-release-agent-demo-v2" required></label>
          <div class="split">
            <label>Base ref<input name="base_ref" value="v1.0.0" required></label>
            <label>Target ref<input name="target_ref" value="release/1.1.0" required></label>
          </div>
          <label>Release version<input name="release_version" value="1.1.0" required></label>
          <div class="form-actions">
            <button type="submit"{preview_disabled}>Start briefing</button>
            <span class="inline-status">{html.escape(preview_status)}</span>
          </div>
        </form>
        </div>
      </section>

      <section class="tab-panel" id="tab-queue">
        <div class="panel queue-panel">
        <div class="panel-header queue-header">
          <span class="step">2</span>
          <div>
            <h2>Release review queue</h2>
            <p>{html.escape(store_message)}</p>
          </div>
        </div>
        {review_table}
        <div class="subsection-header">
          <h3>Workflow activity</h3>
          <p>{html.escape(workflow_message)}</p>
        </div>
        {workflow_table}
        </div>
      </section>

      <section class="tab-panel" id="tab-console">
        <div class="panel narrow-panel">
          <div class="panel-header">
            <span class="step">3</span>
            <div>
              <h2>Review console</h2>
              <p>Select a release from the review queue to open its decision page.</p>
            </div>
          </div>
          <p class="empty">The review console is release-specific. Open a review from the queue to see risk details, the Human Review Card link, and the decision form.</p>
        </div>
      </section>
    </main>
    """


def _review_detail_content(review: ReleaseReview) -> str:
    card_link = (
        f'<a class="button" href="{html.escape(review.human_review_card_link)}" target="_blank">Open Human Review Card</a>'
        if review.human_review_card_link
        else '<span class="muted">No review card link stored yet.</span>'
    )
    gate_banner = _gate_banner(review)
    artifact_section = _artifact_section(review)
    release_actions_section = _release_actions_section(review)
    workflow_error = (
        f'<div><dt>Workflow error</dt><dd class="error-text">{html.escape(review.workflow_error)}</dd></div>'
        if review.workflow_error
        else ""
    )
    override_visible = review.review_decision == "approve_with_override"
    override_hidden = "" if override_visible else " hidden"
    override_required = " required" if override_visible else ""
    decision_banner = _decision_banner(review)
    decision_panel = _decision_panel(review, override_hidden, override_required)
    return f"""
    <section class="hero compact">
      <div>
        <p class="eyebrow">Release review #{review.id}</p>
        <h1>{html.escape(review.release_range)}</h1>
        <p>{html.escape(review.repository)}</p>
      </div>
      {card_link}
    </section>

    <nav class="tabs detail-tabs" aria-label="Release dashboard sections">
      <a class="tab-link" href="/dashboard">Create Release Briefing</a>
      <a class="tab-link" href="/dashboard">Release Review Queue</a>
      <span class="tab-link active">Review Console</span>
    </nav>

    {gate_banner}
    {decision_banner}

    <main class="detail-grid">
      <section class="panel">
        <h2>Review summary</h2>
        <dl class="facts">
          <div><dt>Risk</dt><dd>{html.escape(_risk_text(review))}</dd></div>
          <div><dt>Gate status</dt><dd>{_status_badge(review.gate_status)}</dd></div>
          <div><dt>Workflow status</dt><dd>{_workflow_badge(review.workflow_status)}</dd></div>
          <div><dt>Workflow started</dt><dd>{html.escape(review.workflow_started_at or "Not available")}</dd></div>
          <div><dt>Workflow completed</dt><dd>{html.escape(review.workflow_completed_at or "Not available")}</dd></div>
          {workflow_error}
          <div><dt>Review status</dt><dd>{html.escape(review.review_status)}</dd></div>
          <div><dt>Human decision</dt><dd>{_decision_badge(review.review_decision)}</dd></div>
          <div><dt>Recommended next step</dt><dd>{html.escape(review.recommended_next_step or "Not available")}</dd></div>
          <div><dt>Publication status</dt><dd>{html.escape(review.publication_status_message or "Not available")}</dd></div>
        </dl>
      </section>

      {decision_panel}

      {artifact_section}
      {release_actions_section}
    </main>
    """


def _review_row(review: ReleaseReview) -> str:
    card_cell = (
        f'<a href="{html.escape(review.human_review_card_link)}" target="_blank">Open card</a>'
        if review.human_review_card_link
        else '<span class="muted">Missing</span>'
    )
    return f"""
    <tr>
      <td><strong>{html.escape(review.release_range)}</strong><br><span>{html.escape(review.repository)}</span></td>
      <td>{html.escape(_risk_text(review))}</td>
      <td>{_status_badge(review.gate_status)}</td>
      <td>{_workflow_badge(review.workflow_status)}</td>
      <td>{html.escape(review.recommended_next_step or "Review release package")}</td>
      <td>{card_cell}</td>
      <td>{_review_status_text(review)}</td>
      <td><a href="/dashboard/reviews/{review.id}">Review</a></td>
    </tr>
    """


def _decision_panel(
    review: ReleaseReview,
    override_hidden: str,
    override_required: str,
) -> str:
    if review.review_status == "completed":
        override_detail = (
            f'<div><dt>Override reason</dt><dd>{html.escape(review.override_reason)}</dd></div>'
            if review.override_reason
            else ""
        )
        return f"""
        <section class="panel">
          <h2>Decision recorded</h2>
          <p class="form-intro">This review is read-only because a human decision has already been submitted.</p>
          <dl class="facts">
            <div><dt>Decision</dt><dd>{_decision_badge(review.review_decision)}</dd></div>
            <div><dt>Reviewer</dt><dd>{html.escape(review.reviewer or "Not available")}</dd></div>
            <div><dt>Reviewer notes</dt><dd>{html.escape(review.reviewer_notes or "No reviewer notes recorded.")}</dd></div>
            {override_detail}
          </dl>
        </section>
        """

    return f"""
    <section class="panel">
      <h2>Submit decision</h2>
      <p class="form-intro">Record the reviewer decision after checking the Human Review Card and release artifacts.</p>
      <form method="post" action="/dashboard/reviews/{review.id}/decision">
        <label>Decision
          <select name="review_decision" required data-review-decision>
            {_decision_options(review.review_decision)}
          </select>
        </label>
        <div class="decision-help">
          <strong>Decision guide</strong>
          <ul>
            <li><b>approve</b>: use only when normal approval is allowed.</li>
            <li><b>approve_with_override</b>: requires an override reason.</li>
            <li><b>request_changes</b>: use when blockers, warnings, or missing information remain.</li>
            <li><b>reject</b>: use when the release should not continue.</li>
          </ul>
        </div>
        <label>Reviewer<input name="reviewer" value="{html.escape(review.reviewer or "")}" required></label>
        <label>Reviewer notes<textarea name="reviewer_notes" rows="5">{html.escape(review.reviewer_notes or "")}</textarea></label>
        <label data-override-reason-field{override_hidden}>Override reason<textarea name="override_reason" rows="3" data-override-reason{override_required}>{html.escape(review.override_reason or "")}</textarea></label>
        <button type="submit">Submit review decision</button>
      </form>
    </section>
    """


def _workflow_run_row(run: ReleaseWorkflowRun) -> str:
    review_cell = (
        f'<a href="/dashboard/reviews/{run.release_review_id}">Review #{run.release_review_id}</a>'
        if run.release_review_id
        else '<span class="muted">No review created yet</span>'
    )
    error = _truncate(run.workflow_error or "", 140)
    return f"""
    <tr>
      <td><strong>{html.escape(run.workflow_run_id)}</strong></td>
      <td>{_workflow_badge(run.workflow_status)}</td>
      <td>{html.escape(run.workflow_started_at or "Not available")}</td>
      <td>{html.escape(run.workflow_completed_at or "Not completed")}</td>
      <td>{review_cell}</td>
      <td class="error-cell">{html.escape(error) if error else '<span class="muted">None</span>'}</td>
    </tr>
    """


def _artifact_section(review: ReleaseReview) -> str:
    links = {
        **review.artifact_links,
    }
    if review.human_review_card_link and "human_review_card" not in links:
        links["human_review_card"] = review.human_review_card_link

    if not links:
        return """
        <section class="panel artifacts-panel">
          <h2>Artifacts</h2>
          <p class="empty">No artifact links have been stored for this review yet.</p>
        </section>
        """

    groups = [
        (
            "Human review",
            [
                ("human_review_card", "Human Review Card"),
                ("human_review_notification", "Human Review Notification"),
                ("compact_release_view", "Compact Release View"),
            ],
        ),
        (
            "Release communication",
            [
                ("release_notes_preview", "Release Notes Preview"),
                ("customer_release_notes", "Customer Release Notes"),
                ("technical_changelog", "Technical Changelog"),
            ],
        ),
        (
            "Validation and planning",
            [
                ("testing_qa", "Testing and QA"),
                ("pull_request_preparation", "Pull Request Preparation"),
                ("deployment_rollback_guidance", "Deployment and Rollback Guidance"),
                ("deployment_and_rollback_guidance", "Deployment and Rollback Guidance"),
            ],
        ),
    ]
    rendered_groups = [
        _artifact_group(title, entries, links)
        for title, entries in groups
        if any(links.get(key) for key, _label in entries)
    ]
    return f"""
    <section class="panel artifacts-panel">
      <h2>Artifacts</h2>
      <p class="form-intro">Open the generated release review material stored in Google Drive.</p>
      <div class="artifact-groups">
        {"".join(rendered_groups)}
      </div>
    </section>
    """


def _artifact_group(
    title: str,
    entries: list[tuple[str, str]],
    links: dict[str, str],
) -> str:
    items = "\n".join(
        _artifact_link(label, links[key])
        for key, label in entries
        if links.get(key)
    )
    return f"""
    <section class="artifact-group">
      <h3>{html.escape(title)}</h3>
      <ul>{items}</ul>
    </section>
    """


def _artifact_link(label: str, link: str) -> str:
    return f'<li><a href="{html.escape(link)}" target="_blank">{html.escape(label)}</a></li>'


def _release_actions_section(review: ReleaseReview) -> str:
    approved = review.review_decision in {"approve", "approve_with_override"}
    status_message = (
        "This release is approved for the next controlled release steps."
        if approved
        else "Release actions are unavailable because this review is not approved."
    )
    override_note = (
        "<p class=\"form-intro\">Override reason must be retained as part of the release audit trail.</p>"
        if review.review_decision == "approve_with_override"
        else ""
    )
    cards = [
        (
            "GitHub Release",
            [
                "Create GitHub release draft",
                "Attach technical changelog",
                "Attach release evidence summary",
            ],
        ),
        (
            "Customer Communication",
            [
                "Publish customer-facing release notes",
                "Send release announcement for review",
            ],
        ),
        (
            "Engineering Follow-up",
            [
                "Create final release PR",
                "Prepare tag v1.1.0",
                "Confirm deployment checklist",
            ],
        ),
        (
            "Audit Trail",
            [
                "Store approval decision",
                "Store generated artifacts",
                "Store override reason if applicable",
            ],
        ),
    ]
    rendered_cards = "".join(
        _release_action_card(title, actions, approved)
        for title, actions in cards
    )
    return f"""
    <section class="panel release-actions-panel">
      <h2>Release Actions Preview</h2>
      <p class="form-intro">Preview only. No publishing action is implemented or executed.</p>
      <div class="release-action-status {'available' if approved else 'locked'}">
        {html.escape(status_message)}
      </div>
      {override_note}
      <div class="release-action-grid">
        {rendered_cards}
      </div>
    </section>
    """


def _release_action_card(title: str, actions: list[str], available: bool) -> str:
    action_items = "\n".join(f"<li>{html.escape(action)}</li>" for action in actions)
    label = "Future capability" if available else "Locked"
    return f"""
    <section class="release-action-card {'available' if available else 'locked'}">
      <div>
        <h3>{html.escape(title)}</h3>
        <span>{html.escape(label)}</span>
      </div>
      <ul>{action_items}</ul>
      <button type="button" disabled>Preview only</button>
    </section>
    """


def _queue_summary(
    reviews: list[ReleaseReview],
    workflow_runs: list[ReleaseWorkflowRun],
) -> dict[str, int]:
    return {
        "active": len(reviews),
        "blocked": sum(1 for review in reviews if review.gate_status == "blocked"),
        "running": sum(1 for run in workflow_runs if run.workflow_status == "running"),
        "failed": sum(1 for run in workflow_runs if run.workflow_status == "failed"),
    }


def _gate_banner(review: ReleaseReview) -> str:
    status = review.gate_status or "unknown"
    if status == "blocked":
        message = "This release cannot be approved normally while safety gates are blocked."
        css = "blocked"
    elif status == "warning":
        message = "This release has warnings that require reviewer attention or an override reason."
        css = "warning"
    elif status == "pass":
        message = "No blocking safety gate condition was detected. Review the artifacts before approval."
        css = "pass"
    else:
        message = "Gate status is unavailable. Review the evidence before making a decision."
        css = "unknown"
    return f"""
    <section class="gate-banner {css}">
      <strong>{html.escape(status.title())}</strong>
      <span>{html.escape(message)}</span>
    </section>
    """


def _decision_banner(review: ReleaseReview) -> str:
    decision = review.review_decision or "pending_review"
    if decision in {"", "pending_review"}:
        return ""

    title, message, css = _decision_outcome(decision)
    details = []
    if review.reviewer:
        details.append(f"Reviewer: {review.reviewer}")
    if review.reviewer_notes:
        details.append(f"Notes: {review.reviewer_notes}")
    if decision == "approve_with_override" and review.override_reason:
        details.append(f"Override reason: {review.override_reason}")
    detail_markup = (
        f'<p>{html.escape(" | ".join(details))}</p>'
        if details
        else ""
    )
    return f"""
    <section class="decision-banner {css}">
      <strong>{html.escape(title)}</strong>
      <span>{html.escape(message)}</span>
      {detail_markup}
    </section>
    """


def _decision_outcome(decision: str) -> tuple[str, str, str]:
    if decision == "request_changes":
        return (
            "Changes requested",
            "This release needs changes and should be re-evaluated before approval.",
            "changes",
        )
    if decision == "approve":
        return (
            "Approved",
            "The reviewer accepted this release briefing.",
            "approved",
        )
    if decision == "approve_with_override":
        return (
            "Approved with override",
            "The reviewer accepted warnings with a documented override reason.",
            "override",
        )
    if decision == "reject":
        return (
            "Rejected",
            "This release should not proceed.",
            "rejected",
        )
    return (
        decision.replace("_", " ").title(),
        "A human review decision has been recorded.",
        "unknown",
    )


def _risk_text(review: ReleaseReview) -> str:
    score = "unknown" if review.risk_score is None else str(review.risk_score)
    return f"{review.risk_level or 'unknown'} ({score})"


def _status_badge(status: str | None) -> str:
    value = status or "unknown"
    css = html.escape(value)
    return f'<span class="badge {css}">{html.escape(value)}</span>'


def _workflow_badge(status: str | None) -> str:
    value = status or "idle"
    css = html.escape(value)
    return f'<span class="badge workflow {css}">{html.escape(value)}</span>'


def _decision_badge(decision: str | None) -> str:
    value = decision or "pending_review"
    css = html.escape(value)
    return f'<span class="badge decision {css}">{html.escape(value)}</span>'


def _review_status_text(review: ReleaseReview) -> str:
    if review.review_status == "completed" and review.review_decision:
        return f"{html.escape(review.review_status)}<br>{_decision_badge(review.review_decision)}"
    return html.escape(review.review_status)


def _decision_options(current: str | None) -> str:
    decisions = ["request_changes", "approve", "approve_with_override", "reject"]
    return "\n".join(
        f'<option value="{decision}"{" selected" if decision == current else ""}>{decision}</option>'
        for decision in decisions
    )


def _workflow_run_from_row(row: tuple[Any, ...]) -> ReleaseWorkflowRun:
    return ReleaseWorkflowRun(
        workflow_run_id=str(row[0]),
        workflow_status=row[1],
        workflow_started_at=_stringify_datetime(row[2]) if row[2] else None,
        workflow_completed_at=_stringify_datetime(row[3]) if row[3] else None,
        workflow_error=row[4],
        release_review_id=row[5],
    )


def _review_from_row(row: tuple[Any, ...]) -> ReleaseReview:
    return ReleaseReview(
        id=row[0],
        decision_recorded_at=_stringify_datetime(row[1]),
        repository=row[2],
        release_range=row[3],
        risk_level=row[4],
        risk_score=float(row[5]) if row[5] is not None else None,
        gate_status=row[6],
        recommended_next_step=row[7],
        publication_status_message=row[8],
        human_review_card_link=row[9],
        review_decision=row[10],
        reviewer=row[11],
        reviewer_notes=row[12],
        override_reason=row[13],
        review_status=row[14],
        processed_at=_stringify_datetime(row[15]) if row[15] else None,
        processing_result=row[16],
        processing_notes=row[17],
        artifact_links=_parse_artifact_links(row[18]) if len(row) > 18 else {},
        workflow_status=row[19] if len(row) > 19 else None,
        workflow_started_at=(
            _stringify_datetime(row[20]) if len(row) > 20 and row[20] else None
        ),
        workflow_completed_at=(
            _stringify_datetime(row[21]) if len(row) > 21 and row[21] else None
        ),
        workflow_error=row[22] if len(row) > 22 else None,
    )


def _parse_artifact_links(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            str(key): str(link)
            for key, link in value.items()
            if key and isinstance(link, str) and link.strip()
        }
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return _parse_artifact_links(parsed)
    return {}


def _truncate(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _stringify_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return str(value)


def _page(title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #111827;
      --muted: #475569;
      --line: #cbd5e1;
      --panel: #f8fafc;
      --blue: #2563eb;
      --cyan: #0891b2;
      --green: #047857;
      --red: #b91c1c;
      --amber-bg: #fff7ed;
    }}
    * {{ box-sizing: border-box; }}
    [hidden] {{
      display: none !important;
    }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #ffffff;
      color: var(--ink);
    }}
    body::before {{
      content: "";
      display: block;
      height: 8px;
      background: linear-gradient(90deg, var(--blue), var(--cyan), var(--green));
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      gap: 32px;
      padding: 48px 64px 32px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .hero.compact {{ align-items: center; }}
    .hero.danger {{ border-bottom-color: #fecaca; }}
    .eyebrow {{
      margin: 0 0 10px;
      text-transform: uppercase;
      letter-spacing: 0;
      font-size: 13px;
      font-weight: 800;
      color: var(--blue);
    }}
    h1 {{
      margin: 0;
      max-width: 760px;
      font-size: 48px;
      line-height: 1.05;
      letter-spacing: 0;
    }}
    h2 {{
      margin: 0 0 8px;
      font-size: 25px;
      letter-spacing: 0;
    }}
    h3 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }}
    p {{
      margin: 12px 0 0;
      max-width: 700px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.45;
    }}
    .status {{
      min-width: 190px;
      align-self: flex-start;
      padding: 18px 22px;
      border: 1px solid #fdba74;
      background: var(--amber-bg);
      border-radius: 8px;
      color: #9a3412;
      text-align: center;
    }}
    .status span {{
      display: block;
      font-size: 14px;
      font-weight: 700;
    }}
    .status strong {{
      display: block;
      margin-top: 6px;
      font-size: 18px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 28px;
      padding: 36px 64px 56px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      padding: 28px 64px 0;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px 20px;
      background: #f8fafc;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .metric strong {{
      display: block;
      margin-top: 8px;
      color: var(--ink);
      font-size: 32px;
      line-height: 1;
    }}
    .metric.blocked {{
      border-color: #fecaca;
      background: #fef2f2;
    }}
    .metric.warning {{
      border-color: #fde68a;
      background: #fffbeb;
    }}
    .metric.running {{
      border-color: #bfdbfe;
      background: #eff6ff;
    }}
    .metric.failed {{
      border-color: #fecaca;
      background: #fef2f2;
    }}
    .dashboard-layout {{
      display: grid;
      grid-template-columns: minmax(320px, 0.72fr) minmax(0, 1.28fr);
      gap: 28px;
      padding: 36px 64px 56px;
      align-items: start;
    }}
    .tabs {{
      padding: 32px 64px 56px;
    }}
    .tab-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      border-bottom: 1px solid #dbe3ec;
      margin-bottom: 24px;
    }}
    .tab-button, .tab-link {{
      appearance: none;
      border: 0;
      border-bottom: 3px solid transparent;
      background: transparent;
      color: #475569;
      padding: 13px 16px 12px;
      font: inherit;
      font-size: 15px;
      font-weight: 800;
      cursor: pointer;
      text-decoration: none;
    }}
    .tab-button.active, .tab-link.active {{
      color: var(--blue);
      border-bottom-color: var(--blue);
    }}
    .tab-panel {{
      display: none;
    }}
    .tab-panel.active {{
      display: block;
    }}
    .narrow-panel {{
      max-width: 680px;
    }}
    .detail-tabs {{
      padding-top: 24px;
      padding-bottom: 0;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      border-bottom: 1px solid #dbe3ec;
    }}
    .queue {{
      padding: 32px 64px 0;
    }}
    .section-heading {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: end;
      margin-bottom: 18px;
    }}
    .empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 20px;
      background: #f8fafc;
      font-size: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: white;
    }}
    th, td {{
      padding: 14px 16px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      vertical-align: middle;
      font-size: 15px;
    }}
    th {{
      background: #f1f5f9;
      color: #334155;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    td span, .muted {{
      color: var(--muted);
    }}
    .subsection-header {{
      margin: 28px 0 14px;
      padding-top: 22px;
      border-top: 1px solid #e2e8f0;
    }}
    .subsection-header p {{
      margin-top: 6px;
      font-size: 15px;
    }}
    .error-cell {{
      max-width: 360px;
      color: #991b1b;
      font-weight: 650;
    }}
    .badge {{
      display: inline-block;
      min-width: 74px;
      border-radius: 999px;
      padding: 5px 10px;
      background: #e2e8f0;
      color: #334155;
      font-size: 13px;
      font-weight: 800;
      text-align: center;
    }}
    .badge.blocked {{
      background: #fee2e2;
      color: #991b1b;
    }}
    .badge.warning {{
      background: #fef3c7;
      color: #92400e;
    }}
    .badge.pass {{
      background: #dcfce7;
      color: #166534;
    }}
    .badge.running {{
      background: #dbeafe;
      color: #1d4ed8;
    }}
    .badge.completed {{
      background: #dcfce7;
      color: #166534;
    }}
    .badge.failed {{
      background: #fee2e2;
      color: #991b1b;
    }}
    .badge.idle {{
      background: #e2e8f0;
      color: #475569;
    }}
    .badge.request_changes {{
      background: #fee2e2;
      color: #991b1b;
    }}
    .badge.approve {{
      background: #dcfce7;
      color: #166534;
    }}
    .badge.approve_with_override {{
      background: #fef3c7;
      color: #92400e;
    }}
    .badge.reject {{
      background: #e2e8f0;
      color: #334155;
    }}
    .error-text {{
      color: #991b1b;
      font-weight: 700;
    }}
    .gate-banner, .decision-banner {{
      display: flex;
      align-items: center;
      gap: 18px;
      margin: 28px 64px 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px 20px;
      background: #f8fafc;
    }}
    .decision-banner {{
      display: grid;
      gap: 8px;
    }}
    .gate-banner strong, .decision-banner strong {{
      min-width: 86px;
      font-size: 17px;
    }}
    .gate-banner span, .decision-banner span {{
      color: #334155;
      font-size: 16px;
      line-height: 1.4;
    }}
    .decision-banner p {{
      margin: 0;
      max-width: none;
      color: #475569;
      font-size: 14px;
    }}
    .gate-banner.blocked {{
      border-color: #fecaca;
      background: #fef2f2;
      color: #991b1b;
    }}
    .gate-banner.warning {{
      border-color: #fde68a;
      background: #fffbeb;
      color: #92400e;
    }}
    .gate-banner.pass {{
      border-color: #bbf7d0;
      background: #f0fdf4;
      color: #166534;
    }}
    .decision-banner.changes, .decision-banner.rejected {{
      border-color: #fecaca;
      background: #fef2f2;
      color: #991b1b;
    }}
    .decision-banner.approved {{
      border-color: #bbf7d0;
      background: #f0fdf4;
      color: #166534;
    }}
    .decision-banner.override {{
      border-color: #fde68a;
      background: #fffbeb;
      color: #92400e;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
      gap: 28px;
      padding: 36px 64px 56px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 28px;
    }}
    .artifacts-panel {{
      grid-column: 1 / -1;
    }}
    .release-actions-panel {{
      grid-column: 1 / -1;
    }}
    .artifact-groups {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .release-action-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .release-action-status {{
      display: inline-block;
      margin-top: 12px;
      border-radius: 6px;
      padding: 9px 12px;
      font-size: 14px;
      font-weight: 800;
    }}
    .release-action-status.available {{
      border: 1px solid #bbf7d0;
      background: #f0fdf4;
      color: #166534;
    }}
    .release-action-status.locked {{
      border: 1px solid #fecaca;
      background: #fef2f2;
      color: #991b1b;
    }}
    .artifact-group {{
      border: 1px solid #dbe3ec;
      border-radius: 8px;
      background: white;
      padding: 18px;
    }}
    .release-action-card {{
      display: grid;
      align-content: space-between;
      gap: 16px;
      min-height: 240px;
      border: 1px solid #dbe3ec;
      border-radius: 8px;
      background: white;
      padding: 18px;
    }}
    .release-action-card.locked {{
      background: #f8fafc;
      opacity: 0.76;
    }}
    .release-action-card div {{
      display: grid;
      gap: 8px;
    }}
    .release-action-card span {{
      justify-self: start;
      border-radius: 999px;
      background: #e2e8f0;
      color: #334155;
      padding: 5px 9px;
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .release-action-card.available span {{
      background: #dbeafe;
      color: #1d4ed8;
    }}
    .artifact-group ul {{
      display: grid;
      gap: 10px;
      margin: 14px 0 0;
      padding-left: 18px;
    }}
    .release-action-card ul {{
      display: grid;
      gap: 8px;
      margin: 0;
      padding-left: 18px;
      color: #475569;
      font-size: 14px;
      line-height: 1.4;
    }}
    .artifact-group a {{
      color: var(--blue);
      font-weight: 800;
      text-decoration: none;
    }}
    .artifact-group a:hover {{
      text-decoration: underline;
    }}
    .panel-header {{
      display: flex;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 22px;
    }}
    .step {{
      display: grid;
      place-items: center;
      flex: 0 0 auto;
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: var(--blue);
      color: white;
      font-weight: 800;
    }}
    .panel p {{
      margin-top: 2px;
      font-size: 15px;
    }}
    .queue-panel {{
      overflow: hidden;
    }}
    .queue-header {{
      margin-bottom: 18px;
    }}
    .facts {{
      display: grid;
      gap: 18px;
      margin: 18px 0 0;
    }}
    .facts div {{
      display: grid;
      gap: 6px;
    }}
    .facts dt {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .facts dd {{
      margin: 0;
      color: var(--ink);
      font-size: 17px;
      line-height: 1.4;
    }}
    form {{
      display: grid;
      gap: 16px;
    }}
    .form-intro {{
      margin: 0 0 16px;
      font-size: 15px;
    }}
    .decision-help {{
      border: 1px solid #dbe3ec;
      border-radius: 8px;
      background: #ffffff;
      padding: 14px 16px;
    }}
    .decision-help strong {{
      display: block;
      margin-bottom: 8px;
      color: #334155;
      font-size: 14px;
    }}
    .decision-help ul {{
      margin: 0;
      padding-left: 18px;
      color: #475569;
      font-size: 14px;
      line-height: 1.45;
    }}
    .split {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    label {{
      display: grid;
      gap: 7px;
      color: #334155;
      font-size: 14px;
      font-weight: 700;
    }}
    input, select, textarea {{
      width: 100%;
      min-height: 42px;
      border: 1px solid #b6c2d1;
      border-radius: 6px;
      padding: 10px 12px;
      color: var(--ink);
      background: white;
      font: inherit;
      font-size: 15px;
    }}
    textarea {{
      resize: vertical;
      line-height: 1.35;
    }}
    button, .button {{
      justify-self: start;
      border: 0;
      border-radius: 6px;
      padding: 11px 16px;
      background: var(--blue);
      color: white;
      font-weight: 800;
      font-size: 15px;
      cursor: pointer;
      text-decoration: none;
    }}
    button:disabled {{
      background: #94a3b8;
      cursor: not-allowed;
    }}
    .form-actions {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 14px;
    }}
    .inline-status {{
      color: var(--muted);
      font-size: 14px;
      font-weight: 700;
    }}
    .button.secondary {{
      background: #e2e8f0;
      color: #0f172a;
    }}
    .result {{
      padding: 36px 64px;
    }}
    pre {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #0f172a;
      color: #e2e8f0;
      padding: 20px;
      font-size: 14px;
      line-height: 1.45;
    }}
    @media (max-width: 900px) {{
      .hero, .grid, .metrics, .dashboard-layout, .tabs, .queue, .detail-grid {{
        padding-left: 24px;
        padding-right: 24px;
      }}
      .hero, .grid, .metrics, .dashboard-layout, .split, .detail-grid, .artifact-groups, .release-action-grid {{
        grid-template-columns: 1fr;
      }}
      .gate-banner, .decision-banner {{
        margin-left: 24px;
        margin-right: 24px;
        align-items: flex-start;
        flex-direction: column;
      }}
      .hero {{
        display: grid;
      }}
      h1 {{
        font-size: 38px;
      }}
    }}
  </style>
</head>
<body>
  {content}
  <script>
    document.querySelectorAll("[data-tab]").forEach((button) => {{
      button.addEventListener("click", () => {{
        const tab = button.dataset.tab;
        document.querySelectorAll("[data-tab]").forEach((item) => item.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("active"));
        button.classList.add("active");
        document.getElementById(`tab-${{tab}}`)?.classList.add("active");
      }});
    }});
    document.querySelectorAll("form").forEach((form) => {{
      const decision = form.querySelector("[data-review-decision]");
      const overrideField = form.querySelector("[data-override-reason-field]");
      const overrideReason = form.querySelector("[data-override-reason]");
      if (!decision || !overrideField || !overrideReason) {{
        return;
      }}
      const syncOverrideReason = () => {{
        const show = decision.value === "approve_with_override";
        overrideField.hidden = !show;
        overrideReason.required = show;
        if (!show) {{
          overrideReason.value = "";
        }}
      }};
      syncOverrideReason();
      decision.addEventListener("change", syncOverrideReason);
    }});
  </script>
</body>
</html>"""
