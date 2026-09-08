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
opened. It closes when they are settled — settled including "decided
against", which is what Item 1 mostly is. Work that is not one of those
moves gets its own segment; that is the guard, and it is the whole
reason this file is allowed more than one item.

Items close independently, so each carries its own `### Doc impact` and
`### Status` and there is no segment-level `## Doc impact`.

### Items

| Item | Covers | State |
|---|---|---|
| **19G.1** | §8 move #3 — whether summary drift deserves a mechanism | **Decided** 2026-09-08. Rung 1 landed; rungs 2–4 open. |
| **19G.2** | §8 move #2 — regenerate `spec/operator_button_audit.md` §§4–5, which describe a Session Home layout replaced 2026-08-19 | **Not started.** Filed in `guide/todo_master.md`; one PR. Plan it when it starts. |
| 19G.3+ | Open. Admitted only for follow-ups that trace to the 08sep assessment. | — |

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
were mechanized four days later by `tests/unit/test_doc_conventions.py`
(#2092), and row 3 records British spelling as "not a convention the
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

- **Does `docs/practice-audit-2026-09-04.md` §2 want a dated correction
  now** that two of its rows have been mechanized and one has been
  overtaken? Rule V says a dated document is annotated, never silently
  rewritten. **Decides:** the author, at PR 4.

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
the close, by which point the file is there.*

- `docs/unenforced_conventions.md` — **new.** The live list Article VI
  promises: one row per convention deliberately left unenforced, what it
  is written down at, why no check exists, and what constant would make
  it derivable. Seeded with class D and with the class B registry
  rejected here, so the reasoning is findable from where a future reader
  will look rather than only from an archived plan (PR 4).
- `constitution.md` — VI gains a pointer to that file (PR 4). Not
  counted by `close_check` — see Open questions.
- `docs/practice-audit-2026-09-04.md` — a dated annotation recording
  that rows 1b and 2 were mechanized by #2092 and row 3 overtaken by the
  2026-09-07 spelling entry; the table itself is not rewritten (PR 4,
  pending the open question).
- `spec/visibility_policy.md` — §3.1 gains one sentence recording that
  the table is now derived from the constant by a test, not merely
  transcribed from it (PR 3).
- `guide/README.md` — the `segment_*.md` row already covers this file;
  no change expected. <!-- doc-impact-waived: generic row already covers a new live plan; revisit only if 19G changes the folder's shape -->
- `docs/status.md` — row when each rung lands.

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
