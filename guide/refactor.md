# Refactor Plan — Split `routes_operator.py` by feature area

**Project:** Review Robin Web
**Status:** Stub — not yet started
**Sizing:** 1 package-conversion PR + 10 mechanical slice PRs

---

## 1. Why now

`app/web/routes_operator.py` has grown past 4,400 lines. The file
already has clear feature-area seams that map almost 1:1 to the
operator chrome's nav structure, so the split is mostly mechanical
rather than architectural.

The trigger is **Segment 13C (enhanced instruments)**: 13C will pile
new code onto the already-largest slice inside the file. Splitting
before 13C means 13C lands cleanly into a focused, single-purpose
module; splitting after means a bigger, riskier split with a fatter
diff to review.

Segment 12A (export + import) is also still planning-only at the
time of writing, so the split lands cleanly ahead of 12A's new
routes too — those can target organised files from day one rather
than fattening the monolith further.

## 2. Non-goals

- **No behavior change.** Every URL path, dependency, audit event,
  and template call site stays identical. This is a pure
  relocation.
- **No service-layer changes.** Services and view-shape adapters
  are out of scope; the seam being touched is strictly the route
  layer.
- **No test rewrites.** Integration tests already exercise routes
  via URL paths (not symbol imports), so they should pass unchanged
  through every slice PR. Symbol-level imports (rare) are updated
  in-place when encountered.
- **No new abstractions.** Don't introduce a base class, a route
  registry, or a "plugin" pattern. The split is one big file
  becoming several smaller files; nothing more.

## 3. Approach

Convert `app/web/routes_operator.py` into a package
(`app/web/routes_operator/__init__.py`) that re-exports a single
assembled `router`. App registration in `app/main.py` does not
change. The public import surface
(`from app.web.routes_operator import router`) is preserved —
this is the only external import site (verified: only `app/main.py`
imports the symbol; no test imports any internal symbol).

Slices are organised by feature area, matching the operator
chrome's tab structure (Setup / Operations / Settings) plus the
session-lifecycle and lobby boundaries that already exist
implicitly in the file.

### Sub-module pattern (pin once, reuse in every slice)

Each sub-module under `app/web/routes_operator/` declares an
unprefixed router:

```python
router = APIRouter()
```

and writes full paths starting with `/sessions/{session_id}/...`
(or `/sessions`, `/settings`, etc.). The package
`__init__.py` owns the operator-wide prefix and mounts every
sub-module:

```python
router = APIRouter(prefix="/operator", tags=["operator"])
router.include_router(_settings.router)
router.include_router(_lobby.router)
# …one line per sub-module
```

This avoids per-area prefix decisions in each slice PR and keeps
the cross-area URL families that already exist (Assignments and
Rule Builder both live under `/sessions/{id}/assignments/...`)
working without any router gymnastics.

### Shared `Jinja2Templates` instance

Lines 51–61 of today's file instantiate one `Jinja2Templates`
and register three operator-only Jinja entries
(`display_field_label`, `is_locked_display_source`,
`lifecycle_label`). After the split, every sub-module needs the
same configured instance. Put the single `_templates` in the new
`_shared.py` and import it from each sub-module — one
registration point, zero risk of drift across 10 files. (The peer
modules `routes_about.py` / `routes_auth.py` / `routes_reviewer.py`
each build their own `Jinja2Templates`, but they don't share
custom globals the way operator does, so the duplication
wouldn't cost anything there.)

## 4. PR ladder

PRs land in this order; smallest and most self-contained first to
de-risk the package conversion before tackling the heaviest slices.

1. **Package conversion + shared-helpers PR.** Turn
   `routes_operator.py` into a package directory
   (`app/web/routes_operator/__init__.py`) and lift the genuinely
   cross-area helpers into a new `_shared.py` inside the package.
   Both moves are pure mechanical relocation; landing them
   together avoids one cycle of import-path churn and removes the
   "what does sibling mean now?" naming question. Existing route
   registration in `app/main.py` stays identical.

   Cross-area helpers to lift into `_shared.py`:
   - `_require_editable` — used by ~9 of the 10 slices.
   - `_require_response_loss_ack` — used by ~9 of the 10 slices.
   - `_lifecycle_error_response` — Session Home + Instruments.
   - `_quick_setup_cookie_name` + `_quick_setup_unlocked` —
     Quick Setup *and* Session Home (the latter reads
     `_quick_setup_unlocked` while building the Quick Setup card
     context at line 450 of today's file).
   - `_QUICK_SETUP_COOKIE_PREFIX` — the constant the cookie
     helpers reference.
   - The shared `_templates = Jinja2Templates(...)` and its
     globals/filter registration.

   Helpers that are NOT cross-area and stay with their slice:
   - `_require_instrument_in_session` — every callsite is inside
     instrument routes; travels with the Instruments slice.
   - `_require_ready` / `_require_invitation_in_session` — used
     only inside Operations routes; travel with the Operations
     slice.
   - `_require_rtd_in_session`, `_can_edit_instrument`,
     `_require_instrument_editable`, `_instruments_redirect`,
     `_build_field_rows`, `_parse_optional_float`,
     `_rtd_redirect_with_error` — instruments-only.
   - `_settings_redirect_url` — settings-only.
   - `_resolve_save_as_name`, `_name_taken_by_other` —
     Rule Builder only.
   - `_render_assignments_hub` — Assignments slice only.
   - `_handle_import` — Setup rosters slice only.
   - `_handle_quick_setup_import`, `_run_quick_setup_import`,
     `_run_quick_setup_assignments` — Quick Setup slice only.

2. **Slice PRs**, in this order (smallest first; sizes measured
   against the post-13A-1 file at 4,423 lines). Each is a single
   feature area moving to its own file under the new package.

   1. Sessions lobby (~73 lines; 2 routes — list / bulk-delete-
      selected). Smallest and most self-contained — the cleanest
      first slice to validate the package plumbing.
   2. Operator settings (~115 lines; the per-operator credentials
      surface).
   3. Setup-invite + email-template editor (~125 lines).
   4. Assignments (~316 lines; manual + full-matrix + delete-all).
   5. Session Home (~365 lines; detail / new / create / edit /
      delete / lifecycle transitions).
   6. Setup rosters (~370 lines; Reviewers + Reviewees pages and
      their imports).
   7. Quick Setup (~566 lines; lock toggle, per-slot routes,
      submit-all). Will gain one more route when **Segment 12A
      PR 6** wires Slot 4 (configuration import) — that route
      lands in this sub-module.
   8. Rule Builder (~669 lines; the editor page + copy / save /
      delete / generate). Freshly bounded by Segment 13A-1 PR 4b
      (PR #602, 2026-05-07) — clean self-contained block.
   9. Operations pages (~750 lines; Validate, Previews, Manage
      Invitations, Responses, Outbox).
   10. Instruments (~1,500 lines) — landed last because it's the
       largest slice; deferring it keeps the diff size of every
       earlier PR manageable, and isolates the riskiest move into
       its own reviewable PR.

## 5. Land-safety checklist (per slice)

Each slice PR follows the same shape:

- All moved routes keep their exact URL paths, methods, and
  dependency injection signatures.
- All moved routes keep their exact audit-event emissions
  (`event_type`, envelope shape, identity slots).
- The full `pytest` suite passes locally and in CI (SQLite +
  Postgres) without test changes other than direct symbol imports
  if any exist.
- `ruff check .` passes.
- The PR description names the slice and lists the routes moved,
  for the audit trail.

## 6. Sequencing

- **Land before 12A starts coding** so 12A's new routes target
  organised files.
- **Land before 13C starts coding** so 13C's new instruments
  routes don't fatten an already-oversized slice.
- 12B, 13B, and 14-1 are independent of this refactor and can
  interleave freely.

## 7. Rollback

Every slice PR is independently revertable — reverting any one
slice puts those routes back into a single file without affecting
the others. The package conversion (PR 1) is the only PR with a
broader blast radius; if it needs to be reverted, all subsequent
slice PRs revert with it as a unit.
