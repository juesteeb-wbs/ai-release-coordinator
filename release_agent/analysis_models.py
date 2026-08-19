from dataclasses import asdict, dataclass, field
from typing import Any, Literal


ChangeCategory = Literal[
    "feature",
    "fix",
    "breaking_change",
    "security",
    "internal",
    "documentation",
    "dependency",
    "unknown",
]

CustomerImpact = Literal["none", "low", "medium", "high"]
ValidationStatus = Literal[
    "verified",
    "partially_verified",
    "unsupported",
    "conflicting_evidence",
    "needs_human_review",
]


@dataclass(frozen=True)
class EvidenceReference:
    type: str
    reference: str


@dataclass(frozen=True)
class ChangeRecord:
    change_id: str
    title: str
    summary: str
    categories: list[ChangeCategory]
    customer_impact: CustomerImpact
    migration_required: bool
    documentation_required: bool
    regression_testing_required: bool
    approval_blocker: bool
    classification_confidence: float
    evidence: list[EvidenceReference]
    warnings: list[str] = field(default_factory=list)
    source_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    statement: str
    artifact_targets: list[str]
    change_ids: list[str]
    evidence: list[EvidenceReference]
    confidence: float
    validation_status: ValidationStatus


@dataclass(frozen=True)
class RegressionTestSuggestion:
    test_id: str
    title: str
    change_references: list[str]
    priority: str
    preconditions: list[str]
    steps: list[str]
    expected_result: str
    automation_candidate: bool


@dataclass(frozen=True)
class RiskFactor:
    name: str
    score: float
    weight: float
    explanation: str


@dataclass(frozen=True)
class RiskAssessment:
    score: float
    level: str
    factors: list[RiskFactor]
    explanation: str


@dataclass(frozen=True)
class QACheck:
    status: str
    title: str
    change_references: list[str]


@dataclass(frozen=True)
class GeneratedArtifacts:
    customer_release_notes: str
    technical_changelog: str
    suggested_regression_tests: list[RegressionTestSuggestion]
    risk_and_impact_assessment: RiskAssessment
    qa_checklist: list[QACheck]
    deployment_and_rollback_guidance: str
    missing_documentation_warnings: list[str]


@dataclass(frozen=True)
class AnalysisResult:
    source_evidence_file: str
    repository: str
    release_range: str
    base_sha: str
    target_sha: str
    changes: list[ChangeRecord]
    claims: list[ClaimRecord]
    artifacts: GeneratedArtifacts
    warnings: list[str]
    review_markdown: str
    executive_summary: str
    blocker_summary: str
    warning_summary: str
    artifact_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
