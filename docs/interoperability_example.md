# The interoperability example: Utilities' Interop proof of concept

**Status:** adopted 2026-11-11 (author: "interop-poc becomes the example
code for interoperability"). Built in segments 23A–23C
(`guide/archive/segment_23A_interop_poc.md`,
`guide/archive/segment_23B_interop_return.md`,
`guide/archive/segment_23C_diagnostic_status.md`) and verified on the
production host.

**What it is.** Utilities' *Interop proof of concept*
(`/utilities/interop-poc/`, package `utilityapps/interop_poc/`) is the
working example of a Cordware application handing work to Review Robin
and reading it back. A real sender — ApplyDesk first — starts from it.
The contract it exercises is `spec/handoffs.md`; the page itself is
specified in `utilityapps/spec/utilities.md` § *Interop proof of
concept*. This document says what to take from it and what not to.

## 1. Where each part lives

| Part | File | Shows |
|---|---|---|
| The page and its gate | `utilityapps/interop_poc/routes.py` | One GET, super-admin only, every response `no-store` |
| The bundle | `utilityapps/interop_poc/mock.py` | Rosters in Review Robin's own CSV formats; an application ID as the reviewee's opaque key; a profile link per application |
| The create and the reads | `utilityapps/templates/interop_poc/page.html` | The browser-side flow below, in two inline scripts |
| The sender's tests | `utilityapps/tests/test_interop_poc.py` | What the page must keep doing |
| Review Robin's side | `app/web/routes_operator/_handoffs.py`, `app/services/handoffs.py`, `app/web/views/_handoffs.py`, `tests/integration/test_handoffs.py` | The receiving routes and their tests |

## 2. What a sender copies

**The create** (`spec/handoffs.md` §1–§7):

- **One origin, the operator's own sign-in.** The browser posts
  same-origin JSON with the operator's session; there is no
  server-to-server call and no cross-app credential.
- **The holding tab.** A tab is opened *during* the click (so no
  pop-up blocker refuses it), then sent to the receipt's Session Home;
  if the browser blocked it, the page shows the link instead.
- **`redirect: "manual"`.** A sign-in redirect reads as `not_authorized`
  rather than as a page of HTML the sender cannot parse.
- **One transfer, retried until it lands.** A fresh `transfer_id` per
  click; on a `5xx`, no answer, an unreadable answer or
  `transfer_in_progress` the *same* transfer is sent again, so a retry
  finds the session already made rather than making a second.
- **Refusals by code**, each named for the operator, with the issue
  lines of an `invalid_setup`.

**The reads back** (`spec/handoffs.md` §10):

- **Pull, not push.** The sender asks Review Robin, as its operator,
  when the operator looks; Review Robin holds no address of the sender.
- **Status by version.** It checks `status_schema_version` and shows
  *unavailable* for one it does not read, never a misread.
- **Results, then completion, one after the other**, so a refused
  `results.csv` costs no second request. Each CSV carries an `ETag`; a
  sender that keeps it can send `If-None-Match` and get a `304` for an
  unchanged one (the example does not).
- **A failed read shows *Unavailable, last checked …*** and why — never
  old numbers or zero.
- **Text by `textContent` only**: everything Review Robin returns is
  data.

## 3. What a sender does not copy

- **The mock.** Synthetic `example.edu` people and `applydesk.invalid`
  links stand in for the sender's own records.
- **`localStorage` as the record of what was sent.** The example has no
  database; a real sender stores each `transfer_id` with its own record,
  so the link survives another browser.
- **The super-admin gate.** A real sender gates on its own operators;
  Review Robin still checks, on every call, that the person operates the
  session.
- **The provisional paths.** `/operator/handoffs/…` is the proof of
  concept's; ApplyDesk's segment settles the final routes
  (`guide/interoperability.md` §4).

## 4. Keeping it current

**A change to the handoff contract updates the example in the same
change**: a route, a code, a bundle field, or a status or CSV shape in
`spec/handoffs.md` lands with the page and `utilityapps/tests/
test_interop_poc.py` following it, so the example never teaches a
contract Review Robin no longer offers. Nothing checks this yet; it is
queued in `docs/unenforced_conventions.md` §2.4.
