from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import IntEnum, Enum
from typing import Any


# ---------------------------------------------------------------------------
# Value-object enums
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    """Finding severity with integer ordering (CRITICAL > HIGH > ...)."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Confidence(IntEnum):
    """Confidence level with integer ordering (CONFIRMED > LIKELY > UNCERTAIN)."""

    UNCERTAIN = 0
    LIKELY = 1
    CONFIRMED = 2


class FindingCategory(str, Enum):
    """Broad finding category."""

    CORRECTNESS = "correctness"
    SECURITY = "security"
    DESIGN = "design"
    CONSISTENCY = "consistency"
    HYGIENE = "hygiene"


class ValidationStatus(str, Enum):
    """Status assigned after validation pass."""

    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNCERTAIN = "uncertain"
    SUPPRESSED = "suppressed"
    UNVALIDATED = "unvalidated"


class Classification(str, Enum):
    """Whether the issue was introduced, modified, or pre-existing."""

    INTRODUCED = "introduced"
    MODIFIED = "modified"
    PRE_EXISTING = "pre_existing"
    UNCLASSIFIED = "unclassified"


class LifecycleState(str, Enum):
    """Current lifecycle state of a finding."""

    OPEN = "open"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


# ---------------------------------------------------------------------------
# Value-object dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Evidence:
    """Supporting evidence collected during analysis."""

    tool_calls: list[str] = field(default_factory=list)
    code_references: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorAttribution:
    """Git/GitHub author information attached to a finding."""

    name: str
    email: str
    github_username: str | None = None
    attribution_source: str = "unknown"


# ---------------------------------------------------------------------------
# Core entity
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """Central finding entity produced by the QA pipeline.

    Mutable by design so pipeline steps (enrichment, validation,
    deduplication, suppression) can update fields in place.
    """

    id: str = ""
    source: str = ""
    tier: int = 1
    category: FindingCategory = FindingCategory.CORRECTNESS
    severity: Severity = Severity.MEDIUM
    confidence: Confidence = Confidence.LIKELY
    classification: Classification = Classification.UNCLASSIFIED
    file: str = ""
    start_line: int = 1
    end_line: int = 1
    title: str = ""
    explanation: str = ""
    evidence: Evidence = field(default_factory=Evidence)
    recommendation: str = ""
    cwe: str | None = None
    author: AuthorAttribution | None = None
    code_under_review: str = ""
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED
    validation_reasoning: str = ""
    suppression_key: str = ""
    lifecycle_state: LifecycleState = LifecycleState.OPEN
    first_seen: str = ""
    last_seen: str = ""
    related_findings: list[str] = field(default_factory=list)
    root_cause_cluster: str | None = None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the finding to a plain dict suitable for JSON output.

        Enum values are converted via ``.value``; nested dataclasses are
        recursively converted.
        """

        def _convert(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                return {k: _convert(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_convert(item) for item in value]
            return value

        result: dict[str, Any] = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if val is None:
                result[f.name] = None
            elif hasattr(val, "__dataclass_fields__"):
                # Nested dataclass (Evidence, AuthorAttribution)
                nested: dict[str, Any] = {}
                for nf in fields(val):
                    nested[nf.name] = _convert(getattr(val, nf.name))
                result[f.name] = nested
            else:
                result[f.name] = _convert(val)
        return result
