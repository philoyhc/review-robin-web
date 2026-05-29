"""Extract Setup card on Session Home — four per-entity rows
(Reviewers / Reviewees / Relationships / Session settings) plus
a Zip-all bundle footer.

The card was renamed from "Extract Data" to "Extract Setup" on
2026-05-29 to mark it as the **porting / archival** surface —
the CSVs an operator would feed back into Quick Setup, or hand
off to a colleague cloning the session. The Responses row moved
to the new **Extract data** Operations-strip tab (per
``guide/extract_data.md``), which is where fine-grained shaping
of response data lives. The Zip-all bundle's contents are
deliberately unchanged in this PR — it still includes
responses + reviewer/reviewee stats + per-instrument files
(see ``app/services/extracts/zip_bundle.py``); the bundle slim
is a follow-up PR.

Slice 2 of the §12.B ladder (``guide/archive/major_refactor.md``).

Read-only by nature: Segment 11H shipped every row inert; Segment
12A's PRs flip ``is_wired`` and supply ``download_url`` per row.
12A-3 PR 1 added the Relationships row; PR 2 retired the
Assignments row (assignments are derived post-15D — output, not
input — so the download has no place in a porting bundle) and
reordered the row list to the target left/right column layout.
The card stays interactive in every lifecycle state (no
lock-card wrap).

Audit log download is *deliberately* not surfaced here — it
lives at ``GET /operator/sessions/{id}/export/audit_log.csv``
(Segment 12B PR 1) but per industry best practice (GitHub,
Stripe, Slack, Notion) audit data belongs behind an admin /
diagnostics doorway, not alongside everyday data exports. The
tile relocates to the Sys Admin page when Segment 16 ships.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.services import (
    csv_imports,
    relationships as relationships_service,
)


@dataclass(frozen=True)
class ExtractDataRow:
    """One row inside the Extract Data card on Session Home."""

    key: str
    """Stable identifier — ``reviewers`` / ``reviewees`` /
    ``relationships`` / ``settings`` / ``bundle``. DOM id is
    ``#extract-data-{key}`` (DOM ids kept stable across the
    2026-05-29 card rename to avoid a wider sweep)."""

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
        Reviewees / Relationships). Session settings + the
        zip-bundle row keep the title-only treatment."""
        return self.key in (
            "reviewers",
            "reviewees",
            "relationships",
        )


@dataclass(frozen=True)
class ExtractDataContext:
    rows: list[ExtractDataRow]
    bundle: ExtractDataRow
    col_one: list[ExtractDataRow]
    col_two: list[ExtractDataRow]


def build_extract_data_context(
    db: Session, review_session: ReviewSession
) -> ExtractDataContext:
    sid = review_session.id
    code = review_session.code or "session"

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    relationship_count = relationships_service.existing_count(db, sid)
    instrument_count = len(
        list(
            db.execute(
                select(Instrument).where(Instrument.session_id == sid)
            ).scalars()
        )
    )

    # Two-column layout matching the Quick Setup slot placement:
    #
    #   Col 1            |  Col 2
    #   ---------------- | ----------------
    #   Reviewers        |  Relationships
    #   Reviewees        |  Session settings
    #                    |  Zip all
    #
    # The template renders the two columns as explicit ``<div>``
    # children. Per-entity rows (Reviewers / Reviewees /
    # Relationships) grey out when the count is 0 — there's
    # nothing to download. Settings stays always-live: session
    # metadata always exists even on a freshly-created draft.
    # The Zip-all bundle contains only the four setup CSVs (per
    # ``guide/extract_data.md``); response data downloads live on
    # the Extract data Operations-strip tab.
    col_one = [
        _entity_row(
            key="reviewers",
            label="Reviewers",
            noun="reviewer",
            count=reviewer_count,
            sid=sid,
            code=code,
        ),
        _entity_row(
            key="reviewees",
            label="Reviewees",
            noun="reviewee",
            count=reviewee_count,
            sid=sid,
            code=code,
        ),
    ]
    col_two = [
        _entity_row(
            key="relationships",
            label="Relationships",
            noun="relationship",
            count=relationship_count,
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
    ]
    # Flat ``rows`` preserves the historical iteration contract
    # (callers + tests). Read column-major: col 1 (rows[0:2])
    # then col 2 (rows[2:4]).
    rows = col_one + col_two

    bundle = ExtractDataRow(
        key="bundle",
        label="Zip all",
        filename=f"{code}_setup.zip",
        count=sum(r.count for r in rows),
        count_summary="zip of the four setup CSVs",
        is_wired=True,
        download_url=f"/operator/sessions/{sid}/export/bundle.zip",
        coming_in=None,
    )

    return ExtractDataContext(
        rows=rows, bundle=bundle, col_one=col_one, col_two=col_two
    )


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
