"""Band 3's visibility grid: labels must not wear a control's classes.

Segment 19J Item 7 rung 1. The grid's first column and its two fixed
cells are rendered by ``b3_static_pill``; every other cell is a
``b3_mode_cycle`` chip the operator clicks to rotate the mode. Before
this rung the two macros emitted the *same* class string —
``pill pill-count tag-chip is-selected`` — so nothing in the resting
state told them apart, and because the static one carried ``tag-chip``
it also inherited ``cursor: pointer``, aiming the pill vocabulary's one
affordance at the cells that do nothing.

The assertions here read the **rendered elements** inside the Band 3
region rather than searching the page for a class name. A bare
``"tag-chip" in body`` check passes on every page in the app: the class
is defined in ``base.html``'s inline CSS, which ships with every
response (learned the hard way three times in 19J.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

#: The five cells ``b3_static_pill`` renders: three audience row
#: labels, plus the two grid cells whose mode is not the operator's to
#: choose (peer reviewers always see raw responses while the session is
#: ongoing; reviewees see nothing).
FIXED_LABELS = ["Reviewers", "Raw responses", "Reviewees", "—", "Observers"]


@dataclass
class Span:
    classes: list[str]
    attrs: dict[str, str]
    text: str = ""

    @property
    def is_control(self) -> bool:
        """Does this element offer a click, by class or by attribute?"""
        return (
            "tag-chip" in self.classes
            or self.attrs.get("role") == "button"
            or "onclick" in self.attrs
        )


class _SpanCollector(HTMLParser):
    """Collects every ``<span>`` with a ``class``, plus its text."""

    def __init__(self) -> None:
        super().__init__()
        self.spans: list[Span] = []
        self._open: list[Span] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "span":
            return
        d = {k: (v or "") for k, v in attrs}
        span = Span(classes=d.get("class", "").split(), attrs=d)
        self.spans.append(span)
        self._open.append(span)

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._open:
            self._open.pop()

    def handle_data(self, data: str) -> None:
        if self._open:
            self._open[-1].text += data


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _band3_spans(client: TestClient, db: Session, *, code: str) -> list[Span]:
    """Every ``<span class=...>`` inside the first Band 3 grid."""
    review_session = _make_session(client, db, code=code)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    start = body.index("<div data-new-model-band3")
    # The grid is the first table in the region; the hidden mode
    # inputs sit between the div and it.
    end = body.index("</table>", start)
    collector = _SpanCollector()
    collector.feed(body[start:end])
    return collector.spans


def test_fixed_cells_carry_no_control_classes(
    client: TestClient, db: Session
) -> None:
    """The five ``b3_static_pill`` cells are labels, and look like it."""
    spans = _band3_spans(client, db, code="19j7-1")
    fixed = [s for s in spans if s.attrs.get("title") == "Fixed"]

    assert [s.text.strip() for s in fixed] == FIXED_LABELS

    for span in fixed:
        assert span.classes == ["pill", "pill-count"], (
            f"{span.text.strip()!r} renders {span.classes}; a fixed cell "
            "must carry neither tag-chip (cursor: pointer) nor "
            "is-selected (the reserved accent shade)"
        )
        assert not span.is_control


def test_cycle_chips_are_still_controls(
    client: TestClient, db: Session
) -> None:
    """The mutation guard: rung 1 must not disarm the real chips.

    Without this, stripping ``tag-chip`` from *both* macros would pass
    the test above while removing the only affordance the grid has.
    """
    spans = _band3_spans(client, db, code="19j7-2")
    cycles = [
        s for s in spans if "data-new-model-vp-cycle-audience" in s.attrs
    ]

    # Reviewers × released, reviewees × released, observers × both.
    assert len(cycles) == 4

    for span in cycles:
        assert "tag-chip" in span.classes
        assert span.attrs.get("role") == "button"
        assert span.attrs.get("tabindex") == "0"


def test_no_label_in_the_grid_pretends_to_be_clickable(
    client: TestClient, db: Session
) -> None:
    """The invariant this rung establishes, stated once.

    Inside the Band 3 grid, an element that carries a control's classes
    must also carry a control's behaviour — and vice versa. This is what
    would catch the defect coming back through a different macro.
    """
    spans = _band3_spans(client, db, code="19j7-3")

    for span in spans:
        has_control_class = "tag-chip" in span.classes
        has_control_behaviour = (
            span.attrs.get("role") == "button" or "onclick" in span.attrs
        )
        assert has_control_class == has_control_behaviour, (
            f"{span.text.strip()!r} carries {span.classes} with "
            f"role={span.attrs.get('role')!r} — a pill either offers a "
            "click and says so, or does neither"
        )
