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

## Item 1 — Protected super-admin (unremovable in-app)

**The problem.** The Sys Admin page (`/operator/sys-admin/users`) can
demote, revoke, and hard-remove any workspace user. The only guards today
(`app/services/users.py`) are **identity-agnostic**:

- `_guard_self` — you can't act on *yourself*;
- **last-sys-admin floor** — can't demote/remove the *only* remaining
  sys-admin (count-based);
- ownership guards (`still_owner` / `owns_sessions`).

So the **originally-seeded admin has no special standing** — any *other*
sys-admin can demote or remove them as long as one admin remains. Two
current behaviours make this an unreliable half-protection:

- `remove_user` **hard-deletes** the row; if that email is still in
  `SYS_ADMIN_EMAILS`, the person is **re-seeded on next sign-in** (accidental
  resurrection).
- `demote` leaves the row, so the env-var seed list is **inert** afterwards —
  the demotion sticks and the seed list does *not* protect them.

There is no way to designate an account that **cannot be removed or demoted
from within the app**.

**The fix — anchor protection in deployer config.** Add a **`SUPER_ADMIN_EMAILS`**
setting (App Service App Setting / `.env`), kept **distinct** from the general
`SYS_ADMIN_EMAILS` seed list so "seeded once" ≠ "protected forever." Because
App Settings are **not editable from inside the app**, no in-app admin can
touch a protected account — only someone with Azure config access can, by
editing the setting and restarting.

1. **Config** — `app/config.py`: `super_admin_emails: list[str]` (same
   `NoDecode` + comma-split validator as `operator_emails` /
   `sys_admin_emails`). Env `SUPER_ADMIN_EMAILS`.
2. **Guards** — in `app/services/users.py`, `demote` / `revoke` /
   `remove_user` / `remove_from_all_sessions` refuse when
   `target.email ∈ super_admin_emails` (case-insensitive), raising a new
   `UserOperationError(code="protected_super_admin", …)`. This sits *above*
   the last-admin floor — it protects a *specific* account, not just a count.
3. **Self-healing (recommended)** — a `SUPER_ADMIN_EMAILS` address is always
   granted `is_operator = is_sys_admin = True`. Decide between: (a) enforce
   only at first-sign-in bootstrap (`app/web/deps.py`), matching the existing
   seed model; or (b) **re-assert on every sign-in** for protected emails, so
   a pre-feature manual demotion can't leave a "protected" account without
   rights. Lean (b) — cheap, and it makes the guarantee real regardless of
   prior DB state.
4. **UI** — the Sys Admin user list shows a **"protected"** badge on those
   rows and hides/disables the Demote / Revoke / Remove controls (the POST
   guards remain the real enforcement; the UI is just honest about it).

**Scope / size.** One config field + guards in ~4 service functions + the
bootstrap tweak + a Sys Admin template touch + tests. No migration (config,
not schema). Self-contained.

**Definition of done.**

- With `SUPER_ADMIN_EMAILS=<email>` set, an in-app sys-admin **cannot**
  demote, revoke, remove, or strip sessions from that account — each attempt
  returns `protected_super_admin` and a clear message.
- A protected email always resolves to a full-rights sys-admin on sign-in
  (per the chosen self-healing rule).
- Unit tests cover each guarded path + the bootstrap/self-heal; full suite +
  `ruff` green.
- `docs/deployment_dev.md` + `docs/deployment_nus.md` §7 document
  `SUPER_ADMIN_EMAILS` (and §7.1 notes the seeded admin can be made
  protected); `docs/security_posture.md` notes the protection.

**Open question.** Should the last-admin floor be *replaced* by
"≥1 protected super-admin must exist," or kept as an independent backstop?
Default: keep both — they guard different things (count vs identity).

---

## Future items (add as they come up)

Landing place for further small in-app security / authz refinements
(e.g. audit-surface access tightening, rate-limit / abuse guards, session
fixation / CSRF posture review, permission-check coverage sweeps). Log new
ones here as `Item N` with the same problem / fix / scope / done-when shape.
The user will populate this list as security refinements are identified.

---

## Doc impact

- `docs/deployment_dev.md` / `docs/deployment_nus.md` — document
  `SUPER_ADMIN_EMAILS` (Item 1).
- `docs/security_posture.md` — note the protected-super-admin guarantee.
- `docs/status.md` — record when an item ships.
