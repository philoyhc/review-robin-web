# docs/

**Reference material about the running system.**

Answers the question: *how does X work today?* Subsystem
deep-dives: deployment, operations, security, the database, and the
limits a pilot should know. What the product does is `spec/`; what is
still to be built is `guide/todo_master.md`; what shipped and when is
the archived segment plans (`guide/archive/README.md`).

| File | Covers |
|---|---|
| `archive/status.md` | **Retired 2026-10-05.** Was the implementation-status file: an "As of" narrative, the project timeline from 2026-09-12, a Segments shipped table, and "Capabilities today" / "What's deliberately not yet there" / "Architectural notes". By then it was 457 KB, and nearly all of it restated an archived plan or a spec. Its two facts stated nowhere else moved first (to `local_setup.md` and `spec/operator_ui_concept.md`). Kept as a dated record; **do not update it**. |
| `archive/status_history.md` | **Retired 2026-10-05 with `archive/status.md`.** The timeline rows dated 2026-09-11 and earlier, split out of the status file on 2026-09-19. Verbatim. |
| `archive/quickstart.md` | **Retired 2026-09-06 — superseded by the in-app Guide at `/guide`.** Was the operator manual: an end-to-end walkthrough for a colleague running their first review. Segment 19E rung 2 moved the material into `app/web/templates/guide.html` and made that canonical, so the documentation lives where the app is. Kept as the record of what the Guide was built from; **do not edit it** — corrections go to the template. |
| `architecture.md` | Cloud / deployment topology (App Service + Postgres + Key Vault + Monitor + Storage behind Easy Auth), a rendered diagram, and the provisioned-resource cost table. The infra companion to `spec/architecture.md` (which covers the app's domain layering). |
| `database.md` | SQLAlchemy + Alembic conventions, dialect parity, where Postgres lives. |
| `local_setup.md` | Developer how-to for running tests, migrations, and the dev server locally — including a **Running in a GitHub Codespace** section (absorbed from the retired `codespace_setup.md`: SQLite + fake auth, port forwarding, optional Postgres parity + devcontainer). |
| `deployment_dev.md` | Dev Azure App Service deployment notes (resource names, env vars, GRANT bootstrap, planned production flow). |
| `deployment_nus.md` | **Migration runbook** — moving the deploy target from personal Azure to the institutional (NUS) host while keeping localhost + CI unchanged, then retiring personal Azure. Comprehensive GitHub-side (OIDC federated identity, secrets, workflow target) + Azure-side (the settings `nus_azure_status.md` leaves to it, NUS Entra Easy Auth, DB bootstrap, the in-VNet runner every pipeline job needs) checklists, cutover order, and verification. |
| `nus_azure_status.md` | **Current NUS production Azure handoff/status** (2026-10-01) — verified network/App Service/Postgres/Key Vault/App Gateway/runner state, plus the two active external blockers: Southeast Asia runner VM capacity awaiting Microsoft Support, and the production domain/hostname decision being rationalized across analogous citizen-developed applications. Renamed from nus_azure_status_v7.md on 2026-10-05: the revision number lives in its `Status date` line, so a new revision edits the file in place rather than repointing every citation. |
| `operations_runbook.md` | Day-to-day procedures for operating the deployed service (deploy, restart, logs, secrets). |
| `troubleshooting.md` | Symptom-driven diagnosis for the deployed dev slot. |
| `backup_restore.md` | Database backup / restore mechanism and data-retention notes. |
| `known_limitations.md` | Current scope limits and deferred items, stated plainly for a pilot. |
| `security_posture.md` | Authorization model (three-tier operator/admin/super-admin), permission / destructive-action audit, the identity subsystem (Easy Auth headers, `AuthenticatedUser`, `ALLOW_FAKE_AUTH`, diagnostic routes — absorbed from the retired `authentication.md`), CSRF posture (full write-up), deferred hardening. |
| `archive/azure_provision.md` | **Retired 2026-10-03 — superseded by `nus_azure_status.md`.** Was the pricing-calculator shopping list: the Azure resources (SKU + price knobs) to estimate for a single sandboxed pilot, sized to carry a ~1,500-reviewer review. Kept as the record of the estimate and its sizing rationale; **do not plan from it**. |
| `archive/azure_github_setup.md` | **Retired 2026-10-03 — superseded by `deployment_nus.md`.** Was the 8-phase Azure + GitHub setup runbook for a two-environment PRD / NPRD build (a `v0.1 draft`) that was never executed; the NUS environment was provisioned on a different shape. Kept as the record of that draft; **do not execute from it**. |
| `cli_setup.md` | Workstation companion to `deployment_nus.md` (first written for the retired `archive/azure_github_setup.md`) — CLIs needed on your workstation, shell-choice notes for Windows, one-time auth setup, plus WSL2 setup on Windows 11 and connectivity tests to run before the cutover. (Absorbed the former `cli_setup_notes.md` scratch fixes: the WSL "not a real error" note, clone-before-identity-check, `az login` before B.5, and the `PG_SERVER`/`MY_IP` definitions in B.9.4.) |
| `unenforced_conventions.md` | The list `constitution.md` VI promises: §1 the conventions deliberately left as guidance, each with the reason a check would be worse; §2 the revisit queue of rules that could be derived but are not yet. |
| `archive/practice-audit-2026-09-04.md` | **Retired 2026-10-04 — a dated record, superseded as a live view by `unenforced_conventions.md` and `rrw_sdd_in_practice.md`.** Development-practice audit (2026-09-04) — what actually gates a merge, and which project conventions are enforced mechanically vs by the developer noticing. Establishes that the merge discipline (stratify by what the diff touches; wait for `ci-postgres` when it could matter) is sound and followed, so branch protection was *not* recommended; found the enum→display-label convention mechanised in code but drifted in three specs, and retired button terminology still live in `spec/rehydrate.md` (both fixed in #2086). Its two recommendations — a documentation-drift test derived from `DISPLAY_LABELS`, and a fresh-context diff reviewer — both shipped (#2086, #2087); see the status block at the top of the document. Appendix A benchmarks the practice against loop engineering and the 2026 vibe-coding evidence. Every claim is reproducible or flagged as an inference. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.
