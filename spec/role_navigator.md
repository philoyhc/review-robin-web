# Role navigator (chip strip)

The role-navigator is the small chip strip that appears immediately below the page header on every participant-facing `/me` surface. It lets a multi-role user swap surfaces (reviewer surface ↔ reviewer summary ↔ reviewee results ↔ observer collation) without bouncing back through the `/me` dashboard.

This spec documents the partial. The broader cross-cutting participant-model contract is in `spec/participant_model.md`; the dashboard side that informs the same priority rules is in `spec/reviewer-surface.md`.

---

## 1. What it does

For every role the signed-in user holds on the current session, the strip renders one chip in a stable priority order: **Reviewer → Reviewee → Observer**.

- The chip matching the **current surface** renders full-colour (its role-specific palette) and **carries no link** — it reads as "you are here".
- Other roles render **muted** (grey palette overriding the role colours). If the surface is currently reachable they render as `<a>` links; if not, as plain `<span>`s.

Roles the user doesn't hold are not rendered. A single-role user sees a one-chip strip; a triple-role user sees three chips, exactly one full-colour and the other two muted.

---

## 2. Surfaces that include the strip

The partial is included by:

| Surface route | Template | `active_role` passed |
|---|---|---|
| `GET /me/sessions/{id}/{page_n}` (reviewer surface) | `reviewer/review_surface.html` | `"reviewer"` |
| `GET /me/sessions/{id}/summary` (reviewer summary) | `reviewer/summary.html` | `"reviewer"` |
| `GET /me/sessions/{id}/results` (reviewee placeholder) | `reviewer/results.html` | `"reviewee"` |
| `GET /me/sessions/{id}/collation` (observer placeholder) | `reviewer/collation.html` | `"observer"` |

**Suppressed in operator-preview mode.** The reviewer-surface template reuses the same partial under the operator-side preview route (`/operator/sessions/{id}/previews`), which renders `review_surface.html` with `preview_mode = True`. The chip strip is wrapped in `{% if not preview_mode %}` so the operator preview doesn't leak a misleading "you are here" chip for an arbitrary reviewer the operator is impersonating.

---

## 3. Helper contract

**Function:** `build_role_chips(db, *, user, review_session, active_role) -> list[dict]`.
**Module:** `app/web/routes_reviewer/_shared.py`.

**Inputs:**

| Parameter | Type | Meaning |
|---|---|---|
| `db` | `sqlalchemy.orm.Session` | Live request session. |
| `user` | `User` | Signed-in user; `user.email` is the match key. |
| `review_session` | `ReviewSession` | The session the surface is rendering. |
| `active_role` | `str` | One of `"reviewer"` / `"reviewee"` / `"observer"` — which chip in the result list should render as the active "you are here" state. The caller (the surface route) knows this from its own URL. |

**Output:** A list of dicts, ordered by `_ROLE_PRIORITY = ("reviewer", "reviewee", "observer")`. Each entry carries:

| Key | Type | Meaning |
|---|---|---|
| `role` | `str` | `"reviewer"` / `"reviewee"` / `"observer"`. The CSS class derives from this (`pill-role-<role>`). |
| `target` | `str` | Absolute path the chip links to. Used only when the chip renders as an `<a>` (i.e. `active is False` and `enabled is True`). |
| `active` | `bool` | `True` iff `role == active_role`. The template renders the chip as a no-link `<span>` with the `rs-role-nav-active` modifier. |
| `enabled` | `bool` | `True` when the role's surface is currently reachable. Inactive + enabled → muted link. Inactive + disabled → muted span. |

When the user has no roles on the session (an empty list returned), the template renders nothing. This branch shouldn't fire in practice — the route's gate would have rejected the request first — but the partial is safe in that case.

### Per-role target + reachability

| Role | Target | Reachable when |
|---|---|---|
| reviewer | `/me/sessions/{id}/summary` if `pill.state == "submitted"`, else `/me/sessions/{id}/1` | `session_status_for_reviewer(reviewer, session) != "not opened"`. Closes when the session is `draft` / `validated` (the reviewer surface itself would 403 / redirect). |
| reviewee | `/me/sessions/{id}/results` | Always (today). W16 will gate on `responses_release_at` + `release_until_offset`. |
| observer | `/me/sessions/{id}/collation` | Always (today). W17 will add the analogous gate. |

### Identity match

The same case-insensitive email match drives roster membership detection (`func.lower(column) == casefold(user.email)`):

- Reviewer: `Reviewer.status == "active"` and `func.lower(Reviewer.email) == user_email`.
- Reviewee: `Reviewee.status == "active"`, `participants.is_email_identified(reviewee)`, and case-insensitive `email_or_identifier` match. Confidential / non-email reviewees are filtered out.
- Observer: `Observer.status == "active"` and `func.lower(Observer.email) == user_email`.

The reviewer match also fetches the reviewer's `session_pill_for_reviewer` state to decide the summary-vs-page-1 target.

---

## 4. Template + CSS contract

**Partial:** `app/web/templates/reviewer/_role_chips.html`.

Expects `role_chips` in the template context (an empty list is rendered as nothing). For each entry, renders:

- `chip.active = True` → `<span class="pill pill-role-<role> rs-role-nav-active">{{ Label }}</span>`.
- `chip.active = False` and `chip.enabled = True` → `<a class="pill pill-role-<role> rs-role-nav-muted" href="{{ chip.target }}">{{ Label }}</a>`.
- `chip.active = False` and `chip.enabled = False` → `<span class="pill pill-role-<role> rs-role-nav-muted">{{ Label }}</span>`.

Labels are the role names capitalised (`Reviewer` / `Reviewee` / `Observer`).

The strip wrapper is `<div class="rs-role-nav">`.

**CSS** lives in `app/web/templates/base.html` alongside the `.pill-role-*` palette:

- `.rs-role-nav` — `display: flex; flex-wrap: wrap; gap: var(--space-1); margin: 0 0 var(--space-4) 0;`. Sits below the page header, before the description card.
- `.rs-role-nav .rs-role-nav-muted` — `background: var(--surface-2, #f3f4f6); color: var(--text-muted); text-decoration: none;`. Overrides the `.pill-role-*` colour palette so the chip looks "not selected".
- `.rs-role-nav a.rs-role-nav-muted:hover` — `color: var(--text-primary); text-decoration: underline;`. The hover affordance that says "clickable".
- `.rs-role-nav .rs-role-nav-active` — `font-weight: 600;`. Pairs with the role's own palette (the chip keeps its `.pill-role-<role>` colour) to read as "selected".

---

## 5. Adding the strip to a new surface

If a future participant surface (e.g. the W16 reviewee results body, the W17 observer collation body, or any further `/me/sessions/{id}/<something>` page) wants the strip:

1. In the surface route, compute `role_chips = build_role_chips(db, user=user, review_session=session, active_role="<role>")`. Pass it into the template context.
2. In the template, add `{% include "reviewer/_role_chips.html" %}` directly under the page header (the `rs-page-header` div) and before any description card.
3. If the surface also renders in an operator-preview context (the reviewer-surface preview is the only current example), wrap the include in `{% if not preview_mode %}` so the operator's preview doesn't leak a chip.

Adding a fourth role would touch:
- The `_ROLE_PRIORITY` tuple in `_shared.py`.
- The per-role branch in `build_role_chips` that emits the target + reachability entry.
- The per-role `if`/`elif` branch in `_role_chips.html` (currently three branches, one per role).
- A matching `.pill-role-<role>` palette entry in `base.html`.

The strip itself doesn't need template structural changes.

---

## Cross-references

- `spec/participant_model.md` — the broader participant-model contract (rosters, gates, lobby union).
- `spec/reviewer-surface.md` — the `/me` dashboard's session-name + per-pill priority pick rules (same priority ladder).
- `spec/audience_and_identity_model.md` — audience taxonomy + identity-match rules.
- `app/web/routes_reviewer/_shared.py` — `build_role_chips` + `_ROLE_PRIORITY`.
- `app/web/templates/reviewer/_role_chips.html` — the partial.
- `app/web/templates/base.html` — `.rs-role-nav*` styles.
