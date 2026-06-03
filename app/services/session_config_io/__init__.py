"""Session settings export + import — Segment 12A-1 PR 1 + 12A-3 PR 3.

Produces the Settings CSV the Extract Data card on Session Home
serves at ``GET /operator/sessions/{id}/export/settings.csv`` and
applies one back via ``apply_session_config(db, session, rows)``.
3-column ``field,value,data_type`` shape; every row class
documented in ``guide/segment_12A-1_export.md`` /
``guide/segment_12A-2_import.md`` (the import contract is kept as
historical-reference; the actual delivery is 12A-3 PR 3).

``serialize_session_config(session)`` returns a deterministic
``list[Row]`` for a fully-loaded session; the route streams it
through ``app.services.extracts.stream_csv``.
``apply_session_config(db, session, rows)`` parses + applies the
inverse, returning an ``ApplyResult`` with counts on success or
errors on validation failure.

Inclusion rule (paraphrased from the segment doc):

    Snapshot the operator's typing — every per-session
    configuration field they would otherwise have to retype to
    set up an equivalent new session. Excludes
    machine-derived state (``status``, ``assignment_mode``,
    validation reports, lifecycle stamps), reviewer-determined
    state (responses), system-emitted state (audit events),
    operator-level state (SMTP credentials, operator-library
    RTDs / RuleSets), and seeded RTDs / RuleSets that
    auto-materialise on session create.

The CSV is "fallback for what the operator would type", not a
machine-only round-trip — the order is fixed so re-exporting
the same session is byte-stable, and an operator hand-editing
the file in Excel is a supported workflow.

This package is split by concern — ``_rows.py`` (the ``Row``
primitive + cell formatters), ``_serialize.py`` (the export
side), ``_apply.py`` (the import side) — with this ``__init__``
re-exporting the public surface so callers keep writing
``from app.services import session_config_io``.
"""

from __future__ import annotations

from app.services.session_config_io._apply import (
    ApplyResult,
    apply_session_config,
)
from app.services.session_config_io._apply_parse import ApplyError

# ``_ParseError`` / ``_parse_group_kind`` are re-exported for the
# unit test that exercises the group-kind cell parser directly.
from app.services.session_config_io._apply_shared import (  # noqa: F401
    _ParseError,
    _parse_group_kind,
)
from app.services.session_config_io._rows import HEADER, Row
from app.services.session_config_io._serialize import serialize_session_config

__all__ = [
    "ApplyError",
    "ApplyResult",
    "HEADER",
    "Row",
    "apply_session_config",
    "serialize_session_config",
]
