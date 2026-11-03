"""Roster CSV imports: parse, check, save.

Was a single 2,258-line ``csv_imports.py`` until segment 20E rung 2 cut it
along its seams. The public surface is preserved here as an explicit
re-export wall, so ``from app.services import csv_imports`` and
``from app.services.csv_imports import <name>`` work as before, private
names included (tests and a few services reach them).

Layout, each importing only from the ones above it:

- ``_parse.py`` — decoding, row reading, cell checks, the three
  ``parse_*_csv``.
- ``_identity.py`` — the directory check (``DirectoryCheck``), the
  same-person test and the cross-roster and incoming identity checks.
- ``_modes.py`` — append and merge (``AppendConflict``, ``append_conflicts``,
  ``merge_conflicts``, ``_merge_rows``).
- ``_saving.py`` — ``save_*``, ``_save``, ``delete_all_*`` and the counts
  (not ``_save.py``, which the ``_save`` function would shadow here).

A test that replaces a name here (``monkeypatch.setattr(csv_imports, …)``)
reaches callers outside the package only; a call between the modules goes
to the defining module, so patch that one.
"""

from __future__ import annotations

from app.services.csv_imports._parse import (
    log,
    MAX_BYTES,
    MAX_ROWS,
    NUL_MESSAGE,
    _ROSTER_COLUMNS,
    ParseResult,
    decode_csv,
    csv_error_message,
    _unreadable_issue,
    _read_dict_rows,
    _missing_columns_issues,
    cell_length_issues,
    over_long_field_message,
    tag_comma_issues,
    comma_tag_message,
    _cell,
    _none_if_blank,
    _profile_link_header,
    _profile_link,
    _VALID_ROSTER_STATUSES,
    _parse_status,
    _parse_email,
    parse_reviewer_csv,
    parse_reviewee_csv,
    parse_observer_csv,
)
from app.services.csv_imports._identity import (
    DirectoryCheck,
    directory_check,
    directory_checks,
    is_comparable_identity,
    _IDENTITY_ROSTERS,
    _IDENTITY_MODELS,
    _identity_holders,
    _ROSTER_ORDER,
    _first_disagreeing_holder,
    cross_table_identity_conflict,
    _with_mirrors,
    check_cross_table_identity,
    check_incoming_identity,
    _FILE_BY_LABEL,
    _incoming_holders,
)
from app.services.csv_imports._modes import (
    AppendConflict,
    append_conflicts,
    merge_conflicts,
    _MERGE_KEEPS,
    _merge_rows,
)
from app.services.csv_imports._saving import (
    existing_reviewer_count,
    existing_reviewee_count,
    existing_observer_count,
    _count,
    save_reviewers,
    save_reviewees,
    save_observers,
    _observer_to_kwargs,
    _reviewer_to_kwargs,
    _reviewee_to_kwargs,
    _save,
    _detach_outbox_if_reviewers,
    _reaches_assignments,
    _count_assignments,
    _count_relationships,
    existing_assignment_count,
    delete_all_reviewers,
    delete_all_reviewees,
    delete_all_observers,
    _delete_all,
)

__all__ = [
    "log",
    "MAX_BYTES",
    "MAX_ROWS",
    "NUL_MESSAGE",
    "_ROSTER_COLUMNS",
    "ParseResult",
    "decode_csv",
    "csv_error_message",
    "_unreadable_issue",
    "_read_dict_rows",
    "_missing_columns_issues",
    "cell_length_issues",
    "over_long_field_message",
    "tag_comma_issues",
    "comma_tag_message",
    "_cell",
    "_none_if_blank",
    "_profile_link_header",
    "_profile_link",
    "_VALID_ROSTER_STATUSES",
    "_parse_status",
    "_parse_email",
    "parse_reviewer_csv",
    "parse_reviewee_csv",
    "parse_observer_csv",
    "DirectoryCheck",
    "directory_check",
    "directory_checks",
    "is_comparable_identity",
    "_IDENTITY_ROSTERS",
    "_IDENTITY_MODELS",
    "_identity_holders",
    "_ROSTER_ORDER",
    "_first_disagreeing_holder",
    "cross_table_identity_conflict",
    "_with_mirrors",
    "check_cross_table_identity",
    "check_incoming_identity",
    "_FILE_BY_LABEL",
    "_incoming_holders",
    "AppendConflict",
    "append_conflicts",
    "merge_conflicts",
    "_MERGE_KEEPS",
    "_merge_rows",
    "existing_reviewer_count",
    "existing_reviewee_count",
    "existing_observer_count",
    "_count",
    "save_reviewers",
    "save_reviewees",
    "save_observers",
    "_observer_to_kwargs",
    "_reviewer_to_kwargs",
    "_reviewee_to_kwargs",
    "_save",
    "_detach_outbox_if_reviewers",
    "_reaches_assignments",
    "_count_assignments",
    "_count_relationships",
    "existing_assignment_count",
    "delete_all_reviewers",
    "delete_all_reviewees",
    "delete_all_observers",
    "_delete_all",
]
