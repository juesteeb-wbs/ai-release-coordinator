from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from release_agent.errors import ReleaseRequestError


ReleaseMode = Literal["preview"]


@dataclass(frozen=True)
class ReleaseRequest:
    repository_owner: str
    repository_name: str
    base_ref: str
    target_ref: str
    release_version: str
    release_mode: ReleaseMode = "preview"
    publish_enabled: bool = False

    def validate(self) -> None:
        required = {
            "repository_owner": self.repository_owner,
            "repository_name": self.repository_name,
            "base_ref": self.base_ref,
            "target_ref": self.target_ref,
            "release_version": self.release_version,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ReleaseRequestError(f"Missing required fields: {', '.join(missing)}")
        if self.release_mode != "preview":
            raise ReleaseRequestError("release_mode must be 'preview' for the MVP.")
        if self.publish_enabled:
            raise ReleaseRequestError("publish_enabled must remain false for the MVP.")

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ReleaseRequest":
        request = cls(
            repository_owner=str(data.get("repository_owner", "")),
            repository_name=str(data.get("repository_name", "")),
            base_ref=str(data.get("base_ref", "")),
            target_ref=str(data.get("target_ref", "")),
            release_version=str(data.get("release_version", "")),
            release_mode=data.get("release_mode", "preview"),
            publish_enabled=bool(data.get("publish_enabled", False)),
        )
        request.validate()
        return request


@dataclass(frozen=True)
class EvidenceWarning:
    code: str
    message: str
    reference: str | None = None


@dataclass(frozen=True)
class ResolvedRefs:
    base_ref: str
    base_sha: str
    target_ref: str
    target_sha: str


@dataclass(frozen=True)
class CommitEvidence:
    sha: str
    message: str
    author_name: str | None
    author_email: str | None
    authored_at: str | None
    committer_name: str | None
    committed_at: str | None
    html_url: str | None


@dataclass(frozen=True)
class PullRequestEvidence:
    number: int
    title: str
    body: str | None
    labels: list[str]
    author: str | None
    state: str
    merged_at: str | None
    merge_commit_sha: str | None
    html_url: str | None


@dataclass(frozen=True)
class FileEvidence:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None = None
    omitted_reason: str | None = None


@dataclass(frozen=True)
class CheckRunEvidence:
    name: str
    status: str | None
    conclusion: str | None
    html_url: str | None


@dataclass(frozen=True)
class ReleaseEvidence:
    collected_at: str
    request: ReleaseRequest
    resolved_refs: ResolvedRefs
    commits: list[CommitEvidence]
    pull_requests: list[PullRequestEvidence]
    files: list[FileEvidence]
    check_runs: list[CheckRunEvidence]
    tag_metadata: dict[str, Any] | None
    warnings: list[EvidenceWarning] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
