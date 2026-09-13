# Findings — spec discrepancies surfaced by Segment 19M

**Opened** 2026-09-13 · **Source:** the `spec/` history sweep
(`guide/segment_19M_spec_history_sweep.md`, record at
`guide/sweep_2026-09-13_spec_history.md`).

**Why this file exists.** 19M was a prose sweep, and the rule it ran under —
`rrw_sdd_in_practice.md` §4, *the spec is the contract; when the code drifts,
fix the code* — means a sweeper who finds spec and code disagreeing **may not
quietly rewrite the spec to match**. So every divergence became a finding
instead of an edit. This is that register: one table, every finding, resolved
rows struck through with what the fix was.

**86 of 86 resolved. 0 open — closed 2026-09-13.**

Every row is struck, and the last column of each says what the fix was.
There is no bucket table any more because there is nothing left to
bucket; what the buckets meant is kept below, since the reader of a
closed register wants to know how the rows were sorted before they were
settled.

**Two rows carry forward as work rather than as findings**, which is not
the same as being open:

- **`SC-42`** — assignment row status does not round-trip.
  `spec/roundtrip_coverage.md` now states it as a knowing gap and marks
  carrying it as future work.
- **`SC-45`** — the mixed email-folding convention, logged as **19N Item
  2** with the sites tabulated and the choice of fold left to the
  author. No code moved: picking wrong fails closed for a real
  participant.

*`SC-02` and `SC-03` were resolved, reopened by 19N behaviour (3), and closed
again by slice 1 — they stay struck throughout, because both fixes happened
and the second replaced the first rather than undoing it. `SC-09` closed in
slice 5.*

**Resweep 2026-09-13, after 19N.1 closed.** Every open row re-read against the
code that item left behind. Eight rows closed across its seven PRs (`SC-02`,
`SC-03`, `SC-09`, `SC-37`, `SC-38`, `SC-39`, `SC-40`, `SC-41`) and one opened
(`SC-44`). One open row changed shape rather than closing: `SC-27` now has a
cheaper fix available. `SC-06`, `SC-22`, `SC-26`, `SC-28`, `SC-32` and `SS-02`
were re-checked and stand as written — 19N.1 touched none of the code they
name.

## Reading key

| tag | kind |
|---|---|
| **SC** | spec says one thing, code does another |
| **SS** | two live specs disagree |
| **SI** | one spec contradicts itself |
| **CC** | two code comments disagree, or a comment names something absent |
| **ID** | a spec names an identifier that does not exist |
| **DT** | a document describes its own tooling imprecisely |

Each open `SC` row carries a **bucket**, so they can be ruled in batches
rather than one at a time. The bucket is a read, not a finding:

- **(a)** the code looks intended and the spec is stale — the `SC-01`…`SC-04`
  shape, which the author ruled *"update spec/comments; code is correct"*.
- **(b)** the spec states a requirement the code has not met. Here the spec is
  working, and the question is whether to build or to retire.
- **(c)** a genuine judgment, where neither side is obviously right.

A bucket is not a verdict. Two rows sat in (a) on a first pass while their own
text argued the code was the bug — accepting (a) wholesale would have rewritten
a contract this register was defending. Read the row before applying the batch.

**The (a) batch was worked on 2026-09-13**, each row verified against the code
before any spec moved. Nine closed. The caveat above earned its place twice
over: `SC-16`'s code carried a comment explaining why it diverged, so the spec
was the only side that had not been told; and `SC-25` was not a wrong number
to correct but a **count that should not have been in a spec at all** — nothing
renews a tally, so it staled the day it was written, and the fix was to name
the audience rather than count the cards.

The remaining four were put to the author, who ruled `SC-05`, `SC-12` and
`SC-29` as (a) and re-bucketed `SC-19` to (c) for investigation. Twelve of the
thirteen are now closed. **The spec check then found three errors inside the
first batch's own `SC-11` rewrite** — a validator attributed to a function with
no caller in `app/`, and two rules (a minimum-step tied to type precision, a
duplicate-option check) carried over verbatim from the old text and enforced
nowhere. The lesson is narrower than "verify": *rewriting a paragraph does not
inherit verification of the sentence above it*, and clauses kept from the text
being replaced are the ones least likely to be checked.

## The findings

Grouped by kind, ids ascending. Struck-through id = resolved; the last column
says what the fix was. Every `where` is the contract side; `reality` is the
code, the other spec, or the other comment.

| id | where | contract / one side | reality | disposition |
|---|---|---|---|---|
| ~~`SC-01`~~ | `settings_inventory.md` §10 | a `session_rule_sets[n].library_name` row on input must be **recognized and skipped** | `_apply_rule_set.py:53` raises; apply is two-phase, so the **whole import is rejected** | **Fixed** — spec now states the strict reject as deliberate, with its reason (a misspelled attribute would otherwise be dropped in silence) and its cost (such a bundle needs the column removed first) |
| ~~`SC-02`~~ | `assignments.md` | a `stale` pill when a rule + roster pass would produce a different set | `views/_assignments.py:221` hardcodes `is_stale = False`; `:202` `any_stale = False` | **Fixed** — spec states the absence as the contract: no `stale` pill, no staleness signal, and a rule edit is invisible until regeneration. Also surfaced that the `"generate"` next-action state is unreachable, and a code comment forecasting a PR that had shipped | **Closed again by 19N slice 1 (2026-09-13).** The first fix stated the absence as the contract; the signal is now restored on a different basis — the engine's own reconcile diff rather than a count of eligible pairs — so `spec/assignments.md` states the presence again. Three dead consumers revived with it: the pill, `any_stale`, and `instruments.stale_generated`, which had been a **registered no-op** giving Validate a clean bill on exactly what it existed to catch
| ~~`SC-03`~~ | `assignments.md` §Staleness | the check is `stamp_changed(instrument, db)` | 0 occurrences in `app/` or `tests/` | **Fixed** — section removed with `SC-02`; the helper does not exist | **Closed again by 19N slice 1 (2026-09-13).** The first fix stated the absence as the contract; the signal is now restored on a different basis — the engine's own reconcile diff rather than a count of eligible pairs — so `spec/assignments.md` states the presence again. Three dead consumers revived with it: the pill, `any_stale`, and `instruments.stale_generated`, which had been a **registered no-op** giving Validate a clean bill on exactly what it existed to catch
| ~~`SC-04`~~ | `reviewer-surface.md` | `typical_chars = max_length * 0.75` | `views/_instruments.py:226` is `0.5`, and `test_instrument_builder_routes.py:6859` **asserts** `0.5` | **Fixed** — spec now `0.5`. The gate is no longer on the wrong side |
| ~~`SC-05`~~ | `reviewer-surface.md` | the spec's heading format | `test_reviewer_view_helpers.py` pins the code's format **while citing the spec section it contradicts** | **Fixed 2026-09-13** — the composition table now matches `instrument_heading` on both counts it got wrong: the multi-instrument prefix is `#{N}`, not `Page #{N}`, and a single instrument with only a description renders that description as the H2 rather than no heading at all. The second is a deliberate legacy fallback the code and its test both carry; the spec had it as *no heading renders* |
| ~~`SC-06`~~ | `assignments.md` | `POST …/assignments/instrument/{iid}/self-reviews-active` | `…/assignments/{instrument_id}/self-reviews/active` (`_assignments.py:479`) | **Fixed 2026-09-13** — spec now names the shipped path, `POST /sessions/{sid}/assignments/{iid}/self-reviews/active` (`_assignments.py:490`). A URL is contract, so the side that moved is the one no bookmark or form action depends on |
| ~~`SC-07`~~ | `csv_contracts.md` §4 items 1 and 7 | seeded RuleSets are not re-emitted, or a re-import trips `uq_session_rule_set_session_name` | `_serialize._non_seeded_session_rule_sets` returns every row | **Investigated on instruction: not a bug.** Seeding was retired and apply upserts by name, so neither half held. Spec rewritten, and it had been citing a test file that does not exist |
| ~~`SC-08`~~ | `csv_contracts.md` §5 | `decode_csv(content: bytes) -> str` | `decode_csv(content, source, *, max_bytes=…) -> tuple[str \| None, ValidationIssue \| None]` | **Fixed 2026-09-13** — the helper table now carries the real signature, and says why it returns a `ValidationIssue` instead of raising (a caller renders the two operator-facing failures like any other validation problem) rather than only what it returns |
| ~~`SC-09`~~ | `settings_inventory.md` §2 | the **session-level** `assignment_mode` takes `manual` / `rule_based` | written only `rule_based` (`_generate.py`), reset to `None` when every assignment is deleted | **Fixed 2026-09-13 (19N slice 5).** §2 now says `rule_based` or NULL, names the engine as the only writer, and states what NULL *means* — never Generated, the state delete-all restores and three validation rules skip on. `roundtrip_coverage.md` updated with it |
| ~~`SC-37`~~ | the contract: *assignments are never hand-created, uploaded or edited — always generated* | no operator path creates an assignment outside the rule engine | **Rehydrate does.** `POST …/rehydrate/commit` → `rehydrate_session` → `load_responses` creates `Assignment(…, created_by_mode="manual")` at `responses_import.py:330-341` for any (reviewer, reviewee, instrument) triple the responses CSV carries that the regenerated rules did not produce | **Decided 2026-09-13: load what legitimate assignments can carry, and export a CSV of the responses dropped** (19N behaviour 4). The author superseded an initial *fail loudly* with this: nothing is invented, nothing vanishes, and a restore whose rules moved since collection still completes. Originally registered as needing a decision: The pipeline regenerates via `replace_assignments` first (`session_rehydrate.py:598`) and backfills second (`:608`), so the alternative to creating the row is **dropping the response** — data loss on a restore. Either the backfill is legitimate and the contract needs an exception naming it, or rehydrate must fail loudly when responses reference a pair the rules do not generate. **Fixed 2026-09-13 (19N.1 slices 3a + 3b).** The backfill is gone; a row the rules did not produce is dropped, reported and downloadable. With it went the last `created_by_mode="manual"` writer in the codebase, which is what made slice 4 possible. This was the one place the contract was reachable by an operator |
| ~~`SC-38`~~ | the same contract | a row's recorded mode can only be a value the engine produces | `Assignment.created_by_mode` is `String(32)` with **`default="manual"`** (`assignment.py:57`) — not the `AssignmentMode` enum, whose only member is `rule_based`. So the column's default is a value the enum does not admit, and any future `Assignment()` without an explicit mode is stamped `manual`. **Nothing reads the field**: all four app references are writes | **Fixed 2026-09-13 (19N.1 slice 4).** Defaulted to `rule_based`; the 14 test files seeding `"manual"` (16 occurrences — the measured figure, after an earlier miscount of "ten") now seed the real value, so no fixture asserts a retired vocabulary. **Retiring the column was the larger option not taken:** 67 `Assignment(...)` constructions across `tests/` omit the field, so binding it as required would have churned 67 sites, and dropping it would close the seam the enum exists to hold open for a second mode. A test now pins the default and dies if it returns to `"manual"` |
| ~~`SC-39`~~ | `instruments.md` — `+Instrument` and `Replicate` | neither section listed assignment rows among the side effects | `_instrument_crud.py:255` and `:412` cloned them from a source instrument, inheriting `created_by_mode` | **Fixed 2026-09-13 (19N slice 2).** Both clones removed; a new or duplicated instrument gets no rows and waits for Generate. The spec had never documented the clone, so the silence is now explicit rather than merely unbroken. **Eleven reviewer-surface tests silently depended on it as fixture setup** — their comment said *"no manual Assignment seeding is needed"* — and now regenerate instead, which is what the operator does; the second generate needs `confirm_replace`, without which the route is a no-op redirect the clone used to hide. *Completed 2026-09-13: this row was struck while `replicate_instrument`'s own docstring still said "Assignment rows are cloned from the source so the replica joins the matrix immediately" — the code had changed, the sentence describing it had not. Found by re-verifying the struck rows against the shipped code rather than trusting the strike. Sixth instance in this segment of prose outliving the thing it describes, and the only one in a file the fix itself edited.* |
| ~~`SC-10`~~ | `settings_inventory.md` §2 | Edit surface is `/operator/sessions/{id}/edit` | `_session_home.py:241` is a **308** to `…?editing=1#session-config`; the page is gone | **Fixed 2026-09-13** — §2 now says editing is **inline on Session Home** (`?editing=1#session-config`) and that `/edit` survives only as the 308 shim, so an old bookmark still lands right. The sub-page the spec described has not existed for some time |
| ~~`SC-11`~~ | `instruments.md` | Band 3 bounds rules for `Number` / `Rating` / `SingleSelect` / `MultiSelect` | `bulk_save_fields` branches on `String` / `Integer` / `Decimal` / `List` — the four the spec's own Type picker lists eight lines above | **Fixed 2026-09-13** — the bounds list now names the four `data_type` values the validator branches on (`String` / `Integer` / `Decimal` / `List`, `_response_fields.py:160-177`), which are the same four the Bounds row eight lines above already used. The old list named response-type display names that reach no branch |
| ~~`SC-12`~~ | `reviewer-surface.md` | Discard labeled `Discard`; a per-page `Page #{N}: {short_label}` button; Save is Primary | `Cancel`; `< Previous page` / `Page {N} of {M}` / `Next page >`; Save is `.btn.secondary` | **Fixed 2026-09-13** — the control is labelled **`Cancel`**, not `Discard` (the `data-rs-discard` hook keeps the older name, and the spec now says so), and `Save` is **Secondary**, not Primary. Renamed at all 21 references rather than one, since prose naming a control must quote the control (`CLAUDE.md`). The pager prose was already correct — the register's paraphrase of it was the stale part |
| ~~`SC-13`~~ | `reviewer-surface.md` | page buttons carry `max-width: 16em; text-overflow: ellipsis` | neither rule exists in `base.html` | **Fixed 2026-09-13 (author: follow code)** — the truncation rule does not exist; the spec no longer promises it. A label past the 32-char cap renders full width, and the Setup-side cap is the only guard |
| ~~`SC-14`~~ | `reviewer-surface.md` | Enter / Shift+Enter move focus down / up a column | **no `keydown` handler on the reviewer surface at all** | **Fixed 2026-09-13 (author: follow code)** — Tab is all that ships; the surface binds no `keydown` handler. Column-wise Enter / Shift+Enter moved to the *what lands later* list, **keeping its two obligations** (Enter must not submit the form, Enter in a `<textarea>` stays a newline) so they are not rediscovered when it is built |
| ~~`SC-15`~~ | `reviewer-surface.md` | status column renders on `submitted_at` **or** `show_acknowledge` | `_context.py:528` uses `show_incomplete_marks`; `show_acknowledge` has 0 occurrences — and the same file says elsewhere there is no such flag | **Fixed 2026-09-13 (author: follow code)** — the flag is `show_incomplete_marks`; `show_acknowledge` exists nowhere. Both halves of the self-contradiction now agree, and the *no checkbox* paragraph names the real flag instead of denying a fake one |
| ~~`SC-16`~~ | `reviewer-surface.md` | dashboard `closed` renders `pill-lifecycle-archived` (muted grey) | `reviewer/dashboard.html:122` renders `pill-error` (red) | **Fixed 2026-09-13** — spec now says `pill-error` (red), with the reason the template already records: it matches the past-deadline pill in the End column, and the muted grey it replaced read as plain text rather than a pill. *The code carried its own justification the whole time; only the spec had not been told* |
| ~~`SC-17`~~ | `reviewer-surface.md` | `submit_redirect_url(review_session, position)` → `/{page_n}` | `submit_redirect_url(review_session, *, fully_submitted=False)` → `/summary` or the bare session URL | **Fixed 2026-09-13 (author: follow code)** — the spec now carries the real signature, `submit_redirect_url(review_session, *, fully_submitted=False)`, and both targets: `/summary` when fully submitted, the bare session URL otherwise (which 303s to `/1`). It takes **no page position** — since 18L the URL slot is the operator-defined page number, so submit does not return the reviewer to the page they were on |
| ~~`SC-18`~~ | `role_navigator.md` §2 | preview route is `…/previews` | the route rendering `review_surface.html` is `…/preview-surface/{page_n}`; `/previews` is the hub | **Fixed 2026-09-13** — spec now names `…/preview-surface/{page_n}` as the route that renders `review_surface.html`, and says `…/previews` is the hub. Both routes exist, which is why the wrong one read as plausible |
| ~~`SC-19`~~ | `role_navigator.md` | identity match is `func.lower(column) == casefold(email)` in SQL | `build_role_chips` folds via `normalize_email` in Python | **Fixed 2026-09-13 (author: follow code, after re-bucketing to (c) for investigation)** — `build_role_chips` folds **both sides in Python** through `normalize_email` (`.strip().casefold()`); there is no SQL-side `lower()` on this path. The investigation's finding: `casefold` and `lower()` are **not equivalent** (German ß, Turkish İ), so the folding function is contract, not detail — the spec now says which one. *It also turned up `SC-45`* |
| ~~`SC-20`~~ | `preview_hub.md` §3 | a per-artifact "Send test to…" affordance, lifecycle-gated | a case-insensitive grep of `app/` for `send test` and for `send_test` → **0** | **Fixed 2026-09-13 (author: follow code)** — marked **Not built**; nothing in `app/` sends a preview to a test address. The design and its constraints stay below as the contract for when it lands, because the `To:`-address rule is the reason to build it carefully |
| ~~`SC-21`~~ | `preview_hub.md` + `session_home.md` | Next Action card carries a "See previews" button in `validated` | no such string anywhere in `app/` | **Fixed 2026-09-13 (author: follow code)** — three passages across two specs said the button exists. All now say it does not, and `session_home.md`'s *no See previews in `ready`* rule becomes *no such button in any state*, keeping the intent that previewing is validation-time |
| ~~`SC-22`~~ | `preview_hub.md` | Operations row is `[Assignments][Validate][Previews][Invitations][Responses]` | `session_top_nav.html` renders a sixth tab, `Extract data` | **Fixed 2026-09-13** — the Operations row now lists six tabs including `Extract data`, with a reason for its position (it is what the operator reaches for once responses are in). Confirmed against `_ops_pages` in `partials/session_top_nav.html:22` |
| ~~`SC-23`~~ | `session_home.md` §1 | an Activated-state exception: body split by `<hr class="next-action-divider">`, `.next-action-buttons` **not** rendered while Activated, `.next-action-confirm` pre-Activated | neither class appears in any template (CSS rules in `base.html` only), and `workflow_card.md` specifies a single button row in **every** state | **Fixed 2026-09-13 (author: follow code)** — the Activated-state exception is gone. The card renders the same two blocks in every state, and `workflow_card.md`'s single-row contract is named as the gate. `.next-action-confirm` and `hr.next-action-divider` are recorded as rendered by no state, and their orphan CSS removed under `SC-36` |
| ~~`SC-24`~~ | `operator_button_audit.md` §11.5 | Inactivate / Activate gated on "≥1 selection" only | the template also gates them, and the count pill, on `can_edit` | **Fixed 2026-09-13 (author: follow code)** — **eight** rows carried the incomplete gate, not the two logged; all now read *≥1 selection **and** `can_edit`* |
| ~~`SC-25`~~ | `role_landing_and_visibility.md` §3 | "the eight operator cards"; a stranger "saw all eleven" | `_guide.py` `SECTIONS` has **12** (9 operator + 3 role) | **Fixed 2026-09-13** — the two table rows now read *every `operator`-audience card* rather than counting them. **The count was the defect, not the number**: a tally in a spec self-stales, since nothing renews it, and `GuideSection.audience` already says which cards those are. The companion *"saw all eleven"* claim had gone already |
| ~~`SC-26`~~ | `reconciling_regeneration.md` | the `include` seed is pair-level via `is_self_review(reviewer, reviewee)` | `_generate.py:334-347` applies the **whole-group** rule on group-scoped instruments, which `assignments.md` specifies | **Fixed 2026-09-13 (author: follow code)** — the pair-level test was the wrong description: on a group-scoped instrument the engine applies the **whole-group** rule. This spec now says when `include` is set and points at `assignments.md` for what a self-review is, rather than restating a rule it was getting wrong |
| ~~`SC-27`~~ | `reconciling_regeneration.md` + `assignments.md` | `reconcile_impact` returns per-instrument counts | returns one aggregate `ReconcileImpact` for the session | **Fixed 2026-09-13 (author: follow code)** — both specs now say `reconcile_impact` aggregates across the session, because the banner is its only consumer and asks one question. The per-instrument shape the specs wanted **exists separately** as `staleness_by_instrument` (19N.1 slice 1), so a preview reads that rather than widening this one; both share the engine's diff and cannot disagree |
| ~~`SC-28`~~ | `quick_setup_card_spec.md` | operator is sent to the Operations Assignments page to regenerate | generation fires from the Workflow card's stepper | **Fixed 2026-09-13 (author: follow code)** — regeneration fires from the Workflow card stepper, where every lifecycle action starts; the Assignments page carries the same action for an operator already there |
| ~~`SC-29`~~ | `csv_contracts.md` §3.3 | the Settings CSV has an RTDs section (example `rtd.Long_text.data_type,…`) | `_serialize` emits no RTD rows; such a row hits the unknown-key ignore | **Fixed 2026-09-13, and widened on the author's ruling** — *"all RTD related stuff should be retired"*. The §3.3 example row and the RTDs section went, and with them the live RTD vocabulary across `app/`: a **dead 89-line template macro**, three **dangling references** to things that do not exist (`validation_block_for_rtd`, `_rtds.py`, `_apply_rtds`, plus `_require_rtd_in_session` in `docs/`), a `counts["rtds"]` counter that could only ever report zero, and a redundant `rtds[` parse branch whose removal changes nothing (those rows land on the same silent ignore). What stays is the back-compat tolerance itself — an old bundle still imports |
| ~~`SC-30`~~ | `ui_elements.md` §1 | Sign out is a **Secondary** control | `base.html:3414-3417` ships a bespoke `.chrome-user .signout` — `--border-default` (not `--btn-secondary-border`), `--text-body`, `--surface-muted` hover | **Fixed 2026-09-13 (author: follow code)** — Sign out is **not** a `.btn` role. It ships a bespoke chrome rule (`--border-default`, `--text-body`, `--surface-muted` hover) that reads Secondary-ish at chrome scale without joining the button vocabulary. The spec said Secondary and pointed at §6 for the definition — a pointer to a role the control does not use |
| ~~`SC-31`~~ | `visual_style_general.md` Patterns | status strip fills `bg-muted` with `border-subtle` **top and bottom**, between chrome and page body | `--surface-card`, top border only, **inside** the nav card | **Fixed 2026-09-13 (author: follow code)** — recorded as an explicit override in `visual_style_rrw.md`, not by editing the cross-app baseline: `.status-row` sits **inside** the session nav card, so it takes `--surface-card` and a top border only. Placement and fill move together — the general spec's `bg-muted` + two borders describe a strip that stands alone, which this one does not. The register had the fill *unaccounted for*; it was the placement override's unstated consequence |
| ~~`SC-32`~~ | `ui_elements.md` §4 vs two other specs | §4 said `.card.danger-zone` has a **white** background | `visual_style_general.md` and `visual_style_rrw.md` both contract the lock card's amber surface, "fill included"; code ships `--card-warning-bg` | **Confirmed 2026-09-13** — three-way agreement verified: `ui_elements.md` §4 now contracts the amber fill (`--card-warning-bg`), the two visual-style specs already did, and `base.html:2014-2017` ships it. Nothing left to rule |
| ~~`SC-33`~~ | `ui_elements.md` pills | `.pill-success` text is `--status-success-fg` | `base.html:3289` ships `--status-success-accent`; they share `--green-deep` in light but **diverge in dark**, and every other pill uses its `-fg` | **Fixed in code 2026-09-13 (author: investigate).** The register's read was right and the reason is now known: `--status-*-accent` is the **glyph** token — signal icons, status symbols, standalone marks on the page background — while `-fg` is the text-on-pill token. `.pill-success` was the only pill reaching for the icon one. **Invisible in light** (both resolve to `--green-deep`) and a **contrast drop in dark**: 6.3:1 for `--green-bright` against 8.0:1 for `--green-glow`, both AA, only `-fg` reaching AAA. The contract was right, so the code moved — which is why an earlier batch's attempt to edit the spec to match was reverted |
| ~~`SC-34`~~ | `session_home.md` | `.next-action-confirm` renders in pre-Activated states | `base.html:3094` has the rule; `next_action_card.html` emits no element with the class | **Fixed 2026-09-13 (author: follow code)** — closed with `SC-23`: no template emits `.next-action-confirm`, the spec says so, and `ui_elements.md`'s parts list drops it |
| ~~`SC-35`~~ | `ui_elements.md` | `placeholder_card` is the reuse point for placeholder cards | the macro has **no callers**; the one live `.card.placeholder` is hand-written in `session_previews.html` | **Removed 2026-09-13 (author: remove if no callers)** — verified uncalled, then deleted: `_placeholder_card.html` is gone and both specs now say the pattern is a **class, not a macro**. Three prose references had to follow, and the path guard caught all three — two repointed, and `docs/status.md`'s dated row marked `path-ref-ok`, since repointing a log falsifies it |
| ~~`SC-36`~~ | `base.html` | — | **orphan CSS with no contract behind it:** `.setup-nav` / `.setup-nav > .btn` (831-839, 0 template users), the `.btn-cta` rules (0 markup callers), `.next-action-confirm` | **Cleaned up 2026-09-13 (author: clean up as recommended)** — `.setup-nav` / `.setup-nav > .btn`, every `.btn-cta` rule (v1 and ui-v2, plus the `.setup-grid` child), `hr.next-action-divider` and `.next-action-confirm` all removed. `base.html` is a generator input, so the theme tools were regenerated with them |
| ~~`SC-40`~~ | `rehydrate.md` §9 | *"no response is lost"* on a restore | **false for group-scoped rows.** `responses_import.py:295-313` warns and skips when a group identity does not resolve or its regenerated group has no member assignments — and `ResponseLoadResult.warnings` is **surfaced nowhere**: not in the `session.rehydrated` audit counts, not to the commit route, not to the operator. The restore commits and the responses are gone | **Code, and the most serious row here.** Silent data loss on a restore path, present today and independent of `SC-37`. Found by the Codex review on #2358, verified here. **Fixed 2026-09-13 (19N.1 slices 3a + 3b).** The row is dropped with a reason, counted in the `session.rehydrated` audit event, and downloadable as a CSV from the Rehydrate page's outcome card — a commit that drops rows deliberately does **not** redirect, because a 303 cannot carry a file. The `warnings` list it replaced was read by nothing at all |
| ~~`SC-41`~~ | the contract: `manual` is not reachable | a clone's `assignment_mode` reflects its own assignments | `session_clone.py:107` copied it from the source, so a clone claimed a generation that never happened — it carries **no** `Assignment` rows | **Fixed 2026-09-13 (19N slice 5), and it was a live bug, not only contract drift.** NULL is this codebase's marker for never-Generated; three validation rules skip on it so a session with no pairs is not *also* told every reviewer is missing. A clone defeated that skip — proven by a test that failed with `assignments.reviewer_missing` sitting beside `assignments.no_included_pairs`, exactly the doubled noise the skip exists to prevent. Clones now start NULL, which also stops a legacy `manual` propagating |
| ~~`SC-42`~~ | the author's contract — *"individual rows can be turned inactive, and that's the extent of operator manual work **and export import round trip**"* | inactivation survives the round trip | `Assignment.include` is carried by no export and reset to `True` whenever assignments regenerate; `rehydrate.md` §9 admits it. There is no assignments extract at all | **Ruled 2026-09-13 (author: follow code; mark the gap clearly).** `spec/roundtrip_coverage.md` now names it outright: **assignment row status does not round-trip**, and this is the one place the author's contract is knowingly unmet — inactivation is the whole manual surface, and it is the part that does not survive. **Carrying it is future work**, recorded so it is not rediscovered as a bug |
| ~~`SC-43`~~ | `session_home.md` / the Next Action card's intent | a pre-Validate Generate nudge exists for the operator | `compute_next_action_generate_state` (`views/_assignments.py:308`) is **called by nothing in `app/`** — exported from `views/__init__.py` and exercised only by tests. `15B` Slice 4 wired it; `1a5b8608`, *"strip Home route validated plumbing and unused imports"*, unwired it, and nothing noticed. `page_ctx.any_stale` exists solely to feed it | **Retired 2026-09-13 (author: retire).** `compute_next_action_generate_state`, `NextActionGenerateState`, both exports and the seven-test file are gone — and with them `page_ctx.any_stale`, which existed only to feed the resolver and became dead the moment it went. Suite 3,892 → 3,885. *The affordance was wired by 15B Slice 4 and unwired by a commit titled "strip unused imports"; four months later the decision was to let that stand* |
| ~~`SC-44`~~ | `rehydrate.md` §7 | the `session.rehydrated` audit event carries counts for `reviewers`, `reviewees`, `observers`, `relationships`, `assignments` and `responses` | the orchestrator builds four keys — `reviewers`, `reviewees`, `responses`, `responses_dropped` — and **three of the six named have never existed**. §7 also promises a `refs` slot that `EVENT_SCHEMAS` does not admit for this event type | **Ruled 2026-09-13 (author: follow current code; anything more is future work).** §7 already names the four keys the orchestrator builds — aligned during 19N.1's close. Whether a rehydrate *should* audit observer, relationship and assignment counts stays unanswered, and stays future work rather than an open discrepancy |
| ~~`SC-45`~~ | `email_identity.normalize_email`'s docstring — *"Use this at **every** identity-comparison site so the uniqueness gate ... and the access gate ... use one convention"* | **the convention is not one.** `normalize_email` is `.strip().casefold()`, but **ten-plus sites compare SQL-side** with `func.lower(column)` — `users.py:479`, `participants.py:94,102,118`, `_coverage.py:296,360,368`, `audit.py:894`, `_session_home.py:625`, `_dashboard.py:100`. Several compare a `func.lower` column against an already-`casefold`ed Python value | **Logged 2026-09-13 (author: log as a 19N item)** as **Item 2 — one email fold, not two** in `guide/segment_19N_generated_assignments.md`, with the ten sites tabulated and two open questions for the author: which fold wins, and whether a stored normalized column pays for itself. No code moved — picking wrong fails closed for a real participant |
| ~~`SS-01`~~ | the five validation severities | `instruments.no_fields` error; `no_display_fields` warning; `zero_included` warning; `assignments.no_included_pairs` warning; `reviewer_missing` warning — `validate_page.md` **agrees with the code** | `instruments.md` and `assignments.md` say warning / info / error / error / error | **Fixed 2026-09-13 (author: follow code).** The shipped severities are error / warning / warning / warning / warning, which is what `validate_page.md` already said; `instruments.md` and `assignments.md` now agree. **Two of the five were specified as errors where the code warns** — built as written they would have blocked activation, which is why this needed a ruling rather than a sweep |
| ~~`SS-02`~~ | `rehydrate.md` §9 | cohort rules are not restored; the observers CSV carries only Email/Name/Tag1/Status | `csv_contracts.md` §3.2b and `roundtrip_coverage.md` say `CohortRule` round-trips, and the code agrees: `observers_extract.HEADER` includes it, `csv_imports.py:532-572` re-validates through `CohortRuleSet` | **Confirmed 2026-09-13 (author: follow current code).** Cohort rules *do* round-trip — `observers_extract.HEADER` carries `CohortRule` and `csv_imports` re-validates through `CohortRuleSet` — and `rehydrate.md` §9 already says so, the sweep having settled it. Nothing left to reconcile |
| ~~`SS-04`~~ | `operator_button_audit.md` §1 | 11 nav tabs, omitting **Observers** and **Extract data** | both required by `operator_ui_concept.md` | **Fixed** — added as chrome rows **12 and 13**, appended rather than slotted, because that file states its own rule that numbers are stable identifiers other documents cite |
| ~~`SS-05`~~ | `operator_button_audit.md` §13 | the page is "Manage Invitations" | `operator_ui_concept.md` and `operations_pages.md` call it "Invitations" | **Fixed** — `Invitations`, the chrome label, in all four places. Not one-sided: `email_infra_options.md` used the long form three times, so it was a vocabulary in circulation. **Not settled** — the long form survives in four more spec locations and one shipped back-link; see `SS-07` |
| ~~`SS-06`~~ | `session_home.md`, `operator_ui_concept.md` | a "ten-state cascade" | both list twelve, and `workflow_card.md` says twelve | **Fixed — not a mismatch.** Twelve states over ten numbers (1–10 plus `4W` and `4Err`); both counts were right. Now stated in `workflow_card.md`, so the five documents saying *ten-state cascade* stop reading as errors |
| ~~`SS-07`~~ | `operator_ui_concept.md`, `operations_pages.md` and the chrome itself | the page is `Invitations` — `session_top_nav.html:65` renders that label | `settings_inventory.md:56` and `rrw_functional_spec.md:1241,1263,1710,1767` still say **Manage Invitations**, and `:1263` is a *heading* whose own next sentence says *"The Invitations page"* | **Fixed 2026-09-13 (author: Invitations; follow code).** Four references across `settings_inventory.md` and `rrw_functional_spec.md` now use the chrome label the nav renders. `docs/status.md` keeps its own — those are dated log rows and a route table carrying segment provenance, and repointing a log falsifies it |
| ~~`SI-01`~~ | `instruments.md` | the action-row list omits `+Page break` | the per-instrument action-row section includes it, and the template renders it | **Fixed** — added to **both** lists in rendered order (Delete → `+Instrument` → `+Page break` → Lock/Unlock); ASCII box realigned |
| ~~`SI-02`~~ | `csv_contracts.md` | header: "five roster-shaped pairs (… Observers, Settings)" | §4's byte-stability contract: "four (Reviewers, Reviewees, Relationships, Settings)" | **Fixed — a distinction, not a correction.** Five pairs exist; byte-stability is established for four; whether Observers meets it is unverified and §4 now says so. *A guarantee that quietly covers four while the header counts five is how a round-trip regression goes unnoticed* |
| ~~`SI-03`~~ | `settings_inventory.md` §10 | two `audit_events` rows, ✅ analytics-only | …and ❌ out of scope | **Fixed** — duplicate removed; the survivor states what its ✅ does and does not mean |
| ~~`SI-04`~~ | `setup_pages.md` | the Upload confirm copy, two clauses | the same copy, three clauses, in the same file | **Fixed** — the partial now points at the full one. The template renders count / assignments / responses, and *the response clause had gone missing once already* |
| ~~`SI-05`~~ | `reviewer-surface.md:145` | *(See "Form scope" below)* | the section is "Form HTML mechanics" | **Fixed** — repointed to the heading that exists |
| ~~`SI-06`~~ | `permissions.md` | a decorator-scan recipe for finding ungated routes | the scan flags ≥9 correctly-gated `_instruments.py` routes | **Fixed** — the method now says to follow `Depends()` **transitively**. *A check that flags a correctly-gated route is worse than none, because the next reader believes it* |
| ~~`SI-07`~~ | `operations_pages.md` | a query budget of 43 / 84 / 134 / 234 / 434, *"measured through the real routes"* | **pinned by nothing** — the related test only asserts relative growth under 2.5× | **Fixed 2026-09-13 in code (author: fix as recommended)** — the row said *a guard is the right answer and a guard is code*, so a guard was written. `test_the_assignments_page_query_count_is_flat_in_the_roster` drives the real route at two roster sizes and asserts the count does not move. **It pins flatness, not the number 43**: a figure self-stales, and a legitimately added query would fail a 43-pinned test while the contract still held. Mutation-tested — a per-instrument query escapes it (correctly: that is not roster-scaled), an N+1 over reviewers is caught |
| ~~`SI-08`~~ | `quick_setup_card_spec.md` | *"retained for fixture compatibility"* | the Quick Setup per-slot endpoints have **no live caller** (0 template hits) | **Fixed 2026-09-13 (author: fix as recommended).** The unverifiable claim was already gone; what was missing was the fact. `quick_setup_card_spec.md` now states that the per-slot routes exist and **no UI calls them** — zero template references — so they are backend entry points exercised by tests, and anything describing them as card-reachable describes the pre-consolidation shape |
| ~~`SI-09`~~ | `validate_page.md` | a rule count in the §3.2 heading, "(18 registered)" | nothing renews it | **Fixed** — the count is out of the heading |
| ~~`SI-10`~~ | `csv_contracts.md` §3.3 | the `rtds[` import tolerance appears only as an aside | the enforcement is unconditional and stronger than its documentation | **Fixed 2026-09-13 (author: fix as recommended)** — the `rtds[…]` import tolerance has its own bullet in §3.3 instead of riding inside the friendly-labels rule as an aside. The guarantee is the import's, unconditional, and a reader looking for *what happens to an old bundle* now finds it under its own heading |
| ~~`CC-01`~~ | `session_lifecycle.py:36-38` | `SessionStatus`'s docstring: `expired` and `archived` are "reserved for later segments" | `expire_session` (`:459`) and `archive_session` (`:678`) write both | **Fixed 2026-09-13** — all five lifecycle values are live; the docstring now says so rather than reserving two for later segments |
| ~~`CC-02`~~ | `routes_operator/_shared.py:298` | `"group_instrument_no_rule": 409` | dead mapping. **Checked**: `open_instrument`'s comment at `:779` records that Wave 5 PR 5.3 retired the gate deliberately | **Fixed 2026-09-13** — mapping removed. The gate it belonged to was retired deliberately in Wave 5 PR 5.3, so this was dead matter, not a lost guard |
| ~~`CC-03`~~ | `app/schemas/rules.py:6,367` | docstrings describe themselves as mirroring `rule_set_revisions` | a dropped table | **Fixed 2026-09-13** — the docstring now says the table it mirrored has been dropped and the fields are carried in-memory |
| ~~`CC-04`~~ | `services/csv_imports.py:61-63` | `decode_csv`'s `max_bytes` is overridable "so the manual-assignments importer in `app.services.assignments` can stay on its own `MANUAL_CSV_MAX_BYTES` constant" | neither the importer nor the constant exists — both went with the CSV-upload path in 16A PR 5 | **Fixed 2026-09-13 (19N slice 6).** The docstring now says the parameter is overridable, that no *production* caller overrides it today (only a test, exercising the too-large path), and what the retired caller was. Under the ruling this was worse than stale: a reader would conclude manual upload still exists |
| ~~`CC-05`~~ | `_serialize.serialize_session_config` docstring | lists "3. Operator-defined RTDs" and "6. Field-label overrides" as emitted sections | neither is emitted | **Fixed 2026-09-13** — corrected in the RTD retirement rather than here: the docstring listed a phantom response-type section and a retired field-labels section **while omitting data shapes and session tags, both live**. Three errors in one list, not one |
| ~~`CC-06`~~ | `services/visibility_policies.py:365-370` | documents `while_ongoing` as `[activated_at, deadline)` | the behavior is a status check, matching the spec | **Fixed 2026-09-13** — the docstring named a timestamp range; the window is resolved by a status check, which is what the spec contracts. The docstring moved, not the code |
| ~~`CC-07`~~ | `_operations.py:264,358-366` + `views/_previews.py:19` | the preview follow-on was Segment 18Q | `_preview_surface.py:3-6` explicitly corrects them | **Fixed 2026-09-13** — three comments said Segment 18Q; `_preview_surface.py` had been carrying the correction all along (*"not Segment 18Q, which is the unrelated no-code blob-storage deferral"*). All three now name the 2026-05-28 follow-on to Segment 11F |
| ~~`CC-08`~~ | `db/models/email_outbox.py` | "Segment 14-1" | the specs say "Segment 14B"; the equivalence is in the 14B plan header | **Fixed 2026-09-13** — four occurrences of `Segment 14-1` now read `Segment 14B`, matching the specs, so a reader grepping either name finds the same thing |
| ~~`CC-09`~~ | `base.html` comments | `--accent-blue-bg` (2330), "the active side fills accent-blue" (3571), `--accent-blue-marker` (872); and **"Danger Outline (.destructive)"** at 2479 | retired token names, and the pre-19B button vocabulary the doc guard bans in prose | **Fixed 2026-09-13, and wider than logged.** The four logged items were real; sweeping for the rest found **five more** prose uses of *accent-blue* as a colour word with no token of that name — nine in total. Each now names the token that actually ships (`--status-info-bg`, `--selected-bg`, `--btn-primary-bg`, `--nav-marker-setup`), and `Danger Outline` becomes `Destructive`. **`base.html` turned out to be a generator input**: `tools/theme_{customizer,preview}.html` are generated from it and committed, so both were regenerated — the guard added in 19K.7 caught the drift the moment the comments changed |
| ~~`CC-10`~~ | `_display_fields.py:797-801` | a docstring listing 3 `SortSpecError` codes | it raises 5 | **Fixed 2026-09-13** — the docstring listed four codes and the function raises five; `bad_id` was missing. (The register said three listed — re-counted from the file.) |
| ~~`CC-11`~~ | `_serialize.py:561` | a comment saying a behavior "drops in PR 5.2" | PR 5.2 shipped | **Fixed 2026-09-13** — PR 5.2 shipped and `library_origin_id` went with it, so the comment was stale twice over: the forecast had happened, and the *"stays for now"* it forecast was already false |
| ~~`CC-13`~~ | `instruments.md:41` | the Contents entry `[Band 1 — Assignment rule + Unit of review](#band-1--assignment-rule--unit-of-review)` | the heading at `:415` is `### Instrument assignment rule (Band 1) + Unit of review`, which slugs to `instrument-assignment-rule-band-1--unit-of-review`. **The anchor has never resolved** | **Fixed 2026-09-13 on the author's ruling** — *"Band 1, 2, 3 are the old names; should follow the headers on the actual card."* The three section headings now carry the card's own names, per the author's mapping — Band 1 = `Instrument assignment rule` (+ `Unit of review`), Band 2 = `Preview review instrument`, Band 3 = `Visibility`, `Response fields` — with the ToC entries, their anchors and the one inbound link following. **My first pass named two of the three from the spec's own prose rather than the card, and got both wrong**; the author supplied the mapping. The shorthand stays as an alias, recorded in a mapping table at the top of the card section, because the code uses it. **Every anchor in the file now resolves**, verified by extracting headings and links and diffing the sets. `Band N` stays in body prose where it is shorthand for an identifier (`band2_state`, `band1_touched_links`) — those are names, not labels |
| ~~`CC-12`~~ | `tests/integration/test_cascade_ties.py:291` | the comment *"The two values `spec/ui_elements.md` §6 states in prose"* | the test **hardcodes** both specificity tuples and never reads the spec, so if §6 stopped stating them the suite would stay green and the comment would be false | **Dropped 2026-09-13 by the author.** Not worth the change; the test's hardcoded tuples stand and the comment's claim is left as it is |
| ~~`ID-01`~~ | `operator_button_audit.md:42,44,45,46` | `accent-blue`, `accent-red`, `accent-amber`, `accent-amber-dark` | 0 definitions in `base.html` | **Fixed** — **the legend names no tokens at all** now: "Solid fill", "Outline red", "Filled amber, light label", "Outline amber". It exists as a reading key for `ui_elements.md` §6, so it points rather than restates, and cannot drift from §6 again |
| ~~`ID-02`~~ | `session_home.md:112,147,499` | `accent-blue` ×3 | — | **Fixed** — `--card-active-border` (the card border) and `--btn-primary-bg` (the button fill): **two tokens for what one retired name covered**, which is why the flat vocabulary was retired |
| ~~`ID-03`~~ | `session_home.md:443-444` | `bg-muted`, `text-muted`, `text-secondary` | the `.card.placeholder` rule | **Fixed** — `--surface-muted`, and `--text-subtle` on **both** heading and body; the shipped rule uses one token for the two |
| ~~`ID-04`~~ | `extract_data.md:915,917,919` | `--accent-blue` ×2, `--color-border` | `--color-border` had **0 occurrences of any kind** | **Fixed** — `--card-active-border`, `--border-subtle` |
| ~~`ID-05`~~ | `participant_model.md:86` | `--accent-blue`, `--accent-blue-bg-faint` | — | **Fixed** — `--card-active-border` + `--card-active-bg` |
| ~~`ID-06`~~ | `role_navigator.md:113,114` | `--surface-2, #f3f4f6`, `--text-muted`, `--text-primary` | — | **Fixed** — `--surface-muted`, `--text-subtle`, `--text-body`, **and the hard-coded hex fallback goes with them**, since a literal cannot follow the theme |
| ~~`ID-07`~~ | `csv_contracts.md:605` | `field_labels.apply_captured_labels` | `field_labels.apply_import` (`field_labels.py:277`) | **Fixed** — renamed. The same wrong name is at `services/setup_templates.py:35` |
| ~~`ID-08`~~ | `visual_style_rrw.md:213` | cites `session_home.md` "Enum vs. display label" | that heading does not exist | **Fixed** — §"Lifecycle state vocabulary". **Not caught by the `§N` guard, because it is a *named* reference** |
| ~~`DT-01`~~ | `rrw_sdd_in_practice.md:85` | quotes the `spec-writer` charter as *"to match the code … so the specs never drift from reality"* | the quoted words no longer exist | **Fixed** — §6.1 requoted to the charter that exists: at a close, align the spec to what shipped; outside one, the spec wins and divergence is reported |
| ~~`DT-02`~~ | `:115` | *"updates `spec/` to match the code after a change"* alongside *"flag drift … rather than silently rewriting"* | **opposite instructions for the same situation** | **Fixed** — §6.4 now carries **at a close**, and the passage names the contradiction it had papered over |
| ~~`DT-03`~~ | `:201` | the maker/checker table: *"spec-writer (writes spec to match code)"* | same imprecision | **Fixed** — Appendix row qualified the same way |
| ~~`DT-04`~~ | `docs/practice-audit-2026-09-04.md`, `docs/status.md`, `guide/todo_master.md` | each describes `spec-writer`'s job against the old charter | — | **Dissolved, and that is the finding.** The practice audit is a **dated** document whose quote was accurate on its date, and `todo_master.md` records what a *pass found* rather than what the charter says. Repointing either falsifies a log |

Alongside `DT-01`…`DT-03`, §6.2's currency trade-off was restated: it said
*"only the functional spec dates itself: 4 of 36"*, and **no live spec carries
a currency line at all now** — 19M replaced each with a sweep-record pointer.
The figure was the smaller half; the paragraph described a *mechanism* that no
longer exists.

## The tally

**83 findings**, counted by distinct id rather than asserted: `SC` 43, `CC` 12,
`SI` 10, `ID` 8, `SS` 6, `DT` 4.

*Recount before quoting this number.* It was published as 64, grew to 75 as the
verification passes reported, fell to **74** when a section heading turned out to
have been counted as a finding, and is **79**: `SS-07` came from the check over the
resolved rows, `CC-12` from the pass over the writer instructions, and
`SC-37`…`SC-39` from splitting `SC-09` once the author ruled the assignment
contract. `SC-40` and `SC-41` came from the Codex review of that split — both
verified here before being written down — and `SC-42` records a gap the author
deliberately deferred rather than one nobody noticed. The `SS` ids run 01, 02, 04, 05, 06, 07 — there
is no third, because that number was the heading. Nothing renews a count, which is the defect this segment exists to
remove, so a register carrying one had better be honest about it:

```
grep -o '\b\(SC\|SS\|SI\|CC\|ID\|DT\)-[0-9][0-9]\b' \
  guide/findings_2026-09-13_spec_discrepancies.md | sort -u | wc -l
```

## Three things that are not rows

**A structural question.** `spec/role_landing_and_visibility.md` may be a
`docs/` document living in `spec/`. Its opening answers *"given my role, can I
sign in, where do I land, and what do I see?"*, and its tables were introduced
as *"recorded from a running app"* — which is §4's question for **`docs/`**, not
the contract question for `spec/`. The sweep softened the method claim and
declined to move the file: relocating a spec is a contract decision, and
`tests/unit/test_spec_coverage.py` maps routing modules to governing specs, so a
move is not a file rename.

**Frozen measurements, as a class rather than a list.** Counts in a contract rot
exactly as a `*Current:*` block does. One was converted — `permissions.md`'s
*"128 of 128 routes carry a dependency"* → *"every such route carries one"*,
keeping the counting method as the invariant, after checking that no test reads
`128`. **Five test-case counts in `permissions.md` §7 were kept and not
verified**, because the batch could not tell whether the author uses them as a
coverage floor. That is the open question this class leaves.

**A decision that looks like an omission.** `visual_style_general.md`'s **61**
`accent-*` / `bg-page` / `text-primary` names were left entirely alone. That
file's own preamble states the constraint forward — *"These are the design
system's role names, not Review Robin's shipped token identifiers. This document
is portable"* — with a pointer to `color_tokens.md` as authoritative. Renaming
them would have broken the document's stated portability and contradicted its
own guard paragraph. So `ID-01`…`ID-06` are real and this file's 61 are not.
Two other retired-token hits in `spec/` are also correct: `color_tokens.md:7` is
the do-not-reintroduce constraint, which must name them to forbid them, and
`ui_elements.md:23` explains why `visual_style_general.md` uses role names.

## What is not in this register

- **Anything in `docs/`, `guide/` or the root documents**, except where the `DT`
  rows reach them. Out of 19M's scope.
- **Fixes to the open rows.** *A sweep recommends.*

## Two things this register got wrong about itself

Kept because they are the reason it now reads the way it does.

**It miscounted itself three times** — 64, then 75, then 74.

**It claimed two fixes that had never been made.** `SI-02` and `SI-05` were
described in an item's *plan* and neither was in the script that ran: the intent
was written, the record of having done it was written, and the work was not
done. Nothing tests spec prose against a register, so the suite could not catch
it. The audit that found them was 25 predicates, one per actioned row, each
`True` only if **the edit is present in the file** — not a search for the
finding's description, which is what made the two invisible.

*That is the same screw turning: a `*Current:*` block rots because nothing
renews it; a finding rots unless something checks it; a correction rots; a count
rots. **And a claim that a thing was fixed rots the moment it is written,
because it is believed on sight and nothing re-derives it.*** Which is why every
struck-through row above says what the fix *was*, in terms a reader can go and
check in the file.

---

# Second pass — a fresh audit, 2026-09-13

**1 open of 24. 23 settled — 2026-09-13.** Opened the same day the first
register closed, at the author's instruction: *"send agents out to do a fresh
audit to look for gaps between spec and code, spec and spec."* Seven agents
covered all 39 live `spec/` files plus a code-side sweep for dead matter and
false self-description. **Every row below was re-verified by hand against the
file and line it names before being written here** — three agent claims were
dropped or corrected at that step, including one citation to a prohibition that
exists in a different spec than the one named.

**The headline is not a spec gap.** `NF-01` is a live user-facing bug, now
logged as **19N Item 3**. And **seven of these rows are leftovers of the first
register's own fixes** — see "What this pass says about the last one" below,
which is the most useful thing in this table.

**Settled 2026-09-13** at the author's instruction (*"log NF-01 in 19N; fix the
obvious ones among the others"*): the fifteen rows whose fix was a prose or
comment correction the code already settles. What stays open is the five
dead-matter rows and `NF-22` — deletions and a ruling, neither of which is
obvious — plus `NF-23`, opened by this pass.

**The fixing ran claim-scoped, not row-scoped**, which is the lesson this table
opened with. That found **five sites no row had named**: two more `Discard`s
inside `review_surface.html` (`NF-05`), a third contradicting passage in
`session_home.md` (`NF-10`), a second live docstring resting on the inert rule
(`NF-20`), and the retired `AssignmentMode` values sharing `NF-08`'s sentence.
It also **dropped one clause that verification could not support** — there is no
`_RULE_KEY_GATE` (`NF-20`) — and **declined one** that looked like a finding and
was not: `preview_hub.md` already says in bold that send-test is unbuilt.

| bucket | ids | open | settled |
|---|---|:--:|:--:|
| **code** — a live defect | `NF-01` | 0 | 1 (logged as 19N Item 3) |
| **spec** — a claim the code disproves | `NF-02`…`NF-09` | 0 | 8 |
| **spec** — self-contradiction or spec-vs-spec | `NF-10`…`NF-14` | 0 | 5 |
| **code** — dead matter with no caller | `NF-15`…`NF-19` | 0 | 5 (four deletions; two entries kept, each with its reason) |
| **code** — a comment that misdescribes its own code | `NF-20`, `NF-21` | 0 | 2 |
| **a ruling** — structural, not a defect | `NF-22` | 0 | 1 (a ruling *and* one real fix) |
| **spec** — opened by this pass | `NF-23` | 1 | 0 |
| **spec** — opened while settling set 2 | `NF-24` | 0 | 1 |

**The dead-matter rows were worked on the author's instruction, 2026-09-13**
("fix sets 2 and 3"), as their own PR rather than riding in on the prose one.
Two things in them survived the pass and both are recorded in their rows: the
`instrument.rule_pinned` **schema entry** stays, because `EVENT_SCHEMAS.keys()`
drives the audit-log viewer's filter list and dropping a key makes historic rows
of that type unfilterable; and `participant_token` stays, because a documented
convenience wrapper with fifteen test call sites is not dead in the sense the
others were. **Unreachable for writes is not the same as unused** — that
distinction is the one useful thing this bucket taught.

| id | where | contract / one side | reality | disposition | outcome |
|---|---|---|---|---|---|
| ~~`NF-01`~~ | `next_action_card.html:432` | the failure banner names the action that failed | `{% set _button_label = "Prepare session" if super_failure.button == "prepare" else "Activate session" %}` — but `_workflow.py:391` **and** `:410` pass `super_button="close"`, so a failed **Close session** is headlined *"Activate session failed…"* | **Live defect, user-facing.** The only one in this table. A three-branch label or a lookup keyed on `super_failure.button` fixes it; the failure paths already carry the right value | **Logged 2026-09-13 (author: log it in 19N)** as **Item 3 — the failure banner names the wrong button** in `guide/segment_19N_generated_assignments.md`. Verification widened it: not one wrong value but **three of five** — `close`, `release_responses` and `stop_release` all headline *"Activate session failed"*, and `super_step="close"` is missing from `_step_label_map` besides, so that banner also drops its step phrase. The vocabulary is recorded in four places (routes, template, `_shared.py:351`, `spec/workflow_card.md` ×3) and updated in none. No code moved |
| ~~`NF-02`~~ | `assignments.md:874-876` | *"**To-keep.** Pairs surviving both passes. Their `Assignment.include` is preserved"* | `_generate.py:345-347` sets `pair_include = self_reviews_active if is_self else True`, and `:457-461` overwrites `row.include` whenever it differs — so a manually-Inactivated **non-self** pair is flipped back to `True` on the next regenerate | **Leftover of `SC-42`.** That row stated the gap in `roundtrip_coverage.md` and left two other specs asserting the opposite | **Fixed** — the bullet now says `include` is **recomputed, not preserved**, names both code sites, and points at 19N Item 1 Semantics 6 for the deferral |
| ~~`NF-03`~~ | `reconciling_regeneration.md:73-74` | *"Non-self-review pairs are always `include=True`, so only self-review `to_keep` pairs can ever change"* | premise right, conclusion wrong — a non-self row set to `False` **does** change, back to `True`. Same code as `NF-02` | **Leftover of `SC-42`**, second site | **Fixed** — the false conclusion replaced: the expected value is `True` for every non-self pair, so a hand-inactivated row is reset here too |
| ~~`NF-04`~~ | `_generate.py:455-456` (comment) | *"only refresh `include` in place when a `self_reviews_active` toggle changed it"* | the loop below it refreshes on any difference, self-review or not | **Code comment**, same false claim as `NF-02`/`NF-03`, inside the code that disproves it | **Fixed** — the comment now describes the loop below it |
| ~~`NF-05`~~ | `visual_style_rrw.md:447, 449, 690` | the reviewer action row carries *"Discard"* | shipped label is `Cancel` (`review_surface.html:130,160`) | **Leftover of `SC-12`**, which renamed 21 references in `reviewer-surface.md` and never looked here | **Fixed** — `Cancel` in all three `visual_style_rrw.md` places, plus **two more the row did not name**, both inside `review_surface.html` itself (`:181` the action-row comment, `:409` the JS-handler comment). Correction to the row as written: the shipped label is at `_action_row.html:39`, not `review_surface.html:130,160` — those are the missing-card Cancel. `data-rs-discard` stays; it is an identifier |
| ~~`NF-06`~~ | `visual_style_rrw.md:696-699` | Page buttons ship *"a defensive CSS truncation rule (`max-width: 16em; text-overflow: ellipsis`)"* | `base.html` contains **zero** `text-overflow` declarations | **Leftover of `SC-13`**, which removed this exact sentence from `reviewer-surface.md` only | **Fixed** — sentence removed; the 32-char cap (real, `_instrument_crud.py:515`) now says it is the whole of the defence |
| ~~`NF-07`~~ | `quick_setup_card_spec.md:52` | *"The per-slot routes (`POST …/quick-setup/{kind}`)"* | four slots match, but **Settings** is `POST /sessions/{id}/import-config`; `quick-setup/settings` has 0 hits | **Leftover of `SI-08`** — this sentence was written *in this session* and overgeneralised the route shape | **Fixed** — the four `quick-setup/{kind}` slots named, with Settings' `import-config` called out as predating the card |
| ~~`NF-08`~~ | `domain_assumptions.md:26-28` | *"Archived (data collected has been downloaded and **deleted**)"*, and a status list of Draft / Ready / Expired / Archived | `archive_session` (`session_lifecycle.py:686-691`) *"is reversible … and **deletes no data**"*, and `validated` is a fifth live state the line omits | **The worst factual drift found.** A spec telling a reader that archiving destroys their data, when it destroys nothing and is reversible | **Fixed** — the five live states with their display labels, and archiving stated as reversible and non-destructive. The **same line's other half** was stale too and went with it: *"FullMatrix, Manual, RuleBased"* — `AssignmentMode` has had one member since 16A, and Full Matrix is a rule set, which is the absorption that line anticipated |
| ~~`NF-09`~~ | `architecture.md:175-177` | the band2 / pagination AJAX endpoints *"still hand-roll `request.json()`… R4 aligns them"* | R4 shipped: both call `require_json_object` (`_shared.py:377-400`), whose docstring says R4 ran **and deliberately kept** the non-Pydantic contract | **Spec describes pending work that landed, and landed differently** | **Fixed** — the paragraph now records that R4 shipped and resolved it the *other* way (factor out the parse, keep the 400 contract), with the convergence rule scoped to new endpoints |
| ~~`NF-10`~~ | `session_home.md:492-497` | *"The standard body / confirm / buttons stack handles every state except Activated, which uses an inline two-section layout"* | `:120-136` of the **same file**, rewritten this session, says there is no Activated exception and neither class renders in any state | **Leftover of this session's own rewrite** — one file, two passages, opposite claims | **Fixed** — `:492-497` rewritten to match `:120`, and **a third passage in the same file** (`:116-119`, *"the Activated state's two-section layout reads taller"*) that the row did not name |
| ~~`NF-11`~~ | `preview_hub.md:115, 119, 121` | the hub renders in states `draft`, `validated`, `ready`, **`closed`** | `session_home.md:43-46` (and `operator_ui_concept.md:39`): *"There is no `closed` state in the canonical enum… Nothing — CSS class, query param or column value — may name a `closed` state."* The enum value is `expired`, displayed as "Closed" | **Spec-vs-spec.** Cited here against the file that actually carries the prohibition — the audit first named `lifecycle.md`, which does not | **Fixed** — all five states named, `expired` in place of `closed`, with the display label and the prohibition cited. Also verified: the hub's route carries no lifecycle gate at all, so *"renders in all states"* is true. The send-test copy nearby is **not** a finding — `:85` already says in bold that it is not built. **Two more sites, found by the `spec-writer` verification pass, not by the fixing:** `session_home.md:253` lists `closed` as an extraction state **two hundred lines after that same file states the prohibition**, and `_operations.py:190` names `draft / ready / closed` in a live code comment. Both corrected here — the claim-scoped sweep had swept `preview_hub.md` and stopped |
| ~~`NF-12`~~ | `roundtrip_coverage.md:129` | Relationships is *"the **only** roster path whose `status` round-trips"* | `:124` and `:127` of the same table mark reviewer / reviewee / observer `status` as round-tripping | **Self-contradiction** — the ✅/❌ marks are right, the connecting prose is not | **Fixed** — the "only" claim dropped; the note now says what the marks say, and names observers as the one exception and why |
| ~~`NF-13`~~ | `rehydrate.md:212` | the `*_observers.csv` manifest lists `ObserverEmail, ObserverName, ObserverTag1, Status` | the header is five columns including `CohortRule` (`observers_extract.py:26-35`) — and `:499-504` of the same document depends on it | **Self-contradiction**; §4 understates the file §9 relies on | **Fixed** — `CohortRule` added, so §4 and §9 agree |
| ~~`NF-14`~~ | `workflow_card.md:549, 554, 763` | Close session *"Calls `lifecycle.close_session`"* and *"Emits `session.closed`"* | neither exists: 0 occurrences in `app/`. The real names are `expire_session` and `session.expired` | **Two identifiers that name nothing** | **Fixed** — `expire_session` / `session.expired` in all three places, with one line on why the service keeps the enum's name and the button keeps the operator's |
| ~~`NF-15`~~ | `app/services/rules/preview.py` + `partials/_rule_set_preview.html` | a live rule-preview surface the docstrings describe as refetched by *"the editor's JS hook"* after each edit | **219 lines with no caller**: nothing imports the module, no template includes the partial, and `…/rule-based/preview` does not exist | **Dead surface.** Its own sibling (`_assignments.py:17-18`) already records that the `rule-based-editor` routes exist nowhere | **Deleted 2026-09-13 (author: fix set 2)** — module, partial and its 128-line unit-test file, 347 lines in all. Nothing imported it, no template included it, and the route its docstrings described (`…/rule-based/preview`) never existed | <!-- path-ref-ok -->
| ~~`NF-16`~~ | `_instrument_crud.py:644-698` + `audit.py:466` | `pin_rule_set`, a 55-line mutating service, and its registered `instrument.rule_pinned` event | no route, no template, no test reaches it; it is the sole emitter, so the allowlist key is unreachable | **Dead write path plus an unreachable registry entry** | **Half deleted, half kept deliberately.** `pin_rule_set` and its two export lines are gone — a 55-line mutating service no route, template or test reached. **The `instrument.rule_pinned` schema entry stays**, now carrying a comment saying why: `EVENT_SCHEMAS.keys()` is what the audit-log viewer renders as filter checkboxes and validates filter input against (`views/_audit_log.py:163, 206`), so dropping the key would make any historic row of that type unfilterable. The row called it "an unreachable registry entry" — it is unreachable for *writes*, which is not the same as unused, and the register's own precedent for the retired `instruments.no_rule_pinned` rule says keep it |
| ~~`NF-17`~~ | `_instrument_crud.py:624-642` | `has_unpinned` *"Drives the Next Action card's 'Empty Setup' state"* | no caller. `_workflow_card.py:100-102` records that the card *"switched from rule-set-centric `has_unpinned` to `has_unconfigured`"* | **Dead, and its docstring asserts the opposite of the file that stopped calling it** | **Deleted** — function plus two export lines. The comment at `_workflow_card.py:100`, which recorded the switch away from it, now also records that the helper it replaced was carrying a docstring claiming this card still drove it |
| ~~`NF-18`~~ | `date_formatting.py:106-125` | `timezone_label`, a CLDR zone-name formatter | no app caller — and it is the **only** importer of `babel`, a shipped dependency (`pyproject.toml:22`, `requirements.txt:12`). The app's zone display goes through `gmt_offset_zone_label` | **Dead function carrying a dependency** | **Deleted, and `babel` with it** — the function, its four unit tests, and the pin from both `pyproject.toml` and `requirements.txt`. It was the dependency's only importer; the app's zone display goes through `gmt_offset_zone_label`. `README.md` never named `babel`, so nothing there to update |
| ~~`NF-19`~~ | five symbols | `RuleSetRevisionSchema`, `SessionRead`, `canonical_default`, `preset_list_options_by_key`, `participant_token` | each occurs once in `app/` — its own definition. Two of them (`canonical_default`, `preset_list_options_by_key`) additionally describe a call site that does not exist | **Dead cluster**; the last is a test-only convenience wrapper and is the weakest of the five | **Four of five deleted** — `RuleSetRevisionSchema` (whose own docstring says the table it mirrored has been dropped), `SessionRead`, `canonical_default`, `preset_list_options_by_key`, plus `_ApplyConflict`, raised by nothing and describing an RTD reference in a codebase where RTD is retired. **`participant_token` kept:** it is a documented one-shot convenience wrapper over `ParticipantTokenizer` with **15 test call sites**, so "occurs once in `app/`" is true of it and means something different — deleting it would rewrite a readable test suite to buy nothing. The row itself called it the weakest of the five |
| ~~`NF-20`~~ | `validation.py:811-827` | the `instruments.no_rule_pinned` registry entry carries `severity=warning` and operator-facing `why` copy — *"An unpinned legacy instrument is silently skipped during generation, leaving its reviewer page empty"* | the handler (`:444-458`) is `return` / `yield` — **a registered no-op**. Unlike `instruments.stale_generated`, this retirement is deliberate and its docstring says so; what is stale is the `why` three hundred lines away, and `_RULE_KEY_GATE` routing a key nothing produces | **The second registered no-op this codebase has had.** The first was an accident 19N.1 revived; this one is intentional, so the fix is to retire the copy, not the rule | **Fixed** — the `why` retired to say the rule is inert and nobody reads this copy. **A second live site the row did not name** went with it: `validation.py:284`, a *different* rule's docstring justifying its own silence by the noise this one makes. Correction to the row as written: there is no `_RULE_KEY_GATE` — that clause was an agent claim that survived my verification and does not exist. `validate_page.md:220` and `instruments.md:986` were already correct |
| ~~`NF-21`~~ | `deps.py:398-400` and `:495-496` | *"Phase 1 stub — defined but not referenced by any route yet"*, on `require_reviewee_in_session` and `require_observer_in_session` | both are **live access gates**: the observer one at `_collation.py:51,68,103`, the reviewee one composed into `require_reviewee_with_current_grant` (`deps.py:438`), which gates `/results` | **In the auth layer.** Nothing behaves wrongly, but a reader auditing access control is told these gates are inert | **Fixed** — both docstrings now name the route each gate actually serves, and say which is a route dependency and which is composed |
| ~~`NF-22`~~ | `architecture.md:57-58` / `CLAUDE.md` | route handlers hold *"no SQL, no business rules"* | **54** `db.execute(select…)` / `scalar_one` sites across 13 of ~20 `routes_operator` files. `_instruments.py:1044-1101` runs three queries plus the last-instrument floor rule and the next-sibling choice in the route body | **Needs a ruling, not a fix.** Either the rule is aspirational and should say so, or this is a real backlog; at 54 sites it is a segment, not a row | **Settled 2026-09-13 (author: fix set 3)** — and the row's own figure did not survive re-running. There is no pattern yielding **54**: it is `db.execute(` (**30**) plus `scalar_one` (**25**) counted as separate sites when they are mostly the same call chained across two lines. `select(` is **31**. The "13 of ~20 files" was right — 13 of 22. **Classifying all 30 changed the answer.** Nearly every one is a *scoped entity lookup* — load the row named by a path parameter, scoped to the session, 404 if absent — and several are already factored into `_require_*_in_session` helpers. That is a route resolving its own arguments, not a business rule; the rule reads *"no SQL, no business rules"* and this row treated two prohibitions as one. `spec/architecture.md` and both `CLAUDE.md` twins now say which is which, with the measurement beside it. **One site was a real violation** and is fixed: `instruments_delete` held a last-instrument floor (now `instruments.LastInstrumentError`, so every caller gets it, not just the one that checked) and a next-sibling landing choice (now `views.instrument_delete_landing_id`, per the fourth seam). Seven tests, each mutation-tested to fail exactly one |
| `NF-23` | `visual_style_rrw.md:447, 449, 690` / `reviewer-surface.md:1222` / `views/_instruments.py:3` | the reviewer action row carries **one button per instrument**, labelled `Page #{N}: {Instrument.short_label}`, rendered as Primary anchors that *"JS-toggle which instrument is visible (no server round-trip)"* | **no such button ships.** `Page #` has **zero** occurrences in `app/`. `_action_row.html` renders Save / Cancel / Submit, then — only when `page_count > 1` — `< Previous page` / `Page N of M` / `Next page >` as plain `<a href>` links that **do** round-trip the server (`:47-60`). The model moved from per-instrument toggle buttons to operator-defined pages with prev/next navigation, and `reviewer-surface.md:154-156, 198` already documents the shipped shape — so that file contradicts its own copy inventory 1,070 lines later. `_instruments.py` still advertises *"page-button helpers"* it does not have. The `Page #{N}: {short_label}` string does survive, as the per-instrument **H2** (`instrument_heading`), which `:1235` describes correctly | **Opened by the settling pass, 2026-09-13.** Surfaced while fixing `NF-05` / `NF-06`, whose sentences sit inside this larger false premise — including the one that roots the real 32-char `short_label` cap in a button that no longer exists. **Not fixed with them:** rewriting a navigation contract across two specs on a fixer's own reading is how a spec starts describing the code's accidents. Needs a look at the live surface, and probably a line on whether per-instrument paging was retired or deferred | |
| ~~`NF-24`~~ | `workflow_card.md:623` | the State-1 Setup checklist's third entry is *"Instruments (all rules pinned)"* | **two things wrong.** The shipped label is bare **Instruments** (`next_action_card.html:382`) — the parenthetical never rendered. And the check behind it, `instruments_configured_ok = not has_unconfigured`, keys off *at least one visible response field and all three Band 1 links touched* (`configured_counts`), not rule pinning; a NULL `rule_set_id` is the Full Matrix default and passes | **Found by the `spec-writer` sweep over set 2, and fixed with it** — not an independent bug bundled in: it is the last live claim resting on the rule-pinning concept whose helper (`has_unpinned`, `NF-17`) this same PR deletes. Leaving the spec asserting "all rules pinned" while removing the code that meant it is precisely the row-scoped miss this register exists to stop |

## Also checked, and clean

Recorded so the next pass does not re-sweep them. The participant slice came back
clean on behaviour, which is the reassuring result for the surfaces that gate
disclosure: the access-gate composition and its 404-not-403 rule, `_PER_CELL_VALID_MODES`
against `visibility_policy.md` §3.1 cell-for-cell, `build_role_chips` / `_ROLE_PRIORITY`
including the reviewee-omitted-vs-observer-greyed asymmetry, and
`is_response_release_window_open`. Also verified: the 21-column `responses.csv` header and
its strict parser, `session.rehydrated`'s four `counts` keys, the `data_shapes[N].*`
serialization, `session_clone`'s roster-status copy and zero-observer copy, all ten
Workflow-card visibility formulas, `ui_elements.md` §6's button-role table, `color_tokens.md`'s
80 / 107 / 16 token counts (recounted from `base.html`), the `ACCEPTED_BELOW_AA` ratios,
and the `.rs-help-card` hex values.

**On permissions, the coverage is partial and that is stated deliberately.** Gates were
followed **transitively through `Depends()`** for `owners/add`, `clone`,
`export/audit_log.csv`, the sys-admin adopt route, `quick-setup/lock`, the instrument
page-break routes and the Extract-data sub-API — all matching `permissions.md`. A bulk
scanner was built, produced ~120 false "ungated" hits from a regex that could not parse
multi-line decorators, and was **discarded rather than reported**. That is the trap
`permissions.md` §3 names: a check that flags a correctly-gated route is worse than no
check, because the next reader believes it.

## What this pass says about the last one

Seven of the twenty-three rows above — `NF-02`, `NF-03`, `NF-04`, `NF-05`, `NF-06`,
`NF-07`, `NF-10`, plus the three `response_type.*` entries folded into `NF-16`'s
neighbourhood — are **leftovers of fixes made earlier the same day**.

The cause is one thing, and it is worth more than any single row here:

> **A row-scoped fix is not a claim-scoped fix.**

Each register row named one location. Each fix corrected that location. The *same
claim* lived in other files, and nothing looked for it — `SC-12` and `SC-13` swept
`reviewer-surface.md` while the identical sentences sat in `visual_style_rrw.md`;
`SC-42` stated the round-trip gap in `roundtrip_coverage.md` while two other specs
asserted the opposite; the Next Action rewrite fixed one passage of `session_home.md`
and left its own file contradicting itself four hundred lines down; the RTD
retirement swept prose and missed three registered audit-event types; and one row
(`NF-07`) is a sentence written *during* that session that overgeneralised a route
shape nobody re-checked.

**The remedy is procedural, not a row to close:** when a finding is fixed, grep the
*claim* across `spec/`, `docs/`, `app/` and `tests/` — not the file the row cited.
The first register's own `CC-09` learned this once (four logged occurrences turned
out to be nine) and the lesson did not generalise to the rows around it.

**Run that way, the settling pass earned it back.** Sixteen rows were fixed by
grepping the claim rather than the citation, and that turned up **five sites no
row had named** and one whole finding no row had (`NF-23`) — against **one
clause dropped** as unsupportable and **one candidate declined** as already
documented. The five extra sites are the measure of what row-scoped fixing was
leaving behind: roughly a third again on top of what the rows themselves said.
