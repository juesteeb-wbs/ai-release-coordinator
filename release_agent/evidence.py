from typing import Any

from release_agent.limits import EvidenceLimits
from release_agent.models import (
    CheckRunEvidence,
    CommitEvidence,
    EvidenceWarning,
    FileEvidence,
    PullRequestEvidence,
    ReleaseEvidence,
    ReleaseRequest,
    ResolvedRefs,
    utc_now,
)
from release_agent.redaction import redact_secrets
from release_agent.errors import GitHubClientError


class ReleaseEvidenceCollector:
    def __init__(self, github_client: Any, limits: EvidenceLimits | None = None) -> None:
        self.github_client = github_client
        self.limits = limits or EvidenceLimits()

    def collect(self, request: ReleaseRequest) -> ReleaseEvidence:
        request.validate()
        owner = request.repository_owner
        repo = request.repository_name

        base_sha = self.github_client.resolve_commit_sha(owner, repo, request.base_ref)
        target_sha = self.github_client.resolve_commit_sha(owner, repo, request.target_ref)
        compare = self.github_client.compare(owner, repo, request.base_ref, request.target_ref)

        warnings: list[EvidenceWarning] = []
        commits = [_commit_from_github(commit) for commit in compare.get("commits", [])]
        pull_requests = self._collect_pull_requests(owner, repo, commits, warnings)
        files = self._collect_files(compare.get("files", []), warnings)
        check_runs = self._collect_check_runs(owner, repo, target_sha, warnings)
        tag_metadata = self.github_client.tag_metadata(owner, repo, request.base_ref)

        return ReleaseEvidence(
            collected_at=utc_now(),
            request=request,
            resolved_refs=ResolvedRefs(
                base_ref=request.base_ref,
                base_sha=base_sha,
                target_ref=request.target_ref,
                target_sha=target_sha,
            ),
            commits=commits,
            pull_requests=pull_requests,
            files=files,
            check_runs=check_runs,
            tag_metadata=tag_metadata,
            warnings=warnings,
        )

    def _collect_check_runs(
        self,
        owner: str,
        repo: str,
        target_sha: str,
        warnings: list[EvidenceWarning],
    ) -> list[CheckRunEvidence]:
        try:
            return [
                _check_run_from_github(run)
                for run in self.github_client.check_runs_for_ref(owner, repo, target_sha)
            ]
        except GitHubClientError as exc:
            warnings.append(
                EvidenceWarning(
                    code="check_runs_unavailable",
                    message=f"Check-run evidence could not be retrieved: {exc}",
                    reference=target_sha,
                )
            )
            return []

    def _collect_pull_requests(
        self,
        owner: str,
        repo: str,
        commits: list[CommitEvidence],
        warnings: list[EvidenceWarning],
    ) -> list[PullRequestEvidence]:
        pull_requests_by_number: dict[int, PullRequestEvidence] = {}
        for commit in commits:
            pulls = self.github_client.pull_requests_for_commit(owner, repo, commit.sha)
            if not pulls:
                warnings.append(
                    EvidenceWarning(
                        code="commit_without_pull_request",
                        message="No associated pull request was found for commit.",
                        reference=commit.sha,
                    )
                )
            for pull in pulls:
                evidence = _pull_request_from_github(pull)
                pull_requests_by_number[evidence.number] = evidence
        return sorted(pull_requests_by_number.values(), key=lambda pull: pull.number)

    def _collect_files(
        self,
        files: list[dict[str, Any]],
        warnings: list[EvidenceWarning],
    ) -> list[FileEvidence]:
        collected: list[FileEvidence] = []
        total_patch_chars = 0

        for file_data in files:
            filename = file_data["filename"]
            if self.limits.is_binary_path(filename):
                warnings.append(
                    EvidenceWarning(
                        code="binary_file_omitted",
                        message="Binary file omitted from patch evidence.",
                        reference=filename,
                    )
                )
                collected.append(_file_from_github(file_data, patch=None, omitted_reason="binary"))
                continue

            if self.limits.is_generated_path(filename):
                warnings.append(
                    EvidenceWarning(
                        code="generated_file_omitted",
                        message="Generated file omitted from patch evidence.",
                        reference=filename,
                    )
                )
                collected.append(_file_from_github(file_data, patch=None, omitted_reason="generated"))
                continue

            patch = file_data.get("patch")
            omitted_reason = None
            if patch is not None:
                patch, redacted = redact_secrets(patch)
                if redacted:
                    warnings.append(
                        EvidenceWarning(
                            code="secret_redacted",
                            message="Potential secret redacted from patch evidence.",
                            reference=filename,
                        )
                    )
                if len(patch) > self.limits.max_file_patch_chars:
                    patch = patch[: self.limits.max_file_patch_chars]
                    omitted_reason = "file_patch_truncated"
                    warnings.append(
                        EvidenceWarning(
                            code="file_patch_truncated",
                            message="Patch exceeded per-file evidence limit.",
                            reference=filename,
                        )
                    )
                if total_patch_chars + len(patch) > self.limits.max_total_patch_chars:
                    patch = None
                    omitted_reason = "total_patch_limit"
                    warnings.append(
                        EvidenceWarning(
                            code="total_patch_limit",
                            message="Patch omitted because total evidence limit was reached.",
                            reference=filename,
                        )
                    )
                else:
                    total_patch_chars += len(patch)

            collected.append(_file_from_github(file_data, patch=patch, omitted_reason=omitted_reason))

        return collected


def _commit_from_github(commit: dict[str, Any]) -> CommitEvidence:
    details = commit.get("commit", {})
    author = details.get("author") or {}
    committer = details.get("committer") or {}
    return CommitEvidence(
        sha=commit["sha"],
        message=details.get("message", ""),
        author_name=author.get("name"),
        author_email=author.get("email"),
        authored_at=author.get("date"),
        committer_name=committer.get("name"),
        committed_at=committer.get("date"),
        html_url=commit.get("html_url"),
    )


def _pull_request_from_github(pull: dict[str, Any]) -> PullRequestEvidence:
    user = pull.get("user") or {}
    return PullRequestEvidence(
        number=pull["number"],
        title=pull["title"],
        body=pull.get("body"),
        labels=[label["name"] for label in pull.get("labels", [])],
        author=user.get("login"),
        state=pull.get("state", ""),
        merged_at=pull.get("merged_at"),
        merge_commit_sha=pull.get("merge_commit_sha"),
        html_url=pull.get("html_url"),
    )


def _file_from_github(
    file_data: dict[str, Any],
    *,
    patch: str | None,
    omitted_reason: str | None,
) -> FileEvidence:
    return FileEvidence(
        filename=file_data["filename"],
        status=file_data.get("status", ""),
        additions=file_data.get("additions", 0),
        deletions=file_data.get("deletions", 0),
        changes=file_data.get("changes", 0),
        patch=patch,
        omitted_reason=omitted_reason,
    )


def _check_run_from_github(run: dict[str, Any]) -> CheckRunEvidence:
    return CheckRunEvidence(
        name=run.get("name", ""),
        status=run.get("status"),
        conclusion=run.get("conclusion"),
        html_url=run.get("html_url"),
    )
