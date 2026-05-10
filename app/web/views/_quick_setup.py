"""Quick Setup card view-shape adapter (Segment 11H scaffold +
Segment 11J wiring) — the bulk-populate card on Session Home and
the new-session preview variant.

Slice 7 of the §12.B ladder (``guide/major_refactor.md``).

Owns the ``QuickSetupSlot`` / ``QuickSetupContext`` dataclasses,
the per-slot error-message renderer, and the two context builders:

- ``build_quick_setup_context(...)`` — Session Home variant.
  Reads the operator's lock-toggle cookie + the session lifecycle
  to decide ``is_available`` / ``is_locked`` / ``show_lock_toggle``.
- ``build_new_session_quick_setup_context(...)`` — new-session
  page variant. Card always unlocked, lock toggle suppressed.

15D PR 7a retired the legacy "Assignments (manual CSV or RuleSet
pick)" slot. Generation is now an explicit operator action on the
Operations Assignments page (15D PR 6a) — not a Quick Setup
side-effect. PR 7c re-introduces a slot 3 carrying Relationships.

Source range in pre-PR-7 ``_legacy.py``: lines 398-863.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import csv_imports
from app.services import relationships as relationships_service
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle


@dataclass(frozen=True)
class QuickSetupSlot:
    """One slot inside the Quick Setup card on Session Home.

    Post-15D PR 7a every slot is a plain CSV file upload. The legacy
    ``rule_or_csv`` mode (RuleSet dropdown + manual-CSV alternative)
    retired with the assignments-slot retirement; PR 7c re-introduces
    a ``relationships`` slot in the same file-upload mode.
    """

    key: str
    """Stable slot identifier — ``reviewers`` / ``reviewees`` /
    ``settings`` (PR 7c re-adds ``relationships``). Used as the
    DOM-id suffix (``#quick-setup-{key}``) so URL fragments scroll
    directly to a slot, and as the ``data-wire-target`` value so
    11J's wiring can locate the slot without a CSS-selector
    contract."""

    label: str
    """Human-readable slot label, used in the H3 heading."""

    count: int
    """Current population — count of reviewers / reviewees.
    ``0`` for the configuration-import slot."""

    mode: str
    """``"file_upload"`` for every slot post-15D PR 7a."""

    is_wired: bool
    """``True`` once 11J / 12A / 15D wires the slot. While ``False``
    the slot's controls render ``disabled`` and a ``coming_in``
    tooltip surfaces the wiring PR's name."""

    wire_url: str | None
    """POST URL once ``is_wired=True``. ``None`` while inert."""

    coming_in: str | None
    """``"Wired in Segment 11J PR A"``-style tooltip while
    ``is_wired=False``. ``None`` once wired."""

    error_message: str | None = None
    """Populated when the operator's last submit for this slot was
    rejected (parse / validation failure, or a lifecycle rejection
    on ``ready``). Rendered as a ``banner-error`` inside the slot.
    The cancel link in the banner returns the operator to the slot
    fragment with a clean URL."""

    cancel_url: str | None = None
    """Clean Home URL with this slot's fragment anchor. Used as the
    Cancel target for the error banner. Stable across renders."""


@dataclass(frozen=True)
class QuickSetupContext:
    """Page-shape adapter output for the Quick Setup card.

    ``slots`` renders top-to-bottom in the order given; the card
    iterates and the ``quick_setup_slot`` macro renders each one.

    Two status signals — ``is_locked`` (visual greying) and
    ``show_lock_toggle`` (whether the operator can unlock) —
    together capture the card's availability:

    - **Available** (``draft`` AND no persisted responses):
      ``show_lock_toggle=True``. ``is_locked`` is ``True`` by
      default on every fresh page load; the cookie-driven
      ``is_unlocked`` flips it off. The operator must explicitly
      Unlock before any submit.
    - **Unavailable** (``validated`` / ``ready`` / ``closed``, or
      any state with persisted responses): ``show_lock_toggle=False``
      and ``is_locked=True`` permanently. The body greys; the
      operator can't unlock. Defense-in-depth route gates
      (``_require_editable`` + ``_require_response_loss_ack``)
      stay in place but never fire from this surface because the
      submit forms aren't reachable when the body's locked.

    ``is_disabled`` mirrors ``not is_available`` for templates
    that want a single boolean to drive label-only signals; it's
    not a separate visual lock primitive.

    ``title`` overrides the H2 text. Session Home uses the default
    ``"Quick Setup"``; the new-session preview variant uses
    ``"Quick setup (optional)"`` to convey that the card surfaces
    early as a hint about post-creation setup paths.

    ``show_lock_toggle`` gates the Lock / Unlock footer button.
    Session Home renders it only while the card is available
    (``draft`` AND no responses); the new-session preview variant
    also suppresses it (no session row → nothing to lock).
    """

    slots: list[QuickSetupSlot]
    is_disabled: bool
    is_locked: bool
    description: str
    title: str = "Quick Setup"
    show_lock_toggle: bool = True
    show_confirm_replace: bool = True
    """Gate the card-level "This will replace any existing reviewers,
    reviewees, assignments or settings, according to what is uploaded."
    checkbox at the top of the body. Suppressed on the new-session
    Quick Setup variant — there's nothing to replace yet."""

    external_form_id: str | None = None
    """When set, slot inputs are associated with this external form
    via the HTML ``form="..."`` attribute, and the partial skips
    rendering its own ``<form>`` scaffold + footer. Used on the
    new-session page so the Create-session form's submit also
    carries any Quick Setup uploads through to the same dispatch
    pipeline."""


def build_quick_setup_context(
    db: Session,
    review_session: ReviewSession,
    *,
    user: User | None = None,
    is_unlocked: bool = False,
    error_kind: str | None = None,
    error_reason: str | None = None,
) -> QuickSetupContext:
    """Build the Quick Setup card context for Session Home.

    ``is_unlocked`` reflects the operator's lock-toggle cookie
    (``qsu_{session_id}=1``). Default is ``False`` ⇒ ``is_locked=True``
    on every fresh page load.

    ``error_kind`` + ``error_reason`` come from the
    ``?quick_setup_error=...&quick_setup_reason=...`` redirect flag set
    by the slot's POST handler on rejection. The pair drives the
    inline ``banner-error`` rendered inside the offending slot. Other
    slots are unaffected.
    """

    sid = review_session.id
    # Card is functional only on ``draft`` AND when no reviewer
    # responses exist yet. Outside that window — ``validated`` /
    # ``ready`` / ``closed``, or any state with persisted responses
    # from a prior activation cycle — the card stays permanently
    # locked (body greyed, Lock / Unlock toggle hidden, submits
    # rejected at the service layer via ``_require_editable`` +
    # ``_require_response_loss_ack``). The single description copy
    # names both conditions.
    has_responses = responses_service.session_response_count(db, sid) > 0
    is_available = lifecycle.is_draft(review_session) and not has_responses
    is_disabled = not is_available

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    relationship_count = relationships_service.existing_count(db, sid)

    cancel_url_for = lambda key: (  # noqa: E731
        f"/operator/sessions/{sid}#quick-setup-{key}"
    )

    def _error_for(slot_key: str) -> str | None:
        if error_kind != slot_key:
            return None
        return _quick_setup_error_message(slot_key, error_reason)

    slots = [
        QuickSetupSlot(
            key="reviewers",
            label="Reviewers",
            count=reviewer_count,
            mode="file_upload",
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/quick-setup/reviewers",
            coming_in=None,
            error_message=_error_for("reviewers"),
            cancel_url=cancel_url_for("reviewers"),
        ),
        QuickSetupSlot(
            key="reviewees",
            label="Reviewees",
            count=reviewee_count,
            mode="file_upload",
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/quick-setup/reviewees",
            coming_in=None,
            error_message=_error_for("reviewees"),
            cancel_url=cancel_url_for("reviewees"),
        ),
        QuickSetupSlot(
            key="relationships",
            label="Relationships",
            count=relationship_count,
            mode="file_upload",
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/quick-setup/relationships",
            coming_in=None,
            error_message=_error_for("relationships"),
            cancel_url=cancel_url_for("relationships"),
        ),
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 12A PR 6",
            error_message=None,
            cancel_url=cancel_url_for("settings"),
        ),
    ]

    description = (
        "Bulk-populate reviewers, reviewees, relationships, and "
        "session settings from files in one place. Available only "
        "when session is in draft mode and does not have any "
        "responses."
    )

    # Default-locked on every fresh page load when the card is
    # available; the cookie-driven ``is_unlocked`` flips it off
    # until the operator locks again or the cookie is cleared.
    # When the card isn't available (validated / ready / closed
    # / or any state with persisted responses), force-lock and
    # hide the toggle entirely so the operator can't visually
    # unlock something the route layer would reject anyway.
    is_locked = True if not is_available else not is_unlocked

    return QuickSetupContext(
        slots=slots,
        is_disabled=is_disabled,
        is_locked=is_locked,
        description=description,
        show_lock_toggle=is_available,
    )


def _quick_setup_error_message(slot_key: str, reason: str | None) -> str:
    """Render the banner-error copy for a slot's last failed submit.

    ``reason`` is a stable token from the route handler:

    - ``"parse"`` — the upload couldn't be parsed / validated. The
      message points the operator at the per-entity Setup page where
      the per-row error feedback lives.
    - ``"lifecycle"`` — the submit hit ``_require_editable`` on a
      ``ready`` session. The message names the next move (Pause).
    - ``"needs_confirm"`` — the form was submitted without ticking
      the card-level replacement-confirmation checkbox at the top
      of Quick Setup.
    """

    label_for = {
        "reviewers": "Reviewers",
        "reviewees": "Reviewees",
        "relationships": "Relationships",
        "settings": "Session settings",
    }
    label = label_for.get(slot_key, slot_key)
    if reason == "lifecycle":
        return (
            "Setup edits are paused while the session is Activated. "
            "Pause the session before applying setup changes."
        )
    if reason == "needs_confirm":
        return (
            "Tick the replacement-confirmation box at the top of "
            "Quick Setup before submitting."
        )
    # Default / parse-error path. Keep the message short — the
    # per-entity Setup page is the authoritative error surface.
    per_entity_path = {
        "reviewers": "reviewers",
        "reviewees": "reviewees",
        "relationships": "relationships",
    }.get(slot_key)
    if per_entity_path:
        return (
            f"Could not import {label.lower()}. "
            f"Open the {label} Setup page for per-row error details."
        )
    return f"Could not import {label.lower()}."


def build_new_session_quick_setup_context(
    db: Session | None = None,
    user: User | None = None,
) -> QuickSetupContext:
    """Quick Setup card for the ``/operator/sessions/new`` page.

    When called with ``db`` and ``user``, the slots render wired and
    their inputs associate with the create-session form (via the
    ``external_form_id`` HTML attribute) so the operator can stage
    Quick Setup uploads alongside the session-creation form. The
    POST ``/operator/sessions`` handler creates the session and then
    dispatches the same per-slot pipeline used by the Session Home
    consolidated submit.

    Called with no arguments, the function returns an inert preview
    shape — every slot ``is_wired=False`` — for callers that want
    the eventual visual without hooking up the back end.

    The card is always unlocked (``is_locked=False``) and the
    Lock / Unlock toggle is suppressed: there's no session to lock.
    The card-level replace-confirmation checkbox is also suppressed
    (``show_confirm_replace=False``) — there's nothing to replace
    on a freshly-created session.
    """

    is_wired = db is not None and user is not None

    slots = [
        QuickSetupSlot(
            key="reviewers",
            label="Reviewers",
            count=0,
            mode="file_upload",
            is_wired=is_wired,
            wire_url=None,
            coming_in=None if is_wired else "Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="reviewees",
            label="Reviewees",
            count=0,
            mode="file_upload",
            is_wired=is_wired,
            wire_url=None,
            coming_in=None if is_wired else "Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="relationships",
            label="Relationships",
            count=0,
            mode="file_upload",
            is_wired=is_wired,
            wire_url=None,
            coming_in=None if is_wired else "Wired in Segment 15D PR 7c",
        ),
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 12A PR 6",
        ),
    ]

    return QuickSetupContext(
        slots=slots,
        is_disabled=False,
        is_locked=False,
        description=(
            "Bulk-populate reviewers, reviewees, relationships, "
            "and session settings from files in one place — "
            "submitted alongside the session details above."
        ),
        title="Quick setup (optional)",
        show_lock_toggle=False,
        show_confirm_replace=False,
        external_form_id="create-session-form" if is_wired else None,
    )


