# Sweep — history out of `spec/` (2026-09-13, Segment 19M)

**Swept:** 2026-09-13 onward, per batch · **Scope:** all **39 live
`spec/*.md`** files, 22,493 lines · **Plan:**
`guide/segment_19M_spec_history_sweep.md` · **Trigger:** not cadence —
the author's rule, after `guide/sweep_2026-09-13_ui_elements.md`
established it on one file and then had to be reversed to obey it.

<!-- sweep-scope: partial -->

**This does not reset the corpus cadence.** It reads every live `spec/`
file and **no** `docs/` file and no root document, so it is not the
whole-folder sweep the 8-weeks / 500-merges clock measures. The clock
still runs from `guide/sweep_2026-09-05_spec-docs.md`. Whether a
`spec/`-complete sweep should count is Open question 2 in the plan.

## 0. The rule being applied

> *"Express constraints as such, with brief reasoning if needed. But
> that's not strictly speaking 'history', even though the reasoning was
> confirmed through something in the history."* — the author, 2026-09-13

Three buckets, and the middle one is what makes the sweep safe rather
than destructive:

| bucket | disposition |
|---|---|
| **provenance** — when it landed, which PR, what it was called before, which proposal lost, what a previous draft got wrong | **out**, to `docs/status.md` / segment plans / this record |
| **constraint** — anything telling a future author *this must not change* | **stays**, re-expressed forward with a brief reason. *A reason established historically is not history.* |
| **absent subject** — a class, template or hack with **0** occurrences in `app/` | **deleted**, retirement recorded here |

**Uncertain passages are kept and listed.** A wrongly-kept sentence costs
a reader seconds; a wrongly-deleted constraint costs the next author a
regression.

## 0a. Correction mid-sweep — a spec is a contract, not ship-state

The author, three batches in: *"See sdd in practice doc in repo root for
distinction in function between spec and the other docs."* Then, pointedly:
*"Section 4."*

`rrw_sdd_in_practice.md` §4 splits the three folders **by question
answered**, and the authority column is the part this sweep had been
getting wrong:

| folder | answers | authority |
|---|---|---|
| `spec/` | *What is X supposed to look like and behave like?* | **The contract.** "When the code drifts from a spec, the spec is the canonical source — **fix the code** (or update the spec deliberately as part of a feature change, never silently)." |
| `docs/` | *How does X work today?* | Ship-state |
| `guide/` | *What are we building next, and how?* | The plan |

**The batches had been briefed to write "plain present-tense description
of what ships". That is `docs/`'s function.** The error is not in removing
history — that stands — but in what replaced it. A spec states an
obligation; it does not report the tree.

Three consequences, sent to all six agents mid-run:

1. **No measurements of the current tree.** *"36 `onclick` attributes"*,
   *"18 banner elements"*, *"0 occurrences in `app/`"*, *"no current users
   in app markup"* are ship-state — **and self-staling, which is this
   sweep's own diagnosis one level up.** §1 says a `*Current:*` block rots
   because nothing renews it; a count pasted into a contract rots the same
   way. State the rule, not the tally.
2. **A spec never hedges itself against the code.** *"Checked against
   `base.html`"*, *"verified"*, *"authoritative"*, a caveat naming which
   entries are reliable — none of it belongs in a contract, which does not
   report its own confidence level. **The reversal's own header note did
   exactly this** and is corrected.
3. **Where spec and code disagree, the spec wins — so do not rewrite the
   contract to match the code.** Verification is how a sweeper decides
   what to write, not something written down. A divergence is a **code
   defect or a deliberate contract change**, and §4 says a contract is
   never updated silently. This *reverses* part of the original brief: the
   absent-subject bucket still applies to an entry whose subject is
   genuinely gone with no contract behind it, but a spec **requiring**
   something the code lacks is a finding about the code.

**Consequence for the batches: fewer edits, more findings.** The
rule-shaped batches (Item 4's engine specs, Item 6's CSV contracts) should
now produce divergence reports where they would have produced rewrites,
and that is the correct outcome rather than an under-delivery.

*Item 3 completed before this reached it, so it ran under the old brief.
Its batch record below marks the two places the old framing shows, rather
than presenting them as settled.*


## 1. Why a mechanical pass was refused

The `ui_elements.md` sweep's dead-identifier pass produced twelve
candidates, of which **four were correctly-recorded history** that would
have made the file worse if "fixed". And across its two passes that sweep
made **five false claims** about the code — three in the sweep, two in the
reversal, both of the latter inside text the reversal had just declared
authoritative.

*Every one was possible because the passage being edited was a narrative
about the past rather than a description a reader could check. Prose about
what happened cannot go stale visibly; prose about what is can.* That is
the argument for the sweep and the reason it cannot be run by `grep`.

## 2. Batch records

Appended per item as each batch lands. Each records, per file: what was
removed and under which bucket, what was re-expressed forward, what was
deleted as an absent subject, what was kept as uncertain, every claim the
reading could not verify against the code, and every file read with no
finding.

*A batch that lists only changes implies the rest was read. The
no-finding list is what makes that true.*

<!-- Batch records begin here. -->

---

## Batch record — Item 3, core contracts and cross-cutting

Seven files: `rrw_functional_spec.md`, `architecture.md`, `lifecycle.md`,
`permissions.md`, `audience_and_identity_model.md`, `README.md`,
`domain_assumptions.md`. **412 inserted / 520 deleted.** Dated lines
**63 → 12**, and each of the twelve survivors is a constraint, a pointer,
or an example payload.

**This batch ran under the pre-correction brief** — it finished before
§0a below reached it — so it was asked for "present-tense description of
what ships" rather than for a contract. Its output mostly survives that,
because the files are rule-shaped and the batch treated them so; the two
places where the framing shows are noted as open decisions rather than
quietly kept.

### Provenance removed

Roughly **145 passages**: segment and PR attributions (19F, 18S, 18R,
19C, 19H, 19I, Wave 5, 18G, 18J, 15D, 13E, 11K, 16A/16B/16C), commit SHAs
(`49f1875`, `dfedd22a38da`, `36e7b1e7`), shipped-on dates, retired-on
dates, and **six "this document used to say X until 2026-09-10"
self-correction notes** in the functional spec alone — notes added by the
2026-09-10 sweep that corrected the text, then left behind as a record of
the correction inside the contract.

### Constraints re-expressed forward — the load-bearing ones

- **The audit cutover.** Now a named heading (`### Cutover boundary —
  2026-05-07`) stating the obligation rather than the event: the log is
  append-only, so anything reading `detail` across the whole table must
  branch on `audit_events.created_at`, the only cutover marker there is.
  The `EVENT_SCHEMAS` allowlist and the register-your-event_type
  obligation were **added** — `CLAUDE.md` requires them and this file did
  not state them.
- **Two lifecycle gates, stated as prohibitions.** *"The gate is
  `is_editable`, not `is_ready`"*, and for instruments *"it must not be
  `not is_ready`"* — because `is_ready` protects a surface only while the
  session is collecting, so on `expired` / `archived` the page would
  render live Delete buttons over finished data, and deleting an
  instrument runs the `Instrument` → `assignments` → `responses` cascade.
- **`_REVERT_RETURN_TO` fails silently.** Every slug a template posts must
  be in the allowlist; a missing one still 303s to Session Home, so the
  bug looks like success.
- **The results window needs `expired`, not merely the anchor reached** —
  otherwise an anchor set by any other path would open it.
- **The §19 reading guide**: *"a spec missing from it is a spec nobody is
  sent to."* Verified — all 37 other live specs are named.

### Absent subjects deleted — 4, each verified

The **RTD** glossary entry (no model, table, service or template; 13 hits,
all code comments); two retired bulk audit rows
(`instruments.bulk_accepting_responses`, `.bulk_visibility_when_closed` —
absent from `EVENT_SCHEMAS`, so no allowlist entry depended on them); and
`permissions.md`'s dated *"Drift noted at writing"* section, all three of
whose bullets were confirmed closed.

### Two self-contradictions resolved — flagged, not silent

Both were a file disagreeing with **itself**, which is why they were
fixed rather than reported:

- `lifecycle.md`'s header said **four** live states with `expired`
  reserved, directly above its own five-row table, and against
  `expire_session` at `session_lifecycle.py:459`. Now "five live states …
  none reserved".
- `audience_and_identity_model.md` said **two** live audiences three
  paragraphs above "the reviewee is a live participant audience". Now
  four, verified against the live `_results.py` / `_collation.py` routes
  and the gates in `deps.py`.

### Open decision — the functional spec's currency line

The batch **removed** `rrw_functional_spec.md`'s *"Aligned with the system
as of 2026-08-18"* and replaced it with a pointer to the sweep record,
reasoning that a hand-kept date moves only when someone remembers it.

**That has a precedent and a counter-authority, and the author should
settle it.** The precedent: 19J.1 did exactly this to `spec/README.md`, on
the stated grounds that *"a date nobody owns is what let §9.7 describe a
card that never shipped."* The counter-authority:
`rrw_sdd_in_practice.md` §6.2 presents the currency date as a **property
of the functional altitude** — it "carries a currency date and expects
ship-state may move ahead" — and notes only 4 of the live spec files
carry one, deliberately.

**Two consequences either way.** §6.2's *"4 of 36"* figure is now 3, and
`rrw_sdd_in_practice.md` line 38 **quotes the removed sentence** as
evidence. Those are the author's own measured analysis, so this sweep did
not edit them; a root document was out of scope and editing someone's
measurements as a side effect of a prose sweep would be the wrong kind of
thorough.

### Code-side findings — reported, not fixed

Under §4 the spec is canonical, so these are defects in the code or dead
matter, not stale prose:

- **`session_lifecycle.py:36-38`** — `SessionStatus`'s docstring still
  says `expired` and `archived` are *"reserved for later segments"* while
  `expire_session` (:459) and `archive_session` (:678) write both. The
  code-side twin of the `lifecycle.md` header error above.
- **`_shared.py:298`** — `"group_instrument_no_rule": 409` is a dead
  mapping. **Checked before trusting it**, because the batch wrote a spec
  claim on its strength: `open_instrument` carries a comment at :779
  recording that Wave 5 PR 5.3 retired that gate deliberately. So nothing
  raises the code, the mapping is dead, and the spec claim is true.
- **`app/schemas/rules.py:6,367`** — live docstrings describe themselves
  as mirroring `rule_set_revisions`, a dropped table.
- **`architecture.md:379`** — a stale *forward* pointer: magic-link
  anonymous access "deferred to Segment 16A", which shipped as the
  sys-admin page; `guide/deferred_consolidated.md:749` puts it under 14B.
- **`app/web/static/guide/`** holds 40 files for 20 figures, not the
  "thirty-two files for sixteen" the spec asserted. The count was removed
  rather than restated — nothing renews a count in prose — and the
  pairing rule and its failure mode kept.

### Frozen measurements — one converted, five kept

`permissions.md`'s *"128 of 128 routes carry a dependency"* became **"every
such route carries one"**, with the counting method preserved as the
invariant to check when adding a route. Verified first that no test reads
`128`.

Five test-case counts in `permissions.md` §7 were **kept and not
verified** — the same class of frozen measurement, but the batch could not
tell whether the author uses them as a coverage floor. Carried here as an
open item rather than guessed at.

### Stale identifiers — found and since fixed here

`rrw_functional_spec.md:1022` named `accent-blue` and `lifecycle.md:449`
named `accent-amber-dark` / `accent-amber-bg`, none of which is defined in
`base.html`. Both fixed after the batch closed: lifecycle now names the
shipped `--card-warning-border` / `--card-warning-bg` pair (verified, four
definitions across light and dark), and the functional spec now says
"blue-framed" with **no token identifier at all**, because §6.2 puts that
altitude at technology-neutral and shipped token names belong to the
per-page specs.

### Kept as uncertain — 5

Chief among them `domain_assumptions.md`'s `## Domain` block, whose
`Status:` lines contradict the shipped machine (`ready` described as
deadline-derived; archive described as deleting data). **Kept whole**: it
is undated and reads as the author's original domain intent, which is what
that file exists to record, and rewriting it would be authoring rather
than sweeping. Also kept: `architecture.md`'s consistency-audit ids
(`R1`–`R7`, a findability gap rather than history) and `lifecycle.md`
§8.2.3's auto-archive precondition for an unbuilt trigger.

### Open question 1 answered

The plan left *"one sweep record or six?"* to whoever landed Item 3: **one
file, as started.** Three batches in it is nowhere near the ~1,000-line
revisit threshold, and the three-bucket rule's boundary cases — a
retired-class record that still guards a live allowlist entry, a count
nobody renews — only make sense read across batches. Revisit after Item 6.

---

## Batch record — Item 4, the domain engine

Six files: `visibility_policy.md`, `assignments.md`, `instruments.md`,
`sort_by_reviewee.md`, `reconciling_regeneration.md`, `validate_page.md`.
**3,190 → 3,073 lines, 469 rewritten.**

**This is the first batch to run under §0a's correction, and it behaved as
§0a predicted: ten divergence findings and almost no deletions.** Absent
subjects deleted: **2** across six files, against **0** in four of them.
The batch also **rolled back one of its own earlier edits** once the
correction arrived — it had written the code's aggregate
`ReconcileImpact` shape into two specs, and restored the per-instrument
contract instead. *That is the correction working at the only point where
it could be observed.*

### Constraints re-expressed forward — the ones worth reading

- **The visibility ban, strengthened rather than restated.** Was: *"Both
  writers enforce it, since 19C Item 9 … Until then the import checked
  only the vocabulary."* Now: *"**Both writers enforce it, and both
  must.** Checking the vocabulary is not enough on the import path: a
  value can be one of `row` / `aggregated` / `identified` /
  `deidentified` and still be illegal in the cell it lands in, so a
  hand-built bundle would otherwise persist a `reviewee`
  `while_ongoing` grant no editor can author — a disclosure the resolver
  would then honor like any other row."*
- **The window is the status column, not the deadline.** *"A session
  leaves `ready` only when the operator closes it from the Workflow
  card"* — so the deadline passing does not close the window.
- **Why reconcile may not become a replace.** *"`Assignment.responses` is
  `cascade="all, delete-orphan"`, so a wholesale replace takes every
  saved response with it … neither the wholesale replace nor a
  keep-or-lose prompt may come back."* And the delete order is stated as
  load-bearing: these are bulk Core deletes that **bypass** the ORM
  cascade, so deleting assignments first orphans the responses and breaks
  the FK.
- **`unquote()` is not optional, and a test cannot be trusted to say so.**
  Starlette does not percent-decode cookie values, so without it
  `json.loads` fails on the browser's own encoding and SSR silently falls
  back to insertion order — silently, because the client-side JS
  re-sorts after paint and the badge still shows the column sorted. *A
  cookie-decoding test must write the value the way the browser writes
  it; one that sets raw JSON exercises nothing.*
- **Sorting must not happen in Python on a paged table.** Sorting a
  fetched window *"would sort page 2 within page 2 — invisible on an
  unpaged table, a lie on a paged one."*
- **The palette keys on instrument id, not loop position**, so colour
  rides with the instrument across reorder, replicate and delete.
- **A locked card never displays unsaved values** — *"a lock that copied
  the edited values into the read-only view would leave a collapsed,
  locked card asserting state the database does not have."*

### Absent subjects deleted — 2, both contract-sanctioned

The legacy single-mode visibility encoding (`visible_when` column: 26
hits in `app/`, **all** `responses_visible_when_closed` or comments; the
ORM carries only the four pair columns plus `observer_tag`) and the
Response Type Definitions card (`ResponseTypeDefinition` → **0** hits; no
model file). Both were already declared retired by the specs' own bodies,
so deleting the entries follows the contract rather than softening it, and
each absence is now stated as a rule (*"There is **no** page-level
response-type catalogue"*).

### Spec-vs-code divergences — contract left standing

Verified here rather than taken on the batch's word:

- **The `stale` pill is specified and cannot render.** `is_stale = False`
  at `views/_assignments.py:221` and `any_stale = False` at :202 — both
  hardcoded — while the same file's docstrings at :73 and :107 still
  describe the computation they no longer do. `compute_staleness` is live
  but uncalled on this path. **Confirmed.** Spec left standing: this is a
  code defect or a deliberate contract retirement, and §4 says that
  choice is made deliberately.
- **`stamp_changed` does not exist** — 0 hits in `app/` and `tests/`.
  **Confirmed.** The same finding one layer down.
- **A route path disagrees, and a URL is contract.** Spec:
  `…/assignments/instrument/{iid}/self-reviews-active`. Code
  (`_assignments.py:479`): `…/assignments/{instrument_id}/self-reviews/active`.
  **Confirmed.** Left standing; someone must choose which spelling wins.
- **Band 3 bounds validator** names `Number` / `Rating` / `SingleSelect` /
  `MultiSelect` where `bulk_save_fields` branches on `String` / `Integer`
  / `Decimal` / `List` — the four the spec's own Type picker lists eight
  lines above.
- **The `include` seed is pair-level in one spec, group-aware in code and
  in another spec.** Here the **code is right** and
  `reconciling_regeneration.md` is incomplete; left standing, because
  completing it is a contract edit.
- **A stale code comment, not a spec problem:**
  `visibility_policies.py:365-370` documents `while_ongoing` as
  `[activated_at, deadline)` while the behaviour matches the spec's
  status-column rule. The docstring is what is wrong.

### A spec-vs-SPEC conflict — five validation severities

Not spec-vs-code. `validate_page.md` **agrees with the code**; the
per-page specs do not:

| rule | code + `validate_page.md` | per-page spec |
|---|---|---|
| `instruments.no_fields` | error | **warning** |
| `instruments.no_display_fields` | warning | **info** |
| `instruments.zero_included` | warning | **error** |
| `assignments.no_included_pairs` | warning | **error** |
| `assignments.reviewer_missing` | warning | **error** |

**Verified the two consequential ones**: both `assignments.no_included_pairs`
and `instruments.zero_included` are `Severity.warning` in
`app/services/validation.py`. As *errors* they would **block activation**,
so the direction matters.

**My read, for the author to confirm:** `spec/README.md`'s precedence rule
gives the subsystem spec authority, and validation's subsystem spec is
`validate_page.md` — so the per-page lists are the ones to correct. But
that is an error → warning downgrade in two live specs, which is a
deliberate contract change and not a sweep's to make. All five left
untouched.

### Kept as uncertain, and claims not verified

Chief among the uncertain: `assignments.md`'s whole `### Staleness`
section and its `stale` pill (kept because the spec is left stricter), and
the `always` visibility window — 0 occurrences of the value anywhere, but
`spec/README.md` still lists it as one of four windows, so deleting it
would dangle another spec's summary. Reworded to *"**Reserved**, and not
authorable — no pair encodes it"* instead of deleted.

Unverified and carried rather than guessed: the status-row copy *"N
instruments — M accepting responses."*; the word *"pastel"* for the
`--surface-tint-1..6` palette; the truncation string; the tri-state click
transitions in the operator JS; `validate_page.md`'s banner copy.

### Two findings in other batches' files

`operator_ui_concept.md:96` lists the `rrw-sort` adopters as *"Reviewers /
Reviewees / Relationships + the Operations Assignments table"* —
Invitations and Responses are missing, and Assignments no longer uses
`apply_cookie_sort` at all. And `instruments.md` contradicts itself on
whether the action row carries `+Page break`. Reported, not touched.

### Stale colour identifiers: none

`grep -n "accent-\|text-primary\|bg-page"` over all six files → **0**.

---

## Batch record — Item 5, participant and reviewer surfaces

Five files: `reviewer-surface.md`, `participant_model.md`,
`role_landing_and_visibility.md`, `role_navigator.md`, `preview_hub.md`.
**65 provenance passages removed.**

**The correction's clearest demonstration.** This batch **reverted six
contract-to-code rewrites** it had already made, stripped the ship-state
measurements and reliability caveats it had written into all five files,
and reported **15 divergences** instead. One revert is worth naming: it
had deleted the Next Action card's *"See previews"* button as an absent
subject; under §4 that was wrong, because the button is a **contract** and
the code is what lacks it. Restored.

### The finding that matters most — a test that cites the spec it contradicts

`reviewer-surface.md` specifies `typical_chars = max_length * 0.75` and
names `_TYPICAL_RESPONSE_FRACTION` as the factor. **Verified here:**
`views/_instruments.py:226` sets it to **0.5**, and
`tests/integration/test_instrument_builder_routes.py:6859` asserts
`"TYPICAL_RESPONSE_FRACTION = 0.5"` in the rendered body.

So the spec stands against the code **and** against a test that pins the
code. The same shape appears in divergence 1, where
`test_reviewer_view_helpers.py` pins the code's heading format *and cites
this spec section as its authority* — **the test and the spec it names
disagree, and the test is what would fail if the contract were honored.**

*A test that enshrines an implementation against its own cited spec is a
harder problem than prose drift: the gate is on the wrong side.* Left
standing, unfixed; changing it means changing an assertion, which is a
deliberate call.

### Constraints re-expressed forward

- **No per-row submitted timestamp.** Submit stamps a single `now()`
  across every row, so a per-row stamp is always NULL or
  uniform-for-the-reviewer; printing it repeats the summary page's
  session-level timestamp once per reviewee.
- **The hub carries no embedded copy of the reviewer surface** — *"a
  second rendering path is the one thing a production-parity preview
  cannot afford."* Likewise no preview-only context builder: one that
  un-collapsed groups is the drift the shared path exists to prevent.
- **`/results` answers 404, not 403, and carries no role-naming
  `detail`** — either tells the caller both that the session exists and
  that they are on it.
- **`build_role_chips` must not answer from roster membership alone** — a
  membership-only answer hands a user a live Reviewee chip pointing at the
  404 `/results` gives them. Reachability is asked per role and never
  inherited from the route's own gate.
- **The URL slot carries the page number, never the instrument position**,
  which keeps a single-page session a degenerate case of one model.
- **308, not 303, for `/preview`** — it has to keep the GET method and the
  bookmark semantics, and its target is the route, never a fragment,
  because *"an anchor into a card is only as durable as the card."*
- **The archive short-circuit is defense in depth and must not be removed
  as redundant.** The rule is *emergent* — it holds only while two
  `session_lifecycle` predicates keep refusing archived sessions — so
  `_observer_collation.py` carries an explicit `is_archived` branch
  returning `cohort_empty=False`, because `True` renders "No cohort is
  configured for you yet" and blames the operator for something that is
  configured.

### A structural question the sweep could not settle

**`role_landing_and_visibility.md` may be a `docs/` document living in
`spec/`.** Its own opening answers *"given my role, can I sign in, where
do I land, and what do I see?"* and its tables were introduced as
*"recorded from a running app"* — which is §4's question for `docs/`, not
the contract question for `spec/`. The batch softened the method claim but
**declined to move or rewrite the file**, and flags it for the author.

*That is the right call: relocating a spec is a contract decision, and it
is exactly the kind of thing a prose sweep should surface rather than
perform.*

### Absent subjects deleted — verified 0 occurrences each

`DashboardPageRow` / `_build_dashboard_page_rows` / `_rollup_page_state`
(the "per-page sub-rows" section, replaced by the rule it implies: *"One
row per session, never per page"*), `build_preview_context`,
`.rs-paginated`, and `participant_model.md`'s `### Drift (planned
cleanup)` subsection. The **Enter / Shift+Enter column-navigation
requirement was kept** even though no `keydown` handler exists on the
surface — a requirement the code has not met is the spec working.

### Divergences left standing — 15

Beyond those above: action-row button labels (`Discard` vs `Cancel`, Save
as Primary vs `.btn.secondary`), the missing `max-width: 16em` /
`text-overflow: ellipsis` on page buttons, the Operations chrome row
missing `Extract data`, the per-artifact *"Send test to…"* affordance
(nothing in `app/`), `show_acknowledge` (0 occurrences, and the file
already contradicts itself about it), the dashboard `closed` pill
(`pill-lifecycle-archived` specified, `pill-error` rendered),
`submit_redirect_url`'s signature, the preview route path, and the
identity-match mechanism (SQL `func.lower` specified, Python
`normalize_email` used).

Also reported, not spec: `_operations.py` and `views/_previews.py`
attribute the preview follow-on to "Segment 18Q" while
`_preview_surface.py:3-6` explicitly corrects that attribution. **Two code
comments disagree with each other.**

### Stale identifiers — 3 lines, left for Item 1

`participant_model.md:86` (`--accent-blue`, `--accent-blue-bg-faint`;
the rule uses `--card-active-border` / `--card-active-bg`),
`role_navigator.md:113` (`--surface-2`, `--text-muted`; really
`--surface-muted` / `--text-subtle`) and `:114` (`--text-primary`; really
`--text-body`).

### One pre-existing dangling pointer, reported not fixed

`reviewer-surface.md:145` says *(See "Form scope" below)*; the section is
called "Form HTML mechanics".
