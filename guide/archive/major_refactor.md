# Refactor Plan — Split `routes_operator.py` by feature area

**Project:** Review Robin Web
**Status:** Complete — all 11 PRs landed; `_legacy.py` deleted in
PR 10 by renaming to `_instruments.py`.
**Sizing:** 1 package-conversion PR + 10 mechanical slice PRs

### Progress (2026-05-08)

| PR | Slice | Module | Status |
|---|---|---|---|
| 0  | Package shape + `_shared.py`         | `__init__.py`, `_shared.py`, `_legacy.py` | Landed (#651) |
| 1  | Sessions lobby                       | `_lobby.py`         | Landed (#651) |
| 2  | Operator settings                    | `_settings.py`      | Landed (#651) |
| 3  | Setup-invite + email template editor | `_setup_invite.py`  | Landed (#651) |
| 4  | Assignments                          | `_assignments.py`   | Landed (#652) |
| 5  | Session Home                         | `_session_home.py`  | Landed (#653) |
| 6  | Setup rosters                        | `_setup_rosters.py` | Landed (#654) |
| 7  | Quick Setup (+ deferred `create_session`) | `_quick_setup.py` | Landed (#655) |
| 8  | Rule Builder                         | `_rule_builder.py`  | Landed (#656) |
| 9  | Operations                           | `_operations.py`    | Landed (#657) |
| 10 | Instruments                          | `_instruments.py`   | Landed |

---

## 1. Why now

`app/web/routes_operator.py` is 4,423 lines and 79 route decorators
(verified 2026-05-08 against the post-13A-1 file). The file already
has clear feature-area seams that map almost 1:1 to the operator
chrome's nav structure, so the split is mostly mechanical rather than
architectural.

The trigger is **Segment 13C (enhanced instruments)**: 13C piles new
code (group-scoped instrument creation, duplicate button, fanout
helpers) onto the already-largest slice inside the file
(Instruments, ~1,500 lines). Splitting before 13C means 13C lands
cleanly into a focused, single-purpose module; splitting after means
a bigger, riskier split with a fatter diff to review.

Segment 12A (export + import) is also still planning-only at the
time of writing. 12A adds:
- One new RuleSet-scoped route family (`/operator/rule-sets/...`),
  which has nowhere natural to live in today's file — it would land
  wherever it fits, fattening whichever slice was nearest.
- A new Quick Setup Slot 4 import endpoint (12A PR 6), which fattens
  the existing Quick Setup section.
- New Extract Data routes that fit on Session Home.

Splitting first lets all three target organised files from day one.

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
- **No new operator-wide chrome.** Don't touch breadcrumbs,
  templates, or `views.py` shape adapters.

## 3. Approach

Convert `app/web/routes_operator.py` into a package
(`app/web/routes_operator/__init__.py`) that re-exports a single
assembled `router`. App registration in `app/main.py:29` does not
change. The public import surface
(`from app.web.routes_operator import router`) is preserved.

Verified external import sites (the only ones that matter — every
other reference is a docstring / comment / spec callout):

- `app/main.py:9` — `from app.web.routes_operator import router as operator_router`.
- `app/services/email_templates.py:413` — comment-only reference,
  no symbol import.
- No test file imports anything from `routes_operator`.

### 3.0 Pinned decisions

These were settled before authoring PR 0; later sections defer to them.

- **PR 0 scope.** Package shape + every cross-slice helper lifted into
  `_shared.py` + `_legacy.py` housing all 79 routes unchanged. No real
  slice ships in PR 0. See §6 for the full checklist.
- **Legacy container.** `app/web/routes_operator/_legacy.py`. The
  package `__init__.py` does `from . import _legacy` and mounts
  `_legacy.router`. Slice PRs carve routes out of `_legacy.py` into
  their sibling `_<area>.py` until `_legacy.py` is empty and gets
  deleted in PR 10.
- **Slice file naming.** Underscore-prefixed
  (`_lobby.py`, `_session_home.py`, …) — package-private, matches
  `_shared.py`, deliberate divergence from peer `routes_*.py` modules
  because the package directory already namespaces them.
- **Import-graph invariant.** Every slice imports only from
  `_shared.py` and from outside the package
  (`app.services.*`, `app.db.*`, `app.web.deps`, `app.web.views`,
  `app.web.breadcrumbs`, `app.web.return_to`). **No slice-to-slice
  imports.** `_shared.py` imports nothing from the package. PR review
  must reject any future drift on this invariant.
- **Sequencing with feature segments.** Segment 12A and Segment 13C
  PR authoring is paused for the duration of the 11-PR refactor
  ladder. 12B (audit retention), 13B (sort by reviewee), 14-1 (email
  infra) remain free to interleave. See §9.

### 3.1 Sub-module pattern (pin once, reuse in every slice)

Each sub-module under `app/web/routes_operator/` declares an
unprefixed router:

```python
# app/web/routes_operator/_lobby.py
from fastapi import APIRouter
router = APIRouter()

@router.get("/sessions", response_class=HTMLResponse)
def list_sessions(...): ...
```

and writes full paths starting with `/sessions/{session_id}/...`
(or `/sessions`, `/settings`, etc.). The package
`__init__.py` owns the operator-wide prefix and mounts every
sub-module:

```python
# app/web/routes_operator/__init__.py
from fastapi import APIRouter
from . import (
    _lobby,
    _settings,
    _session_home,
    _setup_rosters,
    _setup_invite,
    _quick_setup,
    _assignments,
    _rule_builder,
    _instruments,
    _operations,
)

router = APIRouter(prefix="/operator", tags=["operator"])
router.include_router(_lobby.router)
router.include_router(_settings.router)
router.include_router(_session_home.router)
router.include_router(_setup_rosters.router)
router.include_router(_setup_invite.router)
router.include_router(_quick_setup.router)
router.include_router(_assignments.router)
router.include_router(_rule_builder.router)
router.include_router(_instruments.router)
router.include_router(_operations.router)
```

This avoids per-area prefix decisions in each slice PR and keeps
the cross-area URL families that already exist (Assignments and
Rule Builder both live under `/sessions/{id}/assignments/...`)
working without any router gymnastics. Mount order is irrelevant
for correctness (no overlapping paths), but the grouping above
matches operator-chrome nav order so `app.routes` reads naturally.

### 3.2 Shared `Jinja2Templates` instance

Lines 51–61 of today's file instantiate one `Jinja2Templates`
and register three operator-only Jinja entries
(`display_field_label`, `is_locked_display_source`,
`lifecycle_label`). After the split, every sub-module needs the
same configured instance. Put the single `_templates` in the new
`_shared.py` and import it from each sub-module — one
registration point, zero risk of drift across 10 files.

**Critical detail:** today's directory is
`Path(__file__).parent / "templates"`. Post-conversion `__file__`
is `app/web/routes_operator/_shared.py`, so the relative path must
become `Path(__file__).parent.parent / "templates"`. Without this
fix every operator template render 500s — pin it in the
package-conversion PR and add a smoke test that hits
`GET /operator/sessions` to catch a regression.

The peer modules `routes_about.py` / `routes_auth.py` /
`routes_reviewer.py` each build their own `Jinja2Templates` but
don't share custom globals, so they stay as they are. Don't
extract a project-wide template factory — out of scope.

### 3.3 Cross-file `qsu_` cookie prefix

`app/main.py:21` hardcodes the `qsu_` cookie prefix in the
`_QUICK_SETUP_COOKIE_RE` regex used by the navigation middleware
that expires the unlock cookie. Today's `routes_operator.py:691`
defines `_QUICK_SETUP_COOKIE_PREFIX = "qsu"` and uses it locally.
Post-refactor the constant lives in `_shared.py`.

**Resolution for the package-conversion PR:** leave `main.py`'s
regex literal as-is (it's the wider-scoped owner of the
navigation behavior; `routes_operator/_shared.py` is the
narrow-scoped writer). Add a comment in both files cross-referencing
the other so the next reader doesn't change one without the other.
Don't introduce a third home for the constant — that's a new
abstraction, which is out of scope.

## 4. Slice boundaries (line ranges in today's file)

Verified against `app/web/routes_operator.py` at 4,423 lines
(2026-05-08). All ranges are inclusive.

| # | Slice | Module | Lines | Routes | Helpers carried |
|---|---|---|---|---|---|
| — | Header / imports | `__init__.py` + `_shared.py` | 1–62 | — | template factory, globals, lifecycle filter |
| 1 | Sessions lobby | `_lobby.py` | 64–123 | 2 | — |
| 2 | Operator settings | `_settings.py` | 126–238 (incl. helper) | 3 | `_settings_redirect_url` |
| 3 | Session Home (incl. lifecycle, edit, delete, validate) | `_session_home.py` | 241–525, 2182–2294, 2296–2380, 2447–2510 | 11 | (lifecycle handlers + helpers stay with Home) |
| 4 | Setup rosters (Reviewers / Reviewees pages + imports + delete-all) | `_setup_rosters.py` | 528–667, 2122–2180, 2296–2348 | 6 | `_handle_import` |
| 5 | Quick Setup | `_quick_setup.py` | 669–1259 | 5 (today; +1 in 12A PR 6) | `_QUICK_SETUP_COOKIE_PREFIX`, `_quick_setup_cookie_name`, `_quick_setup_unlocked`*, `_handle_quick_setup_import`, `_run_quick_setup_import`, `_run_quick_setup_assignments` |
| 6 | Assignments (manual + full-matrix + delete-all) | `_assignments.py` | 1261–1342, 2015–2120, 2350–2380 | 4 | `_render_assignments_hub` |
| 7 | Rule Builder | `_rule_builder.py` | 1345–2014 | 5 | `_resolve_save_as_name`, `_name_taken_by_other` |
| 8 | Setup-invite + email-template editor | `_setup_invite.py` | 2576–2725 | 3 | `_VALID_TEMPLATES`, `_build_field_rows` |
| 9 | Instruments | `_instruments.py` | 2512–2575, 2871–3962 | ~30 | `_can_edit_instrument`, `_require_instrument_editable`, `_require_instrument_in_session`, `_instruments_redirect`, `_parse_optional_float`, `_rtd_redirect_with_error`, `_require_rtd_in_session`, `_require_response_field_in_instrument`, `_require_display_field_in_instrument` |
| 10 | Operations (Validate + Previews + Manage Invitations + Outbox + Responses + reminders) | `_operations.py` | 460–525, 2727–2868, 3963–4423 | ~15 | `_require_ready`, `_require_invitation_in_session` |

\* `_quick_setup_unlocked` is also read by Session Home at today's
line 450 while building the Quick Setup card context. To avoid an
import cycle (`_session_home` → `_quick_setup` would be fine, but
`_quick_setup` doesn't need anything from `_session_home`), put
the cookie helpers in `_shared.py` instead. See §5.

### 4.1 Notes on overlapping ranges

- **Validate page (lines 460–525).** Lives between Session Home
  (387–457) and roster imports (528–584) in today's file. It's
  rendered from the Operations row but reads the same readiness
  report as Session Home's `?validated=1` flow. Travel with the
  Operations slice — same `severity`/`activate` query semantics,
  same `validation` service, no Session-Home-specific state.

- **Setup-invite block (2576–2725) sits between Instruments
  (2527–2573) and Instruments-detail (2871+).** `_build_field_rows`
  and `_VALID_TEMPLATES` only touch `email_templates`; they're
  Setup-invite-only. The Instruments slice picks up at line 2871
  (`_instruments_redirect`) cleanly.

- **Lifecycle helpers (2382–2440).** `_require_editable`,
  `_require_response_loss_ack`, `_lifecycle_error_response`,
  `_require_instrument_in_session` are used cross-slice — they
  go in `_shared.py`. See §5 for the call-site audit.

- **Roster delete-all routes (2296–2348).** Today they sit in
  the lifecycle / session-management region. They're roster-
  specific behavior so they travel with Setup rosters — the
  helper they use (`_require_editable`) is in `_shared.py`.

- **Assignments-delete-all (2350–2380).** Travels with Assignments,
  not Session Home, since its URL is `/assignments/delete-all` and
  its template re-render path is the assignments hub.

## 5. Shared-helpers map (`_shared.py`)

Helpers that have callsites in 2+ slices, or that capture
project-wide invariants (template factory, cookie naming):

```python
# app/web/routes_operator/_shared.py
from pathlib import Path
from fastapi import HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession
from app.services import instruments as instruments_service
from app.services import lifecycle_display, session_lifecycle as lifecycle


# ------------------------------------------------------------------ #
# Template factory + Jinja globals — single source of truth.
# Note the `.parent.parent` hop: __file__ is now one level deeper
# (app/web/routes_operator/_shared.py) than the legacy
# routes_operator.py was, so the templates dir resolves up two.
# ------------------------------------------------------------------ #
_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "templates")
)
_templates.env.globals["app_version"] = settings.app_version
_templates.env.globals["display_field_label"] = (
    instruments_service.display_field_label
)
_templates.env.globals["is_locked_display_source"] = (
    instruments_service.is_locked_display_source
)
_templates.env.filters["lifecycle_label"] = (
    lifecycle_display.lifecycle_display_label
)


# ------------------------------------------------------------------ #
# Lifecycle / edit-lock guards (cross-slice).
# ------------------------------------------------------------------ #
def _require_editable(review_session: ReviewSession) -> None: ...
def _require_response_loss_ack(
    db: Session, review_session: ReviewSession, ack: str | None
) -> None: ...
def _lifecycle_error_response(exc: lifecycle.LifecycleError) -> HTTPException: ...


# ------------------------------------------------------------------ #
# Quick Setup cookie naming. Mirror constant of the regex in
# app/main.py:21 — keep both call sites in sync.
# ------------------------------------------------------------------ #
_QUICK_SETUP_COOKIE_PREFIX = "qsu"
def _quick_setup_cookie_name(session_id: int) -> str: ...
def _quick_setup_unlocked(
    request: Request, review_session: ReviewSession
) -> bool: ...
```

### 5.1 Helpers that stay slice-local

| Helper | Sole-callsite slice | Why local |
|---|---|---|
| `_settings_redirect_url` | Settings | Only Save / Clear handlers call it. |
| `_handle_import` | Setup rosters | Reviewer + reviewee imports only. |
| `_handle_quick_setup_import` / `_run_quick_setup_import` / `_run_quick_setup_assignments` | Quick Setup | Card-specific dispatch. |
| `_render_assignments_hub` | Assignments | Manual + full-matrix re-render path. |
| `_resolve_save_as_name` / `_name_taken_by_other` | Rule Builder | Save / Save As collision check. |
| `_VALID_TEMPLATES` / `_build_field_rows` | Setup-invite | Email-template editor row builder. |
| `_can_edit_instrument` / `_require_instrument_editable` / `_require_instrument_in_session` / `_instruments_redirect` / `_parse_optional_float` / `_rtd_redirect_with_error` / `_require_rtd_in_session` / `_require_response_field_in_instrument` / `_require_display_field_in_instrument` | Instruments | All instrument / RTD CRUD only. |
| `_require_ready` / `_require_invitation_in_session` | Operations | Used by invitations + reminders only. |
| `_REVERT_RETURN_TO` constant | Session Home | Read only by `session_revert_to_draft`. |

### 5.2 Cross-slice-helper call-site audit

Before lifting `_require_editable` and `_require_response_loss_ack`
into `_shared.py`, verify they aren't ever shadowed by slice-local
copies. Today's file has exactly one definition of each, used by:

- `_require_editable`: ~9 of 10 slices. Lifts cleanly.
- `_require_response_loss_ack`: roster imports + Quick Setup
  imports. Lifts cleanly.
- `_lifecycle_error_response`: verified 2026-05-08, three callsites
  in today's file: lines 2466 + 2502 (Session Home activate /
  revert) and 3916 (Instruments). Cross-slice — keep in `_shared.py`.

## 6. PR ladder

Smallest and most self-contained first to de-risk the package
conversion before tackling the heaviest slices.

### PR 0 — Package conversion + shared helpers

Turn `routes_operator.py` into a package directory
(`app/web/routes_operator/__init__.py`) and lift every cross-slice
helper into a new `_shared.py`. The legacy file is renamed to
`_legacy.py` inside the new package; all 79 routes continue to
live there unchanged. No real slice ships in PR 0.

This shape isolates the three things that are most likely to
regress (template-directory path, import graph, cookie cross-file
constant) into a single reviewable diff before PRs 1-10 start
moving routes.

**PR 0 explicit checklist:**

- `app/web/routes_operator.py` → `app/web/routes_operator/_legacy.py`
  (route bodies unchanged; helper definitions deleted because
  they've moved to `_shared.py`; helper *call sites* now import
  from `._shared`).
- `app/web/routes_operator/__init__.py` does
  `from . import _legacy` (and only `_legacy` for now), declares
  `router = APIRouter(prefix="/operator", tags=["operator"])`,
  and calls `router.include_router(_legacy.router)`.
- `app/web/routes_operator/_shared.py` owns the template factory,
  Jinja globals, all helpers in §5, and `_QUICK_SETUP_COOKIE_PREFIX`.
- Template directory uses `.parent.parent / "templates"` with a
  comment explaining the hop.
- `app/main.py:9` import unchanged.
- `app/main.py:21` `_QUICK_SETUP_COOKIE_RE` unchanged; add a
  cross-reference comment to `_shared.py`'s constant and vice-versa.
- New smoke test `tests/integration/test_operator_smoke.py` (or
  added to the nearest existing routes-smoke file) hits
  `GET /operator/sessions` and asserts 200 + a known string from
  `sessions_list.html`. This catches a `.parent.parent` template-
  path regression that would otherwise 500 every operator page.
- `pytest` passes (SQLite + Postgres CI).
- `ruff check .` passes.
- Helper call-site audit: every `_require_editable`,
  `_require_response_loss_ack`, `_lifecycle_error_response` call
  in `_legacy.py` resolves via `from ._shared import ...` — no
  shadowed local copies left behind.

### PRs 1-10 — Slice PRs

Each slice PR moves one feature area from the legacy container in
`__init__.py` (or `_legacy.py`) into its own sub-module file. Order
matches the planned per-slice size, smallest first; the last PR
(Instruments) is largest because it's the riskiest move and earns
its own focused review.

| PR | Slice | ~Lines moved | Routes moved | Notes |
|---|---|---|---|---|
| 1 | Sessions lobby | ~73 | 2 | Bonus first slice if not already shipped in PR 0. |
| 2 | Operator settings | ~115 | 3 | Per-operator credentials surface. |
| 3 | Setup-invite + email template editor | ~150 | 3 | Includes `_VALID_TEMPLATES`/`_build_field_rows` helpers. |
| 4 | Assignments (manual + full-matrix + delete-all) | ~316 | 4 | Includes `_render_assignments_hub`. |
| 5 | Session Home | ~430 | 11 | Detail / new / create / edit / delete / validate / activate / revert / delete-data. |
| 6 | Setup rosters | ~370 | 6 | Reviewers + Reviewees pages + imports + delete-alls. |
| 7 | Quick Setup | ~570 | 5 | Will gain Slot 4 import in **12A PR 6** post-refactor. |
| 8 | Rule Builder | ~669 | 5 | Bounded by 13A-1 PR 4b — clean self-contained block. |
| 9 | Operations | ~750 | ~15 | Validate + Previews + Manage Invitations + Outbox + Responses + reminders. |
| 10 | Instruments | ~1,500 | ~30 | Largest; isolated to its own focused review. Touches `spec/instruments.md:10`. |

## 7. Land-safety checklist (per slice PR)

Each slice PR follows the same shape:

- [ ] All moved routes keep their exact URL paths, methods, and
  dependency-injection signatures.
- [ ] All moved routes keep their exact audit-event emissions
  (`event_type`, envelope shape, identity slots).
- [ ] All `_templates.TemplateResponse(...)` calls render the same
  template paths (the template tree under `app/web/templates/` is
  untouched).
- [ ] All `RedirectResponse(url=...)` strings are byte-identical
  (relocation can silently drop a `#fragment` if grep-and-paste
  goes wrong — diff the moved block, don't retype).
- [ ] The full `pytest` suite passes locally and in CI (SQLite +
  Postgres) without test changes other than direct symbol imports
  if any exist.
- [ ] `ruff check .` passes.
- [ ] No new symbol shadows a `_shared.py` helper (e.g. don't let
  a slice import `_require_editable` and *also* define a local
  shadow during the move).
- [ ] The PR description names the slice and lists the routes
  moved, for the audit trail.
- [ ] If the slice's routes are referenced by file path in any
  `spec/` doc, update the path in the same PR. Today the only
  live references are `spec/instruments.md:10` (Instruments slice
  → PR 10) and `spec/sessions_overview.md:203` (Sessions lobby
  slice → PR 1).
- [ ] `guide/archive/unfinished_business.md` references to
  `routes_operator.py:<line>` (15+ callouts at lines 101, 308, 460,
  685, 794, 942, 1004, 1193, 1543, 1559, 1666, etc.) — update only
  when the unfinished item is actually being worked on, not as
  part of the refactor. The refactor is structural only.

## 8. Per-slice risk + verification

| Slice | Risk | Targeted verification beyond `pytest` |
|---|---|---|
| Sessions lobby | None notable | `tests/integration/test_sessions_overview*.py` |
| Operator settings | `return_to` redirects easy to typo | `tests/integration/test_operator_settings.py` (or whichever covers Save/Clear flows) |
| Setup-invite | `_VALID_TEMPLATES` literal must match service | `tests/integration/test_email_template*.py`; spot-check `?template=invitation|reminder|responses_received` |
| Assignments | Re-render-on-error path uses `_render_assignments_hub` | `tests/integration/test_assignments*.py`, manual import error path |
| Session Home | `?validated=1` round-trip + lifecycle redirects | `tests/integration/test_session_home*.py`, activate/revert flows |
| Setup rosters | Import preview → confirm-replace → response-loss-ack chain crosses 4 conditions | `tests/integration/test_csv_imports*.py`, both reviewer + reviewee importer error matrices |
| Quick Setup | Per-slot scoped error redirects + lock cookie + `submit_all` chain | `tests/integration/test_quick_setup*.py`; manual: `qsu_{id}` cookie set/cleared on lock POST + nav-away |
| Rule Builder | Save / Save As collision logic; copy / generate dispatch | `tests/integration/test_rule_*` plus rule-engine unit tests |
| Operations | Reminder dispatch + invitation regeneration | `tests/integration/test_invitations*.py`, `test_responses*.py`, `test_outbox*.py` |
| Instruments | Largest surface; bulk visibility + RTD CRUD + bulk-save-fields | `tests/integration/test_instruments*.py`, `test_response_types*.py`; manual smoke at `/sessions/{id}/instruments` |

## 9. Sequencing

- **Segments 12A and 13C are paused for the duration of the 11-PR
  ladder.** No 12A or 13C PR is authored until PR 10 (Instruments)
  has landed. This avoids interleave merge-conflict surface in
  the slice PRs and means every new route from those segments
  lands in the post-refactor target file from day one.
- 12B (audit retention), 13B (sort by reviewee), and 14-1
  (email infra) are independent of this refactor and can interleave
  freely between slice PRs.
- PRs 1-9 are independent of each other — pick smallest-first per
  the §6 table to keep review load even.
- PR 10 (Instruments) lands last; it's the largest move and the
  one that empties `_legacy.py`. Once it merges, delete
  `_legacy.py` and the `from . import _legacy` line in
  `__init__.py` in the same PR.

## 10. New-routes home for in-flight segments

Once PR 0 lands, in-flight segments target these files:

| Segment / PR | New routes | Lands in |
|---|---|---|
| 12A PR 6 (Quick Setup Slot 4 import) | `POST /sessions/{id}/quick-setup/settings` (or per the segment's final wiring) | `_quick_setup.py` |
| 12A PR 6 (Extract Data downloads on Session Home) | `GET /sessions/{id}/extract/...` | `_session_home.py` (or new `_extract.py` if it grows past ~100 lines) |
| 12A PR 7 (RuleSet round-trip) | `GET /rule-sets/{id}/export.json`, `POST /rule-sets/import` | new `_rule_sets.py` (these are operator-scoped but workspace-level, not session-scoped) |
| 13C PR 2 (group-scoped instrument creation) | `POST /sessions/{id}/instruments/add-group-scoped` (or per the segment's final wiring) | `_instruments.py` |
| 13C PR 5 (duplicate instrument) | `POST /sessions/{id}/instruments/{instrument_id}/duplicate` | `_instruments.py` |

12A PR 7's `_rule_sets.py` is the only genuinely new module past
PR 0-10; the rest fit in slices already drawn.

## 10.1 Per-slice PR description template

Standardize slice PR bodies so reviewers can scan all 10 the same way:

```markdown
## Slice: <name>  (PR <n> of 10)

### Routes moved
- `GET  /operator/<path>` — <handler name>
- `POST /operator/<path>` — <handler name>
- …

### Helpers moved
- Slice-local: <list>
- Lifted to `_shared.py`: <list, or "none — already in PR 0">

### Source ranges (in pre-refactor `routes_operator.py`)
- <line range> → `_<area>.py`

### Audit-event impact
None — pure relocation. No `event_type`, envelope shape, or identity
slot changed. Verified by diffing the moved blocks against the source
ranges above.

### Verification
- [ ] `pytest` (SQLite) green
- [ ] `pytest` (Postgres CI) green
- [ ] `ruff check .` green
- [ ] §7 land-safety checklist all ticked
- [ ] §8 targeted tests for this slice exercised
```

## 11. Rollback

Every slice PR is independently revertable — reverting any one
slice puts those routes back into the legacy container in
`__init__.py` without affecting the others. The package conversion
(PR 0) is the only PR with a broader blast radius; if it needs to
be reverted, all subsequent slice PRs revert with it as a unit.

The legacy container in `__init__.py` (or `_legacy.py`) is the
intentional "still works" backstop during the slice migration —
don't delete it until PR 10 lands and routes_operator/__init__.py
contains nothing but the prefix-mounting boilerplate.

---

## 12. Follow-on refactor candidates (post-routes_operator)

With the `routes_operator` ladder complete (#651 → #659) plus its
doc sweep (#660), an architectural audit of the rest of the codebase
surfaced **four** distinct next-target candidates. They're sketched
here at the same level of detail as §3-§11 above so any of them can
be picked up as a self-contained ladder when the time comes.

The audit also confirmed what's *not* a problem: layering is clean
(services don't import from `app/web/`), tests cleanly exercise HTTP
routes (no internal-helper coupling), and there's no dead code or
stale scaffolding hanging around.

### 12.A — Split `app/services/instruments.py` (highest architectural value)

**Status: Complete (2026-05-09).** All 5 PRs landed (#663 → #666 →
the PR 4 finale that deletes `_legacy.py` by renaming it to
`_instrument_crud.py`). Final layout:

```
app/services/instruments/
├── __init__.py           # Re-export wall (preserves pre-package surface)
├── _state.py             # saved_state_for_session + _instrument_label
├── _rtds.py              # Response Type Definitions (PR 1)
├── _display_fields.py    # Display fields (PR 2)
├── _response_fields.py   # Response fields + bulk_save_fields (PR 3)
└── _instrument_crud.py   # Instrument lifecycle + bulk toggles (PR 4)
```

`_instrument_label` lifted to `_state.py` in PR 2 to break a
display-fields ↔ legacy import cycle (it's used in audit-summary
copy by every slice). Model classes (`InstrumentResponseField`,
`ResponseTypeDefinition`) re-exported through their natural slices
(`_response_fields.py` and `_rtds.py`) to preserve the pre-package
surface where two route handlers reach them as
`instruments_service.<Model>`.

**Why.** 2,469 LOC, ~50 public functions, owns five unrelated
concerns (Response Type Definitions / display fields / response
fields / instrument CRUD / shared state). Imported by 5 sibling
files (`csv_imports.py`, `sessions.py`, `assignments.py`,
`routes_reviewer.py`, `routes_operator/_shared.py`). Only candidate
that's both size-and-coupling debt rather than just size.

**Slice boundaries (line ranges verified against the current file):**

| Slice | Module | Lines | Highlights |
|---|---|---|---|
| 1 | `_rtds.py` (Response Type Definitions) | 158-749 | `add/update/delete_response_type_definition`, `get_session_rtds`, `assert_rtd_precision`, RTD error classes |
| 2 | `_display_fields.py` | 1122-1648 | `add/update/delete/move_display_field`, `seed_display_fields_from_*`, `prune_unpopulated_display_fields` |
| 3 | `_response_fields.py` | 1650-2303 | `bulk_save_fields` (~230 LOC, the largest function in the codebase), `add/update/delete/move_response_field` |
| 4 | `_instrument_crud.py` | 750-1121 + 2305-2469 | `create_instrument`, `delete_instrument`, `update_instrument_description`, `update_short_label`, `bulk_set_accepting`, `bulk_set_visibility` |
| 5 | `_state.py` (lifted in PR 0) | 41-156 | `saved_state_for_session` — read by all four other slices |

**Approach.** Convert `app/services/instruments.py` into a package
(`app/services/instruments/__init__.py`) that re-exports the public
surface. Callers continue to write `from app.services import
instruments` and `instruments.add_response_field(...)` unchanged —
the public names move into sub-modules but `__init__.py` does
explicit `from ._rtds import (...)` re-exports, so the import
surface stays byte-identical. Mirrors the `routes_operator` playbook
except the public symbols are functions (not a `router`).

**Sequencing.**

| PR | Slice | ~Lines moved | Risk |
|---|---|---|---|
| 0 | Package conversion + `_state.py` lift + `__init__.py` re-export wall | ~120 | Medium — prove the import surface stays stable before slicing |
| 1 | RTDs → `_rtds.py` | ~590 | Low — self-contained, only `add/update/delete` emit audit events |
| 2 | Display fields → `_display_fields.py` | ~530 | Medium — `seed_*` helpers called from `csv_imports.py` |
| 3 | Response fields → `_response_fields.py` | ~650 | Medium — `bulk_save_fields` is ~230 LOC |
| 4 | Instrument CRUD → `_instrument_crud.py` | ~540 | Low — leftover after the above land |

**Total:** 1 prep PR + 4 slice PRs = 5 PRs.

**Risks.**

- 19+ audit emitters spread across these slices, all using the
  Segment 11K canonical envelope schema. Pure relocation — the
  EVENT_SCHEMAS registry doesn't care which file the emitter lives
  in. The strict-mode test gate
  (`tests/unit/test_audit_detail_schema.py`) catches any drift.
- All 5 importers use `from app.services import instruments`
  (module-level), not symbol imports — re-export wall keeps them
  green.
- `test_display_field_routes.py` (2,167 LOC) and
  `test_response_type_definitions.py` (817 LOC) exercise routes,
  not service symbols — no test rewrites expected.

### 12.B — Split `app/web/views.py` (largest size win, lowest risk)

**Status: Complete (2026-05-09).** All 11 PRs landed (#668 → #677
plus the PR 10 finale that deletes `_legacy.py` by renaming it to
`_rule_builder.py`). Final layout:

```
app/web/views/
├── __init__.py           # Re-export wall (preserves pre-package surface)
├── _responses.py         # Responses page rows (PR 1)
├── _extract_data.py      # Extract Data card (PR 2)
├── _invitations.py       # Invitations page rows (PR 3)
├── _filters.py           # Shared filter / search helpers (PR 4)
├── _setup.py             # Setup overview rows + status pills (PR 5)
├── _instruments.py       # Instruments page context (PR 6)
├── _quick_setup.py       # Quick Setup card (PR 7)
├── _validate.py          # Validate page (PR 8)
├── _previews.py          # Email + reviewer-surface previews (PR 9)
└── _rule_builder.py      # Rule Builder + Rule Based card (PR 10)
```

The smoke test in `tests/integration/test_operator_smoke.py`
caught one re-export wall oversight during PR 0 (covered by the
extension to `test_operator_session_home_renders` for the
view-builder-dense path); none thereafter. No cross-slice imports
were needed beyond `_setup.session_status_pills` (used by
`_instruments.build_instruments_context`) and the lazy
`routes_reviewer.build_preview_context` import in
`_previews.build_surface_preview_context` (a pre-existing cycle
break preserved verbatim).

**Why.** 3,483 LOC, 79 builders / dataclasses, no architectural
debt — `views.py` is the canonical "view-shape adapter" seam from
CLAUDE.md. The file's existing `# ----` section comments already
group it cleanly along entity / page lines.

**Slice boundaries (verified):**

| Slice | Module | Lines | Pages / entities served |
|---|---|---|---|
| 1 | `_setup.py`           | 44-272    | Setup overview rows, `SetupRow`, status pills |
| 2 | `_instruments.py`     | 273-422   | Instruments page context, `InstrumentHeading`, `PageButton`, constraint summaries |
| 3 | `_validate.py`        | 424-803   | Validate page (`SetupCoverageRow`, `SeverityChip`, `ValidateContext`, `build_validate_context`) |
| 4 | `_quick_setup.py`     | 806-1271  | Quick Setup card on Session Home + new-session page |
| 5 | `_extract_data.py`    | 1273-1417 | Extract Data card |
| 6 | `_invitations.py`     | 1418-1535 | Invitations page rows |
| 7 | `_responses.py`       | 1537-1571 | Responses page rows |
| 8 | `_filters.py`         | 1572-1733 | Shared filter / search helpers across Invitations + Responses |
| 9 | `_previews.py`        | 1735-2267 | Email Previews + reviewer-surface preview iframe |
| 10 | `_rule_builder.py`   | 2269-3483 | Rule Builder + Rule Based card (~1,200 LOC, largest slice) |

**Approach.** Identical to `routes_operator` playbook: package
conversion (`app/web/views/__init__.py`) + re-export wall. Callsites
(`from app.web import views`) stay byte-identical.

**Sequencing.** 1 package-conversion PR + 9 slice PRs = 10 PRs.
Smallest first: Responses → Extract Data → Invitations → Filters →
Setup → Instruments → Quick Setup → Validate → Previews → Rule
Builder (largest, isolate last).

**Risks.**

- 6 importers in `app/web/`: every operator route slice +
  `routes_reviewer.py`. All use `from app.web import views` — re-
  export wall keeps them green.
- 8 inline `from app.services.rules import library` callsites at
  `views.py` lines 1016, 1191, 2348, 3123, 3226, 3365 (plus the 2
  in `_rule_builder` and `_quick_setup` route slices). These are
  stylistic relics — confirmed no circular-import risk. §12.C2
  addresses them; if §12.C2 lands first, §12.B's slice PRs lift
  them to module scope as part of the move.

### 12.C — Cross-cutting hygiene bundle (small, fast, multiple wins)

**Status: Complete (2026-05-09).** All 3 PRs landed (#680 → #681 →
#682) in the recommended C1 → C2 → C3 order. C1 promoted the CSV
decode helper to a public `decode_csv`; C2 lifted the 14 inline
rules-library / TypeAdapter imports to module scope; C3 introduced
`app/services/_queries.py::session_scoped(target, session_id)` and
migrated the busiest callers in `assignments.py`.

Three independent low-risk items the audit flagged that don't
warrant a multi-PR ladder of their own. Sequencing recommendation
in §12.C.0 below; per-item plans in §12.C.1 / §12.C.2 / §12.C.3.

#### 12.C.0 — Sequencing & total PR count

**Recommended order: C1 → C2 → C3.**

| Sub-item | PRs | Why this order |
|---|---|---|
| C1 — CSV decode helper | 1 | Smallest + most contained. Pure dedup, ~30 net LOC. Locks in the per-PR template (verified ranges, ruff-clean diff, smoke tests untouched) before C2 / C3. |
| C2 — Lift inline imports | 1 (omnibus) **or** 3 (per file) | Mechanical. Touches three files (`routes_operator/_quick_setup.py`, `routes_operator/_rule_builder.py`, `views/_quick_setup.py`, `views/_rule_builder.py` — see §12.C.2 callsite map). Recommend the omnibus PR — each per-file diff is too small to justify its own review. |
| C3 — Session-scoped query helper | 1 (helper + busiest callers) | Introduces a new abstraction. Land last so its callsite migrations don't collide with file moves from any in-flight slice work. |

**Total: 3 PRs (recommended) or 5 PRs (if C2 is split per-file).**

Each PR can interleave with feature work — none of them depends
on a slice ladder being open or closed.

#### 12.C.1 — Shared CSV decode helper

**Today (verified 2026-05-09).**
`app/services/csv_imports.py:33-49` already factors the
"decode UTF-8-with-BOM + raise size-limit error + raise
decode error" sequence into a private `_decode_csv(content,
source)` helper. `csv_imports.parse_reviewer_csv` (callsite at
line 142) and `csv_imports.parse_reviewee_csv` (callsite at
line 240) both consume it.

`app/services/assignments.py:175-198` reimplements the same
sequence inline inside `parse_manual_csv` — same shape, same
1 MiB ceiling, same `"File too large"` / `"File is not valid
UTF-8"` `ValidationIssue` copy — but with its own constant
(`MANUAL_CSV_MAX_BYTES`, line 27) instead of `csv_imports.MAX_BYTES`
(line 17). Both constants are `1 * 1024 * 1024`.

**Plan (1 PR).**

Step 1. Promote `csv_imports._decode_csv` to a public helper.
Two options for the home:

- **A (recommended).** Keep it in `csv_imports.py`. Rename
  `_decode_csv` → `decode_csv` (drop the underscore) and adjust
  the two existing in-file callsites at 142 and 240. Net diff:
  `_decode_csv` → `decode_csv`, plus the cross-module import.
- B. Lift to a new `app/services/_csv_shared.py` if `csv_imports`
  feels too entity-specific to host generic CSV plumbing. Net
  diff is bigger and introduces an extra module — pick A unless
  reviewer prefers B.

Step 2. Rewrite `assignments.parse_manual_csv` to call the
promoted helper. The call passes the assignment's
`MANUAL_CSV_MAX_BYTES` constant explicitly (since `_decode_csv`
currently uses `csv_imports.MAX_BYTES` as a module-level
default). To preserve the assignments-side error message wording
(`"max {MAX_BYTES // 1024} KiB"`), the helper signature gains a
`max_bytes` parameter:

```python
def decode_csv(
    content: bytes, source: str, *, max_bytes: int = MAX_BYTES
) -> tuple[str | None, ValidationIssue | None]:
```

Existing callers in `csv_imports.py` rely on the default; the
new caller in `assignments.py` passes `max_bytes=MANUAL_CSV_MAX_BYTES`.

Step 3. Drop the now-redundant inline decode block from
`assignments.parse_manual_csv` (lines 175-198 in today's file).
Net delta: ~25-30 lines removed, ~5 lines added.

**Risk.** Trivial — pure dedup with no behaviour change.
Existing tests cover both the size-limit and UTF-8 error paths
(`tests/integration/test_import_routes.py`,
`tests/integration/test_assignment_routes.py`); no rewrites
expected.

**Critical files.**
- `app/services/csv_imports.py` (promote `_decode_csv` → `decode_csv`,
  add `max_bytes` parameter).
- `app/services/assignments.py` (replace inline decode block with
  `csv_imports.decode_csv(...)` call).

#### 12.C.2 — Lift inline rules-library / TypeAdapter imports to module scope

**Today (verified 2026-05-09).** Fourteen inline imports inside
function bodies, distributed:

| File | Inline `library` / `engine` | Inline `TypeAdapter` | Total |
|---|---|---|---|
| `app/web/routes_operator/_rule_builder.py` | 4 (lines 120, 198, 491, 618) | 1 (line 615) | 5 |
| `app/web/routes_operator/_quick_setup.py` | 1 (line 564) | 1 (line 556) | 2 |
| `app/web/views/_rule_builder.py` | 4 (lines 133, 908, 1011, 1150) | 1 (line 135) | 5 |
| `app/web/views/_quick_setup.py` | 2 (lines 230, 405) | 0 | 2 |
| **Total** | **11** | **3** | **14** |

The audit's import-graph trace (see §12.A's file-level imports +
the views-package re-export wall) confirmed no circular imports
exist between `app.services.rules.{library, engine}` /
`pydantic.TypeAdapter` and the four files above. The inline
imports are stylistic relics from the Segment 13A / 13A-1
build-out, not cycle breaks.

**Plan.**

Either:

- **Omnibus PR (recommended).** Single PR touches all 4 files;
  for each file: delete every inline import, add the equivalent
  module-level imports at the top. The 4 files are independent
  — no ordering concerns within the PR. Net diff is ~14
  inline-imports-deleted plus ~6 module-level-imports-added
  (3 files import `library` only; 1 imports `library + engine`;
  3 import `TypeAdapter`; the union dedups to 6 module-level
  lines).
- Per-file PR (4 PRs). Same diff, sliced. Reasonable if
  reviewers prefer smaller diffs, but each per-file diff is
  ~5 lines net — overhead per PR likely exceeds review time
  saved.

**Module-level imports each file gains.**

| File | Adds at top |
|---|---|
| `routes_operator/_rule_builder.py` | `from pydantic import TypeAdapter`<br>`from app.services.rules import engine, library` |
| `routes_operator/_quick_setup.py` | `from pydantic import TypeAdapter`<br>`from app.services.rules import engine, library` |
| `views/_rule_builder.py` | `from pydantic import TypeAdapter`<br>`from app.services.rules import engine, library` |
| `views/_quick_setup.py` | `from app.services.rules import library` |

**Risk.** Minimal. `pytest -q` is the gate. Verification step
in PR review: re-run the import-graph trace
(`python -c "import app.web.routes_operator._rule_builder"`
× 4 files) to prove no `ImportError` on package init — the
single load-time check the inline imports were arguably
inserted to defer.

**Critical files.** The four listed above. No service / model /
template changes.

#### 12.C.3 — Session-scoped query builder

**Today (verified 2026-05-09).** 38 callsites of
`select(X).where(X.session_id == ...)` across the service layer:

| Service module | Callsites |
|---|---|
| `app/services/assignments.py` | 15 |
| `app/services/instruments/_instrument_crud.py` | 6 |
| `app/services/csv_imports.py` | 6 |
| `app/services/instruments/_display_fields.py` | 5 |
| `app/services/responses.py` | 2 |
| `app/services/invitations.py` | 2 |
| `app/services/instruments/_state.py` | 1 |
| `app/services/instruments/_rtds.py` | 1 |
| **Total** | **38** |

Each callsite saves ~3 lines after migration; the cumulative
audit point (one place to look if the `session_id` column ever
gets renamed) is the bigger win.

**Plan (1 PR).**

Step 1. Add `app/services/_queries.py` with a single helper:

```python
def session_scoped(model, session_id):
    """Pre-filtered ``select(model).where(model.session_id == session_id)``.

    Use as ``db.execute(session_scoped(Reviewer, sid).order_by(...))``.
    Saves the repeated where-clause across the service layer and gives
    the codebase one place to look if the column is ever renamed.
    """
    return select(model).where(model.session_id == session_id)
```

Step 2. Migrate the **15 highest-frequency callsites in
`assignments.py`** in the same PR. That file dominates the
callsite count and is the easiest place to validate the helper's
fit before committing the rest. Pre-migration line tally:
`grep -cE "\\.where\\(.*\\.session_id ==" app/services/assignments.py`
should drop from 15 → 0 after the migration.

Step 3. Leave the other 23 callsites for follow-up PRs that
piggy-back on related-area work. (E.g. when a future PR touches
`_instrument_crud.py`, it migrates that file's 6 callsites in
the same diff.) The plan deliberately avoids a forced
sweep-everything PR — incremental migration carries less merge-
conflict risk.

**Risk.** Slightly higher than C1 / C2 because it introduces a
new abstraction. Mitigations:

- **Validate the helper shape on `assignments.py` first**
  (Step 2 above) — if the API turns out wrong, only one file is
  affected.
- **Don't rename / move `session_scoped` once it lands.** The
  helper signature is the public contract; future migrations
  trust it.
- **Leave existing where-clauses alone outside `assignments.py`.**
  Half-migration is fine; piecemeal migration is the plan, not
  an oversight.

**Sequencing concern.** Land C3 after any in-flight slice
ladder closes. Migrating callsites in a file that's about to
move would create needless merge churn. (As of 2026-05-09 §12.A
and §12.B are both complete, so C3 is safe to author.)

**Critical files.**
- `app/services/_queries.py` (new).
- `app/services/assignments.py` (15 callsites migrated in PR 1).

#### 12.C.4 — Verification (applies to every C* PR)

- `pytest -q` (1008 tests today) green on SQLite locally and on
  the `ci-postgres` job in CI.
- `ruff check .` green.
- For C1: a one-line grep in the PR description confirming
  `assignments.py` no longer carries
  `content.decode("utf-8-sig")`.
- For C2: a one-line `python -c "import …"` smoke for each of
  the four files in the PR description, proving package init
  doesn't `ImportError`.
- For C3: a before/after callsite count for `assignments.py`
  (15 → 0).

### 12.D — Split large integration test files

**Status: Complete (2026-05-09).** Single PR #683 with 6 commits.
`tests/integration/test_display_field_routes.py` (2,167 LOC, 53
tests) split into 6 per-surface files
(`test_display_field_routes.py` 7 CRUD tests +
`test_display_field_lazy_seeding.py` 4 tests +
`test_display_field_locked_rows.py` 3 tests +
`test_display_field_state_machine.py` 8 tests +
`test_response_field_bulk_save.py` 17 tests +
`test_response_type_card.py` 14 tests) backed by a new
`tests/integration/_display_field_helpers.py` shared-helper module
(7 helpers, mirrors the `_preview_iframe.py` convention). The
`reviewer_user` fixture stayed inline in `test_response_field_bulk_save.py`
since exactly one test consumes it. Pure relocation — no fixture
or test changes.

**Why.** `tests/integration/test_display_field_routes.py` is 2,167
LOC, 40+ test functions covering at least 5 distinct surfaces
(display-field CRUD, lazy-seeding from reviewees / assignments,
locked-row gates, state-machine renders, response-field bulk save,
RTD card renders). It outgrew its filename — a fresh contributor
reading "display field routes" wouldn't expect to find RTD or
response-field assertions inside.

**Slice boundaries (by `def test_*` headers):**

| New file | Tests (~) | Surface |
|---|---|---|
| `test_display_field_routes.py` | ~10 | Display-field CRUD (the original scope) |
| `test_display_field_lazy_seeding.py` | ~3 | `reviewees_import_lazy_seeds_*`, `manual_assignments_import_lazy_seeds_pair_context_*` |
| `test_display_field_locked_rows.py` | ~5 | locked-name / locked-email gate tests |
| `test_display_field_state_machine.py` | ~6 | `state_machine_*` editing-param render tests |
| `test_response_field_bulk_save.py` | ~10 | `bulk_save_*` tests (live here today by accident) |
| `test_response_type_card.py` | ~6 | RTD card render tests + `rtd_*_route_*` tests |

**Approach.** Pure file-level relocation — no fixture changes, no
test changes. 1 PR with 6 commits, or 6 small PRs.

**Risks.** Lowest risk + lowest architectural value. Recommend
doing this **after** §12.A so the test split aligns with the new
service boundaries it tests.

### 12.E — Recommendation

| Goal | Pick |
|---|---|
| Pay down the biggest architectural debt | **§12.A — instruments service** |
| Largest LOC reduction with lowest risk | **§12.B — views.py** |
| Quick wins between bigger refactors | **§12.C — hygiene bundle** |
| Test-suite legibility (best after A) | **§12.D — test files** |

**Recommended order:** §12.A first (highest value), then §12.B
(largest mechanical win), interleaved with §12.C1 + §12.C2 (free
wins that don't conflict). Defer §12.C3 and §12.D until §12.A
lands so callsite migrations and test-file boundaries align with
the new service boundaries.

If only one ladder gets authored: **§12.A**. It's the only target
where the size pain is also a coupling pain — splitting it earns
both a smaller file and clearer boundaries between RTDs / display
fields / response fields / instrument CRUD.

### 12.F — Verification (applies to every plan in §12)

- `pytest -q` green on SQLite + `ci-postgres` (currently 1007
  tests).
- `ruff check .` green.
- Source-range citations in each slice PR description so reviewers
  can diff "before" against the pre-refactor file (the same pattern
  the §6 ladder used).
- Strict-mode audit-event gate
  (`tests/unit/test_audit_detail_schema.py`) catches any accidental
  envelope drift in §12.A's slice PRs.
- For §12.B, add a smoke test on `GET /operator/sessions/{id}` to
  the package-conversion PR (catches re-export wall regressions on
  the most-imported builders), mirroring the
  `routes_operator/_shared.py::_templates` template-path hop
  smoke test in §6 PR 0.
