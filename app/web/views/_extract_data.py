"""Extract Data card on Session Home — five per-entity rows
(Reviewers / Reviewees / Assignments / Responses / Session settings)
plus a Zip-all bundle footer.

Slice 2 of the §12.B ladder (``guide/major_refactor.md``).

Read-only by nature: Segment 11H shipped every row inert; Segment
12A's PRs flip ``is_wired`` and supply ``download_url`` per row.
The card stays interactive in every lifecycle state (no lock-card
wrap).

Source range in pre-PR-2 ``_legacy.py``: lines 1272-1414.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.services import (
    assignments,
    csv_imports,
    responses as responses_service,
)


@dataclass(frozen=True)
class ExtractDataRow:
    """One row inside the Extract Data card on Session Home.

    12A's PRs flip ``is_wired`` and supply ``download_url`` per row;
    11H ships every row inert.
    """

    key: str
    """Stable identifier — ``settings`` / ``reviewers`` / ``reviewees``
    / ``assignments`` / ``responses`` / ``bundle``. DOM id is
    ``#extract-data-{key}``."""

    label: str

    filename: str
    """Final filename the download will carry, e.g.
    ``session-CS101-reviewers.csv``. Surfaced to the operator as a
    secondary line so they know what to expect."""

    count: int
    count_summary: str

    is_wired: bool
    download_url: str | None
    coming_in: str | None

    @property
    def show_count(self) -> bool:
        """True for the four entity rows whose count is operator-
        meaningful inline alongside the title (Reviewers / Reviewees /
        Assignments / Responses). Session settings + the zip-bundle row
        keep the title-only treatment."""
        return self.key in ("reviewers", "reviewees", "assignments", "responses")


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
    assignment_count = assignments.existing_count(db, sid)
    response_count = responses_service.session_response_count(db, sid)
    # 12A-1 PR 3 — assignments CSV is manual-mode only. Per
    # Scenario A "snapshot the inputs, never the outputs",
    # rule-based / full-matrix sessions don't export rows; the
    # destination operator re-runs the same generation path
    # (RuleSet pick + Generate, or Full Matrix).
    assignment_mode = (review_session.assignment_mode or "").strip()
    assignments_is_manual = assignment_mode == "manual"
    if assignments_is_manual:
        assignments_coming_in: str | None = None
    elif assignment_mode == "rule_based":
        assignments_coming_in = (
            "Assignments derived from a RuleSet — re-run "
            "Generate on the destination session against the "
            "same RuleSet selection. Manual export only."
        )
    elif assignment_mode == "full_matrix":
        assignments_coming_in = (
            "Assignments derived from Full Matrix — re-run the "
            "Full Matrix action on the destination session. "
            "Manual export only."
        )
    else:
        assignments_coming_in = (
            "No assignments generated yet — manual export only."
        )
    instrument_count = len(
        list(
            db.execute(
                select(Instrument).where(Instrument.session_id == sid)
            ).scalars()
        )
    )

    rows = [
        ExtractDataRow(
            key="reviewers",
            label="Reviewers",
            filename=f"{code}_reviewers.csv",
            count=reviewer_count,
            count_summary=_extract_summary("reviewer", reviewer_count),
            is_wired=True,
            download_url=f"/operator/sessions/{sid}/export/reviewers.csv",
            coming_in=None,
        ),
        ExtractDataRow(
            key="assignments",
            label="Assignments",
            filename=f"{code}_assignments.csv",
            count=assignment_count,
            count_summary=_extract_summary("assignment", assignment_count),
            is_wired=assignments_is_manual,
            download_url=(
                f"/operator/sessions/{sid}/export/assignments.csv"
                if assignments_is_manual
                else None
            ),
            coming_in=assignments_coming_in,
        ),
        ExtractDataRow(
            key="reviewees",
            label="Reviewees",
            filename=f"{code}_reviewees.csv",
            count=reviewee_count,
            count_summary=_extract_summary("reviewee", reviewee_count),
            is_wired=True,
            download_url=f"/operator/sessions/{sid}/export/reviewees.csv",
            coming_in=None,
        ),
        ExtractDataRow(
            key="responses",
            label="Responses",
            filename=f"session-{code}-responses.csv",
            count=response_count,
            count_summary=_extract_summary("response", response_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 5",
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

    bundle = ExtractDataRow(
        key="bundle",
        label="Zip all",
        filename=f"session-{code}-export.zip",
        count=sum(r.count for r in rows),
        count_summary="zip of all five CSVs above",
        is_wired=False,
        download_url=None,
        coming_in="Wired in Segment 12A PR 6",
    )

    return ExtractDataContext(rows=rows, bundle=bundle)


def _extract_summary(noun: str, count: int) -> str:
    if count == 0:
        return f"0 {noun}s"
    if count == 1:
        return f"1 {noun}"
    return f"{count} {noun}s"
