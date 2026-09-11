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

**The clock reset, 2026-09-11.** Two items arrived from the author the
day after the queue emptied — 19J.4 and 19J.5, both out of one
operator-experience report about large rosters. They are the first
exercise of the widened admission rule: neither is a finding of
19J.1–3, so under the struck original neither would have been admitted
here. The close trigger is live again and unchanged — this segment
closes when 19J.4 and 19J.5 close, or at the next assessment snapshot,
whichever comes first.

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
| **19J.4** | Navigation busy indicator, once in the chrome | **Built 2026-09-11** (1 rung; `close_check` PASS) — held open for dev-slot verification, now tracked as item 3 of `guide/post_azure_todo_checklist.md` |
| **19J.5** | Row pagination on the seven roster-bearing pages | **Closed 2026-09-11** (4 rungs + a verification PR; seven of seven pages paged, sort in SQL) |
| **19J.6** | Session-nav hover standardised to the selected style | **Closed 2026-09-11** (1 PR; `close_check` C3 fails by construction — logged after it shipped, adjudicated in Status) |
| **19J.7** | Pills rationalization — one vocabulary for two jobs | **Stub, opened 2026-09-11** — audit landed, decision open |
| 19J.8+ | ~~Open to further items, any source (author, 2026-09-10). Closes when the queue empties or at the next snapshot.~~ Four items admitted 2026-09-11; the rule stands, the clock resets on each. | Open |

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

---

## Item 4 — Navigation busy indicator, once in the chrome

### Opportunity

Operator report, 2026-09-11: *"When the rosters get large, assignments,
invitations, and responses take longer to load. It's not a big deal but
would be nice if there's on screen [feedback] to reassure operator that
the app is not hanging."*

Measured in the session container before writing this item — full-matrix
sessions seeded through the real import + generate routes, timing the
three pages and counting SQL statements per render:

| roster | assignments | Assignments | Invitations | Responses |
|---|---:|---|---|---|
| 25×25 | 625 | 182 ms / **43 q** | 295 ms / 708 q | 274 ms / 1,332 q |
| 50×50 | 2,500 | 165 ms / **43 q** | 506 ms / 2,633 q | 999 ms / 5,132 q |
| 100×100 | 10,000 | 76 ms / **43 q** | 2,209 ms / 10,233 q | 3,947 ms / 20,232 q |
| 200×200 | 40,000 | 516 ms / **43 q** | 9,323 ms / 40,433 q | 16,125 ms / 80,432 q |

SQLite, in-process, ≈0.2 ms per query. Production Postgres pays a
network round trip per query, so **the query count is the portable
number and these times are a floor, not a ceiling.**

Assignments is flat at 43 queries at every scale — its `LIMIT 200` and
its indexes hold. Invitations and Responses are N+1:
`app/services/responses/_core.py:804` issues one `SELECT responses WHERE
assignment_id = :id` per assignment inside the per-reviewer loop, and
`app/services/monitoring.py:283` (`_assignment_complete`) does the same
per assignment on the reviewee side. Responses pays both, because it
builds its rows from `per_reviewee_coverage` **and** calls
`summary_counts` (`app/web/routes_operator/_operations.py:757`) — a
second full per-reviewer pass whose only consumer is one integer,
`incomplete_count` (`:814`).

So these pages are slow for a fixable reason, and **this item is not
that fix** (see Out of scope). It is the affordance worth having
regardless: a cold slot, a large extract, a generate over 40,000 pairs
will always take seconds, and today the app offers the operator nothing
but the browser's own tab spinner while the old page sits there looking
live.

### Decision

One **global navigation busy indicator** in
`app/web/templates/base.html`: a delegated listener over same-origin
link clicks and form submits that arms a short timer and then marks the
document busy — an indeterminate progress bar in the page chrome, plus a
busy state on the control that was clicked. No per-page work and no
per-route opt-in; all 34 templates that extend `base.html` inherit it,
including every page added after it.

**Rejected: per-page async table loading** (render the shell, fetch the
table into it). Better on the two worst pages, but it splits each page
into two routes, doubles the round trips, and pushes the sort / filter /
POST-redirect flows through a second code path — a large change to buy
on three pages what the chrome buys on all of them. Reconsider only if
the N+1 fix does not land.

**Rejected: a determinate progress bar.** A single blocking
`TemplateResponse` has no progress to report, and a bar that invents one
is a lie the operator can catch by watching it.

### Semantics

- **Arms on a delay, not on the event** — ~200 ms, so a page that
  returns in 60 ms never flashes. A page slower than the delay is
  exactly the page this exists for.
- **What counts as a navigation**: an unmodified left click on a
  same-origin `a[href]`, and a form `submit`. Excluded — modified and
  middle clicks, `target="_blank"`, `download`, and bare `#` fragments.
  None of them replace the page.
- **Disarms on `pageshow`.** The back button restores from bfcache with
  the DOM as it was; without this the bar is still running on a page
  that finished loading minutes ago.
- **Never `disabled` a submit button synchronously.** A disabled control
  is not serialized, so its `name`/`value` disappears from the payload —
  and this codebase's forms carry meaning in exactly that slot (the
  super-button, the roster bulk actions). Mark busy after the submit is
  dispatched, or use `aria-disabled` + `pointer-events: none`.
- **Double-submit suppression** is a consequence of the busy state, not
  its goal, and must not be bought with the mechanism ruled out above.
- **`prefers-reduced-motion`** gets a static bar, not an animated one.
- **Assistive tech**: the bar carries a polite `role="status"` region.
  No focus is moved and nothing is trapped.
- **JS off**: nothing renders, nothing breaks. Progressive enhancement
  over a server-rendered page, in the idiom `base.html` already uses six
  times.

### Judgment calls — decided

- **In `base.html`, not a static asset** (2026-09-11) — CSS and JS stay
  inline there by the templating convention; `app/web/static/` exists
  for the Guide's screencaps and is deliberately not an asset pipeline.
- **One indicator, not one per slow page** (2026-09-11) — the report
  names three pages, but the affordance belongs to the chrome; a
  per-page one has to be remembered on every page added afterwards.
- **Indeterminate** — see Decision.

### Blast radius (measured)

```
$ wc -l app/web/templates/base.html                              # 4,178
$ grep -c "<script" app/web/templates/base.html                  # 6
$ grep -rln 'extends "base.html"' app/web/templates | wc -l      # 34
$ grep -rl 'method="post"' app/web/templates | wc -l             # 26 templates
$ grep -rho 'method="post"' app/web/templates | wc -l            # 73 forms
$ grep -rn -i "spinner|busy|loading" spec/ui_elements.md \
      spec/operator_ui_concept.md                                # 0 hits
```

- **1 template touched**; **34 inherit** the result.
- **73 forms across 26 templates** are the submit surface — the reason
  the `disabled`-serialization rule above is a semantics line and not a
  footnote.
- **No existing convention to extend**: neither UI spec mentions a busy,
  loading or spinner state today, so §1 of `spec/ui_elements.md` gains
  an entry rather than amending one.

### Status

**2026-09-11 — landed in one rung, as planned, but in six files rather
than one.** The ladder held; the blast radius did not.

**What the blast radius missed, and how.** It counted the template the
change lives in (1 touched, 34 inheriting) and never asked what a
*navigation* is. Some links in this app are not navigations: **twelve
anchors across five templates** point at routes that answer with
`Content-Disposition: attachment`. The browser downloads the file and
leaves the page where it was — so no load event ever arrives, and the
bar would have run until the give-up timer on every export the operator
clicks. The one bug this feature could plausibly ship, and the measured
blast radius pointed straight past it, because it measured *where the
code goes* rather than *what the code observes*.

**How it was closed, and why not with a bespoke marker.** Two anchors
already carried `download` — `reviewer/collation.html`'s CSV link and
one on the Extract data page. So the exclusion the plan's Semantics
already named is a convention this codebase had started and not
finished, not a new signal: the other twelve were brought into line
rather than given a `data-rrw-no-busy` of their own. That also makes the markup more
correct independently of this feature.

**Seven of the twelve were found by the test, not by me.** The first
pass marked five anchors from a `grep` over `href="…download…"`. The
scan in `tests/unit/test_busy_indicator.py` — which walks every
template and fails on an attachment link without the attribute — then
failed on four more in `session_extract_data.html`; re-reading that
page for those four turned up three more, the `data-shape-download`
anchors whose `href` is written at runtime and so matches no static
scan at all. The scan carries its own anti-vacuity test (it finds 11
attachment-href anchors today and asserts at least 5), because a regex
that matched nothing would have passed silently and certified the very
blindness it exists to prevent.

**What the suite covers and what it cannot.** Nothing in pytest clicks
a link, so the arming, the bfcache clear and the reduced-motion path
are dev-slot verification and the PR says so plainly. What *is* covered
is the regression a future editor is most likely to introduce:
`disabled` on a submit button. It is the obvious way to stop a double
submit, it looks harmless, and it drops the button's `name`/`value`
from the payload — which the Workflow super-button and the roster bulk
actions depend on. `test_the_script_never_disables_the_submitter`
slices the IIFE out of `base.html` and asserts the string is absent, so
the edit fails a test instead of failing in production.

**Decisions confirmed at build:**

- 200 ms arming delay and a 60 s give-up timer. The give-up value comes
  from the measurement, not from taste: the slowest page measured for
  this item was 16.1 s, so 60 s cannot cut a real load short and still
  bounds a missed signal.
- `aria-busy` on the clicked control, never `disabled` — as planned,
  now test-pinned.
- The bar ships `hidden` in the initial HTML and the live region does
  not, because a region created and populated in the same tick is not
  reliably announced.
- Links already carrying `aria-disabled` are skipped too — the extract
  page renders its Download buttons that way before a shape is wired,
  and they navigate nowhere.

### PR ladder

1. **The indicator** — CSS, the delegated script, and the `role="status"`
   region, all in `base.html`. One rung: the scaffold-first rule
   (`CLAUDE.md` → Working approach) governs new pages, cards and
   navigation affordances, and this adds none of the three. ~~Must not
   touch any page template~~, any route, or the N+1.

   *Struck 2026-09-11 at build.* The one-rung shape held and the route
   and N+1 exclusions held; the page-template exclusion did not survive
   the attachment-link finding in `### Status` above. Nine anchors
   across five templates gained a `download` attribute, which is the
   signal the script reads and a convention `collation.html` had
   already started.

### Definition of done

- the bar arms on a slow navigation and never on a fast one — dev slot,
  and the PR description says plainly that this half is dev-slot
  verified rather than test-covered
- a back-button restore shows no bar
- a submit button's `name`/`value` still reaches its route: a test posts
  through a form whose branch depends on the button's value
- the `prefers-reduced-motion` path is present
- JS off: every page renders as it does today
- `.venv/bin/pytest` and `.venv/bin/ruff check .` both pass
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19J.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Where the bar sits** — fixed to the viewport top, or the top of the
  content column. Author decides at the rung; fixed survives a scrolled
  page, which is the case that matters on a 200-row table.

### Out of scope

- **The N+1 fix on Invitations and Responses.** Measured above and named
  here so it is not lost. It is a service-layer change with its own
  contract — a prefetched response map threaded through
  `_state_from_assignments` and `_assignment_complete` — and its own
  test surface. Prototyped in the session container: Invitations
  **2,348 → 666 ms, 10,233 → 333 queries**; Responses only 1.6× until
  `per_reviewee_coverage` gets the same treatment. A candidate item for
  this segment, not part of this one.
- **The `summary_counts` second pass on Responses**, which costs about
  half that page's queries to produce one integer. Same reason.

### Doc impact

- `spec/ui_elements.md` — §1 Page chrome gains the busy-indicator entry:
  when it arms, what it renders, and the reduced-motion and JS-off
  behaviour (Item 4).
- `docs/status.md` — row when the item closes (Item 4).

---

## Item 5 — Row pagination on the seven roster-bearing pages

### Opportunity

Author, 2026-09-11: the pages that stop at 200 rows should offer a row
of range links — `1–200`, `201–400`, `401–556` — across **all seven
pages that carry a roster table**, not only the capped ones.

Where those seven stand today:

- **Reviewers / Reviewees / Relationships / Observers** — `200`
  unfiltered, `500` filtered (`_SETUP_DEFAULT_CAP` /
  `_SETUP_FILTERED_CAP`, `app/web/routes_operator/_shared.py:480`).
  Rows past the cap are unreachable except by searching for them.
- **Assignments** — `PAIR_PREVIEW_LIMIT = 200`
  (`app/services/assignments/_coverage.py:28`), applied as a SQL
  `LIMIT`.
- **Invitations / Responses** — uncapped by decision
  (`spec/operations_pages.md:189`), which is why they are the two that
  hurt at scale (19J.4's table).

The measured shape decides the cost, and it differs by page:

- The four Setup pages already load the **whole** roster, sort it in
  Python and filter it in Python, and only then slice `[:cap]`
  (`_setup_reviewers.py:148–152` and its three siblings). The cap is a
  rendering slice over a list already in memory — paging them costs an
  offset and a pager, and not one extra query.
- Assignments caps in SQL, so `OFFSET` is cheap — measured
  `list_pairs(limit=200)` at **12 ms** against 40,000 assignments. But
  its cookie sort runs in Python *after* the fetch. Fetching everything
  and slicing instead — the Setup pages' shape — measured **1,989 ms**
  to hydrate 40,000 pairs with three joined loads, against **23 ms** to
  sort them. The cost is hydration, not ordering.

### Decision

A **pager on all seven pages**, rendered **twice** — at the existing
count-line position and again below the table — as a row of range links
with first / last jumps inline at each end.
`app/web/templates/operator/partials/_preview_count_line.html` is
already included by all seven, so the pager ships as one partial beside
it and every page gets it from one edit.

**Suppressed whenever the roster is already partitioned by the filter
strip** (author, 2026-09-11): a search or status filter is the
operator's own partition of the roster, and a second partition stacked
on it is two mental models for one table. ~~Filtered views keep today's
behaviour exactly — the 500 cap and its `Showing first 500 of 900
matching reviewers; 400 more not shown.` line.~~ Filtered views keep the
500 cap; their **wording changes** — see the count-line semantics below,
revised by the author 2026-09-11.

**Rejected: an infinite-scroll or "load more" control.** It cannot say
where you are, cannot be linked to, and cannot be jumped from; the
request is explicitly for a row of ranges.

**Rejected: fetch-all-and-slice on Assignments** — 1,989 ms, measured
above.

### Semantics

- **Page size is the existing cap**, 200. The unfiltered cap stops being
  a truncation and becomes a page size. The filtered 500 stays a
  truncation, because filtered views carry no pager.
- **The count line stops being the table's caption and becomes the
  filter's** (author, 2026-09-11). ~~`Showing first 200 of 1,240
  reviewers; 1,040 more not shown.` describes rows being withheld, and
  stops being true once they are reachable. The paged line states a
  position — `Showing 201–400 of 1,240 reviewers.` — so
  `app/web/views/_preview_counts.py`'s four-state table gains a fifth
  state.~~ Where the pager renders, **no line renders at all**: the
  ranges already say where the operator is, and a sentence repeating
  them is the noise the quiet case was introduced to avoid (19I Item 4).
  The sentence is needed *more* on filtered views, which carry no pager,
  and it reads:

  | State | Sentence |
  |---|---|
  | filter active, under the cap | `Showing 37 reviewers.` |
  | filter active, capped | `Showing 500 of 900 reviewers, 400 more not shown.` |
  | no filter (pager renders, or the roster fits one page) | *(nothing)* |

  So `app/web/views/_preview_counts.py` does not gain a fifth state. Of
  the three states that produce a sentence today, **one retires**
  (capped-and-unfiltered, now the pager's job) and two survive reworded;
  the quiet state absorbs every unfiltered case. The helper only ever
  fires when a filter is active. Its `total` argument goes with the
  retired state — nothing left counts against the roster — and the word
  `matching` goes with it too: once `of M` can only mean the matching
  pool, the qualifier the current docstring introduced to disambiguate
  the two pools has nothing left to disambiguate.
- **One flag drives both.** The pager's suppression and the count line's
  appearance key off the same `is_filtered` the routes already compute —
  not off `matching < total`, which is what `preview_count_line` tests
  today. A filter that happens to match every row is still a filtered
  view: it renders `Showing 1,240 reviewers.` and no pager, which is the
  honest answer (the filter ran and excluded nothing) and keeps the two
  affordances from ever disagreeing about which mode the page is in.
- **Out-of-range offsets clamp, they do not 404**: past the end lands on
  the last page, negative on the first. A stale link after a delete is
  not an error page.
- **Invitations and Responses gain a cap they never had.**
  `spec/operations_pages.md` calls both uncapped, deliberately; paging
  them changes that contract, so the spec edit is part of this item
  rather than a consequence of it.
- **The pager drops `selected=`.** Selection stays page-local: the
  checkboxes act on rows in view, and carrying a hidden selection across
  a page boundary is how an operator deletes something they cannot see.
- **Sort is a cookie** and survives paging unchanged on the four Setup
  pages, which sort the whole roster before slicing. On Assignments it
  does not — see Open questions.
- **The edit-row force-include** (`_setup_reviewers.py:154–161`, which
  prepends an edited row that falls outside the window) should instead
  land the operator on the page that holds the row.
- **Elision.** 40,000 assignments is 200 range links. The pager renders
  a window around the current page with first and last always present;
  the window size is a rung-1 decision.

### Judgment calls — decided

- **Two pagers, above and below the table** (author, 2026-09-11) — a
  200-row table is many screens tall, and a pager only at the top makes
  the operator scroll back to use it.
- **Ranges, not page numbers** (author, 2026-09-11) — `201–400` says
  where you are in the roster; `page 2` makes the reader multiply.
- **No count line where the pager renders** (author, 2026-09-11) — the
  pager states the position, so the sentence would be a second voice
  saying the same thing. This supersedes the "fifth state" written into
  this item the day it was planned; struck above rather than edited out,
  because the superseded shape was a real decision.
- **The filtered sentence drops the roster total** (author, 2026-09-11)
  — `Showing 37 reviewers.` replaces today's `Showing 3 of 1,240
  reviewers.`. Worth naming what that costs: the operator loses the
  denominator that says how far the filter narrowed. Against it, the
  roster total is on the page anyway (the info card) and the sentence
  now has one job. Flagged to the author at rung 2 if the loss reads
  worse in practice than it does here.
- **Page size is not operator-configurable** (2026-09-11) — one number,
  already specified and already tested. A selector is a setting, an
  inventory row in `spec/settings_inventory.md` and a persistence
  question, for a need nobody has stated.

### Blast radius (measured)

```
$ grep -rln "_preview_count_line.html" app/web/templates             # 7
$ grep -rn "views.preview_count_line" app/web/routes_operator/*.py   # 7
$ grep -rln "preview_count_line\|Showing first\|_SETUP_DEFAULT_CAP\
      \|PAIR_PREVIEW_LIMIT\|table-showing-hint" tests/ --include=*.py # 11
$ grep -rln "Showing first\|200 unfiltered\|500 when" spec/ docs/    # 3
```

- **7 templates, 7 route call sites, 6 route modules** — the four
  `_setup_*.py` slices, `_assignments.py`, and `_operations.py` twice
  (Invitations and Responses live in the same module).
- **11 test files** name a cap or the count line;
  `tests/unit/test_preview_count_line.py` is the contract test for the
  sentence itself, and is where the surviving two states and the two
  `None` branches get pinned.
- **3 spec files**: `spec/setup_pages.md` "Preview tables (shared toggle
  pattern)", `spec/assignments.md` "The preview-count line (Segment 19I
  Item 10)", and `spec/operations_pages.md`'s two uncapped statements
  (`:189`, `:291`).

### Status

**2026-09-11 — rung 1 landed: the scaffold, inert, on all seven pages.**
Three rungs remain.

**What the scaffold is.** `app/web/views/_pager.py` computes the
ranges; `operator/partials/_preview_pager.html` renders them, twice per
page. The ranges are real — 556 reviewers produce `1–200 / 201–400 /
401–556` — and nothing navigates. A test asserts `offset=` appears
nowhere on the page, which is the assertion rung 2 deletes; that
expiry is the intended lifecycle of a scaffold test, not drift.

**The suppression rule is enforced in the route, not the helper.**
`build_pager` never learns about filters. The route passes `None` while
one is active, reading the same `is_filtered` that summons the count
line — so the two affordances cannot disagree about which mode the page
is in, which the item's Semantics named as the thing to get right and
is easiest to get wrong by letting each side compute its own answer.

**Decisions confirmed at build:**

- **Window of five ranges** before elision (the open question rung 1
  was to settle). Five keeps the strip on one line at the narrowest
  operator width, and the window **re-anchors rather than shrinks** at
  the last page, so walking to the end does not change the strip's
  width under the cursor.
- **First / Last render as ranges, not as the words.** `« 1–200` and
  `39,801–40,000 »` keep one vocabulary on the strip; the guillemets
  carry "jump", the label carries "to where".
- **No First anchor when the window already starts at the top** (and
  the mirror at the end). Two ways to reach the same place is a strip
  that has stopped saying anything.
- **`clamp_offset` clamps rather than 404s** — past the end lands on
  the last page, negative on the first. A link that was valid before
  someone deleted forty rows should not be an error page. Landed in
  rung 1 though nothing reads it yet, because it is the helper's own
  contract and belongs with the arithmetic it guards.
- **Page size stays 200** and is not operator-configurable, as planned.

**Scope beyond the rung:** `spec/ui_elements.md` gained the §10
primitive and a §7 pointer with this rung rather than at item close,
because the surface it describes now exists. The three per-page specs
(`setup_pages`, `assignments`, `operations_pages`) describe behaviour
that is not wired and land with the rungs that wire it.

**2026-09-11 — rung 2 landed: the four Setup pages paged.** Two rungs
remain.

**The shape.** `_shared._setup_row_window` cuts the window for all
four slices — clamping the offset, slicing, and landing an edit target
on its own page — so the four routes share one implementation of a
rule rather than four copies drifting apart. `?offset=` is the only
new parameter, and it needs no filter state riding with it because the
pager never renders on a filtered view.

**The count line changed for all seven pages, not four.** It is one
helper, so rung 2 could not rewrite its contract for the Setup pages
alone. Its new signature takes `pool` (the matching set) and the
route's own `is_filtered`, and drops `total` — the roster denominator
retired with the branch that used it.

**A deviation from this item's Decision, recorded rather than
absorbed.** The plan said the capped-and-unfiltered sentence retires.
It does — but *per page, as that page's pager goes live*, not at a
stroke. Assignments really does still truncate at 200 with an inert
strip, and taking its notice away at rung 2 would have left an
operator with a pager whose links do nothing and no sentence saying
rows were withheld. So `preview_count_line` carries a transitional
`paged` argument, defaulting to the noisier `False`, and the three
un-wired pages pass it. It is documented with its removal point in
the module docstring and pinned by a test; rung 4 deletes it along
with the branch it guards.

**Noun agreement, which the change surfaced rather than caused.** The
old sentence put the noun against the *pool* (`Showing 1 of 2
reviewers.`) where the plural was always right. The new one puts it
against the count, and `Showing 1 reviewers.` is the commonest case
there is — an operator searching for one person. Added a trailing-`s`
rule, with all five real nouns pinned so a future noun it would mangle
fails a test instead of reaching an operator.

**19 existing tests changed, and each was read before it was
changed.** The risk in a rung like this is updating an assertion to
whatever the code now prints. Two were not simple rewordings and are
worth naming:

- `test_unfiltered_cap_is_200` (×3 pages) asserted that a sentence
  said 50 rows were withheld. Rather than deleting the assertion, it
  now fetches `?offset=200` and proves the rows are *there* — the
  claim the item exists to make, which the old test could not make.
- Two `test_assignments_typeahead` assertions expected `None` from a
  filter that matched every row. Under the new contract such a view
  speaks (`Showing 3 assignments.`), so the two searches are now told
  apart by their counts rather than by presence versus absence, which
  is a stronger assertion than the one it replaces.

**The scaffold test expired on schedule**, as rung 1 predicted:
`test_rung_one_links_are_inert` is gone, replaced by its opposite on
the Setup pages and by an unchanged inertness check on the three still
waiting. The file is renamed from `test_preview_pager_scaffold.py`.

**Third time for one trap.** Asserting on a bare class name matches
`base.html`'s inline CSS, which ships on every page. It caught me
again in this rung (`"table-showing-hint" not in body` passed for the
wrong reason). Any class-name assertion in this codebase must target
the rendered element — a property of a single-file inline-CSS app, and
now noted in three consecutive Status blocks.

**Not covered, and said rather than implied.** The per-page *behaviour*
tests run against Reviewers. The other three Setup pages are covered
by the shared helper's own tests and by the parameterized template
assertions; their route wiring is identical code. A per-page
behavioural sweep would need per-page seeding — Relationships needs
pairs — and buys little against one shared implementation.

**2026-09-11 — rung 3 landed: Invitations and Responses paged.** One
rung remains.

**The contract these two lose.** `spec/operations_pages.md` stated
twice that they were uncapped, deliberately — they rendered every
matching row, whatever the number, which is exactly why 19J.4's
benchmark found them the two that hurt. Both statements are struck and
replaced rather than edited away.

**One decision the plan did not make, made here.** A *filtered* view on
these two **stays uncapped**, where the four Setup pages cap theirs at
500. Those two carry the 500 from Segment 15F; these never had a cap,
and inventing one would take rows away from a filtered view that shows
them today — a loss nothing in this item asks for. The pager is
suppressed on a filtered view either way, so the difference is visible
only on a filter matching more than 500 rows. Consistency would have
been the other call and is the weaker one: it buys symmetry by
removing rows.

**What this does not fix.** Paging these two cuts the HTML they emit,
not the work behind it: every row is built before any slice happens,
so the N+1 measured in 19J.4 is untouched. That was true when the item
was planned and is restated here because a reader seeing "the two slow
pages are paged" would reasonably assume otherwise.

**Sort needed no attention here**, unlike the rung still to come. Both
routes already sort the whole row list before filtering, so slicing
after that is a slice of a globally sorted set. Assignments is the
only page where the cookie sort runs over a window rather than the
whole, which is what rung 4's open question is about.

**A test that was weak until it was re-read.** The first Responses
test seeded 4 reviewers × 2 reviewees, so the table held two rows, no
pager rendered, and the test asserted only that a clamped offset did
not error — it would have passed against a route that was never wired.
Re-seeded to 210 reviewees, since Responses is one row per reviewee
and overflows on the other side of the matrix from Invitations.

**2026-09-11 — rung 4 landed: Assignments paged, sort moved into SQL.
All four rungs are done.** The author chose the SQL sort.

**The open question this rung existed to settle** — whether the cookie
sort stays window-local, moves into SQL for the DB-backed keys, or
fetches everything — resolved to the second, and then went further
than the option was written. `pair_tag_*` was the key the option
proposed leaving out, on the reasoning that it resolves through
`pair_context_lookup` rather than a column. It resolves just as well
through an outer join to `relationships` gated on `status = 'active'`,
which is the condition the rule engine already applies. So every sort
key is SQL-backed and no key behaves differently from its neighbours —
which is worth more than the join costs.

**A measured finding that changed the build, and would not have been
found by writing the obvious code.** `apply_cookie_sort` compares text
with Python's `<`: code point, case-significant. A database orders by
*its* collation. Measured on Postgres 16 (2026-09-11), the same seven
names order:

- Python, and Postgres under `C`, and SQLite's default BINARY:
  `Ana Lim | Bravo | Delta | _edge | alpha | ana lim | charlie`
- Postgres under a locale-aware collation:
  `_edge | alpha | ana lim | Ana Lim | Bravo | charlie | Delta`

The first is what this app has always rendered, on every deployment,
because the sort ran in Python. An unqualified `ORDER BY` would have
silently adopted the second wherever the database is locale-aware —
which Azure Postgres commonly is. Hence an explicit `COLLATE "C"`,
applied on Postgres only.

**Three more rules had to be carried across, each a branch a naive
`ORDER BY` inverts.** An empty string is not a value (`NULLIF`);
absent sorts last in *both* directions (`NULLS LAST` on every clause,
not just ascending); ties fall through to a **total** order, without
which two adjacent pages can show the same row or neither.

**Verified against a database shaped like production, not just
against CI's.** A Postgres 16 was started in the sandbox and a
database created with an ICU `en-US` collation, so its default
ordering is locale-aware. The full suite passes there — 3,682 passed,
16 skipped, the whole Alembic chain — as it does on SQLite.

**And the guard was mutation-tested, because a test that cannot fail
certifies nothing.** With the `COLLATE "C"` removed: 2 of the 8
ordering tests fail on the locale-aware database, and **all 8 pass on
SQLite**. The SQLite suite is structurally blind to this class of bug.
Whether `ci-postgres` would catch it depends on that container's
locale, which could not be determined from the sandbox — an
Ubuntu-packaged Postgres initialises as `C.UTF-8`, where the guard is
invisible. Rather than depend on it, `tests/unit/test_pair_sort_sql.py`
compiles the expression against the Postgres dialect and asserts the
collation is emitted: that runs in the ordinary SQLite suite and holds
whatever locale any server has. It was mutation-tested too — 2 of its
3 fail with the guard removed.

**The transitional `paged` argument retired exactly as rung 2 said it
would.** Once this rung landed, no caller passed `paged=False`, so the
branch was dead by construction rather than by anyone remembering to
check. Both went, and `test_no_unfiltered_view_ever_speaks` replaced
the removal-date note.

**The route lost 41 lines.** `_assignment_sort_value`, the Python
resolver, and the `apply_cookie_sort` call all went with the sort
itself. `pair_context_lookup` stays — the template still renders pair
context — but it no longer has a second job.

**2026-09-11 — a verification the author asked for, and the gap it
found.** Asked to double-check that Invitations and Responses really
stop at 200 rather than still rendering everything, I counted the
rendered rows instead of re-reading the code. They do: a 210-row
roster renders **200** on page 1 and 10 on page 2, on both pages.

But the check found that **rung 3's own tests would not have caught the
opposite.** They asserted a pager appears and that page 2 holds the
right rows; none counted page 1. Drop the slice and every row renders
with a pager sitting uselessly above it — `build_pager` keys off the
total, not the window — and every assertion still passed. Counting is
the assertion that fails, so the two tests now count, and a mutation
confirmed it: with the slice removed, both fail.

**What the same measurement says about the gain.** Query count is
**identical** across unfiltered-paged, filtered-all-match and
filtered-one-match — 873 in each at 210 reviewers. Paging cut the HTML
and nothing else, which is what rung 3's entry above already claimed;
this is that claim measured rather than asserted. At this scale even
the HTML saving is small (417 KB against 427), because ~200 KB of the
page is chrome and a row costs about 1.1 KB: the saving is real only
where the roster is large, which is the case the item was for.

**A test that pins a decision rather than a behaviour.** A filtered
view still renders all 210 rows with no pager — rung 3's uncapped
decision — and nothing said so in a test. It does now
(`test_a_filtered_operations_view_renders_every_matching_row`), because
that is the one way an operator can still reach the unbounded render
these pages used to do always, and if it ever reads as a bug the test
is where the decision lives.

**2026-09-11 — closed.** Four rungs, all landed, plus a fifth PR that
counted what the rung-3 tests had only implied. The ladder held as
written; two things it did not anticipate are recorded above — the
transitional `paged` argument that rung 2 needed and rung 4 retired,
and the collation finding that changed how rung 4 had to be built.

Intended versus done, in one line each:

| Rung | Intended | Done |
|---|---|---|
| 1 | Scaffold, inert, all seven pages | As planned |
| 2 | Four Setup pages wired | As planned, **plus** the count-line contract, which is one helper and could not be rewritten for four pages alone |
| 3 | Invitations + Responses, spec edit | As planned, **plus** a decision the plan left open: a filtered view on those two stays uncapped |
| 4 | Assignments + the sort question | As planned; the author chose the SQL sort, and it took every key rather than the DB-backed subset the option described |

**One spec the plan never named, found by the close pass.**
`spec/sort_by_reviewee.md` grouped Assignments with the four rosters as
surfaces whose sort runs through `apply_cookie_sort` — which rung 4
made false, and which nothing in the build pointed at because the rung
touched `_assignments.py` and `_coverage.py`, not that spec. `close_check`
could not catch it either: it asks whether the paths a manifest *names*
were edited, never which paths the edit implied. `spec-writer` found it
at step 3 of the close, which is the step that exists for exactly this.
The bullet is added above rather than waived, per the rule that
undeclared spec impact is the failure mode that section prevents.

`python3 tools/close_check.py 19J.5` passes; its standing note
(`_operations` touched, `spec/validate_page.md` and
`spec/preview_hub.md` not in the manifest) is adjudicated as it was at
rung 2 — neither documents the count line, and `preview_hub.md`'s only
"Showing" is an out-of-scope bullet about submission state.

**A test bug worth recording, because it nearly became a code bug.**
The first suppression test passed `?search=` and saw a pager; the
route's parameter is `q` (`status_filter` is aliased to `status`).
Read as a failure of the suppression rule, the fix would have been in
the route. The lesson is the same one the assertion on `table-pager`
taught two minutes earlier — that string appears in `base.html`'s CSS
on **every** page, so the first version of three tests asserted the
presence of a stylesheet. Both were caught by expecting the test to
fail for a reason I could name.

### PR ladder

A pager is a navigation affordance, so per `CLAUDE.md` → Working
approach the surface lands inert before it moves anything.

1. **Pager scaffold** — the partial, its two render positions on all
   seven pages, real ranges computed from the real counts, every link
   inert. Nothing paginates yet; the point is agreeing the shape.
   **Landed 2026-09-11**, as planned.
2. **The four Setup pages wired** — `offset` param, slice, clamping, the
   count line's revised filtered-only contract, the edit-row landing,
   filter suppression. **Landed 2026-09-11**, as planned, plus the
   helper rewrite it could not avoid (see `### Status`).
3. **Invitations + Responses wired** — the two that change contract from
   uncapped; `spec/operations_pages.md` lands with them. **Landed
   2026-09-11**, as planned, plus the filtered-cap decision the plan
   left open (see `### Status`).
4. **Assignments wired** — SQL `OFFSET`, plus whatever the sort question
   below resolves to. **Landed 2026-09-11**: the author chose the SQL
   sort, and it took every key rather than the DB-backed subset the
   option described (see `### Status`).

### Definition of done

- every row is reachable by the pager on all seven pages: row 1,201 of
  1,240 is visible without searching for it
- a filtered view renders no pager and the revised sentence: `Showing N
  <noun>.` under the cap, `Showing N of M <noun>, X more not shown.` when
  the 500 cap bites
- an unfiltered view renders the pager and **no** count line
- an out-of-range `offset` clamps — no 4xx, no 5xx
- the pager renders identically above and below the table
- `tests/unit/test_preview_count_line.py` covers the two surviving
  states and pins that the unfiltered branches return `None`
- `.venv/bin/pytest` and `.venv/bin/ruff check .` both pass
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19J.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- ~~**Assignments' sort under paging.** Today the cookie sort orders
  only the fetched 200, so page 1 is already a window-local sort;
  paging makes that visible rather than creating it. Three ways out:
  keep it window-local (matches today exactly), push the sort into SQL
  for the DB-backed keys and leave `pair_tag_*` — which resolves
  through `pair_context_lookup` — out of it, or fetch-all-and-slice
  (ruled out at 1,989 ms). **Author decides at rung 4**; the SQL sort
  is the recommendation.~~ **Settled 2026-09-11: SQL sort** (author),
  and `pair_tag_*` went in with the rest.
- **A filtered set larger than 500** still truncates and still carries
  no pager, so rows 501–900 of a filtered view stay unreachable except
  by narrowing the search further. That follows from the suppression
  rule rather than contradicting it, but it is the one place the rule
  costs something. **Author decides** whether to accept it or raise the
  filtered cap.
- **Pager window size** before elision — rung 1.

### Out of scope

- **The N+1 on Invitations and Responses.** Paging those two reduces the
  HTML they emit, not the work behind it: every row is built before any
  slice happens. Recorded with its measurement in 19J.4's Out of scope.
- **Operator-configurable page size** — see Judgment calls.
- **Server-side sort on the four Setup pages.** They sort the whole
  roster before slicing, so paging is already correct there.

### Doc impact

- `spec/setup_pages.md` — the "Preview tables (shared toggle pattern)"
  section: the pager, the filter-suppression rule, and the count line's
  retreat to filtered views only, including its two retired states
  (Item 5).
- `spec/assignments.md` — "The preview-count line (Segment 19I Item 10)":
  the same three changes as they land on the Assignments table (Item 5).
- `spec/operations_pages.md` — the two **uncapped** statements retired;
  Invitations and Responses page on the same terms as the rest (Item 5).
- `spec/ui_elements.md` — §10 Layout primitives gains the pager; §7
  Tables points at it (Item 5).
- `spec/sort_by_reviewee.md` — the "wrapper rows need a resolver"
  bullet: Assignments left that group at rung 4, since its sort is now
  `ORDER BY` rather than `apply_cookie_sort`. **Added at close**, not
  at planning — see `### Status` (Item 5).
- `docs/status.md` — row when the item closes (Item 5).

---

## Item 6 — Session-nav hover standardised to the selected style

### Opportunity

Author, 2026-09-11: *"the hover over style for the setup and operations
tabs are different from that for Session home tab. standardize to —
mouse hover over style = tab selected style"*.

They were different in a way no template diff would show. Every nav
colour came from a theme token except one: the tab strip hovered to a
literal `rgba(255, 255, 255, 0.7)`. Seventy per cent white reads as a
tinted near-white over the light Setup / Operations strips and as a
glaring pale block over the dark ones, because a literal cannot follow
the theme — the strip has a dark-mode token, the hover did not.

### Decision

Every session-nav target paints its **own selected colours** on hover:
`--nav-tab-active-bg` / `--nav-tab-active-fg` for a tab, and the
anchor's selected background for Home (the shared tab token on v1, the
page surface on v2, matching each version's own active rule).

**The active underline is excluded**, confirmed by the author when the
question was put back to them. The `::after` marker stays on `.active`
alone: painted under the cursor it would leave the operator unable to
tell which page they are on while hovering.

**Rejected: a new hover token.** A third colour would have kept the
three targets distinguishable from each other and from selected, which
is precisely the drift being removed — and it would need a dark value
of its own, which is how the current one went wrong.

### Semantics

- **Hover matches selected completely, bar the underline.** Verifiable
  rather than approximate: of the ten rules targeting `.nav-tab.active`,
  one sets background / colour / weight, one sets colour under
  `body.ui-v2`, and the other eight are `::after`.
- **The one property hover does not restate is unreachable.** v1's
  `.nav-tab.active { font-weight: 500 }` loses to
  `body.ui-v2 .nav-tab { font-weight: 600 }` on specificity (0,2,0
  against 0,2,1), and every template rendering a nav tab sets `ui-v2`.
- **A disabled tab never hovers.** The rules carry
  `:not(.disabled):not([aria-disabled="true"])`.

### Judgment calls — decided

- **`:not()` rather than a later override** (2026-09-11) —
  `body.ui-v2 .nav-tab:hover` is (0,3,1) against
  `.nav-tab.disabled:hover`'s (0,3,0), so the disabled guard has been
  losing on every v2 page and "coming soon" tabs have been taking a
  hover background. `:not()` settles it by never matching rather than
  by out-ranking, which cannot be undone by a future rule's position.
- **The dead token goes with it** — `--nav-home-bg-hover` lost its only
  consumer, so it was dropped from both themes and the catalogue under
  `spec/color_tokens.md`'s existing "Dropped as unused" convention.

### Blast radius (measured)

```
$ grep -c "rgba(255, 255, 255, 0.7)" app/web/templates/base.html   # 2 rules
$ grep -rl "session_top_nav.html\|class=\"nav-tab" app/web/templates/operator/*.html \
    | xargs grep -L "body_class.*ui-v2"                            # none — all v2
$ grep -rn -- "--nav-home-bg-hover" app/web/templates/base.html    # 2 (both defs)
```

- **1 stylesheet**, 4 rules (two hover pairs, v1 and v2).
- **Every** nav-tab template is `ui-v2`; the v1 rules are reachable by
  nothing, which is what makes the font-weight gap above harmless.
- **1 token retired**, semantic count 107 → 106.

### Status

**2026-09-11 — landed in one PR, as a chrome fix rather than a
feature.** Two things it turned up that the request did not name:

- **A latent bug.** The disabled-tab guard has been losing to the v2
  hover rule on specificity, so reserved "coming soon" tabs on the
  Previews page have been highlighting on hover. Fixed in passing,
  because leaving it would have meant a disabled tab taking the *full
  selected* treatment once hover matched selected — the change would
  have made an existing bug louder.
- **A token retired itself**, and the semantic-count test caught the
  drift rather than anyone noticing: `spec/color_tokens.md` claimed 107
  where the stylesheet declared 106.

**What the suite cannot reach.** Nothing in pytest renders CSS, so the
colours are dev-slot verification and were added as a row to
`guide/post_azure_todo_checklist.md` item 3 rather than claimed.
`tests/unit/test_session_nav_hover.py` pins what is checkable — the
rules say what they should, and the literal has not crept back — and
was mutation-tested: restoring the old rule fails 2 of its 6.

**`close_check 19J.6` fails C3, and cannot pass.** Both specs it names
were edited in `c8aadf89` — the hover PR, merged earlier the same day —
and the Item 6 heading landed in `c1aec996`, when this write-up was
added. An item's window is dated from its heading, so for an item
**logged after its work shipped** every honoured bullet reads as an
un-honoured one. The check is asking "was this edited since the item
existed?"; the answer is no, and the right answer is "it was edited
before, by the work this item describes".

Recorded rather than worked around. The two paths were **not** waived:
a waiver means *dropped during the build*, and using it for *honoured
early* would make the marker mean two opposite things — which is how a
checker starts lying. Nor were the specs re-touched to move them into
the window; inventing an edit to satisfy an arithmetic is the same
failure with an extra commit. Everything C3 exists to catch is
satisfied and verifiable by SHA: `spec/ui_elements.md` §2 gained the
hover rule and `spec/color_tokens.md` lost `--nav-home-bg-hover`, both
in `c8aadf89`.

**This is a real limitation of the tool, not of this item.** 19J.3
split `close_check` without changing what it asks, and what it asks is
"did a file change inside a window" — a question that has no correct
answer for a retroactive log. Whether that is worth fixing (an
explicit `since:` marker on an item, say) is the author's call, and is
noted here rather than assumed.

**`close_check 19J.6`'s six notes, adjudicated.** All six name a route
module touched in this item's window against a spec not in this item's
manifest — `_assignments`, `_operations`, the four `_setup_*`. None of
them is this item's work: they were touched by **19J.5's four rungs**,
which landed the same day, and the window is dated from the item
heading rather than from the first commit that mentions the item. A
same-day sibling is indistinguishable from a scope leak to a date
comparison. Each of those specs is in **19J.5's** manifest and was
edited with the rung that touched it. Nothing to add here.

### PR ladder

1. **The standardisation**, in `base.html`, with the spec entry and the
   browser-checklist row. **Landed 2026-09-11.**

### Definition of done

- hover on a Setup tab, an Operations tab and the Home anchor paints
  that target's selected colours, in both themes (dev slot)
- the active underline shows on the current tab only
- a "coming soon" tab does not highlight
- `.venv/bin/pytest` and `.venv/bin/ruff check .` both pass
- `### Doc impact` section present and current
- ~~`python3 tools/close_check.py 19J.6` exits 0; any warning
  adjudicated~~ — **cannot pass for a retroactively logged item**; the
  six notes and the C3 failure are adjudicated in `### Status` above,
  with the honouring commit named by SHA
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

None. The one that mattered — whether hover should match selected
*completely* — was put to the author and answered: yes, minus the
underline.

### Out of scope

- **The rest of the pill / chip vocabulary.** Hover is one affordance;
  whether a rounded pill reads as clickable at all is Item 7.
- **v1's unreachable nav rules.** They are dead by the `ui-v2` sweep
  above, not by this change, and deleting them is a separate tidy-up
  with its own blast radius.

### Doc impact

- `spec/ui_elements.md` — §2 Session-scoped chrome gains the
  hover-equals-selected rule, the underline exclusion and the
  disabled-tab guard (Item 6).
- `spec/color_tokens.md` — `--nav-home-bg-hover` removed from the
  catalogue and named in "Dropped as unused"; the headline count moves
  107 → 106 (Item 6).
- `guide/post_azure_todo_checklist.md` — item 3 gains the hover row,
  since no Python test renders CSS (Item 6).
- `docs/status.md` — row when the item closes (Item 6).

---

## Item 7 — Pills rationalization: one vocabulary for two jobs

**Opened as a stub 2026-09-11; planned out the same day** after four
border treatments were mocked up and reviewed with the author. The
mockups are not committed — they were a disposable comparison sheet,
and the decision they produced is below.

### Opportunity

Author, 2026-09-11: *"currently, the UI uses pill style both for pure
display and also for clickable chips. thinking of how to visually
distinguish between the two cases."*

Measured before proposing anything, in
`guide/pill_style_audit.md`: **250 pill/chip elements across 28
templates**, 32 distinct class combinations, split **189 display** to
**61 interactive**.

The finding that makes this worth an item rather than a tidy-up:
**the only thing distinguishing a clickable pill from a label today is
`cursor: pointer` on `.tag-chip`** — invisible until the pointer is
already over it, absent on touch, absent from every screenshot,
including the Guide's. And six class combinations are used both ways,
the worst being `pill pill-count tag-chip` at 44 interactive against 1
display. That one display case is `b3_static_pill`
(`instruments_index.html:3896`), which carries the *identical* class
string to the column-visibility toggle and therefore also inherits the
pointer cursor — the single existing affordance pointing the wrong way.

### Decision

**Reserve the shade, not the hue.** Author, 2026-09-11: *"only the
particular shade of blue is reserved for clickable/draggables; lightly
shades are entirely ok to use for static"*, and earlier the same day:
*"reserve blue with accent outline for chips/pills that allow
interaction (whether by clicking, or in the case of Instruments Band 2,
by clicking and dragging)"*.

Two mechanisms, both narrow:

1. **The reserved pair — `--blue-strong` `#2563eb` (light) and
   `--blue-glow` `#4b8bf5` (dark), reached through `--selected-bg` —
   means "you can act on this"** on a pill or chip surface. A control
   renders transparent-filled with a 2px edge and matching text in the
   reserved shade; `is-selected` stays a solid fill of the same shade.
2. **No static pill carries the reserved pair.** Every other blue stays
   available to statics and none of them moves: `--status-info-bg`
   `#dbeafe`, `--status-info-fg` `#1e40af`, `--role-reviewer-fg`
   `#1d4ed8`.

Resolving every pill-facing token through its `var()` chain, in both
themes, found **exactly one static class on the reserved pair**:
`--lifecycle-validated-fg` is `--blue-strong` / `--blue-glow`, which is
`--selected-bg` to the digit. It retargets to the pair `pill-info`
already uses (`--blue-deeper` `#1e40af` / `--blue-soft` `#93c5fd`) —
no new token, and Validated stays the cool step between Draft (amber)
and Ready (green).

That answers the two questions the stub left open:

1. **Which side moves** — the control, as the stub reasoned. Confirmed,
   and now cheaper than the stub assumed: 54 controls take a CSS rule,
   and the static side is one token swap rather than a recolour.
2. **What carries the signal** — a 2px outline in the reserved shade.

**Rejected alternatives**, all four mocked up before the choice:

- **Hairline border in `--border-subtle`.** Rejected: `#e5e7eb` against
  a `#dbeafe` chip is nearly invisible in light mode. It ships a change
  nobody notices and the question returns.
- **Outline swap in `--border-default`** (neutral grey — the Secondary
  `.btn` role from `spec/ui_elements.md` §6, borrowed at pill scale).
  Rejected: it separates control from label but spends no signal on
  *which* color means action, so a reader still learns a separate rule
  for links — and `--text-link` is already the reserved shade.
- **Shape change**, controls to `border-radius: 4px`. Rejected: splits
  one vocabulary into two and makes `.tag-chip` a misnomer, to carry a
  signal the outline already carries.
- **Moving all 69 pale-blue statics off the hue.** Rejected by the
  author: the reservation is on the shade, and a 20-template recolor
  buys nothing the shade rule does not.

### Semantics

Per mechanism, at the boundaries:

- **Visible but not actionable.** `.tag-chip.is-disabled` (Band 1 link
  chips, 2 sites in `instruments_index.html`) sets `cursor: default`
  and is genuinely inert. It **suppresses the outline** — otherwise the
  reserved shade would claim "actionable" about an element whose own
  CSS says it is not.
- **A static pill wearing a control's class string.** `b3_static_pill`
  renders `pill pill-count tag-chip is-selected` with no interactive
  attribute. The class string is the defect, not an exemption: it is
  fixed, and it is fixed first (rung 1).
- **Selected state.** `is-selected` keeps its solid `--selected-bg`
  fill and gains a border in the same color, so the box does not change
  size when the chip is toggled.
- **Every pill gets `border: 1px solid transparent` at the base.**
  Adding a visible border to controls alone would grow each chip by 2px
  and reflow every table where a status label sits beside a toggle.
- **2px comes from `inset box-shadow`, not `border-width`.** Same
  reason: the box geometry has to stay identical.
- **Hover is unchanged.** The outline is a resting-state signal;
  `cursor: pointer` stays, and nothing new fires on hover.
- **`--text-link` is the reserved shade and stays that way.** Links are
  actionable, so the rule formalizes existing practice rather than
  carving an exception out of it. The spec has to say so, or it reads
  as an oversight.
- **Scope is pill and chip surfaces.** `--focus-ring`,
  `--btn-primary-bg` and `--card-active-border` also resolve to the
  pair and are all actionable or focus-related, so they are consistent
  with the rule without being touched. `--status-info-border` resolves
  to it on a *static* info panel and is the one known inconsistency
  outside pills — recorded in Open questions, not fixed here, because
  widening the scope turns a three-rung item into a whole-app color
  audit.
- **The instruments audience override wins on specificity, by design
  and for now.** `instruments_index.html:125-126` paints
  `body.ui-v2 [data-new-model-audience="reviewees"|"observers"]
  .tag-chip:not(.is-selected)` with a filled `--selected-bg` at opacity
  0.4 — (0,3,1) against the proposed rule's (0,2,1). Those chips are
  clickable, so the reservation holds; the *treatment* does not match.
  Left alone in this item (see Open questions).

### Judgment calls — decided

- **2026-09-11 — the guard resolves tokens, it does not assert class
  names.** A bare class-name assertion matches `base.html`'s own inline
  CSS, which ships on every page; 19J.5 hit that three times. The test
  parses the token blocks and follows each `var()` chain to a hex.
- **2026-09-11 — Validated's replacement is a pair already in use**
  rather than a new hue. Zero new tokens, and the lifecycle ramp still
  reads amber → cool → green.
- **2026-09-11 — `b3_static_pill` lands before the outline, not with
  it.** Under the new rule it would render as an outlined control that
  does nothing, so the bug gets louder; fixing it first also makes rung
  1 shippable on its own merit, today, as a pointer-cursor defect.
- **2026-09-11 — the reservation is scoped to pill and chip surfaces.**
  Stated in the spec as a scope, not left implicit, so the next reader
  knows `--status-info-border` was seen and deferred rather than missed.

### Blast radius (measured)

Taken 2026-09-11 at `ebe00540`.

| What | Count | Command |
|---|---:|---|
| Templates rendering `.tag-chip` | 10 | `grep -arl "tag-chip" app/web/templates --include=*.html \| grep -v base.html \| wc -l` |
| Band 2 pill attribute sites | 26 | `grep -ac "data-new-model-band2-pill" app/web/templates/operator/instruments_index.html` |
| `b3_static_pill` — macro + call sites | 1 + 5 | `grep -an "b3_static_pill(" app/web/templates/operator/instruments_index.html` |
| `tag-chip is-disabled` sites | 2 | `grep -arc "tag-chip is-disabled" app/web/templates/operator/instruments_index.html` |
| Test files mentioning pill or chip | 93 | `grep -rln "pill\\|tag-chip" tests/ \| wc -l` |
| Static pill classes on the reserved pair | 1 | token resolution over `base.html`, both theme blocks, following every `var()` |

**A correction to the audit.** `guide/pill_style_audit.md` counts
`b3_static_pill` as **1** display use of `pill pill-count tag-chip`.
It renders **5 times** — the audit's scan reads `class="..."` strings,
so it saw the macro definition once and could not see the five
`{{ b3_static_pill(...) }}` call sites. The audit's headline split
(250 / 189 / 61) is unaffected in shape; the one both-ways combination
it flags is worse than reported, not better.

**Specs that carry the affected tokens:** `spec/color_tokens.md`
(lifecycle-badge table, selection table, and the "Deliberate couplings"
section) and `spec/ui_elements.md` §9 "Badges / pills".

**Guide screencaps that go stale:** `assignments-page.png` and
`-dark.png` (`guide.html:383`, the nine-chip column-toggle row) and
`instrument-card-fields-and-visibility.png` and `-dark.png`
(`guide.html:303`, the Band 2 pill row). Retaking them is dev-slot
work, not sandbox work.

### PR ladder

Each rung carries its own spec edit; there is no trailing docs rung.

1. **`b3_static_pill` off the control class string.** The macro drops
   `tag-chip is-selected` and carries a static class only. 5 render
   sites, one file. *Must not touch* `base.html` — this rung is a defect
   fix that stands on its own whether or not the rest lands.
2. **Validated off the reserved shade, plus the guard.**
   `--lifecycle-validated-fg` retargets to `--blue-deeper` /
   `--blue-soft` in both theme blocks;
   `tests/unit/test_reserved_shade.py` resolves every pill-facing token
   and asserts the reserved pair appears only on control rules. The two
   land together because the test is red before the swap.
   `spec/color_tokens.md`'s lifecycle-badge row updates with it.
   *Must not touch* templates.
3. **The control outline.** The `base.html` rule for `.tag-chip` and
   `[data-new-model-band2-pill]`, the transparent baseline border on
   `.pill`, and the `is-disabled` suppression; integration tests
   asserting the rendered chip on Assignments and the rendered Band 2
   pill carry it (targeting the element, not the class name).
   `spec/ui_elements.md` §9 and `spec/color_tokens.md` "Deliberate
   couplings" document the rule; `guide/post_azure_todo_checklist.md`
   gains the screencap-retake row. *Must not* recolor any static pill.

### Definition of done

- `b3_static_pill` renders no `tag-chip` and no `is-selected`, at all
  5 call sites.
- `--lifecycle-validated-fg` resolves to `#1e40af` (light) and
  `#93c5fd` (dark).
- `tests/unit/test_reserved_shade.py` passes, and **fails** when
  `--lifecycle-validated-fg` is reverted — mutation-checked, not
  assumed.
- Rendered `.tag-chip` and `[data-new-model-band2-pill]` elements carry
  the outline; a rendered `.tag-chip.is-disabled` does not.
- No static pill's color changes except Validated's foreground.
- `spec/ui_elements.md` §9 describes the control treatment and names
  `--text-link` as the same rule, not an exception.
- `spec/color_tokens.md` "Deliberate couplings" states the reservation
  and its scope (pill and chip surfaces).
- `guide/post_azure_todo_checklist.md` carries the screencap-retake row
  naming the four files.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent
  container before each push.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19J.7` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- **Does the reservation extend past pill and chip surfaces?**
  `--status-info-border` resolves to the reserved pair on a static info
  panel. Scoped out of this item deliberately. **Author decides**
  whether it becomes 19J.8, a deferred entry, or nothing.
- **The instruments audience override.** `instruments_index.html:125-126`
  leaves two chip rows filled rather than outlined, at 0.4 opacity.
  They are clickable so the rule is not violated, but the treatment is
  inconsistent. **Author decides** whether that is a visibility-grid
  item rather than a pill one.
- **Band 1 `is-unset` chips.** They are clickable, so the rule says they
  take the outline — but they would then carry an amber fill with a blue
  edge, which no other chip does. **Needs a look on the dev slot** before
  rung 3 is called done; if it reads badly, the fallback is to suppress
  the outline the way `is-disabled` does and record why.

### Out of scope

- **Accessibility is not the problem here.** The interactive pills
  already carry `role="button"`, `tabindex="0"` and `aria-pressed`, so
  a screen reader and a keyboard distinguish what the eye cannot.
  Whatever is chosen must not become a reason to drop those — and the
  outline does not, it finally says the same thing to the eye.
- **Status colours are not entangled.** The semantic modifiers
  (`pill-info` / `-success` / `-warning` / `-error` / `-super`) are
  display-only in all 50 of their uses, so a control treatment need not
  negotiate with them.
- **The 69 static pills on other blues.** `#dbeafe`, `#1e40af` and
  `#1d4ed8` are not the reserved pair; they stay, by the author's
  decision above.
- **The 32-class-combination consolidation.** The audit's larger
  finding — six combinations used both ways — is a naming problem, not
  a color one. Not addressed here; recorded in
  `guide/pill_style_audit.md` and available to a later item.
- **Retaking the Guide screencaps.** Dev-slot work after deploy, per
  `CLAUDE.md` → Where work runs. Tracked on the post-Azure checklist,
  not done in the sandbox.

### Doc impact

- `guide/pill_style_audit.md` — the measured audit this item starts
  from (Item 7).
- `spec/color_tokens.md` — "Deliberate couplings" gains the reserved-pair
  rule and its scope; the lifecycle-badge row retargets
  `--lifecycle-validated-fg` (Item 7).
- `spec/ui_elements.md` — §9 "Badges / pills" documents the control
  treatment, the `is-disabled` suppression, and `--text-link` as the
  same rule (Item 7).
- `guide/post_azure_todo_checklist.md` — screencap-retake row naming
  the four affected files (Item 7).
- `docs/status.md` — row when the item closes (Item 7).
