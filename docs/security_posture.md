# Security posture

> **Draft — Segment 14A PR 4.** This file currently holds only the
> permission and destructive-action audit matrices produced by the
> §5.6 / §5.7 review. Segment 14A **PR 6** (§5.10) completes it into
> the full security / compliance posture note by adding: the Azure
> Easy Auth trust model, the CSRF posture (segment-plan decision 2),
> `ALLOW_FAKE_AUTH` gating, and the deferred-infrastructure items.
> Until then, treat the sections below as the authoritative audit
> record and the rest of the note as pending.

## Authorization model

Three layers, all in `app/web/deps.py`:

- **`require_operator`** — workspace allowlist gate. Mounted as a
  router-level dependency on the whole `routes_operator` package
  (`routes_operator/__init__.py`), so *every* `/operator/*` route is
  behind it. A signed-in user not on the operator/sys-admin
  allowlist is redirected to `/request-access`.
- **`require_session_operator`** — per-session membership gate.
  Resolves `{session_id}` and 403s unless the caller is an operator
  of *that* session. Applied per-route on session-scoped operator
  routes, either directly or via slice helpers
  (`_require_instrument_in_session`, `_require_rtd_in_session`, …)
  that also re-scope any child id to the session.
- **`require_sys_admin`** — workspace sys-admin gate; strictly
  tighter than `require_operator`. `require_sys_admin_or_session_operator`
  relaxes the per-session check for sys-admins on diagnostic routes.
- **`require_reviewer_in_session`** — reviewer identity gate. 403s
  unless the caller has an *active* `Reviewer` row whose email
  matches the authenticated identity (case-insensitive).

## §5.6 Permission audit

Reviewed 2026-05-18. Every route family resolves identity through
the dependencies above; no route trusts a client-supplied actor id.

| Route family | Gate | Notes |
|---|---|---|
| `/operator/*` (all) | `require_operator` | Router-level dependency — no operator route can skip it. |
| Operator session-scoped routes | `require_session_operator` | Direct or via `_require_*_in_session` helpers. |
| `/operator/sessions` bulk routes (tags / archive / delete-selected) | `require_operator` + per-id check | Each client-supplied `session_id` is re-resolved with `sessions.get_for_user`; non-owned ids are skipped. |
| `/operator/settings/library/*` deletes | `require_operator` + owner check | Query filters `owner_user_id == user.id`; cross-operator id 404s. |
| `/operator/sys-admin/*` | `require_sys_admin` | Includes user admit/revoke/promote/demote/remove. |
| Export routes (`/export/*.csv`, `bundle.zip`) | `require_session_operator` | |
| `/export/audit_log.csv` | `require_sys_admin` | Tightened in Segment 16C PR 1. |
| Reviewer surface + save/submit/clear | `require_reviewer_in_session` | |
| `/reviewer/invite/{token}` | identity + token lookup | Email-mismatch → dedicated 403 page. |

POST endpoints verified not to trust client-side identifiers:
reviewer `save`/`submit` build the assignment index from
`_reviewer_assignments` (scoped to `reviewer_id`), so a foreign
`assignment_id` in the form body is silently dropped — never
written. Operator child-id routes 404 on cross-session ids via the
`_require_*_in_session` helpers.

**Result: no gaps found.**

## §5.7 Destructive-action audit

Reviewed 2026-05-18. Each destructive action carries an explicit
confirmation, a permission gate, and an audit event (every mutating
service writes an `audit_events` row).

| Action | Confirm | Permission | Audit |
|---|---|---|---|
| Delete response data (`/delete-data`) | `confirm=true` | `require_session_operator` | ✓ |
| Delete session (`/delete`, `/delete-selected`, `/delete-archived-selected`) | `confirm=true` | `require_session_operator` / per-id check | ✓ |
| Close / reopen session (`/activate`, `/revert`, `/workflow/activate`) | `activate_confirm` banner | `require_session_operator` | ✓ |
| Replace reviewers / reviewees roster | `confirm_replace` + response-loss ack | `require_session_operator` | ✓ |
| Replace assignments (import / generate / `delete-all`) | `confirm`/`confirm_replace` + response-loss ack | `require_session_operator` | ✓ |
| Replace relationships (`delete-all`) | `confirm=true` | `require_session_operator` | ✓ |
| Delete instrument / field | `confirm=true` | `require_session_operator` (via helper) | ✓ |
| Reviewer clear (`/clear`) | `confirm=true` | `require_reviewer_in_session` | ✓ |
| Revoke / regenerate invitation links | operator UI action | `require_session_operator` | ✓ |

User-facing warnings are rendered by the operator templates that
own each confirm checkbox; they are not exercised by the test
suite and are verified on the dev slot.

**Result: no gaps found.**

## Denial-path test coverage

| Gate | Test |
|---|---|
| `require_operator` | `test_operator_allowlist_gate.py` |
| `require_session_operator` | `test_assignment_routes.py::test_non_operator_gets_403_on_assignments_hub_and_post` |
| `require_sys_admin` | `test_sys_admin_chrome.py` (root + diagnostics) |
| `require_reviewer_in_session` | `test_reviewer_response_flow.py::test_other_session_url_returns_403`, `::test_inactive_reviewer_row_403s_on_surface` |
| Client-id trust (reviewer POST) | `test_reviewer_response_flow.py::test_save_drops_foreign_assignment_id_from_post` |
| Export sys-admin gate | `test_extracts_audit_log_route.py::test_audit_log_route_rejects_non_sys_admin` |
