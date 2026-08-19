import json
from pathlib import Path

from release_agent.analysis_models import AnalysisResult


def write_analysis_outputs(result: AnalysisResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        json.dumps(result.to_dict(), indent=2),
        encoding="utf-8",
    )
    (output_dir / "customer-release-notes.md").write_text(
        result.artifacts.customer_release_notes,
        encoding="utf-8",
    )
    (output_dir / "technical-changelog.md").write_text(
        result.artifacts.technical_changelog,
        encoding="utf-8",
    )
    (output_dir / "deployment-and-rollback.md").write_text(
        result.artifacts.deployment_and_rollback_guidance,
        encoding="utf-8",
    )
    (output_dir / "review-preview.md").write_text(
        result.review_markdown,
        encoding="utf-8",
    )
