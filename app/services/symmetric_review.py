"""Symmetric review: the Reviewees roster mirrors the Reviewers roster
(segment 20B, ``guide/segment_20B_symmetric_review.md``).

While ``ReviewSession.symmetric_review`` is on, the Reviewers roster is the
only one edited. Every service that writes reviewers calls
:func:`sync_reviewees_from_reviewers` before it commits, which brings the
Reviewees roster into step:

- each reviewer has one reviewee, linked by ``Reviewee.mirrors_reviewer_id``
  (so an address correction updates the same row: its id, assignments and
  responses are kept);
- the reviewee carries the reviewer's name, address, profile link, status,
  tags and directory match;
- a reviewee whose reviewer is gone is deleted, its assignments, responses
  and relationships with it (the cascade a reviewee delete takes);
- the reviewee tag labels and the "what they see of their own entry" list
  follow the reviewers'.

One function rather than a mirror inside each writer, so the eight writers
cannot drift apart. It is a no-op while the mode is off.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, SessionFieldLabel
from app.services import email_identity

#: The fields a mirrored reviewee takes from its reviewer: reviewee field
#: on the left, reviewer field on the right.
MIRRORED_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "name"),
    ("email_or_identifier", "email"),
    ("profile_link", "profile_link"),
    ("status", "status"),
    ("tag_1", "tag_1"),
    ("tag_2", "tag_2"),
    ("tag_3", "tag_3"),
    ("directory_object_id", "directory_object_id"),
    ("directory_mail", "directory_mail"),
    ("directory_upn", "directory_upn"),
)

_TAG_SLOTS = ("tag_1", "tag_2", "tag_3")

#: A reviewer's "what they see of their own entry" key as the reviewee's
#: list names it (``participant_info``): only the address is spelled
#: differently.
_SELF_FIELD_KEY = {"email": "email_or_identifier"}


def sync_reviewees_from_reviewers(db: Session, review_session: ReviewSession) -> None:
    """Bring the Reviewees roster into step with the Reviewers roster.

    A no-op unless symmetric review is on. Flushes; the caller commits.
    """
    if not review_session.symmetric_review:
        return
    db.flush()
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id).order_by(Reviewer.id)
        ).scalars()
    )
    reviewees = list(
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id).order_by(Reviewee.id)
        ).scalars()
    )
    by_link = {r.mirrors_reviewer_id: r for r in reviewees if r.mirrors_reviewer_id is not None}
    # An unlinked reviewee can only come from a copy made outside the
    # reconcile (a clone or a rehydrate of both rosters): adopt it for the
    # reviewer with its address, so its assignments survive, else drop it.
    unlinked = {
        email_identity.normalize_email(r.email_or_identifier): r
        for r in reviewees
        if r.mirrors_reviewer_id is None
    }
    deleted_any = False
    for reviewer in reviewers:
        reviewee = by_link.pop(reviewer.id, None)
        if reviewee is None:
            reviewee = unlinked.pop(email_identity.normalize_email(reviewer.email), None)
        if reviewee is None:
            reviewee = Reviewee(session_id=review_session.id)
            db.add(reviewee)
        reviewee.mirrors_reviewer_id = reviewer.id
        for reviewee_field, reviewer_field in MIRRORED_FIELDS:
            value = getattr(reviewer, reviewer_field)
            if getattr(reviewee, reviewee_field) != value:
                setattr(reviewee, reviewee_field, value)
    for gone in [*by_link.values(), *unlinked.values()]:
        db.delete(gone)
        deleted_any = True
    _mirror_labels(db, review_session)
    mirrored_self_fields = (
        [_SELF_FIELD_KEY.get(key, key) for key in review_session.reviewer_self_fields]
        if review_session.reviewer_self_fields is not None
        else None
    )
    if review_session.reviewee_self_fields != mirrored_self_fields:
        review_session.reviewee_self_fields = mirrored_self_fields
    db.flush()
    if deleted_any:
        # Group self-review membership is read off the roster (findings
        # B7), as ``roster_bulk.bulk_delete`` recomputes after a reviewee
        # delete.
        from app.services.assignments import recompute_self_review_classification

        recompute_self_review_classification(db, session_id=review_session.id)


def _mirror_labels(db: Session, review_session: ReviewSession) -> None:
    """The reviewee tag labels follow the reviewers', so a rule on
    ``Reviewee.tag_1`` means what ``Reviewer.tag_1`` means."""
    rows = list(
        db.execute(
            select(SessionFieldLabel).where(
                SessionFieldLabel.session_id == review_session.id,
                SessionFieldLabel.source_type.in_(("reviewer", "reviewee")),
                SessionFieldLabel.source_field.in_(_TAG_SLOTS),
            )
        ).scalars()
    )
    reviewer_labels = {r.source_field: r for r in rows if r.source_type == "reviewer"}
    reviewee_labels = {r.source_field: r for r in rows if r.source_type == "reviewee"}
    for slot in _TAG_SLOTS:
        source = reviewer_labels.get(slot)
        target = reviewee_labels.get(slot)
        if source is None:
            if target is not None:
                db.delete(target)
        elif target is None:
            db.add(SessionFieldLabel(
                session_id=review_session.id,
                source_type="reviewee",
                source_field=slot,
                label=source.label,
            ))
        elif target.label != source.label:
            target.label = source.label
