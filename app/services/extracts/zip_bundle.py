"""Zip-all bundle — Segment 18D PR E1 / 18H Part 3.

Collects the operator-facing per-session CSVs — Reviewers,
Reviewees, Relationships, Responses, Settings, plus the two
bundle-only Reviewer / Reviewee stats CSVs (18H Part 3) — into one
in-memory zip archive. Backs the Extract Data card's "Zip all"
tile: one download for porting a whole session.

The Sys-Admin-gated audit-events extract is deliberately not in
the bundle (it lives behind the diagnostics doorway).
"""

from __future__ import annotations

import io
import zipfile

from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services import responses as responses_service
from app.services.extracts import filename, stream_csv
from app.services.extracts.entity_stats_extract import build_entity_stats
from app.services.extracts.relationships_extract import serialize_relationships
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.session_config_io import HEADER as SETTINGS_HEADER
from app.services.session_config_io import serialize_session_config

__all__ = ["build_session_bundle"]


def build_session_bundle(
    db: Session, review_session: ReviewSession
) -> tuple[bytes, dict[str, int]]:
    """Build the all-CSVs zip for ``review_session``.

    Returns ``(zip_bytes, counts)`` — the zip archive bytes and a
    per-CSV data-row-count map for the ``session.bundle_extracted``
    audit envelope. Each CSV is named ``{code}_{kind}.csv`` inside
    the archive, matching the per-entity downloads.
    """
    reviewers = list(serialize_reviewers(db, review_session))
    reviewees = list(serialize_reviewees(db, review_session))
    relationships = list(serialize_relationships(db, review_session))
    responses = list(serialize_responses(db, review_session))

    # Settings serialiser returns Row objects; the CSV prepends the
    # 3-column header, exactly as the standalone Settings route does.
    settings_rows = serialize_session_config(db, review_session)
    settings_csv: list[tuple[str, ...]] = [SETTINGS_HEADER]
    settings_csv.extend(
        (r.field, r.value, r.data_type) for r in settings_rows
    )

    # Bundle-only stats CSVs (18H Part 3) — roster shape plus
    # aggregate response-activity columns; not individual downloads.
    reviewer_stats, reviewee_stats = build_entity_stats(
        db, review_session
    )

    members: dict[str, list[tuple[str, ...]]] = {
        "reviewers": reviewers,
        "reviewees": reviewees,
        "relationships": relationships,
        "responses": responses,
        "settings": settings_csv,
        "reviewer_stats": reviewer_stats,
        "reviewee_stats": reviewee_stats,
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for kind, rows in members.items():
            archive.writestr(
                filename(review_session, kind),
                b"".join(stream_csv(rows)),
            )

    # Data-row counts (header / preamble excluded), matching how
    # each per-entity route counts its own download.
    counts = {
        "reviewers": max(0, len(reviewers) - 1),
        "reviewees": max(0, len(reviewees) - 1),
        "relationships": max(0, len(relationships) - 1),
        "responses": responses_service.session_response_count(
            db, review_session.id
        ),
        "settings": len(settings_rows),
        "reviewer_stats": max(0, len(reviewer_stats) - 1),
        "reviewee_stats": max(0, len(reviewee_stats) - 1),
    }
    return buffer.getvalue(), counts
