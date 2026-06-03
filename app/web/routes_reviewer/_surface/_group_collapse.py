"""Group-scoped instrument row collapse (Segment 13C reviewer surface).

Folds a group-scoped instrument's per-assignment rows into one
row per boundary-defined group; the representative row carries
a ``group_identity`` block (boundary tag values + member names)
and a ``group_label`` for aria text.

Pure: takes built row dicts + the assignment → group key map,
returns a fresh list. No DB reads.
"""
from __future__ import annotations


# A group row's identity cell lists at most this many member names
# before collapsing the rest to a "+N more" suffix (Segment 13C).
GROUP_MEMBER_NAME_LIMIT = 10


def _collapse_group_rows(
    per_assignment_rows: list[dict],
    *,
    group_key_by_assignment: dict[int, tuple[str, ...]],
    name_visible: bool,
) -> list[dict]:
    """Collapse a group-scoped instrument's per-assignment rows into
    one row per boundary-defined group (Segment 13C reviewer surface).

    Rows are partitioned by their assignment's group key; each
    partition yields one row carrying its lowest-id member assignment
    as the representative — response inputs key off it and the write
    fan-out spreads the answer to the rest. The representative row
    gains a ``group_identity`` block (boundary tag values + member
    names) and a ``group_label`` for aria text; its per-reviewee
    ``display_cells`` / ``sort_values`` are cleared.
    """
    partitions: dict[tuple[str, ...], list[dict]] = {}
    for row in per_assignment_rows:
        group_key = group_key_by_assignment.get(row["assignment"].id, ())
        partitions.setdefault(group_key, []).append(row)
    collapsed: list[dict] = []
    for group_key in sorted(partitions):
        members = sorted(
            partitions[group_key], key=lambda r: r["assignment"].id
        )
        representative = dict(members[0])
        names = sorted(r["assignment"].reviewee.name for r in members)
        shown = names[:GROUP_MEMBER_NAME_LIMIT]
        # Compose the group's tag line from every visible
        # ``reviewee.tag_*`` display field — matching the operator's
        # Band 2 preview, which joins each selected tag-pill value
        # with commas above the member names. Reading only the
        # boundary tags (via ``group_key``) silently drops any
        # non-boundary tag display field the operator chose. Falls
        # back to the boundary-key composition when there are zero
        # visible reviewee.tag_* display fields, so the line is
        # never blank when a boundary tag value exists.
        tag_values: list[str] = []
        for cell in members[0].get("display_cells", []) or []:
            field = cell.get("field")
            if field is None:
                continue
            source_type = getattr(field, "source_type", "")
            source_field = getattr(field, "source_field", "") or ""
            if source_type != "reviewee" or not source_field.startswith("tag_"):
                continue
            value = (cell.get("value") or "").strip()
            if value:
                tag_values.append(value)
        if tag_values:
            tag_line = ", ".join(tag_values)
        else:
            tag_line = ", ".join(v for v in group_key if v)
        representative["display_cells"] = []
        representative["sort_values"] = {}
        representative["group_identity"] = {
            "tag_line": tag_line,
            "member_names": shown,
            "extra_count": len(names) - len(shown),
            "show_members": name_visible,
        }
        representative["group_label"] = (
            tag_line or ", ".join(shown) or "the group"
        )
        collapsed.append(representative)
    return collapsed
