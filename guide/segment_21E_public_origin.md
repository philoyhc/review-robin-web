# Segment 21E — The public origin

**Opened:** 2026-10-30 · **Theme:** the host rewrites each request's scheme and host to a configured public origin, so every URL an application builds from the request names the address users reach · **Related:** `guide/archive/segment_21D_prefix_flip.md` (open question 1: "the request's own host"), `guide/deferred_consolidated.md` ("The request host behind the institutional gateway"), `cordware/spec/host.md`

## Opportunity

21D ruled that absolute URLs take the request's own host, and left the gateway's host header for stage 4 to check. Stage 4 has now checked it, in Cordware's private deployment record. The institutional gateway sends the applications the App Service's own host name; only Easy Auth reads the original from `X-Original-Host`. The app server also ignores App Service's `X-Forwarded-Proto`, so the scheme the applications see is `http`. Every URL built from the request therefore names a private backend over `http`. There are two kinds:

- **Invitation links.** There are six `request.url_for("reviewer_invite", …)` calls. Scheduled invitations are observed on page load (`observe_scheduled_events_on_load`), so they take the same path.
- **Framework redirects.** A URL missing its trailing slash gets a `307` whose `Location` is absolute and built from the request: `GET /x` with `Host: backend` answers `Location: http://backend/x/` (checked 2026-10-30). Sixteen routes end in a slash, across RRW, Residential and Utilities.

The deployment's choice (Cordware's private to-do, item 12) was a custom domain or the host trusting `X-Original-Host`. The author ruled for neither, on 2026-10-30.

## Decision

**A configured public origin, applied by the host to every request.** The new host setting is `CORDWARE_PUBLIC_ORIGIN` (`https://host[:port]`), unset by default. When it is set, a pure-ASGI middleware wrapping the whole host rewrites each `http` scope's `scheme`, `server` and `Host` header to the origin before any route or mount sees it. `request.url_for`, `request.url` and the framework's slash redirects then name the public address with no change in the applications. Unset, nothing changes: local runs and tests keep request-derived URLs.

**No forwarded header is read.** The App Service is reachable only through the gateway, and the origin comes from configuration, so there is nothing to trust or forge.

**Rejected:**
- *Trusting `X-Original-Host` and `X-Forwarded-Proto`, accepted only when they match the configured origin* (a proposal of 2026-10-30). It only ever rewrites to a value the configuration already holds, binds the host to one gateway's headers, and needs forged-header handling for no gain.
- *A custom domain on the App Service.* It is Microsoft's recommended shape, but it needs an IT DNS record, a certificate binding and a gateway change. It still leaves the scheme `http` without `FORWARDED_ALLOW_IPS`, and it cannot help a link built with no request. It stays optional hardening in Cordware's records, not a blocker.
- *Swapping each `url_for` for an origin-based helper.* With the request rewritten, `url_for` is already right, and the redirects can't be reached that way.

## Semantics

- **Validation at startup.** The host refuses to start, naming the setting, when the value:
  - is not `http(s)://host[:port]`;
  - carries a path other than `/`, or a query, fragment or user info;
  - is `http` outside `APP_ENV=local`.

  A trailing `/` is stripped. An empty value counts as unset. Lands in `cordware/spec/host.md`, "Public origin".
- **What changes when set:**
  - `scope["scheme"]` becomes the origin's scheme;
  - `scope["server"]` becomes `(host, port)`, with the port defaulted from the scheme;
  - the `host` header is replaced by the origin's netloc. Every other header passes through as sent, `X-Original-Host` included;
  - `root_path` and `path` are untouched, so mounts and prefixes work as now;
  - non-`http` scopes (`lifespan`) pass through.
- **Where it applies:** on every request: `/health`, the landing page, every mount. A probe that reaches the backend directly sees public-origin URLs in any redirect, which is harmless, since it reads only `/health`.
- **Easy Auth** runs in front of the app and keeps its own `forwardProxy` setting. It never sees the rewrite.
- **Unset is today's behavior,** byte for byte: the middleware is not installed.

## Judgment calls — decided

- The setting lives in `CordwareSettings` (`cordware/main.py`), the host's own, not in the identity settings the applications read. Only the host uses it. If segment 14B's background worker needs it for request-free links, it moves to the platform settings then (recorded in 14B).
- The middleware is installed only when the setting is set, so an unset deployment carries no extra layer.
- A request-free URL helper is not built: no caller exists, because scheduled invitations run on page load.

## Blast radius (measured)

Taken 2026-10-30 at `3427ae4`.

| What | Count | Command |
|---|---|---|
| `url_for("reviewer_invite")` call sites | 6 | `grep -rn 'url_for("reviewer_invite"' app --include=*.py \| grep -v '``'` |
| Routes ending in `/` (each with a slash redirect) | 16 | `grep -rhoE '@(router\|app)\.(get\|post)\(\s*"[^"]*/"' app cordware residentialapps utilityapps --include=*.py \| wc -l` |
| Host settings | 2 (`cordware_apps`, `log_level`) | `grep -n "class CordwareSettings" -A6 cordware/main.py` |
| Host middleware today | 0 | `grep -n "add_middleware" cordware/main.py` |
| Tests pinning absolute URLs | 1 file (`tests/integration/test_mount_requirements.py`, requirement 4) | `grep -rln "Requirement 4" tests` |

## PR ladder

1. **This plan**, with its queue entry. Prose only.
2. **The setting, the middleware and the tests.**
   - Lands in `cordware/main.py`:
     - the `public_origin` field and its validation;
     - the startup refusal;
     - the middleware, installed outermost when set.
   - Tests in `cordware/tests/test_host.py`:
     - unset changes nothing;
     - set, `/health`, the landing page and a mount see the origin;
     - a slash redirect's `Location` is the origin;
     - a forged `Host` or `X-Original-Host` changes nothing;
     - each invalid value refuses to start;
     - `http` is allowed only locally.
   - `tests/integration/test_mount_requirements.py` requirement 4 gains the set case: an invitation link carries the origin and `/reviewrobin` whatever `Host` is sent.
   - Docs: `cordware/spec/host.md`, `spec/settings_inventory.md`, `.env.example` (commented).
   - Must not touch the applications. This is the last build rung, so `diff-reviewer` reads it.
3. **Close.**
   - `spec-writer` on the doc-impact specs.
   - `spec/architecture.md`: absolute URLs now come from the public origin when one is set.
   - The deferred entry is retired, and the plan is archived.

**Cordware's side**, in its own PR on the author's word: item 12 is closed by this ruling, and the custom domain is recorded as optional hardening. `CORDWARE_PUBLIC_ORIGIN` joins plan B3's release App Settings, and B3's invitation-link check already tests it at the first release. The value lives only there, never in this repository.

## Definition of done

- With `CORDWARE_PUBLIC_ORIGIN` set, a slash redirect and an invitation link under `/reviewrobin` both name the origin, whatever `Host` is sent (tests).
- Unset, every existing test passes unchanged.
- An invalid value refuses to start, naming the setting (tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 21E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- None open. The custom domain is the deployment's optional hardening (Cordware); a request-free link builder is 14B's when its worker lands.

## Out of scope

- A custom domain, `FORWARDED_ALLOW_IPS`, and the production value: Cordware's.
- Request-free link building for a background worker: segment 14B.
- Any change to the applications' URL helpers (`app/web/urls.py` and its Residential and Utilities equivalents): they emit paths, which the mount already prefixes.

## Doc impact

- `cordware/spec/host.md` — new "Public origin" section: the setting, its validation, what the middleware rewrites and what it leaves alone (rung 2).
- `spec/settings_inventory.md` — `CORDWARE_PUBLIC_ORIGIN` in §8 beside `CORDWARE_APPS` (rung 2).
- `spec/architecture.md` — absolute URLs come from the configured public origin when set, else the request's host (close).
- `guide/deferred_consolidated.md` — the request-host entry, retired as built (close).
- `guide/segment_14B_email_infrastructure.md` — a background worker's request-free links need the origin moved to the platform settings (close). <!-- cites: guide/segment_14B_email_infrastructure.md -->
- `guide/todo_master.md` — the queue entry, deleted at close.
