"""``.chrome-link`` is styled wherever it is used (findings E7, 2026-10-05).

The class had a rule only under ``.chrome-user``, so the Owners cards'
per-row Remove — a ``<button class="chrome-link">`` — rendered as a
browser-default button, and the audit log's ``Older events →`` as an
unstyled link. ``spec/operator_button_audit.md`` records the reuse as
deliberate, so the class owes a rule that holds outside the chrome: a
link look for a button (no background, border or padding; the link
colour) and a disabled state.
"""

from __future__ import annotations

from ._base_css import css, rules


def _decls(selector: str) -> str:
    found = [body for sel, body in rules(css()) if sel == selector]
    assert found, f"no rule for {selector!r}"
    return " ".join(found)


def test_a_chrome_link_button_outside_the_chrome_draws_as_a_link() -> None:
    body = _decls("body.ui-v2 .chrome-link")
    for decl in (
        "background: none",
        "border: 0",
        "padding: 0",
        "color: var(--text-link)",
        "cursor: pointer",
    ):
        assert decl in body, decl


def test_an_in_content_anchor_keeps_its_resting_underline() -> None:
    """spec/visual_style_rrw.md "Links": links in page content keep the
    browser's resting underline, so the base rule must not remove it."""
    assert "text-decoration" not in _decls("body.ui-v2 .chrome-link")


def test_a_disabled_chrome_link_reads_as_disabled_like_btn_reset() -> None:
    body = _decls("body.ui-v2 .chrome-link:disabled")
    assert "opacity: 0.5" in body
    assert "cursor: not-allowed" in body
