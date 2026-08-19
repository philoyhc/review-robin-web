# Landing pages — audit & plan (Segment 18R Item 6)

> **Archived 2026-08-19 — the work shipped.** 18R Item 6 landed (PRs #1982,
> #1983): the role-aware `/` + `/operator` redirects, the non-operator → `/me`
> bounce, `/request-access` retired into `/about`, and the About link on the
> `/me` chrome. Current behaviour lives in `spec/operator_ui_concept.md`
> ("Entry & landing"), `spec/reviewer-surface.md`, and `spec/visual_style_rrw.md`;
> ship-state in `docs/status.md`. Kept as the audit + decision record.

Standing notes for the **landing-pages** work: the entry routes a
signed-in user hits before they reach a working surface. Audited
2026-08-19 against `main` at `ce4b176`.

**The problem in one line:** the app's front door (`/`) serves a raw
JSON blob, `/operator` 404s, and there is no role-aware routing — so a
freshly-signed-in user (via Azure Easy Auth) lands nowhere useful unless
they already know the deep URL (`/operator/sessions` or `/me`).

---

## 1. Current entry routes — ground truth

Probed with the test client + route/template reads. Status is what the
route returns *today*.

| URL | Result | What it serves | Verdict |
|---|---|---|---|
| `/` | `200` **JSON** | `{"name","status":"ok","health","docs"}` — no chrome, no HTML (`app/main.py:87` `root()`) | 🔴 not a human front door |
| `/operator` | **`404`** | no route at the bare prefix (the operator router mounts at `prefix="/operator"` but no sub-router defines the prefix root) | 🔴 no operator landing |
| `/operator/` | **`404`** | same | 🔴 |
| `/operator/sessions` | page | the session **lobby** — the de-facto operator landing (`routes_operator/_lobby.py`) | 🟢 works |
| `/me` | page | the **cross-role participant dashboard** — one row per session the user touches as reviewer / reviewee / observer (`routes_reviewer/_dashboard.py`, `@router.get("")`) | 🟢 works |
| `/about` | page | About card; extends `base.html`, takes `?return_to=` (`routes_about.py`, `about.html`) | 🟢 works |
| `/request-access` | page | denied-access landing for a signed-in but non-allowlisted user; minimal chrome (identity + Sign out), reached via the `OperatorAllowlistDenied` → 303 handler (`main.py:60-64`, `request_access.html`) | 🟢 works |
| `/health` | `200` JSON | infra probe (Easy-Auth-excluded path) | 🟢 (not user-facing) |
| `/auth/me`, `/auth/me/debug` | JSON / HTML | identity diagnostics | 🟢 (not user-facing) |

**Chrome affordances today:**

- **Operator chrome** (`base.html` top bar): the brand identity is a plain
  `<span class="chrome-app-identity">Review Robin Web App (version X)</span>`
  — **not a link**. There is no "click the logo to go home." The user menu
  carries Settings / Admin (sys-admin only) / About / Sign out.
- **Reviewer chrome** (`reviewer/_top_bar.html`): lighter "Review Robin"
  identity; the user menu carries **"My Reviews" → `/me`** (only when the
  reviewer has more than one session), plus Sign out. So participants *do*
  have a home link; operators do not.

---

## 2. Gaps

1. **No front door at `/`.** After sign-in, a browser hitting the base URL
   gets JSON, not a page, and there is **no role-aware routing** — an
   operator should land on the lobby, a participant on `/me`.
2. **`/operator` (bare) 404s.** A user who types or bookmarks `/operator`
   hits a 404; the only operator entry is the deeper `/operator/sessions`.
3. **The operator brand isn't a home link.** Operators have no "home"
   affordance in the chrome (participants have "My Reviews").
4. **Dual-role users have no unified home.** This app's operators are often
   also reviewers. `/me` is participant-only, `/operator/sessions` is
   operator-only — nothing offers both, and `/` can't help.

---

## 3. URLs that want a landing page

- **`/`** — the priority: a role-aware home (redirect *or* a hub page).
- **`/operator`** — should at minimum 302 to `/operator/sessions`.
- `/me` — already a good participant landing; **no change needed**.

Precedent for a new page: `about.html` / `request_access.html` show the
established "full page extending `base.html` with `{% block body_class %}ui-v2`"
pattern, and `request_access.html` shows how to override `top_bar` for a
minimal chrome. Role info is cheap to resolve at request time:
`user.is_operator` (a column) + a roster-email match (the dashboard already
does the participant-union query).

---

## 4. Recommendation — two approaches for `/`

### Option A — smart redirect (minimal)

`/` becomes a pure role router (302):

- operator (or sys-admin) → `/operator/sessions`
- participant-only → `/me`
- signed in but neither → `/request-access`

`/operator` → 302 to `/operator/sessions`. No new page; smallest diff.

*Weakness:* a **dual-role** user is sent one way with no choice, and there
is still no real "home" page — just a bounce.

### Option B — a home hub page (fuller) — *recommended*

`/` renders a real HTML landing (extends `base.html`, `ui-v2`) that greets
the signed-in user and shows **role-appropriate entry buttons** —
**"Operator console"** (→ lobby) and/or **"My reviews"** (→ `/me`) — plus
About / Sign out. A signed-in-but-non-allowlisted, non-participant user
gets the "request access" message inline (or is redirected to
`/request-access`). `/operator` → 302 to the lobby (or, later, its own
small operator home).

*Why B:* the ask is a real front door ("`/` needs some work"), and a hub is
the only clean answer to the **dual-role** case (both buttons, user
chooses). It also gives operators the "home" affordance they currently lack
— the hub is what a future clickable brand-logo would link to.

**Lean:** **B for `/`**, with the A-style `/operator` → lobby redirect
folded in.

### Landing-by-role decision table (the contract to build against)

| Signed-in user is… | Option A (redirect) | Option B (hub) |
|---|---|---|
| operator only | → `/operator/sessions` | hub with **Operator console** |
| participant only | → `/me` | hub with **My reviews** |
| operator **and** participant | → `/operator/sessions` (loses the choice) | hub with **both** buttons |
| allowlisted, neither yet | → `/request-access`? (awkward) | hub with a "nothing assigned yet" note |
| signed in, not allowlisted | → `/request-access` | → `/request-access` (unchanged) |

---

## 5. Proposed slices (scaffold-first, per `CLAUDE.md`)

If Option B is chosen:

1. **Scaffold** — a static `home.html` (extends `base.html`) + a
   `GET /` that renders it with placeholder role buttons (both shown,
   inert-ish), and a `GET /operator` → 302 `/operator/sessions`. Retire the
   JSON root (or keep a JSON body only for a non-HTML `Accept` header, TBD —
   see open questions). Land the surface before the logic.
2. **Wire role resolution** — compute the user's roles (`is_operator` +
   participant-union) in a small view helper and show only the buttons that
   apply; handle the neither/not-allowlisted branches.
3. **Chrome home link (optional follow-on)** — make the operator brand
   identity link to `/` (or the lobby), matching the participant "My
   Reviews" affordance, so the hub is reachable from anywhere.

---

## 6. Open questions to settle before building

- **Redirect vs hub** for `/` (Option A vs B). *Lean: B.*
- **Does `/` still need to answer non-browser clients?** The current JSON
  root doubles as a cheap liveness/metadata endpoint. Options: keep JSON for
  `Accept: application/json` and serve HTML otherwise; or move the metadata
  to `/about` / rely on `/health` and make `/` HTML-only. `/health` already
  covers liveness, so HTML-only `/` is probably fine — confirm.
- **`/operator` target** — straight redirect to `/operator/sessions`, or a
  dedicated operator home hub later? (Redirect now; hub only if an operator
  landing accrues more than "go to the lobby".)
- **Dual-role default** — the hub shows both; is there a remembered
  last-used surface, or always the neutral hub? *Lean: neutral hub, no
  memory, keep it simple.*

---

## 7. Decision & build status (2026-08-19)

**Chosen: Option A (role-aware redirect), simplified.** A sys-admin is
always also an operator in practice, so there is no separate
sys-admin landing — the split is two-way. `/` routes on
`is_operator OR is_sys_admin` (safe even against the config-edge
`SYS_ADMIN_EMAILS`-only user, whom `require_operator` admits anyway).

**Decisions settled:**

- **(a) The JSON `/` is dropped.** `/` is now a role-aware redirect;
  liveness / metadata lives only at `/health`.
- **(b) `/request-access` is retired**, and `/about` is repurposed to
  carry its "signed in but no access / how to get in" role. The
  operator-denied bounce points at `/me`.

**Final contract:**

| Route | Who | → |
|---|---|---|
| `/` | operator **or** sys-admin | `/operator/sessions` |
| `/` | participant or nobody | `/me` |
| `/operator`, `/operator/` | anyone (unguarded) | `/operator/sessions` (lobby gate then applies) |
| any `/operator/*` | non-operator/non-sys-admin | `/me` *(was `/request-access`)* |

**Build status:**

- **Slice 1 — shipped.** The `/` role redirect (302; JSON dropped) and
  the `/operator` + `/operator/` → lobby redirects, in `app/main.py`.
  Tests: `tests/integration/test_landing_pages.py`.
- **Slice 2 — shipped.** Flipped `OperatorAllowlistDenied` → `/me`
  (`app/main.py`); retired `/request-access` (route in `routes_auth.py` +
  `request_access.html` template); repurposed `/about` to carry the
  access-help role — it now passes the signed-in identity + operator
  contact and renders an "Access" card (`routes_about.py`, `about.html`).
  Comment/docstring refs across `deps.py` / `error_handlers.py` /
  `routes_operator/__init__.py` / `sys_admin_users.html` repointed at `/me`.
  Tests: the bounce-target assertions across
  `test_operator_allowlist_gate.py` / `test_operator_lobby_access_gate.py`
  / `test_preview_route.py` now expect `/me`; the retired page + the
  `/about` access-help are covered in `test_landing_pages.py`; two chrome
  tests updated for `/about` now carrying an identity.

**Item 6 complete.** Both slices shipped; full suite green (2,679 passed).
