# Segment U1 — Utilities: the Email Address Checker

**Opened:** 2026-10-30 · **Theme:** the `utilityapps/` package mounted at `/utilities`, with the Email Address Checker built on fake Graph, ready for a real-tenant smoke test · **Related:** `utilityapps/docs/email_address_checker_functional_spec_v0.1.md` (the functional spec; "the spec" below), `cordware/spec/identity.md` "Graph" (the shared Graph helper this segment builds; its deferred entry retired at rung 4)

## Opportunity

Lists of institutional addresses mix a person's sign-in name, primary mail
and aliases, so one person can show up as two reviewers or two roster rows.
Production sign-ins have confirmed that the two forms differ: the mail
claim is the mail address and `preferred_username` is the sign-in name
(`cordware/spec/identity.md`). Nothing in Cordware can show an operator
which addresses in a list belong to the same account. Delegated Graph is now
proved from Cloud Shell, with a lookup by mail needing `$filter=mail eq`
(Cordware's private progress report, 2026-10-30), but no application
calls it yet. The checker would be the first.

## Decision

**Build phase 1 of the spec (§13) in RRW, against a fake directory.**
U1 lands the package and mount, then the checker itself: CSV in, primary
mail and UPN lookups, classification, duplicate groups, and CSV out. It
also builds the **shared Graph helper in `cordware/`**, which the
deferred entry said would wait until the first of its three users was
built; the checker is that first user. Alias lookup (spec phase 2) stays
off, so every run reports `lookup_coverage=BASIC_ONLY`. The spec's phases
0 and 3, the real-tenant probe and deployment, belong to Cordware's
private side.

**No server state between steps.** The preview page carries the
uploaded CSV back in a hidden field (at most 1 MiB). The check's POST
renders the summary page with the result CSV embedded as a download.
The server never holds a file, so it has nothing to store, expire or
leak, as the spec's §10 requires.

**Rejected:**
- *A per-application Graph client in `utilityapps/`*: the deferred entry
  rules out one client per application, and Residential's identity
  matching and RA Leave's `Mail.Send` would each copy it.
- *An in-memory result cache keyed for the download*: it is state that
  breaks with more than one worker.
- *Re-running the lookups on download*: it doubles the Graph calls and
  can return a different answer than the summary showed.

## Semantics

- **Input** (spec §4, landing in `utilityapps/spec/`):
  - BOM-tolerant UTF-8. The `email` column is matched case-insensitively;
    if there is no such column, the operator picks one from the header.
  - Lookup keys are the address stripped and lowercased; the cell itself
    is never rewritten.
  - Blank or malformed addresses become `INVALID_INPUT` and are never
    queried. Exact repeats are counted in the preview and looked up once.
  - A file over 500 rows or 1 MiB is rejected whole, with a message.
    So are a header-only file, a file with no header, and a non-CSV file.
- **Lookup:**
  - One query per distinct key: `$filter=mail eq '…' or
    userPrincipalName eq '…'`, OData-escaped, selecting `id`,
    `displayName`, `mail` and `userPrincipalName`.
  - `match_type` comes from which returned field equals the key.
  - Two or more objects in the result make the row `AMBIGUOUS`.
- **Failure is never absence:**
  - A 401, 403, 429 after its retries, a 5xx, a timeout or a missing
    token makes the row `ERROR`, never `NOT_FOUND` (spec §6, test 8).
  - A 429's `Retry-After` is honored, with at most two retries.
  - The export still carries the rows that completed.
- **Output columns:**
  - The input's columns come first, in order. The spec's nine result
    columns follow.
  - A name that collides with an input column takes a `check_` prefix.
  - A cell starting with `=`, `+`, `-`, `@`, a tab or a carriage return
    gets a leading `'` (spec §4).
- **Duplicate groups:** resolved rows are grouped by object ID. A group
  is numbered only when it holds two or more distinct keys (spec §7).
  Repeats of one address never form a group.
- **Access:**
  - Super-admin only, through `Identity.is_super_admin`. Anyone else
    signed in gets a plain `403`.
  - `/utilities/health` answers signed out.
  - Result pages are `no-store`.
  - Logs carry counts and failure codes only (spec §10).

## Judgment calls — decided

- Segment ID `U1`: a utilities `1A` would collide with Residential's in `tools/close_check/`, which reports a plan name found in two trees as ambiguous.
- CSRF follows RRW's posture, Easy Auth plus `SameSite=Lax` (`docs/security_posture.md` "CSRF posture"), not form tokens. The spec's §4 is revised to say so at close.
- One `or` query rather than two: it halves the calls. The real-tenant smoke test confirms it, and splitting into two queries is a one-function change.
- The landing page's Utilities link comes from the registry, as every mount's does; the landing page is not edited.
- A utilities-only PR runs the `full` lane, which errs toward running more; a utilities lane can wait until a second tool exists.
- The fake directory is a fixture of invented `example.edu` accounts, built in code and never read from a file of real data (spec §9).
- 2026-10-30, rung 3: a cell over the `csv` module's 131,072-character limit is refused by name, not by raising the limit, which is process-wide and which RRW's importers rely on (Codex, `#3409`).
- 2026-10-30, rung 4: requests go through `urllib`, not `httpx`, which is only a dev dependency; adding it would change the deploy manifest for one client.
- 2026-10-30, rung 4: the fake directory follows fake auth (a local run with it on), so the helper adds no setting.

## Blast radius (measured)

Taken 2026-10-30 at `7ebad71`.

| What | Count | Command |
|---|---|---|
| Utilities code today | 0 (2 prose files) | `git ls-files utilityapps` |
| Registry entries | 3; one added | `grep -c "AppEntry(" cordware/main.py` |
| Import-boundary rules | 3 packages; `utilityapps` added to each | `grep -n '"app"\|"residentialapps"\|"cordware"' cordware/tests/test_import_boundary.py` |
| Packaging | `app*`, `cordware*`, `residentialapps*` | `grep -n include pyproject.toml` |
| Tests that build the host or read the registry | 10 files | `grep -rln "REGISTRY\|CORDWARE_APPS" cordware/tests residentialapps/tests tests` |
| Python already naming `utilityapps` | 8 lines (CI lanes, close check, their tests) | `grep -rn utilityapps --include=*.py .` |
| Graph clients in code | 0 | `grep -rln "graph.microsoft.com" app cordware residentialapps` |

## PR ladder

1. **Package and mount.**
   - Lands: the `utilityapps` package with `create_app`,
     `/utilities/health`, and a Utilities index with one card. Also its
     registry entry, packaging, boundary rules both ways, mount tests,
     and `utilityapps/spec/` drafted.
   - Must not touch: the checker, or Graph.
   - Base SHA recorded in the PR body.
2. **Scaffold.**
   - Lands: the upload, preview and result pages as static placeholders,
     with real copy and inert controls, plus `utilityapps/guide/` browser
     checks for the author.
   - Must not touch: CSV handling.
3. **CSV in and out.**
   - Lands: the parser, column choice, limits, the preview wired to it,
     and the output writer with prefixing and the formula guard. All of
     it is pure functions, tested without Graph.
4. **The Graph helper in `cordware/`.**
   - Lands: a client protocol; the Easy Auth delegated-token client,
     which reads the token header, escapes, retries and maps errors; and
     the fake directory used in local runs and tests. Tested on httpx's
     mock transport.
   - Also lands `cordware/spec/identity.md`'s section naming the helper.
   - Must not touch: Residential.
5. **Check and download.**
   - Lands: classification, duplicate groups, and the result page with
     the embedded CSV. Also the `403`, `no-store`, and the log-hygiene
     tests.
   - This is the last build rung, so `diff-reviewer` reads the
     cumulative diff from rung 1's base here.
6. **Close.**

Cordware's side follows separately, on the author's word:
- the import rule for `utilityapps` changes from `exclude` to runtime
  code;
- `deployment/apps.toml` gains the app;
- `/utilities/health` joins the Easy Auth exclusions;
- the real-tenant smoke test, which is the spec's phase 0 for this
  checker.

## Definition of done

- `CORDWARE_APPS=utilities` starts the app alone, and also alongside RRW and Residential. `/utilities/health` answers `200` signed out.
- The spec's acceptance tests 1–4 and 6–14 each have a test. Test 5 is the coverage label; test 15 is the author's smoke test.
- `cordware/tests/test_import_boundary.py` passes with `utilityapps` in every rule.
- `## Doc impact` section present and current
- `python3 tools/close_check.py U1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **An expired token:** Easy Auth's access token lasts about an hour, and only the browser can call `/.auth/refresh`. Should the check page call it before posting, or just show "sign in again" on a `401`? The real-tenant smoke test decides; until then the `401` message is built.
- **Alias lookup (spec §15.1):** Cordware's phase 0 probe decides it; U1 builds none of it.
- **Operator scope (spec §15.2):** super-admin only, as the spec proposes. Reopens only on demonstrated need.

## Out of scope

- Alias lookup, which is spec phase 2: a later item, if the probe allows it.
- Cordware's import rules, app selection, Easy Auth exclusions and deployment: the private repository.
- Moving Residential's identity matching or RA Leave's sending onto the helper: each does so when it is built.
- Any write to RRW, Residential or Entra data (spec §2).

## Doc impact

- `utilityapps/spec/email_check.md` — new: the input, lookup, classification and output contract, from the spec's §§4–7 as built (rungs 1–5).
- `utilityapps/docs/email_address_checker_functional_spec_v0.1.md` — revised to say what was decided: CSRF posture, the single query, no server state (at close).
- `utilityapps/spec/utilities.md` — new: the mount, health, index and import boundaries (rung 1).
- `utilityapps/README.md` — the package layout and the mount (rung 1).
- `cordware/spec/host.md` — the `utilities` registry entry and its health path (rung 1).
- `cordware/spec/identity.md` — the Graph helper: token source, errors, the fake directory (rung 4).
- `guide/deferred_consolidated.md` — the shared Graph helper entry, retired as built (rung 4).
- `spec/settings_inventory.md` — any setting the helper or the checker adds (rungs 4–5).
