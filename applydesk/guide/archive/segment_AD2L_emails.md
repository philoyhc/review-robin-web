# Segment AD2L — Email templates (version 1)

**Opened:** 2026-11-23 · **Theme:** Emails' templates and Process's send ticks move into the database; an Emails card's *Save* keeps its template for every exercise · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/spec/applications.md` ("The Emails page"), rulings 16, 54 and 65 (`applydesk/guide/todo_master.md`)

## Opportunity

- **Emails keeps nothing an exercise can rely on.**
  - On a sample exercise, a card's *Save* keeps the template "in this tab only"; the status row, Home and Dossiers' *Released* still read the sample's.
  - On a scratch exercise it writes into the browser's in-memory store, which a deploy, a restart or eight idle hours drops.
- **The send ticks have no home either.** Process's "Send email", *Receipt* and *Reminder* ticks are stored for a scratch exercise in the same memory, and a sample's are hard-coded (`workflow._SENDS`), so a Process save on a sample changes nothing Emails reads.
- **The order from AD2C** (author, 2026-11-23): after AD2E's panels and AD2D's form, Emails is the last page on the browser store. Once it leaves, AD2G can remove the store.

## Decision

- **Tables**, keyed per exercise (ruling 37).
  - `email_send`: one row per (item, audience) Process ticks. `item` is `receipt`, `reminder` or an outcome's key; rows are retired, never deleted (ruling 74).
  - `email_template`: one row per (item, audience) with its subject, body and a `version` counting its saves.
  - `exercise.sends_saved`: false until a Process save records the ticks; a sample keeps its own until then.
- **Process's save records the ticks** it already builds (`process_save.build`'s second value), in the same transaction as the timeline, for every exercise.
- **One card's Save keeps one template**, as today.
  - The checks stay as they are: the email must be one Process owes, at most 300 and 20,000 characters, no other kind's tag.
  - It runs under the exercise's lock (`panels_store.lock`), guarded by the Process revision the page opened at (as today) and by the template's own `version`, so two operators saving one card cannot overwrite each other unseen.
  - The save is audited as `exercise.email_saved`.
- **The readers read the store.** `workflow.sends`, `template_text` and `emails` read the stored ticks and templates, else the sample's. A sample's card that was never saved reads its default (written) or empty (owed), as now.
- **No new page or card:** the Emails card already has *Save*; it posts for every exercise. No scaffold rung.

**Rejected:**
- **Templates as one JSON per exercise.** A card saves alone, and two cards saved at once must not overwrite each other.
- **Storing the sends in `outcome` and `stage` columns.** The form's receipt and reminder have no outcome; one table covers both, keyed as Emails names them.

## Semantics

- **An outcome retired by Process** retires its sends rows; its template row stays (ruling 74) and is read again if the key is ever owed again, which it cannot be, since keys are never reused.
- **A template saved empty** (no subject or no body) is kept as owed, as today's "Saved, still owed".
- **Stale pages.** A card opened before Process last saved is refused as now (*reload Emails*). A card opened before another save of the same template is refused (*saved since this page opened; reload*), 409.
- **A sample exercise** keeps `_SENDS` until its first Process save, and its `_WRITTEN` defaults for every card not yet saved.

## Judgment calls — decided

- The template's own `version` guard, not the exercise's: cards are independent, so saving one must not stale the others.
- The sends ride Process's revision rather than a revision of their own, because only Process writes them.
- Sending stays AD7's; nothing here sends.

## Blast radius (measured)

Taken 2026-11-23 at `5fd6aec29`.

| What | Count | Command |
|---|---|---|
| Scratch store reads and writes of the sends and templates | 7 | `grep -rn 'SENDS_PAGE\|SCRATCH_PAGE\|scratch_templates(' applydesk/*.py \| grep -v "def \|= \""` |
| Calls of the Emails readers | 7 | `grep -rn 'workflow.emails(\|workflow.sends\|template_text(\|scratch_templates(' applydesk/*.py \| grep -v "def "` |
| Test files on Emails or the ticks | 7 | `grep -rln '/emails"\|data-em-save\|em-said\|template_text\|workflow.sends' applydesk/tests --include=*.py` |

## Status

**Closed 2026-11-23.** Intended versus done:

- **The ladder held:**
  - #4179 plan;
  - #4180 tables;
  - #4181 `email_store`;
  - #4182 Emails and the ticks stored for every exercise, which also carried the cumulative read.
- **Decisions confirmed at build:**
  - The owed check is a callable the store reads under the exercise's lock. A Process save that lands first is therefore seen.
  - A card's text and version come from one read. Read separately, a save landing between them could pair old text with a newer version (cold read).
  - Recording no ticks at all is a valid save: the exercise sends no email.
  - With every Setup page in the database, the scratch page store (`scratch.page`, `save_page`, `Scratch.pages`) is deleted here rather than in AD2G. The browser-held exercise itself stays until AD2G.
  - A refusal that already says "Not saved" is shown once.
- **Left:** `workflow.sends` still opens a session per call, and Process's cards call it per outcome. This is a cost, not a defect, and goes with AD2G's request-scoped loading.
- **Reads:** one cumulative `diff-reviewer` read of rungs 2–4 (base `26fbd7687`) found 3 defects and several leftovers, all fixed except the per-call reads above.

## PR ladder

1. **PR 1 — this plan.**
2. **PR 2 — the tables.**
   - `email_send`, `email_template` and `exercise.sends_saved`, with a migration round-tripped on Postgres.
   - Nothing reads them yet.
3. **PR 3 — `email_store`.**
   - Loads and saves the ticks (whole, with Process's save) and one template (under the lock, both guards, audited).
   - Must not change a page.
4. **PR 4 — Emails and the ticks stored for every exercise.**
   - Process's save records the ticks; Emails' card *Save* posts for every exercise; the readers read the store.
   - The scratch sends and templates paths are deleted, and the page's "kept in this tab only" path goes.
   - Last build rung: the cumulative `diff-reviewer` read.
5. **PR 5 — close.**

## Definition of done

- **The tables** exist for sends and templates, with `exercise.sends_saved`. The migration round-trips in `ci-postgres`.
- **A saved template** survives a restart, and is refused on a stale Process revision or a stale template version (`applydesk/tests/test_email_store.py`).
- **Process's ticks** survive a restart and drive Emails, Home and the status row on every exercise, a sample's included (a test).
- The scratch paths are gone: `grep -rn 'SENDS_PAGE\|SCRATCH_PAGE' applydesk --include=*.py` finds nothing.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2L` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None.

## Out of scope

- **Sending** any email, and its log: AD7.
- **Evaluators' invitations and reminders** for a linked gate: Review Robin's handoff, not a template here.
- **The browser store's removal** and the scratch exercise itself: AD2G's first part, next in the order.

## Doc impact

- `applydesk/spec/applications.md` — "The Emails page": *Save* for every exercise, its refusals and its two guards; the scratch-only and "this tab only" lines go; Process's ticks stored with its save.
- `applydesk/spec/architecture.md` — the `email_send` and `email_template` tables and `exercise.sends_saved`, `email_store.py`, the `exercise.email_saved` event.
- `applydesk/guide/ad2_series.md` — AD2L's row: its plan pointer, then its archived copy.
- `applydesk/guide/todo_master.md` — the roadmap's AD2 row names AD2L's plan while open (at close: closed).
- `applydesk/README.md` — the plan's index row, moved at close.
