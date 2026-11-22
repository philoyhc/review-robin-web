# Segment AD2B — Exercises and Details

**Opened:** 2026-11-22 · **Theme:** an exercise's own settings move from sample data and the scratch store into the database, and the Operator Lobby's scaffold is wired to them · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/spec/applications.md`, `applydesk/spec/permissions.md`, `applydesk/guide/ad2_deferred_findings.md`

## Opportunity

An exercise's settings live in two places that do not persist:
- **Sample exercises:** their name, code, description, eligibility, blind flag, help contact and timezone are constants in `sample_data.py`. Details' *Lock* posts are refused for them (`routes_operator.exercise_details` 404s unless scratch).
- **Scratch exercises:** their settings are held in server memory for one browser.

The database's `exercise` row holds only a public ID and a creation time (AD2A).

The Operator Lobby is AD1T's scaffold. Sorting, tags, the filter, *Go to Archive* and the tick panel's actions are inert, and *Created* and *Tags* are sample values.

The AD2 series gave AD2B six findings. Five stay here: AD-54, AD-55, AD-60, AD-97 and AD-40 (`applydesk/guide/ad2_deferred_findings.md`). AD-52's invitee list moves to AD2C, as a stage item (author, 2026-11-22).

## Decision

- **The `exercise` row holds its settings:**
  - name and code (code unique among live exercises, case-insensitive);
  - `description` (AD-55: the field's name follows the pages);
  - eligibility as an enum, `open` or `invitation`;
  - blind;
  - help contact and timezone, each NULL meaning the operator settings' default (AD-54);
  - tags;
  - `created_by_id` and `created_at`;
  - `archived_at` and `deleted_at` (ruling 74: nothing hard-deleted);
  - a `revision`.
- **NULL for unset:** "Not set" is never stored (AD-60). Pages print it.
- **One service, `applydesk/exercises.py`, reads and writes them:**
  - The pages keep their sample-shaped `Exercise`. `lookups.exercise_or_404` overlays the row's settings on the sample's stages and applications, which stay sample data until AD2C–AD2F.
  - Scratch exercises also have rows (AD2A), so their Details save to the database too. The scratch store keeps only the other pages.
- **Details' *Lock* saves any exercise the viewer operates.** It names the revision it opened at and is refused if a newer one exists (ruling 74). It is audited as `exercise.details_changed` with a changes envelope.
- **The seed** writes the samples' settings into their rows.
- **One clock and one date helper** (AD-40, AD-97):
  - `applydesk/clock.py` gives "now" (the sample's fixed day where the sample needs it);
  - operator pages print stored times as `YYYY-MM-DD HH:MM` in the exercise's timezone.
- **The Operator Lobby is wired:**
  - its rows come from the database (live exercises the viewer owns or operates);
  - sorting is server-side by query string, so a reload keeps it;
  - the tag chips with *OR*, and the filter box over name, code and tags;
  - *Go to Archive* lists archived exercises, each with *Restore*;
  - the tick panel's *Save* (name, code, tags), *All tags to all*, *Remove from all*, *Duplicate settings only*, *Archive* and *Delete*.
  - Delete and archive are Owner-only (`applydesk/spec/permissions.md` §3).
- **Inert in the panel, saying why:**
  - *Duplicate*, which copies the setup: it waits for AD2C–AD2F to store the setup;
  - *Purge*: it waits for AD2D's applications.
  - So *Purge and archive* archives only, and says the purge is not built.

Rejected: moving the whole `Exercise` dataclass to the database at once. Stages, forms and applications are later segments' tables. Overlaying the stored settings keeps every page working between segments, as the series requires.

## Semantics

- **Code:**
  - blank is allowed, so a new exercise has none;
  - two live exercises may not share one, ignoring case;
  - an archived or deleted exercise frees its code.
- **Eligibility:** stored as the enum only. Who is invited is a stage item, AD2C's (AD-52).
- **Timezone:**
  - NULL means the operator settings' default;
  - choosing the default stores NULL, so Details can say "the default" truthfully (AD-54).
- **Revision:** it rises on every saved change. A Lock that started at an older revision is refused and saves nothing.
- **Archive and Restore:**
  - archived exercises leave the Lobby and appear on Archive;
  - Restore brings one back unless its code is now taken, in which case it is refused and says so.
- **Delete:**
  - sets `deleted_at`;
  - the exercise leaves every page;
  - its audit trail stays;
  - asks first;
  - Owner-only.
- **Tags:** trimmed, case-insensitive per exercise, at most 20 per exercise and 40 characters each; shown in the case first typed.
- **Duplicate settings only:**
  - a new Draft exercise with the settings and tags;
  - named "Copy of …", no code;
  - its Owner is whoever duplicated it.
- **Sorting and filtering** are query parameters (`sort`, `dir`, `tag`, `any`, `q`). Unknown values are ignored, never echoed.

## Judgment calls — decided

- Overlay, not replace: `sample_data.Exercise` stays the pages' shape until AD2G retires the simulation.
- Invitees are a stage item, not the exercise's: AD-52 moves to AD2C (author, 2026-11-22).
- Server-side sorting rather than client-side: the Lobby lists only what the viewer operates, a short list, and a query string survives a reload.

## Blast radius (measured)

Taken 2026-11-22 at `579a52717`.

| What | Count | Command |
|---|---|---|
| Modules reading sample exercises | 7 (10 call sites) | `grep -rln "sample_data.exercise(\|sample_data.exercises()\|sample_data.EXERCISES" applydesk/*.py` |
| "Not set" stored or compared | 7 files | `grep -rln "\"Not set\"\|'Not set'" applydesk/*.py applydesk/templates -r` |
| Fixed clocks (`TODAY`) | 6 uses | `grep -rn "TODAY\b" applydesk/*.py \| wc -l` |
| Test files on the Lobby | 11 | `grep -rln "operator/exercises\"" applydesk/tests` |
| Migrations | 6; this adds two or three | `ls applydesk/alembic/versions` |

## PR ladder

1. **PR 1 — this plan.**
2. **PR 2 — the stored exercise.**
   - The columns, with a migration round-tripped on Postgres.
   - `exercises.py` with get, list, save, revision and audit.
   - The seed writing settings.
   - `exercise_or_404` overlaying the stored settings.
   - Must not change any page's look.
3. **PR 3 — Details saves to the database.**
   - Any operated exercise saves, with the revision guard; "Not set" becomes NULL (AD-55, AD-60, AD-54).
4. **PR 4 — one clock and the date helper** (AD-40, AD-97).
5. **PR 5 — Lobby scaffold for Archive.** The Archive page, with the list, *Restore* and the copy, as a scaffold.
6. **PR 6 — the Lobby wired.**
   - Rows from the database, sorting, tags and the filter.
   - The panel's Save, the two tag actions, Duplicate settings only, Archive and Delete.
   - Archive and Restore.
   - Last build rung: the cumulative `diff-reviewer` read.
7. **PR 7 — close.**

## Definition of done

- **Details on a sample exercise saves and survives a restart.** A stale Lock is refused (a new `test_exercises.py`).
- **The Lobby sorts and filters through its query string.** Its tag chips filter with *OR*. Archive and Restore round-trip, and Delete removes the exercise from every page, by its Owner only (`test_pages.py`, `test_lobby_browser.py`).
- **No "Not set" is stored** (`grep -rn '"Not set"' applydesk/exercises.py applydesk/seed.py` finds none).
- **AD-40, AD-54, AD-55, AD-60 and AD-97 are struck** in `applydesk/guide/ad2_deferred_findings.md`, each with its PR.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None open. Answered 2026-11-22 (author):
- *Duplicate* stays on the panel, inert, saying why.
- *Purge and archive* archives now.
- Invitees are a stage item, deferred to AD2C.

## Out of scope

- **AD2O:** Make Owner, step down, leave, *Your role* (`applydesk/spec/permissions.md` §3, §7).
- **AD2C:** invitees, a stage item (AD-52).
- **AD2C onward:** stage dates (*Opens*, *Applications close*, *Expected outcome* stay sample values), forms, applications, panels and dossiers.
- **AD3:** what a published exercise fixes, and Validate's warnings.

## Doc impact

- `applydesk/spec/applications.md` — Details saving to the database with the revision guard; the Operator Lobby wired (sorting, tags, the filter, Archive and Restore, the panel's actions, what stays inert); dates on operator pages.
- `applydesk/spec/architecture.md` — the module map (`exercises.py`, `clock.py`), the `exercise` columns, the migrations.
- `applydesk/spec/permissions.md` — §3 and §6: archive and delete built, Owner-only.
- `applydesk/guide/ad2_deferred_findings.md` — AD-40, AD-54, AD-55, AD-60, AD-97 struck with their PRs.
- `applydesk/guide/ad2_series.md` — AD2B's row points at this plan, then its archived copy; AD-52 moved to AD2C's row.
- `applydesk/guide/todo_master.md` — the queue entry deleted at close.
- `applydesk/README.md` — the plan's index row, moved at close.
