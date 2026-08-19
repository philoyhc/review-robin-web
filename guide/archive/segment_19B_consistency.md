# Segment 19B — Consistency remediation

> **Archived 2026-08-19 — shipped complete.** Retired to `guide/archive/`
> once every finding landed. The per-finding catalogue is
> `guide/archive/consistency_audit.md`.

> **Started + completed 2026-08-19.** The code-level sibling of Segment
> 19A (documentation hygiene). Where 19A keeps `spec/` and `docs/`
> current, 19B keeps the **code** internally consistent — it worked
> through the drift catalogued in `guide/archive/consistency_audit.md`. **All
> 29 findings resolved across 15 items (PRs #1987–#2003)** — see the
> "Segment complete" note at the end.

## Charter

The 2026-08-19 consistency audit (`guide/archive/consistency_audit.md`) swept
four seams — service / route / template / view-adapter — for places
where Review Robin Web does the **same conceptual thing in more than
one way**: the same business operation invoked through divergent
service APIs, the same HTTP action exposed under divergent
conventions, the same derived value computed twice, the same user
gesture presented through divergent affordances. It found **28
findings** (6 High / 10 Medium / the rest Low), each anchored to
`path:line`, with a batched remediation order.

19B lands that remediation in reviewable slices, in the audit's
recommended order. Each slice cites the audit's finding ids so the
catalogue stays the index of record.

## Slices

### Item 1 — S1–S5: service-layer identity + dedup — ✅ done 2026-08-19

The first, highest-value batch — the service-layer findings, which
were the only ones carrying a genuine correctness risk (auth-adjacent
identity comparison) rather than pure maintenance drift.

- **S1 — one instrument label.** Deleted the divergent
  `app/services/validation.py::_instrument_label` (it fell back to the
  internal `name`); `validation.py` now imports the canonical
  `app.services.instruments._instrument_label`, whose fallback is
  `Instrument_{id}`. An instrument with no `short_label` now reads the
  same across validation messages, audit copy, and operator UI.
  *(Test `tests/unit/test_validation_per_instrument.py` updated: its
  `_add_instrument` helper now sets `short_label`, matching how
  production instruments actually acquire an operator-facing label.)*

- **S2 / S3 / S4 — one email-identity home.** New
  `app/services/email_identity.py` holds:
  - `EMAIL_RE` — the email-shape regex, previously copied verbatim in
    five modules (participants / reviewers / reviewees / observers /
    csv_imports).
  - `looks_like_email(value)` — the "is this a well-formed email?"
    predicate, previously split between a strict `fullmatch` (the
    surface-reachability gate) and a `"@" in value` heuristic (import
    time).
  - `normalize_email(value)` — `strip().casefold()`, the canonical
    case-insensitive comparison key.

  Every identity-match site now folds through `normalize_email`:
  the roster uniqueness gates (`reviewers`/`reviewees`/`observers`
  `_email_taken` / `_identifier_taken`, converted from SQL
  `func.lower` to a session-bounded in-Python scan so the fold matches
  the access gates), the participant access gates (`app/web/deps.py`),
  the cross-role lobby (`routes_reviewer/_shared.py::build_role_chips`,
  whose three role branches now use one convention instead of mixing
  SQL `lower` with Python `casefold`), the Validate-page duplicate
  checks, the CSV importers + relationships CSV match, the
  self-review classifier, the session-rehydrate + responses-import
  matchers, and the rule engine. `str.casefold` (not `str.lower`) is
  the Unicode-correct fold, so write-time uniqueness and read-time
  access can no longer disagree.

  *Deliberate scope note:* the **global** `users`-table lookup
  (`app/services/users.py`) stays on SQL `func.lower` — it can't load
  the whole table into Python, and it doesn't participate in the
  per-session roster write-vs-gate hazard S2 is about.

- **S5 — one bulk status-flip.** New
  `app/services/roster_bulk.py::bulk_set_status` replaces the four
  byte-identical `_bulk_set_status` copies in reviewers / reviewees /
  observers / relationships; each caller now supplies only what
  genuinely differs (model, status normaliser, `*OperationError`
  class, entity noun).

  Also folded in the S8 doc-fix (the `create_reviewer` docstring
  claimed a "case-sensitive" duplicate check that was always
  case-insensitive).

  Verification: full suite green (2,680 passed, 17 skipped); ruff
  clean. No schema/migration change. Behaviour change is limited to
  the casefold-vs-lower distinction (identical for ASCII; casefold is
  the more correct fold for the rare non-ASCII address) and the S1
  label fallback.

### Item 2 — S6–S7: service-dedup tail — ✅ done 2026-08-19

The remaining service-layer findings — pure maintenance dedup, zero
behaviour change. Completes the whole service column (S1–S8).

- **S6 — one roster-status home.** New `app/services/roster_status.py`
  holds `ROSTER_STATUSES` (the shared `{"active", "inactive"}`
  vocabulary), `normalise_status(value, *, error_cls)`, and
  `is_active(row)`. Kept deliberately dependency-light (no `audit` /
  `session_lifecycle` imports) so the assignments package can use it
  without an import cycle — which is why it's a separate module from
  the heavier `roster_bulk`. The four `_normalised_status` /
  `_normalised_rel_status` collapse to one-line delegations passing
  their own `*OperationError`; the relationships CSV-parse check
  reuses `ROSTER_STATUSES`; `assignments/_shared._is_active` delegates
  to `is_active`.
- **S7 — one response-count query.** Extracted
  `_response_count_for_field(db, field_id)` into
  `instruments/_state.py` (the cross-slice plumbing home both slices
  already import from); the three copies in `_band2.py` (×2) and
  `_response_fields.py` now call it.

  Verification: full suite green (2,680 passed, 17 skipped); ruff
  clean. No schema change; no behaviour change.

### Item 3 — R1 / R10 / R11: route-sweep mechanical + doc batch — ✅ done 2026-08-19

The first, no-URL-change batch of the route sweep. The two gating design
decisions were settled by the maintainer: **R1 — keep the extract-data
AJAX sub-API as a blessed exception** (document, don't convert); **R6 —
adopt the `delete` = destroy-owned-row / `remove` = detach-membership
rule** (lands in a later batch).

- **R1** — `spec/architecture.md` gained a "Route conventions" section:
  the POST + verb-in-path + `Form` + 303-redirect house style, plus the
  extract-data REST/JSON/PATCH sub-API documented as the blessed
  exception and the pattern new AJAX endpoints should converge on (R4).
- **R10** — the two bare `status_code=303` literals (`_results.py`,
  `_rehydrate.py`) now use `status.HTTP_303_SEE_OTHER`.
- **R11** — the `/edit` legacy GET redirect moved from 301 to
  `status.HTTP_308_PERMANENT_REDIRECT`, matching the `/preview` shim.
- Also fixed the `_instruments_band2.py` docstring that claimed "204"
  but returned `200`.

Verification: full suite green; ruff clean. No behaviour change beyond
the 301→308 status on one legacy redirect.

### Item 4 — R5 / R6 / R7 / R9: URL-verb renames — ✅ done 2026-08-19

The route-naming batch. The naming rules are now recorded in
`spec/architecture.md` § "Route conventions".

- **R5** — the four lobby bulk routes `*-selected` →
  `bulk-archive` / `bulk-unarchive` / `bulk-delete` /
  `bulk-delete-archived` (joining `bulk-tags`), across `_lobby.py` + the
  three templates + three test files.
- **R6** — applied the `delete`=destroy / `remove`=detach rule: the only
  offender, `/sys-admin/users/{id}/remove` (which deletes the user), is
  renamed `/delete`. `owners/{uid}/remove` and
  `users/{id}/remove-from-all-sessions` are genuine detaches, unchanged.
- **R7** — documented as a **justified divergence** (not renamed):
  instruments has two creation kinds so verb-first `add-group` /
  `add-new-model` names the kind, while single-kind `owners/add` stays
  sub-resource. Forcing one mould degrades the other; the convention is
  documented instead.
- **R9** — `setupinvite` → `setup-invite` on the three routes + every URL
  reference (manage-url, two chrome partials, the page template, three
  test files). Internal identifiers (handler names, template filename,
  DOM ids) are unchanged — only the URL moved.

Verification: full suite green (2,680 passed, 17 skipped); ruff clean.
The renamed URLs are operator-internal POST endpoints + one setup GET;
no legacy redirect shims were kept (a shim would re-introduce the kind
of thing R11 cleaned up).

### Item 6 — R2 / R4: route-sweep structural (activate UX + AJAX bodies) — ✅ done 2026-08-19

Two of the three structural route items (maintainer-chosen approaches):

- **R2 — align the activate error surface.** The Validate-page
  `/activate` (post-warnings-acknowledge commit) and the Workflow-card
  `/workflow/activate` can't merge, so `_redirect_url` moved from
  `_workflow.py` to `_shared.py` and `session_activate`'s
  `LifecycleError` handler now redirects to the Session Home flash
  (`super_status=failed&super_button=activate`) instead of raising an
  error page — both activate buttons now fail the same way. (`/revert`
  and the instrument edit-lock keep the error-page response.) Four
  lifecycle tests updated from `400` → `303`+flash.
- **R4 — shared parse helper (not full Pydantic).** The six copied
  `await request.json()` + dict-check blocks (`_instruments_band2.py`
  ×3, `_instruments.py` ×2, `_instruments_pagination.py` ×1) now call
  `require_json_object(request, label=...)` in `_shared.py`, keeping the
  hand-rolled **400 + tailored message** the client JS expects. The
  extract-data sub-API stays the blessed Pydantic pattern for new
  endpoints (R1 note).

Verification: full suite green (2,680 passed, 17 skipped); ruff clean.

### Item 7 — R3: resolved by decision (accepted as-is) — 2026-08-19

The last route item. Converting the bulk / delete-all handlers to inline
re-render would need a **new page-level error banner** across the four
setup templates (the `edit_error` banner renders only inside the add/edit
form), and every error path in scope (`not_in_session` /
`invalid_status` / missing-`confirm`) is **unreachable through the UI** —
only a forged/buggy client hits them. Maintainer decision: **accept
as-is + document + defer the build**. The convention (inline re-render =
form-error contract; forged-only bulk guards keep the error page) is
recorded in `spec/architecture.md` § "Route conventions"; the deferred
four-template banner build is logged in `guide/deferred_consolidated.md`
(Part C) with its lift trigger. No code change.

**This closes the entire route sweep, R1–R11.**

### Item 8 — U1 / U2 / U4: UI-vocabulary batch (button styling) — ✅ done 2026-08-19

The template/CSS-only "button vocabulary" batch. Best verified on the
dev slot after deploy (the test suite doesn't exercise button classes).

- **U1** — every routine in-editor **Save** is now Secondary: the four
  operator row-edit Saves, the reviewer-surface `Save`, and the
  sessions-lobby expander `Save`. The reviewer-surface **`Submit`**
  stays Primary as the page's single main affirmative — a clean
  Save/Discard-secondary → Submit-primary hierarchy.
- **U2** — the two banner Cancels styled `.btn secondary`
  (`next_action_card.html`, `instruments_index.html` ×2) → `.btn alert`,
  matching `session_validate.html`.
- **U4** — the no-op `.btn primary` token dropped everywhere: the U1
  row-Saves became `.btn secondary`; the two reviewer Download buttons
  became bare `.btn` (visual no-op). No `btn primary` remains.

Verification: full suite green (2,680 passed, 17 skipped); ruff clean.

### Item 9 — U5 + U6: amber `danger-solid` for archive — ✅ done 2026-08-19

Maintainer-chosen resolution (differentiate, not collapse):
`.btn.danger-solid` became a **filled amber** style — distinct from the
outline-red `.btn.destructive` (deletes) and the outline-amber
`.btn.alert` (lock recovery). All archive/purge actions
(`next_action_card` "Archive session", `sessions_list` "Purge and
archive"/"…all") now use it; the Acknowledge-and-activate confirm
buttons already used `danger-solid`, so they pick up the amber too — a
"proceed with caution" reading. `spec/ui_elements.md` refreshed (button
table + hover + confirm-banner notes). Template/CSS-only — best
eyeballed on the dev slot; full suite green.

### Item 10 — U3: unify the delete-confirm mechanism — ✅ done 2026-08-19

The safety-weighted one. Both `session_detail.html` danger-zone buttons
(`Delete Data`, `Delete session`) were "required-checkbox-only" — the
button was **never greyed**, so the app's highest-stakes action (Delete
session on Session Home) was its *least*-gated. **Fixed:** both now use
the app-wide `data-delete-confirm` / `data-delete-btn`
**disabled-until-checked** standard (button ships
`disabled aria-disabled="true"`; the checkbox enables it; `required`
still belt-and-suspenders the JS-off case). The `Delete session`
`is_ready` lock still holds — the checkbox is `disabled` when the session
is activated, so the button stays disabled via the same JS. Every
delete-confirm is now disabled-until-checked.

Confirm-label voice unified to the affirmative **"Yes, delete …"**: the
sessions-lobby / archived expanders' bare "Allow delete" → compact "Yes,
delete". The expanders keep their **own per-node script** (a *list* of
destructive rows can't use the app-wide single-`querySelector` pairing) —
same behaviour + voice, justified implementation split. Documented in
`spec/ui_elements.md` (danger-zone → "Delete-confirm standard").

Verification: full suite green (2,680 passed, 17 skipped); ruff clean.
Template-only — best eyeballed on the dev slot.

### Item 11 — U7 + U8: label/verb nits — ✅ done 2026-08-19

- **U7** — the two "Clear all" filter-reset controls (`sessions_list`,
  `sessions_archived`) and the "Clear filters" link
  (`sys_admin_session_audit_log`) → **"Clear"**, matching the seven
  setup/list pages. The destructive "Clear all settings" / "Clear all
  responses" headings are separate actions, left alone.
- **U8** — the reviewer-surface abandon-input control (`_action_row.html`)
  relabelled `Discard` → **`Cancel`**, matching every operator inline
  editor. The `data-rs-discard` JS hook is unchanged (internal).

Six tests updated for the new labels. Full suite green; ruff clean.

**This closes the entire UI-vocabulary sweep, U1–U8.**

### Item 12 — U9 + U10: style nits — ✅ done 2026-08-19

- **U9** — the three `data-shape-delete` "Delete shape" buttons in the
  extract-data shaper were `.btn secondary`; since they hit the persisted
  `DELETE .../shapes/{id}` endpoint they're now `.btn destructive`,
  matching the app-wide "Delete = red" convention.
- **U10** — the two danger-zone `<h2 style="margin-top: 0;">` inline
  styles were **redundant** (the ui-v2 `.card h2 { margin: 0 … }` rule
  already zeroes the top margin); dropped both, so all five danger-zone
  headings are bare `<h2>` and consistent — no visual change.

Full suite green (2,680 passed, 17 skipped); ruff clean. **This closes
the entire template/UX seam, U1–U10.**

### Item 13 — V1 + V4: instrument label/heading dedup — ✅ done 2026-08-19

The instrument-label family — folds together with S1 (the same
`short_label`-fallback question).

- **V1** — `_reviewee_results.py` and `_reviewer_summary.py` dropped
  their byte-identical inline `instrument_heading` reimpl and now call
  the canonical `instrument_heading(...).title` (the same one the
  reviewer surface + observer collation use), so the same instrument
  reads identically across every reader surface. The empty-title case
  falls back to the canonical operator label `_instrument_label`
  (`Instrument_{id}`) — never the internal `name`. One test rewritten
  (it asserted the old `name`-fallback bug).
- **V4** — the hand-rolled `short_label or name …` display/error labels
  (`_assignments.py`, `visibility_policies.py`, `_surface/_context.py`,
  `extracts/responses_import.py` ×2) now route through the canonical
  `instruments._instrument_label`. The **CSV-safe positioned variants**
  stay as their own named helpers
  (`entity_metadata_extract._instrument_short_or_fallback`,
  `by_instrument_extract.fallback_instrument_label`).

Verification: full suite green (2,680 passed, 17 skipped); ruff clean;
no import cycles.

### Item 14 — V2: one progress-pill helper — ✅ done 2026-08-19

New `app/web/views/_progress.py::progress_pill(state) → ProgressPill(css,
label)`, registered as a Jinja global on both the operator and reviewer
template instances. The four hand-rolled progress pills
(`reviewer/dashboard`, `operator/session_invitations`,
`…_reviewer_detail`, `reviewer/review_surface`) now render
`<span class="pill {{ p.css }}">` from it. One canonical colour semantic
(**blue = not started · amber = in progress · green = submitted /
complete**) closes the drift; the helper normalises **both enum
spellings** (`in_progress` and `in progress`), closing the vocabulary
split. The page-level `complete` state keeps its own label. Two tests
updated for the new canonical rendering. Full suite green; ruff clean.

### Item 15 — V3 + V5 + V6: the dedup tail — ✅ done 2026-08-19

- **V3** — new `User.display_label` property (`display_name or email`);
  the seven email-fallback User sites (`_lobby`, three creator-pill
  templates, the owner-candidate option, the two "Signed in as" chrome
  bars) now use it. The `display_name or "—"` name-only variant (email
  in an adjacent column) stays inline as the deliberate form; the
  `Observer` sites are a separate model, left alone.
- **V5** — the bucket-set logic moved to `monitoring.is_at_risk_state` /
  `is_incomplete_state`; all four properties (two `monitoring`
  dataclasses + the `_responses` / `_invitations` view rows) delegate.
- **V6** — new `app/services/text.py::pluralize(count, singular,
  plural=None)`; `_setup`'s draft/drafts and the five response/submission
  idioms in `responses/_core.py` call it.

Full suite green (2,680 passed, 17 skipped); ruff clean; no import
cycles.

## ✅ Segment complete

**Every consistency-audit finding is resolved** — Service **S1–S8**,
Route **R1–R11**, Template/UX **U1–U10**, View-adapter **V1–V6**, across
15 items / PRs #1987–#2003. Two findings closed by decision rather than
code (R3 accepted + deferred; R1/R7 documented as justified
conventions). See `guide/archive/consistency_audit.md` for the per-finding
record.

## Hard dependencies

- **None.** Item 1 shipped standalone. The route + UI decisions
  (R1 / R6) gate their own slices but nothing else.

## Doc impact

- `guide/archive/consistency_audit.md` is the finding index — cite finding ids
  from each slice; leave the audit itself as the frozen catalogue.
- `guide/todo_master.md` carries the at-a-glance 19B entry.
- `docs/status.md` gets a timeline row per shipped slice.
