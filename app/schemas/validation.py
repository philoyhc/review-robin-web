from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ValidationIssue(BaseModel):
    severity: Severity
    source: str
    row_number: int | None = None
    field: str | None = None
    message: str
    detail: dict[str, Any] | None = None

    @property
    def is_blocking(self) -> bool:
        return self.severity is Severity.error
