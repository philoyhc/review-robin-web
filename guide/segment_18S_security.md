# Segment 18S — Security refinements

**Status:** In progress — **Item 1 shipped 2026-08-17** (three-tier role
model; PR ladder 1–4: config + self-heal #1925, guards #1926, UI #1927, docs).
A holding segment for **small, self-contained security / authorization
hardening** on shipped surfaces. Items land as independent slices; the segment
stays open as a home for further security refinements as they're identified.

> Distinct from `guide/deferred_infra.md` (Azure-portal / platform hardening
> — Key Vault, VNet, private endpoints) and from `docs/security_posture.md`
> (the standing description of the current posture). 18S is **in-app**
> authorization / account-safety work the agent can implement and test.

---

## Item 1 — Three-tier role model + protected super-admin

**Status: ✅ Shipped 2026-08-17** (PRs #1925 config+self-heal, #1926 guards,
#1927 UI, + docs). Outcome vs plan: implemented as designed. Decision 3 was
relaxed — a thin delegating `User.is_super_admin` property **was** added (the
"can be added later if callers want it" clause) because the chrome needs the
predicate across all template envs; the config-derived resolver lives in the
new `app/auth/roles.py`. The `requires_super_admin` actor guard means a
deployment with **no** `SUPER_ADMIN_EMAILS` set has no one who can
promote/demote admins — acceptable (localhost uses `fake_auth_super_admin`;
deploys set the list), flagged for follow-up if a fallback is wanted.

Formalize a **strict three-tier role hierarchy** with **nested
capabilities** and a **config-anchored top tier**. This both adds a tier
above today's model *and* tightens who may manage whom.

### The tiers

| Tier | Stored as | Added / revoked by |
|---|---|---|
| **Operator** | `users.is_operator` | **Admins** (and super-admins, by nesting) |
| **Admin** | `users.is_sys_admin` | **Super-admins only** |
| **Super-admin** | *derived*: email ∈ `SUPER_ADMIN_EMAILS` (deployer config) | **Azure App Settings only** — never in-app |

- **Super-admin is set only via the `SUPER_ADMIN_EMAILS` App Setting.** No
  in-app path adds or removes one; only someone with Azure config access can
  (edit the setting + restart). App Settings aren't reachable from inside the
  app, so this is the hard anchor.
- **"Admin" is today's `is_sys_admin`.** The role keeps its name/flag; what
  changes is that promoting/demoting it becomes **super-admin-only**.

### Capability nesting (strict superset)

**Everything an operator can do, an admin can do; everything an admin can do,
a super-admin can do.** So **super-admin ⊇ admin ⊇ operator**. (Today's gates
already treat sys-admin as implying operator; extend so super-admin implies
admin — satisfied for free by the self-heal below.)

### Who can manage whom

| Actor ↓ \ can add/revoke → | Operator | Admin | Super-admin |
|---|---|---|---|
| **Operator** | ✗ | ✗ | ✗ |
| **Admin** | ✓ | ✗ | ✗ |
| **Super-admin** | ✓ | ✓ | ✗ (config only) |

- **Operators** (`is_operator`) — admitted/revoked by **admins** (current
  behaviour; keep).
- **Admins** (`is_sys_admin`) — promoted/demoted by **super-admins only**.
  This **tightens** today's behaviour, where *any* sys-admin can promote or
  demote *any* sys-admin.
- **Super-admins** — never added or revoked in-app; the Sys Admin
  demote / revoke / remove / remove-from-all-sessions paths **refuse** to act
  on a super-admin target (`protected_super_admin`).

### Why this matters (today's gaps)

The Sys Admin page can demote / revoke / hard-remove any user. Today's guards
(`app/services/users.py`) are **identity-agnostic**: `_guard_self` (not
yourself), the **last-sys-admin count floor**, and ownership
(`still_owner` / `owns_sessions`). So the seeded admin has **no special
standing** — any other admin can demote or remove them. And the seed list is
an unreliable protector: `remove_user` hard-deletes (a still-listed
`SYS_ADMIN_EMAILS` re-seeds on next login), while `demote` leaves the row so
the seed list is inert afterwards.

### Design

- **Config.** `super_admin_emails: list[str]` in `app/config.py` (same
  `NoDecode` + comma-split validator as `operator_emails` /
  `sys_admin_emails`); env `SUPER_ADMIN_EMAILS`.
- **Derived, not stored.** `user.is_super_admin` is a **computed** property
  (`email ∈ super_admin_emails`, case-insensitive) — never a DB column — so
  it can't drift from config and can't be flipped in-app. **No migration.**
- **Self-heal on sign-in.** A super-admin email always resolves to
  `is_sys_admin = is_operator = True`, so every existing sys-admin/operator
  gate passes for a super-admin with no special-casing. *(Open question:
  enforce at first-sign-in only, or re-assert on every sign-in? Lean
  **every sign-in** so a pre-feature manual demotion can't strand a
  "protected" account without rights.)*
- **Actor guard — managing admins.** The promote / demote (`is_sys_admin`)
  paths require the **actor** to be a super-admin — a new
  `require_super_admin`-style gate on those two routes / a service check.
  Operator management (admit / revoke) keeps requiring admin.
- **Target guard — protection.** demote / revoke / remove_user /
  remove_from_all_sessions refuse when the **target** is a super-admin,
  raising `UserOperationError(code="protected_super_admin", …)`. Sits *above*
  the last-admin floor (protects a specific account, not just a count).
- **UI.** Sys Admin user list shows **tier badges** (Operator / Admin /
  Super-admin); Promote/Demote controls render only for a super-admin actor;
  Demote/Revoke/Remove are hidden or disabled on super-admin rows (server
  guards remain the real enforcement). Chrome may add a `(super admin)`
  suffix alongside the existing `(sys admin)` one.
- **Floors.** Keep the count-based `last_admin` floor as a backstop; a
  non-empty `SUPER_ADMIN_EMAILS` also guarantees ≥1 protected admin.

### Prior documentation (reconcile)

The **current two-tier model is documented** and must be updated as part of
this item:

- **`spec/audience_and_identity_model.md` §4 "System administrator"** — the
  authoritative prior doc: operator + sys-admin, the Accounts Management
  page, and the `last_admin` / `owns_sessions` / `still_owner` guards.
  Rewrite §4 to the three-tier model (tiers, nesting, the management matrix,
  the config-anchored super tier).
- Originated in `guide/archive/segment_16A_sys_admin_page.md` (the 16A design;
  archived — historical only).
- `spec/role_navigator.md` is about **participant** role-switching chips
  (reviewer / reviewee / observer), **not** the admin hierarchy — no change.

### Scope / size

Config field (+ `fake_auth_super_admin` sandbox toggle) + derived
`is_super_admin` helper + self-heal in `get_or_create_user` + actor-super
guard on promote/demote + target-super guard on
demote/revoke/remove(+from-all-sessions) + Sys Admin template (tier badges +
conditional controls) + tests. **No migration** (super-admin is
config-derived; `is_operator` / `is_sys_admin` columns already exist).

### Definition of done

- With `SUPER_ADMIN_EMAILS=<email>` set: a super-admin **cannot** be demoted,
  revoked, removed, or stripped of sessions in-app (each returns
  `protected_super_admin`); a **plain admin cannot promote/demote admins**
  (only super-admins can); admins can still admit/revoke operators.
- **Capability nesting holds:** a super-admin passes every admin gate; an
  admin passes every operator gate.
- A super-admin email always resolves to a full-rights admin on sign-in (per
  the chosen self-heal rule).
- `spec/audience_and_identity_model.md` §4 rewritten to the three-tier model;
  `docs/deployment_dev.md` + `docs/deployment_nus.md` §7 document
  `SUPER_ADMIN_EMAILS`; `docs/security_posture.md` records the hierarchy.
- Unit tests cover the management matrix, the protection guards, and the
  self-heal; full suite + `ruff` green.

### Open questions

- Self-heal on **every** sign-in vs first-only (lean every).
- Keep the count-based `last_admin` floor alongside the identity-based
  protection? Default: **keep both** — they guard different things (count vs
  identity).

---

### Item 1 — implementation (decisions + PR ladder)

> **Grounded against the live code (2026-08-17).** File/line anchors below are
> from a read of the current implementation. No migration: `super_admin_emails`
> is config-derived and `is_operator` / `is_sys_admin` columns already exist.

**Decisions (resolving the open questions + design choices).**

1. **Self-heal = every sign-in, but super-admin-only.** `get_or_create_user`
   (`app/web/deps.py:47-102`) currently bootstraps role flags **only on
   first sign-in** and returns existing rows untouched (`:65-81`), a
   once-only contract guarded by
   `test_bootstrap_runs_once_env_var_removal_does_not_auto_revoke`. The
   super-admin self-heal is added as a **narrow** re-assertion that fires for
   super-admin emails *only* (force `is_sys_admin = is_operator = True` on
   every sign-in, existing rows included). Normal operator/sys-admin bootstrap
   stays once-only. This guarantees a manual demotion can't strand a protected
   account without loosening the existing contract for everyone else.
2. **Keep both floors** — the count-based `last_admin` floor stays alongside
   the identity-based `protected_super_admin` guard.
3. **`is_super_admin` is a service helper, not a model `@property`.** The
   `User` model (`app/db/models/user.py`) has no computed properties and does
   not import config; add a casefold-membership helper (mirroring
   `deps._email_in`) rather than coupling the model to settings. A thin
   delegating property can be added later if callers want `user.is_super_admin`.
4. **`SUPER_ADMIN_EMAILS` stays optional** — it is *not* added to the
   `validate_critical_settings` fail-fast (`app/config.py:116-120`); making it
   required would break existing deployments. A non-empty list still
   guarantees ≥1 protected admin as a bonus.
5. **Local-dev fake super-admin via a sandbox toggle.** The localhost fake
   operator (`fake_auth_email`, default `operator@example.edu`) needs
   super-admin rights for testing. Mirror the existing
   `fake_auth_operator` / `fake_auth_sys_admin` pattern with
   `fake_auth_super_admin: bool = True` — honoured **only** when
   `allow_fake_auth` + `is_fake`, so it's inert in any deployed env. The fake
   email is folded into the *effective* super-admin set the resolver consults
   (not stored, not a real `SUPER_ADMIN_EMAILS` entry), preserving the
   config-derived invariant. (Alternative considered: document
   `SUPER_ADMIN_EMAILS=operator@example.edu` in `.env.example` / local-setup
   instead — rejected as the default because it needs per-machine env
   coordination and doesn't match the seamless fake-auth precedent.)

**PR ladder** (each slice independently reviewable + shippable; backend tiers
land before the UI that surfaces them):

1. **Config + derived super-admin + self-heal** *(backend; no guards / no UI —
   delivers capability nesting for free).*
   - Add `super_admin_emails: Annotated[list[str], NoDecode] = []` to
     `app/config.py` (mirror `:39-40`) and extend the `_split_email_list`
     validator target list (`:47-52`); env `SUPER_ADMIN_EMAILS`.
   - **Local-dev super-admin (Decision 5).** Add a sandbox toggle
     `fake_auth_super_admin: bool = True` alongside `fake_auth_operator` /
     `fake_auth_sys_admin` (`config.py:24-25`). When `allow_fake_auth` +
     `is_fake` + `fake_auth_super_admin`, the fake identity
     (`fake_auth_email`, default `operator@example.edu`) resolves as
     super-admin — so the localhost operator has full super-admin rights with
     zero env coordination. Inert in prod (`allow_fake_auth` must be false).
     Implement by folding the fake email into the **effective** super-admin
     set the `is_super_admin` resolver / self-heal consults (e.g. an
     `effective_super_admin_emails(settings)` helper = `super_admin_emails +
     [fake_auth_email] if (allow_fake_auth and fake_auth_super_admin)`), so
     the "derived from config, never stored" invariant still holds.
   - Add an `is_super_admin(email, settings)` helper (casefold membership vs
     the effective set, mirroring `deps._email_in:31-35`).
   - In `get_or_create_user`, add the super-admin-only re-assertion (per
     Decision 1) for both the existing-row path (`:65-70`) and the
     first-sign-in path (`:82-97`). The every-sign-in rule means an
     already-existing local `operator@example.edu` row (created before this
     feature under the once-only operator/sys-admin bootstrap) is elevated on
     its next request without a DB reset.
   - Tests: self-heal on first **and** subsequent sign-in; a manually-demoted
     super-admin re-asserts to full rights; a non-super email is unaffected
     (once-only contract intact); **fake-auth super-admin** — with
     `allow_fake_auth` + `fake_auth_super_admin`, the fake email is
     super-admin, and it is *not* when either flag is off.
   - *Risk note:* smallest, self-contained slice; establishes super-admin ⊇
     admin ⊇ operator before any guard depends on it. Land first.

2. **Management guards** *(backend; no UI).*
   - **Actor guard:** `promote` / `demote` (`app/services/users.py:209` /
     `:231`) require the **actor** to be super-admin →
     `UserOperationError(code="requires_super_admin", …)`; operator
     admit / revoke keeps requiring admin. (Confirm the exact
     `promote`/`demote` actor-vs-target signature when wiring.)
   - **Target guard:** `demote` / `revoke` / `remove_user` /
     `remove_from_all_sessions` refuse when the **target** is super-admin →
     `UserOperationError(code="protected_super_admin", …)`, placed *above* the
     `last_admin` count floor (`:239-246`, `:363-370`).
   - Extend `_handle_toggle` (`routes_operator/_sys_admin.py:254-278`):
     `requires_super_admin` → 403, `protected_super_admin` → 409.
   - Tests: the full who-manages-whom matrix (admin **cannot** promote/demote;
     super-admin can; admin **can** still admit/revoke operators) + the
     protection guard on all four target paths.

3. **Sys Admin page UI + chrome** *(consequential UI → scaffold-first per
   `CLAUDE.md`; may split 3a / 3b).*
   - `GET /sys-admin/users` (`_sys_admin.py:208`) passes `actor_is_super_admin`
     + per-row `is_super_admin` into the template context.
   - **3a (scaffold):** `templates/operator/sys_admin_users.html` — render the
     three-tier badge (reshape the two yes/no columns `:173-186`), add
     `data-is-super-admin` to each `<tr>` (`:154-159`); add the `(super admin)`
     chrome suffix in **both** `base.html:2827` and
     `reviewer/_top_bar.html:22`. Static, no control-gating yet.
   - **3b (wiring):** Promote/Demote controls render only for a super-admin
     actor; Demote / Revoke / Remove hidden or disabled on super-admin rows;
     update the inline JS gating (`:191-376`). Server guards from PR 2 remain
     the real enforcement — the UI is advisory.

4. **Docs** *(fold into the relevant PRs or land last).*
   - Rewrite `spec/audience_and_identity_model.md` §4 (`:104-130`) to the
     three-tier model (tiers, nesting, the management matrix, the
     config-anchored super tier).
   - Document `SUPER_ADMIN_EMAILS` in `docs/deployment_dev.md` +
     `docs/deployment_nus.md` §7 (incl. §7.1: the seeded admin can be made a
     protected super-admin); record the hierarchy + protected-super-admin
     guarantee in `docs/security_posture.md`; note the ship in `docs/status.md`.
   - Document the `fake_auth_super_admin` sandbox toggle in
     `spec/settings_inventory.md` (alongside the existing `FAKE_AUTH_*` rows)
     and in the local-dev notes (`docs/local_setup.md` / `docs/codespace_setup.md`,
     which already state the fake operator carries "operator + sys-admin" — update
     to "operator + sys-admin + super-admin").

**Sequencing:** 1 → 2 → 3 (→ 3a → 3b) → 4. PR 1 must precede PR 2 (guards
assume nesting); PR 3 must follow PR 2 (UI mirrors the server guards). PR 4 can
ride alongside PR 3 or land as its own slice.

**Test files to extend** (existing coverage to build on): the guard suite
`tests/integration/test_sys_admin_users.py`; the self-heal / bootstrap seam
`tests/integration/test_operator_allowlist_gate.py`; chrome + `require_sys_admin`
`tests/integration/test_sys_admin_chrome.py`; config validation
`tests/unit/test_config_validation.py`.

---

## Item 2 — No-super-tier fallback (fix the admin-management lockout)

**Status: building 2026-08-17.**

**The problem (footgun from Item 1).** `promote` / `demote` require the
**actor** to be a super-admin (`requires_super_admin`), but super-admin is
derived only from `SUPER_ADMIN_EMAILS`. A deployment that leaves that list
empty — e.g. one bootstrapped only via `SYS_ADMIN_EMAILS` (the documented
"seed the first admin" path) — has **no valid actor**, so admin promote/demote
becomes impossible for everyone. `SUPER_ADMIN_EMAILS` is optional (Item 1
Decision 4), so this is reachable by a correct-looking config.

**The fix (Option A — graceful fallback).** When **no super-admin tier is
configured at all** (`effective_super_admin_emails()` is empty), fall back to
the pre-18S rule: any admin may promote/demote admins. The strict
super-admin-only enforcement engages **only once a super-admin exists**. This
can never lock anyone out, keeps `SUPER_ADMIN_EMAILS` optional, and the
no-super case simply behaves like the old two-tier model. (Rejected
alternative: requiring `SUPER_ADMIN_EMAILS` in the `validate_critical_settings`
fail-fast — secure-by-default but a breaking config requirement that reverses
Decision 4.)

**Scope.**
- `app/services/users.py::_guard_actor_super_admin` — early-return (allow) when
  `effective_super_admin_emails()` is empty; enforce only when the tier exists.
- `app/web/routes_operator/_sys_admin.py` — pass `can_manage_admins`
  (`user.is_super_admin OR no super tier configured`) to the page.
- `templates/operator/sys_admin_users.html` — gate the Promote/Demote toolbar
  on `can_manage_admins` (else the UI hides controls a plain admin is now
  allowed to use).
- `app/main.py::create_app` — a startup **warning** log (not a raise) when a
  deployed (non-local) env boots with no super-admin configured, so the
  degraded-to-two-tier state is visible in logs.
- Tests: plain admin **can** promote/demote when `SUPER_ADMIN_EMAILS` is empty;
  **cannot** once a super-admin exists (Item 1 behaviour preserved); the UI gate
  follows.
- Docs: note the fallback in `docs/security_posture.md` + this plan.

**Definition of done.** With `SUPER_ADMIN_EMAILS` unset, a plain admin can
promote/demote admins again (no lockout); with it set, Item 1's strict rule and
the protected-super-admin guarantee are unchanged. Full suite + `ruff` green.

---

## Future items (add as they come up)

Landing place for further small in-app security / authz refinements
(e.g. audit-surface access tightening, rate-limit / abuse guards, session
fixation / CSRF posture review, permission-check coverage sweeps). Log new
ones here as `Item N` with the same problem / fix / scope / done-when shape.
The user will populate this list as security refinements are identified.

---

## Doc impact

- `spec/audience_and_identity_model.md` §4 — rewrite to the three-tier role
  model (Item 1).
- `docs/deployment_dev.md` / `docs/deployment_nus.md` §7 — document
  `SUPER_ADMIN_EMAILS` (and §7.1: the seeded admin can be made a protected
  super-admin).
- `docs/security_posture.md` — record the role hierarchy + the
  protected-super-admin guarantee.
- `docs/status.md` — record when an item ships.
