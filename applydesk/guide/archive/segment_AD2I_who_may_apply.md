# Segment AD2I — Who may apply

**Opened:** 2026-11-27 · **Theme:** ruling 84 built: the Form chooses who may apply, Create dossiers only creates, the first item comes before gates, and a stage's items reorder · **Related:** `applydesk/guide/ad2_series.md`, `applydesk/guide/segment_AD2K_populate_dossiers.md`, `applydesk/spec/applications.md`, rulings 77, 81, 83 and 84 (`applydesk/guide/todo_master.md`)

## Opportunity

- **A Form-led invite list forces dossiers in advance** (author, 2026-11-27). With up to three dossiers per person, the only invite list is Create dossiers, so the operator makes three dossiers per invitee before anyone applies.
- **Who may apply lives on Details** (`exercise.eligibility`, *Open to all signed in* / *Invitation only*), far from the Form it governs, and ruling 83 already makes *Invitation only* mean "Create dossiers first".
- **A new stage offers *+Gate* and *+Outcome* before anything says whose dossiers the exercise holds**; only publishing catches it (`timeline_checks.NO_FIRST_ITEM`).
- **A stage's items cannot be reordered**: the order is fixed by kind (`_process_cards.html`), so Create dossiers and a Form on one stage, or two gates, keep the order they were added in.

## Decision

- **The Form's *Who may apply*** is a dropdown on the Form item: *Anyone signed in*, *Invitees*, *Dossiers* (author, 2026-11-27).
  - *Dossiers* is greyed out without a Create dossiers earlier; with one, the box shows *Dossiers*, disabled.
  - *Invitees* shows the invite list: the people search and CSV, as Create dossiers', one row per person.
  - Stored in `exercise.eligibility` (`open`, `invitation`; *Dossiers* is derived, never stored), saved with Process.
- **Invitees are their own table**, `invitee` (exercise, person, via, added by and when, removed): Create dossiers' entries are dossiers; an invitee is a person who may submit, up to dossiers per person.
- **Details' *Who may apply* retires**: Details shows neither the control nor the field; the Form's dropdown is the one place.
- **Before a Form or Create dossiers exists**, every stage offers only *+Form* and *+Create dossiers*.
- **Grip handles reorder a stage's items within the stage** (author, 2026-11-27), stored as the stage's item order; a drop that breaks a rule is undone, saying why.

**Rejected:**
- **Invitees as Create dossiers entries with a flag**: one table, two meanings; a per-person limit counts entries, an invite list does not.
- **Reordering across stages** (author, 2026-11-27): more ways to break a rule for a move rarely needed; remove and re-add serves.
- **Keeping Details' control until AD4**: two places for one setting.

## Semantics

- **Existing exercises.** `invitation` with Create dossiers on a stage holding the Form: its live entries' people become invitees (a data migration), the entries stay; `invitation` without either list keeps `invitation` with an empty invite list.
- **An empty invite list** with *Invitees* chosen: a warning on the Outline ("No one is invited yet"), not an error.
- **The dropdown's value when Create dossiers is removed** after *Dossiers* showed: what is stored (`open` by default).
- **Item order** is the stage's own; gates keep their numbers by order across the timeline, as now. The outcome stays last in its stage: it decides on the gates before it.
- **A refused drop**: the item returns to where it was; the reason shows on the stage, as the move guards' titles do.

## Judgment calls — decided

- **`eligibility` keeps its stored values** (2026-11-27): `open` and `invitation` read as *Anyone signed in* and *Invitees*; renaming stored values buys nothing.
- **The invitee list is shown only while *Invitees* is chosen** (2026-11-27); switching away keeps it, as Details' roster did.

## Blast radius (measured)

Taken 2026-11-27 at `d70ab00c3`.

| What | Count | Command |
|---|---|---|
| Modules reading `eligibility` | 6, 34 lines | `grep -rn "eligibility" applydesk --include=*.py --include=*.html \| grep -v /tests/ \| grep -v alembic` |
| Test files naming it | 5 | `grep -rln "eligibility\|Invitation only" applydesk/tests` |
| Specs and docs naming it | 4 | `grep -rln "Invitation only\|eligibility" applydesk/spec applydesk/docs` |
| Add buttons a stage shows | 4, in `_process_cards.html` | `grep -n "data-pc-act=" applydesk/templates/applydesk/operator/_process_cards.html` |

## Status

Closed 2026-11-27: rung 1 #4257, rung 2 #4258, rung 3 #4259, rung 4 #4260, rung 5 #4261, close in this PR.

- **Intended vs done.** Built as planned, except that rung 5 stores no
  `stage.item_order`. The rules fix every kind's place: Create dossiers
  before the Form and the gates, the outcome last, and the Form never
  beside a gate. Only the gates between stay free, and they already save
  their order as `gate.position`. So the page draws that order, the grips
  move items within it, and a move that breaks it is put back with its
  reason. No migration was needed. The server needs no check for the
  forced kinds, since Create dossiers, the Form and the outcome are flags
  drawn in a fixed order.
- **Decisions confirmed at build:**
  - A published Form keeps *Who may apply*: `exercises.set_eligibility`
    refuses a change (Codex on #4259, replacing Details' server lock).
    Unset reads as *Anyone signed in*, so the page's first save writes
    nothing.
  - The invite list sits outside the Form's lock, as Create dossiers'
    list does, each change kept as made.
  - *Dossiers* shows for a Create dossiers anywhere on the timeline (one
    after the Form is already `POPULATE_AFTER_FORM`).
  - The empty invite list is a warning, `timeline_checks.NO_INVITEES`.
  - A published stage's gate order is refused on the server too.
- **Reads.** One cumulative `diff-reviewer` read, rungs 2–5 from
  `c521cd1`. It found 10 issues: a published-Form lock missing on the
  server (also Codex's), a published gate order enforced only on the page,
  the invite list inside the lock, the data move mixing MINs across
  columns, a dead guard, an inconsistent *Dossiers* rule, test gaps, and
  stale comments. All fixed in rungs 3–5, except two left as is: a Process
  change bumps Details' revision, and no browser test drags a successful
  move with the mouse.
- **`spec-writer` at close** aligned the three specs. It flagged stale
  AD2K text (the `candidate` table's uniqueness, `ad2k1entries` missing
  from the migration list), which is left for AD2K's close.

## PR ladder

1. **Plan** (this file), ruling 84, the series row. Prose only.
2. **The first item before gates.** *+Gate* and *+Outcome* hidden until a Form or Create dossiers is in the process (server and page). Must not touch storage.
3. **The Form's dropdown.** *Who may apply* on the Form item, saved with Process into `exercise.eligibility`; *Dossiers* derived and locked; Details' control and field retired.
4. **The invite list.** Migration `ad2i1_invitees` (the table, the data move); `applydesk/invitees.py`; its search and change routes; the list on the Form under *Invitees*, sharing Create dossiers' typeahead.
5. **Reordering.** Grip handles on a stage's items; ~~the order stored (`stage.item_order`)~~ the gates' order saved as their positions (Status) and read back; a breaking drop undone with its reason; the Outline's empty-invite warning.
   - **Last build rung:** `diff-reviewer` on the cumulative diff from rung 2's base.
6. **Close:** `spec-writer` on `applydesk/spec/`; Status compacted; the plan archived.

## Definition of done

- A new exercise's stage shows only *+Form* and *+Create dossiers* (a test).
- The Form's dropdown saves *Anyone signed in* and *Invitees*, and shows *Dossiers*, locked, after a Create dossiers (tests).
- An invitee added by search and by CSV is listed and audited; Details shows no *Who may apply* (tests).
- A reorder is saved and read back; a breaking one is refused (tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2I` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Whether a dossier's title is offered for a search add** (AD2K's open question) stays with AD2K's close; this segment does not decide it.

## Out of scope

- A Form's submissions creating or joining dossiers, and enforcing the invite list at submit: AD4.
- Reordering across stages (rejected above).

## Doc impact

- `applydesk/spec/applications.md` — Process's add buttons before the first item, the Form's *Who may apply* and invite list, reordering; Details without *Who may apply*.
- `applydesk/spec/architecture.md` — the `invitee` table, the migration, `applydesk/invitees.py`, `timeline_checks.NO_INVITEES` (no `stage.item_order`: Status).
- `applydesk/spec/permissions.md` — the Invitee audience read from the Form's list; the invitee audit events.
- `applydesk/guide/ad2_series.md` — the AD2I row closed (at close).
