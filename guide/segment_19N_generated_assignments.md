# Segment 19N — assignments are always generated

**Opened:** 2026-09-13 · **Theme:** make *"assignments are only ever produced by the rule engine"* true in the code, and give the operator the signal that makes it workable · **Related:** `guide/findings_2026-09-13_spec_discrepancies.md` (`SC-02`, `SC-03`, `SC-09`, `SC-37`…`SC-41`, `CC-04`), `spec/assignments.md`, `spec/rehydrate.md`

## Item 1 — the generated-only contract, and the staleness signal it needs

### Opportunity

The author ruled the contract on 2026-09-13: **assignments are never hand-created, uploaded or edited — always generated. An operator may turn individual rows inactive, and that is the whole of the manual surface, along with the export/import round trip.**

The code does not meet it in four places, and one of those is reachable by an operator today. The pattern is consistent and worth stating once: *a signal or guarantee was specified, switched off for a good local reason, and the gap was then papered over somewhere else.* The clone below, the rehydrate backfill, and `include=True`-on-regenerate are three instances of it.

### Decision

Restore the signal first, then remove the workarounds it was standing in for. Rejected alternative: remove the workarounds first. Without a staleness signal an operator who adds an instrument gets no indication that the generated set is now out of date, so dropping the clone would silently leave a half-configured session — trading a quiet wrong answer for a quieter one.

**And rehydrate is gated off while this segment runs.** Ruled by the author on 2026-09-13, after establishing nobody had used it on real data: *"not ready in the specific sense that not all the possible details are fully worked out, even though unproblematic cases will work."* That is the shape of the risk — nothing in the running app looks wrong, so the gap is invisible until it costs someone data.

Two alternatives rejected. **Leave it live and fix `SC-40` first:** keeps a live silent-data-loss path open while its replacement is designed, which is the pressure that produces a hasty mechanism. **Delete the feature:** discards a built, tested pipeline whose gap is in the unsettled cases rather than the machinery. A flag keeps the 21 existing tests meaningful and makes re-opening a decision rather than a rebuild.

### Semantics — the intended behaviours

**1. Only the rule engine writes `Assignment` rows.** No hand-authoring, no CSV upload, no creation during import, no cloning.

**2. Adding or duplicating an instrument creates no assignment rows.** The new instrument has none until the next generate. This is already the normal state: a new session's Default Instrument has zero assignments until the operator prepares, and nobody treats that as broken. The clone in `create_instrument` is guarded by `if existing:`, so it does nothing before the first generate anyway — it only papers over post-generate inconsistency.

**3. The assignments surface tells the operator when the generated set is stale** — the instruments, rules, roster or relationships have moved since the last generate. `spec/assignments.md` specified this pill; `views/_assignments.py` hardcodes `is_stale = False` because the eligibility helper that fed `compute_staleness` was retired and it would otherwise false-positive every pinned instrument. A signal that cannot be computed correctly must be rebuilt, not left switched off — **this is the prerequisite for (2)**.

**4. Rehydrate loads what legitimate assignments can carry, and hands back the rest.** Assignments are regenerated from the restored rules; a response row is loaded only if it lands on a generated assignment. Every row that cannot — a per-reviewee pairing the rules do not produce, *or* a group-scoped row whose identity does not resolve or whose group has no member assignments — is **dropped and exported as a CSV of dropped responses** for the operator. The restore succeeds.

*Ruled by the author, 2026-09-13, superseding this item's first draft of "fail loudly".* It is the better answer to the same problem: nothing is invented (no backfill, so the generated-only contract holds) and nothing vanishes (the dropped rows come back as data the operator can act on), while a restore whose rules moved since collection still completes instead of becoming un-restorable.

This closes `SC-37` and `SC-40` with one mechanism. `SC-40` is the reason the export must cover **every** unmappable row rather than only per-reviewee pairings: `responses_import.py:295-313` warns and skips group-scoped rows, and `ResponseLoadResult.warnings` is surfaced nowhere — not the `session.rehydrated` audit counts, not the route, not the operator — while `spec/rehydrate.md` §9 claims *"no response is lost"*. **No warning from this loader may remain invisible.** The dropped count belongs in the audit event too.

**5. `created_by_mode` records only values the engine produces**, or is retired. The session-level `assignment_mode` likewise: `session_clone.py:107` copies it from the source, so a pre-16A `manual` propagates into every clone — and a clone carries no assignments, so the mode describes a generation that never happened (`SC-41`). Today it is `String(32)` defaulting to `"manual"` — a value its own enum does not admit — and **nothing reads it**: all five references are writes.

**6. `Assignment.include` is the only operator-writable assignment state.** It *should* round-trip; **the author has deferred that as a future improvement (2026-09-13), so for now the round trip deliberately carries no assignment row status.** Today `include` is carried by no export and reset to `True` whenever assignments regenerate (`spec/rehydrate.md` §9). Behaviour (4) is what makes the deferral safe: an inactivated pair's responses are no longer silently invented a home, and anything that cannot be placed comes back in the dropped-responses CSV.

### Judgment calls — decided

- **2026-09-13.** Staleness before clone-removal, per Decision above.
- **2026-09-13.** Rehydrate gated rather than fixed in place or deleted, per Decision above.
- **2026-09-13.** **404, not a disabled page.** An operator who has never seen this feature should not be told it exists and is being withheld; there is nothing for them to act on.
- **2026-09-13.** **The gate is on all three routes, not the page alone.** Validate and commit accept a POST from anyone who knows the path, so hiding the lobby button would have left the pipeline — and its data-loss case — reachable.
- **2026-09-13.** **The suite runs with the gate open** (`REHYDRATE_ENABLED=true`), so the existing rehydrate tests keep their value. The cost is that every other test then runs with the gate open too, and a flipped default would pass all of them — so the guard reads the default off the `Settings` class rather than the live object.
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

### Status

**2026-09-13.** The ladder gained a **slice 0 the plan did not name**, and it landed first: rehydrate gated off. It came out of the author's question about whether rehydrate was ready — the premise turned out to be wrong (it was shipped, unguarded, with an unconditional lobby button and a spec header reading *"the whole pipeline is live"*), but the instinct behind it was right, and `SC-40` had meanwhile turned out to be live rather than hypothetical. Scope recorded here rather than folded into slice 1 silently.

*`close_check 19N.1` reports **FAIL** while this item is open, and that is correct: C3 names `spec/assignments.md` and `spec/settings_inventory.md` as committed-but-unedited, because the slices that edit them have not shipped. The three specs slice 0 touched pass. It is a close gate — the definition of done requires exit 0 at close, not at every commit.*

Decisions confirmed at build:

- **The backfill's stated reason is obsolete**, established by running rather than reading: a rehydrate of a session whose instrument is unpinned and carries responses reports **0 backfills**. `_generate.py:548` and `:668` still claim unpinned instruments are "skipped silently" and are stale.
- **Two specs asserted the lobby's Rehydrate button is always rendered** (`sessions_overview.md`, `operator_button_audit.md`). The gate falsified both; drift this change created was fixed by it.
- **The first gate test passed for the wrong reason** — an unauthenticated request returns 401 before the gate runs, so a naive "not 200" would have proved nothing. The guard now uses an authenticated client.
- **A mutation run was invalidated by `git checkout`**, which reverted the uncommitted work along with the mutation; two mutations then "passed" against a codebase with no gate. Re-run from an in-memory copy: 5/5 caught, each by the single test that should catch it. This is verbatim the lesson 19K recorded.

### PR ladder

Slices, in dependency order. Sizes to be confirmed when each is cut.

0. **Rehydrate gated off** — ✅ landed. `rehydrate_enabled` ships false, the three routes 404, the lobby button does not render, and the machinery stays covered (the suite sets `REHYDRATE_ENABLED=true`). Ruled by the author after establishing nobody has used it on real data: *not ready in the specific sense that not all the possible details are fully worked out, even though unproblematic cases will work.* Stops `SC-40`'s live exposure so slice 3 is unhurried.
1. **Staleness signal restored** — behaviour (3). Unblocks 2.
2. **Instrument add / duplicate stop writing assignments** — behaviours (1), (2); closes `SC-39`.
3. **Rehydrate loads-and-reports** — behaviour (4); closes `SC-37` and `SC-40`. Includes the dropped-responses CSV and its delivery.
4. **`created_by_mode` defaulted, bound or retired** — behaviour (5); closes `SC-38`.
5. **`assignment_mode` normalized, then the spec follows** — `SC-09` + `SC-41`. The spec edit alone is not enough: legacy `manual` values need resetting to `None` and `session_clone` must stop propagating them, or the forbidden value stays reachable in newly cloned sessions.
6. **Comment follow-ups** — `CC-04`, the two stale `_generate.py` docstrings.

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

- **How is the dropped-responses CSV delivered?** The commit flow redirects to the new session's Home, which a file download does not ride. Options: a stored artefact alongside the session's extracts, a count plus download link on the `rehydrated=1` banner, or a stash the operator collects once. **Decides:** the author, at slice 3.
- **Can `compute_staleness` be given a correct eligible count**, or does the signal need a different basis? **Decides:** the build.

*Answered 2026-09-13 by the author:* `include` round-trip is deferred to a future improvement, so no carrier is needed now (behaviour 6); and rehydrate loads-and-reports rather than failing loudly (behaviour 4).

### Out of scope

- The retired manual-CSV upload route — already gone (16A PR 5); nothing to do.
- **`Assignment.include` round-tripping** — deferred by the author as a future improvement; the round trip carries no assignment row status for now. Recorded so the gap is not mistaken for an oversight.
- `CC-12` (the `test_cascade_ties.py` comment) — unrelated to assignments; stays in the register.

### Doc impact

- `spec/assignments.md` — restore the staleness contract in the form the code can actually compute, and state that only the engine writes assignment rows (Item 1).
- `spec/rehydrate.md` — the header retracts *"the whole pipeline is live"* for the gate; §9 states the dropped-response gap and the contract the feature must meet before the flag opens; §6.3 item 3 follows when slice 3 lands (Item 1).
- `spec/sessions_overview.md` and `spec/operator_button_audit.md` — both asserted the lobby's Rehydrate button is always rendered, which slice 0's gate falsified; each now names the flag (Item 1).
- `spec/settings_inventory.md` — drop `manual` from the session-level `assignment_mode` values (Item 1).
- `guide/findings_2026-09-13_spec_discrepancies.md` — mark `SC-02`, `SC-03`, `SC-09`, `SC-37`, `SC-38`, `SC-39` as they land (Item 1).
- `guide/todo_master.md` — the live-segment entry and its ordering (Item 1).
- `docs/status.md` — row when the item lands.
