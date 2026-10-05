"""Zip bundles — setup + responses.

Two complementary archives:

- **Setup bundle** (``build_setup_bundle``) — Reviewers /
  Reviewees / Relationships / Settings only. Backs the
  Session Home Extract Setup card's "Zip all" tile: the
  porting / archival shape Quick Setup can re-ingest. Renamed
  from "session bundle" on 2026-05-29 when the response data
  moved off the Session Home card to its own Operations-strip
  tab (per ``guide/archive/extract_data.md``).
- **Responses bundle** (``build_responses_bundle``) — the
  unified Responses CSV, which Rehydrate reads, plus the files
  each lens card on the Extract data tab downloads, as that card
  is configured. Backs the tab's intro-card "Zip all" button;
  the card's chips pick which lens cards ride along.

The Sys-Admin-gated audit-events extract is deliberately not in
either bundle (it lives behind the diagnostics doorway).
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataShape, Instrument, ReviewSession
from app.services import responses as responses_service
from app.services.extracts import filename, stream_csv
from app.services.extracts.by_instrument_extract import (
    by_instrument_filename_slug,
    serialize_by_instrument,
)
from app.services.extracts.data_shape_extract import (
    build_shape_rows,
    shape_filename,
)
from app.services.extracts.entity_metadata_extract import (
    SELF_REVIEW_HANDLING_DEFAULT,
    build_reviewee_metadata,
    build_reviewer_metadata,
    metadata_filename,
)
from app.services.extracts.observers_extract import serialize_observers
from app.services.extracts.participant_tokens_extract import (
    serialize_participant_tokens,
)
from app.services.extracts.relationships_extract import serialize_relationships
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.session_config_io import HEADER as SETTINGS_HEADER
from app.services.session_config_io import serialize_session_config

__all__ = [
    "build_setup_bundle",
    "build_responses_bundle",
    "build_by_instrument_bundle",
    "ByInstrumentOptions",
    "MetadataOptions",
]


@dataclass(frozen=True)
class ByInstrumentOptions:
    """The By instrument card's chip row, as its Zip-all route
    reads it: ``instrument_ids`` ``None`` ships every instrument."""

    instrument_ids: set[int] | None = None
    include_metadata: bool = True
    include_empty_assignments: bool = True


@dataclass(frozen=True)
class MetadataOptions:
    """A response metadata card's chip row, as its Download route
    reads it: ``instrument_ids`` ``None`` ships no per-field blocks,
    only the cross-instrument totals."""

    instrument_ids: set[int] | None = None
    all_rows: bool = True
    self_review_handling: str = SELF_REVIEW_HANDLING_DEFAULT


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


def build_responses_bundle(
    db: Session,
    review_session: ReviewSession,
    *,
    by_instrument: ByInstrumentOptions | None = ByInstrumentOptions(),
    reviewer_metadata: MetadataOptions | None = MetadataOptions(),
    reviewee_metadata: MetadataOptions | None = MetadataOptions(),
    include_data_shapes: bool = True,
    include_participant_tokens: bool = True,
) -> tuple[bytes, dict[str, int]]:
    """Build the Extract data tab's Zip-all archive.

    Always ``{code}_responses.csv``, the file Rehydrate needs. Then,
    for each intro-card chip that is on, exactly the files that
    card's own button downloads, under the same names:

    * ``by_instrument`` — the By instrument card's Zip all,
      flattened: one ``{code}_by_instrument_{slug}.csv`` per chosen
      instrument.
    * ``reviewer_metadata`` / ``reviewee_metadata`` — the card's
      Download, ``{code}_reviewer_metadata{suffix}.csv``.
    * ``include_data_shapes`` — every saved shape's Download,
      ``{code}_{slug}{suffix}.csv``, each with its own saved chips.
    * ``include_participant_tokens`` — the Token keys card's
      ``{code}_participant_tokens.csv``, only when the session has
      ``observers_enabled`` on, as that card only renders then.

    ``None`` for a card's options leaves its files out. A name that
    repeats an earlier member's (a shape named after another file)
    gains ``_2``, ``_3`` before the extension rather than replacing it.

    Returns ``(zip_bytes, counts)`` for the
    ``session.responses_bundle_extracted`` audit envelope:
    response rows, files per card, and token rows.
    """
    members: list[tuple[str, list[tuple[str, ...]]]] = [
        (
            filename(review_session, "responses"),
            list(serialize_responses(db, review_session)),
        )
    ]

    by_instrument_files = 0
    if by_instrument is not None:
        for name, rows in _by_instrument_members(
            db, review_session, by_instrument
        ):
            members.append((name, rows))
            by_instrument_files += 1

    metadata_files = {"reviewer_metadata": 0, "reviewee_metadata": 0}
    for kind, options, build, all_kwarg in (
        (
            "reviewer_metadata",
            reviewer_metadata,
            build_reviewer_metadata,
            "all_reviewers",
        ),
        (
            "reviewee_metadata",
            reviewee_metadata,
            build_reviewee_metadata,
            "all_reviewees",
        ),
    ):
        if options is None:
            continue
        rows = build(
            db,
            review_session,
            instrument_ids=options.instrument_ids,
            self_review_handling=options.self_review_handling,
            **{all_kwarg: options.all_rows},
        )
        members.append(
            (
                metadata_filename(
                    review_session, kind, options.self_review_handling
                ),
                rows,
            )
        )
        metadata_files[kind] = 1

    data_shape_files = 0
    if include_data_shapes:
        shape_members = _data_shape_members(db, review_session)
        members.extend(shape_members)
        data_shape_files = len(shape_members)

    # Token keys ride only when the session has observers: the
    # tokens are the deanonymization key for the observer-side
    # Anonymized output and have no other consumer, and the Token
    # keys card itself renders only then.
    participant_tokens_rows = 0
    if include_participant_tokens and review_session.observers_enabled:
        token_rows = list(serialize_participant_tokens(db, review_session))
        members.append(
            (filename(review_session, "participant_tokens"), token_rows)
        )
        participant_tokens_rows = max(0, len(token_rows) - 1)

    counts = {
        "responses": responses_service.session_response_count(
            db, review_session.id
        ),
        "by_instrument_files": by_instrument_files,
        "reviewer_metadata_files": metadata_files["reviewer_metadata"],
        "reviewee_metadata_files": metadata_files["reviewee_metadata"],
        "data_shapes": data_shape_files,
        "participant_tokens": participant_tokens_rows,
    }
    return _zip_named(members), counts


def _data_shape_members(
    db: Session, review_session: ReviewSession
) -> list[tuple[str, list[tuple[str, ...]]]]:
    """Every saved shape's Download, ``{code}_{slug}{suffix}.csv``,
    each with its own saved chips, ordered by name then id."""
    shapes = db.execute(
        select(DataShape)
        .where(DataShape.session_id == review_session.id)
        .order_by(DataShape.name, DataShape.id)
    ).scalars()
    return [
        (
            shape_filename(review_session, shape),
            list(build_shape_rows(db, review_session, shape)),
        )
        for shape in shapes
    ]


def build_data_shapes_bundle(
    db: Session, review_session: ReviewSession
) -> tuple[bytes, dict[str, int]]:
    """The Data shaper card's Zip all: every saved shape's file, as
    its own Download names it, and nothing else (findings D13,
    2026-10-03). Returns ``(zip_bytes, {"data_shapes": n})``."""
    members = _data_shape_members(db, review_session)
    return _zip_named(members), {"data_shapes": len(members)}


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
    instrument's short label (or the ``Instrument_{session_seq}`` fallback)
    sanitised for filesystem safety. Each CSV carries a meta
    header + the wide-format data table — see
    ``by_instrument_extract.py``.

    The three options gate the By-instrument card's chip row:

    * ``instrument_ids`` — when provided, only these instruments
      ship. ``None`` (default) = every instrument on the session.
      The ``Instrument_{session_seq}`` fallback is fixed per
      instrument, so it stays stable as the operator toggles chips
      on / off.
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
    members = list(
        _by_instrument_members(
            db,
            review_session,
            ByInstrumentOptions(
                instrument_ids=instrument_ids,
                include_metadata=include_metadata,
                include_empty_assignments=include_empty_assignments,
            ),
        )
    )
    return _zip_named(members), {"instrument_files": len(members)}


def _by_instrument_members(
    db: Session,
    review_session: ReviewSession,
    options: ByInstrumentOptions,
) -> Iterator[tuple[str, list[tuple[str, ...]]]]:
    """``(name, rows)`` per instrument the By instrument card would
    ship, in instrument order, named
    ``{code}_by_instrument_{slug}.csv``."""
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    code = (review_session.code or "session").strip() or "session"
    used_slugs: set[str] = set()
    for position, instrument in enumerate(instruments, start=1):
        if (
            options.instrument_ids is not None
            and instrument.id not in options.instrument_ids
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
                include_metadata=options.include_metadata,
                include_empty_assignments=options.include_empty_assignments,
            )
        )
        yield f"{code}_by_instrument_{slug}.csv", rows


def _zip_named(members: list[tuple[str, list[tuple[str, ...]]]]) -> bytes:
    """Write ``(name, rows)`` members in order. A name already
    taken gains ``_2``, ``_3`` … before ``.csv``, so no member
    silently replaces another."""
    used: set[str] = set()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, rows in members:
            stem, dot, ext = name.rpartition(".")
            candidate, n = name, 2
            while candidate in used:
                candidate = f"{stem}_{n}{dot}{ext}"
                n += 1
            used.add(candidate)
            archive.writestr(candidate, b"".join(stream_csv(rows)))
    return buffer.getvalue()


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
