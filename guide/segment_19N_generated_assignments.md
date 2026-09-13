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

**Established by running, not reading:** rehydrating a session whose instrument is unpinned (Full Matrix) and carries responses reports **0 backfills** — so the backfill's stated reason in the step-5 comment, *"default Full-Matrix instruments"*, is obsolete. Since Wave 5 PR 5.3 every instrument is a target and a NULL `rule_set_id` is treated as Full Matrix at the diff site; `_generate.py:548` and `:668` still said unpinned instruments were "skipped silently" — *both fixed by slice 6.*

### Status

**Closed 2026-09-13.** Seven PRs. Ladder landed in order but for slice 0, which the plan did not name and which shipped first; slice 3 split into 3a (load-or-drop) and 3b (delivery) once the author's answer on the CSV arrived.

**Intended vs done.** All six behaviours shipped. The load-bearing outcome is checkable in one command: `app/services/` holds exactly one `Assignment(...)` constructor, `_generate.py:445`, reachable only through `replace_assignments`. Rung 5's legacy-row data migration is struck — *"don't worry about historic sessions, they are still dispensable at this point"* (author); `spec/settings_inventory.md` tells a reader to tolerate a stored `manual` rather than pretend it cannot occur. `rehydrate_enabled` **stays false**: the data-loss defect that prompted the gate is fixed, but the author's reason was broader — nobody has run the pipeline on real data.

**Decisions confirmed at build:**

- **`compute_staleness` did not need a correct eligible count** — the basis moved to the engine's own reconcile diff. The retired predicate compared totals (so a rule swapping one pair for another read as fresh) and gated on `rule_id is not None` (so unpinned Full-Matrix instruments were invisible). Cost measured, not assumed: **10 queries for 5 instruments over a 10×10 roster**.
- **The rehydrate backfill's stated reason was obsolete**, established by running: a rehydrate of a session with an unpinned instrument carrying responses reports **0 backfills**.
- **Three paths wrote assignment rows outside the engine**, none of them visible as such: the instrument clone, the session clone's `assignment_mode` copy (a live bug — it defeated the NULL-means-never-generated skip that stops a pairless session *also* being told every reviewer is missing), and the rehydrate backfill.
- **The pre-flight analyzer already rejects four of the eight drop reasons**, so only the four it cannot pre-check can reach a commit.

**What this item kept finding, including in its own prose.** A signal specified, switched off for a good local reason, and papered over by something nearby that looks like cover: a *registered no-op* validation rule with a severity and a fix link; eleven reviewer-surface tests whose `generate` had been a no-op redirect the instrument clone was quietly supplying rows for; a `ResponseLoadResult.warnings` list appended to at seven sites and **read by nothing**; `?rehydrated=1` written by a redirect and **read by nothing**.

Four times the failure was the same shape — **prose asserting a consumer that does not exist** — and the checker found it each time, not me: a "Pairs may be stale" badge and a Next Action Generate offer (slice 1, → `SC-43`); a new instrument "flags the session stale" (slice 2); three false claims in docstrings written minutes earlier (slice 6); and the plan's own option list proposing a download link on a banner that was never built (slice 3b). The cause is identical in all four: **prose written from the surrounding prose rather than from the file it describes.**

**Two process findings worth more than the code.** `close_check` passed throughout while **three specs were edited without a Doc impact bullet** — C3 asks whether every *declared* path was edited, never whether every *edited* path was declared, so the manifest's completeness rests on the author noticing. And a mutation run was invalidated by `git checkout` reverting uncommitted work along with the mutation; re-run from an in-memory copy, 5/5 caught. That is verbatim the lesson 19K recorded, repeated.

**Carried out of this item:** `SC-43` (an unwired next-action resolver — wire or retire), `SC-44` (should a rehydrate audit its observer / relationship / assignment counts?), and a `tools/` follow-up for `close_check`'s one-directional manifest check.

### PR ladder

Slices, in dependency order. Sizes to be confirmed when each is cut.

0. **Rehydrate gated off** — ✅ landed. `rehydrate_enabled` ships false, the three routes 404, the lobby button does not render, and the machinery stays covered (the suite sets `REHYDRATE_ENABLED=true`). Ruled by the author after establishing nobody has used it on real data: *not ready in the specific sense that not all the possible details are fully worked out, even though unproblematic cases will work.* Stops `SC-40`'s live exposure so slice 3 is unhurried.
1. **Staleness signal restored** — ✅ landed. — behaviour (3). Unblocks 2.
2. **Instrument add / duplicate stop writing assignments** — ✅ landed. — behaviours (1), (2); closes `SC-39`.
3. **Rehydrate loads-and-reports** — ✅ landed as 3a + 3b. — behaviour (4); closes `SC-37` and `SC-40`. Includes the dropped-responses CSV and its delivery.
4. **`created_by_mode` defaulted, bound or retired** — ✅ landed (defaulted). — behaviour (5); closes `SC-38`.
5. **`assignment_mode` normalized, then the spec follows** — ✅ landed. — `SC-09` + `SC-41`. The spec edit alone is not enough: ~~legacy `manual` values need resetting to `None`~~ and `session_clone` must stop propagating them, or the forbidden value stays reachable in newly cloned sessions. *The data migration is struck (2026-09-13, author): historic sessions are dispensable at this stage, so a legacy row keeping `manual` costs nothing. `spec/settings_inventory.md` states that a reader must tolerate the value rather than pretending it cannot occur. Stopping the clone was the half that mattered — it was minting new ones.*
6. **Comment follow-ups** — ✅ landed. — `CC-04`, the two stale `_generate.py` docstrings.

`include` round-trip (behaviour 6) is deferred by the author as a future improvement — see Out of scope.

### Definition of done

- Each behaviour in Semantics is either shipped or explicitly deferred with a reason.
- No `Assignment` row can be created by any path other than the rule engine, or the exception is named in `spec/assignments.md`.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19N.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added

### Open questions

- ~~**How is the dropped-responses CSV delivered?**~~ **Answered at slice 3b:** the commit stops rather than redirecting when rows were dropped, and the CSV rides the existing `rehydrate_stash`. The banner option was unbuildable as written — `?rehydrated=1` is read by nothing.
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
- `spec/instruments.md` — `+Instrument` and `Replicate` no longer clone assignment rows; the side-effect lists said nothing about them either way (Item 1).
- `spec/roundtrip_coverage.md` — the `assignment_mode` row's *"clone-only by design"* line explained the Settings CSV, not the clone, and read as a defence of it (Item 1).
- `spec/reconciling_regeneration.md` — the `created_by_mode` section states that a column default must never name a mechanism that cannot write (Item 1).
- `guide/findings_2026-09-13_spec_discrepancies.md` — mark `SC-02`, `SC-03`, `SC-09`, `SC-37`, `SC-38`, `SC-39` as they land (Item 1).
- `guide/todo_master.md` — the live-segment entry and its ordering (Item 1).
- `docs/status.md` — row when the item lands.

---

## Item 2 — one email fold, not two

### Opportunity

`email_identity.normalize_email` is `.strip().casefold()`, and its
docstring says to use it *"at **every** identity-comparison site so the
uniqueness gate that rejects a duplicate on write and the access gate
that grants a surface on read use one convention."* The convention is
not one. **Ten-plus sites compare SQL-side** with `func.lower(column)`:

| file | line(s) |
|---|---|
| `app/services/users.py` | 479 |
| `app/services/participants.py` | 94, 102, 118 |
| `app/services/assignments/_coverage.py` | 296, 360, 368 |
| `app/services/audit.py` | 894 |
| `app/web/routes_operator/_session_home.py` | 625 |
| `app/web/routes_reviewer/_dashboard.py` | 100 |

Several compare a `func.lower` column against a value already folded in
Python, so the two conventions meet inside one expression.

`lower()` and `casefold()` agree on ASCII and **diverge on real
inputs** — German ß folds to `ss` under casefold but not under lower;
Turkish İ likewise — and `func.lower` does not strip. So a roster row
and its access check can fold differently: a legitimate participant
refused entry to a surface they are on, or a duplicate slipping past the
uniqueness gate that exists to catch it.

Nothing has failed in production, because the rosters seen so far are
ASCII. That is why this is an opportunity and not an incident.

### Decision

**`str.lower`, applied in Python, and the fold never enters SQL.**
Ruled by the author 2026-09-13, on the recommendation below.

**Rejected: casefold everywhere** — the answer the Open Questions
leaned toward, and the dangerous one. Casefold is the Unicode-correct
fold for caseless *search*; identity is not search. It maps `ß` to
`ss`, so `straße@example.com` and `strasse@example.com` — two
different mailboxes — become one key, and that key decides access at
the three `web/deps.py` gates, at `auth.roles.is_super_admin`, at the
reviewer dashboard's roster match and at invite acceptance.

**The first draft of this Decision was wrong about the direction, in
the safe-sounding direction.** It said the pre-fix state failed
*closed* — a `ß` holder cannot match their own lower-cased row — and
concluded there was no pressure to choose quickly. That is one of two
pairings. The other was never checked: a `ß` holder's casefolded key
matches an unrelated **`ss`-spelled** row exactly, at every gate
above, because casefold was applied consistently on both sides there.
So a real fail-open existed. Low likelihood in an ASCII tenancy and no
evidence it occurred, but the reassurance was unearned and is
withdrawn.

**Rejected: fold inside SQL.** It cannot be made trustworthy here,
and measuring it turned out to be worse than the argument that
predicted it. Against Postgres 16 stood up in the sandbox, SQLite, and
CPython:

| input | Python `.lower()` | Postgres `lower()` | SQLite `lower()` |
|---|---|---|---|
| `ÄÖÜ` | `äöü` | `äöü` | `ÄÖÜ` — unchanged |
| `İstanbul` | `i̇stanbul` (9 chars, `i` + U+0307) | `istanbul` (8) | `İstanbul` — unchanged |

**Two hazards, not one.** SQLite's `lower()` is ASCII-only, so a
`func.lower` comparison means one thing in the suite and another in
production — a test pinning it would assert two different things in
the two CI jobs. *And* Python and Postgres disagree on `İ`, so the two
sides of one comparison can disagree **in production**, where no test
can show it. The second was not predicted; it was found by measuring
rather than asserting, after the first draft of this Decision shipped
the Postgres half as a claim.

**Deferred: the stored normalized column.** Fold in Python at write,
compare with `==`, index it. That is the design that puts non-ASCII
identity back in scope, and it is a migration across `users`,
`reviewers`, `reviewees` and `observers` plus a write-path invariant —
a segment, not an item. Nothing justifies it yet: **the institution's
MS365 tenancy is not expected to produce non-ASCII addresses**
(author, 2026-09-13). This item is future-proofing the *failure
direction*, not fixing a live incident.

### Semantics

- **Every ASCII identity** — Python and SQL now agree, because
  `str.lower` and `lower()` agree on ASCII in both dialects. That is
  every identity this deployment has, and it is what makes the dozen
  `func.lower(column)` comparisons correct rather than accidentally
  correct.
- **`ß` and `ss`** — distinct identities, permanently. Not a gap to
  close later; closing it would be the fail-open above.
- **Other non-ASCII case** (`Ä`, `İ`) — out of scope *by
  construction*, not by neglect: the comparison happens in SQL, where
  the dialects disagree. The stored-column design above is what would
  bring it in.
- **The local part** — lower-cased, which RFC 5321 does not licence
  (local parts are case-sensitive there). Every mail system ignores
  that and users expect it. A deliberate concession, recorded in
  `docs/security_posture.md` rather than left implicit.

### Judgment calls — decided

- **`normalize_email` changed rather than adding a second helper**
  (2026-09-13). Two folds side by side is the condition this item
  exists to end; a `normalize_email_strict` would recreate it.
- **No SQL-side site changed.** They already use `lower`. Moving the
  fold to Python at a dozen call sites would cost the index and buy
  nothing once both sides agree.
- **The module docstring's claim was corrected, not just the code.**
  It said folding through `normalize_email` meant write-time and
  read-time "can never disagree". The SQL-side sites never folded
  through it, so that was false when written and is the claim `SC-45`
  actually found.

### Blast radius (measured)

Re-run at close, 2026-09-13. Every line states the raw figure the
command returns **and** what to subtract, because three attempts at
this block published numbers that did not reproduce:

```
grep -rn "normalize_email(" app/ --include=*.py | grep -v "def "
  -> 58 invocations, 20 files

grep -rn "func\.lower" app/ --include=*.py
  -> 15 lines; 2 are prose in email_identity.py's docstring, 13 code

grep -rn "\.casefold()" app/ --include=*.py
  -> 23 lines; 1 is prose in email_identity.py's docstring, 22 code,
     none in a gate module except the `not-identity:`-marked tag
     search in assignments/_coverage.py

grep -rc "normalize_email" tests/ --include=*.py
  -> 0 before this item; the fold had no direct coverage at all
```

**Three wrong versions of this block, each correcting the last.**
"14 call sites" reconciled to nothing the command produces. The
correction published `func.lower` and `.casefold()` counts taken
*before* the fix rather than after. The correction of *that* disclosed
the 2 prose lines in the `func.lower` figure and silently omitted the
1 prose line in the `.casefold()` figure — so "22" still did not
reproduce from the command printed beside it. Stated raw-then-adjusted
here so the reader can run the command and land on the same place.

**And it measured the wrong thing**, which cost more than the bad
number. Counting what *calls* `normalize_email` says nothing about
what bypasses it. Four identity comparisons folded inline —
`auth/roles.py` (super-admin), `routes_reviewer/_dashboard.py`,
`routes_reviewer/_invite.py`, and two `assignments/_coverage.py`
handle filters — so changing one function body did not reach them.
The `.casefold()` grep is the one that would have shown it, and it was
not run until the verification pass asked why the gates still merged.
All four are now routed through the fold, and
`test_no_identity_gate_folds_inline` makes that structural: a bare
`.casefold()` in a gate module fails unless the line above it says
`not-identity:` and why.

### PR ladder

1. The one-line fold change, its docstring, the module docstring's
   false claim, and the first tests `normalize_email` has ever had.

### Definition of done

- `normalize_email` folds with `str.lower`, and its docstring says why
  casefold was rejected.
- `straße@` and `strasse@` are asserted **distinct**, with the premise
  (that casefold would merge them) asserted alongside so the test
  cannot quietly stop testing anything.
- Python and SQLite folds asserted equal on ASCII identities.
- The SQLite/Postgres `lower()` divergence pinned in a form true on
  both dialects.
- `docs/security_posture.md` records the convention and the RFC 5321
  concession.

### Out of scope

- Non-ASCII identity matching. See the deferred stored column above.
- The four already-consistent `func.lower` sites, which need nothing.

### Doc impact

- `docs/security_posture.md` — the identity-matching convention, once chosen (Item 2).
- `guide/findings_2026-09-13_spec_discrepancies.md` — `SC-45` closes when this lands (Item 2).

### Status

**Opened and closed 2026-09-13.** Surfaced while investigating
`SC-19`, which asked only which fold *one* call site uses; the answer
was "Python casefold", and the question that mattered turned out to be
why the other twelve do something else.

**Intended vs done.** The item opened with two open questions and the
expectation that casefold would win. Investigation reversed that: the
"Unicode-correct" answer is the one that fails open on an access gate,
and the cheap answer is the correct one. Two things the plan did not
anticipate:

- **`normalize_email` had no test at all.** The convention every
  identity gate rests on was asserted only through the surfaces using
  it. Eight tests now cover it directly.
- **The module docstring was itself false** — it claimed write-time
  and read-time comparisons "can never disagree" because everything
  folds through `normalize_email`, when the SQL-side sites never did.
  That claim is what `SC-45` was really about.

- **Changing one function did not close the gates it was written for**,
  and it took two verification passes to find them all. The first found
  four identity comparisons folding inline — `auth.roles.is_super_admin`
  among them. The second found **three more**, and the worst of those
  was inside a module already on the new test's list:
  `deps.py:134`, the sign-in resolution deciding which `User` row an
  authenticated principal becomes, folding with a bare `.lower()` that
  the test's `.casefold()`-only regex could not see. Also
  `users.py`'s uniqueness gate and the session-owner lookup, both
  absent from the list entirely.
  The root cause each time was the same: the blast radius counted
  callers of `normalize_email` rather than sites that fold without it.
  All seven are routed now; the test matches both folds in both
  spellings and covers eight modules.
- **The pre-fix state was not merely fail-closed.** The first draft said
  so and stopped at the self-match direction; a `ß` holder's casefolded
  key matched an unrelated `ss` row at every gate. Withdrawn and
  recorded, in the plan and in `docs/security_posture.md`.

Nothing broke: the suite went 3,903 → 3,914, all additions. Seven
mutations across the fold and the four gates, each caught — reverting
to casefold fails exactly the eszett test, and reverting any gate fails
the structural one.

---

## Item 3 — the failure banner names the wrong button

### Opportunity

The workflow card's failure signal headlines whichever action
failed. It derives that headline from one line
(`next_action_card.html:432`):

```jinja
{% set _button_label = "Prepare session" if super_failure.button == "prepare" else "Activate session" %}
```

Two values in, five values out. `_workflow.py` and
`_session_home.py` between them pass **five** distinct
`super_button` values:

| value | passed at | headline today |
|---|---|---|
| `prepare` | `_workflow.py:106, 185, 226` | "Prepare session failed…" ✓ |
| `activate` | `_workflow.py:263, 275, 353`; `_session_home.py:541` | "Activate session failed…" ✓ |
| `close` | `_workflow.py:391, 410` | **"Activate session failed…"** ✗ |
| `release_responses` | `_workflow.py:441` | **"Activate session failed…"** ✗ |
| `stop_release` | `_workflow.py:478` | **"Activate session failed…"** ✗ |

So an operator whose **Close session** fails its precondition is
told *"Activate session failed at the pre-flight check"* — naming
an action they did not take, on a session that is already
activated. The error detail below it is correct, which makes the
headline worse rather than harmless: the two disagree and the
bold one is wrong.

There is a second, quieter half. `_step_label_map` in the same
block covers `generate` / `validate` / `activate` /
`precondition`. `_workflow.py:411` passes `super_step="close"`,
which the map does not carry, so that banner silently drops its
step phrase. The template's `{% if super_failure.step in
_step_label_map %}` guard means an unmapped step degrades
quietly instead of rendering a raw enum — correct behaviour for
an unknown value, and the reason this went unnoticed.

Nothing is mis-routed and no state is wrong: the failure paths
already carry the right `super_button`, and `_redirect_url`
already forwards it. Only the label lookup is short.

### Decision

**A lookup keyed on `super_button`, beside `_step_label_map`,
carrying all five values** — and `_step_label_map` gains `close`,
`release` and `stop`. An unknown key falls back to a generic
"Action failed" rather than to any named button, so the next
value added to the vocabulary reads vague instead of wrong.

Rejected: **extend the ternary to a five-branch chain.** It puts
the vocabulary in an expression nobody greps, which is how it
came to be two values behind in the first place.

Rejected: **derive the label from the lifecycle state.** The
state at redirect time is the state the action failed to leave,
so it names the wrong action for exactly the failures that
matter.

Also to settle in this item: `_shared.py:351` documents
`super_button` as *"`\"prepare\"` or `\"activate\"`"*, and
`spec/workflow_card.md` says the same in four places (`:100-102`,
`:140-141`, `:442-443`, `:663-665`). The spec, the helper's docstring and the
template are all two values behind the routes — one vocabulary
recorded in **three files and six passages** besides the template
(`_shared.py` ×1, `views/_workflow_card.py` ×1,
`spec/workflow_card.md` ×4) and updated in none.

### Semantics

- **Unknown `super_button`** — headline reads "Action failed"; the
  step phrase and error detail render as they do today. No
  *unrecognized* value may fall through to a named button.
- **Absent `super_button`** — *not* the same case, and this bullet
  was wrong until 2026-09-13. A URL that omits the slot never
  reaches the template's fallback: `views.parse_super_failure`
  infers a button from the step name (`generate` / `validate` →
  `prepare`, `activate` → `activate`, else `prepare`) so an old
  bookmark still resolves, which `spec/workflow_card.md` documents.
  That inference predates the three later buttons and can only ever
  name one of the original two — a limitation, not a defect, and the
  reason the slot is now always passed explicitly.
- **Unknown `super_step`** — unchanged: the phrase is omitted,
  the headline and error still render.
- **`super_failure` absent** — unchanged: no signal line.

### Blast radius (measured)

```
grep -rn "super_button" app/ --include=*.py   # 32 (11 call sites, 21 plumbing)
grep -rn "super_failure" app/web/templates/   # 7, all next_action_card.html
grep -rn "parse_super_failure" app/ tests/    # to re-measure at build
```

One template block, one view helper's docstring, one spec (four
passages of it).

### PR ladder

1. The lookup + `_step_label_map` additions, a test per
   `super_button` value asserting its headline, and the
   `_shared.py` / `spec/workflow_card.md` vocabulary fix. One
   slice — the map and the copy that documents it should not
   land apart.

### Definition of done

- Each of the five `super_button` values renders its own
  headline, asserted by a test that drives the real route.
- An unrecognized value renders "Action failed" and names no
  button.
- A step phrase renders only where it adds something: `precondition`
  does, and a step that merely repeats the button label is
  suppressed.
- `spec/workflow_card.md`, `_shared.py`'s `_redirect_url` and
  `views/_workflow_card.py`'s `parse_super_failure` all enumerate
  the same five values the routes pass.

### Open questions

None. **Answered 2026-09-13 by the author: "copy follow button
labels."** Reading them off the shipped markup corrected my own
guess in this section — the button is `Stop releasing<br>responses`,
so the headline is **"Stop releasing responses failed"**, not the
"Stop release" written above.

### Out of scope

- The `super_*` query-param mechanism itself. It works; only its
  vocabulary is short.

### Doc impact

- `spec/workflow_card.md` — enumerate all five `super_button` values in **all four** places the two-value vocabulary appears: the `super_failure` slot description (`:100-102`), the `parse_super_failure` helper note (`:140-141`), the Failure-handling redirect URL (`:442-443`) and the Workflow-failure signal section (`:663-665`); add the unknown-value fallback (Item 3).
- `guide/findings_2026-09-13_spec_discrepancies.md` — `NF-01` closes when this lands (Item 3).
- `docs/status.md` — row when the item lands.

### Status

**Opened and closed 2026-09-13.** Found by the second-pass audit as
`NF-01` — the only live user-facing defect in that register of 22.

**Intended vs done.** The ladder's single rung landed as planned: the
keyed lookup, the `_step_label_map` addition, the vocabulary fix in
`_shared.py` and `spec/workflow_card.md`. Three things the plan did
not anticipate:

- **The plan's own copy guess was wrong.** It assumed the fifth button
  read "Stop release". It renders `Stop releasing<br>responses`, so
  the headline is "Stop releasing responses failed". Taken off the
  markup, not from the plan.
- **A vocabulary site the plan missed**, and a count that did not
  reconcile. `views/_workflow_card.py`'s `parse_super_failure`
  docstring carried the same two-value claim and the plan had not
  named it. The commit that fixed it then said "four other places",
  which is neither the file count nor the passage count: it is
  **three files, six passages** — `_shared.py` ×1,
  `views/_workflow_card.py` ×1, `spec/workflow_card.md` ×4. Caught
  by the verification pass, not by me; the fifth unreproducible
  figure this session's work has produced.
- **Step suppression, decided at build.** Adding `close` to the step
  map would have produced "Close session failed at the Close session."
  The phrase is now dropped when it repeats the button label, which
  also retires the same redundancy the shipped `activate` path had.
  Beyond the literal ask, small, and flagged in the PR.

Seven tests; four mutations, each failing exactly the right ones —
reverting to the two-value ternary fails five.
