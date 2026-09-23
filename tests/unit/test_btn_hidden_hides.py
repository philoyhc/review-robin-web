"""A ``hidden`` ``.btn`` is not displayed (19S Item 10 rung A).

``hidden`` is a UA ``display: none``, and any author ``display`` beats
it, so ``base.html`` restores it for buttons with a ``.btn[hidden]``
rule. That rule was (0,2,1) and ``body.ui-v2 button.btn``'s
``display: inline-block`` is (0,2,2), so on every ``ui-v2`` page a
``hidden`` button stayed visible — found in Chromium with JavaScript
off, where Session Home's Owners card must ship its staging buttons
``hidden``.

The suite has no layout engine, so this checks the cascade itself: for
every rule in the inline stylesheet that sets ``display`` on a ``.btn``,
some ``[hidden]`` rule hiding that element outranks it, or ties and
comes later.
"""

from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "app/web/templates/base.html"

RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
DISPLAY = re.compile(r"(?:^|;)\s*display\s*:\s*([^;]+)")


def _stylesheet() -> str:
    html = BASE.read_text()
    start = html.index("<style")
    return html[html.index(">", start) + 1 : html.index("</style>", start)]


def _rules() -> list[tuple[int, str, str]]:
    css = re.sub(r"/\*.*?\*/", "", _stylesheet(), flags=re.S)
    found = []
    for order, match in enumerate(RULE.finditer(css)):
        display = DISPLAY.search(match.group(2))
        if display is None:
            continue
        for selector in match.group(1).split(","):
            found.append((order, " ".join(selector.split()), display.group(1).strip()))
    return found


def _specificity(selector: str) -> tuple[int, int, int]:
    ids = len(re.findall(r"#[\w-]+", selector))
    classes = len(re.findall(r"\.[\w-]+|\[[^\]]*\]|(?<!:):(?!:)[\w-]+", selector))
    bare = re.sub(r"#[\w-]+|\.[\w-]+|\[[^\]]*\]|::?[\w-]+(?:\([^)]*\))?", " ", selector)
    elements = len(re.findall(r"(?:^|[\s>+~])([a-zA-Z][\w-]*)", bare))
    return ids, classes, elements


def _split(selector: str) -> tuple[str, str, str]:
    """``(ancestors, subject element, subject)`` of a selector."""
    parts = re.split(r"\s*[\s>+~]\s*", selector)
    subject = parts[-1]
    return " ".join(parts[:-1]), re.match(r"[a-zA-Z]*", subject).group(0), subject


def _is_btn(selector: str) -> bool:
    return re.search(r"\.btn(?![\w-])", _split(selector)[2]) is not None


def _covers(hiding: str, shown: str) -> bool:
    """Whether every element ``shown`` matches, ``hiding`` also matches
    once it carries ``hidden`` — same or no ancestors, same or no
    element name."""
    h_ancestors, h_element, _ = _split(hiding)
    s_ancestors, s_element, _ = _split(shown)
    return h_ancestors in ("", s_ancestors) and h_element in ("", s_element)


def test_every_btn_display_rule_is_outranked_by_a_hidden_rule() -> None:
    rules = [rule for rule in _rules() if _is_btn(rule[1])]
    shown = [rule for rule in rules if rule[2] != "none" and "[hidden]" not in rule[1]]
    hiding = [rule for rule in rules if rule[2] == "none" and "[hidden]" in rule[1]]

    assert shown, "expected base.html to set display on .btn"
    assert hiding, "expected a .btn[hidden] { display: none } rule"
    for order, selector, value in shown:
        beaten = any(
            _covers(h_selector, selector)
            and (_specificity(h_selector), h_order) > (_specificity(selector), order)
            for h_order, h_selector, _ in hiding
        )
        assert beaten, (
            f"`{selector} {{ display: {value} }}` outranks every "
            "`.btn[hidden]` rule, so a hidden button of that shape shows"
        )


def test_the_specificity_helper_reads_the_case_that_broke() -> None:
    assert _specificity("body.ui-v2 button.btn") == (0, 2, 2)
    assert _specificity(".btn[hidden]") == (0, 2, 0)
    assert _specificity("button.btn[hidden]") == (0, 2, 1)
    assert _specificity("body.ui-v2 button.btn[hidden]") == (0, 3, 2)
