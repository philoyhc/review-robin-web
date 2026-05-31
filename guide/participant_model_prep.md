# Participant-model prep — implementation phase audit

A bookkeeping audit of every schema and UI / code change called for
by `guide/participant_model_upgrade.md`, classified by
**implementation phase**:

1. **Schema** — additive migrations.
2. **UI placeholders** — empty operator / participant surfaces that
   establish layout and navigation without functionality.
3. **Wiring & logic** — services, route guards, helpers, validation,
   business rules; connects placeholders to real behavior.

Implementation flows **(1) → (2) → (3)** wherever the work allows.
Some items don't split cleanly (e.g. a CSV import flow or a per-cell
display branch ships with the wiring it depends on, not as a
placeholder); the classification records where each piece
*primarily* belongs.

This doc carries no rationale and no segment sequencing — see
`participant_model_upgrade.md` for both. The goal here is just
implementation sequencing.

## Markers

| Marker | Meaning |
|---|---|
| **✔** | **Candidate** — not yet on disk; can ship as inert prep ahead of its slice. |
| **✓ already exists** | **Done** — already pre-positioned (typically by an earlier segment); participant model just consumes. |
| **⚠** | **Partial / open question** — resolve before pre-positioning. |
| **✘** | **Cannot pre-position** — UI change, behavior change, or removal; ships with owning slice. |

---

## Phase 1 — Schema

Table / column additions and `EVENT_SCHEMAS` registrations. Mostly
inert additive migrations that land first.

| # | Change | Ref | Pre-position? | Notes |
|---|---|---|---|---|
| S1 | New `observers` table | §3.1 | ✔ | Single `tag_1` column. Empty until roster slice. |
| S2 | New `instrument_view_policies` table | §3.3 | ✔ | Empty until policy-authoring slice. |
| S3 | `sessions.opens_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Lands on `sessions.scheduled_activate_at` (18G Part 0a). The participant model consumes that column; no migration needed. |
| S4 | `sessions.responses_close_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Reuse `sessions.deadline` per §3.4 lean. No new column. |
| S5 | `sessions.results_open_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Lands on `sessions.responses_release_at` (18G Part 0a — pre-positioned inert *explicitly for the participant model*; see the inline comment in `app/db/models/review_session.py`). |
| S6 | `sessions.results_close_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Derived from `sessions.responses_release_at` (S5) + `sessions.release_until_offset` (18G Part 0b — ISO 8601 duration). Follows the 18G anchor + offset pattern; no separate absolute column. |
| S7 | `sessions.relationships_enabled` (Boolean, default FALSE) | §3.8 | ⚠ | Column ships inert ✔; **backfill** (existing-relationships → TRUE) must wait for the toggle slice or existing sessions lose the tab once UI reads the flag. |
| S8 | `sessions.observers_enabled` (Boolean, default FALSE) | §3.8 | ✔ | No backfill (no observer rows exist yet). |
| S9 | `reviewees.results_acknowledged_at` (DateTime tz, NULL) | §6 | ✔ | Per §6 leaning toward column over a `result_acknowledgements` table. |
| S10 | Register new event types in `EVENT_SCHEMAS` | §3.5 | ✔ | `instrument.view_policy_set`, `session.schedule_set`, `observer.added` / `.removed` / `.bulk_*`, `results.released`, `results.acknowledged`, `session.feature_toggled`. Allowlist entries only; no emission yet. |
| S11 | `reviewers.profile_link` (String(2000), NULL) | §3.9 | ✔ | Mirrors `reviewees.profile_link`. Column add pre-positions cleanly; the ~12-file surface mirror is Phase 3 wiring (W11). |

**Not added** (per §3.6): nothing on `assignments`; no `participants`
identity table.

**Already pre-positioned by Segment 18G Part 0** (see
`app/db/models/review_session.py`): `scheduled_activate_at`,
`responses_release_at`, `release_until_offset`, plus the anchor /
offset / retention scaffolding. The participant model consumes these
as-is — the entire §3.4 schedule story is already on disk and just
needs the slice that lights it up.

**Magic-link extension** (§4): the existing `invitations` table is
reviewer-keyed. Extending tokened landings to reviewees / observers
needs design before any Phase 1 work — polymorphic FK vs sibling
tables vs discriminator. Flagged as TBD.

---

## Phase 2 — UI placeholders

Empty, visible shells that establish surface area, layout, and
navigation. Inert by construction: no submission, no behavior. They
exist so operators / designers / participants can see where the
feature *will* live before any wiring lands.

A surface only qualifies as a Phase 2 placeholder if its inert form
is genuinely useful (visual review, layout validation, navigation
discovery). When the inert form would mislead users ("I clicked
'Add Observer' and nothing happened — is it broken?"), defer to
Phase 3.

| # | Placeholder | Ref | Notes |
|---|---|---|---|
| P1 | Empty Observers Setup page | §3.1 | Page renders with column headers + a "No observers yet" empty state. No add / import affordance. Operators see the page shape. |
| P2 | Band 3 visibility-policy card on the Instrument editor | §3.3 | Three audience rows (Reviewee / Peer reviewer / Observer) render with disabled toggles and a "Authoring coming soon" hint. |
| P3 | Session-schedule authoring card on Settings | §3.4 | Four datetime inputs render disabled, anchored at the 18G columns. Read-only display of any existing values. |
| P4 | Two-checkbox card on New Session form + Session Settings | §3.8 | Checkboxes render, default-unchecked. Submission persists silently to the S7 / S8 columns but the Setup nav doesn't yet read them — Phase 3 wires the gate. |
| P5 | Empty `/me/sessions/{id}/results` page | §5 | Reviewee landing renders "Your results will appear here when released." Gated on `require_reviewee_in_session` (which can be the no-op pre-position version from W2). |
| P6 | Empty `/me/sessions/{id}/collation` page | §5 | Observer landing renders the same shape with "Collation will appear here once released." |
| P7 | Role-pill column on the `/me/` lobby table | §5 | Column appears in the existing dashboard table; renders a single "Reviewer" pill on every row since the query is reviewer-only today. Phase 3 broadens the query and the column carries real values. |

Surfaces deliberately **not** in Phase 2 (defer to Phase 3 because
the inert form would mislead users):

- Quick Setup Observer slot — operators expect submission to work.
- `Acknowledge` button on /results — a non-functional button is
  worse than no button.
- Extract Setup observer shapes — a dropdown entry that 404s on
  download is confusing.
- Magic-link issuance affordance — a button that does nothing
  invites repeat clicks.

---

## Phase 3 — Wiring & logic

Services, helpers, route guards, validation, business rules, removals.
Lights up the placeholders.

| # | Item | Ref | Pre-position? | Notes |
|---|---|---|---|---|
| W1 | `is_email_identified(reviewee)` helper | §3.2 | ✔ | Pure code; ships as dead code in Phase 1 prep. |
| W2 | `require_reviewee_in_session` dependency | §4 | ✔ | Defined but unused until P5 / W17 lights it up. |
| W3 | `require_observer_in_session` dependency | §4 | ✔ | Defined but unused until P6 / W18 lights it up. |
| W4 | `app/services/participants.py` cross-role query | §5 | ✔ | Defined but unused until W19 broadens `/me/`. |
| W5 | `app/services/collation.py` service | §7 | ⚠ | Pure code can pre-position; rendering needs `instrument_view_policies` rows from W15. |
| W6 | Per-session toggle wiring | §3.8 | ✘ | Setup nav reads S7 / S8; route guards (404 when off); lock-on-data check on the Settings card; migration backfill `relationships_enabled = TRUE` for sessions with existing rows. |
| W7 | Visibility-policy resolver | §3.3 | ✘ | View-time join through `instrument_id` to `instrument_view_policies`. Drives what reviewees / observers see on W17 / W18. |
| W8 | Reviewee-reachability warning on Validate page | §3.3 | ✘ | Cross-cutting soft warning; calls W1. |
| W9 | Friendly-label retirement | §3.7 | ✘ | Removal — strip the rename affordance from Setup-Reviewers / Setup-Reviewees for fixed columns. Verify CSV-import header matching first. |
| W10 | Observer CSV importer + Setup-page table population + sort + friendly-label resolver | §3.1 | ✘ | The slice that turns P1 into a real Setup page. Mirrors the reviewer importer patterns. |
| W11 | Reviewer `profile_link` surface mirror | §3.9 | ✘ | One coordinated slice: services, CSV import/export, Setup-Reviewers template + route, Quick Setup, field labels, display fields, view adapter, tests. The column from S11 lights up only when this lands. |
| W12 | Quick Setup Observer slot submission | §3.8 | ✘ | Wired Quick Setup card surface; persists to `observers`. |
| W13 | Extract Setup observer shapes | §3.8 | ✘ | Observer roster CSV (and any later observer-specific extracts) become selectable when S8 = TRUE. |
| W14 | Session schedule authoring | §3.4 | ✘ | Wires P3's disabled inputs; persists to the 18G columns; integrates with the 18G scheduler. |
| W15 | Band 3 visibility-policy editor | §3.3 | ✘ | Wires P2's disabled toggles; persists to `instrument_view_policies`; emits `instrument.view_policy_set` audit events. |
| W16 | Reviewee results surface | §5 | ✘ | Wires P5: resolves visibility policy via W7, renders the collation in the policy's form, gates on the `results_open_at` window. |
| W17 | Observer collation surface | §5 | ✘ | Wires P6: resolves visibility policy via W7, filters by observer `tag_1`. |
| W18 | Unified `/me/` lobby cross-role query | §5 | ✘ | Wires P7's pill column with real data via W4; broadens the existing dashboard query. |
| W19 | `Acknowledge` flow | §6 | ✘ | Button + handler on /results; writes to S9; emits `results.acknowledged`; surfaces to operator. |
| W20 | Reviewee / observer email notifications | §6 | ✘ | Gated on Segment 14B. Results-ready notices, acknowledgement nudges. |
| W21 | Magic-link landing for reviewees / observers | §4 | ✘ | Blocked on the `invitations`-extensibility design call. |

---

## What could ship as a Phase 1 prep PR

Rolling up the ✔ rows across all three phases — these are the items
that can land *today* as one coordinated prep PR with zero
user-visible change:

- **Schema** — S1, S2, S8, S9, S10, S11 (all unconditionally inert).
  S3 / S4 / S5 / S6 are already on disk; no migration needed.
- **Wiring stubs** — W1, W2, W3, W4 (dead code, no callers yet).

That's roughly one Alembic migration + one helpers commit. Each
Phase 2 / Phase 3 slice then lights up a subset of these without
doing its own schema work.

## Items blocking the prep PR

| Block | What it needs |
|---|---|
| S7 backfill (W6) | Defer to the W6 toggle slice; the S7 column itself can pre-position now. |
| Magic-link schema shape | Design call on `invitations` extensibility (polymorphic FK vs sibling tables vs discriminator). Blocks W21 entirely. |

## Cross-references

- `guide/participant_model_upgrade.md` — full design rationale, schema
  details, and segment sketch.
- `guide/segment_14B_email_infrastructure.md` — notification dependency
  for W20.
- `guide/archive/segment_18G_scheduled_events.md` — scheduler that the
  §3.4 windows (S3–S6) ride on; W14 integrates with it.
- `spec/audience_and_identity_model.md` — update first when work
  begins.
