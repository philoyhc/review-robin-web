"""Previews-page view-shapes (Segment 11F) — reviewer-picker
context, three-tab email previews, the merge-tag editor strip.

Slice 9 of the §12.B ladder (``guide/archive/major_refactor.md``).

Owns:

- **Reviewer picker** — ``PreviewPickerOption`` /
  ``PreviewPickerContext`` + ``build_preview_picker_context`` /
  ``_extract_email_from_picker_value`` /
  ``_picker_assigned_reviewee_names``.
- **Email previews region** — ``EmailBody`` / ``EmailPreviewTab`` +
  ``EMAIL_PREVIEW_TABS`` / ``PREVIEW_INVITE_URL_PLACEHOLDER`` +
  ``resolve_email_preview_tab`` / ``email_preview_from_display`` /
  ``build_email_preview_body``.
- **Merge tags** — ``merge_tags_for_template`` (used by the
  email-template editor's right card).

The iframe-embedded reviewer-surface preview card (Segment 11F PR C)
was retired in the Segment 18Q follow-on; the picker row now carries
an "Open full preview" link that opens the operator-side full
preview surface (``routes_operator/_preview_surface.py``) in a new tab.

Source range in pre-PR-9 ``_legacy.py``: lines 30-557.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import email_templates


# How many reviewee names the picker context strip shows before
# collapsing the rest into the `<details>` disclosure tail.
PREVIEW_PICKER_REVIEWEE_PEEK_COUNT = 3


@dataclass(frozen=True)
class PreviewPickerOption:
    """One row backing the picker `<datalist>` and the prev/next math.

    ``label`` is the display string (``"Name (email)"``); ``value`` is
    the bare email the form submits. Sort order across all options is
    alphabetical by email (case-insensitive), matching the order
    `app/services/monitoring._assigned_active_reviewers` uses elsewhere.
    """

    reviewer_id: int
    name: str
    email: str
    label: str


@dataclass(frozen=True)
class PreviewPickerContext:
    options: list[PreviewPickerOption]
    """Every reviewer in the session, alphabetical by email. Backs both
    the `<datalist>` and the prev/next math."""

    raw_query: str
    """The operator's typed value (post-strip), forwarded to the input
    so refresh/back doesn't blank it."""

    current: PreviewPickerOption | None
    """The resolved selection, or ``None`` when nothing is selected
    (no param, empty param, or unmatched param)."""

    current_index: int | None
    """0-based index of ``current`` within ``options``; ``None`` when
    no current selection."""

    prev_email: str | None
    """Email to step to on Previous; wraps. ``None`` when no current."""

    next_email: str | None
    """Email to step to on Next; wraps. ``None`` when no current."""

    reviewee_count: int
    """How many distinct reviewees ``current`` is assigned to (counting
    only ``include=True`` assignments). 0 when no current."""

    reviewee_peek: list[str] = field(default_factory=list)
    """First ``PREVIEW_PICKER_REVIEWEE_PEEK_COUNT`` reviewee names for
    the context strip."""

    reviewee_tail: list[str] = field(default_factory=list)
    """Remaining reviewee names that go inside the `<details>`
    disclosure. Empty when ``reviewee_count`` is at or below the peek
    count."""

    no_match_query: str | None = None
    """When the operator submitted a value that didn't resolve, the
    typed value (post-strip). The template renders the "No reviewer
    matched 'foo'." note. ``None`` when the input was empty or
    resolved cleanly."""


_PICKER_LABEL_EMAIL_RE = re.compile(r"\(([^()]+@[^()]+)\)\s*$")


def _extract_email_from_picker_value(value: str) -> str:
    """Parse the picker's submitted value into an email.

    Accepts a bare email (``"alice@x.edu"``) or a datalist label
    (``"Alice Smith (alice@x.edu)"``). Returns the trimmed lower-case
    email, or the trimmed lower-case input unchanged when no parens-
    enclosed email is found (the caller treats unmatched values as a
    no-match).
    """
    stripped = value.strip()
    if not stripped:
        return ""
    match = _PICKER_LABEL_EMAIL_RE.search(stripped)
    if match is not None:
        return match.group(1).strip().casefold()
    return stripped.casefold()


def build_preview_picker_context(
    db: Session, review_session: ReviewSession, reviewer_query: str
) -> PreviewPickerContext:
    """Hydrate the Previews-page reviewer picker.

    ``reviewer_query`` comes from ``?reviewer_email=`` and may be
    blank, an email, or the datalist label format
    (``"Name (email)"``). Resolution is case-insensitive on email.
    Unmatched non-empty values surface as ``no_match_query`` so the
    template renders the inline "No reviewer matched" note rather than
    silently falling back.
    """

    reviewer_rows = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(Reviewer.email)
        ).scalars()
    )

    options = [
        PreviewPickerOption(
            reviewer_id=r.id,
            name=r.name,
            email=r.email,
            label=f"{r.name} ({r.email})",
        )
        for r in reviewer_rows
    ]

    raw = reviewer_query.strip()
    parsed_email = _extract_email_from_picker_value(reviewer_query)

    current: PreviewPickerOption | None = None
    current_index: int | None = None
    if parsed_email:
        for idx, opt in enumerate(options):
            if opt.email.casefold() == parsed_email:
                current = opt
                current_index = idx
                break

    prev_email: str | None = None
    next_email: str | None = None
    if current is not None and len(options) > 0 and current_index is not None:
        n = len(options)
        prev_email = options[(current_index - 1) % n].email
        next_email = options[(current_index + 1) % n].email

    no_match: str | None = None
    if raw and current is None:
        no_match = raw

    reviewee_count = 0
    reviewee_peek: list[str] = []
    reviewee_tail: list[str] = []
    if current is not None:
        names = _picker_assigned_reviewee_names(
            db, review_session.id, current.reviewer_id
        )
        reviewee_count = len(names)
        reviewee_peek = names[:PREVIEW_PICKER_REVIEWEE_PEEK_COUNT]
        reviewee_tail = names[PREVIEW_PICKER_REVIEWEE_PEEK_COUNT:]

    return PreviewPickerContext(
        options=options,
        raw_query=raw,
        current=current,
        current_index=current_index,
        prev_email=prev_email,
        next_email=next_email,
        reviewee_count=reviewee_count,
        reviewee_peek=reviewee_peek,
        reviewee_tail=reviewee_tail,
        no_match_query=no_match,
    )


def _picker_assigned_reviewee_names(
    db: Session, session_id: int, reviewer_id: int
) -> list[str]:
    """Distinct reviewee names this reviewer is assigned to, sorted.

    Only counts ``include=True`` assignments (matching how the rest of
    the app treats included assignments as the live set). Sort by name
    so the context strip is stable across reloads.
    """
    rows = db.execute(
        select(Reviewee.name)
        .join(Assignment, Assignment.reviewee_id == Reviewee.id)
        .where(
            Assignment.session_id == session_id,
            Assignment.reviewer_id == reviewer_id,
            Assignment.include.is_(True),
        )
        .distinct()
        .order_by(Reviewee.name)
    ).all()
    return [row[0] for row in rows]


# --- Email previews region (segment 11F PR B) ----------------------------- #
#
# The previews page renders three reviewer-facing emails through a single
# tabbed card. The `EMAIL_PREVIEW_TABS` registry pins the tab order
# (chronological: invitation → reminder → responses-received) and tells the
# template which tabs are shipped vs. coming. The route's render dispatch
# lives in `build_email_preview_body` below. All three are live as of
# Segment 11F PR D (reminder) + Segment 11E PR 6 (responses-received);
# the ``is_shipped`` field stays for any future tab additions that need
# to land registry-first and dispatch-second.

# A placeholder URL the operator-facing preview substitutes for `$invite_url`.
# Real invitation tokens are one-time-use and would be wasted (and audit-
# muddying) if minted just to power a preview render.
PREVIEW_INVITE_URL_PLACEHOLDER = "(preview link — real invitation URL is generated when the operator sends)"


@dataclass(frozen=True)
class EmailBody:
    """Rendered email body for the previews page.

    `subject`, `body` come from `email_templates.render_*`. `from_display`
    + `to_display` are envelope strings the operator sees in the preview
    header — they're not part of the rendered template, just the chrome
    around it.
    """

    subject: str
    from_display: str
    to_display: str
    body: str


@dataclass(frozen=True)
class EmailPreviewTab:
    """One entry in the previews page's email tab strip."""

    key: str
    """URL slug — what `?email=` resolves to."""

    label: str
    """Human-readable tab label."""

    template_setup_param: str
    """Value to thread into the deep-link to the Email Template Setup
    page (`/setupinvite?template=...`). Same as `key` for now; kept
    separate so the URL slug can diverge from the Setup-page slug
    without ripple."""

    is_shipped: bool
    """`True` once the matching render adapter is wired in. All three
    tabs are shipped as of Segment 11F PR D (reminder) + Segment 11E
    PR 6 (responses-received); the field stays for any future tab
    additions that land registry-first and dispatch-second."""

    description: str
    """One-line description rendered below the tab strip when this tab
    is active. Grounds the operator in when this email gets sent."""


EMAIL_PREVIEW_TABS: tuple[EmailPreviewTab, ...] = (
    EmailPreviewTab(
        key="invitation",
        label="Invitation",
        template_setup_param="invitation",
        is_shipped=True,
        description="Sent when the operator activates the session.",
    ),
    EmailPreviewTab(
        key="reminder",
        label="Reminder",
        template_setup_param="reminder",
        is_shipped=True,
        description=(
            "Sent against an active session past the configured "
            "reminder threshold. Operators trigger reminders from "
            "Manage Invitations."
        ),
    ),
    EmailPreviewTab(
        key="responses_received",
        label="Responses received",
        template_setup_param="responses_received",
        is_shipped=True,
        description="Sent the moment the reviewer submits their review.",
    ),
)


def resolve_email_preview_tab(key: str) -> EmailPreviewTab:
    """Return the registry entry for ``key``, falling back to
    ``"invitation"`` when ``key`` is unknown or not yet shipped.

    The fallback keeps `?email=foo` from 404'ing or rendering a blank
    region — the operator gets the canonical first tab instead. PRs
    D / E lift this once the matching tab ships.
    """
    for tab in EMAIL_PREVIEW_TABS:
        if tab.key == key and tab.is_shipped:
            return tab
    # Unknown or unshipped — fall back to the first shipped tab.
    for tab in EMAIL_PREVIEW_TABS:
        if tab.is_shipped:
            return tab
    raise RuntimeError(  # pragma: no cover — invariant: invitation always ships
        "EMAIL_PREVIEW_TABS has no shipped entries"
    )


def email_preview_from_display(user: User) -> str:
    """Format the From-header string the preview shows, given the
    operator's SMTP credentials.

    Reads ``smtp_username`` / ``smtp_from_display_name`` directly off
    the User row (no decryption — the displayed header doesn't need
    the password). When the credentials aren't configured, returns a
    placeholder pointing at Settings so the preview surfaces the
    missing config rather than rendering an empty header.
    """
    username = (user.smtp_username or "").strip()
    if not username:
        return "(SMTP From not configured — see Settings)"
    display_name = (user.smtp_from_display_name or "").strip()
    if display_name:
        return f"{display_name} <{username}>"
    return username


def build_email_preview_body(
    *,
    tab: EmailPreviewTab,
    review_session: ReviewSession,
    reviewer: Reviewer,
    from_display: str,
) -> EmailBody | None:
    """Render the active tab's email for the picker-selected reviewer.

    All three tabs ship live render adapters as of Segment 11F PR D
    (reminder) + Segment 11E PR 6 (responses-received); a ``None``
    return only happens if a caller passes a future-unshipped tab
    directly."""
    if tab.key == "invitation":
        subject, body = email_templates.render_invitation(
            review_session, reviewer, PREVIEW_INVITE_URL_PLACEHOLDER
        )
        return EmailBody(
            subject=subject,
            from_display=from_display,
            to_display=reviewer.email,
            body=body,
        )
    if tab.key == "reminder":
        subject, body = email_templates.render_reminder(
            review_session, reviewer, PREVIEW_INVITE_URL_PLACEHOLDER
        )
        return EmailBody(
            subject=subject,
            from_display=from_display,
            to_display=reviewer.email,
            body=body,
        )
    if tab.key == "responses_received":
        subject, body = email_templates.render_responses_received(
            review_session, reviewer
        )
        return EmailBody(
            subject=subject,
            from_display=from_display,
            to_display=reviewer.email,
            body=body,
        )
    return None


# Per-template merge-tag list surfaced by the email-template editor's
# right card. Invitation / reminder share the canonical five tags;
# responses-received drops ``$invite_url`` (moot post-submit) and adds
# ``$submitted_at``. Kept here (not in ``email_templates``) because the
# tag *descriptions* are operator-facing copy — view-shape rather than
# render-time data.
_MERGE_TAG_DESCRIPTIONS = {
    "$reviewer_name": "Reviewer's name from the roster.",
    "$session_name": "Session name.",
    "$deadline": "Session deadline (YYYY-MM-DD), blank when unset.",
    "$help_contact": "Per-session help contact.",
    "$invite_url": "Reviewer-specific invitation URL.",
    "$submitted_at": (
        "When the reviewer submitted, formatted YYYY-MM-DD HH:MM TZ. "
        "Renders \"(not yet submitted)\" in previews before the "
        "reviewer has submitted anything."
    ),
}

_MERGE_TAGS_BY_TEMPLATE: dict[str, tuple[str, ...]] = {
    "invitation": (
        "$reviewer_name",
        "$session_name",
        "$deadline",
        "$help_contact",
        "$invite_url",
    ),
    "reminder": (
        "$reviewer_name",
        "$session_name",
        "$deadline",
        "$help_contact",
        "$invite_url",
    ),
    "responses_received": (
        "$reviewer_name",
        "$session_name",
        "$deadline",
        "$help_contact",
        "$submitted_at",
    ),
}


def merge_tags_for_template(template: str) -> list[dict[str, str]]:
    """Returns the editor's right-card merge-tag list for ``template``.
    Unknown ``template`` values raise ``KeyError`` — the route already
    validates against ``_VALID_TEMPLATES`` before dispatching here."""
    return [
        {"tag": tag, "description": _MERGE_TAG_DESCRIPTIONS[tag]}
        for tag in _MERGE_TAGS_BY_TEMPLATE[template]
    ]


