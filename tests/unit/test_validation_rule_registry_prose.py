"""Every Validate ``why`` line is for operators (findings 2026-10-07 B7).

``spec/validate_page.md``: write the rationale in operator-readable prose,
naming the operator surface, never an internal column, route or service
path. Three lines named the ``include`` flag, ``rule_set_id`` with a spec
path, and the reviewee results route.
"""

from __future__ import annotations

import re

from app.services.validation import REGISTERED_RULES

#: What the three named: a code literal, a route, a spec path, a column.
INTERNALS = re.compile(
    r"``|/me/|/operator/|spec/|\.py\b|rule_set_id|\bNULL\b|\binclude`` flag"
)


def test_no_why_line_names_an_internal() -> None:
    offenders = {
        rule.key: INTERNALS.findall(rule.why)
        for rule in REGISTERED_RULES
        if INTERNALS.search(rule.why)
    }
    assert not offenders, offenders
