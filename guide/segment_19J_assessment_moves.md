# Segment 19J — The assessment's three moves

**Opened:** 2026-09-10 · **Theme:** the three recommended next moves in
`guide/codebase_assessment_10sep.md` §8 · **Related:**
`guide/archive/segment_19G_post_assessment.md` (the same shape, one
assessment earlier), `guide/codebase_assessment_10sep.md`

The 10sep snapshot closed with three recommended moves, capped at three
by the assessment skill's own rule. This segment is those three and
nothing else. It exists because 19G proved the shape works: a segment
opened to settle an assessment's §8, with a finite scope and no
admission of anything that arrives later.

**What 19G also proved, and what this plan therefore expects.** That
segment planned two items and closed at ten, **eight of them produced
by the previous item's findings** rather than by the plan. The three
below are not a prediction of how many items this segment will have.
They are the three that were known at opening. ~~If a fourth arrives
from a finding, it is admitted; if one arrives from anywhere else, it
gets its own segment.~~

**Admission widened by the author, 2026-09-10, before the first
build.** The segment stays open for further items after these three,
whatever their source — not only findings of 19J.1–3. The original
rule is struck above rather than deleted, because the narrower shape
was a real decision and the reason it was widened matters: 19G and 19H
both took items the plan had not named and both closed cleanly, so the
restriction was buying a discipline those two segments already showed
they did not need.

**What that costs, and the trigger that answers it.** An open admission
rule is how 19C became a standing home — nineteen days, ten items, a
plan nobody read. The guard is not the admission rule but the close
trigger, which 19H demonstrated: this segment closes **when its queue
empties or at the next assessment snapshot, whichever comes first**,
and the queue emptying is checked at every item close rather than
noticed later. If the plan passes ~2,000 lines before that, it closes
on length and the residue opens a new segment — the rule 19I closed on
when its theme ran out.

**The trigger fired the same day, and is deliberately held.**
2026-09-10: 19J.1, 19J.3 and 19J.2 all closed, so the queue is empty
and the rule above says close. It stays open on the author's explicit
direction ("keep 19J open for more items after these 3"), which
post-dates the rule and overrides it. Recorded rather than quietly
resolved either way, because a close trigger that is silently skipped
the first time it fires is not a trigger — and because the plan is
~800 lines, well short of the length ceiling, so the reason to hold it
open is the author's and not the document's. **The next item admitted
here resets the clock; if none arrives, the next assessment snapshot
closes it.**

**Already, before the first build.** Measuring the blast radius of
these three corrected **three claims** that were carried in prose,
two of them mine from the snapshot published hours ago. Each correction
is recorded in the item that found it, and one of them changes what
Item 1 is for.

Items close independently, so each carries its own `### Doc impact`
and `### Status` and there is no segment-level `## Doc impact`.

### Items

| Item | Covers | State |
|---|---|---|
| **19J.1** | `spec/rrw_functional_spec.md` swept against the code | **Closed 2026-09-10** (3 rungs; 15 findings) |
| **19J.2** | The refinement allowance, measured rather than asserted | **Closed 2026-09-10** (1 rung; no stable term) |
| **19J.3** | `tools/close_check.py` — split it or stop mentioning it | **Closed 2026-09-10** (1 rung; split) |
| 19J.4+ | Open to further items, any source (author, 2026-09-10). Closes when the queue empties or at the next snapshot. | Open — **empty** |

---

## Item 1 — `spec/rrw_functional_spec.md` swept against the code

### Opportunity

`spec/rrw_functional_spec.md` is the **canonical entry point for new
readers** — `spec/README.md` says so — and it is the only ⚠ row in the
10sep snapshot's compliance table. §9.7 lists an Assignments
**"Self-reviews card — session-wide self-reviews-active toggle"** that
does not exist; the toggle is per-instrument, inside the per-instrument
status table (`session_assignments.html:85–90`). It was found by
`spec-writer` at 19I.12's close, reported, and left because inventing
the card is a feature decision and deleting the prose is a spec claim
nobody had settled.

**The snapshot's characterisation of this file was wrong, and measuring
it is what showed that.** §5 of `codebase_assessment_10sep.md` calls it
"the least-audited live spec" and cites `spec/README.md`'s "aligned
with the system as of 2026-08-18" as "23 days stale". Measured:

```
$ git log --oneline --since=2026-08-18 -- spec/rrw_functional_spec.md | wc -l
9
$ git diff <first-since>^ HEAD -- spec/rrw_functional_spec.md
725 insertions, 381 deletions
```

**Nine edits and 1,106 changed lines since the date it claims alignment
to.** The file is not neglected. What is true is narrower and more
interesting: every one of those nine edits was made by a segment
touching **the sections its own work touched** — 19C's friendly-label
carrier, 19F's specs pass, 19I.2, 19I.4, 19I.10, 19I.12 — and no edit
has ever read the document end to end. The alignment date in
`spec/README.md` has not moved through any of them.

So the defect is **not staleness; it is that piecemeal currency reads
as whole-document currency.** A spec edited nine times in three weeks
looks maintained, and its index line still promises alignment to a date
before all nine. A reader has no way to tell which sections were
checked and which were merely nearby. §9.7 is one section nobody's work
happened to touch, and it is wrong.

### Decision

**Sweep the document end to end against the code, fix what has drifted,
and replace `spec/README.md`'s fixed alignment date with something that
cannot silently rot.**

- **The sweep is section by section**, using the same shape as
  `guide/sweep_2026-09-05_spec-docs.md`: each §N read, each claim about
  behaviour checked against the code path that implements it, findings
  recorded with `path:line` evidence before any fix.
- **The alignment line changes form.** A date maintained by hand is a
  claim with no owner, which is what produced this item. It becomes a
  statement of **what kind of currency the reader can expect** —
  swept-on-date plus the note that per-subsystem specs are authoritative
  where they disagree — with the date owned by the sweep record rather
  than by whoever last edited a paragraph.
- **§9.7's Self-reviews card is deleted, not built.** The per-instrument
  toggle is the shipped design, `spec/assignments.md` documents it, and
  nothing else in the corpus references a session-wide card. Deleting
  the bullet is a correction; building the card is a feature request
  that has never been made.

Rejected: **fixing §9.7 alone and closing.** It is the cheap move and
it is the one that guarantees a repeat — §9.7 is wrong because nobody
read the whole document, and fixing only the section somebody happened
to notice leaves the mechanism exactly as it was. The measurement above
is the argument: nine edits, none of them a read-through.

Rejected: **retiring `rrw_functional_spec.md` in favour of the
per-subsystem specs.** It is the document a new reader meets first and
the only one that describes the product rather than a surface. The
overlap with per-subsystem specs is real but the answer to it is the
precedence note above, not deletion.

### Semantics

- **A drifted claim is one the code contradicts**, not one the code has
  moved past in emphasis. §9.7's card is drift; a section describing a
  page's purpose in different words than the surface spec is not.
- **Where this document and a per-subsystem spec disagree**, the
  subsystem spec wins and this one is corrected to match — the
  precedence the alignment line will state explicitly.
- **A section with no corresponding code** is either a feature that was
  cut (delete, recording what it said) or one never built (mark it, do
  not silently keep it in the present tense). The sweep must say which.
- **The sweep record is the artefact**, not the diff. `guide/sweep_*`
  is the existing shape; this one is scoped to a single file and says
  so.

### Judgment calls — decided

- **The whole document, not a sampled audit** (2026-09-10). At 2,235
  lines and 107 headings a sample would leave the same "which sections
  were checked?" question this item exists to answer.
- **`spec/README.md`'s line changes in this item, not a later one**
  (2026-09-10) — the line is the mechanism that let §9.7 sit wrong, and
  fixing the instance without the mechanism is the rejected alternative.
- **The snapshot gets an amendment** (2026-09-10). §5's "least-audited"
  and "23 days stale" are wrong as measured. 08sep was amended three
  times and 19G.3 established that a correction states what the claim
  used to be; this follows both.

### Blast radius (measured)

```
$ wc -l spec/rrw_functional_spec.md                                    # 2,235
$ grep -c "^## \|^### " spec/rrw_functional_spec.md                    # 107 headings
$ git log --since=2026-08-18 --oneline -- spec/rrw_functional_spec.md  # 9 commits
$ grep -rln "rrw_functional_spec" --include="*.md" . | grep -v archive # 10 files
```

- **1 spec, 2,235 lines, 107 sections** to read.
- **10 live documents reference it**: `spec/README.md`,
  `spec/permissions.md`, `spec/email_template_editor.md`,
  `docs/status.md`, `docs/practice-audit-2026-09-04.md`,
  `rrw_sdd_in_practice.md`, `guide/todo_master.md`,
  `guide/sweep_2026-09-05_spec-docs.md`, `guide/sweep_template.md`,
  `guide/codebase_assessment_10sep.md`. Only `spec/README.md`'s
  reference makes a claim about its currency.
- **Known drift so far: 1** (§9.7). The sweep's job is to find out
  whether that number is 1 or 20, and **the honest reading of this plan
  is that nobody knows** — which is the item.
- **No code changes expected.** If the sweep finds a claim the code
  should honour rather than the spec should drop, that is a finding and
  a new item, not a widening of this one.

### Status

**2026-09-10 — rung 1 landed. Rungs 2 and 3 follow.**

`guide/sweep_2026-09-10_rrw_functional_spec.md`, 467 lines, all
**108** headings read (the plan and the 10sep assessment both said
107 — that count excluded the `#` title; the file is 1 + 20 `##` +
87 `###`). **Fifteen findings across fourteen sections; 94 of 108
sections current (87%).** No spec was edited, as the rung
intended.

**The Opportunity's diagnosis was confirmed from inside the
document.** 19F changed the reviewee results gate to require a
resolving visibility grant. §10.9 says so correctly and names the
segment; §4.4 and §17 gate 5, describing the same gate, still
carry the pre-19F check. One fact, three places, and the one that
is right is the section 19F PR 6 happened to open. That is
piecemeal currency, demonstrated rather than argued.

**What the count of findings should not be read as.** Fifteen is
low for 2,235 lines, and the nine edits since August are why —
this is a maintained document with unmaintained *corners*. The
corners are where the value was: §5.3 still says reviewees are
"not participants" three months after they became an
authenticated audience, and §18's glossary prints "seven"
display-field sources directly above a bracket enumerating nine.

**Two findings turned out to be bigger than the assessment
recorded**, both because measuring changed the shape:

- **F7, the Self-reviews card.** The 10sep snapshot called it a
  card that does not exist. True — but
  `review_session.self_reviews_active` **does** exist, round-trips
  through the Settings CSV and clone, and has **no UI anywhere**
  (zero template hits). So the fix is not one deletion: §9.7's
  card goes, §8.6 must say the flag rides the Settings CSV, and
  whether a session-wide flag with no operator surface is a gap or
  a deliberate advanced affordance is the author's call.
- **F10, the Responses extract columns.** §12.3's *count* is
  right (21, checked column by column) and two *details* are
  wrong — the tenth column is `RevieweeEmail`, not
  `RevieweeEmail_or_Identifier`, and `SelfReview` sits after
  `Value`, not after `Version`. §12.7 promises byte-stable round
  trip, so this list is a contract a downstream consumer builds
  against; a wrong name and a wrong position are the two things
  that break one.

**One finding was written wrong and corrected inside the sweep.**
F15's first draft asserted that "Segment 14-1" appears "once in
the entire repository". Measured: **ten occurrences across four
files** — `email_outbox.py`, an outbox test, a shipped Alembic
migration, and this spec. So the two names are not a typo here but
a **corpus-wide vocabulary split**: the code, tests and schema say
14-1, the plans say 14B, and this spec is where they meet. The
disposition changed with it — rung 2 must not quietly make the
spec agree with the roadmap and disagree with the schema comments
a reader hits next. **The wrong version is left in the sweep with
its correction**, per 19G.3: a silent fix erases the evidence that
asserting-instead-of-measuring is still happening, including here,
in the document written to catch it.

**Three code comments** were found describing a world that has
moved, and recorded rather than fixed (this item's scope is one
spec): `deps.py:398` calls a referenced dependency an unreferenced
"Phase 1 stub"; `field_labels.py:89` says "12 in-scope slots"
where the constant holds 9 — **the identical 9-vs-12 drift the
specs had fixed on 2026-08-20**, never swept into the code; and
`sessions.py:190` names the Edit Session page that retired in 18R
Item 4. Each is a candidate 19J item if the author wants the class
chased in `app/`.

**Open question answered.** The plan asked what count would make
rung 2 too big to land in one PR. Fifteen findings over fourteen
sections, all update-in-place, is one PR — but **two of them (F7,
F15) carry a question the sweep declined to decide**, so rung 2
should land the thirteen mechanical ones and take direction on
those two.

**2026-09-10 — rungs 2 and 3 landed together, and both open
questions were answered by the author.** All fifteen findings
applied across fourteen sections, plus `spec/README.md`'s currency
line. Rung 3 merged into this push because its one edit is the
mechanism rung 2's edits exist to stop repeating.

**F7 — "Self review assignments are flipped active/inactive
through Assignments page" (author).** Checking that answer
corrected the sweep's own finding. The sweep said the session-wide
flag's "only operator surface is the Settings CSV round-trip",
implying it does nothing. **It is read by the generator** —
`_generate.py:346`, `review_session.self_reviews_active if
is_self else True` — so it seeds the `include` value of every
self-review pair at generation, and the Assignments status card
overrides per instrument afterwards. Two live layers, not a dead
column. §8.6 turned out to describe exactly that already and was
left alone; §9.7's phantom card went, and §9.7 / §10.3 / §5.9 now
name the real surfaces. **The finding was wrong in the direction
of alarm**, which is the opposite of this segment's usual failure
and worth the same treatment: corrected in place, stating what it
used to say.

**F15 — the author's convention hypothesis was right, and the fix
was already in the repo.** Numbering moved from `-1` / `-2` to
letters (the archive still holds `segment_12A-1/-2/-3`), and
`guide/segment_14B_email_infrastructure.md` **line 4 already
reads "Renamed from `segment_14-1_email_infra.md`"**. So the
equivalence needed stating in the spec, not building: §11.6 now
says 14B, points at that plan, and says in one sentence why the
schema comments still say 14-1. No corpus-wide rename, no new
item.

**A near-miss worth recording.** Rung 2 was written on a branch
restarted from `origin/main`, which does not carry rung 1 — so
`spec/README.md`'s new pointer to the sweep record was a **dead
path**, and `tests/unit/test_doc_conventions.py` failed on it.
That test is 19G.7's broken-path check, catching exactly the class
it was built for, on the sweep whose §6 notes the same check
cannot see F13. The work was saved as a patch, the branch reset to
rung 1's head, and the patch reapplied — no commit was lost, and
the check went green once the sweep file was actually present.

**Doc impact gained nothing.** `guide/segment_14B_email_infrastructure.md`
was read to resolve F15 but not edited — it already carried the
rename — so it is cited, not committed to.

### PR ladder

1. **The sweep, recorded.** Read all 107 sections against the code;
   produce `guide/sweep_2026-09-<dd>_rrw_functional_spec.md` in the
   existing sweep shape, with every finding carrying `path:line`
   evidence and a proposed disposition. **No spec edits in this rung** —
   the record is reviewable on its own, and separating finding from
   fixing is what let 19G.7 catch a measurement that had certified a
   corpus clean and was itself wrong.
2. **The fixes.** Apply the dispositions, §9.7 included. Each
   correction states what the claim used to be.
3. **The alignment line.** `spec/README.md`'s currency claim reworded,
   pointing at the sweep record.

Must not touch: the per-subsystem specs (a disagreement is fixed *here*,
per Semantics), and any code.

### Definition of done

- `guide/sweep_2026-09-<dd>_rrw_functional_spec.md` exists, covers all
  107 sections, and every finding carries `path:line` evidence
- §9.7 no longer describes a Self-reviews card
- `spec/README.md`'s line no longer carries a hand-maintained date
- the 10sep snapshot carries an amendment correcting "least-audited"
  and "23 days stale"
- `.venv/bin/pytest` and `.venv/bin/ruff check .` both pass
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19J.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **How many findings is "too many to fix in rung 2"?** If the sweep
  returns twenty, rung 2 splits by section group rather than growing.
  Decided at rung 1's end, on the count.

### Out of scope

- **Building a session-wide self-reviews card.** A feature request
  nobody has made.
- **The per-subsystem specs' own currency.** The 8-weeks-or-500-merges
  sweep cadence (19A Item 2) covers those; this item is one file.
- **`spec/README.md`'s other rows.** Only the row that made a currency
  claim about the file being swept.

### Doc impact

- `spec/rrw_functional_spec.md` — §9.7's Self-reviews card deleted, plus
  whatever else the sweep finds (Item 1).
- `spec/README.md` — the `rrw_functional_spec.md` row's currency claim
  reworded to point at the sweep record rather than a hand-kept date
  (Item 1).
- `guide/codebase_assessment_10sep.md` — §5's "least-audited live spec"
  and "23 days stale" amended; nine edits and 1,106 changed lines say
  otherwise, and the real defect is piecemeal currency reading as
  whole-document currency (Item 1).
- `docs/status.md` — row when the item closes (Item 1).

---

## Item 2 — The refinement allowance, measured rather than asserted

### Opportunity

`guide/codebase_assessment_10sep.md` §7 says the projection method
"models remaining features and does not model refinement", names a
missing term of **"roughly +1.5k production per active week"**, and
asks the next snapshot to carry it or record why not.

**That figure is an assertion, and this project's own standing rule is
that every number in an assessment is produced by a command or does not
go in.** It was reasoned from three windows read off the table, not
computed. It is currently the only number in that document that would
fail the rule it is written under.

The evidence it was reasoned from, taken from the sidecars:

| Snapshot | Window | Merges | Production LOC | Δ |
|---|---|---|---|---|
| 17aug | 2026-06-03 → 08-18 | 106 | 55,165 | — |
| 19aug | 2026-08-19 | 26 | 55,394 | +229 |
| 04sep | 2026-08-19 → 09-04 | 91 | 55,504 | +110 |
| 05sep | 2026-09-04 → 09-05 | 23 | 55,704 | +200 |
| 08sep | 2026-09-05 → 09-08 | 98 | 57,122 | +1,418 |
| 10sep | 2026-09-08 → 09-10 | 67 | 58,724 | +1,602 |

Two things are visible immediately and neither supports "+1.5k per
active week" as stated. The two large windows are **3 days each**, not
weeks. And the 04sep window is 16 calendar days and 91 merges for
**+110** — an order of magnitude below the recent pair. Whatever the
right term is, *per active week* is probably the wrong unit, and the
mean over these six windows is not it either.

### Decision

**Compute the term, decide its unit from the data, and write whichever
answer the data gives — including "there is no stable term".**

- **The unit is chosen after looking**, not before. Candidates: LOC per
  merge, LOC per non-merge commit, LOC per calendar day of an active
  window, LOC per closed item. The sidecars carry merge and commit
  counts for every window; item counts come from the archived plans.
- **Feature windows and refinement windows are separated** before any
  rate is computed, because mixing them is the defect §7 named. The
  classifier is the segment plans: a window whose segments shipped a
  new route or a new page is a feature window; one whose segments
  shipped only changes to existing surfaces is refinement.
- **"No stable term" is a permitted and possibly correct answer.** Six
  windows spanning +110 to +1,602 may simply not have a rate. If so,
  §7's method changes differently — a range with a stated floor and an
  explicit "unmodelled" line rather than a false precision.

Rejected: **carrying +1.5k/week forward and checking it next snapshot.**
That is what §7 proposed, and it is the weaker version of this item: it
makes one more snapshot's projection depend on an unmeasured figure, and
if it is wrong the error compounds into the next reconciliation exactly
as the skill's own "a recalled delta compounds" warning describes.

Rejected: **dropping §7's projections altogether.** They have been
useful twice — 05sep's being too low is what 08sep diagnosed, and
08sep's being too low is what produced this item. A projection that is
reconciled honestly each time earns its place; the fix is the missing
term, not the section.

### Semantics

- **An "active window"** is one between two snapshots with at least one
  segment closing in it. All six above qualify; the definition matters
  for future windows where a snapshot is taken during a quiet period.
- **Production LOC only.** Templates track production loosely and tests
  track it strongly; if the term is real it should be visible in the
  number the projection is about.
- **The sidecars are the source.** Six exist (`17aug` → `10sep`); older
  snapshots predate the sidecar convention and are excluded, with the
  exclusion stated rather than silent.
- **A term derived from six points is weak evidence** and the write-up
  says so. Six is what exists.

### Judgment calls — decided

- **The result changes `§7` of the *current* snapshot, not only the
  next one** (2026-09-10). §7 already names the term; if the measurement
  contradicts it, leaving it standing means the live snapshot carries a
  figure known to be wrong.
- **Segment plans are the feature/refinement classifier** (2026-09-10),
  not a heuristic over the diff. The plans state what each segment set
  out to ship, which is the question being asked.

### Blast radius (measured)

```
$ ls guide/archive/codebase_assessment_*.json guide/codebase_assessment_*.json
6 sidecars (17aug, 19aug, 04sep, 05sep, 08sep, 10sep)
$ ls guide/archive/segment_*.md | wc -l
(the plans that classify each window)
```

- **6 data points.** No new measurement infrastructure needed — every
  figure is already in a sidecar or an archived plan.
- **1 document changed** (`guide/codebase_assessment_10sep.md` §7),
  plus the skill's own guidance if the finding generalises.
- **No code, no spec.** This is arithmetic over existing artefacts.
- **The one risk is a false rate from six points**, which the write-up
  states rather than hides.

### Status

**2026-09-10 — landed in one rung, as planned. The answer is the
permitted one: there is no stable term.**

Five deltas, computed from the six sidecars; classification applied
mechanically rather than from recollection —
`git diff --name-status <since>..<head>` for files added under
`app/web/routes*` and `app/web/templates/*.html`. **Exactly one of
the five is a feature window** (05sep→08sep: `routes_guide.py`,
`routes_templates.py`, `guide.html`); the two templates added in the
most recent window are partials, not pages.

Every candidate unit the plan named was computed, plus one it did
not — production-touching commits — because "merges" turned out to
count windows where production was barely touched at all (91 merges
for +110 lines). None stabilises: **14× to 117× spread across the
four refinement windows**, tightest per non-merge commit, worst on
the asserted unit.

**The asserted figure, in its own unit.** "+1.5k per active week"
measures 48 to 5,607 across the five windows — a **117× spread**
around a median of 1,603. The assertion was not wildly placed; it was
placed in a distribution too wide for any single figure to carry a
projection, which is what "compute it" was for.

**Two corrections the measurement made to §7's diagnosis, which was
also mine.**

1. **The feature/refinement split does not explain the variance** —
   and it was the fix §7 proposed. The feature window is *mid-range*
   on every unit (14.5 LOC per merge, against 1.2–23.9 for refinement
   windows), and the biggest window in the set is a refinement window.
   Sorting windows by kind does not sort them by growth, so "the
   method does not model refinement" was the wrong account of why the
   projection kept being overtaken.
2. **Net production LOC is a residual.** Gross production churn against
   net growth: 1,736→229, 1,754→**110**, 224→**200**, 3,342→1,418,
   4,476→1,602 — a net/gross ratio from **0.06 to 0.89**. A window that
   rewrites in place and one that adds look nothing alike, and the
   projection is the difference of two numbers an order of magnitude
   larger than itself. That is the mechanism; "refinement" was a label
   on it, not an explanation.

**What §7 became.** No allowance line. The per-item table is stated as
a **floor** that models named work only, and future snapshots
reconcile against it by saying *by how much it was overtaken* — a
measurement — rather than projecting a total that pretends to model
the overtaking. A third snapshot being overtaken is now the expected
result rather than a surprise to explain.

**Open question answered: no.** The mechanism generalises, but the
`codebase-assessment` skill lives outside this repository; changing it
is the author's call, not a side effect of an item that measured one
project's five windows.

**What this item did not do.** It did not re-take any snapshot's
tables — the sidecars are the record and this read them, as Out of
scope required. Six sidecars exist; older snapshots predate the
convention and are excluded, stated here rather than left silent. Five
points is weak evidence for any positive claim, which is part of why
the negative one — *no stable term* — is the defensible answer.

### PR ladder

1. **The measurement and the §7 amendment**, together. One rung: the
   arithmetic is short, and a rung that computed a number without
   writing what it means would be a commit nobody can review.

### Definition of done

- the term is computed from the six sidecars with the commands recorded
- feature and refinement windows are separated, with the classification
  per window stated
- `guide/codebase_assessment_10sep.md` §7 carries the computed term, its
  unit, and its weakness — or records that no stable term exists and
  what §7 does instead
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19J.2` exits 0; any warning adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Does the finding belong in the `codebase-assessment` skill?** If the
  term generalises past this repo it is guidance, not a local number.
  Decided when the number exists.

### Out of scope

- **Re-taking any prior snapshot's tables.** The sidecars are the
  record; this item reads them.
- **Projecting anything past v1.**

### Doc impact

- `guide/codebase_assessment_10sep.md` — §7's asserted "+1.5k per active
  week" replaced by the computed term and its unit, or by an explicit
  finding that no stable term exists (Item 2).
- `docs/status.md` — row when the item closes (Item 2).

---

## Item 3 — `tools/close_check.py` — split it or stop mentioning it

### Opportunity

Three consecutive snapshots have carried the same observation:
`tools/close_check.py` holds two jobs in one file. It was 770 LOC when
first noted, 863 at 08sep, and **1,000 at 10sep — +30% since the
observation was made**, each snapshot repeating it and none acting. The
10sep entry says a fourth repetition should come with either a split or
a decision to stop mentioning it. This is that.

**Measured, and the measurement corrects the observation itself.** All
three snapshots describe the two halves as sharing "`REPO`, `_git` and
`last_touched_ever`". They do not:

```
$ grep -n "last_touched_ever" tools/close_check.py
502:def last_touched_ever(path: str) -> str | None:
627:            ever = last_touched_ever(entry["path"]) or "never"
```

Line 627 is inside `check_manifest` — the close-check half. **The sweep
half never calls it.** The shared surface is `REPO` and `_git`, and
nothing else.

And there are **three** modes, not two:

| Lines | Job | Entry |
|---|---|---|
| 121–800 | the per-segment close check | `close_check.py <id>` |
| 801–860 | the archive-wide baseline report | `--archived` |
| 861–956 | the sweep-cadence report | `--stale` |

680 / 60 / 96 lines, sharing two module-level names. That is less
coupling than three snapshots have claimed, which makes the split
cheaper than the observation implied — and cheapness was the reason
given each time for not doing it.

### Decision

**Split it into a package**, `tools/close_check/`, mirroring the
per-concern carves 18O and 18N used on production code:

- `_shared.py` — `REPO`, `_git`, `Unresolvable`, `resolve_committed`
- `_manifest.py` — the close check (parsing, windows, C1–C7,
  `check_manifest`, `run`, `report`)
- `_archive.py` — `archived_report`
- `_sweep.py` — `sweep_scope`, `last_sweep_date`, `stale_report`
- `__init__.py` — `main()` and the argument parser

The CLI is unchanged: `python3 tools/close_check.py <id>` must keep
working, because that exact string appears in every plan's Definition
of done and in `CLAUDE.md`.

Rejected: **stop mentioning it.** The other half of the 10sep
ultimatum, and it loses on the measurement above — the coupling that
justified inaction turns out to be two names. A watchlist entry
declined on a reason that has been checked and found wrong should be
acted on, not retired.

Rejected: **splitting only the sweep half out** and leaving 740 lines.
It is the smaller change and it leaves `--archived` — a third job — in
a file named for the first. The three-way split is barely more work
than the two-way one.

### Semantics

- **The CLI contract is frozen.** Every flag, exit code and stderr line
  behaves identically; `tests/unit/test_close_check.py` loads the module
  by path and must keep passing, which is the contract's own gate.
- **`tools/close_check.py` stays as the entry point** — a package
  directory beside it would change the invocation string. Either the
  file becomes a thin shim importing the package, or the package
  directory takes the name and the `.py` goes; the rung decides on
  whether `importlib.util.spec_from_file_location` in the existing test
  survives it. **Whichever keeps the invocation string identical wins.**
- **No behaviour change.** Not one check's verdict may move. The proof
  is running the split version against every archived plan and diffing
  the output against the pre-split run.

### Judgment calls — decided

- **A package, not two files** (2026-09-10) — there are three jobs, and
  `_shared.py` has somewhere to live.
- **The observation's own error is recorded, not quietly fixed**
  (2026-09-10). Three snapshots said `last_touched_ever` was shared. The
  10sep amendment says what the claim used to be, per 19G.3.

### Blast radius (measured)

```
$ wc -l tools/close_check.py                                  # 1,000
$ grep -rn "close_check" --include="*.py" . | grep -v tools/  # 1 caller
$ grep -rn "close_check.py" --include="*.md" . | wc -l        # every plan's DoD
```

- **1 file, 1,000 lines, 3 jobs**, sharing 2 module-level names.
- **1 code caller**: `tests/unit/test_close_check.py`, which loads it by
  path via `importlib.util.spec_from_file_location`.
- **Every archived plan's Definition of done** names the invocation
  string, which is why it is frozen.
- **No production code touches it.** It is dev tooling; `app/` has no
  reference.

### Status

**2026-09-10 — landed in one rung, as planned. Two costs the plan did
not predict, both measured.**

`tools/close_check.py` is now a 36-line shim over
`tools/close_check/`: `_shared.py` (37), `_manifest.py` (683),
`_archive.py` (85), `_sweep.py` (126), `__init__.py` (the 107-line
reasoning docstring + `main`). The invocation string is unchanged.

**The shape was verified, not assumed.** A `.py` and a same-named
package directory coexist, and the directory wins on the same
`sys.path` entry — probed in a throwaway tree for both `python3
tools/close_check.py` and `importlib.util.spec_from_file_location`
(the test's loader) before a line of the real carve was written.

**`_shared` is three names, not the file the plan imagined.**
Measured usage across the three halves:

| name | manifest | archive | sweep |
|---|---|---|---|
| `REPO` | 10 | 2 | 5 |
| `_git` | 6 | 0 | 3 |
| `Unresolvable` | 3 | 0 | 2 |

Nothing else crosses. `resolve_committed`, the three manifest regexes
and `last_touched_ever` are manifest-only — so the coupling is even
lower than the item's Opportunity measured, and lower again than the
three snapshots that declined the split on it.

**`_archive` is not a peer of the other two.** It calls five
`_manifest` functions (`find_manifests`, `_section`, `parse_bullets`,
`window`, `honoured`) and adds a loop and totals. "Three jobs in one
file" was right about the count and wrong about the shape: two are
independent, one is a driver. That is why it is 85 lines and not 600,
and it is recorded in its own module docstring.

**Cost 1 — the carve broke the test seam, and the fix is the
interesting part.** `REPO` was a module global, so
`monkeypatch.setattr(cc, "REPO", root)` reached every reader. After
the split, `from ._shared import REPO` binds a **copy per module** and
that one patch silently misses them — eight tests failed on a real
path escaping into `/tmp`. The fix keeps a single patch point rather
than adding three: `_manifest`, `_archive` and `_sweep` reference
`_shared.REPO` through the module instead of importing the name, and
the test patches `cc._shared.REPO`. The plan's Definition of done
allowed exactly this ("or its loader is updated with the reason
recorded"); the reason is recorded in the test, in eight lines,
because the next person to add a module here needs to know why the
constant is spelled the long way.

**Cost 2 — the carve created a bytecode cache where there was none,
and it served stale code inside twenty minutes.** A single-file script
run as `python3 tools/close_check.py` is compiled and **never
cached**; once it is a package the script *imports*, every module gets
a `.pyc`. Python invalidates on `(mtime, size)` — so a same-size edit
restored within the same filesystem second is indistinguishable from
the original. Restoring a mutation of `"pass"` → `"okay"` (four
characters for four) produced a tool that kept printing `OKAY` from a
clean source, and it took a `find -name __pycache__ -delete` to
resolve. `__pycache__/` is already in `.gitignore` so nothing ships,
but **the tool now has a staleness mode it did not have before**, and
anyone editing it in a tight loop should know that.

**The proof the plan asked for, and a check on the proof.** All CLI
modes were captured before the carve and diffed after: `--archived`,
`--stale`, five ids spanning pass and fail (`19J.1`, `19J.2`,
`19I.12`, `18R`, `19G`), `--json`, an unknown id, `--since` without
`--stale`, and `--help` — 22 streams over stdout and stderr, plus
every exit code. **All 22 byte-identical; exit codes `0 0 0 0 0 1 0 0
2 2 0` match.**

That claim was then tested for vacuity, because "no diff" is the
easiest passing assertion to write and the hardest to trust. The
first mutation attempt (`sed` on the literal `PASS`) **matched
nothing** — the verdict is computed from a constant, not printed
literally — and reported "not caught", which would have certified the
harness as blind. The real mutation, flipping the `PASS` constant's
value, was caught. The lesson is 19I's at one more remove: *a
mutation test can itself be vacuous, and a vacuous mutation test
looks exactly like a failing one.*

**Judgment held.** The plan rejected "stop mentioning it" on the
grounds that the coupling justifying three snapshots of inaction had
never been checked. The check confirmed the plan: three shared names,
one of the three "jobs" a thin driver. The split was cheap. The two
costs above are real and neither would have been visible without
building it.

### PR ladder

1. **The split**, with the CLI frozen and the archived-plan output
   diffed pre- and post-split as the proof.

### Definition of done

- `python3 tools/close_check.py <id>`, `--archived`, `--stale`,
  `--since`, `--json` all behave identically
- the pre/post `--archived` output over every archived plan is
  byte-identical
- `tests/unit/test_close_check.py` passes unmodified, or its loader is
  updated with the reason recorded
- `.venv/bin/pytest` and `.venv/bin/ruff check .` both pass
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19J.3` exits 0 — **run from the split
  version**
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

None. The one that mattered — whether the coupling makes a split
expensive — was answered by the measurement.

### Out of scope

- **Any change to what the checks check.** C1–C7 keep their current
  semantics exactly; this is a carve, not a revision.
- **The long-window C3 weakness**, measured and downgraded at 19G.10.

### Doc impact

- `guide/codebase_assessment_10sep.md` — §5's and §9's
  `tools/close_check.py` entries: the split recorded, and the
  three-snapshot claim that the halves share `last_touched_ever`
  corrected with what it used to say (Item 3).
- `docs/status.md` — row when the item closes (Item 3).
