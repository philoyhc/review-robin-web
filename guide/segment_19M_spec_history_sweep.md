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
| dated references | **252 lines** carry a `YYYY-MM-DD` | `grep -c '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' spec/*.md` |
| retirement / provenance language | **239 lines** | `grep -ci 'retired\|no longer exists\|used to \|superseded\|was renamed\|shipped in\|Corrected 20' spec/*.md` |
| plan apparatus | **86 blocks, all in `ui_elements.md`** | `grep -c '\*Current:\*\|\*Migration delta:\*\|\*PR:\*\|\*Canonical:\*' spec/*.md` |

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
grep -c '20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]' spec/*.md   # 252 dated lines
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

### Doc impact

- `spec/csv_contracts.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/extract_data.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/roundtrip_coverage.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/rehydrate.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/settings_inventory.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/email_template_editor.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/email_infra_options.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/timezone_display.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `spec/blob_storage.md` — history-shaped passages sorted into the three buckets; constraints re-expressed forward (Item 6).
- `guide/sweep_2026-09-13_spec_history.md` — the batch's record: per-file dispositions, the uncertain-and-kept list, and every claim not verified against the code (Item 6).
- `docs/status.md` — row when the item closes (Item 6).
