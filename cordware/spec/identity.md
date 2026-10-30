# Cordware identity

The contract of the trusted identity Cordware supplies to every mounted
application. Design and rationale are in
`docs/archive/cordware_repository_strategy_v0.8.md` §3; the host's startup, guard and
log events are in `cordware/spec/host.md`. This file states what an
application can rely on.

Cordware is the only reader of Azure Easy Auth's `X-MS-CLIENT-PRINCIPAL*`
headers and the only source of the fake local identity. It decides **who the
request is from**. Each application maps that to its own users and
permissions; nothing here decides what anyone may do. The module is
`cordware/identity.py`; its settings are `cordware/settings.py`.

RRW re-exports it under its own names in `app/auth/identity.py`
(`spec/architecture.md`).

## `Identity`

A frozen dataclass.

| Field | Meaning |
|---|---|
| `principal_id` | The provider's stable id for the account (Entra object id), or `None`. |
| `email` | As the provider gave it, not normalized, or `None`. |
| `name` | Display name, or `None`. |
| `provider` | The identity provider, or `None`; `"fake"` on the fake identity. |
| `is_fake` | `True` only on the fake identity. Default `False`. |
| `tenant_id` | The account's directory tenant (Entra `tid`), or `None`. |
| `upn` | The account's user principal name, as the provider gave it, or `None`. |
| `mail` | The account's primary email, as the provider gave it, or `None`. Never the UPN standing in for it. |
| `resolved_with` | The `IdentitySettings` passed to `resolve_identity`, or `None`. Not part of equality or `repr`: two resolutions of one principal are the same identity. |

`tenant_id`, `upn` and `mail` are for an application that matches a roster
on first sign-in and then binds on the tenant and the Entra object ID:
Residential tries the UPN and the primary email as separate candidates, so
neither may stand in for the other
(`residentialapps/docs/residentialapps_email_identity_matching.md`).
`principal_id` is the object ID whenever `X-MS-CLIENT-PRINCIPAL-ID` or an
object-ID claim is present, which Easy Auth sends for Entra; its last
fallback, `sub`, is a per-application identifier, not the object ID, so an
application binding on it should hold out for one of the others.
`email` is unchanged: the one address RRW and the super-admin list read, by
its own order below, in which `preferred_username` (often the UPN) comes
before the `email` claim. All three new fields default to `None`, so an
`Identity` built without them is as before.

Computed properties, never stored:

- `display_label` is `name`, else `email`, else `""`.
- `is_super_admin` is `is_super_admin_email(email)`.
- `super_admin_configured` is `super_admin_configured()`.

Both role properties read `resolved_with` when it is set, else the host's
settings. The flag, the predicate and `super_admin_configured` therefore agree
by construction, and an identity built by hand answers as a resolved one
would.

## Resolution

- **`get_identity(request)`** is the only dependency. It takes the request and
  nothing else, and calls `resolve_identity(request)`. FastAPI reads every
  parameter of a dependency from the request, so a settings parameter would
  become an optional body and a caller could post
  `{"allow_fake_auth": true}`. A test pins the signature to `request` alone.
- **`resolve_identity(request, settings=None)`** is the same resolution with
  an `IdentitySettings` passed in, for tests. **Never a dependency.** With
  `settings` given, the identity returned carries them as `resolved_with`.
- **`current_identity(request, settings=None)`** runs steps 1 and 2 below
  and returns `None` where step 3 would refuse: no 401, no count, no
  `identity.headers_missing` (`identity.header_malformed` is still logged,
  as on every request). `resolve_identity` calls it, so the two cannot
  diverge. For a page that shows who is signed in without requiring it
  (the host's landing page, `cordware/spec/host.md`).

Resolution order:

1. Easy Auth headers present: the identity parsed from them (below).
2. Else, if `ALLOW_FAKE_AUTH` is on: the fake identity.
3. Else a **401** `Not authenticated` (`HTTPException`), and the request is
   counted as missing headers (Logging).

Easy Auth headers win over the fake identity when both could apply. Whether the
identity is *enough* for an application (RRW answers 401 when there is no
email) is the application's rule.

## Easy Auth headers

Headers count as present when any of `X-MS-CLIENT-PRINCIPAL-NAME`,
`X-MS-CLIENT-PRINCIPAL-ID` or `X-MS-CLIENT-PRINCIPAL` is non-empty
(`X-MS-CLIENT-PRINCIPAL-IDP` alone does not).

`X-MS-CLIENT-PRINCIPAL` is base64 (strict) of JSON text, an object with a
`claims` list of `{typ, val}` objects. The text is read as `json.loads` reads
bytes: UTF-8, a UTF-8 BOM, or the UTF-16 / UTF-32 it detects. A value that is
not base64, not decodable JSON, or not a JSON object is malformed, as is one
past Python's integer-digit or nesting limits: the header contributes
nothing and `identity.header_malformed` is logged. An object without a
`claims` list is not malformed; it contributes no claims, and a non-empty
string `auth_typ` (or else `identityProvider`) still names the provider.
Entries of `claims` that are not objects with a non-empty string `val` are
skipped.

A claim is chosen by the **order of the types listed below**, not the token's
own claim order; within one type the first non-empty value wins. Each field
takes the first source that has a value:

| Field | Sources, in order |
|---|---|
| `email` | claim `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`, `preferred_username`, `email`, each counting only when non-empty after strip; then `X-MS-CLIENT-PRINCIPAL-NAME` if it contains `@` |
| `name` | claim `name`, `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name`; then `X-MS-CLIENT-PRINCIPAL-NAME` if it has no `@` and no claim gave an email |
| `principal_id` | `X-MS-CLIENT-PRINCIPAL-ID`; then claim `http://schemas.microsoft.com/identity/claims/objectidentifier`, `oid`, `sub`; the header and each claim counting only when non-empty after strip |
| `provider` | `X-MS-CLIENT-PRINCIPAL-IDP`; then the payload's `auth_typ`, then `identityProvider` |
| `tenant_id` | claim `http://schemas.microsoft.com/identity/claims/tenantid`, `tid` |
| `upn` | claim `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn`, `upn`, then `preferred_username` (usually the UPN in Entra's v2 tokens when no `upn` claim is issued, though it may be another username; v1's `unique_name` is not read) |
| `mail` | claim `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`, `email`; never `preferred_username` or `X-MS-CLIENT-PRINCIPAL-NAME` |

`tenant_id`, `upn` and `mail` come from `X-MS-CLIENT-PRINCIPAL` alone, each
claim counting only when non-empty after strip. With the simple headers only,
all three are `None`. Which claims a deployment's tokens carry is a fact of
the deployment. On the institutional one (2026-10-30, Cordware's private
progress report): `emailaddress` carries the mail and `preferred_username`
the sign-in name, which differ there; `tenantid` is present; there is no
`upn` claim. So `email` and `mail` are the mail address, `upn` is the sign-in
name, and `tenant_id` is set.

A malformed `X-MS-CLIENT-PRINCIPAL` with none of the simple headers still
counts as headers present: the result is an `Identity` with every field
`None`, not the fake identity and not a 401 here. The application then
refuses it for want of an email.

`decode_client_principal(request)` returns the decoded payload object, or
`None` when the header is absent or malformed (nothing is logged).
`extract_claims(request)` returns its claims as `{"typ", "val"}` string pairs
in token order, `[]` when there are none. Both are for diagnostic pages.

## The fake identity

`principal_id`, `email` and `name` from `FAKE_AUTH_PRINCIPAL_ID`,
`FAKE_AUTH_EMAIL` and `FAKE_AUTH_NAME`; `tenant_id` from
`FAKE_AUTH_TENANT_ID` (`None` when blank); `upn` and `mail` from `FAKE_AUTH_UPN` and
`FAKE_AUTH_MAIL`, each the fake email when blank, so one setting serves the
usual case and either can be set apart to try an alias; `provider="fake"`;
`is_fake=True`.
`is_fake` is set nowhere else, so an application may key local-only
behavior off it alone. The host's guard confines fake auth to
`APP_ENV=local` (`cordware/spec/host.md` "Fake-auth guard"), so `is_fake` is
never true in a deployed environment.

## Host-level reads

Valid outside a request. Each takes an optional `IdentitySettings`, else reads
the host's.

| Name | Returns |
|---|---|
| `fake_auth()` | `FakeAuth(enabled, email)`: `ALLOW_FAKE_AUTH` and `FAKE_AUTH_EMAIL`. |
| `app_env()` | `APP_ENV`. |
| `is_local()` | `app_env() == "local"`. |
| `super_admin_emails()` | The effective super-admin list: a tuple, normalized. |
| `super_admin_configured()` | Whether that list is non-empty. |
| `is_super_admin_email(email)` | Whether `email` is in that list. `None` or blank never is. |

`missing_header_count()` returns the requests this process has refused for want
of headers.

### Email comparison

`strip()` then `str.lower()`; deliberately not `casefold`. This is the rule
RRW's `normalize_email` states (`app/services/email_identity.py`). Cordware
cannot import an application, so it keeps its own copy, and a test beside
`normalize_email`'s own pins the two equal on that file's cases
(`tests/unit/test_email_identity_fold.py`).

### The effective super-admin list

`SUPER_ADMIN_EMAILS`, plus `FAKE_AUTH_EMAIL` while both `ALLOW_FAKE_AUTH` and
`FAKE_AUTH_SUPER_ADMIN` are on. Entries are normalized and de-duplicated in
order; a blank entry never counts, the fake email included, so a blank
`FAKE_AUTH_EMAIL` adds nothing. Local fake auth with `SUPER_ADMIN_EMAILS`
empty therefore has a non-empty list while the fold-in is on, and an
application's "no super-admin" fallback stays off.

Super-admin is a **platform role**: Cordware asserts it, every application
reads it the same way, and nothing in-app can change it.

## Settings

`IdentitySettings` (`cordware/settings.py`), read once at import into
`identity_settings`, from the `.env` in the working directory (the repository
root, the file RRW uses); a shell value overrides the file; unknown keys in
the file are ignored. It is separate from the host's `CordwareSettings` because
applications import identity and never the entry point (`cordware/spec/host.md`
"Import boundary").

| Setting | Default | Meaning |
|---|---|---|
| `APP_ENV` | `local` | The deployment's environment. Only `local` permits fake auth. |
| `ALLOW_FAKE_AUTH` | `false` | Whether a request without Easy Auth headers is the fake identity. |
| `FAKE_AUTH_PRINCIPAL_ID` | `local-dev` | The fake identity's `principal_id`. |
| `FAKE_AUTH_EMAIL` | `operator@example.edu` | The fake identity's `email`. |
| `FAKE_AUTH_NAME` | `Local Operator` | The fake identity's `name`. |
| `FAKE_AUTH_TENANT_ID` | `local-tenant` | The fake identity's `tenant_id`. |
| `FAKE_AUTH_UPN` | empty | The fake identity's `upn`; blank is `FAKE_AUTH_EMAIL`. |
| `FAKE_AUTH_MAIL` | empty | The fake identity's `mail`; blank is `FAKE_AUTH_EMAIL`. |
| `FAKE_AUTH_SUPER_ADMIN` | `true` | Whether the fake email joins the effective super-admin list while fake auth is on. |
| `SUPER_ADMIN_EMAILS` | empty | Comma-separated emails (not JSON), trimmed, empty items dropped. Set only by the deployer. Compared with `email`, so list each account's mail address, not its sign-in name where the two differ. |

Every setting can be set per run (`$env:NAME=…` or `export NAME=…`) over
`.env`. The inventory entry for each is `spec/settings_inventory.md` §8.

## Logging

Logger `cordware.identity`, `extra["event"]`; the shape of a record is
`cordware/spec/host.md` "Logging". The host's identity events
(`identity.fake_auth_refused`, `identity.fake_auth_enabled`,
`super_admin.unconfigured`) are listed there.

| Event | Level | When |
|---|---|---|
| `identity.header_malformed` | warning | **Every time** an `X-MS-CLIENT-PRINCIPAL` header is malformed (§ Easy Auth headers). The fact only, never the header's contents. |
| `identity.headers_missing` | warning | **Once per process**, on the first request refused for want of headers. |

With fake auth off every unauthenticated probe is a request without headers, so
the later ones are counted, not logged. The running count is read by
`missing_header_count()` and carried as `missing_identity_headers` on the
host's `host.stopping` line. The counter and the once-only check share a lock,
because FastAPI runs a plain-function dependency on a worker thread.

## Graph

`cordware/graph.py`: Microsoft Graph as the signed-in user, with the
delegated token Easy Auth's token store keeps for them. The host owns the
token, so it owns the one client every application uses. Built for the
Email Address Checker (Utilities segment U1, rung 4); directory lookups
only.

- **Which directory.** `directory_for(request, settings=None)` returns
  `FakeDirectory` on a local run with fake auth on. Otherwise it returns
  `GraphDirectory` with the token Easy Auth passes in
  `X-MS-TOKEN-AAD-ACCESS-TOKEN`; with none (the token store off, or the
  sign-in not asking for Graph) it raises `GraphError("no_token")`.
- **`find_users(address)`** sends one `GET /v1.0/users` with
  `$filter=mail eq '…' or userPrincipalName eq '…'` (an OData literal, a
  quote doubled), `$select=id,displayName,mail,userPrincipalName` and
  `$top=5`, and returns each match as a `DirectoryUser`; an empty `mail`
  is `None`. More than one match is the caller's to judge.
- **A failure is never an empty answer.** It is a `GraphError` whose
  `kind` is `no_token`, `unauthorized` (`401`), `forbidden` (`403`),
  `throttled` (`429`), `server` (`5xx`), `network` or `bad_response`. A
  `429` waits its `Retry-After`, up to 30 s, and a `5xx` or network
  failure waits 1 s then 2 s: at most two retries, then the error. `401`
  and `403` are raised at once.
- **The fake directory** is a fixed set of invented `example.edu`
  accounts, one per case a caller must handle: a UPN that is not the
  mail, an account with no mail, and an address that is one account's
  mail and another's UPN. Three addresses fail on purpose
  (`throttled@`, `outage@`, `denied@`). It is never real data.
- **No dependency.** Requests go through the standard library;
  `GraphDirectory` takes the transport as a parameter, so the tests never
  touch the network.
- **Logging.** Logger `cordware.graph`: `graph.request_failed`, a
  warning carrying `kind` and `status` only, never the address, the
  query or the token.

Not yet proved from application code: a call through the Web App's
egress, and the token's refresh once it expires (about an hour). Both
are Cordware's private deployment checks.

## Tests

`cordware/tests/test_graph.py` covers the Graph helper: the query, each
failure and its retries, the log line, the fake directory and
`directory_for`. `cordware/tests/test_identity.py` covers the parser, the fake identity, every
switch set per run, the dependency's signature, the guard, the log events and
the super-admin reads. RRW's suite keeps exercising the re-export
(`tests/integration/test_setup_template_download.py` passes settings to
`resolve_current_user`; `tests/unit/test_roles_super_admin.py` covers the
super-admin reads through `app/auth/roles.py`).
