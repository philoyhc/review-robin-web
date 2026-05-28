# Segment 18N — Housekeeping (file splits + reviewer-surface asymmetry)

**Status:** Stub created 2026-05-28. Sources: the
[2026-05-28 codebase assessment](codebase_assessment_28may.md) §5
"Weaknesses" — file-size creep, and the defensive code asymmetry
between the reviewer surface GET and POST save handlers. Both
were flagged on the 19may assessment (file-size creep as a watch
item) and worsened by the 18I → 18J → 18K → 18L → 18M sequence;
the 28may assessment escalates them as the two open watch items.

The "18N" number follows the 18-family sequence after 18M; no
prior 18N existed. It is **not** related to the 17A
housekeeping segment beyond following the same pattern (pure
structural cleanup, no behaviour change).

## Goal

Pure structural / consistency cleanup — **no behaviour change,
no new features, no new routes or models**. Two independent
tracks; each PR small and reviewable, each landable on its own.

## Why a separate segment

- The items are real but small, share no theme with any feature
  segment, and would only muddy a feature PR if bundled in
  (`CLAUDE.md`: "Don't bundle independent changes"). Collecting
  them under one housekeeping number keeps the feature segments
  clean and gives the cleanup a place to live.
- **No dependencies, no dependents.** Can interleave at any
  cadence. Best landed *before* Segment 14B (email infrastructure)
  adds its route-heavy bulk — both tracks pay off more the
  earlier they land.
- Mirrors the 17A precedent: a single housekeeping segment
  collected from the codebase-assessment watch list, landed as a
  short sequence of small focused PRs.

## PR sequence

| PR | Track | Title | Depends on |
|---|---|---|---|
| 1 | A | Align reviewer-surface page-validity check between GET and POST save | — |
| 2 | B | Split `services/instruments/_instrument_crud.py` into per-concern slices | — |
| 3 | B | *(optional)* Carve route slices out of `routes_operator/_instruments.py` | — |

The two tracks are independent. PR 1 is small enough to land
first as a warm-up; PR 2 is the substantive item. PR 3 is
discretionary — land only if `routes_operator/_instruments.py`
keeps growing through 14B.

Each PR ships with a passing full `pytest` run on the session
container, and `ruff check` clean. A split that needs test edits
beyond import-path fixes is a signal the split was not purely
structural — stop and reconsider rather than editing behaviour
tests.

## Track A — Defensive-asymmetry alignment (1 PR)

From the 28may assessment §5. The reviewer surface's GET and
POST save handlers disagree on how to handle the "empty pages
list" edge case:

- **GET** (`routes_reviewer/_surface.py:784`):
  ``page_count = len(pages) or 1`` — clamps an empty session to
  page 1.
- **POST save** (`:993`): ``if page_n < 1 or page_n > len(pages)
  → 404`` — hard-fails the empty case.

The asymmetry is currently unreachable in production because
``_require_session_accepting`` at ``:987`` 403s first whenever
there are no assignments (which an empty session always
implies), but the defensive shape is inconsistent and would mask
a real bug if the upstream guard ever changed. Landing this
before any 14B / 21 work touches the surface keeps the audit
trail clean.

**PR 1 — Align the two checks.** Pick one direction (proposed:
tighten the GET to match the POST's hard check, since
``_require_session_accepting`` already guarantees the empty
case can't reach either handler) and lift the page-validity
logic into one helper called from both routes. The helper
returns the validated ``page_n`` or raises 404; both routes
call it after the ``_require_session_accepting`` gate. Add a
focused integration test asserting the empty / out-of-range
behaviour on both methods so the asymmetry can't drift back.

Out of Track A's scope:

- Any reshape of ``_require_session_accepting`` or the rest of
  the GET / POST gating stack. The defensive consistency fix
  is small; broader refactors don't belong here.
- Any behaviour change beyond the alignment.

## Track B — File splits

From the 28may assessment §5. Current state:

- **15 files past 800 LOC** (up from 13 on 19may).
- **6 files past 1,150 LOC** (up from 4 on 19may).
- Largest file is now ``app/services/instruments/_instrument_crud.py``
  at **1,928 LOC** — the 18J takeover consolidated several
  previously-split flows; 18K added the ``acknowledged_drop``
  guard + ``validation`` dual-write; 18M added the page-break
  + reorder helpers.

The split precedent is the 17A track A (operator-routes /
session-config-io splits) and the May 9 packaging of
``instruments.py`` / ``views.py``. Each split is pure
structure — move code, keep the public import surface stable
(``from app.services.instruments import ...`` keeps working via
``__init__.py`` re-exports).

**PR 2 — Split ``services/instruments/_instrument_crud.py``
(1,928 LOC) into per-concern slices.** The file has clear
groupings already (see the per-section anchors in the file
itself):

- **Keep in ``_instrument_crud.py``** (~700 LOC after the split):
  the basic per-instrument CRUD — ``ensure_default_instrument``,
  ``ensure_locked_display_fields``, ``create_instrument``,
  ``replicate_instrument``, ``delete_instrument``,
  ``update_instrument_description``, ``update_short_label``,
  ``is_configured``, ``has_unconfigured``, ``has_unpinned``,
  ``pin_rule_set``, plus the Band 1 group / unit-of-review
  helpers (``encode_group_kind``, ``decode_group_kind``,
  ``set_group_boundary``, ``set_unit_of_review``) and
  ``set_column_widths``. These read as the "what is an
  instrument and how does the operator manipulate it" core.
- **Carve into ``_band2.py``** (~550 LOC): the Band 2 state
  save path — ``set_band2_state``, ``_sync_response_fields_to_db``,
  ``_sync_display_field_visibility``, ``_band2_parse_float``,
  ``_validate_response_field_shape``, ``_band2_unique_field_key``,
  the ``_BAND2_*`` constants. This is the densest concern in
  the file and the natural break point.
- **Carve into ``_pagination.py``** (~250 LOC): the 18M
  ordering + page-break helpers — ``_ordered_instruments``,
  ``reorder_instruments``, ``create_page_break_after``,
  ``clear_page_break``. Clean self-contained block at the
  bottom of the current file.
- **Carve into ``_bulk_toggles.py``** (~125 LOC, optional):
  ``bulk_set_accepting``, ``bulk_set_visibility``. Standalone
  helpers used only by the operator Instruments page's bulk-
  action card; pull them out only if the post-split
  ``_instrument_crud.py`` is still over ~1,000 LOC.

The ``__init__.py`` re-exports the public surface so callers
keep writing ``from app.services.instruments import
set_band2_state`` (etc.) unchanged. The private helpers
imported across slices (``_instrument_label``,
``_BAND2_DATA_TYPE_TO_INLINE``) move into ``_state.py`` or
the new slice that's their primary owner; cross-slice imports
land via ``from app.services.instruments._state import …``,
matching the existing intra-package convention.

**PR 3 (optional) — Carve route slices out of
``routes_operator/_instruments.py`` (1,497 LOC).** This file
already had a major split in 17A; it has crept back up
because 18K added the ``band2-state`` route's
``acknowledged_drop`` handling, 18M added the page-break
create / delete routes, and 18J added the identity / preview-
sample endpoints. Candidate splits:

- ``_band2_state.py`` — the ``band2-state`` /
  ``preview-sample`` / ``column-widths`` routes (the API
  surface of the Band 2 save UX).
- ``_pagination.py`` — the page-break + reorder routes.

Only land this PR if the file is still over ~1,200 LOC after
PR 2 lands (PR 2 won't shrink it directly but may surface
opportunities for view-layer adapters that move logic out of
the route). Otherwise defer to a future housekeeping pass.

Out of Track B's scope:

- ``app/services/responses.py`` (1,444 LOC) and
  ``app/services/assignments.py`` (1,222 LOC) — both cohesive
  single concerns; their growth is core-domain, not accretion.
  Not splitting now.
- ``app/services/scheduled_events.py`` (1,231 LOC) — 18G's
  lazy-observer dispatch; will likely grow further once 14B
  wires the email-send side. Defer until then so the split
  can account for the additional code.
- ``app/web/routes_reviewer/_surface.py`` (1,271 LOC) — large
  but cohesive (one route's full GET + POST stack); splitting
  it sensibly requires lifting the ``_surface_context``
  builder into ``app/web/views/`` first, which is a bigger
  move than this segment scopes.
- Any behaviour change, new feature, new route, or new model.

## Done when

- The reviewer surface's empty-pages handling is consistent
  between GET and POST save, gated by one helper, and pinned
  by an integration test.
- No ``app/`` production file is over ~1,200 LOC without a
  deliberate reason (PR 2 brings ``_instrument_crud.py`` from
  1,928 → ~700; PR 3 if landed brings
  ``routes_operator/_instruments.py`` to similar).
- No behaviour change: the test suite passes unchanged across
  every PR.

## Sequencing

PRs 1 and 2 are mutually independent and can land in any
order. PR 3 is gated on PR 2's outcome (only land if the
operator-routes file is still oversized). Best landed before
14B Part A so the split files absorb the email-wiring code in
their post-split shape rather than getting absorbed into a
pre-split monolith.

The full suite passes on every PR — no behaviour drift, no
test-shape edits beyond import-path fixes.

## Related context

- ``guide/codebase_assessment_28may.md`` §5 — the source of
  both watch items.
- ``guide/archive/codebase_assessment_19may.md`` §5 — flagged
  file-size creep as a watch item; this segment closes the
  follow-up.
- ``guide/archive/segment_17A_housekeeping.md`` — precedent
  for the file-split shape and the "small focused PRs under
  one housekeeping segment" pattern.
- ``guide/archive/major_refactor.md`` — the May 9 package
  splits this segment extends.
- ``CLAUDE.md`` — operator-route + service-package
  conventions Track B follows.
