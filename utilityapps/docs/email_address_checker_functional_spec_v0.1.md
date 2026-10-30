# Cordware Utilities — Email Address Checker

**Functional specification:** v0.1 (proposed)  
**Date:** 30 October 2026  
**Status:** Built as phase 1 by segment U1 (2026-10-30); the contract as built is `utilityapps/spec/email_check.md`, which governs where the two differ. Decisions taken at build are listed under "Revisions at build" below.  
**Suggested source location:** `utilityapps/docs/email_address_checker_functional_spec_v0.1.md` in `philoyhc/review-robin-web`  
**Primary audience:** Codex/implementation agents, Cordware administrators and reviewers

## Revisions at build (segment U1, 2026-10-30)

Kept here so this proposal and the built contract can be read together
(`utilityapps/guide/archive/segment_U1_email_checker.md`, "Judgment calls"):

- **CSRF** (§4, §10): RRW's posture, Easy Auth plus `SameSite=Lax`
  cookies (`docs/security_posture.md` "CSRF posture"), not per-form tokens.
- **One query** (§5 steps 1–2): `mail eq '…' or userPrincipalName eq '…'`
  per address, through the host's shared Graph helper
  (`cordware/spec/identity.md` "Graph"). The real-tenant smoke test
  confirms the combined form; splitting it is a one-function change.
- **No server state** (§3, §10): the preview carries the file back in the
  page, and the result page carries the CSV as a `data:` download; the
  server holds neither between requests.
- **Limits** (§4, §10): request sizes are refused on `Content-Length`
  before parsing; the whole check has a 120 s budget, after which
  unfinished lookups are `ERROR` and the rest still download; a refused
  sign-in stops the remaining lookups.
- **Not built:** alias lookup (§5 step 3, phase 2), so every run is
  `BASIC_ONLY`. A cell over the `csv` module's 131,072-character limit is
  refused by name.

## 1. Decision: a cluster for small applications

**Recommended cluster name:** **Cordware Utilities** (short label: **Utilities**). The purpose is to accommodate small, general-purpose institutional or administrative tools that do not belong to Review Robin or Residential Apps.

| Existing family | Public entry or mounts | Responsibility |
|---|---|---|
| Review Robin | `/reviewrobin` | Its own mature application and data |
| Residential Apps | `/residentialops`, `/supportlogs` | Residential operations and sensitive student support, independently authorized |
| **Cordware Utilities** (proposed) | **`/utilities`** | A lightweight collection of independent, narrowly scoped tools |

The Utilities family is **one Cordware-mounted application**, initially providing a Utilities index and the Email Address Checker at **`/utilities/email-check`**. Subsequent small tools can be separate feature modules under the same mount when they share reasonable authorization and operational requirements. Tools with materially different confidentiality or trust boundaries can instead become their own Cordware mounts.

**Proposed code package:** `utilityapps/` (rather than `tools/`, which already denotes development/deployment scripts in the repositories). Proposed registry key `utilities`, factory `utilityapps.main:create_app`, logger prefix `utilityapps`, health path `/utilities/health`.

This is an architectural proposal, not an existing registry entry.

## 2. Purpose and rationale

Review Robin has an established email-based identity and permission model. Institutional users may have several deliverable addresses (a UPN, primary mailbox address, and secondary/friendly SMTP aliases) belonging to **one** Entra account. As a result, an email list may mix different representations of the same person.

Rather than redesign the mature Review Robin user model now, provide a separate **read-only CSV-in/CSV-out directory checking utility**. Administrators upload a list of email addresses and receive a CSV identifying those resolvable in Entra, their primary address, and any duplicated Entra identities within the upload. Administrators make corrections outside this tool.

The checker may also be used to clean up provisional Residential Apps roster source files, but does **not** replace Residential Apps' first-sign-in identity binding or its roster administration.

### In scope

- Upload a CSV containing institutional email addresses.
- Check each unique address against Microsoft Graph on behalf of a signed-in, authorized administrator.
- Compare against users' `mail` (primary email) and `userPrincipalName` (UPN).
- Attempt secondary-alias resolution **only after capability and permission have been verified in the institutional tenant**.
- Produce a result CSV that preserves input rows, marks the lookup status, and, where found, includes institutional account details and a suggested primary email.
- Highlight two or more different input addresses resolving to the same Entra user object ID.
- Permit a new check by uploading a new file; no persistent directory import or write-back.

### Out of scope (v1)

- Modify Entra/Exchange, Review Robin, or Residential Apps databases.
- Automatically merge Review Robin user records or change their role assignments.
- Automatically decide which email the Easy Auth identity will supply to Review Robin.
- Interactive fuzzy name matching, arbitrary directory browsing, mailbox deliverability tests, Teams or Forms integration, background sync, scheduled jobs.
- Claim that an address is undeliverable, unowned, or invalid simply because Graph user lookup finds nothing.

## 3. User, access, and workflow

**V1 authorized operator:** Cordware platform super-admin only, using the established `SUPER_ADMIN_EMAILS` predicate and trusted Easy Auth identity. No new generic permission framework is introduced for this utility. Reconsider app-specific grants if there is a demonstrated need for non-super-admin operators.

The operator:

1. Opens Cordware landing page → **Utilities** → **Email Address Checker**.
2. Uploads a `.csv` file. The page detects `email` by header, or asks the operator to choose a column from the CSV header.
3. Reviews a lightweight preview: row count, selected column, blank/invalid addresses, repeated input addresses. No Graph calls before explicit **Check addresses** action.
4. Runs the check using the operator's delegated Graph token.
5. Sees a result summary with counts by status and a **Download checked CSV** action.
6. Downloads the annotated CSV and applies any changes in the source system manually.

A single-page or simple two-step server-rendered interface is sufficient. The desktop-first CSV workflow must still be functional on narrow screens. No spreadsheet-like editing grid, database, or task queue is required for v1.

If the operator is authenticated but not authorized, respond with a normal **403** (not an invitation to request access). If delegated Graph access is not available, show a clear error and do not infer negative results.

## 4. Input contract

- **Format:** UTF-8 CSV (UTF-8 with BOM accepted); one header row; RFC 4180-style quoting handled by the CSV parser.
- **Email column:** `email` by default (case-insensitive name match), otherwise explicit operator selection.
- **Other columns:** Accepted and preserved in the output in original order, enabling use with Review Robin exports and residential roster CSVs.
- **Whitespace/case:** Preserve original value; derive a lookup key by stripping leading/trailing whitespace and lowercasing only. Do not rewrite the original cell silently.
- **Duplicates:** Preserve every input row, including duplicate addresses; look up each normalized unique address at most once per run.
- **Invalid/empty values:** Mark `INVALID_INPUT`, retain the row and do not send a Graph request.
- **Initial limits:** Maximum 500 data rows and 1 MiB per file, configurable after real-world testing. Show a clear rejection if exceeded rather than partially processing without notice.
- **Security:** Reject non-CSV uploads and malformed input; enforce request-size limits, CSRF protection (as built: Easy Auth plus `SameSite=Lax`, "Revisions at build"), safe CSV parsing, bounded memory and request timeouts. Prevent CSV formula injection in exported cells that Excel may interpret as formulas, while retaining the source data faithfully in a safe form.

The app should not treat an email address as authenticated evidence of account ownership. The CSV is merely a collection of addresses for investigation.

## 5. Directory lookup and matching

The initial Microsoft Graph permission is **delegated `User.ReadBasic.All`**, already declared and tenant-wide consented for Cordware. It permits the signed-in administrator to list/read other users' basic profile fields, including `id`, `displayName`, `mail`, and `userPrincipalName`. This does not require the person being checked to sign in.

### Lookup order

For each normalized, valid, distinct input address:

1. Query Graph's **user** directory for an exact `mail` match.
2. Query for an exact `userPrincipalName` match if necessary; or combine compatible queries if the implementation confirms equivalent semantics.
3. **Optional alias probe**, behind an explicitly enabled capability flag: attempt an exact match in `proxyAddresses` using a Graph query form demonstrated to work in the NUS tenant for the delegated token. SMTP address case and the primary/secondary distinction must be handled correctly. This is a proof-of-capability gate, **not** an assumed feature of `User.ReadBasic.All`.
4. Deduplicate results by Entra `id` (within the tenant). Do not infer a match from display names or approximate string similarities.
5. Return Graph's basic attributes, plus the *method by which the account was resolved*.

Lookups must be safely URL-encoded, properly escape OData string literals, and must not be implemented by downloading the entire directory into application memory. Use pagination only where required to establish uniqueness. In the event of multiple different matching user objects, do not pick a winner.

### Permission and alias caveat

Microsoft Graph documents `proxyAddresses` as the Exchange-related list of associated mailbox addresses, and documents certain advanced queries on it. **It remains to be established empirically** whether the existing delegated permission permits a useful exact-alias lookup in NUS. Access to the `proxyAddresses` result property, filtering by it, and NUS directory policy should be tested separately. Do not silently fall back to broad tenant-directory download. If alias lookup needs additional permission, document the exact least-privileged option and obtain approval before enabling it.

An address that belongs to a distribution list, shared mailbox, guest, external user, or other non-user object may not resolve via `/users`. The checker makes no assertion about mailbox deliverability.

## 6. Result classification

| `status` | Meaning | Action |
|---|---|---|
| `OK` | Input matches a user account's Graph primary `mail` | No primary-email correction suggested |
| `USE_PRIMARY` | A unique user is found by UPN or a **verified** secondary alias; their nonempty Graph `mail` differs from input | Show primary address for consideration |
| `FOUND_NO_PRIMARY` | Unique user found but Graph `mail` is empty/null | Report ID/UPN, no recommended primary email |
| `NOT_FOUND` | No user found through the lookup methods actually available for this run | Investigate; not proof of an invalid mailbox or nonexistent alias |
| `AMBIGUOUS` | Different Entra user objects appear to match | No recommendation; manual review |
| `INVALID_INPUT` | Missing/clearly malformed address | Correct CSV input |
| `ERROR` | Lookup incomplete: token, permission, network, timeout or rate-limit problem | Retry later; never classify as `NOT_FOUND` |

Additional **`match_type`**: `PRIMARY_MAIL`, `UPN`, `SMTP_ALIAS`, `NONE`, or `MULTIPLE`. `SMTP_ALIAS` is never emitted unless alias lookup has been verified and actually returned a unique user.

Additional **`lookup_coverage`**: `BASIC_ONLY`, `ALIAS_ENABLED`, or `ALIAS_UNAVAILABLE`. This avoids concealing the fact that `NOT_FOUND` may mean *unresolved secondary alias* if the current permission cannot query aliases.

`recommended_email` means **Graph's primary `mail` for correspondence**, where available. It is *not* certified as the login identifier for Review Robin. Both `userPrincipalName` and `recommended_email` are exported independently.

### Example (illustrative only)

Input:

```csv
email,source_role
jane.tan@example.edu,Reviewer
e0123456@example.edu,Reviewer
jane@example.edu,Reviewer
unknown@example.edu,Reviewer
```

Possible output **only if Graph resolves the alias**:

```csv
email,source_role,status,match_type,lookup_coverage,recommended_email,user_principal_name,display_name,entra_object_id,duplicate_account_group,notes
jane.tan@example.edu,Reviewer,OK,PRIMARY_MAIL,ALIAS_ENABLED,jane.tan@example.edu,e0123456@example.edu,Jane Tan,11111111-1111-4111-8111-111111111111,1,
e0123456@example.edu,Reviewer,USE_PRIMARY,UPN,ALIAS_ENABLED,jane.tan@example.edu,e0123456@example.edu,Jane Tan,11111111-1111-4111-8111-111111111111,1,
jane@example.edu,Reviewer,USE_PRIMARY,SMTP_ALIAS,ALIAS_ENABLED,jane.tan@example.edu,e0123456@example.edu,Jane Tan,11111111-1111-4111-8111-111111111111,1,
unknown@example.edu,Reviewer,NOT_FOUND,NONE,ALIAS_ENABLED,,,,,,No user-directory match
```

In a **basic-only** run, the third row may instead be `NOT_FOUND` with `lookup_coverage=BASIC_ONLY`, even if the address delivers to Jane's mailbox.

The output must include the original row/columns, retaining original order. New columns must be prefixed or renamed on collision with uploaded columns, and the exported CSV must be safe to open in spreadsheet software.

## 7. Duplicate-account detection

After lookups, group all successfully resolved rows by `(tenant_id, entra_object_id)`; a group is notable when it contains **two or more distinct normalized input addresses**. Assign a run-local `duplicate_account_group` label and present the count of groups in the summary.

This flags apparent alias-related duplicates in the source list. It does **not** assert that two Review Robin database records should automatically merge: they may have different historical activity, permissions or other application state.

Exact duplicate input addresses should be counted separately in the preview, not mistaken for alias-related duplicates.

## 8. Review Robin compatibility warning

Review Robin is mature and must **not** be changed by this utility. The current shared Cordware identity adapter (`cordware/identity.py`) derives its `Identity.email` from Easy Auth claims in priority order, using the email-address claim, then `preferred_username`, then `email`, with a fallback to the simple principal-name header when it looks like an address.

Therefore:

- `mail` is a useful **primary mailbox address**, not necessarily the exact email used as Review Robin's application identity key.
- `userPrincipalName` is a useful **institutional sign-in identifier**, not necessarily the actual value Review Robin sees in Easy Auth headers.
- A `USE_PRIMARY` suggestion must **not** be bulk-applied to Review Robin users without first comparing it with a real production Easy Auth identity claim for representative accounts.
- The first release should label the output `recommended_email` or `primary_mail`, not `review_robin_login_email`.

A separate, carefully reviewed migration tool could later use the CSV to reconcile Review Robin accounts, but is out of scope here.

## 9. Hosting, authentication and deployment

- **Development:** Public RRW monorepo only; **no app code changes** in the private Cordware repository.
- **Production:** Cordware's private importer copies allowlisted runtime code from an approved RRW SHA; private Cordware owns Azure deployment and NUS-specific environment details.
- **Code/package proposal:** `utilityapps/` with `main.py`, `email_check/` and minimal shared UI/templates. Keep prose in `utilityapps/docs/` (excluded from production import). Do not create `tools/` as the application package.
- **Mount:** Registry entry `utilities` at `/utilities`, landing page title **Cordware Utilities**. Health endpoint `/utilities/health` must be added to Easy Auth excluded paths and documented in the private Cordware setup; all other routes remain authenticated.
- **Independence:** `CORDWARE_APPS=utilities` starts the utility alone with Cordware locally and in tests; it must not import `app` (Review Robin) or `residentialapps` business modules or use their database URLs.
- **App-selection:** Add `utilities` to private `deployment/apps.toml` only when the first deployment is authorized; no assumption that it is enabled immediately.
- **Importer:** Add the new top-level `utilityapps` path in the private allowlist, bump the rules version, and verify imports. The current allowlist fails closed for unknown top-level paths.
- **Stack:** Existing FastAPI/Jinja, shared design tokens and navigation patterns, no frontend framework. No application database is required for v1.
- **Local and CI:** A fake Graph client with deterministic fixtures; never use real NUS directory data in public tests or fixtures. Explicit real-tenant testing follows completion of Easy Auth.

## 10. Privacy, security and operational behavior

- **Authentication:** Only accept Cordware-trusted Easy Auth identities; no client-supplied claims or manually entered Graph tokens. V1 authorization is restricted to platform super-admins.
- **Delegated Graph token:** Use the current operator's delegated access token supplied through the configured Easy Auth token store/integration. No application-only directory permissions, stored refresh tokens, or new client secrets.
- **Data handling:** Process uploads transiently; do not save input or result CSVs to PostgreSQL, SharePoint, Azure Blob, server filesystem, or application logs. Return the result as an immediate authenticated download, with no public file URL.
- **Log hygiene:** Structured metadata may include actor, timestamp, number of rows, lookup counts and failure codes; **never** log uploaded addresses, names, full Entra IDs, tokens or CSV contents.
- **Controls:** HTTPS, security headers, upload-size/row limits, CSRF protection, no-cache/no-store on results, no content in error traces, and escaping of all displayed or exported untrusted data.
- **Graph outages and throttling:** Honor `Retry-After` for HTTP 429; use bounded retries/backoff for transient errors, mark unresolved attempts `ERROR`, and make the export available for rows that did complete. Do not turn a failed lookup into a false `NOT_FOUND`.
- **Concurrency:** Dedupe lookups within the file and use conservative bounded concurrency; no background worker or persistent job queue in v1.
- **Administrative telemetry:** Report aggregate counts but do not retain personnel-level lookup history. If a stronger audit requirement is subsequently adopted, define minimal retention and storage separately rather than casually retaining CSVs.

## 11. User-interface requirements

A plain, accessible interface:

1. **Utilities landing:** title and one card/link, **Email Address Checker**.
2. **Upload screen:** short purpose statement; CSV upload; email-column selection only when necessary; preview of total, valid, blank/invalid and duplicate input rows.
3. **Check action:** explicit start button, progress/processing state, clear explanation when Graph access is not configured.
4. **Result screen:** aggregate counts by status; alias coverage clearly shown; a short caveat that `NOT_FOUND` is not a mail-deliverability test; a single **Download checked CSV** action.
5. **Download:** file name such as `email-check-results-YYYYMMDD.csv`; no page containing the full directory results is required.

Do not imply the tool is checking login readiness, entitlement or institutional employment/student status.

## 12. Minimum acceptance tests

1. CSV with standard `email` column yields an output containing every input row in original order and all original columns.
2. A selectable nonstandard address column works without changing the other columns.
3. A primary `mail` match returns `OK`, Entra ID, UPN and primary email.
4. A UPN match with different nonnull `mail` returns `USE_PRIMARY` and both values.
5. An alias resolves to a unique user only when the alias feature is enabled and the tenant probe has succeeded; otherwise the result is marked with basic-only coverage.
6. Different aliases resolving to one Entra user are flagged as one duplicate-account group; repeated identical rows do not create an alias-related group.
7. A missing user returns `NOT_FOUND` with coverage information, never an assertion that email is undeliverable.
8. Graph HTTP 401/403/429/5xx, expired tokens and network failures do not produce `NOT_FOUND`; failed rows are `ERROR`.
9. Multiple different users returned for one address produce `AMBIGUOUS`, not an arbitrary suggestion.
10. Blank/malformed addresses are `INVALID_INPUT`, retained and not queried.
11. Unauthorized users cannot access the form, run lookup requests or download results.
12. Uploaded or returned data never reaches databases, logs or publicly accessible URLs; spreadsheet formula injection is prevented.
13. `/utilities/health` is independent of Graph and signed-out accessible once configured; the rest of the mount requires authentication.
14. `CORDWARE_APPS=utilities` starts independently; GET crawl, mount-path tests, import boundary tests and existing CI lanes all pass.
15. Local development uses fake Graph responses; deployment performs a real-tenant smoke test only after final Easy Auth configuration.

## 13. Implementation sequence and proof-of-concept gate

**Phase 0 — Validate live Graph capability.** After the pending Web App-side Easy Auth UAMI/FIC assertion wiring and interactive Graph-token validation, test a small set of **real, authorized test accounts** using (i) UPN, (ii) primary `mail`, and (iii) known secondary SMTP aliases. Record whether each lookup works under the actual delegated `User.ReadBasic.All` token and whether aliases can be queried without additional consent. Validate the actual Easy Auth email claim used by Review Robin. Do not record identifiable test data in the public repository.

**Phase 1 — Build minimum checker.** In RRW, add `utilityapps/` with one Utilities mount, one email-check tool, CSV upload/parser, primary-mail/UPN Graph queries, output and duplicate detection; tests and CI. Alias checks may remain disabled.

**Phase 2 — Alias support if permitted.** Enable verified alias matching, otherwise retain basic-only mode with honest status labeling. If additional permissions are necessary, decide separately whether the marginal value justifies asking IT for broader delegated access.

**Phase 3 — Controlled deployment.** Update private Cordware importer allowlist and app selection, import approved RRW code, add `/utilities/health` to Easy Auth exclusions, validate protected UI and actual Graph calls, then permit authorized operators to use it. The production runner's GitHub Actions artifact-egress dependency must be resolved for the intended release workflow.

## 14. Dependencies and reference sources

- Private Cordware: `docs/cordware_azure_progress_runner_2026-10-29.md` — public HTTPS working, delegated `User.ReadBasic.All` and `Mail.Send` consent complete; Easy Auth final managed-identity assertion wiring still pending; runner artifact storage egress still pending.
- Private Cordware: `spec/cordware_setup.md`, `spec/importer.md`, `tools/import_rules.toml`, `deployment/apps.toml` — mounted applications, protected health exclusions, allowlisted imports and app selection.
- Public RRW: `cordware/main.py`, `cordware/identity.py`, `residentialapps/guide/todo_master.md` — registry, actual identity claim extraction, application independence and development conventions.
- Microsoft Graph: [List users](https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0); [user resource, including `mail`/`proxyAddresses`](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0); [advanced directory queries](https://learn.microsoft.com/en-us/graph/aad-advanced-queries); [throttling guidance](https://learn.microsoft.com/en-us/graph/throttling).

## 15. Decisions left open

Only two decisions materially change the v1 implementation:

1. **Alias capability:** Does the actual tenant and delegated token allow an exact secondary-alias query, or is broader consent necessary? Resolve through Phase 0, not assumption.
2. **Operator scope:** V1 defaults to platform super-admin only. Extend to explicitly designated Utility operators later only if operationally needed and after choosing how those grants are governed and audited.

The cluster name, mount, output fields and no-database posture above are recommendations for adoption, not previously approved RRW/Cordware rulings.
