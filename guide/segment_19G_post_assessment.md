# Segment 19G — Post-assessment follow-ups

**Opened:** 2026-09-08 · **Theme:** settling the recommended moves from
`guide/codebase_assessment_08sep.md` §8 · **Related:**
`guide/codebase_assessment_08sep.md`, `constitution.md`,
`tests/unit/test_doc_conventions.py`

**Bounded, not a standing home.** 19C closed on 2026-09-08 because a
segment kept open as a home for whatever came next accreted ten items
over nineteen days and produced a plan nobody read. This segment is a
different shape on purpose: its scope is the recommended moves in one
dated assessment, which is a finite list written before the segment
opened. Work that is not one of those moves, or a patch arising from
them, gets its own segment; that is the guard, and it is the whole
reason this file is allowed more than one item.

**Both moves are settled as of 2026-09-08, and the segment is
deliberately kept open** (author, 2026-09-08) for the patches this work
turned up — see "Patch queue" below. The original framing said the
segment closes once the moves are settled; that is amended rather than
quietly ignored, because "we'll leave it open a bit" is the exact
sentence 19C died of. What keeps this from being 19C is that the queue
is **finite, named, and already written down**: three one-line fixes
found while doing Items 1 and 2, none of which was in scope at the time.

**Close it when the queue is empty**, or at the next assessment
snapshot, whichever comes first. *(The queue emptied 2026-09-08 with
19G.3. The segment stays open only for the two carried open questions
below; if neither is picked up before the next snapshot, close it.)* If 19G.3+ reaches four items, or admits
anything that did not come out of this segment's own work, the shape has
outlived its use and the remaining work gets its own segment — that is
the trigger 19C never had, and it is the only reason the concession
above is safe to make.

Items close independently, so each carries its own `### Doc impact` and
`### Status` and there is no segment-level `## Doc impact`.

### Items

| Item | Covers | State |
|---|---|---|
| **19G.1** | §8 move #3 — whether summary drift deserves a mechanism | **Closed** 2026-09-08 (PRs #2197 → #2202). Answered per class; all four rungs landed. |
| **19G.2** | §8 move #2 — regenerate `spec/operator_button_audit.md` §§4–5, which described a Session Home layout replaced 2026-08-18 | **Closed** 2026-09-08 (PR #2203). One PR, three `spec-writer` corrections. |
| **19G.3** | The patch queue below — three documentation corrections | **Closed** 2026-09-08. One PR; a fourth found beside them. |
| **19G.4** | `close_check` sees root-level `.md` — the first of the two carried open questions | **Closed** 2026-09-08. One PR. |
| **19G.5** | The six broken `§N` references the measurement found | **Closed** 2026-09-08. One PR. |
| **19G.6** | The C3 window boundary — `close_check`'s window excluded its own start commit | **Closed** 2026-09-08. One PR. |
| **19G.7** | The `§N` heading-validity check — and the seventh broken reference the 19G.5 measurement could not see | **Closed** 2026-09-08. One PR. |
| **19G.8** | A cited path is not a commitment — `close_check`'s prefixed-path false positive | **Closed** 2026-09-08. One PR. |
| **19G.9** | Archived sessions read "not opened" on `/me` for reviewer and observer rows | **Planned** 2026-09-08, not started. |
| 19G.10+ | Admitted only for work arising from this segment's own items. | Open — **empty** |

### Patch queue

Three one-line corrections found while doing Items 1 and 2, each out of
scope where it was found and each an instance of the class Item 1
conceded as unmechanizable — prose disagreeing with a source, with no
constant to derive from. Whether they are worth a shared item or one
PR is a judgment for whoever picks them up; they are listed together
because they were found together and share a cause.

| # | Where | What is wrong | Found by |
|---|---|---|---|
| a | `rrw_sdd_in_practice.md`, capability table | "Spec coverage enforced — **Not yet** … deferred", while `constitution.md` II cites `tests/unit/test_spec_coverage.py` as shipped 2026-09-05 | 19G.1 rung 2, extending the check's corpus to root-level docs |
| b | `spec/ui_elements.md` §"Inline-style buttons" | Records the Danger Zone's 2026-05-22 move to the Edit page as *"Current: migrated"* — half a round trip; 18R Item 4 brought the buttons back to Session Home | 19G.2, re-deriving §§4–5 |
| c | `app/web/routes_operator/_session_home.py` ~line 235 | The `/edit` redirect's comment says a non-owner "still gets **403**, not a bounce"; 19F PR 1 made that gate answer **404**, reserving 403 for the sys-admin exemption | 19G.2's `spec-writer` pass |

Entry **c** is code rather than prose, and is the one of the three that a
future check could plausibly catch — a docstring naming a status code
the gate does not return is derivable from the gate. Filed here rather
than in `docs/unenforced_conventions.md` §2 because nobody has measured
how many such comments exist.

§8's **move #1** is deliberately *not* an item here: it is Segment 20,
which has its own plan (`guide/segment_20_operator_polish_and_documentation.md`)
and is reserved until the institutional Azure deployment concludes.
Naming it here as well would give one piece of work two homes, which is
the failure `docs/status.md` and `guide/todo_master.md` between them
already make easy enough.

---

## Item 1 — Summary drift: what gets mechanized, and what is conceded

### Opportunity

`guide/codebase_assessment_08sep.md` §5 recorded four documentation
defects found in one window, each live for between three weeks and four
months, every one found by a human-directed audit and none by a check.
§8's move #3 asked whether the class deserves a mechanism and proposed a
shape for one: *a check that lists which documents summarise another and
flags them when the source changes.* The author deferred the question to
one session of thinking. This is that session.

The finding that decides it: **the four instances are four different
classes**, and the proposed mechanism targets exactly one of them.

| # | Instance | Prose disagrees with… | Class | Fixed by |
|---|---|---|---|---|
| 1 | `spec/permissions.md` stated the enumeration threat model backwards | **behavior** — nothing was its source | **D** | `4ed5455f` (19F PR 6) |
| 2 | `spec/visibility_policy.md` §3.1 stated the per-cell rule as the opposite of the constant it documents | **a code constant** (`_PER_CELL_VALID_MODES`) | **A** | `0acbcd2e` (19C Item 9) |
| 3 | Three files summarizing `spec/session_home.md` described a page retired three weeks earlier (18R Item 4) | **a source document's content** | **B** | 19C close (`0dc1807f`) |
| 4 | `docs/status.md` promised the technical-support contact as *"Segment 19C Item 8"* — Item 8 is the input-boundaries work — in three copies | **a document's internal numbering** | **C** | `1be3896d`, `874c5d61` |

Only row 3 is summary drift in the sense §8 meant. Row 2 is a constant
transcribed backwards, which Article II says to derive rather than watch.
Row 4 is not a summary at all — it is a pointer into another document's
item numbering, and the target never existed under that number. Row 1 has
no document on the other side to compare against.

**A correction to the shape of the question**, which is the reason this
item is worth a plan rather than a paragraph. The obvious adjacent
mechanism — validate every backticked repo-relative path in live prose —
**catches none of the four.** Row 4's pointer is not a path; row 3's
three summaries all named `spec/session_home.md` correctly and were wrong
about its contents. What that check catches is a **fifth class the
assessment did not count, because no instance of it had been looked
for**: at `5ab5e2f8` there are **84 broken path references in live prose**,
across 14 files, naming 37 distinct targets, of which 31 once existed and
were deleted, moved to an `archive/`, or carved into a package. It is
worth building on the strength of that 84, and not on the four.

Two further measurements, both at `5ab5e2f8`:

- **`docs/authentication.md` was retired *by a documentation sweep*
  (`fcc3a8c2`) and five live references to it survive**, one of them in
  `docs/security_posture.md`. The cadence that is supposed to catch this
  class generated an instance of it while running.
- **139 live references name a numbered section of another file**
  (`` `spec/permissions.md` §4 ``). That is class C's surface area, and
  it is larger than the path-reference surface anyone had noticed.

And one observation that belongs here because it is the same defect one
level up. `constitution.md` VI closes: *"The list of them should be
short, written down, and revisited when a constant appears that would
make one derivable."* **No such live list exists.** The nearest thing is
`docs/practice-audit-2026-09-04.md` §2, a dated audit table — and it has
itself drifted: rows 1b and 2 are marked "currently violated" and both
were mechanized the same morning by `tests/unit/test_doc_conventions.py`
(#2086, 37 minutes after that audit was committed — this read "#2092,
four days later" until the close; #2092 added a third check to the same
file later the same day), and row 3 records British spelling as "not a convention the
repository states", which stopped being true on 2026-09-07. A document
summarizing the state of another quietly stopped agreeing with it —
class B, in the document that catalogues the classes.

### Decision

**Answer move #3 per class, not as one question.** Two are mechanized,
one is deferred to a measurement, one is conceded in writing. Plus the
uncounted fifth, built on its own evidence.

**A — prose that restates a code constant → derive it, case by case.**
`tests/unit/test_doc_conventions.py` already does exactly this twice
(lifecycle display labels; color primitives read out of `base.html`).
Row 2 is a third instance and the constant is sitting there. A prototype
run 2026-09-08 parses all six cells of §3.1's table and matches
`_PER_CELL_VALID_MODES`; run against the pre-`0acbcd2e` text it reports
`DRIFT`. This is not a new kind of mechanism, it is one more instance of
the one Article II already prescribes — which is the argument for doing
it and the reason it is cheap.

**B — prose summarizing another document → do not mechanize. Concede.**
*This is the assessment's own proposal, and it is the rejected
alternative*, on `constitution.md` VI:

- It needs a hand-maintained registry of which documents summarize
  which. VI names a growing allowlist as the thing that disqualifies a
  rule from becoming a test.
- Its signal is "source edited more recently than summary". On a hot
  source — `spec/architecture.md`, `spec/lifecycle.md` — that fires on
  every edit, and clearing it needs a human to judge whether *this* edit
  touched what the summary claims. There is no way to record "checked,
  still agrees" except touching the summary or adding an allowlist entry,
  so the check sits red for reasons that are usually nothing. That is the
  argued-with, then raised, then disabled path VI describes, and a
  disabled check leaves the practice worse than the paragraph did.
- Its yield is one instance in four.

What replaces it is a habit rather than a mechanism, written as guidance:
**a change that retires a page, a section or a file greps for what points
at it, in the same change.** `fcc3a8c2` is the evidence that this does
not happen by itself.

**C — pointers into another document's internal structure → measure
before committing.** Rows 3 and 4 both fail here and neither proposed
check reaches them. A heading-validity check is conceivable — 139 live
`§N` references — but its cost depends on how consistently the *targets*
number their sections, which is not measured. Filed as this item's open
question rather than as a ladder rung, because a check that first
requires a section-numbering convention to be true everywhere is a much
larger change than it looks.

**D — prose about behavior with no source → conceded outright.** No
mechanism is proposed and none is obvious; this is what Article III's
cold reader and Article IV's human verifier are for. It goes on the list
VI promises, which this item also creates, because a concession nobody
wrote down is indistinguishable from an oversight.

**E — broken path references (the uncounted class) → mechanize, on its
own 84.** A test reading every backticked repo-relative path in live
`spec/`, `docs/` and `guide/` prose, failing on one that names nothing.
It derives from the filesystem and git history, so there is no registry
to maintain and nothing to keep in step by hand. It does not answer move
#3 — it answers a question nobody had asked, which the investigation into
move #3 turned up.

### Semantics

**Class E — the path-reference check, at the boundaries:**

- **Forward references.** 6 of the 37 broken targets never existed:
  planned modules named by a deferred spec (`app/services/blob_store.py`),
  a planned directory (`tests/e2e/`), a placeholder (`guide/segment_NNA.md`),
  an elided path (`spec/archive/.../reconciling_regeneration.md`), and a
  dotted attribute reference (`app/services/session_lifecycle.is_editable`)
  that is not a path at all. The last three are excluded by shape — a
  path containing `...`, a segment matching `NN`, a dotted tail that is
  not a real extension. The genuine forward references carry an inline
  marker on the line, the pattern `test_doc_conventions.py` already uses
  for deliberate historical references, so the exception sits next to the
  claim rather than in a list that grows somewhere else.
- **Dated documents opt out wholesale.** A snapshot, a sweep or an
  archived plan is a record of what was true on its date; a reference
  that was right then is not a defect now. Live prose only — the same
  line `test_doc_conventions.py` already draws.
- **A directory reference** (`app/web/views/`) satisfies a reference to
  the module it replaced only if written as the directory. `app/web/views.py`
  after the carve is stale and should fail; 17 of the 84 are exactly this.
- **Second run** is identical: the check reads the tree, holds no state.

**Class A — the visibility-grid check, at the boundaries:**

- It is coupled to the table's *shape*, not only its content: it locates
  §3.1, takes rows beginning `` | ` ``, and reads backticked tokens from
  each cell, intersected with the mode vocabulary so window names and
  prose fall out. Against the pre-`0acbcd2e` text — which had different
  columns entirely — it parses zero rows and reports every cell as
  drifted. **It fails closed, but its message on a restructure is less
  useful than on a wrong value.** Accepted: a restructure of a table that
  transcribes a constant should draw a reader's eye, and the failure says
  which constant to check.
- Lands in `spec/visibility_policy.md` §3.1, which already names the
  constant as its source; the check makes that sentence load-bearing.

### Judgment calls — decided

- **Answer per class rather than yes or no** (2026-09-08). §8 asked one
  question about four instances that turned out to share nothing but the
  symptom. Answered as one question it forces a false choice: a mechanism
  justified by four instances that catches one, or a concession that
  gives up two classes which are cheaply derivable.
- **Build the path-reference check anyway, on its own evidence**
  (2026-09-08). It answers none of move #3 — a fact worth stating plainly
  rather than letting the 84 borrow authority from the four. It earns its
  place because 84 live instances is a larger number than the thing that
  prompted the question.
- **Reference validity is the first rung, not the grid check** (2026-09-08).
  It is the larger of the two and the one with a cleanup cost, so it sets
  the segment's shape; the grid check is 40 lines against a green tree
  and can land any time after.
- **Fix all 84 references before the check, not behind it** (author,
  2026-09-08). The alternative — land the check plus a `close_check`
  step that validates only the paths a close touches, then drain the
  backlog behind it — was offered and declined. A check that ships red is
  a check whose first job is to be silenced.
- **Inline markers, not an allowlist file, for forward references**
  (2026-09-08). VI disqualifies a growing allowlist; a marker on the line
  cannot grow anywhere the reader is not already looking.
- **The conceded class gets written down as a live list** (2026-09-08),
  because VI promises one and there is none — only a dated audit that has
  itself drifted.

### Blast radius (measured)

At `5ab5e2f8`, 2026-09-08. Two commands produce every number below; the
second is the rung 1 PR's working script and is reproduced in full in
its body.

```bash
# C1 — every backticked repo-relative path reference in spec/ docs/ guide/
grep -rhoE '`(spec|docs|guide|app|tests|tools)/[A-Za-z0-9_./-]+`' \
    spec/*.md docs/*.md guide/*.md | wc -l

# C2 — of those, the ones in LIVE prose that name nothing.
#      Live = filename does not match codebase_assessment_ | sweep_ |
#      practice-audit- | segment_ (dated records opt out wholesale).
#      Each target tested with Path(t).exists(); each broken target then
#      tested with `git log --all -1 -- <target>` to split
#      once-existed from never-existed.

# C3 — section-level references, the form PR 2 does not cover
grep -rhoE '`(spec|docs|guide)/[^`]+\.md` §[0-9]' \
    spec/*.md docs/*.md guide/*.md | wc -l
```

| What | Count | From |
|---|---|---|
| Backticked repo-path refs across all `.md` | 2,031 † | C1 |
| …of those, in live prose | 1,789 | C2 |
| **Broken refs in live prose** | **84** | C2 |
| Distinct broken targets | 37 | C2 |
| …that once existed (deleted, moved, or carved into a package) | 31 | C2 |
| …that never existed (forward reference or malformed) | 6 | C2 |
| Files carrying at least one broken ref | 14 | C2 |
| …of which two ledgers hold 60 of the 84 | `docs/status.md` 37, `guide/todo_master.md` 23 | C2 |
| Section-level (`§N`) references — class C's surface | 139 † | C3 |
| Existing derived doc checks to extend | 5 tests, 200 LOC | `wc -l tests/unit/test_doc_conventions.py` |

† Taken at `5ab5e2f8`, before this plan existed. C1 and C3 scan every
`.md` including dated ones, so both rise once this file lands, and rise
again with every edit to it — this plan cites paths and sections of its
own. Deliberately not pinned to a post-landing figure: quoting one would
make the footnote stale on the next revision of the paragraph above it,
which is the failure this whole item is about. Re-run C1 and C3 for a
current value. The live-prose numbers are unaffected in either
direction — a `segment_*` filename is a dated record and opts out of that
set — so the 84 is measured on the same corpus before and after.

### PR ladder

1. **PR 1 — repoint the 84 broken references.** Lands: every live-prose
   path reference resolving, or carrying a forward-reference marker.
   Mostly mechanical (a moved file gains its `archive/` prefix, a carved
   module becomes its package directory), but 28 need a judgement about
   what the right target is *now* — `docs/authentication.md`'s five
   references have to point at whatever absorbed it, which is a reading,
   not a rename. Must not touch: dated snapshots, sweeps, archived plans;
   any prose beyond the path itself.
2. **PR 2 — the class E path-reference check.** Lands: the test in
   `tests/unit/test_doc_conventions.py`, green from its first commit
   because PR 1 went first; the forward-reference marker documented
   beside the existing historical marker. Must not touch: any `.md`
   content — if PR 2 has to edit prose, PR 1 was incomplete.
3. **PR 3 — derive `spec/visibility_policy.md` §3.1 from
   `_PER_CELL_VALID_MODES`.** Lands: the prototype as a real test, same
   file, same idiom as the lifecycle-label check. Must not touch: the
   constant, or the spec's prose.
4. **PR 4 — the list VI promises.** Lands: `docs/unenforced_conventions.md`,
   with class D and the rejected class B registry on it, and a pointer
   from `constitution.md` VI. Names `docs/practice-audit-2026-09-04.md`
   §2 as its dated predecessor rather than replacing it in place — an
   audit is a record of its date and is not rewritten. Must not touch:
   the constitution's rule text; VI gains a pointer, not a new rule.

### Definition of done

- C2 reports 0 broken references: every one of the 84 either resolves or
  carries a forward-reference marker.
- The class E check fails when a broken reference is introduced into a
  live document, and passes when the same reference is added to a dated
  one — both directions exercised, not just the green case.
- The §3.1 check passes, and fails when run against `0acbcd2e~1`.
- A live list of unenforced conventions exists, is linked from
  `constitution.md` VI, and carries class D.
- The rejected registry mechanism is recorded with its reason where a
  future reader will look for it — not only in this plan.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Does the `§N` reference form deserve the same treatment?** 139 live
  references name a numbered section of another file — class C's surface,
  and row 4's defect exactly: a pointer whose target never carried that
  number. PR 2 does not reach it, and neither does anything else. Whether a heading-validity check is
  cheap depends on how consistently sections are numbered in the targets,
  which is not yet measured. **Decides:** a measurement, before any
  commitment; filed here rather than in the ladder because a check that
  needs a heading-numbering convention to be true first is a bigger
  change than it looks.
- **`close_check` cannot see the file this item most commits to.** Its
  `COMMITTED_PATH` pattern matches backticked `.md` paths under `spec/`
  or `docs/` only, so the `constitution.md` bullet below — a root file —
  is silently not counted, and the item's manifest reads as three paths
  rather than four. Nothing is wrong with the run; the scope is simply
  narrower than the manifest it validates, which is the same shape of
  defect this item is about. **Decides:** the author — whether to widen
  the pattern to root-level `.md` (a one-line change with an unmeasured
  blast radius across every existing plan's manifest) or to record the
  limit and keep root files out of doc-impact manifests deliberately.
  Not folded into the ladder: it changes a tool every open plan is
  measured by, which is its own slice.

**Both of the above outlived Item 1 and are promoted to
`## Carried open questions` at the end of this file** (2026-09-08).
Neither is Item-1-shaped: the `close_check` scope affects every plan in
the repository, and the `§N` question is a candidate for a later item
rather than a loose end of this one. Left here as well, struck through
nowhere, because the reasoning that produced them belongs with the item
that found them.

- ~~**Does `docs/practice-audit-2026-09-04.md` §2 want a dated
  correction now** that two of its rows have been mechanized and one has
  been overtaken?~~ **Answered at PR 4: yes, as an annotation.** The
  table is untouched and a dated note at the head says which three rows
  have been overtaken and by what. Additive and reversible.

### Out of scope

- **The other two moves from §8** — Segment 20 (move #1) and the
  regeneration of `spec/operator_button_audit.md` §§4–5 (move #2). Both
  are this segment's other items, planned separately when they start.
- **Any prose rewriting during PR 1.** A broken pointer is repointed; a
  paragraph that reads badly around it stays as it is. Mixing the two
  makes an 84-line mechanical diff unreviewable.
- **A spelling sweep.** `CLAUDE.md` forbids one explicitly, and PR 1
  touches ~14 files at exactly the density that would tempt it.
- **Retrofitting the check to `app/` docstrings.** They carry path
  references too and are not measured here. Filed, not planned.

### Doc impact

*`close_check 19G.1` reports C2 FAIL until PR 4 lands, because
`docs/unenforced_conventions.md` does not exist yet. That is the check
working: C2 asks whether a committed path exists, which is a question for
the close, not for the plan. The Definition of done requires exit 0 at
the close, by which point the file is there.* — **Resolved 2026-09-08:
PR 4 landed the file and `close_check 19G.1` exits 0 on C1–C6.**

- `docs/unenforced_conventions.md` — **new.** The live list Article VI
  promises: one row per convention deliberately left unenforced, what it
  is written down at, why no check exists, and what constant would make
  it derivable. Seeded with class D and with the class B registry
  rejected here, so the reasoning is findable from where a future reader
  will look rather than only from an archived plan (PR 4).
- `constitution.md` — VI gains a pointer to that file (PR 4). Not
  counted by `close_check` — see Open questions.
- `docs/practice-audit-2026-09-04.md` — a dated annotation recording
  that rows 1b and 2 were mechanized by **#2086** (this bullet said
  #2092 when written; the annotation itself was corrected before it
  landed — #2092 added a third check to the same file later the same
  day) and row 3 overtaken by the 2026-09-07 spelling entry; the table itself
  is not rewritten. **Done** (PR 4); the open question it was pending on
  is answered in `## Carried open questions`.
- `spec/visibility_policy.md` — §3.1 gains one sentence recording that
  the table is now derived from the constant by a test, not merely
  transcribed from it (PR 3).
- `guide/README.md` — the `segment_*.md` row already covers this file;
  no change expected. <!-- doc-impact-waived: generic row already covers a new live plan; revisit only if 19G changes the folder's shape -->
- `docs/status.md` — **one row at the close**, not one per rung: four
  rungs in a day describing one decision reads better as a single entry,
  and the plan carries the per-rung detail.
- `rrw_sdd_in_practice.md` — three citation pointers repointed to
  `guide/archive/` (PR 2). Not a content edit; named here because the
  file sits outside `close_check`'s `spec/`-and-`docs/` scope and would
  otherwise go unrecorded — the same blind spot as the `constitution.md`
  bullet above. <!-- doc-impact-waived: path repoints only, no prose changed; recorded for the manifest's completeness rather than as a spec commitment -->

### Status

**2026-09-08 — PR 1 landed, and the count it was named for was wrong in
an instructive way.**

The rung read *"repoint the 84 broken references … but 28 need a
judgement about what the right target is now."* Both halves needed
correcting once the 84 were read one at a time rather than counted.

**Only 36 were repointed. 42 are history and were left as written.**
The discriminator turned out to be grammatical, not structural: a
reference that says *"Plan: X"*, *"spec: X"*, *"As-built layout: X"*,
*"Reference implementation: X"* is a pointer a reader is meant to
follow, and if X has moved the pointer is broken **today** — those were
repointed, archived plans included. A reference that says *"retired X"*,
*"formerly X"*, *"renamed SEEDS in X"*, *"split X into a package"* is a
record of what was true on its date, and repointing it would falsify the
record.

**This was already the repository's policy and the plan did not know
it.** `docs/status.md`'s own 19F row says it in as many words —
*"`docs/status.md`'s historical rows were left as written — a log must
be true of its date, not of today"* — decided during 19F and never
carried anywhere a planner would find it. The rung's "28 need a
judgement" undercounted because it treated the question as *which
target* rather than *whether to repoint at all*.

**Where the 84 went:**

| Disposition | Count |
|---|---|
| Repointed to a live target | 36 |
| Left as history, covered by a section marker | 36 |
| Left as history or as a forward reference, covered by an inline marker | 12 |
| Unaccounted | **0** |

**The section marker is new and is the rung's one design decision.**
`docs/status.md` §Project timeline, §Segments shipped and
`guide/todo_master.md` §Done are dated registers inside otherwise-live
files. Marking 36 lines individually would have been noise; marking the
two files wholesale would have blinded the check to the live half of the
two most-referenced documents in the repository (`## Capabilities
today`, `## What's deliberately not yet there`, `## Upcoming`). So the
opt-out is scoped to the section: `<!-- path-ref-ok: section -->` under
the heading, running until the next `##`. It mirrors the existing
`<!-- retired-term-ok: file -->` idiom one level down. PR 2 reads both
it and the inline `<!-- path-ref-ok -->`.

**Two references were rewritten rather than repointed**, because the
path was never the problem:
`spec/sessions_overview.md` said `` `app/services/session_lifecycle.is_editable` ``,
a dotted attribute written as a path, now `` `is_editable` in
`app/services/session_lifecycle.py` ``; and `spec/assignments.md` cited
`` `spec/archive/.../reconciling_regeneration.md` `` — an elided path
that was wrong twice over, since the file is live at
`spec/reconciling_regeneration.md` and never went to an archive. The
Semantics section's "excluded by shape" list is one item shorter as a
result: the dotted form is fixed at source rather than tolerated.

**Not done in this rung, and not a surprise:** PR 2's check, which is
what makes any of this hold. Until it lands, the tree is merely correct
rather than kept correct.

**2026-09-08 — PR 2 landed. Green from its first commit, and three
things the plan did not anticipate.**

**The shape-exclusion list is empty.** Semantics committed to excluding
by shape — a path containing `...`, a `NN` placeholder, a dotted
attribute tail. None was needed: PR 1 fixed two at source and marked the
third, so the check has no shape rules at all and one fewer thing to
argue about. A tolerated exception and a fixed defect look identical from
a passing suite; only one of them stays fixed.

**The corpus grew to the repository root, and that cost three
references.** The rung said *"must not touch any `.md` content — if PR 2
has to edit prose, PR 1 was incomplete."* It touched one file. Scoping
the check to PR 1's corpus (`spec/`, `docs/`, `guide/`) would have left
`constitution.md`, `CLAUDE.md` and `rrw_sdd_in_practice.md` unchecked —
the three most load-bearing documents in the repository, and precisely
the blind spot this item already filed against `close_check`. Extending
the corpus found **three broken references in
`rrw_sdd_in_practice.md`**, all citation pointers to since-archived
plans, all repointed here. Three lines in one file is not a second
cleanup; baking a known gap into a coverage check would have been worse
than the rule the rung wrote to prevent one.

**The section marker needed hardening the plan had not specified.**
As first written the marker would have been honoured anywhere inside a
`##` section, which would have let a future editor drop one mid-section
to silence a single inconvenient line — an opt-out that reads as
structural but acts as a per-line escape. It is now honoured **only as
the first non-blank line under the heading**, which is where PR 1 placed
all three, and a mutation moving one eight lines down fails the check.

**A second test, for the direction nobody would notice.** An inline
marker whose reference has since started resolving is drift of the same
kind as a dangling reference, and the suite stays green through it. The
both-directions rule is `test_spec_coverage.py`'s and it applies here:
`test_no_inline_path_marker_outlives_the_reference_it_covers` fails on a
marker covering nothing. Section markers are exempt by design — they
describe what a section *is*, so one covering no broken reference today
is still true.

**Mutation-checked in six directions**, each failing exactly one test and
the right one: a broken reference added to live prose; the same
reference added to a dated document (passes, correctly); an inline
marker deleted; a section marker deleted; a section marker moved off its
first-line position; and an inline marker made stale.

**Found, not fixed, and filed rather than folded in:**
`rrw_sdd_in_practice.md`'s capability table still reads *"Spec coverage
enforced — Not yet … deferred"*, while `constitution.md` II cites
`tests/unit/test_spec_coverage.py` as shipped on 2026-09-05. That is a
live class B instance — prose disagreeing with another document — in the
document the constitution is derived from, and it is exactly the class
this item conceded as unmechanizable. Left for the author: correcting it
is a content edit, and folding one into the PR that builds the reference
check would widen a check into an edit.

**2026-09-08 — PR 3 landed. The accepted weakness turned out not to be
necessary.**

Semantics conceded that the grid check would be *"coupled to the table's
shape, not only its content"*, and that **"its message on a restructure
is less useful than on a wrong value"** — a restructured table would
report every cell as drifted rather than saying the table had moved.
That was accepted at planning time and did not survive contact: the
check now asserts **parseability separately from content**, so a
restructure fails `test_the_visibility_grid_table_is_still_a_grid` with
"no longer yields a table of `audience` rows against `window` columns",
and only a genuinely wrong value reaches the per-cell comparison. Run
against the pre-`0acbcd2e` text — the real defect, whose heading and
columns were different entirely — it fails with exactly that message.

**Nothing about the grid is hardcoded in the test.** The prototype in
the Decision carried a literal mode vocabulary. The built version reads
the audiences and windows from `_PER_CELL_VALID_MODES`'s own keys and
the vocabulary from `MODE_LABELS`, so a fourth mode added to the label
map fails here until §3.1 documents it. **Windows come from the table's
header row rather than from column order**, which was not in the plan
and matters: a swapped pair of columns now reads as swapped values and
fails, where positional parsing would have passed it.

**Mutation-checked in seven directions**, each failing the right test: a
mode added to a cell; a mode dropped from a cell; the two column headers
swapped; a row deleted; the heading renamed; the **constant** changed
rather than the doc; and the historical pre-fix section spliced back in.
The last three fail the shape test first, which is the point of
separating it.

**One sentence added to the spec**, as the manifest committed: §3.1 now
says the table is derived rather than transcribed, names the parser, and
tells a future editor which part is free prose (all of it) and which
part is load-bearing (the backticked mode names in each cell). A check
nobody knows about gets worked around by someone rewording a table in
good faith.

**2026-09-08 — PR 4 landed. The list needed a second half the plan had
not imagined, and writing it found two things.**

**The open question is answered: yes, annotate.**
`docs/practice-audit-2026-09-04.md` gains a dated note at its head and
its §2 table is left exactly as written, which is what Article V
prescribes for a dated document. Three of its rows had been overtaken —
rows 1b and 2 mechanized 37 minutes after it was written, row 3's premise
reversed by the 2026-09-07 spelling entry — and a reader arriving at
that table cold had no way to know. Reversible: the note is additive and
the author can strike it.

**The list splits in two, and the split is the point.** The plan
described one list. Writing it made a distinction impossible to ignore:
a rule that *cannot* be checked cleanly and a rule that *could* be but
nobody has written are opposite facts, and filing them together lets the
second quietly acquire the dignity of a decision. So §1 is Article VI's
list proper, and **§2 is a revisit queue** — the half VI's trade-off asks
for ("revisited when a constant appears that would make one derivable")
and which a single list cannot express.

**Two findings, both from measuring rather than assuming:**

- **"Route handlers stay thin" cannot be checked today because the tree
  does not obey it.** 17 routing modules contain `select(`. That earns
  it a place in §1 with an honest reason — a check failing on 17 files
  the day it lands is exactly VI's argued-with-then-disabled sequence —
  and a note that it moves to §2 once the SQL moves into services. The
  entry is about the gate, not a licence on the rule.
- **"No slice-to-slice imports in `app/web/routes_operator/`" is clean:
  20 slices, 0 violations.** Mechanizable with no allowlist and green
  from its first commit — the same shape as rung 2. It goes in §2 as the
  strongest candidate there, and the best moment to pin a convention is
  while it is still being followed by hand.

**Every claim in the file was falsified, not carried.** The 2026-09-04
audit's rows 1c and 4 are quoted by many documents; this list re-ran
both against the current tree rather than repeating them. Bypassing
`| lifecycle_label` in a live template: **2940 passed**. A
`sqlalchemy.dialects.postgresql` import in a model, used as a column
type so `ruff`'s `F401` cannot fire: **`ruff` clean, 2940 passed**. A
list of unenforced conventions whose own claims have gone stale would be
self-refuting.

**One error caught in passing.** The first draft of the audit annotation
credited `tests/unit/test_doc_conventions.py` to #2092. It shipped in
**#2086** (`04962397`); #2092 added a third check to the same file four
days later. Both numbers appear in that audit, which is how the wrong
one got picked up.

**The ladder is complete.** `close_check 19G.1` C2 now passes. What
remains before the item closes is the close sequence itself, not a rung:
the `spec-writer` pass over the doc-impact specs, the `docs/status.md`
row, and the two open questions above it — the `§N` heading-validity
measurement, and whether `close_check`'s `COMMITTED_PATH` should widen
to root-level `.md`.


**2026-09-08 — CLOSED. The `spec-writer` pass found two wrong numbers,
both mine, in the item about documents that stop agreeing with their
sources.**

Neither was caught by a check. Both were caught by a reader that had not
written the thing — Article III, doing the job it exists for, on the one
item least entitled to need it.

**Flag 1 — "21 slices, 0 violations" was 20.** The verification script
globbed `_*.py`, which matches `__init__.py`. The reader put it at 20 by
counting `include_router` calls; checking both ways confirms **20 slices,
one `_shared.py` the convention names as the legal import target, and
`__init__.py` — 22 files, 20 slices.** The reader's diagnosis was right
and its cause was worse than it guessed: not `_shared.py` miscounted,
but the package initialiser counted as a slice. The "0 violations" half
was independently confirmed and stands. Corrected in
`docs/unenforced_conventions.md` §2.2, this file, and `docs/status.md`.

**Flag 2 — "mechanised four days later" was 37 minutes.**
`docs/practice-audit-2026-09-04.md` was committed at 09:12:37 UTC and
`tests/unit/test_doc_conventions.py` at 09:49:43 UTC — the same morning,
not four days apart. The error started in this item's Opportunity, was
carried into the Doc impact bullet, into PR 4's Status entry, and out of
the plan into a **shipped annotation on the audit itself**, where it
misinformed the exact reader that annotation exists to serve. Four
sites, all corrected; #2092's "four days" is likewise "later the same
day" (11:57 UTC).

**What that says, and it is the item's own thesis turned inward.** The
class this item conceded — prose disagreeing with a source, with no
constant to derive from — is exactly what both flags were. A date and a
count are the *most* checkable kind of claim, and neither had anything
checking it. The concession in §1.4 is therefore not a corner case: it
covers the failure mode that this item, with its subject matter fresh in
mind, committed twice in a day. The list is right that no cheap
mechanism exists; it is also evidence that the human-or-agent reader is
carrying real load, not ceremony.

**Intended versus done.**

| Rung | Intended | Done |
|---|---|---|
| 1 | Repoint 84 broken references | 36 repointed, 48 marked, 0 unaccounted — only 36 *should* be repointed, and the repository had already decided that in 19F |
| 2 | The path-reference check | Landed, plus a second test for stale markers, plus a corpus widened to root-level docs at the cost of 3 more repoints |
| 3 | Derive §3.1 from the constant | Landed, with parseability split from content so the plan's accepted weakness did not have to be accepted |
| 4 | The list Article VI promises | Landed, split into "unenforced by decision" and "unenforced by nobody having written it" |

Three of the four rungs came in *larger* than planned and one weakness
came in smaller. The blast radius was right about the count (84) and
wrong about its meaning, which is the failure a measured blast radius is
least protected against: it counts instances, not what they are.

**Close sequence.** `close_check 19G.1` exits 0 on C1–C6. `spec-writer`
run over the four doc-impact files; two flags raised, both real, both
fixed above, none changing a decision. `docs/status.md` row added. The
plan **stays in `guide/`** — this is an item close, not a segment close,
and 19G.2 is still open.


---

## Item 2 — Regenerate the button audit's Session Home sections

### Opportunity

`spec/operator_button_audit.md` §§4–5 described the Session Home layout
as it stood on 2026-05-22 and carried a banner naming three false
claims: that the Danger Zone had moved to an Edit Session Details page,
that Session Home had an Extract Data card, and a Next-Action state
table predating the Workflow card. The banner was added at 19C's close
and the regeneration deferred — correctly, since 19C was closing
*because* it kept absorbing one more thing.

It matters more than a stale section usually would because `CLAUDE.md`
points at this file for button vocabulary. A reader sent here for the
canonical role of a button lands two sections away from three false
statements about the page they are most likely editing.

### Decision

**Re-derive §§4–5 from the templates, and point rather than copy for the
state machine.**

`spec/workflow_card.md` already owns which button appears in which of
the Workflow card's states, across §§240–589. Regenerating §5a as a full
state table would produce a second copy of that — a class B drift
instance manufactured by the item that exists to clear one. So §5a
records the **vocabulary** (fifteen sites, four roles, no inline styles)
and points at `spec/workflow_card.md` for the cascade.

*Rejected: renumber the button table.* The audit numbers buttons
1–143 running; the retired page's #16/#17 and the Danger Zone's
#17a/#17b would all shift. New buttons take #144–#160 and the two
Danger Zone entries **keep their old numbers**, because those are
literally the same two buttons that moved and renumbering them loses the
thread a reader follows.

### Semantics

- **A retired page keeps its section**, marked retired, with a table of
  where its buttons went. Deleting §4 would leave a reader with a
  dangling `/edit` bookmark and no explanation.
- **The audit stays a dated snapshot.** §§4–5 carry a 2026-09-08
  re-derivation date; every other section keeps its own. The header's
  refresh history gains a line rather than being rewritten.
- **Findings elsewhere in the file that describe these surfaces** are
  annotated as superseded, not deleted — they are dated findings, and
  the reasoning in them outlives the surface.

### Judgment calls — decided

- **Point at `spec/workflow_card.md` rather than copy its table**
  (2026-09-08). A duplicated state machine is the drift class this
  segment exists to reduce.
- **Two drift findings annotated though they sit outside §§4–5**
  (2026-09-08). Both describe the surfaces this item re-derived, in the
  present tense, and both were false. Regenerating §§4–5 while leaving
  "the current activated-state Next Action surface renders…" three
  hundred lines down would have moved the falsehood rather than removed
  it.
- **The Extract Data page gets a note, not a new section** (2026-09-08).
  Following the card to `session_extract_data.html` and auditing that
  page is a new section, not a re-derivation of §5; the gap is recorded
  where the card used to be.

### Blast radius (measured)

At `ffb1a4a6`, 2026-09-08.

| What | Count |
|---|---|
| Sections re-derived | 2 (§4, §5), 5 sub-sections |
| Button sites enumerated from the templates | 24 across `session_detail.html` (7), `next_action_card.html` (15), `_quick_setup_card.html` (3, minus 2 already numbered) |
| Templates read | 3 + 2 included partials |
| Drift findings annotated | 2 |
| Other files changed | 0 |

### PR ladder

1. **PR 1 — the regeneration.** Lands: §§4–5 re-derived, the banner
   replaced by a refresh note, the two superseded drift findings
   annotated. Must not touch: any other section's tables, the role
   legend, or any file but this one.

### Definition of done

- §§4–5 contain no claim contradicted by the templates at `ffb1a4a6`.
- The stale-warning banner is gone, replaced by a refresh note that says
  which sections were re-derived and when.
- `tests/unit/test_doc_conventions.py` passes — including the
  path-reference check, which this item's own draft tripped.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Does `spec/ui_elements.md` want the same treatment?** Its
  inline-styled-buttons section records the Danger Zone's 2026-05-22
  move to `session_edit.html` as *"Current: migrated"*, which is half a
  round trip — the buttons came back. Not fixed here: it is a different
  file and a different section, and this item's scope is the two
  sections named. **Decides:** the author.

### Out of scope

- **A section for the Extract Data page.** See Judgment calls.
- **Re-deriving any other section.** Each carries its own date; a
  whole-file re-audit is the periodic refresh the Maintenance section
  describes, not this item.

### Doc impact

- `spec/operator_button_audit.md` — §§4–5 re-derived from the templates;
  the stale banner replaced by a refresh note; two superseded drift
  findings annotated (PR 1).
- `docs/status.md` — row at the close.

### Status

**2026-09-08 — landed in one PR, and the rung-2 check caught the author.**

The draft of §4 wrote `` `app/web/templates/operator/session_edit.html`
no longer exists `` without the `<!-- path-ref-ok -->` marker that rung 1
had placed on the line it replaced.
`test_every_path_reference_in_live_prose_resolves` failed, named the
file and line, and told me which of repoint-or-mark applied. **The check
built four rungs ago caught a regression introduced by the person who
built it, in a sentence whose whole subject is a retired file** — which
is the argument for Article II in one line: the constant does not get
tired of checking.

**And then the other rung-2 test caught the author too, on a real
limitation of the check.** The `docs/status.md` row for this item quoted
the escape marker literally while *describing* it. The check cannot tell
a marker from a mention of one, so the row read as a marker covering a
line whose references all resolve —
`test_no_inline_path_marker_outlives_the_reference_it_covers` fired,
correctly by its own rule and unhelpfully by intent. Reworded to name
the marker without spelling it. **Filed, not fixed:** a mention-versus-use
distinction would need the check to parse markdown code spans, which is
more machinery than the trap costs. Worth knowing that the plan files
escape it only by accident — a `segment_*` filename is outside the
live-prose corpus, so this document may quote the marker freely and
`docs/` may not.

Everything else went as planned. The one judgment that grew was
annotating two drift findings outside §§4–5: both described the
regenerated surfaces in the present tense and both were false, so
leaving them would have relocated the defect rather than fixed it.

**`spec-writer` adjudication — three flags in the spec, all real, all
mine; one in code, filed.**

- **A cross-reference to the wrong section.** §4's "Was → Now" table
  sent buttons #16 and #17 to **§5c** (Quick Setup) instead of **§5b**
  (Session Details). The two rows beside them, #17a and #17b, point at
  §5e correctly — so the table was half right, which is the version a
  reader trusts. Corrected.
- **A justification I inferred rather than checked.** Rows #155 and
  #160 described their `.btn.alert` Cancels as *"recovery inside a lock
  card, per §6"*. Neither is in a lock card: #155 sits on a
  `.banner.banner-warning` and #160 on a `.banner.banner-error`, and
  `.card.lock` appears in neither template. §6 offers the lock card as
  an **example** of Outline-amber, and I read the example as the
  definition. The role was right and the reason was wrong — which is
  the more durable error, because a reader copies the reason. Both rows
  now cite the inline-banner convention in `spec/visual_style_rrw.md`
  §5a, and say plainly that §6's lock card is one use of the role, not
  its definition.
- **A misquoted heading.** The file cited `spec/ui_elements.md`
  §"Inline-styled buttons"; the heading is "Inline-style buttons". The
  substance of the citation — that the entry records only the first half
  of the Danger Zone's round trip — was confirmed correct.

**Filed, not fixed — a stale code comment.**
`app/web/routes_operator/_session_home.py:235` says the `/edit` redirect
keeps its gate *"so a non-owner still gets 403, not a bounce"*. Since
19F PR 1 that gate answers **404** for an ordinary non-owner, reserving
403 for the sys-admin exemption. It is one line in a file this item's
ladder says not to touch, and it is code rather than spec. Recorded here
and in the PR for the author.

**Worth noting what the pass did *not* find.** The fifteen button sites,
every label and class, the counter-intuitive role mapping
(`danger-solid` = Alert filled amber, `alert` = Outline-amber), and both
superseded-annotation claims were re-derived independently and matched.
The three flags were all in the connective tissue — a section number, a
justification, a heading — which is where a document that reads fluently
hides its errors.


---

## Item 3 — The patch queue

### Opportunity

Three documentation corrections, each found while doing Items 1 and 2,
each out of scope where it was found, and each an instance of the class
Item 1 conceded as unmechanizable: prose disagreeing with a source, with
no constant to derive from. Listed in "Patch queue" above with where
they came from.

They are worth doing together rather than singly because they are one
finding repeated: **a claim that was true when written, in a document
nobody re-read when the thing it described changed.**

### Decision

Fix all three in one PR, and in each case **say what the claim used to
be**. A silent correction loses the only evidence that the class exists;
these three are the standing test of whether Item 1's concession was
right, and a test whose failures are quietly erased proves nothing.

*Rejected: fix the two prose ones and leave the code comment.* It is the
one of the three a future check could plausibly derive — a docstring
naming a status code its gate does not return — so leaving it would have
kept the most mechanizable instance as the unfixed one.

### Judgment calls — decided

- **A fourth was fixed alongside** (2026-09-08). The same table as patch
  (a) said `tests/unit/test_doc_conventions.py` had **3 checks**; it has
  **9**. Found while correcting the row above it, same table, same
  class, one line. Leaving a number I had just read to be wrong would
  have been a choice, not a scope boundary.
- **Each correction is dated in place** (2026-09-08), not silently
  applied — Article V, and the evidence argument above.

### Blast radius (measured)

| What | Count |
|---|---|
| Files changed | 3 (`rrw_sdd_in_practice.md`, `spec/ui_elements.md`, `app/web/routes_operator/_session_home.py`) |
| Claims corrected | 4 (three queued + one found beside them) |
| Code changed | none — the third is a comment |
| Tests changed | none |

### PR ladder

1. **PR 1 — the four corrections.** Must not touch: anything but the
   claims named, and no behaviour.

### Definition of done

- Each of the three queued claims is true, and says what it used to say.
- `pytest -q -n auto` green with no test edited — this item changes no
  behaviour, so a changed test would mean it did.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. The two the segment carries are above and are not this item's.

### Out of scope

- **Any mechanism for this class.** Item 1 settled that; these are the
  instances, not a reopening of the decision.

### Doc impact

- `spec/ui_elements.md` — the inline-style-buttons entry corrected: the
  Delete buttons came back to Session Home when 18R Item 4 retired the
  page they had moved to (PR 1).
- `rrw_sdd_in_practice.md` — the "Spec coverage enforced" row flipped
  from "Not yet … deferred" to enforced-since-2026-09-05, and the
  doc-conventions check count corrected 3 → 9 (PR 1). Outside
  `close_check`'s scope; recorded for the manifest's completeness.
  <!-- doc-impact-waived: root-level file, invisible to COMMITTED_PATH — the segment's own carried open question -->
- `docs/status.md` — row at the close.

### Status

**2026-09-08 — all four corrected; the check caught a pointless marker.**

The three queued claims were each verified false against the code before
being touched, not taken from the queue on faith: the spec-coverage gate
exists with three assertions and an empty declared-debt baseline; the
Delete buttons are in a `.card.danger-zone` on Session Home and
`session_edit.html` is gone; `require_session_operator` answers 404 for
an ordinary non-owner and 403 only for a sys-admin.

**A fourth turned up in the same table as the first** — a check count of
3 where the file now has 9 — which is the pattern worth naming: patch
(a)'s row and this one sit four lines apart in a table titled "Evidence
(re-takeable)", and neither had been re-taken.

**The marker check earned its place again.** The `spec/ui_elements.md`
correction names `session_edit.html`, so I marked the line — and
`test_no_inline_path_marker_outlives_the_reference_it_covers` failed,
because a bare filename is not a prefixed path and the marker therefore
covered nothing. It was right: the marker was noise, and the check
declined to let me leave decoration behind. Removed.

**`spec-writer` adjudication — two flags, both dates I introduced while
correcting stale claims, and the second one propagated.**

- **"four days after the gate shipped" was three.** 2026-09-05 to
  2026-09-08. Arithmetic, inside the sentence explaining how long a
  claim had been wrong.
- **"18R Item 4 retired that page on 2026-08-19" was 2026-08-18** —
  every 18R Item 4 commit is 08-18, and `session_edit.html` was deleted
  at 10:36 UTC that day. The reader called it a fresh error. It is
  worse: **the date originated in the 2026-09-08 assessment itself**
  (`8eb73359`, §3), and from there it went into `spec/operator_button_audit.md`
  §4's heading at 19G.2, into `spec/ui_elements.md` and `docs/status.md`
  at 19G.3, and into this file's own roster row. **Five instances of one
  wrong date, spread by the two items whose subject was stale claims.**
  All five corrected, and the assessment's §3 with them.

**This is the finding, and it is not a flattering one.** Item 1 conceded
class D — prose about behaviour with no source to check against — as
unmechanizable, and argued the separate reader carries it. Three
consecutive `spec-writer` passes have now returned findings that are
**entirely** of that class: a slice count, two dates, a section
reference, a justification, a heading. Not one was substance; every one
was connective tissue. The concession is holding, but the load it is
carrying is heavier than §1.4 makes it sound, and a date that
propagates five ways in one day is evidence that "a person will notice"
is doing real work rather than nominal work.

**Recorded for the carried `close_check` question.** C3 reported
`spec/ui_elements.md` and `docs/status.md` "not modified in window" when
both had been modified in the commit that introduced the `## Item 3`
heading — the window's own boundary commit. Third occurrence in this
segment; 19G.1 and 19G.2 cleared it only because a later commit happened
to touch the same paths, as this adjudication commit does. That makes it
a property of the tool, not of an item, and it belongs with the
`COMMITTED_PATH` question rather than being re-diagnosed each time.


---

## Item 4 — `close_check` sees root-level `.md`

### Opportunity

`COMMITTED_PATH` matched `spec/` and `docs/` only, so a Doc-impact
bullet naming a root-level document was silently dropped: not verified,
and a waiver on it not counted either. 19G.1 committed to a
`constitution.md` edit and the tool reported **four committed paths
against a five-bullet manifest**. The check that asks whether promised
doc edits happened had a scope narrower than the manifests it validates,
and the files it dropped — `constitution.md`, `CLAUDE.md`,
`rrw_sdd_in_practice.md` — are the repository's most load-bearing.

### Decision

**Widen, but asymmetrically.** A path under `spec/` or `docs/` keeps
today's behaviour and counts anywhere in the bullet. A **bare filename**
counts **only in the leading position**, before the em-dash. Bare names
resolve root → `spec/` → `docs/`, read from the filesystem, so there is
no list to maintain.

*Rejected: match bare names anywhere.* Measured over the 99 plans, that
counts **five passing mentions as commitments** and flips one archived
plan to FAIL — 19E's `docs/README.md` bullet *describes* `quickstart.md`
retiring, and the tool would then have demanded the retired file still
exist. The false positive is not hypothetical; it is what the first
implementation did.

*Rejected: count only the bullet head, for every path.* That loses
**seven real commitments** across the archived plans, because bullets
here legitimately commit to several specs in their description
("Per-Part spec docs as the scope settles — A, B, C"). The asymmetry is
the price of keeping both halves right.

### Semantics

- **A bare name that resolves nowhere** is reported unchanged, so C2
  names the string the author wrote rather than a guess at what they
  meant.
- **`guide/` stays out of scope**, as the skill has always defined the
  manifest. `guide/README.md` bullets remain uncounted; 19G.1's waiver
  on one is therefore still decorative, which is now a stated fact
  rather than a silent one.
- **Duplicate paths across bullets** still count once per bullet — a
  pre-existing behaviour this item neither introduces nor fixes.

### Judgment calls — decided

- **The first implementation was wrong and the measurement caught it**
  (2026-09-08). Matching bare names anywhere looked obviously right and
  was checked against the 99 plans only afterwards; the check is what
  turned up the 19E flip. Recorded because the plan's own rule — measure
  the blast radius before cutting the first slice — is what saved it.
- **The skill and the template were updated with the tool** (2026-09-08).
  Both said "under `spec/` or `docs/`"; leaving them would have made the
  guidance disagree with the gate on the day the gate changed.

### Blast radius (measured)

Over all 99 plans (live + archived), Doc-impact bullets only, with
continuation lines accumulated as `parse_bullets` does:

| What | Count |
|---|---|
| Newly-counted paths, bare-anywhere rule | 13 — of which 5 passing mentions |
| Newly-counted paths, **head-only bare rule (shipped)** | 6 — of which 5 real commitments |
| Real commitments a head-only-for-everything rule would lose | 7 |
| Plans whose PASS/FAIL outcome changes | **0** |

### PR ladder

1. **PR 1 — the widening, its tests, and the guidance.** Must not touch:
   any plan's manifest, or `close_check`'s window logic.

### Definition of done

- `close_check 19G.1` counts the `constitution.md` bullet.
- No plan's outcome changes — verified by running the before/after set.
- Five tests cover the four new behaviours and the no-regression half,
  each mutation-checked.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.4` exits 0; any warning adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None of this item's own. The **C3 window-boundary** behaviour recorded
  at 19G.3 is untouched here and stays with the segment.

### Out of scope

- **The C3 window boundary.** Same tool, different defect: a path whose
  only edit lands in the commit that introduces the item heading reads
  as unmodified. **Four occurrences this segment** — it fired on this
  item too, on `docs/status.md`, while the item was fixing the *other*
  `close_check` defect. Not folded in, because the fix is to the window
  logic rather than the path pattern and it deserves its own
  measurement; but four for four is no longer a coincidence, and any
  item that adds a heading and edits its manifest paths in one commit
  will hit it.

### Doc impact

- `guide/segment_plan_template.md` — the Doc-impact prompt states the
  new rule (PR 1). <!-- doc-impact-waived: guide/ is outside the manifest scope this item just defined; named for completeness -->
- `docs/status.md` — row at the close.

### Status

**2026-09-08 — shipped, and the first implementation was wrong.**

Widening the pattern to match bare names anywhere is the obvious change
and it is what I wrote first. Running it over the 99 plans showed it
counting five passing mentions as commitments and flipping **19E** from
PASS to FAIL on a `quickstart.md` that its bullet merely described
retiring. The asymmetric rule — prefixed paths anywhere, bare names in
the leading position only — keeps every real commitment, drops every
false positive measured, and changes **no plan's outcome**.

The order matters and is the transferable part: the blast radius was
measured *before* the change was believed, and the first measurement was
itself wrong — it read only bullet first lines, while the tool
accumulates continuations, so it reported 5 newly-matched paths where
there were 13. The second measurement is the one that found the 19E
flip. **A measurement that does not model the thing it measures is worse
than none, because it is believed.**

`.claude/skills/segment-plan/SKILL.md` and
`guide/segment_plan_template.md` both said "under `spec/` or `docs/`"
and were updated in the same change — the gate and its guidance
disagreeing on the day the gate moves is how the next reader learns the
wrong rule.

**One advisory note, adjudicated.** C3 reports `_session_home` touched
with `spec/session_home.md` and `spec/permissions.md` absent from the
manifest. That touch is 19G.3's correction to the `/edit` redirect's
**comment** — no route, no gate, no behaviour — so neither spec has
anything to say about it. The note firing on a comment-only edit is the
check working as designed and owing nothing, the same adjudication 19C's
close made on a docstring.


---

## Item 5 — The six broken `§N` references

### Opportunity

The measurement this segment carried as an open question was run on
2026-09-08. **130 `§N` references in live prose, 26 target files, no
missing files, and six that named a number the target does not carry as
a section.** One of the six was a wrong *file*, introduced by 19G.2
eleven hours earlier and missed by that item's own `spec-writer` pass.

The measurement's harder finding was that the repository numbers
sections **five different ways**, and a naive heading-only parser flags
twelve — twice as many false as true. So the six could not be read off a
grep; each needed its intended target established from the citing
sentence.

### Decision

**Fix all six by making the pointer unambiguous, not by inventing
section numbers in the targets.**

Five of the six were not dangling so much as *unresolvable without
guessing a convention*: `§0` meant item 0 of a numbered list inside a
named section, and `§3` meant the third `##` by ordinal position.
Neither convention is stated anywhere. Rewriting them as
`§"Shared body shape" item 0` and `§"Coverage matrix — configuration"`
uses the idiom the repo already has for named sections
(`spec/session_home.md` §"Lifecycle state vocabulary") and needs no
convention to decode.

*Rejected: number the targets' sections instead.* That is a change to
four specs to satisfy six citations, and it would make the numbering a
contract those files never agreed to.

### Semantics

- **Archived documents keep their references.** `guide/archive/` copies
  of the same `§0` pointer stay as written; a closed plan is a record.
- **The current assessment was included** even though its filename marks
  it dated. It carried the same wrong pointer twice, it is the live
  snapshot, and it had already been amended earlier the same day —
  leaving two known-wrong pointers in it while fixing three identical
  ones elsewhere would have been arbitrary.

### Judgment calls — decided

- **Each intended target was read from the citing sentence** (2026-09-08),
  not inferred from the number. `spec/roundtrip_coverage.md` §3 resolves
  to "Coverage matrix — configuration" because both citations are about a
  coverage row and the Settings-CSV carrier, which is what that section
  holds — the ordinal arithmetic only confirmed it.
- **The 19G.2 error is named as mine in the record** (2026-09-08). It is
  the only one of the six that was flatly wrong rather than ambiguous,
  and the item that produced it ran a `spec-writer` pass that verified
  the button role mapping and did not check the cross-file citation.

### Blast radius (measured)

| What | Count |
|---|---|
| `§N` references in live prose, before | 130 |
| Unresolved under the three heading conventions | 6 |
| References edited | 8 (the six, plus the same pointer twice in the current assessment) |
| Files changed | 5 |
| `§N` references after (five became `§"name"`) | 125, **0 unresolved** |

### PR ladder

1. **PR 1 — the eight corrections.** Must not touch: the targets'
   headings, or any archived document.

### Definition of done

- Every corrected pointer names something that exists — verified by
  grepping each new target.
- Re-running the measurement returns **0 unresolved**, and the
  measurement still catches an injected bad reference (checked, so the
  zero is not vacuous).
- `### Doc impact` section present and current
- ~~`python3 tools/close_check.py 19G.5` exits 0~~ — **not met, and
  deliberately not forced.** See Status: C3 reports the known
  window-boundary artifact, fifth occurrence.
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Build the check now?** The corpus is clean, so it would be green
  from its first commit — the rung-2 shape. Against: it must encode
  three numbering conventions to avoid the 2:1 noise the measurement
  found, and a check carrying three conventions is closer to VI's
  "mechanise it badly" line than the path check was. **Decides:** the
  author. Recorded on the segment's carried question rather than here.

### Out of scope

- **Numbering the four unnumbered specs.** See Decision.
- **The C3 window boundary.** Still open, five occurrences now.

### Doc impact

- `spec/operator_button_audit.md` — row #155's citation repointed to the
  file that actually carries §5a (PR 1). *Named without backticked paths
  deliberately: the first draft of this bullet cited both the wrong and
  the right file as paths, and `close_check` counted all three as
  commitments — the prefixed-path false-positive 19G.4 measured and left
  open, biting the manifest that documents it.*
- `spec/email_template_editor.md` — two `roundtrip_coverage` pointers
  named rather than numbered (PR 1).
- `docs/status.md` — two `setup_pages` pointers named; row at the close.

### Status

**2026-09-08 — six fixed, eight edited, and the corpus is now clean.**

The measurement reported 130 references and 6 unresolved. After the
corrections it reports **125 and 0** — 125 rather than 130 because five
citations became named-section references, which the `§N` form no longer
counts.

**The zero was checked for vacuity.** Injecting `spec/lifecycle.md §99`
into a live document brings the count back to 1, so the parser is still
reading what it claims to read. A measurement that returns zero because
it stopped looking is the failure this segment has spent all day on.

**One of the six was mine, from eleven hours earlier.** 19G.2 cited
`spec/visual_style_rrw.md` §5a for the inline-banner convention; the
section is `spec/ui_elements.md` §5a. That item's `spec-writer` pass
checked the button role mapping — the substance — and did not check the
cross-file citation, which is the fourth consecutive pass whose findings
were entirely connective tissue and the first where the tissue was a
pointer rather than a number or a date.

**C3 fails, and this time I did not work around it.**
`spec/operator_button_audit.md` and `spec/email_template_editor.md` are
reported "not modified in window" when both were modified in the commit
that introduced the `## Item 5` heading — the window's own boundary,
**fifth occurrence in this segment**.

Three times before this I cleared it by finding another reason to touch
the same file in a later commit. Each of those edits was real, but the
pattern is not: *a check satisfied by finding an excuse to write to a
file again is a check being worked around, not passed*, and it is the
same shape as the empty commit that the PR rules forbid for kicking CI.
There is no further honest edit to make to those two specs here, so the
Definition of done's `exits 0` line is **struck rather than met**, with
the reason recorded.

**One more thing this item exposed, before the boundary.** The first
draft of the Doc-impact bullet above backticked both the wrong file and
the right one, and `close_check` counted three commitments where there
is one change — the *prefixed-path* false positive 19G.4 measured and
deliberately left open, biting the manifest of the item that documents
it, two items later. Reworded to name one path. The tool's rule is still
the one the repo wants; the manifest adapted, which is the right
direction.

**2026-09-08, later — the struck line is now met, by the check changing.**
19G.6 makes the window `[start, end]`, and `close_check 19G.5` exits 0
with no file edited to make it do so. The Definition of done above keeps
its strike: it records what was true at the close, and the reason it was
struck is what produced Item 6.
---

## Item 6 — The C3 window boundary

### Opportunity

`close_check`'s C3 asks whether every path a manifest committed to was
edited inside the plan's window. The window ran `git log start..end`,
which **excludes `start` itself** — so a plan that landed its `Doc
impact` manifest and the doc edit it commits to in one commit read as
having dropped the commitment.

That is not a rule anyone chose. It is the arithmetic of `A..B`, and the
module's docstring recorded it as a consequence ("a plan that lands its
manifest and its spec edit in one commit reads as unhonoured") rather
than as a reason. Nowhere else does C3 ask *when* in the window an edit
fell; its evidence standard is "a non-merge commit touched this path",
and the docstring is explicit that it does not judge whether the edit
was *correct* — "a one-character change to a committed path passes C3".
By that standard an edit in the boundary commit is the same evidence as
an edit the day after.

It bit this segment four times, and 19G.5 stopped clearing it: three
times before, C3 was made to pass by finding another reason to touch the
same file in a later commit, and Item 5 recorded why that is not a pass —
*a check satisfied by finding an excuse to write to a file again is a
check being worked around*. Item 5 therefore closed with its
`exits 0` line struck. A check whose standard close move is a manufactured
edit is on `constitution.md` Article VI's road: retired by attrition,
one waiver at a time.

### Decision

**The window becomes `[start, end]`** — the commit that records the
commitment can also honour it.

Rejected: **downgrade the boundary case to a WARN**, as the item-anchor
ambiguity already is. That warn exists because two readings of the
timestamps are equally consistent — the item was logged after its work
landed, *or* this is another item's edit — and a person resolves it in
one `git log`. Here there is nothing to resolve: the file was edited, in
this plan's own commit, at the moment the commitment was written. A warn
would ask a reader to adjudicate a fact, and would still leave the
`exits 0` line unmeetable.

Rejected: **leave it and waive each occurrence.** Five occurrences in
three plans across four months is a recurring shape, not an accident,
and Article VI is explicit that a check routinely waived is worse than
no check.

### Semantics

- **Root commit.** `start^!` is the commit with its parents excluded, so
  it resolves to the one commit whether or not it has a parent. Verified
  against this repo's root commit.
- **Merge start.** `-G` cannot return a merge (default `git log` shows no
  diff for merges), and `--no-merges` is kept on the fallback, so a merge
  start reads exactly as it did before.
- **Backwards.** The window widens at its start by one commit and no
  further; an edit before the window opens — including one before a
  tagged bullet's `## Item n` heading — is still outside it. The
  item-anchor logic and its warn are untouched.
- **Cost.** One extra `git log` per path, and only when the ordinary
  range came back empty.

### Judgment calls — decided

- **Two `git log` calls, not one clever range** (2026-09-08). `git log
  A^! A..B -- path` expresses the same set in one call. Two calls put
  the boundary case in the code where a reader meets it, and this is a
  check whose semantics are the entire point.
- **The count of prior occurrences stays at five in the prose, six in
  the measurement** (2026-09-08). Five is the number of *situations* the
  segment recorded; six is path-instances, because 14B commits to
  `spec/email_infra_options.md` in two separate bullets. Both are stated
  rather than reconciled into one number that means neither.

### Blast radius (measured)

Across all 99 plans (live + archived), at `bf611798`. The archived half
is reproducible with `python3 tools/close_check.py --archived` on either
side of this commit; the live half needed a throwaway walker over
`close_check`'s own `parse_bullets` / `window` / `honoured`, because
nothing in the tool reports across *live* plans. Per-plan figures are
reproducible one at a time with `python3 tools/close_check.py <id>`.

- **22** committed paths currently fail C3; **6** of them are honoured
  by the window's own start commit and nothing else. After the change,
  **16** fail and **0** are boundary cases.
- Every one of the six was read: `19B` `docs/status.md` (`53d867dc`),
  `14B` `spec/email_infra_options.md` twice (`27d7081e`), and Item 5's
  three paths (`87ae5a05`). In each, the commit that added the manifest
  or the item heading also carried the doc edit. **No false pass is
  introduced in the corpus** — the change turns exactly these six.
- Verdicts that flip **FAIL → PASS**: three. `14B` (live), `19B`
  (archived), `19G.5`. `python3 tools/close_check.py --archived` moves
  from 132/148 (89%) to 133/148 (90%), and 25 → 26 plans fully honoured.
- Callers: `honoured()` has two, both inside `check_manifest`
  (`grep -n "honoured(" tools/close_check.py`).

### PR ladder

1. **PR 1 — the boundary, its tests, and the two prose homes.** One PR:
   the code change is four lines and the docstring that mis-states the
   rule sits in the same file. Must not touch the item-anchor logic, the
   heading regexes, or any archived plan.

### Definition of done

- `honoured()` counts the start commit; `tools/close_check.py 19G.5`
  exits 0 **without any file being edited to make it do so** — the
  struck line in Item 5's Definition of done is now met by the check
  changing, not by the corpus being made to fit it.
- Three new tests in `tests/unit/test_close_check.py`, each shown to
  fail against a mutant: the boundary case fails on the pre-change
  `honoured`; the never-touched guard fails when the fallback always
  returns a date; the before-the-window guard fails when the fallback
  drops its anchor.
- The archived-corpus numbers above are reproducible with
  `python3 tools/close_check.py --archived`, and each named plan's
  verdict with `python3 tools/close_check.py <id>`.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.6` exits 0
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. The remaining 16 C3 failures are the check working: archived
  plans that dropped a commitment. They are a reading task for whoever
  wants it, not a defect in the tool.

### Out of scope

- **The other 16 failures.** Each is a real unhonoured commitment on a
  plan that has already closed. Recorded here so the number is not read
  as a regression.
- **Widening `COMMITTED_PATH` to `tools/` and `guide/`.** The manifests
  that name `tools/README.md` already mark themselves *"for the human —
  outside the script's regex"*, so the convention holds; changing the
  regex is 19G.4's class, not this one, and bundling it here would put
  two independent changes in one PR.

### Doc impact

- `docs/status.md` — row at the close.
- *(for the human — outside the script's regex)* `tools/README.md`'s
  `close_check.py` row and `.claude/skills/segment-plan/SKILL.md` step 2,
  both of which state the window rule; the check and its guidance move
  together, which is 19G.1 rung 2's lesson.

### Status

**2026-09-08 — landed as planned: one PR, four lines of behaviour, three
tests.**

Intended one PR; shipped one PR. The ladder's "must not touch" held —
the item-anchor logic, the heading regexes and the archived plans are
untouched, and the diff outside the boundary is docstring, README, skill
and this plan.

**Decisions confirmed at build:**

- **`start^!` rather than `start^..end`** (2026-09-08). `start^` breaks
  on a root commit; `^!` resolves to the one commit whether or not it has
  a parent, verified against this repo's root commit `2420f8e6`.
- **The fallback runs only when the ordinary range came back empty**, so
  the common path costs nothing.

**Every one of the six boundary cases was read before the change, not
after.** That was the check on the decision: if any of the six had been
a mass restructure that merely happened to touch a committed path, the
change would have manufactured a false pass. All six are a manifest or
an item heading landing in the same commit as the doc edit it names —
`19B` `53d867dc` (a one-line `docs/status.md` row), `14B` `27d7081e`
(the Segment 14 → 14A/B/C split, renaming 34 lines of
`spec/email_infra_options.md`), and Item 5's `87ae5a05`.

**The three tests were each shown to fail against a mutant**, because a
guard that cannot fail is not a guard:

| Test | Mutant it fails against |
|---|---|
| the boundary case | the pre-change `honoured` |
| a path no commit touched | the fallback always returning a date |
| an edit before the window opens | the fallback dropping its `start` anchor |

The second and third exist because this change *widens* a check, and the
cheap way to make a boundary case pass is to stop checking. The
never-touched guard is the one that would catch that.

**This item's own close is the case it fixes.** Item 6's `docs/status.md`
row lands in the commit that introduces the `## Item 6` heading — so
under the old window `close_check 19G.6` would have failed C3 on its own
manifest, and under the new one it passes. That is not a coincidence to
smile at: it is why the boundary recurs. A one-item documentation change
has no second commit to spend, and the check was asking for one.

**What did not change.** The remaining 16 C3 failures across the archived
plans are real dropped commitments, and this change does not touch them.
The `--archived` figure moving 89% → 90% is one plan, not a trend.

## Item 7 — The `§N` heading-validity check

### Opportunity

19G.5 fixed six broken `§N` references and reported the corpus clean:
**125 references, 0 unresolved**, with the zero checked for vacuity by
injecting a bad reference and seeing it caught.

The zero was true of what the measurement could see. Re-measured
2026-09-08 at `61300c06` with a whole-text scan, live prose carries
**132** `§N` references, not 125: **7 wrap across a line break**, and the
19G.5 scan read line by line. It never saw them. Six of the seven
resolve. The seventh does not —

```
docs/unenforced_conventions.md §2.1  ->  `spec/architecture.md`
                                          §3
```

— and `spec/architecture.md` carries no numbered sections at all; every
`##` in it is a name. `§3` means **layer 3 of the numbered list inside
"Three-layer split"**, which is where the `sqlalchemy.dialects.postgresql`
rule actually sits (line 89). That is the same unresolvable-without-
guessing form 19G.5 rewrote elsewhere as `§"Shared body shape" item 0`,
and it is mine, from 19G.1, three items and eleven hours before the
measurement that was supposed to find it.

So the carried question — *does the `§N` form deserve a check?* — arrives
with its own answer attached. A hand measurement certified a corpus it
could not fully read, and a broken reference of the exact class survived
the item that existed to remove it. That is not an argument that the
class is cheap to check; it is an argument that a human pass over 132
references is not the instrument.

### Decision

**Build it**, in `tests/unit/test_doc_conventions.py`, alongside the path
check it is the sibling of. Scan the **whole text**, not line by line.

Rejected: **`docs/unenforced_conventions.md` §1**, the file the carried
question named as the other outcome. It was the right destination while
the cost was unmeasured — a check needing an unstated section-numbering
convention to hold repo-wide would have been Article VI's "mechanise it
badly". The measurement removed that: **46 of 50 (file, §N) pairs use one
form**, and the whole corpus needs four, each of which is load-bearing on
real references. Four fixed forms is not a convention the repo must first
adopt; it is a description of what it already does.

Rejected: **a section-scoped opt-out**, the shape the path check uses.
Measured, the section form would excuse **31 of 132 references** to cover
the **one** historical citation that needs excusing — 30 working pointers
going unchecked to save one marker. The path check earned its section
form at 36 references; this one has not. An escape hatch is sized to what
it must excuse.

### Semantics

- **Corpus.** `LIVE_PROSE`, the same as the path check: top-level `.md`
  in root, `spec/`, `docs/`, `guide/`, minus dated documents.
- **Multiline.** The whitespace between the backticked path and `§` may
  include a newline. The line reported is where the reference *starts*;
  the marker is honoured on any line the reference spans.
- **A target that does not exist** is the path check's finding, not this
  one — the reference is skipped here rather than reported twice.
- **Named-section references** (`§"Route conventions"`) are outside the
  pattern by construction: it requires digits. The repo's answer to an
  unnumberable pointer is to name the section, and naming it is how a
  reference leaves this check's scope.
- **`§N.M`** resolves against the exact number only. `§5.6` does not
  match a `## 5.` heading; the reference names a subsection or it does
  not.

### Judgment calls — decided

- **Period optional in the plain form** (2026-09-08). `### 1.1 X` numbers
  without one, and 198 headings across live prose take that shape.
  Requiring the period drops resolution from 130 to 100.
- **A distinct marker, `<!-- section-ref-ok -->`** (2026-09-08), rather
  than reusing `<!-- path-ref-ok -->`. The two checks honour scope
  differently — this one has no section form — and one marker name
  meaning two scopes is a trap for the next reader.
- **The four heading forms are exactly the four in use** (2026-09-08). A
  fifth would be dead code, and dead code in a check is where the next
  allowlist starts.

### Blast radius (measured)

At `61300c06`, whole-text scan over `LIVE_PROSE`:

| | count |
|---|---|
| `§N` references in live prose | **132** |
| of those, wrapped across a line break | **7** |
| seen by the 19G.5 line-local scan | 125 |
| distinct (file, §N) pairs | 50 across 26 target files |
| unresolved before this item | **1** |
| references the rejected section-marker form would have excused | 31 |

Heading forms carrying the 132: 123 plain (`## 3. X`, `### 1.1 X`), 3
bold-paragraph (`**8.2.7 X**`), 3 `## §5.6 X`, 1 `## Section 10 — X`.

### PR ladder

1. **PR 1 — the correction, then the check**, as two commits so the
   history shows the check added to a corpus already clean. Must not
   touch the path check, its markers, or any archived document.
   ~~Two commits~~ — **one**; see Status.

### Definition of done

- `docs/unenforced_conventions.md` §2.1 names the section instead of
  numbering it.
- The check is green, and green is not vacuous: reverting the correction
  makes it fail on that exact reference.
- Four mutants, each run: the reverted correction (the check catches it);
  a line-local scan (green with the defect present — the 19G.5 blind spot
  demonstrated rather than asserted); a resolving `§5a` (the stale-marker
  guard fires); numbers scraped from anywhere rather than headings (green
  with the defect present — anchoring is load-bearing).
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.7` exits 0
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. The carried question this item answers is struck below.

### Out of scope

- **A check for named-section references** (`§"Route conventions"`).
  Resolving one means matching heading text, which drifts on every
  rewording — the class the repo conceded as B, not a gap this item
  leaves.
- **Re-auditing the path check for the same multiline blind spot.** It
  scans line by line too, but a path reference is a single backticked
  token with no separator inviting a break. **Measured rather than
  assumed:** a scan for a backticked span made of path characters and a
  line break returns 29 hits across live prose, every one a
  backtick-pairing artefact across unrelated inline-code spans or a
  wrapped UI label (`` `Reviewer\n  Email` ``, `` `Data\nshaper` ``), and
  **zero** wrapped paths. The failure mode does not exist there.

### Doc impact

- `docs/unenforced_conventions.md` — §2.1's architecture pointer names
  the section rather than numbering it (PR 1). *The target is named
  without backticks deliberately: `close_check` counts a prefixed path
  anywhere in a bullet as a commitment, so backticking it would commit
  this item to editing a file it only cites — the false positive 19G.4
  measured and 19G.5 hit.* ~~biting a third manifest in three items~~ —
  **wrong, corrected at 19G.8**: it bit **two** manifests, this one and
  19G.5. Item 6's bullets name `tools/` and `.claude/` paths under the
  "for the human" convention, which is a different mechanism — those
  paths are outside the regex entirely and were never counted. The
  miscount then propagated to the 08sep assessment §8, which is the
  class this segment has spent two days on, committed by the item that
  was documenting it.
- `docs/status.md` — the 19G.5 row gains `<!-- section-ref-ok -->`, the
  corpus's only marker; row at the close (PR 1).

### Status

**2026-09-08 — landed as one PR and, after a false start, one commit.**

Intended one PR; shipped one PR. The ladder said two commits — the
correction, then the check — so the history would show the check added to
a corpus already clean. **It was built that way and collapsed**, because
the ordering put the correction one commit *before* the window its own
item opens: `close_check 19G.7` failed C3 on
`docs/unenforced_conventions.md`, edited in commit 1, with the window
opening at commit 2 where the `## Item 7` heading landed.

**That is 19G.6 working, not 19G.6 falling short.** The boundary fix
widened the window by exactly one commit — the one that records the
commitment — and deliberately not backwards. An edit made *before* the
item existed is outside the window by design; that property has its own
guard test, added the same day. The honest orders are the plan heading
first, or everything together. Squashed to one commit rather than
reshuffling the plan file across two, and the ladder rung is struck with
this reason instead of quietly rewritten.

**Decisions confirmed at build:**

- **Period optional** in the plain heading form. Confirmed by
  measurement: requiring it drops resolution from 130 of 132 to 100.
- **No section-scoped marker.** Confirmed by measurement: the section
  form would have excused 31 references to cover 1.
- **Four heading forms, all load-bearing.** A fifth was drafted (a bare
  `### 4 X` with no period and no dot) and dropped when it matched
  nothing the other four had not already matched.

**Four mutants, each run, and one of them changed what this item claims.**

| Mutant | Result |
|---|---|
| the correction reverted | check **fails** on `docs/unenforced_conventions.md:117` — it catches the real one |
| the scan made line-local | **green with the defect present** — the 19G.5 blind spot, demonstrated |
| `§5a` made to resolve | stale-marker guard **fires** |
| numbers scraped from anywhere, not headings | **green with the defect present** — anchoring is load-bearing |

The fourth was wrong on its first run and said so: the mutant scraped
bare integers, which broke `§5.6` and `§8.2.7` elsewhere and failed for a
reason that had nothing to do with anchoring. Re-run with dotted numbers
preserved, it passes green with the defect standing, which is the claim.
A mutant that fails for the wrong reason is a mutant that proved nothing.

**What this item does not claim.** The check reads numbers, not meaning:
`§4` pointing at a section that exists but says something else still
passes. That is class B, conceded at 19G.1, and no heading check reaches
it.

## Item 8 — A cited path is not a commitment

### Opportunity

`close_check`'s `COMMITTED_PATH` matches a backticked `spec/` or `docs/`
path **anywhere** in a Doc-impact bullet. That is deliberate and
measured: bullets legitimately commit to several specs after the dash
("Per-Part spec docs as the scope settles — `spec/assignments.md` (Part
1), `spec/csv_contracts.md` (Part 2)"), and 19G.4 found a head-only rule
would lose seven such commitments across the archived plans.

The cost is a bullet that *cites* a path — describing an edit to a
pointer, whose target it must name — and has the target read as a
commitment the item never made. It bit **two** manifests in this
segment:

| Item | Bullet | What it cited |
|---|---|---|
| 19G.5 | `spec/operator_button_audit.md` — row #155's citation repointed | the wrong file and the right one, counted as two more commitments |
| 19G.7 | `docs/unenforced_conventions.md` — §2.1's architecture pointer | `spec/architecture.md`, a file the item only reads |

Both escapes available were bad. **Waiving** is per-bullet, so it would
waive the bullet's real commitment too. **Dropping the backticks** —
what I did, twice — distorts the prose to satisfy the checker, against
`CLAUDE.md`'s and this skill's "backtick every path", and leaves a
document whose typography encodes a tool's parsing limits. That is the
same shape as the C3 workaround 19G.6 removed: *a check satisfied by
editing the prose to suit it is a check being worked around.*

**A correction, made before building on the claim.** The 08sep
assessment §8 and 19G.7's own bullet said this had bitten **three**
consecutive manifests, naming 19G.6 among them. It bit two. 19G.6's
bullets name `tools/README.md` and `.claude/skills/segment-plan/SKILL.md`
under the "for the human" convention — paths outside the regex entirely,
never counted, a different mechanism. The wrong count was written in
19G.7 and propagated to the assessment the same day: class B, in the
segment that conceded class B, committed by the item documenting it.
Both copies are corrected rather than quietly restated.

### Decision

**The author says which, once, in the bullet:**
`<!-- cites: spec/architecture.md -->`, comma-separated for several,
matched anywhere in the bullet, and the named paths drop out of that
bullet's committed set. **C7** fails a `cites:` naming a path the bullet
does not contain, so the escape cannot outlive its reason or quietly
become a blanket — the same both-directions rule as
`test_doc_conventions.py`'s two markers.

Rejected: **head-only for prefixed paths, as 19G.4 already does for bare
names.** Measured over all 99 plans, exactly **two** bullets name a path
in the head *and* more after the dash — and in both, the after-dash
paths are **real commitments**: `11J`'s bullet commits to a matching
edit in `spec/session_home.md` §"Quick Setup card", and `19C`'s is a
compound bullet committing to four specs separated by semicolons. The
rule would lose four commitments and gain nothing historically. The
grammar does not carry the distinction; only the author does.

Rejected: **inferring it from the sentence** — a path followed by "— what
changes" is a commitment, one inside a noun phrase is a citation. `11J`'s
genuine second commitment has no dash at all, so the heuristic misreads
the one case in the corpus that most needs reading right.

### Semantics

- **Opt-in.** No existing plan carries the marker, so no existing verdict
  moves; verified against the archived report and every live plan.
- **Scope.** The marker binds its own bullet only. Two bullets naming the
  same path need two markers, which is correct: one bullet may commit to
  a file another only cites.
- **A bullet whose every path is cited** commits to nothing and is legal
  — that is a prose bullet, the shape the "for the human" convention
  already uses.
- **C7 reads the bullet before the filter**, so a marker naming a path
  that *is* the bullet's only commitment still resolves rather than
  reading as absent.
- **Not retroactive.** 19G.5's and 19G.7's bullets keep their
  backtick-less prose and the notes explaining it. A closed item's
  manifest is a record of what it committed to; rewriting it to look
  tidy under the new rule would erase the only evidence the defect had a
  cost.

### Judgment calls — decided

- **`C7`, not `C5`** (2026-09-08). The C5 slot is free because 19A
  dropped a vocabulary-rename check, and reusing the number would make
  that record read as something it is not. The docstring now says so
  rather than leaving "there is no C5" as a bare fact.
- **A marker, not a config list** (2026-09-08). A repo-level list of
  "paths that are usually cited" is the growing allowlist Article VI
  names; the marker is local, self-documenting, and dies with its bullet.
- **Comma-separated in one marker** rather than one marker per path
  (2026-09-08). 19G.5's bullet cites two, and two comments on one bullet
  reads worse than one comment naming two.

### Blast radius (measured)

At `f506285f`, over all 99 plans (live + archived):

| | count |
|---|---|
| bullets carrying a `cites:` marker today | **0** — the feature is opt-in |
| plan verdicts that change | **0** (`--archived` report byte-identical; eight live plans re-run individually) |
| bullets with a head path *and* after-dash paths | **2**, both genuine multi-path commitments — the rejected rule's cost |
| manifests the defect has bitten | **2** (19G.5, 19G.7) |

### PR ladder

1. **PR 1 — the marker, C7, its tests, and the three prose homes.** Must
   not touch the window logic, the heading regexes, `COMMITTED_PATH`
   itself, or any archived plan's manifest.

### Definition of done

- A cited path named by `<!-- cites: … -->` is not counted; without the
  marker it still is.
- C7 fails a `cites:` naming a path its bullet does not contain.
- Four mutants, each run: the pre-change parser (three tests fail); a
  marker that drops every path in its bullet (three fail); `cited_absent`
  hard-wired empty (C7's test fails); head-only for prefixed paths (the
  rejected alternative — two fail, including 19G.4's own guard).
- No existing plan's verdict moves — archived report byte-identical.
- The three-manifest miscount corrected in both places it reached.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.8` exits 0
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None.

### Out of scope

- **Widening `COMMITTED_PATH` to `tools/` and `guide/`.** Still 19G.4's
  class, still handled by the "for the human" convention, still not
  bundled here.
- **Retrofitting the marker onto 19G.5 and 19G.7.** See Semantics — a
  closed manifest is a record.

### Doc impact

- `docs/status.md` — row at the close. The 19G.7 row does not carry the
  three-manifest claim (checked), so nothing there needs amending.
- *(for the human — outside the script's `spec/` + `docs/` regex)*
  `guide/codebase_assessment_08sep.md` §8's three-manifest claim
  corrected to two; `tools/README.md`'s `close_check.py` row;
  `.claude/skills/segment-plan/SKILL.md`'s Doc-impact contract; and
  `guide/segment_plan_template.md`'s Doc-impact comment — the last three
  all state what counts as a commitment, and the rule and its guidance
  move together. *Four real commitments the tool cannot verify, because
  `guide/`, `tools/` and `.claude/` are outside the regex: the item
  fixing one blind spot in the manifest pattern writes its own manifest
  around another, which is 19G.4's class and stays out of scope.*

### Status

**2026-09-08 — landed as planned: one PR, one commit, five tests.**

Intended one PR; shipped one PR. The ladder's "must not touch" held:
`COMMITTED_PATH` itself, the window logic and the heading regexes are
unchanged, and no archived manifest was edited.

**The correction came before the build, and changed the item.** The
Opportunity was drafted from the claim already in the assessment — that
the defect had bitten three consecutive manifests. Checking it against
the plan file showed it bit two: 19G.6's bullets name `tools/` and
`.claude/` paths, which the regex never matched. Had the claim gone
unchecked, this item would have opened with a false measurement in
service of a real defect, which is the cheapest way to make a good fix
untrustworthy. Both copies are corrected and neither is deleted.

**Decisions confirmed at build:**

- **The rejected head-only rule was measured, not assumed.** Exactly two
  bullets in the 99 plans have a head path plus after-dash paths, and
  reading both showed the after-dash paths are real commitments in each
  — `11J` commits to a matching `spec/session_home.md` edit expressed
  without a dash at all, and `19C` is a compound four-spec bullet. The
  rule would have cost four commitments. **The one case that most needs
  reading right is the one a grammar heuristic gets wrong**, which is
  why the marker is authored rather than inferred.
- **Opt-in means no verdict moves.** The `--archived` report is
  byte-identical across the change and eight live plans were re-run
  individually.

**Four mutants, each run:**

| Mutant | Result |
|---|---|
| the pre-change parser | 3 tests **fail** — the marker is doing the work |
| a marker that empties its whole bullet | 3 **fail** — it removes only what it names |
| `cited_absent` hard-wired empty | C7's test **fails** — the staleness guard is real |
| head-only for prefixed paths (the rejected rule) | 2 **fail**, including 19G.4's own guard against exactly this |

**The marker ships with no use in a live manifest, deliberately.** This
item's own bullets cite nothing — the four paths they name are outside
the regex, not cited within it — and inventing a use to demonstrate the
feature would be the vice the item exists to remove. Its end-to-end path
is the same `parse_bullets` every manifest goes through, exercised by
five tests; 19G.5's and 19G.7's bullets stay as written, because a closed
manifest is a record of what it committed to and of what the defect cost.

**What this does not fix.** `guide/`, `tools/` and `.claude/` are still
outside `COMMITTED_PATH`, so four of this item's five real doc
commitments are unverifiable — recorded in the Doc impact rather than
smoothed over. That is 19G.4's class and it stays open.

## Item 9 — Archived sessions read "not opened" on `/me`

### Opportunity

An archived session still lists a row on `/me` for reviewer and observer
participants, and its Session-status pill reads **`not opened`**.

`can_archive` (`app/services/session_lifecycle.py:80`) admits **draft,
validated and expired** — a `ready` session must be paused first. So an
archived session was one of three things, and the label is only true for
two of them. A session archived from `expired` **ran**: reviewers opened
it, worked in it and submitted. Telling them it was never opened is
false, and it is false precisely for the participants who did the work.

The current behaviour is deliberate and documented — but the recorded
reason covers the *link*, not the *label*.
`session_status_for_reviewer`'s docstring says `archived → "not opened"
(by design — archive retires a session out of reviewer reach; the
dashboard hides its link)`. Hiding the link is right and is not in
question here. Nothing in the record defends the word.

Two paths reach it, and both fall through the same `else`:
`session_status_for_reviewer` (`session_lifecycle.py:924`) for reviewer
rows, and `_non_reviewer_session_status`
(`app/web/routes_reviewer/_dashboard.py:60`) for observer rows.

### Decision

**Keep the `session_status` string exactly as it is, and render a second
grey `archived` pill beside it** in the Session-status cell of
`/me`, on reviewer and observer rows.

The pill is `pill-lifecycle-archived` — already defined at
`app/web/templates/base.html:3057` and already the operator lobby's
vocabulary for archived sessions (`operator/sessions_list.html:40`,
`operator/sessions_archived.html:15`). A participant meeting it is
meeting a word the product already uses, not a new one.

**Rejected: relabelling the status to `archived`.** Reachability is
derived from the label string in two places —
`"enabled": session_status != "not opened"` at `_dashboard.py:196` and
`_shared.py:227`. Renaming the archived status flips both to `True` and
re-links the reviewer surface on an archived session. Not a disclosure
(the route still renders the not-open page) but a live link to a dead
end, which is the thing the current design avoids. Relabelling therefore
means decoupling `enabled` from the label *first* — a behaviour change,
in service of a copy change. Keeping the string makes the link
behaviour unchanged **by construction** rather than by careful editing.

**Rejected: an `(a)` marker appended to `not opened`.** Same blast
radius as the second pill, but it is a private code: nothing on the page
expands it, so it needs a `title` or a legend, and `title` alone is
invisible on touch. At equal cost the pill is legible without
decoding. (Author, 2026-09-08.)

**Rejected: applying the same treatment to reviewee rows.** Not needed
and not possible: `reviewee_has_current_grant` returns `False` on an
archived session (`app/services/visibility_policies.py:280`), and
`_dashboard.py:144` filters the reviewee role on that predicate, so a
reviewee-only row cannot exist on an archived session. 19F's disclosure
rule stands untouched, and the scoping to reviewer/observer is enforced
upstream rather than by a new condition here.

### Semantics

- **Which rows.** Only rows where `session.status == "archived"`. Every
  other state renders exactly as today.
- **Which participants.** Reviewer and observer. The reviewee case is
  structurally unreachable (see Decision), so no role test is written
  into the template — the row's existence already implies the role.
- **Layout.** Side by side with the status pill if the column takes it;
  wrapping to a line below it if not. **The fallback is pre-authorized**
  (author, 2026-09-08) — it does not need a second decision at build.
- **No new route field.** The item dict already carries
  `"session": review_session` (`_dashboard.py:246`), used for
  `item.session.name` at `dashboard.html:29`, so the template branches on
  `item.session.status` directly. A raw enum comparison, not user-visible
  copy, which is what `lifecycle_display.py`'s docstring reserves the
  filter for.
- **Not the role chips.** `_shared.py`'s chips grey out on an archived
  session and carry no status word at all, so there is nothing there for
  a second pill to sit beside. Unchanged.
- **Not `review_surface.html`.** That template's `session_status`
  variable is the per-reviewer response state (`submitted` / `saved` /
  `Draft`), a name collision with the lifecycle-derived one. It must not
  be touched.

### Judgment calls — decided

- **Pill, not a suffix or a tooltip** (2026-09-08). See Decision — same
  cost, nothing to decode.
- **Grey, not amber or red** (2026-09-08). `pill-lifecycle-archived` is
  the muted token the operator lobby uses for archived. Archive is not
  an alarm; it is a retirement.
- **Lowercase `archived`** (2026-09-08). The pill vocabulary on this page
  is lowercase — `open`, `closed`, `not opened` — and mixing cases in one
  cell would read as two different kinds of thing.
- **The status string stays wrong, and that is the trade** (2026-09-08).
  This annotates the falsehood rather than removing it: a reader who
  ignores the second pill still reads `not opened`. Accepted because the
  alternative costs a behaviour change; recorded here so the residue is
  not mistaken for a complete fix.

### Blast radius (measured)

At `4affd7d4`:

| What | Count | Command |
|---|---|---|
| templates rendering the lifecycle `session_status` | **1** of 4 hits — `reviewer/dashboard.html`; the other three are the operator setup row, sys-admin sessions, and the response-state collision above | `grep -rln "session_status" app/web/templates` |
| callers of the two status functions | **3** — `_dashboard.py:166`, `_dashboard.py:175`, `_shared.py:218` | `grep -rn "session_status_for_reviewer(\|_non_reviewer_session_status(" app/` |
| status functions edited | **0** — the string is unchanged | — |
| `enabled` couplings edited | **0** — `_dashboard.py:196`, `_shared.py:227` untouched | — |
| specs naming the archived row's label | **3** — `role_landing_and_visibility.md` (lines 121, 183), `participant_model.md` (lines 118, 130), `reviewer-surface.md` (line 868) | `grep -rln "not opened" spec/` |
| specs naming the *rule* and needing no edit | **1** — `role_navigator.md:64` quotes `!= "not opened"`, which does not move | same |
| tests asserting `not opened` on `/me` | **10** across 2 files, all expected to keep passing | `grep -c "not opened" tests/integration/test_me_dashboard_*.py` |

### PR ladder

1. **PR 1 — the pill, its test, and the three specs.** One rung: this is
   a pill inside an existing cell, not a new page, card or navigation
   affordance, so `CLAUDE.md`'s scaffold-first rule does not apply and a
   placeholder slice would land nothing a reviewer could react to. Must
   not touch: `session_status_for_reviewer`,
   `_non_reviewer_session_status`, either `enabled` condition, the
   `_shared.py` chips, or `review_surface.html`.

### Definition of done

- An archived session's `/me` row renders both pills for a reviewer and
  for an observer; every other lifecycle state renders one, unchanged.
- The reviewer and observer links on an archived row stay **disabled** —
  asserted directly, not inferred from the string being unchanged.
- The ten existing `not opened` assertions still pass untouched. If any
  needs editing, the string moved and the Decision was violated.
- **The squeeze question is answered by observation, not guess**: `/me`
  rendered with a seeded archived row and captured with the
  pre-installed Chromium at a stated viewport width, with the screenshot
  and the width in the PR body. If it is crowded, the pill wraps below —
  pre-authorized above.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19G.9` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. The one variable — side by side or stacked — has its decision
  rule and its fallback recorded above, and the observation that settles
  it is a Definition-of-done line.

### Out of scope

- **Fixing the `enabled`-couples-to-the-label design.** Two call sites
  derive reachability from a display string, which is fragile
  independently of this item. Naming it here so the next reader knows it
  was seen and left; it belongs with a relabelling, if one ever happens.
- **Reviewee rows.** See Decision — structurally unreachable, and 19F's
  rule is deliberate.
- **The archived state on any other participant surface.** `/results`,
  `/collation` and the not-open page each handle archive already; this
  item is the `/me` row only.

### Doc impact

- `spec/role_landing_and_visibility.md` — §4's Reviewer and Observer
  tables: the `archived` row's `/me` cell gains the companion pill
  (PR 1).
- `spec/participant_model.md` — the reviewer/observer asymmetry paragraph
  and the observer row of the audience table both say the row "reads
  'not opened'"; both gain the second pill (PR 1).
- `spec/reviewer-surface.md` — the Session-status pill vocabulary gains
  the archived companion, stated as a companion rather than a fourth
  value (PR 1).
- `spec/role_navigator.md` — **deliberately unchanged**: its reachability
  rule quotes `!= "not opened"`, and this item leaves that string alone.
  Named so a reader auditing the change knows it was checked, not missed.
  <!-- cites: spec/role_navigator.md -->
- `docs/status.md` — row at the close (PR 1).

## Carried open questions

Promoted from Item 1 at its close (2026-09-08) because neither is
Item-1-shaped and both would otherwise be buried in a closed item.

- ~~**Does the `§N` reference form deserve a heading-validity check?**~~
  **Answered 2026-09-08 as 19G.7: yes, built.** See Item 7 — and note
  that the corpus was *not* clean when this line said it was: the 19G.5
  measurement read line by line and never saw the 7 references that wrap,
  one of which was broken. The intermediate note follows, then the
  original text.

- ~~**Does the `§N` reference form deserve a heading-validity check?**~~
  **Measured 2026-09-08 (see Item 5), and the corpus is now clean** — a
  check built today would be green from its first commit. Whether to
  build it is still open; the measurement changed its cost, not the
  decision. The original text follows.

- **Does the `§N` reference form deserve a heading-validity check?**
  139 live references name a numbered section of another file
  (`` `spec/permissions.md` §4 ``). That is class C's surface — the class
  neither rung 2's path check nor anything else reaches, and the class
  `"Segment 19C Item 8"` belonged to. Whether a check is cheap depends on
  how consistently the *targets* number their sections, which is still
  unmeasured. **Decides:** a measurement first. If it turns out cheap,
  this becomes **19G.3**; if it needs a section-numbering convention to
  hold repo-wide first, it goes to `docs/unenforced_conventions.md` §1
  with that as its reason.

- ~~**Should `close_check`'s `COMMITTED_PATH` widen to root-level `.md`?**~~
  **Answered 2026-09-08 as 19G.4: yes, asymmetrically.** See Item 4.
  The original text follows.

- **Should `close_check`'s `COMMITTED_PATH` widen to root-level `.md`?**
  It matches backticked `.md` paths under `spec/` or `docs/` only, so
  Item 1's `constitution.md` and `rrw_sdd_in_practice.md` bullets were
  never counted — the tool that checks whether committed doc edits
  happened has a scope narrower than the manifests it validates, which is
  this segment's own subject one level up. **Decides:** the author. A
  one-line pattern change with an unmeasured blast radius across every
  existing plan's manifest, so it is a slice of its own, not a rung.

