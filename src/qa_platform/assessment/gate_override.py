from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class GateOverride:
    override_id: str
    scan_id: str
    approved_by: str
    reason: str
    expires_at: str
    created_at: str = ""

    def is_valid(self) -> bool:
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return expiry > datetime.now(timezone.utc)
        except ValueError:
            return False


class OverrideManager:
    def __init__(self) -> None:
        self._overrides: dict[str, GateOverride] = {}

    def add(self, override: GateOverride) -> None:
        self._overrides[override.scan_id] = override

    def get_active(self, scan_id: str) -> GateOverride | None:
        override = self._overrides.get(scan_id)
        if override and override.is_valid():
            return override
        return None
