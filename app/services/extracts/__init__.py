"""Per-session CSV extracts (Segment 12A-1 + 12A-3).

Shared plumbing for the five downloads on the Extract Data
card — filename convention + a chunked CSV-streaming helper.
The per-extract serialisers live alongside this module:

- ``app/services/session_config_io/`` — Settings CSV
  (3-column ``field,value,data_type`` shape).
- ``app/services/extracts/reviewers_extract.py`` — Reviewers
  CSV (12A-1 PR 2).
- ``app/services/extracts/reviewees_extract.py`` — Reviewees
  CSV (12A-1 PR 2).
- ``app/services/extracts/relationships_extract.py`` —
  Relationships CSV (12A-3 PR 1).
- ``app/services/extracts/observers_extract.py`` — Observers
  CSV. Closes the Extract Setup leg of L2 from
  ``guide/participant_model_remainder.md``.
- ``app/services/extracts/responses_extract.py`` — Responses
  CSV (12A-1 PR 4).

The Manual Assignments extract from 12A-1 PR 3 retired in
12A-3 PR 2.

Plan: ``guide/archive/segment_12A-1_export.md``,
``guide/segment_12A-3_export_import_updates.md``.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from typing import Any

from app.db.models import ReviewSession

__all__ = ["filename", "stream_csv"]


def filename(session: ReviewSession, kind: str) -> str:
    """The canonical ``{code}_{kind}.csv`` filename for an extract.

    Centralised so every route reaches for the same string.
    """

    code = (session.code or "session").strip() or "session"
    return f"{code}_{kind}.csv"


def stream_csv(rows: Iterable[Iterable[Any]]) -> Iterator[bytes]:
    """Yield CSV bytes for ``rows`` over a chunked ``StringIO``.

    Each yielded chunk is a UTF-8-encoded CSV byte string. The
    helper writes each row independently and then drains the
    buffer so memory stays flat for sessions with thousands of
    rows. Headers are just another row — the caller is
    responsible for prepending them.
    """

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(row)
        chunk = buffer.getvalue()
        if not chunk:
            continue
        yield chunk.encode("utf-8")
        buffer.seek(0)
        buffer.truncate()
