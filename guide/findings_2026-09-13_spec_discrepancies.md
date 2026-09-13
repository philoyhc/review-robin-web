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

**27 of 74 resolved. 47 open.**

| what the open rows need | ids | count |
|---|---|---|
| **a ruling** — which side is right | `SC-05`, `SC-06`, `SC-08`…`SC-36` | 31 |
| **a contract decision** | `SS-01`, `SS-02` | 2 |
| **code** — a comment or a dead mapping | `CC-01`…`CC-11` | 11 |
| **code** — a guard | `SI-07` | 1 |
| **prose** — a fact worth restoring | `SI-08`, `SI-10` | 2 |

## Reading key

| tag | kind |
|---|---|
| **SC** | spec says one thing, code does another |
| **SS** | two live specs disagree |
| **SI** | one spec contradicts itself |
| **CC** | two code comments disagree, or a comment names something absent |
| **ID** | a spec names an identifier that does not exist |
| **DT** | a document describes its own tooling imprecisely |

The 31 open `SC` rows carry a **bucket**, so they can be ruled in batches
rather than thirty-one times. The bucket is a read, not a finding:

- **(a)** the code looks intended and the spec is stale — the `SC-01`…`SC-04`
  shape, which the author ruled *"update spec/comments; code is correct"*.
- **(b)** the spec states a requirement the code has not met. Here the spec is
  working, and the question is whether to build or to retire.
- **(c)** a genuine judgment, where neither side is obviously right.

A bucket is not a verdict. Two rows sat in (a) on a first pass while their own
text argued the code was the bug — accepting (a) wholesale would have rewritten
a contract this register was defending. Read the row before applying the batch.

## The findings

Grouped by kind, ids ascending. Struck-through id = resolved; the last column
says what the fix was. Every `where` is the contract side; `reality` is the
code, the other spec, or the other comment.

| id | where | contract / one side | reality | disposition |
|---|---|---|---|---|
| ~~`SC-01`~~ | `settings_inventory.md` §10 | a `session_rule_sets[n].library_name` row on input must be **recognized and skipped** | `_apply_rule_set.py:53` raises; apply is two-phase, so the **whole import is rejected** | **Fixed** — spec now states the strict reject as deliberate, with its reason (a misspelled attribute would otherwise be dropped in silence) and its cost (such a bundle needs the column removed first) |
| ~~`SC-02`~~ | `assignments.md` | a `stale` pill when a rule + roster pass would produce a different set | `views/_assignments.py:221` hardcodes `is_stale = False`; `:202` `any_stale = False` | **Fixed** — spec states the absence as the contract: no `stale` pill, no staleness signal, and a rule edit is invisible until regeneration. Also surfaced that the `"generate"` next-action state is unreachable, and a code comment forecasting a PR that had shipped |
| ~~`SC-03`~~ | `assignments.md` §Staleness | the check is `stamp_changed(instrument, db)` | 0 occurrences in `app/` or `tests/` | **Fixed** — section removed with `SC-02`; the helper does not exist |
| ~~`SC-04`~~ | `reviewer-surface.md` | `typical_chars = max_length * 0.75` | `views/_instruments.py:226` is `0.5`, and `test_instrument_builder_routes.py:6859` **asserts** `0.5` | **Fixed** — spec now `0.5`. The gate is no longer on the wrong side |
| `SC-05` | `reviewer-surface.md` | the spec's heading format | `test_reviewer_view_helpers.py` pins the code's format **while citing the spec section it contradicts** | **(a)** — sibling of `SC-04`; whichever wins, the test moves too |
| `SC-06` | `assignments.md` | `POST …/assignments/instrument/{iid}/self-reviews-active` | `…/assignments/{instrument_id}/self-reviews/active` (`_assignments.py:479`) | **(a)** — **a URL is contract**, so one side must move |
| ~~`SC-07`~~ | `csv_contracts.md` §4 items 1 and 7 | seeded RuleSets are not re-emitted, or a re-import trips `uq_session_rule_set_session_name` | `_serialize._non_seeded_session_rule_sets` returns every row | **Investigated on instruction: not a bug.** Seeding was retired and apply upserts by name, so neither half held. Spec rewritten, and it had been citing a test file that does not exist |
| `SC-08` | `csv_contracts.md` §5 | `decode_csv(content: bytes) -> str` | `decode_csv(content, source, *, max_bytes=…) -> tuple[str \| None, ValidationIssue \| None]` | **(a)** |
| `SC-09` | `settings_inventory.md` §2 | `assignment_mode` values `manual` / `rule_based` | `AssignmentMode` admits only `rule_based`; three tests still set `manual` | **(a)** |
| `SC-10` | `settings_inventory.md` §2 | Edit surface is `/operator/sessions/{id}/edit` | `_session_home.py:241` is a **308** to `…?editing=1#session-config`; the page is gone | **(a)** |
| `SC-11` | `instruments.md` | Band 3 bounds rules for `Number` / `Rating` / `SingleSelect` / `MultiSelect` | `bulk_save_fields` branches on `String` / `Integer` / `Decimal` / `List` — the four the spec's own Type picker lists eight lines above | **(a)** |
| `SC-12` | `reviewer-surface.md` | Discard labeled `Discard`; a per-page `Page #{N}: {short_label}` button; Save is Primary | `Cancel`; `< Previous page` / `Page {N} of {M}` / `Next page >`; Save is `.btn.secondary` | **(a)** |
| `SC-13` | `reviewer-surface.md` | page buttons carry `max-width: 16em; text-overflow: ellipsis` | neither rule exists in `base.html` | **(b)** |
| `SC-14` | `reviewer-surface.md` | Enter / Shift+Enter move focus down / up a column | **no `keydown` handler on the reviewer surface at all** | **(b)** |
| `SC-15` | `reviewer-surface.md` | status column renders on `submitted_at` **or** `show_acknowledge` | `_context.py:528` uses `show_incomplete_marks`; `show_acknowledge` has 0 occurrences — and the same file says elsewhere there is no such flag | **(c)** — also an `SI`, since the spec contradicts itself |
| `SC-16` | `reviewer-surface.md` | dashboard `closed` renders `pill-lifecycle-archived` (muted grey) | `reviewer/dashboard.html:122` renders `pill-error` (red) | **(a)** |
| `SC-17` | `reviewer-surface.md` | `submit_redirect_url(review_session, position)` → `/{page_n}` | `submit_redirect_url(review_session, *, fully_submitted=False)` → `/summary` or the bare session URL | **(c)** — the spec also contradicts itself here |
| `SC-18` | `role_navigator.md` §2 | preview route is `…/previews` | the route rendering `review_surface.html` is `…/preview-surface/{page_n}`; `/previews` is the hub | **(a)** |
| `SC-19` | `role_navigator.md` | identity match is `func.lower(column) == casefold(email)` in SQL | `build_role_chips` folds via `normalize_email` in Python | **(a)** |
| `SC-20` | `preview_hub.md` §3 | a per-artifact "Send test to…" affordance, lifecycle-gated | a case-insensitive grep of `app/` for `send test` and for `send_test` → **0** | **(b)** |
| `SC-21` | `preview_hub.md` + `session_home.md` | Next Action card carries a "See previews" button in `validated` | no such string anywhere in `app/` | **(b)** |
| `SC-22` | `preview_hub.md` | Operations row is `[Assignments][Validate][Previews][Invitations][Responses]` | `session_top_nav.html` renders a sixth tab, `Extract data` | **(a)** |
| `SC-23` | `session_home.md` §1 | an Activated-state exception: body split by `<hr class="next-action-divider">`, `.next-action-buttons` **not** rendered while Activated, `.next-action-confirm` pre-Activated | neither class appears in any template (CSS rules in `base.html` only), and `workflow_card.md` specifies a single button row in **every** state | **(b)** — corroborated by `SC-34` |
| `SC-24` | `operator_button_audit.md` §11.5 | Inactivate / Activate gated on "≥1 selection" only | the template also gates them, and the count pill, on `can_edit` | **(c)** |
| `SC-25` | `role_landing_and_visibility.md` §3 | "the eight operator cards"; a stranger "saw all eleven" | `_guide.py` `SECTIONS` has **12** (9 operator + 3 role) | **(a)** |
| `SC-26` | `reconciling_regeneration.md` | the `include` seed is pair-level via `is_self_review(reviewer, reviewee)` | `_generate.py:334-347` applies the **whole-group** rule on group-scoped instruments, which `assignments.md` specifies | **(c)** — here the **code is right and this spec is incomplete** |
| `SC-27` | `reconciling_regeneration.md` + `assignments.md` | `reconcile_impact` returns per-instrument counts | returns one aggregate `ReconcileImpact` for the session | **(c)** — the design's reason (one path serving the banner *and* a per-instrument preview) needs per-instrument. A batch had written the aggregate in and reverted it |
| `SC-28` | `quick_setup_card_spec.md` | operator is sent to the Operations Assignments page to regenerate | generation fires from the Workflow card's stepper | **(c)** |
| `SC-29` | `csv_contracts.md` §3.3 | the Settings CSV has an RTDs section (example `rtd.Long_text.data_type,…`) | `_serialize` emits no RTD rows; such a row hits the unknown-key ignore | **(a)** |
| `SC-30` | `ui_elements.md` §1 | Sign out is a **Secondary** control | `base.html:3414-3417` ships a bespoke `.chrome-user .signout` — `--border-default` (not `--btn-secondary-border`), `--text-body`, `--surface-muted` hover | **(b)**. §1 now points at §6 rather than restating it, per `operator_button_audit.md`'s rule that a role is defined in one place |
| `SC-31` | `visual_style_general.md` Patterns | status strip fills `bg-muted` with `border-subtle` **top and bottom**, between chrome and page body | `--surface-card`, top border only, **inside** the nav card | **(c)** — RRW overrides the *placement* explicitly but not the fill, so the fill is unaccounted for |
| `SC-32` | `ui_elements.md` §4 vs two other specs | §4 said `.card.danger-zone` has a **white** background | `visual_style_general.md` and `visual_style_rrw.md` both contract the lock card's amber surface, "fill included"; code ships `--card-warning-bg` | **(a)** — resolved to amber by `ui_elements.md`'s own precedence rule. Listed because it is a **contract text change**, not a provenance edit, so it deserves confirmation |
| `SC-33` | `ui_elements.md` pills | `.pill-success` text is `--status-success-fg` | `base.html:3289` ships `--status-success-accent`; they share `--green-deep` in light but **diverge in dark**, and every other pill uses its `-fg` | **(b)** — **likely a code bug**; contract left as `-fg`. A batch had written `-accent` to match the code and reverted it |
| `SC-34` | `session_home.md` | `.next-action-confirm` renders in pre-Activated states | `base.html:3094` has the rule; `next_action_card.html` emits no element with the class | **(b)** |
| `SC-35` | `ui_elements.md` | `placeholder_card` is the reuse point for placeholder cards | the macro has **no callers**; the one live `.card.placeholder` is hand-written in `session_previews.html` | **(b)** |
| `SC-36` | `base.html` | — | **orphan CSS with no contract behind it:** `.setup-nav` / `.setup-nav > .btn` (831-839, 0 template users), the `.btn-cta` rules (0 markup callers), `.next-action-confirm` | **(c)** — cleanup, not a contract |
| `SS-01` | the five validation severities | `instruments.no_fields` error; `no_display_fields` warning; `zero_included` warning; `assignments.no_included_pairs` warning; `reviewer_missing` warning — `validate_page.md` **agrees with the code** | `instruments.md` and `assignments.md` say warning / info / error / error / error | **Contract decision.** `spec/README.md`'s precedence rule gives the subsystem spec authority, so the per-page lists are what to correct — but **two are specified as errors where the code warns, and as errors they would block activation**. All five untouched |
| `SS-02` | `rehydrate.md` §9 | cohort rules are not restored; the observers CSV carries only Email/Name/Tag1/Status | `csv_contracts.md` §3.2b and `roundtrip_coverage.md` say `CohortRule` round-trips, and the code agrees: `observers_extract.HEADER` includes it, `csv_imports.py:532-572` re-validates through `CohortRuleSet` | **Wants confirmation.** The rehydrate bullet **was edited** — its pointer named text the sweep removed. The one spec-vs-spec conflict the sweep settled rather than reported |
| ~~`SS-04`~~ | `operator_button_audit.md` §1 | 11 nav tabs, omitting **Observers** and **Extract data** | both required by `operator_ui_concept.md` | **Fixed** — added as chrome rows **12 and 13**, appended rather than slotted, because that file states its own rule that numbers are stable identifiers other documents cite |
| ~~`SS-05`~~ | `operator_button_audit.md` §13 | the page is "Manage Invitations" | `operator_ui_concept.md` and `operations_pages.md` call it "Invitations" | **Fixed** — `Invitations`, the chrome label, in all four places. Not one-sided: `email_infra_options.md` used the long form three times, so it was a vocabulary in circulation |
| ~~`SS-06`~~ | `session_home.md`, `operator_ui_concept.md` | a "ten-state cascade" | both list twelve, and `workflow_card.md` says twelve | **Fixed — not a mismatch.** Twelve states over ten numbers (1–10 plus `4W` and `4Err`); both counts were right. Now stated in `workflow_card.md`, so the five documents saying *ten-state cascade* stop reading as errors |
| ~~`SI-01`~~ | `instruments.md` | the action-row list omits `+Page break` | the per-instrument action-row section includes it, and the template renders it | **Fixed** — added to **both** lists in rendered order (Delete → `+Instrument` → `+Page break` → Lock/Unlock); ASCII box realigned |
| ~~`SI-02`~~ | `csv_contracts.md` | header: "five roster-shaped pairs (… Observers, Settings)" | §4's byte-stability contract: "four (Reviewers, Reviewees, Relationships, Settings)" | **Fixed — a distinction, not a correction.** Five pairs exist; byte-stability is established for four; whether Observers meets it is unverified and §4 now says so. *A guarantee that quietly covers four while the header counts five is how a round-trip regression goes unnoticed* |
| ~~`SI-03`~~ | `settings_inventory.md` §10 | two `audit_events` rows, ✅ analytics-only | …and ❌ out of scope | **Fixed** — duplicate removed; the survivor states what its ✅ does and does not mean |
| ~~`SI-04`~~ | `setup_pages.md` | the Upload confirm copy, two clauses | the same copy, three clauses, in the same file | **Fixed** — the partial now points at the full one. The template renders count / assignments / responses, and *the response clause had gone missing once already* |
| ~~`SI-05`~~ | `reviewer-surface.md:145` | *(See "Form scope" below)* | the section is "Form HTML mechanics" | **Fixed** — repointed to the heading that exists |
| ~~`SI-06`~~ | `permissions.md` | a decorator-scan recipe for finding ungated routes | the scan flags ≥9 correctly-gated `_instruments.py` routes | **Fixed** — the method now says to follow `Depends()` **transitively**. *A check that flags a correctly-gated route is worse than none, because the next reader believes it* |
| `SI-07` | `operations_pages.md` | a query budget of 43 / 84 / 134 / 234 / 434, *"measured through the real routes"* | **pinned by nothing** — the related test only asserts relative growth under 2.5× | **Needs a guard, and a guard is code.** Rewording would be theater |
| `SI-08` | `quick_setup_card_spec.md` | *"retained for fixture compatibility"* | the Quick Setup per-slot endpoints have **no live caller** (0 template hits) | **Prose** — restore the verifiable fact in place of the unverifiable claim |
| ~~`SI-09`~~ | `validate_page.md` | a rule count in the §3.2 heading, "(18 registered)" | nothing renews it | **Fixed** — the count is out of the heading |
| `SI-10` | `csv_contracts.md` §3.3 | the `rtds[` import tolerance appears only as an aside | the enforcement is unconditional and stronger than its documentation | **Prose** — give it its own bullet |
| `CC-01` | `session_lifecycle.py:36-38` | `SessionStatus`'s docstring: `expired` and `archived` are "reserved for later segments" | `expire_session` (`:459`) and `archive_session` (`:678`) write both | **Code** — comment only |
| `CC-02` | `routes_operator/_shared.py:298` | `"group_instrument_no_rule": 409` | dead mapping. **Checked**: `open_instrument`'s comment at `:779` records that Wave 5 PR 5.3 retired the gate deliberately | **Code** — dead-matter removal, not a lost gate |
| `CC-03` | `app/schemas/rules.py:6,367` | docstrings describe themselves as mirroring `rule_set_revisions` | a dropped table | **Code** — comment only |
| `CC-04` | `services/csv_imports.py:61-63` | names a `MANUAL_CSV_MAX_BYTES` constant and a "manual-assignments importer" | neither exists | **Code** — comment only |
| `CC-05` | `_serialize.serialize_session_config` docstring | lists "3. Operator-defined RTDs" and "6. Field-label overrides" as emitted sections | neither is emitted | **Code** — comment only; same defect as `SC-29` |
| `CC-06` | `services/visibility_policies.py:365-370` | documents `while_ongoing` as `[activated_at, deadline)` | the behavior is a status check, matching the spec | **Code** — the docstring is what is wrong |
| `CC-07` | `_operations.py:264,358-366` + `views/_previews.py:19` | the preview follow-on was Segment 18Q | `_preview_surface.py:3-6` explicitly corrects them | **Code** — **two comments disagreeing with each other** |
| `CC-08` | `db/models/email_outbox.py` | "Segment 14-1" | the specs say "Segment 14B"; the equivalence is in the 14B plan header | **Code** — findability, not error |
| `CC-09` | `base.html` comments | `--accent-blue-bg` (2330), "the active side fills accent-blue" (3571), `--accent-blue-marker` (872); and **"Danger Outline (.destructive)"** at 2479 | retired token names, and the pre-19B button vocabulary the doc guard bans in prose | **Code** — the guard reads specs, not CSS comments, so the retired vocabulary survives where nothing looks |
| `CC-10` | `_display_fields.py:797-801` | a docstring listing 3 `SortSpecError` codes | it raises 5 | **Code** — comment only |
| `CC-11` | `_serialize.py:561` | a comment saying a behavior "drops in PR 5.2" | PR 5.2 shipped | **Code** — comment only |
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

**74 findings**, counted by distinct id rather than asserted: `SC` 36, `CC` 11,
`SI` 10, `ID` 8, `SS` 5, `DT` 4.

*Recount before quoting this number.* It was published as 64, grew to 75 as the
verification passes reported, and is **74** — the `SS` ids run 01, 02, 04, 05,
06, with no third, because that number was a section heading before it was
de-numbered. Nothing renews a count, which is the defect this segment exists to
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
