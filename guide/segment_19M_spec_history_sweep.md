# Segment 19M — a general sweep: history out of the specs

**Opened** 2026-09-13, at the author's instruction, after the
`spec/ui_elements.md` sweep (`guide/sweep_2026-09-13_ui_elements.md`)
established the rule on one file and then had to be reversed to obey it.

> *"Send agents out to sweep all spec docs to do the same. Express
> constraints as such, with brief reasoning if needed. But that's not
> strictly speaking 'history', even though the reasoning was confirmed
> through something in the history."* — the author, 2026-09-13

**Items close independently.** Each item is one batch of `spec/` files and
lands as its own slice. The segment stays open until every batch has
closed, and is explicitly shaped to admit further items — a batch may
produce findings that want their own.

## Opportunity

A spec says what *is*. Across `spec/` the specs also say when things
landed, what they used to be called, which proposal lost, and what a
previous draft got wrong. Measured at `b42e4297` over the **39 live files
/ 22,493 lines**:

| kind of drift | measure | command |
|---|---|---|
| dated references | **273 lines** carry a `YYYY-MM-DD` | `grep -c '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' spec/*.md` |
| retirement / provenance language | **255 lines** | `grep -ci 'retired\|no longer exists\|used to \|superseded\|was renamed\|shipped in\|Corrected 20' spec/*.md` |
| plan apparatus | **86 blocks, all in `ui_elements.md`** | `grep -c '\*Current:\*\|\*Migration delta:\*\|\*PR:\*\|\*Canonical:\*' spec/*.md` |

> **Two of these three figures were published wrong and are corrected
> here (2026-09-13).** The table first read **252** dated lines and
> **239** retirement phrases; re-measured against the git objects at
> `b42e4297` rather than by summing a printed per-file table, they are
> **273** and **255**. The error was arithmetic on my part, not a change
> in the corpus. The *argument* the table supports — three distinct kinds
> of drift, only the third confined to one file — is unaffected, and the
> apparatus count of **86** reconciles exactly.
>
> Corrected in every place the numbers were spent, not only where the
> error was found: this table, the blast-radius commands below,
> `guide/todo_master.md`'s segment row, and the `docs/status.md` row —
> because *recording that a number is unreliable does not stop you
> spending it*, which this repo has already learned once
> (`docs/status.md`, 2026-09-12).

Three separate problems, and only the third is confined to one file:

1. **Mode.** `ui_elements.md` alone still carries the `*Current:*` /
   `*Canonical:*` / `*Migration delta:*` / `*PR:*` shape of the plan it
   was before 2026-05-11. *A `*Current:*` block is a snapshot and nothing
   renews it.* Six of ~23 entries were converted on 2026-09-13; the rest
   are Item 1's.
2. **Narrative.** Every other file drifts as dated prose: *"Corrected
   2026-09-08"*, *"retired 2026-05-05 (`62a85fee`)"*, *"the Delete buttons
   moved there on 2026-05-22 and came back when 18R Item 4 retired that
   page"*. A reader wanting the contract reads the provenance first.
3. **Stale identifiers — a second class, found only because of the
   first.** `ui_elements.md` names five colour tokens that have **0
   definitions** in `base.html` (`accent-blue`, `accent-green`,
   `accent-amber`, `accent-red`, `text-primary`), on **~28 lines**, while
   `spec/color_tokens.md`'s opening paragraph records that vocabulary as
   *"fully retired"*. One live spec naming a vocabulary another live spec
   retires. This is drift in *what a thing is called*, not in *when it
   happened*, and it is Item 1's to measure across the token family.

**The evidence that this is not cosmetic** is the ui_elements sweep's own
record: across two passes it made **five false claims** about the code
(three in the sweep, two in the reversal), and every one was possible
because the entry being edited was a narrative about the past rather than
a description a reader could check. *Prose about what happened cannot go
stale visibly; prose about what is can.*

## Decision

**Sort every history-shaped passage into three buckets, and act
differently on each.** This is the rule the author supplied, and its
second clause is the one that makes the sweep safe:

- **Provenance → out.** When something landed, its PR or segment number,
  its commit SHA, what it was called before, which proposal lost, what a
  previous draft got wrong. The record lives in `docs/status.md`, the
  segment plans, and the sweep records.
- **Constraint → stays, expressed forward.** Anything that tells a future
  author *this must not change* keeps its place and gets a **brief**
  reason. **A reason established historically is not history.** So:
  > *"19L.1 shipped a fill too (`--row-selected-bg`); it resolved to
  > `--status-info-bg`'s own primitives, which back both `.pill-count`
  > and `.pill-info` from one rule, so every pill on a selected row went
  > invisible."*

  becomes

  > *"**No fill.** A row fill resolves to the same primitives that back
  > `.pill-count` and `.pill-info`, so it erases every pill the row
  > carries; the six pale pill fills sit between relative luminance 0.810
  > and 0.914 against a 1.000 card, leaving no clearance above the band."*

  Same constraint, same reason, no provenance — and it now reads as a
  property of the design rather than an anecdote about a PR.
- **Absent subject → deleted.** An entry describing a class, template or
  hack with **0 occurrences** in `app/` is not a stale description, it is
  an absent subject. Delete the entry; record the retirement in the
  sweep record.

**Rejected — a mechanical date-stripping pass.** `grep` can find a date;
it cannot tell a changelog row from the sentence that stops the next
author re-adding a fill. The ui_elements sweep's own dead-identifier pass
produced twelve candidates of which **four were correctly-recorded
history that would have made the file worse if "fixed"**. Every passage
has to be read for what it *does*.

**Rejected — one agent over 39 files.** The batches below are drawn so
that files which cross-reference each other are read by the same agent;
a single agent over 22,493 lines would read none of them well.

**Rejected — fixing the stale-identifier class everywhere in this
segment.** Item 1 measures and fixes it in the token family, where it was
found and where it is dense. Elsewhere agents **report** occurrences and
correct one only when already rewriting that line — the same tier rule
`CLAUDE.md` uses for spelling, and for the same reason: a sweep that
grows a second subject finishes neither.

## Semantics

Per mechanism, at the boundaries:

- **A dated correction note** (`*Corrected 2026-09-08: this read that …*`)
  is provenance *wrapping* a constraint. The correction's **conclusion**
  is the content; the account of the wrong version goes. Where the note
  exists only to say "an earlier draft was wrong and here is the right
  answer", only the right answer survives.
- **A retired-class record** (`.table-pager` — *"Retired 2026-09-11
  (19J.9)"*) is an absent subject **unless** its presence stops
  reintroduction. Default: delete and record. Keep only where the name is
  still reachable — a token still defined in `base.html`, a class a
  template still emits.
- **An `added <date>` column** in a primitives table is a changelog.
  The column goes; the rows stay.
- **A figure a test reads** (a rail width, a contrast ratio, a padding
  pair) is a **constraint** whatever tense surrounds it. It never goes.
- **A cross-reference into a passage this sweep deletes** must be
  repointed or dropped in the same slice, or the repo's
  path-reference guard fails — and a dangling pointer to a section that
  no longer exists is worse than the history was.
- **Empty batch.** A file with no history-shaped passage is reported as
  read-with-no-finding, not omitted. *Silence has to mean something.*

## Judgment calls — decided

- **Batches drawn by cross-reference density, not by line count.**
  2026-09-13. The token family is four files and 2,616 lines; the data-IO
  batch is nine files and ~4,700. Even batches would have split
  `ui_elements.md` from `color_tokens.md`, which is the one pair whose
  inconsistency this segment has already measured.
- **Agents do not commit and do not push.** 2026-09-13. Six agents
  committing into one checkout on one designated branch is a merge
  problem invented for no gain; they edit a disjoint file set and report,
  and the batch is committed here after the suite runs.
- **Agents run the doc guards, not the full suite.** 2026-09-13. Six
  concurrent full runs contend and each would read the others'
  half-written files. The full suite runs once per batch, here, before
  the commit.
- **`ui_elements.md` stays in the segment despite being partly done.**
  2026-09-13. Six entries converted, ~17 not, and the file holds the
  entire plan-apparatus class. Finishing it elsewhere would split one
  file's conversion across two records.
- **Uncertain passages are kept, not deleted.** 2026-09-13. An agent that
  cannot tell whether prose is load-bearing keeps it and says so. A
  wrongly-kept sentence costs a reader a few seconds; a wrongly-deleted
  constraint costs the next author a regression — the asymmetry is not
  close.

## Blast radius (measured)

At `b42e4297`, 2026-09-13:

```
ls spec/*.md | wc -l                     # 39 live spec documents
cat spec/*.md | wc -l                    # 22,493 lines
grep -c '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' spec/*.md   # 273 dated lines
grep -c '\*Current:\*\|\*Migration delta:\*\|\*PR:\*\|\*Canonical:\*' spec/*.md  # 86, all ui_elements.md
grep -rln 'spec/' tests/ --include=*.py  # tests that read a spec as data
```

**Specs read as data by a test** — these carry figures that are
constraints regardless of tense, and none may lose one:

- `tests/unit/test_doc_conventions.py` — `spec/ui_elements.md` §6 button
  roles; the lifecycle display-label mapping; `CLAUDE.md` / `AGENTS.md`
  byte-identity.
- `tests/integration/test_cascade_ties.py` — two values `ui_elements.md`
  §6 states **in prose**.
- `tests/unit/test_lobby_row_selection.py` — reads the shipped rail width
  from `base.html` and requires `ui_elements.md` to state the same figure.
- `tests/integration/test_setup_delete_scaffold.py` — the Destructive
  role per §6.
- `tests/unit/test_spec_coverage.py` — every routing module has a
  governing spec, so **no spec file may be deleted**.
- `tests/unit/test_guide_indexes.py` + the path-reference guard — every
  path named in live prose must resolve, and every new `guide/` file
  needs an index row.

**Code changed: 0.** This segment edits `spec/`, plus `guide/` records and
`docs/status.md` rows.

## PR ladder

One rung per item; six rungs, landing in the order below. Each rung
touches **only** its own file list and leaves every other spec alone.

1. **Item 1 — visual / token family** (4 files, 2,616 lines):
   `ui_elements.md`, `visual_style_rrw.md`, `visual_style_general.md`,
   `color_tokens.md`. Finishes `ui_elements.md`'s plan-apparatus
   conversion and settles the retired-token vocabulary across the family.
   **Lands first** because it is the one batch with a measured defect
   already in hand, and because the guards above concentrate here.
2. **Item 2 — operator chrome and page surfaces** (8):
   `operator_ui_concept.md`, `operator_button_audit.md`,
   `sessions_overview.md`, `session_home.md`, `setup_pages.md`,
   `operations_pages.md`, `workflow_card.md`, `quick_setup_card_spec.md`.
3. **Item 3 — core contracts and cross-cutting** (7):
   `rrw_functional_spec.md`, `architecture.md`, `domain_assumptions.md`,
   `README.md`, `lifecycle.md`, `permissions.md`,
   `audience_and_identity_model.md`.
4. **Item 4 — domain engine** (6): `instruments.md`, `assignments.md`,
   `sort_by_reviewee.md`, `reconciling_regeneration.md`,
   `visibility_policy.md`, `validate_page.md`.
5. **Item 5 — participant and reviewer surfaces** (5):
   `reviewer-surface.md`, `participant_model.md`,
   `role_landing_and_visibility.md`, `role_navigator.md`,
   `preview_hub.md`.
6. **Item 6 — data IO and infrastructure** (9): `csv_contracts.md`,
   `extract_data.md`, `roundtrip_coverage.md`, `rehydrate.md`,
   `settings_inventory.md`, `email_template_editor.md`,
   `email_infra_options.md`, `timezone_display.md`, `blob_storage.md`.

4 + 8 + 7 + 6 + 5 + 9 = **39**, the full live corpus, each file in exactly
one rung.

## Definition of done

Per item:

- Every file in the batch is either edited or reported as
  read-with-no-finding. **No file is silently skipped.**
- Every removed passage is provenance, an absent subject, or a constraint
  re-expressed forward — and the record says which, per file.
- No constraint lost: every re-expressed passage keeps its reason, and
  every figure a test reads is still stated.
- No dangling cross-reference: a pointer into deleted text is repointed
  or dropped in the same slice.
- Stale-identifier occurrences reported per file; corrected only on lines
  already being rewritten.
- `.venv/bin/pytest` green and `ruff check .` clean, run here before the
  commit.
- The batch's record is appended to
  `guide/sweep_2026-09-13_spec_history.md`, including the
  uncertain-and-kept list and every claim the agent could not verify.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19M.<n>` exits 0; any warning adjudicated
- `spec-writer` run against the batch; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

For the segment: every item closed, then the plan moves to
`guide/archive/` with its `guide/archive/README.md` row.

## Open questions

1. **Does the sweep record belong in one file or six?** Started as one
   (`guide/sweep_2026-09-13_spec_history.md`) with a section per batch,
   on the reasoning that the three-bucket rule is one subject and a
   reader comparing batches should not open six files. Revisit if the
   file passes ~1,000 lines. *Decides: whoever lands Item 3.*
2. **Is this a corpus sweep for cadence purposes?** It reads all 39 live
   `spec/` files but **no** `docs/` file and no root document, so it is
   not the whole-folder sweep the 8-week / 500-merge clock measures.
   Marked `partial` until that is settled. *Decides: the author, or
   whoever next runs `close_check --stale`.*
3. **Does the stale-identifier class want its own item?** Item 1
   measures it in the token family; the other five batches only report.
   If the reports total more than ~40 lines outside the token family it
   is an item, not a footnote. *Decides: the count, after Item 6.*

## Out of scope

- **`docs/`, root documents, and `guide/`.** History *belongs* in
  `docs/status.md`, the segment plans and the sweep records — that is
  where this sweep sends it. Sweeping them would be the opposite change.
- **`spec/archive/`.** Archived specs are records; history is their
  content.
- **Deleting a spec file.** `tests/unit/test_spec_coverage.py` requires a
  governing spec per routing module, and consolidation is a different
  decision from this one.
- **Renaming identifiers, filenames or DB columns for any reason.**
  `CLAUDE.md`: a name is a name.
- **Fixing spec-vs-code drift the sweep happens to find.** Report it;
  fixing it is ordinary follow-on work, as the 2026-09-05 sweep's eight
  findings were. *A sweep recommends.*

---

## Item 1 — the visual / token family

### Opportunity

Finishes `ui_elements.md`'s plan-apparatus conversion (~17 entries remain of ~23) and settles the retired-token vocabulary across the family, where it was measured: five `accent-*` / `text-primary` names with **0** definitions in `base.html`, on ~28 lines, against `color_tokens.md` recording that vocabulary as *"fully retired"*. **Lands first** — it is the batch with a defect already in hand, and every spec-reading guard concentrates here.

### Scope — the batch's file list

- `spec/ui_elements.md`
- `spec/visual_style_rrw.md`
- `spec/visual_style_general.md`
- `spec/color_tokens.md`

**4 files.** No file outside this list is edited by this item, and every file in it is either edited or recorded as read-with-no-finding.

### Decision

The segment's three-bucket rule, unchanged: provenance out, constraints re-expressed forward with a brief reason, absent subjects deleted. See `## Decision` above — it is not restated per item, because an item restating a shared rule is how the two copies drift apart.


### Status — 2026-09-13 (batch landed; item open pending adjudication)

**Intended vs done.** The batch landed as one rung, as the ladder said. What
the plan did **not** anticipate is that the brief itself was wrong: every
batch was told to write *"plain present-tense description of what ships"*,
which is `docs/`'s function, not `spec/`'s. The author's mid-sweep pointer
to `rrw_sdd_in_practice.md` §4 corrected it, and §0a of the record carries
the correction in full.

*Decisions confirmed at build:* 2026-09-13.

- **`visual_style_general.md` swept only one line.** Its 61 `accent-*` names
  were read and deliberately left: the file's own preamble states forward
  that they are the portable design system's role names and points at
  `color_tokens.md` as authoritative, so renaming them would break its
  stated portability and contradict its own guard paragraph. **This is a
  scope reduction the plan's Item 1 text did not predict** — it had named
  the retired-token fix as one of two specific jobs across all four files.
- **The plan expected the apparatus conversion to be partial.** It went to
  **0**, which is more than the item promised.
- **Two "kept as uncertain" entries are guard-shaped**, and that category
  was not in the plan: the retired-pager-strip paragraph and §10's
  `.session-row-selected` row are both retained *because a test depends on
  them*, not because their subject is live.

### Doc impact

- `spec/ui_elements.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 1).
- `spec/visual_style_rrw.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 1).
- `spec/visual_style_general.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 1).
- `spec/color_tokens.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 1).
- `guide/sweep_2026-09-13_spec_history.md` — the batch's record: per-file dispositions, the uncertain-and-kept list, and every claim not verified against the code (Item 1).
- `docs/status.md` — row when the item closes (Item 1).


## Item 2 — operator chrome and page surfaces

### Opportunity

The densest narrative batch: `operator_button_audit.md` carries 24 dated lines and 27 retirement phrases over 790 lines, and `operator_ui_concept.md` 15 and 24 over 500 — both are audit documents by origin, which is why they read as logs.

### Scope — the batch's file list

- `spec/operator_ui_concept.md`
- `spec/operator_button_audit.md`
- `spec/sessions_overview.md`
- `spec/session_home.md`
- `spec/setup_pages.md`
- `spec/operations_pages.md`
- `spec/workflow_card.md`
- `spec/quick_setup_card_spec.md`

**8 files.** No file outside this list is edited by this item, and every file in it is either edited or recorded as read-with-no-finding.

### Decision

The segment's three-bucket rule, unchanged: provenance out, constraints re-expressed forward with a brief reason, absent subjects deleted. See `## Decision` above — it is not restated per item, because an item restating a shared rule is how the two copies drift apart.


### Status — 2026-09-13 (batch landed; item open pending adjudication)

**Intended vs done.** The batch landed as one rung, as the ladder said. What
the plan did **not** anticipate is that the brief itself was wrong: every
batch was told to write *"plain present-tense description of what ships"*,
which is `docs/`'s function, not `spec/`'s. The author's mid-sweep pointer
to `rrw_sdd_in_practice.md` §4 corrected it, and §0a of the record carries
the correction in full.

*Decisions confirmed at build:* 2026-09-13.

- **The batch wrote, then removed, a header inverting §4's authority.** It
  had told a reader of `operator_button_audit.md` to *"treat a contradicting
  row as the row being wrong"*. Recorded because it is the clearest instance
  of the pre-correction brief producing a wrong result.
- **Fifteen spec-vs-spec contradictions were resolved**, which the plan did
  not scope — it anticipated provenance removal. Most were a file
  contradicting itself; the rest were settled by `spec/README.md`'s
  precedence rule rather than by preference.

### Doc impact

- `spec/operator_ui_concept.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `spec/operator_button_audit.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `spec/sessions_overview.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `spec/session_home.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `spec/setup_pages.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `spec/operations_pages.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `spec/workflow_card.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `spec/quick_setup_card_spec.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 2).
- `guide/sweep_2026-09-13_spec_history.md` — the batch's record: per-file dispositions, the uncertain-and-kept list, and every claim not verified against the code (Item 2).
- `docs/status.md` — row when the item closes (Item 2).


## Item 3 — core contracts and cross-cutting

### Opportunity

`rrw_functional_spec.md` is the canonical entry point for new readers and was swept against the code on 2026-09-10 (19J.1), so its *facts* are the freshest in the corpus and its 23 dated lines are the purest case of the thing this segment removes — provenance in a document a newcomer reads first.

### Scope — the batch's file list

- `spec/rrw_functional_spec.md`
- `spec/architecture.md`
- `spec/domain_assumptions.md`
- `spec/README.md`
- `spec/lifecycle.md`
- `spec/permissions.md`
- `spec/audience_and_identity_model.md`

**7 files.** No file outside this list is edited by this item, and every file in it is either edited or recorded as read-with-no-finding.

### Decision

The segment's three-bucket rule, unchanged: provenance out, constraints re-expressed forward with a brief reason, absent subjects deleted. See `## Decision` above — it is not restated per item, because an item restating a shared rule is how the two copies drift apart.


### Status — 2026-09-13 (batch landed; item open pending adjudication)

**Intended vs done.** The batch landed as one rung, as the ladder said. What
the plan did **not** anticipate is that the brief itself was wrong: every
batch was told to write *"plain present-tense description of what ships"*,
which is `docs/`'s function, not `spec/`'s. The author's mid-sweep pointer
to `rrw_sdd_in_practice.md` §4 corrected it, and §0a of the record carries
the correction in full.

*Decisions confirmed at build:* 2026-09-13.

- **This batch closed before the correction reached it**, so it ran under the
  pre-correction brief. Its record marks the two places the old framing
  shows rather than presenting them as settled.
- **An open decision was created rather than closed**: the batch removed
  `rrw_functional_spec.md`'s currency line in favour of a sweep-record
  pointer. 19J.1 set that precedent on `spec/README.md`; §6.2 presents the
  currency date as a property of the functional altitude. **Both knock-ons
  — §6.2's "4 of 36" figure and its line-38 quotation — are in the record,
  unedited**, because they are the author's measured analysis.

### Doc impact

- `spec/rrw_functional_spec.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 3).
- `spec/architecture.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 3).
- `spec/domain_assumptions.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 3).
- `spec/README.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 3).
- `spec/lifecycle.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 3).
- `spec/permissions.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 3).
- `spec/audience_and_identity_model.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 3).
- `guide/sweep_2026-09-13_spec_history.md` — the batch's record: per-file dispositions, the uncertain-and-kept list, and every claim not verified against the code (Item 3).
- `docs/status.md` — row when the item closes (Item 3).


## Item 4 — the domain engine

### Opportunity

Rule-shaped specs, so the constraint bucket dominates and the forward-expression rule does most of the work here. `visibility_policy.md`'s 3 x 2 grid and `assignments.md`'s engine semantics are constraints whatever tense surrounds them.

### Scope — the batch's file list

- `spec/instruments.md`
- `spec/assignments.md`
- `spec/sort_by_reviewee.md`
- `spec/reconciling_regeneration.md`
- `spec/visibility_policy.md`
- `spec/validate_page.md`

**6 files.** No file outside this list is edited by this item, and every file in it is either edited or recorded as read-with-no-finding.

### Decision

The segment's three-bucket rule, unchanged: provenance out, constraints re-expressed forward with a brief reason, absent subjects deleted. See `## Decision` above — it is not restated per item, because an item restating a shared rule is how the two copies drift apart.


### Status — 2026-09-13 (batch landed; item open pending adjudication)

**Intended vs done.** The batch landed as one rung, as the ladder said. What
the plan did **not** anticipate is that the brief itself was wrong: every
batch was told to write *"plain present-tense description of what ships"*,
which is `docs/`'s function, not `spec/`'s. The author's mid-sweep pointer
to `rrw_sdd_in_practice.md` §4 corrected it, and §0a of the record carries
the correction in full.

*Decisions confirmed at build:* 2026-09-13.

- **First batch under the correction, and it behaved as §0a predicted:** ten
  divergence findings, **two** absent-subject deletions across six files,
  and **zero** in four of them. The plan's Item 4 text had said to expect
  "fewer deletions and more rewrites"; the outcome was fewer of both and
  more *reports*.
- **It reverted one of its own edits** — it had written the code's aggregate
  `ReconcileImpact` shape into two specs and restored the per-instrument
  contract.

### Doc impact

- `spec/instruments.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 4).
- `spec/assignments.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 4).
- `spec/sort_by_reviewee.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 4).
- `spec/reconciling_regeneration.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 4).
- `spec/visibility_policy.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 4).
- `spec/validate_page.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 4).
- `guide/sweep_2026-09-13_spec_history.md` — the batch's record: per-file dispositions, the uncertain-and-kept list, and every claim not verified against the code (Item 4).
- `docs/status.md` — row when the item closes (Item 4).


## Item 5 — participant and reviewer surfaces

### Opportunity

`reviewer-surface.md` is 1,388 lines with 13 dated references and a *what lands later* section — the one place in the corpus where future-tense content is legitimate, so the batch has to separate *deferred* from *historical* rather than treating both as drift.

### Scope — the batch's file list

- `spec/reviewer-surface.md`
- `spec/participant_model.md`
- `spec/role_landing_and_visibility.md`
- `spec/role_navigator.md`
- `spec/preview_hub.md`

**5 files.** No file outside this list is edited by this item, and every file in it is either edited or recorded as read-with-no-finding.

### Decision

The segment's three-bucket rule, unchanged: provenance out, constraints re-expressed forward with a brief reason, absent subjects deleted. See `## Decision` above — it is not restated per item, because an item restating a shared rule is how the two copies drift apart.


### Status — 2026-09-13 (batch landed; item open pending adjudication)

**Intended vs done.** The batch landed as one rung, as the ladder said. What
the plan did **not** anticipate is that the brief itself was wrong: every
batch was told to write *"plain present-tense description of what ships"*,
which is `docs/`'s function, not `spec/`'s. The author's mid-sweep pointer
to `rrw_sdd_in_practice.md` §4 corrected it, and §0a of the record carries
the correction in full.

*Decisions confirmed at build:* 2026-09-13.

- **Six rewrites reverted** once the correction arrived — the largest number
  of any batch, including one where it had deleted a Next Action button as
  an absent subject when the button is a **contract** and the code is what
  lacks it.
- **A structural question was surfaced and deliberately not acted on:**
  `role_landing_and_visibility.md` may be a `docs/` document living in
  `spec/`. Relocating a spec is a contract decision and
  `test_spec_coverage.py` maps routing modules to governing specs, so a move
  is not a rename.
- **The plan asked for a pointer this batch did not add** — that the
  `beforeunload` pattern ships on the operator side. Added by hand
  afterwards, verified against `instruments_index.html:3737` at that head.

### Doc impact

- `spec/reviewer-surface.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 5).
- `spec/participant_model.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 5).
- `spec/role_landing_and_visibility.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 5).
- `spec/role_navigator.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 5).
- `spec/preview_hub.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 5).
- `guide/sweep_2026-09-13_spec_history.md` — the batch's record: per-file dispositions, the uncertain-and-kept list, and every claim not verified against the code (Item 5).
- `docs/status.md` — row when the item closes (Item 5).


## Item 6 — data IO and infrastructure

### Opportunity

Contract documents, where a dated note is often a **compatibility** statement rather than provenance — *"old bundles carrying this column are silently ignored"* is a live constraint on the importer. `settings_inventory.md` leads the corpus on retirement language (29 lines) largely for that reason.

### Scope — the batch's file list

- `spec/csv_contracts.md`
- `spec/extract_data.md`
- `spec/roundtrip_coverage.md`
- `spec/rehydrate.md`
- `spec/settings_inventory.md`
- `spec/email_template_editor.md`
- `spec/email_infra_options.md`
- `spec/timezone_display.md`
- `spec/blob_storage.md`

**9 files.** No file outside this list is edited by this item, and every file in it is either edited or recorded as read-with-no-finding.

### Decision

The segment's three-bucket rule, unchanged: provenance out, constraints re-expressed forward with a brief reason, absent subjects deleted. See `## Decision` above — it is not restated per item, because an item restating a shared rule is how the two copies drift apart.


### Status — 2026-09-13 (batch landed; item open pending adjudication)

**Intended vs done.** The batch landed as one rung, as the ladder said. What
the plan did **not** anticipate is that the brief itself was wrong: every
batch was told to write *"plain present-tense description of what ships"*,
which is `docs/`'s function, not `spec/`'s. The author's mid-sweep pointer
to `rrw_sdd_in_practice.md` §4 corrected it, and §0a of the record carries
the correction in full.

*Decisions confirmed at build:* 2026-09-13.

- **Two rewrites reverted**, both where a contract had been narrowed to match
  the code (`library_name`, `assignment_mode`).
- **The compatibility-tolerance category was larger than the plan implied.**
  The plan called it "the batch's highest-risk category"; in practice seven
  distinct tolerances had to be kept and re-expressed as obligations, any one
  of which would have broken a real importer if deleted.
- **One spec-vs-spec conflict was resolved by editing rather than
  reporting** — the observer-cohort-rule bullet in `rehydrate.md` — because
  its pointer named text this sweep removed. Flagged in the record for
  adjudication rather than presented as settled.
- **`blob_storage.md`: read, no finding.** The only file in the corpus with
  none.

### Doc impact

- `spec/csv_contracts.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/extract_data.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/roundtrip_coverage.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/rehydrate.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/settings_inventory.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/email_template_editor.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/email_infra_options.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/timezone_display.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/blob_storage.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6). <!-- doc-impact-waived: read, no finding — 0 dated lines, 0 provenance, 0 retirement language. Its future-tense options ladder and the deferral itself are the document's subject, so there was nothing in the three buckets to sort. The only file in the corpus with none. -->
- `guide/sweep_2026-09-13_spec_history.md` — the batch's record: per-file dispositions, the uncertain-and-kept list, and every claim not verified against the code (Item 6).
- `docs/status.md` — row when the item closes (Item 6).

---

## Item 7 — the doc-only fixes the sweep's findings ask for

### Opportunity

The sweep registered **75 discrepancies** in
`guide/findings_2026-09-13_spec_discrepancies.md` and actioned none, on the
rule that *a sweep recommends*. The author's instruction now splits them:
**doc-only fixes land here, in 19M.** Everything needing a code change or a
contract decision stays in the register.

The split is not the same as the register's own five kinds, because
*kind* and *cost* are different axes:

| register kind | doc-only? |
|---|---|
| **ID** stale identifier in a spec | **yes** — the spec names something that does not exist; the fix is the real name |
| **SI** a spec contradicting itself | **yes** — one of the two statements is wrong and the file settles it |
| **SS** two specs disagreeing | **mostly** — where one is plainly wrong or the precedence rule decides. **Not** where the code would have to move |
| **DT** documentation describing its own tooling | **yes** |
| **SC** spec vs code | **no** — each is *fix the code* or *change the contract deliberately*, and §4 puts that choice with the author |
| **CC** code comments | **no** — a code change, however small |

So Items 7–10 are ID, SI, SS-where-doc-only, and DT. **SC and CC stay in
the register**, and the one SS that needs a decision (SS-01, the five
validation severities, two of which would block activation) stays with it.

### Decision

**Four items, split by what makes each fix decidable**, not by file:

- **Item 7 — ID.** A spec names an identifier that does not exist. Decided
  by grepping the real name. No judgement.
- **Item 8 — SI.** A file contradicts itself. Decided by the file's own
  majority, or by the code where the file is evenly split.
- **Item 9 — SS, doc-only subset.** Decided by `spec/README.md`'s
  precedence rule (the per-subsystem spec wins), or by one side being
  plainly wrong about the other's content.
- **Item 10 — DT.** Decided by reading the tool.

**Rejected — one item for all four kinds.** They close on different
evidence, and a single item would let the easy ones carry the hard ones
through a close check. The ID fixes are mechanical; SS-04 is a re-audit
nobody has scoped.

**Rejected — fixing SC-01 here** (`library_name`, which makes an older
bundle unimportable). It is the finding I would act on first and it needs
no contract decision — but it is a **code** change, so it is not 19M's.

### Two findings that dissolved on verification

Recorded because they are the same shape as the sweep's own
*"four of twelve candidates were correctly-recorded history"*:

- **SS-06 is not a mismatch.** Three specs say the Workflow card has a
  *"ten-state cascade"* and `workflow_card.md` says *"twelve states"*. Its
  table carries states **1–10 plus `4W` and `4Err`** — so twelve rows,
  ten numbered states. **Both counts are correct**, of different things.
  The fix is to say which is being counted, not to change a number.
- **SI-01 has a right answer in the code.** `instruments.md`'s action-row
  list omits `+Page break`; the per-instrument section includes it.
  `instruments_index.html:510` renders the button, so the list is the
  wrong one.

### Semantics

- **A count in a heading is the self-staling class, and removing it is the
  fix** — not re-measuring it. `validate_page.md`'s *"(18 registered)"* is
  accurate today and will not stay so.
- **Where a spec states a verification method, the method must actually
  find the answer.** `permissions.md`'s recipe would falsely flag ≥9 routes
  whose gate is two levels deep. *A method producing false positives is
  worse than none, because the next person runs it and believes the
  result.*
- **A distinction is sometimes the fix.** `csv_contracts.md` says "five
  roster-shaped pairs" in its header and "four" in its byte-stability
  contract. Both are right about different things: five pairs exist
  (Observers has both an importer and an extract), and byte-stability is
  established for four. Whether Observers meets it is **unverified**, so
  the fix names five pairs, scopes the guarantee to four, and says the
  fifth is unchecked rather than implying either.

### Blast radius (measured)

At `83282ddb`, 2026-09-13 — 75 findings, of which doc-only:

```
grep -c '^| ID-' guide/findings_2026-09-13_spec_discrepancies.md   # 8  (Item 7)
grep -c '^| SI-' guide/findings_2026-09-13_spec_discrepancies.md   # part of 10 (Item 8)
```

**Item 7's eight ID rows touch six spec files.** Six are the retired
colour vocabulary (`accent-*`, `text-primary`, `bg-page`, `surface-2`,
`text-muted` — all **0** definitions in `base.html`); two are other wrong
names. **Code changed: 0.**

### PR ladder

One rung per item, Items 7 → 10 in order. Item 7 first because it is the
only one with no judgement in it, so it establishes the shape cheaply.

### Definition of done

- Every ID row either fixed or moved to a later item with a reason.
- Every replacement token verified to exist in `base.html` before it is
  written — *the sweep's own thirteen errors were mostly a name or number
  substituted inside a correct sentence.*
- `.venv/bin/pytest` green, `ruff check .` clean.
- The register updated: each actioned row marked, with what it became.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19M.7` exits 0; any warning adjudicated
- `spec-writer` run against the batch; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

1. **Does `ID-01` need `ui_elements.md` §6 first?** The four retired names
   are in `operator_button_audit.md`'s **role legend**, which exists to
   restate §6's vocabulary as a reading key. If §6 names the live tokens,
   the legend can point rather than restate — which is the same fix §1 took
   during the verification pass. *Decides: whoever lands Item 7.*

### Out of scope

- **SC and CC rows.** Code changes or contract decisions.
- **SS-01.** Two of the five severities would block activation as errors;
  that is a deliberate contract change.
- **Adding a test to pin anything.** Several findings (SI-07's query
  budget) would be better held by a guard than by prose. That is a code
  change and belongs in its own item.

### Status — 2026-09-13 (item closed)

**Intended vs done.** As planned, one rung, no judgement calls needed. Two
things the plan did not predict:

- **Open question 1 answered in the simplest direction.** ID-01's four
  names sit in `operator_button_audit.md`'s *role legend*, which exists to
  restate §6 as a reading key. Rather than repoint the four tokens, the
  legend **stops naming tokens at all** — so it cannot drift from §6 again.
  That is the same fix §1 of `ui_elements.md` took during the verification
  pass, arrived at independently.
- **One retired name covered two different live tokens.** `session_home.md`
  used `accent-blue` for both a card border and a button fill; those are
  `--card-active-border` and `--btn-primary-bg`. *That is the argument for
  the two-tier system, found by having to undo a flat name.*

**Open question 3 (from the segment's own list) is answered here**: stale
identifiers came to 8 rows across 7 files, six of them one cluster — a
footnote, and now closed rather than filed.

*Decisions confirmed at build:* 2026-09-13.

### Doc impact

- `spec/operator_button_audit.md` — the role legend's four retired token names (Item 7).
- `spec/session_home.md` — `accent-blue` and the `.card.placeholder` rule's three retired names (Item 7).
- `spec/extract_data.md` — two retired names, one of which has 0 occurrences of any kind (Item 7).
- `spec/participant_model.md` — the `.rs-acknowledge-card` pair (Item 7).
- `spec/role_navigator.md` — three retired names across two lines (Item 7).
- `spec/csv_contracts.md` — `field_labels.apply_captured_labels`, whose real name is `apply_import` (Item 7).
- `spec/visual_style_rrw.md` — a named cross-reference to a `session_home.md` heading that does not exist (Item 7).
- `guide/findings_2026-09-13_spec_discrepancies.md` — mark each actioned ID row with what it became (Item 7).
- `docs/status.md` — row when the item closes (Item 7).

---

## Item 8 — SC-01 … SC-04, where the author ruled the code correct

### Opportunity

Four of the register's spec-vs-code findings were the ones with a
consequence attached: an older settings bundle that cannot import at all,
a documented pill that cannot render, a helper named in a spec that does
not exist, and a figure the code *and a test* both contradict.

§4 puts that choice with the author, and it arrived in one line:

> *"SC01-04 — update spec/comments; code is correct"*

### Decision

**The code stands; the documentation moves** — in all four, and in both
directions the instruction names: `spec/` prose **and** the code's own
comments.

This is the deliberate contract change §4 permits, as against the silent
one it forbids, so **the decision is recorded in the register beside each
row** rather than only in a commit message. Four contracts changed on one
line of instruction; the line is part of the record.

**Rejected — treating SC-01 as a bug to fix in code.** It was the finding
I would have acted on first, and I said so. The author's reading is
better: strictness on rule-set attributes is worth the cost, because a
misspelled attribute dropped in silence would change *which pairs
generate* — and the top-level unknown-key ignore already covers the case
where silence is safe. **The spec now states the cost** (such a bundle
needs the column removed before import) rather than pretending there is
none.

**Rejected — deleting the `stale` field and its plumbing.** Out of scope:
the instruction was to correct the documentation, and removing a field the
status block constructs positionally is a code change with its own risk.

### Semantics

- **An absence is a contract and is stated as one.** Not *"staleness is
  deferred"* but *"there is no `stale` pill and no staleness signal on this
  page"*, with the consequence a reader needs — a rule edit is invisible
  until regeneration — because *a reader who assumes the page warns them
  will not check.*
- **A docstring describing a computation the function no longer performs is
  the same defect as a stale spec**, one layer in. `is_stale` said
  *"`eligible_count != generated_count` AND a rule is pinned"*; it is
  `False` unconditionally.

### Blast radius (measured)

At `83282ddb`: **3 spec files** (`settings_inventory.md`,
`assignments.md`, `reviewer-surface.md`) and **1 code file**, comments
only (`app/web/views/_assignments.py` — three docstrings and one inline
comment). **No behaviour changed**; the suite is the check.

### What correcting the comments turned up

Two findings the register did not have, both the sweep's own defect sitting
in code rather than in `spec/`:

- **The `"generate"` next-action state is unreachable** — gated on
  `any_stale`, which is forced `False`, so the branch never returns. Its
  docstring described what it *would* catch as though it ran.
- **The inline comment forecast a PR that had already shipped**: *"force
  False here **until PR 5.3** retires the legacy pinning path"*. PR 5.3
  shipped. The force is the design, not a pending state — and the real
  reason is better than the forecast: an always-stale badge trains the
  operator to ignore it, which is worse than reporting nothing.

### Definition of done

- All four rows marked **ACTIONED** in the register, with what each became.
- The author's instruction quoted in the register, not just the commit.
- No behaviour change: `.venv/bin/pytest` green, `ruff check .` clean.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19M.8` exits 0; any warning adjudicated
- `spec-writer` run against the batch; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

None. The decision was explicit and the four targets were already
verified by the sweep and its verification passes.

### Out of scope

- **SC-05**, the sibling of SC-04 — a test pinning the code's heading
  format *while citing the spec section it contradicts*. Not named in the
  instruction, so it stays in the register.
- **SC-06 … SC-36**, and every `CC` row. `CC-01`, `CC-03`, `CC-05` and
  `CC-11` are the same class as the two comment defects this item fixed,
  and are still open.

### Status — 2026-09-13 (item closed)

**Intended vs done.** The four spec edits landed as planned. The **code
comments turned out to carry more than the register knew**, which the plan
records as its own finding:

- **The `"generate"` next-action state is unreachable** — gated on
  `any_stale`, forced `False`. Its docstring described what it would catch
  as though it ran.
- **The inline comment forecast a PR that had shipped** — *"until PR 5.3"*.
  So the force is the design, not a pending state, and the honest reason is
  better than the forecast: an always-stale badge trains the operator to
  ignore it.

**I had argued the other way on SC-01** and the author's reading is better:
strictness on rule-set attributes is worth the cost, because a misspelled
attribute dropped in silence would change which pairs generate. The spec now
states the cost rather than pretending there is none. *Recorded because the
reversal is the useful part.*

*Decisions confirmed at build:* 2026-09-13, on the author's instruction
*"SC01-04 — update spec/comments; code is correct"*.

### Doc impact

- `spec/settings_inventory.md` — §10's `session_rule_sets` row: the strict reject, its reason, and its cost (Item 8).
- `spec/assignments.md` — §Staleness restated as an absence; the status-table Generated row drops the `stale` pill (Item 8).
- `spec/reviewer-surface.md` — the textarea factor becomes `0.5` in both places that name it (Item 8).
- `guide/findings_2026-09-13_spec_discrepancies.md` — SC-01..SC-04 marked actioned, with the author's instruction quoted and the two new code-comment findings recorded (Item 8).
- `docs/status.md` — row when the item closes (Item 8).

---

## Item 9 — the SI and doc-only SS rows

### Opportunity

Ten `SI` rows (a spec contradicting itself) and the `SS` rows a document
can settle without the code moving. Both are doc-only by construction: one
of the two statements is wrong, or the precedence rule decides.

### Decision

**Where a file contradicts itself, the code settles it; where two files
disagree, `spec/README.md`'s precedence rule does.** And twice the right
fix was **to point rather than to restate**, which is the same conclusion
Item 7 reached about the role legend and the verification pass reached
about `ui_elements.md` §1 — *a second copy of a statement is a second thing
to keep in step.*

**Rejected — renumbering `operator_button_audit.md`'s chrome table** to
slot the two missing tabs into render order. That file states its own rule:
numbers are stable identifiers other documents cite. So Observers and
Extract data are rows **12 and 13**, and the row order is explicitly not
the render order.

### Semantics

- **A count in a heading is removed, not re-measured.**
  `validate_page.md`'s *"(18 registered)"* was accurate and would not stay
  so.
- **A stated verification method must find the answer it claims to.**
  `permissions.md`'s decorator scan reports false positives, because
  several `_instruments.py` routes are gated two levels deep through
  `Depends(_require_instrument_in_session)`. It now says to follow
  `Depends()` transitively, and why: *a check that flags a correctly-gated
  route is worse than none, because the next reader believes it.*
- **A partial copy of a label is how a clause goes missing.**
  `setup_pages.md` stated the Upload confirm two ways — a three-clause
  version and a two-clause one. The template renders three
  (count / assignments / responses), and the response clause had gone
  missing once already, so the short version now points at the full one
  instead of restating it.
- **Two counts of different things are not a contradiction.** The Workflow
  card has **twelve states over ten numbers** — 1–10 with `4W` and `4Err`
  branching off 4. `workflow_card.md` now says both, so the five documents
  calling it a *ten-state cascade* stop reading as errors.

### Blast radius (measured)

7 spec files. `spec/instruments.md`, `spec/settings_inventory.md`,
`spec/setup_pages.md`, `spec/permissions.md`, `spec/validate_page.md`,
`spec/operator_button_audit.md`, `spec/workflow_card.md`, plus
`spec/email_infra_options.md` for the three `Manage Invitations` mentions.
**Code changed: 0.**

### Definition of done

- Every SI row fixed or moved with a reason; the doc-only SS subset fixed.
- Each fix checked against the code or the template first, not against the
  surrounding prose.
- `.venv/bin/pytest` green, `ruff check .` clean.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19M.9` exits 0; any warning adjudicated
- `spec-writer` run against the batch; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

None.

### Out of scope

- **SS-01**, the five validation severities. Two would block activation as
  errors; a deliberate contract change.
- **SI-07's query budget.** Rewording it does not fix it — nothing pins the
  figures, and the related test only asserts relative growth. **A guard is
  the right answer and a guard is code**, so it stays registered.

### Status — 2026-09-13 (item closed)

**Intended vs done.** Eight fixes landed. Three things the plan did not
anticipate:

- **`SS-05` was not one-sided.** *"Manage Invitations"* is used in
  `email_infra_options.md` three times as well as in the audit's own
  heading, so it was a vocabulary in circulation rather than one file's
  slip. All four now use the chrome label, `Invitations`.
- **`SI-03` needed a distinction, not a deletion.** Two `audit_events` rows
  carried opposite marks. They were answering different questions — *is
  there an extract* (yes) and *is it in this inventory's scope* (no) — so
  the surviving row states what its ✅ does and does not mean.
- **`SI-01`'s ASCII box had to stay aligned.** Adding `+Page break` to the
  card diagram meant shortening *"delete-confirm checkbox"* to keep all 66
  characters; verified by measuring characters rather than bytes, since the
  box-drawing glyphs are three bytes each.

*Decisions confirmed at build:* 2026-09-13.

### Doc impact

- `spec/instruments.md` — `+Page break` added to both action-row lists, in rendered order (Item 9).
- `spec/settings_inventory.md` — the duplicate `audit_events` row removed; the survivor states what its mark covers (Item 9).
- `spec/setup_pages.md` — the partial Upload confirm label points at the full one (Item 9).
- `spec/permissions.md` — the route-gate verification method follows `Depends()` transitively (Item 9).
- `spec/validate_page.md` — the rule count comes out of the §3.2 heading (Item 9).
- `spec/operator_button_audit.md` — Observers and Extract data as chrome rows 12 and 13; §13 renamed to `Invitations` (Item 9).
- `spec/email_infra_options.md` — three `Manage Invitations` mentions renamed (Item 9).
- `spec/workflow_card.md` — twelve states over ten numbers, stated so neither count reads as an error (Item 9).
- `guide/findings_2026-09-13_spec_discrepancies.md` — mark each actioned row (Item 9).
- `docs/status.md` — row when the item closes (Item 9).

---

## Item 10 — the documentation that describes this segment's own tooling

### Opportunity

Rewriting `.claude/agents/spec-writer.md` left four documents describing a
charter that had changed. `rrw_sdd_in_practice.md` describes it in **four**
places; one was already correct and three were not, including a verbatim
quote of words the file no longer contains.

**The sweep also removed every currency line from `spec/`**, which
falsifies §6.2's trade-off rather than just its figure: it said *"only the
functional spec dates itself: 4 of 36"*, and the answer is now **none of
39**.

### Decision

**Correct the facts; leave the arguments.** These are the author's measured
analysis, so each edit is the smallest one that makes the sentence true,
and every surrounding claim about the practice stands.

§6.2's trade-off is restated rather than renumbered, because *what* changed
is more informative than the count: currency moved from an in-file date to
a sweep-record pointer, on the reason 19J.1 gave when it did this to
`spec/README.md` first — *a date nobody owns is what let §9.7 describe a
card that never shipped.* It trades a figure that rots quietly for one that
rots visibly, since a sweep record carries its own date and scope.

### `DT-04` dissolves, and that is the finding

`docs/practice-audit-2026-09-04.md` quotes the old charter and
`guide/todo_master.md` mentions `spec-writer` five times. **Neither is
changed, and neither is an omission.** The practice audit is a **dated**
document whose quote was accurate on 2026-09-04, and `todo_master.md`'s
mentions all record what a *pass found*, not what the charter says.
Repointing either would falsify a log — the reasoning the sweep applied
four times to `spec/`, holding here for `docs/` and `guide/`.

*Only `rrw_sdd_in_practice.md` describes the charter in the present tense,
which is why it is the only file this item edits.*

### Blast radius (measured)

**1 file, 4 edits.** `rrw_sdd_in_practice.md` §6.1 (the quote), §6.2 (the
currency trade-off), §6.4 (the unqualified clause), and the Appendix
maker/checker row. **Code changed: 0. Other documents changed: 0**, for the
reason above.

### Definition of done

- All three DT rows corrected; DT-04 recorded as dissolved with its reason.
- No argument altered — only claims about the tool and the figure.
- `.venv/bin/pytest` green, `ruff check .` clean.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19M.10` exits 0; any warning adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

None.

### Out of scope

- **Every `CC` row.** Code comments.
- **`docs/practice-audit-2026-09-04.md` and `guide/todo_master.md`** — see
  above; deliberately unchanged.

### Status — 2026-09-13 (item closed)

**Intended vs done.** Four edits where the plan predicted three, because
§6.2's figure turned out to be the smaller half of the problem: **no live
spec carries a currency line at all now**, so the trade-off paragraph
described a mechanism that no longer exists rather than a count that had
moved.

**And the item shrank on investigation.** DT-04 named three further
documents; none needed changing, because a dated audit and a record of what
a pass found are both legitimate history. *The sweep spent all day learning
to tell those apart from drift, and the lesson held on the last item.*

*Decisions confirmed at build:* 2026-09-13.

### Doc impact

- `rrw_sdd_in_practice.md` — §6.1's charter quote, §6.2's currency trade-off, §6.4's unqualified clause, and the Appendix maker/checker row (Item 10).
- `guide/findings_2026-09-13_spec_discrepancies.md` — DT-01..DT-03 marked actioned; DT-04 recorded as dissolved (Item 10).
- `docs/status.md` — row when the item closes (Item 10).
