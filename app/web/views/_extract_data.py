"""Extract Data card on Session Home — five per-entity rows
(Reviewers / Reviewees / Relationships / Session settings /
Responses) plus a Zip-all bundle footer.

Slice 2 of the §12.B ladder (``guide/major_refactor.md``).

Read-only by nature: Segment 11H shipped every row inert; Segment
12A's PRs flip ``is_wired`` and supply ``download_url`` per row.
12A-3 PR 1 added the Relationships row; PR 2 retired the
Assignments row (assignments are derived post-15D — output, not
input — so the download has no place in a porting bundle) and
reordered the row list to the target left/right column layout.
The card stays interactive in every lifecycle state (no
lock-card wrap).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession
from app.services import (
    csv_imports,
    relationships as relationships_service,
    responses as responses_service,
)


@dataclass(frozen=True)
class ExtractDataRow:
    """One row inside the Extract Data card on Session Home."""

    key: str
    """Stable identifier — ``reviewers`` / ``reviewees`` /
    ``relationships`` / ``settings`` / ``responses`` / ``bundle``.
    DOM id is ``#extract-data-{key}``."""

    label: str

    filename: str
    """Final filename the download will carry, e.g.
    ``CS101_reviewers.csv``. Surfaced to the operator as a
    secondary line so they know what to expect."""

    count: int
    count_summary: str

    is_wired: bool
    download_url: str | None
    coming_in: str | None

    @property
    def show_count(self) -> bool:
        """True for the per-entity rows whose count is operator-
        meaningful inline alongside the title (Reviewers /
        Reviewees / Relationships / Responses / Audit log).
        Session settings + the zip-bundle row keep the title-only
        treatment."""
        return self.key in (
            "reviewers",
            "reviewees",
            "relationships",
            "responses",
            "audit_log",
        )


@dataclass(frozen=True)
class ExtractDataContext:
    rows: list[ExtractDataRow]
    bundle: ExtractDataRow


def build_extract_data_context(
    db: Session, review_session: ReviewSession
) -> ExtractDataContext:
    sid = review_session.id
    code = review_session.code or "session"

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    relationship_count = relationships_service.existing_count(db, sid)
    response_count = responses_service.session_response_count(db, sid)
    audit_event_count = len(
        list(
            db.execute(
                select(AuditEvent).where(AuditEvent.session_id == sid)
            ).scalars()
        )
    )
    instrument_count = len(
        list(
            db.execute(
                select(Instrument).where(Instrument.session_id == sid)
            ).scalars()
        )
    )

    # Row order = DOM order. The ``extract-data-grid`` CSS wraps
    # row-major in a 2-column grid, so this list lays out as:
    #
    #   Reviewers       |  Session settings
    #   Reviewees       |  Responses
    #   Relationships   |  Audit log
    #                   |  Zip all  (inert)
    #
    # Left column = per-entity rosters (operator-uploaded porting
    # inputs). Right column = session-level outputs (settings,
    # downstream-analysis, audit history, future bundle).
    # Per-entity rows (Reviewers / Reviewees / Relationships /
    # Responses / Audit log) grey out when the count is 0 — there's
    # nothing to download. Settings stays always-live: session
    # metadata always exists even on a freshly-created draft.
    rows = [
        _entity_row(
            key="reviewers",
            label="Reviewers",
            noun="reviewer",
            count=reviewer_count,
            sid=sid,
            code=code,
        ),
        ExtractDataRow(
            key="settings",
            label="Session settings",
            filename=f"{code}_settings.csv",
            count=instrument_count,
            count_summary=_extract_summary("instrument", instrument_count),
            is_wired=True,
            download_url=f"/operator/sessions/{sid}/export/settings.csv",
            coming_in=None,
        ),
        _entity_row(
            key="reviewees",
            label="Reviewees",
            noun="reviewee",
            count=reviewee_count,
            sid=sid,
            code=code,
        ),
        _entity_row(
            key="responses",
            label="Responses",
            noun="response",
            count=response_count,
            sid=sid,
            code=code,
        ),
        _entity_row(
            key="relationships",
            label="Relationships",
            noun="relationship",
            count=relationship_count,
            sid=sid,
            code=code,
        ),
        _entity_row(
            key="audit_log",
            label="Audit log",
            noun="audit event",
            count=audit_event_count,
            sid=sid,
            code=code,
        ),
    ]

    bundle = ExtractDataRow(
        key="bundle",
        label="Zip all",
        filename=f"session-{code}-export.zip",
        count=sum(r.count for r in rows),
        count_summary="zip of all six CSVs above",
        is_wired=False,
        download_url=None,
        coming_in="Wired in Segment 12A PR 6",
    )

    return ExtractDataContext(rows=rows, bundle=bundle)


def _entity_row(
    *,
    key: str,
    label: str,
    noun: str,
    count: int,
    sid: int,
    code: str,
) -> ExtractDataRow:
    """Per-entity Extract Data row that greys out when ``count``
    is 0 — there's nothing to download yet. Once the operator
    populates the entity, the row goes live."""

    has_data = count > 0
    return ExtractDataRow(
        key=key,
        label=label,
        filename=f"{code}_{key}.csv",
        count=count,
        count_summary=_extract_summary(noun, count),
        is_wired=has_data,
        download_url=(
            f"/operator/sessions/{sid}/export/{key}.csv"
            if has_data
            else None
        ),
        coming_in=None if has_data else f"No {noun}s to download yet",
    )


def _extract_summary(noun: str, count: int) -> str:
    if count == 0:
        return f"0 {noun}s"
    if count == 1:
        return f"1 {noun}"
    return f"{count} {noun}s"
