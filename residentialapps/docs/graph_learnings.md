# Microsoft Graph: what Residential Apps can take from RRW and Utilities

**Status:** learning notes, 2026-11-01. They come from building and
deploying the Email Address Checker and RRW's directory features on the
institutional host. They are not a spec: the contracts are
`cordware/spec/identity.md` ("Graph"), `utilityapps/spec/email_check.md`
and `guide/email_and_scheduling.md`. The institution's resource names stay
in Cordware's private records.

## 1. Use the host's client; don't write another

- **`cordware/graph.py` is the one Graph client.** `directory_for(request)`
  returns the directory as the signed-in user sees it: Graph with their
  delegated token, or a fixed fake directory on a local fake-auth run.
- **Calling Graph:** Easy Auth puts the user's token in the
  `X-MS-TOKEN-AAD-ACCESS-TOKEN` header. The client sends it, and it never
  logs it.
- **Its lookups** cover the most common case, an address checked
  against the directory:
  - `find_users` matches `mail` or `userPrincipalName` exactly;
  - `search_users` matches by prefix, for a picker;
  - `look_up_all` runs a batch, four at a time, within a time budget;
  - `classify` turns each result into an outcome.

  Residential's roster import and Support Logs' student lookups should
  reuse these, as RRW's roster upload does.
- **A failure is never an empty answer.** A `GraphError` carries a
  `kind`: `no_token`, `unauthorized`, `forbidden`, `throttled`, `server`,
  `network` or `bad_response`. Treat "could not ask" as unknown, never as
  "nobody there". Support Logs' "Not matched to a student" must not be
  shown for a lookup that failed.
- **The local fake directory** has one invented account for each awkward
  case, plus addresses that fail on purpose (`throttled@`, `outage@` and
  `denied@`, each at `example.edu`). Use them in tests and browser checks.

## 2. Addresses: sign-in name, mail and aliases

- **The sign-in name (UPN) may not be the email address.** Never assume
  the two are the same, or that one can be derived from the other. Easy
  Auth's `emailaddress` claim is the mail, so admin lists and roster
  emails should hold mail addresses, and a match should try both the mail
  and the UPN.
- **Look a user up by mail with `$filter=mail eq '…'`.** `GET
  /users/{mail}` answers "not found"; only the UPN or the object ID works
  in the path.
- **Aliases are not visible.** `User.ReadBasic.All` cannot see secondary
  addresses, so an alias-only address comes back `NOT_FOUND`. The
  Email Address Checker marks this `BASIC_ONLY`.
  `residentialapps_email_identity_matching.md` already handles it:
  exact UPN or mail only, with an administrator correcting the rest.
- **Store the directory object ID at the first good lookup**, as RRW's
  roster rows do (`directory_object_id`), so later matches don't rest on
  an address that can change.

## 3. The token lasts about an hour, and the browser renews it

- **Expiry:** Easy Auth's Graph token expires after about an hour. Pages
  still load after that, because Easy Auth's own sign-in lasts longer.
  Only Graph calls fail, with `unauthorized`.
- **`/.auth/refresh` renews it**, using the refresh token Easy Auth keeps.
  That works even after the access token has expired, because the
  sign-in asks for `offline_access`. It was proved by hand on
  2026-11-01. Only the browser can call it, since it needs the Easy Auth
  cookie.
- **Use the shared script.** RRW's and Utilities' base templates both
  carry `<script data-graph-renewal>`:
  - it renews in the background once 45 minutes have passed;
  - it exposes `window.cordwareRenewGraph()` for a renew-and-retry.

  When Residential has a page that calls Graph, copy the block into
  Residential's base template unchanged. Add that template to
  `cordware/tests/test_graph_renewal.py`, which holds the copies equal.
  They share one `localStorage` key, so a renewal in any app serves all
  of them.
- **What renewal doesn't cover:** a POST from a page left open past
  expiry. Its server-side lookups can still fail `unauthorized`. A
  picker's `fetch` can renew and retry; a plain form POST can't. Say
  "reload, then try again" rather than "sign out".

## 4. Email: who can send, and how

- **What's granted** (read 2026-11-01): delegated `Mail.Send` and
  `User.ReadBasic.All`, with tenant-wide consent, and **no application
  permission**.
- **So mail goes out only as the signed-in user**, through `POST
  /me/sendMail` with their token. That was proved from the Web App:
  `202`, and the mail was delivered. Sent mail appears in that user's
  Sent Items.
- **Nothing can send on a clock yet.** A scheduled reminder or a
  notice to RAs, sent with nobody signed in, needs a shared mailbox under
  an application `Mail.Send` permission. IT would scope that to the one
  mailbox with an Exchange access policy. RRW's
  `guide/email_and_scheduling.md`, choice 2, asks the same question.
  Until IT grants it, clock mail can only wait for an operator.
- **SMTP is out.** Institutional tenants typically block basic SMTP
  AUTH under MFA. RRW is retiring its per-operator SMTP settings
  (`guide/email_and_scheduling.md`, "Narrowed").
- **RRW sends no mail itself yet.** Its Graph transport is still a stub,
  so Residential should not assume a shared email service exists to
  call.

## 5. Limits worth designing around

- **Request time:** the gateway allows 120 s per request, inside App
  Service's fixed 230 s. Keep each request's lookups well inside that.
  The checker batches at 60 s for this reason.
- **Throttling:** Graph answers `429` with `Retry-After`. The client
  waits up to 30 s, and `look_up_all` runs four lookups at a time. A
  large roster is better checked in batches than in one request.
- **One process:** the host runs as one instance with one `uvicorn`
  process and Always On. A background loop, such as a clock for
  reminders, would run exactly once today. It still needs a lock in case
  the plan scales out.
- **Logs:** the server's output, Graph failures included (event
  `graph.request_failed`, carrying the kind and status but never the
  address), can be queried in the host's Log Analytics workspace as
  `AppServiceConsoleLogs`.
