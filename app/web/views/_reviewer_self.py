"""What a participant is shown of their own roster entry, per side.

`guide/participant_info.md` Items 1, 3, 4 and 5. The reviewer's
functions (Item 1: the reviewer surface and its preview, ``/summary`` and
the pre-open "opens later" page; the Reviewers page's card and readout),
the reviewee's (Item 4: ``/results``; the Reviewees page's card and
readout) and the observer's (Item 5: ``/collation``; the Observers
page's), each a thin wrapper over ``_participant_self``'s one core.

The selections themselves, their defaults and their storage live in
``app.services.participant_info``; this module shapes them for the pages.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession
from app.services.participant_info import (
    REVIEWER_SELF_DEFAULT,
    REVIEWER_SELF_FIELD_KEYS,
    effective_reviewer_self_fields,
    effective_self_fields,
)

from ._participant_self import (
    OBSERVER_SPEC,
    REVIEWEE_SPEC,
    REVIEWER_SPEC,
    SelfFieldChip,
    SelfFieldValue,
    self_chips,
    self_kept,
    self_label,
    self_line,
    self_readout,
)
from ._setup import ColumnReadout

__all__ = [
    "REVIEWER_SELF_DEFAULT",
    "REVIEWER_SELF_FIELD_KEYS",
    "SelfFieldChip",
    "SelfFieldValue",
    "observer_self_card_context",
    "observer_self_line_for",
    "reviewee_self_card_context",
    "reviewee_self_line_for",
    "reviewer_self_card_context",
    "reviewer_self_chips",
    "reviewer_self_kept",
    "reviewer_self_label",
    "reviewer_self_line",
    "reviewer_self_line_for",
    "reviewer_self_readout",
]


# ── Reviewers (Items 1 and 3) ────────────────────────────────────────


def reviewer_self_label(review_session: ReviewSession, key: str) -> str:
    """The field's operator-facing name, as the roster index reads."""
    return self_label(REVIEWER_SPEC, review_session, key)


def reviewer_self_chips(
    readouts: Iterable[ColumnReadout], selected: Iterable[str]
) -> list[SelfFieldChip]:
    """One chip per populated column, in roster order.

    ``readouts`` is ``reviewer_column_state(...).readouts``: Name and
    Email always, Profile and each tag only while some row holds a value,
    each already under its operator-facing label.
    """
    return self_chips(REVIEWER_SPEC, readouts, selected)


def reviewer_self_kept(
    chips: Iterable[SelfFieldChip], selected: Iterable[str]
) -> list[str]:
    """Selected keys the card offers no chip for, in roster order."""
    return self_kept(REVIEWER_SPEC, chips, selected)


def reviewer_self_card_context(
    review_session: ReviewSession, readouts: Iterable[ColumnReadout]
) -> dict[str, object]:
    """The Reviewers page's three keys for this feature: the card's chips
    and kept keys, and the readout row's pills, from the stored selection
    or the default.

    One helper for both renders of the page — the GET and the failed CSV
    import's in-place re-render — so the second cannot ship an empty card
    and a readout of `none` by omitting a key.
    """
    selected = effective_reviewer_self_fields(review_session)
    chips = reviewer_self_chips(readouts, selected)
    return {
        "self_field_chips": chips,
        "self_field_kept": reviewer_self_kept(chips, selected),
        "self_field_readout": reviewer_self_readout(review_session, selected),
    }


def reviewer_self_readout(
    review_session: ReviewSession, selected: Iterable[str]
) -> list[str]:
    """The roster card's `Reviewers see:` pills, in roster order."""
    return self_readout(REVIEWER_SPEC, review_session, selected)


def reviewer_self_line(
    review_session: ReviewSession,
    reviewer: Reviewer,
    selected: Iterable[str],
) -> list[SelfFieldValue]:
    """The selected fields of this reviewer's own row, in roster order;
    a field empty on the row is skipped."""
    return self_line(REVIEWER_SPEC, review_session, reviewer, selected)


def reviewer_self_line_for(
    review_session: ReviewSession, reviewer: Reviewer
) -> list[SelfFieldValue]:
    """The reviewer's own line under the session's selection, stored or
    default: what the surface, ``/summary`` and the pre-open page show
    after the ``Reviewer`` pill (participant info Items 1 and 3)."""
    return reviewer_self_line(
        review_session, reviewer, effective_reviewer_self_fields(review_session)
    )


# ── Reviewees (Item 4) ───────────────────────────────────────────────


def reviewee_self_card_context(
    review_session: ReviewSession, readouts: Iterable[ColumnReadout]
) -> dict[str, object]:
    """The Reviewees page's card chips and kept keys and its `Reviewees
    see:` pills, as `reviewer_self_card_context` gives the Reviewers
    page's — under the same three keys, since each page has one card."""
    selected = effective_self_fields(review_session, "reviewee")
    chips = self_chips(REVIEWEE_SPEC, readouts, selected)
    return {
        "self_field_chips": chips,
        "self_field_kept": self_kept(REVIEWEE_SPEC, chips, selected),
        "self_field_readout": self_readout(REVIEWEE_SPEC, review_session, selected),
    }


def reviewee_self_line_for(
    review_session: ReviewSession, reviewee: Reviewee
) -> list[SelfFieldValue]:
    """The reviewee's own line on ``/results``, after the role pills,
    under the session's selection, stored or default."""
    return self_line(
        REVIEWEE_SPEC,
        review_session,
        reviewee,
        effective_self_fields(review_session, "reviewee"),
    )


# ── Observers (Item 5) ───────────────────────────────────────────────


def observer_self_card_context(
    review_session: ReviewSession, readouts: Iterable[ColumnReadout]
) -> dict[str, object]:
    """The Observers page's card chips and kept keys and its `Observers
    see:` pills, under the Reviewers page's three keys.

    The Observers index lists all three columns whatever their counts, so
    the card offers the tag only while some row holds one; Name and Email
    are always offered, as on the other pages.
    """
    offered = [r for r in readouts if r.slot != "tag-1" or r.count]
    selected = effective_self_fields(review_session, "observer")
    chips = self_chips(OBSERVER_SPEC, offered, selected)
    return {
        "self_field_chips": chips,
        "self_field_kept": self_kept(OBSERVER_SPEC, chips, selected),
        "self_field_readout": self_readout(OBSERVER_SPEC, review_session, selected),
    }


def observer_self_line_for(
    review_session: ReviewSession, observer: Observer
) -> list[SelfFieldValue]:
    """The observer's own line on ``/collation``, after the role pills,
    under the session's selection, stored or default."""
    return self_line(
        OBSERVER_SPEC,
        review_session,
        observer,
        effective_self_fields(review_session, "observer"),
    )
