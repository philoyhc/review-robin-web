# Segment 18Q — Blob storage (object store seam + first consumers)

**Status:** Planning. Grounded in `spec/blob_storage.md` (candidate uses +
prioritization) and `guide/deferred_infra.md` §1 (the portal-side storage
prerequisite). Institutional Azure blob provisioning has been **requested**
(account awaiting finalization), so object storage is now a real option
rather than a hypothetical.

> **Key sequencing fact:** the account is *not* a blocker for starting.
> **Phase 0 and all Tier-1 test coverage are buildable and testable on
> localhost today** — against an in-memory/filesystem backend (pytest/CI)
> and the **Azurite** emulator (real SDK path) — with zero dependency on the
> real storage account. The account only gates the final Tier-3 validation
> on the Azure dev slot.

---

## Why this segment

`spec/blob_storage.md` established that RRW has **no application blob
storage** today (every need met by Postgres `bytea`, on-the-fly streaming,
or external URLs) and catalogued the candidate uses. The pursued set is
**#1, #2, #3, #4, #6, #7** (photos #5 + email attachments #8 parked). This
segment turns that into an ordered slice ladder, **foundation first**.

The foundation is deliberately not one of the six uses: it is the
`blob_store` seam plus the cross-cutting plumbing (dependencies, config,
CI, deploy/runtime wiring, provisioning docs) that every use sits on.
Getting Phase 0 comprehensive and de-risked is the whole point of landing
it before any consumer.

---

## Phase 0 — the foundation (comprehensive)

Phase 0 ships **no user-visible behaviour**. It lands the seam + all the
plumbing so a consumer can be wired with a one-line `get_blob_store()`
call. It must leave the test suite **Azure-free** and every deployed/no-blob
environment working exactly as before (`blob_backend` defaults to a
non-Azure backend).

Answering the framing question directly — **yes, several cross-cutting
files need additions beyond the service code.** The full checklist:

### P0.1 — Dependencies (`pyproject.toml` **and** `requirements.txt`)

There is **no `requirements.md`** — runtime deps live in two files kept in
sync by hand (same discipline as the `CLAUDE.md`/`AGENTS.md` twins):

- `pyproject.toml` `[project].dependencies` — the source of truth for
  `pip install -e .[dev]` (local + both CI jobs).
- `requirements.txt` — consumed by the Azure deploy build job (Oryx /
  `pip install -r requirements.txt`).

Add to **both**:

- **`azure-storage-blob>=12`** — the Blob SDK (put/get/delete, container
  ops, SAS generation). Works against Azurite via a dev connection string.
- **`azure-identity>=1.17`** — `DefaultAzureCredential` for
  managed-identity auth in deployed Azure (no account key), and the
  user-delegation-key path for MI-based SAS.

Design guard so this stays cheap for tests: the Azure SDK is imported
**lazily inside `AzureBlobStore` only**. `MemoryBlobStore` /
`FilesystemBlobStore` never import it, so the pytest default path has no
Azure import cost and no live-account dependency even though the wheels are
installed. (Alternative considered — an optional `[azure]` extra — rejected
because the deploy build installs `requirements.txt`, not an extra, so the
SDK would be absent in production. Base deps + lazy import is simpler and
correct.)

### P0.2 — Config (`app/config.py` + `.env.example`)

New `Settings` fields (env-var-backed, `pydantic-settings`), all optional
with safe defaults:

| Field | Default | Purpose |
|---|---|---|
| `blob_backend` | `"memory"` (local/tests) → `"none"` for prod default? see note | `none` / `memory` / `filesystem` / `azure` — selects the backend. |
| `blob_connection_string` | `None` | Azurite / shared-key local dev (`UseDevelopmentStorage=true`). |
| `blob_account_url` | `None` | `https://<acct>.blob.core.windows.net` — managed-identity path in Azure. |
| `blob_container` | `"rrw"` | Container name. |
| `blob_local_dir` | `./.blobstore` | Root dir for the `filesystem` backend. |
| `blob_sas_ttl_minutes` | `15` | Default TTL for generated signed URLs. |

- **Backend-default note:** tests/local default to `memory`; the deployed
  default should be `none` until the container is provisioned, so a
  mis-set env can't silently half-enable blob. Consumers must treat a
  `none` backend as "feature off, use the existing `bytea`/streaming path."
- Extend `validate_critical_config` (the startup guard): when
  `blob_backend == "azure"`, require exactly one of `blob_connection_string`
  or `blob_account_url`; in a non-local `app_env`, warn (don't hard-fail —
  it's opt-in) if a consumer expects blob but `blob_backend == "none"`.
- `.env.example` gains a commented blob block: `BLOB_BACKEND=memory` for the
  no-Azurite path, plus the Azurite `BLOB_CONNECTION_STRING` /
  `BLOB_BACKEND=azure` recipe commented out.

### P0.3 — The seam (`app/services/blob_store.py`)

A small, backend-agnostic service shaped like `rehydrate_stash` so a
`bytea` payload can be swapped to blob behind it without touching callers.

- **Protocol / ABC `BlobStore`** with:
  - `put(key, data: bytes, *, content_type: str | None = None) -> None`
  - `get(key) -> bytes | None`
  - `exists(key) -> bool`
  - `delete(key) -> None`
  - `signed_url(key, *, ttl_minutes: int | None = None) -> str | None`
    — a time-limited download URL, or **`None`** when the backend can't
    mint one (memory/filesystem).
  - `sweep(prefix: str, *, older_than: timedelta) -> int` — app-side TTL
    sweep (the fallback for backends/plans without storage-lifecycle rules).
  - `supports_signed_urls: bool`
- **Backends:** `MemoryBlobStore` (dict), `FilesystemBlobStore` (tmp/dir,
  good for a persistent local dev without Azurite), `AzureBlobStore` (lazy
  SDK import; MI via `DefaultAzureCredential` when `blob_account_url` is
  set, else connection-string/Azurite; SAS via user-delegation key under
  MI, service SAS under shared key).
- **Factory** `get_blob_store(settings) -> BlobStore` (cached), returning a
  sentinel/`None`-equivalent for `blob_backend == "none"`.
- **App-served fallback route** (Phase 0 or first consumer): a
  permission-checked `GET …/blob/{opaque_key}` that streams
  `blob_store.get(key)` — the download path when `signed_url` returns
  `None`, and the option the institution can prefer over exposing SAS URLs
  at all. Consumers branch: `signed_url(key) or app_download_url(key)`.

### P0.4 — Tests (Azure-free by default) + optional Azurite CI job

- **Backend contract tests** — one parametrized suite run against
  `MemoryBlobStore` + `FilesystemBlobStore` asserting the `BlobStore`
  contract (put→get round-trip, `exists`, `delete`, `sweep` by
  prefix+age, `signed_url` returns `None` where unsupported). Runs in the
  normal SQLite/pytest job — **no Azure, no Azurite** — so CI stays
  hermetic.
- **Azurite integration test** — an `@pytest.mark.azurite` suite exercising
  the **real `AzureBlobStore` SDK path**: container create, put/get/delete,
  and **SAS generation + validation** (fetch the blob back through the
  signed URL). Skipped by default.
- **New CI job `ci-azurite`** (mirrors `ci-postgres`): a
  `mcr.microsoft.com/azure-storage/azurite` **service container** on ports
  10000–10002, `BLOB_BACKEND=azure` +
  `BLOB_CONNECTION_STRING=UseDevelopmentStorage=true`, running only the
  `azurite`-marked subset. This is how the real SDK integration is
  validated in CI without a real account — the direct analogue of how
  `ci-postgres` validates the Postgres dialect. **Cannot** cover
  managed-identity token auth or storage-lifecycle policies (Azurite
  emulates neither — those are Tier-3 dev-slot checks).

### P0.5 — Deploy + runtime wiring (workflow, App Service, managed identity)

- **Deploy workflow (`main_app-review-robin-web-dev.yml`).** The build job
  installs `requirements.txt`, so the added SDK ships automatically — **no
  workflow edit needed for the dependency.** The workflow itself does *not*
  set runtime config (it only uses `secrets.DATABASE_URL` in the migrate
  job); leave it unchanged unless we choose to script app-settings via
  `az webapp config appsettings set` (currently portal-managed — keep that
  convention).
- **App Service App Settings** (portal, per `docs/deployment_dev.md`
  "Set as App Service App Settings"): `BLOB_BACKEND=azure`,
  `BLOB_ACCOUNT_URL=https://<acct>.blob.core.windows.net`,
  `BLOB_CONTAINER=<name>`. No connection-string secret when using managed
  identity.
- **Managed identity + role assignment** (portal / IaC — `deferred_infra`
  §1 territory, needs the finalized account): assign the App Service's
  system-assigned (or a user-assigned) identity the **Storage Blob Data
  Contributor** role scoped to the storage account/container. This is the
  keyless auth path `DefaultAzureCredential` uses; it mirrors the Key Vault
  managed-identity direction already sketched in `deferred_infra` §1.
  Prefer it over an account-key/connection-string secret.
- **Container posture:** private (no anonymous access); access only via MI
  or short-TTL user-delegation SAS; encryption-at-rest is on by default;
  consider blob soft-delete + a lifecycle rule for transient prefixes
  (the storage-side counterpart to `sweep`).

### P0.6 — Provisioning + docs

- `docs/azure_provision.md` §7 — currently says "RRW's application code
  needs **no** blob storage (verified: no `azure-storage` dependency)".
  **This becomes stale the moment P0.1 lands.** Rewrite it to: a real
  storage-account line (SKU/redundancy/region), the private-container +
  MI-role-assignment steps, and the cost note.
- `docs/deployment_dev.md` — add the three `BLOB_*` App Settings to the
  env table + a note on the MI role assignment.
- `docs/local_setup.md` — add an **Azurite** section (Docker
  `mcr.microsoft.com/azure-storage/azurite` or `npm i -g azurite`; blob
  endpoint `127.0.0.1:10000`; `UseDevelopmentStorage=true`), plus the
  simpler `BLOB_BACKEND=filesystem` no-emulator path.
- `docs/security_posture.md` / `docs/backup_restore.md` — update the
  "storage is a deferred item / no blob storage configured" notes once the
  seam exists (SAS TTLs, private container, MI-over-keys).
- `guide/deferred_infra.md` §1 — mark the storage-account + role-assignment
  as the active portal prerequisite for this segment.
- `spec/blob_storage.md` — cross-link this segment; move its "If it lands —
  where it plugs in" from hypothetical to "implemented in 18Q Phase 0."

**Phase 0 involves no Alembic migration** — the seam is standalone. The
first *consumer* (#2) adds the first nullable `blob_key` column.

---

## Consumer phases (from `spec/blob_storage.md` prioritization)

Each consumer is additive and keeps its pre-blob path as the fallback when
`blob_backend == "none"`.

### Tier 1 — pilot integration
- **C1 (use #2) — Rehydrate stash offload.** `rehydrate_stashes` gains a
  nullable `blob_key`; `rehydrate_stash.put/get/sweep` write/read the
  payload via `blob_store` when a backend is configured, else keep the
  existing `bytea` column. **First real consumer** — validates the seam
  end-to-end on an existing, well-tested feature with a built-in fallback.
  One small additive migration. Full pytest coverage via the memory
  backend; Azurite smoke via `ci-azurite`.

### Tier 2 — the flagship pair (shared async-staging plumbing, built once)
- **C2 (use #1) — Async extract generation + SAS delivery.** Generate the
  Zip-all / responses bundle into blob (background), hand the operator a
  `signed_url` (or the app-served fallback), short retention. Introduces
  the produce-once/serve-via-URL plumbing (a small jobs/staging table +
  status).
- **C3 (use #3) — Async / chunked large uploads.** The inbound mirror —
  stage a large rehydrate `responses.csv` / roster upload into blob, then
  process in the background. Reuses C2's staging plumbing in reverse.

### Tier 3 — deferred, gated on other work
- **C4 (use #6) — Audit-log cold storage.** Archive aged `audit_events` to
  append-only JSONL blobs before trimming the hot table. Gated on a
  retention/purge policy decision (18C scheduled purge is partly deferred)
  and pairs with the JSON→JSONB migration (`deferred_infra` §2).
- **C5 (use #7) — Backup / restore artifacts.** App-level "download
  everything" session archive to blob. Largely overlaps platform-level
  Postgres backup; lowest urgency.

### Outside the ladder — blocked on product design
- **(use #4) — Operator-/Observer-published reports.** In the pursued set
  but **blocked on a feature that doesn't exist yet**, not on storage: the
  published-report mechanism is only sketched in `spec/visibility_policy.md`.
  Blob is a downstream dependency — revisit when that feature is designed.

**Landing order:** **Phase 0 (P0.1 → P0.6)** → **C1** → **C2** → **C3**,
then C4 / C5 opportunistically; use #4 waits on its own feature.

---

## Testing strategy (three tiers)

Mirrors the repo's existing "SQLite/CI locally, real validation on the dev
slot" posture:

1. **pytest / CI (Azure-free):** memory + filesystem backends prove the
   seam contract, every consumer's logic, and the `bytea`/streaming
   fallback. The primary pre-PR gate. Runs in the existing SQLite +
   `ci-postgres` jobs unchanged.
2. **Azurite (`ci-azurite` + local):** real `azure-storage-blob` SDK path,
   container ops, and SAS sign+verify — locally (Docker/npm) and in CI via
   a service container. Opt-in (`@pytest.mark.azurite`).
3. **Azure dev slot:** managed-identity token auth and storage-lifecycle
   policies — the two things Azurite can't emulate — validated after the
   account finalizes, per the standard dev-slot verification convention.

---

## Done when

- `get_blob_store()` is callable; memory + filesystem + Azure backends pass
  the shared contract suite; `ci-azurite` is green.
- A no-blob (`blob_backend == "none"`) environment behaves exactly as
  before — no consumer regressions; the full existing suite stays green.
- `azure-storage-blob` + `azure-identity` are in **both** `pyproject.toml`
  and `requirements.txt`; the deploy build installs them; the SDK is
  imported lazily so the pytest default path never touches Azure.
- The provisioning + deployment + local-setup + security docs reflect blob
  as real (no stale "no blob dependency" line).
- **C1 (rehydrate stash)** round-trips a payload through Azurite in
  `ci-azurite` and through the memory backend in the normal suite, with the
  `bytea` fallback still covered.

---

## Doc impact

- **New:** this file; cross-linked from `spec/blob_storage.md` +
  `guide/deferred_infra.md` §1 + `guide/todo_master.md` roadmap.
- **Update on Phase 0:** `pyproject.toml`, `requirements.txt`,
  `app/config.py`, `.env.example`, `docs/azure_provision.md` §7,
  `docs/deployment_dev.md`, `docs/local_setup.md`,
  `docs/security_posture.md`, `guide/deferred_infra.md` §1,
  `.github/workflows/` (+`ci-azurite.yml`).
- **Update per consumer:** `docs/rehydrate.md` §3.3 (C1),
  `docs/backup_restore.md` (C5), `docs/status.md` (each shipped slice),
  `spec/blob_storage.md` (flip uses from "candidate" to "shipped").

---

## Open questions for IT / account finalization

- **Auth model:** managed identity + role assignment (preferred, keyless)
  vs. an account-key/connection-string secret. Confirms whether we need a
  new GitHub/App Service secret at all.
- **Redundancy / region / SKU** for the storage account (cost + latency).
- **Lifecycle policies:** are storage-side auto-expiry rules available for
  transient prefixes, or do we rely solely on the app-side `sweep`?
- **SAS vs app-proxied downloads:** does the institution allow handing
  browsers time-limited SAS URLs, or must all bytes proxy through the app
  (the `GET …/blob/{key}` fallback)? Drives C2's delivery design.
