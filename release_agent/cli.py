import argparse
import json
from pathlib import Path
import sys

from release_agent.analyzer import DeterministicReleaseAnalyzer
from release_agent.artifact_writer import write_analysis_outputs
from release_agent.errors import ReleaseAgentError
from release_agent.evidence import ReleaseEvidenceCollector
from release_agent.github_client import GitHubClient
from release_agent.models import ReleaseRequest


def main() -> None:
    parser = argparse.ArgumentParser(prog="release-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect-evidence")
    collect.add_argument("--owner", required=True)
    collect.add_argument("--repo", required=True)
    collect.add_argument("--base-ref", required=True)
    collect.add_argument("--target-ref", required=True)
    collect.add_argument("--release-version", required=True)
    collect.add_argument("--output", required=True)

    analyze = subparsers.add_parser("analyze-evidence")
    analyze.add_argument("--evidence-file", required=True)
    analyze.add_argument("--output-dir", required=True)

    args = parser.parse_args()
    if args.command == "collect-evidence":
        request = ReleaseRequest(
            repository_owner=args.owner,
            repository_name=args.repo,
            base_ref=args.base_ref,
            target_ref=args.target_ref,
            release_version=args.release_version,
        )
        collector = ReleaseEvidenceCollector(GitHubClient())
        try:
            evidence = collector.collect(request)
        except ReleaseAgentError as exc:
            print(f"Evidence collection failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(evidence.to_dict(), indent=2), encoding="utf-8")
        print(
            "Collected evidence for "
            f"{args.owner}/{args.repo} {args.base_ref}..{args.target_ref} "
            f"at target {evidence.resolved_refs.target_sha}"
        )
    elif args.command == "analyze-evidence":
        evidence_path = Path(args.evidence_file)
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        result = DeterministicReleaseAnalyzer().analyze(
            evidence,
            source_evidence_file=str(evidence_path),
        )
        output_dir = Path(args.output_dir)
        write_analysis_outputs(result, output_dir)
        print(
            "Generated analysis artifacts for "
            f"{result.repository} {result.release_range} in {output_dir}"
        )


if __name__ == "__main__":
    main()
