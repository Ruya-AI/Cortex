from __future__ import annotations

from pydantic import BaseModel, Field


class IgnoreConfig(BaseModel):
    max_file_size_kb: int = 10240
    extra_binary_extensions: list[str] = []


class GeneratedCodeConfig(BaseModel):
    paths: list[str] = []
    markers: list[str] = ["@generated", "AUTO-GENERATED", "DO NOT EDIT"]
    behavior: str = "skip"


class ReviewConfig(BaseModel):
    pr_finding_limit: int = 15
    severity_threshold: str = "low"
    ensemble_passes: int = 1
    ensemble_threshold: float = 0.5
    positive_feedback: bool = True
    cross_file_correlation: bool = True


class ModelConfig(BaseModel):
    code_review: str = "claude-sonnet-4-20250514"
    security_review: str = "claude-sonnet-4-20250514"
    architecture: str = "claude-sonnet-4-20250514"
    validator: str = "claude-opus-4-20250514"


class SecurityConfig(BaseModel):
    data_classification: str = "internal"
    exposure_surface: str = "internal-only"
    compliance_frameworks: list[str] = []
    high_risk_paths: list[str] = []


class PrivacyConfig(BaseModel):
    ai_review_mode: str = "cloud"
    ai_exclude_paths: list[str] = []
    approved_providers: list[str] = ["anthropic"]
    audit_log: bool = True
    code_retention_days: int = 0


class KnowledgeBaseConfig(BaseModel):
    conventions_path: str | None = None
    security_policies_path: str | None = None
    architecture_path: str | None = None


class GateThreshold(BaseModel):
    max_critical: int = 0
    max_high: int = 0
    max_medium: int | None = None
    max_low: int | None = None
    required_confidence: str = "high"


class QualityGateConfig(BaseModel):
    current_mode: str = "shadow"
    thresholds: GateThreshold = Field(default_factory=GateThreshold)


class SuppressionEntry(BaseModel):
    pattern: str
    file_scope: str | None = None
    reason: str = ""
    approved_by: str | None = None
    expires: str | None = None


class SuppressionConfig(BaseModel):
    default_expiry_days: int = 90
    entries: list[SuppressionEntry] = []


class CostConfig(BaseModel):
    max_per_pr: float = 1.0
    max_nightly: float = 10.0
    alert_threshold_monthly: float = 500.0


class ReportingConfig(BaseModel):
    author_attribution: bool = True
    default_author_name: str = "Unknown"
    default_author_email: str = ""


class LinearConfig(BaseModel):
    api_key: str | None = None
    team_id: str | None = None
    max_issues_per_scan: int = 20
    min_severity: str = "medium"


class IntegrationsConfig(BaseModel):
    linear: LinearConfig = Field(default_factory=LinearConfig)


class QAConfig(BaseModel):
    version: str = "2.0"
    ignore: IgnoreConfig = Field(default_factory=IgnoreConfig)
    generated_code: GeneratedCodeConfig = Field(default_factory=GeneratedCodeConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)
    quality_gates: QualityGateConfig = Field(default_factory=QualityGateConfig)
    suppressions: SuppressionConfig = Field(default_factory=SuppressionConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    integrations: IntegrationsConfig = Field(default_factory=IntegrationsConfig)
