from collections.abc import Iterable
import json
import os
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import certifi

from release_agent.errors import GitHubClientError

try:
    import truststore
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    truststore = None


class GitHubClient:
    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com"):
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.ssl_context = _create_ssl_context()

    def resolve_commit_sha(self, owner: str, repo: str, ref: str) -> str:
        encoded_ref = quote(ref, safe="")
        commit = self.get_json(f"/repos/{owner}/{repo}/commits/{encoded_ref}")
        return commit["sha"]

    def compare(self, owner: str, repo: str, base: str, head: str) -> dict[str, Any]:
        encoded_base = quote(base, safe="")
        encoded_head = quote(head, safe="")
        return self.get_json(f"/repos/{owner}/{repo}/compare/{encoded_base}...{encoded_head}")

    def pull_requests_for_commit(self, owner: str, repo: str, sha: str) -> list[dict[str, Any]]:
        return self.get_json(f"/repos/{owner}/{repo}/commits/{sha}/pulls")

    def check_runs_for_ref(self, owner: str, repo: str, ref: str) -> list[dict[str, Any]]:
        data = self.get_json(f"/repos/{owner}/{repo}/commits/{ref}/check-runs")
        return data.get("check_runs", [])

    def tag_metadata(self, owner: str, repo: str, tag: str) -> dict[str, Any] | None:
        try:
            return self.get_json(f"/repos/{owner}/{repo}/git/ref/tags/{quote(tag, safe='')}")
        except GitHubClientError:
            return None

    def get_json(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        pages: list[Any] = []
        next_url: str | None = url

        while next_url:
            data, links = self._request_json(next_url)
            if isinstance(data, list):
                pages.extend(data)
            elif pages:
                pages.append(data)
            else:
                return data
            next_url = links.get("next")

        return pages

    def _request_json(self, url: str) -> tuple[Any, dict[str, str]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-release-agent-demo-evidence-collector",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=20, context=self.ssl_context) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload, _parse_link_header(response.headers.get("Link", ""))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GitHubClientError(f"GitHub API request failed: {exc.code} {body}") from exc
        except URLError as exc:
            raise GitHubClientError(f"GitHub API request failed: {exc.reason}") from exc


def _parse_link_header(header: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for part in _split_link_header(header):
        section = part.strip()
        if not section:
            continue
        url_part, *params = section.split(";")
        rel = None
        for param in params:
            name, _, value = param.strip().partition("=")
            if name == "rel":
                rel = value.strip('"')
        if rel:
            links[rel] = url_part.strip("<>")
    return links


def _split_link_header(header: str) -> Iterable[str]:
    return header.split(",") if header else ()


def _create_ssl_context() -> ssl.SSLContext:
    ca_bundle = os.getenv("GITHUB_CA_BUNDLE")
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    if truststore is not None:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context(cafile=certifi.where())
