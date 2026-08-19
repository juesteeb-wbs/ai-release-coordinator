from release_agent.evidence import ReleaseEvidenceCollector
from release_agent.errors import GitHubClientError
from release_agent.limits import EvidenceLimits
from release_agent.models import ReleaseRequest


class FakeGitHubClient:
    def resolve_commit_sha(self, owner, repo, ref):
        refs = {"v1.0.0": "base-sha", "release/1.1.0": "target-sha"}
        return refs[ref]

    def compare(self, owner, repo, base, head):
        return {
            "commits": [
                {
                    "sha": "commit-with-pr",
                    "html_url": "https://example.test/commit-with-pr",
                    "commit": {
                        "message": "Add CSV ticket export",
                        "author": {
                            "name": "Ada",
                            "email": "ada@example.com",
                            "date": "2026-07-22T10:00:00Z",
                        },
                        "committer": {
                            "name": "Ada",
                            "date": "2026-07-22T10:01:00Z",
                        },
                    },
                },
                {
                    "sha": "direct-commit",
                    "html_url": "https://example.test/direct-commit",
                    "commit": {"message": "Direct maintenance commit"},
                },
            ],
            "files": [
                {
                    "filename": "app/main.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 1,
                    "changes": 11,
                    "patch": "+API_TOKEN=abc123\n+print('hello')",
                },
                {
                    "filename": "dist/generated.js",
                    "status": "added",
                    "additions": 1,
                    "deletions": 0,
                    "changes": 1,
                    "patch": "+generated",
                },
                {
                    "filename": "docs/large.md",
                    "status": "modified",
                    "additions": 100,
                    "deletions": 0,
                    "changes": 100,
                    "patch": "+0123456789abcdef",
                },
            ],
        }

    def pull_requests_for_commit(self, owner, repo, sha):
        if sha == "commit-with-pr":
            return [
                {
                    "number": 1,
                    "title": "Add CSV ticket export",
                    "body": "Adds export endpoint.",
                    "labels": [{"name": "enhancement"}],
                    "user": {"login": "juesteeb-wbs"},
                    "state": "closed",
                    "merged_at": "2026-07-22T10:05:00Z",
                    "merge_commit_sha": "merge-sha",
                    "html_url": "https://example.test/pull/1",
                }
            ]
        return []

    def check_runs_for_ref(self, owner, repo, ref):
        return [
            {
                "name": "tests",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://example.test/checks/1",
            }
        ]

    def tag_metadata(self, owner, repo, tag):
        return {"ref": "refs/tags/v1.0.0", "object": {"sha": "base-sha"}}


def test_collect_evidence_normalizes_github_data_and_warnings():
    request = ReleaseRequest(
        repository_owner="juesteeb-wbs",
        repository_name="ai-release-agent-demo-v2",
        base_ref="v1.0.0",
        target_ref="release/1.1.0",
        release_version="1.1.0",
    )
    collector = ReleaseEvidenceCollector(
        FakeGitHubClient(),
        EvidenceLimits(max_file_patch_chars=8, max_total_patch_chars=20),
    )

    evidence = collector.collect(request)

    assert evidence.resolved_refs.base_sha == "base-sha"
    assert evidence.resolved_refs.target_sha == "target-sha"
    assert [commit.sha for commit in evidence.commits] == ["commit-with-pr", "direct-commit"]
    assert evidence.pull_requests[0].labels == ["enhancement"]
    assert evidence.files[0].patch == "+[REDACT"
    assert evidence.files[0].omitted_reason == "file_patch_truncated"
    assert evidence.files[1].omitted_reason == "generated"
    assert evidence.check_runs[0].conclusion == "success"
    assert evidence.tag_metadata["ref"] == "refs/tags/v1.0.0"

    warning_codes = {warning.code for warning in evidence.warnings}
    assert "commit_without_pull_request" in warning_codes
    assert "secret_redacted" in warning_codes
    assert "file_patch_truncated" in warning_codes
    assert "generated_file_omitted" in warning_codes


def test_collect_evidence_omits_binary_files():
    client = FakeGitHubClient()
    original_compare = client.compare

    def compare_with_binary(owner, repo, base, head):
        data = original_compare(owner, repo, base, head)
        data["files"] = [
            {
                "filename": "docs/screenshot.png",
                "status": "added",
                "additions": 0,
                "deletions": 0,
                "changes": 0,
            }
        ]
        return data

    client.compare = compare_with_binary
    request = ReleaseRequest(
        repository_owner="juesteeb-wbs",
        repository_name="ai-release-agent-demo-v2",
        base_ref="v1.0.0",
        target_ref="release/1.1.0",
        release_version="1.1.0",
    )

    evidence = ReleaseEvidenceCollector(client).collect(request)

    assert evidence.files[0].omitted_reason == "binary"
    assert any(warning.code == "binary_file_omitted" for warning in evidence.warnings)


def test_collect_evidence_warns_when_check_runs_are_unavailable():
    class NoCheckRunsClient(FakeGitHubClient):
        def check_runs_for_ref(self, owner, repo, ref):
            raise GitHubClientError("403 Resource not accessible by personal access token")

    request = ReleaseRequest(
        repository_owner="juesteeb-wbs",
        repository_name="ai-release-agent-demo-v2",
        base_ref="v1.0.0",
        target_ref="release/1.1.0",
        release_version="1.1.0",
    )

    evidence = ReleaseEvidenceCollector(NoCheckRunsClient()).collect(request)

    assert evidence.check_runs == []
    assert any(warning.code == "check_runs_unavailable" for warning in evidence.warnings)
