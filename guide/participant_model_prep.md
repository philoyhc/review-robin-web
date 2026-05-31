# Participant-model prep — pre-position audit

A bookkeeping audit of every schema and UI change called for by
`guide/participant_model_upgrade.md`, tagged by **whether it can
pre-position** as an inert change ahead of the slice that lights it up.

This doc carries no rationale and no segment sequencing — see
`participant_model_upgrade.md` for both. The goal here is just: how
much could ship today as a single "prep" PR that changes nothing
user-visible, leaving each feature slice to wire UI on top of
already-existing schema?

## What "pre-position" means

A change pre-positions when it can land **before** its owning slice
with zero user-visible effect:

- additive nullable / defaulted column → ✔
- new empty table → ✔
- new audit event-type registration in `EVENT_SCHEMAS` → ✔
- new dependency / helper / service stub (dead code) → ✔
- migration backfill on existing rows → ✘ (lights up behavior)
- UI affordance (template / route / nav change) → ✘
- removal of an existing UI affordance → ✘

## Schema changes

| # | Change | Ref | Pre-position? | Notes |
|---|---|---|---|---|
| S1 | New `observers` table | §3.1 | ✔ | Single `tag_1` column. Empty until roster slice. |
| S2 | New `instrument_view_policies` table | §3.3 | ✔ | Empty until policy-authoring slice. |
| S3 | `sessions.opens_at` (DateTime tz, NULL) | §3.4 | ✔ | NULL = today's manual-driven behavior. |
| S4 | `sessions.responses_close_at` (DateTime tz, NULL) | §3.4 | ⚠ | Open question (§9): may reuse existing `deadline` instead of adding this column. Resolve before pre-positioning. |
| S5 | `sessions.results_open_at` (DateTime tz, NULL) | §3.4 | ✔ | |
| S6 | `sessions.results_close_at` (DateTime tz, NULL) | §3.4 | ✔ | |
| S7 | `sessions.relationships_enabled` (Boolean, default FALSE) | §3.8 | ⚠ | Column ships inert ✔; **backfill** (existing-relationships → TRUE) must wait for the toggle slice or existing sessions lose the tab once UI reads the flag. |
| S8 | `sessions.observers_enabled` (Boolean, default FALSE) | §3.8 | ✔ | No backfill (no observer rows exist yet). |
| S9 | `reviewees.results_acknowledged_at` (DateTime tz, NULL) | §6 | ✔ | Per §6 leaning toward column over a `result_acknowledgements` table. |
| S10 | Register new event types in `EVENT_SCHEMAS` | §3.5 | ✔ | `instrument.view_policy_set`, `session.schedule_set`, `observer.added` / `.removed` / `.bulk_*`, `results.released`, `results.acknowledged`, `session.feature_toggled`. Allowlist entries only; no emission yet. |

**Not added** (per §3.6): nothing on `assignments`; no `participants`
identity table.

**Magic-link extension** (§4): the existing `invitations` table is
reviewer-keyed. Extending tokened landings to reviewees / observers
needs design before pre-positioning — polymorphic FK vs sibling
tables vs discriminator. Flagged as TBD, not pre-positionable as-is.

## UI changes

All UI changes ship with their owning slice — none pre-position. Listed
for audit completeness so the team can see the full surface.

| # | Change | Ref | Owning slice (sketch) |
|---|---|---|---|
| U1 | Observers Setup page (mirrors Reviewers) | §3.1 | Observer roster |
| U2 | Per-instrument visibility-policy editor (Band 3) | §3.3 | Visibility-policy authoring |
| U3 | Reviewee-reachability soft warning on Validate page | §3.3 | Visibility-policy authoring |
| U4 | Session-schedule authoring (Settings card) | §3.4 | Schedule authoring + 18G integration |
| U5 | Remove friendly-label rename for fixed roster columns | §3.7 | Friendly-label retirement |
| U6 | Two-checkbox card on New Session + Session Settings | §3.8 | Per-session feature toggles |
| U7 | Setup nav reads `relationships_enabled` / `observers_enabled` | §3.8 | Per-session feature toggles |
| U8 | Quick Setup surfaces Observer slot (when toggle on) | §3.8 | Per-session feature toggles |
| U9 | Extract Setup picks up observer shapes (when toggle on) | §3.8 | Per-session feature toggles |
| U10 | Reviewee results surface `/me/sessions/{id}/results` | §5 | Reviewee surface |
| U11 | Observer collation surface `/me/sessions/{id}/collation` | §5 | Observer surface |
| U12 | Unified `/me/` lobby — cross-role table + role pills | §5 | Unified participant landing |
| U13 | `Acknowledge` button on /results | §6 | Reviewee surface (or follow-up) |
| U14 | Reviewee / observer email notifications | §6 | Notifications (gated on Segment 14B) |
| U15 | Magic-link landing for reviewees / observers | §4 | Magic-link affordance |

## Helpers / dependencies / services (code, not schema)

| # | Item | Ref | Pre-position? |
|---|---|---|---|
| H1 | `is_email_identified(reviewee)` helper | §3.2 | ✔ — pure code, unused until validation slice |
| H2 | `require_reviewee_in_session` dependency | §4 | ✔ — defined but unused until reviewee surface |
| H3 | `require_observer_in_session` dependency | §4 | ✔ — defined but unused until observer surface |
| H4 | `app/services/participants.py` cross-role query helper | §5 | ✔ — defined but unused until lobby broadens |
| H5 | `app/services/collation.py` service | §7 | ⚠ — pure code can pre-position; rendering needs `instrument_view_policies` rows |

## What could ship as one prep PR

Rolling up the ✔ rows:

- **Schema** — S1, S2, S3, S5, S6, S8, S9, S10 (all unconditionally
  inert). Plus S4 / S7 once their open questions resolve.
- **Code** — H1, H2, H3, H4 (dead code, no callers yet).

That's roughly one Alembic migration + one helpers commit. Zero
user-visible change. Each subsequent feature slice then lights up a
subset of these without doing its own schema work.

## Items blocking the prep PR

| Block | What it needs |
|---|---|
| S4 (`responses_close_at`) | Decide §9 open question — reuse `deadline` or add column. |
| S7 backfill | Defer to the per-session-toggle slice; the column itself can pre-position now. |
| Magic-link schema shape | Design call on `invitations` extensibility (polymorphic FK vs sibling tables vs discriminator). |

## Cross-references

- `guide/participant_model_upgrade.md` — full design rationale, schema
  details, and segment sketch.
- `guide/segment_14B_email_infrastructure.md` — notification dependency.
- `guide/archive/segment_18G_scheduled_events.md` — scheduler the §3.4
  windows must ride on.
- `spec/audience_and_identity_model.md` — update first when work begins.
