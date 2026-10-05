"""The pending Band 3 row's fill is a token the contrast audit sees
(findings Ec1, 2026-10-05).

It was a raw ``rgba(254, 243, 199, 0.5)`` with no dark override: in dark
mode light text sat on a pale wash, about 3:1 by arithmetic, and the
audit — which pairs tokens, not literals — could not see it. The fill is
now ``--row-pending-bg``, remapped for dark, and the rule states its
text colour so the audit's rule pass pairs the two.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ._base_css import css, rules

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from _harness_common import collect_contrast_pairs  # noqa: E402

SELECTOR = "[data-new-model-rf-row][data-row-pending=\"true\"] > td"


def test_the_pending_fill_is_a_token_not_a_literal() -> None:
    bodies = [b for sel, b in rules(css()) if sel.startswith(SELECTOR)]
    assert bodies, "the pending-row rule moved"
    body = " ".join(bodies)
    assert "background: var(--row-pending-bg)" in body
    assert "rgba(" not in body


def test_the_contrast_audit_pairs_it_with_its_text() -> None:
    html = (Path(__file__).resolve().parents[2] / "app/web/templates/base.html").read_text()
    assert ("--text-body", "--row-pending-bg") in collect_contrast_pairs(html)
