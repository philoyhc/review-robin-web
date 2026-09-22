"""Four invariants over the repo's hand-maintained indexes — 19S Item 2.

`tests/unit/test_doc_references.py` asks whether a path resolves and
whether a `§N` names a real section. Nothing asked whether a *count* or
an *entry* is current, and three drift instances in two indexes were each
caught by a person reading (19S Item 1, entry E4):

* `docs/status.md`'s summary line ran two items behind, missed by two
  consecutive closes;
* `guide/todo_master.md`'s ``## Done`` had no entry for segments 19P or
  19Q while ``## Upcoming`` still described 19R as open, and the
  section's own *by first PR number ascending* rule had drifted far
  enough that 19I (#2230) sat below 19O (#2382);
* 19O's entry ended *"the segment stays open"* under a heading reading
  ``✅ closed``.

The four checks below are the subset that is derivable without judging
prose, and each passed on the tree when it was written — which is
`docs/unenforced_conventions.md` §2's bar for a check worth writing.
The residue that is *not* derivable stays conceded at §1.4 / §1.5: no
check here asks whether a sentence's content is current, because the
only cheap way to do that enforces a mention rather than the fact.

**Why the parsers are pure functions over text.** Each check is a
function taking the document's text, so the recogniser can be exercised
on synthetic input and against a mutation of the property it protects —
the second and third of the three things `docs/unenforced_conventions.md`
§1.8 asks of a new guard. A check that only ever runs against the live
tree cannot show that it would fail.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TODO_PATH = REPO / "guide" / "todo_master.md"
STATUS_PATH = REPO / "docs" / "status.md"
ARCHIVE_DIR = REPO / "guide" / "archive"

#: Segments numbered below this are legacy and out of scope (author's
#: ruling, 2026-09-22): that era used grouped headings (``### Segment
#: 11``, ``### Segment 13``) rather than one per segment, and **52 of
#: its 67** archived plans have no ``### Segment <id>`` heading of their
#: own — measured with `id_pattern`, the criterion G1 applies. An
#: earlier version of this comment said 34, a figure no reading of the
#: corpus supports (cold read, 2026-09-22). Expressed
#: as one comparison rather than a list of exceptions, so §2's
#: *no allowlist* bar survives — the same shape the pre-16 filter takes
#: in this item's plan.
LEGACY_BEFORE_SEGMENT = 16

#: A ``## Done`` entry heading. The section also carries ``### P0 —``
#: style audit headings and a few non-segment scopes; only the PR
#: numbers they declare matter to G2, so the pattern is deliberately
#: every ``### `` heading rather than only the segment ones.
_HEADING = re.compile(r"^### .*$", re.M)

#: A PR reference inside a heading. Two digits minimum so a ``#2`` in
#: prose cannot be read as a PR; the trailing ``(?!\d)`` is what the
#: five-digit cap is *for*. Without it ``#123456`` matched and captured
#: ``12345`` — a silent truncation, the exact opposite of what an
#: earlier version of this comment claimed (cold read, 2026-09-22).
_PR_REF = re.compile(r"#(\d{2,5})(?!\d)")

#: ``segment_<id>_<slug>.md`` / ``segment_<id>.md``. ``_`` is outside
#: the id's character class, so ``segment_19P_expander_revamp.md`` gives
#: ``19P`` and ``segment_12A-2_import.md`` gives ``12A-2``.
_PLAN_NAME = re.compile(r"^segment_(\d+[A-Za-z0-9-]*)")

#: ``**Plan:** `guide/...`` under ``## Upcoming``. Keyed on the
#: ``**Plan:**`` label rather than on any backticked plan path, because
#: citing an *archived* plan in body prose is legitimate and common —
#: `guide/todo_master.md`'s Stubs section names one as a stub's source.
#:
#: ``\s+``, not ``\s*``. With ``*`` this matched `guide/todo_master.md`'s
#: **own prose about this check** — ``no `**Plan:**` pointer under
#: `## Upcoming` resolves`` — capturing `` pointer under ``. That false
#: positive was also what satisfied the floor below, so the floor passed
#: while all three real pointers could have been reformatted away
#: (cold read, 2026-09-22).
_PLAN_POINTER = re.compile(r"\*\*Plan:\*\*\s+`([^`]+)`")

_AS_OF = re.compile(r"\*\*As of:\*\*\s*(\d{4}-\d\d-\d\d)")
_TIMELINE_ROW = re.compile(r"^\|\s*(\d{4}-\d\d-\d\d)\s*\|", re.M)
_TIMELINE_HEADING = "## Project timeline"


# --- parsing -------------------------------------------------------


def section(text: str, start: str, end: str) -> str:
    """The slice of `text` between two headings, matched **anchored**.

    Each marker must appear as a whole line. An unanchored
    ``text.index("## Done")`` also matches ``### Done`` and any
    backticked mention in prose — and rung 2's own job is to edit the
    ``## Done`` maintenance note, where the natural sentence quotes
    ``## Upcoming``. That would have truncated this section to the note
    and reported all 39 modern plans as missing, loudly but wrongly
    (cold read, 2026-09-22).

    Raises rather than returning an empty string when a marker is
    missing: these headings moving should fail here rather than quietly
    stop checking anything.
    """
    opening = re.search(rf"^{re.escape(start)}$", text, re.M)
    if opening is None:
        raise ValueError(f"no line reading {start!r}")
    rest = text[opening.start() :]
    closing = re.search(rf"^{re.escape(end)}$", rest, re.M)
    if closing is None:
        raise ValueError(f"no line reading {end!r} after {start!r}")
    return rest[: closing.start()]


def timeline_bounds(status_text: str) -> tuple[int, int]:
    """``(start, end)`` offsets of the ``## Project timeline`` body.

    Ends at the next ``## `` heading — `docs/status.md` carries four
    more after it, so the table is not the tail of the file.
    """
    opening = re.search(rf"^{re.escape(_TIMELINE_HEADING)}$", status_text, re.M)
    if opening is None:
        raise AssertionError(
            f"docs/status.md carries no {_TIMELINE_HEADING!r} heading"
        )
    rest = status_text[opening.end() :]
    following = re.search(r"^## ", rest, re.M)
    end = opening.end() + (following.start() if following else len(rest))
    return opening.end(), end


def timeline_section(status_text: str) -> str:
    """The ``## Project timeline`` table, not the whole document.

    `_TIMELINE_ROW` read file-wide before: every dated row happens to
    sit in that one table today, but G3 would then have maxed over a
    dated row in any table added later (cold read, 2026-09-22).
    """
    start, end = timeline_bounds(status_text)
    return status_text[start:end]


def id_pattern(identifier: str) -> re.Pattern[str]:
    """``### Segment <id>`` matching the id whole, hyphens included.

    ``\\b`` is not enough: a hyphen is a non-word character, so
    ``^### Segment 12C\\b`` matches ``### Segment 12C-1`` and lets one
    entry answer for a different segment's plan. That is the same hole
    that left this module's first G1 mutation inert, and the archive
    holds a live instance — ``segment_12C_self-review_revamp.md`` has no
    heading of its own while ``12C-1`` does (cold read, 2026-09-22).
    """
    return re.compile(rf"^### Segment {re.escape(identifier)}(?![\w-])", re.M)


def segment_id(plan_filename: str) -> str | None:
    """``segment_19P_expander_revamp.md`` → ``19P``; ``None`` if the
    name does not carry a leading numeric id."""
    match = _PLAN_NAME.match(plan_filename)
    return match.group(1) if match else None


def segment_number(identifier: str) -> int | None:
    """``19P`` → ``19``; ``None`` when the id has no leading digits."""
    match = re.match(r"(\d+)", identifier)
    return int(match.group(1)) if match else None


def lowest_pr(heading: str) -> int | None:
    """The lowest PR number a heading declares, or ``None``.

    The *heading only* — a heading citing a foreign PR ("superseded by
    #1234") would order wrongly, and the convention that keeps this
    honest is that foreign references belong in the body. There are no
    such headings today; when one appears, this is where it shows up.
    """
    numbers = [int(n) for n in _PR_REF.findall(heading)]
    return min(numbers) if numbers else None


def plan_pointers(upcoming_text: str) -> list[str]:
    """Every ``**Plan:**`` path under ``## Upcoming``."""
    return _PLAN_POINTER.findall(upcoming_text)


# --- the four checks, each a function of the text it reads ---------


def missing_done_entries(
    done_text: str, plan_filenames: list[str]
) -> list[str]:
    """**G1** — archived plans from `LEGACY_BEFORE_SEGMENT` on with no
    ``### Segment <id>`` heading in ``## Done``.

    Asks for **at least one** heading, never exactly one: the mapping is
    not one-to-one in either direction. Id ``18R`` matches both
    *Segment 18R* and *Segment 18R Part 2*, and one heading can cover
    several plans.

    A plan archived **unbuilt** would fail this while being correct.
    There is no such plan from segment 16 on today, and the escape when
    one appears belongs in the plan file — a line saying it was retired
    unbuilt — rather than a list inside this test, which would be the
    allowlist §2's bar forbids.
    """
    missing = []
    for name in sorted(plan_filenames):
        identifier = segment_id(name)
        if identifier is None:
            continue
        number = segment_number(identifier)
        if number is None or number < LEGACY_BEFORE_SEGMENT:
            continue
        if not id_pattern(identifier).search(done_text):
            missing.append(name)
    return missing


def out_of_order_headings(done_text: str) -> list[tuple[str, int, int]]:
    """**G2** — ``## Done`` headings declaring a PR, out of ascending
    order by the lowest each declares.

    Non-strict: two headings declaring the same lowest PR are in order.
    Headings declaring no PR are skipped rather than failed: **35**
    declare none and no rule can place those, which the section's own
    maintenance note says. It says *many* predate the convention rather
    than all, and that is the honest word — some postdate it
    (``### Sys Admin per-row actions``, ``### Segment 18R Part 2``). An
    earlier version said 33 and said they all predate it; both were
    wrong (cold read, 2026-09-22).
    """
    out_of_order: list[tuple[str, int, int]] = []
    highest = 0
    for heading in _HEADING.findall(done_text):
        lowest = lowest_pr(heading)
        if lowest is None:
            continue
        if lowest < highest:
            out_of_order.append((heading[:60], lowest, highest))
        highest = max(highest, lowest)
    return out_of_order


def stale_as_of(status_text: str) -> tuple[str, str] | None:
    """**G3** — ``(as_of, newest_row)`` when ``**As of:**`` does not
    equal the newest date in the project timeline, else ``None``.

    Takes the **maximum** row date rather than the first, so a row
    inserted out of order cannot hide a stale header. A future-dated row
    therefore fails, which is correct: the header is a claim about what
    the document covers.
    """
    as_of_match = _AS_OF.search(status_text)
    if as_of_match is None:
        raise AssertionError("docs/status.md carries no `**As of:**` date")
    rows = _TIMELINE_ROW.findall(timeline_section(status_text))
    if not rows:
        raise AssertionError("docs/status.md carries no dated timeline rows")
    newest = max(rows)
    as_of = as_of_match.group(1)
    return None if as_of == newest else (as_of, newest)


def queued_archived_plans(upcoming_text: str) -> list[str]:
    """**G4** — ``**Plan:**`` pointers under ``## Upcoming`` that
    resolve into ``guide/archive/``.

    A **dangling** path is already
    `tests/unit/test_doc_references.py`'s. This takes only the case that
    check cannot see: a pointer correctly repointed at the archive while
    the entry stays queued as upcoming work.
    """
    return [
        path
        for path in plan_pointers(upcoming_text)
        if path.startswith("guide/archive/")
    ]


# --- the live tree -------------------------------------------------


def _todo_sections() -> tuple[str, str]:
    text = TODO_PATH.read_text()
    return (
        section(text, "## Done", "## Upcoming"),
        text[text.index("## Upcoming") :],
    )


def _archived_plan_names() -> list[str]:
    return [p.name for p in ARCHIVE_DIR.glob("segment_*.md")]


def test_every_modern_archived_plan_has_a_done_entry() -> None:
    """G1 on the tree. Would have caught 19P and 19Q."""
    done, _ = _todo_sections()
    missing = missing_done_entries(done, _archived_plan_names())
    assert not missing, (
        "archived plans from segment "
        f"{LEGACY_BEFORE_SEGMENT} on with no `### Segment <id>` entry in "
        "`guide/todo_master.md`'s `## Done`:\n  " + "\n  ".join(missing)
    )


def test_done_headings_declaring_a_pr_run_ascending() -> None:
    """G2 on the tree. Would have caught six segments of newest-first
    drift."""
    done, _ = _todo_sections()
    wrong = out_of_order_headings(done)
    assert not wrong, (
        "`## Done` is sorted by first PR number ascending; these "
        "headings declare a lower PR than one above them:\n  "
        + "\n  ".join(f"{h} (#{low} after #{high})" for h, low, high in wrong)
    )


def test_status_as_of_matches_its_newest_timeline_row() -> None:
    """G3 on the tree. Would have caught the summary line two items
    behind."""
    stale = stale_as_of(STATUS_PATH.read_text())
    assert stale is None, (
        f"docs/status.md says `**As of:** {stale[0]}` but its newest "
        f"timeline row is {stale[1]}"
    )


def test_no_upcoming_entry_points_at_an_archived_plan() -> None:
    """G4 on the tree."""
    _, upcoming = _todo_sections()
    queued = queued_archived_plans(upcoming)
    assert not queued, (
        "`## Upcoming` entries whose `**Plan:**` is already archived:\n  "
        + "\n  ".join(queued)
    )


def test_the_checks_see_the_corpus_they_claim_to_cover() -> None:
    """Floors under each check's input, per §1.6.

    `section()` fails loudly if ``## Done`` moves, but a change to the
    *heading level* or to the ``**Plan:**`` label would leave every
    check above passing over an empty list. The floors sit **just**
    below the counts measured on 2026-09-22 — 84 headings, 49 declaring
    a PR, 39 modern plans, 3 pointers, 71 rows — deliberately close,
    because generous slack absorbs a recogniser narrowing: at a floor of
    30, tightening `_PR_REF` to four digits dropped 16 three-digit
    headings (``#651``–``#789``) out of G2's subject and still left 33,
    so the floor passed while the check covered less (cold read,
    2026-09-22). A close floor bites on a format change; a slack one
    does not, which is `docs/unenforced_conventions.md` §1.6's
    distinction between vacuity and coverage.
    """
    done, upcoming = _todo_sections()
    headings = _HEADING.findall(done)
    declaring = [h for h in headings if lowest_pr(h) is not None]
    modern = [
        n
        for n in _archived_plan_names()
        if (i := segment_id(n))
        and (num := segment_number(i)) is not None
        and num >= LEGACY_BEFORE_SEGMENT
    ]
    assert len(headings) >= 80, f"only {len(headings)} `### ` headings in Done"
    assert len(declaring) >= 45, f"only {len(declaring)} declare a PR"
    assert len(modern) >= 38, f"only {len(modern)} archived plans are modern"
    pointers = plan_pointers(upcoming)
    assert len(pointers) >= 3, f"only {len(pointers)} `**Plan:**` pointers"
    for path in pointers:
        assert path.startswith("guide/") and path.endswith(".md"), (
            f"`**Plan:**` captured {path!r}, which is not a plan path — "
            "the recogniser is matching prose, not a pointer"
        )
    rows = _TIMELINE_ROW.findall(timeline_section(STATUS_PATH.read_text()))
    assert len(rows) >= 65, f"only {len(rows)} dated timeline rows"


def test_the_legacy_filter_is_load_bearing() -> None:
    """The pre-16 filter excludes real plans, not a hypothetical era.

    Without this, a filter that happened to exclude nothing would look
    identical to one doing its job — and G1 would be asserting over a
    corpus of 39 while appearing to cover 106.
    """
    done, _ = _todo_sections()
    names = _archived_plan_names()
    modern = [
        n
        for n in names
        if (i := segment_id(n))
        and (num := segment_number(i)) is not None
        and num >= LEGACY_BEFORE_SEGMENT
    ]
    legacy_missing = [
        n
        for n in names
        if n not in modern
        and (i := segment_id(n))
        and not id_pattern(i).search(done)
    ]
    assert len(modern) < len(names), "the filter excludes nothing"
    assert legacy_missing, (
        "no legacy plan lacks a `## Done` heading, so the filter is "
        "excluding nothing that would otherwise fail — re-check the "
        "author's 2026-09-22 ruling before trusting G1's scope"
    )


# --- the recognisers, outside their production examples ------------
#
# docs/unenforced_conventions.md §1.8, third clause. Each case below is
# a boundary this item's plan names in `Semantics`.


def test_segment_id_parses_the_shapes_the_archive_holds() -> None:
    assert segment_id("segment_19P_expander_revamp.md") == "19P"
    assert segment_id("segment_12A-2_import.md") == "12A-2"
    assert segment_id("segment_04A.md") == "04A"
    assert segment_id("segment_09_1A.md") == "09"
    assert segment_id("new_ux_ideas.md") is None


def test_segment_number_reads_the_leading_digits() -> None:
    assert segment_number("19P") == 19
    assert segment_number("12A-2") == 12
    assert segment_number("04A") == 4
    assert segment_number("A") is None


def test_g1_accepts_one_id_matching_several_headings() -> None:
    """Id ``18R`` matches two headings in the live section; at least one
    is the rule, so neither the plan nor a second heading fails."""
    done = (
        "## Done\n"
        "### Segment 18R — UX refinement — done (#1899)\n"
        "### Segment 18R Part 2 — UX refinement (Items 3–6) — done\n"
    )
    assert missing_done_entries(done, ["segment_18R_testing.md"]) == []


def test_g1_does_not_let_a_longer_id_satisfy_a_shorter_one() -> None:
    """``### Segment 19P`` must not answer for a plan whose id is
    ``19`` — the word boundary is what stops it."""
    done = "## Done\n### Segment 19P — the expander revamp\n"
    assert missing_done_entries(done, ["segment_19_something.md"]) == [
        "segment_19_something.md"
    ]


def test_g1_does_not_let_a_hyphenated_id_satisfy_its_stem() -> None:
    """``### Segment 12C-1`` must not answer for plan id ``12C``.

    The live instance: `guide/archive/segment_12C_self-review_revamp.md`
    has no heading of its own, and ``### Segment 12C-1`` does. Under
    ``\\b`` it passed — a hyphen is a non-word character — which is the
    same hole that left this module's first G1 mutation inert. Pre-16,
    so G1 does not count it, but the hole was in the pattern rather than
    in the filter (cold read, 2026-09-22).
    """
    done = "## Done\n### Segment 12C-1 — Self-review revamp\n"
    assert missing_done_entries(done, ["segment_12C_x.md"]) == []
    assert id_pattern("12C").search(done) is None
    assert id_pattern("12C-1").search(done) is not None


def test_g1_ignores_the_legacy_era() -> None:
    done = "## Done\n(no segment headings at all)\n"
    assert missing_done_entries(done, ["segment_11A_cleanup.md"]) == []
    assert missing_done_entries(done, ["segment_19Z_new.md"]) == [
        "segment_19Z_new.md"
    ]


def test_g2_ties_are_in_order_and_headings_without_a_pr_are_skipped() -> None:
    done = (
        "## Done\n"
        "### Segment A — done (#100)\n"
        "### Segment B — done (#100, #180)\n"
        "### P0 — an audit heading with no PR\n"
        "### Segment C — done (#200 → #210)\n"
    )
    assert out_of_order_headings(done) == []


def test_lowest_pr_takes_the_minimum_a_heading_declares() -> None:
    assert lowest_pr("### Segment X — PRs #2515 → #2540") == 2515
    assert lowest_pr("### Segment Y — #2540, #2515") == 2515
    assert lowest_pr("### Segment Z — no numbers") is None
    assert lowest_pr("### Segment W — item #7 of nine") is None


def test_g4_keys_on_the_plan_label_not_on_any_archived_path() -> None:
    """A stub citing an archived plan in body prose stays legal; only a
    ``**Plan:**`` pointer is a claim that the work is upcoming."""
    upcoming = (
        "## Upcoming\n"
        "1. **14B — Email.**\n"
        "   **Plan:** `guide/segment_14B_email_infrastructure.md`.\n"
        "#### Stubs\n"
        "- filed at `guide/archive/segment_19P_expander_revamp.md` Item 6.\n"
    )
    assert queued_archived_plans(upcoming) == []


def test_g4_does_not_read_the_repo_s_prose_about_itself() -> None:
    """`guide/todo_master.md` describes **this check** inside
    ``## Upcoming``, and the description contains the label.

    With ``\\s*`` the regex matched ``**Plan:**`` followed immediately by
    a closing backtick and captured `` pointer under ``. A count-only
    floor could not see that: the false positive *raised* the count, so
    the floor passed while every real pointer could have been
    reformatted away (cold read, 2026-09-22). The live floor asserts the
    shape of each capture for the same reason.
    """
    prose = (
        "## Upcoming\n"
        "   - and no `**Plan:**` pointer under `## Upcoming` resolves\n"
        "     into `guide/archive/`.\n"
    )
    assert plan_pointers(prose) == []
    assert queued_archived_plans(prose) == []


def test_section_raises_rather_than_reading_nothing() -> None:
    """A moved heading fails loudly instead of silently checking an
    empty string."""
    try:
        section("## Upcoming\nonly\n", "## Done", "## Upcoming")
    except ValueError:
        return
    raise AssertionError("section() accepted text with no `## Done`")


# --- mutations: each check fails when its property is broken --------
#
# docs/unenforced_conventions.md §1.8, second clause. The mutation is
# applied to a copy of the document's text, never to the tree — a check
# that has to edit its own subject to be demonstrated is the shape this
# item's plan rules out.


def test_g1_fails_when_a_modern_plan_loses_its_entry() -> None:
    """The mutation deletes the whole heading line.

    The first draft of this test renamed it to ``### Segment
    19R-removed`` and **the check stayed green**: ``-`` is a non-word
    character, so ``^### Segment 19R\\b`` still matched. An inert
    mutation demonstrates nothing, which is why
    `docs/unenforced_conventions.md` §1.8 asks for the mutation to
    *fail* rather than for it to exist.
    """
    done, _ = _todo_sections()
    assert re.search(r"^### Segment 19R ", done, re.M), (
        "19R's entry moved; re-pick the mutation"
    )
    mutated = re.sub(
        r"^### Segment 19R .*$", "(entry deleted)", done, count=1, flags=re.M
    )
    missing = missing_done_entries(mutated, _archived_plan_names())
    assert "segment_19R_optimization_and_bugfixes.md" in missing


def test_g2_fails_when_two_headings_swap() -> None:
    done = (
        "## Done\n"
        "### Segment B — done (#2382)\n"
        "### Segment A — done (#2230)\n"
    )
    wrong = out_of_order_headings(done)
    assert [(low, high) for _, low, high in wrong] == [(2230, 2382)]


def test_g2_compares_against_the_running_maximum_not_the_previous() -> None:
    """``100, 300, 200`` is out of order; an adjacent-pair check misses
    it once a later heading climbs again.

    The two-heading case above cannot tell the two implementations
    apart, and replacing the running maximum with ``highest = lowest``
    left all tests green (cold read, 2026-09-22). Newest-first drift of
    the 19I/19O shape is a *run*, not a swap, so this is the shape that
    matters.
    """
    done = (
        "## Done\n"
        "### Segment A — done (#100)\n"
        "### Segment C — done (#300)\n"
        "### Segment B — done (#200)\n"
        "### Segment D — done (#250)\n"
    )
    wrong = out_of_order_headings(done)
    assert [(low, high) for _, low, high in wrong] == [(200, 300), (250, 300)]


def test_g3_fails_when_a_newer_row_lands_without_the_header() -> None:
    """The mutation appends at the **end** of the table.

    The first draft inserted it directly after ``|---|---|``, i.e. as
    the *first* row — where `max(rows)` and ``rows[0]`` are
    indistinguishable, so the ordering semantics the docstring sells
    went undemonstrated. Replacing `max` with ``rows[0]`` left all
    tests green (cold read, 2026-09-22).

    The **second** draft then appended after the last *line* of the
    section, which is a ``---`` rule occurring 18 times in the file, so
    ``str.replace(..., 1)`` hit the first one and the row landed outside
    the table — invisible again. It splices by **offset** after the last
    dated row now. Rows are newest-first, so the newest date ends up
    last, where only `max` finds it.
    """
    text = STATUS_PATH.read_text()
    assert stale_as_of(text) is None, "the tree is already stale; fix that"
    start, end = timeline_bounds(text)
    rows = list(_TIMELINE_ROW.finditer(text[start:end]))
    insert_at = start + rows[-1].end()
    mutated = (
        text[:insert_at]
        + "\n| 2099-01-01 | a newer row, appended last. |"
        + text[insert_at:]
    )
    stale = stale_as_of(mutated)
    assert stale is not None and stale[1] == "2099-01-01"


def test_g3_finds_the_newest_row_wherever_it_sits() -> None:
    """`max`, not first-or-last: a row out of order cannot hide a
    stale header. This is the property the live mutation above could not
    show on its own."""
    synthetic = (
        "**As of:** 2026-01-01\n\n## Project timeline\n\n"
        "| Date | Milestone |\n|---|---|\n"
        "| 2026-01-01 | first. |\n"
        "| 2026-06-01 | newest, in the middle. |\n"
        "| 2026-01-01 | last. |\n"
    )
    assert stale_as_of(synthetic) == ("2026-01-01", "2026-06-01")


def test_g4_fails_when_a_queued_plan_is_archived() -> None:
    _, upcoming = _todo_sections()
    victim = "`guide/segment_19S_post_assessment.md`"
    assert victim in upcoming, "19S's pointer moved; re-pick the mutation"
    mutated = upcoming.replace(
        victim, "`guide/archive/segment_19S_post_assessment.md`", 1
    )
    assert queued_archived_plans(mutated) == [
        "guide/archive/segment_19S_post_assessment.md"
    ]
