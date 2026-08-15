# Blob storage — candidate uses (stub)

> **Status: stub / not built.** Review Robin Web has **no application
> blob storage** today, by deliberate choice — every current need is met
> with Postgres `bytea`, on-the-fly streaming, or external URLs (see
> "Current posture" below). Provisioning an Azure Blob container (or
> S3-compatible bucket) is **deferred infrastructure**
> (`guide/deferred_infra.md` §1 — needs the Azure portal + a managed
> identity + a storage account). This doc exists to **capture the
> candidate uses** so that, if and when blob storage is provisioned, the
> decision is made against a considered list rather than reached for
> reflexively. It is a companion to `docs/backup_restore.md` (which
> records that exports are stream-only) and `spec/email_infra_options.md`
> (the sibling "options" spec for the email backend).

Nothing here is a commitment. Adding blob storage is a real cost — a new
`azure-storage-blob` dependency, container provisioning + lifecycle
policies, a managed-identity grant, and the loss of the current
"one Postgres, no object store" operational simplicity. Each use below
should clear that bar on its own before it lands; several never will.

---

## Current posture — how these needs are met without blob storage

| Need | Handled today by |
|---|---|
| Rehydrate Validate→Commit hand-off | `rehydrate_stashes.payload` — a zipped file set in a Postgres `bytea` (`LargeBinary`) column, TTL-swept (`spec`/`docs/rehydrate.md` §3.3). Survives scale-out; **no blob store required**. |
| CSV / ZIP extracts (`export/*.csv`, `bundle.zip`) | Generated on demand and **streamed** to the operator's browser; never written server-side, never retained (`docs/backup_restore.md`). |
| Uploaded roster / config / responses CSVs | Parsed **in memory** and discarded once the import completes; only the resulting rows persist. |
| Reviewee / reviewer photos | `profile_link` is an **external URL** the operator supplies — the app hosts no image bytes. |
| Operator SMTP password | `smtp_password_encrypted` — Fernet ciphertext in a `bytea` column, not a file. |
| Deployment artifacts | Azure **does** use blob for build/deploy artifacts, but that is platform-level and outside the app (`docs/architecture.md` — "the application itself has no blob storage"). |

The line to hold: **small, transient, or already-in-Postgres** payloads
stay where they are. Blob storage earns its place only when a payload is
**large, retained, or served directly to a third party**.

---

## Potential uses (if blob storage becomes available)

Ordered roughly by how likely each is to clear the cost bar. The
**Prioritization** section below records which of these are actually
being pursued and in what order; #5 (hosted photos) and #8 (email
attachments) are **parked** — not in the current set.

### 1. Large / async extract generation and delivery
The Zip-all setup bundle and the responses bundle are streamed
synchronously today. For a large session (hundreds of reviewers ×
multi-instrument responses) that risks request timeouts and holds a
worker for the whole generation. **Blob would let** an extract be
generated once into a container, then handed to the operator as a
**time-limited (SAS) download URL** — decoupling generation from the
request, enabling background/async generation, and allowing a short
retention window instead of "the only copy is the operator's download."

### 2. Rehydrate stash payload offload
`rehydrate_stashes.payload` is a `bytea` blob in the hot database. It is
small and transient today, but a rehydrate set for a 1,500-reviewer
session (the case `responses_import.py` is explicitly sized for) can be
multi-megabyte, and every stash bloats Postgres storage + backups.
**Blob would let** the stash row hold only a **blob key + token + TTL**,
with the bytes in object storage under a **lifecycle rule** that mirrors
the 1-hour TTL — moving large transient blobs off the DB. (Keep the
`bytea` path as the fallback; the model already uses portable
`LargeBinary`.)

### 3. Async / chunked large uploads
CSV imports are capped (`csv_imports`: 5000 rows / 1 MiB) and held in
memory; the rehydrate responses parser deliberately has **no** such cap.
Very large uploads strain the request path. **Blob would let** a big
upload land in a container first (direct-to-blob or streamed), then be
processed in the background, with progress tracked in Postgres — the same
staging pattern as (1) in reverse.

### 4. Operator- / Observer-published reports
`spec/visibility_policy.md` sketches a future **published-report**
mechanism (cohort-aggregate summaries an operator or observer explicitly
makes available). Such reports — HTML snapshots, PDFs, or CSVs frozen at
publish time — need somewhere durable to live and a shareable link.
**Blob would be** the natural home: publish → store → serve via SAS URL to
the named audiences, with revocation by deleting/expiring the blob.

### 5. Directly-hosted participant photos
Today `profile_link` leans on an external URL the operator maintains.
**Blob would let** operators **upload** reviewer/reviewee photos, hosted
in a container and referenced by a stable key — removing the dependency on
external image hosts and their availability / hotlink rules. (Adds
content-type + size validation + a moderation/again-cost consideration.)

### 6. Audit-log cold storage / archival
`audit_events` is the append-only spine and grows unbounded. Retention /
purge is partly deferred (18C scheduled purge). **Blob would let** old
audit rows be archived to append-only JSONL objects (cheap, immutable,
lifecycle-tiered) before trimming the hot table — keeping the compliance
trail while bounding Postgres growth. Pairs with the deferred JSON→JSONB
work in `guide/deferred_infra.md` §2.

### 7. Backup / restore artifacts
`docs/backup_restore.md` notes storage is a deferred item. **Blob would**
give a place for DB dumps, point-in-time snapshot exports, or a
"download everything" session archive — distinct from the platform-level
Azure backup of the Postgres server itself.

### 8. Email attachments (only if the product grows them)
The `email_outbox` today carries rendered text, no attachments. If a
future feature emails a results PDF or a bundle, **blob would** hold the
attachment bytes with the outbox row referencing a key — rather than
inlining large binaries into the mail path or the DB.

---

## Prioritization

The set being pursued is **#1, #2, #3, #4, #6, #7**. #5 (hosted photos)
and #8 (email attachments) are parked. The ordering below reflects
dependency structure, not just value: the six all sit on a foundation
that isn't itself one of them, and two of them share plumbing.

### Phase 0 — the prerequisite (gates everything)
Provision the storage account + build the thin
`app/services/blob_store.py` seam (`put` / `get` / `signed_url` /
`delete` / `sweep`, same shape as `rehydrate_stash`) + the optional
`blob_*` config that degrades to today's `bytea` / streaming paths. Not
one of the six, but nothing below ships without it — so it is the real
first move. See "If it lands — where it plugs in."

### Tier 1 — pilot integration (do first)
- **#2 Rehydrate stash offload.** Smallest, most self-contained, lowest
  risk: the stash already exists as portable `LargeBinary`, the seam is
  shaped like it, and the change is additive (nullable `blob_key` +
  `bytea` fallback). Its role is to **validate the seam** on an existing
  feature before anything bigger is built. Modest standalone value (only
  bites at ~1,500-reviewer scale); high value as the de-risking step.

### Tier 2 — the flagship pair (build the async-staging plumbing once)
- **#1 Async extract generation + SAS delivery.** Highest user-facing
  value; fixes a real latent pain (request timeouts + a worker held for
  the whole generation on large sessions; "the only copy is the
  operator's download"). The produce-once / serve-via-signed-URL pattern
  is the reusable core.
- **#3 Async / chunked large uploads.** The inbound mirror of #1 — reuses
  the same staging plumbing in reverse for the uncapped rehydrate
  `responses.csv` / large rosters. Ships right after #1 while that
  machinery is fresh.

### Tier 3 — deferred, gated on other work
- **#6 Audit-log cold storage.** Gated on a retention / purge policy
  decision (18C scheduled purge is partly deferred) and pairs with the
  JSON→JSONB migration (`guide/deferred_infra.md` §2). A scale /
  compliance concern that does not bite pre-pilot.
- **#7 Backup / restore artifacts.** Largely overlaps the platform-level
  Azure Postgres backup that already exists at the server tier; the
  app-level "download everything" archive is a safety-net nicety. Lowest
  urgency of the set.

### Outside the ladder — blocked on product design
- **#4 Operator- / Observer-published reports.** In the pursued set, but
  **blocked on a feature that does not exist yet**, not on storage: the
  published-report mechanism is only sketched in `spec/visibility_policy.md`
  as future work, and blob is a *downstream dependency* of it. It cannot
  be sequenced until that feature is specced — revisit when the report
  feature is designed rather than slotting it into a tier above.

**Build order:** Phase 0 seam → **#2** → **#1** → **#3**, then #6 / #7
opportunistically; #4 waits on its own feature.

This ladder is planned in detail — with a comprehensive Phase 0 covering
dependencies, config, CI (an Azurite job), deploy/runtime wiring, and
provisioning docs — in **`guide/segment_18Q_blob.md`**. Institutional Azure
blob provisioning has been requested (account awaiting finalization);
Phase 0 + Tier-1 testing are buildable on localhost now (memory /
filesystem backends + the Azurite emulator) without the account.

---

## Cross-cutting primitives blob would bring

Independent of any single use, object storage supplies a few primitives
the current stack lacks:

- **Time-limited signed URLs (SAS / presigned)** — hand a third party a
  scoped, expiring link without proxying bytes through the app. Enables
  (1), (4), (5).
- **Lifecycle / TTL expiry at the storage layer** — auto-delete transient
  blobs on a schedule, matching things like the rehydrate stash TTL (2)
  without an app-side sweeper.
- **Cheap, tiered, near-unbounded capacity** — moves large or cold bytes
  off expensive hot Postgres storage + backups (2), (6), (7).
- **Decoupled async generation** — produce-once, serve-many, out of the
  request path (1), (3).

---

## If it lands — where it plugs in

- **Dependency + config.** Add `azure-storage-blob` (or an S3 SDK); one
  `blob_*` settings block in `app/config.py`; a managed-identity grant on
  the storage account (mirrors the Key Vault / VNet items in
  `guide/deferred_infra.md` §1). Keep it **optional** — a `None` config
  falls back to today's `bytea` / streaming paths so SQLite tests and
  no-blob deployments keep working.
- **A thin `app/services/blob_store.py` seam.** `put(key, bytes) -> url`,
  `get(key) -> bytes`, `signed_url(key, ttl)`, `delete(key)`, `sweep()` —
  the same shape as `rehydrate_stash`, so a payload can be swapped from
  `bytea` to blob behind the service without touching callers.
- **Model changes are additive.** Tables that currently hold `LargeBinary`
  (e.g. `rehydrate_stashes.payload`) gain a nullable `blob_key` and keep
  the inline column as the fallback — no destructive migration.
- **Portability caveat.** Per the repo convention, tests run on SQLite and
  CI round-trips Postgres; a blob seam must degrade to in-DB / in-memory so
  neither dialect nor the test suite depends on a live storage account.

---

## See also

- `docs/backup_restore.md` — exports are stream-only; storage deferred.
- `guide/deferred_infra.md` §1 — blob provisioning as Azure portal work.
- `docs/rehydrate.md` §3.3 — the current `bytea` stash ("no blob storage
  required").
- `spec/email_infra_options.md` — sibling "options" spec (email backend).
- `spec/visibility_policy.md` — the future published-report mechanism (use #4).
