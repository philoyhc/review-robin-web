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
| S1 | New `observers` table | §3.1 | ✓ shipped (#1678) | Single `tag_1` column. Empty until roster slice. |
| S2 | New `instrument_view_policies` table | §3.3 | ✓ shipped (#1678) | Empty until policy-authoring slice. |
| S3 | `sessions.opens_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Lands on `sessions.scheduled_activate_at` (18G Part 0a). The participant model consumes that column; no migration needed. |
| S4 | `sessions.responses_close_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Reuse `sessions.deadline` per §3.4 lean. No new column. |
| S5 | `sessions.results_open_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Lands on `sessions.responses_release_at` (18G Part 0a — pre-positioned inert *explicitly for the participant model*; see the inline comment in `app/db/models/review_session.py`). |
| S6 | `sessions.results_close_at` (DateTime tz, NULL) | §3.4 | ✓ already exists | Derived from `sessions.responses_release_at` (S5) + `sessions.release_until_offset` (18G Part 0b — ISO 8601 duration). Follows the 18G anchor + offset pattern; no separate absolute column. |
| S7 | `sessions.relationships_enabled` (Boolean, default FALSE) | §3.8 | ✓ shipped (#1678) | Backfill resolved to FALSE per operator call (no extant sessions populate Relationships). The toggle slice (W6) wires the Setup-nav gating. |
| S8 | `sessions.observers_enabled` (Boolean, default FALSE) | §3.8 | ✓ shipped (#1678) | No backfill needed. |
| S9 | `reviewees.results_acknowledged_at` (DateTime tz, NULL) | §6 | ✓ shipped (#1678) | Per §6 leaning toward column over a `result_acknowledgements` table. |
| S10 | Register new event types in `EVENT_SCHEMAS` | §3.5 | ✓ shipped (#1678) | `observer.created / .updated / .bulk_inactivated / .bulk_reactivated`, `observers.deleted_all`, `instrument.view_policy_set`, `session.schedule_set`, `session.feature_toggled`, `results.released`, `results.acknowledged`. Allowlist entries only; no emission yet. |
| S11 | `reviewers.profile_link` (String(2000), NULL) | §3.9 | ✓ shipped (#1678) | Mirrors `reviewees.profile_link`. Column shipped; the ~12-file surface mirror is Phase 3 wiring (W11). |

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
| P1 | Empty Observers Setup page | §3.1 | ✓ shipped (#1686, polish via #1687–#1692). Two-column page grid (Upload + Operator actions row above; full-width Observers table; Danger Zone half-width below). Observers table has 6 columns (select-checkbox / Name / Email / Tag1 / Status / Updated) with per-column sort; rendering reads `observers` directly so seeded rows display in place of the mock row. |
| P2 | Band 3 visibility-policy card on the Instrument editor | §3.3 | Three audience rows (Reviewee / Peer reviewer / Observer) render with disabled toggles and a "Authoring coming soon" hint. |
| P3 | Session-schedule authoring card on Settings | §3.4 | Four datetime inputs render disabled, anchored at the 18G columns. Read-only display of any existing values. |
| P4 | Two-checkbox card on New Session form + Session Settings | §3.8 | ✓ shipped (#1685 + #1705). Session Settings side via #1685 (User interface settings card on Session Edit Details: checkboxes inside the main edit form, dirty Save, persisted on submit, lock-on-data UI). New Session form side via #1705 (same card placed above the Quick Setup card; values flow through `SessionCreate` to `sessions.create_session` so the toggles persist on session creation). |
| P5 | Empty `/me/sessions/{id}/results` page | §5 | ✓ shipped (#1713). Mirrors the reviewer surface chrome — `<h1>{{ session.name }}</h1>` + inline caption "Results of the review" + the standard `rs-status-panel` description card. Gated on `require_reviewee_in_session` (W2). Mount-order note: registered before `_surface` in `routes_reviewer/__init__.py` so the catch-all `/me/sessions/{id}/{page_n}` doesn't swallow the literal `/results` segment. Role-navigator chips added in #1715. |
| P6 | Empty `/me/sessions/{id}/collation` page | §5 | ✓ shipped (#1713). Same shape as P5 with caption "Observer view of the session". Gated on `require_observer_in_session` (W3). Same mount-order rule as P5. Role-navigator chips added in #1715. |
| P7 | Role-pill column on the `/me/` lobby table | §5 | ✓ shipped (#1684); refined through this session's stream. Three CSS classes (`.pill-role-reviewer` blue / `.pill-role-reviewee` green / `.pill-role-observer` amber) under `body.ui-v2`. The dedicated Roles column was folded into the Session cell — pills now render on a second line directly beneath the session name (#1712) — and the cross-role query populating the pill list shipped via W18 (#1709). Session-name + per-pill links land on the appropriate role surface via the priority ladder Reviewer → Reviewee → Observer with per-role reachability gates (#1714). "View responses" + "Until" stay as placeholder em-dashes pending W16 / W17. |

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
| W1 | `is_email_identified(reviewee)` helper | §3.2 | ✓ shipped (PR 2) | Lives in `app/services/participants.py`. |
| W2 | `require_reviewee_in_session` dependency | §4 | ✓ shipped (PR 2) | Defined in `app/web/deps.py`; no route mounts it yet. |
| W3 | `require_observer_in_session` dependency | §4 | ✓ shipped (PR 2) | Defined in `app/web/deps.py`; no route mounts it yet. |
| W4 | `app/services/participants.py` cross-role query | §5 | ⚠ shape stub remains | `ParticipantSession` dataclass + `sessions_for_user` signature shipped; body still returns `[]`. W18 (#1709) shipped the union inline in `routes_reviewer/_dashboard.py` rather than through `participants.sessions_for_user`; the stub can be retired or back-filled to call the dashboard's path as a follow-up cleanup. |
| W5 | `app/services/collation.py` service | §7 | ⚠ | Pure code can pre-position; rendering needs `instrument_view_policies` rows from W15. |
| W6 | Per-session toggle wiring | §3.8 | ✓ shipped (#1685 + #1686) | Both flags wired end-to-end: Setup nav reads `relationships_enabled` / `observers_enabled` and conditionally renders the tabs; new `require_relationships_enabled_session` + `require_observers_enabled_session` route gates return 404 when the flag is off; lock-on-data check at the service layer rejects True→False flips when rows exist (so a direct API call can't bypass the disabled UI); `session.feature_toggled` audit event fires when either flag flips. No migration backfill — operator confirmed FALSE for all existing sessions per S7. |
| W7 | Visibility-policy resolver | §3.3 | ✘ | View-time join through `instrument_id` to `instrument_view_policies`. Drives what reviewees / observers see on W17 / W18. |
| W8 | Reviewee-reachability warning on Validate page | §3.3 | ✘ | Cross-cutting soft warning; calls W1. |
| W9 | Friendly-label retirement | §3.7 | ✓ shipped (#1680) | Reviewee identity slots (Name / Email_Identifier / Profile) dropped from the editor + Settings-CSV allowlist; alembic `c8d4e9f1a2b3` deletes persisted override rows. Reviewer side already had only tag slots — no change needed. |
| W10 | Observer CSV importer + Setup-page table population + sort + friendly-label resolver | §3.1 | ✓ shipped (#1706) | Turns P1 into a functional Setup page. `app/services/observers.py` carries `create_observer` / `update_observer` / `bulk_inactivate` / `bulk_reactivate` with `ObserverOperationError` and audit envelopes; `csv_imports.parse_observer_csv` + `save_observers` + `delete_all_observers` + `existing_observer_count` reuse the shared `_save` / `_delete_all` infra; `ObserverImportRow` lives in `app/schemas/imports.py`; `observers.imported` registered in `EVENT_SCHEMAS`; `OBSERVERS_STATUS_OPTIONS` / `filter_observers_rows` / `observers_search_options` in `app/web/views/_filters.py`; `_setup_observers.py` has the full route surface (page / create / update / bulk in-/reactivate / delete-all / import); template refit to live UI with Upload + Operator actions + preview table + Danger Zone. Single-tag observer keeps the friendly-label editor card out of scope. |
| W11 | Reviewer `profile_link` surface mirror | §3.9 | ⚠ partially shipped (#1680) | Quick Setup (CSV import via `parse_reviewer_csv` + `ReviewerImportRow`) and Extract Settings (`reviewers_extract.HEADER` + per-row serialize) wired. **Remaining:** services/reviewers create+update normalisation, Setup-Reviewers template + route, field labels default entry, display fields (label / CSV name / `ALLOWED_SOURCES` / seeding), view adapter, reviewer-summary cell styling. |
| W12 | Quick Setup Observer slot submission | §3.8 | ✘ | Wired Quick Setup card surface; persists to `observers`. |
| W13 | Extract Setup observer shapes | §3.8 | ✘ | Observer roster CSV (and any later observer-specific extracts) become selectable when S8 = TRUE. |
| W14 | Session schedule authoring | §3.4 | ✘ | Wires P3's disabled inputs; persists to the 18G columns; integrates with the 18G scheduler. |
| W15 | Band 3 visibility-policy editor | §3.3 | ✘ | Wires P2's disabled toggles; persists to `instrument_view_policies`; emits `instrument.view_policy_set` audit events. |
| W16 | Reviewee results surface | §5 | ✘ | Wires P5: resolves visibility policy via W7, renders the collation in the policy's form, gates on the `results_open_at` window. |
| W17 | Observer collation surface | §5 | ✘ | Wires P6: resolves visibility policy via W7, filters by observer `tag_1`. |
| W18 | Unified `/me/` lobby cross-role query | §5 | ✓ shipped (#1709, polish #1712 / #1714 / #1715) | The `/me` dashboard now unions three roster lookups (reviewer / email-identified reviewee / observer, active rows only, case-insensitive email match) and emits one row per session the user touches with the full role list. Reviewer-specific fields (per-reviewer pill, deep link, per-page sub-rows) populate only when the user is an active reviewer; reviewee / observer-only rows show "—" in the Reviewer status column. Session-name + per-pill links resolve by priority Reviewer → Reviewee → Observer with per-role reachability gates (#1714); pills fold into the Session cell (#1712); the same cross-role navigator chip strip appears on each role-specific surface so the user can swap roles without going back to `/me` (#1715). Lives inline in `_dashboard.py` for now — see W4 for the unfinished move into `participants.sessions_for_user`. |
| W19 | `Acknowledge` flow | §6 | ✘ | Button + handler on /results; writes to S9; emits `results.acknowledged`; surfaces to operator. |
| W20 | Reviewee / observer email notifications | §6 | ✘ | Gated on Segment 14B. Results-ready notices, acknowledgement nudges. |
| W21 | Magic-link landing for reviewees / observers | §4 | ✘ | Blocked on the `invitations`-extensibility design call. |

---

## What's shipped

- **Phase 1 schema + audit allowlist** (PR #1678) — S1, S2,
  S7, S8, S9, S10, S11. Alembic migration `b3e7d2a4c8f1`.
- **Phase 1 helper / dependency stubs** (PR #1679) — W1, W2,
  W3, W4 as dead code / shape-only.
- **§3.7 friendly-label retirement + §3.9 partial**
  (PR #1680):
  - W9 friendly-label retirement (reviewee identity slots
    retired; alembic `c8d4e9f1a2b3` drops persisted
    overrides).
  - W11 partial — Reviewer PhotoLink wired through Quick
    Setup (CSV import) + Extract Settings (CSV output).
    Remaining surface-mirror touchpoints listed inline on
    the W11 row.
- **`/me/` lobby cross-role layout** (PR #1684) — P7
  shipped. New columns + role-pill stack ready for the
  cross-role query (W18) to populate.
- **Per-session feature toggles — Session Settings side**
  (PR #1685) — P4 partial (Session Settings card fully
  wired) + W6 Relationships side.
- **Observers placeholder Setup page + nav gating**
  (PR #1686) — P1 shipped; W6 Observers side completes the
  toggle wiring.
- **Observers page polish** (PRs #1687 → #1692) — help-text
  styling alignment with Reviewers/Reviewees, button-style
  conventions, Upload-card column-list parity (ObserverTag1),
  full-width data-table layout, 6-column sortable table with
  mock row + select-checkbox + Updated column.
- **Card-spacing audit** (PRs #1693 → #1703) — diagnosed
  and resolved the doubled / mismatched inter-card gaps
  on Setup pages and Session Home; gaps now uniform 16px
  vertical / 20px horizontal across `.bottom-grid` /
  `.bottom-left` / `.extract-data-grid` / `.extract-data-column`.
- **Per-session feature toggles — New Session form side**
  (PR #1705) — P4 completed. Same User interface settings
  card from Session Edit Details placed above the Quick
  Setup card on the create form; `relationships_enabled` /
  `observers_enabled` flow through `SessionCreate` to
  `sessions.create_session` so the toggles persist at
  creation time.
- **Observers Setup page CRUD** (PR #1706) — W10 shipped.
  `app/services/observers.py` + `csv_imports` observer
  shapes + `ObserverImportRow` + `observers.imported` audit
  + filter/search helpers + full `_setup_observers.py`
  route surface; the page replaces P1's inert shell with
  Upload + Operator actions + preview table + Danger Zone.
- **`/me` cross-role union** (PR #1709) — W18 shipped.
  `_dashboard.py` unions the three rosters; reviewee /
  observer-only rows now appear on `/me` with their role
  pills; reviewer-specific columns gate on `pill is not None`.
- **Operator lobby owner-only access regression test**
  (PR #1710) — pins the contract: only SessionOperator
  members + sys-admins reach `/operator/*`; participant
  rosters never confer operator access.
- **`/me` polish stream** (PRs #1712, #1714, #1715) — folds
  the Roles column into the Session cell (#1712); adds
  role-aware + reachability-gated links from the
  session-name + per-pill anchors on `/me` (#1714); adds
  the role-navigator chip strip below the session-name
  header on every role-specific surface so the user can
  swap roles without going back to `/me` (#1715).
- **Reviewee + observer placeholder surfaces**
  (PR #1713) — P5 + P6 shipped. `/me/sessions/{id}/results`
  and `/me/sessions/{id}/collation` render the reviewer-
  surface chrome (header + inline caption + optional
  description card), gated by `require_reviewee_in_session`
  / `require_observer_in_session`. Real body content lands
  with W16 / W17.

Each subsequent Phase 2 / Phase 3 slice lights up a subset of
the Phase 1 schema without doing its own migration.

## Items still blocking later phases

| Block | What it needs |
|---|---|
| S7 backfill (W6) | Resolved — backfilled FALSE per operator call (no extant sessions populate Relationships); the W6 toggle slice now just wires Setup-nav gating + lock-on-data behavior on top of the column. |
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
