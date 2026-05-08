# Refactor Plan — Split `routes_operator.py` by feature area

**Project:** Review Robin Web
**Status:** Stub — not yet started
**Sizing:** ~1 prep PR + ~10 mechanical slice PRs

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
change. Each sub-module owns its own `APIRouter()` instance with
the appropriate path prefix; `__init__.py` includes them all into
the top-level router so the public import surface
(`from app.web.routes_operator import router`) is preserved.

Slices are organised by feature area, matching the operator
chrome's tab structure (Setup / Operations / Settings) plus the
session-lifecycle and lobby boundaries that already exist
implicitly in the file.

## 4. PR ladder

PRs land in this order; smallest and most self-contained first to
de-risk the package conversion before tackling the heaviest slices.

1. **Prep PR — extract shared helpers.** Move the cross-area
   helpers (the lifecycle / editability gates, the response-loss
   acknowledgement gate, the instrument-membership check, the
   lifecycle-error response shaper, and the quick-setup cookie
   helpers) into a new sibling module. Pure relocation. Unblocks
   every later split.

2. **Package conversion PR.** Turn `routes_operator.py` into a
   package directory; the original file becomes
   `__init__.py` and gets thinned down as later PRs lift slices
   out. Existing route registration in `app/main.py` stays
   identical.

3. **Slice PRs**, in this order. Each is a single feature area
   moving to its own file under the new package; smallest first.

   1. Operator settings (the per-operator credentials surface).
   2. Sessions lobby (list / create / bulk-delete-selected).
   3. Session Home (detail / edit / delete / lifecycle transitions).
   4. Quick Setup (lock toggle, per-slot routes, submit-all).
   5. Setup rosters (Reviewers + Reviewees pages and their imports).
   6. Assignments (manual + full-matrix + delete-all).
   7. Rule Builder (the editor page + copy / save / delete /
      generate).
   8. Setup-invite + email-template editor.
   9. Operations pages (Validate, Previews, Manage Invitations,
      Responses, Outbox).
   10. Instruments — landed last because it's the largest slice;
       deferring it keeps the diff size of every earlier PR
       manageable, and isolates the riskiest move into its own
       reviewable PR.

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
the others. The package conversion (PR 2) is the only PR with a
broader blast radius; if it needs to be reverted, all subsequent
slice PRs revert with it as a unit.
