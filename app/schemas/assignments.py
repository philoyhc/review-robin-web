from __future__ import annotations

from enum import Enum


class AssignmentMode(str, Enum):
    full_matrix = "full_matrix"
    manual = "manual"
    rule_based = "rule_based"
