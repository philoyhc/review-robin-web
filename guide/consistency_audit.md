# Consistency audit — one functionality, many call paths

**Audited 2026-08-19 against `main` at `fd4950b`.**

The question this doc answers: *where does Review Robin Web do the same
conceptual thing in more than one way* — the same business operation
invoked through divergent service APIs, the same HTTP action exposed
under divergent conventions, the same derived value computed in two
places, or the same user gesture presented through divergent UI
affordances. These are not (mostly) bugs today; they are drift hazards —
each pair is a place where a future edit to one copy silently disagrees
with the other.

Four read-only agents swept four seams in parallel: the service /
business-logic layer, the route / HTTP layer, the Jinja template / UX
layer, and the view-adapter / data-shaping layer. Every `path:line`
below was read directly by an agent; the two highest-severity items
(S1, V1) were additionally hand-verified while writing this up.

---

## Remediation status

Tracked as **Segment 19B** (`guide/segment_19B_consistency.md`).

- **✅ Service column complete (S1–S8)** — shipped 2026-08-19.
  - **Item 1** (PR #1987): S1 (one instrument label), S2/S3/S4 (the
    `email_identity` module), S5 (shared `bulk_set_status`), S8
    (docstring fix).
  - **Item 2**: S6 (shared `roster_status` — `ROSTER_STATUSES` /
    `normalise_status` / `is_active`), S7 (shared
    `_response_count_for_field`).
- **🔶 Route sweep (R1–R11) in progress.**
  - **Item 3** (this slice): R1 (documented the extract-data AJAX
    sub-API as a blessed exception in `spec/architecture.md`), R10
    (bare `303` → `status.HTTP_303_SEE_OTHER`), R11 (`/edit` legacy
    redirect 301 → 308), + the `_instruments_band2.py` `204`/`200`
    docstring fix. **Still open:** R2–R9 (activate consolidation,
    error-redisplay unification, AJAX Pydantic bodies, the URL-verb
    renames, the two-route edit consolidation).
- **Open** — the UI-vocabulary sweep (U1–U8) and the view-adapter dedup
  (V1–V6). Order below unchanged.

---

## Severity-ranked master list

| # | Sev | Seam | One line |
|---|-----|------|----------|
| ✅ **S1** | 🔴 High | Service | `_instrument_label` has two implementations with **different fallbacks** — same instrument shows two different names |
| **V1** | 🔴 High | View | `instrument_heading` reimplemented inline in two view modules; single-instrument fallback diverges (`name` vs `description`) |
| **V2** | 🔴 High | View/UX | Reviewer-progress pill state → (label, colour) hand-rolled in 4 templates; same state coloured differently; two enum spellings |
| **U1** | 🔴 High | UX | "Save" styled Primary on some surfaces, Secondary on others — split even within one page |
| **U2** | 🔴 High | UX | Banner "Cancel" styled `.btn alert` (per spec) vs `.btn secondary` |
| **U3** | 🔴 High | UX | Destructive-delete confirmation gated two incompatible ways; the highest-stakes action is the *least* gated |
| ✅ **S2** | 🟠 Med | Service | Roster email matching uses three case-folding conventions (`casefold` / SQL `lower` / `lower`) — write-time vs gate-time can disagree |
| ✅ **S3** | 🟠 Med | Service | "Is this an email" classified two incompatible ways (strict regex vs `"@" in value`) |
| ✅ **R1** | 🟠 Med | Route | Data-shaper endpoints are a REST/PATCH/DELETE/JSON island in a POST-only app *(documented as a blessed exception)* |
| **R2** | 🟠 Med | Route | "Activate session" exposed at two URLs with divergent failure UX |
| **R3** | 🟠 Med | Route | Same operation-error class redisplayed three ways (inline re-render / raw error page / flash redirect) |
| **R4** | 🟠 Med | Route | JSON AJAX bodies: hand-rolled `request.json()` validation vs Pydantic model |
| **V3** | 🟠 Med | View | User display-label (`display_name or email`) hand-rolled 7+ times, with a `"—"`-fallback variant |
| **V4** | 🟠 Med | View/Service | Instrument friendly-label fallback reimplemented ~8 places with **four different tails** |
| ✅ **S4** | 🟠 Med | Service | `_EMAIL_RE` regex literal duplicated five times |
| ✅ **S5** | 🟠 Med | Service | `_bulk_set_status` reimplemented four times (verbatim algorithm) |
| **R5** | 🟡 Low | Route | Bulk-action naming: `bulk-<verb>` vs `<verb>-selected` |
| **R6** | 🟡 Low | Route | Single-entity removal verb: `/delete` vs `/remove` vs `/delete-all` |
| **R7** | 🟡 Low | Route | Creation verb: `owners/add` (sub-resource) vs `add-group` (verb-first) |
| **U4** | 🟡 Low | UX | Dead/duplicate Primary token `class="btn primary"` vs `class="btn"` |
| **U5** | 🟡 Low | UX | "Archive" styled Destructive one place, Outline-amber another |
| **U6** | 🟡 Low | UX | Two class names for one identical Destructive style (`.destructive` / `.danger-solid`) |
| **U7** | 🟡 Low | UX | Filter-reset label: "Clear" / "Clear all" / "Clear filters" |
| **U8** | 🟡 Low | UX | Abandon-edits verb: "Discard" (reviewer) vs "Cancel" (operator) |
| ✅ **S6** | 🟡 Low | Service | Status normalization / active-predicate duplicated in five spots |
| ✅ **S7** | 🟡 Low | Service | "Count responses for a field id" query duplicated three times |
| **V5** | 🟡 Low | View | `is_at_risk` / `is_incomplete` predicates duplicated between service and view dataclasses |
| **V6** | 🟡 Low | View | Ad-hoc pluralization inline in multiple modules; no `pluralize()` helper |
| others | 🟡 Low | Route/UX/Service | R8–R11, U9–U10, S8 — naming/style nits, listed in-section |

---

## A. Service / business-logic layer

### S1 🔴 Two `_instrument_label` implementations with different fallbacks — *verified* — ✅ done (19B Item 1)

Same functionality: the human-readable operator/reviewer label for an
instrument.

- Canonical (CLAUDE.md names this the home):
  `app/services/instruments/_state.py:39` — returns `short_label`, else
  `f"Instrument_{instrument.id}"`. Its docstring explicitly states the
  auto-generated `name` "no longer participate[s] in the chain" per the
  2026-05-28 identifier policy.
- Private re-implementation:
  `app/services/validation.py:272` — returns
  `instrument.short_label or instrument.name`, i.e. it falls back to
  exactly the `name` the canonical version deliberately dropped.

**Divergence:** an instrument with no `short_label` is labelled
`Instrument_42` in audit copy / operator UI but by its raw
auto-generated `name` in the four validation messages that call the
local copy (`validation.py:396,441,512,577`). Same instrument, two
different names in the operator's face.

**Fix:** delete `validation.py:_instrument_label`; import
`_instrument_label` from `app.services.instruments` (the documented
cross-slice home). Trivial, user-visible, highest value.

### S2 🟠 Roster email matching uses three case-folding conventions — ✅ done (19B Item 1)

Same functionality: "does this roster row's email match this identity",
case-insensitively. Three mutually inconsistent normalisations are live:

- Python `.casefold()` — `app/web/deps.py:263,266,312,323,366,375`;
  `routes_reviewer/_dashboard.py:80`;
  `app/services/relationships.py:96,98,130,145`;
  `app/web/views/_filters.py` (many);
  `app/services/assignments/_self_review.py:30`.
- SQL `func.lower(...)` — `app/services/reviewers.py:106`,
  `reviewees.py:111`, `observers.py:109` (the uniqueness gates),
  `app/services/users.py:479`,
  `app/web/routes_reviewer/_shared.py:154,175`.
- Python `.lower()` — `app/services/csv_imports.py:267,290,478,571,598`,
  `session_rehydrate.py:283,287`,
  `extracts/responses_import.py:260,319,335`,
  `rules/engine.py:318,321`, `validation.py:120,159`.

**Divergence:** `str.casefold()` is strictly more aggressive than SQL
`LOWER` / `str.lower()` (e.g. `ß`, Turkish dotless-i). The uniqueness
check that decides whether a duplicate email is *rejected on write*
(`func.lower`) can disagree with the *identity gate that grants access*
(`casefold`) for the same address. Worse, it is inconsistent **within a
single function**: `build_role_chips` in `routes_reviewer/_shared.py`
matches reviewers/observers with SQL `func.lower` (154, 175) but matches
reviewees with `.casefold()` (167).

**Fix:** one `normalize_email(s) -> s.strip().casefold()` helper applied
both when storing and when comparing; roster uniqueness compares against
the stored normalised value.

### S3 🟠 "Is this an email" classified two incompatible ways — ✅ done (19B Item 1)

- Strict regex `_EMAIL_RE.fullmatch(...)` —
  `app/services/participants.py:32` (`is_email_identified`, the
  surface-reachability gate used by `deps.py:321`, `validation.py:192`,
  `routes_reviewer/_shared.py:165`).
- Cheap heuristic `"@" in value` —
  `app/services/csv_imports.py:577,607`, `app/services/reviewees.py:78`.

**Divergence:** `foo@bar` (no dotted domain) passes `"@" in value` but
fails `_EMAIL_RE.fullmatch`. A reviewee created/imported with such a
value is treated as email-shaped by CSV import yet flagged
`unreachable_for_results` and denied `/results` by the regex gate.

**Fix:** route both through one predicate
(`participants.is_email_identified` or a shared `looks_like_email`).

### S4 🟠 `_EMAIL_RE` regex literal duplicated five times — ✅ done (19B Item 1)

Identical `re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")` at
`participants.py:29`, `reviewers.py:37`, `observers.py:48`,
`reviewees.py:34`, `csv_imports.py:31`. The `participants.py:23-28`
comment already flags this drift risk. **Fix:** one module-level
constant (e.g. a small `app/services/_email.py`) imported everywhere —
folds naturally into the S2/S3 fix.

### S5 🟠 `_bulk_set_status` reimplemented four times — ✅ done (19B Item 1)

`reviewers.py:290`, `reviewees.py:326`, `observers.py:255`,
`relationships.py:726` are the same algorithm verbatim (normalise target
status → load session-scoped candidates ordered by id → raise
`*_OperationError("not_in_session")` on missing ids → compute `flipped` →
`invalidate_if_validated` → flush → `audit.write_event(snapshot(...))`),
parameterised only by model class, id-kwarg, and error type. Event-type
naming *is* consistent (`{entity}.bulk_inactivated` / `.bulk_reactivated`),
so the hazard is maintenance, not behaviour. **Fix:** one generic
`_bulk_set_status(db, *, model, rows_kwarg, error_cls, entity_noun, ...)`.

### S6 🟡 Status normalisation / active-predicate duplicated in five spots — ✅ done (19B Item 2)

`_normalised_status` (`reviewers.py:80`, `reviewees.py:85`,
`observers.py:83`) and `_normalised_rel_status` (`relationships.py:444`)
were the same `(status or "active").strip().lower()` + allowlist check
with per-module error types; `assignments/_shared.py:24` open-coded the
active test as `(row.status or "active") == "active"`. The allowlist was
in fact identical across all four (`{"active", "inactive"}`).

**Fixed:** new `app/services/roster_status.py` holds `ROSTER_STATUSES` +
`normalise_status(value, *, error_cls)` + `is_active(row)` (kept
dependency-light so the assignments package can import it without a
cycle). Each `_normalised_status` / `_normalised_rel_status` is now a
one-line delegation passing its own `*OperationError`; the relationships
CSV-parse check reuses `ROSTER_STATUSES`; `assignments/_shared._is_active`
delegates to `is_active`.

### S7 🟡 "Count responses for a field id" query duplicated three times — ✅ done (19B Item 2)

Identical `select(func.count(Response.id)).where(Response.response_field_id == field.id)`
at `instruments/_band2.py:521`, `_band2.py:577`,
`_response_fields.py:874` — all gating a destructive field change on "has
responses". **Fixed:** extracted `_response_count_for_field(db, field_id)`
into `instruments/_state.py` (the cross-slice plumbing home both slices
already import from); the three sites call it. (`session_lifecycle
.session_has_responses` correctly keeps its existence `.limit(1)` probe —
the field-level sites need the count for the error message.)

### S8 🟡 Stale docstring vs code — ✅ done (19B Item 1)

`app/services/reviewers.py:127-129` documented the duplicate check as a
"case-sensitive match", but `_email_taken` was case-*in*sensitive.
Doc-only; no second code path. **Fixed** alongside the S2 rework.

**Checked & clean:** roster single-update audit envelopes are consistent
(`reviewers.py:278` / `reviewees.py:311` / `observers.py:243` all use
`payload=audit.changes(...)` + `refs={...}`); operator permission gating
consistently routes through `permissions.user_can_view_session` — no
hand-rolled ownership logic found.

---

## B. Route / HTTP layer

Dominant conventions (the healthy baseline): POST-redirect-GET is
near-universally `status.HTTP_303_SEE_OTHER` (~110 sites); mutations are
POST-only with a verb-in-path + Form body + redirect; auth is applied
consistently (operator = router-level `require_operator` + per-handler
`require_session_operator`; reviewer = per-handler `require_*_in_session`
wrapper) — **no handler re-resolves identity inline.**

### R1 🟠 Data-shaper endpoints are a REST island in a POST-only app — ✅ done (19B Item 3, documented as exception)

**Resolution (chosen):** keep the AJAX/JSON sub-API as-is and **document
it as a blessed exception** rather than converting it to the
Form-and-redirect style. `spec/architecture.md` § "Route conventions"
now records the house style + this exception, and names it the pattern
new AJAX endpoints (R4) should converge onto.

`app/web/routes_operator/_extract_data.py` is the **only** module using
HTTP `PATCH`/`DELETE` app-wide (census: 118 POST, 54 GET, 1 PATCH, 1
DELETE). It uses a Pydantic body + JSON responses + REST status codes,
where every other resource mutation is POST + verb-in-path + Form +
redirect. Same conceptual action, two worlds:

- Delete a child: `DELETE .../extract-data/shapes/{id}` → `204`
  (`_extract_data.py:369-389`) vs
  `POST .../instruments/{id}/delete` → `303`
  (`_instruments.py:1026`).
- Create/update: `POST .../shapes` (`201`) + `PATCH .../shapes/{id}`
  (`200`) (`_extract_data.py:258-260, 310-315`) vs `POST .../update` +
  `Form(...)` + redirect everywhere else.

**Decision needed:** this is a deliberate AJAX/JSON sub-API and is
defensible — but it should be a *documented* exception (a spec note) so
the other AJAX endpoints (R4) converge onto it rather than each inventing
their own contract.

### R2 🟠 "Activate session" exposed at two URLs with divergent failure UX

Both flip `validated → ready` via `lifecycle.activate_session`:
`POST /sessions/{id}/activate` (`_session_home.py:511-538`) **raises**
`_lifecycle_error_response(exc)` (error page); the parallel
`POST /sessions/{id}/workflow/activate` (`_workflow.py:274`) **303-
redirects** back with `?super_status=failed&super_error=...` flash
params. Same transition, two error-UX models. Likewise `/activate` vs the
`/workflow/prepare|close|archive` family. **Fix:** route the Session-Home
button at the `/workflow/*` handler, or align the error surface.

### R3 🟠 Same operation-error class redisplayed three ways

`ReviewerOperationError` (+ reviewee/observer siblings) handled
inconsistently *within one file*: inline page re-render with
`edit_error=` (HTML 400) at `_setup_reviewers.py:294-312`, but
`raise HTTPException(400)` (generic error page) at
`_setup_reviewers.py:400-403,431,451` (the bulk/delete-all handlers). A
third style — 303 + `super_*` flash — exists in `_workflow.py:66` /
`_session_home.py:580`. A roster op that fails validation can re-render
inline, dump to a raw error page, or bounce with a flash depending only
on which button was pressed. **Fix:** one redisplay contract per surface
(inline re-render is richest and already used for create/update).

### R4 🟠 JSON AJAX bodies: hand-rolled validation vs Pydantic model

Raw `await request.json()` + manual `isinstance` → `HTTPException(400)`
at `_instruments_band2.py:66,109,219`, `_instruments.py:1155,1211`,
`_instruments_pagination.py:125`; vs Pydantic `payload: DataShapePayload`
(auto 422) at `_extract_data.py:260,315`. Same endpoint class, two
validation contracts / two error shapes. **Fix:** define request models
for the instrument AJAX bodies (converges with R1).

### R5 🟡 Bulk-action naming: `bulk-<verb>` vs `<verb>-selected`

Roster pages use `bulk-inactivate` / `bulk-reactivate`
(`_setup_reviewers.py:382,411`, `_setup_observers.py:338,369`,
`_setup_relationships.py:361,390`); the lobby uses
`archive-selected` / `unarchive-selected` / `delete-selected` /
`delete-archived-selected` (`_lobby.py:362,205,405,231`) — plus the
odd-one-out `bulk-tags` (`_lobby.py:152`) reaching for the roster prefix
in the lobby module. `bulk-<verb>` dominates 6:1. **Fix:** standardise on
`bulk-<verb>`.

### R6 🟡 Single-entity removal verb: `/delete` vs `/remove` vs `/delete-all`

`/instruments/{id}/delete`, `/sessions/{id}/delete` vs
`/sessions/{id}/owners/{uid}/remove` (`_session_home.py:649`),
`/sys-admin/users/{uid}/remove` (`_sys_admin.py:421`),
`/users/{uid}/remove-from-all-sessions` (`_sys_admin.py:406`) vs
wholesale `/reviewers/delete-all` etc. `delete` and `remove` used
interchangeably. **Latent rule worth making explicit:** `delete` =
destroy a row you own; `remove` = detach a relationship/membership.
(Note `users/{id}/remove` actually deletes the user — breaks even the
latent rule.)

### R7 🟡 Creation verb: `owners/add` vs `add-group`

Sub-resource `/sessions/{id}/owners/add` (`_session_home.py:597`) vs
verb-first `/instruments/add-group` / `add-new-model`
(`_instruments.py:953,977`). **Fix:** one of `{collection}/add` or
`{collection}/create`.

### R8–R11 🟡 Smaller route nits

- **R8** Two "edit session metadata" routes — `/lobby-edit`
  (`_lobby.py:263`) and `/config` (`_session_home.py:413`) — each
  re-implements the draft-only gate; consolidate the write.
- **R9** `setupinvite` is the only unhyphenated multi-word segment
  (`_setup_invite.py:55,89,139`); norm is hyphenated (`extract-data`,
  `delete-all`, `lobby-edit`). → `setup-invite`.
- **R10 — ✅ done (19B Item 3).** The two bare `status_code=303` literals
  (`_results.py`, `_rehydrate.py`) now use `status.HTTP_303_SEE_OTHER`.
- **R11 — ✅ done (19B Item 3).** The `/edit` legacy GET redirect moved
  from 301 to `status.HTTP_308_PERMANENT_REDIRECT`, matching the
  `/preview` shim.

**Intentional exception (flagged, not a defect):**
`/export/audit_log.csv` depends on `require_sys_admin` alone while its
sibling exports use `require_session_operator` — a deliberate Segment 16C
tightening, noted in-code. The `_instruments_band2.py` docstring that
claimed "204" but returned `200` is **✅ fixed (19B Item 3)**.

---

## C. Template / UX layer

Measured against the canonical vocabulary in `spec/ui_elements.md` §6
(Primary = bare `.btn`, Secondary = `.btn.secondary`, Destructive =
`.btn.destructive`, Outline-amber = `.btn.alert`) and
`spec/operator_button_audit.md`.

### U1 🔴 "Save" styled Primary on some surfaces, Secondary on others

Same "commit my edits" gesture, two stylings — and the split occurs
*within a single page*. **Primary:** `reviewer/_action_row.html:36`;
`session_reviewers.html:177`, `session_reviewees.html:182`,
`session_relationships.html:190`, `session_observers.html:142,234`;
`sessions_list.html:190`. **Secondary:** `instruments_index.html:397`;
`session_extract_data.html:600`; `partials/_quick_setup_card.html:192`
(`Submit`); `partials/_field_labels_editor.html:56` (`Save labels`).
Sharpest: on `session_reviewers.html`, `Save labels` is Secondary while
the row-edit `Save` on the same page is Primary. Spec says routine
submits are Secondary; Primary is a page's single main affirmative.
**Fix:** Secondary for all in-editor Save/Submit, applied uniformly.

### U2 🔴 Banner "Cancel" styled `.btn alert` vs `.btn secondary`

`spec/ui_elements.md` §5a mandates every redirect-back banner carry a
Cancel styled `.btn.alert`. Followed at `session_validate.html:36,63`;
violated (`.btn secondary`) at `partials/next_action_card.html:105` and
`instruments_index.html:350,353`. Two structurally identical
confirm-or-cancel banners, different Cancel colours. **Fix:** `.btn.alert`
for all banner Cancels.

### U3 🔴 Destructive-delete confirmation gated two incompatible ways

- **`required` checkbox only** (button never disabled) —
  `session_detail.html:467,474` (`Delete Data`) and `:483,491`
  (`Delete session`).
- **JS-enabled disabled button** (`disabled` until a `data-delete-confirm`
  checkbox flips it) — `session_reviewees.html:575-586`,
  `session_observers.html:744-753`, `session_reviewers.html`,
  `session_relationships.html:622`; `sessions_list.html:203,251` +
  `sessions_archived.html:153`. `reviewer/review_surface.html:533-542`
  uses **both**.

**Consequence:** the highest-stakes action in the app — `Delete session`
on Session Home — is the *least* gated (always-clickable, no disabled
state), while deleting a roster requires the checkbox to un-grey the
button. Confirm copy also diverges ("Yes, delete …" vs bare "Allow
delete"). **Fix:** one mechanism (disabled-until-checked is the more
visibly safe) + one confirm-label voice.

### U4 🟡 Dead/duplicate Primary token `class="btn primary"`

`.btn.primary` has **no CSS rule** — it renders identically to bare
`.btn`. Both spellings are live (`btn primary`: `reviewer/summary.html:25`,
`reviewer/collation.html:99`, `session_reviewees.html:182`, …; bare `btn`:
`reviewer/results.html:195`, `sessions_list.html:190`, …). Harmless today
but a live trap — adding a `.btn.primary` rule would silently restyle only
the `btn primary` buttons. **Fix:** drop the no-op `primary` token.

### U5 🟡 "Archive" styled Destructive one place, Outline-amber another

`next_action_card.html:354` (`Archive session`) = `.btn destructive`;
`sessions_list.html:198,247` (`Purge and archive` / `… all`) =
`.btn alert` (spec-reserved for lock-card recovery + banner Cancel).
Pick one role for archive.

### U6 🟡 Two class names for one Destructive style

`.btn.destructive` and `.btn.danger-solid` share one CSS rule
(`base.html:1630-1631`) — visually identical. `danger-solid` appears only
at `session_validate.html:43`, `next_action_card.html:101`. Collapse to
one class.

### U7 🟡 Filter-reset label: "Clear" / "Clear all" / "Clear filters"

"Clear" on the seven setup/list pages (`session_reviewers.html:134`, …);
"Clear all" on `sessions_list.html:29` / `sessions_archived.html:25`;
"Clear filters" on `sys_admin_session_audit_log.html:166`. One verb
phrase.

### U8 🟡 Abandon-edits verb: "Discard" (reviewer) vs "Cancel" (operator)

`reviewer/_action_row.html:33,39` label the abandon-input control
`Discard`; every operator inline editor labels the equivalent `Cancel`.

### U9–U10 🟡 Style nits

- **U9** `Delete` styled `.btn secondary` in the extract-data shaper
  (`session_extract_data.html:608,695,762`) where Delete is
  `.btn destructive` everywhere else (client-side shape/lens deletes, but
  the plain-Secondary makes a delete read as routine).
- **U10** Danger-zone `<h2 style="margin-top:0">` inline-style drift
  (`session_detail.html:457`, `session_observers.html:740`) vs bare `<h2>`
  elsewhere — move to a `.card.danger-zone h2` rule.

**Checked & clean:** breadcrumbs (all through `_partials/breadcrumb.html`,
no hand-rolled HTML); `.page-grid` / `.bottom-grid` usage; lock-card
"Revert to draft" (`.btn alert` on all five setup pages + Instruments);
the roster danger-zone delete-all pattern (uniform across the four roster
pages — the U3 divergence is against `session_detail` and the lobby
expander, not among these four). Note `spec/operator_button_audit.md` is
stale in one spot (lists a "Pause Session" button that is now "Revert to
draft") — doc refresh only.

---

## D. View-adapter / data-shaping layer

### V1 🔴 `instrument_heading` reimplemented inline; fallback diverges — *verified*

Canonical: `app/web/views/_instruments.py:97`
`instrument_heading(instrument, position, total_count)`. For
`total_count == 1` with no short_label it falls back to **`description`**
(then `None`). Used by the reviewer surface and observer collation
(`_observer_collation.py:157`).

Two inline reimplementations that do **not** call the helper and are
byte-identical to each other:
`_reviewee_results.py:547-553` and `_reviewer_summary.py:417-423`. For
the single-instrument, no-short_label case they render **`instrument.name`**,
not `description`.

**Divergence:** for the *same instrument*, the reviewer surface + observer
collation show one heading while the reviewee `/results` page + reviewer
post-submit summary show a different one — even though both inline copies'
comments claim to "mirror the reviewer surface" (`_reviewer_summary.py:410`
even names `instrument_heading` as the thing it mirrors, then
re-implements it). **Fix:** both call `instrument_heading(...).title`, or
extract a `heading_title_only(...)` in `_instruments.py`.

### V2 🔴 Reviewer-progress pill rendered inconsistently in 4 templates

The *value* is well-sourced (`ReviewerSessionState.pill_state`,
`responses/_core.py:735,833`, via `monitoring.ReviewerProgress.pill_state`).
The *presentation* (state → pill class + text) is hand-rolled per
template and disagrees:

- `reviewer/dashboard.html:135-143` — `in progress` → `pill-warning`
- `operator/session_invitations.html:138-141` — `in progress` →
  `pill-empty` (grey; no distinction from not-started)
- `operator/session_invitations_reviewer_detail.html:64-69` —
  `in progress` → `pill-empty`
- `reviewer/review_surface.html:98` — `in_progress` → `pill-warning`

Two problems: **colour drift** (same "in progress" state amber on the
dashboard, grey on the operator surfaces — no shared macro), and a
**vocabulary split** (surface uses underscore `in_progress` /
`not_started` / `complete`; monitoring uses space-separated `in progress`
/ `not started`). Related: the Manage-Invitations filter dropdown
title-cases via `_filters.py:41-46` while the table cell prints raw
`row.review_progress_state` — same row, two spellings. **Fix:** one Jinja
macro `progress_pill(state)` (or a view helper returning `(css, label)`)
+ one canonical enum spelling (or an explicit normaliser).

### V3 🟠 User display-label hand-rolled 7+ times, with a `"—"` variant

`display_name or email`: `_lobby.py:60`, `sessions_list.html:97`,
`sessions_archived.html:85`, `sys_admin_sessions.html:42`,
`session_detail.html:274`, `reviewer/_top_bar.html:23`, `base.html:2893`.
`display_name or "—"` (drops email): `sys_admin_users.html:179`,
`session_detail.html:227,248`, `session_observers.html:350`. Same "who is
this user" label resolves to email on some pages, a bare em-dash on
others. **Fix:** a `User.display_label` property returning
`display_name or email`, plus a deliberately-named dash variant.

### V4 🟠 Instrument friendly-label fallback reimplemented ~8 places, four tails

Beyond the three existing helpers (`_state.py:62` `_instrument_label`,
`validation.py:275`, `extracts/by_instrument_extract.py:65`), hand-rolled
sites bypass all of them with **four distinct tails**:

- `short_label or name`: `_assignments.py:204`,
  `_reviewee_results.py:549`, `_reviewer_summary.py:419`,
  `extracts/responses_import.py:272,279,300`
- `short_label or name or id`: `visibility_policies.py:383`
- `short_label or name or f"Instrument {id}"`:
  `_surface/_context.py:263-267`
- `short_label or f"Instrument_{position}"` (drops name):
  `extracts/entity_metadata_extract.py:199-200`

Cross-surface labels for the same blank-`short_label` instrument won't
match. **Fix:** promote one helper to a shared module both services and
views import; layer `instrument_heading` on top; keep the CSV-safe
`Instrument_{position}` variant explicitly named. (Folds together with S1
— the same underlying `short_label`-fallback question.)

### V5 🟡 Derived-state predicates duplicated between service and view

`is_at_risk`: `monitoring.py:174` and re-declared on the view row
`_responses.py:38`. `is_incomplete`: `monitoring.py:57` and
`_invitations.py:54`. If the bucket set changes, both must move in
lockstep. **Fix:** view dataclass delegates to the service predicate.

### V6 🟡 Ad-hoc pluralization inline

`_setup.py:151` (`draft`/`drafts` — but `submitted` never pluralised) and
`responses/_core.py:547` (`response`/`responses`) each reinvent
count-noun agreement. A shared `pluralize(n, singular, plural)` helper.

**Checked & clean:** sorting (`_sort.py`) / filtering (`_filters.py`) are
well-centralised (all through `_matches_search` +
`_extract_filter_label_tail`; no inline re-sort found); date/time
formatting single-sourced in `services/date_formatting.py` (the one
un-zoned call, `_audit_log.py:108`, is intentional/documented UTC
forensic surface); mode strings (Raw/Anonymized/Summarized) centralised
in `visibility_policies.py`; coverage thresholds single-sourced
(`AT_RISK_THRESHOLDS`); `summarize_field` is the single aggregation impl
(observer collation imports it rather than re-deriving).

---

## Recommended remediation order

Grouped so each PR is a coherent, reviewable slice (per `CLAUDE.md`).

1. **The instrument-label family (S1 + V4 + V1).** One shared
   `instrument_label` helper in a module both services and views import;
   settle the `short_label` fallback tail once; have `validation.py`,
   `_reviewee_results.py`, `_reviewer_summary.py`, and the ~8 hand-rolled
   sites call it; `instrument_heading` layers position on top. Fixes the
   one user-visible name mismatch (S1) and the heading divergence (V1) in
   the same slice.
2. **Email identity normalisation (S2 + S3 + S4).** One
   `app/services/_email.py` with `EMAIL_RE`, `normalize_email`, and
   `looks_like_email`; apply at both store-time and compare-time; delete
   the five regex copies and the `"@" in value` heuristics. Auth-adjacent
   correctness — worth a careful test pass.
3. **The progress-pill macro (V2).** One `progress_pill(state)` partial
   returning `(css, label)`, one canonical enum spelling; repoint the four
   templates + the invitations filter/cell.
4. **UI vocabulary sweep (U1–U8).** Largely mechanical, spec-backed:
   Save→Secondary, banner Cancel→`.btn alert`, unify the delete-confirm
   mechanism (U3 is the one with real safety weight — do it deliberately),
   drop the no-op `primary` token, one "Clear" label, one abandon-edits
   verb. Refresh `spec/operator_button_audit.md` in the same PR.
5. **Route-convention sweep (R1–R11).** Two decisions to settle *first*:
   (a) is the extract-data REST/JSON style a blessed AJAX exception, or
   should it/the instrument AJAX endpoints (R1+R4) converge on one
   contract? (b) `delete` vs `remove` verb rule (R6). Then the mechanical
   nits (R9/R10/R11) and the two-URL consolidations (R2/R8).
6. **Service dedup (S5–S7) — ✅ done (19B Items 1–2).** Plus the view
   dedup tail (V5–V6: delegated predicates, a `pluralize` helper) still
   open — lowest risk, do when touching those files anyway.

**Two design decisions gate the route work and should be answered before
PR 5:** the AJAX-contract question (R1) and the delete/remove verb rule
(R6). Everything else is convergence onto an already-dominant convention.
