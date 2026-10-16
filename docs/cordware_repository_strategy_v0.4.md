# Cordware Repository and Deployment Strategy

**Version:** 0.4 draft  
**Status:** Adopted project direction following NUS IT advice on 16 October 2026.  
**Architecture:** Multi-repo development, Cordware integration repo, one production deployment.

---

## 1. Decision

Cordware production will use:

> **independent canonical source repositories -> automated synchronization -> one Cordware integration/deployment repository -> one Azure App Service.**

The canonical repos remain:

- `philoyhc/review-robin-web`
- `philoyhc/nuscr-res-apps`
- future app-specific repos as needed

A new repo should be created for Cordware, e.g.:

`philoyhc/cordware`

Cordware is not the normal development repo for RRW or Residential Apps.

---

## 2. Repository responsibilities

### `review-robin-web`

Authoritative for:

- RRW source code;
- RRW tests;
- RRW migrations;
- RRW authorization;
- RRW docs/issues/PR history;
- RRW release-worthy revisions.

### `nuscr-res-apps`

Authoritative for:

- Residential Apps source code;
- Leave / Events / Support modules;
- Residential authorization;
- Residential DB migrations;
- Residential docs/issues/PR history;
- release-worthy revisions.

### `cordware`

Authoritative for:

- Cordware landing shell;
- shared authenticated-identity plumbing;
- integrated route composition;
- exact set of upstream app revisions included;
- cross-module integration tests;
- production packaging;
- production Azure deployment.

---

## 3. Cordware repo shape

Suggested structure:

```text
cordware/
├── app/
│   ├── core/
│   ├── reviewrobin/          # synchronized; not edited directly
│   ├── residentialapps/      # synchronized; not edited directly
│   └── future_app/
├── module-manifest.yml
├── integration-tests/
├── deployment/
├── docs/
└── .github/workflows/
```

---

## 4. Source of truth rule

> **Never maintain application code independently in both the source repo and Cordware.**

The source application repo is authoritative.

The synchronized Cordware subtree is generated/imported material.

If a Cordware test exposes a bug in RRW or Residential Apps, fix the source repo first and resync.

---

## 5. Sync mechanism

Preferred mechanism:

> **automated one-way synchronization PR**

For RRW:

1. select/approve an RRW commit;
2. automation checks out `review-robin-web`;
3. automation checks out `cordware`;
4. replace `app/reviewrobin/`;
5. update `module-manifest.yml`;
6. commit on a Cordware branch;
7. open a PR;
8. run Cordware integration CI;
9. merge deliberately.

The same process applies to Residential Apps.

Do not push synchronized source directly into Cordware `main`.

---

## 6. Module manifest

Example:

```yaml
modules:
  reviewrobin:
    repo: philoyhc/review-robin-web
    commit: <sha>
    path: app/reviewrobin

  residentialapps:
    repo: philoyhc/nuscr-res-apps
    commit: <sha>
    path: app/residentialapps
```

The manifest is the production composition record.

It supports:

- auditability;
- rollback;
- reproducibility;
- identification of the exact upstream source revision in production.

---

## 7. CI model

### Source repo CI

Validates that an individual app revision is internally sound.

### Cordware CI

Validates that the selected set of app revisions works together inside the shared deployment.

Cordware CI should include:

- shell/navigation tests;
- shared identity tests;
- `/reviewrobin` integration tests;
- `/residentialapps` integration tests;
- cross-module regression tests;
- config collision checks;
- migration orchestration checks;
- production packaging tests.

---

## 8. Production deployment

Only the Cordware repo deploys the adopted single-App-Service production architecture.

This means one:

- production workflow;
- GitHub OIDC deploy identity;
- Azure role assignment;
- self-hosted runner target;
- App Service deployment target.

Source application repos do not need production Azure RBAC merely to participate in Cordware.

This is a primary reason the adopted architecture reduces recurring IT work.

---

## 9. OIDC transition

Current RRW OIDC federation refers to:

`repo:philoyhc/review-robin-web:ref:refs/heads/main`

The Cordware production deploy identity/federation should eventually refer to:

`repo:philoyhc/cordware:ref:refs/heads/main`

or an environment-based subject if a protected GitHub production environment is adopted.

The project cannot create Azure role assignments, so IT may be required once to grant the Cordware deployment identity Website Contributor or the agreed least-privilege role on the production App Service.

The old RRW production deployment identity can remain during transition and later be retired or repurposed.

---

## 10. App repos remain independently deployable in principle

The canonical source repos should retain enough deployment knowledge that they can later return to independent production deployment if the infrastructure model changes.

For example, if future subdomains become available:

```text
reviewrobin.<approved-domain>
    <- deploy from review-robin-web

residentialapps.<approved-domain>
    <- deploy from nuscr-res-apps
```

This is why Cordware should not absorb ordinary application development history.

---

## 11. No repo rename required

Under the adopted model:

- do **not** rename `review-robin-web` to Cordware;
- do **not** rename `nuscr-res-apps`;
- do **not** make either one the umbrella repository.

Create a separate Cordware repo.

This preserves project identity and makes the architecture reversible.

---

## 12. Secrets and configuration

A shared repo/deployment does not imply indiscriminate secret sharing.

Cordware production config should distinguish:

### Shared/platform

- Azure tenant/subscription;
- App Service target;
- common Easy Auth identity;
- common host;
- common logging.

### RRW-specific

- RRW DB URL/secret;
- RRW operator/admin config;
- RRW-specific integration settings.

### Residential-specific

- Residential DB URL/secret;
- RA/staff/admin config;
- module-specific settings.

Use separate Key Vault secrets/config namespaces where practical.

---

## 13. Database/migration ownership

Application migrations are authored in the canonical source repos.

They are synchronized into Cordware with the module source.

Cordware deployment coordinates the migration sequence but does not become the only place where migration history exists.

---

## 14. Write protection for synchronized modules

Recommended controls:

- documentation markers: "generated from upstream; do not edit directly";
- CODEOWNERS/review rules;
- CI check that manifest/source markers exist;
- sync job replaces the full module subtree;
- optionally reject direct edits to synchronized trees unless made by the sync workflow.

---

## 15. Development workflow example

### RRW feature

```text
feature branch in review-robin-web
    -> RRW PR
    -> RRW CI
    -> merge to RRW main
    -> sync-to-Cordware workflow
    -> Cordware PR
    -> Cordware integration CI
    -> merge
    -> Cordware production deployment
```

Residential Apps follows the same pattern.

---

## 16. Migration into this repo model

1. create `philoyhc/cordware`;
2. add Cordware shell skeleton;
3. add `module-manifest.yml`;
4. define the synchronized module contract;
5. retrofit RRW for Cordware module composition;
6. build RRW sync automation;
7. sync RRW;
8. prove integration;
9. adapt Residential Apps to the same contract;
10. build Residential Apps sync automation;
11. add Cordware production workflow;
12. obtain final Azure OIDC/RBAC setup;
13. deploy from Cordware.

---

## 17. Strategic benefit

This model preserves the principal advantage of separate projects while still complying with the IT-advised operational architecture.

It gives:

- independent app development;
- one institutional web namespace;
- one certificate;
- one App Service;
- one Easy Auth boundary;
- one Azure deployment identity;
- one production pipeline;
- straightforward future return to separate deployments.

The concise model is:

> **separate where development benefits from separation; combine only at the integration/deployment boundary.**
