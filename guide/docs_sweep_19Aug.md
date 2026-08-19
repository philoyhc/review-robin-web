# Docs sweep — audit & recommendations (2026-08-19)

A whole-`docs/` audit comparing every file against the shipped code.
Ran as four parallel code-verified passes over the 20 files in `docs/`;
every finding below cites `file:line` and the contradicting reality (a
code path, a workflow job, a sibling doc).

`docs/` is meant to answer *"how does X work today?"* — operational
reference for the running system. This audit sorts each file by the
action it needs, into the four buckets requested:

1. **[Revise into a `spec/` doc](#1-revise-into-a-spec-doc)** — content that is design / contract intent, not "how it works today."
2. **[Update in place](#2-update-in-place)** — factual drift; the file stays in `docs/`.
3. **[Consolidate](#3-consolidate)** — overlapping or coupled files that should merge / reconcile.
4. **[Retire](#4-retire)** — outlived its usefulness, or its live content is already covered elsewhere.

Files needing none of the above are listed under
[Current](#current--no-action). A cross-cutting-fixes list and a
reference-repointing appendix follow.

> **Nothing has been changed yet.** This is a decision-support
> document; the retire / move items in particular are structural and
> want a green light before execution. Any retire or move must also
> **repoint the live references** catalogued in
> [Appendix A](#appendix-a--reference-repointing-required).

---

## Summary

| File | Verdict | Bucket |
|---|---|---|
| `status.md` | Update | 2 |
| `README.md` | Update (index) | 2 |
| `quickstart.md` | Update (minor) | 2 |
| `architecture.md` | Current | — |
| `rehydrate.md` | Revise → `spec/` | 1 |
| `authentication.md` | Consolidate → `security_posture.md` (then retire) | 3 / 4 |
| `database.md` | Update | 2 |
| `imports.md` | Retire | 4 |
| `local_setup.md` | Update + consolidate w/ `codespace_setup.md` | 2 / 3 |
| `codespace_setup.md` | Current (consolidation candidate) | 3 |
| `deployment_dev.md` | Update (dead link) | 2 |
| `deployment_nus.md` | Current | — |
| `operations_runbook.md` | Update | 2 |
| `troubleshooting.md` | Current | — |
| `backup_restore.md` | Update | 2 |
| `known_limitations.md` | Update | 2 |
| `azure_provision.md` | Current | — |
| `azure_github_setup.md` | Consolidate / reconcile w/ `deployment_nus.md` | 3 |
| `cli_setup.md` | Current (absorbs `cli_setup_notes.md`) | 3 |
| `cli_setup_notes.md` | Retire (fold into `cli_setup.md`) | 3 / 4 |

---

## 1. Revise into a `spec/` doc

### `rehydrate.md` — move to `spec/rehydrate.md` (trim the build scaffolding)

The content is **accurate** — every load-bearing reference verified
live (`routes_operator/_rehydrate.py`, `breadcrumbs.operator_rehydrate_session`,
`app/services/session_rehydrate.py`, `app/services/extracts/responses_import.py`,
the `rehydrate_stash` model). But the file is titled *"functional spec"*
and still carries pre-implementation design records — **§10 "Resolved
decisions", §11 "New machinery to build", §12 "Testing expectations"** —
which read as `spec/` design intent, not `docs/`-style "how it works
today." Recommendation: relocate to `spec/rehydrate.md` and trim (or
demote) the build-time sections, leaving `docs/` to link it. Low
urgency — it misleads no one, it's just filed in the wrong folder.

---

## 2. Update in place

Factual drift; each file stays in `docs/`.

### `status.md` — **Update** (body is current to 18S; header + a few rows lag)

- **L3 "As of: 2026-06-05 / latest 18P" trails the body.** The segment
  index already records **18R + 18S dated 2026-08-17** (L190–191) and
  the three-tier super-admin model (L236–241). Refresh the "As of"
  banner + intro to name 18S as latest.
- **L348–349 list the retired session `/edit` page as a live form.**
  `GET /operator/sessions/{id}/edit` is now only a redirect stub to
  `?editing=1#session-config` (`_session_home.py:234`); the apply route
  is `POST .../config` (`_session_home.py:413`); **no `POST .../edit`
  exists.** Both rows are stale.
- **Segment index skips 18Q** (L189 18P G2 → L190 18R). Add an 18Q row
  (blob-storage deferral, no-code) so the sequence reads complete.
- **L206** "VNet integration deferred to Segment 14" contradicts the
  doc's own L54 (post-14A sweep reworded VNet as "deferred
  infrastructure").
- Correctly captured (no drift): RTD retirement (L182), the 18R bulk
  accepting/visibility toggle retirement + routes/audit events
  (L385–386, 667). These match code.

### `database.md` — **Update** (Tests section is inverted; table count stale)

- **L90–96 "Tests" is backwards on two counts.** (1) Says the fixture
  lives in `tests/db/conftest.py` — **that file doesn't exist**; the
  fixture is in `tests/conftest.py`. (2) Claims tests apply `alembic
  upgrade head` "not `Base.metadata.create_all()`" — the **exact
  opposite** of `tests/conftest.py:41`, which builds the SQLite schema
  from `Base.metadata.create_all` as the fast path and only runs the
  migration chain on the Postgres path.
- **L33 "all 12 tables" → 21 tables** (`grep __tablename__` over
  `app/db/models/`).
- Deferred pointer already correct (`guide/deferred_consolidated.md` at
  L84, L162 — the freshly-moved target). ✅

### `local_setup.md` — **Update** (Segment-4-era staleness)

- **L163–165** "Expected: **24 passed**, ~1 second … `tests/db/`
  fixtures run `alembic upgrade head`." Wrong on all three counts:
  there are **240** `test_*.py` files; the fixture uses
  `Base.metadata.create_all` (`conftest.py:41`); the real runtime is
  ~35s with `-n auto` (as `codespace_setup.md:80` already states).
- **L49** "12 domain models" → **20** model files.
- **L249–268 §10 "What is intentionally not in this segment yet"** —
  every row shipped long ago (CSV import, assignment gen, reviewer
  surface, email, exports, rule-based, 14A). **Retire the section.**
- **L263** cites `guide/archive/unfinished_business.md` items #27–#29 as
  "the remainder" — that catalog retired 2026-05-10 (dead pointer).
- Note: §3 (auth) *was* refreshed (correct 18S super-admin detail), so
  the file is only partly stale. (Also a **consolidation** candidate
  with `codespace_setup.md` — see §3.)

### `security_posture.md` — **Update** (mostly current; strong doc)

- **L208 deferred-hardening row is stale:** "In-app operator/sys-admin
  revoke UI | Segment 16A PR 6 — not yet shipped." Revoke **shipped**
  (18S): `app/services/users.py` `admit`/`revoke`/`promote`/`demote`/
  `remove_from_all_sessions`/`remove_user`, fronted by
  `/operator/sys-admin/users` routes. Move this row out of "Deferred."
- **Participant gates missing** from the authz model (L32–33) and the
  §5.6 table (L82): add `require_reviewee_in_session` +
  `require_observer_in_session` (shipped, wired into
  `routes_reviewer/_results.py`, `_collation.py`).

### `operations_runbook.md` — **Update**

- **L56–58** "In-app revoke UI is not yet shipped (Segment 16A PR 6);
  revoking access is a manual `UPDATE users SET is_operator=false`."
  Superseded by the 18S Sys Admin users page
  (`_sys_admin.py` revoke/promote/demote/remove routes).
- **L47–54** allowlist section is pre-18S — describes only
  `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS`; add the three-tier model +
  `SUPER_ADMIN_EMAILS` (`app/auth/roles.py`).

### `known_limitations.md` — **Update** (one stale entry)

- **L34–36** "Revoking operator/sys-admin access is a manual database
  `UPDATE` until Segment 16A PR 6 ships." Same as above — in-app
  revoke/demote shipped in 18S. Remove or reword.
- Speculative watch: a `deploy_nus.yml` + `docs/deployment_nus.md` now
  exist (NUS migration underway), so the "single environment" framing
  may need revisiting — but the dev slot is still the live target, so
  not yet wrong.

### `backup_restore.md` — **Update** (one stale line)

- **L68–69** "`users` … removed only by a manual DB operation (no
  in-app user delete yet)." `remove_user` (`app/services/users.py:388`)
  provides in-app deletion via the Sys Admin UI (with
  `protected_super_admin` / `last_admin` guards).

### `deployment_dev.md` — **Update** (dead link)

- **L14** cites `guide/segment_05A.md §3.1` — that file is now at
  `guide/archive/segment_05A.md`. Repoint. (Env-var table + all workflow
  claims verified accurate against
  `.github/workflows/main_app-review-robin-web-dev.yml`.)

### `quickstart.md` — **Update** (minor; otherwise current)

- **L259** calls Extract data "the card on Session Home"; it's its own
  Operations-strip page (`GET /sessions/{id}/extract-data`). Fix the
  placement wording. (Operator flow otherwise matches live routes; no
  retired concepts; screenshot slots reconciled.)

### `README.md` — **Update** (index integrity)

- **Missing a row for `cli_setup_notes.md`** (the file exists but isn't
  in the table). Moot if that file is retired per §4 — but the index
  must end consistent with whatever moves happen here.
- Every other row maps to an existing file with an accurate
  description. Whatever we retire / move below, this index is the last
  step to reconcile.

### Cross-cutting batch fixes

Two errors repeat across files — fix once, apply everywhere:

- **"No in-app revoke UI (Segment 16A PR 6)"** — stale in **three**
  docs: `security_posture.md:208`, `operations_runbook.md:56–58`,
  `known_limitations.md:34–36`. All superseded by the 18S Sys Admin
  users page.
- **conftest fixture / test-count inversion** — in **two** docs:
  `database.md:90–96` and `local_setup.md:163–165`. Both claim
  `alembic upgrade head` where the reality is `Base.metadata.create_all`
  (`tests/conftest.py:41`), both cite a nonexistent `tests/db/conftest.py`,
  and both carry stale counts (12→21 tables; 24→240 test files; 12→20
  models).

---

## 3. Consolidate

### `cli_setup_notes.md` → fold into `cli_setup.md`, then retire

`cli_setup_notes.md` is **not a document** — it's a raw four-item
editing worklist (L1: *"Update docs/cli_setup.md A2.1 to say that the
below is not a real 'error'"*). Its four corrections should land in
`cli_setup.md` and the scratch file be deleted:

- the WSL `WSL_E_VM_MODE_INVALID_STATE` "not a real error" note;
- clone-repo-before-identity-check reordering (Appendix A.5);
- `az login` before B.5;
- the `PG_SERVER` / `MY_IP` shell setup — a **genuine fix**: `cli_setup.md`
  B.9.4 (L534–539) uses `$PG_SERVER` / `$MY_IP` but never defines them.

Its own pointer is already imprecise (cites section "A2.1"; the appendix
uses `A.1`–`A.8`). An unfinished editing TODO shouldn't live in `docs/`
as a peer document.

### `authentication.md` ↔ `security_posture.md` — merge the accurate core, drop the stale

`authentication.md`'s core (Easy Auth header parsing, `AuthenticatedUser`,
`ALLOW_FAKE_AUTH`, the CSRF decision) is accurate and widely referenced,
but two sections are dead weight:

- **L150–156 "What this segment does not implement"** claims no DB user
  records, no roles/permissions, no magic links — **all three shipped**
  (`User` + `get_or_create_user`, the 18S three-tier model, magic-link
  invitations). A stale Segment-3 snapshot.
- **L159–165 authorization list** is incomplete (missing the participant
  gates + the super-admin tier).

It already "pairs with `security_posture.md`," and the two overlap on
Easy Auth / CSRF / identity trust. Recommendation: **fold the accurate
identity-mechanics into `security_posture.md`** (which already owns the
authz model + audits) and retire the standalone `authentication.md`, OR
— if kept — update in place per the two findings above. Either way the
"does not implement" section goes. *(This is the file the request
flagged for retirement; retiring it is defensible only after its live
identity-mechanics content lands in `security_posture.md`, since
CLAUDE.md / README / architecture / `security_posture.md` all link it —
see Appendix A.)*

### `local_setup.md` ↔ `codespace_setup.md` — overlapping dev-env setup

`codespace_setup.md` is self-described as a "companion to `local_setup.md`"
and covers the same ground (running the suite + dev server, SQLite +
fake auth, Postgres-parity). `codespace_setup.md` is **current**;
`local_setup.md` is **stale** (§2 above). Options: merge into one
"developer setup" doc (Codespace as a section), or keep both but fix
`local_setup.md` so they stop drifting apart. Merging is cleaner given
the shared surface.

### `azure_github_setup.md` ↔ `deployment_nus.md` — reconcile contradictory topologies

`azure_github_setup.md` (self-labelled **"v0.1 draft"**) describes a
**two-environment PRD + NPRD** topology (Functions, App Configuration,
Communication Services) that **contradicts** the authoritative
single-pilot plan: `azure_provision.md:8–19` ("single sandboxed pilot —
**not** a PRD/NPRD split") and `deployment_nus.md` (a single PRD
environment). The deploy-identity design also diverges — Phase 4
hardcodes GitHub environments `production`/`staging`, while
`deployment_nus.md:205–210` designs a single generic `environment:<name>`
NUS credential. A reader following both runbooks gets conflicting OIDC
setups. This is forward-looking greenfield planning; either **reconcile
/ merge into `deployment_nus.md`**, or **move it to `guide/`** as a
scale-up target so it stops reading as the current plan. `cli_setup.md`
is coupled to it (shared `production`/`staging` + `psql-nrrw-nprd`
naming) — its references should travel with whatever we decide.

---

## 4. Retire

### `imports.md` — retire (dead core + live content covered elsewhere)

- **L77–149 "ManualAssignment CSV" — describes a removed feature.** The
  manual-CSV assignment upload route was retired 2026-05-11
  (`_assignments.py:277`); the documented Preview/Save workflow and its
  error table no longer exist.
- **L83–123 `AssignmentContext1/2/3`** — retired entirely in 15D PR 6b
  (`assignments/_coverage.py:79`); the `Assignment.context` JSON column
  it "lands in" **was dropped** (pair-context now comes from the
  `relationships` table).
- The **still-live** part (reviewer / reviewee CSV columns) is already
  covered by **`spec/csv_contracts.md`** (which itself points back here
  as "implementation-side notes") and the `quickstart.md` operator
  manual. So the unique content is dead and the live content is
  duplicated. Recommendation: **retire**, or reduce to a one-line stub
  pointing at `spec/csv_contracts.md` + `quickstart.md`. (Minor live
  gap to fold into `csv_contracts.md` if not already there: the reviewer
  importer also accepts a **`PhotoLink`** column — `csv_imports.py:299`
  → `Reviewer.profile_link`.)

### `cli_setup_notes.md` — retire (after folding its fixes into `cli_setup.md`; see §3)

### Section-level retirements (inside otherwise-kept files)

- `local_setup.md` **§10** (L249–268) — obsolete "not yet implemented" table.
- `authentication.md` **L150–156** — obsolete "does not implement" section.
- `status.md` **L348–349** — the retired `/edit`-page route rows.

---

## Current — no action

`architecture.md` (infra topology, internally consistent; one forward
note: it calls the storage account "no blob dependency" while
`deployment_nus.md` calls the same account the "18Q blob store" — true
today since 18Q is deferred, will diverge when 18Q lands),
`deployment_nus.md` (matches `.github/workflows/deploy_nus.yml` exactly;
status "plan" by design), `azure_provision.md` (SKUs consistent; code
path `assignments/_generate.py` correct), `cli_setup.md` (current once it
absorbs `cli_setup_notes.md`), `codespace_setup.md` (clean; consolidation
candidate only), `troubleshooting.md` (entries map to real behavior).

---

## Appendix A — reference repointing required

Retiring / moving a doc breaks live cross-references. **Frozen files are
left alone** (`guide/archive/**`, dated `codebase_assessment_*`
snapshots) — their links were correct when written. The **live**
references to reconcile:

**If `imports.md` is retired:**
- `spec/csv_contracts.md:32` ("implementation-side notes on the …").
- `README.md:168`, `CLAUDE.md:230`, `AGENTS.md:230` ("deeper dives" list).
- `docs/README.md:18` (index row).

**If `authentication.md` is retired / merged into `security_posture.md`:**
- `README.md:119`, `README.md:168`; `CLAUDE.md:230` + `AGENTS.md:230`
  (byte-identical twins — edit both).
- `spec/settings_inventory.md:442`.
- `docs/architecture.md:77`, `docs/codespace_setup.md:213`,
  `docs/local_setup.md:236`, `docs/deployment_dev.md:257`,
  `docs/security_posture.md:5,167,186`, `docs/azure_github_setup.md:76`.
- `docs/README.md:16` (index row).
- `guide/todo_master.md:76` (CSRF write-up pointer).

**If `azure_github_setup.md` moves to `guide/`:** its companions
`cli_setup.md` + `cli_setup_notes.md` reference it, and it's linked from
`docs/README.md`. Move/repoint together.

`docs/README.md` is the hand-maintained index — reconcile it **last**,
after the moves settle, so it ends pointing only at files that exist.

---

## Appendix B — out-of-scope aside (code / spec, not `docs/`)

The audit surfaced one non-`docs/` drift worth logging: `expired` is a
**live** lifecycle state (`expire_session`, `ready → expired`), but
`app/services/session_lifecycle.py:6–7,55–57` code comments and
`spec/lifecycle.md`'s header still call it "reserved." A comment-level
nit; fold into the next lifecycle touch.
