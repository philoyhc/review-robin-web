from __future__ import annotations

from enum import Enum


class AssignmentMode(str, Enum):
    """The mechanism that wrote a given batch of Assignment rows.

    ``manual`` retired in 16A PR 5 alongside the manual-CSV upload
    path. ``rule_based`` is the only remaining writer — produced by
    the rule engine on POST /assignments/rule-based/generate. The
    enum is kept (rather than collapsing to a string column) for
    future expansion when 13C-style group-scoped instruments add
    another mode.
    """

    rule_based = "rule_based"
