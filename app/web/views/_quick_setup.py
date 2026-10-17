"""Quick Setup card view-shape adapter (Segment 11H scaffold +
Segment 11J wiring) — the bulk-populate card on Session Home and
the new-session preview variant.

Slice 7 of the §12.B ladder (``guide/archive/major_refactor.md``).

Owns the ``QuickSetupSlot`` / ``QuickSetupContext`` dataclasses,
the per-slot error-message renderer, and the two context builders:

- ``build_quick_setup_context(...)`` — Session Home variant.
  Reads the session lifecycle and responses to decide
  ``is_available`` / ``is_locked``.
- ``build_new_session_quick_setup_context(...)`` — new-session
  page variant. Card always live.

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
from app.services import session_lifecycle as lifecycle

from ._upload_problems import problem_kinds, problems_sentence


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
    ``relationships`` / ``observers`` / ``settings``; both variants show
    all five. Used as the
    DOM-id suffix (``#quick-setup-{key}``) so URL fragments scroll
    directly to a slot, and as the ``data-wire-target`` value so
    11J's wiring can locate the slot without a CSS-selector
    contract."""

    label: str
    """Human-readable slot label, used in the H3 heading."""

    count: int
    """Current population — count of the slot's rows (reviewers,
    reviewees, relationships or observers). ``0`` for the
    Session settings slot."""

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
    on ``ready``). Rendered as a full-width ``banner-error`` above
    the slots, tied to this slot by id. The cancel link in the banner returns the operator to the slot
    fragment with a clean URL."""

    cancel_url: str | None = None
    """Clean Home URL with this slot's fragment anchor. Used as the
    Cancel target for the error banner. Stable across renders."""

    error_details: tuple[str, ...] = ()
    """The lines listed under ``error_message`` for a rejected file, one
    each: a Settings CSV's validation errors (findings D31), or a roster
    file's kinds of problem with no row named
    (``roster_problem_details``; the roster's Setup page shows rows), or
    the instruments a Settings file would delete."""

    error_reason: str | None = None
    """The refusal's reason token (``parse``, ``needs_confirm``, …) when
    this slot refused, rendered as the banner's
    ``data-quick-setup-reason`` so the page names it without copy."""

    deletion_count: int = 0
    """How many instruments a refused Settings file would delete, when
    that is why it was refused (findings S4): the banner then carries a
    ``Yes, delete`` tick whose value is this count, which the next
    submit sends as ``acknowledge_instrument_deletion``. ``0`` renders
    no tick."""


@dataclass(frozen=True)
class QuickSetupContext:
    """Page-shape adapter output for the Quick Setup card.

    ``slots`` renders top-to-bottom in the order given; the card
    iterates and the ``quick_setup_slot`` macro renders each one.

    ``is_locked`` (visual greying, inputs disabled) is the card's
    availability, and nothing else — there is no Lock / Unlock
    (``guide/operator_pages_enhancements.md`` Item 1):

    - **Available** (setup editable — ``draft`` or ``validated`` —
      AND no persisted responses): ``is_locked=False``; the slots are
      live on load and the replace checkbox gates every replacing
      submit.
    - **Unavailable** (``ready`` or later, or any session with
      persisted responses): ``is_locked=True``. The body greys and
      the inputs are disabled. Defense-in-depth route gates (each
      slot's inline ``is_editable`` check, plus
      ``_require_response_loss_ack`` on the Reviewers, Reviewees and
      Settings slots) stay in place but never fire from this surface
      because the submit forms aren't reachable when the body's
      locked.

    ``is_disabled`` mirrors ``not is_available`` for templates
    that want a single boolean to drive label-only signals; it's
    not a separate visual lock primitive.

    ``title`` overrides the H2 text. Session Home uses the default
    ``"Quick Setup"``; the new-session preview variant uses
    ``"Quick setup (optional)"`` to convey that the card surfaces
    early as a hint about post-creation setup paths.
    """

    slots: list[QuickSetupSlot]
    is_disabled: bool
    is_locked: bool
    description: str
    title: str = "Quick Setup"
    show_confirm_replace: bool = True
    """Gate the card-level "Yes, replace existing reviewers, reviewees
    or settings, according to what is uploaded. …" checkbox just above
    the footer. Suppressed on the new-session
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
    error_kind: str | None = None,
    error_reason: str | None = None,
    error_details: tuple[str, ...] = (),
    error_count: int = 0,
) -> QuickSetupContext:
    """Build the Quick Setup card context for Session Home.

    ``error_kind`` + ``error_reason`` name the slot that refused and
    why: from the refusal itself when a Quick Setup route re-renders
    Session Home, with ``error_details`` (the file's own lines) and
    ``error_count`` (the instrument count a ``deletes_instruments``
    refusal re-offers its tick with); or from the Create page's redirect
    codes, read through :func:`quick_setup_url_failure`, with neither
    (findings O7). The pair drives that slot's ``banner-error``,
    rendered full-width above the slots. Other slots are unaffected.
    """

    sid = review_session.id
    # Card is functional while setup is editable (``draft`` or
    # ``validated`` — the single ``lifecycle.is_editable`` predicate the
    # routes gate on; author's ruling, 2026-10-07, findings B1) AND no
    # reviewer responses exist yet. Outside that window — ``ready``,
    # ``expired``, ``archived``, or any session with persisted responses
    # from a prior activation cycle — the card stays permanently
    # locked (body greyed, controls disabled). A submit that
    # arrives anyway is refused by the slot's inline ``is_editable``
    # check, or, on a session with responses, by
    # ``_require_response_loss_ack``. The single description copy
    # names both conditions.
    #
    # 19R.1 rung 2 — this asked the question through
    # ``responses.session_response_count``, which loads every
    # ``Assignment`` in the session as an ORM object to decide whether
    # any instrument is group-scoped, then in the common case runs a
    # ``COUNT`` anyway. The card needs a yes/no, and
    # ``session_has_responses`` is the helper that answers exactly that
    # — its own docstring says so, and seven other call sites already
    # use it. The two agree by construction: the deduped count collapses a
    # group's fan-out to one cell per group, which can shrink a
    # positive count but never reach zero, so ``> 0`` and "a row
    # exists" are the same question.
    has_responses = lifecycle.session_has_responses(db, review_session)
    is_available = lifecycle.is_editable(review_session) and not has_responses
    is_disabled = not is_available

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    relationship_count = relationships_service.existing_count(db, sid)
    observer_count = csv_imports.existing_observer_count(db, sid)

    cancel_url_for = lambda key: (  # noqa: E731
        f"/operator/sessions/{sid}#quick-setup-{key}"
    )
    # The re-offered tick renders only for the refusal that asks for it,
    # and only with a count to carry.
    _deletion_count = (
        error_count
        if error_kind == "settings"
        and error_reason == "deletes_instruments"
        and error_count > 0
        else 0
    )

    def _error_for(slot_key: str) -> str | None:
        if error_kind != slot_key:
            return None
        return _quick_setup_error_message(
            slot_key,
            error_reason,
            has_details=bool(error_details),
            count=_deletion_count,
        )

    def _reason_for(slot_key: str) -> str | None:
        return error_reason if error_kind == slot_key else None

    def _details_for(slot_key: str) -> tuple[str, ...]:
        # The route's own lines, already capped; never read from a URL.
        return tuple(error_details) if error_kind == slot_key else ()

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
            error_details=_details_for("reviewers"),
            error_reason=_reason_for("reviewers"),
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
            error_details=_details_for("reviewees"),
            error_reason=_reason_for("reviewees"),
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
            error_details=_details_for("relationships"),
            error_reason=_reason_for("relationships"),
            cancel_url=cancel_url_for("relationships"),
        ),
    ]
    # Observers slot — always shown, as on the New session card
    # (``guide/quick_setup_update.md`` Item 2). An upload that saves rows
    # turns ``observers_enabled`` on, so the rows never sit behind a
    # hidden tab.
    slots.append(
        QuickSetupSlot(
            key="observers",
            label="Observers",
            count=observer_count,
            mode="file_upload",
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/quick-setup/observers",
            coming_in=None,
            error_message=_error_for("observers"),
            error_details=_details_for("observers"),
            error_reason=_reason_for("observers"),
            cancel_url=cancel_url_for("observers"),
        )
    )
    slots.append(
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            mode="file_upload",
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/import-config",
            coming_in=None,
            error_message=_error_for("settings"),
            error_details=_details_for("settings"),
            error_reason=_reason_for("settings"),
            cancel_url=cancel_url_for("settings"),
            deletion_count=_deletion_count,
        )
    )

    # The description copy lists the slots that actually render so
    # the operator can see at a glance what they can bulk-populate.
    slot_phrase = (
        "reviewers, reviewees, relationships, observers, and "
        "session settings"
    )
    if has_responses:
        # A session reverted from ``ready`` keeps its responses, so it
        # lands here in ``draft`` but permanently locked. Spell out
        # why — Quick Setup's bulk imports replace rosters / settings
        # wholesale and would discard those responses.
        description = (
            f"Bulk-populate {slot_phrase} from files in one place. "
            "Quick Setup is locked because this session already holds "
            "reviewer responses from a prior activation. Use the "
            "individual Setup pages to make changes."
        )
    else:
        description = (
            f"Bulk-populate {slot_phrase} from files in one place. "
            "Available only while setup is editable (draft or "
            "validated) and the session has no responses."
        )

    # Locked exactly when unavailable (``ready`` / ``expired`` /
    # ``archived``, or any session with persisted responses), so the
    # card never offers what the route layer would reject.
    return QuickSetupContext(
        slots=slots,
        is_disabled=is_disabled,
        is_locked=not is_available,
        description=description,
    )


#: The slots a refusal names, and the one reason a redirect carries:
#: the Create page's ``refused`` (findings O7). Every other refusal
#: re-renders Session Home, so no other code reaches the page by URL.
_SLOT_KEYS = frozenset(
    {"reviewers", "reviewees", "relationships", "observers", "settings"}
)
URL_REASONS = frozenset({"refused"})


def quick_setup_url_failure(
    kind: str | None, reason: str | None
) -> dict[str, str]:
    """The ``error_kind`` / ``error_reason`` keywords for
    :func:`build_quick_setup_context` from Session Home's
    ``?quick_setup_error=…&quick_setup_reason=…`` codes, or none for a
    pair the Create page does not send: an unlisted code shows nothing,
    as ``super_error`` does (findings O7)."""

    if kind in _SLOT_KEYS and reason in URL_REASONS:
        return {"error_kind": kind, "error_reason": reason}
    return {}


#: How many error lines a refused slot's banner lists (a Settings CSV's
#: errors, a roster file's kinds of problem, the instruments a Settings
#: file deletes), how long each may be, and how many URL-encoded bytes
#: they may take together, a measure kept from when the lines rode the
#: redirect (a value quoted in a message can be non-ASCII, up to twelve
#: encoded bytes a character). They are re-rendered now, never read
#: from a URL (findings O7); the caps keep the banner short. A longer
#: list ends with a count of the rest.
SETTINGS_ERROR_DETAIL_LIMIT = 5
SETTINGS_ERROR_DETAIL_MAX_CHARS = 200
SETTINGS_ERROR_DETAIL_MAX_BYTES = 2000


def _clip(line: str) -> str:
    if len(line) > SETTINGS_ERROR_DETAIL_MAX_CHARS:
        return line[: SETTINGS_ERROR_DETAIL_MAX_CHARS - 1] + "…"
    return line


def settings_error_details(errors: list) -> list[str]:
    """Format ``apply_session_config``'s ``ApplyResult.errors`` as the
    lines the Settings slot's banner lists (findings D31): the row
    and field when the error has them, then the message."""

    lines = []
    for error in errors:
        where = []
        if error.row_number:
            where.append(f"Row {error.row_number}")
        if error.field:
            where.append(error.field)
        lines.append(
            f"{', '.join(where)}: {error.message}" if where else error.message
        )
    return _capped(lines)


def roster_problem_details(issues: list) -> list[str]:
    """The kinds of problem that refused a roster file in Quick Setup,
    one line each with how many rows have it ("ReviewerEmail is blank
    (2 rows)"), capped for the banner. The lines are the Setup pages'
    upload cards' too (``problem_kinds``); neither lists rows
    (``guide/quick_setup_update.md`` Item 3)."""

    return _capped(problem_kinds(issues))


def deleted_instrument_details(labels: list[str]) -> list[str]:
    """The instruments a Settings file would delete, one label a line,
    capped as the other lists are (findings S4); the banner's lead
    sentence carries the full count."""

    return _capped(labels)


def _capped(all_lines: list[str]) -> list[str]:
    """The lines a banner lists: at most
    ``SETTINGS_ERROR_DETAIL_LIMIT``, each clipped, within the byte
    budget, then a count of the rest."""

    from urllib.parse import quote_plus

    lines: list[str] = []
    spent = 0
    for raw in all_lines[:SETTINGS_ERROR_DETAIL_LIMIT]:
        line = _clip(raw)
        cost = len(quote_plus(line))
        if lines and spent + cost > SETTINGS_ERROR_DETAIL_MAX_BYTES:
            break
        spent += cost
        lines.append(line)
    hidden = len(all_lines) - len(lines)
    if hidden > 0:
        lines.append(f"…and {hidden} more.")
    return lines


def _quick_setup_error_message(
    slot_key: str,
    reason: str | None,
    has_details: bool = False,
    count: int = 0,
) -> str:
    """Render the banner-error copy for a slot's last failed submit.

    ``reason`` is a stable token from the route handler:

    - ``"parse"`` — the upload couldn't be parsed / validated. With
      ``has_details`` a roster slot's message leads into the list of
      the file's kinds of problem the banner shows; Settings lists its
      errors under its plain sentence.
    - ``"lifecycle"`` — the submit failed the slot's inline
      ``is_editable`` check on a ``ready`` session. The message names the next move (Revert to
      draft — the operator-facing name for this transition; *Pause* is
      the legacy internal one, per 19O Item 7 entry 13).
    - ``"needs_confirm"`` — the form was submitted without ticking
      the card-level replacement-confirmation checkbox at the top
      of Quick Setup.
    - ``"deletes_instruments"`` — a valid Settings file would delete
      ``count`` instruments it does not name (findings S4). The banner
      lists them under this sentence and re-offers the tick.
    - ``"refused"`` — the Create page's code for a staged file it
      refused (findings O7): its lines are not carried, so the sentence
      sends the operator back to Quick Setup to see them.
    """

    label_for = {
        "reviewers": "Reviewers",
        "reviewees": "Reviewees",
        "relationships": "Relationships",
        "observers": "Observers",
        "settings": "Session settings",
    }
    label = label_for.get(slot_key, slot_key)
    if reason == "lifecycle":
        return (
            "Setup edits are locked while the session is Activated. "
            "Revert the session to draft before applying setup changes."
        )
    if reason == "needs_confirm":
        return (
            "Tick the replacement-confirmation box just above "
            "Submit, then submit again."
        )
    if reason == "refused":
        return (
            f"The {label.lower()} file was refused, so none of the files "
            "uploaded with the new session were saved. Upload them again "
            "in Quick Setup to see why."
        )
    if reason == "deletes_instruments" and slot_key == "settings" and count:
        one = count == 1
        return (
            f"Nothing was imported. This settings file deletes {count} "
            f"instrument{'' if one else 's'} it does not name, with "
            f"{'its' if one else 'their'} fields:"
        )
    # Default / parse-error path. The lines are the kinds of problem
    # (``roster_problem_details``), as the Setup pages' upload cards
    # show them; neither surface points at the other, and neither lists
    # rows (``guide/quick_setup_update.md`` Item 3).
    if has_details and slot_key != "settings":
        return problems_sentence(label.lower())
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

    The card is always live (``is_locked=False``). The card-level replace-confirmation checkbox is also suppressed
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
        # Observers slot — always renders, as on Session Home. An upload
        # that saves rows turns ``observers_enabled`` on whether or not
        # the form's box is ticked (``guide/quick_setup_update.md``
        # Item 2).
        QuickSetupSlot(
            key="observers",
            label="Observers",
            count=0,
            mode="file_upload",
            is_wired=is_wired,
            wire_url=None,
            coming_in=None if is_wired else "Wired in Segment 21",
        ),
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            mode="file_upload",
            is_wired=is_wired,
            wire_url=None,
            coming_in=None if is_wired else "Wired in Segment 12A-3 PR 4",
        ),
    ]

    return QuickSetupContext(
        slots=slots,
        is_disabled=False,
        is_locked=False,
        description=(
            "Bulk-populate reviewers, reviewees, relationships, "
            "observers, and session settings from files in one "
            "place — submitted alongside the session details above."
        ),
        title="Quick setup (optional)",
        show_confirm_replace=False,
        external_form_id="create-session-form" if is_wired else None,
    )


