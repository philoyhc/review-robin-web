"""Every disabled ``.btn`` renders at one opacity (post_assessment_1oct E6).

``spec/ui_elements.md`` §6: one rule covers all four disabled forms —
``.btn:disabled``, ``button.btn:disabled``, ``a.btn.disabled`` and
``.btn[aria-disabled="true"]`` — at ``opacity: 0.5``, so a role's
disabled look moves in one place. A second rule,
``body.ui-v2 a.btn[aria-disabled="true"]``, set 0.55 and won on
specificity (0,3,2 against 0,3,1), so an aria-disabled anchor rendered
fainter than a disabled ``<button>`` beside it. This holds every rule
that styles a disabled ``.btn`` to the one value.
"""

from __future__ import annotations

import re

from ._base_css import css, rules

# ``.btn`` as a class of its own — not ``.btn-icon`` / ``.btn-reset``,
# which are separate controls with their own disabled look.
_BTN = re.compile(r"\.btn(?![-\w])")
_DISABLED = re.compile(r':disabled|\.disabled\b|\[aria-disabled="true"\]')
_OPACITY = re.compile(r"(?<![-\w])opacity\s*:\s*([^;]+)")


def _disabled_btn_opacities() -> list[tuple[str, str]]:
    found = []
    for selector, body in rules(css()):
        for one in selector.split(","):
            one = one.strip()
            if _BTN.search(one) and _DISABLED.search(one):
                for value in _OPACITY.findall(body):
                    found.append((one, value.strip()))
    return found


def test_every_disabled_btn_rule_uses_the_one_opacity() -> None:
    found = _disabled_btn_opacities()
    # The premise: the unified rule is still there to be checked.
    assert ('body.ui-v2 .btn[aria-disabled="true"]', "0.5") in found
    assert [pair for pair in found if pair[1] != "0.5"] == []
