# Segment 23G — A linked instrument Review Robin may extend: *Review Robin Session (custom)*

**Opened:** 2026-11-18 · **Theme:** a second linked-gate type whose instrument starts with the gate's fields, held, and lets Review Robin reorder them, set required, add fields and branch between them · **Related:** `spec/linked_sessions.md` (`instrument_structure`), `spec/instruments.md` ("A linked instrument", "Branching between response fields"), `spec/handoffs.md` (§6a re-send, §10 results), `applydesk/guide/todo_master.md` (ruling 36), `guide/archive/` (23F)

## Opportunity

A gate Apply Desk sends to Review Robin today makes a **linked instrument** that is fixed whole (`instrument_structure`, 23F rung 7): its response fields are the application's, in its order, required as it says, and "a field is never branched" (`spec/linked_sessions.md`). That suits a gate whose results Apply Desk derives from a known set of answers, and stays the default. But an evaluation often wants more than the gate's fields: the author's example is a *Familiarity* rating asked first, with *Score* and *Comments* shown only above a threshold, so an evaluator who barely knows a candidate is not made to score them. Review Robin's instrument editor already does this (two-level branching, `app/services/responses/_branching.py`); the lock forbids it, and Apply Desk's own gate editor should not grow a second branching editor.

## Decision

The author's, 2026-11-18 (ruling 36): **two types of Review Robin gate**.

1. **Review Robin Session** (the default): the instrument locked as 23F made it. Nothing changes.
2. **Review Robin Session (custom)**: the instrument **starts with the gate's response fields**, each **held** (Review Robin may not delete it, nor change its key, label, type, bounds, options or help text, which stay the application's), but Review Robin **may**:
   - **reorder** fields, held and its own alike;
   - **set required or not** on every field (Review Robin's say, not the gate's);
   - **add fields** of its own;
   - **branch between fields** as any instrument does: a held or own parent, governing held or own fields, *Show* or *Require*.

The type is the gate's, chosen on Process, and travels in the handoff; Review Robin keeps it per linked instrument. The rest of the lock stands: one instrument, its rule fixed, its name and description the application's.

Rejected: **unlocking the linked instrument outright**, since Apply Desk reads its results back by the held fields' keys (`spec/handoffs.md` §10) and a deleted or redefined field breaks that contract. **Branching in Apply Desk's gate editor**, sent across: a second branching editor to build and keep in step with Review Robin's, for what Review Robin's operator can already do where the instrument lives.

## Semantics

- **Held vs own.** A held field is one the application sent, known by `field_key`; an own field is one Review Robin added. A held field's row shows the lock glyph on its fixed chips (`spec/ui_elements.md` §9) and has no delete; an own field's row is as any instrument's.
- **Required.** Review Robin's for every field in custom mode; the gate's `required` sets the starting value at the create only, and a re-send never overwrites it.
- **Branching.** As `spec/instruments.md` "Branching between response fields" (two levels, one branch per parent, no cycle); held and own fields may be parents or governed alike.
- **A re-send** (§6a) into a custom instrument updates held fields in place by key, **keeps** own fields, the order and the branches; a newly sent field joins at the end; a held field the re-send drops is deleted, and a branch that loses its parent or a governed field is dropped, **audited** (`instrument.branch_dropped`, reason `field_removed`). A held field whose type changes so its branch no longer fits (a String parent; a value outside new bounds) loses that branch the same way. A field holding responses refuses as today (`ResponsesPresentError`).
- **Results** (§10) carry the **held** fields' answers only, as today. Each held field of a pair is in one of three states, and Apply Desk keeps them apart (author, 2026-11-25):
  - **answered**: a row with its value;
  - **not asked**: a branch closed it on a submitted assignment, a row with no value marked `not_asked` (`closed_by_branch`). Not a response, and nothing owed: it never counts against the evaluator or the gate's progress;
  - **missing**: asked and not answered (an optional field left blank, or the assignment not submitted), no row, as today. Not a response either, but owed while the session is open.

  A derivation reads answers only, so both leave a mean's `at_least` short; the result's note says which, e.g. "4.2 from 3 of 5 · 2 not asked". Own fields' answers stay in Review Robin (its own extracts); returning them is out of scope.
- **Switching type** on a linked draft not yet opened: *custom → default* drops own fields and branches and restores the gate's order and required, audited; *default → custom* keeps everything. Once the session opens, the type is fixed (ruling 29's re-send window).
- **Not linked, or another profile**: nothing changes; the mode exists only under `instrument_structure`.

## Judgment calls — decided

- The mode is a column on the instrument (`linked_mode`: `locked` / `custom`), not a new `Lock` member: the lock is per profile, the type per gate.
- The handoff carries it as one Settings row, `instruments[1].linked_mode`, owned by the application like the instrument's name.
- Held fields are known by key, not by a flag copied onto the field, so a re-send that renames nothing needs no migration of field rows.
- **Renamed** *Review Robin (advanced)* → *Review Robin Session (custom)*, mode `advanced` → `custom` (author, 2026-11-25); the default reads *Review Robin Session*, as Apply Desk's gate type does. Nothing was built under the old name.

## Blast radius (measured)

Taken 2026-11-18 at `295cdf575`.

- `app/services/linked_instruments.py` (293 lines: `owns_row`, `apply_owned`, `set_up`); `app/services/instruments/_band2.py:1175` `replace_response_fields` (unbranches every field today).
- References to the lock or the fixed rendering: `grep -rn "refuse_linked_structure\|INSTRUMENT_STRUCTURE\|data-linked-fixed\|linked_instruments" app --include=*.py --include=*.html | wc -l` → 36, across `app/services/{handoffs,linked_settings,linked_apps}.py`, `app/services/instruments/{_instrument_crud,_display_fields}.py`, `app/web/routes_operator/{_instruments,_instruments_band2,_instruments_pagination,_quick_setup,_shared}.py`, `app/web/templates/operator/instruments_index.html`, `app/web/templates/base.html`.
- Tests: `tests/integration/test_linked_sessions.py`, `tests/integration/test_chip_edge.py`, `tests/unit/test_linked_sessions_spec.py`.
- Apply Desk: `applydesk/stages.py` (`Gate.via`), `applydesk/templates/applydesk/operator/_process_cards.html` (the gate card), `applydesk/extract.py` (`process.csv` detail).

## PR ladder

1. **Plan** (this file), its queue entry and README row; ruling 36 in `applydesk/guide/todo_master.md`.
2. **The mode, stored and sent**: `Instrument.linked_mode` (migration, default `locked`), the handoff's `instruments[1].linked_mode` row (owned, validated, audited), `set_up` taking it. No page change. Must not touch the editor.
3. **What custom allows**: the refusals and the fixed rendering by mode: held rows fixed and undeletable, own rows and +, ⑂, reorder and required live; the card's Save and the response-field routes accept them. Integration and Chromium tests on a linked custom instrument.
4. **The re-send into custom**: `replace_response_fields` keeping own fields, order, branches and required; broken branches dropped and audited; switching type on an unopened draft.
5. **Results**: held answers only; a `not_asked` row for a held field a branch closed (`spec/handoffs.md` §10). `diff-reviewer` reads 2–5.
6. **Apply Desk**: the gate's *Type* on Process (*Review Robin Session* / *Review Robin Session (custom)*), shown on the gate card and Evaluations, in `process.csv`; a result's note telling *not asked* from *missing*; sample only, as Apply Desk sends nothing until AD5.
7. **Close**, after the author's check.

## Definition of done

- A linked instrument sent as custom lets Review Robin reorder, require, add and branch, and refuses deleting or redefining a held field (tests, Chromium tests).
- A re-send keeps own fields, order, branches and required, dropping only what it must, audited (tests).
- Results carry held answers and a `not_asked` row where a branch closed one; Apply Desk's note tells *not asked* from *missing* (tests).
- Apply Desk's Process offers the two types (tests).
- The author has used both types locally and approved them.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 23G` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Who sets *Required* on a held field?** Review Robin, as ruling 36 says: the gate's value is the start only (author, 2026-11-25, given what a fixed *Required* costs a branched instrument).
- **Own fields' answers back to Apply Desk** (a *Familiarity* worth showing on the dossier?): proposed later, Review Robin's extracts only; the author's.
- **May a held field be hidden** (`visible`) in custom mode, or only branched? Proposed: its visibility stays the application's.
- **Apply Desk's derivations over a branched field**: *not asked* and *missing* kept apart, neither a response (author, 2026-11-25; Semantics, "Results").

## Out of scope

- **Branching in Apply Desk's own gate editor**: rejected above.
- **Own fields' answers in Apply Desk's results**: an open question, later if wanted.
- **Native (unlinked) instruments**: unchanged.

## Doc impact

- `spec/linked_sessions.md` — `instrument_structure`: the two modes and what custom allows, refuses and holds; the coupled-locks note.
- `spec/instruments.md` — "A linked instrument": held vs own fields in custom mode, their rendering and routes.
- `spec/handoffs.md` — §6a re-send into a custom instrument; §10 results' `not_asked` row; the `linked_mode` row.
- `spec/csv_contracts.md` — the Settings CSV's `instruments[1].linked_mode` row.
- `applydesk/spec/applications.md` — the gate's *Type* on Process.
- `guide/todo_master.md` — the queue entry (rung 1); deleted at close.
- `guide/README.md` — this plan's row (rung 1); moved to the archive's index at close.
