# Segment 18S — Security refinements

**Status:** Planning. A holding segment for **small, self-contained security
/ authorization hardening** on shipped surfaces. Items land as independent
slices; the segment stays open as a home for further security refinements as
they're identified.

> Distinct from `guide/deferred_infra.md` (Azure-portal / platform hardening
> — Key Vault, VNet, private endpoints) and from `docs/security_posture.md`
> (the standing description of the current posture). 18S is **in-app**
> authorization / account-safety work the agent can implement and test.

---

## Item 1 — Three-tier role model + protected super-admin

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

Config field + derived `is_super_admin` property + self-heal in
`get_or_create_user` + actor-super guard on promote/demote + target-super
guard on demote/revoke/remove(+from-all-sessions) + Sys Admin template (tier
badges + conditional controls) + tests. **No migration** (super-admin is
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
