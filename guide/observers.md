# Observers — participant role + collation surface

Standing notes for the **observer** participant role: who they
are, the data model, the surfaces, and the wiring tail that's
still to ship.

## Status

**Paused 2026-06-01.** Operator-side observer plumbing is live
(roster Setup page, Quick Setup slot, Extract Setup row, bundle
inclusion, per-session enable toggle, friendly-label resolver,
visibility-policy column) but the participant-facing collation
surface (`/me/sessions/{id}/collation`) renders only the
placeholder chrome — no body. The body wiring is paused while
we rethink the **use scenarios**: what does an observer want
to see when they land on a session, how do they navigate
within it, and which sessions belong on their `/me` lobby vs.
need a different entry point?

This file is the home for any further observer-side work. When
the body wiring resumes, fold it into a `segment_22_observers.md`
plan and link from `guide/todo_master.md`'s Upcoming list.

## Where the wiring stands

What's shipped (live in production):

- **Schema** — `observers` table, `observer.*` audit events,
  `sessions.observers_enabled` toggle.
- **Roster** — Setup-Observers page (CRUD + bulk + delete-all
  + Upload + Operator-actions row + Danger Zone) shipped
  W10 / PR #1706.
- **Quick Setup Observers slot** — Session Home + new-session
  form both upload a CSV with the same shape as the Setup
  page (W12 / PR #1754). Renders only when
  `observers_enabled` is on.
- **Extract Setup Observers row + bundle** — per-row CSV
  download (`observers.csv`) + inclusion in the Zip-all
  bundle, gated on the same toggle (W13 / PR #1755).
- **Per-instrument visibility policy** — operators can
  author Raw / Anonymized / Summarized for the `observer`
  audience on each instrument's Band 3 visibility editor
  (W15 + the per-window mode pair columns from S14).
- **`/me/sessions/{id}/collation` placeholder route** — page
  renders the reviewer-surface chrome with the caption
  "Observer view of the session"; gated on
  `require_observer_in_session` (W3 / P6, PR #1713). No
  body content yet.
- **Cross-role lobby support** — observers appear on
  `/me/` with the amber `observer` role pill if they're on
  any session's roster (W18, polish through #1715). Their
  role-navigator chip strip links to `/me/sessions/{id}/collation`.

## What's still pending (re-evaluating)

Two items from the participant-model wiring inventory still
to ship; both paused with this file:

### W17 — Observer collation surface body

Source: `guide/archive/participant_model_upgrade.md` §7.

The placeholder route (P6) needs body content. Sketched
shape: a cross-reviewee collation table grouped by the
session's instruments, filtered to the reviewees whose
`tag_1` matches the observer's `tag_1` (the "scope" filter),
with cells resolved through `visibility_policies.resolve_mode`
(W7, shipped) per `(instrument, observer)` pair.

Open questions before this lands:

- **Scope filter semantics.** `tag_1` on the observer was
  picked as the cohort key in §3.1; needs validation against
  realistic use cases (does an observer always have one tag?
  what about observers who should see *every* reviewee?).
- **Default render mode for observers.** When the operator
  hasn't authored a per-instrument policy for the observer
  audience on a given instrument, should the cell render
  Summarized aggregates (the safest default) or stay empty?
- **Cross-reviewee aggregation.** The reviewee `/results`
  surface (W16) shows one row per reviewer of *this*
  reviewee. The observer surface needs to flip the axis —
  rows are reviewees, columns are some shape of reviewer-
  aggregate. The summarized-mode aggregate primitives from
  W16 carry over; the layout is the open piece.

### W5 — `app/services/collation.py` service

Source: `guide/archive/participant_model_upgrade.md` §7.

The supporting service module that W17's route would call
into. Bundled with W17 — no useful pre-positioning since
W17 is its sole consumer. Skeleton would be:

```
build_observer_collation_context(
    db, *, review_session, observer
) -> ObserverCollationContext
```

…paralleling `build_reviewee_results_context` (the W16
adapter). The W7 resolver + the per-data-type aggregation
helpers from W16's `_summarize_field` are the reusable
primitives.

## Cross-references

- `guide/archive/participant_model_upgrade.md` — design rationale +
  the full audience taxonomy (§3.1 observer scope, §7
  collation render shape).
- `guide/archive/participant_model_remainder.md` — outstanding
  participant-model items overall; observer-side items
  filed here once this stub took ownership.
- `spec/audience_and_identity_model.md` — authoritative
  audience taxonomy.
- `spec/setup_pages.md` — Observers Setup page contract.
- `app/services/visibility_policies.py::resolve_mode` —
  the resolver W17 calls.
- `app/web/views/_reviewee_results.py::_summarize_field` —
  the per-data-type aggregation primitives W5 will reuse.
