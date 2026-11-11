# Cordware Utilities

The Email Address Checker's contract is `utilityapps/spec/email_check.md`.

The contract of the Utilities application as the Cordware host sees it.
The host's side is `cordware/spec/host.md`; this file states only what
Utilities adds. The design it follows is
`utilityapps/docs/email_address_checker_functional_spec_v0.1.md` §1 and §9.

## One application, one mount

| | Utilities |
|---|---|
| Registry name | `utilities` |
| Mount path | `/utilities` |
| Factory | `utilityapps.main:create_app` |
| Logger prefix | `utilityapps` |
| Landing-page title | `Utilities` |
| Health | `GET /utilities/health`, route name `utilities_health` |

- The registry lists it last, after Residential's two, so an unset
  `CORDWARE_APPS` mounts it last and the landing page lists it so.
- The factory is a zero-argument callable returning a new `FastAPI`
  application with no schema pages. It reads no setting and opens no
  database: Utilities has none (spec §9).
- Each tool is a feature module inside this one application. A tool with
  a materially different trust boundary becomes its own mount instead.

## Health

`/utilities/health` answers `{"status": "ok"}` with no identity, no
setting and no Graph call, so Easy Auth can exclude it from sign-in, as it
does the other applications' probes. Cordware's deployment excluded it on
2026-10-30, ahead of the first release.

## Pages

| Page | Path | Reached by |
|---|---|---|
| Index | `/` (the bare mount) | Anyone Easy Auth lets in: the route checks no identity itself, since it names tools and holds nothing about anyone. Each tool gates its own routes. |
| Email Address Checker | `/email-check/` and the steps it posts to | The platform super-admin only (`utilityapps/spec/email_check.md` "Access") |
| Telegram egress probe | `/diagnostics/telegram-egress`, and `…/run` it posts to | The platform super-admin only. Not on the index: an operator diagnostic, not a tool |
| Interop proof of concept | `/interop-poc/` | The platform super-admin only. Not on the index: a working model for the next application that hands work to Review Robin |

The index lists one card per tool, linking to its first page. Every page
links back to the host's landing page (`/`) and to `/.auth/logout`.

## Telegram egress probe

A temporary diagnostic (`utilityapps/docs/cordware_telegram_egress_probe_handover_v0.1.md`):
can this App Service reach `api.telegram.org:443`? Removed when Telegram
Test replaces it.

- **`GET`** explains and offers **Run probe**; it sends nothing.
- **`POST …/run`** sends one `GET` to Telegram's `getMe` with a fixed,
  invalid token: no retry, redirects not followed, certificates and host
  names verified, each socket operation held to 3 s, the whole attempt
  (DNS included) to 7 s, at most 4 KiB read. Nothing in the request comes
  from the caller.
- **The pass** is Telegram's own error envelope (`ok` false, `error_code`
  equal to the HTTP status), whatever the status: `TELEGRAM_REACHABLE`.
  Any other answer, a proxy refusing the tunnel included, is
  `HTTP_INTERMEDIARY_OR_UNEXPECTED`; a failure is
  `DNS_FAILURE`, `CONNECT_TIMEOUT`, `READ_TIMEOUT`, `TLS_FAILURE`,
  `NETWORK_ERROR` or `OTHER_ERROR`, shown without its detail.
- **Shown:** the outcome, HTTP status, whether the envelope matched (with
  Telegram's description, cut to 80 printable characters), elapsed ms, the
  time in UTC and SGT, a correlation ID and one line of guidance.
- **Logged:** outcome, status, elapsed ms, on a failure the exception's
  class (and the class urllib wrapped in it) with its errno, never its
  message, and correlation ID. Nothing is kept.
- **Spacing:** one run at a time, at least 30 s apart across the process;
  sooner is a `429` page. Every response is `no-store`.
- **Cross-site posts:** the host's `SameSite=Lax` sign-in cookie, as every
  Cordware form (`docs/security_posture.md`, "CSRF posture"), so no token:
  that is a platform property no in-app test can show. No Easy Auth
  exclusion: the probe is behind sign-in like every other page.
- **No feature flag:** Utilities reads no setting (above), and the
  super-admin gate is the access control.

## Interop proof of concept

Segment 23A (`guide/archive/segment_23A_interop_poc.md`): one click
creates a populated Review Robin draft session and opens its Session
Home in a new tab. Review Robin's side is `spec/handoffs.md`. Kept as a
model once ApplyDesk's handoff exists (author, 2026-11-11).

- **The mock** (`utilityapps/interop_poc/mock.py`): *Mock Scholarship
  2027*, three synthetic `example.edu` reviewers plus the signed-in
  super-admin, and six applications whose IDs are the reviewees' opaque
  `RevieweeEmail` keys, each with a placeholder `ProfileLink`
  (`applydesk.invalid`). Shown on the page as the two CSVs it sends.
- **The bundle** sits in the page as JSON; the script adds a fresh
  `transfer_id` and a `POC-<YYMMDD-HHMMSS>` code per transfer.
- **Create in Review Robin** opens the holding tab during the click,
  posts with `redirect: "manual"` (a non-operator's `303` reads as
  `not_authorized`), then moves the tab to the receipt's Session Home, or
  shows the link when the tab was blocked.
- **A refusal** closes the tab and names the error, with the slot,
  reason and issue lines of an `invalid_setup`, and the draft's link on
  a `transfer_incomplete`; the next click is a new transfer. **A `5xx`,
  no answer, an answer it cannot read, or `transfer_in_progress`** keeps the transfer, so trying
  again finds a session already made.
- Text is inserted with `textContent` only; every response is `no-store`.
- **Sent to Review Robin** (segment 23B): the sessions this browser
  created, kept in `localStorage` (Utilities has no database; clearing it
  forgets the list, not the sessions). Each offers:
  - **Refresh status**: reads Review Robin's status (`spec/handoffs.md`
    §10) and shows the state and counts with their denominators; a failed
    read shows *Unavailable, last checked …* and why, never old counts or
    zero.
  - **Fetch results**: reads `results.csv`, then `completion.csv`, shows
    the answers in a table and offers both downloads. A refused
    `results.csv` fetches no `completion.csv`.

Templates write app paths through `url()` in `utilityapps/web.py`, which
adds the mount's prefix; `host_url()` marks a path that is the host's.

## Import boundaries

Enforced by `cordware/tests/test_import_boundary.py`:

- `utilityapps` imports neither `app` (Review Robin) nor `residentialapps`,
  and neither of them imports it. It may import `cordware`, never
  `cordware.main`, except in `utilityapps/tests/`, which builds the host.
- `cordware` imports it only through the registry's factory string.
