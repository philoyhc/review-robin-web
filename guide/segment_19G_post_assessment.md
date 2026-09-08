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
| **19G.2** | §8 move #2 — regenerate `spec/operator_button_audit.md` §§4–5, which described a Session Home layout replaced 2026-08-19 | **Closed** 2026-09-08 (PR #2203). One PR, three `spec-writer` corrections. |
| **19G.3** | The patch queue below — three documentation corrections | **Closed** 2026-09-08. One PR; a fourth found beside them. |
| 19G.4+ | Admitted only for work arising from this segment's own items. | Open — **empty** |

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

---

## Carried open questions

Promoted from Item 1 at its close (2026-09-08) because neither is
Item-1-shaped and both would otherwise be buried in a closed item.

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

- **Should `close_check`'s `COMMITTED_PATH` widen to root-level `.md`?**
  It matches backticked `.md` paths under `spec/` or `docs/` only, so
  Item 1's `constitution.md` and `rrw_sdd_in_practice.md` bullets were
  never counted — the tool that checks whether committed doc edits
  happened has a scope narrower than the manifests it validates, which is
  this segment's own subject one level up. **Decides:** the author. A
  one-line pattern change with an unmeasured blast radius across every
  existing plan's manifest, so it is a slice of its own, not a rung.

