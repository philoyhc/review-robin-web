"""Every ``var(--token)`` in ``base.html``'s stylesheet names a declared
token (findings Ec2, 2026-10-05).

The missing-required list's ``<li>`` indent read ``var(--space-5)``, a
step the spacing scale skips (4 / 8 / 12 / 16 / 24 / 32;
``spec/color_tokens.md``). An undeclared custom property with no
fallback makes the declaration invalid at computed-value time, so the
padding fell to 0 and nothing said so. A ``var()`` carrying its own
fallback (``var(--n, 4)``) is exempt: those tokens are set per element,
from markup or script, and the fallback is the default.
"""

from __future__ import annotations

import re

from ._base_css import css


def test_every_token_without_a_fallback_is_declared() -> None:
    sheet = css()
    declared = set(re.findall(r"(--[\w-]+)\s*:", sheet))
    bare = set(re.findall(r"var\(\s*(--[\w-]+)\s*\)", sheet))
    assert bare, "the var() scan found nothing; the parser moved"
    assert sorted(bare - declared) == []


def test_the_missing_list_indent_is_on_the_scale() -> None:
    sheet = css()
    rule = re.search(r"\.rs-missing-list li \{([^}]*)\}", sheet)
    assert rule, "the missing-list item rule moved"
    assert "padding-left: var(--space-6)" in rule.group(1)
