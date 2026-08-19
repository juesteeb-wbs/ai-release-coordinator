import pytest

from release_agent.errors import ReleaseRequestError
from release_agent.models import ReleaseRequest


def test_release_request_accepts_preview_mode_with_publishing_disabled():
    request = ReleaseRequest.from_mapping(
        {
            "repository_owner": "juesteeb-wbs",
            "repository_name": "ai-release-agent-demo-v2",
            "base_ref": "v1.0.0",
            "target_ref": "release/1.1.0",
            "release_version": "1.1.0",
            "release_mode": "preview",
            "publish_enabled": False,
        }
    )

    assert request.repository_name == "ai-release-agent-demo-v2"


def test_release_request_rejects_publish_enabled():
    with pytest.raises(ReleaseRequestError, match="publish_enabled"):
        ReleaseRequest.from_mapping(
            {
                "repository_owner": "juesteeb-wbs",
                "repository_name": "ai-release-agent-demo-v2",
                "base_ref": "v1.0.0",
                "target_ref": "release/1.1.0",
                "release_version": "1.1.0",
                "publish_enabled": True,
            }
        )


def test_release_request_rejects_unsupported_release_mode():
    with pytest.raises(ReleaseRequestError, match="release_mode"):
        ReleaseRequest.from_mapping(
            {
                "repository_owner": "juesteeb-wbs",
                "repository_name": "ai-release-agent-demo-v2",
                "base_ref": "v1.0.0",
                "target_ref": "release/1.1.0",
                "release_version": "1.1.0",
                "release_mode": "publish",
            }
        )


def test_release_request_rejects_missing_required_fields():
    with pytest.raises(ReleaseRequestError, match="repository_owner"):
        ReleaseRequest.from_mapping(
            {
                "repository_owner": "",
                "repository_name": "ai-release-agent-demo-v2",
                "base_ref": "v1.0.0",
                "target_ref": "release/1.1.0",
                "release_version": "1.1.0",
            }
        )
