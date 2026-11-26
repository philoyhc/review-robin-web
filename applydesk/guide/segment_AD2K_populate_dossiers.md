# Segment AD2K — Populate Dossiers

**Opened:** 2026-11-26 · **Theme:** ruling 83 built: the first item populates dossiers, Candidates becomes *Populate Dossiers*, and Process validates the timeline · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/archive/segment_AD2F_dossiers.md` (once closed), `applydesk/spec/applications.md`, rulings 24, 26, 77, 81 and 83 (`applydesk/guide/todo_master.md`)

## Opportunity

- **A new exercise starts with the Form on its first stage** (`stages.plan_of`, an unsaved ordinary exercise). Ruling 83 makes the first item a choice between a Form and Populate Dossiers, so the operator has to remove the Form to start the other way.
- **Candidates holds a person once** (`uq_candidate_pair`). Ruling 83 makes each entry a dossier, and one person may hold several.
- **A dossier has exactly one source** (`ck_dossier_one_source`). A dossier populated first cannot later gain the application a later Form adds (ruling 83).
- **Nothing checks the timeline as a whole.** An exercise can be published with no Form and no Candidates, and so no dossiers.

## Decision

- **A new exercise starts with a blank stage** (author, 2026-11-26): no Form, no item; *+Form* and *+Populate Dossiers* both offered.
- **Candidates is shown as *Populate Dossiers*** on Process, Dossiers, the CSV and Home. Identifiers, the `candidate` table and audit event names keep their names (`CLAUDE.md`: shipped identifiers are not renamed).
- **An entry is a dossier.**
  - `candidate` loses `uq_candidate_pair` and gains an optional `title`.
  - Adding someone again adds an entry, up to the per-person maximum.
  - Removing an entry retires it and its dossier. Re-adding someone makes a new entry, not a revival (ruling 83 replaces AD2F's revive).
- **Dossiers per person** live on the exercise (`dossiers_per_person`, 1 by default, up to 20) and are set on whichever item populates: Populate Dossiers, or a first Form. Populate Dossiers' adds are refused past it; a Form's submissions enforce it with AD4.
- **A populated dossier may later gain an application.** `ck_dossier_one_source` becomes *a candidate or an application, or both*, `candidate_id` stays unique. Nothing links them until AD4.
- **One validation service**, `timeline_checks.check(plan)`, returning errors and warnings. Its errors block publishing the first stage (`locks.publish_problems`); both show on Process's Outline and Home's Validate.
  - Errors: the first stage holds neither a Form nor Populate Dossiers; Populate Dossiers after a Form; a Form after Populate Dossiers, until AD4 builds its entry rule ("A later Form needs its entry rule: not built yet").
  - Warnings: Populate Dossiers has no entries; no outcome follows the last gate.
- **Minting** (AD2F's `sync_candidates`) tests "Populate Dossiers is the first item" in place of "no form anywhere".

**Rejected:**
- **Renaming the table and modules now.** It touches a migration and every reader for a label; the label is what the operator sees.
- **Leaving a later Form publishable without its entry rule.** It would invite no one, or everyone, silently.

## Semantics

- **The first item** is the first stage's: a stage holds at most one of Form and Populate Dossiers.
- **Per-person count** counts live entries for one person in one exercise. Lowering the maximum below what is already held refuses the save, naming who is over.
- **A blank first stage** saves and stays a draft; only publishing asks for a first item.
- **The samples** keep their Form first stages; nothing about them changes.

## Judgment calls — decided

- **The setting on the exercise, not the item** (2026-11-26): one populating item per exercise, so one value; it moves with the item if the first item changes.
- **Maximum 20 per person** (2026-11-26): a cap for the page, raised if an exercise needs it.

## Blast radius (measured)

Taken 2026-11-26 at `2e8ba675a`.

| What | Count | Command |
|---|---|---|
| Unsaved first stages built with the Form | 4 (`stages.py`) | `grep -rn "form=True" applydesk --include=*.py \| grep -v /tests/` |
| Modules naming Candidates | 17 | `grep -rln "candidates\|Candidates" applydesk --include=*.py --include=*.html \| grep -v /tests/` |
| Template lines saying Candidates | 14 | `grep -rn Candidates applydesk/templates \| wc -l` |
| Test files naming candidates | 18 | `grep -rln "Candidate\b\|candidates" applydesk/tests \| wc -l` |

## Status

- **2026-11-26, the build:** rungs 2–5 built; rung 4 split in two to keep each PR readable: **4a** entries (migration, service, the list by entry, minting by first item) and **4b** *Dossiers per person* on the populating items, saved with Process. Rung 2's base on `main`: `1764162` (the plan's merge).
- **The cumulative read** (`diff-reviewer`, 1 read, at rung 5) found 1 medium and 7 lows:
  - fixed at rung 5: *Dossiers per person* shown on two items of one stage could save the other's value: it is one setting, every box kept the same; a SQLite add race (a no-op write, as `panels_store.lock`); a comment; `plan_of`'s docstring.
  - stays: a blank box refuses the save with the range, not silently; publishing checks the timeline for the first stage only, as planned; the spec's old one-per-person and revival lines are the close's `spec-writer` pass; seven code comments still say *Candidates* (no page does).
  - the sample `c4xh2ndv6s` now warns that no outcome follows its last gate: true, and kept; "nothing about the samples changes" holds for their timelines, not their warnings.
- **Decisions confirmed at build:** one stage may still hold both the Form and Populate Dossiers (the *Invitation only* roster, until AD4); only the CSV gives an entry a title.

## PR ladder

1. **Plan** (this file), the series row. Prose only.
2. **A blank first stage.** An unsaved ordinary exercise's first stage holds nothing; Home's next step and the form moves read "no form". Must not touch the samples.
3. **The label.** *Populate Dossiers* on every page, the CSV and the spec; *+Populate Dossiers*.
4. **Entries and the per-person setting.** Migration `ad2k1_entries` (`uq_candidate_pair` dropped, `title`, `exercise.dossiers_per_person`, the dossier check relaxed); the service and the item's UI; minting by "first item".
5. **Validation.** `timeline_checks`, the Outline, publishing and Home's Validate.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
6. **Close:** `spec-writer` on `applydesk/spec/`; Status compacted; the plan archived.

## Definition of done

- A new exercise's Process shows one blank stage with *+Form* and *+Populate Dossiers* (a test).
- No page says *Candidates* (`grep -rn Candidates applydesk/templates` finds none).
- One person holds two entries, and two dossiers, up to the maximum; past it, refused (tests).
- Publishing a first stage holding neither item is refused with the error (a test).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2K` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **A title for an entry added by search** (cold read): today only the CSV gives one, so two search entries for one person look alike. Author.

- **The *Invitation only* setting on Details** stops meaning anything under ruling 83. It stays until AD4 replaces it with a later Form's entry rule; decided with AD4.

## Out of scope

- A later Form's entry rule, and its submissions joining dossiers: AD4.
- A Form's per-person enforcement: AD4, at submit.
- The candidate dossier's page: AD2V.

## Doc impact

- `applydesk/spec/applications.md` — Process's first stage, *Populate Dossiers* and its entries, the per-person setting, validation's errors and warnings.
- `applydesk/spec/architecture.md` — the migration, `timeline_checks`, the candidate and dossier tables' changes.
- `applydesk/docs/data_and_visibility_model.md` — §2's populating item, as built.
- `applydesk/guide/ad2_series.md` — the AD2K row closed (at close).
