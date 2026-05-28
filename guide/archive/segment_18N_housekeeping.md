# Segment 18N — Housekeeping (file splits + reviewer-surface asymmetry + settings round-trip)

**Status:** Stub created 2026-05-28. Sources: the
[2026-05-28 codebase assessment](codebase_assessment_28may.md) §5
"Weaknesses" — file-size creep, and the defensive code asymmetry
between the reviewer surface GET and POST save handlers — plus a
2026-05-28 catch-up item the user surfaced after the assessment
landed: the session-settings export / import round-trip is
missing every column Segment 18G added (a Zip-all → import
silently drops scheduled activation, invite + reminder offsets,
archive / release schedule, retention exception + overrides).
The file-size creep was flagged on the 19may assessment as a
watch item; the 28may assessment escalates it. Mirrors the
[18D](archive/segment_18D_export_and_import_update.md) "catch-up
pass on the export / import surface" pattern for Track C.

The "18N" number follows the 18-family sequence after 18M; no
prior 18N existed. It is **not** related to the 17A housekeeping
segment beyond following the same pattern (small focused PRs
under one housekeeping number).

## Goal

Structural / consistency cleanup plus an export / import catch-up
pass — **no new features, no new routes or models**. Tracks A
and B are pure structural (no behaviour change); Track C closes
a real round-trip gap surfaced after 18G shipped its scheduled-
event columns. Three independent tracks; each PR small and
reviewable, each landable on its own.

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

| PR | Track | Title | Status |
|---|---|---|---|
| 1 | A | Align reviewer-surface page-validity check between GET and POST save | **shipped** PR #1556 |
| 2 | B | Split `services/instruments/_instrument_crud.py` into per-concern slices | **shipped** PR #1557 |
| 3 | B | Carve route slices out of `routes_operator/_instruments.py` | **shipped** PR #1558 |
| 4 | B | Split `services/responses.py` into `_core` + `_group_reconciliation` | **shipped** PR #1559 |
| 5 | C | Settings round-trip: serialise + apply every operator-input column the export was silently dropping (scope widened from 8 18G fields to the full audit set) + regression tests | **in flight** |

The three tracks are independent. PR 1 is small enough to land
first as a warm-up; PR 2 is the substantive structural item;
PR 4 is the substantive functional catch-up. PR 3 is
discretionary; PR 5 is the test gate for PR 4.

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

## Track C — Settings round-trip catch-up

Segment 18G shipped eight new ``ReviewSession`` columns
covering the scheduled-event story (``scheduled_activate_at`` /
``responses_release_at`` anchors, ``invite_offsets`` /
``reminder_offsets`` / ``archive_offset`` /
``release_until_offset`` offsets, ``retention_exception`` /
``retention_overrides`` retention). Quick Setup (``_quick_setup.py``)
and the Edit Session Details form (``_session_home.py``) write
to them; the schedule-aware UI surfaces (Workflow card,
Manage-Invitations captions, Schedule timeline preview) read
them; the lazy-observer dispatch fires off them. But the
session-config export / import surface
(``app/services/session_config_io/_serialize.py:_session_rows``
at lines 85-122, plus the apply path at
``app/services/session_config_io/_apply.py``) was last touched
under Segment 18D (2026-05-17) — pre-18G — and emits only seven
Section-1 rows: ``name`` / ``code`` / ``description`` /
``display_timezone`` / ``deadline`` / ``help_contact`` /
``self_reviews_active``. Every 18G column is silently dropped
on round-trip.

Concrete user-visible loss: an operator who configures a
session through Quick Setup (or Edit Session Details), then
clicks "Zip all" to bundle it for a colleague, then has the
colleague import the bundle into a fresh session, **loses every
scheduled-event configuration in the round-trip**. The
imported session boots with all 18G columns NULL — no
scheduled activation, no auto-send invites or reminders, no
archive / release schedule, no retention rules. The lazy-
observer dispatch then doesn't fire because the anchors and
offsets are gone.

Mirrors the [18D](archive/segment_18D_export_and_import_update.md)
catch-up pass on the export / import surface, scoped narrowly to
the 18G slot.

**PR 4 — Serialise + apply the 18G ``ReviewSession`` columns.**
Extend ``_session_rows`` in ``_serialize.py`` to emit the eight
18G columns alongside the existing seven. Each row uses the
typed-cell helper that matches the column shape:

- ``session.scheduled_activate_at`` / ``session.responses_release_at``
  — ``datetime`` rows, formatted with ``iso_in_zone`` against
  the resolved session timezone (mirrors ``session.deadline``).
- ``session.invite_offsets`` / ``session.reminder_offsets`` —
  ``string`` rows carrying the comma-joined offset list (the
  same shape the Quick Setup + Edit Session forms accept),
  empty when the column is NULL.
- ``session.archive_offset`` / ``session.release_until_offset``
  — ``string`` rows.
- ``session.retention_exception`` — ``boolean`` row.
- ``session.retention_overrides`` — ``json`` row (open-ended
  key set; the Section-1 reader handles ``json`` via the
  ``_json`` typed-cell helper).

Extend ``_apply.py``'s session-section reader to round-trip
each, parsing strings through the same ``parse_and_validate_*``
helpers in ``app/services/scheduled_events.py`` that Quick Setup
+ Edit Session Details already call (so invalid imported
offsets fail with the same operator-facing message they'd see
on a direct edit). Invalid datetime / offset / JSON values fail
the apply with the existing ``_ParseError`` shape; a partial
apply rolls back.

Zip-all integration is automatic — ``app/services/extracts/zip_bundle.py``
calls ``serialize_session_config`` for the settings.csv member,
so adding the rows on the serialize side lights up the bundle
without a separate touch.

**PR 5 — Round-trip regression test.** New
``tests/integration/test_session_config_round_trip_scheduled_events.py``
that:

1. Boots a fresh session via Quick Setup with every 18G column
   populated (a scheduled activation in 24h, two invite offsets,
   three reminder offsets, archive + release offsets, retention
   exception true, retention overrides with a JSON dict).
2. Calls ``serialize_session_config`` and asserts every 18G row
   appears in the expected typed-cell shape.
3. Calls ``apply_session_config`` against a *fresh* session
   with the serialised rows and asserts every column matches
   the original.
4. Also exercises the Zip-all path
   (``zip_bundle.build_session_bundle``) to confirm the
   settings.csv member contains the rows end-to-end.

Pin the test alongside the existing
``test_session_config_round_trip*`` test files so the doc-trail
is obvious.

Out of Track C's scope:

- Any change to Quick Setup's editor surface or to Edit Session
  Details. Both already accept the 18G columns; the gap is
  only on the export / import side.
- Any change to the ``scheduled_events.py`` parsers /
  validators. Track C uses them as-is.
- The Responses-flavour column + retention CSV columns 18D
  flagged as consumer-blocked. Those ride with 13C and 18G
  Part 4 (or the 18G Part 4 carve-out follow-on); not this
  segment.
- Reflowing the existing 18D Section-1 row order. Append the
  new rows after ``self_reviews_active`` so existing exports
  parse cleanly under the importer's positional-then-keyed
  contract.

## Done when

- The reviewer surface's empty-pages handling is consistent
  between GET and POST save, gated by one helper, and pinned
  by an integration test.
- No ``app/`` production file is over ~1,200 LOC without a
  deliberate reason (PR 2 brings ``_instrument_crud.py`` from
  1,928 → ~700; PR 3 if landed brings
  ``routes_operator/_instruments.py`` to similar).
- A Quick Setup → Zip-all → import round-trip preserves every
  18G ``ReviewSession`` column, pinned by a regression test.
- No behaviour change on Tracks A and B; the test suite passes
  unchanged. Track C ships its own regression test; the
  pre-existing suite still passes unchanged across the apply
  path (the new rows are additive and the existing readers
  ignore unknown keys).

## Sequencing

PRs 1, 2, and 4 are mutually independent and can land in any
order. PR 3 is gated on PR 2's outcome (only land if the
operator-routes file is still oversized). PR 5 is the test
gate for PR 4 and lands paired with it (or immediately after).

Best landed before 14B Part A so the split files absorb the
email-wiring code in their post-split shape rather than getting
absorbed into a pre-split monolith, **and** so a 14B-configured
session can already round-trip its email-related settings cleanly
(Track C's PR 4 + PR 5 establish the catch-up cadence 14B can
extend).

The full suite passes on every PR — no behaviour drift, no
test-shape edits beyond import-path fixes on Tracks A / B.

## Related context

- ``guide/codebase_assessment_28may.md`` §5 — source of
  Tracks A and B watch items.
- ``guide/archive/codebase_assessment_19may.md`` §5 — flagged
  file-size creep as a watch item; this segment closes the
  follow-up.
- ``guide/archive/segment_17A_housekeeping.md`` — precedent
  for the file-split shape and the "small focused PRs under
  one housekeeping segment" pattern.
- ``guide/archive/segment_18D_export_and_import_update.md`` —
  the prior catch-up pass on the export / import surface; Track
  C extends its pattern to cover the 18G slot.
- ``guide/archive/segment_18G_scheduled_events.md`` — defines
  every column Track C closes the round-trip for.
- ``guide/archive/major_refactor.md`` — the May 9 package
  splits this segment extends (Track B).
- ``CLAUDE.md`` — operator-route + service-package
  conventions Track B follows.
