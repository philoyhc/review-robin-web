# Segment 20J — An instrument not set up: no Full Matrix default, and Validate refuses it

**Opened:** 2026-11-11 · **Theme:** retire the untouched-link Full Matrix default, and have Validate enforce what the Workflow card already requires of an instrument · **Related:** `guide/segment_23C_diagnostic_status.md`, `spec/assignments.md`, `spec/validate_page.md`, `spec/instruments.md`

## Opportunity

An instrument is set up when it has a visible response field and all three Band 1 links are set (`instruments.is_configured`). Two things do not hold to that:

- **The engine.** An instrument whose links were never set still generates every reviewer against every reviewee: the synthetic Full Matrix, a legacy default from before the links had to be set (author, 2026-11-11). 23C's status showed it on production as "0 complete of 24" for a session nobody had set up.
- **Validate.** Only the Workflow card checks `is_configured`: an instrument not set up leaves the setup incomplete, so the card offers no **Prepare** (`spec/instruments.md`, "off-validate"). Validate raises nothing for a link not set, and only a warning for no visible response field. So `mark_validated` and `activate`, which refuse only on Validate errors, pass a session the card would not prepare.

## Decision

**An instrument not set up has no assignments, and Validate says why** (author, 2026-11-11: "there shouldn't be a usable/reachable full Matrix default for untouched links"; "include the visible response field error too"):

1. **No default.** The engine returns no pairs for an instrument with any Band 1 link not set (`band1_touched_links` short of all three). One choke point: `_diff_one_instrument`, which Generate, the reconcile dry-run and the staleness verdict all run through.
2. **New Validate error `instruments.band1_not_set`**, one per instrument with a link not set, naming the links. Setup gate; its fix link is the instrument's card.
3. **`instruments.no_visible_response_fields` becomes an error.** Its condition is unchanged: it fires once the session has reviewers and reviewees.

**Explicit *All* stays Full Matrix.** All three links set to *All* stores no rule set (`rule_set_id` NULL), and the engine still reads that as every pair. It is the operator's choice, not a default, so the synthetic schema stays, keyed by the touched links rather than by the missing rule set.

**Rejected:**
- **Validate errors alone** (this plan's first draft). The default would stay reachable in draft, by Generate and on the Assignments page (author).
- **Reviving `instruments.no_rule_pinned`.** A NULL `rule_set_id` is still not a gap (explicit *All* stores none). The retired key stays registered for audit history.

## Semantics

- **Generate runs only in draft or validated** (`require_editable`), and asks for acknowledgment when responses would be lost. A draft's stand-in rows go on its next Generate; a live session is never regenerated, so a legacy one keeps its rows until reverted and regenerated.
- **Staleness:** an instrument not set up with stand-in rows reads stale (its target is now empty). One never generated does not.
- **Validate severity is the gate.** `mark_validated` and `activate` already refuse on any error (`has_errors`): no lifecycle code changes.
- **Templates, Quick Setup, Rehydrate and the 23A handoff** seed the default instrument with its links not set, as now. Their sessions generate nothing until the operator sets the links, which the Workflow card already asks for. A pre-gate export with no `band1_touched_links` rehydrates with no assignments.
- **The handoff status** (23C) reports both errors and the empty assignments with no change of its own; `spec/handoffs.md` §10 loses "the Validate rules below do not".

## Judgment calls — decided

- The new rule sits in the Setup gate beside `instruments.no_fields`: it is about the instrument, not its assignments.
- `no_visible_response_fields` keeps its Operations gate and key: a move would rename audit history for no gain.
- Tests that generate on the untouched default set their instrument up through one shared helper, not a fixture that touches links silently, so a test that means "not set up" still can.

## Blast radius (measured)

Taken 2026-11-11 at `ff34c9f`, by a prototype of each change run through the full suite.

| What | Count | Command |
|---|---|---|
| Tests the two Validate errors fail | 12, in 8 files | `pytest -n auto` on the prototype |
| Tests the engine change fails as well | 90 in all, in 26 files | the same, with both |
| Callers of `replace_assignments` outside the package | 3 | `grep -rn "replace_assignments(" app \| grep -v "app/services/assignments"` |
| Live specs mentioning Full Matrix | 11 | `grep -rl "Full Matrix" spec/*.md` |

## Status

**Closed 2026-11-11.** Intended versus done:

- **The ladder grew one change after it opened.** The plan first drafted only the Validate errors; before it merged the author ruled the default must go too (rung 3). Shipped as planned: plan (#3793), the Validate errors (#3794), no default (#3795), close.
- **Rung 3 found two more readers of the default:** the staleness fast path, which counted every pair without the engine, and the reconcile cache, whose stamp now carries whether the links are set (`STAMP_VERSION` v7).
- **A link set or unset became a setup mutation** (from the cold read): `record_band1_links_set` reverts a validated session and writes `instrument.band1_links_set`. Before, a save that changed only which links were set did neither.
- **The engine is not run** for an instrument with a link not set, so its stored rule can neither be walked nor fail Generate.
- **Fixtures departed from the judgment call above:** most set `band1_touched_links` inline (on `ensure_default_instrument`'s result or a direct `Instrument`), the rest through `mark_band1_touched_on_all_instruments`. Either way the setup is explicit in each test, which was the call's point.
- **Rehydrate** of an extract whose instrument never set its links now drops that instrument's responses, reported (`spec/rehydrate.md` §9). Rehydrate is off.
- **A pre-existing test bug** surfaced in rung 2: a builder test's instrument delete never sent its `confirm`, a 400 nobody checked.
- **Reads:** one cold read on the cumulative diff (rungs 2 and 3). It found no remaining path to the default and no weakened test; its five findings (the lifecycle and audit gap, Rehydrate, overclaiming prose, the engine run, plan mismatches) were all acted on in rung 3 or here. `spec-writer` at the close aligned eight specs; three more older Full Matrix lines were fixed here.

## PR ladder

1. **Plan** (this file).
2. **The Validate errors.** The rule and its registration, the gate map, the severity change, `spec/validate_page.md`, the "off-validate" passage of `spec/instruments.md`, `spec/handoffs.md` §10, and the 12 tests (severity pins, the parity snapshots regenerated, three fixtures set up).
3. **No default.** The engine change, the test helper, the 78 further tests, and `spec/assignments.md` § *Synthetic Full Matrix* (explicit *All* only). Last build rung: `diff-reviewer` reads 20J's cumulative diff.
4. **Close.** The other specs' Full Matrix lines, by `spec-writer`.

## Definition of done

- A fresh session's Generate makes no assignments until each instrument's three links are set; with all three set to *All*, every pair (`tests/integration/test_instrument_builder_routes.py`, `tests/unit/test_assignment_staleness.py`).
- An instrument with a link not set, or no visible response field, raises a Validate error, and `mark_validated` and `activate` refuse it (`tests/unit/test_validation_15E_rules.py`, `tests/integration/test_session_lifecycle.py`, `tests/integration/test_instrument_builder_routes.py`).
- The 23C status of a fresh handoff shows `instruments.band1_not_set` under `validation`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20J` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None.

## Out of scope

- **The Workflow card**: it already gates on `is_configured`.
- **Live legacy sessions**: not regenerated (see Semantics).

## Doc impact

- `spec/assignments.md` — no assignments for an instrument not set up; the synthetic Full Matrix is explicit *All* only.
- `spec/validate_page.md` — the rule table: `instruments.band1_not_set`, `no_visible_response_fields` an error, `no_rule_pinned`'s note.
- `spec/instruments.md` — the "Not set" gate is enforced by the engine and Validate as well as the card; "off-validate" goes.
- `spec/handoffs.md` — §10's validation bullet.
- `spec/workflow_card.md` — its Full Matrix line.
- `spec/rehydrate.md` — §9: an extract whose instrument never set its links rehydrates with no assignments for it (rung 3).
- `spec/architecture.md` — its Full Matrix lines.
- `spec/README.md` — its Full Matrix line.
- `spec/lifecycle.md` — the activation note's Full Matrix line (close).
- `spec/rrw_functional_spec.md` — the rule overview's Full Matrix line (close).
- `spec/csv_contracts.md` — the demo template's Full Matrix line (close).
- `guide/todo_master.md` — the queue entry, deleted at close.
