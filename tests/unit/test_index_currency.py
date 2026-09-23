"""Five invariants over the repo's hand-maintained indexes — 19S Items 2 and 5.

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

**G5 joined them at 19S Item 5**, over a different hand-maintained
claim in the same family: a `Blast radius` section that records a count
without recording *when* it was true, so a later re-run cannot tell a
stale number from a tree that has legitimately moved.

The five checks below are the subset that is derivable without judging
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

import pytest

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

#: The first plan whose ``Blast radius`` sections must state **when**
#: their numbers were taken (19S Item 5; author's ruling 2026-09-22 that
#: the cutoff is a segment comparison, not a date). A *date* cutoff would
#: need ``git log`` per section to decide whether a section is in scope,
#: because a section carries no date until this very convention gives it
#: one — circular. A segment id is in the filename.
#:
#: Sorted as ``(leading number, remainder)`` so ``19R`` < ``19S`` < ``20``:
#: one comparison rather than a list of the 93 legacy sections, the shape
#: `LEGACY_BEFORE_SEGMENT` already set.
#:
#: **19S, not the next segment, deliberately.** All 7 of 19S's sections
#: already carry an anchor, so the check covers real sections from its
#: first commit instead of covering nothing — a guard whose fixture
#: reaches no case is the vacuity `docs/unenforced_conventions.md` §1.6
#: concedes and §1.8 exists to catch.
ANCHOR_REQUIRED_FROM = (19, "S")

#: A ``Blast radius`` heading at segment (``##``) or item (``###``)
#: level. 97 of the corpus's 100 are item-level.
_BLAST_HEADING = re.compile(r"^#{2,3} Blast radius", re.M)

#: The anchor: a backticked short sha, **or** an ISO date on a line that
#: also says it was taken or measured. Both forms are already in use —
#: *"Taken 2026-09-22 at `92f7aff`"*.
#:
#: **The verb is not decoration.** A bare ISO date in the opening lines
#: passes as an anchor while stating no measurement point at all, and
#: that shape is common: **344 of the corpus's 3,109 sections (11%)**
#: open with one — *"✅ Shipped 2026-05-04"*, *"on the author's ruling,
#: 2026-09-22"*. No `Blast radius` section exhibits it today (**0** live
#: false positives), so the requirement was added on the shape rather
#: than on an instance — cold read, 2026-09-22. All 7 in-scope sections
#: satisfy it; the descriptive corpus figure moves 69 → 67.
_SHA = re.compile(r"`[0-9a-f]{7,40}`")
_ISO_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")
_TAKEN = re.compile(r"\b[Tt]aken\b|\b[Mm]easured\b")

#: How far past the heading the anchor may sit, in **non-blank** lines.
#: Two rather than one so a wrapped opening sentence still counts;
#: measured 2026-09-22, one and two give the identical count, so the
#: extra line buys tolerance without buying false positives.
_ANCHOR_WINDOW = 2

#: What this scan **cannot** see, stated because
#: `docs/unenforced_conventions.md` §1.6 asks a clean measurement to name
#: the shape it would miss rather than only the population it covered:
#: a `Blast radius` heading at `#` or `####`; an anchor written into the
#: heading text itself (`### Blast radius (measured at 92f7aff)`), which
#: `blast_radius_sections` begins reading one line too late to see; an
#: anchor more than `_ANCHOR_WINDOW` non-blank lines down; a date in any
#: non-ISO form; a sha without backticks; and a plan filename with no
#: leading digits, which `_PLAN_NAME` drops before `plan_sort_key` can
#: object. **0** instances of each today.

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


def plan_sort_key(identifier: str) -> tuple[int, str]:
    """``"19S"`` -> ``(19, "S")``, so plan ids order as a reader expects.

    ``19R`` < ``19S`` < ``19T`` < ``20``, and ``12A-2`` sorts after
    ``12A``. Raises rather than guessing on an id with no leading digits:
    every archived plan has them (checked 2026-09-22), and a silent
    fallback would drop a plan out of G5's scope without saying so.
    """
    match = re.match(r"(\d+)(.*)", identifier)
    if match is None:
        raise AssertionError(f"plan id with no leading number: {identifier!r}")
    return (int(match.group(1)), match.group(2))


def blast_radius_sections(text: str) -> list[tuple[int, list[str]]]:
    """Every ``Blast radius`` section as ``(heading line index, body)``.

    The body runs to the next heading of any level, so a section's
    opening lines are read from the section itself rather than from a
    fixed number of lines that a table could push past.
    """
    lines = text.split("\n")
    found: list[tuple[int, list[str]]] = []
    for index, line in enumerate(lines):
        if not _BLAST_HEADING.match(line):
            continue
        body: list[str] = []
        for following in lines[index + 1 :]:
            if re.match(r"^#{1,6} ", following):
                break
            body.append(following)
        found.append((index, body))
    return found


def section_is_anchored(body: list[str]) -> bool:
    """Whether a ``Blast radius`` body states when it was measured.

    A backticked sha counts on its own; a date has to appear on a line
    that also says *taken* or *measured*, so a section opening on an
    unrelated ISO date does not pass as an anchor. See `_SHA`.
    """
    seen = 0
    for line in body:
        if not line.strip():
            continue
        if _SHA.search(line) or (_ISO_DATE.search(line) and _TAKEN.search(line)):
            return True
        seen += 1
        if seen >= _ANCHOR_WINDOW:
            return False
    return False


def _plan_files() -> list[Path]:
    """Every segment plan, live and archived.

    **Archived ones included on purpose**: 19S will archive, and a scan
    of only ``guide/`` would quietly stop covering it on the day it
    moved — the failure mode G5 exists to prevent, applied to G5.

    ``_PLAN_NAME`` drops a filename with no leading digits. That is the
    silent drop `plan_sort_key` refuses to make, moved to where it is
    visible: the only such file today is ``segment_plan_template.md``,
    and the floor in
    `test_g5_sees_the_sections_it_claims_to_cover` is what would notice
    if the filter ever swallowed a real plan.
    """
    return sorted(
        p
        for directory in (REPO / "guide", ARCHIVE_DIR)
        for p in directory.glob("segment_*.md")
        if _PLAN_NAME.match(p.name)
    )


def _plan_texts() -> list[tuple[str, str]]:
    """``(filename, text)`` per plan — the I/O boundary, so every check
    below takes text and can be exercised on synthetic input, which is
    the shape this module's four other checks already have."""
    return [(p.name, p.read_text()) for p in _plan_files()]


def in_g5_scope(filename: str) -> bool:
    """Whether a plan's ``Blast radius`` sections must carry an anchor."""
    identifier = segment_id(filename)
    assert identifier is not None, f"not a plan filename: {filename!r}"
    return plan_sort_key(identifier) >= ANCHOR_REQUIRED_FROM


def unanchored_sections(
    named_texts: list[tuple[str, str]] | None = None,
) -> list[tuple[str, int]]:
    """**G5** — in-scope ``Blast radius`` sections stating no anchor.

    Takes ``(filename, text)`` pairs so the check is a function of text,
    like its four siblings; the default reads the corpus. Returns
    ``(filename, 1-based heading line)`` per offender.
    """
    offenders: list[tuple[str, int]] = []
    for name, text in named_texts if named_texts is not None else _plan_texts():
        if not in_g5_scope(name):
            continue
        for index, body in blast_radius_sections(text):
            if not section_is_anchored(body):
                offenders.append((name, index + 1))
    return offenders


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
    # 2, not 3, since 19S closed (2026-09-23): the queue holds 14B and
    # 20. A close floor, as above — it falls with the queue it measures.
    assert len(pointers) >= 2, f"only {len(pointers)} `**Plan:**` pointers"
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
    """Repoints the first live ``**Plan:**`` pointer into the archive.
    Derived rather than named: the named pointer (19S's) left the queue
    when 19S closed, and the mutation went with it."""
    _, upcoming = _todo_sections()
    pointers = plan_pointers(upcoming)
    assert pointers, "no `**Plan:**` pointer under Upcoming to mutate"
    victim = pointers[0]
    archived = "guide/archive/" + victim.rsplit("/", 1)[-1]
    mutated = upcoming.replace(f"`{victim}`", f"`{archived}`", 1)
    assert queued_archived_plans(mutated) == [archived]


def test_g5_every_in_scope_blast_radius_states_its_anchor() -> None:
    """**G5** — a `Blast radius` section from `ANCHOR_REQUIRED_FROM` on
    says when its numbers were taken (19S Item 5).

    Without an anchor a re-run cannot tell a stale number from a tree
    that has legitimately moved, so the comparison the convention exists
    for is impossible. 162 of 171 rows in the corpus are re-runnable
    exactly as written; the missing piece was never runnability.
    """
    offenders = unanchored_sections()
    assert offenders == [], (
        "`Blast radius` section with no commit or date to measure "
        "against: " + ", ".join(f"{name}:{line}" for name, line in offenders)
    )


def test_g5_sees_the_sections_it_claims_to_cover() -> None:
    """The live floor: G5's scope is non-empty, and the heading
    recogniser reaches **both** heading levels.

    A recogniser that matched no heading would satisfy G5 by seeing
    nothing — `docs/unenforced_conventions.md` §1.6's vacuity, and the
    reason `ANCHOR_REQUIRED_FROM` is 19S rather than the next segment.
    Measured 2026-09-22: 7 in-scope sections against 93 legacy.

    The two levels are pinned **separately**. A floor on the total
    absorbs a narrowing to `###` only: dropping `##` loses 3 of 100 and
    97 clears any plausible total floor — measured, cold read
    2026-09-22, and this repo has a documented history of floors
    absorbing narrowings.
    """
    texts = _plan_texts()
    in_scope = [
        (name, index)
        for name, text in texts
        if in_g5_scope(name)
        for index, _ in blast_radius_sections(text)
    ]
    assert len(in_scope) >= 7, f"G5 covers only {len(in_scope)} sections"

    every = [s for _, text in texts for s in blast_radius_sections(text)]
    assert len(every) >= 98, f"only {len(every)} `Blast radius` sections seen"

    item_level = sum(
        1
        for _, text in texts
        for line in text.split("\n")
        if line.startswith("### Blast radius")
    )
    segment_level = sum(
        1
        for _, text in texts
        for line in text.split("\n")
        if line.startswith("## Blast radius")
    )
    assert item_level >= 95, f"only {item_level} item-level sections seen"
    assert segment_level >= 3, (
        f"only {segment_level} segment-level (`##`) sections seen — the "
        "recogniser has narrowed to item level"
    )


def test_g5_excludes_the_legacy_corpus_and_that_exclusion_is_load_bearing() -> None:
    """Legacy sections are not checked, and some of them would fail.

    If every legacy section happened to be anchored the cutoff would be
    decorative; 30 of the 93 are not, so it carries weight. Asserted
    rather than assumed, the way G1's filter is.
    """
    legacy_unanchored = [
        (name, index + 1)
        for name, text in _plan_texts()
        if not in_g5_scope(name)
        for index, body in blast_radius_sections(text)
        if not section_is_anchored(body)
    ]
    assert legacy_unanchored, (
        "no legacy section lacks an anchor, so the cutoff is decorative"
    )
    # …and none of them reaches G5.
    assert unanchored_sections() == []


def test_plan_sort_key_orders_within_and_across_segment_numbers() -> None:
    assert plan_sort_key("19R") < plan_sort_key("19S")
    assert plan_sort_key("19S") < plan_sort_key("19T")
    assert plan_sort_key("19T") < plan_sort_key("20")
    assert plan_sort_key("12A") < plan_sort_key("12A-2")
    assert plan_sort_key("9Z") < plan_sort_key("10A")


def test_plan_sort_key_refuses_an_id_with_no_leading_number() -> None:
    """A silent fallback would drop a plan out of scope without saying
    so, which is the shape of defect this module is for."""
    with pytest.raises(AssertionError):
        plan_sort_key("template")


def test_section_is_anchored_accepts_both_forms_and_only_near_the_heading() -> None:
    assert section_is_anchored(["Taken 2026-09-22 at `92f7aff`."])
    assert section_is_anchored(["", "Measured at `9b32a9f`."])
    assert section_is_anchored(["Taken 2026-09-22."])
    assert section_is_anchored(["Measured 2026-09-22 over the archive."])
    # Two non-blank lines of grace, and no more: an anchor buried below a
    # table is not an opening statement of when the numbers were taken.
    assert section_is_anchored(["intro", "second line taken 2026-09-22"])
    assert not section_is_anchored(["intro", "second", "taken 2026-09-22"])
    assert not section_is_anchored(["| what | count |", "|---|---|"])
    # A sha needs its backticks: a bare hex-looking word is not a claim.
    assert not section_is_anchored(["Taken at 92f7aff."])


def test_a_bare_prose_date_is_not_an_anchor() -> None:
    """The false-positive shape the cold read quantified at 11% of all
    sections: a date that states no measurement point.

    0 `Blast radius` sections exhibit it today, so this pins the rule
    rather than a live instance — which is the point, since the next
    section written is where it would appear.
    """
    assert not section_is_anchored(["✅ Shipped 2026-05-04."])
    assert not section_is_anchored(
        ["Promoted from Item 1 on the author's ruling, 2026-09-22."]
    )
    assert not section_is_anchored(["(round 3, 2026-05-01)"])
    # …and the same date with the verb is an anchor.
    assert section_is_anchored(["Taken 2026-05-01."])


def test_blast_radius_sections_stop_at_the_next_heading() -> None:
    text = "\n".join(
        [
            "### Blast radius (measured)",
            "",
            "Taken 2026-09-22 at `abcdef1`.",
            "",
            "### PR ladder",
            "",
            "1. Rung 1 — 2026-09-23 is not this section's anchor.",
        ]
    )
    found = blast_radius_sections(text)
    assert len(found) == 1
    index, body = found[0]
    assert index == 0
    assert "PR ladder" not in "\n".join(body)
    assert "2026-09-23" not in "\n".join(body)


def test_g5_fails_when_an_in_scope_section_loses_its_anchor() -> None:
    """The mutation `docs/unenforced_conventions.md` §1.8 asks for.

    Strips the anchor from a real in-scope section and asserts G5
    reports it — run against a temporary copy so the check is proved
    against the corpus it guards rather than a synthetic one.
    """
    name = "segment_19S_post_assessment.md"
    # Wherever it lives — `guide/` while open, `guide/archive/` since.
    (path,) = [p for p in _plan_files() if p.name == name]
    original = path.read_text()
    sections = blast_radius_sections(original)
    assert sections, "19S has no `Blast radius` section to mutate"

    lines = original.split("\n")
    index, body = sections[0]
    # Blank the anchor out of the section's opening window — the same
    # window `section_is_anchored` reads, derived from it rather than
    # hard-coded, so narrowing one cannot leave the other behind.
    blanked = 0
    for offset in range(index + 1, len(lines)):
        if not lines[offset].strip():
            continue
        lines[offset] = _SHA.sub("REDACTED", lines[offset])
        lines[offset] = _TAKEN.sub("noted", lines[offset])
        blanked += 1
        if blanked >= _ANCHOR_WINDOW:
            break
    mutated = "\n".join(lines)
    assert mutated != original, "the mutation changed nothing"

    offenders = unanchored_sections([(name, mutated)])
    assert offenders, "G5 passed a section whose anchor was removed"
    assert offenders[0][0] == name
    # The unmutated text still passes, so the mutation is what failed it.
    assert unanchored_sections([(name, original)]) == []
