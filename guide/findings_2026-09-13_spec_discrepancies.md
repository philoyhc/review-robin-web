# Findings — spec discrepancies surfaced by Segment 19M

**Opened** 2026-09-13 · **Source:** the `spec/` history sweep
(`guide/segment_19M_spec_history_sweep.md`, record at
`guide/sweep_2026-09-13_spec_history.md`) · **Status:** open register,
nothing actioned.

**Why this file exists.** 19M was a prose sweep, and the rule it ran
under — `rrw_sdd_in_practice.md` §4, *the spec is the contract; when the
code drifts, fix the code* — means a sweeper who finds spec and code
disagreeing **may not quietly rewrite the spec to match**. So every
divergence became a finding instead of an edit. This is that register.

**A sweep recommends; the fixes ship afterwards as ordinary work.** None
of the below is actioned. Each row names the contract, what actually
happens, and what deciding it involves — because most of these are a
choice between *fix the code* and *change the contract deliberately*, and
that choice is the author's.

## How the sweep produced these

All six batches have reported.

The correction arrived mid-sweep. Three batches **reverted rewrites they
had already made** once it landed — Item 5 reverted six, Item 6 two, Item
4 one — which is why several rows below read "the batch had changed this
and put it back". *Those reverts are the most load-bearing thing in this
document: without the correction, nine contracts would have been silently
demoted to descriptions of the code.*

## The tally

**75 findings**, counted by distinct id rather than asserted:

| kind | count | what it is |
|---|---|---|
| **SC** | 36 | spec says one thing, code does another |
| **CC** | 11 | two code comments disagree, or one names something absent |
| **SI** | 10 | one spec contradicts itself |
| **ID** | 8 | a spec names an identifier that does not exist |
| **SS** | 6 | two live specs disagree |
| **DT** | 4 | documentation that describes its own tooling imprecisely |

*Recount before quoting this number.* It was published as 64 and grew to
75 as the verification passes reported, and nothing renews a count —
which is the defect this whole segment exists to remove, so a register
carrying one had better be honest about it. The command:

```
grep -o '\b\(SC\|SS\|SI\|CC\|ID\|DT\)-[0-9][0-9]\b' \
  guide/findings_2026-09-13_spec_discrepancies.md | sort -u | wc -l
```

## Reading key

| tag | kind |
|---|---|
| **SC** | spec says one thing, code does another |
| **SS** | two live specs disagree |
| **SI** | one spec contradicts itself |
| **CC** | two code comments disagree, or a comment names something absent |
| **ID** | a spec names an identifier that does not exist |

---

## Priority 1 — a real defect with user-visible consequence

### SC-01 · An older settings bundle cannot be imported at all

**`spec/settings_inventory.md` §10 row §9** (explicit): *"a
`session_rule_sets[n].library_name` row on input **must be recognized and
skipped**, not rejected — a bundle taken while that column existed is
otherwise unimportable in full."*

**Code:** `app/services/session_config_io/_apply_rule_set.py:53` —
`raise _ParseError(f"unknown session_rule_sets[] attribute {attr!r}")`.
That becomes an `ApplyError`, and because apply is two-phase
(validate-all, then write), **phase 2 never runs and the whole import is
rejected.**

**Verified** here by reading both. This is the one finding with a concrete
user consequence: an operator importing a bundle exported before that
column went away gets a total failure, for a cell the spec says carries
nothing usable.

**Action:** add `library_name` to the recognized-and-skipped set. The
contract already says so; no contract decision needed.

### SC-02 · A specified pill cannot render, and the code documents behaviour it no longer has

**`spec/assignments.md`** status table and its `### Staleness` section
specify a `stale` pill "when the current rule + roster pass would produce
a different set".

**Code:** `app/web/views/_assignments.py:221` sets `is_stale = False` and
:202 sets `any_stale = False` — **both hardcoded** — while the same
file's docstrings at :73 and :107 still describe the computation they no
longer perform. `compute_staleness` in `_coverage.py` is live but
uncalled on this path.

**Verified** here. **Related, one layer down: SC-03 — `stamp_changed` (the
helper the spec names for the check) has 0 occurrences in `app/` and
`tests/`.**

**Action:** either implement staleness and delete the dead docstrings, or
retire the contract deliberately and remove the section. *The current
state is the worst of the three: a documented feature, a docstring
promising it, and a constant that forbids it.*

### SC-04 · A test enshrines the code against the spec it cites

**`spec/reviewer-surface.md`** specifies `typical_chars = max_length *
0.75` and names `_TYPICAL_RESPONSE_FRACTION` as the factor.

**Code:** `app/web/views/_instruments.py:226` — `= 0.5`. **And
`tests/integration/test_instrument_builder_routes.py:6859` asserts
`"TYPICAL_RESPONSE_FRACTION = 0.5"` in the rendered body.**

**Verified** here, all three. The same shape recurs at **SC-05**, where
`tests/unit/test_reviewer_view_helpers.py` pins the code's heading format
*and cites this spec section as its authority* — so the test and the spec
it names disagree, and the test is what would fail if the contract were
honored.

**Action:** decide which is right, then change the other **and its test**.
*This is harder than prose drift: the gate is on the wrong side, so the
suite currently defends the divergence.*

---

## Spec vs code — contract left standing

Every row: the spec was **not** edited. Verified-by column says who
checked it.

| id | where | contract | code | verified |
|---|---|---|---|---|
| SC-06 | `spec/assignments.md` | `POST …/assignments/instrument/{iid}/self-reviews-active` | `…/assignments/{instrument_id}/self-reviews/active` (`_assignments.py:479`) — **a URL is contract** | here |
| SC-07 | `spec/csv_contracts.md` §4 items 1 and 7 | seeded RuleSets are not re-emitted, or a re-import trips `uq_session_rule_set_session_name` | `_serialize._non_seeded_session_rule_sets` returns **every** row | Item 6 |
| SC-08 | `spec/csv_contracts.md` §5 | `decode_csv(content: bytes) -> str` | `decode_csv(content, source, *, max_bytes=…) -> tuple[str \| None, ValidationIssue \| None]` | Item 6 |
| SC-09 | `spec/settings_inventory.md` §2 | `assignment_mode` values `manual` / `rule_based` | `AssignmentMode` admits only `rule_based`; three tests still set `manual` | Item 6 |
| SC-10 | `spec/settings_inventory.md` §2 | Edit surface is `/operator/sessions/{id}/edit` | `_session_home.py:241` is a **308** to `…?editing=1#session-config`; the page is gone | Item 6 |
| SC-11 | `spec/instruments.md` | Band 3 bounds rules for `Number` / `Rating` / `SingleSelect` / `MultiSelect` | `bulk_save_fields` branches on `String` / `Integer` / `Decimal` / `List` — the four the spec's own Type picker lists eight lines above | Item 4 |
| SC-12 | `spec/reviewer-surface.md` | Discard labelled `Discard`; a per-page `Page #{N}: {short_label}` button; Save is Primary | `Cancel`; `< Previous page` / `Page {N} of {M}` / `Next page >`; Save is `.btn.secondary` | Item 5 |
| SC-13 | `spec/reviewer-surface.md` | page buttons carry `max-width: 16em; text-overflow: ellipsis` | neither rule exists in `base.html` | Item 5 |
| SC-14 | `spec/reviewer-surface.md` | Enter / Shift+Enter move focus down / up a column | **no `keydown` handler on the reviewer surface at all** | Item 5 |
| SC-15 | `spec/reviewer-surface.md` | status column renders when a row has `submitted_at` **or** `show_acknowledge` | `_context.py:528` uses `show_incomplete_marks`; `show_acknowledge` has 0 occurrences — **and the file already says elsewhere there is no such flag** (also SI) | Item 5 |
| SC-16 | `spec/reviewer-surface.md` | dashboard `closed` renders `pill-lifecycle-archived` (muted grey) | `reviewer/dashboard.html:122` renders `pill-error` (red) | Item 5 |
| SC-17 | `spec/reviewer-surface.md` | `submit_redirect_url(review_session, position)` → `/{page_n}` | `submit_redirect_url(review_session, *, fully_submitted=False)` → `/summary` or bare session URL | Item 5 |
| SC-18 | `spec/role_navigator.md` §2 | preview route is `…/previews` | the route rendering `review_surface.html` is `…/preview-surface/{page_n}`; `/previews` is the hub | Item 5 |
| SC-19 | `spec/role_navigator.md` | identity match is `func.lower(column) == casefold(email)` in SQL | `build_role_chips` folds via `normalize_email` in Python | Item 5 |
| SC-20 | `spec/preview_hub.md` §3 | per-artifact "Send test to…" affordance, lifecycle-gated | `grep -rni "send test\|send_test"` over `app/` → **0** | Item 5 |
| SC-21 | `spec/preview_hub.md` + `spec/session_home.md` | Next Action card carries a "See previews" button in `validated` | no such string anywhere in `app/` | Item 5 |
| SC-22 | `spec/preview_hub.md` | Operations row is `[Assignments][Validate][Previews][Invitations][Responses]` | `session_top_nav.html` renders a sixth tab, `Extract data` | Item 5 |
| SC-23 | `spec/session_home.md` §1 | an "Activated state exception": body split by `<hr class="next-action-divider">`, buttons beside their section, `.next-action-buttons` **not** rendered while Activated; `.next-action-confirm` pre-Activated | neither class appears in any template (CSS rules in `base.html` only), and `spec/workflow_card.md` specifies a single button row in **every** state | Item 2 |
| SC-24 | `spec/operator_button_audit.md` §11.5 | Inactivate / Activate gated on "≥1 selection" only | the template also gates them, and the count pill, on `can_edit` | Item 2 |
| SC-25 | `spec/role_landing_and_visibility.md` §3 | "the eight operator cards"; a stranger "saw all eleven" | `_guide.py` `SECTIONS` has **12** (9 operator + 3 role) | Item 5 |
| SC-26 | `spec/reconciling_regeneration.md` | the `include` seed is pair-level via `is_self_review(reviewer, reviewee)` | `_generate.py:334-347` applies the **whole-group** rule on group-scoped instruments — which `spec/assignments.md` specifies. **Here the code is right and this spec is incomplete** | Item 4 |
| SC-27 | `spec/reconciling_regeneration.md` + `spec/assignments.md` | `reconcile_impact` returns per-instrument counts | returns one aggregate `ReconcileImpact` for the session. **Item 4 had written the aggregate in and reverted it** — the design's reason (one path serving the banner *and* a per-instrument preview) needs per-instrument | Item 4 |
| SC-28 | `spec/quick_setup_card_spec.md` | operator is sent to the Operations Assignments page to regenerate | generation fires from the Workflow card's stepper | Item 2 |
| SC-29 | `spec/csv_contracts.md` §3.3 | the Settings CSV has an RTDs section (example `rtd.Long_text.data_type,…`) | `_serialize` emits no RTD rows; such a row hits the unknown-key ignore | Item 6 |

### SC-30 … SC-36 · Item 1, the visual / token family

Item 1 reported last. Its divergences are visual-layer contracts, and two
of them are **likely code bugs** rather than contract questions.

| id | where | contract | code |
|---|---|---|---|
| SC-30 | `ui_elements.md` §1 | Sign out is a **Secondary** control | `base.html:3414-3417` ships a bespoke `.chrome-user .signout` rule instead — `--border-default` (not `--btn-secondary-border`), `--text-body`, and a `--surface-muted` hover. **This row's own description was wrong until the verification pass**: it said the spec named no token, when §1 had come to restate §6's `--btn-secondary-*` pair. §1 now points at §6 instead of restating it, per `operator_button_audit.md`'s own rule that the role definition lives in one place |
| SC-31 | `visual_style_general.md` Patterns | status strip fills `bg-muted` with `border-subtle` **top and bottom**, sitting between chrome and page body | `--surface-card`, top border only, **inside** the nav card. RRW overrides the *placement* explicitly but **not** the fill — so the fill is unaccounted for. **Needs a decision** |
| SC-32 | `ui_elements.md` §4 vs two other specs | §4 said `.card.danger-zone` has a **white** background; `visual_style_general.md` and `visual_style_rrw.md` both contract the **same amber surface as the lock card, "fill included"**; code ships `--card-warning-bg` | **Resolved to amber** by `ui_elements.md`'s own header precedence rule. Flagged because it is a **contract text change**, not a provenance edit |
| SC-33 | `ui_elements.md` pills | `.pill-success` text is `--status-success-fg` | `base.html:3289` ships `--status-success-accent`. They share `--green-deep` in light but **diverge in dark** (`--green-glow` vs `--green-bright`), and every other pill uses its `-fg`. **Contract left as `-fg`; likely a code bug.** Item 1 had written `-accent` to match the code and reverted it |
| SC-34 | `session_home.md` | `.next-action-confirm` renders in pre-Activated states | `base.html:3094` has the rule; `next_action_card.html` emits no element with that class. *Corroborates SC-23* |
| SC-35 | `ui_elements.md` | the `placeholder_card` macro is the reuse point for placeholder cards | the macro has **no callers**; the one live `.card.placeholder` is hand-written in `session_previews.html`. The old entry also claimed three pages use it — false on all three, so the page list was dropped as ship-state rather than corrected |
| SC-36 | `base.html` | — | **Orphan CSS, no contract behind any of it:** `.setup-nav` / `.setup-nav > .btn` (831-839, 0 template users), the `.btn-cta` rules (0 markup callers), `.next-action-confirm`. Code cleanup |

**CC-09 · Retired token names inside `base.html`'s own comments.**
Line 2330 (`` `.pill-count` (`--accent-blue-bg` light blue) ``), line 3571
("the active side fills accent-blue"), line 872
(`--accent-blue-marker` is #93c5fd) — and **line 2479 carries "Danger
Outline (.destructive)", the pre-19B button vocabulary the doc guard bans
in live prose.** The guard reads specs, not CSS comments, so the retired
vocabulary survives where nothing looks.

**A decision Item 1 made by reading rather than sweeping, recorded because
it looks like an omission:** `visual_style_general.md`'s **61 lines** of
`accent-*` / `bg-page` / `text-primary` names were **left entirely
alone**. That file's own preamble already states the constraint forward —
*"These are the design system's role names, not Review Robin's shipped
token identifiers. This document is portable"* — with a pointer to
`color_tokens.md` as authoritative and an explicit note that it retires
the flat vocabulary. *Renaming them would have broken the document's
stated portability and contradicted its own guard paragraph.* So ID-01
through ID-06 are real and this file's 61 are not.

---

## Spec vs spec

### SS-01 · Five validation severities — and two would block activation

`spec/validate_page.md` **agrees with the code**; the per-page specs do
not.

| rule | code + `validate_page.md` | per-page spec |
|---|---|---|
| `instruments.no_fields` | error | **warning** (`instruments.md`) |
| `instruments.no_display_fields` | warning | **info** (`instruments.md`) |
| `instruments.zero_included` | warning | **error** (`instruments.md`) |
| `assignments.no_included_pairs` | warning | **error** (`assignments.md`) |
| `assignments.reviewer_missing` | warning | **error** (`assignments.md`) |

**Verified** here for the two consequential ones: both are
`Severity.warning` in `app/services/validation.py`. As *errors* they would
**block activation**, so the direction matters.

**Proposed resolution, for confirmation:** `spec/README.md`'s precedence
rule gives the subsystem spec authority, and validation's subsystem spec
is `validate_page.md` — so the per-page lists are what to correct. But
that is an error → warning downgrade in two live specs, which is a
deliberate contract change. **All five left untouched.**

### SS-02 · Observer cohort rules — resolved in favour of the CSV contract, flagged

`spec/rehydrate.md` §9 said cohort rules are not restored and the
observers CSV carries only Email/Name/Tag1/Status.
`spec/csv_contracts.md` §3.2b and `spec/roundtrip_coverage.md` say
`CohortRule` round-trips. Code agrees with the latter:
`observers_extract.HEADER` includes `CohortRule`, `csv_imports.py:532-572`
re-validates through `CohortRuleSet`, and rehydrate calls
`parse_observer_csv` + `save_observers`.

**Item 6 changed the rehydrate bullet** — it *had* to, because its pointer
named text the sweep removed. **This is the one spec-vs-spec conflict the
sweep resolved by editing rather than reporting; flagged for
adjudication.**

### SS-03 · Others, left standing

| id | conflict | left |
|---|---|---|
| SS-04 | `operator_button_audit.md` §1 prescribes 11 nav tabs, omitting **Observers** and **Extract data**, both required by `operator_ui_concept.md` | standing; already filed in `todo_master.md`, and filling it is a re-audit plus a renumber |
| SS-05 | `operator_button_audit.md` §13 calls the page "Manage Invitations"; `operator_ui_concept.md` and `operations_pages.md` call it "Invitations" | standing — a rename is not a history question |
| SS-06 | "ten-state cascade" in `session_home.md` and `operator_ui_concept.md`, while both list twelve and `workflow_card.md` says twelve | standing |

### Resolved by the sweep — recorded so the decision is visible

These were fixed because one side was a file contradicting **itself**, or
because a live spec already carried the answer:

- `sessions_overview.md` page H1 → **`Sessions Lobby`** (its own two other
  mentions, and the template).
- `/edit` redirect → **308** (`operator_ui_concept.md` owns the route
  contract; `session_home.md` said 301 twice).
- `operator_ui_concept.md` §5 → **six** Operations tabs, table reordered to
  match its own chrome diagram.
- Outbox → the **sys-admin** path (`_operations.py:758` records the
  per-session route retired).
- Bulk-action rows on Invitations / Responses → **prohibition**
  (`operations_pages.md` already said neither page carries one).
- `operator_button_audit.md` rows 105–110 → **`is_editable`**, not
  `is_ready` (the audit contradicted itself; `_shared.py:831` confirms).
- Rule Builder page → **Band 1 is the sole authoring surface**.
- `lifecycle.md` header → **five live states, none reserved**
  (`expire_session` at `session_lifecycle.py:459`).
- `audience_and_identity_model.md` → **four live audiences**.
- Zip-all → **wired** (`_extracts.py:324-346`), against the same
  section's "inert".

---

## Spec contradicts itself — left standing

| id | where |
|---|---|
| SI-01 | `spec/instruments.md` — the action-row list omits `+Page break`; the per-instrument action-row section includes it |
| SI-02 | `spec/csv_contracts.md` — header says "five roster-shaped pairs (… **Observers**, Settings)"; §4's byte-stability contract says "four (Reviewers, Reviewees, Relationships, Settings)" |
| SI-03 | `spec/settings_inventory.md` §10 carries **two** `audit_events` rows with opposite marks (✅ analytics-only / ❌ out of scope) |
| SI-04 | `spec/setup_pages.md` states the Upload confirm copy two ways in one file |
| SI-05 | `spec/reviewer-surface.md:145` says *(See "Form scope" below)*; the section is called "Form HTML mechanics" |

---

## Code-internal — no spec impact

| id | where | what |
|---|---|---|
| CC-01 | `app/services/session_lifecycle.py:36-38` | `SessionStatus`'s docstring says `expired` and `archived` are "reserved for later segments" while `expire_session` (:459) and `archive_session` (:678) write both |
| CC-02 | `app/web/routes_operator/_shared.py:298` | `"group_instrument_no_rule": 409` is a dead mapping. **Checked**: `open_instrument` carries a comment at :779 recording that Wave 5 PR 5.3 retired the gate deliberately — so this is dead matter, not a lost gate |
| CC-03 | `app/schemas/rules.py:6,367` | docstrings describe themselves as mirroring `rule_set_revisions`, a dropped table |
| CC-04 | `app/services/csv_imports.py:61-63` | names a `MANUAL_CSV_MAX_BYTES` constant and a "manual-assignments importer" that do not exist |
| CC-05 | `_serialize.serialize_session_config` docstring | still lists "3. Operator-defined RTDs" and "6. Field-label overrides" as emitted sections |
| CC-06 | `app/services/visibility_policies.py:365-370` | documents `while_ongoing` as `[activated_at, deadline)`; the behaviour matches the spec's status-column rule, so the docstring is what is wrong |
| CC-07 | `_operations.py:264,358-366` + `views/_previews.py:19` vs `_preview_surface.py:3-6` | **two code comments disagree** about whether the preview follow-on was Segment 18Q; the latter explicitly corrects the former |
| CC-08 | `app/db/models/email_outbox.py` | says "Segment 14-1" where the specs say "Segment 14B" (the equivalence is recorded in the 14B plan header, so this is findability, not error) |

---

## Stale identifiers in specs

Retired colour-token vocabulary — **0 definitions in `base.html`**; the
live tokens are `--status-*` / `--card-*` / `--text-body`.
**`spec/ui_elements.md`'s own family is Item 1's and still in flight.**

| id | where | names |
|---|---|---|
| ID-01 | `operator_button_audit.md:42,44,45,46` | `accent-blue`, `accent-red`, `accent-amber`, `accent-amber-dark` — the role legend, so `ui_elements.md` §6 owns the replacement |
| ID-02 | `session_home.md:112,147,499` | `accent-blue` |
| ID-03 | `session_home.md:443-444` | `bg-muted`, `text-muted`, `text-secondary` (the `.card.placeholder` rule) |
| ID-04 | `extract_data.md:915,917,919` | `--accent-blue`, `--color-border` — the latter has **0 occurrences of any kind** |
| ID-05 | `participant_model.md:86` | `--accent-blue`, `--accent-blue-bg-faint`; the rule uses `--card-active-border` / `--card-active-bg` |
| ID-06 | `role_navigator.md:113,114` | `--surface-2`, `--text-muted`, `--text-primary`; really `--surface-muted` / `--text-subtle` / `--text-body` |

**Fixed already**, recorded so the register is not read as outstanding:
`lifecycle.md:449` → the shipped `--card-warning-*` pair, and
`rrw_functional_spec.md:1022` → "blue-framed" with no token identifier,
since §6.2 puts that altitude at technology-neutral.

### Other stale names

| id | where | names | reality |
|---|---|---|---|
| ID-07 | `csv_contracts.md:605` | `field_labels.apply_captured_labels` | `field_labels.apply_import` (`field_labels.py:277`). **Same wrong name in `app/services/setup_templates.py:35`** |
| ID-08 | `visual_style_rrw.md:213` | cites `session_home.md` "Enum vs. display label" | that heading does not exist; it is "Lifecycle state vocabulary". Not caught by the `§N` guard because it is a *named* reference |

---

## Structural question — not a discrepancy, but it belongs here

**`spec/role_landing_and_visibility.md` may be a `docs/` document living
in `spec/`.** Its opening answers *"given my role, can I sign in, where do
I land, and what do I see?"*, and its tables were introduced as *"recorded
from a running app"* — which is §4's question for **`docs/`**, not the
contract question for `spec/`.

Item 5 softened the method claim and **declined to move or rewrite the
file.** Relocating a spec is a contract decision, and
`tests/unit/test_spec_coverage.py` maps routing modules to governing
specs, so a move is not a file rename.

---

## Frozen measurements — the class, not a list

Counts in a contract rot exactly as a `*Current:*` block does, which is
19M's own diagnosis one level up. One was converted:
`permissions.md`'s *"128 of 128 routes carry a dependency"* → *"every such
route carries one"*, keeping the counting method as the invariant. First
checked that no test reads `128`.

**Five test-case counts in `permissions.md` §7 were kept and not
verified** — the batch could not tell whether the author uses them as a
coverage floor. That is the open question this class leaves.

---

## What is not here

- **Nothing outstanding from the batches — all six have reported.**
  `ui_elements.md` §6 still owns the role-legend replacement ID-01 needs,
  and that is a follow-on edit rather than a missing finding.
- **Anything in `docs/`, `guide/` or the root documents.** Out of 19M's
  scope. One consequence is recorded in the sweep record instead:
  `rrw_sdd_in_practice.md` §6.2's *"4 of 36"* currency-line count and its
  line-38 quotation are affected by the functional spec's currency line
  being replaced with a sweep-record pointer.
- **Fixes.** *A sweep recommends.*

---

## DT — documentation that now describes its own tooling imprecisely

A fifth kind, added when the author instructed that **`spec-writer`'s
instruction be updated**. Its charter had a contradiction that cost two
long per-invocation overrides during 19M: step 3 said *"update the spec to
match current behaviour … Reflect what the code actually does now"*, while
step 5 said *"flag drift … rather than silently rewriting"*. **Those are
opposite instructions for the same situation**, and under §4 the first one
is wrong outside a segment close.

`.claude/agents/spec-writer.md` now draws the distinction §6.1 actually
makes, as two modes:

- **Mode A — a segment close.** The segment deliberately shipped code, so
  the shipped behaviour *is* the intended new contract and aligning the
  spec is the deliberate act §4 calls for. *"Spec on the way out."*
- **Mode B — anything else** (a verification pass, a sweep, a drift someone
  noticed). **The spec wins**; a divergence merely discovered has no
  decision behind it, so it is reported, not re-aligned. Where the spec is
  stricter, it stays stricter. *"If you cannot tell which mode you are in,
  you are in Mode B."*

It also now forbids the two things this sweep had to strip out by hand —
tree measurements and a spec hedging itself against the code — and carries
the constraint-keeps-its-reason rule, the grep-`tests/`-before-deleting
rule, and the keep-if-uncertain rule.

### The knock-on — reported, not edited

`rrw_sdd_in_practice.md` describes the charter in **four** places. One is
now *more* accurate than before; three are imprecise:

| id | where | what it says | status |
|---|---|---|---|
| DT-01 | `rrw_sdd_in_practice.md:85` | quotes the charter as *"to match the code … so the specs never drift from reality"* | **the quoted words no longer exist in the file.** The *phase rule* the sentence supports is unaffected — it is now stated explicitly as Mode A — but the quotation needs requoting or paraphrasing |
| DT-02 | `:115` | *"`spec-writer` updates `spec/` to match the code after a change … and must 'flag drift … rather than silently rewriting'"* | the second quote survives; the first half is now **conditional on a close**. This line is where the old contradiction is most visible, because it states both halves side by side without noticing they conflict |
| DT-03 | `:201` | the maker/checker table: *"spec-writer (writes spec to match code)"* | imprecise for the same reason |
| — | `:95` | *"that stays `spec-writer`'s job **at the close**, and the author's"* | **already correct, and now corroborated** — this is the only one of the four that carried the phase qualifier |

**Not edited.** It is the author's own analysis, carrying measured figures,
and §6.1's argument does not change — only its characterization of a tool.
*That DT-04 exists at all is the same lesson the sweep keeps producing: a
document describing a thing goes stale when the thing changes, and nothing
renews it.* Note that `:95` is right precisely because it named the phase;
the three that are wrong all omitted it.

### DT-04 · The same imprecision, in three other live documents

`docs/practice-audit-2026-09-04.md`, `docs/status.md` and
`guide/todo_master.md` each describe `spec-writer`'s job. They were not
read against the new definition — out of 19M's scope — and should be
checked when DT-01..DT-03 are actioned.

---

## ACTIONED — ID-01 … ID-08 (Segment 19M Item 7)

All eight fixed. **Every replacement was verified to exist in `base.html`
before it was written**, because the sweep's own thirteen errors were
mostly a name substituted inside an otherwise correct sentence.

| id | was | now |
|---|---|---|
| ID-01 | `operator_button_audit.md`'s role legend named `accent-blue` / `accent-red` / `accent-amber` / `accent-amber-dark` | **the legend no longer names tokens at all** — "Solid fill", "Outline red", "Filled amber, light label", "Outline amber". Open question 1 answered: the legend exists to be a reading key for §6, so it points rather than restates, and cannot drift from §6 again |
| ID-02 | `session_home.md` ×3 `accent-blue` | `--card-active-border` (the card border) and `--btn-primary-bg` (the button fill) — **two different tokens for what one retired name had covered**, which is why the flat vocabulary was retired |
| ID-03 | `bg-muted` / `text-muted` / `text-secondary` | `--surface-muted`, and `--text-subtle` on **both** heading and body — the shipped rule uses one token for the two, not two |
| ID-04 | `extract_data.md` `--accent-blue` ×2, `--color-border` | `--card-active-border`, `--border-subtle`. `--color-border` had **0 occurrences of any kind** |
| ID-05 | `--accent-blue` + `--accent-blue-bg-faint` | `--card-active-border` + `--card-active-bg` |
| ID-06 | `--surface-2, #f3f4f6`, `--text-muted`, `--text-primary` | `--surface-muted`, `--text-subtle`, `--text-body` — **and the hard-coded hex fallback goes with them**, since a fallback literal cannot follow the theme |
| ID-07 | `field_labels.apply_captured_labels` | `field_labels.apply_import` (`field_labels.py:277`) |
| ID-08 | a named cross-reference to `session_home.md` "Enum vs. display label" | §"Lifecycle state vocabulary", the heading that exists. **Not caught by the `§N` guard, because it is a *named* reference** |

**Two retired-token hits remain in `spec/` and are correct:**
`color_tokens.md:7` is the do-not-reintroduce constraint, which must name
them to forbid them; `ui_elements.md:23` explains why
`visual_style_general.md` uses role names deliberately. Its 61 are
untouched for the reason Item 1 recorded.

*Open question 3 is also answered by this item: stale identifiers were
**8 rows across 7 files**, six of them one cluster. A footnote, not its own
segment — and now closed rather than filed.*

---

## ACTIONED — SC-01 … SC-04, on the author's decision (Segment 19M Item 8)

> *"SC01-04 — update spec/comments; code is correct"* — the author,
> 2026-09-13.

That is the deliberate contract change §4 requires. In all four the **code
stands and the documentation moves.** Recorded here rather than only in the
commit, because a contract that changes silently is the thing §4 forbids and
these four changed on one line of instruction.

| id | what the spec claimed | what it says now |
|---|---|---|
| **SC-01** | a `library_name` row on input **must be recognized and skipped**, *"not rejected — a bundle taken while that column existed is otherwise unimportable in full"* | an unrecognized `session_rule_sets[n].<attr>` row **is rejected**: the parse phase raises and the whole apply fails before any write. The strictness is stated as deliberate, distinguished from the top-level unknown-key silent ignore, with its reason (a misspelled rule-set attribute would otherwise be dropped in silence and change which pairs generate) **and its cost** (such a bundle needs the column removed before import) |
| **SC-02** | the status table carries a `stale` pill when a rule/roster pass would produce a different set | *"**There is no `stale` pill and no staleness signal on this page.**"* Stated as the contract, with the consequence a reader needs: a rule edit is invisible until regeneration, and *"a reader who assumes the page warns them will not check"* |
| **SC-03** | the check is `stamp_changed(instrument, db)` | gone with §Staleness — the helper does not exist |
| **SC-04** | `typical_chars = max_length * 0.75` | `* 0.5`, matching the code **and the test that asserts it**. The gate is no longer on the wrong side |

### What the code side turned up, which the finding had not

The docstrings were the point of *"spec/comments"*, and correcting them
surfaced two things the register did not have:

- **The `"generate"` next-action state is unreachable.** It is gated on
  `any_stale`, which is forced `False`, so that branch never returns. The
  docstring described what it *would* catch as though it ran.
- **The code comment forecast a PR that had already shipped.** It read
  *"force False here **until PR 5.3** retires the legacy pinning path
  entirely"* — and PR 5.3 shipped, retiring the group-instrument rule gate
  (`session_lifecycle.py:779`). So the force is not pending; it is the
  design. Rewritten to say so, and to give the real reason: an
  always-stale badge trains the operator to ignore it, *"which is worse
  than reporting nothing."*

*Both are the same defect as the specs had — a description that outlived
what it described — sitting in the code rather than in `spec/`. `CC-01`,
`CC-03`, `CC-05` and `CC-11` are the same class and remain open.*

### Still open from the SC block

**SC-05 through SC-36 are untouched.** SC-05 is the sibling of SC-04 — a
test pinning the code's heading format *while citing the spec section it
contradicts* — and was not named in the instruction, so it stays. The
register's tally is unchanged at **75**; four are now marked actioned
rather than removed, because *what a finding became is worth more than its
absence.*

---

## Verification pass — what the five checks caught, and what it cost

`spec-writer` was run per batch in **Mode B** (report-only; see
`.claude/agents/spec-writer.md`). Two passes have reported. **Both found
errors the sweep introduced**, which is the fourth time today a pass has
caught the previous one.

### Corrected here — six, each verified independently before the edit

- **A corrupted primitive name made a published contrast figure wrong.**
  `color_tokens.md` said *"a pair at `--gray-soft` / `--slate-deeper`
  measures 1.47:1 light and 1.95:1 dark"*. **I recomputed both:**
  `--slate-deeper` (`#2b3547`) on `--ink-abyss` is **1.50**;
  `--slate-deep` (`#3a465c`) is **1.95**. The pre-sweep text named
  `--slate-deep` and even carried a footnote reconciling that exact
  figure. One letter, and the number attached to it became false.
- **An overclaimed test guarantee.** `ui_elements.md` said
  `test_pager_link_style.py` *"asserts no rule for those selectors
  survives"* for **five** class names. It pins **four**;
  bare `.table-pager` and `.table-pager-jump` are asserted nowhere. Now
  states which four the test holds and that the other two are held **by
  the paragraph alone** — *"a rule for either would pass the suite; that
  is what the prohibition is for."* **The sweep invented a stronger
  guarantee than exists**, which is worse than the retirement record it
  replaced.
- **A cross-theme match that holds in one theme.** `visual_style_rrw.md`
  said `expired` is red *"matching the reviewer dashboard's 'closed' pill
  so the post-window state reads the same on both surfaces."* In dark the
  lifecycle pair resolves to `--red-bright` and the dashboard's error pill
  to `--red-soft`. Now says the **hue** is the shared signal and the value
  is not — which is what the surrounding paragraph already argued.
- **A categorical claim false outside one wrapper.** *"No
  `margin-bottom`. A card's vertical spacing comes from its wrapper's flex
  or grid `gap`."* True inside `.page-grid` / `.bottom-grid`, which zero
  it; a bare `.card` keeps the base margin, which is what stacks
  consecutive top-level cards on the sys-admin pages.
- **`301` where the code says `308`, twice.**
  `rrw_functional_spec.md:1016,1052`. The sweep corrected this same fact
  in `session_home.md` and left it standing here, producing a **three-way
  disagreement** in which the functional spec was the sole outlier.
  `_session_home.py:249` is `HTTP_308_PERMANENT_REDIRECT`.
- **A mechanical artifact of a trim.** `setup_pages.md` had an orphan
  semicolon opening a line where a parenthetical had been cut.

### Two `spec/README.md` rows, both pre-existing

Neither was touched by the sweep, and both were caught by asking for a
second opinion on them:

- The `roundtrip_coverage.md` row described that file's gap list by its
  **old** contents — *"feature toggles"* has **0** occurrences in the file,
  and *"roster status"* is listed there as something that **does**
  round-trip. Repointed to the four gaps the file actually names.
- The `ui_elements.md` row called it *"current implementation per element
  family"* — ship-state framing for a file whose own opening says it is
  **the contract**. Reframed.

### Reported and left standing

- **`permissions.md`'s verification recipe does not find its own answer.**
  The invariant holds — a mechanical parse of 132 session-scoped routes
  found 0 violations — but the *method* the spec describes ("scan every
  `@router.get/post` decorator") would falsely flag at least 9 routes in
  `_instruments.py`, whose gate is two levels deep via
  `_require_instrument_in_session`. **A stated method that would produce
  false positives is worse than no method**, because the next person runs
  it and believes the result. Filed as **SI-06**.
- **`operations_pages.md`'s query budget is pinned by nothing.** The
  43 / 84 / 134 / 234 / 434 table is presented as *"measured through the
  real routes"*; the only related test asserts **relative growth under
  2.5×** and would pass with every figure drifted. Filed as **SI-07** —
  the frozen-measurement class, in the one place it was kept deliberately.
- `quick_setup_card_spec.md` lost the fact that the per-slot endpoints have
  **no live caller** (0 hits across the templates) when *"retained for
  fixture compatibility"* was trimmed as unverifiable. The trim was right;
  the fact is worth restoring. Filed as **SI-08**.
- `docs/status.md:308` narrates the *earlier, partial* `ui_elements.md`
  sweep — a "How to read an entry" note and residual apparatus blocks —
  which this segment has since removed entirely. It is a dated journal
  entry so it is not wrong, but a reader following it will not find what it
  describes. Out of `spec/`'s scope.

*The pattern across all four passes today is the same and worth stating
once: **every pass caught the previous one and introduced its own.** Ten
edits, three wrong; the reversal, two wrong; the sweep, six wrong. The
defect rate is not falling, so the check is not optional — and the two
errors here that mattered most were both a **single token or number
substituted inside an otherwise correct sentence**, which is the hardest
kind to see and the easiest kind to compute.*

### Passes 3 and 4 — four more corrected, two registered

**Corrected (verified independently first):**

- **A route path missing its router prefix.** `reconciling_regeneration.md`
  gave Prepare session as `POST /sessions/{id}/workflow/prepare`. The
  router mounts at `prefix="/operator"`, so the path is
  `/operator/sessions/{id}/workflow/prepare` — which `workflow_card.md` and
  `next_action_card.html` both carry correctly. **A URL is contract**, and
  this one 404s for anyone who builds the request from it.
- **`spec/README.md` contradicted the spec it indexes.** It described the
  reviewer sort as having *"live-only persistence"* while
  `sort_by_reviewee.md` had just corrected its own heading to *"view-time
  override"* and its body describes a cookie. Both were edited the same
  day, in different batches — *the index is the one place a
  cross-batch inconsistency has nowhere to hide, and nothing checks it.*
- **`spec/README.md` described `role_landing_and_visibility.md` by removed
  text** — its *"recorded from a running app"* method claim and an
  observer-archive item now written as a standing guard rather than an open
  divergence. The sweep touched the target and not its index row.
- **`preview_hub.md` denied a live sibling section.** It said *"there is no
  Preview Pages grouping in the page taxonomy"* while
  `operator_ui_concept.md` §"4. Preview Pages" carries the grouping,
  `README.md` lists it, and `operator_ui_concept.md:22` names
  `preview_hub.md` as *"the Preview Pages contract"*. The pre-sweep text
  said the grouping *"is retired"* — false the same way — so the sweep
  **restated a pre-existing falsehood in the present tense** rather than
  introducing it. Now states that the grouping has one member and that the
  grouping and the tab row are different axes.

**Registered, not fixed:**

| id | where | what |
|---|---|---|
| SI-06 | `permissions.md` | the stated verification recipe would falsely flag ≥9 routes whose gate is two levels deep via `_require_instrument_in_session`. **A method that produces false positives is worse than no method**, because the next person runs it and believes the result. The invariant itself holds — 132 routes, 0 violations |
| SI-07 | `operations_pages.md` | the 43/84/134/234/434 query budget is presented as *"measured through the real routes"* and **nothing pins it**; the related test only asserts relative growth under 2.5× |
| SI-08 | `quick_setup_card_spec.md` | lost the fact that the per-slot endpoints have **no live caller** (0 template hits) when *"retained for fixture compatibility"* was trimmed as unverifiable. The trim was right; the fact is worth restoring |
| SI-09 | `validate_page.md` | `### 3.2 Current rules (18 registered)` — accurate today (18 `ValidationRule` entries) but a tree measurement in a heading, the self-staling class. Predates 19M |
| CC-10 | `_display_fields.py:797-801` | the `SortSpecError` docstring lists **3** of the **5** codes it raises. Code-internal |

**One verification claim was itself wrong, and the repo's own guard
settles it.** The Item 5 pass wrote that `instruments_index.html` has
*"embedded NULs elsewhere in it"*. It has **none** — `tests/unit/test_templates_are_text.py`
passes and a byte count returns 0. That guard exists because of 19L.4, and
this is the first time it has answered a question rather than prevented
one. *Five verification passes, one false claim: the same rate as the
sweeps they were checking.*

### Pass 5 — Item 6, the highest-risk batch. Three more corrected.

**All seven compatibility tolerances survive and are stated as
obligations**, each re-verified against the code by the pass: the
`field_labels.*` silent ignore (`_apply_parse.py:196-222`, where an
unmatched top-level key falls through to "Unknown field path — silently
ignore"); the `display_fields[m].label` drop (`_apply_instrument.py:81-86`);
case-insensitive `data_type` (`_apply_parse.py:59-60` lowercases before
validating — **and the spec generalized it correctly**, since it is every
row's third column, not an RTD quirk); the data-shape fallbacks;
permissive-read / strict-write on identity label slots; the six
`localStorage` keys; and rehydrate's presence inference
(`session_rehydrate.py:496-507`, inferred *before* `apply_session_config`
at :515). **The two wholesale section deletions cost no input obligation** —
neither §4.5 nor §6 carried one, both only pointed elsewhere, and no
`see §4.5` / `see §6` survives anywhere.

**Corrected:**

- **The sweep replaced an accurate statement with a false one.**
  `email_infra_options.md` came to read *"the enqueue paths write only
  `queued` until the dispatch helper lands."* **Verified false:**
  `invitations.py:297` writes `status="queued"`, flushes, and **flips it to
  `sent` six lines later in the same call** — no row is ever persisted at
  `queued`. The pre-sweep text said *"`queued`, `sent` today"*, which was
  right, and the rewrite also contradicted `email_template_editor.md`,
  untouched, which describes the same path correctly. *This is the clearest
  instance of the failure mode: a sentence written from the surrounding
  prose rather than from the code it describes.* Now states that only
  `queued` and `sent` are persisted and that `sending` / `failed` exist for
  a dispatcher that does not run.
- **A column that does not exist, asserted more firmly than before.**
  `roundtrip_coverage.md` carried a matrix row and an asymmetry note for
  `session_rule_sets.library_origin_id`. **Verified gone**: column, FK and
  index were dropped by
  `alembic/versions/d8f4a92c1e6b_wave5_pr2_retire_rule_set_library.py`, and
  the model's own docstring says so. The claim predates 19M — but the sweep
  **rewrote that line and made it more specific** (*"emits no
  `library_origin_id` cell"*, which asserts the column exists), without
  checking. Row removed; the asymmetry now names only `assignment_mode`.
- **A provenance citation the sweep removed everywhere else in the same
  file.** `csv_contracts.md` §3.1 kept *"`Status` (18P PR C)"* while the
  parallel §2.1 / §2.2 tables and §3.2b had theirs stripped. `csv_contracts.md`
  now carries **0** such citations.

**Registered:**

| id | where | what |
|---|---|---|
| CC-11 | `_serialize.py:561` | comment reads *"the `library_origin_id` column … stays for now (drops in PR 5.2)"*. PR 5.2 shipped and dropped it — a code comment that outlived its own forecast |
| SI-10 | `csv_contracts.md` §3.3 | the `rtds[` import tolerance exists only as an aside inside the `field_labels.*` bullet (*"like an `rtds[` row"*), before and after the sweep. **The enforcement is stronger than its documentation**: `_apply_parse.py:196-201` returns early unconditionally. Worth its own bullet |

### The verification tally, stated plainly

**Five passes; thirteen sweep errors corrected; one pass wrong itself.**

Three of the thirteen share a shape worth naming, because it is not
carelessness and re-reading would not have caught it: a **single token or
number substituted inside an otherwise correct sentence** —
`--slate-deeper` for `--slate-deep`, `301` for `308`, *"writes only
`queued`"* for *"`queued`, `sent`"*. In each case the sentence read
plausibly, the surrounding argument was sound, and the only way to catch it
was to compute the value or open the file. *Two of the three replaced text
that had been **correct** before the sweep touched it.*

That is the argument for the check, and for its cost: the sweep's own §1
says a `*Current:*` block rots because nothing renews it. §2b said a finding
rots unless something checks it. This section is the third turn of the same
screw — **a correction rots too**, and the only thing that catches it is
another pass that reads the code rather than the prose.

---

## ACTIONED — the SI, doc-only SS, and DT rows (Segment 19M Items 9 and 10)

### Item 9

| id | resolution |
|---|---|
| SI-01 | `+Page break` added to **both** action-row lists in rendered order (Delete → `+Instrument` → `+Page break` → Lock/Unlock). The template renders it, so the lists were the wrong side |
| SI-02 | **a distinction, not a correction** — five roster-shaped pairs exist and byte-stability is established for four; whether Observers meets it is unverified, and the file now says so rather than implying either |
| SI-03 | the duplicate `audit_events` row removed; the survivor states **what its ✅ does and does not mean** — there is an extract, and audit events are outside this inventory's scope, so there is nothing here to round-trip |
| SI-04 | the two-clause Upload confirm label now **points at** the three-clause one. The template renders count / assignments / responses, and *the response clause had gone missing once already* |
| SI-05 | *(See "Form scope" below)* → §"Form HTML mechanics", the section that exists |
| SI-06 | `permissions.md`'s method now says to follow `Depends()` **transitively**, because a decorator scan flags ≥9 correctly-gated `_instruments.py` routes. *A check that flags a correctly-gated route is worse than none, because the next reader believes it* |
| SI-09 | the rule count comes **out of** the §3.2 heading rather than being re-measured |
| SS-04 | Observers and Extract data added as chrome rows **12 and 13** — appended, not slotted, because that file states its own rule that numbers are stable identifiers other documents cite |
| SS-05 | `Invitations`, the chrome label, in all four places. **Not one-sided**: `email_infra_options.md` used *"Manage Invitations"* three times, so it was a vocabulary in circulation |
| SS-06 | **twelve states over ten numbers** — 1–10 with `4W` and `4Err` — stated in `workflow_card.md`, so the five documents calling it a *ten-state cascade* stop reading as errors |

**Still registered from this group:** `SI-07` (the query budget). Rewording
does not fix it — nothing pins the figures and the related test only asserts
relative growth. **A guard is the right answer and a guard is code.**
`SI-08` and `SI-10` likewise remain, as prose additions rather than
corrections.

### Item 10

| id | resolution |
|---|---|
| DT-01 | §6.1 requoted to the charter that exists: at a close, align the spec to what shipped; outside one, the spec wins and divergence is reported. Its own default quoted — *"if you cannot tell which mode you are in, you are in Mode B"* |
| DT-02 | §6.4's unqualified *"updates `spec/` to match the code after a change"* now carries **at a close** — and the passage names the contradiction it had papered over, since it stated both halves side by side without noticing they conflicted |
| DT-03 | the Appendix maker/checker row qualified the same way |
| — | **§6.2's trade-off restated.** It said *"only the functional spec dates itself: **4 of 36**"*; **no live spec carries a currency line at all now** — 19M replaced each with a sweep-record pointer. The figure was the smaller half: the paragraph described a *mechanism* that no longer exists |

### DT-04 dissolves — and that is the finding

`docs/practice-audit-2026-09-04.md` quotes the old charter;
`guide/todo_master.md` mentions `spec-writer` five times. **Neither was
changed, and neither is an omission.** The practice audit is a **dated**
document whose quote was accurate on its date, and `todo_master.md`'s
mentions record what a *pass found* rather than what the charter says.
Repointing either falsifies a log.

*That is the same call the sweep made four times over `spec/` — and making
it correctly here, on the last item, is the only evidence that the day's
lesson took rather than being written down.*

---

## The register was wrong about two of its own fixes

Asked whether the register reflected the fixes, I audited all **25 actioned
claims** mechanically rather than answering from memory. **23 held. Two did
not:**

| id | the register claimed | the truth |
|---|---|---|
| **SI-02** | *"the file now says so"* — five pairs exist, byte-stability established for four, Observers unverified | `csv_contracts.md` still said *"five main roster-shaped pairs"* in its header and *"the four roster-shaped pairs"* in §4, **with no distinction between them.** The fix existed only in the plan's Semantics section and in this register |
| **SI-05** | *(See "Form scope" below)* → §"Form HTML mechanics" | `reviewer-surface.md:145` still said *"Form scope"* |

**Both are now actually fixed**, and `csv_contracts.md` §4 states the gap
rather than implying either way: *"Observers is the fifth pair and is not
claimed here … a guarantee that quietly covers four while the header counts
five is how a round-trip regression goes unnoticed."*

### Why this happened, precisely

Both were described in Item 9's **plan** — SI-02 in its `Semantics`, SI-05
in its finding list — and **neither was in the script that ran.** I wrote
the intent, wrote the record of having done it, and did not do it. The
suite could not catch it: nothing tests spec prose against a register.

*This is the fifth turn of the same screw, and the sharpest, because it is
the register's own integrity rather than a spec's.* §1: a `*Current:*` block
rots because nothing renews it. §2b: a finding rots unless something checks
it. §7: a correction rots too. The tally section: a count rots. **And now: a
claim that a thing was fixed rots the moment it is written, because it is
believed on sight and nothing re-derives it.**

**What the audit is, so it can be re-run.** 25 predicates, one per actioned
row, each `True` only if the edit is present in the file — not a search for
the finding's *description*, which is what made the two invisible. Two
minutes to write, and it is the only reason this answer is not "yes,
updated."

*The honest reading of the day's error count is now **fifteen**, not
thirteen: thirteen wrong claims about the code, and two wrong claims about
having fixed them.*
