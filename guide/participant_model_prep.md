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
| S10 | Register new event types in `EVENT_SCHEMAS` | §3.5 | ✓ shipped (#1678; S12 add-ons shipped alongside the S12 migration) | `observer.created / .updated / .bulk_inactivated / .bulk_reactivated`, `observers.deleted_all`, `instrument.view_policy_set`, `session.schedule_set`, `session.feature_toggled`, `results.released`, `results.acknowledged`. Allowlist entries only; no emission yet. **S12 add-ons (shipped):** `session.responses_released` (snapshot — operator pressed Release-now; carries `responses_release_at` and a flag if a prior `responses_release_until` was cleared), `session.responses_release_stopped` (snapshot — operator pressed Stop-release; carries `responses_release_until` which the button has just stamped to `now()`). Buttons + emitters arrive with the Operations-row release controls slice. |
| S11 | `reviewers.profile_link` (String(2000), NULL) | §3.9 | ✓ shipped (#1678) | Mirrors `reviewees.profile_link`. Column shipped; the ~12-file surface mirror is Phase 3 wiring (W11). |
| S12 | Visibility-window axis — `instrument_view_policies.visible_when` (String(16), NULL) + `sessions.responses_release_until` (DateTime tz, NULL) replacing `release_until_offset` | §3.3 + §3.4 | ✓ shipped — Alembic `f4a92b3c6d18`; both columns land inert, W14 wiring rewired to the datetime; legacy validator + magnitude-cap helpers retired. | **`visible_when` (add).** Carries the per-(instrument, audience) window pick: `while_ongoing` (`[activated_at, deadline)`) / `after_release` (`[responses_release_at, responses_release_until)`) / `throughout` (union of the two) / `always` (reserved for operator, who isn't an audience row). Nullable; lands inert. Read by W7 (resolver), written by W15 (Band 3 editor). **`responses_release_until` (add) + `release_until_offset` (retire).** The Edit / Create form's "Release responses until (optional)" input becomes a `datetime-local` writing this absolute timestamp; the session-level **Stop release** button writes `responses_release_until = now()`; the **Release responses now** button writes `responses_release_at = now()` and clears `responses_release_until` so the window re-opens open-ended. Both buttons live on an Operations-row surface. Migration steps: add `responses_release_until` nullable; for any row where `release_until_offset IS NOT NULL` and `responses_release_at IS NOT NULL`, write `responses_release_until = responses_release_at + parse_iso_duration(release_until_offset)`; **for offset-only rows** (`release_until_offset IS NOT NULL` and `responses_release_at IS NULL` — allowed today by the W14 validator under the §8.2.2 anchor-null rule), drop the staged offset silently — `responses_release_until` stays NULL since there is no anchor to compute the close datetime against, and the new model has no inert-offset shape to carry it through. Operators who had staged an offset alone re-enter a close datetime on the form after the migration; documented in `guide/participant_model_upgrade.md` §3.4. Drop `release_until_offset`. View-time predicate: *release window is open* ⇔ `responses_release_at IS NOT NULL` AND `now() ≥ responses_release_at` AND (`responses_release_until IS NULL` OR `now() < responses_release_until`). Archive forces zero visibility for non-operator audiences at view time — no schema change. Replaces W14's offset shape (PR #1716) — the W14 wiring is the only writer / reader of `release_until_offset`, so the swap is contained; the existing `parse_and_validate_release_until_offset` validator + 365-day magnitude cap retire (the cap moves to a soft "until must be within 365 days of `responses_release_at`" check on the datetime path if we want to keep it). |
| S13 *(parked candidate)* | `instrument_view_policies.peer_scope` (String(16), NULL) — `self` / `all`; NULL ≡ strict default `self` | §3.3 | ✘ parked — design decision in `guide/participant_model_upgrade.md` §3.3 "Scope of the visibility policy" defers this in favour of an Operator- / Observer-published report mechanism. | Would carry the per-policy-row "Self only / All peers" toggle for the `peer_reviewer` audience (reviewer viewing peers' work on the same reviewee). Nullable so existing rows don't need a backfill; the resolver treats `NULL` ≡ `"self"` so today's strict default holds. Only meaningful when `audience == "peer_reviewer"`; service rejects non-NULL on `reviewee` / `observer` rows (mirrors the `observer_tag` rule). Sketched here for traceability if the cohort-aggregate use case ever steers us back to a per-instrument toggle rather than a published-report mechanism — not actively in design today. |
| S14 | `instrument_view_policies` per-window mode pairs — `while_ongoing_granularity` + `while_ongoing_identification` + `after_release_granularity` + `after_release_identification` (each `String(16)`, NULL); legacy `enabled` / `granularity` / `identification` / `visible_when` quadruple retired | §3.3 | ✓ shipped — expand `a7e3b1d92c64`, read-path swap #1730, contract `b8f4c2a91d35` drops the legacy quadruple. | Splits the legacy single-mode + window-axis encoding into two **window-specific mode pairs** so the editor's column axis can be the window ("Session ongoing" / "Responses released") instead of the mode. Each pair encodes the audience's mode in that window; `NULL` ≡ "off in this window". `(aggregated, identified)` stays reserved-incoherent. Shipped in three PRs: (i) expand — Alembic `a7e3b1d92c64` adds the four pair columns + backfills from the old quadruple; (ii) PR B/C (#1730) flips service + route + view + template over to read / write the pair columns while mirror-writing the legacy quadruple for rollback safety; (iii) contract — Alembic `b8f4c2a91d35` drops `enabled` / `granularity` / `identification` / `visible_when`. Downgrade on the contract step re-adds the columns and best-effort backfills from the pair state. |

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
| P2 | Band 3 visibility-policy card on the Instrument editor | §3.3 | ✓ shipped (#1656) → lit up by W15 below. The placeholder card was a 4-row × 2-axis (What / When) chip grid with an explicit "Operator" row and toggleable Reviewees / Observers rows; W15 + S14 replaced it with the per-window-axis 3 × 2 grid (Reviewers / Reviewees / Observers × Session-ongoing / Responses-released) that now lives on the Instruments page (`instruments_index.html`, see W15). The Operator row is gone — Operator visibility is the implicit baseline, not a stored row. |
| P3 | Session-schedule authoring card on Settings | §3.4 | ✓ shipped (#1656). Lives on the Session Edit Details page (`session_edit.html`) and the New Session form (`session_new.html`) as the right-hand column of the Edit Session Details card — six inputs in a 2-col sub-grid: Start (`scheduled_activate_at`) + End (`deadline`) + Release-responses-from (`responses_release_at`) in the left sub-column; Auto-send-invites (`invite_offsets`) + Auto-send-reminders (`reminder_offsets`) + Release-responses-until (`release_until_offset`) in the right. Note: the two operator-platform datetime fields (Start + End) ship fully wired since Segment 18G, and the two offset inputs since 18G Parts 2/3 — only the two participant-platform fields (`responses_release_at`, `release_until_offset`) render `disabled` with the "Participants platform" placeholder hint. W14 unlocks those two and persists them onto the existing 18G columns. |
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
| W7 | Visibility-policy resolver | §3.3 | ✓ shipped (alongside W15) | `app/services/visibility_policies.py::resolve_mode` takes the persisted policy row + the two window-open booleans (`while_ongoing_open` / `after_release_open`) and returns the operator-facing mode (`"raw"` / `"anonymized"` / `"summarized"` / `None`). After-release wins when both windows are open. Consumed by W16 (reviewee `/results`) and the future W17 (observer `/collation`). |
| W8 | Reviewee-reachability warning on Validate page | §3.3 | ✓ shipped (PR #1758) | Cross-cutting soft warning; calls W1's `is_email_identified`. New rule `reviewees.unreachable_for_results` with `severity=warning` (non-blocking — anonymous-identifier sessions are a legitimate use case); check counts active reviewees with non-email identifiers and emits one umbrella issue with the count + a fix link to Reviewees Setup anchored at the first offending row. Mapped under the Setup gate. |
| W9 | Friendly-label retirement | §3.7 | ✓ shipped (#1680) | Reviewee identity slots (Name / Email_Identifier / Profile) dropped from the editor + Settings-CSV allowlist; alembic `c8d4e9f1a2b3` deletes persisted override rows. Reviewer side already had only tag slots — no change needed. |
| W10 | Observer CSV importer + Setup-page table population + sort + friendly-label resolver | §3.1 | ✓ shipped (#1706) | Turns P1 into a functional Setup page. `app/services/observers.py` carries `create_observer` / `update_observer` / `bulk_inactivate` / `bulk_reactivate` with `ObserverOperationError` and audit envelopes; `csv_imports.parse_observer_csv` + `save_observers` + `delete_all_observers` + `existing_observer_count` reuse the shared `_save` / `_delete_all` infra; `ObserverImportRow` lives in `app/schemas/imports.py`; `observers.imported` registered in `EVENT_SCHEMAS`; `OBSERVERS_STATUS_OPTIONS` / `filter_observers_rows` / `observers_search_options` in `app/web/views/_filters.py`; `_setup_observers.py` has the full route surface (page / create / update / bulk in-/reactivate / delete-all / import); template refit to live UI with Upload + Operator actions + preview table + Danger Zone. Single-tag observer keeps the friendly-label editor card out of scope. |
| W11 | Reviewer `profile_link` surface mirror | §3.9 | ⚠ partially shipped (#1680 + #1756); two touchpoints parked | Shipped: Quick Setup CSV import (`parse_reviewer_csv` + `ReviewerImportRow`, #1680), Extract Settings (`reviewers_extract.HEADER` + per-row serialize, #1680), services/reviewers create + update normalisation, Setup-Reviewers template + route, field labels default entry (`("reviewer", "profile_link"): "Profile"`), preview-table column visibility (mirrors Reviewees: hidden when no row has data, visible in edit mode or when at least one row carries a link) — all in PR #1756. **Parked (different design call):** display-fields `ALLOWED_SOURCES` / seeding (the display-fields system is reviewer-form-facing and shows reviewee data; reviewer `profile_link` doesn't naturally fit there), operator-side reviewer-summary cell styling (separate slice once that surface is in scope). |
| W12 | Quick Setup Observer slot submission | §3.8 | ✓ shipped (PR #1754) | Right column on the Quick Setup card reads Relationships → Observers → Session settings when `observers_enabled` is on; collapses back to Relationships → Session settings when off. `_split` formula flipped from `(length + 1) // 2` to `length // 2`. New `POST /operator/sessions/{id}/quick-setup/observers` route mirrors the Relationships slot — file-upload mode, `confirm_replace` on existing rows, lifecycle gate on Activated, no response-loss ack. `submit-all` + the create-session POST both pick up an `observers_file` parameter + the matching dispatcher branch. |
| W13 | Extract Setup observer shapes | §3.8 | ✓ shipped (PR #1755) | New `observers_extract.py` serialiser (column shape `ObserverEmail` / `ObserverName` / `ObserverTag1` / `Status` — round-trips with the Quick Setup slot + the Observers Setup-page upload). New `GET /operator/sessions/{id}/export/observers.csv` route + `session.observers_extracted` audit event registered in `EVENT_SCHEMAS`. Extract Setup card's right column gains the Observers row between Relationships and Session settings when the toggle is on; the Zip-all bundle picks up an `{code}_observers.csv` member. |
| W14 | Session schedule authoring | §3.4 | ✓ shipped (anchor wired in PR #1716; close re-shaped to datetime by S12) | Wires P3's two disabled inputs: `responses_release_at` (datetime-local, parsed via `scheduled_events.parse_and_validate_responses_release_at` — no minimum-lead floor since the operator can backdate Release-from) + `responses_release_until` (datetime-local, parsed via `scheduled_events.parse_and_validate_responses_release_until` — must close after the anchor, within 365 days, when both are set; accepts an until alone under §8.2.2). Both fields ride on `SessionCreate` end-to-end through `sessions.create_session` / `sessions.update_session`, with the latter diffing them for `session.updated` audit emission. The Edit form prefills both via `responses_release_at_input_value` / `responses_release_until_input_value`. S12 retired the original ISO 8601 offset shape (`release_until_offset`, `parse_and_validate_release_until_offset`); the Settings-CSV slot followed (`session.responses_release_until` as a datetime, replacing the string). |
| W15 | Band 3 visibility-policy editor | §3.3 | ✓ shipped (editor + transparency surfaces; resolver W7 + consumer surfaces W16 / W17 still pending) | Editor + persistence + reviewer-surface transparency shipped end-to-end across multiple PRs:<br>• **Service** — `app/services/visibility_policies.py` carries `encode_mode` / `decode_mode` (operator-facing modes Raw / Anonymized / Summarized ↔ the stored `(granularity, identification)` pairs), `_PER_CELL_VALID_MODES` + `valid_modes_for_cell` (per-(audience, window) vocabulary including the fixed cells: Reviewer Session-ongoing pinned to Raw, Reviewee Session-ongoing pinned to off), and `upsert_policy` / `upsert_many` emitting `instrument.view_policy_set` per row touched.<br>• **Schema reshape** — S12 (Alembic `f4a92b3c6d18`) added the `visible_when` window axis + the `responses_release_until` close datetime; S14 (Alembic `a7e3b1d92c64` expand + `b8f4c2a91d35` contract) replaced the single-mode `enabled` / `granularity` / `identification` / `visible_when` quadruple with four per-window pair columns (`while_ongoing_granularity` / `while_ongoing_identification` / `after_release_granularity` / `after_release_identification`); NULL in both members ≡ "off in this window".<br>• **Persistence path** — visibility hidden inputs ride the card's main Save form via `form="dfsave-<id>"`; `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/save` reads the six per-(audience, window) form fields alongside the rest of the card's state and calls `upsert_many` (the standalone `/view-policy` POST + "Save visibility" submit retired in PR #1733). The chip click fires the dirty tracker so Save flips active (PR #1734).<br>• **Editor template** — the Band 3 block on `instruments_index.html` renders a 3-row (Reviewers / Reviewees / Observers) × 2-window-column (Session ongoing / Responses released) chip grid. Static pills mark the fixed cells; the remaining four cells cycle through their per-cell valid modes. The Operator row is gone — Operator is the implicit baseline.<br>• **Reviewer-surface transparency card** — read-only "Who can see what you wrote (other than admin)" card lands in the per-instrument intro grid on `review_surface.html`, mirroring the persisted policy for two non-admin audiences (You / Reviewees). Observers are intentionally omitted. PR #1733 adds the matching preview alongside the description card in the operator's Band 2 intro grid (`band2_preview_visibility_rows_by_instrument`). PR #1734 renames the `summarized` mode's display label to "Anonymized summaries" everywhere it surfaces.<br>• **View adapter** — `build_instruments_context` carries `band3_visibility_by_instrument` (the editor's per-audience state) + `band2_preview_visibility_rows_by_instrument` (the Band 2 preview rows). `build_reviewer_visibility_rows` is the shared builder for both the reviewer surface and the operator's Band 2 preview.<br>• **PR trail** — #1656 (P2 placeholder), #1728 (W15 persistence — service / route / template, single-mode encoding), #1724 (S12 — `visible_when` + `responses_release_until`), #1729 (S14 expand — per-window pair columns), #1730 (read-path swap to per-window pairs + UI redesign), #1731 (S14 contract — drop legacy quadruple), #1732 (reviewer transparency card), #1733 (card-Save consolidation + Band 2 preview + Observers row drop on the reviewer surface), #1734 (chip click → Save active + "Anonymized summaries" rename).<br>• **Still pending** — W7 (resolver), W16 (reviewee `/results` body), W17 (observer `/collation` body). See `spec/visibility_policy.md` for the consolidated contract. |
| W16 | Reviewee results surface | §5 | ✓ shipped (PRs #1737 → #1749) | Wires P5: resolves visibility policy via W7 + renders the responses in the policy-picked form. Three modes ship end-to-end:<br>• **Raw** — per-reviewer rows; identity column is the *reviewer* (the reviewee already knows the responses are about them); rows filtered by `Assignment.reviewee_id == reviewee.id`. Group-scoped instruments drop the display-field columns. Window-gating mirrors the reviewer surface (pre-release scaffolding renders empty cells; explicitly-closed release windows drop the section entirely).<br>• **Anonymized** — same table shape as Raw, but every identification cell (Reviewer name + email + display-field values) collapses to the muted em-dash. Response values still surface.<br>• **Summarized** — different render shape: identification columns collapse to a single "Summary" cell carrying `Number of reviewers assigned: N` + `Number of reviewers with some responses: M`; rows collapse to one aggregate row. Per-data-type aggregates: Integer / Decimal show Average + Median + Min + Max (labels render with em-dashes at zero responses); List shows each declared option with its frequency + percentage (zeros surface); String shows Total length + Average length characters. Operator-set column widths intentionally ignored.<br>• Code: `app/web/views/_reviewee_results.py` (`SummarizedFieldCell`, `SummarizedRow`, `_summarize_field`), `app/web/templates/reviewer/results.html`. PR trail: **#1737** Raw + structure, **#1738 → #1740** Anonymized + window-gating refinements, **#1741 → #1746** scope-guard regression tests for the Same Group + Different team configuration, **#1747** Summarized baseline, **#1748** broadened aggregates (median/min/max/percentages/length), **#1749** zero-response label scaffolding. |
| W17 | Observer collation surface | §5 | ✘ | Wires P6: resolves visibility policy via W7, filters by observer `tag_1`. |
| W18 | Unified `/me/` lobby cross-role query | §5 | ✓ shipped (#1709, polish #1712 / #1714 / #1715) | The `/me` dashboard now unions three roster lookups (reviewer / email-identified reviewee / observer, active rows only, case-insensitive email match) and emits one row per session the user touches with the full role list. Reviewer-specific fields (per-reviewer pill, deep link, per-page sub-rows) populate only when the user is an active reviewer; reviewee / observer-only rows show "—" in the Reviewer status column. Session-name + per-pill links resolve by priority Reviewer → Reviewee → Observer with per-role reachability gates (#1714); pills fold into the Session cell (#1712); the same cross-role navigator chip strip appears on each role-specific surface so the user can swap roles without going back to `/me` (#1715). Lives inline in `_dashboard.py` for now — see W4 for the unfinished move into `participants.sessions_for_user`. |
| W19 | `Acknowledge` flow | §6 | ✓ shipped (PR #1750) | Bottom-right half-width Acknowledge card on `/me/sessions/{id}/results`, blue-emphasis modelled on the selected Data shape sub-card (new `.rs-acknowledge-card` CSS class in `base.html`: blue border + 1px shadow + faint blue tint). Pre-ack: checkbox + Acknowledge button gated by the existing `data-delete-confirm` / `data-delete-btn` JS pattern. Post-ack: form collapses to "✓ Acknowledged on {date}" strip + a `✓ Acknowledged` `pill-success` in the page header. `POST /me/sessions/{id}/results/acknowledge` calls `app/services/reviewees.py::acknowledge_results` — idempotent, returns `False` when already acknowledged so the route doesn't double-stamp. New audit event `reviewee.results_acknowledged` registered in `EVENT_SCHEMAS` (snapshot envelope: reviewee_id + acknowledged_at; the schema-line name uses `reviewee.*` to align with the model's `reviewee.*` event family rather than the placeholder `results.acknowledged` originally sketched in S10). No DB migration — `reviewees.results_acknowledged_at` was pre-positioned in #1678. |
| W20 | Reviewee / observer email notifications | §6 | ✘ | Gated on Segment 14B. Results-ready notices, acknowledgement nudges. |
| W21 | Magic-link landing for reviewees / observers | §4 | ✘ | Blocked on the `invitations`-extensibility design call. |

---

## What's shipped

- **Phase 1 schema + audit allowlist** (PR #1678) — S1, S2,
  S7, S8, S9, S10, S11. Alembic migration `b3e7d2a4c8f1`.
- **Phase 1 helper / dependency stubs** (PR #1679) — W1, W2,
  W3, W4 as dead code / shape-only.
- **Band 3 visibility-policy placeholder** (PR #1656) — P2
  shipped. Four-row table inside each instrument card's Band
  3 section; Operator + Reviewers rows fixed, Reviewees +
  Observers rows toggleable with muted cycle chips. Inert
  outside edit mode. W15 wires the chips to
  `instrument_view_policies`.
- **Session-schedule disabled-placeholder inputs** (PR #1656)
  — P3 shipped. `responses_release_at` (datetime-local) and
  `release_until_offset` (text) render disabled inside the
  Edit Session Details card's right-hand column on both
  `session_edit.html` and `session_new.html`, alongside the
  18G-wired Start / End / invite-offsets / reminder-offsets
  inputs. W14 unlocks them onto the existing 18G columns.
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
- **Schedule authoring (W14)** + **release-window reshape
  (S12)** — PR #1716 wired P3's two disabled inputs onto
  the existing 18G `responses_release_at` /
  `release_until_offset` columns; S12 (Alembic
  `f4a92b3c6d18`) then retired the offset shape in favour
  of `responses_release_until` as an absolute close
  datetime, with the validator + Settings-CSV slot
  following. The Release-now / Stop-release Operations
  buttons + their two audit events
  (`session.responses_released` /
  `session.responses_release_stopped`) registered in
  `EVENT_SCHEMAS` are the remaining piece of the
  release-window story.
- **Visibility-policy editor (W15) + per-window mode pairs
  (S14)** — the Band 3 placeholder (P2 / #1656) was lit
  up across a sequence of PRs:
  - **Persistence (W15)** — `app/services/visibility_policies.py`
    with `encode_mode` / `decode_mode` + per-(audience, window)
    validation + `upsert_policy` / `upsert_many` emitting
    `instrument.view_policy_set`; `build_instruments_context`
    carries `band3_visibility_by_instrument`.
  - **S14 expand** (Alembic `a7e3b1d92c64`) adds the four
    per-window mode pair columns
    (`while_ongoing_granularity` / `_identification` +
    `after_release_*`) and backfills from the legacy
    quadruple.
  - **PR #1730** flips service / route / view / template
    onto the per-window pair columns and rebuilds the
    editor as a 3-row × 2-window-column chip grid
    (Reviewers / Reviewees / Observers × Session ongoing /
    Responses released).
  - **S14 contract** (Alembic `b8f4c2a91d35`) drops the
    legacy `enabled` / `granularity` / `identification` /
    `visible_when` quadruple.
  - **Reviewer-surface transparency card** (PR #1732) —
    read-only "Who can see what you wrote" card lands in
    the per-instrument intro grid on `review_surface.html`,
    via the shared `build_reviewer_visibility_rows`
    builder.
  - **Card-Save consolidation + Band 2 preview** (PR #1733) —
    the standalone `/view-policy` POST + "Save visibility"
    submit retire; visibility hidden inputs ride the card's
    main Save form via `form="dfsave-<id>"`, and
    `/fields/save` reads them and calls `upsert_many`. The
    same builder feeds a read-only preview alongside the
    description card in the operator's Band 2 intro grid.
    Observers row dropped from the reviewer-surface card
    (they're admin-side); the heading gains the "(other
    than admin)" suffix.
  - **Chip-click → Save active + label rename** (PR #1734) —
    `[data-new-model-vp-cycle-audience]` added to the dirty
    tracker's click allowlist so a visibility-cell click
    flips Save active; the operator-facing
    "Summarized responses" label renames to "Anonymized
    summaries" in the chip selector and the transparency
    cards.
- **W16 reviewee `/results` body — all three modes** (PRs
  #1737 → #1749). Raw (per-reviewer rows, identified) +
  Anonymized (same shape, identification dashed) + the new
  Summarized aggregate render shape (counts cell + per-data-
  type aggregates: numerical mean/median/min/max, list
  per-choice frequency + percentage, string total + average
  character length; labels render at zero responses with
  em-dash placeholders). Visibility resolver W7
  (`visibility_policies.resolve_mode`) drives the mode pick;
  window-gating mirrors the reviewer surface. PR trail:
  **#1737** Raw + structure, **#1738 → #1740** Anonymized
  + gating refinements, **#1741 → #1746** scope-guard
  regression tests for the Same Group + Different team
  configuration, **#1747** Summarized baseline, **#1748**
  broadened aggregates (median / min / max for numerical,
  percentage for List, total + average length for String),
  **#1749** zero-response label scaffolding.
- **W19 `Acknowledge` flow** (PR #1750). Bottom-right
  half-width Acknowledge card on `/results`, blue emphasis
  modelled on the selected Data shape sub-card (new
  `.rs-acknowledge-card` CSS class). Pre-ack: checkbox +
  Acknowledge button gated by the existing
  `data-delete-confirm` / `data-delete-btn` JS pattern.
  Post-ack: form collapses to "✓ Acknowledged on {date}"
  strip + a `✓ Acknowledged` `pill-success` in the page
  header. `POST /me/sessions/{id}/results/acknowledge`
  calls `reviewees.acknowledge_results` (idempotent — second
  POST is a no-op, original stamp preserved). New audit
  event `reviewee.results_acknowledged` registered in
  `EVENT_SCHEMAS` (snapshot envelope: reviewee_id +
  acknowledged_at). No DB migration — column
  `reviewees.results_acknowledged_at` was pre-positioned
  in #1678.
- **`/me` lobby — per-page sub-rows retired** (PR #1751).
  Multi-paged sessions now show only the main session row;
  pagination happens via the surface's own pager rather
  than deep-linked from the lobby.
  `DashboardPageRow` + `_build_dashboard_page_rows` +
  `_rollup_page_state` deleted from `_dashboard.py`; 6
  sub-row integration tests retired (3 sibling lobby-shape
  tests stay).
- **Outstanding-only filter doc** (PR #1752). New
  `guide/participant_model_remainder.md` lists only the
  open W items + loose ends + blockers, for quicker
  scanning of what's left. `_prep.md` (this file) stays
  the canonical historical audit; refresh the remainder
  doc whenever something ships by moving the row from
  there back to here.
- **W12 Quick Setup Observers slot** (PR #1754). Right
  column on the Quick Setup card reads
  Relationships → Observers → Session settings when
  `observers_enabled` is on; collapses back to
  Relationships → Session settings when off.
  `POST /operator/sessions/{id}/quick-setup/observers`
  route + `submit-all` branch + create-session POST
  branch wire the file upload through the standard CSV
  pipeline.
- **W13 Extract Setup Observers row + bundle** (PR
  #1755). Sibling `observers_extract.py` serialiser;
  `GET /operator/sessions/{id}/export/observers.csv` +
  the new `session.observers_extracted` audit event.
  Extract Setup card gains the Observers row between
  Relationships and Session settings when the toggle is
  on; the Zip-all bundle picks up an
  `{code}_observers.csv` member. Closes the Extract
  Setup leg of L2 — the Observers round-trip
  (Setup page → Quick Setup → Extract Setup → bundle)
  is end-to-end.
- **W11 in-scope — Reviewer `profile_link` Setup mirror**
  (PR #1756). `services/reviewers.create_reviewer` +
  `update_reviewer` accept the kwarg and run it through
  the same blank-→-None normaliser as the tag slots;
  audit snapshot picks it up. Setup-Reviewers route wires
  the form param through create + update; template
  Profile-link column mirrors the Reviewees treatment.
  `field_labels` defaults map gains
  `("reviewer", "profile_link"): "Profile"`. Two
  out-of-scope touchpoints stay parked on the W11 row
  above.
- **L1 cleanup — retire dead `sessions_for_user` stub**
  (PR #1757). `ParticipantSession` dataclass +
  `sessions_for_user` function deleted from
  `app/services/participants.py`; two pinning unit tests
  retired. The W18 implementation (PR #1709) built the
  cross-role union inline in `_dashboard.py` and never
  consumed the stub. `is_email_identified` (W1) stays
  live. Remainder doc also rolls W5 into W17 in the same
  PR (no useful pre-positioning since W17 is the sole
  consumer of a future `collation.py` module).
- **W8 — Validate-page reviewee reachability warning**
  (PR #1758). New rule
  `reviewees.unreachable_for_results` registered with
  `severity=Severity.warning` (non-blocking — anonymous-
  identifier sessions stay activatable). Check counts
  active reviewees whose `email_or_identifier` isn't a
  deliverable email; emits one umbrella issue with the
  count + a fix link to Reviewees Setup anchored at the
  first offending row. Mapped under the Setup gate.

Each subsequent Phase 2 / Phase 3 slice lights up a subset of
the Phase 1 schema without doing its own migration.

## Items still blocking later phases

| Block | What it needs |
|---|---|
| S7 backfill (W6) | Resolved — backfilled FALSE per operator call (no extant sessions populate Relationships); the W6 toggle slice now just wires Setup-nav gating + lock-on-data behavior on top of the column. |
| Magic-link schema shape | Design call on `invitations` extensibility (polymorphic FK vs sibling tables vs discriminator). Blocks W21 entirely. |

## Loose ends to attend to

All loose ends from the original audit have closed:

- **L1** — `sessions_for_user` + `ParticipantSession` stub retired in PR #1757; the W18 cross-role union lives inline in `_dashboard.py`.
- **L2** — Observers round-trip closed end-to-end (Setup page → Quick Setup [W12 / #1754] → Extract Setup [W13 / #1755] → bundle).

## Cross-references

- `guide/participant_model_upgrade.md` — full design rationale, schema
  details, and segment sketch.
- `guide/segment_14B_email_infrastructure.md` — notification dependency
  for W20.
- `guide/archive/segment_18G_scheduled_events.md` — scheduler that the
  §3.4 windows (S3–S6) ride on; W14 integrates with it.
- `spec/audience_and_identity_model.md` — update first when work
  begins.
