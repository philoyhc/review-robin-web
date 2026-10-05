"""Invariants over the repo's hand-maintained indexes — 19S Items 2 and 5.

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

**G1 and G2 retired 2026-10-05** with the ``## Done`` section they read,
when `guide/todo_master.md` became open work only (the section is
verbatim in `guide/archive/todo_master_done.md`). G1 asked that every
archived plan from segment 16 on have a Done entry; the archive index
already names every archived plan (`tests/unit/test_guide_indexes.py`).
G2 kept the list sorted by PR number, which mattered only while it grew.
**G3 retired the same day** with `docs/status.md` itself, archived to
`docs/archive/status.md`: it held that file's ``As of`` line to its
newest timeline row, and a file nobody updates has no header to drift.
G4 remains.

**G5 joined G1–G4 at 19S Item 5**, over a different hand-maintained
claim in the same family: a `Blast radius` section that records a count
without recording *when* it was true, so a later re-run cannot tell a
stale number from a tree that has legitimately moved.

The checks below are the subset that is derivable without judging
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
ARCHIVE_DIR = REPO / "guide" / "archive"


#: The first plan whose ``Blast radius`` sections must state **when**
#: their numbers were taken (19S Item 5; author's ruling 2026-09-22 that
#: the cutoff is a segment comparison, not a date). A *date* cutoff would
#: need ``git log`` per section to decide whether a section is in scope,
#: because a section carries no date until this very convention gives it
#: one — circular. A segment id is in the filename.
#:
#: Sorted as ``(leading number, remainder)`` so ``19R`` < ``19S`` < ``20``:
#: one comparison rather than a list of the 93 legacy sections.
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


#: ``segment_<id>_<slug>.md`` / ``segment_<id>.md``. ``_`` is outside
#: the id's character class, so ``segment_19P_expander_revamp.md`` gives
#: ``19P`` and ``segment_12A-2_import.md`` gives ``12A-2``.
_PLAN_NAME = re.compile(r"^segment_(\d+[A-Za-z0-9-]*)")

#: ``**Plan:** `guide/...`` in `guide/todo_master.md`. Keyed on the
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


# --- parsing -------------------------------------------------------


def segment_id(plan_filename: str) -> str | None:
    """``segment_19P_expander_revamp.md`` → ``19P``; ``None`` if the
    name does not carry a leading numeric id."""
    match = _PLAN_NAME.match(plan_filename)
    return match.group(1) if match else None


def plan_pointers(upcoming_text: str) -> list[str]:
    """Every ``**Plan:**`` path in the text."""
    return _PLAN_POINTER.findall(upcoming_text)


# --- the checks, each a function of the text it reads --------------


def queued_archived_plans(upcoming_text: str) -> list[str]:
    """**G4** — ``**Plan:**`` pointers in `guide/todo_master.md` that
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


def _todo_text() -> str:
    """The whole of `guide/todo_master.md`, which holds open work only
    since 2026-10-05 — so G4 reads all of it rather than a section."""
    return TODO_PATH.read_text()


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
    the shape this module's other checks already have."""
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
    like its siblings; the default reads the corpus. Returns
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


def test_no_upcoming_entry_points_at_an_archived_plan() -> None:
    """G4 on the tree."""
    queued = queued_archived_plans(_todo_text())
    assert not queued, (
        "`## Upcoming` entries whose `**Plan:**` is already archived:\n  "
        + "\n  ".join(queued)
    )


def test_the_checks_see_the_corpus_they_claim_to_cover() -> None:
    """The floor under G4's input, per §1.6.

    A change to the ``**Plan:**`` label would leave the check above
    passing over an empty list. The floor sits **just** below the count
    measured on 2026-09-22 — 3 pointers — deliberately close, because generous slack absorbs a
    recogniser narrowing: a close floor bites on a format change; a
    slack one does not, which is `docs/unenforced_conventions.md` §1.6's
    distinction between vacuity and coverage.
    """
    pointers = plan_pointers(_todo_text())
    # 2, not 3, since 19S closed (2026-09-23): the queue holds 14B and
    # 20. A close floor, as above — it falls with the queue it measures.
    assert len(pointers) >= 2, f"only {len(pointers)} `**Plan:**` pointers"
    for path in pointers:
        assert path.startswith("guide/") and path.endswith(".md"), (
            f"`**Plan:**` captured {path!r}, which is not a plan path — "
            "the recogniser is matching prose, not a pointer"
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


# --- mutations: each check fails when its property is broken --------
#
# docs/unenforced_conventions.md §1.8, second clause. The mutation is
# applied to a copy of the document's text, never to the tree — a check
# that has to edit its own subject to be demonstrated is the shape this
# item's plan rules out.


def test_g4_fails_when_a_queued_plan_is_archived() -> None:
    """Repoints the first live ``**Plan:**`` pointer into the archive.
    Derived rather than named: the named pointer (19S's) left the queue
    when 19S closed, and the mutation went with it."""
    upcoming = _todo_text()
    pointers = plan_pointers(upcoming)
    assert pointers, "no `**Plan:**` pointer in todo_master to mutate"
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
    rather than assumed.
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
