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

**2026-09-13, slice 1 — staleness signal restored.** Closes `SC-02` and `SC-03`. The open question *"can `compute_staleness` be given a correct eligible count"* is answered **no, and it did not need one**: the basis moved to the engine's own reconcile diff. The retired predicate was wrong in two ways beyond the missing count — it compared totals, so a rule change swapping one pair for another read as fresh, and it gated on `rule_id is not None`, so unpinned Full-Matrix instruments were invisible. **Cost measured rather than assumed: 10 queries for 5 instruments over a 10×10 roster** — linear in instruments, independent of roster size. Three dead consumers revived, the third being `instruments.stale_generated`, a **registered no-op** with a severity, a fix link and a `why` describing the situation it no longer detected. Two tests that pinned the retirement were reversed, and `eligible_count` — a field promising "pairs the engine would produce" and fed by a dict that was never populated — now carries a real figure from the same walk.

**The spec-writer pass found my own spec sentence claiming two things that do not ship**, and both were removed rather than built. There is no "Pairs may be stale" page badge — only the per-instrument pill — and the Next Action card does not offer Generate: `compute_next_action_generate_state` is wired to no route. 15B Slice 4 wired it; `1a5b8608` (*"strip unused imports"*) unwired it, and nothing noticed. Restoring staleness made its `"generate"` branch reachable **in tests**, which is what exposed that it is reachable nowhere else. Registered as `SC-43` — wire or retire — rather than fixed here: the signal ships on two live surfaces, so this is an extra affordance, not a gap. *A spec asserting a consumer that does not exist is the defect this segment keeps cataloguing, written by the person cataloguing it.*

**2026-09-13, slice 2 — instrument add and duplicate stop writing assignments.** Closes `SC-39`. The spec had **never documented the clone**: neither `+Instrument`'s side-effects list nor `Replicate`'s clone list mentioned assignment rows, so the code was doing something unsaid. The silence is now explicit. What the build turned up: **eleven reviewer-surface tests silently depended on the clone as fixture setup** — their own comment read *"`instruments/add` clones full-matrix assignments onto the new instrument automatically, so no manual Assignment seeding is needed"* — and they now regenerate, which is what the operator does. That exposed a second thing: the generate route requires `confirm_replace` once rows exist, so the fixtures' later generate had been a **no-op redirect**, invisible while the clone was quietly supplying the rows.

**And the spec-writer pass caught me writing a false claim again, one slice after the last one.** My `+Instrument` bullet said a new instrument "flags the session **stale**". It does not, on three counts: slice 1 deliberately excludes never-generated instruments, so its own `is_stale` is always `False`; siblings do not go stale either, because adding an instrument changes none of their inputs; and there is no session-level badge, as slice 1 itself established. The carriers are the page's **not generated** state and `assignments.instrument_empty` on Validate. *Twice now the error has been the same shape — asserting a consumer or a signal that does not exist — and both times the checker found it, not me.*

**2026-09-13, slice 5 — `assignment_mode` normalized, and it was a live bug.** Closes `SC-09` and `SC-41`. `session_clone.py` copied the source's `assignment_mode` into a clone that carries **no** `Assignment` rows, so the clone claimed a generation that never happened. NULL is this codebase's marker for never-Generated — `replace_assignments` sets the column, delete-all clears it, and **three validation rules skip on NULL** so a session with no pairs is not *also* told every reviewer is missing. The clone defeated that skip: a test written before the fix failed with `assignments.reviewer_missing` sitting beside `assignments.no_included_pairs`, which is exactly the doubled noise the skip exists to prevent. Codex had flagged this as legacy-`manual` propagation; the propagation is real but it is the smaller half. `roundtrip_coverage.md` had documented the copy as *"clone-only by design"* — on inspection that sentence explains why the **Settings CSV** drops the column, and never argues the clone should carry it.

Decisions confirmed at build:

- **The backfill's stated reason is obsolete**, established by running rather than reading: a rehydrate of a session whose instrument is unpinned and carries responses reports **0 backfills**. `_generate.py:548` and `:668` still claim unpinned instruments are "skipped silently" and are stale.
- **Two specs asserted the lobby's Rehydrate button is always rendered** (`sessions_overview.md`, `operator_button_audit.md`). The gate falsified both; drift this change created was fixed by it.
- **The first gate test passed for the wrong reason** — an unauthenticated request returns 401 before the gate runs, so a naive "not 200" would have proved nothing. The guard now uses an authenticated client.
- **A mutation run was invalidated by `git checkout`**, which reverted the uncommitted work along with the mutation; two mutations then "passed" against a codebase with no gate. Re-run from an in-memory copy: 5/5 caught, each by the single test that should catch it. This is verbatim the lesson 19K recorded.

**2026-09-13, slice 6 — the two stale `_generate.py` docstrings, and five false claims of my own.** Closes `CC-04`. Both paragraphs still said unpinned instruments are "skipped silently", describing pre-5.3 behaviour; both also claimed scoped generation "raises `ValueError` if the instrument has no rule pinned", which no code does — the only `ValueError` is *not found in session*. **Three of the five corrections were in prose this slice had just written**, caught by the spec-writer pass, not by me: a rewritten opening that contradicted its own next sentence, a zero-targets note describing a gate that no longer exists, and a `docs/status.md` value list reading as three current values when `AssignmentMode` has one member. The provenance paragraph I had added — *"this said X until Segment 19N"* — went too; a docstring recording what it used to say is history, and the reason survives without it.

*Third time in one segment that the error was the same shape and the checker found it. The shape is now specific enough to name: **prose written from the surrounding prose rather than from the file it describes**, which is exactly what the spec-writer brief warns about, and my rewrites are no more exempt than the code's.*

**2026-09-13, slice 3a — responses load or drop; nothing is fabricated to fit.** Half of `SC-37` / `SC-40`; the delivery half stays open. The find-or-create backfill is gone: a row naming a pair generation did not produce is dropped with a reason, and `serialize_dropped_responses` renders the set under the upload's own header plus `DropReason`. **What the build turned up is that the drop was already happening** — seven `continue` sites each appended to `ResponseLoadResult.warnings`, and *nothing ever read that list*. The orchestrator ignored it; no route, audit event or page saw it. So the dropped CSV replaces the warnings list rather than joining it, and `counts.assignments_backfilled` becomes `counts.responses_dropped` — the audit event was reporting the fabrication count where the interesting number was always the loss.

The retired-behaviour test (`test_per_reviewee_backfills_missing_assignment`) is reversed, as slice 1's two were. 5 mutations, 5 caught; the first pass left padding and truncation alive, and the test that now kills both had to reach `serialize_dropped_responses` through its public dataclass, because `parse_responses_csv` rejects short rows and so cannot produce the case.

*Undeclared spec impact:* `spec/README.md`'s rehydrate row summarised the pipeline as *"assignment regenerate + backfill"*. Bullet added.

**Blocked, not deferred:** the CSV is produced and discarded. Delivery is the open question below, and it is the last thing standing between rehydrate and its gate opening. `app/services/rehydrate_stash.py` — operator-scoped, 1h TTL, Postgres-backed, built for exactly the Validate → Commit hand-off this CSV has to cross — already exists, which makes the stash option cheaper than it looked when the question was written.

### PR ladder

Slices, in dependency order. Sizes to be confirmed when each is cut.

0. **Rehydrate gated off** — ✅ landed. `rehydrate_enabled` ships false, the three routes 404, the lobby button does not render, and the machinery stays covered (the suite sets `REHYDRATE_ENABLED=true`). Ruled by the author after establishing nobody has used it on real data: *not ready in the specific sense that not all the possible details are fully worked out, even though unproblematic cases will work.* Stops `SC-40`'s live exposure so slice 3 is unhurried.
1. **Staleness signal restored** — behaviour (3). Unblocks 2.
2. **Instrument add / duplicate stop writing assignments** — behaviours (1), (2); closes `SC-39`.
3. **Rehydrate loads-and-reports** — behaviour (4); closes `SC-37` and `SC-40`. Includes the dropped-responses CSV and its delivery.
4. **`created_by_mode` defaulted, bound or retired** — behaviour (5); closes `SC-38`.
5. **`assignment_mode` normalized, then the spec follows** — `SC-09` + `SC-41`. The spec edit alone is not enough: ~~legacy `manual` values need resetting to `None`~~ and `session_clone` must stop propagating them, or the forbidden value stays reachable in newly cloned sessions. *The data migration is struck (2026-09-13, author): historic sessions are dispensable at this stage, so a legacy row keeping `manual` costs nothing. `spec/settings_inventory.md` states that a reader must tolerate the value rather than pretending it cannot occur. Stopping the clone was the half that mattered — it was minting new ones.*
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
- `spec/README.md` — the rehydrate row's pipeline summary names the backfill the slice-3 drop replaces (Item 1).
- `guide/findings_2026-09-13_spec_discrepancies.md` — mark `SC-02`, `SC-03`, `SC-09`, `SC-37`, `SC-38`, `SC-39` as they land (Item 1).
- `guide/todo_master.md` — the live-segment entry and its ordering (Item 1).
- `docs/status.md` — row when the item lands.
