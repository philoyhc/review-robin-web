"""Workspace-wide audit of the Band 3 visibility grid — Segment 19C
Item 10.

Two writers create ``instrument_view_policies`` rows.
``visibility_policies.upsert_policy`` has always validated the
``(audience, window)`` cell against ``_PER_CELL_VALID_MODES``; the
Settings-CSV import did not until Item 9 (PR #2188). That guard is
**prospective** — a row an import wrote before it is still stored, and
``resolve_mode`` honours it like any other. The cell that matters is
``("reviewee", "while_ongoing")``, whose only legal mode is ``None``: a
reviewee reading responses while the review is still running.

This module answers *"is any such row in the database now?"*. It reads;
it never writes. Clearing an offending cell is a judgment about a live
review — whether the operator meant ``after_release``, or meant nothing
— and belongs to the operator who owns that session, on the Band 3
editor, which already refuses to author the bad value.

It reads the same table the editor and the import read rather than
restating it, so a change to a cell's rules cannot leave the audit
checking an old copy.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentViewPolicy, ReviewSession
from app.services import session_lifecycle as lifecycle
from app.services.visibility_policies import (
    VisibilityPolicyError,
    decode_mode,
    valid_modes_for_cell,
)

# Ordered as the Band 3 editor presents them.
_WINDOWS: tuple[tuple[str, str], ...] = (
    ("while_ongoing", "Session ongoing"),
    ("after_release", "Responses released"),
)

_AUDIENCE_LABELS: dict[str, str] = {
    "peer_reviewer": "Reviewer",
    "reviewee": "Reviewee",
    "observer": "Observer",
}

# The stored audience and the role-pill class are not the same word:
# the reviewer audience is ``peer_reviewer``, and ``base.html`` styles
# ``.pill-role-reviewer``. Mapped here rather than in the template,
# where ``pill-role-{{ audience }}`` would render a class that does not
# exist and a pill with no styling — invisible in a review of the
# markup, obvious only on the page.
_AUDIENCE_PILL_SLUGS: dict[str, str] = {
    "peer_reviewer": "reviewer",
    "reviewee": "reviewee",
    "observer": "observer",
}

# A finding on one of these is reachable by somebody right now; on any
# other status the grant is closed by the lifecycle whatever the row
# says. Both still list — a draft session becomes a ready one — but the
# live ones sort first, because the reader is deciding what to do today.
_LIVE_STATUSES: frozenset[str] = frozenset({"ready", "expired"})


@dataclass(frozen=True)
class VisibilityAuditRow:
    """One offending ``(instrument, audience, window)`` cell."""

    session_id: int
    session_name: str
    session_code: str
    session_status: str
    instrument_label: str
    audience: str
    audience_label: str
    audience_slug: str
    """The ``.pill-role-*`` suffix ``base.html`` styles — see
    :data:`_AUDIENCE_PILL_SLUGS`."""

    window_label: str
    stored: str
    """What the pair holds, in the operator's vocabulary — a mode name,
    or a description of a pair that is not a mode at all."""

    reason: str
    live: bool


def _cell_finding(
    audience: str, window: str, granularity: str | None, identification: str | None
) -> tuple[str, str] | None:
    """Return ``(stored, reason)`` when this cell is a finding.

    Three shapes, matching the import guard in
    ``session_config_io/_apply_parse``. They are kept distinct because
    ``decode_pair_to_mode`` reads the first two as "off", so collapsing
    them would report a half-authored cell as a legal ``None`` and say
    nothing at all.
    """
    if (granularity is None) != (identification is None):
        return (
            "half-set pair",
            f"{'Granularity' if granularity else 'Identification'} set, "
            "the other empty — set both or neither",
        )
    if granularity is None:
        mode: str | None = None
    else:
        try:
            mode = decode_mode(granularity, identification or "")
        except VisibilityPolicyError:
            return (
                f"{granularity} + {identification}",
                "Not a valid stored mode — the reserved-incoherent pair",
            )
    allowed = valid_modes_for_cell(audience, window)
    if mode in allowed:
        return None
    legal = ", ".join(
        "off" if v is None else str(v) for v in sorted(allowed, key=str)
    )
    return (
        "off" if mode is None else mode,
        f"Cell accepts only {legal}",
    )


def build_visibility_audit_rows(db: Session) -> list[VisibilityAuditRow]:
    """Every stored visibility cell that the Band 3 editor would refuse.

    One query across the workspace, joined to instruments and sessions;
    the decode is in Python against a six-entry table. Empty is the
    expected result, and the card says so in words rather than rendering
    an empty table.
    """
    rows = db.execute(
        select(InstrumentViewPolicy, Instrument, ReviewSession)
        .join(Instrument, Instrument.id == InstrumentViewPolicy.instrument_id)
        .join(ReviewSession, ReviewSession.id == Instrument.session_id)
    ).all()

    findings: list[VisibilityAuditRow] = []
    for policy, instrument, review_session in rows:
        for window, window_label in _WINDOWS:
            finding = _cell_finding(
                policy.audience,
                window,
                getattr(policy, f"{window}_granularity"),
                getattr(policy, f"{window}_identification"),
            )
            if finding is None:
                continue
            stored, reason = finding
            findings.append(
                VisibilityAuditRow(
                    session_id=review_session.id,
                    session_name=review_session.name,
                    session_code=review_session.code,
                    session_status=review_session.status,
                    instrument_label=instrument.name or f"#{instrument.order}",
                    audience=policy.audience,
                    audience_label=_AUDIENCE_LABELS.get(
                        policy.audience, policy.audience
                    ),
                    audience_slug=_AUDIENCE_PILL_SLUGS.get(
                        policy.audience, "reviewer"
                    ),
                    window_label=window_label,
                    stored=stored,
                    reason=reason,
                    live=(
                        review_session.status in _LIVE_STATUSES
                        and not lifecycle.is_archived(review_session)
                    ),
                )
            )

    findings.sort(
        key=lambda r: (not r.live, r.session_code, r.instrument_label, r.audience)
    )
    return findings
