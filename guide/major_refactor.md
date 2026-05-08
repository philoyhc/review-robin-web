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
- [ ] `guide/unfinished_business.md` references to
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
