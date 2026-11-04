"""A roster's unmatched addresses checked against the directory again, on
demand (segment 20I Item 1): the Upload card's "Recheck N unmatched".

A row is *unmatched* when it is active, has an address and has no
directory account (`directory_object_id`), whatever import or form added
it. The recheck looks those addresses up on the operator's token (the
answers the card's countdown already fetched are read, not asked again,
`directory_lookups.known_for`), then, under the session lock, binds each
row the directory now finds, as an upload binds it (`directory_accounts`).
Not found, ambiguous and not checked stay unbound. A row whose account
another row of the roster already holds stays unbound too (20H Item 1).

An expired sign-in (`directory_accounts.sign_in_stop`) saves nothing, as
an upload's does (20G); the route asks to renew.

Each roster's recheck is open while its other writes are: Reviewers and
Reviewees while the session is editable (draft or validated; author,
2026-11-04, findings M1), Observers until it is archived. A recheck that
binds a row sends a validated session back to draft, as any roster write
does (`spec/lifecycle.md` §2.3). One audit event per
recheck, `<roster>.directory_rechecked`, whose counts the card's
directory line shows (`app.web.views.last_directory_check`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.services import assignments, audit, directory_accounts, symmetric_review
from app.services import session_lifecycle as lifecycle
from app.services.session_guard import SessionStateConflict

#: Per roster: the model, its address attribute, and its noun.
ROSTERS: dict[str, tuple[Any, str, str]] = {
    "reviewers": (Reviewer, "email", "reviewer"),
    "reviewees": (Reviewee, "email_or_identifier", "reviewee"),
    "observers": (Observer, "email", "observer"),
}

#: The audit event a recheck writes, per roster.
EVENTS = {kind: f"{kind}.directory_rechecked" for kind in ROSTERS}


@dataclass(frozen=True)
class Recheck:
    """What a recheck came to. ``stopped`` is `sign_in_stop`'s answer:
    set, nothing was saved. ``counts`` is per row: bound by mail or by
    sign-in name, not found, ambiguous, not checked, and ``held`` (found,
    but on an account another row holds)."""

    counts: dict[str, int]
    stopped: str | None = None
    reason: str | None = None


def unmatched_rows(db: Session, *, session_id: int, kind: str) -> list[Any]:
    """The ``kind`` roster's active rows with an address and no account,
    in row order."""
    model, attr, _noun = ROSTERS[kind]
    rows = db.execute(
        select(model)
        .where(
            model.session_id == session_id,
            model.status == "active",
            model.directory_object_id.is_(None),
        )
        .order_by(model.id)
    ).scalars()
    return [row for row in rows if directory_accounts.key(getattr(row, attr)) is not None]


def unmatched_addresses(db: Session, *, session_id: int, kind: str) -> list[str]:
    """The unmatched rows' addresses as written: what the recheck asks."""
    _model, attr, _noun = ROSTERS[kind]
    return [getattr(row, attr) for row in unmatched_rows(db, session_id=session_id, kind=kind)]


_ARCHIVED = "Session is archived; nothing can be rechecked."
_NOT_EDITABLE = "Session is {status}; revert to draft to edit"


def _refuse(review_session: ReviewSession, kind: str) -> None:
    """Refuse a session this roster cannot be written in (archived; for
    Reviewers and Reviewees, anything but draft or validated), and the
    Reviewees recheck under symmetric review (the Reviewers one binds the
    mirror)."""
    if lifecycle.is_archived(review_session):
        raise SessionStateConflict(_ARCHIVED, code="archived")
    if kind != "observers" and not lifecycle.is_editable(review_session):
        raise SessionStateConflict(
            _NOT_EDITABLE.format(status=review_session.status), code="not_editable"
        )
    if kind == "reviewees":
        symmetric_review.refuse_reviewee_write(review_session)


def _lock(db: Session, review_session: ReviewSession, kind: str) -> ReviewSession:
    """Lock and re-read the session under this roster's own gate: the
    Observers roster's ``require_not_archived``, or the setup services'
    ``require_editable``."""
    if kind == "observers":
        return lifecycle.require_not_archived(db, review_session, message=_ARCHIVED)
    return lifecycle.require_editable(db, review_session)


def _tally(status: str | None) -> str:
    if status == "OK":
        return "directory_by_mail"
    if status in ("USE_PRIMARY", "FOUND_NO_PRIMARY"):
        return "directory_by_upn"
    if status == "NOT_FOUND":
        return "directory_not_found"
    if status == "AMBIGUOUS":
        return "directory_ambiguous"
    return "directory_not_checked"


def recheck(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    kind: str,
    directory: Any,
    known: Mapping[str, Any] | None = None,
    correlation_id: str | None = None,
) -> Recheck:
    """Check the ``kind`` roster's unmatched rows again and bind those
    the directory now finds. Looks up before taking the lock, so the
    session is not held across the directory's answers; the rows are
    read again under it. Flushes and audits; the caller commits."""
    model, attr, noun = ROSTERS[kind]
    # Refused before the lookups, so a doomed recheck does not wait out
    # the budget; decided again under the lock below.
    _refuse(review_session, kind)
    addresses = unmatched_addresses(db, session_id=review_session.id, kind=kind)
    if not addresses:
        # Nothing to check (a second tab, a stale page): no event, so the
        # card's line still reports the last check that did something.
        return Recheck(counts={})
    checked = directory is not None
    outcomes = directory_accounts.resolve(directory, addresses, known=known)
    stopped = directory_accounts.sign_in_stop(outcomes, addresses, checked=checked)
    if stopped:
        return Recheck(counts={}, stopped=stopped)

    locked = _lock(db, review_session, kind)
    _refuse(locked, kind)
    counts = dict.fromkeys(
        (
            "directory_by_mail",
            "directory_by_upn",
            "directory_not_found",
            "directory_ambiguous",
            "directory_not_checked",
            "directory_held",
        ),
        0,
    )
    for row in unmatched_rows(db, session_id=locked.id, kind=kind):
        k = directory_accounts.key(getattr(row, attr))
        outcome = outcomes.get(k) if (checked and k is not None) else None
        account = directory_accounts.account_of(outcome)
        if account is None:
            counts[_tally(outcome.status if outcome is not None else None)] += 1
            continue
        if directory_accounts.account_holder(
            db, model, session_id=locked.id, account=account, exclude_id=row.id
        ):
            counts["directory_held"] += 1
            continue
        for name, value in directory_accounts.columns(account).items():
            setattr(row, name, value)
        db.flush()
        counts[_tally(outcome.status)] += 1
    bound = counts["directory_by_mail"] + counts["directory_by_upn"]
    mirrored = None
    if kind == "reviewers" and locked.symmetric_review:
        # The mirror takes the new accounts, then recomputes self-review;
        # it also repairs a drifted mirror, binding or not.
        mirrored = symmetric_review.sync_reviewees_from_reviewers(db, locked)
    elif bound and kind in ("reviewers", "reviewees"):
        # A bound account can make a reviewer and a reviewee one person,
        # so an assignment between them a self-review (Codex, #3558).
        assignments.recompute_self_review_classification(db, session_id=locked.id)
    if bound or mirrored:
        # Validate reads the bound accounts (`*.duplicate_account`) and the
        # Reviewees roster, and a binding can move self-review inclusion
        # (findings M1).
        lifecycle.invalidate_if_validated(
            db,
            review_session=locked,
            user=user,
            reason=f"{kind}_rechecked",
            correlation_id=correlation_id,
        )

    reason = directory_accounts.unchecked_reason(outcomes, addresses, checked=checked)
    audit.write_event(
        db,
        event_type=EVENTS[kind],
        summary=f"Rechecked {len(addresses)} unmatched {noun} address(es); {bound} matched",
        actor_user_id=user.id,
        session=locked,
        payload=audit.counts(**counts),
        context={"directory_unchecked": reason} if reason else None,
        correlation_id=correlation_id,
    )
    db.flush()
    return Recheck(counts=counts, reason=reason)
