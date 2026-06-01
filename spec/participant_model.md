# Participant model

The cross-cutting **participant** surface contract: how the three rosters (reviewer / reviewee / observer) compose into a single user-facing surface family at `/me`, how identity matching works, and where the participant-facing pages plug into the existing reviewer chrome. This doc is the entry point for the participant model — the per-page contracts live in their own specs and are linked inline.

The umbrella design (rationale, future visibility-policy / acknowledge / magic-link arcs) lives in `guide/archive/participant_model_upgrade.md`. This file documents **what is live today** in terms a surface reader can rely on.

---

## 1. The three participant rosters

Each session can carry three independent rosters of people who interact with the session as *participants* (not as the operator running it). The rosters are per-session — adding the same person to two sessions means two rows in each table.

| Roster | Table | Identity column | Setup page | Authoring service |
|---|---|---|---|---|
| Reviewer | `reviewers` | `email` (NOT NULL, strict email shape) | `/operator/sessions/{id}/reviewers` | `app/services/reviewers.py` + `app/services/csv_imports.py` |
| Reviewee | `reviewees` | `email_or_identifier` (NOT NULL, email or opaque handle) | `/operator/sessions/{id}/reviewees` | `app/services/reviewees.py` + `app/services/csv_imports.py` |
| Observer | `observers` | `email` (NOT NULL, strict email shape) | `/operator/sessions/{id}/observers` | `app/services/observers.py` + `app/services/csv_imports.py` |

Two of the three rosters are gated on per-session feature toggles (§2 below); the Reviewer roster is unconditional.

All three rosters carry the same `status` column with `active` / `inactive` values. **Inactive rows do not grant access** to any participant surface — deactivation is the operator's "soft remove".

### Identity matching

The participant gates (`require_reviewer_in_session`, `require_reviewee_in_session`, `require_observer_in_session` in `app/web/deps.py`) compare the authenticated user's email against the roster column **case-insensitively**:

- **Reviewer**: `casefold(Reviewer.email) == casefold(user.email)`.
- **Reviewee**: `casefold(Reviewee.email_or_identifier) == casefold(user.email)` **and** the identifier passes `participants.is_email_identified(reviewee)` (i.e. parses as an email). Reviewees with confidential / opaque identifiers cannot reach the reviewee surface by construction — there is no email inbox to authenticate against.
- **Observer**: `casefold(Observer.email) == casefold(user.email)`.

The same case-insensitive email match is the basis for the cross-role union (§5 below).

---

## 2. Per-session feature toggles

Two boolean columns on `sessions` gate which of the optional Setup tabs render and which participant surfaces are reachable:

| Column | Default | Gates | Authored on |
|---|---|---|---|
| `relationships_enabled` | `False` | The Relationships Setup tab + every route in `_setup_relationships.py` (via `require_relationships_enabled_session`). | User interface settings card on Session Edit Details and Create New Session. |
| `observers_enabled` | `False` | The Observers Setup tab + every route in `_setup_observers.py` (via `require_observers_enabled_session`); the observer collation surface gate `require_observer_in_session` is independent of this flag. | Same card on both forms. |

The card on both forms lives above the Quick Setup card. Saving the form persists both flags through `SessionCreate` to `sessions.create_session` (on the Create form) or `sessions.update_session` (on Edit).

**Lock-on-data invariant.** Once a roster has at least one row, the corresponding flag cannot flip True → False — `sessions.update_session` silently no-ops the flip (the UI also renders the checkbox `disabled` in this case). This prevents orphaning data behind a hidden tab. Both `_has_relationships(db, session_id)` and `_has_observers(db, session_id)` are the load-bearing readers.

**Audit.** Every flip emits `session.feature_toggled` with the canonical `audit.changes({field: [old, new]})` envelope, in addition to the general `session.updated` event recording the same diff alongside any other field edits in the same save.

---

## 3. Setup-Observers page

The Setup-Observers page is documented in `spec/setup_pages.md` (Observers section). Key points relative to the participant model:

- Routes mounted at `/operator/sessions/{id}/observers/*` are uniformly gated by `require_observers_enabled_session`. The page 404s when `observers_enabled = False`.
- The model carries a **single `tag_1`** (not three) and an optional `display_name`; `email` is the required identity. The friendly-label editor card from the Reviewers / Reviewees pages is intentionally absent — single-tag observers don't benefit from it.
- The CSV import contract is documented in `spec/csv_contracts.md` §3.2b — required `ObserverEmail`, optional `ObserverName` / `ObserverTag1`.
- Audit events: `observer.created` (snapshot), `observer.updated` (changes + refs), `observer.bulk_inactivated` / `observer.bulk_reactivated` (snapshot), `observers.imported` (counts + context), `observers.deleted_all` (counts). All registered in `EVENT_SCHEMAS`.

---

## 4. Participant-facing surfaces at `/me`

Three surfaces are participant-role-specific. All three render the reviewer-surface chrome (`body.ui-v2 reviewer` + `reviewer/_top_bar.html`) and carry the role-navigator chip strip below the page header (see §6 + `spec/role_navigator.md`).

| Surface | URL | Gate | Status |
|---|---|---|---|
| Reviewer surface | `/me/sessions/{id}/{page_n}` + `/me/sessions/{id}/summary` | `require_reviewer_in_session` | Live; full response-collection. See `spec/reviewer-surface.md`. |
| Reviewee results | `/me/sessions/{id}/results` | `require_reviewee_in_session` | **Live.** Renders per-instrument sections in raw / anonymized / summarized mode (W16), plus the Acknowledge card at the foot (W19). `POST /me/sessions/{id}/results/acknowledge` stamps `reviewees.results_acknowledged_at` (idempotent). See §4.1 below. |
| Observer collation | `/me/sessions/{id}/collation` | `require_observer_in_session` | **Placeholder.** Same chrome with caption "Observer view of the session". W17 wires the cross-reviewee collation body. |

### 4.1 Reviewee results surface (W16 + W19, live)

`GET /me/sessions/{id}/results` renders the reviewer-surface chrome plus a list of per-instrument sections built by `app/web/views/_reviewee_results.py::build_reviewee_results_context`. Sections appear only for instruments that have a `reviewee` visibility policy row; the section's mode is one of:

- **`raw`** — one row per reviewer who responded; Reviewer name + email shown in the identity column.
- **`anonymized`** — same per-row table; every identification cell (Reviewer name, email, display-field cells) collapsed to a muted em-dash.
- **`summarized`** — per-instrument sections collapse to one aggregate row. The identity column header reads "Summary" and the cell carries two counts: "Number of reviewers assigned" and "Number of reviewers with some responses". Response-field cells render per data type:
  - `Integer` / `Decimal`: Average, Median, Min, Max, (based on N responses). At zero responses, all labels render with em-dash placeholders.
  - `List`: per-choice frequency lines e.g. `A: 2 (33.3%)`. Every declared option surfaces including zeros.
  - `String` (and unknown types): Total length (characters) + Average length (characters), (based on N responses). At zero responses, labels render with em-dash placeholders.

When a policy's window is not open, Raw and Anonymized sections still render their row scaffolding (reviewer identity visible, value cells empty); Summarized sections are omitted entirely because the aggregate has nothing to show.

The **Acknowledge card** (`section.card.rs-acknowledge-card`) always renders at the foot of the page — bottom-right half-width, `border-color: var(--accent-blue)` + 1px shadow + `--accent-blue-bg-faint` tint. Pre-acknowledgement: checkbox (required by JS `data-delete-confirm` / `data-delete-btn` pattern) + "Acknowledge" submit button gated by the checkbox. Post-acknowledgement: the form collapses to a passive "✓ Acknowledged on {date}" strip; the page header gains a `pill-success` "✓ Acknowledged" chip.

`POST /me/sessions/{id}/results/acknowledge` calls `app/services/reviewees.py::acknowledge_results`, which stamps `reviewees.results_acknowledged_at = now()` and emits `reviewee.results_acknowledged` (snapshot envelope: `reviewee_id` + `acknowledged_at`). The operation is **idempotent** — a second POST is a no-op (original timestamp preserved). On success, 303 → `GET /results`.

**Mount-order note.** The routes (`_results.py`, `_collation.py`) are registered **before** `_surface` in `routes_reviewer/__init__.py` because the surface's `/me/sessions/{id}/{page_n}` would otherwise swallow `/results` and `/collation` as the `page_n` value. Treat this as load-bearing — adding any further literal-segment `/me/sessions/{id}/<thing>` routes needs the same precedence.

### Reachability windows (today)

- Reviewer surface: reachable when `session_status_for_reviewer(reviewer, session) != "not opened"`. The surface 403s / redirects until the session has at least once been activated.
- Reviewee results: reachable for any active reviewee whose `email_or_identifier` matches the user's email. **No datetime gate at the route level today.** The per-instrument visibility-policy resolver inside `build_reviewee_results_context` applies the window gate — sections only surface values when the relevant window (while_ongoing / after_release) is currently open. W16 shipped the full resolver; the route itself does not 403 based on the release window.
- Observer collation: reachable for any active observer. **No datetime gate today.** W17 adds the analogous gate.

The release-window columns (`sessions.responses_release_at` + `sessions.responses_release_until`) are operator-authorable now via W14 + S12 but consumed at view time only when W16 / W17 land.

---

## 5. Cross-role lobby: the `/me` dashboard

The `/me` dashboard (`reviewer_dashboard` in `app/web/routes_reviewer/_dashboard.py`) unions the three rosters into a single table, one row per session the user touches in any participant role. The reviewer-dashboard contract is documented in `spec/reviewer-surface.md`; this section covers the participant-model layer specifically.

**Union rule.** For the signed-in user, the dashboard runs three queries (reviewer / reviewee-with-email-identification / observer, `status = active` only, case-insensitive email match) and merges by `session_id`. Each row carries the `roles` list — a subset of `["reviewer", "reviewee", "observer"]` in that priority order.

**Pill stack in the Session cell.** Pills render on a second line directly beneath the session name in the same cell — there is no dedicated Roles column. The CSS classes are `.pill-role-reviewer` (blue), `.pill-role-reviewee` (green), `.pill-role-observer` (amber).

**Session-name link target.** The link picks the first reachable role in priority order Reviewer → Reviewee → Observer. The rationale: reviewer carries the active work (deadline, save / submit), so a multi-role user lands on the actionable page by default; the pills are the explicit escape hatch to the read-only views.

Reachability per role for the link:

| Role | Reachable when |
|---|---|
| reviewer | `session_status_for_reviewer != "not opened"` (per §4). Surfaces with `pill.state == "submitted"` link to `/me/sessions/{id}/summary` instead of `/me/sessions/{id}/1`. |
| reviewee | Always today; gated on the release window in W16. |
| observer | Always today; gated on the release window in W17. |

If no role is reachable, the session name renders as plain text.

**Pill linking.** Each individual pill is a link to its surface when that role is reachable, a plain span otherwise. Single-role users see name and pill leading to the same page; multi-role users get parallel deep-links to all three.

### Drift (planned cleanup)

The W18 cross-role union lives inline in `_dashboard.py`. The `sessions_for_user` stub originally proposed as the canonical home retired with **L1** (PR #1757) — the inline shape was the W18 implementation choice and never grew a second consumer.

---

## 6. Role-navigator chip strip

Every participant-facing surface (reviewer surface, reviewer summary, reviewee results, observer collation) renders a chip strip below the page header showing each role the user holds on this session. The chip matching the current page is highlighted (no link); the others are muted links to their surfaces. Lets a multi-role user swap surfaces without bouncing through `/me`.

Full contract in `spec/role_navigator.md`. Key seam: every surface route calls `build_role_chips(db, user=user, review_session=session, active_role=...)` from `app/web/routes_reviewer/_shared.py` and passes the result as the `role_chips` template context value.

---

## 7. Sessions schedule — release-responses window

The Create New Session and Session Edit Details forms author two extra schedule fields on the session:

| Field | Form input | Service | Validator |
|---|---|---|---|
| `responses_release_at` | `<input type="datetime-local">` "Release responses from (optional)" | Persisted on `sessions.responses_release_at`. | `scheduled_events.parse_and_validate_responses_release_at(raw, *, timezone_name)`. No minimum-lead floor — operator may backdate. |
| `responses_release_until` | `<input type="datetime-local">` "Release responses until (optional)" | Persisted on `sessions.responses_release_until`. | `scheduled_events.parse_and_validate_responses_release_until(raw, *, timezone_name, responses_release_at)`. Datetime parse; must close *after* `responses_release_at` when both are set, and within 365 days of it. |

Both fields ride through `SessionCreate` end-to-end (`create_session` writes; `update_session` diffs them alongside the existing scheduled fields). The §8.2.2 anchor-null rule applies — `responses_release_until` is inert (treated as "no scheduled close") whenever `responses_release_at` is `NULL`. The check happens at view time, not save time; saving an until without an anchor is allowed and harmless. S12 retired the W14 `release_until_offset` (ISO 8601 duration) in favour of this absolute datetime so the form input and the operator's forthcoming Stop release button can write the same column.

The four schedule datetimes (Start / End / Release-from / Release-until) carry a strict ordering chain enforced at save time by `scheduled_events.validate_schedule_ordering` plus the per-field parsers (see `spec/lifecycle.md` §8.2.7). Each `datetime-local` input also carries `min` / `max` attributes the browser picker honours; a small shared partial live-updates the bounds as the operator types.

**Consumer status.** W16's `build_reviewee_results_context` consumes `responses_release_at` / `responses_release_until` inside the per-instrument window gate (via `session_lifecycle.is_response_release_window_open`). The route itself does not gate reachability on this window — sections simply show empty cells until the window opens. W17 (observer collation) will add the analogous consumption on that surface.

---

## 8. Access-control invariants

These hold across the participant-model surface and are pinned by regression tests.

1. **Operator surface stays operator-only.** `/operator/*` is gated by `require_operator` (workspace-level allowlist) and per-session routes additionally by `require_session_operator` (SessionOperator membership). Reviewer / reviewee / observer roster membership **never** grants operator-side access — adding yourself to a roster on someone else's session does not put their session in your operator lobby and does not unlock the per-session edit pages. Pinned by `tests/integration/test_operator_lobby_access_gate.py`.
2. **Per-role gates compose.** A user can simultaneously be an operator on session A and a reviewer / reviewee / observer on session A — the operator surface and the `/me` surface are independent. Same email, both views available.
3. **Inactive rows confer nothing.** All three participant gates require `status = active`. Soft-removing a participant fully removes their access without touching their row.
4. **Confidential reviewees are denied by construction.** `require_reviewee_in_session` filters out reviewees whose `email_or_identifier` is not email-shaped via `participants.is_email_identified`. There is no path to the reviewee surface for confidential-mode rows.

---

## 9. Future work

The participant-model upgrade has a small remaining tail. See `guide/archive/participant_model_remainder.md` for the short list; the next-most-relevant items in priority order:

| Item | What's missing |
|---|---|
| W17 — Observer collation body content | The placeholder route renders only the chrome. W17 wires the cross-reviewee collation body with `tag_1` filtering and the visibility-policy resolver. |
| W21 — Magic-link landings for reviewees / observers | Blocked on the `invitations`-extensibility design call (the table is reviewer-keyed today). |
| W20 — Reviewee / observer email notifications | Blocked on Segment 14B email infrastructure. |

---

## Cross-references

- `guide/archive/participant_model_upgrade.md` — full design rationale + phase plan. Appendix A carries the S / P / W identifier glossary with per-item status + PR pointers.
- `guide/archive/participant_model_remainder.md` — short list of items still to ship or still blocked.
- `spec/audience_and_identity_model.md` — audience taxonomy (operator / reviewer / reviewee / observer / sysadmin); auth posture.
- `spec/setup_pages.md` — Observers page contract.
- `spec/reviewer-surface.md` — `/me` dashboard + reviewer-surface chrome; the role-pill + role-navigator integration points live here.
- `spec/role_navigator.md` — the chip-strip partial used by all four `/me` surfaces.
- `spec/lifecycle.md` — schedule columns including `responses_release_at` / `responses_release_until`.
- `spec/csv_contracts.md` — Observer CSV import contract (§3.2b).
- `spec/settings_inventory.md` — every persisted `sessions` field including the two feature toggles + the release-window columns.
