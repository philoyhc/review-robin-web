# Segment 19N — assignments are always generated

**Opened:** 2026-09-13 · **Theme:** make *"assignments are only ever produced by the rule engine"* true in the code, and give the operator the signal that makes it workable · **Related:** `guide/findings_2026-09-13_spec_discrepancies.md` (`SC-02`, `SC-03`, `SC-09`, `SC-37`, `SC-38`, `SC-39`, `CC-04`), `spec/assignments.md`, `spec/rehydrate.md`

## Item 1 — the generated-only contract, and the staleness signal it needs

### Opportunity

The author ruled the contract on 2026-09-13: **assignments are never hand-created, uploaded or edited — always generated. An operator may turn individual rows inactive, and that is the whole of the manual surface, along with the export/import round trip.**

The code does not meet it in four places, and one of those is reachable by an operator today. The pattern is consistent and worth stating once: *a signal or guarantee was specified, switched off for a good local reason, and the gap was then papered over somewhere else.* The clone below, the rehydrate backfill, and `include=True`-on-regenerate are three instances of it.

### Decision

Restore the signal first, then remove the workarounds it was standing in for. Rejected alternative: remove the workarounds first. Without a staleness signal an operator who adds an instrument gets no indication that the generated set is now out of date, so dropping the clone would silently leave a half-configured session — trading a quiet wrong answer for a quieter one.

### Semantics — the intended behaviours

**1. Only the rule engine writes `Assignment` rows.** No hand-authoring, no CSV upload, no creation during import, no cloning.

**2. Adding or duplicating an instrument creates no assignment rows.** The new instrument has none until the next generate. This is already the normal state: a new session's Default Instrument has zero assignments until the operator prepares, and nobody treats that as broken. The clone in `create_instrument` is guarded by `if existing:`, so it does nothing before the first generate anyway — it only papers over post-generate inconsistency.

**3. The assignments surface tells the operator when the generated set is stale** — the instruments, rules, roster or relationships have moved since the last generate. `spec/assignments.md` specified this pill; `views/_assignments.py` hardcodes `is_stale = False` because the eligibility helper that fed `compute_staleness` was retired and it would otherwise false-positive every pinned instrument. A signal that cannot be computed correctly must be rebuilt, not left switched off — **this is the prerequisite for (2)**.

**4. Rehydrate refuses rather than inventing.** A responses row naming a (reviewer, reviewee, instrument) pairing the restored rules do not generate fails the restore, names the pairings, and leaves no session behind — the all-or-nothing hard delete already holds. It must reach the operator as a readable message on the Validate page, not as an unhandled 500, which is what every commit-time `RehydrateError` currently produces.

**5. `created_by_mode` records only values the engine produces**, or is retired. Today it is `String(32)` defaulting to `"manual"` — a value its own enum does not admit — and **nothing reads it**: all five references are writes.

**6. `Assignment.include` is the only operator-writable assignment state, and it survives the round trip.** Today it is carried by no export and reset to `True` whenever assignments regenerate (`spec/rehydrate.md` §9 admits this). Until it round-trips, half the author's contract is unmet — and this is the case the rehydrate backfill in (4) was the safety net for, which is why (6) is sequenced with (4) rather than after it.

### Judgment calls — decided

- **2026-09-13.** Staleness before clone-removal, per Decision above.
- **2026-09-13.** `SC-39`'s two clone paths are *not* split by "add" vs "duplicate": `create_instrument` (the everyday `+Instrument`) and `replicate_instrument` (duplicate) get the same treatment, because the same premise backs both — *"the tuples are identical across instruments today"* — and that premise is already false for `is_self_review`, which the code recomputes immediately after cloning.

### Blast radius (measured)

At `f60ca533`, 2026-09-13:

| What | Count | Command |
|---|---|---|
| `Assignment(...)` construction sites in `app/` | **4** — 1 engine, 1 rehydrate backfill, 2 instrument clones | `grep -rn "Assignment(" app/ --include=*.py \| grep -v "class Assignment"` |
| References to `created_by_mode` in `app/` | **5**, all writes | `grep -rn "created_by_mode" app/ --include=*.py` |
| Test files seeding `created_by_mode="manual"` | **14** files, 16 occurrences | `grep -rl 'created_by_mode="manual"' tests/ --include=*.py` |
| POST routes on the assignments surface | **5** — generate, delete-all, bulk-activate, bulk-inactivate, per-instrument self-review toggle | `grep -c "@router.post" app/web/routes_operator/_assignments.py` |
| Specs mentioning assignments | **33** | `grep -rln "assignment" spec/*.md` |

**Established by running, not reading:** rehydrating a session whose instrument is unpinned (Full Matrix) and carries responses reports **0 backfills** — so the backfill's stated reason in the step-5 comment, *"default Full-Matrix instruments"*, is obsolete. Since Wave 5 PR 5.3 every instrument is a target and a NULL `rule_set_id` is treated as Full Matrix at the diff site; `_generate.py:548` and `:668` still say unpinned instruments are "skipped silently" and are stale.

### PR ladder

Slices, in dependency order. Sizes to be confirmed when each is cut.

1. **Staleness signal restored** — behaviour (3). Unblocks 2.
2. **Instrument add / duplicate stop writing assignments** — behaviours (1), (2); closes `SC-39`.
3. **Rehydrate refuses, readably** — behaviour (4); closes `SC-37`. Includes the commit-route error surfacing.
4. **`created_by_mode` defaulted, bound or retired** — behaviour (5); closes `SC-38`.
5. **Spec + comment follow-ups** — `SC-09`, `CC-04`, the two stale `_generate.py` docstrings.

`include` round-trip (behaviour 6) is unscheduled pending the open question below.

### Definition of done

- Each behaviour in Semantics is either shipped or explicitly deferred with a reason.
- No `Assignment` row can be created by any path other than the rule engine, or the exception is named in `spec/assignments.md`.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19N.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added

### Open questions

- **Does `include` round-trip, and through what carrier?** There is no assignments extract at all today. Adding one is a new CSV contract; adding an `include` column to an existing extract is smaller but stretches that file's meaning. **Decides:** the author.
- **Does behaviour (4) need an operator escape hatch?** Failing loudly makes an extract whose rules changed after collection un-restorable until someone edits it. **Decides:** the author.
- **Can `compute_staleness` be given a correct eligible count**, or does the signal need a different basis? **Decides:** the build.

### Out of scope

- The retired manual-CSV upload route — already gone (16A PR 5); nothing to do.
- `CC-12` (the `test_cascade_ties.py` comment) — unrelated to assignments; stays in the register.

### Doc impact

- `spec/assignments.md` — restore the staleness contract in the form the code can actually compute, and state that only the engine writes assignment rows (Item 1).
- `spec/rehydrate.md` — §6.3 item 3 and §9: rehydrate refuses rather than backfilling; restate what does and does not round-trip (Item 1).
- `spec/settings_inventory.md` — drop `manual` from the session-level `assignment_mode` values (Item 1).
- `guide/findings_2026-09-13_spec_discrepancies.md` — mark `SC-02`, `SC-03`, `SC-09`, `SC-37`, `SC-38`, `SC-39` as they land (Item 1).
- `docs/status.md` — row when the item lands.
