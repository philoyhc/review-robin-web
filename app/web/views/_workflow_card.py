"""Operations Workflow Card view-shape adapter (Segment 15E PR 3).

Builds the single, state-aware action surface that renders at the
top of every Operations-row page. PR 3 (this slice) ships v1 on
the Assignments page only as the beachhead; PR 4 extends the same
partial to Validate / Previews / Invitations / Responses; PR 5
retires the Session Home Next Action card once the card is on
every Operations page.

Public surface:

- ``WorkflowCardContext`` dataclass — view-shape passed into the
  ``operations_workflow_card.html`` partial. Carries the per-state
  next-action copy, the button-enabled matrix, the acknowledge-
  warnings checkbox flag, and the Generate-wrap banner read from
  the request query string.
- ``build_workflow_card_context(db, review_session, banner=None)``
  context-builder — consumes lifecycle predicates +
  ``validation.validate_session_setup`` output + the gate-split
  mapping (PR 2's ``gate_for_rule_key``) and produces the dataclass.

The card carries five buttons, the same set on every Operations
page:

- **Generate** — POST to existing ``/assignments/generate`` route
  (wrapped with setup-gate + replace_assignments + operations-gate
  validation in this PR; see ``routes_operator/_assignments.py``).
- **Activate** — POST to existing ``/activate`` route.
- **Send invitations** — anchor link to ``/invitations`` page for
  PR 3 (PR 4 turns this into a POST to a wrap endpoint).
- **Send reminders** — anchor link to ``/invitations`` page for
  PR 3 (PR 4 wrap endpoint).
- **Pause** — POST to existing ``/revert`` route (revert-to-draft
  under a friendly label; Close is intentionally omitted —
  there's no ``close_session`` lifecycle transition today).

Pause's destructive confirm checkbox + Activate's acknowledge-
warnings checkbox both render inline as continuations of the
next-action line per the segment spec.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services import session_lifecycle as lifecycle
from app.services import validation
from app.web.views._validate import gate_for_rule_key


@dataclass(frozen=True)
class WorkflowCardContext:
    """View-shape for the Operations Workflow Card partial."""

    title: str
    """Always "Operations workflow" — kept as a field so a future
    polish PR can tweak per-state without re-touching the template."""

    next_action_line: str
    """Single-line "Next action: …" copy. State-aware. The partial
    renders it inside the Activate or Pause form when the inline
    acknowledge / confirm checkbox attaches; otherwise plain text."""

    acknowledge_warnings_count: int
    """When > 0, the Activate button renders with an inline
    "I acknowledge N warning(s)" checkbox (continuation of the
    next-action line) and Activate POST carries
    ``acknowledge_warnings=true``."""

    # Button-enabled matrix. Always rendered; greyed-out via the
    # ``disabled`` attribute when the lifecycle state doesn't
    # permit the action.

    generate_enabled: bool
    generate_is_primary: bool

    activate_enabled: bool
    activate_is_primary: bool

    send_invitations_enabled: bool
    send_invitations_is_primary: bool

    send_reminders_enabled: bool

    pause_enabled: bool

    # URLs the template needs to render forms / anchors.

    generate_url: str
    activate_url: str
    invitations_url: str
    pause_url: str

    # Optional banner surfaced after a Generate-wrap action.
    # Driven by the ``?wf=setup_errors|warnings|errors|clean`` query
    # param. ``None`` when no banner.
    banner_kind: str | None
    banner_text: str | None
    banner_link_href: str | None


_BANNER_TEMPLATES: dict[str, tuple[str, str]] = {
    "clean": (
        "verdict-clean",
        "Generated assignments. Session validated.",
    ),
    "warnings": (
        "verdict-warn",
        "Generated assignments with warnings — see Validate ↗",
    ),
    "errors": (
        "verdict-error",
        "Generated with errors — see Validate ↗",
    ),
    "setup_errors": (
        "verdict-error",
        "Can't generate — setup errors. Fix on Setup tabs ↗ "
        "(see Validate page for the list).",
    ),
}


def _banner_for(
    review_session: ReviewSession, banner_kind: str | None
) -> tuple[str | None, str | None, str | None]:
    if banner_kind not in _BANNER_TEMPLATES:
        return None, None, None
    kind, text = _BANNER_TEMPLATES[banner_kind]
    link = f"/operator/sessions/{review_session.id}/validate"
    if banner_kind == "clean":
        link = None
    return kind, text, link


def build_workflow_card_context(
    db: Session,
    review_session: ReviewSession,
    *,
    banner_kind: str | None = None,
) -> WorkflowCardContext:
    """Build the workflow card view-shape for ``review_session``.

    Runs ``validation.validate_session_setup`` live, splits by gate
    (PR 2) to derive setup-gate-error vs. operations-gate-error
    counts, then composes the per-state next-action line + button
    matrix.
    """
    issues = validation.validate_session_setup(db, review_session)
    report = lifecycle.build_readiness_report(issues)

    setup_errors = sum(
        1
        for i in issues
        if i.severity.value == "error"
        and gate_for_rule_key(i.rule_key or "") == "setup"
    )
    ops_errors = sum(
        1
        for i in issues
        if i.severity.value == "error"
        and gate_for_rule_key(i.rule_key or "") == "operations"
    )

    is_draft = lifecycle.is_draft(review_session)
    is_validated = lifecycle.is_validated(review_session)
    is_ready = lifecycle.is_ready(review_session)

    warning_count = len(report.warnings)

    # Default enabled-flag matrix.
    generate_enabled = is_draft or is_validated
    generate_is_primary = False
    activate_enabled = False
    activate_is_primary = False
    send_invitations_enabled = is_ready
    send_invitations_is_primary = False
    send_reminders_enabled = is_ready
    pause_enabled = is_ready
    acknowledge_warnings_count = 0
    next_action_line = ""

    if is_ready:
        # Activated session. Send invitations is the active verb;
        # Pause is available; Generate is locked (setup is locked
        # in ready state).
        generate_enabled = False
        next_action_line = (
            "Next action: Send invitations to reviewers."
        )
        send_invitations_is_primary = True
    elif is_validated:
        next_action_line = "Next action: Activate session."
        activate_enabled = True
        activate_is_primary = True
        if report.has_non_blocking_findings:
            acknowledge_warnings_count = warning_count
            next_action_line = (
                f"Next action: Activate session — I acknowledge "
                f"{warning_count} warning"
                f"{'s' if warning_count != 1 else ''}."
            )
        pause_enabled = False  # Revert-to-draft only from ready state
    elif is_draft:
        # Pre-Generate (or post-Generate but still draft) — Generate
        # is the canonical primary action. Activate stays disabled
        # until the operator transitions to validated via the
        # existing Session Home "Validate Setup" button; PR 3 keeps
        # that legacy path (PR 5 retires the Next Action card and
        # will surface a validate step on the workflow card itself).
        generate_is_primary = True
        if setup_errors > 0:
            next_action_line = (
                "Next action: fix setup errors — see Validate ↗"
            )
            # Generate is still clickable so the operator can re-run
            # after fixing — the wrap will hard-stop on setup-gate
            # errors anyway.
        elif ops_errors > 0:
            next_action_line = (
                "Next action: fix readiness errors — see Validate ↗"
            )
        elif report.has_non_blocking_findings:
            next_action_line = (
                "Next action: Generate assignments "
                "(setup has warnings — review on Validate)."
            )
        else:
            next_action_line = "Next action: Generate assignments."
    else:
        # Reserved statuses (expired / archived); show no actionable
        # buttons. The next-action line is informational.
        generate_enabled = False
        next_action_line = (
            f"Session is {review_session.status}; no further "
            "actions available here."
        )

    banner_kind_out, banner_text, banner_link = _banner_for(
        review_session, banner_kind
    )

    session_id = review_session.id
    return WorkflowCardContext(
        title="Operations workflow",
        next_action_line=next_action_line,
        acknowledge_warnings_count=acknowledge_warnings_count,
        generate_enabled=generate_enabled,
        generate_is_primary=generate_is_primary,
        activate_enabled=activate_enabled,
        activate_is_primary=activate_is_primary,
        send_invitations_enabled=send_invitations_enabled,
        send_invitations_is_primary=send_invitations_is_primary,
        send_reminders_enabled=send_reminders_enabled,
        pause_enabled=pause_enabled,
        generate_url=f"/operator/sessions/{session_id}/assignments/generate",
        activate_url=f"/operator/sessions/{session_id}/activate",
        invitations_url=f"/operator/sessions/{session_id}/invitations",
        pause_url=f"/operator/sessions/{session_id}/revert",
        banner_kind=banner_kind_out,
        banner_text=banner_text,
        banner_link_href=banner_link,
    )


