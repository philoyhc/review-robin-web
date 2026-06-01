"""Zip bundles — setup + responses.

Two complementary archives:

- **Setup bundle** (``build_setup_bundle``) — Reviewers /
  Reviewees / Relationships / Settings only. Backs the
  Session Home Extract Setup card's "Zip all" tile: the
  porting / archival shape Quick Setup can re-ingest. Renamed
  from "session bundle" on 2026-05-29 when the response data
  moved off the Session Home card to its own Operations-strip
  tab (per ``guide/extract_data.md``).
- **Responses bundle** (``build_responses_bundle``) — the
  unified Responses CSV + bundle-only reviewer/reviewee stats
  + one ``instrument_{n}.csv`` per instrument sorted
  reviewee-first. Backs the new Extract data Operations-strip
  tab's "Zip all" button.

The Sys-Admin-gated audit-events extract is deliberately not in
either bundle (it lives behind the diagnostics doorway).
"""

from __future__ import annotations

import io
import zipfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.services import responses as responses_service
from app.services.extracts import filename, stream_csv
from app.services.extracts.entity_stats_extract import build_entity_stats
from app.services.extracts.by_instrument_extract import (
    by_instrument_filename_slug,
    serialize_by_instrument,
)
from app.services.extracts.observers_extract import serialize_observers
from app.services.extracts.relationships_extract import serialize_relationships
from app.services.extracts.responses_extract import (
    serialize_responses,
    serialize_responses_for_instrument,
)
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.session_config_io import HEADER as SETTINGS_HEADER
from app.services.session_config_io import serialize_session_config

__all__ = [
    "build_setup_bundle",
    "build_responses_bundle",
    "build_by_instrument_bundle",
]


def build_setup_bundle(
    db: Session, review_session: ReviewSession
) -> tuple[bytes, dict[str, int]]:
    """Build the setup-only zip for ``review_session``.

    Returns ``(zip_bytes, counts)`` — the zip archive bytes and a
    per-CSV data-row-count map for the
    ``session.setup_bundle_extracted`` audit envelope. Each CSV
    is named ``{code}_{kind}.csv`` inside the archive, matching
    the per-entity downloads.
    """
    reviewers = list(serialize_reviewers(db, review_session))
    reviewees = list(serialize_reviewees(db, review_session))
    relationships = list(serialize_relationships(db, review_session))

    # Settings serialiser returns Row objects; the CSV prepends the
    # 3-column header, exactly as the standalone Settings route does.
    settings_rows = serialize_session_config(db, review_session)
    settings_csv: list[tuple[str, ...]] = [SETTINGS_HEADER]
    settings_csv.extend(
        (r.field, r.value, r.data_type) for r in settings_rows
    )

    members: dict[str, list[tuple[str, ...]]] = {
        "reviewers": reviewers,
        "reviewees": reviewees,
        "relationships": relationships,
        "settings": settings_csv,
    }
    counts = {
        "reviewers": max(0, len(reviewers) - 1),
        "reviewees": max(0, len(reviewees) - 1),
        "relationships": max(0, len(relationships) - 1),
        "settings": len(settings_rows),
    }
    # Observers ride into the bundle only when the session's
    # ``observers_enabled`` toggle is on, matching the Extract
    # Setup card's per-row gate. The CSV round-trips with the
    # Quick Setup Observers slot + the Observers Setup page.
    if review_session.observers_enabled:
        observers = list(serialize_observers(db, review_session))
        members["observers"] = observers
        counts["observers"] = max(0, len(observers) - 1)
    buffer = _write_archive(review_session, members)
    return buffer, counts


def _shape_filename_slug(name: str) -> str:
    """Filesystem-safe slug for a saved Data shape's
    filename inside the responses bundle. Mirrors
    ``_slug_shape_name`` in the route layer + the
    ``by_instrument_filename_slug`` shape: alphanumerics +
    ``-`` + ``_``, collapsing other runs to ``_``. Empty
    slug falls back to ``shape``."""
    import re

    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return slug or "shape"


def build_responses_bundle(
    db: Session,
    review_session: ReviewSession,
    *,
    include_data_shapes: bool = True,
) -> tuple[bytes, dict[str, int]]:
    """Build the responses-only zip for ``review_session``.

    Returns ``(zip_bytes, counts)`` — the zip archive bytes and a
    per-CSV data-row-count map for the
    ``session.responses_bundle_extracted`` audit envelope.
    Members: the unified ``responses.csv`` + ``reviewer_stats.csv``
    + ``reviewee_stats.csv`` + one ``instrument_{n}.csv`` per
    instrument, plus (when ``include_data_shapes``) one CSV per
    saved Data shape named ``{code}_{slug(name)}.csv``. The
    Data shaper chip on the intro card drives the
    ``include_data_shapes`` flag via a ``?data_shapes=0``
    query param on the route.
    """
    from app.db.models import DataShape
    from app.services.extracts.data_shape_extract import (
        build_shape_rows,
    )

    responses = list(serialize_responses(db, review_session))
    reviewer_stats, reviewee_stats = build_entity_stats(
        db, review_session
    )

    members: dict[str, list[tuple[str, ...]]] = {
        "responses": responses,
        "reviewer_stats": reviewer_stats,
        "reviewee_stats": reviewee_stats,
    }

    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    for position, instrument in enumerate(instruments, start=1):
        members[f"instrument_{position}"] = list(
            serialize_responses_for_instrument(
                db, review_session, instrument, position=position
            )
        )

    data_shape_count = 0
    if include_data_shapes:
        shapes = list(
            db.execute(
                select(DataShape)
                .where(DataShape.session_id == review_session.id)
                .order_by(DataShape.name)
            ).scalars()
        )
        used_slugs: set[str] = set()
        for shape in shapes:
            base_slug = _shape_filename_slug(shape.name)
            candidate = base_slug
            n = 2
            while candidate in used_slugs or candidate in members:
                candidate = f"{base_slug}_{n}"
                n += 1
            used_slugs.add(candidate)
            members[candidate] = list(
                build_shape_rows(db, review_session, shape)
            )
            data_shape_count += 1

    buffer = _write_archive(review_session, members)

    counts = {
        "responses": responses_service.session_response_count(
            db, review_session.id
        ),
        "reviewer_stats": max(0, len(reviewer_stats) - 1),
        "reviewee_stats": max(0, len(reviewee_stats) - 1),
        "instrument_files": len(instruments),
        "data_shapes": data_shape_count,
    }
    return buffer, counts


def build_by_instrument_bundle(
    db: Session,
    review_session: ReviewSession,
    *,
    instrument_ids: set[int] | None = None,
    include_metadata: bool = True,
    include_empty_assignments: bool = True,
) -> tuple[bytes, dict[str, int]]:
    """Build the By-instrument zip for ``review_session``.

    One CSV per included instrument, named
    ``{code}_by_instrument_{slug}.csv`` where ``{slug}`` is the
    instrument's short label (or the ``Instrument_{N}`` fallback)
    sanitised for filesystem safety. Each CSV carries a meta
    header + the wide-format data table — see
    ``by_instrument_extract.py``.

    The three options gate the By-instrument card's chip row:

    * ``instrument_ids`` — when provided, only these instruments
      ship. ``None`` (default) = every instrument on the session.
      Position numbering follows the session-order sequence
      regardless of which subset is selected, so the
      ``Instrument_{N}`` fallback stays stable as the operator
      toggles chips on / off.
    * ``include_metadata`` — when False, each CSV skips the meta
      header block (and the blank separator row) and starts
      directly with the data-table header.
    * ``include_empty_assignments`` — when False, each CSV's
      data table omits assignment rows that have no responses.

    Returns ``(zip_bytes, counts)`` where ``counts`` carries
    ``{"instrument_files": N}`` (the actually-shipped count
    post-filter) for the
    ``session.by_instrument_bundle_extracted`` audit envelope.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )

    code = (review_session.code or "session").strip() or "session"
    used_slugs: set[str] = set()
    shipped = 0
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for position, instrument in enumerate(instruments, start=1):
            if (
                instrument_ids is not None
                and instrument.id not in instrument_ids
            ):
                continue
            slug = by_instrument_filename_slug(
                instrument, position, used=used_slugs
            )
            rows = list(
                serialize_by_instrument(
                    db,
                    review_session,
                    instrument,
                    position=position,
                    include_metadata=include_metadata,
                    include_empty_assignments=include_empty_assignments,
                )
            )
            archive.writestr(
                f"{code}_by_instrument_{slug}.csv",
                b"".join(stream_csv(rows)),
            )
            shipped += 1

    counts = {"instrument_files": shipped}
    return buffer.getvalue(), counts


def _write_archive(
    review_session: ReviewSession,
    members: dict[str, list[tuple[str, ...]]],
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for kind, rows in members.items():
            archive.writestr(
                filename(review_session, kind),
                b"".join(stream_csv(rows)),
            )
    return buffer.getvalue()
