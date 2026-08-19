# Consistency audit — one functionality, many call paths

> **Archived 2026-08-19 — fully remediated.** Every finding (Service
> S1–S8, Route R1–R11, Template/UX U1–U10, View-adapter V1–V6) was
> resolved under **Segment 19B**
> (`guide/archive/segment_19B_consistency.md`), across 15 items / PRs
> #1987–#2003. Kept as the per-finding record. Two findings closed by
> decision rather than code: **R3** (deferred — see
> `guide/deferred_consolidated.md` Part C) and **R1 / R7** (documented as
> justified conventions in `spec/architecture.md`).

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

Tracked as **Segment 19B** (`guide/archive/segment_19B_consistency.md`).

- **✅ Service column complete (S1–S8)** — shipped 2026-08-19.
  - **Item 1** (PR #1987): S1 (one instrument label), S2/S3/S4 (the
    `email_identity` module), S5 (shared `bulk_set_status`), S8
    (docstring fix).
  - **Item 2**: S6 (shared `roster_status` — `ROSTER_STATUSES` /
    `normalise_status` / `is_active`), S7 (shared
    `_response_count_for_field`).
- **✅ Route sweep complete (R1–R11)** — shipped 2026-08-19.
  - **Item 3** (this slice): R1 (documented the extract-data AJAX
    sub-API as a blessed exception in `spec/architecture.md`), R10
    (bare `303` → `status.HTTP_303_SEE_OTHER`), R11 (`/edit` legacy
    redirect 301 → 308), + the `_instruments_band2.py` `204`/`200`
    docstring fix.
  - **Item 4**: the URL-verb renames — R5 (`bulk-<verb>`), R6
    (`delete`=destroy / `remove`=detach; the sys-admin user route
    renamed `/remove` → `/delete`), R9 (`setupinvite` → `setup-invite`),
    and R7 (documented as a justified divergence). The naming rules are
    recorded in `spec/architecture.md` § "Route conventions".
  - **Item 5**: R8 (the duplicated session-deadline parse block →
    shared `parse_session_deadline` helper; the two routes' differing
    draft-gates are intentional and kept).
  - **Item 6**: R2 (aligned `/activate` failure to the Workflow-card
    flash via a shared `_redirect_url`) + R4 (the six hand-rolled AJAX
    parse blocks → shared `require_json_object`, keeping 400).
  - **Item 7**: R3 **resolved by decision** — accepted as-is + documented
    (the forged-only bulk-error redisplay keeps the error page; inline
    re-render is the form-error contract). The page-level-banner build is
    logged in `guide/deferred_consolidated.md` (Part C). **This closes
    the whole route sweep, R1–R11.**
- **✅ Template/UX sweep complete (U1–U10)** — shipped 2026-08-19.
  - **Item 8**: U1 (routine in-editor Save → Secondary; reviewer-surface
    Submit stays Primary), U2 (banner Cancels → `.btn alert`), U4
    (dropped the no-op `.btn primary` token).
  - **Item 9**: U5 + U6 — `.btn.danger-solid` became a **filled amber**
    style (distinct from outline-red `.destructive` and outline-amber
    `.alert`); archive/purge actions now use it. `spec/ui_elements.md`
    refreshed.
  - **Item 10**: U3 — every destructive submit is now
    **disabled-until-checked** (the `session_detail` Delete Data / Delete
    session buttons converted to the app-wide `data-delete-confirm`
    standard; the always-clickable highest-stakes gap is closed), and the
    confirm-label voice is unified to "Yes, delete …".
  - **Item 11**: U7 (filter-reset labels → "Clear") + U8 (reviewer
    abandon-edits verb "Discard" → "Cancel").
  - **Item 12**: U9 (extract-data shaper "Delete shape" buttons →
    `.btn destructive`) + U10 (dropped the redundant danger-zone `<h2>`
    inline margin — the `.card h2` rule already handled it).
- **✅ View-adapter dedup complete (V1–V6)** — shipped 2026-08-19.
  - **Item 13**: V1 (the two inline `instrument_heading` reimpls → the
    canonical helper) + V4 (the hand-rolled instrument friendly-label
    sites → the canonical `_instrument_label`; the CSV-safe positioned
    variants kept as named helpers).
  - **Item 14**: V2 — shared `views.progress_pill(state) → (css, label)`
    helper (Jinja global on both template instances); the four
    hand-rolled progress pills now render one canonical colour semantic
    (blue/amber/green) + one enum spelling.
  - **Item 15**: V3 (`User.display_label` property), V5 (the
    `monitoring.is_at_risk_state` / `is_incomplete_state` predicates,
    delegated by all four dataclasses), V6 (`services.text.pluralize`).

**✅ Audit fully remediated — every finding (S1–S8, R1–R11, U1–U10,
V1–V6) is resolved.** Two findings by deliberate decision rather than
code change: **R3** (accepted; page-banner build deferred to
`deferred_consolidated.md`) and **R1 / R7** (documented as justified
conventions in `spec/architecture.md`).

**Scorecard:** Service **S1–S8 ✅** · Route **R1–R11 ✅** · UI **U1–U10 ✅**
· View **V1–V6 ✅** — **complete**.

---

## Severity-ranked master list

| # | Sev | Seam | One line |
|---|-----|------|----------|
| ✅ **S1** | 🔴 High | Service | `_instrument_label` has two implementations with **different fallbacks** — same instrument shows two different names |
| ✅ **V1** | 🔴 High | View | `instrument_heading` reimplemented inline in two view modules; single-instrument fallback diverges (`name` vs `description`) |
| ✅ **V2** | 🔴 High | View/UX | Reviewer-progress pill state → (label, colour) hand-rolled in 4 templates; same state coloured differently; two enum spellings |
| ✅ **U1** | 🔴 High | UX | "Save" styled Primary on some surfaces, Secondary on others — split even within one page |
| ✅ **U2** | 🔴 High | UX | Banner "Cancel" styled `.btn alert` (per spec) vs `.btn secondary` |
| ✅ **U3** | 🔴 High | UX | Destructive-delete confirmation gated two incompatible ways; the highest-stakes action is the *least* gated |
| ✅ **S2** | 🟠 Med | Service | Roster email matching uses three case-folding conventions (`casefold` / SQL `lower` / `lower`) — write-time vs gate-time can disagree |
| ✅ **S3** | 🟠 Med | Service | "Is this an email" classified two incompatible ways (strict regex vs `"@" in value`) |
| ✅ **R1** | 🟠 Med | Route | Data-shaper endpoints are a REST/PATCH/DELETE/JSON island in a POST-only app *(documented as a blessed exception)* |
| ✅ **R2** | 🟠 Med | Route | "Activate session" exposed at two URLs with divergent failure UX |
| ✅ **R3** | 🟠 Med | Route | Same operation-error class redisplayed three ways (inline re-render / raw error page / flash redirect) *(accepted as-is; page-banner build deferred)* |
| ✅ **R4** | 🟠 Med | Route | JSON AJAX bodies: hand-rolled `request.json()` validation vs Pydantic model |
| ✅ **V3** | 🟠 Med | View | User display-label (`display_name or email`) hand-rolled 7+ times, with a `"—"`-fallback variant |
| ✅ **V4** | 🟠 Med | View/Service | Instrument friendly-label fallback reimplemented ~8 places with **four different tails** |
| ✅ **S4** | 🟠 Med | Service | `_EMAIL_RE` regex literal duplicated five times |
| ✅ **S5** | 🟠 Med | Service | `_bulk_set_status` reimplemented four times (verbatim algorithm) |
| ✅ **R5** | 🟡 Low | Route | Bulk-action naming: `bulk-<verb>` vs `<verb>-selected` |
| ✅ **R6** | 🟡 Low | Route | Single-entity removal verb: `/delete` vs `/remove` vs `/delete-all` |
| ✅ **R7** | 🟡 Low | Route | Creation verb: `owners/add` (sub-resource) vs `add-group` (verb-first) |
| ✅ **U4** | 🟡 Low | UX | Dead/duplicate Primary token `class="btn primary"` vs `class="btn"` |
| ✅ **U5** | 🟡 Low | UX | "Archive" styled Destructive one place, Outline-amber another |
| ✅ **U6** | 🟡 Low | UX | Two class names for one identical Destructive style (`.destructive` / `.danger-solid`) |
| ✅ **U7** | 🟡 Low | UX | Filter-reset label: "Clear" / "Clear all" / "Clear filters" |
| ✅ **U8** | 🟡 Low | UX | Abandon-edits verb: "Discard" (reviewer) vs "Cancel" (operator) |
| ✅ **S6** | 🟡 Low | Service | Status normalization / active-predicate duplicated in five spots |
| ✅ **S7** | 🟡 Low | Service | "Count responses for a field id" query duplicated three times |
| ✅ **V5** | 🟡 Low | View | `is_at_risk` / `is_incomplete` predicates duplicated between service and view dataclasses |
| ✅ **V6** | 🟡 Low | View | Ad-hoc pluralization inline in multiple modules; no `pluralize()` helper |
| ✅ others | 🟡 Low | Route/UX/Service | R8–R11, S8, U9, U10 — all done; naming/style nits, listed in-section |

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

### R2 🟠 "Activate session" exposed at two URLs with divergent failure UX — ✅ done (19B Item 6, aligned)

Both flip `validated → ready` via `lifecycle.activate_session`:
`POST /sessions/{id}/activate` (Validate-page commit) **raised**
`_lifecycle_error_response(exc)` (error page); the parallel
`POST /sessions/{id}/workflow/activate` (Workflow-card button)
**303-redirects** with a `super_*` flash. They can't merge — the
Validate-page activate is the post-warnings-acknowledge commit; routing
it at `/workflow/activate` would re-trigger the warnings detour.

**Resolution (chosen: align the error surface):** `_redirect_url` moved
from `_workflow.py` to `_shared.py`; `session_activate`'s
`LifecycleError` handler now redirects to the Session Home flash
(`super_status=failed&super_button=activate&super_step=activate`)
instead of raising an error page, so an activation failure looks the
same from either button. (`/revert` + the instrument edit-lock keep the
error-page response — a separate concern from activate.)

### R3 🟠 Same operation-error class redisplayed three ways — ✅ resolved by decision (19B Item 7, accepted as-is)

`ReviewerOperationError` (+ siblings): inline page re-render with
`edit_error=` for row create/edit, but `raise HTTPException(400)`
(generic error page) for the bulk / delete-all handlers.

**Resolution (chosen: accept + document + defer the build).** Converting
the bulk / delete-all handlers to inline re-render would need a **new
page-level error banner across all four setup templates** — the existing
`edit_error` banner renders only inside `{% if edit_mode %}` (the
add/edit form), so a bulk error has nowhere to display. And every error
path in scope (`not_in_session` / `invalid_status` / missing-`confirm`)
is **unreachable through the UI** — the checkbox UI never produces them;
only a forged/buggy client can. So the four-template build is deferred:
`spec/architecture.md` § "Route conventions" now records inline
re-render as the **form-error** contract and the forged-only bulk guards
as intentionally using the error page. The banner build is logged in
`guide/deferred_consolidated.md` (Part C) with its lift trigger — a bulk
action that can *legitimately* partially fail.

### R4 🟠 JSON AJAX bodies: hand-rolled validation vs Pydantic model — ✅ done (19B Item 6, shared helper)

Raw `await request.json()` + manual `isinstance` → `HTTPException(400)`
was copied six times across `_instruments_band2.py` (×3),
`_instruments.py` (×2), and `_instruments_pagination.py` (×1); vs the
Pydantic `DataShapePayload` in `_extract_data.py`.

**Resolution (chosen: shared parse helper, not full Pydantic):** the six
copies now call `require_json_object(request, label=...)` in `_shared.py`,
which keeps the hand-rolled **400 + tailored message** the client JS
expects (rather than a Pydantic 422 for these internal-JS-driven
endpoints). The extract-data sub-API remains the blessed Pydantic
pattern for *new* endpoints — recorded in the R1 note in
`spec/architecture.md`.

### R5 🟡 Bulk-action naming: `bulk-<verb>` vs `<verb>-selected` — ✅ done (19B Item 4)

Roster pages used `bulk-inactivate` / `bulk-reactivate`; the lobby used
`archive-selected` / `unarchive-selected` / `delete-selected` /
`delete-archived-selected`. **Fixed:** the four lobby routes renamed to
`bulk-archive` / `bulk-unarchive` / `bulk-delete` / `bulk-delete-archived`
(joining `bulk-tags`), across `_lobby.py` + the three templates + the
three test files. The `bulk-<verb>` convention is recorded in
`spec/architecture.md` § "Route conventions".

### R6 🟡 Single-entity removal verb: `/delete` vs `/remove` vs `/delete-all` — ✅ done (19B Item 4)

The rule (maintainer-approved): **`delete`** destroys a row you own;
**`remove`** detaches a relationship/membership. Under it, the only
offender was `/sys-admin/users/{uid}/remove`, which *deletes* the user —
**renamed to `/sys-admin/users/{uid}/delete`** (the template's JS key was
already "delete"). `owners/{uid}/remove` and
`users/{uid}/remove-from-all-sessions` are genuine detaches and keep
`remove`. Rule documented in `spec/architecture.md`.

### R7 🟡 Creation verb: `owners/add` vs `add-group` — ✅ done (19B Item 4, documented divergence)

Sub-resource `/sessions/{id}/owners/add` vs verb-first
`/instruments/add-group` / `add-new-model`. **Resolution:** neither
`{collection}/add` nor `{collection}/create` fits both — the instruments
collection has **two** creation kinds (group vs new-model), so verb-first
`add-<kind>` names the kind without an artificial `groups/` /
`models/` sub-collection, while single-kind `owners/add` stays
sub-resource. Documented as a deliberate convention in
`spec/architecture.md` rather than churning URLs to make one side worse.

### R8–R11 🟡 Smaller route nits

- **R8 — ✅ done (19B Item 5).** The two "edit session metadata" routes
  (`/lobby-edit`, `/config`) duplicated the deadline parse-and-validate
  block; it moved to a shared `parse_session_deadline` helper in
  `_shared.py`. Their *gate* semantics deliberately differ (the lobby
  expander silently ignores name/code/deadline off-draft; the config
  card hard-requires an editable session) and their field scopes differ,
  so only the parse is shared, not the gate — noted in the helper.
- **R9 — ✅ done (19B Item 4).** `setupinvite` was the only unhyphenated
  multi-word URL segment; the three routes are now `setup-invite` /
  `setup-invite/reset`, with all URL references updated (routes, the
  `_setup.py` manage-url, two chrome partials + the page template, and
  three test files). Internal identifiers (the `setupinvite_*` handler
  names, the `session_setupinvite.html` filename, the `setupinvite-*`
  DOM ids) are unchanged — only the URL moved.
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

### U1 🔴 "Save" styled Primary on some surfaces, Secondary on others — ✅ done (19B Item 8)

Same "commit my edits" gesture, two stylings — the split occurred even
within a single page. **Fixed:** every routine in-editor Save is now
Secondary — the operator row-edit Saves (`session_reviewers` /
`session_reviewees` / `session_relationships` / `session_observers`), the
reviewer-surface `Save`, and the sessions-lobby expander `Save`. The
reviewer-surface **`Submit`** stays Primary as the page's single main
affirmative (the whole point of the surface), giving a clear
Save/Discard-secondary → Submit-primary hierarchy.

### U2 🔴 Banner "Cancel" styled `.btn alert` vs `.btn secondary` — ✅ done (19B Item 8)

Every redirect-back banner should carry a Cancel styled `.btn.alert`.
The two violators (`.btn secondary`) — `partials/next_action_card.html`
(the Regenerate-&-prepare confirm banner) and `instruments_index.html`
(both branches of the `rf-save-error` banner) — are now `.btn alert`,
matching `session_validate.html`.

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
on Session Home — was the *least* gated (always-clickable, no disabled
state), while deleting a roster required the checkbox to un-grey the
button. Confirm copy also diverged ("Yes, delete …" vs bare "Allow
delete").

**✅ done (19B Item 10).** Both `session_detail.html` danger-zone buttons
(`Delete Data`, `Delete session`) now use the app-wide
`data-delete-confirm` / `data-delete-btn` **disabled-until-checked**
standard — the button ships `disabled aria-disabled="true"` and the
checkbox enables it (the `Delete session` `is_ready` lock still holds:
the checkbox is `disabled` when activated, so the button stays disabled
via the same JS). Every delete-confirm is now disabled-until-checked. The
confirm-label voice is unified to the affirmative **"Yes, delete …"** —
the sessions-lobby / archived expanders' bare "Allow delete" → compact
"Yes, delete". *(The expanders keep their own per-node script — a **list**
of destructive rows can't use the app-wide single-`querySelector`
pairing; the disabled-until-checked behaviour + voice are identical.)*
Documented in `spec/ui_elements.md`. Best eyeballed on the dev slot.

### U4 🟡 Dead/duplicate Primary token `class="btn primary"` — ✅ done (19B Item 8)

`.btn.primary` had **no CSS rule** — it rendered identically to bare
`.btn`. **Fixed:** the no-op `primary` token is gone everywhere — the
operator row-edit Saves became `.btn secondary` (U1) and the two reviewer
Download buttons (`reviewer/summary.html`, `reviewer/collation.html`)
became bare `.btn` (visual no-op). No `btn primary` remains in the
templates.

### U5 🟡 "Archive" styled Destructive one place, Outline-amber another — ✅ done (19B Item 9, harmonized to amber danger-solid)

`Archive session` was `.btn destructive` (outline red) in the Workflow
card, `Purge and archive` was `.btn alert` (outline amber) in the lobby.
**Fixed:** all archive/purge actions now use `.btn danger-solid` — the
filled amber style (see U6).

### U6 🟡 Two class names for one Destructive style — ✅ done (19B Item 9, differentiated)

`.btn.destructive` and `.btn.danger-solid` were an identical outline-red
rule. **Resolution (maintainer-chosen: differentiate, not collapse):**
`.btn.danger-solid` is now a **filled amber** style for
serious-but-recoverable actions (purge-and-archive, Archive session, and
the Acknowledge-and-activate confirm — which already used
`danger-solid`), while `.btn.destructive` stays outline-red for
irreversible deletes. The two classes are now distinct, non-redundant
roles. Recorded in `spec/ui_elements.md` (button-vocab table + hover +
confirm-banner notes). Best eyeballed on the dev slot.

### U7 🟡 Filter-reset label: "Clear" / "Clear all" / "Clear filters" — ✅ done (19B Item 11)

The seven setup/list filter resets already said "Clear". **Fixed:** the
two "Clear all" (`sessions_list`, `sessions_archived`) and the "Clear
filters" (`sys_admin_session_audit_log`) filter-reset controls → **"Clear"**.
(The destructive "Clear all settings" / "Clear all responses" headings
are separate actions, not filter resets — left alone.)

### U8 🟡 Abandon-edits verb: "Discard" (reviewer) vs "Cancel" (operator) — ✅ done (19B Item 11)

**Fixed:** the reviewer-surface abandon-input control (`_action_row.html`)
relabelled `Discard` → **`Cancel`**, matching every operator inline
editor. The `data-rs-discard` JS hook attribute is unchanged (internal).

### U9–U10 🟡 Style nits — ✅ done (19B Item 12)

- **U9 — ✅ done.** The three `data-shape-delete` "Delete shape" buttons in
  the extract-data shaper were `.btn secondary`, reading as routine. They
  hit the persisted `DELETE .../shapes/{id}` endpoint, so they're now
  `.btn destructive` (outline red), matching the app-wide "Delete = red"
  convention — a single red control among the Secondary shape-editor
  cluster (Save / Edit / Cancel / +Shape) that signals "this one
  destroys".
- **U10 — ✅ done.** The two danger-zone `<h2 style="margin-top: 0;">`
  inline styles (`session_detail`, `session_observers`) were **redundant**
  — the ui-v2 `.card h2 { margin: 0 … }` rule already zeroes the top
  margin. Dropped both; all five danger-zone headings are now bare `<h2>`
  and consistent (no visual change).

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

### V1 🔴 `instrument_heading` reimplemented inline; fallback diverges — *verified* — ✅ done (19B Item 13)

**Fixed:** `_reviewee_results.py` and `_reviewer_summary.py` now call the
canonical `instrument_heading(...).title` (the same one the reviewer
surface + observer collation use) instead of the byte-identical inline
copy, so the same instrument reads identically across every reader
surface. When the reviewer-facing title is empty (single-instrument, no
short_label, no description) they fall back to the canonical operator
label `_instrument_label` (`Instrument_{id}`) — never the internal
`name`. (Original finding below.)

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

### V2 🔴 Reviewer-progress pill rendered inconsistently in 4 templates — ✅ done (19B Item 14)

**Fixed:** new shared `views.progress_pill(state) → (css, label)` helper
(`_progress.py`), registered as a Jinja global on both the operator and
reviewer template instances. All four templates (`reviewer/dashboard`,
`operator/session_invitations`, `…_reviewer_detail`,
`reviewer/review_surface`) now render `<span class="pill {{ p.css }}">`
from it. One canonical colour semantic — **blue = not started, amber =
in progress, green = submitted/complete** — closes the drift (was:
"submitted" blue on operator invitations, "not started" amber on the
surface). The helper normalises **both enum spellings** (underscore
`in_progress` and space `in progress`), closing the vocabulary split.
The page-level `complete` state keeps its own label (distinct from
`submitted`). Best eyeballed on the dev slot. (Original finding below.)

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

### V3 🟠 User display-label hand-rolled 7+ times, with a `"—"` variant — ✅ done (19B Item 15)

**Fixed:** new `User.display_label` property (`display_name or email`,
the always-present identity column). The seven email-fallback User sites
(`_lobby.py`, `sessions_list` / `sessions_archived` /
`sys_admin_sessions` creator pills, `session_detail` owner-candidate
option, the two "Signed in as" chrome bars) now use it. The
`display_name or "—"` variant (name-only, email shown in an adjacent
column) stays inline — the deliberately-named dash form. The observer
sites are a separate model (`Observer`), left as-is. (Original finding
below.)

`display_name or email`: `_lobby.py:60`, `sessions_list.html:97`,
`sessions_archived.html:85`, `sys_admin_sessions.html:42`,
`session_detail.html:274`, `reviewer/_top_bar.html:23`, `base.html:2893`.
`display_name or "—"` (drops email): `sys_admin_users.html:179`,
`session_detail.html:227,248`, `session_observers.html:350`. Same "who is
this user" label resolves to email on some pages, a bare em-dash on
others. **Fix:** a `User.display_label` property returning
`display_name or email`, plus a deliberately-named dash variant.

### V4 🟠 Instrument friendly-label fallback reimplemented ~8 places, four tails — ✅ done (19B Item 13)

**Fixed:** the hand-rolled `short_label or name …` display/error labels
now route through the canonical `instruments._instrument_label`
(`short_label or Instrument_{id}`, the S1 home) — `_assignments.py`,
`visibility_policies.py`, `_surface/_context.py` (the dropped-field
label), `extracts/responses_import.py` (the two match-error messages);
the two view files were handled by V1. The internal `name` no longer
surfaces anywhere. The **CSV-safe positioned variants** stay as their own
named helpers (`entity_metadata_extract._instrument_short_or_fallback`,
`by_instrument_extract.fallback_instrument_label`) — the deliberately
different `Instrument_{position}` form. (Original finding below.)

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

### V5 🟡 Derived-state predicates duplicated between service and view — ✅ done (19B Item 15)

**Fixed:** the bucket-set logic moved to two module-level predicates in
`monitoring.py` — `is_at_risk_state(state)` and `is_incomplete_state(state)`.
All four properties (the two `monitoring` dataclasses + the
`_responses` / `_invitations` view rows, which carry the same state
under a different field name) now delegate to them, so a bucket change
is a single edit. (Original finding below.)

`is_at_risk`: `monitoring.py:174` and re-declared on the view row
`_responses.py:38`. `is_incomplete`: `monitoring.py:57` and
`_invitations.py:54`. If the bucket set changes, both must move in
lockstep. **Fix:** view dataclass delegates to the service predicate.

### V6 🟡 Ad-hoc pluralization inline — ✅ done (19B Item 15)

**Fixed:** new `app/services/text.py::pluralize(count, singular,
plural=None)`. `_setup.py`'s draft/drafts and the five
`response{'' if n==1 else 's'}` / submission idioms in
`responses/_core.py` now call it.

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
